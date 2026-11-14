# Exploratory: heldout3 results by task kind

The plan lists "results by task kind" as exploratory only. Totals only; no per-task rows were read. Runs: Luna script_first runs 1–2, Sol script_first run 1, Luna browser_use run 1.

## Luna script_first (276 rows)

| Kind | Rows | Pass | Self-check FAIL | False accept | Repair sent | Repaired and passed |
|---|---|---|---|---|---|---|
| nav | 72 | 61% | 29% | 10% | 67% | 46% |
| value | 72 | 72% | 18% | 10% | 46% | 55% |
| title | 28 | 54% | 21% | 25% | 68% | 58% |
| search | 40 | 22% | 68% | 10% | 92% | 19% |
| form | 38 | 45% | 55% | 0% | 82% | 32% |
| spa/js | 26 | 38% | 58% | 4% | 85% | 27% |

- The first script passes its self-check on 31% of tasks (85% of those are graded passes, median 3.6 s). A repair is sent on 69% (39% graded passes, median 9.0 s).
- Failure reason shapes over 129 failed rows: 66 ended on a URL without the expected part, 18 ended with no completion, 10 returned no answer for a value task, 9 gave an answer that does not satisfy the marker, 8 returned evidence not on the page, 5 stopped on a search-results page, 4 hit a fill timeout.

## Sol script_first (138 rows)

| Kind | Rows | Pass | Self-check FAIL | False accept | Repair sent | Repaired and passed |
|---|---|---|---|---|---|---|
| nav | 36 | 100% | 0% | 0% | 14% | 100% |
| value | 36 | 100% | 0% | 0% | 22% | 100% |
| title | 14 | 86% | 7% | 7% | 43% | 83% |
| search | 20 | 70% | 25% | 5% | 75% | 60% |
| form | 19 | 74% | 16% | 11% | 53% | 60% |
| spa/js | 13 | 77% | 8% | 15% | 54% | 71% |

The first script passes its self-check on 63% of tasks (97% graded passes, median 4.5 s).

## Luna browser_use (138 rows)

nav 34/36, value 34/36, title 13/14, search 20/20, form 19/19, spa/js 13/13.
