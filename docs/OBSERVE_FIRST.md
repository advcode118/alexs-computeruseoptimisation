# Observe-first: bounded dev3 ablation

Status: all three pairs complete; **keep as an opt-in experiment**
(`CU_PAGE_SUMMARY=1`). Default-on rollout is not justified by dev3 alone.

## Mechanism and comparison

Fetch the task's start URL over HTTP while Chrome launches. Pass a capped
summary of headings, task-ranked link text/URLs, search forms and fields to
the first model call. An unusable fetch preserves the ordinary script-first
path. There are no task IDs, site-specific rules or grader inputs in this
mechanism. Fetch/read/parse share a 1.5-second consumer deadline; a late
daemon-thread result is discarded. TLS verification is required.

Both arms use `github/t3/tip3` runtime `56fbcab` (including grounded repair
and its current verifier), merged with documentation tip `bec55ab`.
The only experimental switch is `CU_PAGE_SUMMARY=0` versus `1`.
The runtime and grader remain fixed throughout the six runs.
All six manifests identify measured commit `43c8142cbd74c4dbfa7be8d08c934bbaad3f5180`.

## Recovered preliminary evidence

The prior files are `probe_20261113_220428.jsonl` (off) and
`probe_20261113_221313.jsonl` (on), each with 40 dev3 rows and one report.
They predate current grounded repair/verifier and are historical evidence,
not controls for this experiment. Empty probe files are not measurements.
The expired-key attempt on the parent's scratch branch contributes no data.

Recalculation from the saved rows confirms off **26/40** and on **29/40**,
with **18/40 first-script self-passes in each arm**. Single-script runs that
actually stopped and passed the shared grade were **16/40 off versus 15/40
on**. Both arms had three final self-PASS/shared-grade-fail false accepts.
The on file records **29/40 usable summaries**, five no-content responses,
two HTTP 403s and four timeouts; the supplied 30/40 coverage recollection is
not supported by this saved file. An independent counterfactual grade for
every first script is unavailable because these older rows lack self-check
payloads. Their combined cost, **$0.039215**, matches the ledger's final 80
entries exactly. Raw files are preserved losslessly as gzip with SHA-256
digests in `docs/results/observe_first/preliminary_sources.json`.

## Protocol fixed before the new runs

- All 40 dev3 tasks; Luna (`gpt-6-luna`), medium effort, script_first only.
- Three pairs: off/on, on/off, off/on. One sequential probe per agent, each
  invoked through `sh C:/Users/epicd/.cu-optimisation/probe_slot.sh`.
- No warm replay, optional look tool, legacy repair or other experimental arm.
- Record all attempts and failures. No tuning between runs or selective reruns.
- Primary outcome: final shared-graded passes. Also report self-check false
  accepts, independently derivable first-script grades and their coverage,
  first-script self-passes, first-model latency, wall-time median/mean/p90,
  fetch coverage/wait, model calls, steps and token-priced cost.
- First-script self-PASS is not a first-script grade. Intermediate scripts
  lacking selector evidence must remain ungradable rather than count as fails.
- Repeated tasks are not 120 independent tasks. Pair consistency and cost of
  failures matter; three dev3 pairs alone do not justify default-on rollout.

## Budget provenance

Only `C:/Users/epicd/.cu-optimisation/openai-spend-dev-a.json` is used.
Before resumption it contains 2,689 entries and totals **$5.648075**.
The first 2,609 inherited entries plus the recorded allowance total
**$5.608860**; the final 80 entries are the saved dev3 pair, **$0.039215**.
Thus the original-balance-plus-$1 ceiling is **$6.608860**, with **$0.960785**
remaining for all new work. No ledger reset or repricing is performed.

## Offline verification

Before edits: 111 focused tests passed. After explicit opt-in, removal of the
insecure TLS retry, and an absolute summary deadline: 113 passed, covering
summary parsing/ranking/integration, grounded repair, self-check precision,
cache isolation, repair delivery and prompt auditing. No frozen suite ran.

## Completed three-pair result

All six cells completed on the same code, with 40 unique dev3 tasks per cell,
the required model/effort/arm, one completion report per source and no skipped
rows. All failures remain in the denominators, including one off-arm attempt
with no script. These are 240 observations on **40 distinct development tasks**,
not 240 independent tasks. Other development jobs shared the machine.

| Measure | Summary off | Summary on |
|---|---:|---:|
| Final shared-graded passes | 99/120 (82.5%) | 109/120 (90.8%) |
| Final self-PASS but grade fails | 9/120 | 2/120 |
| First-script self-PASS | 35/120 | 56/120 |
| One-script stopped and graded pass | 30/120 | 55/120 |
| Independently derivable first-script passes | 32, plus 1 unavailable | 60, none unavailable |
| First-script pass bounds, including unavailable | 32–33/120 | 60/120 |
| All-task wall median / mean / p90 | 7.25 / 9.34 / 17.13 s | 6.57 / 8.29 / 16.70 s |
| Total wall / graded pass, including failed-task time | 11.32 s | 9.12 s |
| First model-call median / mean | 2.27 / 2.84 s (119 recorded) | 2.40 / 3.23 s (120 recorded) |
| Mean model calls / recorded steps | 2.158 / 2.117 | 1.717 / 1.692 |
| Recorded total cost | $0.079320 | $0.056617 |
| Recorded cost / graded pass | $0.000801 | $0.000519 |

P90 uses the reporter's inclusive linearly interpolated percentile. First-script
grades use saved page/claim evidence and the unchanged shared grader offline;
they are not inferred from self-PASS. Coverage is 119/120 off and 120/120 on.
The 30/55 stopped-and-graded counts are direct observations, distinct from
these counterfactual first-script grades.

| Pair (execution order) | Off passes | On passes | Off false accepts | On false accepts |
|---|---:|---:|---:|---:|
| 1 (off, on) | 33/40 | 35/40 | 3 | 2 |
| 2 (on, off) | 34/40 | 37/40 | 3 | 0 |
| 3 (off, on) | 32/40 | 37/40 | 3 | 0 |

Summary-on improved final completion in each pair. Usable summaries were
delivered in **87/120** on attempts (72.5%). The rest were 15 no-content
responses, six HTTP 403s, three certificate-verification failures and nine
timeouts. All use the ordinary fallback; certificate checks were not bypassed.
Summary wait median/mean/p90 was **326/498/1,263 ms**. The first model call
itself was slower on average, but fewer calls and repairs reduced total time
in this development run. Summary coverage does not identify a causal subgroup:
tasks with usable fetches differ from tasks without them.

**Recommendation: keep the opt-in mechanism for integration review; do not
enable it by default.** The consistent paired gains and improved first-script
grades support further development. They do not establish generalisation,
quiet-machine latency, interaction with other specialists, or a final release
win. No further probe was launched to recover these results.

## Post-measurement review and provenance

The agent's reporting continuation failed authentication after the managed
runner completed. Parent recovery read the six completed manifests and exact
source files, validated membership/model/effort/arm, and preserved lossless gzip
copies with raw-byte SHA-256 digests. The report, every task's metrics, and
reproduction commands are in `docs/results/observe_first/`.

Review found that the compressed download cap did not bound decompressed HTML.
Commit `018ea29` adds a decoded-byte limit for gzip and both deflate forms, with
ordinary fallback on excess. Three local regressions failed before the fix;
valid compressed responses, concatenated gzip members and the fallback path
pass after it. This is a **post-measurement fix**: the live numbers above belong
to `43c8142`, not to a live retest of `018ea29`. Large compressed pages may now
fall back instead of contributing a summary.

Final parent verification: **124 focused offline tests passed** across summary,
reporting, grounded repair, self-check precision, cache, prompt audit and repair
delivery. The temporary `verifier_audit_guard.py` launcher kept protected task
definitions and results closed and disabled non-loopback network access. This
is not a full-suite or completed independent-review claim.

The six-run ledger increased from **$5.648075 to $5.784017**, a **$0.135942**
delta. Recorded task-row costs sum to **$0.135937**; both are preserved rather
than rewriting the five-millionths difference. Including the preliminary pair,
the contribution's ledger increment from $5.608860 is **$0.175157**, below its
$1 cap. This specialist ledger is not the project-wide total; recovery made no
ledger edits and no API calls.
