"""Export sanitized per-task pilot rows and the matched-14 analysis.

Reads the gitignored raw run root read-only; grade fields are copied unchanged,
nothing is re-graded. Scripts, claimed answers, page text and call ids are not
copied (the unresolved call id is recorded in pilot_20261116.md).

    python docs/PR_INTEGRATION_20261116/pilot/export_pilot.py [RUN_ROOT]
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "bench/runs/pr_eval_20261116_pilot"
CONDS = ("baseline", "observe", "segments")
SPLITS = ("dev3", "dev4form", "dev4spa")
FIELDS = [
    "condition", "split", "task_id", "outcome", "success", "end_state", "page_answer_success",
    "wall_ms", "driver_task_wall_ms", "first_model_ms", "budget_hook_ms",
    "model_calls", "script_steps", "tool_steps", "repair_sent", "tier", "n_segments",
    "input_tokens", "output_tokens", "cached_tokens",
    "usd", "actual_usage_usd", "unresolved_reserved_usd", "harness_usd",
    "model", "effort", "revision", "run_id",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def outcome(r: dict) -> str | None:
    # Same codes as analyze.py: P / FA / F, plus FR, None = interrupted.
    if r.get("success") is None:
        return None
    if r["success"]:
        return "P"
    if r.get("end_state") == "PASS":
        return "FA"
    return "FR" if r.get("page_answer_success") is True else "F"


def sanitize(cond: str, split: str, r: dict) -> dict:
    out = {k: r.get(k) for k in FIELDS if k in r}
    out.update(condition=cond, split=split, outcome=outcome(r), tool_steps=r.get("steps"),
               n_segments=len(r.get("segments") or []))
    return {k: out.get(k) for k in FIELDS}


def stats(rows: list[dict]) -> dict:
    done = [r for r in rows if r["outcome"] is not None]
    walls = [r["wall_ms"] / 1000 for r in done]
    passes = sum(r["outcome"] == "P" for r in done)
    settled = sum(r["actual_usage_usd"] or 0 for r in rows)
    reserved = sum(r["unresolved_reserved_usd"] or 0 for r in rows)
    return {
        "tasks": len(done), "passes": passes,
        "false_accepts": sum(r["outcome"] == "FA" for r in done),
        "false_rejects": sum(r["outcome"] == "FR" for r in done),
        "model_calls": sum(r["model_calls"] or 0 for r in done),
        "script_steps": sum(r["script_steps"] or 0 for r in done),
        "tool_steps": sum(r["tool_steps"] or 0 for r in done),
        "settled_usd": round(settled, 6), "reserved_unresolved_usd": round(reserved, 6),
        "settled_usd_per_pass": round(settled / passes, 6) if passes else None,
        "wall_s_total": round(sum(walls), 1),
        "wall_s_mean": round(statistics.mean(walls), 1) if walls else None,
        "wall_s_median": round(statistics.median(walls), 1) if walls else None,
        "wall_s_per_pass": round(sum(walls) / passes, 1) if passes else None,
    }


def main() -> None:
    rows, prov = [], {}
    for cond in CONDS:
        for split in SPLITS:
            d = RUN / "rep1" / cond / split
            for name in ("manifest.json", "rows.jsonl"):
                if (d / name).exists():
                    prov[f"rep1/{cond}/{split}/{name}"] = sha(d / name)
            if (d / "rows.jsonl").exists():
                for line in (d / "rows.jsonl").read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        rows.append(sanitize(cond, split, json.loads(line)))
    for name in ("campaign.py", "analyze.py", "selection.json", "aggregate.json",
                 "campaign_log.jsonl", "campaign_stdout.txt"):
        if (RUN / name).exists():
            prov[name] = sha(RUN / name)

    by = {c: {r["task_id"]: r for r in rows if r["condition"] == c} for c in CONDS}
    seg_done = sorted(t for t, r in by["segments"].items() if r["outcome"] is not None)
    seg_interrupted = sorted(t for t, r in by["segments"].items() if r["outcome"] is None)
    matched = {c: stats([by[c][t] for t in seg_done]) for c in CONDS}
    interrupted_rows = {c: [by[c][t] for t in seg_interrupted] for c in CONDS}
    analysis = {
        "note": "Matched population = the 14 tasks segments completed. Interrupted task "
                "excluded from outcome/time/settled totals; its retained reservation is "
                "reported separately. Grades copied unchanged from raw rows.",
        "matched_tasks": seg_done,
        "interrupted_tasks": seg_interrupted,
        "matched14": matched,
        "interrupted_task_by_condition": {
            c: [{k: r[k] for k in ("task_id", "outcome", "wall_ms", "actual_usage_usd",
                                   "unresolved_reserved_usd", "model_calls")} for r in rs]
            for c, rs in interrupted_rows.items()},
        "full_population": {c: stats(list(by[c].values())) for c in CONDS},
        "paired_matched14": {
            c: {"wins": [t for t in seg_done if by[c][t]["outcome"] == "P" and by["baseline"][t]["outcome"] != "P"],
                "losses": [t for t in seg_done if by[c][t]["outcome"] != "P" and by["baseline"][t]["outcome"] == "P"]}
            for c in ("observe", "segments")},
    }
    (OUT / "pilot_rows.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    with (OUT / "pilot_rows.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (OUT / "pilot_matched.json").write_text(json.dumps(analysis, indent=1) + "\n", encoding="utf-8")
    (OUT / "provenance.json").write_text(json.dumps(
        {"run_root": "bench/runs/pr_eval_20261116_pilot (gitignored, local only)",
         "runtime_revision": "1dede2b6396a1f9a580ca055c3d9d57e77863873",
         "report_commit_private": "deac8e1",
         "row_count": len(rows), "sha256": prov}, indent=1) + "\n", encoding="utf-8")
    print(len(rows), "rows;", json.dumps(matched, indent=1))


if __name__ == "__main__":
    main()
