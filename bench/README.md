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
├── budget.py        # Sonnet-4-6 price and the $40 project stop
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
- The model is `claude-sonnet-4-6`. `claude-sonnet-4-20250514` is retired. Opus is refused.
- The harness uses `--snapshot-mode full` to get complete ARIA snapshots
- Headless mode is on by default; set `headless=False` for debugging
- The LLM judge uses Claude Haiku to minimize cost. It refuses Opus.
- Model context keeps the opening task and the last 6 turns. Each tool result sent to the model is capped at 8000 characters. Saved snapshots keep the full page.
- Navigate and find responses are counted as snapshot tokens, along with action responses.
- After every task the harness prices that task's input and output tokens at the current sonnet-4-6 list price ($3 / MTok input, $15 / MTok output), adds it to `bench/results/spend.json`, and stops on its own if the project total would pass $40.
- The M0 measurement is already in that file: 3.2M input tokens and 3k output tokens, $9.645, about $10. 4/5 succeeded, 36 steps, 94.8s, model time 87%, tools 13%, stopped after 5 of 12 tasks. That entry is the recorded usage, not a new run.
- The 40% hit / 50% match figure is the 5 hand-made snapshots in `bench/snapshots/` only. Runs save real page snapshots under `bench/runs/<run_id>/snapshots/` so the no-model hit rate can be measured on real pages later. This tree does not add a new hit rate.
