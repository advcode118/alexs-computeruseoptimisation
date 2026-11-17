# Review: #79, #81, #82 against tip4

Reviewer: Opus 5.5 review sub-agent, 16 Nov 2026. This is a static, read-only review. I ran no tests, probes or API calls, and changed no code or git state. I read no heldout3, heldout4 or val3 rows, scripts or failures. Evidence figures below are quoted from the PR bodies and branch docs. I have not reproduced them.

Baseline: `t3/tip4` = `b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5`.

## PR identity and what merging actually brings

| PR | Branch head | GitHub base | Relation to tip4 | Effective diff vs tip4 |
|---|---|---|---|---|
| #79 | `9729d851a2b69e0c057784a2b5511941dae52029` | `t3/tip3` (**retarget needed**) | merge-base `b9ac977`, which is in tip4. Unique: `b5e3219`, `9729d85` and merge `4f8f80a` | 5 files: `bench/script_first.py` (+302/−78 in precision rules), `bench/selfcheck_replay.py`, 3 test files. Merges cleanly into tip4 (tree `8450a6ac`) |
| #81 | `69357dde5265fe3c37704b45b8af3f4f606ac422` | `t3/tip4` | 3 commits on tip4 (`f2cd379`, `585deb7`, `69357dd`) | `bench/harness.py` `_clean_url`, `bench/script_first.py` (runtime only), dev5title task set and verifier, tests |
| #82 | `d4f9d03abe278ebad44d1391cc67b4d3b83b8005` | `t3/tip4` | 1 commit on tip4 | New `bench/segments.py`, controller in `bench/harness.py`, flag-gated hooks in `script_first.py`, `arms.py`, `probe.py`, `openai_run.py`, tests and docs |

**Already included.** Part of #79's GitHub diff is already in tip4: `e7cf0dd` and `94b8bcd` (PR #75 `t3/verifier-false-reject-audit`, merged into tip4 at `dcb3fea`). The `heldout3_report.py`, `probe.py`, `docs/VERIFIER_FALSE_REJECT_AUDIT.md` and `tests/test_grade.py` changes therefore come in with no new content. Between #79's base and tip4, `bench/script_first.py` is byte-identical (`git diff b9ac977 b5b74b3 -- bench/script_first.py` is empty). #79's replay numbers were measured on this same self-check code.

**Textual conflicts.** None. `git merge-tree` is clean for tip4+#79, tip4+#81, #79+#81, #79+#82 and #81+#82.

## #79: narrower precision rules (runtime self-check only)

**Scope.** Every change is inside `precision_problem` (now `precision_hits` plus a wrapper that returns the first hit) and its helpers. It is called only from `runtime_verdict` (`script_first.py` ~L1346 at tip4). That function also feeds `strategy_nav.py:637`, `strategy_spa.py:861` and the #82 segment final path. The grader (`evidence_verdict`, `grade_page_answer`, `_returned_problem` at the grade call) is untouched. No markers, hosts or task strings are used. **No weakening of final grading or oracle access.**

**Precision/recall effect.** Each rule now needs stronger evidence before it fires, so the runtime check only gets more lenient. Recall can only rise or stay level, and runtime false accepts can only rise or stay level. Self-check FAILs can only fall. The PR's own dev numbers:

| Measure | tip3 rules | #79 rules | Kind |
|---|---|---|---|
| Per-script recall, 1256 saved dev scripts | 94.3% (477/506) | 97.0% (491/506) | offline replay, measured |
| Per-script precision, same scripts | 92.6% | 92.6% | offline replay, measured |
| dev3 paired, 6 tip3-made runs (240), final pass | 200 | 203 | offline replay. It is exact only because #79 is looser than the code that made the runs |
| dev3 paired, false accepts | 11 | 11 | same |
| dev3 live, 6 alternating pairs | 200/240, FA 12 | 192/240, FA 19 | live. The PR attributes the gap to model variance: first scripts were 39 vs 41 correct in pairs 1–3, and tip3's rules replayed on the after-runs accept the same 19 |
| heldout2 / old held-out paired | 17 / 38 (FA 2) | 18 / 38 (FA 2) | offline replay, n=1 run each |

Verdict: **useful, offline-measured, small (+3/240 on dev3 paired, about +1.3 pts), and in-sample.** dev3 was the tuning set for the narrowing. The live arm was *worse* (−8 passes, +7 FA). That difference is plausibly variance, but it is not evidence of benefit. Token-fragment narrowing also removes extra repair turns (6 of the 15 tip3 false rejects), so some latency and cost saving is likely. That saving is unmeasured as a separate figure.

**Lost catches.** title_overlap loses 1 catch (a container page). quantity_digit and wrong_row lose 2 and 3 flags each, which the PR says other rules catch. One error_page false reject remains.

## #81: title false-reject fixes plus dev5title

Changes:
1. `_clean_url` (`bench/harness.py`) keeps a balanced closing bracket. **This is not runtime-only.** `_remember_url` → `page_url_from_result` produces `steps[-1].page_url`, and that is the URL the grader scores (`harness.py:985,1576`; `script_first.py:2570`). The change applies to every arm. It is a parsing correction (`/wiki/The_Raven_(Poe)` was truncated to `…(Poe`), not a leniency rule, because the graded URL is now the real URL. But any comparison of #81 with a tip4 baseline must **re-grade both arms with the same parser**, or the pass delta mixes grader and agent changes.
2. `_site_name` picks the title part that the hostname spells ("GIMP - Luminosity Masks"). Runtime only (`script_first.py:1010` sits in the precision path).
3. `_returned_problem(..., ignore_spacing=True)` applies only at the runtime call (L1358) and only to `key_text` of 4+ words. The grade call (L731) keeps the exact match. Runtime only.
4. A new `dev5title` split (17 tasks) with a live key verifier and probe wiring. It also adds `SPLIT_DEV5TITLE` to the ledger-missing listing exemption in `plan_probe` (listing only; live execution still needs the ledger).

Evidence (PR body): dev5title Luna, 3 runs, 37/51 → 39/51 pass and FA 4 → 3, which the PR itself calls within noise. Replay: dev5title false rejects 10 → 7, false accepts unchanged. dev3, held-out, heldout2, dev4nav, dev4form and dev4spa show no change. dev5title was built and its key fixed in the same work, so it is in-sample.

Verdict: **useful, low risk, no measured accuracy gain beyond noise.** The URL fix is a true correctness fix that also affects baselines.

**Test-count discrepancy to check.** #81 reports "985 passed, 1 skipped", but tip4 is reported at 992 passed (`docs/GROUNDED_SEGMENTS.md` on #82), and #81 only adds tests. The parent should re-run the full suite on the merged tree rather than trust either figure.

## #79 + #81 together

- Both narrow `site_name` independently: #81 changes *which* part is the site, and #79 skips the rule when the asked object is an organisation word. These compose. #81's new test (`test_site_first_title_takes_the_site_from_the_host`) should still pass under #79: "tutorial's title" is not an `_ORG_OBJECT`, so the answer "GIMP" still FAILs on site_name, and "Luminosity Masks" is spared by `_TITLE_OBJECT` in `_heading_answer`. This is reasoned, not executed.
- #81 notes that "Celery 5.0 (singularity)" is rejected by quantity_digit. #79 restricts that rule to the asked object, so the combination may recover more dev5title false rejects than either PR alone. **This is hypothetical until replayed.**
- Both are monotone loosenings of the runtime check, so the combination can only raise runtime false accepts. The guard is the paired replay below, which counts FA directly.

## #82: grounded segments (opt-in, `CU_SF_SEGMENTS=1`)

**Flag off.** `segment_mode_for` returns `"off"` unless `arm == script_first` and `CU_SF_SEGMENTS=1`. Prompt, tools, `look_enabled`, `run_on_page` error text (`_state is None`), saved rows (`segment_result_fields` → `{}`) and the plan dict are unchanged. With `CU_SF_REPAIR=blind` the run logs `off:legacy` and takes the tip4 path. Merging is behaviour-neutral by construction. The full suite still has to confirm this on the merged tree.

**Oracle and grading.** The controller sets `client.end_markers = {}` and reads only the description and start URL. The final grade is the shared post-run read. `gate_final` only downgrades. PASS needs `final` + `runtime_verdict` PASS + `gate_final` + an http(s) URL (`harness.py` ~L1405–1440 at `d4f9d03`). **No weakening found.**

**Earlier blockers, checked in the d4f9d03 code (static check; the parent says the regressions were run, and I have not re-run them):**

| Finding | Status in code |
|---|---|
| B1: stall overrides PASS / same-URL wizard | Fixed. The override now applies only when `verdict.verdict != PASS` (L1420). `segment_made_progress` counts ok+mutations or changed url/title/h1/text/controls (`segments.py:79-92`) |
| B2: queued calls run unseen | Fixed. After any admitted tool, the rest of `calls[index+1:]` get "Not run" and the loop breaks (L1500-1506) |
| M1: repeat key | Fixed. `segment_request_key` keeps literal code, `final`, checks and errors (`segments.py:69-76`) |
| M2: `--honest` warm pass | Fixed. Warm is skipped for script_first when segments are on (`probe.py:1576`) |
| L1: failed moved segment repeatable | Fixed. `repeatable` needs `receipt["ok"]` (L1400) |

**Remaining risks (not blockers for an opt-in merge):**
- R1. Only one of the ten `.replace()` edits in `_segment_prompt` (`arms.py`) is asserted (`tests/test_segments.py:130`). If a later prompt edit changes any other source string, the segment prompt silently keeps tip4's one-shot wording. This is cheap to guard (assert that each source substring exists). It is a follow-up, not needed now.
- R2. Interaction with #79: `form_seen_before` reads `EarlierPage.stopped = payload.ok is False`. In segment mode, an acked non-final segment on the start page (ok=True, form filled but not submitted) does not count as "stopped". A final segment that returns pre-existing page text without submitting is then not caught by that rule. #79 narrows the rule further to start-page-only. This is a hypothetical precision gap. Check it in the probe's FA inspection on form tasks.
- R3. Segment wall is 45 s and calls are capped at 8. These differ from the default path's limits, so time-outs must be reported separately in any comparison.
- R4. L3/L7 from the earlier review still stand. Model-written expectations are not verification, and the OpenAI nested-schema pass-through is unverified live. Watch the first call for a 400.
- R5. Public form tasks get real POSTs. The receipt reduces replays, but it does not guarantee idempotency.

**Evidence: none on tasks.** 1102 passed, 1 skipped on synthetic fixtures. This is regression coverage, not accuracy. There is no live or replay measurement. The benefit is entirely hypothetical.

## Blockers summary

- **#79:** retarget from `t3/tip3` to the integration branch (or tip4) before merging. There is no code blocker.
- **#81:** none. Record that `_clean_url` changes grader input for all arms.
- **#82:** none for an opt-in merge, since flag-off is neutral and the review fixes are present. It **must not** be described as an improvement until the matched probe below. Its default stays off.

## Integration order

1. **#81** first. It is based on tip4, it is the grade-parser fix every later comparison should share, and it adds dev5title.
2. **#79** next (after the retarget). Run the full suite. Then run `test_selfcheck_precision.py`, `test_verifier_false_rejects.py`, `test_selfcheck_recall.py` and `test_strategy_review_regressions.py` together, to catch rule-composition surprises.
3. **#82** last, so its segment final path is tested against the merged self-check. Run `tests/test_segments.py tests/test_segments_harness.py tests/test_prompt_audit.py` and then the full suite.

## Minimal matched dev-only evaluation

**Stage 0: free, before any paid run.** Do an offline paired replay with `bench.selfcheck_replay` on the same saved dev rows at four commits: tip4, tip4+#81, tip4+#79 and tip4+#79+#81. Report `by_rule`, FR, CA and the paired "first accepted script" pass/FA.
- Use only dev3, heldout2, the old held-out 50 (treated as dev per project memory), dev4nav, dev4form, dev4spa and dev5title rows. Select files by run manifest or filename, and do not open heldout3, heldout4 or val3 files. `build_units` drops rows whose task id is not in `--split`, but `load_rows` still parses every file it is given. Pass only dev files.
- `--split` choices are `dev3|heldout2|held-out|dev` (tip4, #79 and #81 alike). For dev4*/dev5title, call `build_units(load_rows(paths), {t["id"]: t for t in tasks_for_split("dev5title")})` from `python -c`. That needs no code change. Keep `--show none`.
- Caveat: saved `page_url`s were cleaned by the old `_clean_url` during the run, so replay cannot show #81's bracket-URL fix. That fix only shows in new runs, where it applies to both arms alike. Report it separately: it is a grader-input fix, not a self-check gain.
- Decision rule: merge #79/#81 as runtime defaults only if combined paired FA ≤ tip4 FA + 1 across all dev rows and paired pass ≥ tip4. Otherwise keep the narrowing that holds and record the rest as offline-only.
- No live probe is needed for #79/#81. Live variance (±8 on 240) is larger than the effect, and replay is the exact paired comparison for looser rule sets.

**Stage 1: one paid probe, for #82 only.**
- Commit: the integration branch with #81+#79+#82 merged. Both arms use the same commit, and the only difference is `CU_SF_SEGMENTS=0` vs `1`.
- Model: `gpt-6-luna`, effort medium, script_first only, specialists off, cache cold in both arms.
- Tasks: dev4form (12) and dev4spa (12), the multi-step tasks segments target, plus dev3 (40) as a regression and one-shot-cost check. Total 64 tasks per run.
- Order: alternating off/on/off/on, 2 pairs, with the same start state. Do a 1-task smoke run with segments on first, to catch an OpenAI schema 400 (R4).
- Cost: tip4-style Luna runs cost about $0.025 per 40 tasks (from #79's $0.33 for about 14 runs). Segment mode may use up to 8 calls plus snapshots per task, so assume ≤ 5× that. The 2-pair total is likely under $0.50. Set a hard stop at $1.50 on the reconciled ledger, inside the $5 run and $20 project caps.
- Report: graded pass, false accepts (self PASS but grade FAIL), never-accepts, one-shot fraction, model calls per task, wall p50/p90, time-outs, $ per graded pass, and for forms any duplicate-submit evidence from receipts (R2, R5). Split the results by dev4form, dev4spa and dev3.
- Stop or decision: abort if segments-on FA exceeds off FA + 2 in pair 1. Call #82 "promising" only if dev4form+dev4spa pass rises by at least 3 tasks summed over the pairs, with no FA rise and no dev3 regression beyond 2 tasks. dev4form/dev4spa were specialist tune sets, so a positive result still needs a fresh blind set before any accuracy claim.

## Bottom line

| PR | Disposition | Evidence |
|---|---|---|
| #81 | Merge first | Correctness fixes. dev5title replay FR 10→7, and the live delta is noise. The grader URL fix applies to all arms |
| #79 | Retarget, then merge after Stage 0 confirms on the combined tree | Offline dev recall 94.3→97.0%, paired dev3 +3 with equal FA. In-sample; live inconclusive |
| #82 | Merge as opt-in (default off). Benefit unmeasured | Synthetic tests only. Needs the Stage 1 matched probe |
