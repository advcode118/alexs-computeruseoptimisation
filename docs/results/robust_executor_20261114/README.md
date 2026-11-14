# Robust executor: recovery and bounded dev3 comparison

Worktree: `t3/robust-executor`. Runtime comparison base: `bec55ab`
(runtime `56fbcab`). Owner-authorised Luna medium only, dev-d ledger only.

## Preregistered comparison

One pair over all 40 dev3 tasks; alternate tip3/robust and robust/tip3 by task
index. Same current grounded repairs and verifier on both sides. No additional
look, cache, validation, or frozen-test run. The baseline modules are loaded from
Git into memory; no worktree or branch checkout is created. The runner prevents
imports of the frozen task modules. Raw rows, scripts, failures and costs stay
in this directory, including the old negative results.

Report first-script **graded** pass (successful final grade with one script),
final graded pass, runtime PASS rejected by the independent post-run grade
(wrong accept), executed script and model calls, all-attempt mean/median/p90,
and token-priced dollars. This is a development comparison, not a held-out win.
Do not infer faster execution from a favourable median alone.

The local strict/fuzzy experiment is a separate comparison, with a fixed
synthetic HTML page for each case. Four ambiguous cases and four positive
controls: fuzzy 4/8 correct, 4 wrong actions; strict 8/8 correct, 0 wrong actions.
An execution refusal counts as correct only in the intentionally ambiguous
cases, with the DOM independently checked for no mutation. It is not a task
pass. The 77 focused executor/helper/grounded-repair tests pass.

## Recovered evidence

The pre-interruption dev3 baseline finished at 22:18:39 on 13 November:
17/40 first-script passes, 26/40 final passes, 4 wrong accepts, 63 script calls,
70 model calls; all-attempt mean 7.846s, median 6.616s, p90 12.938s; $0.017202.
It is historical context, not the current-base comparator.

Offline parsing of its exact first scripts accepts 32/40 on tip3 and 39/40
on the recovered robust grammar. Parsing alone does not establish correct
execution. The remaining robust failure exceeds the existing action cap.

`recovery.json` records each older run, including the interrupted six-row run.
`offline.json` records the synthetic replay and parser failures. All recovered
JSONL is preserved. The old-set regression figures remain exploratory/noise.

## Spend and reproduction

The unchanged dev-d ledger was $5.711918 at resume. Its 279-row contiguous
suffix matches the recovered owned runs, beginning at $5.608860: $0.103058
already spent. The same original +$1 ceiling ($6.608860) is enforced with a
$0.05 reserve before each task; the ledger is never reset. No other agent's
ledger is used. The paired run is expected to be far below the remaining cap.

```powershell
python -m bench.executor_experiment --recover --offline
python -m pytest -q tests/test_script_resolve.py tests/test_script_helpers.py tests/test_script_first.py tests/test_grounded_repair.py
& 'C:/Program Files/Git/bin/sh.exe' C:/Users/epicd/.cu-optimisation/probe_slot.sh python -m bench.executor_experiment --live
```

The live command refuses to overwrite an existing paired result. The key is
read from the owner-specified file and is not logged. Final measurement and
recommendation are recorded below; the registered pair is complete.

## Completed pair and decision

Measured robust head: `e9c8673d10a87a03d88303685a964c9ec2595a9b`; baseline
modules: `bec55ab`. Parent recovery verified all 80 saved rows, 40 unique
matching dev3 task IDs per condition, model/effort, measured revision, and exact
recomputation of `paired_summary.json`. The raw `paired_dev3.jsonl` is preserved.

| Measure | tip3 | Robust |
|---|---:|---:|
| Final graded passes | 28/40 | 33/40 |
| Wrong accepts | 4/40 | 6/40 |
| One-script stopped and graded passes | 12/40 | 10/40 |
| Script calls / model calls | 80 / 81 | 79 / 80 |
| All-attempt median / mean / p90 | 7.02 / 9.01 / 15.76 s | 5.90 / 6.97 / 13.32 s |
| Recorded USD | $0.024972 | $0.023257 |

P90 is the inclusive linearly interpolated percentile. Pair cost was
**$0.048229**. This is one development pair with shared-machine timing, not
independent repeated evidence. One-script stopped passes do not recover all
counterfactual first-script grades.

**Hold the bundle out of integration.** Higher completion and lower observed
time accompany more wrong accepts and fewer one-script successes. The local
strict-ambiguity controls support that mechanism, not the whole live bundle.
Review or isolate that mechanism before another integration proposal. Recovery
made no runtime edit, benchmark rerun, API call or ledger change.
