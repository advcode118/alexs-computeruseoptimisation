<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Computer-use project: read first

Every agent working here reads `docs/HISTORY.md` (what Origin PRs #6–#20 did, the probe numbers, and why) and `NOTES.md` (on `t3/onboarding-notes`, GitHub PR #2) before changing anything.

- Implementation: Cursor provider, `grok-4.7`, reasoning effort high, fast mode off (the T3 project default; never pass `grok-4.7-high`).
- Design and review only: Claude Opus 5.5 or Fable 5.2 at medium effort. Currently OFF until Tom says his Claude limit has reset.
- Claude API probes use `claude-sonnet-5-5` only, never Opus or Fable through the API. $50 total cap (about $16.64 spent). No live probe without Tom's go. Never merge `main`, never force-push, never delete branches.
- One task per branch and worktree, draft PRs on GitHub, push often. GitHub is the home for the code. Cursor Origin is read-only history.
