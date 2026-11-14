# FORM comparison evidence — 14 November 2026

One completed strategy-off/on pair per split, 52 task rows. All use `script_first`, OpenAI `gpt-6-luna`, medium effort, grounded repair, cold execution and the shared slot wrapper. The runs were recovered rather than restarted.

## Result and decision

| Split | Pass off → on | False accepts off → on | Median calls off → on | Median seconds off → on | Mean seconds off → on | p90 seconds off → on | USD/task off → on |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev3 | 4/6 → 6/6 | 0/6 → 0/6 | 2 → 2 | 11.34 → 10.52 | 12.16 → 10.58 | 26.03 → 15.14 | .000843 → .000346 |
| held-out | 2/6 → 3/6 | 3/6 → 2/6 | 2 → 2.5 | 7.15 → 13.02 | 11.78 → 19.06 | 33.33 → 54.85 | .000759 → .000551 |
| heldout2 | 1/2 → 2/2 | 0/2 → 0/2 | 3.5 → 3.5 | 16.02 → 16.96 | 16.02 → 16.96 | 23.17 → 26.29 | .001304 → .001200 |
| dev4form: first contact = final | 2/12 → 9/12 | 2/12 → 1/12 | 3 → 3.5 | 13.57 → 17.20 | 13.33 → 23.21 | 21.83 → 42.78 | .001074 → .000836 |

Keep **opt-in / experimental**. Fresh-set completion improved, but the on arm misses every requested acceptance target: 90% pass, <5% false accepts per attempt, median <10s, mean <12s and median ≤2 model calls. Its 9/12 passes comprise eight direct specialist completions and one generic fallback recovery. Four fresh tasks fell back, including the one false accept. Older held-out data still contains two direct-specialist false accepts.

Only one repetition per task/variant was run, in split-level off/on order. Wall-time measures include every attempt, specialist failures and fallback; p90 is nearest rank. Timings are noisy on the shared machine. These are development/checkpoint results, with no confidence or generalisation claim. The old `held-out` and `heldout2` sets were permitted development material. No protected gate files were opened or run in this recovery.

## Reproduce and inspect

- [tables.md](tables.md): all eight aggregate rows, mean calls, and each task's wall time, tool steps, model calls and dollars.
- [summary.json](summary.json): unrounded aggregates, route counts, archived-file hashes and definitions.
- [provenance.json](provenance.json): original source paths/hashes, completion-log hashes and ledger reconciliation.
- [failure_summary.json](failure_summary.json): unchanged failed/fallback observations and actions. Their interpretations and remaining limits are in [FORM_STRATEGY.md](../../FORM_STRATEGY.md#measurement).
- The eight `*_off.jsonl` / `*_on.jsonl` files retain all task rows. Recovery checked parsed-row equality against the original `bench/runs` files and each completed probe summary.
- Rebuild and validate aggregates without network or task-catalog imports: `python docs/results/form_specialist_20261114/summarize.py`.

Runtime was frozen at `b42e486`; `git diff b42e486 9bd9402 -- bench` is empty. Dev4form's first agent pair is also the final checkpoint: no subsequent runtime changes, retuning or rerun. Total billed comparisons **$0.042914** equal dev-g's increment **$5.881834 → $5.924748**, within $1. The earlier two empty probe files produced zero task rows and zero billed spend.

## Ancestry and prior tests

`git merge-base --is-ancestor github/t3/tip3 HEAD` succeeded with baseline `bec55ab`, including runtime `56fbcab`. The test diff from that baseline adds only `test_dev4_form.py` and `test_strategy_form.py` (24 cases), with no modified/deleted baseline tests. The grader, generic runtime and marker-blindness tests match tip3.

The prior recorded result **853 passed, 1 skipped in 50.01s** used:

```text
python -m pytest -q --ignore-glob=tests/test_heldout3* --ignore-glob=tests/test_val3*
```

This deliberately narrower selection explains why it cannot be compared directly with tip3's reported 876-pass full suite. No baseline loss was found, so the broad suite was not rerun. Recovery's checks validate all 52 archived rows, off/on task identity and order, provider/model/effort, counts, source equality and exact spend reconciliation. Documentation and evidence are the only changes after `9bd9402`.
