# Experiment 2: script_first extdev failure classification and offline fixes

**Scored against AI (Devin) hand labels from [PR #97](https://github.com/advcode118/alexs-computeruseoptimisation/pull/97), which no human has spot-checked. All results are indicative only.** New candidate outputs below are also assessed by this AI agent using that PR's rubric, not independently validated or scored by the frozen grader.

Question: why did script_first fail on extdev, and which candidate fixes can the saved evidence support without another model/browser run?

**Result:** 6/22 rows end in grammar rejection and 4/22 in a metadata-budget exception; these are the largest observed terminal classes, not proof that removing them solves the tasks.
**Replay:** evidence-only extraction projects 6 correct / 4 partial / 12 wrong versus 3 / 5 / 14 originally; the combined syntax, budget and extraction variant has 6 correct / 4 partial / 5 wrong / 7 unknown. Three partial rows become correct; no originally wrong row is established as fully recovered.

## Scope and reproduction

- Task set: **extdev replicate 1, the 22 paired attempted tasks**, all `script_first` rows in `../extdev_control_20261117/raw/probe_20261117_012232.jsonl` (source lines 3, 7, …, 87). Budget-skipped tasks are excluded. Full task IDs and descriptions remain in the source; IDs are repeated in the output CSVs.
- Original model: **`gpt-6.1-sol`, medium effort; run count 1**, one observed attempt sequence per task, including the original bounded repairs. The 35 saved scripts are not 35 independent task runs.
- Replay: one deterministic offline evaluation per candidate per saved row; **0 model calls, 0 browser runs, $0 provider/API spend**. No secret, network, ledger access, paid probe, or changes under `bench/`. This is not a claim about the cost of the original run or Devin session usage.
- Baseline labels: `../extdev_hand_labels_20261117/hand_labels.csv`, joined by task ID and checked against the source line. Rubric: correct does the whole task; partial does only part or cannot confirm a requirement; wrong includes no answer or reported failure.

From the repository root (Python 3.11+, installed project dependencies):

```sh
python docs/results/extdev_failures_20261117/classify.py
python docs/results/extdev_failures_20261117/replay_fixes.py
source ~/.nvm/nvm.sh && pytest -q bench/test_harness.py tests
```

On this machine the Python/pytest executables are from `/home/ubuntu/repos/alexs-computeruseoptimisation/.venv/bin`; activate that environment first. Both analysis commands accept `--output-dir EXISTING_DIRECTORY` for throwaway reproductions. `classify.py` writes `failures.csv`; `replay_fixes.py` writes it plus `replay.csv` (candidate answers and evidence assessments) and `replay.json` (attempt-level syntax and metadata diagnostics). Nothing runs saved JavaScript.

## Observed failure breakdown

Each row gets one primary terminal class, chosen before consulting its label: budget exception first, then final-script parse rejection, reported site challenge, wrong competition scope, raw-dump answer, unverified requested constraints, then the saved completion reason. Secondary/earlier failures remain in `failures.csv`'s `attempts` JSON, including saved turn verdict/time, parser error and check reason. A successful parser result alone is not an executed or correct script.

| Primary class | Correct | Partial | Wrong | Total |
|---|---:|---:|---:|---:|
| grammar_rejection | 0 | 0 | 6 | 6 |
| metadata_budget | 0 | 1 | 3 | 4 |
| no_answer | 0 | 0 | 2 | 2 |
| raw_dump | 0 | 1 | 0 | 1 |
| self_pass | 3 | 0 | 0 | 3 |
| site_challenge | 0 | 0 | 1 | 1 |
| ungrounded_answer | 0 | 2 | 1 | 3 |
| unverified_constraints | 0 | 1 | 0 | 1 |
| wrong_scope_self_pass | 0 | 0 | 1 | 1 |
| **Total** | **3** | **5** | **14** | **22** |

The `ungrounded_answer` class is an observed self-check reason, not a correctness judgment: NBA leaders and ICSE dates are partial on the AI labels, even though the self-check says the compound answer is absent. Metadata takes precedence over the raw dump on line 79. Raw dumps alone explain line 83. Line 87 returns only the sort order; the requested rating filter remains unconfirmed. Line 71's returned Saudi Pro League table visibly contradicts the requested Portugal World Cup scope despite self-PASS.

Across **35 logged scripts, 14 reject in the current parser (11 tasks)**. Re-parsing the exact scripts reproduces the rejection; the corresponding saved checks explicitly record those errors. `parse_task_script` validates the whole script before dispatch, so those rejected attempts cannot have navigated. This check also disproves a site-only explanation for those attempts. It does **not** prove the generated URL/selector would have worked: Great America's earlier accepted attempt reached a 404. A syntax fix alone cannot establish recovery there.

All four metadata rows carry the exact `Script result metadata exceeds tool-result budget; refusing to cut JSON` exception. The reachable harness path invokes `model_visible_script_result` after its self-check, and caps structured tool results again when building model messages; both can reach `budget_script_result`. That budgeter trims `text`, then refuses oversized non-text metadata. The exact failing payload/call site was **not saved**, so attribution to one of those sites is unverified. Lines 63/67 have zero logged scripts, not evidence that the intended task script executed. Line 39 has an earlier grammar rejection and final ICSE page text but no saved successful script payload. Line 79 has an earlier payload with a large claimed dump; it is a useful stress case, not proven to be the throwing payload. The Booking challenge on line 59 is the agent's saved report; the blank saved evidence cannot independently verify the site's challenge behavior.

### Did the original repair fix it?

| Repair outcome | Rows |
|---|---:|
| Fixed by final AI hand label (19, 27) | 2 |
| Repeated failure class, not fixed | 4 |
| Changed failure class, not fixed | 9 |
| Repair sent, no logged second script | 5 |
| No repair sent | 2 |

`repair_sent` is not proof that a second script ran. `fixed` here means a final correct AI label after an earlier failure, not independently relabelling the intermediate state. A repair that self-PASSes the wrong scope (71) or leaves constraints unverified (87) is not fixed.

## Offline candidate replay

The following scores are **AI-labelled, not human-spot-checked, indicative projections**. Untouched rows retain their PR #97 labels. Unknown is not a success or an accuracy improvement: it replaces the original label when a changed execution path needs a missing live page/model response. Combined gives an available evidence-only extraction precedence over a speculative execution path.

| Variant | Correct | Partial | Wrong | Unknown |
|---|---:|---:|---:|---:|
| baseline | 3 | 5 | 14 | 0 |
| regex_only | 3 | 4 | 8 | 7 |
| metadata_only | 3 | 4 | 11 | 4 |
| extraction_only | 6 | 4 | 12 | 0 |
| combined | 6 | 4 | 5 | 7 |

1. **Grammar relaxation:** a locally patched scanner recognizes regex tokens in locator arguments/options, preserving their source as a parse-only marker. It reuses `parse_task_script` → `parse_browser_action` rather than evaluating arbitrary JS. **21/35 scripts parse before; 28/35 after (+7 scripts, seven task paths unblocked; outcome unknown).** Newly accepted: line/attempt 11/2, 15/1, 31/1, 35/1, 39/1, 43/2, 51/2. This is a syntax feasibility probe, **not a working regex dispatcher**; product work would need a typed regex locator and runtime tests. Dynamic `goto` expressions, `filter({has: …})`, bare locators and banned `fetch` remain rejected (7 scripts). No arbitrary-script/fetch relaxation is proposed for deployment.
2. **Truncate rather than refuse metadata:** `truncate_metadata` uses the existing budgeter, dropping optional metadata (including claimed output if needed) and reserializing valid JSON rather than cutting JSON bytes; it preserves status and caps at 7,700 characters. On line 79's saved earlier payload this produces **7,133 characters after dropping `claimed`**, retaining the trusted page text for extraction. Dropping claims is explicitly lossy, not recovering their correctness. The other three error rows lack replayable payloads; the exact throwing payload is unavailable on all four. **No correct answer credited to metadata-only**; all four affected paths remain unknown. Line 39's saved text supports dates/place only; lines 63/67 have no saved answer evidence; line 79's text supports the event list only when extraction is added.
3. **Evidence-only extraction/trim:** six deliberately narrow, exploratory task-family templates read only that row's `grade_page_text` (never task keys, other arms' answers, or the grader). They emit the NBA first-ranked player and value in each displayed category; events before the navigation footer; the Marketing role card; the visible support number; ICSE dates; or ICSE dates/place. These are candidate output transformations, not new live successes. On empty/irrelevant text they return no output and retain the original label. New answers and their rubric assessment are recorded verbatim in `replay.csv`.

| Source line | Candidate output evidence | Assessment |
|---|---|---|
| 7 | Points Curry 32.0; assists Westbrook 11.7; 3-pointers Curry 5.3; rebounds Capela 14.3; blocks Gobert 2.7; steals Butler 2.1 | Partial → correct: all six displayed categories and values |
| 23 | Visible support telephone `+1 (844) 324-7768` | Wrong → partial: no evidence of a call/message; not counted as contacted support |
| 31 | May 23–28, 2004 | Still partial: no General Chair in saved text |
| 39 | Orlando, Florida, USA; May 19–25, 2002 | Wrong → partial: program committee chairs missing; General Chair is not a substitute |
| 79 | Nine named Fiesta Texas events, each also present as a dated card | Partial → correct: trims unrelated navigation/raw dump |
| 83 | Marketing Analyst — Chicago, IL | Partial → correct: excludes unrelated departments |

No broader navigation, chair-name guessing, or unsupported filter recovery is credited. Better waiting/navigation may help, but saved text without HTML cannot test it. `bench/offline_replay.py` requires exact-URL saved HTML/HAR; none accompanies these extdev attempts. `bench/selfcheck_replay.load_rows` is reused for consistency, but its grader-based scoring is deliberately **not** used, and its omission of no-check rows is repaired by loading those directly. No self-check variant or router simulation is part of experiment 2.

### Per-row projections

C/P/W/U = correct/partial/wrong/unknown; source lines identify full task IDs in both CSVs. All scores below have the same AI-label/indicative-only caveat.

| Line | Task (short name) | Baseline | Regex | Metadata | Extraction | Combined |
|---:|---|:---:|:---:|:---:|:---:|:---:|
| 3 | Great America thrill | W | W | W | W | W |
| 7 | NBA leaders | P | P | P | C | C |
| 11 | Dota DLC cart | W | U | W | W | U |
| 15 | Booking Times Square | W | U | W | W | U |
| 19 | Frontier City family | C | C | C | C | C |
| 23 | SpotHero contact | W | W | W | P | P |
| 27 | Airbnb mansions | C | C | C | C | C |
| 31 | ICSE 2004 chair | P | U | P | P | P |
| 35 | ICSE duplicate statement | W | U | W | W | U |
| 39 | ICSE 2002 chairs | W | U | U | P | P |
| 43 | Rovio anniversary | W | U | W | W | U |
| 47 | APEC tourism actions | W | W | W | W | W |
| 51 | APEC Peru arrivals | W | U | W | W | U |
| 55 | APEC ministers chair | W | W | W | W | W |
| 59 | Booking LA filters | W | W | W | W | W |
| 63 | HF first user message | W | W | U | W | U |
| 67 | HF TEI strengths | W | W | U | W | U |
| 71 | Ronaldo World Cups | W | W | W | W | W |
| 75 | Nets schedule | C | C | C | C | C |
| 79 | Fiesta Texas events | P | P | U | C | C |
| 83 | SpotHero marketing | P | P | P | C | C |
| 87 | Amazon puppy food | P | P | P | P | P |

## Limits and next decision

One run, 22 tasks, one original AI labeller; the original labels were not blind and no human will spot-check them. New candidate assessments are also from one AI agent. The saved text is capped, and no saved HTML/HAR permits navigation replay. Templates were developed after inspecting this development set, so these projections are not a held-out accuracy claim or evidence of generalized recovery. The combined unknown count is not a forecast of failures or successes. No new wall-time speedup is measured or projected: extraction and changed execution paths have no live timings. For context only, the 22 original saved `wall_ms` values have mean **10.267 s** and p90 **15.496 s** (linear interpolation); these timings are unchanged by offline output projections.

The lean next implementation candidate is typed regex locator support plus bounded metadata serialization, with explicit disclosure of dropped fields; the only evidence-backed full output recoveries here are the three extraction trims, all formerly partial. Whether either execution fix improves actual task success requires a separately authorized live run, not this replay.

## Verification

`source ~/.nvm/nvm.sh && source /home/ubuntu/repos/alexs-computeruseoptimisation/.venv/bin/activate && pytest -q bench/test_harness.py tests`

```text
1179 passed, 1 skipped in 42.69s
```

The new tests reproduce both commands in a throwaway output directory, compare all generated files byte-for-byte, tie every score table to 22 rows and the original 3/5/14 labels, check regex parsing without altering the product parser, exercise bounded valid-JSON serialization, and cover extraction with normal, empty and irrelevant evidence. No UI changed; visual verification is not applicable.
