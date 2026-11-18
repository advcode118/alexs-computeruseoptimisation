"""Grader vs label agreement for scorer v2 on extdev and the held-out rows.

Offline: reads saved files only; no model, browser or network call.
Run from the repository root:
    python docs/results/scorer_v2_20261118/agreement.py

Strict agreement: grader PASS <=> label 'correct' ('partial' counts as not
correct). "final" grades include the v1 gates that sit above the page grade
(script_first's own verdict must be PASS), exactly as bench/regrade.py does;
"page" grades are the page grade alone.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
EXTDEV = ROOT / "docs/results/extdev_control_20261117"
LABELS = ROOT / "docs/results/extdev_hand_labels_20261117/hand_labels.csv"
FILES = {"raw/probe_20261117_012232.jsonl": "D", "raw/probe_20261117_015118.jsonl": "U",
         "smoke/probe_20261117_011924.jsonl": "S"}


def table(rows, grade_key, label_key):
    cells = Counter((r[grade_key], r[label_key]) for r in rows)
    n = len(rows)
    agree = sum((r[grade_key] == "PASS") == (r[label_key] == "correct") for r in rows)
    fa = [r["row"] for r in rows if r[grade_key] == "PASS" and r[label_key] != "correct"]
    fr = [r["row"] for r in rows if r[grade_key] != "PASS" and r[label_key] == "correct"]
    return {"n": n, "agree": agree, "agree_pct": round(100 * agree / n, 1) if n else None,
            "false_accepts": len(fa), "false_accept_rows": fa,
            "false_rejects": len(fr), "false_reject_rows": fr,
            "confusion": {f"{g}|{lab}": c for (g, lab), c in sorted(cells.items())}}


def extdev_rows():
    from bench import grade
    from bench.regrade import regrade_row, task_catalog

    catalog = task_catalog()
    labels = {(r["file"], r["line"]): r for r in csv.DictReader(LABELS.open(encoding="utf-8"))
              if r["arm"] != "playwright_mcp"}
    corrections = {r["row"]: r for r in csv.DictReader((HERE / "extdev_label_corrections.csv").open(encoding="utf-8"))}
    cache, out = {}, []
    for g in csv.DictReader((EXTDEV / "regraded_rows.csv").open(encoding="utf-8")):
        key = (g["file"], g["line"])
        if key not in labels:
            continue
        if g["file"] not in cache:
            cache[g["file"]] = [json.loads(x) for x in (EXTDEV / g["file"]).read_text(encoding="utf-8").splitlines() if x.strip()]
        raw = next(x for x in cache[g["file"]] if x.get("task_id") == g["task_id"] and x.get("arm") == g["arm"])
        result = regrade_row(raw, catalog)
        task = catalog[g["task_id"]]["task"]
        claim = raw.get("grade_claim")
        claim = grade.ClaimedEvidence(**claim) if isinstance(claim, dict) else None
        page_ok, page_reason = grade.grade_page_answer(
            task, raw.get("grade_url", ""), raw["grade_page_text"],
            selector_text=raw.get("grade_selector_text", ""), answer=raw.get("claimed_answer", ""), claimed=claim)
        row = FILES[g["file"]] + g["line"]
        label = labels[key]["hand_label"]
        fix = corrections.get(row)
        out.append({"row": row, "file": g["file"], "line": g["line"], "arm": g["arm"], "task_id": g["task_id"],
                    "v1_final": "PASS" if g["new"] == "True" else "FAIL", "v1_reason": g["new_reason"],
                    "v2_final": "PASS" if result["new"] else "FAIL", "v2_reason": result["reason"],
                    "v2_page": "PASS" if page_ok else "FAIL", "v2_page_reason": page_reason,
                    "label_original": label,
                    "label_corrected": fix["corrected"] if fix else label,
                    "correction": fix["justification"] if fix else ""})
        assert not fix or fix["original"] == label, row
    assert len(out) == 109 and {c for c in corrections} <= {r["row"] for r in out}
    return out


def heldout_rows():
    from bench import grade
    from bench.regrade import task_catalog

    catalog = task_catalog()
    keys = json.loads((HERE / "heldout/derived_keys.json").read_text(encoding="utf-8"))
    labels = {r["hid"]: r for r in csv.DictReader((HERE / "heldout/blind_labels.csv").open(encoding="utf-8"))}
    out = []
    for line in (HERE / "heldout/heldout_rows.ndjson").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        v1_task = {k: v for k, v in catalog[r["task_id"]]["task"].items() if k != "key_v2"}
        v2_task = {**v1_task, "key_v2": keys[r["task_id"]]}
        c = r.get("claimed") or {}
        claim = grade.ClaimedEvidence(
            url=c.get("url") or "", title=c.get("title") or "", h1=c.get("h1") or "",
            answer=c.get("answer") or "", key_text=c.get("key_text") or "",
            values=tuple(str(v) for v in (c.get("values") or ())), rejected=bool(c.get("rejected")))
        grades = {}
        for name, task in (("v1", v1_task), ("v2", v2_task)):
            ok, reason = grade.grade_page_answer(task, r["final_url"], r["page_text"], answer=r["answer"], claimed=claim)
            gated = ok and (r["arm"] != "script_first" or r["end_state"] == grade.PASS)
            grades[name] = ("PASS" if ok else "FAIL", reason, "PASS" if gated else "FAIL")
        lab = labels[r["hid"]]
        out.append({"row": r["hid"], "task_id": r["task_id"], "split": r["split"], "arm": r["arm"],
                    "end_state": r["end_state"], "sources": " ".join(r["sources"]),
                    "v1_page": grades["v1"][0], "v1_reason": grades["v1"][1], "v1_final": grades["v1"][2],
                    "v2_page": grades["v2"][0], "v2_reason": grades["v2"][1], "v2_final": grades["v2"][2],
                    "label": lab["label"], "deliverable": lab["deliverable"], "justification": lab["justification"]})
    return out


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ext, held = extdev_rows(), heldout_rows()
    write_csv(HERE / "extdev_rows.csv", ext)
    write_csv(HERE / "heldout_rows.csv", held)
    result = {
        "definition": "strict agreement: grader PASS <=> label 'correct'; partial counts as not correct",
        "extdev": {
            "v1_final_vs_original": table(ext, "v1_final", "label_original"),
            "v2_final_vs_original": table(ext, "v2_final", "label_original"),
            "v2_final_vs_corrected": table(ext, "v2_final", "label_corrected"),
            "v2_page_vs_original": table(ext, "v2_page", "label_original"),
            "v2_page_vs_corrected": table(ext, "v2_page", "label_corrected"),
            "corrections": [{k: r[k] for k in ("row", "label_original", "label_corrected", "correction")}
                            for r in ext if r["correction"]],
        },
        "heldout": {
            "v2_final_vs_blind": table(held, "v2_final", "label"),
            "v2_page_vs_blind": table(held, "v2_page", "label"),
            "v1_final_vs_blind": table(held, "v1_final", "label"),
            "v1_page_vs_blind": table(held, "v1_page", "label"),
            "labels": dict(Counter(r["label"] for r in held)),
        },
    }
    (HERE / "agreement.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for set_name, tables in result.items():
        if isinstance(tables, dict):
            for name, t in tables.items():
                if isinstance(t, dict) and "agree" in t:
                    print(f"{set_name:8} {name:24} n={t['n']} agree={t['agree']} ({t['agree_pct']}%) "
                          f"FA={t['false_accepts']} {t['false_accept_rows']} FR={t['false_rejects']} {t['false_reject_rows']}")


if __name__ == "__main__":
    main()
