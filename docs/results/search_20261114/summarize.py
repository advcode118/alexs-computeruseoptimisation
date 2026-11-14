"""Summarize only this experiment's named files, never other run folders."""
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).parent
groups = []
for label in ("dev3_off1", "dev3_on1", "dev4search_off1", "dev4search_on1", "heldout2_off1", "heldout2_on1", "heldout_off1", "heldout_on1", "dev3_on2", "dev3_off2"):
    path = ROOT / (label + ".jsonl")
    if not path.exists():
        continue
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    times = sorted(row["wall_ms"] / 1000 for row in rows)
    groups.append({"label": label, "n": len(rows), "passes": sum(bool(r["success"]) for r in rows),
        "false_accepts": sum(r["end_state"] == "PASS" and not r["success"] for r in rows),
        "median_calls": statistics.median(r["model_calls"] for r in rows),
        "mean_calls": statistics.mean(r["model_calls"] for r in rows),
        "median_s": statistics.median(times), "mean_s": statistics.mean(times),
        "p90_s": times[math.ceil(.9 * len(times)) - 1],
        "usd": sum(r["usd"] for r in rows), "fallbacks": sum(r.get("strategy") == "search_fallback" for r in rows),
        "rows": rows})

lines = ["# Search checkpoint measurements", "", "All arms: script_first, Luna medium; existing grader unchanged. Times include failed specialist attempts and fallback. p90 is nearest-rank. No repeated-run independence or significance claim.", "", "| Run | Pass | False accepts | Calls med/mean | Wall med/mean/p90 (s) | USD/task | Fallbacks |", "|---|---:|---:|---:|---:|---:|---:|"]
for g in groups:
    lines.append(f"| {g['label']} | {g['passes']}/{g['n']} | {g['false_accepts']}/{g['n']} | {g['median_calls']:g}/{g['mean_calls']:.2f} | {g['median_s']:.2f}/{g['mean_s']:.2f}/{g['p90_s']:.2f} | {g['usd']/g['n']:.6f} | {g['fallbacks']} |")
lines += ["", "## Per-task evidence", "", "| Run | Task | Pass | Self-check | Calls | Steps | Search actions | Wall (s) | USD |", "|---|---|---|---|---:|---:|---:|---:|---:|"]
for g in groups:
    for r in g["rows"]:
        actions = sum(t.get("actions",0) for t in r.get("search_trace",[]))
        lines.append(f"| {g['label']} | {r['task_id']} | {r['success']} | {r['end_state']} | {r['model_calls']} | {r['steps']} | {actions} | {r['wall_ms']/1000:.2f} | {r['usd']:.6f} |")
(ROOT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
(ROOT / "summary.json").write_text(json.dumps([{k:v for k,v in g.items() if k!='rows'} for g in groups], indent=2), encoding="utf-8")
bars = []
for g in groups:
    bars.append(f"<tr><th>{g['label']}</th><td><div style='width:{g['passes']/g['n']*220}px;background:#2d7260;height:18px'></div>{g['passes']}/{g['n']}</td><td><div style='width:{min(g['median_s']*7,360)}px;background:#40618a;height:18px'></div>{g['median_s']:.2f}s</td></tr>")
(ROOT / "comparison.html").write_text("<!doctype html><html><meta charset='utf-8'><title>Search strategy comparison</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;color:#183126;background:#f5f4ed}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:12px;border-bottom:1px solid #c8d0c7}h1{font-size:28px}</style><h1>Search strategy: measured checkpoint</h1><p>Luna medium · unchanged grader · failures included</p><table><tr><th>Run</th><th>Accuracy</th><th>Median wall time</th></tr>" + ''.join(bars) + "</table><p>Small development samples; shared-machine timing. Raw rows and per-task figures are retained.</p></html>", encoding="utf-8")
print('\n'.join(lines[:4 + len(groups) + 2]))
