# Merged into `t3/pr-integration-20261116` — 16 November 2026

Base `t3/tip4` `b5b74b3`. Audit commit `5dfea8e`. All merges are GitHub merge
commits at the exact pinned head (`gh pr merge --merge --match-head-commit`).
Source branches preserved. These merge operations do not include the separately
approved ledger reconciliation and paid pilot; see `pr-integration-budget-smoke.md`.
No merge to `main`, force-push or branch deletion.

| PR | Head | Merge commit | Class | Delta |
|---|---|---|---|---|
| #46 | `e23b4b9a1bc19327403f3e7f528d242d50894fc1` | `81a9f780f92fc7856c4e93ef1730de07727dc0cf` | useful: real Chrome + MCP stdio regression tests | `tests/test_check_page_local.py`, `loop/README.md` |
| #45 | `fb4d7358fa8c45fc356daa2e4a0114cc8cf0703b` | `a96bebddb6d5a44d815946acf9db10d69be270b3` | docs-only, historical | `docs/FAILURE_TAXONOMY.md` |
| #67 | `3bc3c4a7c174ec7016a9b2f1a51cb8adbc8f3da2` | `a11d3a38f29920c600c950841a503c2033e5dce3` | docs-only, research | `docs/ARCHITECTURE_RESEARCH.md` |
| #78 | `ea474cfff81897ccbcee15e3cf64c536fdd93e76` | `d974319e44071298dd34b1ceb2c03f7cde85899a` | docs/DEV evidence only; runtime `3e53020` already in tip4 | `docs/STRATEGY_NAV.md`, `docs/results/nav_reader_20261114_post.jsonl` |
| — | annotation `d0836d3` (cherry-picked `-x`) | `2146779` | dated historical notes on #45/#67 | +20 lines, 2 docs |
| #81 | `69357dde5265fe3c37704b45b8af3f4f606ac422` | `6dfaeab29338025938f839fed1f9699461692554` | runtime correctness fix (title self-check false rejects, `_clean_url` brackets for all arms); no fresh accuracy gain shown | `bench/{harness,probe,script_first,tasks,tasks_dev5_title,verify_dev5_title}.py`, 3 tests |
| #58 | `aad3077cc501a4efb91fc18630000070830b90d8` | `d1dc7bbeb33f5b81d08e3d32801c163349c887b9` | record-only remainder; tip2 runtime already in tip4 | run-plan deviations, manifest additions and historical subset wrapper |
| #82 | `d4f9d03abe278ebad44d1391cc67b4d3b83b8005` | `888f7e245f327b008546f0733b80240a7be359f1` | opt-in runtime (`CU_SF_SEGMENTS`, default off); accuracy inconclusive | `bench/segments.py`, harness/script_first hooks, tests |

Not merged: #79 stays PARKED (saved live 192/240 vs 200/240, false accepts 19
vs 12). The isolated child heads `d0836d3` (contains PR82) and `67db53d`
(contains #79) were not merged whole. #74 PARKED after the DEV pilot (not
merged; private head `deac8e1` not merged). #82 merged opt-in on 16 Nov after
the pilot; see `final_dispositions.md`.

## Focused checks on this tip4-based tree (not PR82)

Windows, Python 3.14.5, Chrome 157. No full suite (parent owns it).

1. `python -m pytest -q -p no:cacheprovider --confcutdir=tests -W error::pytest.PytestUnhandledThreadExceptionWarning tests/test_check_page_local.py tests/test_checks.py`
   - First run, after #78 and before #81, under parallel machine load:
     **18 passed, 1 failed**. The failure was `test_cli_replay_committed_spec`,
     wall-time bound `elapsed < 3` (7.02 s). The test and `loop/` code are
     unchanged since `67bc4ed`. Rerun alone: passed.
   - Final tree `6dfaeab`: **19 passed** in 25.8 s. All seven #46 cases ran.
2. #81 selection: T (`test_selfcheck_precision`, `test_verifier_false_rejects`,
   `test_selfcheck_replay`, `test_runtime_plain_rules`, `test_evidence_judge`,
   `test_grade`, `test_prompt_audit`,
   `test_script_cache.py::test_the_live_run_never_reads_the_answer_key`) plus
   `tests/test_strategy_review_regressions.py tests/test_dev5_title.py`:
   **108 passed** in 68.9 s, with the root conftest's ledger isolation active.
3. `docs/PR_INTEGRATION_20261116/test_title_boundaries.py` (the #81 child's
   synthetic URL bracket, runtime spacing and title boundaries):
   **7 passed**.
4. #78 extract validator: 54 wrappers, batches dev3_off 14 / dev3_always 14 /
   dev3_suspect 14 / dev4_always 12, revision `3e53020`, 4 sources with one
   consistent lowercase 64-hex hash each, no protected-set source names.
   SHA-256 `695faf2e01619232c99bbb302e1d9f1a428e09fb9b17aa231b14fcf224dd341d`,
   the same as the isolated run. `3e53020` is an ancestor of HEAD.
5. `git diff --check b5b74b3 HEAD`: clean.

These checks show regression coverage and correctness. They do not show an
accuracy or speed gain. For later paid comparisons, keep #81's corrected URL
parser common to every arm. Do not soften the grade.

#58 was separately confirmed to contain only the three expected record paths
after retargeting, with no runtime delta, no conflicts and no configured checks.
Its historical subset wrapper was not executed and protected per-task results
were not opened. GitHub reports the exact pinned head merged on 16 Nov 2026.

Isolated reports: `test_maintenance_isolated.md` (PR82 base, 19 passed) and
`test_verifier_title_isolated.md` (#81 alone, 114 passed). Their evidence
links point into the child worktrees.
