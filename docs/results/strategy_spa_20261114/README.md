# SPA specialist evidence

See [the report](../../STRATEGY_SPA.md) for the protocol, counts, limitations,
and reproduction commands. The JSONL files are the unmodified rows returned by
`bench.probe.execute_probe`, not selected successes.

- `*_first.jsonl`: first paired checkpoint on runtime `14d0533`, in the order
  dev3 off/on, then dev4spa off/on. The task-authoring/manual mechanics exposure
  preceding this first model checkpoint is disclosed in the report.
- `*_final.jsonl`: final dev4spa off/on checkpoint on runtime `f023565`, after
  adding the general adjacent-label transparent checkbox pattern.
- `router.json`: model-free HTTP router audit, including the allowed older
  splits as negatives. Classification labels are used only for audit, never
  passed to the strategy.
- `manifest.json`: compact recovery record with hashes of the evidence files,
  paired aggregates, completed-job provenance, and test/ancestry reconciliation.

All model runs use `gpt-6-luna`, medium effort, `script_first` only, the dev-h
ledger, and the single managed probe slot. `strategy_detail` records a
specialist acceptance/handback independently of the eventual shared grade.
