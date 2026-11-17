"""Aggregate pilot rows. Grade fields are read unchanged; nothing is re-graded."""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
CONDS = ("baseline", "observe", "segments")
SPLITS = ("dev3", "dev4form", "dev4spa")


def family(task_id: str) -> str:
    for p in ("dev3_nav_", "dev3_value_", "dev3_search_"):
        if task_id.startswith(p):
            return p[5:-1]
    return "form" if task_id.startswith("dev4_form") else "spa"


def first_script_pass(row: dict) -> bool:
    if row.get("success") is not True:
        return False
    segs = row.get("segments") or []
    if row.get("segment_mode") == "on" or segs:
        # Segmented: every executed segment receipt succeeded (no failed segment, no recovery).
        return bool(segs) and all(s.get("ok") for s in segs)
    return not row.get("repair_sent") and len(row.get("script_turns") or []) <= 1


def p90(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))] if xs else None


def load(rep: int, cond: str):
    rows, statuses = [], {}
    for split in SPLITS:
        d = HERE / f"rep{rep}" / cond / split
        if (d / "manifest.json").exists():
            statuses[split] = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["status"]
        if (d / "rows.jsonl").exists():
            rows += [json.loads(l) for l in (d / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    return rows, statuses


def summarize(rows):
    done = [r for r in rows if r.get("success") is not None]
    walls = [r["wall_ms"] / 1000 for r in done if isinstance(r.get("wall_ms"), (int, float))]
    passes = sum(r["success"] is True for r in done)
    cost = sum(r.get("usd") or 0 for r in rows)
    fam = {}
    for r in done:
        f = fam.setdefault(family(r["task_id"]), [0, 0])
        f[0] += r["success"] is True
        f[1] += 1
    return {
        "rows": len(rows), "graded": len(done), "interrupted": len(rows) - len(done),
        "passes": passes,
        "false_accepts": sum(r.get("end_state") == "PASS" and r["success"] is False for r in done),
        "false_rejects": sum(r.get("page_answer_success") is True and r.get("end_state") != "PASS" for r in done),
        "runtime_pass": sum(r.get("end_state") == "PASS" for r in done),
        "first_script_pass": sum(first_script_pass(r) for r in done),
        "model_calls": sum(r.get("model_calls") or 0 for r in done),
        "script_steps": sum(r.get("script_steps") or 0 for r in done),
        "tool_steps": sum(r.get("steps") or 0 for r in done),
        "cost_usd": round(cost, 6),
        "wall_s_mean": round(statistics.mean(walls), 1) if walls else None,
        "wall_s_median": round(statistics.median(walls), 1) if walls else None,
        "wall_s_p90": round(p90(walls), 1) if walls else None,
        "wall_s_total": round(sum(walls), 1),
        "cost_per_pass": round(cost / passes, 6) if passes else None,
        "wall_s_per_pass": round(sum(walls) / passes, 1) if passes else None,
        "families": {k: f"{v[0]}/{v[1]}" for k, v in sorted(fam.items())},
    }


def main():
    out = {"by_rep": {}, "pooled": {}, "paired": {}}
    per_task = {}
    for rep in (1, 2):
        for cond in CONDS:
            rows, statuses = load(rep, cond)
            if not rows and not statuses:
                continue
            out["by_rep"][f"rep{rep}/{cond}"] = {**summarize(rows), "split_status": statuses}
            for r in rows:
                per_task.setdefault(r["task_id"], {})[f"rep{rep}/{cond}"] = (
                    None if r.get("success") is None else
                    ("P" if r["success"] else ("FA" if r.get("end_state") == "PASS" else "F")))
    for cond in CONDS:
        rows = load(1, cond)[0] + load(2, cond)[0]
        if rows:
            out["pooled"][cond] = summarize(rows)
    # Paired vs baseline within each repetition: tasks where candidate passed and baseline failed, and vice versa.
    for cand in ("observe", "segments"):
        for rep in (1, 2):
            b, c = f"rep{rep}/baseline", f"rep{rep}/{cand}"
            both = [t for t, v in per_task.items() if v.get(b) is not None and v.get(c) is not None]
            if both:
                out["paired"][f"rep{rep}/{cand}"] = {
                    "n": len(both),
                    "cand_only": sorted(t for t in both if per_task[t][c] == "P" != per_task[t][b]),
                    "base_only": sorted(t for t in both if per_task[t][b] == "P" != per_task[t][c]),
                }
    out["per_task"] = dict(sorted(per_task.items()))
    text = json.dumps(out, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("by_rep", "pooled", "paired")}, indent=1))


if __name__ == "__main__":
    main()
