# Experiment 4: pre-router simulation on saved extdev arms

**Scored against AI (Devin) hand labels from [PR #97](https://github.com/advcode118/alexs-computeruseoptimisation/pull/97), which no human has spot-checked; all results are indicative only.** Routed timings and costs are saved-row substitutions, not measurements of a newly executed router.

Question: how much script-stage time precedes an eventual handoff, and can a pre-run router avoid it without sacrificing the cascade's result quality?

**Result:** the observed cascade hands off **20/22 tasks**, spending **167.948 script-stage seconds on those handoffs**: 8.397 s per handoff, 7.634 s per task, **95.6% of all script-stage time**. This is exposure to overhead, not proof all that time is removable without losing useful browser state.
**Simulation:** bypassing only `value` tasks reduces mean wall time from **25.126 s to 22.549 s** with default direct browser_use, or **21.779 s** with ultrafast direct browser_use, retaining the cascade's **20 correct / 2 partial / 0 wrong** AI labels. This is exploratory in-sample evidence for testing a simple pre-router, not a validated speed lead.

## Task set, model, run count and provenance

- **Extdev replicate 1, the 22 paired attempted tasks**, model **`gpt-6.1-sol`, medium effort**. One saved run per arm/configuration on each paired task, not repeated independent measurements. No new live runs.
- Default source: `../extdev_control_20261117/raw/probe_20261117_012232.jsonl`: standalone script_first, default browser_use and observed cascade. The standalone script_first rows define the paired task set and supply only pre-run task descriptions, start URLs and task categories to real policies; their outcomes are not routing features.
- Ultrafast source: `../extdev_control_20261117/raw/probe_20261117_015118.jsonl`: browser_use ultrafast, restricted to those same 22 tasks, not its entire 40-task catalog. Budget skips and non-row report records are excluded.
- Truth: `../extdev_hand_labels_20261117/hand_labels.csv`, joined by **source file + arm + task ID**. Every routed row takes **label, wall time and cost from the same selected arm row**, never the better label from a different run. Cascade selection uses the final cascade label whether its answer came from script or fallback.
- **All 22 cascade rows have `stage_wall_ms`**, including grounding, script and browser_use, plus `answered_by`. Therefore no script_first + browser_use timing composition is needed or used. Full observed cascade `wall_ms` is retained rather than replacing it with a sum of stages. In `bench/cascade.py::run_cascade_task`, the script stage is timed separately (excluding its grade read); only a rejected precision check enters the fallback branch.
- The independent standalone script_first mean is **10.267 s**, p90 **15.496 s**, median **9.638 s**. The actual cascade script-stage mean is **7.982 s**, not the standalone 10 s: it is a separate grounded run. It totals 175.613 s, of which 167.948 s precede handoffs. We do not subtract standalone script timings from cascade rows.

## Policies declared before simulation

These are simple hand rules, not a learned classifier. They were defined before the first simulation and not adjusted after seeing the policy scores, but they are still **exploratory/in-sample**, motivated by this inspected development set rather than pre-registered externally. Category is the second component of `extdev_CATEGORY_…`. `choose_pre_run` receives only pre-run features; the two hand rules actually read category alone. No label, timing, success flag, script, self-check or final URL enters those decisions.

| Policy | Decision |
|---|---|
| `always_cascade` | Use the observed cascade row for every task |
| `always_browser_use` | Use the standalone browser_use row for every task |
| `bypass_value` | Send `value` tasks straight to browser_use; otherwise use observed cascade |
| `nav_only` | Use observed cascade only for `nav` tasks; all other categories go straight to browser_use |
| `oracle_quality_then_time` | Not deployable: choose between observed cascade and direct browser_use using the better AI label (`correct > partial > wrong`), then lower saved wall time on a label tie |

The oracle is an upper bound on result quality **within these two observed choices**, with the fastest observed route at that quality for each task. It is not the minimum possible latency if correctness is ignored. It does not know or create an unobserved successful script. It can choose a slower route than a lower-quality policy.

Each policy is evaluated with **default or ultrafast as its direct browser_use option**. Both groups reuse the **same observed default-fallback cascade** when they select cascade. There is no measured ultrafast-fallback cascade; the ultrafast group must not be interpreted as one. Direct runs start cold from the task's start URL; observed fallback runs continue from a warmed/partially navigated page. We use the measured direct-run times, **not** the unjustified shortcut `cascade_time - script_time`.

## Per-policy results

**All C/P/W scores below use unreviewed AI hand labels and are indicative only.** Times are seconds; p90 uses linear interpolation at `(n-1) × 0.9`. `$/task` is the mean saved row `usd`, not new replay spend or repriced provider billing. `Script s on handoffs` is the **total across 22 tasks** of the selected cascade rows' script stage when they ended in browser_use; direct routes contribute zero. It is not the time for all retained script stages.

| BU mode | Policy | C/P/W | Mean s | p90 s | Median s | $/task | Script s on handoffs (total) | Handoffs |
|---|---|---|---:|---:|---:|---:|---:|---:|
| default | always_cascade | 20/2/0 | 25.126 | 38.068 | 25.022 | 0.050565 | 167.948 | 20 |
| default | always_browser_use | 21/0/1 | 29.455 | 54.878 | 26.540 | 0.074627 | 0.000 | 0 |
| default | bypass_value | 20/2/0 | 22.549 | 32.988 | 23.657 | 0.047840 | 93.429 | 10 |
| default | nav_only | 21/0/1 | 27.020 | 53.280 | 26.316 | 0.069989 | 22.747 | 3 |
| default | oracle_quality_then_time | 22/0/0 | 23.573 | 29.842 | 24.561 | 0.056601 | 45.280 | 7 |
| ultrafast | always_cascade | 20/2/0 | 25.126 | 38.068 | 25.022 | 0.050565 | 167.948 | 20 |
| ultrafast | always_browser_use | 21/0/1 | 25.296 | 35.356 | 27.659 | 0.053288 | 0.000 | 0 |
| ultrafast | bypass_value | 20/2/0 | 21.779 | 32.988 | 23.657 | 0.048643 | 93.429 | 10 |
| ultrafast | nav_only | 21/0/1 | 22.774 | 31.835 | 23.467 | 0.049344 | 22.747 | 3 |
| ultrafast | oracle_quality_then_time | 22/0/0 | 20.721 | 31.170 | 19.619 | 0.044759 | 53.187 | 8 |

`bypass_value` sends ten tasks directly to browser_use; all ten happened to hand off in the observed cascade. It removes **74.519 s** of script-stage exposure from those rows, leaving 93.429 s on ten retained handoffs. The full mean-time reduction is **2.577 s/task** with default direct browser_use or **3.347 s/task** with ultrafast, not automatically 74.519/22: the direct and warm-fallback browser runs differ.

`nav_only` sends 17 tasks directly (all observed handoffs), keeping five cascade paths, three of which still hand off. Removing more script stages does **not** monotonically improve measured total time: default direct browser_use is slower on some tasks than the warmed cascade. The oracle similarly keeps some handoff paths because their observed warm cascade is faster than a direct run at the same label quality.

The only accuracy differences between observed cascade and the paired direct default/ultrafast rows are Booking Times Square and Amazon puppy food (cascade partial, direct correct) and Airbnb mansions (cascade correct, direct wrong). The oracle combines these observed successes into 22 correct; no hand rule here achieves that. Cascade's 20 correct / 2 partial and direct browser_use's 21 correct / 1 wrong represent different quality tradeoffs, not equal accuracy.

## Reproduce

From repository root with Python 3.11+ (simulation itself uses only the standard library):

```sh
python docs/results/extdev_router_20261117/simulate.py
source ~/.nvm/nvm.sh && source /home/ubuntu/repos/alexs-computeruseoptimisation/.venv/bin/activate && pytest -q bench/test_harness.py tests
```

Exact replay command run on this machine: `/home/ubuntu/repos/alexs-computeruseoptimisation/.venv/bin/python docs/results/extdev_router_20261117/simulate.py`. Optional `--output-dir EXISTING_DIRECTORY` writes a throwaway reproduction.

`tasks.csv` contains **220 task-policy records** (22 tasks × 5 policies × 2 direct-browser modes), including category/domain/description, selected arm row, final stage, AI label, time, cost and script-stage handoff exposure. `results.json` contains all aggregates plus standalone-script timing context. **One offline evaluation per policy per saved task; 0 model calls, 0 browser runs, $0 new provider/API spend.** Saved dollar estimates are not reconciled or repriced; no ledger writes, secrets or paid probes. This does not estimate Devin session usage cost.

## Decision and limits

There is enough avoidable-looking stage exposure to justify testing the lean `value` bypass **if a future live run is authorized**. This simulation cannot establish that a pre-router is required, that the saved speed advantage will reproduce, or that all script-stage time before handoff was wasted: scripts can help via navigation, grounding and browser state. Always skipping script does not dominate the observed cascade, and very aggressive category bypass can hurt time as well as quality.

One 22-task development replicate per arm/configuration; no repeated router trials, no human-checked truth, no fresh claim set, and different arm runs are not interchangeable randomized counterfactuals. Policies and their interpretation are in-sample. There is no learned-model inference overhead in these hand rules, but no live router overhead was measured either. The oracle uses unavailable future knowledge and is not a deployable result. Product, self-check and grader code are unchanged. No UI changed; visual verification is not applicable.

## Verification

Full Python aggregate check with the exact pytest command above:

```text
1178 passed, 1 skipped in 35.41s
```

The new tests reproduce CSV/JSON byte-for-byte in a throwaway directory; verify 22 tasks in every policy, the 20 observed handoffs and their stage-time total; exercise pre-run category rules, invalid-policy/ID errors and empty timing summaries; and ensure each simulated label/time/cost comes from its selected arm row. A throwaway consistency check matched all ten README policy summaries to `results.json`.
