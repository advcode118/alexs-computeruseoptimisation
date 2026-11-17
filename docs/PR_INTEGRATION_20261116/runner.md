# Offline evaluation-driver handoff — 16 November 2026

## Status and scope

**Implemented locally; no paid or public-live run launched.**

- Isolated branch: `t3/offline-pr-eval-driver`.
- Inspected baseline/initial HEAD:
  `d4f9d03abe278ebad44d1391cc67b4d3b83b8005` (PR82).
- The initial worktree was clean. No candidate merges were needed for this task.
- Implementation: `tools/pr_eval.py`; focused tests: `tests/test_pr_eval.py`.
- Final local HEAD is supplied in the handoff message. The runtime manifest also
  records the evaluated checkout's HEAD, dirty flag, selected runtime source
  SHA-256s and the driver's SHA-256; an external driver's SHA is distinct from
  the evaluated runtime revision.
- Read `AGENTS.md`, `docs/HISTORY.md`, `NOTES.md`, and the integration audit's
  `README.md`, `budget.md`, `inventory.md`, `runtime_candidates.md`,
  `verifier_segments.md` and `other_candidates.md`.
- No real ledger was read or edited, no protected heldout3/4/val3 per-task
  evidence was inspected, and no saved task outcomes were used for this
  implementation. Tests use synthetic requests, results and temporary ledgers.
- No shared-integration edits, installs, extra checkout, subagents, API calls,
  public task-verifier scripts, GitHub mutations, push, watches or branch
  deletion. This change does not modify production clients, budgets or grading.

## Parent prerequisite: reconcile first

The audit's retained-history charge is **$14.579971**, not the present-main
audit figure of $12.036672. Parent owns the one-time **+$2.543299** import
with provenance and stable-source checks. The documented extra-import route
changes `recorded_extra_usd` from $1.330861 to **$3.874160**.

The runner never performs that import. It requires an existing canonical
`~/.cu-optimisation/openai-spend.json`, correct stored arithmetic, at least the
reconciled total **and** the reconciled extra, and no abort/unresolved calls.
It refuses an environment override pointing to any other resolved path.
There is no `--ledger` escape hatch and no missing-file zero seed.

The extra floor deliberately supports the audit's documented extra-import
route. An alternative full-trie import with lower extra will be refused and
needs explicit adaptation/review. Floors are a sanity check, **not evidence
that the import was performed correctly or that an invoice is complete**.
Parent must quiesce all other paid writers before launching.

## Scope of each invocation

- Direct sequential `run_claude_arm("script_first", task, provider="openai",
  model=..., effort="medium", script_cache=None, ...)`, one cold task at a time.
- Default model: `gpt-6-luna`. Optional `--model gpt-6.1-sol`, still medium only.
- Only `dev3`, `dev4form`, `dev4spa`, `dev5title` are accepted; an absent split
  is refused at launch. `dev5title` is absent at this PR82 baseline.
- `--task-limit N` selects the first N tasks in the existing split order.
  No arbitrary IDs, paths, held-out split aliases, warm pass, browser_use,
  Decisions or task-catalog verifier entrypoints.
- Existing post-run grade and runtime-marker separation remain unchanged.
  The existing catalog import internally constructs its normal catalog;
  the runner selects only the allowed DEV split and exports no other task rows.
- `CU_PAGE_SUMMARY` and the known `CU_SF_*` flags are captured from the
  environment. They are checked before each task/request and after each task;
  drift stops the run. Values are validated before logging. Unknown `CU_SF_*`
  switches and enabled Decisions environment switches are refused.
- Supported strategy values are any comma-ordered subset of `nav,form,spa`.
  Other known flags are listed in `FLAG_CHOICES`. An unset value retains that
  checkout's default. A flag unavailable in a checkout can be ineffectual;
  match capabilities/source hashes as well as flag text between conditions.
- Import/help/default CLI planning makes no ledger, catalog or network access.
  `--execute` is the explicit **parent-only** launch switch. The Python
  `evaluate()` function is also a paid entrypoint, not a dry-run helper.

## Accounting and locking

1. Hold an OS-exclusive, nonblocking lock on the stable sibling
   `openai-spend.json.pr-eval.lock` for ledger load, the entire run, all response
   handling, final accounting and manifest flush. The file is never deleted.
   Windows uses a held `msvcrt` byte lock; POSIX uses `flock`.
2. Hook `OpenAIClient.create_message` only inside the runner's context and
   restore it afterwards. Inspect/bind the checkout's original signature,
   including its default `max_tokens=4096`; a source without `tool_choice`
   also works. Call that original method rather than reimplement HTTP or
   response shaping.
3. Build and validate the actual Responses body, reject unsupported/multimodal
   inputs and hosted tools, calculate a bound, and persist it in
   `recorded_extra_usd` **before** calling the original client.
4. The temporary transport wrapper permits exactly one dispatch to the
   original Responses endpoint with the exact reserved serialized body.
   It validates raw usage before the source normalizer can default absent
   counts to zero or coerce fractions/bools. Unknown usage, malformed details,
   bad totals and inconsistent cache/reasoning counts fail closed.
5. On success, immediately call canonical `OpenAISpendLedger.record_task`
   once per API call, with unique UUID-based run/call IDs. Remove exactly
   that call's reserve and atomically save the actual entry. There is **no
   outer task recorder** or `execute_openai_probe()` call.
6. On an error, retain the reservation and stop. Unresolved records block
   future runs until parent resolves them from evidence. A crash between
   reserve and dispatch may conservatively charge an unsent request.
   No automatic reclaim, retry, reserve expiry or abort reset is implemented.
7. Ledger writes preserve historical task entries, stored price metadata and
   unrelated top-level fields. Only new calls use the checkout's current
   pricing. Unique same-directory temporary files are flushed/fsynced then
   replaced. No production `ledger.save()` call (which rewrites price metadata).
8. A pre-write fingerprint detects observed outside writes. This is not an
   atomic compare-and-swap against nonparticipating writers.

**Caps:** default evaluation new-spend allowance is **$1.50**, measured from
the fixed reconciled origin $14.579971, hence an absolute evaluation ceiling
of **$16.079971**. New invocations/checkouts/flags do not reset it; unrelated
new canonical spend also consumes it conservatively. An explicit
`--evaluation-cap-usd` must be positive and at most $5. Admission uses the
minimum of evaluation ceiling, opening total + $5, $20 project cap, and any
stricter stored run/project caps. Known-price next-call reservations must fit
before dispatch. There is no task-level overshoot allowance.

## Bound assumptions and limitations

The bound is intentionally conservative but **not an unconditional billing
guarantee**:

- Input bound = bytes in the complete `json.dumps(payload)` UTF-8 encoding
  (matching the current transport's default serialization) **+ 4096 tokens
  + 256 tokens per input item and function schema**. This assumes at most
  one text token per serialized byte plus that framing allowance. It includes
  instructions, tools and schemas. It is not an official provider/tokenizer
  upper-bound theorem; unusual server-side framing could exceed it.
- Output is explicitly bounded to an integer 1–4096 tokens, including
  reported reasoning tokens within the output total. The harness's default
  remains 4096, rather than silently changing the task's output budget.
- Reserve every input token at the largest published input/cache-write rate
  in `bench.openai_spend.published_rates()`, multiplied by the long-context
  factor 2; reserve output at long-context factor 1.5 regardless of length.
  At this source: Luna $0.50/$0.75 per million input/output; Sol $10/$15.
  Round reserves **up** to $0.000001.
- Rate provenance is the existing source's published-rate table and cited
  pricing URLs. This offline task did not independently revalidate current
  pricing or the provider's invoice.
- Returned input/output counts are compared with the individual token
  bounds, and actual dollars with both reservation and admission ceiling.
  A violation records the full actual cost, marks the ledger aborted, and
  stops further dispatches. It does **not** clamp already-incurred charges.
  A provider exceeding bounds can therefore already have exceeded a nominal
  cap before detection. Unknown billing fields/missing billing cannot be
  bounded merely by parsing the fields we recognize.
- Ordinary coroutine cancellation waits for the original client's in-flight
  request to complete, accounts it, then re-raises cancellation while still
  holding the run lock. A killed process cannot cancel remote billing; its
  durable outstanding reservation prevents another runner launch.
- All writers must honor this sidecar lock. Stock probes do not; their use
  must remain quiesced. OS locks and atomic replacements are not an
  invoice-completeness proof, network-filesystem guarantee or full
  power-loss transaction system. Windows behavior was tested here; POSIX
  code is implemented but was not executed on this machine.

## Output and timing

Each new output directory contains `manifest.json` and flushed/fsynced
`rows.jsonl` (plus any ordinary harness artifacts). Existing directories are
refused instead of overwritten.

- Manifest: evaluated revision/dirty/source hashes, driver hash, model,
  effort, flags, DEV task order, run/call IDs, opening/closing ledger totals,
  admission ceiling, calls/bounds/statuses and run status.
- Completed rows retain the original grade fields, self-checks, script
  turns, steps/model calls/segment receipts and `wall_ms`. No re-grading.
- `usd` is the sum of per-call actual charges **plus unresolved reservations**;
  `actual_usage_usd` and `unresolved_reserved_usd` are separate. The original
  task-aggregate estimate is retained as `harness_usd`. Per-call pricing also
  avoids applying a long-context threshold to the sum of separate requests.
- An interrupted task without a returned grade has `success: null` and
  `grade_available: false`; it is not fabricated as a zero-cost graded failure.
  The runner stops before another task. Partial output is not a completed
  matched comparison.
- `wall_ms` is explicitly labelled **budget-instrumented harness wall**.
  It preserves the source's exclusion of final grade reads. Ledger work
  occurs inside that clock and can affect the segment deadline.
  `budget_hook_ms` measures successful pre-dispatch/settlement bookkeeping;
  it does not measure every error path or transport-wrapper validation.
  Do not subtract it to claim uninstrumented wall time.
- `driver_task_wall_ms` additionally includes setup, grade and teardown.
  Match runner instrumentation and machine load across conditions; no speed
  or accuracy improvement is established by these offline tests.
- No environment dump, key, headers or raw transport exception is emitted.
  Failure output is deliberately generic; status/usage data remains in the
  local manifest and canonical ledger. DEV row content is the source's
  ordinary task evidence, not an environment export.

## Invocation (examples only; paid example NOT executed)

The parent may copy this driver/tests into integration, or use the absolute
driver while selecting the evaluated checkout with `PYTHONPATH`. Start a
fresh process per condition. The driver does not prepend its own repository
to `sys.path` when run as an absolute script.

```powershell
# Offline plan, no ledger access:
python -m tools.pr_eval --split dev3 --task-limit 1

# Parent-only, AFTER reconciliation/quiescence/explicit launch:
$env:PYTHONPATH = 'C:\Users\epicd\Projects\cuo-pr-integration-20261116'
$env:CU_OPENAI_SPEND_LEDGER = 'C:\Users\epicd\.cu-optimisation\openai-spend.json'
$env:CU_SF_SEGMENTS = '1'
$env:CU_SF_STRATEGY = ''
$env:CU_SF_LOOK = '0'
$env:CU_SF_REPAIR = 'grounded'
$env:CU_SF_MAX_REPAIRS = '3'
$env:CU_PAGE_SUMMARY = '0'
# OPENAI_API_KEY must already exist in the launch environment; do not print it.
python 'C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3df6dc75-c72ace6f81735bf9\tools\pr_eval.py' `
  --execute --split dev4form --task-limit 1 `
  --output 'C:\Users\epicd\Projects\cuo-pr-integration-20261116\bench\runs\pr_eval_segments_smoke'
```

Use unique output directories for off/on runs. Remove `--task-limit` for the
whole selected DEV split. Repeat invocations still share the fixed $1.50
evaluation allowance. An alternate checkout must expose the compatible
`bench` APIs used here; unknown signatures/bodies fail closed.

The runner does not automate matched ordering, starting-state reset,
comparison thresholds or the report's pair-1 stopping rule. Those remain
parent orchestration responsibilities. It provides call admission, serialized
accounting and unchanged grade rows for the approved matched tests.

## Offline verification

Commands were run only in this isolated worktree:

1. `python -m pytest -q tests/test_pr_eval.py`
   - Initial run: 38 passed, 3 failed in new test setup/assertions (synthetic
     cap origin, overrun magnitude, a stub shadowing the function under test).
     Those test-construction mistakes were corrected without loosening the
     admission or accounting contract.
   - Next run: **41 passed in 1.27s**.
2. `python -m pytest -q tests/test_pr_eval.py tests/test_openai_provider.py tests/test_script_cache.py::test_the_live_run_never_reads_the_answer_key tests/test_prompt_audit.py`
   - Before the last portability/provenance additions: **62 passed in 3.52s**.
   - Final result: **63 passed in 2.13s**.
3. `python -m tools.pr_eval --split dev3 --task-limit 1`
   - Offline plan only, exit 0, Luna medium, $1.50 evaluation cap; no ledger
     or catalog access and no execution.
4. `git diff --check`
   - Passed. New files were additionally staged and checked with
     `git diff --cached --check` before the local commit.

Focused coverage includes reservation-before-transport, per-call cache-write
settlement, preservation of historical prices/Decisions records, no outer
double charge, unknown/missing/malformed usage, timeouts, persist failures,
cap and canonical-ledger refusals, source-signature variants, flag freezing,
unchanged grading telemetry, cross-process lock contention, killed-owner
release, cancellation, absent DEV splits, and absolute CLI/PYTHONPATH use.

The requested full suite remains the parent's final combined-tree job after
heavy parallel work completes. No public live verifier was run. The general
verification skill's sync/telemetry and broad check launcher were omitted to
respect this task's strictly local/offline scope and targeted-tests-first
instruction; the repository's declared pytest runner was used directly.

Durable findings: the source client normalizes absent usage to zero and its
ledger writer replaces historical price metadata; this shim explicitly
guards both. Also, a fixed evaluation origin is necessary to avoid resetting
the matched-test allowance on each checkout/flag invocation.
