"""Join AI-written labels to saved attempts; no model calls or browser reads."""

import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def summarize(rows):
    if not rows:
        return {"n": 0, "correct": 0, "partial": 0, "grader_pass": 0,
                "mean_ms": None, "median_ms": None, "p90_ms": None, "usd": 0}
    times = sorted(float(r["wall_ms"]) for r in rows)
    index = (len(times) - 1) * .9
    lo = int(index)
    p90 = times[lo] + (times[min(lo + 1, len(times) - 1)] - times[lo]) * (index - lo)
    return {"n": len(rows), "correct": sum(r["hand_label"] == "correct" for r in rows),
            "partial": sum(r["hand_label"] == "partial" for r in rows),
            "grader_pass": sum(r["grader_pass"] for r in rows),
            "mean_ms": statistics.mean(times), "median_ms": statistics.median(times),
            "p90_ms": p90, "usd": round(sum(float(r["usd"]) for r in rows), 6)}


def join_labels(raw, labels):
    attempts = [r for r in raw if "task_id" in r and not r.get("skipped")]
    assert len({r["task_id"] for r in attempts}) == len(attempts), "duplicate attempt"
    assert set(labels) == {r["task_id"] for r in attempts}, "label coverage mismatch"
    result = []
    for r in attempts:
        label, note = labels[r["task_id"]]
        assert label in {"correct", "partial", "wrong", "infra"}, label
        result.append({"model": r["model"], "task_id": r["task_id"],
                       "grader_pass": r["success"], "grader_reason": r["success_reason"],
                       "hand_label": label, "note": note, "wall_ms": r["wall_ms"],
                       "usd": r["usd"], "steps": r["steps"]})
    return result


def main():
    labels = {}
    for line in (HERE / "labels_input.txt").read_text().splitlines():
        if not line.strip():
            continue
        head, note = line.split("|", 1)
        model, task_id, label = head.split()
        assert task_id not in labels.setdefault(model, {}), "duplicate label"
        labels[model][task_id] = (label, note.strip())
    manifest = json.loads((HERE / "raw_manifest.json").read_text())
    assert set(manifest) == set(labels)
    rows, metrics = [], {}
    for model, filename in manifest.items():
        raw = [json.loads(s) for s in (HERE / filename).read_text().splitlines()]
        joined = join_labels(raw, labels[model])
        rows.extend(joined)
        metrics[model] = summarize(joined)
    with (HERE / "hand_labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (HERE / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
