# Offline maintenance/test integration — 16 November 2026

**Assigned product checks: PASS — 19 passed, 0 failed, 0 skipped.** All seven
new #46 cases executed, including the official MCP SDK stdio round-trip.
The four assigned candidates merged without conflicts; no runtime fix was needed.
Historical annotations for #45/#67 are committed locally.

**Overall evidence-recorder status: BLOCKED, open items `[]`.** Its immutable
aggregate retains three evidence-utility setup failures, subsequently resolved
by successful validators/cleanup commands. These were not pytest failures or
remaining product blockers; see “Failures and caveats.” Completion:
**DONE_WITH_CONCERNS** for the assigned maintenance task.

## Authority and baseline

- Owned worktree: `C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b`.
- Branch: `t3/offline-pr-integration-tests`.
- Initial clean HEAD: `d4f9d03abe278ebad44d1391cc67b4d3b83b8005` (parent PR82).
- Four-candidate merge HEAD: `fd2bc84729716b9d4ae493c0a88f7086d70b05df`.
- Final branch HEAD: `d0836d32f36a078876838764c0d36b3b8aee665b`.
- Offline-only functional testing; local merges and historical annotations explicitly assigned.
- Report/evidence belong in this directory. Shared integration checkout is read-only.
- No paid APIs, public benchmarks, installs, ledger edits, GitHub mutations, watches or delegation.
- Protected heldout3/heldout4/val3 task rows, answers and scripts are outside scope.

## Charters (recorded before tests)

1. **Real page checks and MCP stdio.** Run the repository's
   `tests/test_check_page_local.py` and `tests/test_checks.py`. Expect all seven
   new cases to execute without skips: clean load, console error, image 404,
   script 404, slow navigation, unreachable localhost, and official MCP SDK
   initialization/list/call. Adjacent checks must also pass. Risks: browser
   launch skips, SDK worker-thread exceptions, timeout flakes, and leaked
   browsers/servers. Use installed headless Chrome, generated localhost pages
   on OS-assigned ports, repository fixtures, and private temporary profiles.
   The unreachable-address case uses localhost port 9 but binds no server there.
   Exit after focused results and owned-process cleanup; 180-second command cap.
   `--confcutdir=tests` excludes the root conftest's automatic ledger writes;
   tests/conftest.py only redirects the replay cache to temporary storage.
2. **#78 saved DEV extract.** Parse only
   `docs/results/nav_reader_20261114_post.jsonl`. Expect 54 object wrappers,
   required metadata keys and object rows, batch counts 14/14/14/12 for
   dev3_off/dev3_always/dev3_suspect/dev4_always, revision `3e53020`, and
   lowercase 64-hex source hashes. Check source/hash consistency and DEV labels
   without opening source files or printing per-task claims. Exit on assertions;
   this validates structure/provenance format, not raw-source hash equality.
3. **Integration boundaries and historical docs.** Check pinned refs, local
   merge deltas, docs-only scope for #45/#67/#78 and unchanged runtime versus
   baseline. Add 16-Nov historical annotations for #45 and #67, preserving
   original content. Run `git diff --check`. Exit with exact merge/annotation
   commits and clear distinction between regression coverage and accuracy gains.

## Results

### Commits and merge boundaries

| Candidate | Pinned GitHub ref/head | Local merge commit | Actual first-parent merge delta |
|---|---|---|---|
| #46 | `github/t3/mcp-check-page` / `e23b4b9a1bc19327403f3e7f528d242d50894fc1` | `b09f9162494c2f63cfb4a431f108cd8361cff228` | `loop/README.md`, `tests/test_check_page_local.py` |
| #45 | `github/t3/failure-taxonomy` / `fb4d7358fa8c45fc356daa2e4a0114cc8cf0703b` | `dfcebd21de794c90532dfd92d444f1bd3f1ed3d6` | `docs/FAILURE_TAXONOMY.md` |
| #67 | `github/t3/arch-research` / `3bc3c4a7c174ec7016a9b2f1a51cb8adbc8f3da2` | `bf078fafb51d4e49a260aa22b324800374ac2cd9` | `docs/ARCHITECTURE_RESEARCH.md` |
| #78 | `github/t3/strategy-nav` / `ea474cfff81897ccbcee15e3cf64c536fdd93e76` | `fd2bc84729716b9d4ae493c0a88f7086d70b05df` | `docs/STRATEGY_NAV.md`, `docs/results/nav_reader_20261114_post.jsonl` |

Each merge used `git merge --no-ff --no-edit <full pinned SHA>`, in the table's
order. All used the existing prepared checkout and local Git objects; no fetch,
new checkout, conflict resolution or branch deletion was needed. #45 also
carries its historical predecessor `5dad8ef`; the resulting document is the
later real-log taxonomy, not the superseded “no logs” note.

Annotation commit: `d0836d32f36a078876838764c0d36b3b8aee665b`
(`Mark imported failure taxonomy and architecture research as historical`).
It adds only 20 lines in the two documents. Validation confirmed their original
bodies are preserved after removing the added quote blocks.

The six paths in the table are the **entire tracked delta** from PR82 to final
HEAD. `loop/checks.py`, `loop/mcp_server.py`, `loop/browser.py` and
`tests/test_checks.py` retain their baseline Git blob IDs. There is no runtime,
grader, prompt, dependency or test-implementation change made by this task.
`git diff --check d4f9d03abe278ebad44d1391cc67b4d3b83b8005 HEAD` passed.
Evidence: [boundary validation][capture004], [checkpoint 004][checkpoint004].

### Exact focused test run

Working directory was the owned worktree above. Installed environment:
Windows; Python **3.14.5**; pytest **9.2.0**; Playwright **1.64.1**;
MCP **2.3.0**; AnyIO **4.16.0**; Chrome **157.0.8103.51** at
`C:/Program Files/Google/Chrome/Application/chrome.exe`. No installation ran.

```powershell
$env:DEBUG='pw:browser'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& C:/Users/epicd/AppData/Roaming/npm/node_modules/bun/bin/bun.exe C:/Users/epicd/.claude/skills/gstack/bin/gstack-qa-evidence capture docs/PR_INTEGRATION_20261116 001 --public --timeout-ms 180000 -- python -m pytest -vv -ra -s --confcutdir=tests -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning --junitxml=docs/PR_INTEGRATION_20261116/check_page_local.xml tests/test_check_page_local.py tests/test_checks.py
```

The child pytest command is recorded verbatim in [capture 001][capture001].
`--confcutdir=tests` deliberately excludes root `conftest.py`, whose autouse
fixtures create spend-ledger files even for these unrelated tests.
`tests/conftest.py` remains active and redirects only the replay-cache path.
External pytest plugin autoload and pytest cache writes were disabled.
Unhandled test worker exceptions were promoted to errors.

Run HEAD was `fd2bc84729716b9d4ae493c0a88f7086d70b05df`, with the two historical
annotation edits and initial report present. No tested input subsequently
changed: final HEAD commits those same annotations. The focused suite ran once;
there was no baseline-suite run and no unnecessary full-suite run.

Observed stdout: **`19 passed in 38.75s`**, exit **0**, no warnings reported.
[JUnit][junit] independently records 19 tests, 0 failures, 0 errors, 0 skipped.
The wrapper's measured command span was 42.673 s; its 180 s cap was not reached.
These are test-run durations, not agent performance measurements.

All seven new node IDs executed:

```text
tests/test_check_page_local.py::test_clean_page_passes
tests/test_check_page_local.py::test_console_error_fails
tests/test_check_page_local.py::test_404_asset_fails[img404.html-missing.png]
tests/test_check_page_local.py::test_404_asset_fails[script404.html-missing.js]
tests/test_check_page_local.py::test_slow_url_fails_within_the_navigation_timeout
tests/test_check_page_local.py::test_unreachable_url_fails_fast
tests/test_check_page_local.py::test_real_mcp_client_calls_check_page
```

All twelve existing adjacent cases also passed:

```text
tests/test_checks.py::test_check_module_does_not_reference_the_planner
tests/test_checks.py::test_resolve_localhost_adds_http
tests/test_checks.py::test_tool_descriptions_state_start_and_end
tests/test_checks.py::test_check_page_pass_fail_console_and_failed_requests
tests/test_checks.py::test_http_404_asset_fails_without_a_model
tests/test_checks.py::test_save_then_replay_makes_no_model_call
tests/test_checks.py::test_mcp_tool_check_page_reports_the_fixture
tests/test_checks.py::test_run_loop_fake_planner_reaches_done_without_a_model
tests/test_checks.py::test_stdio_check_page_does_not_open_a_browser
tests/test_checks.py::test_content_length_ping
tests/test_checks.py::test_run_saved_test_rejects_paths_outside_the_repo
tests/test_checks.py::test_cli_replay_committed_spec
```

This is real browser/protocol integration evidence, not mocked browser coverage.
[Playwright stderr][stderr001] shows Chrome's actual executable, `--headless`,
private profile directories and graceful exit. The MCP case spawns
`python -m loop.mcp_server`, initializes the official SDK client, lists tools,
then checks clean, console-error and slow localhost pages. It asserts clean
success, error diagnostics and MCP `is_error` for the timeout, with zero model
calls where asserted. The existing fake-planner case is explicitly synthetic.

### #78 DEV evidence validation

[Capture 002][capture002] retains the exact inline Python validator and output.
Only `docs/results/nav_reader_20261114_post.jsonl` was parsed; source files were
not opened. Passed assertions:

- Exactly **54** valid JSON object wrappers.
- Exact wrapper keys: `source`, `source_sha256`, `revision`, `batch_label`, `row`.
- Every `row` is a nonempty object; two row-key shapes are present.
- Batch counts: `dev3_off=14`, `dev3_always=14`, `dev3_suspect=14`,
  `dev4_always=12`.
- Every revision is exactly **`3e53020`**.
- Each source is a `.jsonl` string; none names heldout3, heldout4 or val3.
- Every source hash is lowercase 64-hex; one consistent hash per source;
  exactly four distinct sources/hashes, one source per batch.
- `3e53020b7d11d0ccf966876d4cdc212be57d9012` is already an ancestor of PR82.
  Thus #78 introduces no new runtime implementation in this integration.

SHA-256 of the inspected worktree extract bytes:
`695faf2e01619232c99bbb302e1d9f1a428e09fb9b17aa231b14fcf224dd341d`.
This fingerprints this local extract, not the uninspected raw sources.
No source-hash equality against raw files, metric recomputation, answer review
or new accuracy claim was attempted. Metadata/shape checks do not establish
scientific reproducibility or present-day usefulness of the reader.

### Historical documentation

- **#45:** the dated annotation labels the 10-Nov tuned/DEV experiment, the
  local Stagehand emulator, later format parity/oracle/timing cleanup, and the
  limits on interpreting old failure counts. Its seven historical failures
  were not independently recounted here; that is attributed to the supplied
  `other_candidates.md` audit.
- **#67:** the dated annotation distinguishes the 13-Nov research from the
  active implementation, labels estimates/causal claims as hypotheses, notes
  that old aggregate/vendor claims were not revalidated, clarifies the
  emulator versus real Stagehand, and rejects interpreting old “dev or val”
  wording as permission to tune on protected sets.
- **#78:** imported the evidence-only remainder and its existing limitations.
  The specialist ledger figure in that document is historical text, not a
  reconciled current project balance.

No research links or public sites were fetched. Only expressly DEV saved
evidence was parsed for this task; the pre-fix mixed-set extract was not opened.
AGENTS.md, docs/HISTORY.md, NOTES.md and the shared audit's other_candidates.md,
README.md and inventory.md were read before integration/testing.

### Cleanup

Both HTTP fixtures bind `127.0.0.1:0` (OS-assigned ports) and call shutdown and
server_close in `finally`. No fixed-port server or shared Chrome profile is
used. The unreachable-address test targets `127.0.0.1:9` without binding it.
The subprocess and pytest exits confirm the in-process HTTP fixture lifetimes
ended; the numeric ephemeral HTTP ports were not separately logged.

[Capture 007][capture007] verified:

- Logged Chrome PIDs **68440** and **139916** are gone.
- Both logged temporary Chrome profile directories are gone.
- There are **zero** running `python -m loop.mcp_server` processes.
- No unrelated process was terminated.

The SDK stdio subprocess and CLI replay subprocess completed within their
existing deadlines. Their child Chrome PIDs were not separately exposed in
the parent debug log. Browser cleanup was not proven by a machine-wide
before/after Chrome inventory; unrelated Chrome sessions were preserved.
Pytest-managed synthetic temporary files were left to pytest's normal retention.
Report/evidence artifacts are intentionally retained in this directory.

### Failures and caveats

**No product test failed or skipped.** The following evidence-tool failures
are preserved rather than hidden:

1. The first invocation through the installed `bun.ps1` shim returned a
   `QA_EVIDENCE ... Usage` error before starting pytest. Direct `bun.exe`
   successfully launched the same requested child command in capture 001.
2. Capture **003** stopped with `UnicodeDecodeError` when Python decoded
   historical Git text using Windows cp1252. Capture **004** added explicit
   UTF-8 to that evidence-only inline command; all scope/body/diff assertions
   passed. No repository implementation was changed.
3. Capture **005** failed with `Get-CimInstance : Invalid query` after nested
   command-line quoting stripped its filter. Capture **006** replayed the
   already-stripped script through EncodedCommand and failed identically.
   Capture **007** used a freshly encoded script with a PowerShell name
   predicate; all cleanup assertions passed.

The evidence recorder aggregates historical `setup-blocked` captures without a
resolved-error state, so [evidence.json][evidence] reports **blocked**, with no
open items. The current targeted product checks, metadata validator, boundary
validator and cleanup check all pass. Raw stdout/stderr and exact argv for
every attempted captured command remain under `.qa-evidence/001`–`007`.

Further limits:

- Parent owns the final combined/full suite after parallel heavy work finishes.
- This establishes regression coverage and documentation completeness, not
  benchmark accuracy, speed improvement or generalisation.
- No protected heldout3/heldout4/val3 per-task rows, answers or scripts were
  opened. No live task-catalog verifier ran.
- No paid API, ledger edit, install, GitHub mutation, watch or delegation ran.
  Only local branch merges and the annotation commit were made.
- Test navigation targets were localhost/file fixtures. Chrome background
  traffic was not packet-captured; zero external network packets is not claimed.
- Skill startup/telemetry/sync and external learning stores were omitted to
  honor the offline, owned-worktree boundary.
- Total session elapsed: **unmeasured**. Sum of captured command spans:
  **51.054 s**, including failed evidence utilities; each non-test capture had
  a 30 s cap. This excludes earlier reads/merges and later report work.

### Evidence checkpoints and operational notes

- [Checkpoint 002][checkpoint002]: passing focused suite led to DEV metadata validation.
- [Checkpoint 003][checkpoint003]: valid DEV wrappers led to integration-boundary validation.
- [Checkpoint 004][checkpoint004]: retained UTF-8 decoding failure and correction.
- [Checkpoint 005][checkpoint005]: passing boundary check led to cleanup inspection.
- [Checkpoint 006][checkpoint006]: retained first CIM quoting failure and replay.
- [Checkpoint 007][checkpoint007]: retained repeated quoting failure and corrected cleanup.

Durable local notes for the parent: use the installed `bun.exe` rather than its
PowerShell shim for exact `--` forwarding; decode Git text explicitly as UTF-8
on Windows; encode a fresh PowerShell command before nested process transport.
For these two ledger-free modules, `--confcutdir=tests` avoids the root autouse
ledger fixtures. Do not generalize that flag to the full suite, which relies
on those isolation fixtures.

## Parent handoff

Recommend integrating **#46 for tested regression coverage**, **#78 for
documentation/DEV-provenance completeness**, and **#45/#67 with the historical
annotations in d0836d3**. No new implementation fix or extra test was authored.
No remote PR check/review state was queried or changed.

The local branch is ready at
**`d0836d32f36a078876838764c0d36b3b8aee665b`**. Tracked worktree is clean;
this report directory is intentionally **untracked local evidence**. The parent
can integrate the local branch and copy the report/evidence separately. Shared
integration files were never edited.

[capture001]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/.qa-evidence/001/receipt.json
[stderr001]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/.qa-evidence/001/stderr
[capture002]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/.qa-evidence/002/receipt.json
[capture004]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/.qa-evidence/004/receipt.json
[capture007]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/.qa-evidence/007/receipt.json
[junit]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/check_page_local.xml
[evidence]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/evidence.json
[checkpoint002]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/exploration-002.json
[checkpoint003]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/exploration-003.json
[checkpoint004]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/exploration-004.json
[checkpoint005]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/exploration-005.json
[checkpoint006]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/exploration-006.json
[checkpoint007]: C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-5f474339-592bd73799bffd6b/docs/PR_INTEGRATION_20261116/exploration-007.json
