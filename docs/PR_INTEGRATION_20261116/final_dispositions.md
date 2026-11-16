# Final per-PR dispositions — 16 November 2026

Baseline `t3/tip4` `b5b74b3`. Branch `t3/pr-integration-20261116`. All 73 PRs open on 16 Nov.
Machine-readable: `final_dispositions.json`. Ancestry detail: `inventory.md`.

| Disposition | Count |
|---|---:|
| merged (GitHub merge commit, exact head) | 7 |
| already contained (exact ancestor of tip4) | 51 |
| not merged (parked / superseded / duplicate / separate history / obsolete) | 15 |

Project accuracy is **not** shown to have improved. #81 is a correctness fix with no fresh accuracy measurement; #82 is opt-in, default off, and its partial DEV pilot is inconclusive. The other merges are docs, tests or records.

Open PRs were left open (no bulk close, no base changes) apart from #82, which was retargeted and merged.

## Merged

| PR | Kind | Merge commit | Performance | Reason |
|---:|---|---|---|---|
| #45 | docs | `a96bebd` | n/a | Historical failure taxonomy, dated annotation added. |
| #46 | tests+docs | `81a9f78` | n/a (regression coverage only) | Real Chrome + MCP stdio regression tests; 7 cases ran green. |
| #58 | records | `d1dc7bb` | n/a | Record-only remainder; tip2 runtime already in tip4. |
| #67 | docs | `a11d3a3` | n/a | Architecture research document, dated annotation added. |
| #78 | docs+DEV evidence | `d974319` | n/a (runtime 3e53020 already in tip4) | Nav strategy report and DEV jsonl; no runtime delta. |
| #81 | runtime correctness | `6dfaeab` | unmeasured accuracy; correctness fix | Title self-check false rejects and _clean_url bracket parsing, common to every arm; focused tests green. |
| #82 | runtime, opt-in (CU_SF_SEGMENTS, default off) | `888f7e2` | INCONCLUSIVE: partial DEV pilot 13/14 vs baseline 12/14 on matched tasks, FA 1->0, FR 0->1, ~1.23x settled cost/pass | Accepted experimental infrastructure with strong offline coverage; not promoted to default; not a proven accuracy win. |

## Not merged

| PR | Kind | Performance | Reason |
|---:|---|---|---|
| #2 | duplicate | n/a | Merge-only commit; its NOTES.md content is already a prefix of baseline notes. |
| #14 | obsolete workflow | n/a | Reinstates Grok/Cursor-era setup/sync/CI and a ledger seed; no runtime contribution. |
| #19 | separate site history | n/a | Progress-site history with no common ancestor; intent superseded by #51. |
| #20 | superseded runtime | n/a (reimplemented) | Returned-evidence functions reimplemented in #30 (contained). |
| #22 | superseded runtime | n/a (reimplemented) | Launch overlap and prompt caching redone in #29/#30 (contained). |
| #24 | superseded runtime | n/a (reimplemented) | Helper blobs identical to #30 (contained). |
| #37 | superseded docs | n/a | Stale failure taxonomy replaced by #45 (merged). |
| #40 | patch-equivalent | n/a | Whole patch already present as #42 257f8cb. |
| #43 | separate site history | n/a | Progress-site stats/assets; ancestor of #51; unrelated to tip4. |
| #49 | parked runtime | negative (historical acceptance gate failed) | Decisions second-opinion experiment failed its gate; keep off. |
| #51 | separate site history | n/a | Site/UI/data only; separate history; no browser-runtime change. |
| #74 | parked runtime | negative direction on DEV rep1 (15/24 vs 18/24, 0 wins, 3 losses); single repetition, not a regression claim | Observe-first page summary; not merged; no accuracy benefit to claim. |
| #76 | parked runtime | unmeasured (paired evidence never committed) | Search strategy; grounding/integration issues unresolved. |
| #77 | parked runtime | negative/unsafe (saved pair: +5 finals, +2 wrong accepts) | Executor bundle; hold. |
| #79 | parked runtime | negative (saved live 192 vs 200 passes, 19 vs 12 false accepts) | Verifier narrowing; parked. |

## Already contained (51)

#1, #3, #4, #5, #6, #7, #9, #10, #11, #12, #13, #15, #16, #17, #18, #21, #23, #25, #27, #28, #29, #30, #31, #32, #33, #34, #36, #38, #41, #42, #44, #47, #50, #52, #53, #54, #55, #56, #57, #59, #60, #62, #63, #66, #68, #69, #71, #72, #73, #75, #80.

#1 targets `main` and must never be merged. The others are exact ancestors of tip4 and need no action.
