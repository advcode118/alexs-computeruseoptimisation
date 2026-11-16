# Older and non-runtime PR candidates

Read-only audit, 16 November 2026. Comparison baseline:
`b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5` (`github/t3/tip4`), the starting
commit of `t3/pr-integration-20261116`.

## Recommendation

- **Prioritize #46:** useful local-browser/MCP regression coverage, conditional on
  the parent running its seven new cases against the integration environment.
- **Integrate #78's remaining documentation/data commit:** the runtime fixes are
  already included; the new material records their limitations and checkpoint.
- **#45 and #67 are useful historical documentation**, with a short dated-status
  annotation before integration. Neither is an accuracy improvement.
- **Park #49 and #14.** #49 has a recorded negative result and is an unapproved
  probe endpoint for this task. #14 contains obsolete agent policy, a stale
  operational ledger seed, and cross-worktree mutation scripts.
- **Park #43/#51/#19 for a separate site port.** These heads have no merge base
  with the integration baseline. #51 has useful reporting infrastructure, but
  the website copy and experiment interpretation need updating before publication.

No tests, browser sessions, probes, external research/provider requests, ledger
access, source edits, or Git mutations were performed. The only authored artifact
is this file. `AGENTS.md`, `docs/HISTORY.md`, and `NOTES.md` were read first.
Protected heldout3/heldout4/val3 per-task contents were not opened. Read-only JSON
aggregation below used original 11-Nov held-out results, 10-Nov tuned/dev results,
and the explicitly development-only #78 checkpoint.

## Pinned candidates and declared checks

All PR URLs below are GitHub PRs, not Origin PRs. Checks were inspected through
`gh pr view/list`; they were not run here. “No checks” means an empty
`statusCheckRollup`, not that local checks failed. All nine candidates are draft,
and their returned `reviews` arrays were empty.

| PR | Exact head reviewed | Novel material against integration | Declared / recorded checks | Disposition |
|---|---|---|---|---|
| [#46](https://github.com/advcode118/alexs-computeruseoptimisation/pull/46) | `e23b4b9a1bc19327403f3e7f528d242d50894fc1` | `tests/test_check_page_local.py`, `loop/README.md` | PR body: seven new tests passed; branch suite 174 passed / 11 failed on old `t3/base`. No GitHub checks. | Merge after focused checks |
| [#78](https://github.com/advcode118/alexs-computeruseoptimisation/pull/78) | `ea474cfff81897ccbcee15e3cf64c536fdd93e76` | Only `docs/STRATEGY_NAV.md` and `docs/results/nav_reader_20261114_post.jsonl` remain | Author: 63 focused; permitted suite 855 passed / 1 skipped; prior pre-fix 892 / 1 is a different run. No GitHub checks. | Merge documentation/data remainder |
| [#45](https://github.com/advcode118/alexs-computeruseoptimisation/pull/45) | `fb4d7358fa8c45fc356daa2e4a0114cc8cf0703b` | `docs/FAILURE_TAXONOMY.md`, absent at baseline | No test claim or GitHub checks; saved-row counts independently recounted here | Merge as dated history |
| [#67](https://github.com/advcode118/alexs-computeruseoptimisation/pull/67) | `3bc3c4a7c174ec7016a9b2f1a51cb8adbc8f3da2` | `docs/ARCHITECTURE_RESEARCH.md` only | Docs-only; author declares no model calls/browser. No GitHub checks. | Merge with historical/research status |
| [#49](https://github.com/advcode118/alexs-computeruseoptimisation/pull/49) | `6b59b525ea279041158b5fc2d320594cdb11261e` | Decisions client, harness/ledger/CLI wiring, tests, experiment archive | PR body: 298 passed / 1 skipped, with 18 new tests claimed. No GitHub checks. Body/title contain stale “not run” language despite saved live runs. | Park runtime; retain negative-result evidence |
| [#43](https://github.com/advcode118/alexs-computeruseoptimisation/pull/43) | `735f7fcbe170261b645129fd69d14487e86a9dd2` | Separate-history site, stats route/charts, copy | Body says figures recomputed and site deployed; no build/test result or GitHub checks | Park; superseded site direction |
| [#51](https://github.com/advcode118/alexs-computeruseoptimisation/pull/51) | `4546426bcf6f115316d32e069df49f1cdf41afcc` | Site/data pipeline replacing #43's stale lead | Body checks off both Python validators, `npx tsc --noEmit`, `npm run build`, production HTTP checks. No GitHub checks. No deployment claimed. | Useful future port, not merge-ready |
| [#19](https://github.com/advcode118/alexs-computeruseoptimisation/pull/19) | `9a0019233268d7e70174ca4c09e61e04526b3f12` | Three link/key edits on separate-history site | No tests/checks; no redeploy | Superseded by #51's single GitHub link |
| [#14](https://github.com/advcode118/alexs-computeruseoptimisation/pull/14) | `bb73288234d5b305fbc716f53294b74aeb43a212` | Workflow/setup/sync/CI files, rules rewrite, fixtures and tracked spend seed | Body: 181 passed. Two `offline` GitHub checks SUCCESS on 10 Nov, actions runs `42815612000` and `42815603366`. | Park whole PR; selectively redesign CI later |

GitHub's reported `CLEAN` merge status for the seven initially assigned PRs is
relative to their **existing bases**, not the new integration branch.

## #46 — useful protocol coverage, not a new tool

[Exact diff](https://github.com/advcode118/alexs-computeruseoptimisation/commit/e23b4b9a1bc19327403f3e7f528d242d50894fc1)
adds 153 test lines and 29 README lines. `loop/checks.py`, `loop/mcp_server.py`,
and `loop/browser.py` have no differences between this head and the integration
baseline. `check_page` was already implemented.

Actual benefit:

- An ephemeral local HTTP server exercises clean loads, console errors, missing
  image/script assets, a slow load, and an unreachable address.
- A real official MCP SDK stdio client initializes, lists tools, and calls
  `python -m loop.mcp_server`. Existing `tests/test_checks.py` already tests the
  deterministic checker and protocol internals; this adds transport integration.
- The documentation accurately describes `ok`, diagnostics, zero model calls,
  and the existing 5-second navigation timeout. Current dependencies already
  declare `mcp==2.3.0` and `anyio` in `pyproject.toml`.

Parent check:

```text
python -m pytest -q tests/test_check_page_local.py tests/test_checks.py
```

Require the seven new cases to **execute**, not all skip. At lines 62–68 the new
browser fixture catches every launch exception and skips; an unavailable browser
does not establish working MCP coverage. The SDK-client case has a 60-second
AnyIO deadline and a 90-second worker-thread join; if it fails, surface the thread
exception rather than treating the historical seven-pass claim as current.
No API probe is needed. The old 11-failure count belongs to an old-base suite;
fresh-worktree/test-isolation improvements are already in the integration line.

## #78 — only the final evidence commit is missing

The implementation/fix commit
`3e53020b7d11d0ccf966876d4cdc212be57d9012` is an ancestor of the baseline.
`git log baseline..head` contains only
`ea474cfff81897ccbcee15e3cf64c536fdd93e76` (“Record reader checkpoint, latency,
limitations and validated accounting”). Its delta is documentation and saved data,
not a new specialist implementation.

The added JSONL has exactly 54 wrapper records with `revision: "3e53020"`:
14 `dev3_off`, 14 `dev3_always`, 14 `dev3_suspect`, and 12 `dev4_always`.
Each wrapper preserves `source`, `source_sha256`, `revision`, `batch_label`, and
the extracted `row`. It is expressly a metric/claim extract, not a raw-file copy.

The documentation's useful addition is the limitation statement: one post-fix
checkpoint does not establish a robust winning reader variant; the later dev4
checkpoint is 9/12, versus the separately preserved 10/12 first contact.
Reader rescues are execution events, not counterfactual evidence that the
unassisted script would have failed. Earlier reader costs omitted cache-write
premiums; the new reserve is an estimate, not reconstructed exact usage.
These are historical development outcomes at that runtime version, not current
independent accuracy or permission to enable the feature by default.

Parent acceptance: confirm the two-file-only delta, JSON parse/schema and batch
counts, and revision/source-hash provenance. No additional live probe or runtime
test run is justified solely by this residual commit. Do not merge the runtime
again or credit its already-contained fixes as new integration gains. The
specialist-ledger total quoted in this document is not the project-wide balance;
defer reconciliation to the assigned ledger audit.

## #45 — valid historical diagnosis, partly already explained elsewhere

[The document](https://github.com/advcode118/alexs-computeruseoptimisation/blob/fb4d7358fa8c45fc356daa2e4a0114cc8cf0703b/docs/FAILURE_TAXONOMY.md)
replaces #37's “no logs” note. Against integration, it adds a 43-line document;
#37 itself is not an ancestor of integration.

Read-only recount of the three named files at
`dbe9bfd5e91c153c47458ae4d1f37e7cc744e1c1` confirms 56 task rows and seven failures:

- `docs/results/2026-11-10/probe_20261110_214520.jsonl`: 32 cells, failed line 3.
- `.../probe_20261110_215922.jsonl`: 12 cells, failed lines 10–12.
- `.../probe_20261110_220242.jsonl`: 12 cells, failed lines 10–12.

The grouping is supported: one navigation miss, four answer-format mismatches,
two empty deliveries. A few quoted answers omit the source's leading em dash;
that does not alter the classification. The measured runtime named in
`docs/TEST_RESULTS.md` is `b33989acd2bc53201c98acb6997ba85639e0a7ad`; the taxonomy's
`1a4a4fe147d0dd9346efd2ef99e94fa7e1be996c` reference identifies historical grading
documentation, not a new experimental run.

Before integration, add a brief status paragraph:

1. This is the **10-Nov tuned/dev experiment**, not current failure rates or
   evidence that script_first never fails.
2. `stagehand` here is the local imitation, not the Stagehand library.
3. Format parity and the oracle/timing cleanup were subsequently integrated
   (#47); current grading/recall diagnostics also differ. Do not re-grade these
   sparse rows by assumption or publish their win rate as today's accuracy.

Its HN diagnosis is partly present in baseline `docs/TEST_RESULTS.md` section 3.3;
the unique benefit is a compact complete inventory with source row references.
No automated test is necessary for this documentation-only addition.

## #49 — recorded negative result; plain-rule wins already included

Review source:
[client/policy](https://github.com/advcode118/alexs-computeruseoptimisation/blob/6b59b525ea279041158b5fc2d320594cdb11261e/bench/decisions.py),
[results sections 7c–7d](https://github.com/advcode118/alexs-computeruseoptimisation/blob/6b59b525ea279041158b5fc2d320594cdb11261e/docs/TEST_RESULTS.md).

The final gate needs `p(task_done) >= 0.90` **and**
`p(answer_needed) <= 0.2`, not the task-done-only policy retained in parts of the
PR body/history. It may turn a soft runtime FAIL into PASS and suppress repair.
The final grader is not replaced, and overturned scripts are excluded from cache
writes. `off` is the default. `shadow` still calls the paid endpoint after timing;
it is not an offline mode.

Read-only aggregation of the six saved
`docs/results/rules_{off,on}_run{1,2,3}_luna_medium_20261111.jsonl` files at the head:

| Historical setting | 50-task pass counts | Overturns passing original grade | Targeted repairs passing original grade |
|---|---|---|---|
| Plain rules, Decisions off | 31, 36, 31 | none | none |
| Plain rules, Decisions on | 29, 35, 37 | 3/9 | 1/14 |

All six files are Luna/medium; the on rows total 149 Decisions calls and zero
logged errors. The fixed acceptance bar required at least 90% of overturns to
pass; 3/9 fails it. The one-task difference in mean pass count is not evidence
of a reliable gain. Section 7d attributes most wrong overturns to evidence still
rejected by the independent final checks. These are original-grader historical
outcomes, not recomputed accuracy at tip4.

Already included:

- #50's URL/title/h1/dash plain rules:
  `3cd5400ff927e2c14ded8083fae9af3805a42a2c` is an ancestor of integration.
- Compatibility for existing `kind: decisions` ledger rows:
  `439bcfc25f8760179e85131c0c715464174e3451`, now
  `bench/openai_spend.py:450–452`. Merging the client is unnecessary to retain
  those historical costs.
- Rich repair/script-turn telemetry has since arrived through #52/#69. Do not
  merge this much older harness merely to obtain `first_runtime_reason`.

Other costs of reviving it: harness hooks assume the older one-repair path;
timeouts may remain billable without recorded usage (explicitly acknowledged
in the PR); after-clock calls still spend money. These require a new integration
and budget design if ever revisited. No Decisions call is authorized by the
current matched-probe approval. **Keep parked; no new paid test.** Preserve the
negative-result note/immutable source links without enabling this runtime.

## #43 / #51 / #19 — useful UI work on a different history

`git merge-base baseline <head>`/three-dot diff finds **no common ancestor** for
all three site heads. #51 builds on #43; #19 is a separate sibling on the earlier
site. Ordinary retarget-and-merge cannot integrate these into tip4. An unrelated
history merge is not a reasonable shortcut for a site update.

### #43: contradictory headline survives its later stats correction

At `735f7fcbe170261b645129fd69d14487e86a9dd2`, the stats page does label the old
Sonnet result an oracle-assisted upper bound. However:

- `data/progress.ts:172–186` still says “18/18 and the fastest,” “latest probe,”
  and 3.18 seconds; the timeline/demo repeats that pitch.
- `.github/readme/hero.svg` and `README.md` still promote those values without
  the same visible qualification.
- `README.md:71` calls Origin the main remote and GitHub a mirror, contradicting
  the project rules.

Reusable charts and accessible tables are presentation work, not measured runtime
benefit. Prefer #51's replacement structure if undertaking a site port; do not
publish #43 as-is.

### #51: best reporting implementation, still not current copy

Useful source-level changes:

- Separate `data/measured.json` aggregates and `data/measured-tasks.json` rows.
- Explicit all-task versus successful-task latency populations, nearest-rank
  p90, per-task harness steps/model calls/script steps, and immutable source links.
- `scripts/check_measured.py` recomputes from pinned Git blobs, checks matching
  baseline source hashes, task pairing, model/effort and cold-run settings.
- `app/components/speed-chart.tsx` has SVG text alternatives and a non-color
  model distinction; `app/stats/page.tsx` provides tables. This is source
  inspection, not a visual/accessibility pass.
- Removes the redundant Origin chip, and retires the oracle-assisted hero.

Required corrections for a later port:

1. **Archive rather than “Latest numbers” / “The fair comparison”.** The data
   remains the 11-Nov 50-task experiment at
   `94427222b9fb9ce7b1e04f5dd62336321a745e00`, with separate #49 experiment
   evidence at `6b59b525ea279041158b5fc2d320594cdb11261e`. Source reproducibility
   does not make the old protocol identical to today's. Independent page/answer
   grading was added by `e7cf0dd50ad5b4785af5048a45cc248ebe7bcd6b`; its diagnostic
   labels cannot be inferred from old `success` values.
2. **Restore methodological caveats.** #51 drops #43's explicit warnings about
   differing arm browsers/timeouts and easy/guessable navigation tasks while
   labelling its comparison “fair.” Keep the version, date, one-run limitation,
   and historical protocol limitations adjacent to the numbers.
3. **Update mechanism prose.** `README.md`, `data/progress.ts` and the demo say
   “repair once.” Tip4 defaults to grounded repair with up to three repairs
   (`bench/arms.py:44`), subject to its budget. Describe the old experiment's
   mechanism separately from current behavior. The browser-use demo's “one
   action per call” simplification also needs qualification: its Python cells
   can batch actions.
4. **Make validation portable.** `check_measured.py` invokes `git show` on both
   old commits. A shallow CI checkout, or an archive without the unmerged
   Decisions objects, cannot reproduce this. Preserve source blobs/hash
   provenance or document an explicit historical-object dependency; do not
   merge #49's runtime merely to make the site validator work.
5. **Keep useful repo documentation.** Replacing baseline README wholesale
   discards Python setup/loop pointers. Baseline README itself has stale Origin
   deployment advice, but preserve its useful setup content during a rewrite.
   `check_site_copy.py` bans generic strings including `Origin`, `Sonnet`,
   `parked` and `untested` across README/app; scope it to stale claims instead
   of preventing honest caveats/history.
6. **Resolve page ownership deliberately.** Comparing whole site trees also
   removes baseline `/desktop`, `/runs`, `app/sheet.tsx`, and `data/loop.ts`.
   Those are not incidental cleanup justified by a stats update.

The committed $3.2185 OpenAI figure is explicitly a dated record, not current
remaining budget. Do not copy it into a ledger.

The integration worktree has no `node_modules`. Before recommending these UI
edits I read the installed sibling checkout's Next guides:
`C:/Users/epicd/Projects/computeruseoptimisation/node_modules/next/dist/docs/01-app/01-getting-started/03-layouts-and-pages.md`
and
`.../01-app/03-api-reference/05-config/02-typescript.md`.
The repo declares Next `^16.4.3`, React `^19.3.1`, TypeScript `^7.0.2`.
Guidance confirms App Router page exports and project-local CLI type checking
for TS7. No source/UI edit was made.

Parent checks if a site port is subsequently authorized: frozen-data recompute
and corrected-copy checks, local `tsc --noEmit`, production build, then rendered
route/link/table/chart inspection including narrow layouts. The original
validators should first be inspected for their old-source dependencies and
blanket banned phrases. No browser session/deploy is needed for this triage.

### #19: not a useful independent integration candidate

The three edits point both “GitHub” and **still-labelled “Cursor Origin”** chips
at GitHub and key the list by label to avoid duplicate href keys. #51 removes
the redundant chip entirely. Baseline does not have this site's `RepoLinks`
implementation. Park #19 rather than importing that site history for a link fix.

## #14 — useful CI idea bundled with obsolete operational behavior

The two commits are
`4cf424bddc00581db431d875d7cfa8710a72d5ab` (workflow/tools) and
`bb73288234d5b305fbc716f53294b74aeb43a212` (fixtures/ledger/Chrome setup).
Read the source; the names “safe sync” and “offline” are not sufficient grounds
for integration.

Concrete blockers:

- `AGENTS.md` restores Grok/Cursor implementation policy, disables Claude review,
  names `t3/base` as integration base, and quotes stale spend. It would regress
  the current authorized agents, branch and budget rules.
- `docs/WORKFLOW.md` instructs Cursor handoffs and integration into `t3/base`.
- `scripts/sync.sh` and `.ps1` enumerate **all worktrees**, fast-forward behind
  branches and push ahead branches. There is no branch-name allowlist or `main`
  exclusion. A clean `main` ahead/behind is eligible; other agents' clean
  worktrees are also eligible. `--dry-run` still fetches with `--prune`.
  The tests leave `main` up-to-date and do not cover its dangerous cases.
- It tracks `bench/results/spend.json` at the PR-described historical
  $12.912192, not the later $26.022488 Claude floor. Do not integrate that seed
  as an operational ledger. This audit did not read a live ledger.
- Bash setup deletes `.venv` when `.venv/bin/python` is absent; on a checkout
  with a Windows `.venv/Scripts` environment this can remove a legitimate env.
  The setup installs all Playwright browsers/system dependencies; it is broader
  than the focused check_page requirement.

Salvage, in a separate narrowly scoped change: read-only-permission GitHub Actions
for permitted offline tests, an idempotent platform-specific setup, and a
`CLAUDE.md` pointer to authoritative rules. Synthetic fixtures may be useful if
relocated explicitly as test data. Integration already ignores
`proxy/replay-cache.sqlite` and has the fresh-worktree skipping/test-isolation
fixes; those benefits are not novel here.

Future tests should exercise setup on Linux/Windows and workflow behavior on
temporary fixture repos. Do not run either sync script in the shared repository,
even as a shortcut for this integration. Historical green CI proves only that
old branch's test suite, not compliance with the current workflow.

## Other open-head scan, without duplicating runtime/graph reviews

A read-only ancestor/name-only-diff filter over the 73 open heads found the two
additional useful non-runtime deltas described above: #67 and #78. Remaining
older nonancestor cases do not justify another runtime review:

- **#2** `f4fac5ba037db87250745e2d03063bece3bf45c7`: its `NOTES.md` content is already
  preserved; baseline has additional Step 3/offline-queue sections. No unique
  documentation to bring back despite the ancestry result.
- **#37** `5dad8efa6e98f5fa58b36cd30785476666d1de0f`: superseded by #45's real-log
  taxonomy; do not merge the “no logs” stub separately.
- **#20/#22/#24/#40**: `docs/HISTORY.md:227–235` explicitly identifies the returned
  evidence/overlap/helpers and cold-latency lines as superseded by #30/#42/tip.
  Their residual files are runtime/test copies, not unique maintainability docs.
  Leave their detailed disposition to the existing graph/runtime inventory.
- **#58** `aad3077cc501a4efb91fc18630000070830b90d8`: the residual paths are
  `docs/HELDOUT3_PLAN.md` and two files under `docs/results/heldout3_20261113/`.
  Only path names were inspected; contents were deliberately not read. Route
  preservation decisions to the validation-evidence owner.
- **#74/#76/#77/#79/#81/#82** were excluded from substantive review as assigned
  to the runtime reviewers. An already-contained head is not a new feature
  merely because its PR is still open.

### #67 annotation needed before treating it as current guidance

Its single-file research note is useful for documenting the architectural bets,
especially browser-use 1.0.3's code-cell loop, observation grounding, warm fallback,
and cautions about vendor benchmarks. Its 88–93%/95% success targets and latency
targets are explicitly estimates, not measurements. External claims were not
revalidated in this saved-evidence audit.

Mark it **13-Nov research, not the active implementation plan**:
grounded repair (#69), stricter checking, and opt-in specialists are already
implemented at tip4. Later observe-first/executor reviews now supply the actual
development experiments; the research note cannot substitute for their findings.
Its unqualified causal statements (“reliable because it looks”) are hypotheses,
not controlled evidence. Aggregate 138-task figures were supplied in its brief,
not independently verified here. Its instruction to use “dev or val” is not
authorization to tune on protected val3; current work uses permitted development
data and any new accuracy claim requires a new blind set.

No code test is needed for the annotated document. Preserve source date and
version links; do not turn projected gains into a release headline.

## Parent handoff order

1. Run #46's local targeted suite in an isolated test environment; merge if the
   actual cases pass.
2. Bring #78's evidence-only remainder and annotated #45/#67 docs into integration;
   their review can proceed independently of runtime tests.
3. Keep #49/#14 and the separate-history site PRs parked. A site modernization is
   useful follow-up work, not a reason to weaken grading or import old workflows.
4. Record merged documentation/test benefits separately from measured runtime
   performance. This audit establishes no new accuracy or speed result.
