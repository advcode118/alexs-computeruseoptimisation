"""Run tasks through the existing loop and write one log record each.

This module does not know about the hidden split. The scorer passes the task
list in. A counted run uses the model planner. The fake planner is not a result.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from bench.catalog import Task
from bench.checks import evaluate
from bench.experiments import ReplayPlanner, make_candidate_planner
from bench.flags import DEFAULTS
from bench.rates import RATES, estimate_dollars
from loop.actions import ActionError, PlannerError
from loop.browser import BrowserSession
from loop.engine import Controller, Engine, Log
from loop.planner import make_planner


@dataclass
class RunSpec:
    name: str = "candidate"
    allow_direct: bool = True
    warm_browser: bool = True
    max_actions: int | None = None
    max_cycles: int = 8
    one_action: bool = False
    handoff: bool = False
    replay_from: Path | None = None
    save_traces: bool = False


def candidate_spec() -> RunSpec:
    return RunSpec(
        name="candidate",
        allow_direct=DEFAULTS["direct_match"],
        warm_browser=DEFAULTS["warm_browser"],
        max_actions=None if DEFAULTS["batch_actions"] else 1,
        max_cycles=8,
        handoff=DEFAULTS["handoff"],
    )


def baseline_spec() -> RunSpec:
    return RunSpec(
        name="baseline",
        allow_direct=False,
        warm_browser=True,
        max_actions=1,
        max_cycles=12,
        one_action=True,
    )


def run_tasks(
    tasks: list[Task],
    *,
    planner_name: str,
    out_dir: Path,
    spec: RunSpec | None = None,
    keys: dict | None = None,
) -> dict:
    spec = spec or (candidate_spec() if planner_name == "model" else RunSpec(name="fake", max_cycles=8))
    if planner_name == "fake":
        spec = RunSpec(name="fake", allow_direct=True, warm_browser=True, max_cycles=8)
    records = []
    started = time.perf_counter()
    session: BrowserSession | None = None
    try:
        if spec.warm_browser:
            session = BrowserSession(headless=True)
            session.open()
        for task in tasks:
            own_session = False
            if session is None:
                session = BrowserSession(headless=True)
                session.open()
                own_session = True
            try:
                records.append(_run_one(session, task, planner_name, spec, out_dir))
            finally:
                if own_session and session is not None:
                    session.close()
                    session = None
    finally:
        if session is not None:
            session.close()
    summary = _summary(records, planner_name, spec, keys)
    summary["run_wall_time_s"] = round(time.perf_counter() - started, 3)
    summary["out_dir"] = str(out_dir)
    _write(out_dir, records, summary)
    return summary


def _run_one(session: BrowserSession, task: Task, planner_name: str, spec: RunSpec, out_dir: Path) -> dict:
    page = session.page
    log = Log(echo=False)
    controller = Controller()
    controller.task = task.instruction
    controller.planner_name = planner_name
    controller.mode = "running"
    engine = Engine(session, controller, log, max_cycles=spec.max_cycles)
    engine.allow_direct = spec.allow_direct
    engine.suppress_direct = not spec.allow_direct
    engine.max_actions = spec.max_actions
    started = time.perf_counter()
    detail = ""
    try:
        if page is None:
            raise ActionError("The browser is not open.")
        target = task.fixture.resolve().as_uri()
        page.goto(target, wait_until="domcontentloaded")
        engine.planner = _planner_for(task, planner_name, spec, target)
        engine.run()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        success, detail = evaluate(page, task.check)
    except (ActionError, PlannerError, Exception) as exc:
        success = False
        detail = _safe_detail(exc)
    elapsed = time.perf_counter() - started
    planner = engine.planner
    llm_calls = _llm_calls(planner, log)
    input_tokens = int(getattr(planner, "input_tokens", 0) or 0)
    output_tokens = int(getattr(planner, "output_tokens", 0) or 0)
    cached_tokens = int(getattr(planner, "cached_input_tokens", 0) or 0)
    model = getattr(planner, "model", None) if llm_calls else None
    priced = estimate_dollars(
        model,
        input_tokens,
        output_tokens,
        llm_calls=llm_calls,
        cached_input_tokens=cached_tokens,
    )
    steps = sum(1 for event in log.snapshot() if event["kind"] == "act")
    cycles = sum(1 for event in log.snapshot() if event["kind"] == "plan")
    if spec.save_traces and getattr(engine, "trace_ok", False) and engine.trace:
        trace_dir = out_dir / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{task.id}.json").write_text(
            json.dumps({"ok": True, "steps": engine.trace}, indent=2) + "\n",
            encoding="utf-8",
        )
    record = {
        "id": task.id,
        "holdout": task.holdout,
        "success": bool(success),
        "wall_time_s": round(elapsed, 3),
        "steps": steps,
        "planner_cycles": cycles,
        "llm_calls": llm_calls,
        "tokens": {
            "input": input_tokens,
            "cached_input": cached_tokens,
            "output": output_tokens,
            "total": input_tokens + cached_tokens + output_tokens,
        },
        "estimated_dollars": priced["estimated_dollars"],
        "dollars_are": priced["dollars_are"],
        "model": priced["model"],
        "rate_found": priced["rate_found"],
        "planner": planner_name,
        "loop_mode": controller.snapshot()["mode"],
        "check": task.check.get("kind"),
        "check_detail": detail,
        "run": spec.name,
    }
    print(
        f"{task.id} success={record['success']} time={record['wall_time_s']} "
        f"llm={record['llm_calls']} dollars={record['estimated_dollars']}",
        file=sys.stderr,
        flush=True,
    )
    return record


def _planner_for(task: Task, planner_name: str, spec: RunSpec, fixture_url: str):
    if planner_name != "model":
        return make_planner(planner_name, fixture_url)
    if spec.replay_from is not None:
        path = spec.replay_from / f"{task.id}.json"
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            steps = payload.get("steps") or []
            if payload.get("ok") and steps:
                return ReplayPlanner(steps)
    if spec.one_action:
        from bench.baseline_agent import make_baseline_planner

        return make_baseline_planner()
    return make_candidate_planner(handoff=spec.handoff)


def _safe_detail(exc: BaseException) -> str:
    from bench.keys import redact

    return redact(str(exc).split("\n", 1)[0][:300])


def _llm_calls(planner, log: Log) -> int:
    calls = getattr(planner, "calls", None)
    if isinstance(calls, int):
        return calls
    return sum(
        1
        for event in log.snapshot()
        if event["kind"] == "status" and str(event["line"]).startswith("model")
    )


def _summary(records: list[dict], planner_name: str, spec: RunSpec, keys: dict | None) -> dict:
    passed = sum(1 for record in records if record["success"])
    shown = [{key: value for key, value in record.items() if key != "check_detail"} for record in records]
    provider = None
    if keys:
        if keys.get("nebius"):
            provider = "nebius"
        elif keys.get("anthropic"):
            provider = "anthropic"
    model = None
    for record in records:
        if record.get("model"):
            model = record["model"]
            break
    if model is None and planner_name == "model" and provider == "nebius":
        model = os.environ.get("LOOP_MODEL") or os.environ.get("RUN_MODEL") or "deepseek-ai/DeepSeek-V4-Pro-0813"
    command = "python -m bench baseline" if spec.name == "baseline" else "python -m bench run"
    if spec.name not in ("baseline", "candidate", "fake"):
        command = f"python -m bench run --mode {spec.name}"
    return {
        "command": command,
        "planner": planner_name,
        "counted": planner_name == "model",
        "run": spec.name,
        "provider": provider,
        "model": model,
        "api_key_present": bool(
            (keys and (keys.get("nebius") or keys.get("anthropic")))
            or os.environ.get("LOOP_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("NEBIUS_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
        ),
        "flags": {
            "direct_match": spec.allow_direct,
            "batch_actions": spec.max_actions is None,
            "warm_browser": spec.warm_browser,
            "a11y_before_image": True,
            "replay": spec.replay_from is not None,
            "handoff": spec.handoff,
            "prompt_cache": False,
            "one_action": spec.one_action,
        },
        "dollars_are": "estimate",
        "dollars_note": "estimated_dollars uses the rate table and API token counts. It is an estimate, not an invoice.",
        "steps_are": "browser actions",
        "rate_table_usd_per_million": RATES,
        "task_count": len(records),
        "holdout_count": sum(1 for record in records if record["holdout"]),
        "passed": passed,
        "failed": len(records) - passed,
        "llm_calls": sum(record["llm_calls"] for record in records),
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
