"""Time script_first's run_script with and without the idle landing wait.

No model call and no spend. `--local` serves loop/fixture over localhost.
`--saved ROWS.jsonl` replays the scripts saved in a probe file against the
live sites and also compares the runtime self-check verdict of both modes.

    python tools/land_wait_bench.py --local --runs 20
    python tools/land_wait_bench.py --runs 3 \
        --saved docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import json
import statistics
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bench.script_first as sf  # noqa: E402

_NEW = sf._may_still_navigate
_CLAIM = (
    "await page.evaluate(() => ({url: location.href, title: document.title, "
    "h1: document.querySelector('h1')?.innerText, key_text: document.title, values: [], answer: document.title}));"
)


def _old(steps) -> bool:
    """The rule before this change: wait unless the script ends on a goto."""
    return bool(steps) and steps[-1].kind != "goto"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        del args


def _local_cases() -> list[dict]:
    handler = functools.partial(_QuietHandler, directory=str(ROOT / "loop" / "fixture"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    return [
        {"id": "goto+evaluate", "task": "", "start_url": base, "code": f"await page.goto('{base}/packing.html');\n{_CLAIM}"},
        {
            "id": "goto+goto+evaluate",
            "task": "",
            "start_url": base,
            "code": f"await page.goto('{base}/broken.html');\nawait page.goto('{base}/packing.html');\n{_CLAIM}",
        },
    ]


def _saved_cases(path: Path) -> list[dict]:
    cases = []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row.get("arm") != "script_first":
            continue
        for index, code in enumerate(row.get("scripts") or []):
            cases.append(
                {
                    "id": f"{row['task_id']}#{index}",
                    "task": row.get("task_description") or "",
                    "start_url": row.get("start_url") or "",
                    "code": code,
                }
            )
    return cases


async def _run(case: dict, mode: str) -> dict:
    sf._may_still_navigate = _old if mode == "before" else _NEW
    client = sf.ScriptFirstClient(headless=True)
    await client.start()
    try:
        text, ms = await client.call_tool("run_script", {"code": case["code"]})
        url = sf._page_url(client._page)
    finally:
        await client.stop()
        sf._may_still_navigate = _NEW
    verdict, _ = sf.script_runtime_verdict(
        text, url, case["start_url"], asks_value=sf.task_asks_value(case["task"]), task=case["task"], earlier=[]
    )
    return {"ms": ms, "verdict": verdict.verdict, "url": url}


def _waits(code: str) -> bool:
    try:
        return _NEW(sf.parse_task_script(code))
    except sf.ScriptError:
        # A script the parser refuses never touches the page in either mode.
        return False


def _p90(values: list[float]) -> float:
    ordered = sorted(values)
    rank = 0.9 * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--saved", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    cases = _local_cases() if args.local or not args.saved else _saved_cases(args.saved)
    rows = []
    for run in range(args.runs):
        for case in cases:
            # Alternate which mode goes first so site caching does not favor one.
            order = ("before", "after") if run % 2 == 0 else ("after", "before")
            pair = {mode: await _run(case, mode) for mode in order}
            rows.append({"id": case["id"], "run": run, "waits_after": _waits(case["code"]), **pair})
    summary = {"scripts": len(cases), "runs": args.runs, "script_runs_per_mode": len(rows)}
    for mode in ("before", "after"):
        times = [row[mode]["ms"] for row in rows]
        summary[f"{mode}_ms"] = {
            "mean": round(statistics.mean(times), 1),
            "median": round(statistics.median(times), 1),
            "p90": round(_p90(times), 1),
        }
    summary["wait_kept_script_runs"] = sum(row["waits_after"] for row in rows)
    summary["verdict_changes"] = [
        {"id": row["id"], "run": row["run"], "before": row["before"]["verdict"], "after": row["after"]["verdict"]}
        for row in rows
        if row["before"]["verdict"] != row["after"]["verdict"]
    ]
    summary["final_url_changes"] = sum(row["before"]["url"] != row["after"]["url"] for row in rows)
    if args.out:
        args.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
