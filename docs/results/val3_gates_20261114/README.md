# val3 development gates, 14 November 2026

These are **validation/development results**, not a final heldout3 result. The
40-task val3 set has now been used for successive aggregate gates and its
by-kind results have informed development priorities. No per-task answers,
scripts, page contents or failure reasons were opened for this report.

Each comparison has three alternating runs per condition using script_first,
gpt-6-luna, medium effort. There are 120 observations per condition, but only
**40 distinct tasks on 26 registrable domains**. Repeated observations stay
together in the site-cluster bootstrap. The earlier count of 27 sites used
hosts rather than registrable domains.

## 1. Grounded repair versus blind repair

Code: `18df996508e5e0420e1ee9ee698d7951a75499f4` in both conditions; blind
uses `CU_SF_REPAIR=blind`. This precedes the stricter verifier.

| Measure | Blind | Grounded |
|---|---:|---:|
| Graded passes | 55/120 (45.8%) | 73/120 (60.8%) |
| Wrong but self-check says PASS | 17/120 (14.2%) | 29/120 (24.2%) |
| Self-check does not accept | 48/120 (40.0%) | 18/120 (15.0%) |
| Self-check precision | 76.4% | 71.6% |
| Median / mean time | 7.35 / 8.74 s | 8.70 / 10.59 s |
| p90 time, nearest rank | 15.39 s | 18.12 s |
| Mean recorded steps | 1.82 | 2.29 |
| Mean model calls | 2.12 | 2.33 |
| Dollars per task | $0.000601 | $0.000778 |
| Dollars per graded pass | $0.001312 | $0.001279 |

Per-run passes: blind **17, 19, 19**; grounded **26, 24, 23**, each out of
40. Per-run false accepts: blind **6, 5, 6**; grounded **8, 9, 12**.

Exploratory paired site-cluster bootstrap (10,000 resamples, seed 20261114):

- Pass-rate difference: **+15.0 percentage points**, 95% interval
  **+5.4 to +25.2**.
- False-accept difference: **+10.0 points**, 95% interval **+3.7 to +16.2**.

Grounding repairs improves completion, but it also increases confident wrong
answers. It is useful engineering progress, not a sufficient reliability win.
The cost per successful task is almost unchanged and mean time rises.

| Task kind | Blind passes | Grounded passes | Blind false accepts | Grounded false accepts |
|---|---:|---:|---:|---:|
| Navigation | 22/30 | 26/30 | 1/30 | 4/30 |
| Value | 20/30 | 22/30 | 2/30 | 7/30 |
| Search | 8/18 | 15/18 | 0/18 | 0/18 |
| Form | 3/18 | 4/18 | 0/18 | 5/18 |
| Title | 2/12 | 4/12 | 9/12 | 8/12 |
| Dynamic page | 0/12 | 2/12 | 5/12 | 5/12 |

## 2. Stricter verifier gate

Complete. Before:
`18df996508e5e0420e1ee9ee698d7951a75499f4`; after:
`56fbcab7c1efb88c90839254bb184f4afb23a537` ([PR #70](https://github.com/advcode118/alexs-computeruseoptimisation/pull/70)).
Both use grounded repair. Order: after, before, repeated three times. All six
runs completed with matching 40-task membership and zero process exit failures.

| Measure | Before | Stricter verifier |
|---|---:|---:|
| Graded passes | 82/120 (68.3%) | 74/120 (61.7%) |
| Wrong but self-check says PASS | 21/120 (17.5%) | 15/120 (12.5%) |
| Self-check does not accept | 17/120 (14.2%) | 31/120 (25.8%) |
| Self-check precision | 79.6% | 83.1% |
| Median / mean time | 8.13 / 10.33 s | 9.16 / 11.25 s |
| p90 time, nearest rank | 19.73 s | 20.02 s |
| Mean recorded steps | 2.31 | 2.54 |
| Mean model calls | 2.35 | 2.66 |
| Dollars per graded pass | $0.001169 | $0.001500 |

Per-run passes: before **28, 26, 28**; after **27, 23, 24**, out of 40.
Per-run false accepts: before **7, 8, 6**; after **4, 7, 4**.

Exploratory site-clustered 95% intervals: pass difference **-6.7 pp
[-15.6, +3.1]**; false-accept difference **-5.0 pp [-11.9, +1.6]**.
Neither interval excludes zero. Lower wrong-accept counts come with lower
observed completion and higher mean latency/cost, so this gate **does not
establish a net improvement**. The stricter verifier remains experimental on
the draft integration branch; it is not a recommended release based on dev3.
Investigate general false-rejection mechanisms on development data before
adopting or narrowing these rules. Do not tune individual val3 failures.

## Measurement corrections and limits

1. **Recall is not independently measured by the final rows.** In
   `bench/probe.py`, `grade_observation` makes a runtime FAIL/UNKNOWN block
   final success. `bench/heldout3_report.py` then divides the joint runtime
   and final passes by final passes. The resulting 100% is imposed by that
   definition, not evidence of zero false rejections. Future reporting needs
   a separately recorded page/answer grade before applying the runtime gate,
   or a blinded audit of rejected results. Existing success scores and the
   frozen grader are not changed here.
2. The confidence intervals are exploratory and conditional on these three
   runs. They were not a preregistered confirmatory test, do not correct for
   repeated selection on val3, and are not a claim of generalisation.
3. Alternation always puts the new version first; it is not counterbalanced.
   The verifier gate overlaps the reader's development probes. Timing needs
   a quiet-machine confirmation before a speed claim. Load can also affect
   timeout failures, so accuracy cannot be assumed immune to contention.
4. No new pre/post page-drift audit accompanies these gates. All 40 tasks are
   retained without rescoring or post-hoc exclusions.
5. `steps`, `script_steps`, and `model_calls` are retained under their recorded
   names in the JSON; they are not interchangeable. Per-task reporting would
   break the gate's aggregate-only rule, so the raw logs remain local and the
   report supplies aggregate and per-run counts instead.

## Provenance

`repair.json` contains complete aggregate metrics and a source manifest with
absolute local filenames, byte counts and SHA-256 digests. It contains no task
identifiers or answers. `verifier.json` records the complete validated second
gate. The analysis checks identical task membership, unique
rows, model, effort and arm before pooling. P90 uses nearest rank.

Analysis script on this machine:
`C:/Users/epicd/AppData/Local/Temp/opencode/val3_gate_summary.py`.

## Next decisions

- Diagnose the stricter verifier's possible false rejections using independent
  development-page grades and local reproductions. Its net gain is unproven.
- Finish the reader comparison (always-on versus suspicious-answer-only),
  preserving the first-contact dev4nav result separately.
- The owner requested Astra for all unfinished agents. Reader, form,
  dynamic-page, observe-first, executor and search work resumed on Astra in
  their original worktrees. Form and dynamic-page drafts are PRs #72 and #73;
  final measurements are pending. A separate Astra contribution investigates
  verifier rejection risks and independently measured recall. Integrate only
  supported changes, retaining negative findings.
- The original heldout3 measurement stays on frozen code in `cuo-tip2` and is
  paused at 5/16 runs. Resume it only when development probes are quiet; it
  cannot validate the later tip3 changes. A later candidate evaluation must
  be explicitly distinguished from that original frozen test.
- Reconcile project spend across the main and nine development ledgers before
  authorising another batch. A read-only recovery snapshot gave approximately
  **$7.19**, versus **$5.88** in the main file alone. This uses a multiset union
  of complete ledger entries (preserving repeated identical calls within a
  ledger) and counts the $1.330861 recorded prior once. Ongoing calls can raise
  it. Keep the $20 project cap, existing per-agent caps, and frozen-run stop;
  no ledger is reset or rewritten by this analysis.
