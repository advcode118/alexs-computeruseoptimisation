"""Summarise the paired live run from the committed raw rows. No network, no model calls.

    python docs/results/paired_run_20261118/summarize.py

Pass = the row's own grade (scorer v2 for extval tasks, run-time) re-checked offline with the
same grader on the saved fields; UNKNOWN / needs approval / skipped are not passes.
p90 = nearest-rank 90th percentile over every attempted task of the arm.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

ARMS = {  # raw file -> arm label
    "A_cascade_interactive.jsonl": "cascade+interactive",
    "B_cascade_browser_use.jsonl": "cascade+browser_use",
    "C_browser_use.jsonl": "browser_use",
}


def p90(values):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)] if ordered else float("nan")


def mean(values):
    return sum(values) / len(values) if values else float("nan")


def regrade(row):
    """Re-run the frozen grader on the saved fields, the same way bench/regrade.py does."""
    from bench.grade import grade_observation
    from bench.tasks import task_by_id

    task = task_by_id(row["task_id"])
    claim = row.get("grade_claim")
    claimed = None
    if isinstance(claim, dict):
        from bench.script_first import ClaimedEvidence
        claimed = ClaimedEvidence(url=claim.get("url", ""), title=claim.get("title", ""), h1=claim.get("h1", ""),
                                  answer=claim.get("answer", ""), key_text=claim.get("key_text", ""),
                                  values=tuple(claim.get("values") or ()), rejected=bool(claim.get("rejected", False)))
    ok, reason, _, _ = grade_observation(task, row.get("grade_url") or row.get("final_url") or "",
                                         row.get("grade_page_text") or "", selector_text=row.get("grade_selector_text") or "",
                                         answer=row.get("claimed_answer") or "", completed=row.get("grade_completed"),
                                         completion_reason=row.get("grade_completion_reason") or "", claimed=claimed)
    own = row.get("end_state") if row.get("arm") == "cascade" else None
    if own is not None and own != "PASS" and row.get("answered_by") != "browser_use":
        ok = False
    return ok, reason


def load():
    out = {}
    for name, label in ARMS.items():
        path = HERE / "raw" / name
        if path.exists():
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            out[label] = [r for r in rows if "task_id" in r]  # drop probe header records
    return out


def summarise(rows):
    attempted = [r for r in rows if not r.get("skipped")]
    passes = [r for r in attempted if r.get("success")]
    calls = [int(r.get("model_calls") or 0) for r in attempted]
    walls = [float(r.get("wall_ms") or 0) / 1000 for r in attempted]
    usd = [float(r.get("usd") or 0) for r in attempted]
    stage_calls = {}
    for r in attempted:
        for stage, n in (r.get("stage_model_calls") or {}).items():
            stage_calls[stage] = stage_calls.get(stage, 0) + int(n or 0)
    answered = {}
    for r in attempted:
        key = r.get("answered_by") or ("browser_use" if r.get("arm") == "browser_use" else "")
        answered[key] = answered.get(key, 0) + 1
    return {
        "tasks": len(rows), "attempted": len(attempted), "skipped": len(rows) - len(attempted),
        "passes": len(passes), "pass_rate": len(passes) / len(attempted) if attempted else float("nan"),
        "calls_mean": mean(calls), "calls_p90": p90(calls),
        "wall_mean_s": mean(walls), "wall_p90_s": p90(walls), "wall_median_s": sorted(walls)[len(walls) // 2] if walls else float("nan"),
        "usd_per_task": mean(usd), "usd_total": sum(usd),
        "wall_s_per_pass": sum(walls) / len(passes) if passes else float("nan"),
        "usd_per_pass": sum(usd) / len(passes) if passes else float("nan"),
        "recovery_fired": sum(1 for r in attempted if any(n for k, n in (r.get("stage_model_calls") or {}).items() if k != "script")),
        "recovery_passes": sum(1 for r in attempted if r.get("answered_by") in ("interactive", "browser_use") and r.get("success")),
        "stage_model_calls": stage_calls, "answered_by": answered,
    }


def main():
    data = load()
    report, mismatches = {}, []
    for label, rows in data.items():
        for r in rows:
            if r.get("skipped"):
                continue
            ok, reason = regrade(r)
            if bool(ok) != bool(r.get("success")):
                mismatches.append({"arm": label, "task_id": r["task_id"], "row": r.get("success"), "regrade": ok, "reason": reason})
        report[label] = summarise(rows)
    common = set.intersection(*[{r["task_id"] for r in rows if not r.get("skipped")} for rows in data.values()]) if data else set()
    report["_paired_tasks"] = sorted(common)
    report["_regrade_mismatches"] = mismatches
    (HERE / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["| Arm | Attempted | Pass | Pass rate | Calls mean | Calls p90 | Wall mean (s) | Wall p90 (s) | $/task | $ total | Wall s/pass | $/pass |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for label in ARMS.values():
        if label in report:
            s = report[label]
            lines.append(f"| {label} | {s['attempted']} | {s['passes']} | {s['pass_rate']:.1%} | {s['calls_mean']:.2f} | {s['calls_p90']} | "
                         f"{s['wall_mean_s']:.1f} | {s['wall_p90_s']:.1f} | {s['usd_per_task']:.4f} | {s['usd_total']:.4f} | "
                         f"{s['wall_s_per_pass']:.1f} | {s['usd_per_pass']:.3f} |")
            if label != "browser_use":
                lines.append(f"|  ↳ recovery stage fired / recovered | {s['recovery_fired']} | {s['recovery_passes']} | | | | | | | | | |")
    print("\n".join(lines))
    print(f"paired tasks: {len(common)}; offline regrade mismatches: {len(mismatches)}")


if __name__ == "__main__":
    main()
