"""Offline script-unit self-check comparison; no models, browser or network."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bench.cascade import precision_check
from bench.cascade_precision import _score, wilson
from bench.regrade import discover, git, task_catalog, unpack
from bench.script_first import claimed_from_payload, task_terms
from bench.selfcheck_replay import build_units, replay_check

HERE = Path(__file__).resolve().parent
EXTDEV = "docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl"
LABELS = "docs/results/extdev_hand_labels_20261117/hand_labels.csv"
CAVEAT = "Extdev scores use AI (Devin) hand labels from PR #97, not human spot-checked; indicative only. Dev/val truth uses the grader, not AI labels."
VARIANTS = ("current_runtime", "current_precision", "runtime_grounding", "runtime_no_dump", "runtime_scope", "precision_all")


def normalize(value):
    return " ".join(str(value or "").casefold().split())


def candidate_rules(description, check):
    payload = check.get("payload") or {}
    answer = claimed_from_payload(payload).answer
    page = normalize(payload.get("text"))
    url = check.get("page_url") or ""
    grounded = bool(answer) and (normalize(answer) in page or answer.strip() == url)
    bounded = len(answer) <= 80 and "\n" not in answer and "\t" not in answer
    surface = normalize(unquote(" ".join(str(x or "") for x in (url, payload.get("title"), payload.get("h1"), answer))))
    words = {token.strip(".-_").casefold()
             for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#_-]*", surface)}
    terms = set(task_terms(description))
    hits = sum(term in words for term in terms)
    scope = bool(terms) and hits / len(terms) >= 0.5
    return {"grounding": grounded, "no_dump": bounded, "scope": scope}


def predictions(description, check, earlier):
    runtime = replay_check(description, check, earlier)
    current = {**check, "verdict": runtime.verdict}
    gate, reason = precision_check(description, current)
    rules = candidate_rules(description, check)
    passed = runtime.verdict == "PASS"
    return {
        "current_runtime": passed,
        "current_precision": gate,
        "runtime_grounding": passed and rules["grounding"],
        "runtime_no_dump": passed and rules["no_dump"],
        "runtime_scope": passed and rules["scope"],
        "precision_all": gate and all(rules.values()),
    }, runtime.verdict, runtime.reason, reason, rules


def load_dev():
    catalog = task_catalog()
    tasks = {key: entry["task"] for key, entry in catalog.items()
             if entry["split"].startswith(("dev", "val")) and not entry["split"].startswith("held")}
    manifest_path = HERE / "sources.json"
    pinned = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    sources = []
    if pinned is None:
        candidates = discover(ROOT)
    else:
        candidates = []
        for source in pinned:
            data = git(ROOT, "show", f"{source['commit']}:{source['path']}")
            assert hashlib.sha256(data.encode()).hexdigest() == source["sha256"]
            candidates.append({**source, "data": data})
    rows = []
    for source in candidates:
        selected = [{**row, "_file": source["path"]} for row in unpack(
            source["data"], jsonl=not source.get("pilot"), pilot=source.get("pilot", False))
            if row.get("arm") == "script_first" and row.get("self_checks") and row.get("task_id") in tasks]
        if selected:
            sources.append({key: source[key] for key in ("path", "commit", "sha256")})
            rows.extend(selected)
    return rows, build_units(rows, tasks), sources


def load_extdev():
    with (ROOT / LABELS).open() as handle:
        labels = {row["task_id"]: row for row in csv.DictReader(handle) if row["arm"] == "script_first"}
    rows = []
    for line, raw in enumerate((ROOT / EXTDEV).read_text().splitlines(), 1):
        row = json.loads(raw)
        if row.get("arm") != "script_first" or row.get("skipped"):
            continue
        label = labels[row["task_id"]]
        assert int(label["line"]) == line
        rows.append({**row, "line": line, "hand_label": label["hand_label"]})
    return rows


def build_records(dev_rows, dev_units, ext_rows):
    records = []
    unit_index = 0
    for dataset, rows in (("dev_val", dev_rows), ("extdev", ext_rows)):
        for row_index, row in enumerate(rows):
            for index, check in enumerate(row["self_checks"]):
                label, truth_note = None, "intermediate script has no AI hand label"
                if dataset == "dev_val":
                    unit = dev_units[unit_index]
                    unit_index += 1
                    label = unit["graded"]
                    truth_note = "grader" if label is not None else "ungradable saved evidence"
                elif index == len(row["self_checks"]) - 1:
                    answer = claimed_from_payload(check.get("payload") or {}).answer
                    if check.get("page_url") == row.get("final_url") and answer.strip() == row.get("claimed_answer", "").strip():
                        label = row["hand_label"]
                        truth_note = "final URL and answer align with AI-labelled row"
                    else:
                        truth_note = "last logged script does not align with AI-labelled final state"
                predicted, verdict, reason, gate_reason, rules = predictions(row["task_description"], check, row["self_checks"][:index])
                records.append({"dataset": dataset, "source": row.get("_file", EXTDEV),
                                "row": row.get("line", row_index + 1), "task_id": row["task_id"], "script": index + 1,
                                "truth": label, "truth_note": truth_note, "saved_verdict": check.get("verdict"),
                                "replayed_verdict": verdict, "runtime_reason": reason, "precision_reason": gate_reason,
                                **rules, **predicted})
    return records


def metrics(records, variant, partial_positive=False):
    counts = Counter()
    unlabelled = 0
    for row in records:
        label = row["truth"]
        if label is None:
            unlabelled += 1
            continue
        truth = label if isinstance(label, bool) else label == "correct" or (partial_positive and label == "partial")
        counts[(row[variant], truth)] += 1
    tp, fp, fn, tn = [counts[key] for key in ((True, True), (True, False), (False, True), (False, False))]
    return dict(TP=tp, FP=fp, FN=fn, TN=tn, unlabelled=unlabelled,
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
                precision_ci95=wilson(tp, tp + fp))


def table(scores):
    lines = ["| Truth set | Variant | TP | FP | FN | TN | Precision | Recall |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for dataset, variants in scores.items():
        for variant, count in variants.items():
            rates = [f"{count[key]:.1%}" if count[key] is not None else "n/a" for key in ("precision", "recall")]
            lines.append(f"| {dataset} | {variant} | {count['TP']} | {count['FP']} | {count['FN']} | {count['TN']} | {' | '.join(rates)} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)
    dev_rows, dev_units, sources = load_dev()
    ext_rows = load_extdev()
    records = build_records(dev_rows, dev_units, ext_rows)
    scores = {name: {variant: metrics([r for r in records if r["dataset"] == dataset], variant, partial)
                     for variant in VARIANTS}
              for name, dataset, partial in (("dev_val_grader", "dev_val", False), ("extdev_strict_AI", "extdev", False), ("extdev_partial_positive_AI", "extdev", True))}
    report = {"caveat": CAVEAT, "scores": scores, "dev_reference_saved_precision": _score(dev_units, True),
              "dev_rows": len(dev_rows), "dev_scripts": len(dev_units), "extdev_rows": len(ext_rows),
              "extdev_scripts": sum(len(row["self_checks"]) for row in ext_rows),
              "extdev_row_labels": dict(Counter(row["hand_label"] for row in ext_rows)),
              "model_calls": 0, "browser_runs": 0}
    out = args.output_dir
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    with (out / "scripts.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    print(CAVEAT)
    print(table(scores))


if __name__ == "__main__":
    main()
