"""Derive scorer-v2 keys mechanically from v1 task fields (validation only).

This is the "derived key" rule in docs/GRADER.md (Scorer v2). It is applied
to the held-out tasks without reading their rows, so the held-out agreement
tests the v2 rules, not hand-tuned keys. Production grading of non-extdev tasks
is unchanged (they carry no key_v2).

Run from the repository root:
    python docs/results/scorer_v2_20261118/heldout/derive_keys.py
"""

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent


def derive_key_v2(task: dict) -> dict:
    from bench import grade

    markers = grade._task_markers(task)
    host = markers.get("host") or urlsplit(task.get("start_url", "")).hostname or ""
    page = {}
    if markers.get("url_contains"):
        page["url_contains"] = markers["url_contains"]
    if markers.get("path_suffix"):
        page.update(path=markers["path_suffix"], path_mode="suffix")
    if markers.get("query_nonempty"):
        page["query_nonempty"] = True
    marker = markers.get("answer_in_text") or ""
    parts = markers.get("answer_parts") or ([marker] if marker else [])
    facts = [[part] for part in parts]
    deliverable = "both" if page and facts else ("page" if page else "answer")
    key = {"deliverable": deliverable, "host": host,
           "reference": markers.get("full_answer") or marker or markers.get("url_contains") or "",
           "deny": list(markers.get("deny") or grade.V2_DEFAULT_DENY)}
    if page:
        key["pages"] = [page]
        if grade.is_search_results_url(markers.get("url_contains") or ""):
            key["allow_search"] = True
    if facts:
        key["facts"] = facts
    return key


def main():
    from bench import grade
    from bench.regrade import task_catalog

    catalog = task_catalog()
    rows = [json.loads(line) for line in (HERE / "heldout_rows.ndjson").read_text(encoding="utf-8").splitlines()]
    ids = sorted({row["task_id"] for row in rows})
    keys = {task_id: derive_key_v2(catalog[task_id]["task"]) for task_id in ids}
    invalid = [task_id for task_id, key in keys.items() if grade._v2_key_problem(key)]
    (HERE / "derived_keys.json").write_text(json.dumps(keys, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(keys)} derived keys; invalid: {invalid}")


if __name__ == "__main__":
    main()
