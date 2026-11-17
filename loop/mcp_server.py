"""MCP stdio server for deterministic page checks, plus Engine.run.

Speak newline-delimited JSON-RPC on stdout. Logs stay off that stream.
Cursor config (run from the repository root):

    {
      "mcpServers": {
        "loop-check": {
          "command": "python",
          "args": ["-m", "loop.mcp_server"]
        }
      }
    }
"""

from __future__ import annotations

import json
import sys
from typing import BinaryIO

from loop.actions import ActionError
from loop.checks import PageProbe, replay_file, spec_destination

PROTOCOL = "2024-11-05"
SERVER_INFO = {"name": "loop-check", "version": "0.1.0"}
INSTRUCTIONS = (
    "Each check has a start and an end. The start is a blank page, or a url passed to "
    "open_url, check_page, or run_loop. The end is the assertion that passes or fails: "
    "url, title, and text for check_page, or Engine.run finishing done or failed for run_loop. "
    "open_url, reload, check_page, console_errors, failed_requests, and run_saved_test never call a model. "
    "check_page fails when a console.error or a failed request (including a 404 asset) was collected during the load. "
    "run_loop is Engine.run. It is the only tool that may call a model, and only when planner is model."
)


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


TOOLS = [
    {
        "name": "open_url",
        "description": (
            "Start of a check: open this url (http, https, file, or a path relative to the repo). "
            "End: the load has finished. Returns the final url and title, plus console_errors and "
            "failed_requests collected during the load with page console and requestfailed listeners. "
            "No assertion and no model call. A blank start is not this tool; omit start_url on check_page."
        ),
        "inputSchema": _schema(
            {"url": {"type": "string", "description": "Page to open. This is the check start."}},
            ["url"],
        ),
    },
    {
        "name": "check_page",
        "description": (
            "Deterministic pass/fail check. Start: start_url when it is set, otherwise the current page "
            "(blank, about:blank, when nothing has been opened). End: the url, title, and text assertions. "
            "Each assertion passes or fails on its own. The check also fails when the load recorded a "
            "console.error or a failed request, including a 404 asset. Returns JSON with ok, console_errors, "
            "and failed_requests. Aimed at http://localhost:3000 with a 5 second navigation timeout. "
            "Never calls a model. save writes a passing spec to tests/replay/<name>.json and is skipped when the check fails."
        ),
        "inputSchema": _schema(
            {
                "start_url": {
                    "type": "string",
                    "description": "Check start. Omit or leave empty to keep the current page, including a blank page.",
                },
                "url": {"type": "string", "description": "End assertion: the page url must contain this text."},
                "title": {"type": "string", "description": "End assertion: the document title must contain this text."},
                "text": {"type": "string", "description": "End assertion: the page body must contain this text."},
                "save": {
                    "type": "string",
                    "description": "File name under tests/replay. Written only when the check passes.",
                },
            },
            [],
        ),
    },
    {
        "name": "reload",
        "description": (
            "Start: the current page. End: the same page after reload. Collects console_errors and "
            "failed_requests for this load. No assertion and no model call."
        ),
        "inputSchema": _schema({}, []),
    },
    {
        "name": "console_errors",
        "description": (
            "Console errors collected during the latest load (page console events whose type is error). "
            "The load start was the url passed to open_url, reload, or check_page, or a blank page. "
            "These errors are part of the check end: a non-empty list fails check_page. "
            "Read-only. No model call."
        ),
        "inputSchema": _schema({}, []),
    },
    {
        "name": "failed_requests",
        "description": (
            "Requests that failed during the latest load (page requestfailed, or an HTTP 404 asset). "
            "The load start was the url passed to open_url, reload, or check_page, or a blank page. "
            "These failures are part of the check end: a non-empty list fails check_page. "
            "Read-only. No model call."
        ),
        "inputSchema": _schema({}, []),
    },
    {
        "name": "run_loop",
        "description": (
            "Run the existing browser loop (Engine.run) when the check is not a simple url, title, or text "
            "assertion. Start: blank (the current page) or start_url. End: the loop finishes done, or fails "
            "on its assertion or an action error. This is the only tool that may call a model, and only when "
            "planner is model. planner fake makes zero model calls and needs no API key."
        ),
        "inputSchema": _schema(
            {
                "task": {"type": "string", "description": "What the loop should do."},
                "start_url": {
                    "type": "string",
                    "description": "Check start. Omit or leave empty for a blank current page.",
                },
                "planner": {
                    "type": "string",
                    "enum": ["fake", "model"],
                    "description": "fake never calls a model. model may call the router.",
                },
            },
            ["task"],
        ),
    },
    {
        "name": "run_saved_test",
        "description": (
            "Replay a check_page spec from tests/replay. Start and end are the url and the assertions stored "
            "in that JSON file. The spec passes or fails with the same rules as check_page. Zero model calls."
        ),
        "inputSchema": _schema(
            {
                "file": {
                    "type": "string",
                    "description": "tests/replay/<name>.json, or the file name alone.",
                }
            },
            ["file"],
        ),
    },
]


class ToolServer:
    """Holds one browser for the life of the MCP process."""

    def __init__(self, session: PageProbe | None = None):
        self.session = session
        self._owns_session = session is None

    def close(self) -> None:
        if self._owns_session and self.session is not None:
            self.session.close()
            self.session = None

    def session_open(self) -> PageProbe:
        if self.session is None:
            self.session = PageProbe()
            self.session.open()
            self._owns_session = True
        return self.session

    def call(self, name: str, arguments: dict | None) -> dict:
        args = arguments or {}
        if not isinstance(args, dict):
            raise ActionError("tool arguments must be an object")
        page = self.session_open()
        if name == "open_url":
            return page.open_url(_required_str(args, "url"))
        if name == "check_page":
            return page.check_page(
                start_url=args.get("start_url"),
                url=args.get("url"),
                title=args.get("title"),
                text=args.get("text"),
                save=args.get("save"),
            )
        if name == "reload":
            return page.reload()
        if name == "console_errors":
            return page.console_errors()
        if name == "failed_requests":
            return page.failed_requests()
        if name == "run_loop":
            from loop.run_tool import run_loop

            return run_loop(
                page,
                task=_required_str(args, "task"),
                start_url=args.get("start_url"),
                planner=args.get("planner") or "fake",
            )
        if name == "run_saved_test":
            file = _required_str(args, "file")
            path = spec_destination(file) if _basename_only(file) else _repo_spec(file)
            return replay_file(path, probe=page)
        raise ActionError(f"unknown tool: {name}")


def handle(server: ToolServer, message: dict) -> dict | None:
    """Return a JSON-RPC response, or None for a notification."""
    if not isinstance(message, dict):
        return _error(None, -32600, "Invalid Request")
    method = message.get("method")
    has_id = "id" in message
    msg_id = message.get("id") if has_id else None
    if not isinstance(method, str):
        if has_id:
            return _error(msg_id, -32600, "Invalid Request")
        return None
    if not has_id:
        return None
    params = message.get("params") or {}
    try:
        if method == "initialize":
            version = PROTOCOL
            if isinstance(params, dict):
                requested = params.get("protocolVersion")
                if isinstance(requested, str) and requested:
                    version = requested
            return _result(
                msg_id,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                    "instructions": INSTRUCTIONS,
                },
            )
        if method == "ping":
            return _result(msg_id, {})
        if method == "tools/list":
            return _result(msg_id, {"tools": TOOLS})
        if method == "resources/list":
            return _result(msg_id, {"resources": []})
        if method == "prompts/list":
            return _result(msg_id, {"prompts": []})
        if method == "tools/call":
            if not isinstance(params, dict):
                return _error(msg_id, -32602, "Invalid params")
            name = params.get("name")
            if not isinstance(name, str) or not name:
                return _error(msg_id, -32602, "Invalid params")
            arguments = params.get("arguments") or {}
            try:
                payload = server.call(name, arguments)
            except ActionError as exc:
                return _result(msg_id, _tool_error(str(exc)))
            return _result(msg_id, _tool_ok(payload))
    except ActionError as exc:
        return _error(msg_id, -32602, str(exc))
    except Exception as exc:
        return _error(msg_id, -32603, _short(exc))
    return _error(msg_id, -32601, f"Method not found: {method}")


def serve(
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    server: ToolServer | None = None,
) -> None:
    incoming = stdin if stdin is not None else sys.stdin.buffer
    outgoing = stdout if stdout is not None else sys.stdout.buffer
    tool_server = server or ToolServer()
    try:
        while True:
            try:
                message = read_message(incoming)
            except json.JSONDecodeError:
                write_message(outgoing, _error(None, -32700, "Parse error"))
                continue
            if message is None:
                return
            response = handle(tool_server, message)
            if response is not None:
                write_message(outgoing, response)
    finally:
        tool_server.close()


def read_message(stdin: BinaryIO) -> dict | None:
    while True:
        line = stdin.readline()
        if line == b"":
            return None
        if not line.strip():
            continue
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip() or b"0")
            while True:
                extra = stdin.readline()
                if extra in (b"\r\n", b"\n", b""):
                    break
                if extra.lower().startswith(b"content-length:"):
                    length = int(extra.split(b":", 1)[1].strip() or b"0")
            payload = stdin.read(length)
            if not payload:
                return None
            data = json.loads(payload.decode())
        else:
            data = json.loads(line.decode())
        if isinstance(data, dict):
            return data
        raise json.JSONDecodeError("expected an object", line.decode(errors="replace"), 0)


def write_message(stdout: BinaryIO, payload: dict) -> None:
    stdout.write(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
    stdout.flush()


def main() -> int:
    serve()
    return 0


def _required_str(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ActionError(f"{key} must be a non-empty string")
    return value


def _basename_only(file: str) -> bool:
    text = file.strip()
    return "/" not in text and "\\" not in text


def _repo_spec(file: str):
    from loop.checks import REPO_ROOT

    text = file.strip()
    if text.startswith(("/", "\\")):
        raise ActionError("spec path must stay inside the repository")
    path = (REPO_ROOT / text).resolve()
    root = REPO_ROOT.resolve()
    if path != root and root not in path.parents:
        raise ActionError("spec path must stay inside the repository")
    if path.suffix != ".json":
        raise ActionError("spec must be a .json file")
    if not path.is_file():
        raise ActionError(f"spec not found: {file}")
    return path


def _tool_ok(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False}


def _tool_error(message: str) -> dict:
    body = {"ok": False, "error": message, "model_calls": 0}
    return {"content": [{"type": "text", "text": json.dumps(body)}], "isError": True}


def _result(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _short(exc: Exception) -> str:
    return str(exc).split("\n", 1)[0][:300]


if __name__ == "__main__":
    raise SystemExit(main())
