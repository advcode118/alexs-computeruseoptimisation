# OpenAI project budget reconciliation — 16 November 2026

## Decision

**Conservative charge for the retained ledger histories: $14.579971. Remaining recorded-budget headroom: $5.420029 of $20.**

The existing main ledger says **$12.036672** and therefore understates this conservative reconciliation by **$2.543299**. Do not start paid probes using its present balance. The retained histories do **not** demonstrate an exhausted cap, but the executable accounting and concurrency controls are **not yet reconciled/safe for another paid run**.

This is a read-only reconciliation, not an API invoice audit. No tests, probes, secret access, ledger writes, source edits, or Git mutations were performed. All dollar amounts below are aggregate recorded budget charges, including historical reserves; they are not independently verified invoice charges. No protected per-task results, answers, scripts, or failures were read.

Scope: `C:/Users/epicd/Projects/cuo-pr-integration-20261116`, branch `t3/pr-integration-20261116`, audited HEAD **`b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5`** (`github/t3/tip4`). Ledger directory: `C:/Users/epicd/.cu-optimisation`. Aggregate computation timestamp: **2026-11-16 12:40:38 UTC**.

At **2026-11-16 12:42:59 UTC**, a second byte-hash read confirmed all 13 ledgers still matched the fingerprints below. This checks input stability, not the absence of in-flight API calls.

## 1. Inputs and arithmetic integrity

All 13 files parse. In every file, the stored total equals `recorded_extra_usd + sum(tasks[].usd)` exactly to six decimal places. No negative entry costs were found. Every file specifies $20 project / $5 per-run caps and `aborted: false`; that flag does not prove concurrency safety or complete billing.

| Ledger filename | Entries | Entry USD sum | Recorded extra | Stored total |
|---|---:|---:|---:|---:|
| `openai-spend.json` | 3,856 | 10.705811 | 1.330861 | 12.036672 |
| `openai-spend-dev-a.json` | 2,929 | 4.453151 | 1.330866 | 5.784017 |
| `openai-spend-dev-b.json` | 3,368 | 4.927170 | 1.330861 | 6.258031 |
| `openai-spend-dev-c.json` | 3,256 | 4.566144 | 1.330861 | 5.897005 |
| `openai-spend-dev-d.json` | 2,968 | 4.429286 | 1.330861 | 5.760147 |
| `openai-spend-dev-e.json` | 3,126 | 4.680119 | 1.330861 | 6.010980 |
| `openai-spend-dev-f.json` | 2,750 | 4.550973 | 1.330861 | 5.881834 |
| `openai-spend-dev-g.json` | 2,802 | 4.593887 | 1.330861 | 5.924748 |
| `openai-spend-dev-h.json` | 2,806 | 4.595577 | 1.330861 | 5.926438 |
| `openai-spend-dev-i.json` | 3,072 | 4.752322 | 1.330861 | 6.083183 |
| `openai-spend-dev-j.json` | 3,189 | 4.914727 | 1.330861 | 6.245588 |
| `openai-spend-dev-k.json` | 3,300 | 4.881350 | 1.330861 | 6.212211 |
| `openai-spend-dev-l.json` | 2,910 | 4.669868 | 1.330861 | 6.000729 |

Naively adding the stored totals yields **$84.021583**. That repeatedly counts copied history and the historical prior and is not project spend.

### Input fingerprints

SHA-256 is over the exact file bytes. Times are UTC last-write times, rounded here to milliseconds. File creation times are not reliable fork dates: the writer replaces each ledger using a temporary file.

| Ledger | Bytes | Modified UTC | SHA-256 |
|---|---:|---|---|
| main | 1461127 | 2026-11-15 02:23:54.707 | `35abe53d32511d6fd415d1fcd6fd7e5c17979a8caf680f98f53c4e9149fab81f` |
| dev-a | 1103685 | 2026-11-14 16:25:35.561 | `d38c0c264360e13eee78b0106ffecb5c2bd5f164aa5fe1e69c95aaeec5c73aa1` |
| dev-b | 1268862 | 2026-11-14 15:23:20.845 | `5ed3bc1a8f5d337681185546d3cf14068a5989d57ca0cb267bb5c7cf990be97e` |
| dev-c | 1224027 | 2026-11-13 22:50:33.759 | `edbd48ea578dbe33096e52f75a9523d229f3f66a758ce2b7c6ba0d6297233f3d` |
| dev-d | 1118083 | 2026-11-14 16:10:24.629 | `10e49e488a9d6eabd51f842fbf85d769f90cae6e95a58abad3b884ac5e080346` |
| dev-e | 1177928 | 2026-11-14 03:01:05.200 | `cc0b4f8d903b0374c3f6830a3a9db980740fe955eab1c28c3f86fba12d874bc4` |
| dev-f | 1037961 | 2026-11-13 22:13:50.156 | `9bf8d8f7291e2584288b3d2e395d184f195b8937ae2e3f604a55b3d4c2fa5e2e` |
| dev-g | 1057553 | 2026-11-14 15:49:44.430 | `46d66878d14095ed9a9affe2fea01366c66cd44f2904586c566e02eed6dc18ab` |
| dev-h | 1059198 | 2026-11-14 15:55:18.871 | `c473c1b0a5dac64d0f45c6be62939b1f1085b6f147f2a67fe75fc825b9a6db64` |
| dev-i | 1158512 | 2026-11-14 16:18:50.213 | `cee9669f7acb914dacd9a0f585542271004f6f433dbdd934024ba91a3ff12410` |
| dev-j | 1202632 | 2026-11-14 18:01:08.849 | `3c8bfabecac5d8d7d342696816158f429410c17dfeb8e825467568562310df56` |
| dev-k | 1243700 | 2026-11-14 17:45:30.869 | `ed37a46bac0b7e46d90b6a23fa088a8ceb05f2ec2cdbe766ad26dc1527a1aab6` |
| dev-l | 1098042 | 2026-11-14 21:50:38.009 | `8c5c61935d54f8af8c281a84b1d1c2dfb4ffb608db8593fe9bfb80dbdf01371d` |

## 2. Why these are forked histories

The strongest evidence is **complete ordered entry equality**, not equal scalar balances or equal token counts:

- Every ledger begins with the same **2,609 complete entries**, costing **$4.277999**; with the documented prior, their common opening balance is **$5.608860**.
- Main and dev-e through dev-l continue identically through entry **2,696**, balance **$5.790813**.
- Main and dev-f through dev-l continue identically through entry **2,750**, balance **$5.881834**.
- Main and dev-l continue identically through entry **2,784**, balance **$5.924355**.
- Dev-f ends at entry 2,750: it contributes **no additional entry spend**.
- All ledgers contain the same inherited **244 Decisions entries / $0.047344**. These are included, not separately added again.

Independent documentary corroboration at the audited HEAD:

- `docs/HISTORY.md:216-218` records that the PC ledger was seeded with the historical OpenAI total **$1.330861**.
- `docs/TEST_RESULTS.md:195-212` explains the predecessor accounting: **$0.280861 priced usage + $1.05 extra/reserves = $1.330861**. The seed is not a new charge on each development fork.
- `docs/FORM_STRATEGY.md:23,69` explicitly labels dev-g's **$5.881834** opening balance as inherited history; its measured ledger increment is **$0.042914**.
- `docs/STRATEGY_SPA.md:218-220` does the same for dev-h; its documented increment **$0.044604** matches the present suffix.
- `docs/results/tip4_gate_20261114/README.md:84-96` documents dev-j's **$5.881834 → $6.245588** increment of **$0.363754**. Its **439 charged ledger entries** correspond to 440 observations with one zero-usage attempt.

This establishes copied ancestry sufficiently for conservative retained-history accounting. No original copy command, fork manifest, or exact fork timestamp was found in the three specified orchestration scripts. The sequence structure establishes relationships to the main-history spine; it does not prove which physical file was the source of every copy.

`agg.py` and `pairs.py` summarize run-result rows; neither clones, merges, reserves, or writes a spend ledger. They were inspected as text, **not executed**. `probe_slot.sh` limits processes, not spend; details below.

## 3. Branch-trie reconciliation

Method: parse money with `Decimal`; compare canonical JSON for **all fields of each complete entry**, preserving order and repetitions. Share an entry only when the entire preceding sequence is also shared. At a divergence, charge both branches separately forever, even if subsequent complete entries happen to match. Add the historical prior once and retain dev-a's additional **$0.000005** conservatively.

This avoids the unsafe inference that equal independent calls must be duplicates. Ledger entries have no request UUID or timestamp; the normal probe writer uses the constant `run_id="probe"` (`bench/openai_run.py:180-202`).

| Fork | Shared spine entries | Inherited opening USD | Additional entries | Suffix USD |
|---|---:|---:|---:|---:|
| dev-a | 2,609 | 5.608860 | 320 | 0.175152 |
| dev-b | 2,609 | 5.608860 | 759 | 0.649171 |
| dev-c | 2,609 | 5.608860 | 647 | 0.288145 |
| dev-d | 2,609 | 5.608860 | 359 | 0.151287 |
| dev-e | 2,696 | 5.790813 | 430 | 0.220167 |
| dev-f | 2,750 | 5.881834 | 0 | 0.000000 |
| dev-g | 2,750 | 5.881834 | 52 | 0.042914 |
| dev-h | 2,750 | 5.881834 | 56 | 0.044604 |
| dev-i | 2,750 | 5.881834 | 322 | 0.201349 |
| dev-j | 2,750 | 5.881834 | 439 | 0.363754 |
| dev-k | 2,750 | 5.881834 | 550 | 0.330377 |
| dev-l | 2,784 | 5.924355 | 126 | 0.076374 |
| **Development suffix total** | | | **4,060** | **2.543294** |

The complete main spine contains 3,856 entries / $10.705811. Its continuation after the latest fork is 1,072 entries / $6.112317; that continuation is already included in the main scalar total.

```text
Main stored total                                  $12.036672
All development suffixes, counted by branch          $2.543294
Dev-a extra above the shared historical prior        $0.000005
Conservative project charge                         $14.579971
Remaining under $20                                  $5.420029
```

Equivalent trie check: **7,916 entries**, entry charge **$13.249105**, plus maximum recorded prior **$1.330866**, gives **$14.579971**. No entry was repriced using today's rates.

### Uncertainty bounds

For the **retained histories**, assuming the supported copied prefixes and faithful append-only records:

- A maximum-multiplicity union of complete entries has **7,834 entries / $13.233706**. With the conservative maximum prior, it gives **$14.564572**. This is an optimistic lower endpoint, **not** the budget to authorize against.
- The trie gives **$14.579971**, a conservative upper endpoint that counts every post-divergence occurrence independently.
- Difference: **82 occurrences across 77 signatures / $0.015399**. All have generic `run_id="probe"`. They can be independent equal-usage calls. No evidence justifies merging them.
- Using only the documented historical prior instead of dev-a's slightly higher value lowers the lower endpoint to **$14.564567**. The unexplained **$0.000005** is retained in the recommended accounting; no refund or repricing is assumed.
- Thus conservatively reserved retained-history headroom is **$5.420029**; the optimistic headroom is **$5.435428**, which should not be spent.

The previous report's **$8.333360** (`docs/results/tip4_gate_20261114/spend.json`) was an older, explicitly non-atomic max-multiplicity estimate. It is neither a present balance nor a reason to remove the $0.015399 uncertainty.

These are not unconditional bounds on all API billing. Existing writer races, a killed process before recording, or calls absent from every retained ledger cannot be recovered from these inputs. There is no finite upper bound on such *unobserved* charges from these files alone. If copied ancestry were rejected altogether, even summing every entry while counting the prior once gives **$68.051251**; that intentionally loose bound ignores the strong copying evidence. Therefore: **retained-history accounting is reconciled conservatively; invoice completeness remains unverified**. A claim that actual project billing is exactly $14.579971 would be too strong.

## 4. Existing controls and gaps

### Already present at the audited baseline

- `bench/openai_spend.py:64-65,87-92`: $20 project and $5 run constants; `CU_OPENAI_SPEND_LEDGER` selects the shared file, otherwise defaults to `~/.cu-optimisation/openai-spend.json`.
- `bench/openai_spend.py:376-404`: historical missing-call allowance and $1 unpriced-call reserve. These are accounting adjustments, **not advance reservations for concurrent calls**.
- `bench/openai_spend.py:435-474`: loads Decisions entries without requiring an effort and preserves a stored scalar exceeding the reconstructed total as extra. Decisions compatibility is already included via **`439bcfc25f8760179e85131c0c715464174e3451`**.
- Cache-write pricing / unpriced-charge retention is already included via **`542ad6ae6fdb07a7e1789971b4515485765ddf68`**; finished-row flushing and browser-use usage compatibility via **`b33989acd2bc53201c98acb6997ba85639e0a7ad`**.

These fixes do not reconcile forked ledgers or provide a concurrent project budget.

### No shared-ledger transaction or advance reservation found

`OpenAISpendLedger` reads into process memory once. `record_task()` mutates that local list. `save()` writes the entire list through the fixed sibling name `.json.tmp`, then replaces the ledger (`bench/openai_spend.py:335-374,426-432`). There is no mutex, reload-and-merge transaction, or reserved-dollar balance. Atomic replacement of a file is **not** atomic read-modify-write: two processes can overwrite each other's entries or collide on the temporary path.

`execute_openai_probe()` loads the ledger once (`bench/openai_run.py:307`). It checks cumulative run/project spend **between tasks**, calls the task, then prices/saves it (`:180-202,332-386`). `execute_benchmark_tasks()` has the same task-level timing (`bench/harness.py:2002-2045`). Consequently even a single run can exceed a nominal cap by its in-flight task. No worst-case next-call/task reservation was found in these paths.

The code search covered the integration baseline's Python budget/writer paths and the specified local orchestration scripts. This does not claim every external launcher or every unmerged branch was exhaustively audited.

### Slot wrapper

`C:/Users/epicd/.cu-optimisation/probe_slot.sh:4-19` uses atomic directory creation to acquire a slot, defaults to **two** slots, and deletes any slot directory older than **40 minutes** when waiting. It has no ledger lock, dollar reservation, heartbeat, or owner-liveness check.

- Different callers can request different slot counts. One caller setting `CU_PROBE_SLOTS=1` does not stop a second caller from taking slot 2.
- Age-only deletion can remove an active long-running owner's slot and admit another process.
- The slot name does not identify a ledger transaction. A nonparticipating writer bypasses it completely.

This is useful resource throttling, not a robust project-spend guard. No existing reliable parallel-call reservation implementation was found.

## 5. Required handoff before new paid calls

Parent-owned actions; none performed in this read-only task:

1. **Quiesce all paid writers and acquire one exclusive project writer lock before reading or changing the ledger.** Recheck all 13 hashes above; recompute if any changed. Stable files alone do not establish that no API call is currently in flight.
2. **Keep one existing canonical ledger:** `C:/Users/epicd/.cu-optimisation/openai-spend.json`. Make every paid process use that exact resolved path via `CU_OPENAI_SPEND_LEDGER`; prohibit per-agent forks and missing-file zero seeds. Preserve the fork files as audit inputs.
3. **Carry forward the conservative missing-history charge once.** With these exact inputs, a documented one-time adjustment of **$2.543299** to main's extra would change `recorded_extra_usd` from **$1.330861 to $3.874160**, leave its existing task entries intact, and bring its total to **$14.579971**. This is imported prior spend plus a conservative overlap allowance, not a new API charge. Record the input hashes and adjustment provenance so rerunning reconciliation cannot double-add it. A transactionally imported trie is another implementation, but do not also add its cost as extra.
4. **Use one serialized paid writer initially.** Hold an OS-level mutex/advisory lock across ledger load, complete paid run, final accounting and flush; start the next process only afterwards. All launchers must honor it. A save-only lock cannot repair stale process-local ledgers. Parallel read-only audits and isolated offline tests can continue.
5. **Hard caps need advance admission control.** Before admitting a billable request, reserve a defensible maximum based on model/rates, input bounds and output-token limit, against both remaining project headroom and that run's remaining $5. Reconcile actual returned usage immediately; keep unresolved charges reserved after errors. For multiple independent model turns in a task, reserve/check each turn or the entire bounded task. Do not rely on typical historical average cost, task-level postchecks, or a fixed $1 error allowance as a guaranteed upper bound.
6. If paid parallelism is required, first implement a single coordinator (or cross-process locked reservation transaction) that serializes **reserve → dispatch ownership → settle**, with unique call/run IDs, crash-safe outstanding reservations, reload-under-lock, and distinct temporary filenames. Sum actual spend and outstanding reservations before authorizing each call. That implementation is not present in the audited baseline and has not been tested here.

**Go/no-go:** the retained ledgers leave $5.420029 conservatively, so they do not establish exhaustion. **No-go with the present main balance and stock concurrent launch path.** The user's post-reconciliation paid approval can be used only after the parent carries forward this charge, resolves any known missing-call evidence, and enforces shared-writer/cap admission controls. These accounting findings make no accuracy or performance claim.

## 6. Source fingerprints for follow-up

Repository paths and line references above are at `b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5`.

| Source | Git blob at audited HEAD |
|---|---|
| `bench/openai_spend.py` | `28e12963d24e26cdcec81ce910bee6964050feb3` |
| `bench/openai_run.py` | `ac9b61aad1977b5ce2f6791a7f135204fe2bb162` |
| `bench/harness.py` | `0150d56a3e14b0d680f65de5d5b86edc7990f4cd` |
| `docs/HISTORY.md` | `86ecb8a7bb4f50357b1b4ac4efd442f19dc42dfa` |
| `docs/TEST_RESULTS.md` | `cd6306b533119179d93b860e11c79afee1ff4698` |
| `docs/FORM_STRATEGY.md` | `065b60f97c564387b65ab662ce8b9b11c6f83f62` |
| `docs/STRATEGY_SPA.md` | `a647ba10fe4a62b33292fdde34662eb467a4fa71` |
| `docs/results/tip4_gate_20261114/README.md` | `654f7d8da954ad38bd34a9acafae41598f5e8c6a` |
| `docs/results/tip4_gate_20261114/spend.json` | `4c6f7ed9d00c639e08fec9b1001df691f2d39c66` |

Local source fingerprints:

| File in `.cu-optimisation` | Modified UTC | SHA-256 |
|---|---|---|
| `agg.py` | 2026-11-14 02:31:33.151 | `fd0a3813b1d1bde90e784b3e00fea2258a1ae85610043282bf268485dd4d63e5` |
| `pairs.py` | 2026-11-14 03:14:39.073 | `721c5bbaf124e874ff029e41c5e4de13daaab04df61f5695b85eb76ba57ffa07` |
| `probe_slot.sh` | 2026-11-14 15:40:23.306 | `2c8c3895f83d558b4f524718c7073074fcac12af34f3b522ec6a7eac0d98eceb` |

The prior aggregate-reconciliation source `C:/Users/epicd/AppData/Local/Temp/opencode/reconcile-completed-spend.py` was read, not run. Its lines 31-43 implement the older maximum-multiplicity method; its result-processing and file-writing paths were not executed. No per-task records are reproduced in this artifact.
