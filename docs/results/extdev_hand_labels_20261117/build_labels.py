"""Join the hand labels to the frozen-grader re-grade and report agreement.

Offline: reads saved files only, calls no model and no browser.
Run from the repository root:
    python docs/results/extdev_hand_labels_20261117/build_labels.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTDEV = HERE.parent / "extdev_control_20261117"
FILES = {
    "D": "raw/probe_20261117_012232.jsonl",
    "U": "raw/probe_20261117_015118.jsonl",
    "S": "smoke/probe_20261117_011924.jsonl",
}
MCP_NOTE = "Chrome failed to launch; no task attempt (infrastructure)"


def load_labels():
    labels = {}
    for line in (HERE / "labels_input.txt").read_text().splitlines():
        if not line.strip():
            continue
        head, note = line.split("|", 1)
        key, label = head.split()
        assert key not in labels, key
        assert label in {"correct", "partial", "wrong"}, line
        labels[(FILES[key[0]], int(key[1:]))] = (label, note)
    return labels


def main():
    labels = load_labels()
    rows = []
    for r in csv.DictReader((EXTDEV / "regraded_rows.csv").open()):
        if r["new"] == "":
            continue  # budget skip: never attempted
        key = (r["file"], int(r["line"]))
        if r["arm"] == "playwright_mcp":
            label, note = "infra", MCP_NOTE
        else:
            label, note = labels.pop(key)
        raw = [json.loads(x) for x in (EXTDEV / r["file"]).read_text().splitlines() if x.strip()]
        match = [x for x in raw if x.get("task_id") == r["task_id"] and x.get("arm") == r["arm"]]
        assert len(match) == 1, key
        mode = match[0].get("browser_use_mode") or ""
        rows.append({
            "file": r["file"], "line": r["line"], "arm": r["arm"],
            "browser_use_mode": mode if r["arm"] in {"browser_use", "cascade"} else "",
            "task_id": r["task_id"], "grader_pass": r["new"], "grader_reason": r["new_reason"],
            "hand_label": label, "note": note,
        })
    assert not labels, f"labels without a row: {sorted(labels)}"
    with (HERE / "hand_labels.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def table(sel):
        c = Counter((r["grader_pass"], r["hand_label"]) for r in sel)
        n = len(sel)
        gp = sum(1 for r in sel if r["grader_pass"] == "True")
        strict = sum(1 for r in sel if r["hand_label"] == "correct")
        lenient = sum(1 for r in sel if r["hand_label"] in {"correct", "partial"})
        agree = sum(1 for r in sel if (r["grader_pass"] == "True") == (r["hand_label"] == "correct"))
        return {
            "n": n, "grader_pass": gp, "hand_correct": strict, "hand_correct_or_partial": lenient,
            "agree_strict": agree,
            "grader_fail_hand_correct": c[("False", "correct")],
            "grader_pass_hand_not_correct": sum(v for (g, h), v in c.items() if g == "True" and h != "correct"),
            "cells": {f"grader={g},hand={h}": v for (g, h), v in sorted(c.items())},
        }

    paired = {r["task_id"] for r in rows if r["file"] == FILES["D"]}
    groups = {
        "all_attempts": rows,
        "all_without_mcp": [r for r in rows if r["arm"] != "playwright_mcp"],
        "paired22_browser_use_default": [r for r in rows if r["file"] == FILES["D"] and r["arm"] == "browser_use"],
        "paired22_browser_use_ultrafast": [r for r in rows if r["file"] == FILES["U"] and r["task_id"] in paired],
        "paired22_script_first": [r for r in rows if r["file"] == FILES["D"] and r["arm"] == "script_first"],
        "paired22_cascade": [r for r in rows if r["file"] == FILES["D"] and r["arm"] == "cascade"],
        "all40_browser_use_ultrafast": [r for r in rows if r["file"] == FILES["U"]],
    }
    out = {name: table(sel) for name, sel in groups.items()}
    reasons = Counter(r["grader_reason"].split(" '")[0].split(":")[0]
                      for r in rows if r["grader_pass"] == "False" and r["hand_label"] == "correct")
    out["grader_fail_hand_correct_reasons"] = dict(reasons.most_common())
    (HERE / "agreement.json").write_text(json.dumps(out, indent=2) + "\n")
    for name, t in out.items():
        print(name, {k: v for k, v in t.items() if k != "cells"} if "n" in t else t)


if __name__ == "__main__":
    main()
