# Scorer v2 (18 Nov 2026)

The frozen extdev grader agreed with the hand labels on 44 of 109 rows. Scorer
v2 grades each extdev task by its deliverable (answer, page, or both), with
written rules in [GRADER.md](../../GRADER.md) ("Scorer v2") and re-authored keys
in `bench/keys_extdev_v2.py`. Tasks outside extdev are graded exactly as before.

Results ([AGREEMENT](AGREEMENT.md)):

| Set | n | v1 agree | v2 agree | v2 false accepts |
|---|---:|---:|---:|---:|
| extdev, original labels (in-sample) | 109 | 40.4% | 99.1% | 1 |
| extdev, corrected labels (1 row) | 109 | — | 100.0% | 0 |
| held-out, blind labels | 55 | 90.9% | 92.7% | 0 |

Offline regrade: `python tools/regrade.py --out docs/results/regrade_20261118_v2`
(59 sources). Against `regrade_20261117`, only the five extdev control groups
change; all 76 common groups from older sets are identical and heldout3 has no
flips ([diff](../regrade_20261118_v2/diff_vs_20261117.json)). Extdev control pass
counts under v2 (v1 in brackets): browser_use default 21/22 (5), cascade 20/22
(4), script_first 3/22 (1), browser_use ultrafast 35/40 (6), smoke cascade 3/3
(0). The six later extdev sources (gpt-6.2 and Sol effort runs, not
hand-labelled) are in the regrade report only. These are re-grades of saved
rows, not new runs; the original result files keep their old-grader numbers.

## Files

| File | What |
|---|---|
| `AGREEMENT.md`, `agreement.json` | Agreement, confusion tables, false accepts/rejects, limits |
| `DISAGREEMENTS.md`, `.csv` | Each extdev row where v1 or v2 disagrees with the labels, classified |
| `KEY_CHANGES.md` | All 40 keys, v1 -> v2, with the page fact behind each change |
| `extdev_label_corrections.csv` | The one corrected extdev label, justified |
| `extdev_rows.csv`, `heldout_rows.csv` | Per-row grades (v1, v2; page and final) and labels |
| `heldout/` | Selection script and manifest (SHA-256), rows, derived keys, labeller rubric and inputs, blind labels |
| `agreement.py`, `build_disagreements.py`, `build_key_changes.py`, `compare_regrades.py` | Rebuild everything above offline |

Order of commits: held-out selection (`62788d6`) → failing v2 tests (`2836aab`)
→ rules, keys and derived held-out keys frozen (`aa9bda7`) → blind labels
(`5117d94`) → agreement computed once. A later commit (`2f0748f`) reverted four
uncited extdev key loosenings to their v1 content; it changes no outcome.
