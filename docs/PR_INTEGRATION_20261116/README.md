# Open PR integration, 16 November 2026

User request: test and merge remaining useful PRs, with independent work in
parallel. Approved destination: a new non-main integration branch. Paid matched
accuracy probes are approved only within the existing project/per-run caps after
reconciling the ledgers.

- Integration branch: `t3/pr-integration-20261116`.
- Starting baseline: `t3/tip4`, `b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5`.
- Initial inventory: 73 open GitHub PRs.
- No merge to `main`, force push, branch deletion or unapproved budget increase.
- Final benchmark grading remains independent of runtime decisions.
- Protected heldout/validation task-level evidence is not tuning data.
- Parallelize read-only audits and isolated tests. Run timing comparisons after
  heavy test jobs finish, using matched starting states and model settings.
- Treat already-contained, superseded, useful, harmful and unmeasured work as
  different outcomes. Passing unit tests alone does not prove an accuracy gain.

## Merged so far

See `merged.md` (#46, #45, #67, #78, #81, #58).

## Work in progress

- [x] Map all 73 PRs: 51 heads already contained in tip4.
- [x] Reconcile ledger forks; import missing prior spend once.
- [x] Opus/Astra independent candidate reviews and focused offline tests.
- [x] Merge six useful correctness, coverage and record PRs.
- [x] Opus-reviewed budget runner and one paid schema/accounting smoke.
- [ ] Complete the predeclared matched development pilot for #74/#82.
- [ ] Decide the remaining experimental merges and run the final combined suite.
- [ ] Publish final per-PR disposition and measured outcomes.

`pr-integration-pilot-plan.md` was written before comparative results.
`pr-integration-budget-smoke.md` records the completed reconciliation and smoke;
the original read-only budget audit remains in `budget.md`.
