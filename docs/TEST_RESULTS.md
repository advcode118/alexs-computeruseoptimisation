# Test results: current scoreboard

Last rewritten 17 Nov 2026 on `devin/1794873658-slim-cascade-core` (stacked on the frozen-grader branch, PR #84).
This file replaces the 10 Nov write-up (18 easy tasks, 2.8–3.2 s, 18/18). That write-up is in git history; it is not the current picture.

**Bottom line.** script_first is fast and cheap, but it is behind browser_use on accuracy on every held-out set we have, by 4–42 pp. No set in the repo shows script_first within 2 pp of the best baseline. The only configuration that gets close is a cascade: Sol script_first, then a browser_use fallback (95.7% vs 96.4% on heldout3 run 1, exploratory). That cascade is now the product direction; Sol (`gpt-6.1-sol`) is the default model.

## 1. How the numbers were graded

- Every pass rate below comes from the frozen arm-neutral grader `bench/grade.py` (SHA-256 `0e65aecefd0d99f2313b6124495014f7ac2bd7acfb1e9c190a625eec12241752`, rules in `docs/GRADER.md`), applied offline to saved runs by `python tools/regrade.py --out docs/results/regrade_20261116`. Full tables: `docs/results/regrade_20261116/report.md`; machine-readable: `regrade.json`.
- The grader accepts an answer by span, not substring, and caps answer length. That removes "dump the page" passes and stops failing correct prose. No paid calls were made to re-grade.
- Re-graded rates use the re-gradable subset only (rows whose saved fields allow it). Rows that need page text the JSONL does not contain are counted as unknown, not as failures.
- **heldout3, val3 and the tip4 gate cannot be re-graded:** their raw rows are on Tom's Windows box (`bench/runs/` is gitignored); only aggregates are in the repo. Their numbers below are on the **old** grader and are marked so.
- Wall times are as recorded. Old rows used different timers per arm (browser_use included Chrome launch, grade read and grading; MCP excluded the start-page peek; script_first overlapped launch with model writing). None of the saved rows can be corrected (`report.md`, "Wall time"). The new single timer (`docs/MEASUREMENT.md`) applies to future runs only. Treat every speed ratio below as approximate and probably flattering to script_first by 1–3 s per task.

## 2. Held-out accuracy (the sets that matter)

### heldout3: 138 tasks, Nov 13, old grader, interim (`docs/HELDOUT3_PLAN.md` "Result")

| Model | script_first | browser_use | Gap | Notes |
|---|---:|---:|---:|---|
| Luna medium | 54% (2 runs) | 96% (1 run) | **−42 pp**, CI [−51, −33] | self-check precision 84% [76, 91]; median 7.3 s vs 20.2 s |
| Sol medium | 88.4% (122/138, 1 run) | no planned run yet | — | self-check precision 95.3%; median 5.9 s |
| Sol medium, first 45 tasks | 91% (41/45) | 98% (44/45, exploratory partial) | **−7 pp** | median 5.8 s vs 17.3 s |

Gaps and caveats, stated plainly:
- Only 3 of the 16 pre-registered runs were finished; the Sol browser_use runs are still owed. Several runs were on a loaded machine (times inflated, pass rates unaffected).
- No offline re-grade was possible (raw rows absent). The span grader may move these numbers in either direction.
- "Recall 100%" in the interim JSON is the old circular definition; the independent recall (PR #75) has not been recomputed for heldout3.
- heldout3 task examples were inspected during later development, and the set is frozen on tip2 code. **It is retired as a claim set.** A fresh external claim set (heldout4) is required for any accuracy claim.

### Exploratory cascades from heldout3 run 1 (not pre-registered, `docs/results/heldout3_20261113/exploratory_cascades.md`)

| Path | Pass | $/task | Median | Mean | p90 |
|---|---:|---:|---:|---:|---:|
| Luna browser_use alone | 96.4% | 0.00130 | 20.2 s | 24.6 s | 47.8 s |
| Sol script_first alone | 88.4% | 0.00626 | 5.9 s | 8.3 s | 14.2 s |
| Luna script_first alone | 54.3% | 0.00054 | 7.3 s | 8.8 s | 16.4 s |
| **Sol script_first → Luna browser_use** | **95.7%** | 0.00638 | 5.9 s | 10.4 s | 15.4 s |
| Luna script_first → Luna browser_use | 89.1% | 0.00109 | 7.7 s | 19.7 s | 52.6 s |

False accepts (self-check PASS, graded fail): Luna 14/138, Sol 6/138. On Luna, false accepts alone cap any cascade at about 90%. This is why Sol is the default and why the self-check must be tuned for precision.

### heldout (50 tasks, Nov 11), re-graded with the frozen grader

| Model | script_first | browser_use | playwright_mcp |
|---|---:|---:|---:|
| Sol medium | 37/50 (74%) | 41/50 (82%) | 38/50 (76%) |
| Luna medium | 27/50 (54%) | 40/49 (82%) | 28/50 (56%) |

The re-grade changed none of these rows (one Luna browser_use row needs page text and is unknown).

### heldout2 (pooled saved runs), re-graded

| Arm | Rows | Pass (frozen grader) |
|---|---:|---:|
| browser_use | 80 | 100.0% |
| playwright_mcp | 40 | 75.0% |
| script_first | 166 | 71.7% (was 72.3%) |

## 3. Development sets (tuned on; not claims)

| Set | Arm | Rows (re-gradable) | Old grader | Frozen grader | Δ |
|---|---|---:|---:|---:|---:|
| dev3 | script_first | 326 | 76.4% | **69.6%** | −6.8 pp |
| dev4form | script_first | 24 | 45.8% | 41.7% | −4.2 pp |
| dev4nav | script_first | 48 | 70.8% | 66.7% | −4.2 pp |
| dev4spa | script_first | 48 | 85.4% | 85.4% | 0 |
| #82 pilot | script_first | 36 of 63 | 63.9% | 63.9% | 0 |
| Nov 10 (14 tasks) | script_first / browser_use / mcp / stagehand | 14 each | 100 / 85.7 / 85.7 / 78.6% | 100 / 92.9 / 85.7 / 78.6% | |

Every pass→fail flip is script_first and every one is `answer_too_long`: the script returned a table row, a block of page text or a whole JSON body that contained the value. The one fail→pass is browser_use (a correct prose answer on Hacker News). That confirms the old substring grade over-credited script_first and under-credited prose arms.

**val3 gate (tip4, Luna, old grader, not re-gradable):** off 79/120 (66%), all specialists on 79/120, +3.4 s mean latency. The specialists did not add a single pass; they have been deleted on this branch.

## 4. Speed (as recorded; see the timing caveat in §1)

| Set | script_first median / mean | browser_use median / mean | playwright_mcp median / mean |
|---|---:|---:|---:|
| held-out split, all saved runs | 5.0 / 6.8 s | 17.0 / 18.8 s | 13.6 / 15.4 s |
| heldout2 | 5.2 / 7.1 s | 17.7 / 18.1 s | 15.0 / 16.5 s |
| dev3 | 6.8 / 9.3 s | — | — |
| heldout3 Luna (old timer) | 7.3 / 8.8 s | 20.2 / 24.6 s | — |

browser_use was run at version 1.0.3 in default mode. `CU_BU_MODE=ultrafast` and newer browser-use versions have not been measured; the speed lead has to be re-established against them before it is claimed.

## 5. What is in the tree now

- Arms: `script_first` (one script, at most one grounded repair, self-check), `browser_use` (1.0.3), `playwright_mcp` (`@playwright/mcp` 0.0.84, `--isolated`), `stagehand` (selectable).
- Deleted on this branch (in git history and the PR docs): FORM/SPA/nav specialists, observe-first, segments (`CU_SF_SEGMENTS`; the #82 pilot was partial and inconclusive: 13 vs 12 matched passes at 53 vs 33 model calls and +3.1 s mean), the blind-repair legacy path, `diff_fast_act`, `macro_replay`, `endpoint`, and the dormant `CU_SF_*` / `CU_PROBE_ONLY_KIND` flags.

## 6. Next measurements (need Alex's go; $15 budget on the new ledger)

1. Baseline control: browser-use newest (default and `ultrafast`), Playwright MCP and current script_first, Sol medium, on a fresh external task sample. If ultrafast is ≤ 12 s at ≥ 95%, the target moves.
2. The cascade: Sol script_first (≤ 1 repair, precision-first self-check) → warm browser_use at the current URL. Report pass rate, **mean** and p90 wall time, and $/task against the best baseline.
3. heldout4: a new pre-registered external claim set, run once on the frozen cascade.

## 7. Approved Sol follow-up, 17 Nov 2026 (indicative only)

Browser_use-only comparison on #103's same 12 extdev tasks, one cold run per
setting: new `gpt-6.2-sol` low and `gpt-6.1-sol` medium, reused `gpt-6.2-sol`
medium. Exact commands, task IDs, per-setting time/cost/AI hand-label accuracy
and ICSE date sensitivity: [report](results/extdev_sol_effort_20261117/README.md).
These are AI-made labels, not human ground truth or a fresh general accuracy
claim. New recorded OpenAI spend $1.836904; final ledger $10.420862 / $22.
