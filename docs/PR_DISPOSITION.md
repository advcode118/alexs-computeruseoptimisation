# PR disposition: open PRs #45–#83

Written 17 Nov 2026, read-only: no PR was closed, merged, retargeted or commented on, and `main` was not touched. Containment was checked with `git merge-base --is-ancestor <PR head> origin/t3/pr-integration-20261116` and `git rev-list --count origin/t3/pr-integration-20261116..<PR head>` ("unique" below). Earlier per-PR record: `docs/PR_INTEGRATION_20261116/final_dispositions.md`.

Already merged (not open, no action): #45, #46, #48, #58, #61, #64, #65, #67, #70, #78, #81, #82.

## Table

| PR | Head (sha) | Disposition | Reason | Evidence |
|---:|---|---|---|---|
| #47 | `t3/tip` `9442722` | close-as-contained | Old consolidated tip; every commit is in the integration line. | ancestor = yes, unique = 0 |
| #49 | `t3/decisions-second-opinion` `6b59b52` | close-as-negative | Decisions second-opinion experiment failed its acceptance gate; kept off. | unique = 9 (`6b59b52` "Record six live runs…"); `final_dispositions.md` "Not merged" |
| #50 | `t3/runtime-plain-rules` `3cd5400` | close-as-contained | Plain runtime rules are in the tree. | ancestor = yes, unique = 0 |
| #51 | `t3/website-heldout-stats-update` `4546426` | close-as-unmeasured (separate history) | Site stats page on a branch with no common ancestor with `main` or the bench; publishes superseded 11 Nov numbers. | `git merge-base pr/51 origin/main` fails; unique = 29 |
| #52 | `t3/probe-trace` `439bcfc` | close-as-contained | Probe traces are in the tree. | ancestor = yes, unique = 0 |
| #53 | `t3/repair-delivery` `56d24cc` | close-as-contained | Repair delivery is in the tree. | ancestor = yes, unique = 0 |
| #54 | `t3/repair-links` `f8932c9` | close-as-contained | Trusted repair links are in the tree. | ancestor = yes, unique = 0 |
| #55 | `t3/script-grammar` `67e1bf6` | close-as-contained | Wider script grammar is in the tree. | ancestor = yes, unique = 0 |
| #56 | `t3/heldout2-tasks` `038848f` | close-as-contained | heldout2 tasks are in `bench/tasks.py`. | ancestor = yes, unique = 0 |
| #57 | `t3/repair-grammar` `0bb215a` | close-as-contained | Measurement branch, contained. | ancestor = yes, unique = 0 |
| #59 | `t3/heldout2-audit` `c365729` | close-as-contained | heldout2 audit is in `docs/HELDOUT2_VERIFY.md`. | ancestor = yes, unique = 0 |
| #60 | `t3/answer-required` `526a6b5` | close-as-contained | Empty-answer FAIL is in the tree. | ancestor = yes, unique = 0 |
| #62 | `t3/heldout3-b` `b7aeea3` | close-as-contained | `bench/tasks_heldout3_b.py`. | ancestor = yes, unique = 0 |
| #63 | `t3/heldout3-a` `abc4a52` | close-as-contained | `bench/tasks_heldout3_a.py`. | ancestor = yes, unique = 0 |
| #66 | `t3/val3-set` `c8c1eef` | close-as-contained | `bench/tasks_val3.py`. | ancestor = yes, unique = 0 |
| #68 | `t3/dev3-set` `fd57370` | close-as-contained | `bench/tasks_dev3.py`. | ancestor = yes, unique = 0 |
| #69 | `t3/grounded-repair` `aa76956` | close-as-contained | Grounded repair is in the tree (now capped at 1 repair). | ancestor = yes, unique = 0 |
| #71 | `t3/tip3` `b9ac977` | close-as-contained | Tip3 is an ancestor of tip4 and the integration branch. | ancestor = yes, unique = 0 |
| #72 | `t3/strategy-form` `441b0ea` | close-as-contained (then deleted) | FORM specialist: in the integration line, deleted on the slim branch; val3 gate showed no pass gain. | ancestor = yes, unique = 0; `docs/results/tip4_gate_20261114/README.md` (79/120 off vs 79/120 on, +3.4 s) |
| #73 | `t3/strategy-spa` `1dab4bb` | close-as-contained (then deleted) | SPA specialist: same as #72. | ancestor = yes, unique = 0; same gate |
| #74 | `t3/observe-first` `6927566` | close-as-negative | Observe-first lost 3/24 on the DEV pilot (15 vs 18) and adds a turn. | unique = 7; `docs/PR_INTEGRATION_20261116/pilot_20261116.md` table |
| #75 | `t3/verifier-false-reject-audit` `94b8bcd` | close-as-contained | Independent recall labels are in the tree. | ancestor = yes, unique = 0 |
| #76 | `t3/strategy-search` `9c6f391` | close-as-unmeasured | Search specialist; paired evidence never committed; conflicts in harness/probe/tasks/openai_run. | unique = 3; `final_dispositions.md`; `pr-branch-audit.md` merge-tree preview |
| #77 | `t3/robust-executor` `74f434e` | close-as-negative | Executor added +2 false accepts on the saved pair. | unique = 7 (`74f434e` "…hold integration on false accepts") |
| #79 | `t3/verifier-recall` `9729d85` | close-as-negative | Narrowed verifier: 192 vs 200 passes, 19 vs 12 false accepts; opposite of the precision-first self-check the cascade needs. | unique = 3; `final_dispositions.md` |
| #80 | `t3/tip4` `b5b74b3` | close-as-contained | Tip4 is an ancestor of the integration branch. | ancestor = yes, unique = 0 |
| #83 | `t3/pr-integration-20261116` `4d9094a` | merge (as part of the stack below) | The single superset line; base of the grader and slim branches. | head of the line #84 and the slim PR stack on |

Totals: 1 merge (#83, via the stack), 20 close-as-contained, 4 close-as-negative (#49, #74, #77, #79), 2 close-as-unmeasured (#51, #76).

## Sequence that lands one slim branch on `main`

Every step needs Alex's go; none has been done.

1. Review and approve the slim PR (this branch → `devin/1794871306-frozen-grader`) and #84 (grader → `t3/pr-integration-20261116`).
2. Merge the slim PR into the grader branch, then merge #84 into `t3/pr-integration-20261116`. Re-run the offline suite on the result (`pytest -q bench/test_harness.py tests`) and `python tools/regrade.py --out /tmp/rg` (pass counts must match `docs/results/regrade_20261116/report.md`).
3. Close the PRs in the table above with a one-line comment linking this file: close-as-negative and close-as-unmeasured first, then the close-as-contained ones. Close #83 after step 4 (its content goes to `main` through the new PR).
4. `main` holds only the Next.js site and shares history with the bench line (merge-base `573e0c5`). Open ONE PR `t3/pr-integration-20261116` → `main`. Today that diff adds files only, except: it deletes `.github/readme/hero.svg` and `how-it-runs.svg` and modifies `.gitignore`, `AGENTS.md` and `README.md`; `app/` and `data/` are untouched. Restore the two SVGs and the site parts of `README.md` before merging, keep the Next.js agent block in `AGENTS.md`, and check `npm run build` still passes.
5. Merge with a merge commit (no squash: the specialist history must stay reachable for the docs that point at it). Do not delete any branch.
6. Re-point `AGENTS.md` at `main` as the tip in a follow-up PR.
