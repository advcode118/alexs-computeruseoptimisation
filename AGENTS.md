<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Computer-use project: read first

Every agent working here reads `docs/HISTORY.md`, `docs/TEST_RESULTS.md` (the current scoreboard) and `NOTES.md` before changing anything. The current tip is the slim cascade-core branch `devin/1794873658-slim-cascade-core`, stacked on the frozen-grader branch `devin/1794871306-frozen-grader` (PR #84) → `t3/pr-integration-20261116` (PR #83). Stack new work on it. `t3/tip` (PR #47) and `t3/tip4` (PR #80) are old and fully contained; do not stack on them. `docs/PR_DISPOSITION.md` lists every open PR #45–#83 and the sequence that lands one branch on `main`.

- **Product direction:** a cascade. script_first (one script, at most one grounded repair, a precision-first self-check) hands off to browser_use when the self-check is not a confident PASS. See `docs/CASCADE.md` for the selectable arm, timing and offline precision. Baselines: browser_use, playwright_mcp, stagehand. Specialists, segments, observe-first and the proxy arms were deleted; find them in git history, not in the tree.
- **Model:** `gpt-6.1-sol` at medium effort is the default for every arm. `gpt-6-luna` is allowed only as an explicit comparison or as the fallback stage.
- **Spend:** Alex approved a fresh **$15** OpenAI budget, tracked on a new ledger `~/.cu-optimisation/openai-spend-20261117.json` ($15 project cap, $5 per-run cap, enforced in `bench/openai_spend.py`). The old ledgers (`openai-spend*.json`, $20 cap, conservatively $14.58 spent per `docs/PR_INTEGRATION_20261116/budget.md`) are closed: do not write to them and do not count them against the new budget. Resolve the open reservation (`32f86e…`, $0.012660) from the provider dashboard before the first paid run. No live probe without Alex's explicit go for that run. Claude API probes: `claude-sonnet-5-5` only, $50 total cap, last recorded total $26.022488.
- **Grading:** the post-run grade is `bench/grade.py`, frozen behind a sha256 pin test. Do not edit it without a new pin and a full offline re-grade (`python tools/regrade.py`). script_first's live run must never read task markers (`tests/test_script_cache.py::test_the_live_run_never_reads_the_answer_key`). Report mean and p90 wall time, not only the median.
- **Claim sets:** heldout3 is retired as a claim set (inspected during development). Any accuracy claim needs a fresh pre-registered external set.
- Never merge into or push to `main`, never force-push, never delete branches, never close or comment on PRs without the user's go. One task per branch and worktree, draft PRs on GitHub, push often.
- Offline tests: Python 3.11+, `pip install -e '.[dev]'`, `playwright install chromium`, `node` on PATH; `pytest -q bench/test_harness.py tests`.
