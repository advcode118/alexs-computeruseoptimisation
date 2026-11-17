# Extdev control, replicate 1

Sol (`gpt-6.1-sol`), medium effort, 40 ordered extdev tasks. Both invocations
finished normally. **This is not a complete, valid four-arm comparison:** the
default invocation exhausted its shared run budget after 22 tasks per arm,
and all 22 attempted Playwright MCP rows failed to launch Chrome.

## Raw files and spend

| Invocation | Raw JSONL | Task rows | Ledger before | Ledger after |
|---|---|---:|---:|---:|
| Default, four arms | `probe_20261117_012232.jsonl` | 160 | $0.155299 | $3.178912 |
| Ultrafast, browser-use only | `probe_20261117_015118.jsonl` | 40 | $3.178912 | $6.277727 |

The ledger was explicitly read between invocations: $3.178912 was below the
$4.50 gate, so ultrafast was allowed. Project cap: $9.00. Run cap: $3.00 per
invocation, checked between tasks rather than within an in-flight task.
Consequently actual invocation usage was $3.023613 and $3.098815 respectively.
No extra invocation was made to fill the default budget skips.

`default_rep1.json` and `ultrafast_rep1.json` capture invocation metadata;
the corresponding `.log` files retain execution output. Browser-use and
cascade rows include `browser_use_mode`: `default` or `ultrafast`, including
budget-skipped rows.

## Requested all-row aggregates

Means and medians below include budget skips (zero cost and zero wall time).
Passes are the frozen grader's `success` field, not browser-use's internal judge.

| Arm | Mode | Rows | Attempted | Skipped | Passes | Total USD | Mean USD/row | Median wall_ms | Mean wall_ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| browser_use | default | 40 | 22 | 18 | 2 | 1.641794 | 0.041045 | 11713.34 | 16200.31 |
| playwright_mcp | default | 40 | 22 | 18 | 0 | 0.057734 | 0.001443 | 5013.93 | 3255.65 |
| script_first | default | 40 | 22 | 18 | 0 | 0.211650 | 0.005291 | 3953.00 | 5647.03 |
| cascade | default | 40 | 22 | 18 | 2 | 1.112435 | 0.027811 | 8136.23 | 13819.57 |
| browser_use | ultrafast | 40 | 40 | 0 | 2 | 3.098815 | 0.077470 | 27658.92 | 32220.88 |

For interpretation, excluding the 18 budget skips in each default arm:

| Arm | Attempted | Mean USD/attempt | Median wall_ms | Mean wall_ms |
|---|---:|---:|---:|---:|
| browser_use | 22 | 0.074627 | 26540.26 | 29455.11 |
| playwright_mcp | 22 | 0.002624 | 5656.41 | 5919.37 |
| script_first | 22 | 0.009620 | 9638.07 | 10267.33 |
| cascade | 22 | 0.050565 | 25022.14 | 25126.49 |

Cascade `answered_by`: **20 browser_use, 2 script**, plus **18 budget-skipped**
rows without an answering stage. The two configurations are not paired over
all 40 attempted tasks, so these aggregates do not establish a mode speedup.

## Playwright MCP environment failure

The first attempted MCP row records:

```text
Task failed: TASK_FAILED: The browser could not start because the required Chrome installation is missing.
```

All 22 attempted MCP rows have an empty grading URL and a completion reason
reporting a missing/unavailable browser. `bench/harness.py:456` launches the
pinned MCP server without a browser/executable override. The environment has
Playwright Chromium (`~/.cache/ms-playwright/chromium-1255`), but no
`/opt/google` installation or `/usr/bin/google-chrome`. Chromium installation
does not satisfy MCP's default Chrome selection. These rows are infrastructure
failures, not evidence of MCP task-solving accuracy or representative speed.
No baseline configuration was changed and no paid rerun was attempted.

## Task-prompt parity (reported, not changed)

Standalone `bench.browser_use_arm.task_text()` and cascade
`bench.cascade.handoff_note()` both use `bench.tasks.task_message()` with the
same description and start URL. Offline comparison across all 40 extdev tasks
found that every cascade handoff begins with the identical standalone task
message, with `ANSWER_FORMAT` occurring exactly once in each. Cascade appends
the warm-handoff receipt (current URL, visited URLs, sanitized failure reason).
Thus the task/ANSWER_FORMAT is the same, but the complete prompt is not
byte-identical because of the receipt. This does not establish the cause of
the smoke's `answer too long` failures; prompts and grading were unchanged.

## Reproduction and checks

```bash
export PATH="$HOME/.nvm/versions/node/v24.22.2/bin:$PATH"
source .venv/bin/activate
export CU_OPENAI_SPEND_LEDGER="$HOME/.cu-optimisation/openai-spend-alex15.json"
export CU_OPENAI_PROJECT_BUDGET_USD=9.00
export CU_OPENAI_RUN_BUDGET_USD=3.00
unset CU_BU_MODE
python tools/extdev_control.py --mode default --execute
# Read ledger, then only proceed if it is <= $4.50:
export CU_BU_MODE=ultrafast
python tools/extdev_control.py --mode ultrafast --execute
```

The wrapper refuses duplicate invocation metadata and checks the ultrafast gate.

Focused offline regression command:

```text
.venv/bin/python -m pytest -q tests/test_browser_use_arm.py tests/test_openai_provider.py
41 passed in 0.20s
```

The prohibited catalog was not opened or run. No prompt/grader changes.
