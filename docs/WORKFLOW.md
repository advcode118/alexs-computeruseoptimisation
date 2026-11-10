# Workflow

T3 and Cursor share this GitHub repo. The rules are in `AGENTS.md`. This page is how a branch moves between them.

## Start a T3 thread

1. Read `AGENTS.md`, `docs/HISTORY.md`, and `NOTES.md` (GitHub PR #2, branch `t3/onboarding-notes`).
2. Check open GitHub PRs. If a draft already owns the harness files you need, stack on that PR or pick other work.
3. Branch from `t3/base` as `t3/<short-name>`. One task, one branch, one worktree.
4. Open a draft PR against `t3/base` before editing. Name the files or subsystems the PR owns.
5. Push to GitHub often. The remote is `github`. Never use `main`, never force-push, never delete a branch.
6. Offline check: `python -m pytest -q bench/test_harness.py tests`. No live probe without Tom's go.

Local setup is `scripts/setup.sh` (Windows: `scripts/setup.ps1`). A cloud agent runs the same install from `.cursor/environment.json`.

## Hand work to Cursor

1. Leave the `t3/*` draft PR open, with the owned files named and what is left to do written in the body.
2. Say which files Cursor must not edit: the held-out task set, the harness judge, and anything another open draft owns.
3. Cursor stacks a `cursor/*` branch on that PR, or checks the branch out in its own worktree. It does not start from `main`.

## Pick up each other's branches

1. Run `scripts/sync.sh` (Windows: `scripts/sync.ps1`). It runs `git fetch github --prune`, fast-forwards clean branches that are behind, and pushes clean branches that are ahead, setting upstream to `github/<same name>`. Dirty and diverged branches are printed and left alone. `--dry-run` fetches and prints the same lines without pulling or pushing.
2. Check the other side's branch out in its own worktree. T3 reads `cursor/*`. Cursor reads `t3/*`.
3. To continue their work, stack a new draft PR on their open draft. Do not edit the same files in parallel.
4. `t3/base` is where the work integrates. Do not merge to `main`.
