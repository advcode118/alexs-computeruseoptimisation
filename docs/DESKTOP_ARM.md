# Desktop arm

Design only. This file adds no arm, client, task, judge, or probe. The harness is unchanged.

`script_first` is the browser measurement. One model call writes a Playwright script, local Chrome runs it, and every browser arm is graded on the live page. A desktop arm is a different surface: windows, named controls, and files, with no URL and no page text. This note is the boundary, so a later change can measure that surface on its own tasks.

The reserved arm id is `desktop`. Nothing in the tree selects it.

## What a later arm would measure

A later `desktop` arm would run a fixed list of non-browser tasks and write one row per task. The row says how long the task took and whether the OS evidence the harness read matched the judge. The browser comparison stays on the current arms and the current web tasks.

Per task, in a desktop log only:

| Field | Meaning |
| --- | --- |
| `success` | True only when the desktop judge passes. A model claim, a completion phrase, or a missing check is a failure. |
| `success_reason` | Why the judge passed or failed, including which evidence was missing. |
| `wall_ms` | Start to judged end. Failed tasks keep their time and stay out of the success mean. |
| `model_ms` | Time in the outer model. |
| `action_ms` | Time in OS actions. This is a desktop field. It is not the browser `tool_ms` bucket. |
| `other_ms` | `wall_ms` minus `model_ms` minus `action_ms`. |
| `steps` | Actions the model issued. One batch is one step. |
| `input_tokens`, `output_tokens`, `usd` | Tokens for this task, priced at the ledger rate the browser arms already use. Past `running_total_usd` stays as recorded. |
| `repair` | True when a second model call ran. The cap is one batch plus at most one repair, and it belongs to this arm alone. |
| `evidence` | What the harness read after the run: window title, accessible name, control value, or file bytes. The model does not supply these strings. |

The desktop report is mean wall time per success, median wall time per success, and the success count, on the desktop list only. One-shot rows and repair rows stay apart. The browser report fields stay where they are: `success_count`, `mean_wall_ms_per_success`, `median_wall_ms_per_success`, `steps_one_shot`, `steps_repair`, and `warm_replay_wall_ms`.

The first task shapes, when a later change adds a list:

1. A window the task names is open. The harness reads its title from the OS after the run.
2. One named text control holds the string the task asked to type. The harness reads the control value.
3. A path the task names contains the bytes the task asked to write. The harness reads the file.

Each task keeps the expected evidence on the judge side. The prompt gets the task text and the window name, control name, or path. It does not get the expected title, value, or bytes. A pass requires the harness read to match. The wrong window, the wrong control, a short read, and empty evidence fail. An unknown result is a failure.

Any later comparison is against other desktop runners on that same list. `playwright_mcp`, `diff_fast_act`, `macro_replay`, `stagehand`, `script_first`, `endpoint`, and `browser_use` stay on web tasks. When a live desktop probe is someday authorized, the outer model is `claude-sonnet-5-5`, the same id the browser arms use. This document does not authorize that probe.

## How it stays separate from script_first

`script_first` stays the browser arm, including its prompt, helpers, cache, and grade.

- The module, when a later PR adds it, is its own file. It does not import `bench.script_first`, `bench.script_helpers`, `bench.script_cache`, `bench.stagehand_local`, `bench.browser_use_arm`, or `proxy`.
- `desktop` is not a member of `ARMS`, `SELECTABLE_ARMS`, `HONEST_ARMS`, `BASELINE_ARMS`, or `WARM_ARMS`. The default probe stays `playwright_mcp`, `diff_fast_act`, `macro_replay`, and `stagehand`. `--honest` stays `playwright_mcp`, `script_first`, `stagehand`, and `browser_use`.
- A later registration refuses a selection that contains `desktop` together with any current arm. Until that registration exists, `resolve_arms` keeps rejecting the name. One invocation runs browser arms or the desktop arm.
- Desktop tasks live on their own list. They are not rows in `bench/tasks.py`, not WebVoyager ids, and not held-out web ids. They have no `start_url` and no `end_markers`.
- The desktop judge is its own function. It does not call `grade_observation`, `grade_arm`, `shared_end_state`, `evidence_verdict`, `check_url_contains`, or `check_text_present`. Those functions do not call the desktop judge. A grading change on the web path stays the same rule for every browser arm.
- The desktop prompt is its own string. `_SCRIPT_FIRST_PROMPT` stays the browser prompt. Desktop prompt text contains no `run_script`, `page.goto`, `page.evaluate`, `cu.click`, `cu.fill`, or `cu.press`.
- The runner does not launch Chrome, Playwright, CDP, `@playwright/mcp`, or a browser-use REPL. It takes no user-data-dir and does not touch the profile lock the browser arms already isolate.
- Rows go to `bench/runs/desktop_<stamp>.jsonl`. The browser summarizer and `plan_probe` do not read that file. A desktop row uses `arm: desktop`.
- A later desktop model call uses its own task-id prefix and its own per-run ceiling. It leaves `SCRIPT_FIRST_CLAUDE_BUDGET_USD` ($2) and `claude_budget_for` on the script_first path as they are. It does not reset the ledger.

## What not to build yet

This document is the whole change.

- An OS driver. No pointer, no screenshot loop, no vision grounder, no accessibility client, and no agent that writes files.
- Registration in `bench/arms.py` or `bench/probe.py`.
- A task file, a judge, fixtures, and tests. When tests come, they feed recorded evidence into the judge and do not open a window.
- A prompt cache or a warm-replay tier.
- Any edit to script_first, the shared web judge, arm timeouts, the model id, or the page-text source.
- A live probe, an Anthropic call, and a spend-ledger write.
- Edits to `NOTES.md`, `docs/HISTORY.md`, and the progress site.
- A router that picks browser or desktop, and a desktop action inside `script_first`.

## Later implementation

The first code change can add the module, the private task list, the fail-closed judge, and offline tests on recorded evidence. That change still runs no live probe, and it still imports nothing from `script_first`. The first numbers are cold wall time and success on the desktop list, in their own table.
