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

## Final status (16 Nov 2026)

- **7 merged** (#46, #45, #67, #78, #81, #58, #82), **51 already contained**,
  **15 not merged**. Per-PR reasons: `final_dispositions.md` / `.json`.
- #82 (segments) merged as accepted experimental infrastructure: opt-in via
  `CU_SF_SEGMENTS=1`, default off. Strong offline coverage; partial DEV pilot
  inconclusive (matched 14 tasks: 13 vs baseline 12, FA 1→0, FR 0→1, ~1.23×
  settled cost per pass). Not promoted to default.
- #74 (observe-first) PARKED: DEV rep 1 was 15/24 vs baseline 18/24, 0 wins,
  3 losses. Single repetition; not a general regression claim. Not merged.
- No blanket claim that project accuracy improved versus tip4 `b5b74b3`.
- Pilot stopped incomplete: `pilot_20261116.md` (with parent corrections),
  sanitized per-task rows in `pilot/`.
- **Budget blocker:** one unresolved OpenAI call
  (`32f86e4fcf454936b4f519150d51e2cb`, run
  `pr-eval-3bc3847883fb4aab8a8549e6b9f8b599`) retains a $0.012660
  reservation; ledger `aborted`, closing total $14.648180. No paid run until it
  is resolved from provider evidence. Ledger not edited here.

## Checklist

- [x] Map all 73 PRs: 51 heads already contained in tip4.
- [x] Reconcile ledger forks; import missing prior spend once.
- [x] Opus/Astra independent candidate reviews and focused offline tests.
- [x] Merge six useful correctness, coverage and record PRs.
- [x] Opus-reviewed budget runner and one paid schema/accounting smoke.
- [~] Matched DEV pilot for #74/#82: stopped after rep 1 (segments 14/15 graded).
- [x] Merge #82 opt-in; park #74; final combined suite (see `merged.md`).
- [x] Publish final per-PR disposition.

`pr-integration-pilot-plan.md` was written before comparative results.
`pr-integration-budget-smoke.md` records the completed reconciliation and smoke;
the original read-only budget audit remains in `budget.md`.
