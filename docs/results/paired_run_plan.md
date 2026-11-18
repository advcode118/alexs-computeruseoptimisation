# Paired live run plan: InteractiveStage vs browser-use (pre-registered)

Written and committed **before any paid call**. Nothing in this file may be changed after the
first paid call except the "Outcome" pointer at the end; deviations go in the results README.

## Question

1. Is the product path (script stage, then our own InteractiveStage) faster and cheaper than
   browser-use at similar accuracy?
2. Is our recovery stage better than using browser-use as the recovery stage?

## Arms (3), all `gpt-6.1-sol`, reasoning effort `medium`, 1 run each, headless

| Arm | Label | What runs |
|---|---|---|
| A | `cascade+interactive` | HTTP grounding, script stage (max 1 repair), precision check, then InteractiveStage (max 4 calls) |
| B | `cascade+browser_use` | same first stages, then browser-use 1.0.6 `ultrafast` as recovery (benchmark only) |
| C | `browser_use` | browser-use 1.0.6 `ultrafast` alone |

Code: branch `devin/paired-run` at the commit that adds this file: InteractiveStage (PR #110 head
`4e0f7c2`) combined with scorer v2 (PR #109 head `76f1ad9`) and the extval set (`628d04b`) in run
commit `ed00ff2`. No PR is merged into `main`. Environment: Windows 11, Python 3.14 venv `.venv` with `pip install -e .[dev,browser_use]`
(browser-use 1.0.6), local Chrome, `PYTHONUTF8=1`.

## Task set: `extval` (fresh, pre-registered)

18 tasks, split `extval`, file `bench/tasks_extval.py`. Selection, decisions and cited keys:
`docs/results/extval_20261118/` (README, KEYS.md, authoring_decisions.jsonl). Canonical SHA-256 of
the 18 tasks (ids, descriptions, start URLs, v2 keys):
`e17277c858da7f446b321431fd48379b2b8cbd989e396655c58dc12f03ed0a03` (checked by `tests/test_extval.py`).

- Deterministic walk of the existing external pool (Mind2Web-Live, WebWalkerQA, WebVoyager) in the
  pre-committed SHA-256 rank order, only sites hashed to extdev, at most 2 per site, read-only
  tasks with a key backed by a quoted page fact. 176 candidates rejected with recorded reasons.
  The procedure was committed (`7a30b02`) before any authoring; no description edits, no substitutions.
- Mix: 7 page tasks, 10 answer tasks, 1 both; sites: espn, spothero, sixflags, icse-conferences,
  rovio, ironhidegames, apec, cambridge, huggingface, amazon (2 each, sixflags/apec 1).
- Keys were written before any arm ran on these tasks; no model has seen them.

Known limits, stated before the run:
- Every extval site also has extdev tasks: this tests new tasks, not new sites.
- This machine geolocates to the UK. SpotHero shows a "not available in GB" notice and Amazon may
  localise. This affects all three arms equally; such tasks stay in the set and are reported.
- Live pages can drift (Amazon filter ids, ESPN fixtures, Hugging Face like counts). Keys are not
  edited after the run; a task whose page changed is reported as drift, not re-keyed.

Never heldout3, never a retired set, never heldout4 (kept untouched as the final claim set).

## Exact commands (bash, repo root, key read from file, never printed)

```bash
export PYTHONUTF8=1
export OPENAI_API_KEY="$(cat ~/.cu-optimisation/openai.key)"
export CU_OPENAI_SPEND_LEDGER=~/.cu-optimisation/openai-spend-paired-20261118.json   # new, empty ledger
export CU_OPENAI_PROJECT_BUDGET_USD=4.50                                             # hard stop for the whole run
P=".venv/Scripts/python -m bench.probe --execute --provider openai --model gpt-6.1-sol --effort medium"

# 0. Smoke (plumbing only, not a result): one task outside the set, all three arms.
CU_OPENAI_RUN_BUDGET_USD=0.40 CU_BU_MODE=ultrafast $P --split tuned --sweep-task --arms cascade --fallback interactive
CU_OPENAI_RUN_BUDGET_USD=0.40 CU_BU_MODE=ultrafast $P --split tuned --sweep-task --arms cascade --fallback browser_use
CU_OPENAI_RUN_BUDGET_USD=0.40 CU_BU_MODE=ultrafast $P --split tuned --sweep-task --arms browser_use

# 1-3. The run, cheapest arm first. Per-arm caps so one runaway task cannot eat another arm's share.
CU_OPENAI_RUN_BUDGET_USD=1.00                     $P --split extval --arms cascade --fallback interactive   # A
CU_OPENAI_RUN_BUDGET_USD=1.30 CU_BU_MODE=ultrafast $P --split extval --arms cascade --fallback browser_use   # B
CU_OPENAI_RUN_BUDGET_USD=1.90 CU_BU_MODE=ultrafast $P --split extval --arms browser_use                     # C
```

The smoke must show, per arm: a row per task, `model_calls` > 0, per-stage dicts summing to the
top-level totals, and the ledger total equal to the sum of row `usd` (plus the one-time $0.05
opening allowance). If any of these fails, stop and fix before step 1 (fix = failing test first).

## Cost estimate and stop rules

From the last committed run (`docs/results/extdev_control_20261117`, Sol medium): browser-use
ultrafast $0.078/task mean (max $0.455), cascade with browser-use recovery $0.051/task (max
$0.107). Our cascade with InteractiveStage is assumed similar to cascade (script stage $0.010/task
plus up to 4 short calls when it fires).

| Item | Tasks | $/task | Expected |
|---|---:|---:|---:|
| Opening allowance (new ledger) | | | 0.05 |
| Smoke (3 arms, 1 task) | 1 | ~0.14 | 0.14 |
| A cascade+interactive | 18 | ~0.05 | 0.90 |
| B cascade+browser_use | 18 | ~0.05 | 0.92 |
| C browser_use ultrafast | 18 | ~0.078 | 1.40 |
| **Total expected** | | | **~3.41** |

Hard stops: `CU_OPENAI_PROJECT_BUDGET_USD=4.50` on a dedicated ledger (checked before each task;
a task in flight can overshoot by at most one task, worst seen $0.455, so the worst case stays
under $5.00), plus the per-arm `CU_OPENAI_RUN_BUDGET_USD` caps above. If the smoke alone costs
more than $0.40, or if A's actual $/task exceeds $0.10, stop and report before continuing.
Arms cut short by a cap are reported as such; headline comparisons use only tasks every arm
finished.

Old ledgers are not touched. `~/.cu-optimisation/openai-spend.json` stays aborted with its
unresolved $0.012660 reservation (`32f86e…`); that reservation is outside this run's $5 and does
not change its cap.

## Metrics (per arm, all tasks attempted, failures included)

- **Pass rate**: graded offline with scorer v2 (PR #109, `bench/grade.py`) on the saved rows; UNKNOWN
  and "needs approval" are not passes. Also reported: the run-time v1 grade, for reference only.
- **Model calls** mean and p90 (cascade: script + recovery stage; browser-use: its LLM requests).
- **Wall time** mean and p90, measurement v2 (`docs/MEASUREMENT.md`): starts after Chrome setup,
  ends when the last agent stage ends; the post-run grade read is excluded for every arm.
- **$ per task**: row `usd` (ledger pricing incl. cache reads/writes), mean and total.
- Per-stage accounting for A and B (`stage_model_calls`, `stage_wall_ms`, `stage_usd`), how often
  each recovery stage fired, and `answered_by`.
- p90 = nearest-rank 90th percentile over all attempted tasks of that arm.

## Grading and checks

1. Regrade every row offline with scorer v2 at the PR #109 head (exact SHA recorded in the results).
2. **Blind labels for every row**: one labeller agent sees only the task, final URL, answer and
   saved page text plus the written v2 rubric, not grader verdicts or keys. Report v2-vs-label
   agreement (this is also the first test of v2 on tasks it was not written on).
3. **Hand spot-check of at least 10 rows** by the reporting agent, covering every arm, both
   passes and fails, every row where v2 and the blind label disagree, and every
   `answered_by=interactive` row.

## Reporting rules

- Commit raw rows (`docs/results/paired_run_20261118/raw/`), the ledger summary (no secrets) and a
  summary table: pass rate, calls mean/p90, wall mean/p90, $/task, with the exact commands above,
  task set hash, model, effort and run count (1).
- One run per arm, 18 tasks: no significance claim. Differences under ~2 tasks are noise.
- If we are not faster or not as accurate, say so plainly. README/site are updated only with
  these numbers, and only if they are honest.

## Outcome

(filled in after the run: link to results)
