# Observe-first: bounded dev3 ablation

Status: measurement in progress; **opt-in only** (`CU_PAGE_SUMMARY=1`).

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

## Recovered preliminary evidence

The prior files are `probe_20261113_220428.jsonl` (off) and
`probe_20261113_221313.jsonl` (on), each with 40 dev3 rows and one report.
They predate current grounded repair/verifier and are historical evidence,
not controls for this experiment. Empty probe files are not measurements.
The expired-key attempt on the parent's scratch branch contributes no data.

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
