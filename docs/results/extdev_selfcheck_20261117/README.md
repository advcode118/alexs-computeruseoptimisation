# Experiment 3: self-check replay on extdev and development scripts

**Extdev scores use AI (Devin) hand labels from [PR #97](https://github.com/advcode118/alexs-computeruseoptimisation/pull/97), which no human has spot-checked; results are indicative only.** Dev/validation scores instead use the same grader-derived truth as `tools/cascade_precision.py`. The two truth standards are not directly comparable.

Question: does the precision-first self-check retain its development-set precision on external-development payloads?

**Result:** the current precision gate reproduces **85 TP / 5 FP (94.4% precision)** on the development reference and accepts **2 correct / 0 incorrect** extdev scripts under strict AI labels, sacrificing one correct ride-list answer. **Two accepted scripts are far too few to establish retained precision** (Wilson 95% precision interval 34.2–100%).
The plain runtime check has six extdev PASSes: 3 correct, 2 partial, 1 wrong. Additional in-sample tightenings do not improve the existing precision gate here; a naive task-term scope rule badly damages development recall.

## Data, unit and truth alignment

- **Unit: one saved script self-check verdict**, not a task, fallback or repaired pipeline result. Every script is replayed with its original earlier-script payloads using `bench.selfcheck_replay.replay_check`. FAIL and UNKNOWN both mean not accepted.
- **Extdev:** 22 paired tasks from replicate 1, model **`gpt-6.1-sol`, medium**, **original run count 1**. Source: `../extdev_control_20261117/raw/probe_20261117_012232.jsonl`. Original row labels: 3 correct / 5 partial / 14 wrong. There are **35 saved script checks across 20 tasks**; two tasks have no saved checks and do not become artificial negatives.
- PR #97 labels the **final task row**, not intermediate scripts. To avoid assigning successful repairs' labels to their failed first scripts, extdev truth is assigned only to a task's last saved check **whose URL and answer match the labelled final row**. This gives **16 aligned script units: 3 correct, 5 partial, 8 wrong**. Fifteen intermediate checks and four non-aligning last checks are unlabelled, not false negatives or true negatives. Non-aligning source lines: 11, 39, 43, 47; no-check rows: 63, 67. All six PASSes are aligned, so their precision denominator is unaffected; recall is conditional on the 16 aligned units, **not all 22 tasks**.
- **Strict truth:** correct is positive; partial and wrong are negative. **Partial-as-positive sensitivity:** correct and partial are positive, wrong negative. No AI labels are invented for earlier scripts.
- **Development/validation reference:** reuse the exact task selector, discovery and `build_units` grading used by `bench.cascade_precision.build_report` (the implementation behind `tools/cascade_precision.py`). **149 saved task sequences, 316 checks, 270 gradable / 46 unknown**, from 11 source files and 64 distinct tasks. Actual available checks are dev3: 191, dev4form: 49, dev4spa: 76. Raw validation-only aggregates cannot supply script payloads and are not invented. Models in these saved rows are **`gpt-6-luna`, medium**, not Sol. These are pooled historical runs/configurations, **not one controlled replicate**; run count is not reconstructible as a single experiment. No new live run was made. File/commit/SHA256 provenance is frozen in `sources.json`; all per-script task IDs are in `scripts.csv`.
- Dev truth is `grade_check` on each check's own evidence, not the parent task's final label. It uses the current grader through `grade_page_answer`, with absent page/selector evidence ungradable. The reference's plain mode uses the saved runtime verdict; our current mode recomputes it. The 14 saved PASS → replay UNKNOWN changes are all ungradable, so the gradable current/reference counts agree exactly. Forty-six checks are ungradable in total.

This choice deliberately reports fewer AI-labelled extdev negatives than the task-level 14 wrong, rather than silently copying task labels onto all 35 scripts. `scripts.csv` retains every check, its saved/replayed verdict, alignment explanation, predictions and rejection reasons.

## Variants (experiment-local only)

All additional rules were designed **after inspecting extdev failures**, so their extdev evaluation is **post-hoc/in-sample**, not evidence of generalization. Thresholds were fixed before the first replay and were not changed after seeing these results. No product or grader code changes.

| Variant | Acceptance rule |
|---|---|
| `current_runtime` | Recomputed `replay_check` PASS; no cascade precision gate |
| `current_precision` | Runtime PASS plus existing `bench.cascade.precision_check`: no multiline/tab answer, maximum 80 characters, no search URL, no navigation landing page, no claimed/live URL mismatch |
| `runtime_grounding` | Runtime PASS plus nonempty answer appearing as a case/whitespace-normalized contiguous span of trusted page text, or exactly equal to live URL; title/h1 alone no longer suffice |
| `runtime_no_dump` | Runtime PASS plus existing-style 80-character limit and no newline/tab; does not apply the other precision-gate rules |
| `runtime_scope` | Runtime PASS plus at least half the distinct `task_terms(description)` occurring as tokens in decoded live URL, title, h1 or answer (not the entire page body); evidence uses the same internal-punctuation preservation and edge stripping as task terms, without a term-count limit |
| `precision_all` | Current precision gate plus all three candidate checks |

These are intentionally simple falsifiable probes, not a new factual judge. Scope tokens can match the right entity on the wrong competition page and miss correct short answers with differently worded titles. Grounding can reject legitimate paraphrases and cannot tell whether an on-page value answers the task. The no-dump rule can reject correct lists.

## Replay scores

**Extdev AI-label scores below are indicative only, with no human spot-check; dev scores use the grader.** Unknown/unlabelled units are excluded from TP/FP/FN/TN, precision and recall: 46 development and 19 extdev units for every variant. Undefined rates would be `n/a`, not 0 or 100%.

| Truth set | Variant | TP | FP | FN | TN | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| dev_val_grader | current_runtime | 86 | 19 | 1 | 164 | 81.9% | 98.9% |
| dev_val_grader | current_precision | 85 | 5 | 2 | 178 | 94.4% | 97.7% |
| dev_val_grader | runtime_grounding | 81 | 17 | 6 | 166 | 82.7% | 93.1% |
| dev_val_grader | runtime_no_dump | 86 | 12 | 1 | 171 | 87.8% | 98.9% |
| dev_val_grader | runtime_scope | 16 | 6 | 71 | 177 | 72.7% | 18.4% |
| dev_val_grader | precision_all | 13 | 1 | 74 | 182 | 92.9% | 14.9% |
| extdev_strict_AI | current_runtime | 3 | 3 | 0 | 10 | 50.0% | 100.0% |
| extdev_strict_AI | current_precision | 2 | 0 | 1 | 13 | 100.0% | 66.7% |
| extdev_strict_AI | runtime_grounding | 3 | 3 | 0 | 10 | 50.0% | 100.0% |
| extdev_strict_AI | runtime_no_dump | 2 | 1 | 1 | 12 | 66.7% | 66.7% |
| extdev_strict_AI | runtime_scope | 3 | 1 | 0 | 12 | 75.0% | 100.0% |
| extdev_strict_AI | precision_all | 2 | 0 | 1 | 13 | 100.0% | 66.7% |
| extdev_partial_positive_AI | current_runtime | 5 | 1 | 3 | 7 | 83.3% | 62.5% |
| extdev_partial_positive_AI | current_precision | 2 | 0 | 6 | 8 | 100.0% | 25.0% |
| extdev_partial_positive_AI | runtime_grounding | 5 | 1 | 3 | 7 | 83.3% | 62.5% |
| extdev_partial_positive_AI | runtime_no_dump | 3 | 0 | 5 | 8 | 100.0% | 37.5% |
| extdev_partial_positive_AI | runtime_scope | 4 | 0 | 4 | 8 | 100.0% | 50.0% |
| extdev_partial_positive_AI | precision_all | 2 | 0 | 6 | 8 | 100.0% | 25.0% |

### All six extdev runtime PASSes

| Source line | Task | AI truth | Current precision gate | Why |
|---:|---|---|---|---|
| 19 | Frontier City family rides | Correct | Reject | Multiline list (true positive lost) |
| 27 | Airbnb Europe mansions | Correct | Accept | PASS |
| 71 | Ronaldo World Cup statistics | Wrong | Reject | Multiline table; returned Saudi Pro League statistics |
| 75 | Nets schedule | Correct | Accept | PASS; answer is live URL |
| 83 | SpotHero marketing | Partial | Reject | Multiline raw dump includes unrelated departments |
| 87 | Amazon puppy food | Partial | Reject | Search-results URL; requested star filter unconfirmed |

The current gate catches the known wrong competition answer **because it is multiline**, not because it understands World Cups. Grounding accepts all six runtime PASSes. Token overlap rejects the wrong Ronaldo answer and partial Amazon state, but accepts the partial SpotHero dump. The obvious dump rule catches the wrong table and partial careers dump but loses the correct ride list, and still accepts the partial Amazon state. Do not infer that new scope reasoning was validated.

The scope tokenizer was corrected after review: dotted versions, domains and compound terms now match verbatim, rather than splitting only the evidence on punctuation. This also removes incidental fragment matches inside compound evidence tokens; aggregate scope recall can therefore decrease. The fixed half-term threshold is unchanged. CSV, JSON and the table above were regenerated with the corrected tokenizer.

## Reproduce

From repository root, Python 3.11+ with project dev dependencies installed:

```sh
python docs/results/extdev_selfcheck_20261117/replay.py
source ~/.nvm/nvm.sh && source /home/ubuntu/repos/alexs-computeruseoptimisation/.venv/bin/activate && pytest -q bench/test_harness.py tests
```

The exact replay command run on this machine was `/home/ubuntu/repos/alexs-computeruseoptimisation/.venv/bin/python docs/results/extdev_selfcheck_20261117/replay.py`. `--output-dir EXISTING_DIRECTORY` writes a throwaway reproduction. `sources.json` pins the development source commits, including the historical file no longer in the worktree; those Git objects must be present. Initial discovery uses the same routine as `tools/cascade_precision.py`; subsequent replays use the pinned manifest rather than drifting with new branches.

Outputs: `results.json` includes confusion counts, precision/recall and Wilson precision intervals plus the exact 85/5 reference; `scripts.csv` contains 351 script-unit records; `sources.json` pins the 11 historical input files. The original 22 task labels are unchanged. **One deterministic offline pass per variant; 0 model calls, 0 browser runs, $0 provider/API spend.** No secrets, paid probes, ledger writes, task-key changes or saved-script execution. Session usage is not included in that API-spend statement.

## Limits and decision

This narrows the question but does not settle it: only six extdev runtime PASSes and two precision-gate acceptances; AI-only final-row labels; incomplete intermediate truth; different development/external models and truth standards; historical pooled development rows were already used for tuning. Candidate rules are extdev-in-sample. No statistical claim that precision generalizes and no recommendation to deploy these added rules follows. Keep the existing gate for now; the extra scope restriction has an especially poor observed recall tradeoff.

No wall-time speedup is measured: this is a verdict replay, not a browser/task run; no latency estimates or changes to the original mean/p90 are claimed. UI/visual checks are not applicable.

## Verification

Full Python aggregate check, using the exact pytest command above:

```text
1183 passed, 1 skipped in 35.10s
```

The tests reproduce CSV/JSON/manifest byte-for-byte in a throwaway directory; tie out the 22 original labels, 35 external checks and six PASSes; preserve intermediate-label unknowns; check strict versus partial-positive metrics and undefined rates; and exercise candidate rules with normal, empty and ungrounded/overlong evidence. Regression cases cover dotted versions, domains and compound terms beyond the task-term count limit, including rejection of split fragments. A throwaway consistency check also matched all 18 README confusion matrices to `results.json`.
