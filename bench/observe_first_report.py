"""Offline paired dev3 report. Reads only the explicit input files; no API calls.

python -m bench.observe_first_report --pair OFF.jsonl ON.jsonl --output report.json
Repeat --pair for repeated off/on measurements. First-script grades are
counterfactual shared grades, never the runtime verifier's own PASS.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import statistics


def load_rows(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    rows = [row for row in records if row.get("task_id")]
    from bench.tasks_dev3 import DEV3_TASK_IDS

    if len(rows) != len(DEV3_TASK_IDS) or {row["task_id"] for row in rows} != set(DEV3_TASK_IDS):
        raise ValueError(f"{path}: requires one complete dev3 cell, without duplicates")
    for row in rows:
        if row.get("skipped") or row.get("arm") != "script_first":
            raise ValueError(f"{path}: skipped task or wrong arm")
        if (row.get("model"), row.get("effort")) != ("gpt-6-luna", "medium"):
            raise ValueError(f"{path}: wrong model/effort")
    return rows


def first_grade(row: dict, task: dict) -> bool | None:
    """Independent shared grade if the first script's required evidence survived.

    The final selector read can only serve a one-script run on the same URL.
    An intermediate script's missing selector read is unknown, not a failure.
    All of this happens offline, after the model and runtime verifier finish.
    """
    checks = row.get("self_checks") or []
    if not checks:
        # Older logs lack intermediate payloads. If the sole script ended on
        # runtime PASS, the recorded final grade is already its shared grade.
        # A runtime FAIL cannot support this inference because it gates grading.
        if len(row.get("scripts") or []) == 1 and row.get("end_state") == "PASS":
            return bool(row["success"])
        return None
    check = dict(checks[0])
    payload = dict(check.get("payload") or {})
    if task.get("end_markers", {}).get("answer_equals_selector") and not payload.get("selector_text"):
        if len(checks) != 1 or check.get("page_url") != row.get("final_url") or not row.get("expected_value"):
            return None
        payload["selector_text"] = row["expected_value"]
    check["payload"] = payload
    from bench.selfcheck_replay import grade_check

    return grade_check(task, check)


def distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "mean": None, "p90": None}
    ordered = sorted(values)
    rank = (len(ordered) - 1) * 0.9
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    p90 = ordered[low] + (ordered[high] - ordered[low]) * (rank - low)
    return {
        "n": len(values), "median": round(statistics.median(values), 3),
        "mean": round(statistics.mean(values), 3), "p90": round(p90, 3),
    }


def task_metrics(row: dict, task: dict) -> dict:
    checks = row.get("self_checks") or []
    scripts = row.get("scripts") or []
    # In older logs a second script was only possible after a failed self-check.
    first_self = checks[0].get("verdict") == "PASS" if checks else (len(scripts) == 1 and row.get("end_state") == "PASS")
    return {
        "task_id": row["task_id"], "graded_pass": bool(row["success"]),
        "runtime_pass": row.get("end_state") == "PASS",
        "first_script_self_pass": first_self,
        "first_script_graded_pass": first_grade(row, task),
        "one_script_stopped_graded_pass": bool(row["success"]) and len(scripts) == 1,
        "wall_ms": row["wall_ms"], "first_model_ms": row.get("first_model_ms"),
        "model_calls": row.get("model_calls"), "steps": row.get("steps"),
        "script_count": len(scripts), "usd": row["usd"],
        "page_summary": row.get("page_summary", "off"),
        "page_summary_waited_ms": row.get("page_summary_waited_ms"),
        "page_summary_ms": row.get("page_summary_ms"),
    }


def summarize(rows: list[dict]) -> dict:
    graded = [row for row in rows if row["first_script_graded_pass"] is not None]
    first_pass = sum(row["first_script_graded_pass"] for row in graded)
    unknown = len(rows) - len(graded)
    return {
        "attempted": len(rows), "final_graded_pass": sum(row["graded_pass"] for row in rows),
        "final_runtime_pass": sum(row["runtime_pass"] for row in rows),
        "final_false_accepts": sum(row["runtime_pass"] and not row["graded_pass"] for row in rows),
        "first_script_self_pass": sum(row["first_script_self_pass"] for row in rows),
        "one_script_stopped_graded_pass": sum(row["one_script_stopped_graded_pass"] for row in rows),
        "first_script_independent_grade": {
            "pass": first_pass, "fail": len(graded) - first_pass, "unavailable": unknown,
            "pass_bounds": [first_pass, first_pass + unknown],
            "false_accepts_among_gradable": sum(row["first_script_self_pass"] and not row["first_script_graded_pass"] for row in graded),
        },
        "wall_ms_all": distribution([row["wall_ms"] for row in rows]),
        "wall_ms_successes": distribution([row["wall_ms"] for row in rows if row["graded_pass"]]),
        "first_model_ms": distribution([row["first_model_ms"] for row in rows if row["first_model_ms"] is not None]),
        "summary_waited_ms": distribution([row["page_summary_waited_ms"] for row in rows if row["page_summary_waited_ms"] is not None]),
        "summary_ms": distribution([row["page_summary_ms"] for row in rows if row["page_summary_ms"] is not None]),
        "fetch_status": dict(Counter(row["page_summary"] for row in rows)),
        "model_calls": distribution([row["model_calls"] for row in rows if row["model_calls"] is not None]),
        "steps": distribution([row["steps"] for row in rows if row["steps"] is not None]),
        "usd": round(sum(row["usd"] for row in rows), 6),
        "total_wall_ms_per_success": round(sum(row["wall_ms"] for row in rows) / sum(row["graded_pass"] for row in rows), 3) if any(row["graded_pass"] for row in rows) else None,
    }


def report(pairs: list[tuple[Path, Path]]) -> dict:
    from bench.tasks_dev3 import DEV3_TASKS

    tasks = {task["id"]: task for task in DEV3_TASKS}
    aggregates = {"off": [], "on": []}
    comparisons = []
    measurements = []
    for number, paths in enumerate(pairs, 1):
        metrics = {}
        for switch, path in zip(("off", "on"), paths):
            metrics[switch] = [task_metrics(row, tasks[row["task_id"]]) for row in load_rows(path)]
            aggregates[switch].extend(metrics[switch])
            measurements.extend({"pair": number, "switch": switch, **row} for row in metrics[switch])
        off = {row["task_id"]: row for row in metrics["off"]}
        on = {row["task_id"]: row for row in metrics["on"]}
        comparisons.append({
            "pair": number, "sources": [str(path) for path in paths],
            "off": summarize(metrics["off"]), "on": summarize(metrics["on"]),
            "on_only_pass": sum(on[key]["graded_pass"] and not off[key]["graded_pass"] for key in off),
            "off_only_pass": sum(off[key]["graded_pass"] and not on[key]["graded_pass"] for key in off),
        })
    return {
        "split": "dev3", "pairs": comparisons,
        "aggregate": {key: summarize(rows) for key, rows in aggregates.items()},
        "measurements": measurements,
        "notes": [
            "Repeated dev3 tasks are not independent samples; no held-out generalization claim.",
            "First-script independent grades force runtime PASS only in the offline counterfactual shared grade.",
            "Older sole-script/runtime-PASS rows reuse their recorded final shared grade; other old rows are unavailable.",
            "Missing intermediate selector evidence is unavailable, not a fail; bounds include all unknowns.",
            "First model latency is API elapsed time; summary waiting is separately included in wall time.",
            "p90 is the inclusive linearly interpolated percentile. Cost is the sum of recorded row costs.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", nargs=2, action="append", required=True, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.pair)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], indent=2))


if __name__ == "__main__":
    main()
