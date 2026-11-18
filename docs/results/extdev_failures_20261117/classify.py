"""Classify the 22 paired extdev script_first rows, without grading them."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bench.selfcheck_replay import load_rows
from bench.script_first import parse_task_script

HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl"
LABELS = ROOT / "docs/results/extdev_hand_labels_20261117/hand_labels.csv"


def rows():
    # load_rows deliberately omits attempts without self_checks; retain those too.
    checks = {(r["task_id"]): r for r in load_rows([str(SOURCE)])}
    with LABELS.open() as handle:
        labels = {r["task_id"]: r for r in csv.DictReader(handle) if r["arm"] == "script_first"}
    result = []
    for line, raw in enumerate(SOURCE.read_text().splitlines(), 1):
        row = json.loads(raw)
        if row.get("arm") != "script_first" or row.get("skipped"):
            continue
        label = labels[row["task_id"]]
        assert int(label["line"]) == line
        row.update(line=line, hand_label=label["hand_label"], hand_note=label["note"])
        assert row.get("self_checks") == checks.get(row["task_id"], {}).get("self_checks", [])
        result.append(row)
    return result


def reason_class(reason):
    reason = (reason or "").lower()
    if "metadata exceeds" in reason:
        return "metadata_budget"
    if "script stopped" in reason:
        return "script_error"
    if "no answer" in reason:
        return "no_answer"
    if "not in the page" in reason or "not on the page" in reason:
        return "ungrounded_answer"
    if "finished" in reason or "completed successfully" in reason:
        return "self_pass"
    return "other"


def parse_error(code):
    try:
        parse_task_script(code)
    except ValueError as exc:
        return str(exc).split(";", 1)[0]
    return ""


def primary(row):
    reason = row.get("grade_completion_reason", "")
    task = row["task_description"].lower()
    answer = row.get("claimed_answer", "")
    if "metadata exceeds" in reason.lower():
        return "metadata_budget"
    if row["scripts"] and parse_error(row["scripts"][-1]):
        return "grammar_rejection"
    if "challenge page" in reason.lower():
        return "site_challenge"
    if "world cups" in task and "Saudi Pro League" in answer:
        return "wrong_scope_self_pass"
    if len(answer) > 500 and ("all the events" in task or "marketing department" in task):
        return "raw_dump"
    if "rated at least" in task and answer == "Price: Low to High":
        return "unverified_constraints"
    return reason_class(reason)


def classify(row):
    attempts = []
    for index, code in enumerate(row["scripts"]):
        check = row["self_checks"][index] if index < len(row["self_checks"]) else {}
        error = parse_error(code)
        attempts.append({
            "attempt": index + 1,
            "class": "grammar_rejection" if error else reason_class(check.get("reason")),
            "parse_error": error,
            "reason": check.get("reason", "not saved (exception before logging)"),
            "turn": row["script_turns"][index] if index < len(row["script_turns"]) else None,
        })
    repair = "not_sent"
    if row.get("repair_sent"):
        if len(attempts) < 2:
            repair = "no_logged_second_script"
        elif row["hand_label"] == "correct":
            repair = "fixed_by_hand_label"
        elif attempts[0]["class"] == attempts[-1]["class"]:
            repair = "repeated_class_not_fixed"
        else:
            repair = "changed_class_not_fixed"
    return {"line": row["line"], "task_id": row["task_id"], "primary": primary(row),
            "hand_label": row["hand_label"], "repair": repair,
            "attempts": json.dumps(attempts, ensure_ascii=False), "hand_note": row["hand_note"]}


def write_csv(path, records):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def breakdown(records):
    counts = Counter((r["primary"], r["hand_label"]) for r in records)
    lines = ["| Primary class | Correct | Partial | Wrong | Total |", "|---|---:|---:|---:|---:|"]
    for name in sorted({r["primary"] for r in records}):
        nums = [counts[name, label] for label in ("correct", "partial", "wrong")]
        lines.append(f"| {name} | " + " | ".join(map(str, [*nums, sum(nums)])) + " |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)
    records = [classify(row) for row in rows()]
    write_csv(args.output_dir / "failures.csv", records)
    print("Scored against AI (Devin) hand labels from PR #97; no human spot-check; indicative only.")
    print(breakdown(records))
    print("Repair outcomes:", dict(sorted(Counter(r["repair"] for r in records).items())))


if __name__ == "__main__":
    main()
