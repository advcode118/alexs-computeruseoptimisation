#!/usr/bin/env python3
"""Time whole playwright_mcp probe cells offline: real MCP server, real Chrome, scripted model.

Each cell is bench.probe.run_claude_arm on the packing fixture, served from
localhost because @playwright/mcp blocks file: URLs. The model is a fixed
three-turn script, so no key is read and nothing is spent. The cell time is
what a probe run pays per task (launch, task, teardown); wall_ms is the
graded task interval the probe reports.

    python tools/bench_mcp_teardown.py --cells 10
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bench import harness as bench_harness  # noqa: E402
from bench.probe import run_claude_arm  # noqa: E402

ARM = "playwright_mcp"
_TEXTBOX_REF = re.compile(r"textbox[^\[]*\[ref=([^\]]+)\]")


class ScriptedModel:
    """Snapshot, type the item into the one textbox and submit, then finish."""

    def __init__(self, item: str):
        self.item = item
        self.turn = 0

    async def create_message(self, messages, tools, system=None, **_options):
        self.turn += 1
        if self.turn == 1:
            return _tool_use("browser_snapshot", {}), 0.0
        if self.turn == 2:
            ref = _TEXTBOX_REF.search(json.dumps(messages[-1]))
            if ref is None:
                raise RuntimeError("no textbox ref in the snapshot")
            call = {"target": ref.group(1), "ref": ref.group(1), "text": self.item, "submit": True}
            return _tool_use("browser_type", call), 0.0
        return {"content": [{"type": "text", "text": "TASK_COMPLETE"}], "stop_reason": "end_turn"}, 0.0


def _tool_use(name: str, arguments: dict) -> dict:
    block = {"type": "tool_use", "id": f"call_{name}", "name": name, "input": arguments}
    return {"content": [block], "stop_reason": "tool_use", "usage": {}}


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass


def _mcp_processes() -> int:
    """Live @playwright/mcp server processes on this machine (POSIX only)."""
    try:
        out = subprocess.run(["pgrep", "-fc", r"node .*playwright.mcp"], capture_output=True, text=True)
    except FileNotFoundError:
        return -1
    return int(out.stdout.strip() or 0)


async def _run_cells(cells: int, start_url: str, runs_dir: Path) -> list[dict]:
    setup = bench_harness.BenchmarkHarness.setup

    async def setup_with_scripted_model(self) -> None:
        await setup(self)
        self.anthropic = ScriptedModel("milk")

    bench_harness.BenchmarkHarness.setup = setup_with_scripted_model
    task = {
        "id": "fixture_packing_add",
        "description": "Add 'milk' to the packing list",
        "start_url": start_url,
        "check_text": "milk",
    }
    rows = []
    try:
        for _ in range(cells):
            started = time.perf_counter()
            row = await run_claude_arm(ARM, task, api_key="", headless=True, runs_dir=runs_dir)
            row["cell_ms"] = (time.perf_counter() - started) * 1000
            rows.append(row)
    finally:
        bench_harness.BenchmarkHarness.setup = setup
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cells", type=int, default=10)
    args = parser.parse_args()

    handler = functools.partial(_QuietHandler, directory=str(ROOT / "bench" / "fixture"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    start_url = f"http://127.0.0.1:{server.server_address[1]}/packing.html"

    before = _mcp_processes()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as runs_dir:
        rows = asyncio.run(_run_cells(args.cells, start_url, Path(runs_dir)))
    total_s = time.perf_counter() - started
    leaked = _mcp_processes() - before
    server.shutdown()

    cells = sorted(row["cell_ms"] for row in rows)
    walls = [float(row.get("wall_ms") or 0) for row in rows]
    print(json.dumps({
        "cells": len(rows),
        "passed": sum(1 for row in rows if row.get("success")),
        "steps": sorted({int(row.get("steps") or 0) for row in rows}),
        "reasons": sorted({str(row.get("reason") or "") for row in rows}),
        "total_s": round(total_s, 2),
        "cell_ms_mean": round(statistics.fmean(cells)),
        "cell_ms_median": round(statistics.median(cells)),
        "cell_ms_p90": round(cells[max(0, -(-len(cells) * 9 // 10) - 1)]),
        "task_wall_ms_mean": round(statistics.fmean(walls)),
        "mcp_servers_left_running_before_exit": leaked,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
