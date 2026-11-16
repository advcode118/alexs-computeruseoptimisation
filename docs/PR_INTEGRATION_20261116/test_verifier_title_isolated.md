# Offline usefulness test: #81 title fixes and #79 verifier recall

16 November 2026. **Recommendation: KEEP #81's correctness fixes; HOLD #79 as a default accuracy improvement.** #79's narrow paired dev3 gain is reproducible, but its live evidence is negative, and broader DEV replay finds one additional false accept. This is a local test report, not a request to change GitHub state.

## Identity and local state

- Worktree: `C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-692a26d3-c467b012bbcb488a`
- Branch: `t3/offline-verifier-title-tests`.
- Initial clean HEAD / baseline #82: **`d4f9d03abe278ebad44d1391cc67b4d3b83b8005`**.
- Underlying tip4: `b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5`. #82 does not change runtime-verdict logic; segments were explicitly off for baseline/comparison tests.
- #81 actual existing ref: `github/t3/fix-title-fa`, head `69357dde5265fe3c37704b45b8af3f4f606ac422`.
- #79 actual existing ref: `github/t3/verifier-recall`, head `9729d851a2b69e0c057784a2b5511941dae52029`.
- The supplied ref strings with appended short SHAs do not exist; the branch heads above match the assigned candidates.
- Local #82+#81 merge: **`2eeeab661f08554af974cc50ae37b0c268228365`**.
- Local #82+#81+#79 merge: **`c6a9f8ccac496c5b870c35d4bb84e8cbecae8d49`**.
- **Final local HEAD: `67db53dc4a74be4a3fa31daf326191672113a260`**, a test-only integration resolution on that merge.
- No textual merge conflicts. No production changes beyond the two candidate merges. The resolution changes one synthetic test fixture, described below.
- Reports/helpers/results under this directory are local, untracked artifacts. Only the useful test resolution was separately committed. Parent can cherry-pick `67db53d` if it chooses to include #79; do not indiscriminately take this entire test branch if holding #79.

Read before changes: `AGENTS.md`, `docs/HISTORY.md`, `NOTES.md`, shared audit `README.md` and `verifier_segments.md`; also candidate/source reports noted below. The shared integration worktree was read only.

## Focused checks

Python 3.14 on Windows; existing pytest/Playwright installation, no installs. `CU_SF_SEGMENTS=0`, `CU_SF_STRATEGY=""` were set for focused checks. Tests that explicitly test segment mode set their own flag.

Define the common selection **T**:

```text
tests/test_selfcheck_precision.py
tests/test_verifier_false_rejects.py
tests/test_selfcheck_replay.py
tests/test_runtime_plain_rules.py
tests/test_evidence_judge.py
tests/test_grade.py
tests/test_prompt_audit.py
tests/test_script_cache.py::test_the_live_run_never_reads_the_answer_key
```

Each invocation uses `python docs/PR_INTEGRATION_20261116/offline_guard.py pytest -q <selection>`.

| Revision | Exact selection beyond T | Result |
|---|---|---|
| baseline `d4f9d03` | none | **93 passed**, 1.89s |
| #81 merge `2eeeab6` | `tests/test_strategy_review_regressions.py docs/PR_INTEGRATION_20261116/test_title_boundaries.py` | **114 passed**, 25.61s |
| combined merge `c6a9f8c`, before resolution | same as #81, plus `tests/test_selfcheck_recall.py` | **129 passed, 1 failed**, 22.46s |
| combined with resolution subsequently committed as `67db53d` | same combined selection | **130 passed**, 33.28s |

Additional targeted #82 integration selection, combined tree with resolution:

```text
python -u docs/PR_INTEGRATION_20261116/offline_guard.py pytest -q
  tests/test_segments_harness.py::test_wizard_bypasses_cache_specialists_and_live_markers
  tests/test_segments_harness.py::test_final_expectations_only_downgrade
  tests/test_segments_harness.py::test_flag_off_and_legacy_keep_original_completion_and_rows
  tests/test_prompt_audit.py
```

**8 passed, 18.26s.** Covers live-marker isolation, grade-only downgrades, flag-off/legacy completion and prompt isolation.

Synthetic boundary checks added locally in `test_title_boundaries.py`:

- Balanced `()`, `[]`, `{}`, nested parentheses survive both `_clean_url` and `page_url_from_result`; extra surrounding punctuation is removed.
- Long key text differing only in spacing is runtime-PASS but still **final-grade FAIL**.
- Short key text, returned values and the actual answer retain exact matching.
- A site-first document title accepts the entry title but rejects the site's name.

### Test caveats and failed attempts

1. The initial launcher denied all Python sockets, including Windows asyncio's internal loopback socket pair. That run gave **82 passed / 11 failed**, all blocked by the launcher. Allowing loopback, with external Python networking still denied, gave the 93-pass baseline above. The failed log is retained as `baseline_tests.txt`; it is not a product regression.
2. An attempted broader `tests/test_segments_harness.py tests/test_prompt_audit.py` run timed out at the tool's 120-second limit without captured output. It supplies **no pass/fail evidence**. The explicit 8-test selection above completed afterward. Full-suite and full-segment verification remain with the parent after parallel heavy work finishes.
3. `bench.tasks` eagerly imports protected catalogs. The launcher substitutes **empty protected-catalog modules** before import, and refuses direct opens of protected catalog/evidence paths. Thus protected heldout3/4/val3 per-task data was not consulted. This deliberately does **not** validate those catalogs or the overall catalog's full-size invariants.
4. No public live catalog verifier was run, including `verify_dev5_title.py`. `tests/test_dev5_title.py` was not selected; its catalog invariants are not part of the results above.
5. Existing pytest fixtures create isolated disposable ledger files under pytest temporary directories. No project/shared ledger was edited or used to fund work.
6. Python networking guard allows loopback and does not sandbox browser subprocess networking. Selected Playwright tests use inspected synthetic routed pages; no public-site benchmark was invoked.
7. Test timings are execution diagnostics on a busy machine, not comparative product latency.

## Semantic integration conflict and safe resolution

The combined-tree failure was:

```text
tests/test_strategy_review_regressions.py::
  test_nav_history_normalization_does_not_bypass_the_earlier_page_check
```

The old fixture asked for a book author on an off-start-page catalog URL, then asserted `FAIL` with “before the form was submitted.” #79 intentionally narrows this rule to form tasks with a stopped earlier script on the start page; the old fixture therefore now PASSes.

Resolution in **`67db53d`**: use a fictional booking form at the start URL with an already-present “Booking received” message. Assert PASS with empty history, then assert FAIL with stopped-script history and retain the specific form-rule reason assertion. This still detects losing/mis-normalizing earlier-page history and tests the narrowed rule's actual scope. No runtime or grader change, no deleted assertion, no loosened grading. Applying this test fixture to the parent's combined tree is the only extra integration edit recommended here.

## Paired offline replay method

Helper: `replay_variants.py`, launched through `offline_guard.py`. Four **separate subprocesses**, with one git-showed runtime module per subprocess:

| Variant | Exact runtime source |
|---|---|
| baseline #82, off | commit `d4f9d03abe278ebad44d1391cc67b4d3b83b8005` |
| baseline+#81 | commit `2eeeab661f08554af974cc50ae37b0c268228365` |
| baseline+#79 | tree `e5a33218527ab5ffb1e3a0a464d0dda1ce46acc0` |
| baseline+#81+#79 | commit `c6a9f8ccac496c5b870c35d4bb84e8cbecae8d49` |

The #79-only tree comes from:

```text
git merge-tree --write-tree d4f9d03abe278ebad44d1391cc67b4d3b83b8005 9729d851a2b69e0c057784a2b5511941dae52029
```

It is not a branch or checkout. The actual local merges were #81 then #79.

For each label (`baseline82`, `pr81`, `pr79`, `pr81_pr79`):

```text
CU_SF_SEGMENTS=0
python docs/PR_INTEGRATION_20261116/offline_guard.py
  docs/PR_INTEGRATION_20261116/replay_variants.py <label>
```

- Stable replay helper: `bench/selfcheck_replay.py` from `d4f9d03`, using its `build_units`, `grade_check`, `confusion` and missing-page-evidence guard.
- Stable dependencies and **one common grader**: combined working tree at `c6a9f8c`; the later `67db53d` changes tests only.
- Runtime receives only the saved description, start URL, page URL and runtime payload/history. `selector_text` is removed from both current and earlier runtime payloads. No task dict, expected answer or marker is substituted into runtime.
- Independent grade receives the saved page/claim and the allowed DEV catalog markers; missing dynamic selector labels or missing page evidence remain **ungraded**, not false accepts.
- Each source file is selected from explicit DEV provenance before parsing. Mixed/unknown task IDs are rejected. Full-file SHA-256s are saved; no duplicate files were found. Repeat runs are retained, not collapsed by task or truncated payload.
- All four variants used identical source hashes and identical independent per-script grade vectors; verified by assertions. Output JSON records module, replay, common grader and probe hashes.
- No browser is opened for replay. Saved scripts are **not executed**. No expected-answer-key value is passed to `script_runtime_verdict`.
- `decisive_rejection_rule` is the first rejection per script, not #79's overlapping all-rule `by_rule` diagnostic. The baseline has no all-hit API; this distinction avoids presenting incompatible rule tallies as paired counts.

### Source provenance and unavailable data

**33 files / 752 task rows / 1,443 saved self-checks**:

1. #79's development scratch archive:
   `C:/Users/epicd/AppData/Local/Temp/claude/7ea2df158edfc897/e3f01de6-33ed-452c-901e-47b4a97380e5/scratchpad/data/`
   - `b_dev3_1.jsonl` through `b_dev3_6.jsonl`: six baseline runs.
   - `a_dev3_1.jsonl` through `a_dev3_6.jsonl`: six #79 runs.
   - Adjacent `pr_body.md` and `live_table.py` explicitly document before/after labels and dev3.
2. Documented full-row archives in this worktree:
   - `docs/results/form_specialist_20261114/dev3_{off,on}.jsonl`
   - `docs/results/form_specialist_20261114/dev4form_{off,on}.jsonl`
   - `docs/results/strategy_spa_20261114/dev3_{off,on}_first.jsonl`
   - `docs/results/strategy_spa_20261114/dev4spa_{off,on}_{first,final}.jsonl`
   - Their adjacent READMEs identify these as DEV evidence.
3. Eleven dev3/dev4nav source files identified and SHA-256 checked against the documented `docs/results/nav_reader_20261114_pre.jsonl` extract. Originals live in
   `C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-52ad5bf5-8d7126bdc5e6ded1/bench/runs/`.
   `docs/STRATEGY_NAV.md` explains the split labels and full-payload source files.

Exact paths, split/cohort labels, SHA-256s, row counts and check counts are in each `replay_*.json`'s `sources` list.

**dev5title replay is not reproduced.** #81's candidate note was found at
`C:/Users/epicd/AppData/Local/Temp/claude/aefc3d1fb457d997/50747b9b-4651-4d84-a466-0914d32585c1/scratchpad/pr-title.md`.
It reports FR 10→7 and unchanged FA, but does not map runs to exact files. `C:/Users/epicd/Projects/cuo-title/bench/runs/` contains ten generically named probe files. No positive file-level split manifest was located for those files, so they were **not opened or guessed from timestamps**. The old candidate helper `replay_all.py` discovers splits by opening broad input files first and deduplicates using a truncated payload prefix; that procedure was not reused. Accordingly, no trustworthy new dev5title paired count or #79+#81 title synergy claim is supplied.

Old `held-out`/`heldout2` archives were not replayed in this narrower assignment. Protected heldout3/4/val3 rows, answers and scripts were not opened.

## Results

### All 33 documented DEV files: identical script units

1,218 independently graded scripts; 225 ungraded in every variant.

| Runtime | True accept | False accept | False reject | True reject |
|---|---:|---:|---:|---:|
| baseline #82 off | 556 | 40 | 25 | 597 |
| +#81 | 556 | 40 | 25 | 597 |
| +#79 | 568 | 41 | 13 | 596 |
| +#81+#79 | 568 | 41 | 13 | 596 |

These are **per-script** counts; repeated scripts/runs are not independent tasks.

### First accepted saved script per task row

| Runtime | Pass | FA | No accepted saved script | No self-checks |
|---|---:|---:|---:|---:|
| baseline #82 off | 556 | 40 | 132 | 24 |
| +#81 | 556 | 40 | 132 | 24 |
| +#79 | 565 | 41 | 122 | 24 |
| +#81+#79 | 565 | 41 | 122 | 24 |

No first accepted script was ungraded. No-self-check rows are separately counted, not invented as failures or successful replay.

| Split | Rows | Baseline / +#81 pass, FA | +#79 / combined pass, FA | Ungraded scripts | Rows without checks |
|---|---:|---:|---:|---:|---:|
| dev3 | 644 | 507, 35 | 516, 35 | 190 | 4 |
| dev4nav | 36 | 25, 2 | 25, 2 | 9 | 0 |
| dev4form | 24 | 3, 3 | 3, 3 | 19 | 0 |
| dev4spa | 48 | 21, 0 | 21, 1 | 7 | 20 |

**Do not read the pooled table as final agent accuracy.** Specialist-on sources do not necessarily save their successful specialist completion as a replayable generic script. Some variants also reject the script at which the producing run stopped; unavailable later repair scripts cannot be simulated. There are 19 baseline / 14 combined rows with a recorded accepted check but no replay acceptance. These are censored/incomplete trajectories, not known eventual failures. The most defensible paired result is the homogeneous six-before-run cohort below.

### Reproduction of #79's strongest paired evidence

Six **baseline-produced** dev3 runs, 240 rows, same saved scripts:

| Runtime | First-accept pass | FA | Never accepts saved script |
|---|---:|---:|---:|
| baseline / +#81 | **200** | **11** | 29 |
| +#79 / combined | **203** | **11** | 26 |

This reproduces the candidate's +3/240 in-sample result. No baseline recorded-acceptance censoring in this cohort. It does not simulate newly generated repairs; the candidate's earlier accepts are available in the recorded trajectory.

On the six #79-produced dev3 runs, baseline replay gives 187 pass / 19 FA / 33 no-accept / 1 missing-check row; #79 gives 192 / 19 / 28 / 1. Five baseline rows are censored at the saved #79 acceptance, so that difference is not an exact baseline counterfactual.

### Saved live results, independently re-counted (no new run)

| Producing runtime | Rows | Saved final pass | Saved final FA | Saved no-accept |
|---|---:|---:|---:|---:|
| before #79 | 240 | **200** | **12** | 28 |
| after #79 | 240 | **192** | **19** | 29 |

The live outcome is negative: eight fewer passes and seven more false accepts. Model variance is plausible, but is not established as the cause and does not convert this into positive live evidence.

**Why baseline live FA is 12 but paired replay FA is 11:** in `b_dev3_5.jsonl`, the `dev3_value_exif_gpsaltref` row records final self-PASS/grade-FAIL, but its only saved self-check is a stopped FAIL. Replay cannot reconstruct that final acceptance from the saved self-check trajectory. No grade or expected value was changed to reconcile it.

### Rule effects and lost catch

Decisive-rejection counts across all 1,218 graded scripts:

| Rule | Baseline FR / caught FA | Combined FR / caught FA |
|---|---:|---:|
| form_seen_before | 7 / 8 | 0 / 8 |
| token_fragment | 5 / 1 | 0 / 1 |
| title_overlap | 0 / 1 | 0 / 0 |
| wrong_row | 0 / 6 | 0 / 3 |
| quantity_digit | 0 / 16 | 0 / 17 |
| heading_value | 1 / 17 | 1 / 19 |
| item_row | 0 / 15 | 0 / 15 |
| site_name | 0 / 7 | 0 / 7 |

The wrong-row count moves to other decisive rules rather than becoming extra accepts. The actual added false acceptance is **`dev4spa_spa_naiveui_beatles`**, first SPA off checkpoint: baseline rejects on `title_overlap`, #79 accepts, and the unchanged independent grade fails. This accounts for the pooled FA increase by one.

The 12 removed script FRs are seven `form_seen_before` and five `token_fragment`; only nine improve first-accept row outcomes because some baseline runs later recover. There is no measured latency saving in this offline replay.

## Grading and interpretation

- #81 `_clean_url` changes **grader input for all arms**, not merely runtime policy. It corrects loss of genuine URL closing brackets. Replaying already-cleaned saved `page_url`s cannot restore the original URL; no inferred/corrected URL was substituted here.
- All runtime comparisons use the same saved URLs and common final grader. A future live comparison must give both arms the same corrected parser.
- #81 runtime `key_text` spacing relaxation does not change the grade's default exact comparison. Synthetic tests explicitly prove runtime-PASS/final-FAIL for a spacing-only discrepancy.
- No grader weakening or answer-key access was introduced by either merge or the local fixture resolution.
- These replay grades use the current allowed DEV task definitions. Older task keys and incomplete saved observations can differ from historical final grades. The report retains the distinction; it does not claim exact reproduction of #79's historical 1,256-script aggregate (a different corpus) or #81's old title replay.
- The prior audit's numeric Stage-0 condition (pass no worse, FA at most +1) is met on this **available subset**, exactly at its FA tolerance. The complete gate is not demonstrated: dev5title is unverified, older DEV sets were not included, specialist trajectories are incomplete, and observed live evidence remains negative.

## Handback

1. **#81: keep** the URL/parser and narrowly scoped title/key-text correctness fixes. Focused tests pass. Claim correctness, not proven accuracy gain; title replay and combined full-suite work remain open.
2. **#79: hold as a default change.** There is a real small, in-sample paired gain, but the broader DEV replay loses a catch and the actual live comparison is negative. Do not market it as demonstrated usefulness on fresh tasks. This report does not tune a subset of rules against the discovered DEV failure.
3. If parent nevertheless elects to integrate #79 under its stated DEV gate, apply the fixture resolution `67db53d`, preserve the strict grader, and disclose the +1 lost catch and the incomplete gate. No textual conflicts were encountered.
4. Parent runs the final combined full suite after heavy parallel work ends. Historical “985 versus 992” whole-suite counts remain unverified here.

Artifacts in this directory: `replay_{baseline82,pr81,pr79,pr81_pr79}.json` (provenance, hashes, aggregate and DEV verdict/index records), matching `.txt` aggregate outputs, focused-test logs, `offline_guard.py`, `replay_variants.py`, and `test_title_boundaries.py`.

No paid/API call, public live benchmark, install, shared-ledger edit, GitHub push/retarget/merge/close, watch, subagent, branch deletion or additional checkout was performed.
