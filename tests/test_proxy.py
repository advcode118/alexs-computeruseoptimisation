"""The proxy starts, lists the child's tools, and forwards a call unchanged.

No API key and no network. A local process stands in for @playwright/mcp.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

from proxy.child import DEFAULT_CHILD_ARGV, PLAYWRIGHT_MCP_VERSION

REPO = Path(__file__).resolve().parents[1]

CHILD_TOOLS = [
    {
        "name": "browser_navigate",
        "description": "Navigate to a URL",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Absolute URL"}},
            "required": ["url"],
        },
    },
    {
        "name": "browser_click",
        "description": "Click a ref",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "element": {"type": "string"},
            },
            "required": ["target"],
        },
    },
]


def _child_script() -> str:
    tools = json.dumps(CHILD_TOOLS)
    return textwrap.dedent(
        f"""\
        import json
        import os
        import sys

        TRACE = os.environ["PROXY_CHILD_TRACE"]
        TOOLS = json.loads({tools!r})

        def emit(payload):
            sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\\n")
            sys.stdout.flush()

        def record(line):
            with open(TRACE, "a", encoding="utf-8") as handle:
                handle.write(line if line.endswith("\\n") else line + "\\n")
                handle.flush()

        while True:
            line = sys.stdin.readline()
            if line == "":
                break
            record(line)
            if not line.strip() or line.lstrip()[:1] not in "{{[":
                continue
            message = json.loads(line)
            if "method" not in message:
                continue
            method = message["method"]
            if method == "initialize":
                emit({{
                    "jsonrpc": "2.0",
                    "method": "notifications/message",
                    "params": {{"level": "info", "data": "boot"}},
                }})
                sys.stdout.write("Content-Length: 999\\r\\n")
                sys.stdout.flush()
                emit({{
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {{
                        "protocolVersion": "2024-11-05",
                        "capabilities": {{"tools": {{"listChanged": False}}}},
                        "serverInfo": {{"name": "playwright", "version": "0.0.84"}},
                    }},
                }})
            elif method == "notifications/initialized":
                pass
            elif method == "tools/list":
                emit({{"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}})
                emit({{"jsonrpc": "2.0", "id": "from-child", "method": "roots/list"}})
                emit({{
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {{"tools": TOOLS}},
                }})
            elif method == "tools/call":
                emit({{
                    "jsonrpc": "2.0",
                    "method": "notifications/progress",
                    "params": {{"progressToken": "1", "progress": 1}},
                }})
                params = message.get("params") or {{}}
                emit({{
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {{
                        "content": [{{
                            "type": "text",
                            "text": json.dumps(params, sort_keys=True),
                        }}],
                        "isError": False,
                    }},
                }})
        """
    )


def _read_response(stdout, wanted_id: int, timeout: float) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        ready, _, _ = select.select([stdout], [], [], remaining)
        if not ready:
            break
        line = stdout.readline()
        if not line:
            break
        message = json.loads(line.decode())
        if message.get("id") == wanted_id:
            return message
    raise AssertionError(f"no response for id {wanted_id}")


def test_proxy_lists_tools_without_a_network_key(tmp_path: Path):
    assert PLAYWRIGHT_MCP_VERSION == "0.0.84"
    assert DEFAULT_CHILD_ARGV == [
        "npx",
        "@playwright/mcp@0.0.84",
        "--isolated",
        "--snapshot-mode",
        "none",
    ]

    script = tmp_path / "child.py"
    script.write_text(_child_script(), encoding="utf-8")
    trace = tmp_path / "trace.jsonl"
    env = os.environ.copy()
    for key in ("ANTHROPIC_API_KEY", "NEBIUS_API_KEY", "OPENAI_API_KEY"):
        env.pop(key, None)
    env["PLAYWRIGHT_MCP_PROXY_CHILD"] = f"{sys.executable} {script}"
    env["PROXY_CHILD_TRACE"] = str(trace)

    proc = subprocess.Popen(
        [sys.executable, "-m", "proxy"],
        cwd=REPO,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None
    stderr_parts: list[bytes] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        stderr_parts.append(proc.stderr.read())

    stderr_thread = threading.Thread(target=_drain_stderr)
    stderr_thread.start()
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if proc.poll() is not None:
                stderr_thread.join(timeout=2)
                raise AssertionError(b"".join(stderr_parts).decode(errors="replace"))
            if trace.exists() and '"tools/list"' in trace.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        else:
            stderr_thread.join(timeout=2)
            detail = b"".join(stderr_parts).decode(errors="replace")
            raise AssertionError(detail or "tools/list did not run at startup")

        def send(payload: dict) -> None:
            proc.stdin.write(json.dumps(payload).encode() + b"\n")
            proc.stdin.flush()

        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "proxy-test", "version": "0"},
                },
            }
        )
        initialized = _read_response(proc.stdout, 1, 5)
        assert initialized["result"]["serverInfo"]["name"] == "playwright-mcp-proxy"
        instructions = initialized["result"]["instructions"]
        assert "does not call a model" in instructions
        assert "do_task_segment" in instructions
        assert "fast_act" in instructions
        assert "browser_snapshot" in instructions

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listed = _read_response(proc.stdout, 2, 5)
        tools = listed["result"]["tools"]
        names = [tool["name"] for tool in tools]
        assert names[: len(CHILD_TOOLS)] == [tool["name"] for tool in CHILD_TOOLS]
        assert names[len(CHILD_TOOLS) :] == ["fast_act", "do_task_segment"]
        for tool, expected in zip(tools, CHILD_TOOLS):
            assert tool["description"] == expected["description"]
            assert tool["inputSchema"] == expected["inputSchema"]
        by_name = {tool["name"]: tool for tool in tools}
        for name in ("fast_act", "do_task_segment"):
            text = by_name[name]["description"]
            assert "do_task_segment" in text
            assert "fast_act" in text
            assert "browser_snapshot" in text
            assert "browser_click" in text
            assert "browser_type" in text

        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "browser_navigate",
                    "arguments": {"url": "https://example.com"},
                },
            }
        )
        called = _read_response(proc.stdout, 3, 5)
        forwarded = called["result"]["content"][0]["text"]
        assert called["result"]["content"][0]["type"] == "text"
        assert called["result"].get("isError") is not True
        assert "full_snapshot_chars:" in forwarded
        assert "diff_chars:" in forwarded

        send(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "fast_act",
                    "arguments": {"task": "Add milk to the packing list"},
                },
            }
        )
        acted = _read_response(proc.stdout, 4, 5)
        fast = json.loads(acted["result"]["content"][0]["text"])
        assert fast["needs_model"] is True
        assert fast["tier"] == "planner"
        assert fast["actions"] == []
        assert fast["model_calls"] == 0
        assert acted["result"].get("isError") is not True

        raw = trace.read_text(encoding="utf-8")
        assert "Content-Length" not in raw
        inbound = [json.loads(line) for line in raw.splitlines() if line.strip().startswith("{")]
        methods = [message["method"] for message in inbound if "method" in message]
        assert methods == [
            "initialize",
            "notifications/initialized",
            "tools/list",
            "tools/call",
            "tools/call",
            "tools/call",
            "tools/call",
        ]
        tool_calls = [message for message in inbound if message.get("method") == "tools/call"]
        assert tool_calls[0]["params"]["name"] == "browser_navigate"
        assert tool_calls[0]["params"]["arguments"] == {"url": "https://example.com"}
        assert tool_calls[1]["params"]["name"] == "browser_evaluate"
        assert "MutationObserver" in tool_calls[1]["params"]["arguments"]["function"]
        assert tool_calls[-1]["params"]["name"] == "browser_snapshot"
        assert inbound[0]["params"]["protocolVersion"] == "2024-11-05"
        assert "id" not in inbound[1]
    finally:
        if proc.poll() is None and proc.stdin is not None:
            proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        elif proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        stderr_thread.join(timeout=5)
