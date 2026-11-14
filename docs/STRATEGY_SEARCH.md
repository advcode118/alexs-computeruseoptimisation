# Search specialist experiment

Base: `github/t3/tip3` runtime `56fbcab`, documentation `bec55ab`.
The pre-existing `t3/strategy-search` worktree was clean and had no specialist
implementation or local live-run files; fast-forwarded without rewriting history.

## Budget and protocol

- Existing ledger: `~/.cu-optimisation/openai-spend-dev-f.json`.
- Original/resume balance: **$5.881834**, 2,750 inherited entries. No prior search
  specialist runs were present. Hard cumulative experiment ceiling: **$6.881834**.
- All live verification/probes and broad offline suites use `probe_slot.sh`.
- API: `gpt-6-luna`, medium, script_first only. No frozen tasks/results inspected.
- Twelve dev4search tasks authored before designing the mechanism, on six unused
  sites (two each). Raw author-verifier attempts are preserved, including failures.
- Current generic grounded-repair baseline is the control, not the obsolete 22%.

## Results

Focused offline check: `python -m pytest -q tests/test_strategy_search.py
tests/test_dev4_search.py tests/test_grounded_repair.py tests/test_script_cache.py`
reported **48 passed in 8.11s**. This includes native forms, form filters, hidden
JS search, bad-choice fallback with retained usage, actual-result landing,
opt-in isolation, and the no-answer-key boundary.

Author attempt 1: 2/12 passed. Preserved in `results/search_20261114/author_attempt1.jsonl`.
Reproducer errors included duplicate form selects, relative link selectors,
hidden inputs, and Pydantic's documentation migration. These are author-route
failures, not agent first-contact measurements. No API calls so far.

The second author verification is queued through the shared managed slots.
Pending paired measurements; no performance claim yet.
