# Cascade benchmark core

The bench supports a script_first → browser_use cascade and comparable baselines.
The default arms are `script_first`, `browser_use`, and `playwright_mcp`, in that
order. `stagehand` remains selectable. The harness measures individual arms;
it does not yet implement cascade routing.

## Environment and offline checks

```bash
export PATH="$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" | sort -V | tail -1)/bin:$PATH"
uv venv --python 3.12
uv pip install -e '.[dev]'
source .venv/bin/activate
playwright install chromium
pytest -q bench/test_harness.py tests
python tools/regrade.py --out /tmp/regrade_check
```

Browser-use live runs additionally need `uv pip install -e '.[browser_use]'`.
Playwright MCP uses pinned `@playwright/mcp@0.0.84` through Node/npx.
No API key or paid request is needed for offline tests or regrading.

## Execution contract

- `script_first` writes a whole-task Playwright script and runs it locally without
  per-click snapshots or settle loops. It accepts locator actions, the cu name
  helpers, and page-context evaluate calls.
- The script_first self-check (`runtime_verdict`) checks execution and live-page
  evidence, without task answer markers. PASS finishes immediately; UNKNOWN
  does not pass or repair. FAIL permits **at most one grounded repair**, within
  the 30-second repair wall budget, showing the failed step and the current page.
  An unavailable snapshot falls back to a reason/URL repair request.
- `browser_use` is browser-use 1.0.6 using one persistent Python REPL against
  local Chrome over CDP. Set `CU_BU_MODE=ultrafast` to pass the library's
  ultrafast mode explicitly; unset it for the library default. This flag is
  independent of model and reasoning effort.
- `playwright_mcp` is the iterative MCP baseline with full snapshots.
- `stagehand` is local Playwright exposing snapshot/run/screenshot, with compact
  action diffs. Browserbase is not used.
- Every task/arm gets an isolated browser profile. The MCP process uses
  `--isolated` only: version 0.0.84 rejects combining it with `--user-data-dir`.

Specialist strategies, observe-first/page summaries, and segmented execution
are not part of this core. Historical segment experiment records remain in
`docs/GROUNDED_SEGMENTS*.md` and `docs/PR_INTEGRATION_20261116/`.

## Plans and opt-in runs

Without `--execute`, the probe prints a plan and does not construct a provider
client or launch a browser:

```bash
python -m bench.probe
python -m bench.probe --provider openai
python -m bench.probe --provider openai --arms script_first,browser_use,playwright_mcp,stagehand
```

OpenAI defaults to **gpt-6.1-sol**, **medium** effort. `gpt-6-luna` is available
with `--model`. Both accept low, medium, high, xhigh, and max in this bench;
Luna also accepts none.
Claude remains `claude-sonnet-5-5`; Opus and retired models are refused.

Only an explicitly authorized live run should add `--execute` and supply the
provider key. `bench.run` also accepts `--provider`, `--model`, `--effort`,
and `--arm`. `--warm-replay` measures only the script_first cache in a separate
warm pass. Cold runs stay cold.

## Spend accounting

The new default OpenAI ledger is
`~/.cu-optimisation/openai-spend-20261117.json`, with a **$15 project cap** and
**$5 per-run cap**. `CU_OPENAI_SPEND_LEDGER` overrides its path.
`CU_OPENAI_PROJECT_BUDGET_USD` overrides the project cap, including when reading
an existing ledger; it does not reset accumulated spend. Without an override,
an existing ledger retains its stored project cap. `CU_OPENAI_RUN_BUDGET_USD`
overrides the per-run (per-cell for sweeps) cap. Both accept only finite positive
dollar amounts; blank values use the defaults. These are stop thresholds checked
between tasks, not hard provider-side limits on an in-flight task. For example:

```bash
export CU_OPENAI_SPEND_LEDGER="$HOME/.cu-optimisation/openai-spend-alex15.json"
export CU_OPENAI_PROJECT_BUDGET_USD=9.00
export CU_OPENAI_RUN_BUDGET_USD=5.00
```

The prior
`openai-spend.json` remains readable by explicit path and is never migrated,
reset, or rewritten by selecting the new default. Existing ledger entries and
unpriced-call reservations remain counted. A sweep covers both models and
accepted efforts, stops at $15, and retains the $5 per-cell cap.

The Claude ledger is separate (`CU_SPEND_LEDGER`), with its existing prior
spend, project abort, and lifetime caps unchanged. Costs come from returned
token usage, not task pass counts. `tools/pr_eval.py` retains exclusive-writer
locking and durable reservations and targets the new canonical ledger; its
evaluation origin is zero for the new project, not the old reconciled total.
It requires an existing ledger and never silently imports or clears old spend.

## Tasks, grading, and saved evidence

All `bench/tasks*.py` and `bench/verify_*.py` catalogs are retained, including
local HTML fixtures under `bench/fixture/`. Use `--split` to select the tuned,
development, validation, or held-out sets. `--only-kind` is an explicit
reporting/selection filter; task markers are not sent to the agent.

`bench/grade.py` is the frozen post-run grader. Its SHA-256 pin test must not
change. `tools/regrade.py` reads saved evidence and task markers without model
calls, browsers, or network. All `docs/results/**` evidence is retained.
Historical arm names in the regrader are necessary to interpret those rows,
not selectable runtime arms.

`proxy/` retains the script parser, page settling and model-ignore counting
used by the kept arms; it no longer exposes a proxy arm, server or MCP child.
