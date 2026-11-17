# PR integration: budget reconciliation and schema smoke (16 Nov 2026)

Author: Opus test sub-agent, the only paid writer. One paid task only. This is an API, schema and accounting smoke. It is not performance evidence.

## 1. Runner review (`t3-3df6dc75…/tools/pr_eval.py` @ d7c4a80)

**No blocking bug. Nothing was patched.** What I checked:
- It holds the sidecar lock `openai-spend.json.pr-eval.lock` across load, run and flush, and reserves durably before each dispatch.
- The ceiling is the minimum of $20, the stored caps, opening + $5 and 14.579971 + 1.50 = **16.079971**.
- It settles once per call, with no outer recorder. `run_claude_arm` does not reach `run_benchmark`'s `ledger.record_task`/`save`.
- An unresolved, overrun or aborted call blocks the next launch.
- The PR82 grade path is deterministic only (`probe.deterministic_success`: "LLM judge is not called"). The `strategy_*` paths go through the patched `OpenAIClient.create_message`.
- `recompute` quantizes to 6 dp, so the exact Decimal arithmetic check in `hold()` stays consistent across invocations.

Minor points, not blocking:
- Reservations are about 25–45× the actual charge (this smoke: $0.0096–$0.0175 reserved per call against $0.0001–$0.0008 actual). Very large prompts could hit the ceiling early, but that is the conservative direction.
- A completed row carries `grade_available: null`. Only interrupted rows set it.
- The bounds are assumptions, not provider invoice guarantees (documented in `runner.md`).

## 2. Ledger reconciliation (done, under the runner's own lock)
- Paid-writer check: 5 `python.exe` and 5 `bash.exe` processes were running (PIDs 146300, 143272, 32208, 78852, 89864; 168936, 138784, 93628, 164780, 164048). None had a probe, `pr_eval`, checkpoint or `ho3` command line. I killed nothing.
- I took `exclusive_writer` from the audited runner, then checked all 13 SHA-256s. All matched `budget.md`.
- Backup of the exact original main ledger, SHA-256 verified as `35abe53d…`: `C:\Users\epicd\.cu-optimisation\ledger-backups\openai-spend.pre-reconcile.20261116T130653Z.131508.json`
- Changes written to `C:\Users\epicd\.cu-optimisation\openai-spend.json` with an atomic write:
  - `recorded_extra_usd` 1.330861 → **3.874160**
  - `running_total_usd` 12.036672 → **14.579971**
  - Added `reconciliation_imports[{id: "budget-reconcile-20261116-fork-suffix-2.543299", adjustment, previous/new, all 13 source hashes, evidence path, backup}]`. The script refuses to run if that ID is already present, so the import cannot be applied twice.
- Verification:
  - All 3,856 entries are unchanged, and so are all other fields, including historical prices.
  - Entry sum 10.705811 + extra 3.874160 = total 14.579971, checked exactly in Decimal. Headroom is 5.420029.
  - The fork files were not touched (hashes rechecked).
  - Post-import main SHA-256: `adb434fe63a1a31eedaf3257ccc665a7840172ae4c0220fbb94622de1fcc5640`.
- Script: `C:\Users\epicd\AppData\Local\Temp\claude\6660201ebf0a9be2\4f719d5f-23f4-4112-9f99-16c2af19a4e4\scratchpad\reconcile.py`
- `OPENAI_API_KEY` was **absent** from the inherited environment. I used the project's documented route (`docs/STRATEGY_SPA.md:208`): export it from `~/.cu-optimisation/openai.key` into the child process only. The key was not printed or edited. `ANTHROPIC_API_KEY` was unset for the launch.

## 3. Schema smoke (one paid task)
- Command: absolute runner, `PYTHONPATH` = PR82 checkout @ `d4f9d03` (dirty = false), `--execute --split dev4form --task-limit 1`, gpt-6-luna, medium, default $1.50 cap.
- Flags: `CU_SF_SEGMENTS=1 CU_SF_STRATEGY= CU_SF_LOOK=0 CU_SF_REPAIR=grounded CU_SF_MAX_REPAIRS=3 CU_PAGE_SUMMARY=0`, with the canonical ledger.
- Output: `C:\Users\epicd\Projects\cuo-pr-integration-20261116\bench\runs\pr_eval_20261116_schema_smoke\` (`manifest.json`, `rows.jsonl`, `harness/`)
- Manifest `status: completed`, exit code 0. It ran 13:07:03–13:08:06 UTC.
- Task `dev4_form_cura_appointment`: **graded fail** ("the script stopped before it finished (segment expectation failed)").
  - `wall_ms` 33,851 (budget-instrumented)
  - `driver_task_wall_ms` 61,228
  - `budget_hook_ms` 656
- 7 calls, **all settled**, none unresolved.
  - Raw usage parsed under the strict schema. It includes `cache_write_30m_tokens` (now reported by the API), all of it within the bounds.
  - Input tokens 1,554–4,464 per call, output tokens 52–756.
- Cost: actual **$0.002209**. The harness estimate was $0.002208 (a 1 µ$ rounding difference between per-call and aggregate pricing).
- Final canonical ledger:
  - Total **$14.582180**, extra 3.874160, 3,863 entries, `aborted: false`.
  - Arithmetic is exact.
  - The 7 `pr_eval_calls` are all settled.
- Remaining evaluation allowance: about $1.497791, out to the 16.079971 ceiling. Project headroom: $5.417820.

## Potential blockers / notes for parent
- The key is not in the inherited environment. Future launches need the same export from the key file, or a set environment variable.
- Stock probes ignore the sidecar lock and would drop the `pr_eval_calls` and `reconciliation_imports` keys on `save()`. Keep them quiesced.
- One task failed on a segment expectation. That says nothing about performance: n = 1 and this was a smoke run.
