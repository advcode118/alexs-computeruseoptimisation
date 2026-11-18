"""Build the blind-label input: one item per attempted row, arms hidden, shuffled.

    python docs/results/paired_run_20261118/label_input.py

labels_input.jsonl has only what a labeller may see: task text, start URL, final URL, the
agent's answer and the saved page text. label_map.json (arm, task id, grader verdict) is
read only after labelling.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
FILES = {"A_cascade_interactive.jsonl": "cascade+interactive", "B_cascade_browser_use.jsonl": "cascade+browser_use",
         "C_browser_use.jsonl": "browser_use"}


def main():
    from bench.tasks import task_by_id

    items, mapping = [], {}
    for name, arm in FILES.items():
        path = HERE / "raw" / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if "task_id" not in row or row.get("skipped"):
                continue
            label_id = "L" + hashlib.sha256(f"{arm}:{row['task_id']}".encode()).hexdigest()[:8]
            task = task_by_id(row["task_id"])
            items.append({"label_id": label_id, "task": task["description"], "start_url": task["start_url"],
                          "final_url": row.get("grade_url") or row.get("final_url") or "",
                          "answer": row.get("claimed_answer") or "",
                          "page_text": (row.get("grade_page_text") or "")[:6000]})
            mapping[label_id] = {"arm": arm, "task_id": row["task_id"], "grader_pass": bool(row.get("success")),
                                 "grader_reason": row.get("success_reason") or ""}
    random.Random(20261118).shuffle(items)
    with (HERE / "labels_input.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    (HERE / "label_map.json").write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(items)} items")


if __name__ == "__main__":
    main()
