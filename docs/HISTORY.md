# Project history: Cursor Origin PRs #6–#20 and the move to T3 Code

This is the full record of what was built before the move to T3 Code. Read it with `NOTES.md` (on `t3/onboarding-notes`, GitHub PR #2) before you change anything.

Until 9 Nov 2026 the work lived in Cursor Origin (`tom-wei-de-vrieze/alexs-computeruseoptimisation`) and was written by Cursor cloud agents. From 9 Nov 2026, coding runs in T3 Code threads on Tom's PC, and the code lives on GitHub (`advcode118/alexs-computeruseoptimisation`). Origin PRs #6–#20 are open and unmerged. They are the project history. Nothing in the new work depends on Origin or on Cursor cloud agents.

All numbers below come from the PR descriptions or from the saved probe logs (`bench/runs/probe_*.jsonl` and `bench/results/spend.json` from each probed tip). Nothing here is estimated.

## Goal

Make computer use faster than the competition. The bar is Stagehand-class wall time per successful task, with a success rate no more than about 2 points below the stronger baseline. Tom's own approach is **script_first**: the model writes one Playwright script for the whole task, the harness runs it, and the end state is judged. Plain Playwright MCP (many small tool calls) and Stagehand are the baselines.

## Hard rules (still in force)

- Claude API calls in code and probes use `claude-sonnet-5-5` only. Never `claude-sonnet-4-6`. Never Opus or Fable through the API.
- Total Claude API spend cap is **$50**. Spend so far is **$16.639436** (`running_total_usd` after the PR #18 probe). The ledger prices tokens at $3/$15 per million and is never reset or repriced. Each three-arm probe stops at $2 of Claude. The code's own project abort is $40.
- No live probe and no Claude API call without Tom saying go. Offline tests are always fine.
- Never merge to `main` (on Origin or GitHub). Never force-push. Never delete branches.
- Report per-task wall time **and** step counts, not just the mean. A faster mean with 2-step scripts is not a win.

## Agent and model rules in T3 Code

- Implementation (code, tests, harness, plumbing): Cursor provider, model `grok-4.7`, reasoning effort high, fast mode off. The T3 project default is set to exactly that, so `t3 thread start` without `--provider/--model` gets it. Do not pass `--model grok-4.7-high`; Cursor rejects that slug.
- Design and review (judge design, replay/patch design, reviewing diffs for judge-softening or benchmark-gaming): Claude Opus 5.5 or Fable 5.2 at medium effort, through Claude Code on Tom's subscription. **Off until Tom says his Claude limit has reset.**
- One task per branch and worktree. Small draft PRs on GitHub. Push often.

## Before the stack: Origin PRs #1–#5 (merged into Origin `main`, ce4430a)

| PR | Title | Branch |
| --- | --- | --- |
| [#1](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/1) | Add a dark-mode progress site | `cursor/progress-site-2be8` |
| [#2](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/2) | Add a testable browser computer-use loop | `cursor/browser-loop-a4d6` |
| [#3](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/3) | Route browser cycles through direct, fast, and Claude tiers | `cursor/step5-router-3081` |
| [#4](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/4) | Click a unique HTML control before calling a model | `cursor/step5-router-3081` |
| [#5](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/5) | Keep a later section open after a direct click | `cursor/step5-router-3081` |

These built the local observe/decide/act loop (`loop/`) and its no-model shortcuts. Origin `main` is preserved on GitHub as `origin-archive/main` because GitHub `main` has a different history (the README and site work).

## The stack: Origin PRs #6–#20

Each PR is stacked on the one before it, except #19, which is based on `main`. #6 is based on `cursor/mcp-page-check-308a`. None has human review comments. The only comments are Vercel preview bots.

### #6 Benchmark harness (Milestone 0)
[Origin #6](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/6) · `cursor/bench-measurement-fcdc` · open

Added `bench/`: `harness.py` drives tasks through `@playwright/mcp` (pinned 0.0.84) and splits wall time into model, tool, and other. It added 12 tasks (2 local fixtures, 10 WebVoyager-style public sites), a judge (URL contains, text present, title, plus an LLM judge), offline shortcut replay, and a summary report. 30 offline tests.

Outcome: the M0 measurement recorded later in the ledger. 4/5 tasks succeeded, 36 steps, 94.8s, model time 87% and tools 13%, 3.2M input tokens against 3k output. It stopped after 5 of 12 tasks and cost $9.645 at the ledger rate. Lesson: model time dominates, and the context was mostly page snapshots.

### #7 Move no-model routing into decide() and add UI backends
[Origin #7](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/7) · `cursor/decide-backend-refind-52f8` · open

Moved the no-model route into `loop/decide.py`. Added `core/backend.py` as the UI contract (observe/act/settle/refind), the Playwright MCP backend (parses 0.0.84 ARIA snapshots), and refind of stale refs by exact role and name. 91 tests passed. No probe.

### #8 Fix the bench harness before another measured run
[Origin #8](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/8) · `cursor/bench-harness-fixes-e44e` · open

Newline-delimited JSON for Playwright MCP 0.0.84, context capped to the opening task plus the last 6 turns, tool results capped at 8000 characters. Added the spend ledger `bench/results/spend.json` with the M0 prior ($9.645), and a $40 project abort. Opus refused before any HTTP call. No new run.

### #9 Forward Playwright MCP unchanged through a stdio proxy
[Origin #9](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/9) · `cursor/playwright-mcp-proxy-263e` · open

`playwright-mcp-proxy` (Python, official `mcp` SDK) in front of `@playwright/mcp@0.0.84 --snapshot-mode none`, forwarding every tool unchanged. Start of the MCP proxy speed layer. 102 tests. No probe.

### #10 Add fast_act and do_task_segment to the proxy
[Origin #10](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/10) · `cursor/fast-act-task-segment-56f9` · open

Two macro tools. `fast_act` runs one `decide()` action batch with no model. `do_task_segment` runs a caller-supplied sub-task through no-model actions and then the cheap Nebius tier (never Claude). 99 tests with mocks. No probe.

### #11 Replay a learned do_task_segment sequence with no model call
[Origin #11](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/11) · `cursor/replay-cache-a194` · open

A sqlite replay cache keyed by domain, task text, and page shape (roles and names). A hit replays by refinding each target. Any miss falls back. 109 tests. No probe.

### #12 Return a settled page diff after each browser action
[Origin #12](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/12) · `cursor/settle-diff-f4f0` · open

After each action the proxy waits for the DOM to go quiet (100ms, 1500ms cap) and returns a compact diff instead of a full snapshot. On a 16-section fixture, the full snapshot is 28,302 characters and the diff is 95. 129 tests. No probe.

### #13 Wait 500ms, soften replay, and add a Stagehand arm
[Origin #13](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/13) · `cursor/live-readiness-stagehand-f676` · open

Settle quiet window raised to 500ms (3000ms cap). Replay key softened to domain + normalized task + sorted role/name set. Added a Playwright-style script path on `fast_act`/`do_task_segment`, a local Stagehand arm (`snapshot`, `run`, `screenshot`), the `model_ignores_tools` counter, and `bench/probe.py`: 3 tasks (`wv_wikipedia_search`, `wv_python_docs`, `wv_hackernews_top`) × 4 arms (`playwright_mcp`, `diff_fast_act`, `macro_replay`, `stagehand`). 142 tests. The PR itself noted that the mechanism that closed the Stagehand gap in a LangChain write-up was an outer model writing one Playwright script, the seed of script_first.

First box probe on this tip (5 Nov, run `probe_20261105_163744`): playwright_mcp 1/3, 417.5s, $1.3122, 63 steps. stagehand 1/3, 33.5s, $0.0974. diff_fast_act 0/3 and macro_replay 0/3 at $0 (no-model path only). The arms collided on a shared Chrome profile lock. Ledger after: $11.054514.

### #14 Measure proxy arms with outer Claude on isolated browsers
[Origin #14](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/14) · `cursor/outer-claude-proxy-arms-8495` · open

Every arm now driven by an outer Claude, with each arm on its own browser profile. 146 tests.

Box probes on this tip (5 Nov). The first run (`probe_20261105_170425`) mostly failed (playwright_mcp 1/3, diff_fast_act 0/3, macro_replay 1/3, stagehand 1/3). The second run (`probe_20261105_171010`), totals over 3 tasks:

| Arm | Success | Wall | s/success | USD | Steps |
| --- | --- | --- | --- | --- | --- |
| playwright_mcp | 3/3 | 28.6s | 9.5 | 0.287 | 10 |
| diff_fast_act | 3/3 | 50.0s | 16.7 | 0.271 | 8 |
| macro_replay | 3/3 | 76.5s | 25.5 | 0.553 | 19 (0 replay hits) |
| stagehand | 1/3 | 31.2s | — | 0.085 | 7 |

Ledger after: $12.912192. The proxy was not faster than plain MCP.

### #15 Fix box scoring and shorten idle settles
[Origin #15](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/15) · `cursor/proxy-box-speed-9b3e` · open

Fixed box issues (the `--isolated` flag, Stagehand's `context.browser`, the huge-page skip, URL parsing for Stagehand). Added adaptive settle (80–100ms on quiet short pages), a cap on macro thrash, and `--warm-replay`. 153 tests.

Cold probe on this tip (`probe_20261105_174317`), totals over 3 tasks:

| Arm | Success | Wall | USD | Steps |
| --- | --- | --- | --- | --- |
| playwright_mcp | 3/3 | 44.15s | 0.287 | 10 |
| diff_fast_act | 3/3 | 89.73s | 0.682 | 25 (HN alone 19) |
| macro_replay | 3/3 | 58.64s | 0.354 | 12 |
| stagehand | 1/3 | 31.74s | 0.080 | 6 |

Ledger after: $15.810525.

**Design stop.** The proxy arms were slower than plain Playwright MCP and not competitive with Stagehand. The likely reason is that these tools did not remove the outer model's round-trips, and model time is most of the wall time (87% in M0). The proxy (`proxy/`) is parked. Don't extend it.

### #16 Add script_first and pin Sonnet 5.5
[Origin #16](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/16) · `cursor/script-first-arm-7aa7` · open

**The pivot.** The outer model for every arm became `claude-sonnet-5-5` (`claude-sonnet-4-6` is refused). Added the `script_first` arm: the model writes one short Playwright script (goto, four locator kinds, `page.evaluate`), and the harness runs it on a private Chrome profile through the Playwright Python API. `--arms` selects the matrix, and the script_first run stops at $2. 162 tests.

Probe on this tip (`probe_20261106_003637`), per task as wall time and steps (Wikipedia / Python docs / HN):

- playwright_mcp 3/3: 5.43s 4 steps / 2.38s 1 / 3.49s 3. That is 3.8s per success, $0.150.
- script_first 1/3: wiki failed (6.26s, 3 steps, stayed on Main_Page) / docs passed (4.09s, 2) / HN failed (4.41s, 3, hit max steps). $0.031.
- stagehand 2/3: wiki failed (6.72s, 5) / docs 3.61s 2 / HN 1.48s 1. $0.053.

Ledger after: $16.043527.

### #17 Repair script_first misses and Stagehand's live URL
[Origin #17](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/17) · `cursor/script-first-repair-d535` · open

Added one `END_STATE_FAILED` repair script when the URL check fails. Model turns start at 4, cap at 6. Stagehand now reports the live page URL. 170 tests.

Probe on this tip (`probe_20261106_010041`):

- playwright_mcp 3/3 at 3.06s per success ($0.167). Steps 1 / 1 / 3.
- script_first 3/3 at 4.56s ($0.042). Steps 2 / 1 / 2: the repair fired on wiki and HN.
- stagehand 3/3 at 15.52s ($0.103). Wiki alone took 40.93s and 6 steps.

Ledger after: $16.352561. This is the last tip on the `cursor/origin-stack-sync` branch (GitHub PR #1).

### #18 Finish script_first on the first script
[Origin #18](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/18) · `cursor/script-first-oneshot-6a7f` · open

The prompt asks for one `page.goto` of the finished URL, and gives the Wikipedia article URL form, the Python docs module URL form, and the HN `.titleline a` read. Waits are dropped, and goto waits for DOMContentLoaded only. A matching URL ends the task. 174 tests.

Probe on this tip (`probe_20261106_012210`), per task (Wikipedia / Python docs / HN):

| Arm | Wikipedia | Python docs | HN | Mean | USD |
| --- | --- | --- | --- | --- | --- |
| playwright_mcp | 3.36s, 1 step | 2.55s, 1 step | 3.03s, 2 steps | 2.98s | 0.165 |
| script_first | 2.94s, 2 steps | 3.44s, 2 steps | 4.62s, 2 steps | 3.67s | 0.047 |
| stagehand | 8.74s, 4 steps | 3.56s, 2 steps | 1.55s, 1 step | 4.62s | 0.074 |

All 3/3. The bar (script_first at or under about 3.1s at 3/3, with 1-step scripts) was **not cleared**. Every script_first task still took 2 steps: the end-state check rejected a first script that was actually right and asked for a repair (the "false-repair tax", about 0.7s). Ledger after: **$16.639436**, the current total.

### #19 Redesign the progress site
[Origin #19](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/19) · `cursor/progress-site-redesign-8676` · open, based on `main`

Redesigned the Next.js progress site (`app/`, `data/progress.ts`) around script_first ("Alex's browser tool"): pitch numbers from the PR #18 probe, how it works, a step-through demo, probe charts, history, and background. script_first has the signature colour, and the baselines are muted. The header and footer link to GitHub **and Cursor Origin**. The live site is https://computer-use-optimisation.vercel.app.

### #20 Stop script_first when the first page is already done
[Origin #20](https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation/pull/20) · `cursor/script-first-landed-stop-e906` · open, **never probed**

Tried to remove the false-repair tax. It adds a 0.8s `wait_for_url` after a click or Enter, reports percent-encoded wiki paths and `title=` parameters as the literal token, counts a title match only when the URL is not already another `/wiki/` article, and ends HN once text is present. 178 tests. This tip was copied to GitHub as `t3/base` (a5a4224).

**Audit finding (onboarding thread, `NOTES.md`).** #20 softens the judge rather than making script_first faster. It rewrites the scored URL into the form the judge expects, so the stop-check and the final judge share one synthesized value. It passes HN on any text at all. And the prompt contains the answers to the three probe tasks. A pass on this tip would not count as a real win, so it was not probed.

## After the move: T3 Code work on GitHub

| GitHub branch | PR | What |
| --- | --- | --- |
| `t3/base` | — | #20 tip as one commit (a5a4224), plus this file |
| `t3/onboarding-notes` | [#2](https://github.com/advcode118/alexs-computeruseoptimisation/pull/2) | `NOTES.md`: script_first flow, the #20 audit, step 2 plan |
| `t3/step2-evidence-judge` | [#3](https://github.com/advcode118/alexs-computeruseoptimisation/pull/3) (draft) | Roadmap step 2: evidence-based judge (PASS/FAIL/UNKNOWN from the live page, judge-only task markers, no answers in prompts, 5 held-out tasks, one shared spend ledger via `CU_SPEND_LEDGER`). 185 passed, 1 skipped. Not probed. |
| `t3/step3-cached-script` | [#4](https://github.com/advcode118/alexs-computeruseoptimisation/pull/4) (draft) | Roadmap step 3: cached-script tier with replay and a one-turn patch, stacked on #3. Offline only. |

Roadmap from here: (1) probe the step 2 judge (about $2, on Tom's go), (2) evidence-based judge, (3) cached-script tier, (4) an endpoint tier for repeated reads, reported as its own arm, (5) desktop, using Microsoft HCU's router design: code/CLI first, then the accessibility tree, then GUI.

## Origin PR → GitHub branch mapping

Every Origin PR head below is on GitHub under the same branch name, at the same commit as Origin (checked against Origin on 10 Nov 2026).

| Origin PR | Branch | Head |
| --- | --- | --- |
| (#6 base) | `cursor/mcp-page-check-308a` | 2cd9ac6 |
| #6 | `cursor/bench-measurement-fcdc` | 5b0e5c3 |
| #7 | `cursor/decide-backend-refind-52f8` | f2dde93 |
| #8 | `cursor/bench-harness-fixes-e44e` | e9badd8 |
| #9 | `cursor/playwright-mcp-proxy-263e` | 7f636a3 |
| #10 | `cursor/fast-act-task-segment-56f9` | d1d7d6e |
| #11 | `cursor/replay-cache-a194` | 8f1e2c3 |
| #12 | `cursor/settle-diff-f4f0` | 15b4ff7 |
| #13 | `cursor/live-readiness-stagehand-f676` | 3a20a0a |
| #14 | `cursor/outer-claude-proxy-arms-8495` | 975583f |
| #15 | `cursor/proxy-box-speed-9b3e` | 73d518e |
| #16 | `cursor/script-first-arm-7aa7` | deef615 |
| #17 | `cursor/script-first-repair-d535` | bf52d79 |
| #18 | `cursor/script-first-oneshot-6a7f` | f771b53 |
| #19 | `cursor/progress-site-redesign-8676` | 1ff4d1d |
| #20 | `cursor/script-first-landed-stop-e906` | 4acc517 |
| #1–#5 (merged) | `cursor/progress-site-2be8`, `cursor/browser-loop-a4d6`, `cursor/step5-router-3081` | on GitHub at the same tips as Origin's branches |
| Origin `main` | `origin-archive/main` | ce4430a |

GitHub `main` (9f666e3) is the README and progress-site history and is not the Origin `main`. `cursor/origin-stack-sync` (GitHub PR #1) holds the Origin stack through #17 plus the Next.js site.

## 11 Nov 2026: handover to Claude Code and the consolidated tip

Work moved from Grok/Cursor to Claude Code (Opus 5.5 and Sonnet 5.5, with Fable 5.2 as advisor). The consolidated tip is `t3/tip` ([PR #47](https://github.com/advcode118/alexs-computeruseoptimisation/pull/47)), stacked on #42.

### Spend, corrected
- Claude ledger: **$26.022488** after the PR #27 probe. The $16.639436 figure above is stale. That ledger lived on the Cursor cloud box (`/workspace/cu-probe-tip-v6/bench/results/spend.json`). Set `CU_SPEND_LEDGER` to a file that starts at that total before any Claude probe from a new machine.
- OpenAI ledger: $1.330861 after the PR #36 runs. It was re-seeded on Tom's PC at `~/.cu-optimisation/openai-spend.json` with that figure as `recorded_extra_usd`.

### What the tip changes and why
1. **No answer key during script_first's run.** Up to #42, script_first's in-run stop/repair check used the task's `end_markers`. That gave it an oracle repair ("answer is not the marked value") and an oracle early stop that the baselines did not have, and that no real user would have. The live check is now `runtime_verdict` in `bench/script_first.py`, which uses no markers. The post-run grade is unchanged and still requires script_first's own PASS. The PR #27 numbers (18/18, 3.18s) were measured with the oracle, so they are an upper bound.
2. **Grading is no longer timed.** The post-run grade read was inside the wall clock, and #42 skipped it for script_first only.
3. **Stagehand cut.** `bench/stagehand_local.py` imitates Stagehand's tool surface on local Playwright. It is not the Stagehand library, so it is out of the comparison until the real library is run.
4. **Same answer-format line for every arm.** The baselines lost Hacker News on phrasing, not on finding the title.
5. Merged in #33/#34, #38, #41/#44, and the docs #21/#31/#32.

### Stale drafts (left open, not merged, not closed)
- #40 is replaced by #42 and the tip.
- #20, #22 and #24 are older copies of returned-evidence/overlap/helpers, redone in #30.
- #2's `NOTES.md` is already in the tip.
- #1 is contained in the tip and conflicts with `main`.
- #37 says there are no logs. PR #45 now groups the real OpenAI failures.
- #14 is the Grok/Cursor sync scripts, no longer used.
- `t3/step-heldout-tasks` is abandoned work-in-progress, replaced by #15/#33.
- The open PRs from #3 to #36 on the main line are all ancestors of the tip.

### Other branches from this session
- PR #45: failure taxonomy from the OpenAI jsonl (Mission 5).
- PR #46: `check_page` over MCP, which was already built (Mission 9). It adds tests and a README section.
- `cursor/local-bench-holdout-a63b`: a backup of the unpushed `computeruseoptimisation-loop` checkout. It has separate history and is not for merging.

### Where it stopped (11 Nov 2026, about 01:30) and what is next
The tip is `t3/tip`, PR #47, at `acf4011` plus this note. It includes PR #48's held-out tightening. The offline suite gives 280 passed, 1 skipped on Windows with Python 3.14.

OpenAI spend this session was $0.0075. The ledger is at $1.338349 of $20. Claude API spend was $0.
- The smoke run (`bench/runs/probe_20261111_012031.jsonl`, Luna medium, 3 tuned tasks) passed. script_first was 3/3 with one script each at 4.2–6.2s. browser_use was 3/3. playwright_mcp was 1/3.
- The 50-task held-out run was **stopped by hand after 8 of 150 rows** (`probe_20261111_012409.jsonl`, partial, not a result).
- `bench/runs/` is gitignored, so both files are only on Tom's PC.

Next, in order:
1. ~~Run the held-out measurement~~ **Done 11 Nov 2026** (Luna and Sol, medium, 50 tasks, no answer key). Results are in `docs/TEST_RESULTS.md` section 7b and `docs/results/heldout_*_20261111.jsonl`. script_first is fastest and cheapest but passes fewer tasks than browser_use.
2. ~~Write the results~~ Done.
3. **Claude comparison (optional, costs Claude API, needs Tom's go).** First point `CU_SPEND_LEDGER` at a file seeded to $26.022488. Then run `--honest`, which now uses 3 arms.
4. **Not done yet:**
   - The prompt and `repair_request` were made site-neutral (done before the held-out run); the earlier tuned-prompt numbers are not comparable.
   - About 19 held-out tasks have a final URL that can be guessed from the task text (see PR #45/#48 notes). Replace some with tasks whose URL is not derivable.
   - There are no multi-step or SPA tasks yet.
   - Mission 6 harness gaps from #32: timeouts and browsers still differ between arms.
   - Mission 10 (CUO-33/34) has not started. `cursor/local-bench-holdout-a63b` may contain earlier work on it.
   - The progress site: decide which site history is canonical (`main` vs the `cursor/progress-site-redesign-8676` line, PR #43). The live Vercel site was deployed from detached worktrees.
5. **Leave open:** PRs #45 (failure taxonomy) and #46 (check_page MCP tests) need a review and stay stacked where they are.

## 11 Nov 2026: plain rules in script_first's runtime check (branch `t3/runtime-plain-rules`)

**Why.** In the Decisions live run, 7 of the 9 right overturns were scripts whose answer was the page URL (4) or the page title (3). `runtime_verdict` failed them only because that answer is not in the body text. A plain rule fixes these with no model call.

**What changed, in `runtime_verdict` only.** (1) An http(s) answer that is the same page as the live or canonical URL (`_same_page`) is not checked against the page text. (2) The answer check also looks in the page title and h1. (3) The answer check folds the common dash variants (hyphen, non-breaking hyphen, figure, en and em dash, horizontal bar, minus) on both sides; non-breaking spaces already fold through `str.split()`. This uses a separate `_norm_runtime`, so the grade's `_norm_answer` is unchanged. Rules 1 and 2 do not apply when the live page is the start page, so a script that never left the start page still gets its repair. A PASS from a rule says which rule in its reason. A URL answer for another page, or an answer found nowhere, still FAILs. Task markers and the grade are untouched.
