"""Live-browser smoke for the tip stack. No Claude call.

Opens the packing fixture in real Chrome twice:

1. The proxy's fast_act script path (settle, then a compact diff).
2. The local Stagehand run tool (snapshot/run, same 500ms settle).

A box that has ANTHROPIC_API_KEY can drive the outer model with:

    ANTHROPIC_API_KEY=... python -m bench.run --arm stagehand --fixtures-only --max-steps 8
    ANTHROPIC_API_KEY=... python -m bench.run --arm diff_fast_act --fixtures-only --max-steps 8
    ANTHROPIC_API_KEY=... python -m bench.probe --execute

This module does not read the key and does not call Anthropic. It reads, by
name only: SETTLE_QUIET_MS, SETTLE_TIMEOUT_MS, PLAYWRIGHT_MCP_PROXY_CHILD.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bench.stagehand_local import StagehandLocalClient
from proxy.child import NdjsonChild

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "loop" / "fixture"
SCRIPT = (
    'page.getByRole("textbox", { name: "Item" }).fill("milk")\n'
    'page.getByRole("button", { name: "Add" }).click()'
)


def _serve_fixture() -> tuple[ThreadingHTTPServer, str]:
    """Playwright MCP blocks file://. The fixture is served on localhost."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(FIXTURE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/packing.html"
    return server, url


def _child_argv() -> list[str]:
    """Proxy child command. --isolated only; 0.0.84 rejects --user-data-dir with it."""
    override = os.environ.get("PLAYWRIGHT_MCP_PROXY_CHILD", "").strip()
    if override:
        import shlex

        return shlex.split(override, posix=(os.name != "nt"))
    return [
        "npx",
        "@playwright/mcp@0.0.84",
        "--isolated",
        "--headless",
        "--browser",
        "chrome",
        "--snapshot-mode",
        "none",
    ]


async def smoke_proxy(url: str) -> dict:
    argv = _child_argv()
    child = NdjsonChild(argv)
    from proxy.segment import dispatch

    await child.start()
    try:
        result = await dispatch(
            child,
            "fast_act",
            {"task": "Add milk to the packing list", "url": url, "script": SCRIPT},
        )
        text = result["content"][0]["text"]
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"summary": text[:300], "ok": False}
        return {
            "path": "proxy-fast_act-script",
            "ok": bool(payload.get("ok")),
            "status": payload.get("status"),
            "tier": payload.get("tier"),
            "settle": payload.get("settle"),
            "diff_present": bool(payload.get("diff")),
            "diff_chars": payload.get("diff_chars"),
            "full_snapshot_chars": payload.get("full_snapshot_chars"),
            "actions": payload.get("actions"),
            "summary": payload.get("summary"),
            "model_calls": payload.get("model_calls"),
        }
    finally:
        await child.stop()


async def smoke_stagehand(url: str) -> dict:
    client = StagehandLocalClient(headless=True)
    await client.start()
    try:
        opened, _ms = await client.call_tool("run", {"code": f"page.goto({json.dumps(url)})"})
        ran, _ms = await client.call_tool("run", {"code": SCRIPT})
        shot, _ms = await client.call_tool("snapshot", {})
        body = await client._page.evaluate("() => document.body.innerText")
        return {
            "path": "stagehand-local-run",
            "backend": client.backend,
            "goto_settle": "settle:" in opened,
            "run_ok": "run failed" not in ran and "fill Item" in ran and "click Add" in ran,
            "settle": "quiet" if "settle: quiet" in ran else ("timeout" if "settle: timeout" in ran else ""),
            "diff_present": "diff_chars:" in ran,
            "snapshot_present": "full_snapshot_chars:" in shot,
            "page_contains_milk": isinstance(body, str) and "milk" in body.casefold(),
            "run_excerpt": ran[:500],
        }
    finally:
        await client.stop()


async def main() -> int:
    server, url = _serve_fixture()
    report: dict = {"anthropic": "not called", "fixture": url}
    try:
        try:
            report["proxy"] = await smoke_proxy(url)
        except Exception as exc:
            report["proxy"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        try:
            report["stagehand"] = await smoke_stagehand(url)
        except Exception as exc:
            report["stagehand"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        server.shutdown()
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    proxy_ok = isinstance(report["proxy"], dict) and report["proxy"].get("ok") is True
    stagehand_ok = isinstance(report["stagehand"], dict) and report["stagehand"].get("run_ok") is True
    return 0 if proxy_ok or stagehand_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
