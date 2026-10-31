"""Run tasks through the existing loop and write one log record each.

This module does not know about the hidden split. The scorer passes the task
list in.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from bench.catalog import Task
from bench.checks import evaluate
from bench.rates import RATES, estimate_dollars
from loop.actions import ActionError, PlannerError
from loop.browser import BrowserSession
from loop.engine import Controller, Engine, Log
from loop.planner import make_planner


def run_tasks(tasks: list[Task], *, planner_name: str, out_dir: Path) -> dict:
    session = BrowserSession(headless=True)
    session.open()
    records = []
    try:
        for task in tasks:
            records.append(_run_one(session, task, planner_name))
    finally:
        session.close()
    summary = _summary(records, planner_name)
    summary["out_dir"] = str(out_dir)
    _write(out_dir, records, summary)
    return summary


def _run_one(session: BrowserSession, task: Task, planner_name: str) -> dict:
    page = session.page
    log = Log(echo=False)
    controller = Controller()
    controller.task = task.instruction
    controller.planner_name = planner_name
    controller.mode = "running"
    engine = Engine(session, controller, log, max_cycles=8)
    started = time.perf_counter()
    detail = ""
    try:
        if page is None:
            raise ActionError("The browser is not open.")
        target = task.fixture.resolve().as_uri()
        page.goto(target, wait_until="domcontentloaded")
        engine.planner = make_planner(planner_name, target)
        engine.run()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        success, detail = evaluate(page, task.check)
    except (ActionError, PlannerError, Exception) as exc:
        success = False
        detail = str(exc).split("\n", 1)[0][:300]
    elapsed = time.perf_counter() - started
    planner = engine.planner
    llm_calls = _llm_calls(planner, log)
    input_tokens = int(getattr(planner, "input_tokens", 0) or 0)
    output_tokens = int(getattr(planner, "output_tokens", 0) or 0)
    model = getattr(planner, "model", None) if llm_calls else None
    priced = estimate_dollars(model, input_tokens, output_tokens, llm_calls=llm_calls)
    steps = sum(1 for event in log.snapshot() if event["kind"] == "act")
    cycles = sum(1 for event in log.snapshot() if event["kind"] == "plan")
    return {
        "id": task.id,
        "holdout": task.holdout,
        "success": bool(success),
        "wall_time_s": round(elapsed, 3),
        "steps": steps,
        "planner_cycles": cycles,
        "llm_calls": llm_calls,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        },
        "estimated_dollars": priced["estimated_dollars"],
        "dollars_are": priced["dollars_are"],
        "model": priced["model"],
        "rate_found": priced["rate_found"],
        "planner": planner_name,
        "loop_mode": controller.snapshot()["mode"],
        "check": task.check.get("kind"),
        "check_detail": detail,
    }


def _llm_calls(planner, log: Log) -> int:
    calls = getattr(planner, "calls", None)
    if isinstance(calls, int):
        return calls
    return sum(
        1
        for event in log.snapshot()
        if event["kind"] == "status" and str(event["line"]).startswith("model")
    )


def _summary(records: list[dict], planner_name: str) -> dict:
    passed = sum(1 for record in records if record["success"])
    shown = [{key: value for key, value in record.items() if key != "check_detail"} for record in records]
    return {
        "command": f"python -m bench run --planner {planner_name}",
        "planner": planner_name,
        "api_key_present": bool(os.environ.get("LOOP_API_KEY") or os.environ.get("OPENAI_API_KEY")),
        "dollars_are": "estimate",
        "dollars_note": "estimated_dollars uses the rate table. It is an estimate, not an invoice.",
        "steps_are": "browser actions",
        "rate_table_usd_per_million": RATES,
        "task_count": len(records),
        "holdout_count": sum(1 for record in records if record["holdout"]),
        "passed": passed,
        "failed": len(records) - passed,
        "real_model_runs": [record["id"] for record in records if record["llm_calls"] > 0],
        "tasks": shown,
    }


def _write(out_dir: Path, records: list[dict], summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        (out_dir / f"{record['id']}.json").write_text(
            json.dumps(record, indent=2) + "\n",
            encoding="utf-8",
        )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
