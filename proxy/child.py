"""Newline-delimited JSON client for @playwright/mcp 0.0.84.

The child writes one JSON-RPC object per line. A notification has a method
and no id. It is not a response, and this client does not wait for one.
Lines that are not JSON (a Content-Length trace, an npm log) are skipped.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shlex
import shutil
import signal
import sys
from typing import Any

PLAYWRIGHT_MCP_VERSION = "0.0.84"
# --isolated is an in-memory profile, so two arms do not share the
# ~/.cache/ms-playwright lock. @playwright/mcp@0.0.84 rejects --isolated
# together with --user-data-dir. Do not pass both. Do not drop --isolated.
DEFAULT_CHILD_ARGV = [
    "npx",
    f"@playwright/mcp@{PLAYWRIGHT_MCP_VERSION}",
    "--isolated",
    "--snapshot-mode",
    "none",
]
CHILD_ARGV_ENV = "PLAYWRIGHT_MCP_PROXY_CHILD"
MCP_LINE_LIMIT = 16 * 1024 * 1024
_MAX_TOOL_PAGES = 20


class ChildProtocolError(RuntimeError):
    """The child closed or answered with something this proxy cannot forward."""


def child_argv() -> list[str]:
    """Pinned npx command, or PLAYWRIGHT_MCP_PROXY_CHILD when a test sets it.

    The default list is --isolated only. It does not pass --user-data-dir.
    """
    override = os.environ.get(CHILD_ARGV_ENV, "").strip()
    if not override:
        return list(DEFAULT_CHILD_ARGV)
    # POSIX shlex treats backslash as an escape, which deletes Windows paths.
    argv = shlex.split(override, posix=(os.name != "nt"))
    if not argv:
        raise ChildProtocolError(f"{CHILD_ARGV_ENV} is empty")
    return argv


def resolve_child_argv(argv: list[str] | None) -> tuple[list[str], str | None]:
    """Return the child command and a profile directory this process owns.

    An explicit argv is returned unchanged. argv None uses
    PLAYWRIGHT_MCP_PROXY_CHILD when set, otherwise --isolated only.
    The second value stays None: this process does not own a profile directory.
    """
    if argv is not None:
        return list(argv), None
    return child_argv(), None


def encode_ndjson(payload: dict) -> bytes:
    """One JSON-RPC object per line. No Content-Length header."""
    return json.dumps(payload, separators=(",", ":")).encode() + b"\n"


class NdjsonChild:
    """One @playwright/mcp process. tools/list runs once, during start."""

    def __init__(self, argv: list[str] | None = None):
        self.argv, self._owned_profile = resolve_child_argv(argv)
        self.process: asyncio.subprocess.Process | None = None
        self.tools: list[dict[str, Any]] = []
        self._request_id = 0
        self._stderr_task: asyncio.Task | None = None

    async def start(self) -> None:
        env = os.environ.copy()
        # stdin is the JSON-RPC pipe. Never let npx wait on an install prompt.
        env["npm_config_yes"] = "true"
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                limit=MCP_LINE_LIMIT,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            program = self.argv[0] if self.argv else "npx"
            raise ChildProtocolError(f"Could not start {program}. It needs to be on PATH.") from exc
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            await self._initialize()
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        task = self._stderr_task
        self._stderr_task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        process = self.process
        self.process = None
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
        profile = self._owned_profile
        self._owned_profile = None
        if profile:
            shutil.rmtree(profile, ignore_errors=True)

    async def call_tool(self, name: str, arguments: dict | None) -> dict:
        """Forward one tools/call. The child's result object is returned as-is."""
        params: dict[str, Any] = {"name": name}
        if isinstance(arguments, dict):
            params["arguments"] = arguments
        message = await self.request("tools/call", params)
        error = message.get("error")
        if error is not None:
            raise ChildProtocolError(_error_text(error))
        result = message.get("result")
        if not isinstance(result, dict):
            raise ChildProtocolError("tools/call returned no result object")
        return result

    async def request(self, method: str, params: dict | None = None) -> dict:
        self._request_id += 1
        request_id = self._request_id
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            payload["params"] = params
        await self._write(payload)
        return await self._read_response(request_id)

    async def notify(self, method: str, params: dict | None = None) -> None:
        """A notification has no id. There is no response to wait for."""
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        await self._write(payload)

    async def _initialize(self) -> None:
        started = await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "playwright-mcp-proxy", "version": "0.1.0"},
            },
        )
        if started.get("error") is not None:
            raise ChildProtocolError(_error_text(started["error"]))
        await self.notify("notifications/initialized")
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(_MAX_TOOL_PAGES):
            params = {"cursor": cursor} if cursor else None
            listed = await self.request("tools/list", params)
            if listed.get("error") is not None:
                raise ChildProtocolError(_error_text(listed["error"]))
            result = listed.get("result")
            if not isinstance(result, dict):
                raise ChildProtocolError("tools/list returned no result object")
            page = result.get("tools")
            if not isinstance(page, list):
                raise ChildProtocolError("tools/list returned no tools array")
            tools.extend(item for item in page if isinstance(item, dict))
            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                self.tools = tools
                return
            cursor = next_cursor
        raise ChildProtocolError("tools/list did not finish")

    async def _write(self, payload: dict) -> None:
        if self.process is None or self.process.stdin is None:
            raise ChildProtocolError("Playwright MCP child is not running")
        self.process.stdin.write(encode_ndjson(payload))
        await self.process.stdin.drain()

    async def _read_message(self) -> dict:
        if self.process is None or self.process.stdout is None:
            raise ChildProtocolError("Playwright MCP child is not running")
        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise ChildProtocolError("Playwright MCP child ended before answering")
            stripped = line.strip()
            if not stripped or stripped[:1] not in (b"{", b"["):
                continue
            try:
                data = json.loads(stripped.decode())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data

    async def _read_response(self, request_id: int) -> dict:
        """Return the object with this id. Notifications are not that object."""
        while True:
            message = await self._read_message()
            if "method" not in message and message.get("id") == request_id:
                return message
            method = message.get("method")
            child_id = message.get("id")
            if isinstance(method, str) and "id" in message and child_id is not None:
                await self._write(
                    {
                        "jsonrpc": "2.0",
                        "id": child_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    }
                )

    async def _drain_stderr(self) -> None:
        if self.process is None or self.process.stderr is None:
            return
        while True:
            line = await self.process.stderr.readline()
            if not line:
                return
            sys.stderr.buffer.write(line)
            sys.stderr.buffer.flush()


def _error_text(error: object) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return "Playwright MCP child returned an error"
