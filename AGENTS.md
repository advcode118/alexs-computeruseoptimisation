<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Computer-use project

This file is the only copy of the project rules. `.cursor/rules/agents.mdc` and `CLAUDE.md` only point here.

### Read first

Before changing anything, read:

- `docs/HISTORY.md` — Origin PRs #6–#20, the probe numbers, and why
- `NOTES.md` — on `t3/onboarding-notes` (GitHub PR #2): script_first flow, the #20 audit, and the step 2 plan
- `docs/WORKFLOW.md` — how to start a T3 thread, hand work to Cursor, and pick up each other's branches

### Models and spend

- Implementation: Cursor provider, `grok-4.7`, reasoning effort high, fast mode off (the T3 project default). Never pass `grok-4.7-high`.
- Design and review only: Claude Opus 5.5 or Fable 5.2 at medium effort. Off until Tom says his Claude limit has reset.
- Claude API calls use `claude-sonnet-5-5` only. Never Opus, Fable, or `claude-sonnet-4-6` through the API.
- The spend cap is $50. Every probe shares one ledger, the file `CU_SPEND_LEDGER` points at. Do not reset it, reprice it, or start a second copy. About $16.64 is already spent (`running_total_usd` after the PR #18 probe; the figures are in `docs/HISTORY.md`).
- No live probe and no Claude API call without Tom's go. Offline tests are always fine.

### Branches and claims

- `t3/*` is T3 work. `cursor/*` is Cursor work. `t3/base` is the integration base.
- Never use `main` as the base. Never merge to `main`. Never force-push. Never delete a branch.
- GitHub is the home for the code. Cursor Origin is read-only history.
- One task per branch and worktree. Draft PRs on GitHub. Push often.
- Before starting, check open GitHub PRs and claim the area by opening a draft PR early. Name the files or subsystems the PR owns.
- If another open draft PR owns the same harness files, stack on that PR or pick other work. Two agents never edit the same files in parallel.

### Roadmap

The roadmap lives in `docs/HISTORY.md` under "After the move".
