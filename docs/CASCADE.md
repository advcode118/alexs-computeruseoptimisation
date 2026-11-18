# Cascade arm

Select explicitly with `python -m bench.probe --arms cascade` (or add
`--provider openai`). It is not a default baseline. Both stages use the same
provider, model and effort; OpenAI defaults to gpt-6.1-sol / medium.

A plain HTTP read supplies static title, first h1, search forms and up to 80
links to the first script prompt only. HTTP failure is nonfatal. Links are
prioritized by task terms when capped. This is grounding, not a live DOM claim.
The script runner retains its existing one-repair maximum. A PASS must also
survive structural precision checks: concise single-line answer, non-search
URL, non-landing page for navigation tasks, and matching claimed/live URL.

`--fallback` picks the recovery stage for a rejected script attempt:

- `interactive` (default, the product path, `bench/interactive.py`): the same
  model continues on the same page in short segments, at most 4 calls, each at
  most 6 lines. Every segment runs through `ScriptFirstClient.call_tool("run_script")`,
  so the same grammar, executor and ActionGate apply, and is judged by the same
  `script_runtime_verdict` plus `precision_check`. After each segment the goal
  checkpoints are evaluated (row field `interactive_checkpoints`) and unmet ones
  are shown to the model with a fresh `page_snapshot`; they do not gate PASS.
  A screenshot is sent only when the task profile is `visual`. A gate block ends
  the task as UNKNOWN / needs approval. No answer key is read during the stage.
- `browser_use`: benchmark comparison only, never the product fallback.
- `none`: stop after the script stage.

A task stopped for approval (profile or gate block) is never a pass in the row.

With `browser_use`, rejected attempts hand off via CDP in the same Chrome, at its
current URL. The handoff carries the original task, URL history and rule name,
not the scripted answer or page evidence. Navigation is allowed. Only the
harness owns and closes Chrome. Post-run grading remains unchanged.

## Rows and timing

`answered_by` is script, interactive, browser_use or none (no accepted answer,
approval needed, or browser_use error). The stage dicts below use the selected
recovery stage's name (`interactive` or `browser_use`).
`handoff_reason` names the rejecting rule or verdict. `stage_wall_ms` contains
grounding, script and browser_use; `stage_usd` and `stage_tokens` contain each
model stage. Top-level usage sums both stages, including cache reads/writes.
`grounding` records ok, error, link/form counts and h1. Script `self_checks`,
`scripts`, `task_description` and `start_url` are retained for replay.

Wall-clock version 2 starts after Chrome setup, before HTTP grounding, and
ends when the last agent run ends. The intermediate script grade read is
subtracted; the final browser grade read happens after the timing boundary.

## Offline precision

Run `python tools/cascade_precision.py`. It discovers the same historical
sources as regrade, excludes every held* split, and uses only dev*/val* rows.
Truth comes from the frozen grader through selfcheck replay, never from live
task markers. Wilson 95% CIs and per-rule catches are in
`results/cascade_selfcheck_20261117/precision.json`.

| Unit | Mode | TP | FP | FN | TN | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| script | plain | 86 | 19 | 1 | 164 | 81.9% | 98.9% |
| script | precision | 85 | 5 | 2 | 178 | 94.4% | 97.7% |
| run-final | plain | 86 | 19 | 1 | 25 | 81.9% | 98.9% |
| run-final | precision | 85 | 5 | 2 | 39 | 94.4% | 97.7% |

The final counts differ from the prototype's 67/12/1/23 and 66/3/2/32.
Here each saved row contributes its own final check (131 graded final units,
versus the prototype's 103); historical paired runs are separate rows, not
collapsed by task. The script totals match exactly.
The precise prototype grouping was not available to reproduce its final totals.

These rules were tuned on these dev rows, not an independent claim set.
Remaining false accepts are wrong-value-on-right-page cases a structural
check cannot see. No live model probes were used for this implementation.
