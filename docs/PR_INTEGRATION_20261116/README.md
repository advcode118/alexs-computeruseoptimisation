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

## Work in progress

1. Map PR ancestry and unique changes.
2. Reconcile shared and experiment spend ledgers.
3. Review independent runtime and non-runtime candidates.
4. Run isolated checks and approved matched development comparisons.
5. Retarget and merge useful candidates, then verify the combined branch.
6. Record each PR's disposition and supporting evidence.
