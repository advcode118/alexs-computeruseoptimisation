"""Offline audit of saved replicate-one evidence; never constructs a model client."""

import csv
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bench import grade
from bench.tasks import tasks_for_split

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
VERIFY = ROOT / "docs/results/ext_sample_20261116"


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def category(row):
    if row["success"]:
        return "PASS"
    reason = row["success_reason"]
    if row["arm"] == "playwright_mcp" and not row.get("grade_url"):
        return "browser unavailable (empty URL)"
    if reason.startswith("URL '") and "does not contain" in reason:
        return "wrong/empty page URL"
    if reason.startswith("URL is a search page"):
        return "search page denied"
    if reason.startswith("URL contains"):
        return "URL matches, later evidence gate failed"
    return reason


def replay(task, row, answer=None, original_claim=True):
    payload = row.get("grade_claim") if original_claim else None
    claim = grade.ClaimedEvidence(**payload) if isinstance(payload, dict) else None
    return grade.grade_observation(
        task, row.get("grade_url", ""), row.get("grade_page_text", ""),
        selector_text=row.get("grade_selector_text", ""),
        answer=row.get("claimed_answer", "") if answer is None else answer,
        claimed=claim,
        completed=row.get("grade_completed") if original_claim else None,
        completion_reason=row.get("grade_completion_reason", "") if original_claim else "",
    )


def stats(rows):
    return {
        "n": len(rows),
        **{f"mean_{key}": round(statistics.mean(r.get(key, 0) for r in rows), 6)
           for key in ("usd", "steps", "input_tokens", "output_tokens", "cached_tokens",
                       "cache_write_30m_tokens", "wall_ms")},
        "median_wall_ms": round(statistics.median(r["wall_ms"] for r in rows), 2),
        "cache_read_fraction": round(sum(r.get("cached_tokens", 0) for r in rows)
                                     / sum(r.get("input_tokens", 0) for r in rows), 4),
    }


def short_context_cost(row):
    cached = row.get("cached_tokens", 0)
    written = row.get("cache_write_30m_tokens", 0)
    ordinary = row["input_tokens"] - cached - written
    return (2 * ordinary + .1 * cached + 2.5 * written + 10 * row["output_tokens"]) / 1_000_000


def main():
    tasks = {t["id"]: t for t in tasks_for_split("extdev")}
    rows = []
    for name in ("probe_20261117_012232.jsonl", "probe_20261117_015118.jsonl"):
        for row in load(RAW / name):
            if "task_id" in row and not row.get("skipped"):
                rows.append({**row, "source_file": name})
    assert len(rows) == 128
    groups = {}
    audits = []
    for row in rows:
        task = tasks[row["task_id"]]
        label = row["arm"] + ":" + row.get("browser_use_mode", "default")
        groups.setdefault(label, []).append(row)
        original = replay(task, row)
        reference = replay(task, row, task["expected_answer"], original_claim=False)
        checks = row.get("self_checks") or []
        audits.append({
            "arm_mode": label, "task_id": row["task_id"], "category": category(row),
            "saved_success": row["success"], "saved_reason": row["success_reason"],
            "frozen_replay_success": original[0], "frozen_replay_reason": original[1],
            "reference_on_saved_page_success": reference[0],
            "reference_on_saved_page_reason": reference[1],
            "expected_answer": task["expected_answer"],
            "url_key": task.get("check_url_contains", ""),
            "grade_url": row.get("grade_url", ""),
            "returned_answer": row.get("claimed_answer", ""),
            "answer_length": len(row.get("claimed_answer", "")),
            "raw_length_limit": 3 * len(task["end_markers"].get("answer_in_text", "")) + 40,
            "page_text_truncated": row.get("grade_page_text_truncated", False),
            "self_check_end_state": row.get("end_state", ""),
            "self_check_verdicts": json.dumps([c.get("verdict") for c in checks]),
            "self_check_reasons": json.dumps([c.get("reason") for c in checks]),
        })
    with (HERE / "attempted_row_audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audits[0]))
        writer.writeheader()
        writer.writerows(audits)

    decisions = {}
    for row in load(VERIFY / "authoring_extdev.jsonl"):
        decisions[(row["source"], row["source_id"])] = row
    finals = {r["task_id"]: r["final_url"] for r in decisions.values()
              if r.get("disposition") == "kept" and r.get("task_id") in tasks}
    synthetic = []
    for task_id, task in tasks.items():
        answer = task["expected_answer"]
        verdict = grade.grade_observation(task, finals[task_id], answer, answer=answer)
        synthetic.append({"task_id": task_id, "success": verdict[0], "reason": verdict[1]})
    assert len(synthetic) == 40
    # These are logical marker-compatibility checks, NOT recreated live page reads.
    verifications = {}
    for p in sorted(VERIFY.glob("verification_extdev*.jsonl")):
        records = load(p)
        verifications[p.name] = {
            "rows": len(records), "key_passes": sum(r.get("key") is True for r in records),
            "reproducer_passes": sum(r.get("reproducer") is True for r in records),
            "reproducer_failures": sum(r.get("reproducer") is False for r in records),
            "contains_page_evidence": any("text" in r or "page_text" in r for r in records),
        }
    script = groups["script_first:default"]
    historic = [r for r in load(ROOT / "docs/results/heldout_sol_medium_20261111.jsonl")
                if r.get("arm") == "browser_use" and not r.get("skipped")]
    default = groups["browser_use:default"]
    ultra = groups["browser_use:ultrafast"]
    paired_ids = {r["task_id"] for r in default}
    paired_ultra = [r for r in ultra if r["task_id"] in paired_ids]
    default_by_id = {r["task_id"]: r for r in default}
    deltas = [r["wall_ms"] - default_by_id[r["task_id"]]["wall_ms"] for r in paired_ultra]
    logs = {}
    for mode in ("default", "ultrafast"):
        log = (RAW / f"{mode}_rep1.log").read_text()
        logs[mode] = {
            "judge_success": len(re.findall(r"Judge: success", log)),
            "judge_failure": len(re.findall(r"Judge: failure", log)),
            "completed_run_lines": len(re.findall(r"completed in \d+ steps", log)),
        }
    result = {
        "attempted_rows": len(rows),
        "failure_categories": {label: dict(Counter(category(r) for r in rr)) for label, rr in groups.items()},
        "exact_failure_reasons": {label: dict(Counter(r["success_reason"] for r in rr)) for label, rr in groups.items()},
        "replay_disagreements": [a for a in audits if a["saved_success"] != a["frozen_replay_success"]
                                 or a["saved_reason"] != a["frozen_replay_reason"]],
        "reference_on_saved_page": {
            label: dict(Counter("PASS" if a["reference_on_saved_page_success"] else a["reference_on_saved_page_reason"]
                                for a in audits if a["arm_mode"] == label)) for label in groups},
        "synthetic_reference_compatibility": synthetic,
        "verification_files": verifications,
        "script_end_states": dict(Counter(r.get("end_state") for r in script)),
        "script_check_verdicts": dict(Counter(c.get("verdict") for r in script for c in r.get("self_checks", []))),
        "script_check_reasons": dict(Counter(c.get("reason") for r in script for c in r.get("self_checks", []))),
        "script_no_checks": [r["task_id"] for r in script if not r.get("self_checks")],
        "script_page_diagnostic": dict(Counter(str(r.get("page_answer_success")) for r in script)),
        "script_pass_end_state_failures": {r["task_id"]: r["success_reason"] for r in script if r.get("end_state") == "PASS"},
        "browser_use_metrics": {
            "historic_1.0.0_different_tasks": stats(historic), "default_22": stats(default),
            "ultrafast_all40": stats(ultra), "ultrafast_paired22": stats(paired_ultra),
            "ultrafast_unpaired18": stats([r for r in ultra if r["task_id"] not in paired_ids]),
            "paired_ultrafast_faster": sum(d < 0 for d in deltas),
            "paired_median_wall_delta_ms": round(statistics.median(deltas), 2),
        },
        "browser_use_log_judges": logs,
        "aggregate_long_context_pricing": {
            label: {
                "rows_above_272k_aggregate_input": [r["task_id"] for r in rr if r["input_tokens"] > 272000],
                "recorded_usd": round(sum(r["usd"] for r in rr), 6),
                "hypothetical_all_short_context_usd": round(sum(short_context_cost(r) for r in rr), 6),
                "warning": "Aggregate request totals trigger the long-context multiplier; individual request sizes are not saved. This counterfactual is not a corrected bill.",
            } for label, rr in (("default", default), ("ultrafast", ultra))
        },
        "frozen_grader_sha256": hashlib.sha256((ROOT / "bench/grade.py").read_bytes()).hexdigest(),
        "ledger_running_total_usd": json.loads((Path.home() / ".cu-optimisation/openai-spend-alex15.json").read_text())["running_total_usd"],
    }
    (HERE / "analysis_rep1.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Attempted rows audited:", len(rows))
    for key in ("failure_categories", "reference_on_saved_page", "script_end_states", "script_check_verdicts",
                "script_page_diagnostic", "browser_use_metrics", "browser_use_log_judges",
                "aggregate_long_context_pricing"):
        print(key + ": " + json.dumps(result[key]))
    print("Synthetic reference/marker compatibility:", sum(r["success"] for r in synthetic), "/40 (not live evidence)")
    print("Stored-page frozen replay disagreements:", len(result["replay_disagreements"]))
    print("Ledger running_total_usd:", result["ledger_running_total_usd"])
    print("Frozen grader SHA256:", result["frozen_grader_sha256"])


if __name__ == "__main__":
    main()
