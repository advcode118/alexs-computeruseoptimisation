# Matched development pilot, 16 November 2026

Purpose: decide whether the remaining opt-in observation/segment PRs are useful
enough to integrate. This is development triage, not a new blind accuracy claim.
Plan written before new comparative results. Existing historical evidence and
offline correctness tests inform candidate selection.

## Fixed foundation

- One frozen experimental checkout containing tip4 + #81 + #74 + #82.
- #79 stays out: its saved live evidence is negative.
- Same corrected URL parser and unchanged independent final grader for all arms.
- Script-first only; Luna at medium effort; fresh browser and cold cache per task.
- Specialist strategies off, look off except where segment mode exposes its tool,
  grounded repair and maximum three repairs for every applicable condition.
- Budget-instrumented wall time must be labelled as such.

## Task selection

Select by identifiers, without inspecting expected answers or new results:

- dev3: four navigation, four value and four search tasks.
- dev4form: six tasks.
- dev4spa: six tasks.

Within each named group sort by SHA-256 of
`pr-integration-20261116:<task_id>` and take the first required count.
Record the resulting 24 unique IDs and catalog/runtime source hashes before
launch. Keep the same IDs in every condition and repetition. Do not replace a
task because an agent fails it. Record environment failures separately.

## Conditions and order

1. Baseline: `CU_PAGE_SUMMARY=0`, `CU_SF_SEGMENTS=0`.
2. Observe-first: `CU_PAGE_SUMMARY=1`, `CU_SF_SEGMENTS=0`.
3. Segments: `CU_PAGE_SUMMARY=0`, `CU_SF_SEGMENTS=1`.

Two repetitions, with condition order reversed:

- First: baseline, observe-first, segments.
- Second: segments, observe-first, baseline.

Each condition covers all 24 selected tasks. Use the same split ordering and
task order within a repetition. Do not enable both experimental flags here.
Existing per-condition call/deadline differences are product settings, so this
is a policy comparison, not an equal-inference-budget causal experiment.

## Admission and stopping

- First run one separate schema/accounting smoke task; exclude it from results.
- Only the reviewed serialized canonical-ledger runner may make paid calls.
- Reconciled opening project charge: $14.579971.
- Default total evaluation allowance: $1.50 across all invocations, including
  smoke, with the existing $5 per-run / $20 project caps additionally enforced.
- Retain unresolved reservations and halt on unknown accounting/configuration
  changes; do not retry automatically or reset the ledger.
- After repetition one, stop a candidate before repetition two if its
  runtime-PASS/final-FAIL count exceeds baseline by more than two.
- Stop the campaign on a systematic provider/schema failure. Keep partial
  rows, label incomplete coverage, and do not claim a full paired result.
- Heavy parallel offline suites must finish before comparative timing runs.

## Decision and reporting

Report per-task success, runtime verdict, independent page/answer grade, model
calls, primitive script steps, total tool steps, cost and wall time. Aggregate
false accepts (`end_state == PASS` and final success false), false rejects
(independent page/answer grade true but runtime did not PASS), first-script
success, mean/median/p90 wall time and total cost/time per passed task.

Candidate is promising for opt-in integration if pooled matched passes improve
by at least two, false accepts do not increase, and no task-family loss exceeds
two passes. Equal accuracy with lower total cost/time is another useful outcome;
report the magnitude and repeat consistency rather than implying significance.
Contradictory repetitions or incomplete runs are inconclusive. Synthetic
correctness fixes can still be accepted as correctness work without an accuracy
claim; experimental defaults remain off.

Existing historical evidence can support keeping an opt-in feature if this
small pilot is inconclusive, but cannot turn a regression into a measured win.
Do not enable a default merely because its tests pass. No further paid rounds
are automatically authorized by a failure to meet the bar.
