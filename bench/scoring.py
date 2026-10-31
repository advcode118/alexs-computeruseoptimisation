"""Score the bench. Hidden tasks are loaded only from score()."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from bench.catalog import Task, _load_directory, agent_tasks
from bench.keys import load_live_keys
from bench.runner import RunSpec, baseline_spec, candidate_spec, run_tasks
from bench.stats import median, success_rate, within_success_band

ROOT = Path(__file__).resolve().parent
PIN_PATH = ROOT / "baseline.json"
BASELINE_CODE = ROOT / "baseline_agent.py"


def load_holdout() -> list[Task]:
    directory = Path(__file__).resolve().parent / "holdout"
    return _load_directory(directory, holdout=True)


def score(
    planner_name: str = "model",
    out_dir: Path | None = None,
    *,
    quick: bool = False,
    spec: RunSpec | None = None,
) -> dict:
    keys = None
    if planner_name == "model":
        keys = load_live_keys()
    if out_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = ROOT / "runs" / stamp
    if spec is None:
        spec = candidate_spec() if planner_name == "model" else RunSpec(name="fake")
    tasks = select_tasks(quick=quick)
    summary = run_tasks(tasks, planner_name=planner_name, out_dir=out_dir, spec=spec, keys=keys)
    if planner_name == "model" and not quick and summary["holdout_count"] == 6 and spec.name == "candidate":
        summary["against_baseline"] = compare_baseline(summary)
        _write_summary(out_dir, summary)
    if quick:
        summary["command"] = "python -m bench run --quick"
        _write_summary(out_dir, summary)
    return summary


def select_tasks(*, quick: bool) -> list[Task]:
    if quick:
        return list(agent_tasks())[:10]
    return list(agent_tasks()) + list(load_holdout())


def pin_baseline(summary: dict) -> dict:
    """Write bench/baseline.json. Call this only after the baseline run."""
    digest = hashlib.sha256(BASELINE_CODE.read_bytes()).hexdigest()
    tasks = []
    for record in summary["tasks"]:
        tasks.append(
            {
                "id": record["id"],
                "holdout": record["holdout"],
                "success": record["success"],
                "wall_time_s": record["wall_time_s"],
                "steps": record["steps"],
                "llm_calls": record["llm_calls"],
                "tokens": record["tokens"],
                "estimated_dollars": record["estimated_dollars"],
                "model": record["model"],
            }
        )
    pin = {
        "frozen": True,
        "code": "bench/baseline_agent.py",
        "code_sha256": digest,
        "planner": "model",
        "provider": summary.get("provider"),
        "model": summary.get("model"),
        "description": (
            "One action per model call on a warm browser. "
            "Token counts come from the API. Dollars are an estimate from the rate table, not an invoice."
        ),
        "task_count": summary["task_count"],
        "holdout_count": summary["holdout_count"],
        "median_wall_time_s": round(median([record["wall_time_s"] for record in tasks]), 3),
        "median_estimated_dollars": _median_dollars(tasks),
        "main_success": round(success_rate(tasks, holdout=False), 4),
        "holdout_success": round(success_rate(tasks, holdout=True), 4),
        "llm_calls": summary["llm_calls"],
        "tasks": tasks,
    }
    PIN_PATH.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    return pin


def compare_baseline(summary: dict) -> dict | None:
    if not PIN_PATH.is_file():
        return None
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    base_time = float(pin["median_wall_time_s"])
    base_cost = pin["median_estimated_dollars"]
    cand_time = median([record["wall_time_s"] for record in summary["tasks"]])
    cand_cost = _median_dollars(summary["tasks"])
    main = success_rate(summary["tasks"], holdout=False)
    hold = success_rate(summary["tasks"], holdout=True)
    time_ratio = (base_time / cand_time) if cand_time else None
    cost_met = False
    if isinstance(base_cost, (int, float)) and base_cost > 0 and isinstance(cand_cost, (int, float)):
        cost_met = cand_cost <= base_cost / 2
    return {
        "baseline_median_wall_time_s": base_time,
        "baseline_median_estimated_dollars": base_cost,
        "candidate_median_wall_time_s": round(cand_time, 3),
        "candidate_median_estimated_dollars": cand_cost,
        "time_ratio": None if time_ratio is None else round(time_ratio, 3),
        "time_target_met": bool(time_ratio is not None and time_ratio >= 2),
        "cost_target_met": cost_met,
        "main_success": round(main, 4),
        "holdout_success": round(hold, 4),
        "baseline_main_success": pin["main_success"],
        "baseline_holdout_success": pin["holdout_success"],
        "within_success_band": within_success_band(pin["main_success"], main)
        and within_success_band(pin["holdout_success"], hold),
    }


def baseline_code_sha256() -> str:
    return hashlib.sha256(BASELINE_CODE.read_bytes()).hexdigest()


def _median_dollars(records: list[dict]):
    amounts = []
    for record in records:
        amount = record["estimated_dollars"]
        if amount is None:
            return None
        amounts.append(float(amount))
    if not amounts:
        return None
    return round(median(amounts), 8)


def _write_summary(out_dir: Path, summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def run_baseline(out_dir: Path | None = None) -> tuple[dict, dict]:
    if out_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = ROOT / "runs" / f"baseline-{stamp}"
    summary = score(planner_name="model", out_dir=out_dir, quick=False, spec=baseline_spec())
    pin = pin_baseline(summary)
    return summary, pin
