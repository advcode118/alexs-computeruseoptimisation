# Benchmark Harness

This benchmark harness measures where time and tokens go when running browser tasks with a Claude model driving `@playwright/mcp`.

## Purpose

Milestone 0 of mcp-turbo: measure the baseline before building optimizations. The harness answers:
- How much time is spent in the model vs browser tools vs overhead?
- How many tokens do snapshots consume?
- How often would no-model shortcuts fire on real tasks?

## Installation

```bash
# Install playwright-mcp globally (pinned version)
npm install -g @playwright/mcp@0.0.84

# Install Python dependencies
pip install -e ".[dev]"
```

## Running the Benchmark

### Full benchmark (requires ANTHROPIC_API_KEY)

```bash
export ANTHROPIC_API_KEY=your-key-here

# Run all tasks
python -m bench.harness

# Run with a specific model
python -m bench.run
```

### Offline mode (no API key needed)

```bash
# Run shortcut replay on saved snapshots
python -m bench.replay_shortcuts

# Run unit tests (no network, no API)
pytest tests/test_bench.py bench/test_harness.py -v

# Generate summary from a run file
python -m bench.summarize bench/runs/latest.jsonl
```

## Task Set

The benchmark includes:

### Fixture tasks (2)
Local HTML pages from `loop/fixture/`:
- `fixture_packing_add`: Add an item to a packing list
- `fixture_packing_multi`: Add multiple items

### WebVoyager tasks (~10)
Adapted from the [WebVoyager dataset](https://github.com/MinorJerry/WebVoyager) on stable public sites:
- Wikipedia search and navigation
- arXiv paper search
- GitHub repository exploration
- Python docs navigation
- MDN Web Docs search
- Hacker News browsing
- BBC Weather lookup
- npm package search
- Stack Overflow search

## Success Evaluation

Success is judged by:
1. **Simple checks** (preferred): URL contains, text present, title matches
2. **LLM judge**: For tasks with open-ended answers, uses Claude Haiku to compare the agent's result to expected criteria

## Metrics Collected

Per task:
- Wall time split: model time vs tool time vs other
- Number of steps (tool calls)
- Input/output tokens
- Snapshot tokens per step
- Success/failure

## Output Files

Results are saved to `bench/runs/<timestamp>.jsonl` as newline-delimited JSON.

### Summary Script

```bash
python -m bench.summarize bench/runs/20241104_120000.jsonl
```

Outputs a markdown table like:

## Results Template

| Task | Success | Steps | Wall Time | Model % | Tool % | Other % | Input Tok | Output Tok | Snapshot Tok |
|------|---------|-------|-----------|---------|--------|---------|-----------|------------|--------------|
| fixture_packing_add | ✓ | 3 | 5.2s | 65% | 30% | 5% | 2,500 | 150 | 1,200 |
| wv_wikipedia_search | ✓ | 4 | 8.1s | 70% | 25% | 5% | 4,000 | 200 | 2,000 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### Summary
- **Tasks**: 12
- **Success Rate**: 83% (10/12)
- **Total Steps**: 45
- **Total Wall Time**: 120.5s
- **Time in Model**: 70% (84.4s)
- **Time in Tools**: 25% (30.1s)
- **Other Time**: 5% (6.0s)
- **Total Input Tokens**: 35,000
- **Total Snapshot Tokens**: 18,000

## Shortcut Replay

The `replay_shortcuts.py` script tests the no-model shortcut logic offline:

```bash
python -m bench.replay_shortcuts bench/snapshots/
```

This:
1. Loads saved ARIA snapshots from benchmark runs
2. Converts them to the `Observation` type used by `loop/planner.py`
3. Runs them through `html_shortcut` and `route_decision`
4. Reports hit rate and whether the shortcut action matched what the model did

### Shortcut Replay Report Example

| Task | Step | Shortcut Fired | Tier | Match |
|------|------|----------------|------|-------|
| wv_wikipedia_search | 1 | ✓ | direct | ✓ |
| wv_wikipedia_search | 2 | ✓ | direct | ✓ |
| fixture_packing_add | 1 | ✗ | fast | - |

## Architecture

```
bench/
├── __init__.py
├── harness.py       # Main benchmark runner
├── budget.py        # claude-sonnet-5-5 id, recorded rate, and the $40 project stop
├── results/
│   └── spend.json   # Running project total, including the M0 prior
├── tasks.py         # Task definitions (fixture + WebVoyager)
├── judge.py         # Success evaluation (checks + LLM judge)
├── summarize.py     # Markdown report generator
├── replay_shortcuts.py  # Offline shortcut testing
├── snapshots/       # Saved ARIA snapshots for offline replay
│   ├── wikipedia_main.json
│   ├── wikipedia_search_results.json
│   └── ...
├── runs/            # Benchmark run results (JSONL)
└── README.md
```

## Notes

- `@playwright/mcp` 0.0.84 is pinned because the tool schema changes between releases. The client speaks newline-delimited JSON and does not wait on notifications.
- The outer model id is `claude-sonnet-5-5` (Claude Sonnet 5.5, no date suffix). `claude-sonnet-4-6` and `claude-sonnet-4-20250514` are refused. Opus is refused. The Messages call sends `anthropic-version: 2026-10-21`.
- The harness uses `--snapshot-mode full` to get complete ARIA snapshots
- Headless mode is on by default; set `headless=False` for debugging
- The LLM judge uses Claude Haiku to minimize cost. It refuses Opus.
- Model context keeps the opening task and the last 6 turns. Each tool result sent to the model is capped at 8000 characters. Saved snapshots keep the full page.
- Navigate and find responses are counted as snapshot tokens, along with action responses.
- After every task the harness prices that task's input and output tokens at the recorded ledger rate ($3 / MTok input, $15 / MTok output), adds it to `bench/results/spend.json`, and stops on its own if the project total would pass $40. Sonnet 5.5 list price is $2 / $10. That price is not applied here, so `running_total_usd` does not move. The operator envelope is $50. The abort stays $40.
- The M0 measurement is already in that file: 3.2M input tokens and 3k output tokens, $9.645, about $10. 4/5 succeeded, 36 steps, 94.8s, model time 87%, tools 13%, stopped after 5 of 12 tasks. That entry is the recorded usage, not a new run. Later box probes are recorded on top of it. `running_total_usd` is $12.912192. Do not reset that total to $9.645 or $11.054514.
- The 40% hit / 50% match figure is the 5 hand-made snapshots in `bench/snapshots/` only. Runs save real page snapshots under `bench/runs/<run_id>/snapshots/` so the no-model hit rate can be measured on real pages later. This tree does not add a new hit rate.
- `model_ignores_tools` counts a full-page `browser_snapshot` (or Stagehand `snapshot` / `observe`) that the outer model issues after an action already returned a compact diff. A snapshot whose own text also contains `full_snapshot_chars` and `diff_chars` still counts. A snapshot with a target or a depth does not count. The same counter lives on the proxy child and on the outer harness.
- Arms: `playwright_mcp` (plain MCP, full snapshots), `diff_fast_act` and `macro_replay` (the proxy tools: settle, compact diff, `fast_act` script, `do_task_segment`), `stagehand` (local Playwright, tools `snapshot` / `run` / `screenshot`), and `script_first` (one whole-task Playwright script, run through the Playwright Python API or MCP `browser_evaluate`, with no per-click settle or snapshot). `browser_run_code_unsafe` is not a tool. The default probe is still the first four. Select the comparison with `--arms playwright_mcp,script_first,stagehand`. That path's Claude stop is $2. The competitive path drives the selected arms with the outer model `claude-sonnet-5-5`. The proxy tools themselves do not call Claude. Pass `--arm` on the full runner for the original four. Browserbase is not opened. Each Playwright MCP process uses `--isolated` only. `@playwright/mcp@0.0.84` rejects `--isolated` together with `--user-data-dir`. The Stagehand and script_first arms use their own user-data-dir, and `context.browser` is a property. Sequential arms do not share the workspace Chrome profile.
- `browser_use` is a baseline beside `playwright_mcp` and `stagehand`. It is browser-use 1.0 (`browser-use==1.0.0`): the model writes Python in one persistent REPL that drives local Chrome over CDP (`Browser('chromium')`, `ChatAnthropic('claude-sonnet-5-5')`). Select it with `--arms playwright_mcp,stagehand,browser_use`. The default probe stays the original four. `@playwright/mcp` stays at 0.0.84.
- The 3-task probe is prepared, not run, from a checkout without `ANTHROPIC_API_KEY`. Box commands, from the repo root:

  ```bash
  python -m bench.probe
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --warm-replay
  python -m bench.probe --execute --no-model-only
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms playwright_mcp,script_first,stagehand
  ```

  The first prints the plan. The second is the competitive 3 tasks times `playwright_mcp`, `diff_fast_act`, `macro_replay`, and `stagehand`, all on the outer Claude loop. Hard Claude stop is $5. The project total still stops at $40. The fifth command is the script_first comparison and stops Claude at $2. Do not pass `--execute` from a checkout that is not supposed to spend. A first snapshot over 40,000 characters is skipped only when the returned body is longer than that. `full_snapshot_chars` inside a compact diff does not skip the task. The third command is the same cold 3x4, then the same 3 tasks again on `macro_replay` and `diff_fast_act`. It records replay hit rate and wall for that warm pass and keeps the replay cache between the two passes. The fourth command is optional. It runs the two proxy arms through `decide()` with no outer model. That path cannot close the Stagehand gap. It is not the competitive measurement. Do not pass `--execute` where the key is unset if you expected the Claude arms to move. This tree does not call Claude.

- OpenAI is a computer-use model under test, selected with `--provider openai`. It is not the coding model. The only ids are `gpt-6.1-sol` and `gpt-6-luna`. One run uses that same model on every arm and the same checks as Claude. The Claude path, including `claude-sonnet-5-5`, is unchanged. Spend goes to `~/.cu-optimisation/openai-spend.json` (`CU_OPENAI_SPEND_LEDGER`), never the Claude `spend.json`. Caps are $5 per run and $20 on that ledger. A sweep of both models at every accepted effort uses one tuned task and stops at $15. A run's dollar cost is the priced token counts and is not known before the API returns them. At the published standard short-context rates, $5 buys 2,500,000 uncached input tokens or 500,000 output tokens of `gpt-6.1-sol`, and 50,000,000 uncached input tokens or 10,000,000 output tokens of `gpt-6-luna`.

  ```bash
  python -m bench.probe --provider openai --model gpt-6.1-sol --effort medium --arms script_first,playwright_mcp,stagehand,browser_use
  OPENAI_API_KEY="$OPENAI_API_KEY" python -m bench.probe --execute --provider openai --model gpt-6.1-sol --effort medium --arms script_first,playwright_mcp,stagehand,browser_use
  OPENAI_API_KEY="$OPENAI_API_KEY" python -m bench.probe --execute --provider openai --model gpt-6-luna --effort medium --arms script_first,playwright_mcp,stagehand,browser_use
  python -m bench.probe --provider openai --sweep-effort --arms script_first,playwright_mcp,stagehand,browser_use
  OPENAI_API_KEY="$OPENAI_API_KEY" python -m bench.probe --execute --provider openai --sweep-effort --arms script_first,playwright_mcp,stagehand,browser_use
  ```

  `--effort` accepts `low`, `medium`, and `high`. `xhigh` is accepted because both model pages list it. `minimal` is rejected. Any other effort is rejected. The sweep command is the one that keeps the full sweep inside $15. Do not pass `--execute` from this checkout. This tree does not call OpenAI.
