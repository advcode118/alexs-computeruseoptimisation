# Observe-first evidence

Only dev3 data is included. Empty/failed-to-start probes are not measurements.

- `probe_20261113_220428.jsonl.gz`: recovered preliminary off cell.
- `probe_20261113_221313.jsonl.gz`: recovered preliminary on cell.
- `preliminary_sources.json`: uncompressed-byte SHA-256 digests.
- `preliminary.json`: recomputed metrics plus per-task timing, steps and cost.

To reproduce the historical report offline:

```sh
python -m bench.observe_first_report \
  --pair docs/results/observe_first/probe_20261113_220428.jsonl.gz docs/results/observe_first/probe_20261113_221313.jsonl.gz \
  --output docs/results/observe_first/preliminary.json
```

The report refuses incomplete, duplicated, skipped or wrong-model cells.
First-script independent grades use the existing shared grader offline, with
the runtime verdict forced to PASS solely to measure the script's result
independently. They never feed back into the run. Intermediate selector
evidence absent from the logs is unavailable, not a failed grade. Reported
lower/upper bounds include all such unknowns. A one-script stopped-and-graded
pass is a separate observed measure and does not claim to identify every
first-script result that could have passed.

For old logs without self-check payloads, a sole-script run ending on runtime
PASS can reuse its recorded final shared grade. Other old first-script grades
remain unavailable; runtime FAIL itself cannot establish a shared-grade fail.

The preliminary pair used the old runtime and is not pooled with the current
grounded-repair comparison. See `../../OBSERVE_FIRST.md` for the protocol.

## Completed tip3 comparison

- `tip3_pair{1,2,3}-{off,on}.jsonl.gz`: six lossless source archives, 40 tasks each.
- `tip3_sources.json`: exact measured revision, execution order, source SHA-256
  and byte counts, and all six completion/budget manifests.
- `tip3_20261114.json`: aggregate, paired and per-task results from the unchanged
  runtime at `43c8142`. The later bounded-decompression fix was not live-tested.

Reproduce offline (no model or browser calls):

```sh
python -m bench.observe_first_report \
  --pair docs/results/observe_first/tip3_pair1-off.jsonl.gz docs/results/observe_first/tip3_pair1-on.jsonl.gz \
  --pair docs/results/observe_first/tip3_pair2-off.jsonl.gz docs/results/observe_first/tip3_pair2-on.jsonl.gz \
  --pair docs/results/observe_first/tip3_pair3-off.jsonl.gz docs/results/observe_first/tip3_pair3-on.jsonl.gz \
  --output docs/results/observe_first/tip3_20261114.json
```

For the parent's protected-data boundary, prefix the module invocation with
`python C:/Users/epicd/AppData/Local/Temp/opencode/verifier_audit_guard.py`
instead of `python -m`. This process-only launcher suppresses eager imports of
protected task definitions and blocks their files and external connections.
It does not change dev3 definitions or any grade.
