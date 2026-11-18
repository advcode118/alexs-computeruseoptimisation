"""Saved-arm pre-router simulation. No model, browser or network calls."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DATA = ROOT / "docs/results/extdev_control_20261117"
DEFAULT = "raw/probe_20261117_012232.jsonl"
ULTRAFAST = "raw/probe_20261117_015118.jsonl"
LABELS = ROOT / "docs/results/extdev_hand_labels_20261117/hand_labels.csv"
CAVEAT = "Scored against AI (Devin) hand labels from PR #97, not human spot-checked; indicative only. Routed timings are saved-row simulations, not new measurements."
POLICIES = ("always_cascade", "always_browser_use", "bypass_value", "nav_only", "oracle_quality_then_time")


def quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def pre_run_features(row):
    parts = row["task_id"].split("_", 2)
    if len(parts) != 3 or parts[0] != "extdev":
        raise ValueError("expected extdev_CATEGORY_task id")
    return {"category": parts[1], "domain": urlsplit(row["start_url"]).hostname,
            "description": row["task_description"]}


def choose_pre_run(policy, features):
    if policy == "always_cascade":
        return "cascade"
    if policy == "always_browser_use":
        return "browser_use"
    if policy == "bypass_value":
        return "browser_use" if features["category"] == "value" else "cascade"
    if policy == "nav_only":
        return "cascade" if features["category"] == "nav" else "browser_use"
    raise ValueError(f"not a pre-run policy: {policy}")


def load_inputs():
    with LABELS.open() as handle:
        labels = {(row["file"], row["arm"], row["task_id"]): row["hand_label"] for row in csv.DictReader(handle)}
    groups = {}
    for filename in (DEFAULT, ULTRAFAST):
        rows = [json.loads(line) for line in (DATA / filename).read_text().splitlines()]
        groups[filename] = {(row["arm"], row["task_id"]): row for row in rows
                            if row.get("arm") and row.get("task_id") and not row.get("skipped")}
    tasks = [task for arm, task in groups[DEFAULT] if arm == "script_first"]
    pairs = []
    for task in tasks:
        arms = {"script_first": groups[DEFAULT]["script_first", task],
                "cascade": groups[DEFAULT]["cascade", task],
                "default": groups[DEFAULT]["browser_use", task],
                "ultrafast": groups[ULTRAFAST]["browser_use", task]}
        truth = {name: labels[ULTRAFAST if name == "ultrafast" else DEFAULT,
                              "browser_use" if name in {"default", "ultrafast"} else name, task] for name in arms}
        assert all(row["model"] == "gpt-6.1-sol" and row["effort"] == "medium" for row in arms.values())
        cascade = arms["cascade"]
        assert {"grounding", "script", "browser_use"} <= cascade["stage_wall_ms"].keys()
        assert cascade["answered_by"] in {"script", "browser_use"}
        pairs.append({"task_id": task, "features": pre_run_features(arms["script_first"]), "arms": arms, "truth": truth})
    return pairs


def simulate(pairs):
    records = []
    quality = {"wrong": 0, "partial": 1, "correct": 2}
    for mode in ("default", "ultrafast"):
        for policy in POLICIES:
            for pair in pairs:
                arms, truth = pair["arms"], pair["truth"]
                if policy == "oracle_quality_then_time":
                    selected = min(("cascade", mode), key=lambda key: (-quality[truth[key]], arms[key]["wall_ms"]))
                else:
                    route = choose_pre_run(policy, pair["features"])
                    selected = "cascade" if route == "cascade" else mode
                row = arms[selected]
                cascade = arms["cascade"]
                used_cascade = selected == "cascade"
                handed_off = used_cascade and row["answered_by"] == "browser_use"
                script_s = row["stage_wall_ms"]["script"] / 1000 if used_cascade else 0.0
                records.append({"browser_use_mode": mode, "policy": policy, "task_id": pair["task_id"],
                                **pair["features"], "selected_row": selected,
                                "final_stage": row["answered_by"] if used_cascade else "browser_use",
                                "hand_label": truth[selected], "wall_s": row["wall_ms"] / 1000, "usd": row["usd"],
                                "script_s": script_s, "handed_off": handed_off,
                                "script_s_on_handoff": script_s if handed_off else 0.0,
                                "bypassed_observed_handoff": not used_cascade and cascade["answered_by"] == "browser_use"})
    return records


def summarize(records):
    n = len(records)
    counts = Counter(row["hand_label"] for row in records)
    times = [row["wall_s"] for row in records]
    return {"tasks": n, **{label: counts[label] for label in ("correct", "partial", "wrong")},
            "mean_s": mean(times) if times else None, "p90_s": quantile(times, 0.9),
            "median_s": median(times) if times else None,
            "usd_per_task": sum(row["usd"] for row in records) / n if n else None,
            "script_stage_s_total": sum(row["script_s"] for row in records),
            "script_s_on_handoff_total": sum(row["script_s_on_handoff"] for row in records),
            "handoffs": sum(row["handed_off"] for row in records),
            "direct_browser_use": sum(row["selected_row"] != "cascade" for row in records),
            "bypassed_observed_handoffs": sum(row["bypassed_observed_handoff"] for row in records)}


def table(summaries):
    lines = ["| BU mode | Policy | C/P/W | Mean s | p90 s | Median s | $/task | Script s on handoffs (total) | Handoffs |", "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for mode, policies in summaries.items():
        for policy, score in policies.items():
            labels = "/".join(str(score[key]) for key in ("correct", "partial", "wrong"))
            lines.append(f"| {mode} | {policy} | {labels} | {score['mean_s']:.3f} | {score['p90_s']:.3f} | {score['median_s']:.3f} | {score['usd_per_task']:.6f} | {score['script_s_on_handoff_total']:.3f} | {score['handoffs']} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)
    pairs = load_inputs()
    records = simulate(pairs)
    summaries = {mode: {policy: summarize([row for row in records if row["browser_use_mode"] == mode and row["policy"] == policy])
                        for policy in POLICIES} for mode in ("default", "ultrafast")}
    context_times = [pair["arms"]["script_first"]["wall_ms"] / 1000 for pair in pairs]
    report = {"caveat": CAVEAT, "summaries": summaries,
              "standalone_script_first": {"mean_s": mean(context_times), "p90_s": quantile(context_times, .9), "median_s": median(context_times)},
              "model_calls": 0, "browser_runs": 0}
    (args.output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    with (args.output_dir / "tasks.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    print(CAVEAT)
    print(table(summaries))


if __name__ == "__main__":
    main()
