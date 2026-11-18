# Paired live run, 18 Nov 2026: InteractiveStage vs browser-use

Pre-registered plan: [`../paired_run_plan.md`](../paired_run_plan.md), committed in `e89e7e4` before
any paid call. Model `gpt-6.1-sol`, effort `medium`, **one run per arm**, task set `extval`
(18 tasks, canonical SHA-256 `e17277c858da7f446b321431fd48379b2b8cbd989e396655c58dc12f03ed0a03`),
browser-use 1.0.6 `ultrafast`, Windows 11 / Python 3.14, run from branch `devin/paired-run`.

## Result

**Not a win.** Our own interactive recovery is the fastest and cheapest arm per task, but it is far
less accurate, and per *successful* task it is slower and more expensive than both browser-use arms.
Our script stage with browser-use as the recovery stage matches browser-use alone on accuracy
(12 vs 11 by the grader, 12 vs 13 by the blind labels: within noise) and is faster and cheaper per
task and per pass. browser-use stays a benchmark, so this
is the bar our own recovery stage has to reach.

| Arm | Attempted | Pass | Pass rate | Calls mean | Calls p90 | Wall mean (s) | Wall p90 (s) | $/task | $ total | Wall s/pass | $/pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cascade+interactive | 18 | 4 | 22.2% | 4.33 | 6 | 21.7 | 32.9 | 0.0412 | 0.7416 | 97.7 | 0.185 |
|  ↳ recovery stage fired / recovered | 14 | 1 | | | | | | | | | |
| cascade+browser_use | 18 | 12 | 66.7% | 8.89 | 24 | 41.1 | 85.4 | 0.0670 | 1.2063 | 61.7 | 0.101 |
|  ↳ recovery stage fired / recovered | 15 | 10 | | | | | | | | | |
| browser_use (ultrafast, alone) | 18 | 11 | 61.1% | 9.72 | 17 | 57.8 | 141.7 | 0.0715 | 1.2871 | 94.5 | 0.117 |

All 18 tasks were attempted by every arm (0 skipped), so every comparison is paired. Pass = scorer v2
(PR #109) at run time; `summarize.py` re-grades every row offline from the saved fields: 0 mismatches.
Wall time is measurement v2 (after Chrome setup, until the last agent stage ends, grade read excluded).
p90 is nearest-rank over the 18 tasks. One run of 18 tasks: differences of one or two tasks are noise.

Spend: ledger `openai-spend-paired-20261118.json` (new for this run) ends at **$3.422664**: 54 run rows
$3.2350 + smoke $0.0377 + $0.05 opening allowance + a $0.10 reserve for one crashed, unrecorded task
(deviation 1). Hard stop was $4.50; the $5 cap was never at risk. See `ledger_summary.json`.

## Why the interactive stage loses

Read from the saved segments (`interactive_scripts`, `interactive_segments` in the A rows):

1. **It must prove its answer on the page it ends on.** It reuses the script stage's runtime verdict
   and precision check, as specified. A question whose facts sit on two pages (e.g.
   `roviocon_theme_series`) can never pass, so the stage spends all 4 calls and delivers nothing
   even though its reported answer had both facts. browser-use as the recovery stage is not held to
   that self-check; only the post-run grader judges it. Arm A is therefore precision-first by design.
2. **Reading the page competes with acting.** The model reads pages with large `page.evaluate`
   calls; each read counts as a segment and fails the evidence check, and 4 calls run out.
3. **The gate cost one task** (`filter_spothero_wheelchair_times_square`): clicking "View parking
   details for …" was blocked as a commit control, almost certainly because the card's text has a
   booking word. That is the gate being conservative on a read-only task (a false positive).

## Checks

- **Hand spot-check, 13 rows** (`spot_check.csv`), all three arms, passes and fails: 9 agree with the
  grader, 1 is ambiguous and 3 do not. The disagreements are grader false rejects in the browser-use
  arms: an empty answer on a correct page (B, `nfl_super_bowl`), a correct page on `espn.co.uk` after
  a UK redirect (C, `real_madrid`), and a long answer the dump guard rejected (C, `hf_trainer`, ambiguous).
  None changes the conclusion; correcting them would widen the gap.
- **Blind labels**: one Opus labeller saw only task text, final URL, answer and saved page text
  (arms hidden, no grader verdicts, no keys). Labels: 31 correct, 14 partial, 9 wrong (`labels.csv`,
  `label_agreement.json`). **Scorer v2 agrees with the blind labels on 36 of 54 rows (66.7%)**:
  11 grader FAIL / label correct, 7 grader PASS / label not correct (6 of them partial).
  - This is the first test of scorer v2 on tasks it was not written on, and it is **well below the 90%
    target** reached in-sample on extdev (PR #109). Real v2 over-strictness seen here: the `both` key for
    Cambridge present perfect demands specific example sentences (B and C gave other valid examples),
    the dump guard rejects long correct Trainer write-ups (B, C), `espn.co.uk` after a UK redirect (C),
    and one Amazon filter URL and one SpotHero facility page (B).
  - Most grader-PASS / label-partial rows are the labeller being stricter than the cited keys: the fact
    (GDC prize, RovioCon theme, Gil tutorial, Jan 2024 update) is not in the 6,000-character saved page
    text, although the key cites it from the source page. One is the Super Bowl XLIX/50 ambiguity.
  - Label-based pass ("correct" only): cascade+interactive 6/18 (two of them answers our stage found but
    never accepted, so nothing was delivered), cascade+browser_use 12/18, browser_use alone 13/18.
    **The conclusion does not change:** our interactive path is far behind; the two browser-use arms
    are within noise of each other.

## Deviations from the plan

1. **Arm A crashed after 16 of 18 tasks.** An oversized script result made `budget_script_result`
   raise inside the interactive stage, which ended the probe and lost the 17th row and its spend.
   Fixed with a failing test first (PR #110, `b3d7477` test, `d4ad3a2` fix); the stage now ends a
   segment error as FAIL and keeps its usage. The 2 missing tasks were then run with the fixed code
   using `run_subset.py` (the same probe arguments, task list filtered only). The fix touches error
   paths only; the 16 earlier rows did not hit them. A conservative $0.10 reserve (above the
   largest arm-A task, $0.092) was added to the ledger for the lost task.
2. Arms ran one after another (A, then B, then C, about 45 minutes in total), not interleaved; live pages
   can drift between arms.
3. browser-use's anonymised telemetry was left on (its default: steps, cost, URLs without query
   strings, error messages; per its notice never task text or secrets).
4. This machine geolocates to the UK. It affected `spothero` (GB notice) and sent browser-use to
   `espn.co.uk` once. It applies to all arms equally but costs the browser-use arms one grader pass.

## Exact commands

```bash
export PYTHONUTF8=1 OPENAI_API_KEY="$(cat ~/.cu-optimisation/openai.key)"
export CU_OPENAI_SPEND_LEDGER=~/.cu-optimisation/openai-spend-paired-20261118.json CU_OPENAI_PROJECT_BUDGET_USD=4.50
P=".venv/Scripts/python -m bench.probe --execute --provider openai --model gpt-6.1-sol --effort medium"
# smoke (raw/smoke/): wv_wikipedia_search, all three arms, CU_OPENAI_RUN_BUDGET_USD=0.40
CU_OPENAI_RUN_BUDGET_USD=0.40 CU_BU_MODE=ultrafast $P --sweep-task --arms cascade --fallback interactive
CU_OPENAI_RUN_BUDGET_USD=0.40 CU_BU_MODE=ultrafast $P --sweep-task --arms cascade --fallback browser_use
CU_OPENAI_RUN_BUDGET_USD=0.40 CU_BU_MODE=ultrafast $P --sweep-task --arms browser_use
# A (tasks 1-16; crashed on 17)
CU_OPENAI_RUN_BUDGET_USD=1.00 $P --split extval --arms cascade --fallback interactive
# A (tasks 17-18, after the fix)
CU_OPENAI_RUN_BUDGET_USD=0.28 .venv/Scripts/python docs/results/paired_run_20261118/run_subset.py \
  extval_value_hf_trainer_parameters extval_filter_amazon_gaming_desktop -- \
  --execute --provider openai --model gpt-6.1-sol --effort medium --split extval --arms cascade --fallback interactive
# B and C
CU_OPENAI_RUN_BUDGET_USD=1.30 CU_BU_MODE=ultrafast $P --split extval --arms cascade --fallback browser_use
CU_OPENAI_RUN_BUDGET_USD=1.90 CU_BU_MODE=ultrafast $P --split extval --arms browser_use
```

## Files

- `raw/A_cascade_interactive.jsonl` (two probe files concatenated: `probe_20261118_125120` tasks 1-16,
  `probe_20261118_130319` tasks 17-18), `raw/B_cascade_browser_use.jsonl`, `raw/C_browser_use.jsonl`,
  `raw/smoke/`. Header records without `task_id` are probe run metadata.
- `summarize.py` → `summary.json` and the table above. `label_input.py` → `labels_input.jsonl` (blind
  input) and `label_map.json`. `labels.csv`: blind labels. `spot_check.csv`: hand check.
- `run_subset.py`: deviation 1. `ledger_summary.json`: totals only, no secrets.
