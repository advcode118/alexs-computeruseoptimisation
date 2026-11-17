# Open-PR inventory — 16 November 2026

## Decision summary

**73 open PRs collapse to seven genuinely uncontained runtime experiments/fixes.** Of those, three are the strongest immediate evaluation candidates: **#81 (title correctness), #74 (opt-in observe-first), #82 (opt-in segments)**. **#76 (search)** and **#79 (verifier narrowing)** need additional evidence/review. Existing evidence argues against wholesale integration of **#77 (executor bundle)** and **#49 (Decisions overturns)**.

This is a read-only usefulness/ancestry triage, not a test result or merge approval. No tests, probes, source edits, Git mutations, PR changes, ledger access/edits, or secrets access were performed. Protected heldout3/heldout4/val3 task definitions, per-task results, scripts and failures were not opened. Filenames and commit metadata were inspected. Historical dev evidence below is attributed to its actual revision; no new accuracy measurement was made. New generalisation claims require a new blind set.

### Pinned comparison

- Integration checkout: `C:/Users/epicd/Projects/cuo-pr-integration-20261116`, branch `t3/pr-integration-20261116`.
- Baseline / #80 / `github/t3/tip4`: **`b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5`**.
- PR82 reference: **`d4f9d03abe278ebad44d1391cc67b4d3b83b8005`**.
- All **51 exact ancestors of tip4 are also exact ancestors of PR82**. PR82 contains only itself additionally among the 73 open heads: **52/73**. It does **not** include #81.
- Metadata companion: [pr_inventory.json](C:/Users/epicd/Projects/cuo-pr-integration-20261116/docs/PR_INTEGRATION_20261116/pr_inventory.json). It records full head/base SHAs, titles, declared base branches, all merge bases, `git cherry` classifications, changed paths and the exact open-head containment graph.

| Mutually exclusive bucket | Count | PRs |
|---|---:|---|
| Exact head contained in baseline | 51 | Every `A` row below, including #1 and #80 |
| Merge-only duplicate content | 1 | #2 |
| Exact patch-equivalent replacement | 1 | #40 |
| Reimplemented/superseded runtime work | 3 | #20, #22, #24 |
| Obsolete/stale contribution | 2 | #14, #37 |
| Separate site history | 3 | #19, #43, #51 |
| Residual docs/evidence/tests, no new runtime | 5 | #45, #46, #58, #67, #78 |
| Genuinely uncontained runtime work | 7 | #49, #74, #76, #77, #79, #81, #82 |

## Method and interpretation

The GitHub open list was obtained with `gh pr list --repo advcode118/alexs-computeruseoptimisation --state open --limit 100`. Each head was checked with `git merge-base --is-ancestor` against both pinned references, then with `git cherry`, `git merge-base --all`, commit metadata and filename-only diffs. Source comparisons used selected non-protected runtime files. The metadata generation additionally derives the complete containment graph from `git rev-list`.

- `A` means **exact head ancestry**, not merely a matching title or patch, and means **zero new contribution to this baseline**. It does not mean every historical implementation remains unchanged.
- `P` means the unique patch is already present under another SHA.
- `R` means a semantic reimplementation: `git cherry` still reports `+`. Do not call those patch-equivalent.
- `D` means residual docs/evidence/tests only; `N` means genuinely novel runtime; `H` means hold/obsolete; `S` means separate site history.
- Table SHAs are unambiguous short forms; the JSON preserves every full SHA and the resolved base SHA. Base names are the **current PR targets**, not necessarily the actual fork point.
- Table paths/reasons describe what is still novel, not the huge two-dot tree difference against an old branch. An old branch lacking later fixes is not itself evidence that its merge would delete those fixes.
- `git cherry` ignores merge commits. #2 therefore required a content check. #79 has two merge bases; one triple-dot diff misleadingly includes already-integrated #75 work.
- GitHub reported all PRs `CLEAN` except #1 `DIRTY`, **relative to their existing targets**. That is not an integration-branch conflict check. No merge simulation or temporary merge was performed.

## Complete inventory: all 73 open PRs

`A` rows are contained in **both** tip4 and PR82. Every other row is contained in **neither**, except #82 which is the PR82 reference itself.

| PR | Head | Current base | Class | Unique changed files or verified reason |
|---:|---|---|---|---|
| 1 | `67bc4ed` | `main` | A / blocker | Origin-stack import already contained. Only open main-targeted PR; GitHub `DIRTY`. Never merge this target. |
| 2 | `f4fac5b` | `t3/base` | Duplicate | Unique merge commit only; original 98-line `NOTES.md` is an exact prefix of baseline notes. |
| 3 | `ce59055` | `t3/base` | A | Evidence judge and harness changes already contained. |
| 4 | `334a41a` | `t3/step2-evidence-judge` | A | Cached-script tier already contained; later no-oracle fixes supersede its historical runtime checks. |
| 5 | `1b26808` | `t3/step3-cached-script` | A | Cached-script review/fixes already contained. |
| 6 | `1aa1989` | `t3/step3-grok-review` | A | Fresh-worktree test skips already contained. |
| 7 | `94c8267` | `cursor/fresh-worktree-suite-ce57` | A | Prompt audit already contained. |
| 9 | `44813ed` | `cursor/prompt-audit-ce57` | A | Endpoint arm already contained. |
| 10 | `f1a1c5a` | `cursor/endpoint-arm-offline-ce57` | A | Cache fingerprint already contained. |
| 11 | `eb81796` | `cursor/cache-fingerprint-ce57` | A | Saved-log reporter already contained. |
| 12 | `c78384e` | `cursor/probe-log-report-ce57` | A | Offline-slice notes already contained. |
| 13 | `ad70719` | `cursor/notes-offline-slices-ce57` | A | Live control fingerprint fix already contained. |
| 14 | `bb73288` | `t3/base` | H | `scripts/setup.*`, `scripts/sync.*`, CI, old rules and fixture/ledger seed. Reinstates Grok/Cursor-era workflow; not a runtime speed contribution. |
| 15 | `cce340e` | `cursor/live-control-fingerprint-e09c` | A | Original held-out marker separation already contained. |
| 16 | `090d32c` | `cursor/held-out-task-set-84ad` | A | browser-use arm already contained. |
| 17 | `1172d64` | `cursor/browser-use-local-arm-afa9` | A | Canonical href attribute fix already contained. |
| 18 | `f89b16a` | `cursor/canonical-href-attribute-5c73` | A | Honest-probe command already contained. |
| 19 | `9a00192` | `cursor/progress-site-redesign-8676` | S / superseded intent | README/site links and React list key. No common ancestor with tip4; #51 removes Cursor links instead. |
| 20 | `33900fe` | `cursor/honest-live-probe-6b25` | R | Returned-evidence functions reproduced in #30; unique old `tests/test_returned_evidence.py` is not new runtime capability. |
| 21 | `db4079b` | `cursor/honest-live-probe-6b25` | A | Browser-use research note already contained. |
| 22 | `0d9348b` | `cursor/script-returned-evidence-fbdb` | R | Browser-launch overlap and prompt caching redone in #29/#30; stacks on #20. |
| 23 | `2e827a6` | `cursor/honest-live-probe-6b25` | A | Fail-closed shared grade already contained. |
| 24 | `ed1b6fd` | `cursor/overlap-launch-and-cache-cbb3` | R | Helper implementation and helper tests exactly match #30 blobs; stacks on #22/#20. |
| 25 | `dbf8642` | `cursor/one-grade-fail-closed-dd49` | A | Claimed-answer recording already contained. |
| 27 | `3409e8a` | `cursor/claimed-answer-every-arm-5fcc` | A | Page-body grading already contained; historical oracle-era numbers are not current accuracy. |
| 28 | `572c190` | `cursor/eiffel-rfc-script-end-state-5fcc` | A | Shared page-read grading already contained. |
| 29 | `b92c7f6` | `cursor/identical-grade-every-arm-4fb2` | A | Stable prompt cache already contained. |
| 30 | `98fcfea` | `cursor/script-first-prompt-cache-4fb2` | A | Returned evidence, launch overlap and helpers already contained. |
| 31 | `38e0bca` | `cursor/speed-overlap-and-helpers-4fb2` | A | Desktop-arm design note already contained. |
| 32 | `0fb9e5a` | `cursor/speed-overlap-and-helpers-4fb2` | A | Fairness audit note already contained. |
| 33 | `4e7e770` | `cursor/speed-overlap-and-helpers-4fb2` | A | Original 50-task scored set already contained. |
| 34 | `a9b5b86` | `cursor/held-out-score-set-c8df` | A | One-pass confidence interval/reporting already contained. |
| 36 | `b33989a` | `cursor/speed-overlap-and-helpers-4fb2` | A | OpenAI provider/accounting arm already contained. |
| 37 | `5dad8ef` | `cursor/speed-overlap-and-helpers-4fb2` | H | Stale “no probe logs” `docs/FAILURE_TAXONOMY.md`; exact ancestor of #45, whose document replaces it. |
| 38 | `fdb2210` | `cursor/openai-computer-use-4106` | A | Offline page replay already contained. |
| 40 | `f4c3ad5` | `cursor/offline-page-replay-6801` | P | Entire unique patch matches #42 `257f8cb`; no fresh latency fix. |
| 41 | `3e8bed0` | `cursor/openai-computer-use-4106` | A | Historical test-results docs/logs already contained. |
| 42 | `257f8cb` | `cursor/openai-computer-use-4106` | A | Cold read/UNKNOWN-call patch already contained, subsequently adjusted by fair-timing work. |
| 43 | `735f7fc` | `cursor/progress-site-redesign-8676` | S | Stats/site/README assets; exact ancestor of #51; no common ancestor with tip4. |
| 44 | `dbe9bfd` | `docs/test-results-2026-11-10` | A | “Our approach” wording already contained. |
| 45 | `fb4d735` | `cursor/failure-taxonomy-2781` | D | `docs/FAILURE_TAXONOMY.md`: real 10-Nov log taxonomy, replacing #37; historical documentation only. |
| 46 | `e23b4b9` | `t3/base` | D / tests | `loop/README.md`, `tests/test_check_page_local.py`; local-browser/MCP coverage for an existing implementation. |
| 47 | `9442722` | `cursor/script-first-cold-restack-694d` | A | No-answer-key runtime, fair timing and consolidated first tip already contained. |
| 49 | `6b59b52` | `t3/runtime-plain-rules` | N / hold | Decisions client/smoke, harness, pricing, reports and tests. Actual historical live runs exist despite stale title; acceptance gate failed. |
| 50 | `3cd5400` | `t3/tip` | A | Plain URL/title/h1/dash runtime rules already contained. |
| 51 | `4546426` | `site/stats-page` | S | Site/UI/data/README and copy checks; contains #43. Separate history; no browser-runtime improvement. |
| 52 | `439bcfc` | `t3/runtime-plain-rules` | A | Probe/repair traces already contained. |
| 53 | `56d24cc` | `t3/probe-trace` | A | Intact repair delivery and required tool calls already contained. |
| 54 | `f8932c9` | `t3/repair-delivery` | A | Trusted repair links/controls already contained. |
| 55 | `67e1bf6` | `t3/runtime-plain-rules` | A | Wider script grammar already contained. |
| 56 | `038848f` | `t3/runtime-plain-rules` | A | Heldout2 task/verifier split already contained. |
| 57 | `0bb215a` | `t3/repair-links` | A | Repair-plus-grammar combination already contained. |
| 58 | `aad3077` | `t3/tip` | D / protected records | Runtime already present through `b6bc142`. Only residual: `docs/HELDOUT3_PLAN.md`, `docs/results/heldout3_20261113/{bu_subset.py,manifest.txt}`; contents withheld. |
| 59 | `c365729` | `t3/heldout2-tasks` | A | Heldout2 audit already contained. |
| 60 | `526a6b5` | `t3/repair-grammar` | A | Missing required answer failure already contained. |
| 62 | `b7aeea3` | `t3/heldout2-tasks` | A | Heldout3b head exactly contained; protected contents not inspected. |
| 63 | `abc4a52` | `t3/heldout2-tasks` | A | Heldout3a head exactly contained; protected contents not inspected. |
| 66 | `c8c1eef` | `t3/tip2` | A | Val3 head exactly contained; protected contents not inspected. |
| 67 | `3bc3c4a` | `t3/tip2` | D | Only `docs/ARCHITECTURE_RESEARCH.md`; research, no runtime effect. |
| 68 | `fd57370` | `t3/tip2` | A | Dev3 definitions/verifier already contained. |
| 69 | `aa76956` | `t3/tip2` | A | Grounded repairs up to three turns and dev3 integration already contained. |
| 71 | `b9ac977` | `t3/tip2` | A | Tip3 consolidated runtime/precision checks already contained. |
| 72 | `441b0ea` | `t3/tip3` | A | FORM specialist and its dev evidence already contained. |
| 73 | `1dab4bb` | `t3/tip3` | A | SPA specialist and its dev evidence already contained. |
| 74 | `6927566` | `t3/tip3` | N | `bench/page_summary.py`, `observe_first_report.py`, harness/probe integration, fixtures/tests and dev evidence; opt-in. |
| 75 | `94b8bcd` | `t3/tip3` | A | Independent recall labels/false-reject audit already contained. Do not credit #79 with introducing them again. |
| 76 | `9c6f391` | `t3/tip3` | N | `strategy_search.py`, dev4search/checker/inspection, harness/openai_run/probe/tasks hooks and tests; paired measurement not committed. |
| 77 | `74f434e` | `t3/tip3` | N / hold | `script_resolve.py`, grammar/helpers/executor/harness/prompt changes, experiment runner and dev results. More wrong accepts in saved pair. |
| 78 | `ea474cf` | `t3/tip3` | D | Reader code/fixes through `3e53020` already included. Only new `docs/STRATEGY_NAV.md` update and `docs/results/nav_reader_20261114_post.jsonl`. |
| 79 | `9729d85` | `t3/tip3` | N / review | Only new runtime/report code: `bench/script_first.py`, `bench/selfcheck_replay.py`; three test files. Includes already-contained #75 ancestry. |
| 80 | `b5b74b3` | `t3/tip3` | A / baseline | This is the pinned baseline, including FORM/SPA/nav and #75 plus integration regressions. |
| 81 | `69357dd` | `t3/tip4` | N | URL punctuation, runtime site-name/evidence checks, dev5title and tests; not contained in #82. |
| 82 | `d4f9d03` | `t3/tip4` | N / PR82 reference | `bench/segments.py`, harness/runtime/arm/probe hooks, docs and synthetic tests; unmeasured opt-in prototype. |

## Verification of historical supersession labels

### #2 is content-contained, not head-contained

`f4fac5ba037db87250745e2d03063bece3bf45c7` is a merge with parents `69f1be1864a76444416de73b358c4b839493c031` and `e35843b144d90cf2859d706420a89dcd7a44e083`, both already in tip4. It is the only unique commit; `git cherry` returns no patches. `NOTES.md` at #2 and its first parent has blob `d1236f2c3311a4b38161837674cbbe6b82bc9fdc`; all 98 original lines survive as an exact baseline prefix. No new notes need recovering.

### #20 → #22 → #24 are redone, not patch-identical

All three old commits are `git cherry +`, and their heads are not ancestors of tip4. Their real dependency chain is #20 → #22 → #24.

- `_returned_problem` and `check_returned_evidence` have identical parsed ASTs in #20 `33900fe`, #30 `98fcfea`, and baseline `b5b74b3`. This verifies the returned-evidence mechanism was carried forward.
- #22, #30 and baseline all have `ScriptFirstClient.start()` delegate to `begin_launch()`; the browser launch overlap exists already. Stable system/tool prompt caching exists in baseline `bench/harness.py` and arrived on the newer #29/#30 line.
- `bench/script_helpers.py` **and** `tests/test_script_helpers.py` are byte-identical between #24 `ed1b6fd` and #30 `98fcfea`.
- The old lines still set runtime `end_markers` from task markers. Baseline `bench/harness.py` explicitly sets them to `{}` and uses `script_runtime_verdict`. Reusing the old benchmark tips would restore oracle-era behaviour; do not treat their old tests as a reason to replace the current harness.

### #40 is genuinely patch-equivalent

`f4c3ad5cd16b619dc7aeed45af133c77aa60da26` (#40) and `257f8cb0c90a0a0aa406be986c6790f4c0a20e45` (#42) both have stable patch ID **`927af539140cf55cb5e6a55294c266a98df54ded`**. `git cherry` marks #40 `-`; #42 is an exact baseline ancestor. No new experiment is needed to decide whether #40 adds code.

### #37 and #14 really are stale

#37's document at `5dad8ef` explicitly says there are no probe logs and no failure groups. #45 `fb4d735` replaces that text with a seven-failure taxonomy from the committed 10-Nov OpenAI logs. #37 is an exact ancestor of #45, so integrating #45 later can account for that history without separately adopting the stale document.

#14's `AGENTS.md` explicitly mandates Grok 4.7/Cursor, an obsolete $16.64 Claude total, and `t3/base`. Its sync script fetches/prunes, fast-forwards and pushes across worktrees. These are verified contents, not an inference from the title. Its tracked fixture/ledger seed is also outside the requested runtime work. Do not integrate the bundle wholesale; a separately justified CI improvement would be a new, selective task.

## The small candidate set, in dependency/evaluation order

The contained spine is #47 → #50 and repair/grammar/task branches → historical #58 runtime → #69/#71 → #80. **There is no need to merge the 51 contained heads to acquire their code.** Current #58 has three late record-only commits outside the spine.

### 1. Independent documentation/test additions

These can be reviewed independently of runtime experiments:

- **#46 `e23b4b9a1bc19327403f3e7f528d242d50894fc1`**: real local HTTP-page and MCP-client regression coverage in `tests/test_check_page_local.py`, documentation in `loop/README.md`. The underlying `check_page` already exists. Parent should check local Chrome availability and MCP SDK compatibility; a passing suite establishes coverage, not benchmark accuracy.
- **#45 `fb4d7358fa8c45fc356daa2e4a0114cc8cf0703b`**: historical failure taxonomy, based on #37. No new runtime benefit.
- **#67 `3bc3c4a7c174ec7016a9b2f1a51cb8adbc8f3da2`**: architecture research only. No measured implementation benefit.
- **#78 `ea474cfff81897ccbcee15e3cf64c536fdd93e76`**: report/evidence completeness only. Its runtime predecessor **`3e53020b7d11d0ccf966876d4cdc212be57d9012` is already in tip4**. Do not pay to re-evaluate it as a newly integrated reader.

### 2. Shared correctness foundation: #81, then independently review #79

**#81 `69357dde5265fe3c37704b45b8af3f4f606ac422`** is a direct tip4 child and a sibling of #82. Its three commits add dev5title (`f2cd379`, `585deb7`) and fixes (`69357dd`):

- `_clean_url` retains balanced URL brackets; this parsing fix affects every arm.
- `_site_name` recognises a site prefix using the live hostname.
- Runtime-only long `key_text` can match despite spacing changes; the final grade stays exact.

Source: exact runtime diff plus GitHub PR81 body. The body reports three baseline dev5title runs at 37/51 and three post-fix runs at 39/51, with false accepts 4 → 3, explicitly within noise. It also discloses a dev5title key correction. This inventory did not independently reproduce those logs; they are **reported development evidence**, not a proven gain or a strictly isolated runtime effect. The mechanistic correctness fixes warrant focused regression checks and a fixed-task matched comparison.

**#79 `9729d851a2b69e0c057784a2b5511941dae52029`** is conditional. It combines current #71 and #75 ancestry; both are already in tip4. Its two unique commits are **`b5e32196f2c79ea74609f818d73d42aa1e08880c`** and **`9729d851a2b69e0c057784a2b5511941dae52029`**. They narrow precision rules and add per-rule replay reporting. Novel paths are only:

`bench/script_first.py`, `bench/selfcheck_replay.py`, `tests/test_selfcheck_recall.py`, `tests/test_selfcheck_replay.py`, `tests/test_verifier_false_rejects.py`.

`git merge-base --all` gives both **`b9ac97772e532596ecaf9ba6b4435ffbce34832e`** and **`94b8bcde8e90d3dd1b75bb2c8b31a63c35081d17`**. A single triple-dot diff can falsely count #75 as novel. #79 and #81 both touch verifier code, but neither contains the other and #81 explicitly leaves the quantity-rule narrowing to #79. Review their combined false-accept/false-reject behaviour. The title's recall percentage was not independently validated here; protected replay inputs were not opened.

### 3. Evaluate the opt-in runtime candidates against the same fixed foundation

| Candidate | Actual dependency/source | Evidence and decision |
|---|---|---|
| **#74 `69275669c66948c32d82c4bf20cbc3d730ba8167`** | Fork point `bec55abe93c7b26f206142e21827e50ad362b8cd`; older tip3 runtime `56fbcab`. Novel summary/harness path. | Strongest saved dev experiment: three dev3 pairs, 99/120 off vs 109/120 on; false accepts 9 vs 2. **40 distinct dev tasks**, not 120 independent tasks. Keep opt-in, adapt to integration, then matched evaluation. |
| **#76 `9c6f391b647f9536756e9846739a4a93b8e0617c`** | Same `bec55ab` fork; new `strategy_search.py` and dev4search. | Committed `docs/STRATEGY_SEARCH.md` and PR body still say paired measurements pending. Author-route checks are not agent accuracy. Conditional candidate; do not treat “measured” in the title as evidence. |
| **#82 `d4f9d03abe278ebad44d1391cc67b4d3b83b8005`** | Direct child of pinned tip4; no dependency on #74/#76/#79/#81. | No new live accuracy measurement. Synthetic/no-model coverage is regression evidence only. Evaluate flag-off/on on matched dev tasks after accounting reconciliation. |

**#74 provenance matters:** `docs/OBSERVE_FIRST.md` at `6927566` attributes all six measured runs to **`43c8142cbd74c4dbfa7be8d08c934bbaad3f5180`**. Decoded gzip/deflate byte limits were added later in **`018ea294e2e4f02d6b94a299436ecd0c69b7ad97`**; final head `6927566` was not live remeasured. Saved aggregate evidence is in `docs/results/observe_first/tip3_20261114.json` with provenance in `tip3_sources.json`. Historical results support usefulness triage, not a claim about current tip4 or the post-fix head.

**Interaction constraint:** #82's active segment mode bypasses caches and specialist strategies (`docs/GROUNDED_SEGMENTS.md`, pinned head). Thus enabling #76/#78 together with segments does not measure their combined effect. #74's first-observation path also needs explicit integration review. Do not combine all candidates before their isolated comparisons and then attribute the result to each.

**Parallelism:** documentation and targeted static/test reviews are independent. #81/#79 verifier integration and #74/#76/#82 harness integration share files and should be applied serially by the parent. Once controls are pinned, independent dev comparisons can be scheduled subject to the reconciled shared project cap and machine/probe-slot constraints. No live evaluation was started by this inventory.

### 4. Hold two novel runtime bundles

**#77 `74f434edec976e286f5dd2c7bbcd837a4f19094b`: hold wholesale.** Source: `docs/results/robust_executor_20261114/README.md` at that head. The actual measured runtime was **`e9c8673d10a87a03d88303685a964c9ec2595a9b`**, compared with `bec55ab`, one 40-task dev3 pair. Final grade improved 28/40 → 33/40, but wrong accepts increased 4/40 → 6/40 and one-script stopped-and-graded passes fell 12/40 → 10/40. Its own final recommendation is to hold the bundle. Strict ambiguity checks have a separate synthetic mechanism test; that does not establish the usefulness of the grammar/preload/prompt bundle. Isolating those checks would be new work, not a reason to merge #77 whole.

**#49 `6b59b525ea279041158b5fc2d320594cdb11261e`: hold runtime.** Eight unique nonmerge commits, not included or patch-equivalent. Its title says “not run live” but `docs/TEST_RESULTS.md` sections 7c/7d and saved old-set results demonstrate actual 11-Nov runs. The later narrowed gate at **`44b118c8cc9a8dd224ccba7dc9507f337a89fcda`**, documented in `6b59b52`, produced nine overturns with only three graded passes: **33%, below its preregistered 90% requirement**. Plain URL/title/h1 rules from #50 are already in baseline; do not re-credit their benefit to Decisions. Porting this old harness/accounting path is not justified by its existing evidence.

## Docs/site-only branches and target blockers

- **#1 is the sole PR whose current base is `main`.** Its head is already in baseline, and GitHub reports conflicts with main. It must not be merged to its present target. Any future PR-status cleanup must respect the no-main rule; no retarget/close action was taken here.
- **#19, #43 and #51 have no merge base with tip4 or PR82.** They descend from the separate `cursor/progress-site-redesign-8676` history. Their incremental PR changes are site/docs/data changes, but wholesale histories include older loop code. Treat as a separate site decision, not a missing runtime stack.
- Site dependency: redesign `1ff4d1d1e9c2a358060b14b9029dc6e2ecd1f1fc` → #43 `735f7fcbe170261b645129fd69d14487e86a9dd2` → #51 `4546426bcf6f115316d32e069df49f1cdf41afcc`. #19 is a sibling of #43, **not** an ancestor of #51. #51 semantically supersedes #19's link goal by publishing only the GitHub link; #19 instead relabels an Origin link target and changes its React key.
- **#58's current head is not a baseline ancestor**, despite the integrated tip2 runtime. Its three unique late commits are `4ec9a69a7eb14aabca1691a76bea2ab8cdaed245`, `d78043188b987a1c268dbba4851a2d4d9dc12713`, and `aad3077cc501a4efb91fc18630000070830b90d8`; the only touched paths are the protected run-record paths listed in the table. Their contents were not read. They add no runtime to benchmark.
- **#78's current head is not a baseline ancestor**, despite its implementation being integrated. Its sole unique commit `ea474cf` contains the post-fix checkpoint report and extract, not new reader fixes.

## Parent handoff

1. Use the JSON's pinned SHAs to avoid moving-base/title mistakes.
2. Do not spend on exact ancestors, #2, #40, reimplemented #20/#22/#24, or report-only #58/#78 as if they were new runtime.
3. Prioritise #81 correctness checks, #74 opt-in adaptation, and #82 matched dev evaluation. Consider #76 only with author/paired evidence; #79 only with verifier precision review.
4. #46 is a useful independent test/docs candidate. #45/#67/#78 can improve documentation completeness.
5. Keep #49/#77 runtime out based on existing negative decision evidence; keep #14 obsolete workflow out; separate the site-history decision.
6. All tests, budget reconciliation, live probes, branch integration and GitHub disposition remain the parent's responsibility. No PR was changed or taken over.
