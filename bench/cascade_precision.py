"""Offline precision measurements; never imported by the live cascade."""

from collections import Counter
from math import sqrt

from bench.cascade import precision_check
from bench.regrade import discover, task_catalog, unpack
from bench.selfcheck_replay import build_units


def wilson(success, total):
    if not total:
        return None
    z = 1.959963984540054
    p = success / total
    center = (p + z*z/(2*total)) / (1+z*z/total)
    radius = z*sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [center-radius, center+radius]


def _score(units, precision):
    counts = Counter()
    catches = Counter()
    for unit in units:
        if unit["graded"] is None:
            continue
        plain = unit["check"].get("verdict") == "PASS"
        accept, reason = precision_check(unit["description"], unit["check"])
        predicted = accept if precision else plain
        counts[(predicted, unit["graded"]) ] += 1
        if plain and not accept:
            catches[(reason, "true_passes_lost" if unit["graded"] else "false_accepts_caught")] += 1
    tp, fp, fn, tn = (counts[key] for key in ((True, True), (True, False), (False, True), (False, False)))
    rules = {}
    for (reason, kind), count in sorted(catches.items()):
        rules.setdefault(reason, {"false_accepts_caught": 0, "true_passes_lost": 0})[kind] = count
    return dict(TP=tp, FP=fp, FN=fn, TN=tn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                precision_ci95=wilson(tp, tp+fp), recall_ci95=wilson(tp, tp+fn), rules=rules)


def build_report(root):
    catalog = task_catalog()
    tasks = {key: entry["task"] for key, entry in catalog.items()
             if entry["split"].startswith(("dev", "val")) and not entry["split"].startswith("held")}
    rows = []
    for source in discover(root):
        for row in unpack(source["data"], jsonl=not source.get("pilot"), pilot=source.get("pilot", False)):
            if row.get("arm") == "script_first" and row.get("self_checks") and row.get("task_id") in tasks:
                rows.append({**row, "_file": source["path"]})
    scripts = build_units(rows, tasks)
    finals = build_units([{**row, "self_checks": row["self_checks"][-1:]} for row in rows], tasks)
    return {name: {mode: _score(units, mode == "precision") for mode in ("plain", "precision")}
            for name, units in (("script", scripts), ("final", finals))}


def markdown(report):
    lines = ["# Cascade self-check precision", "", "| Unit | Mode | TP | FP | FN | TN | Precision | Recall |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for unit, modes in report.items():
        for mode, row in modes.items():
            lines.append(f'| {unit} | {mode} | {row["TP"]} | {row["FP"]} | {row["FN"]} | {row["TN"]} | {row["precision"]:.1%} | {row["recall"]:.1%} |')
    lines += ["", "Rules were tuned on these dev/validation rows, not an independent claim set.",
              "Wilson 95% intervals and per-rule false accepts caught / true passes lost are in precision.json.",
              "Remaining false accepts are wrong-value-on-right-page cases structural checks cannot see."]
    return "\n".join(lines) + "\n"
