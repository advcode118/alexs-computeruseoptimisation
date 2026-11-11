<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Computer-use project: read first

Every agent working here reads `docs/HISTORY.md` (what Origin PRs #6–#20 did, the probe numbers, and why) and `NOTES.md` before changing anything. The consolidated tip is `t3/tip` (GitHub PR #47). Stack new work on it.

- From 11 Nov 2026 the coding agents are Claude Code: Opus 5.5 and Sonnet 5.5 do the work, and Fable 5.2 advises. Grok is no longer used.
- Claude API probes use `claude-sonnet-5-5` only, never Opus or Fable through the API. $50 total cap; the last recorded total is $26.022488 (see `docs/HISTORY.md`). OpenAI probes use `gpt-6-luna` or `gpt-6.1-sol` at medium effort only, with the $5 per run and $20 project caps on `~/.cu-optimisation/openai-spend.json`. No live probe without Tom's go. Never merge `main`, never force-push, never delete branches.
- script_first's live run must never read task markers. Markers are for the post-run grade only, and that grade is the same for every arm (`tests/test_script_cache.py::test_the_live_run_never_reads_the_answer_key`).
- One task per branch and worktree, draft PRs on GitHub, push often. GitHub is the home for the code. Cursor Origin is read-only history.
