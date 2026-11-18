"""Select the held-out rows for scorer v2 validation. Offline; reads saved files only.

A row qualifies when it is a non-skipped arm row from a task set other than
extdev (and never heldout3/heldout4), and its last self-check payload carries
page text read at the row's own final_url. Rows with identical
(task, final_url, answer, page text) are de-duplicated; every source line is kept.

Run from the repository root:
    python docs/results/scorer_v2_20261118/heldout/select_rows.py
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
TEXT_CAP = 8000  # same cap as the extdev grade_page_text


def main():
    from bench.regrade import task_catalog

    catalog = task_catalog()
    rows = {}
    files = []  # output is .ndjson so bench.regrade.discover (*.jsonl) never re-reads it
    for path in sorted((ROOT / "docs/results").rglob("*.jsonl")):
        rel = path.relative_to(ROOT).as_posix()
        low = rel.casefold()
        if "extdev" in low or "heldout3" in low or "heldout4" in low or "scorer_v2" in low:
            continue
        used = False
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            row = value.get("row", value) if isinstance(value, dict) else None
            if not isinstance(row, dict) or not row.get("task_id") or row.get("skipped"):
                continue
            entry = catalog.get(row["task_id"])
            if entry is None or entry["split"] in ("extdev",) or entry["split"].startswith(("heldout3", "heldout4")):
                continue
            checks = [c for c in (row.get("self_checks") or [])
                      if isinstance(c, dict) and isinstance(c.get("payload"), dict) and c["payload"].get("text")]
            if not checks or checks[-1]["payload"].get("url") != row.get("final_url"):
                continue
            payload = checks[-1]["payload"]
            text = payload["text"][:TEXT_CAP]
            key = (row["task_id"], row.get("final_url") or "", row.get("claimed_answer") or "", text)
            item = rows.setdefault(key, {
                "task_id": row["task_id"], "split": entry["split"], "arm": row["arm"],
                "description": entry["task"]["description"], "final_url": row.get("final_url") or "",
                "answer": row.get("claimed_answer") or "", "page_text": text,
                "page_text_truncated": len(payload["text"]) > TEXT_CAP,
                "claimed": payload.get("claimed") or {}, "end_state": row.get("end_state"),
                "sources": []})
            item["sources"].append(f"{rel}:{number}")
            used = True
        if used:
            files.append(rel)
    selected = sorted(rows.values(), key=lambda r: (r["task_id"], r["sources"][0]))
    for index, item in enumerate(selected, 1):
        item["hid"] = f"H{index:02d}"
    blob = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in selected)
    (HERE / "heldout_rows.ndjson").write_text(blob, encoding="utf-8")
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    manifest = {"rows": len(selected), "tasks": len({r["task_id"] for r in selected}),
                "splits": sorted({r["split"] for r in selected}), "files": files,
                "selection_sha256": digest, "text_cap": TEXT_CAP}
    (HERE / "selection.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
