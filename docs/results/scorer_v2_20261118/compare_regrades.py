"""Compare the scorer-v2 regrade with the 17 Nov regrade, per source and arm group.

Run from the repository root after `python tools/regrade.py --out docs/results/regrade_20261118_v2`:
    python docs/results/scorer_v2_20261118/compare_regrades.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / "docs/results/regrade_20261117/regrade.json"
NEW = ROOT / "docs/results/regrade_20261118_v2/regrade.json"


def groups(report):
    out = {}
    for source in report["sources"]:
        for g in source["groups"]:
            out[(source["path"], source["sha256"], g["arm"], g["split"])] = g
    return out


def main():
    old, new = json.loads(OLD.read_text(encoding="utf-8")), json.loads(NEW.read_text(encoding="utf-8"))
    a, b = groups(old), groups(new)
    common = sorted(set(a) & set(b))
    changed = [{"path": k[0], "arm": k[2], "split": k[3], "old_new_pass": a[k]["new_pass"],
                "v2_new_pass": b[k]["new_pass"], "regradable": b[k]["regradable"]}
               for k in common if (a[k]["new_pass"], a[k]["regradable"]) != (b[k]["new_pass"], b[k]["regradable"])]
    only_new = sorted({k[0] for k in set(b) - set(a)})
    only_old = sorted({k[0] for k in set(a) - set(b)})
    result = {"old_grader_sha256": old["grader_sha256"], "new_grader_sha256": new["grader_sha256"],
              "common_groups": len(common), "changed_groups": changed,
              "changed_splits": sorted({c["split"] for c in changed}),
              "sources_only_in_new": only_new, "sources_only_in_old": only_old,
              "old_flips": len(old["flipped_rows"]), "new_flips": len(new["flipped_rows"]),
              "heldout3_flips_old": old["heldout3_flips"], "heldout3_flips_new": new["heldout3_flips"]}
    (ROOT / "docs/results/regrade_20261118_v2/diff_vs_20261117.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "changed_groups"}, indent=1))
    for c in changed:
        print(c)


if __name__ == "__main__":
    main()
