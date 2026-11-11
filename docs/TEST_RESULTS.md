# Test results: script_first vs Playwright MCP, Stagehand, and browser-use

This is a self-contained write-up of every live probe that has been run on this project, written so it can be read in T3 Code. It covers the Claude Sonnet 5.5 18-task probes and the OpenAI gpt-6.1-sol / gpt-6-luna effort-sweep and medium 3-task runs on tip `b33989acd2bc53201c98acb6997ba85639e0a7ad` (draft [PR #36](https://github.com/advcode118/alexs-computeruseoptimisation/pull/36)).

Nothing in the tables is estimated. Every number comes from a saved run file, a probe log, or a spend ledger, cited next to the section. Where a figure is a planning estimate or comes only from an earlier verbal report and is not in a file, that is marked.

**Code tip these OpenAI runs used:** `b33989a` — *Price browser-use cache reads and writes, and keep finished probe rows.*

**When the OpenAI runs happened:** 10 November 2026, 9:45 PM–10:05 PM Europe/London (UTC+0). File birth/mtime on the box:

| Run | File | Started (Europe/London) | Finished (Europe/London) |
| --- | --- | --- | --- |
| Effort sweep (Wikipedia only, 8 effort cells × 4 arms) | `docs/results/2026-11-10/probe_20261110_214520.jsonl` | 9:45:20 PM | 9:59:05 PM |
| Sol medium, 3 tasks | `docs/results/2026-11-10/probe_20261110_215922.jsonl` | 9:59:22 PM | 10:02:42 PM |
| Luna medium, 3 tasks | `docs/results/2026-11-10/probe_20261110_220242.jsonl` | 10:02:42 PM | 10:05:31 PM |

The same three JSONL files are attached under `docs/results/2026-11-10/`. They were copied from `bench/runs/` (gitignored) after a scan for `sk-` and `OPENAI_API_KEY`; none contained secrets.

---

## 1. What the project is

The goal is to make computer use faster than the competition (Stagehand, Playwright MCP, browser-use), without giving up success rate. Tom's own approach is **script_first**, and that is the main metric.

### The four arms

| Arm | What it does |
| --- | --- |
| **script_first** | Tom's approach. The model writes one Playwright script for the whole task. The harness runs that script and grades the end state. A later warm pass can replay a cached script with no (or fewer) model calls. |
| **playwright_mcp** | Baseline: many small tool calls through Playwright MCP. |
| **stagehand** | Baseline: the Stagehand computer-use agent. |
| **browser_use** | Baseline: browser-use 1.0 driving local Chrome. |

All four arms run on the same tasks, the same outer model (when a provider is selected), and the same grader.

### Task sets

1. **3-task probe set** (`--split probe`, the default). These are the three tasks the arms were tuned on:
   - `wv_wikipedia_search` — search Wikipedia for "Ada Lovelace" and confirm the article page.
   - `wv_python_docs` — find the Python docs page for the `heapq` module.
   - `wv_hackernews_top` — go to Hacker News and identify the title of the top story.
2. **18-task held-out / honest set** (`--split honest`). The three tuned tasks above, followed by the fifteen held-out tasks added in PR #15 (`ho_mdn_array_map`, `ho_github_rust`, `ho_arxiv_attention`, `ho_wiki_eiffel_city`, `ho_nodejs_fs_docs`, `ho_httpbin_customer_form`, `ho_pypi_requests`, `ho_rust_book_borrowing`, `ho_w3c_selectors_4`, `ho_iana_status_451`, `ho_rfc9110_get_section`, `ho_schema_person`, `ho_cppreference_vector`, `ho_sqlite_vacuum`, `ho_k8s_pod`). The two sets stay disjoint. The Claude flag `--honest` selects this 18-task split, warms script_first only, and applies Claude spend stops. For OpenAI, `--honest` is refused (see §7).
3. **50-task set** on draft [PR #33](https://github.com/advcode118/alexs-computeruseoptimisation/pull/33) ("Score fifty held-out tasks that the dev set is not allowed to tune") and [PR #34](https://github.com/advcode118/alexs-computeruseoptimisation/pull/34) (confidence interval from one cold pass). **Not yet probed.**

### How grading works (as of `b33989a`)

These rules are in the commits on the PR #36 line. Later grading changes are required to be equal-or-stricter than what came before, and identical across all four arms.

- One shared grading function for every arm.
- The same page is read after each run and used for every arm.
- A Hacker News title must be an **exact match** (case and spacing still fold). A sentence around the live headline fails. Commit `1a4a4fe` restored this after `669fa8a` had loosened it.
- **script_first** must end its own run on PASS. Its returned evidence (URL, title, key text, and values) is checked against the live page. A FAIL or UNKNOWN end state is a fail. Commit `cd8082f` restored the own-PASS requirement after `1a4a4fe` had dropped it.
- An UNKNOWN verdict counts as a fail for every arm.
- The OpenAI path uses the same URL, text, and evidence checks as the Claude path (stated in the OpenAI plan output).

---

## 2. Claude Sonnet 5.5 history (18-task `--honest` probes)

All three probes used `claude-sonnet-5-5` on the 18-task honest set (3 tuned + 15 held-out), with a warm replay of script_first only. Means and medians below are **per successful task**, taken from the `report` block at the end of each log and checked against the JSONL. Spend figures are the `probe claude usd` line in the same log.

The Claude ledger at `/workspace/cu-probe-tip-v6/bench/results/spend.json` currently reads `running_total_usd` **$26.022488** against a **$50** project cap (the code's own abort is $40). That ledger was not changed by the OpenAI runs.

### PR #18 honest probe

Sources: `bench/runs/probe_20261110_134217.jsonl`, `honest-live.log` (`probe claude usd: 3.2448`).

| Arm | Cold success | Mean wall | Median wall | Notes |
| --- | ---: | ---: | ---: | --- |
| script_first | 17/18 | 2.85s | 2.81s | Fail: `ho_rfc9110_get_section` ("Model ended without completing task"). 17 one-shot scripts, one 2-step repair. Warm replay also 17/18, mean 1.80s, median 1.22s. |
| browser_use | 17/18 | 4.76s | 4.39s | Fail: `wv_hackernews_top` ("no deterministic check; LLM judge was not called"). |
| playwright_mcp | 18/18 | 5.71s | 3.86s | |
| stagehand | 17/18 | 13.42s | 5.75s | Fail: `ho_wiki_eiffel_city` (missing text `Paris`). |

**Uneven grading caveat (from this JSONL, not from a later summary):** on `wv_hackernews_top`, playwright_mcp, script_first, and stagehand were marked success with reason "Task completed successfully" and substring reason "no deterministic check; LLM judge was not called". browser_use failed the same task for that same missing deterministic check. So the 18/18 / 17/18 scores on this probe are not on the later shared fail-closed grader. Treat PR #18 as historical, not as a fair comparison.

### PR #23 fair-grading re-probe

Sources: `bench/runs/probe_20261110_143130.jsonl`, `honest-live-pr23.log` (`probe claude usd: 2.9924`). Tip is the fair-grading work (`2e827a6` — *Grade every arm by one fail-closed rule.*).

| Arm | Cold success | Mean wall | Median wall | Failures recorded in the JSONL |
| --- | ---: | ---: | ---: | --- |
| script_first | 16/18 | 3.52s | 2.92s | `ho_wiki_eiffel_city` (missing text `Paris`); `ho_rfc9110_get_section` ("Model ended without completing task"). Warm replay also 16/18, mean 1.48s, median 1.26s. |
| browser_use | 18/18 | 5.41s | 4.81s | |
| playwright_mcp | 17/18 | 6.10s | 3.77s | `wv_hackernews_top` ("empty answer"). |
| stagehand | 16/18 | 12.55s | 7.23s | `wv_hackernews_top` ("empty answer"); `ho_wiki_eiffel_city` (missing text `Paris`). |

### PR #27 re-probe on `3409e8a`

Sources: `bench/runs/probe_20261110_152617.jsonl`, `honest-live-pr27.log` (`probe claude usd: 3.1459`). Tip `3409e8a` — *Grade script_first on the page body the script left.*

| Arm | Cold success | Mean wall | Median wall | Failures recorded in the JSONL |
| --- | ---: | ---: | ---: | --- |
| **script_first** | **18/18** | **3.18s** | **2.98s** | None. 17 one-shot scripts, one 2-step repair. **Warm replay 18/18**, mean 1.81s, **median 1.46s**. |
| playwright_mcp | 17/18 | 5.25s | 4.03s | `wv_hackernews_top` ("answer is not the marked value"). |
| browser_use | 17/18 | 6.03s | 4.95s | `wv_hackernews_top` ("answer is not the marked value"). |
| stagehand | 16/18 | 12.54s | 6.69s | `wv_hackernews_top` ("answer is not the marked value"); `ho_wiki_eiffel_city` (missing text `Paris`). |

This is the best like-for-like Sonnet 5.5 result for script_first: perfect cold success, fastest mean and median, and a warm replay at 1.46s median. The other arms' Hacker News failures are recorded as "answer is not the marked value". This run file does **not** store `claimed_answer`, so the exact text they returned is not in the JSONL. (The later OpenAI medium runs do store answers; see §3.3.)

`docs/HISTORY.md` in this tree still quotes Claude spend as $16.639436 after the PR #18 probe. That figure is stale. The live Claude ledger is $26.022488.

---

## 3. OpenAI Sol / Luna tests on `b33989a`

Provider: `openai`. Models allowed by the harness: `gpt-6.1-sol` and `gpt-6-luna` only. Effort levels accepted by both models: `low`, `medium`, `high`, `xhigh` (`minimal` is rejected). Caps: $5 per run, $15 for an effort sweep, $20 project.

These runs did not touch the Claude ledger.

### 3.1 Effort sweep (Wikipedia only)

Source: `docs/results/2026-11-10/probe_20261110_214520.jsonl` and `openai-sweep-pr36c.log`. Command shape: `python -m bench.probe --execute --provider openai --sweep-effort --arms script_first,playwright_mcp,stagehand,browser_use`. That runs one tuned task (`wv_wikipedia_search`) per effort, Luna then Sol, low through xhigh.

The log summary is: `probe rows: 32`, `probe openai usd: 0.1751`. Wall times are `wall_ms / 1000` from the JSONL. Costs are the `usd` field on each row.

| Model / effort | script_first | playwright_mcp | stagehand | browser_use |
| --- | --- | --- | --- | --- |
| luna / low | ✓ 3.02s $0.000130 | ✓ 9.93s $0.000426 | ✗ 137.03s $0.000659 | ✓ 10.90s $0.000549 |
| luna / medium | ✓ 6.35s $0.000129 | ✓ 8.77s $0.000927 | ✓ 75.54s $0.000939 | ✓ 11.53s $0.000615 |
| luna / high | ✓ 4.06s $0.000166 | ✓ 18.15s $0.000822 | ✓ 50.92s $0.001130 | ✓ 35.89s $0.001349 |
| luna / xhigh | ✓ 4.36s $0.000184 | ✓ 8.54s $0.000937 | ✓ 77.94s $0.002056 | ✓ 14.11s $0.000753 |
| sol / low | ✓ 3.44s $0.002620 | ✓ 12.01s $0.011860 | ✓ 41.46s $0.012407 | ✓ 11.59s $0.015055 |
| sol / medium | ✓ 3.64s $0.002530 | ✓ 16.15s $0.011946 | ✓ 74.26s $0.015489 | ✓ 10.88s $0.012020 |
| sol / high | ✓ 3.54s $0.002630 | ✓ 11.69s $0.011946 | ✓ 45.31s $0.014258 | ✓ 11.73s $0.014218 |
| sol / xhigh | ✓ 3.80s $0.002610 | ✓ 12.09s $0.011860 | ✓ 9.46s $0.010249 | ✓ 9.66s $0.011602 |

The one failure is Stagehand on Luna / low: it finished on `https://en.wikipedia.org/wiki/Main_Page` (URL did not contain `Ada_Lovelace`) and returned an empty claimed answer, after 7 model calls and 137.03s.

**Per-arm totals from the sweep log's `report` block** (means and medians are per *successful* task):

| Arm | Success | Mean wall | Median wall | Sum of `usd` on all 8 cells (incl. the Stagehand fail) | script_first steps |
| --- | ---: | ---: | ---: | ---: | --- |
| script_first | 8/8 | 4.03s | 3.72s | $0.010999 | 8 one-shot scripts, 0 repairs |
| playwright_mcp | 8/8 | 12.17s | 11.85s | $0.050724 | |
| browser_use | 8/8 | 14.54s | 11.56s | $0.056161 | |
| stagehand | 7/8 | 53.56s | 50.92s | $0.057187 | If the 137.03s failure is included, Stagehand's all-cell median is 62.59s and mean is 63.99s. |

script_first was fastest and cheapest in every cell. Effort level made no clear difference to it (range 3.02s–6.35s; the 6.35s Luna / medium cell is the outlier, still well under the other arms). On these four script_first cells, Sol cost $0.010390 and Luna cost $0.000609, about **17×** as much, with no gain in success and no meaningful gain in speed.

### 3.2 Medium effort, 3-task runs

These are separate runs from the sweep's medium Wikipedia cells. Summary numbers are from each log's `report` block (mean wall per success). Per-task rows are from the JSONL.

#### gpt-6.1-sol, medium

Source: `docs/results/2026-11-10/probe_20261110_215922.jsonl`, `openai-medium-gpt-6.1-sol-pr36.log`. Log: `probe rows: 12`, `probe openai usd: 0.0961`.

| Arm | Success | Mean wall (successes) | Median wall (successes) |
| --- | ---: | ---: | ---: |
| script_first | **3/3** | **3.40s** | **3.41s** |
| playwright_mcp | 2/3 | 9.46s | 9.46s |
| stagehand | 2/3 | 40.24s | 40.24s |
| browser_use | 2/3 | 17.68s | 17.68s |

Per task (✓/✗, wall, cost, claimed answer):

| Task | script_first | playwright_mcp | stagehand | browser_use |
| --- | --- | --- | --- | --- |
| Wikipedia | ✓ 3.29s $0.002630 — "Confirmed: on the Ada Lovelace article page on Wikipedia." | ✓ 11.94s $0.005099 — sentence confirming the Ada Lovelace article | ✓ 73.62s $0.015789 — sentence confirming arrival at the article | ✓ 12.77s $0.010666 — sentence confirming the article is open |
| Python docs | ✓ 3.41s $0.002428 — `https://docs.python.org/3/library/heapq.html` | ✓ 6.97s $0.004870 — empty claimed answer (URL check still passed) | ✓ 6.85s $0.010559 — empty claimed answer (URL check still passed) | ✓ 22.58s $0.018456 — found the heapq docs page |
| Hacker News | ✓ 3.48s $0.002542 — `.name Grandfathered` | ✗ 9.22s $0.004039 — "— The top story on Hacker News is “.name Grandfathered”." | ✗ 8.86s $0.010952 — "— The top story on Hacker News is “.name Grandfathered”." | ✗ 10.32s $0.008069 — "The top story on Hacker News is **“.name Grandfathered”**." plus a source URL |

script_first was one-shot on all three tasks.

#### gpt-6-luna, medium

Source: `docs/results/2026-11-10/probe_20261110_220242.jsonl`, `openai-medium-gpt-6-luna-pr36.log`. Log: `probe rows: 12`, `probe openai usd: 0.0079`.

| Arm | Success | Mean wall (successes) | Median wall (successes) |
| --- | ---: | ---: | ---: |
| script_first | **3/3** | **4.53s** | **4.08s** |
| playwright_mcp | 2/3 | 10.23s | 10.23s |
| stagehand | 2/3 | 10.41s | 10.41s |
| browser_use | 2/3 | 16.59s | 16.59s |

| Task | script_first | playwright_mcp | stagehand | browser_use |
| --- | --- | --- | --- | --- |
| Wikipedia | ✓ 3.79s $0.000127 — "Ada Lovelace - Wikipedia" | ✓ 13.12s $0.000331 — sentence confirming the article page | ✓ 11.11s $0.000742 — "— Wikipedia’s Ada Lovelace article is open." | ✓ 16.08s $0.001077 — JSON with url/title/heading |
| Python docs | ✓ 5.71s $0.000138 — "heapq — Heap queue algorithm" | ✓ 7.34s $0.000432 — empty claimed answer (URL check still passed) | ✓ 9.71s $0.000876 — sentence with the heapq URL | ✓ 17.10s $0.000735 — found the heapq docs page |
| Hacker News | ✓ 4.08s $0.000126 — `.name Grandfathered` | ✗ 6.90s $0.000271 — empty answer | ✗ 43.63s $0.002661 — empty answer (11 model calls, 1 `model_ignores_tools`) | ✗ 5.38s $0.000353 — "The top Hacker News story is “.name Grandfathered.”" |

script_first was one-shot on all three tasks.

### 3.3 Hacker News failure analysis (OpenAI medium runs)

The live top title at the time of both medium runs, as returned by script_first and checked against the page, was `.name Grandfathered`.

- **script_first** returned that bare title on both Sol and Luna, and passed the exact-match check.
- **Sol, the other three arms** all found the same title but wrapped it in a sentence (and in browser-use's case, markdown and a source URL). The grader recorded "answer is not the marked value". That is a format failure, not a wrong title.
- **Luna, playwright_mcp and stagehand** returned an empty answer ("empty answer") — real failures, not format issues. Luna browser-use again wrapped the correct title in a sentence.

So script_first's success lead on these 3-task medium runs comes partly from answer format (Sol) and partly from actually returning the title (Luna playwright_mcp / stagehand). The speed lead is real on every task, including the ones the other arms passed.

### 3.4 OpenAI ledger

Source: `~/.cu-optimisation/openai-spend.json` as of after the three runs (the file was not modified while writing this document).

| Field | Value |
| --- | --- |
| `running_total_usd` | **$1.330861** |
| `recorded_extra_usd` | **$1.05** |
| Sum of priced `tasks[].usd` rows | **$0.280861** |
| Project cap | $20 |
| Per-run cap | $5 |
| Priced by model (task rows) | gpt-6-luna $0.021462, gpt-6.1-sol $0.259399 |

`$1.05 + $0.280861 = $1.330861`. The $1.05 extra is not invented token usage. In `bench/openai_spend.py`, `UNPRICED_CALL_RESERVE_USD = 1.0` and `UNRECORDED_CALL_ALLOWANCE_USD = 0.05`. A pricing refusal writes the $1 reserve before it aborts; the $0.05 allowance is for a call that never reached the ledger. Together they are the $1.05 `recorded_extra_usd`.

The three successful runs on this tip priced at $0.1751 + $0.0961 + $0.0079 = $0.2791 in their logs, which accounts for nearly all of the $0.280861 priced total (the remaining ~$0.0018 is earlier priced rows from before these runs).

The ledger file still has `aborted: true` with reason `browser-use usage has unrecognized fields ['cache_read', 'cache_write']. Refusing to price.` That flag is from the earlier abort, before `b33989a` taught the ledger to price those fields. The three runs above completed after that fix (`EXIT 0` in each log) and added their costs to the same ledger.

### 3.5 Bugs found and fixed on the way to `b33989a`

All of these are on the PR #36 branch, and the OpenAI measurements above were taken only after the last of them (`b33989a`).

| Commit | What was wrong | What the fix did |
| --- | --- | --- |
| `669fa8a` then `1a4a4fe` | The OpenAI path commit loosened Hacker News grading so a padded sentence could pass. | `1a4a4fe` grades a Hacker News title by exact match again. Case and spacing still fold. A sentence around the live headline fails. |
| `1a4a4fe` then `cd8082f` | The exact-match fix dropped script_first's requirement that its own run end on PASS. | `cd8082f` grades script_first only when its own run passed. The shared page check still has to pass, and the script's evidence has to be on the live page. FAIL or UNKNOWN stays a fail. |
| `542ad6a` | OpenAI `cache_write_tokens` was not priced, so a call could be refused or left off the ledger. | Cache writes are priced at the published 30-minute rate, or the 12-hour rate when that split is reported. A pricing refusal saves a reserve before it aborts. |
| `b33989a` | browser-use returned `cache_read` / `cache_write` usage fields the ledger did not recognise, so the run aborted and could drop finished rows. | Those fields are priced (cache read = cached input, cache write = 30-minute write rate). Any other unknown usage field is still refused. Each result row is flushed to the JSONL when it finishes. |

---

## 4. Caveats

- **3 tasks vs 18.** The OpenAI tables are one Wikipedia cell per effort, plus two 3-task medium runs. They are not a like-for-like comparison with the Sonnet 18/18 result on PR #27 (3.18s mean, 2.98s median, warm replay 1.46s median). Sol medium's 3.40s mean on 3 tasks is close to that Sonnet mean, but it is a smaller and partly tuned set.
- **One run per cell.** There is no repeat, no confidence interval, and no warm replay on the OpenAI path (`--warm-replay` is refused for OpenAI).
- **Stagehand wall time is highly variable**, from 9.46s (Sol / xhigh, a pass) to 137.03s (Luna / low, a fail) in the sweep alone. A single cell should not be treated as Stagehand's typical speed.
- **Hacker News exact match** is strict by design. Several "failures" still had the right title inside a sentence. script_first's success lead on Sol medium is therefore partly format; its speed lead is not.
- **PR #18 is not on the same grader** as PR #23 and PR #27. See the uneven-grading caveat in §2.
- **PR #40** (skip a second page read on a cold script_first pass) has not been live-probed, and it does not include the browser-use cache-pricing fix, so these OpenAI numbers should not be read as a test of #40.

---

## 5. Open draft PRs (one line each)

Titles are from `gh pr list` at the time this document was written. All of these except GitHub PR #1 and #2 are drafts. The list below is #28–#38 and #40, as requested; #39 was not an open PR in that listing.

| PR | Title (one line) |
| --- | --- |
| [#28](https://github.com/advcode118/alexs-computeruseoptimisation/pull/28) | Grade every arm on one page read and accept a live title inside a sentence. |
| [#29](https://github.com/advcode118/alexs-computeruseoptimisation/pull/29) | Cache script_first's stable prompt so later calls skip that prefill. |
| [#30](https://github.com/advcode118/alexs-computeruseoptimisation/pull/30) | Start Chrome while the model writes and check evidence the script returns. (Claude probe of this tip, about $3, has not been run. That $3 figure is a planning estimate, not a measurement in a run file.) |
| [#31](https://github.com/advcode118/alexs-computeruseoptimisation/pull/31) | Write down the desktop arm before it can mix into script_first. |
| [#32](https://github.com/advcode118/alexs-computeruseoptimisation/pull/32) | Record whether the four arms share timeouts, a browser, the model string, and the page-text source. |
| [#33](https://github.com/advcode118/alexs-computeruseoptimisation/pull/33) | Score fifty held-out tasks that the dev set is not allowed to tune. Not yet probed. |
| [#34](https://github.com/advcode118/alexs-computeruseoptimisation/pull/34) | Report a confidence interval from one cold pass so the scored set is not run twice. Not yet probed. |
| [#36](https://github.com/advcode118/alexs-computeruseoptimisation/pull/36) | Compare the computer-use arms on gpt-6.1-sol and gpt-6-luna without charging the Claude ledger. This is the tip the OpenAI numbers above were measured on (`b33989a`). |
| [#37](https://github.com/advcode118/alexs-computeruseoptimisation/pull/37) | Record that this tree has no probe logs from which to group failures. |
| [#38](https://github.com/advcode118/alexs-computeruseoptimisation/pull/38) | Replay script_first from a saved page so the helpers can be timed with no API call. Offline only. |
| [#40](https://github.com/advcode118/alexs-computeruseoptimisation/pull/40) | Skip the second page read and the extra UNKNOWN model call so a cold script_first run spends less wall time. Not probed. Does not include the browser-use cache-pricing fix from `b33989a`. |

---

## 6. How script_first compares, in brief

- On every OpenAI cell that was run, script_first was the fastest arm and the cheapest arm, and it passed every task (8/8 in the sweep, 3/3 on Sol medium, 3/3 on Luna medium).
- Across the eight sweep cells its median was 3.72s, against 11.85s for Playwright MCP, 11.56s for browser-use, and 50.92s for Stagehand (success-only).
- The best fair Sonnet 5.5 comparison remains PR #27: script_first 18/18 at 3.18s mean / 2.98s median (warm 18/18 at 1.46s median), ahead of Playwright MCP 17/18 at 5.25s, browser-use 17/18 at 6.03s, and Stagehand 16/18 at 12.54s.
- Sol is much more expensive than Luna for the same script_first work, with no success or speed benefit on these tests. If the next step is a fair 18-task comparison, Luna medium is the cheaper way to get it; Sol medium is the closer price-speed analogue to Sonnet, but still needs the 18-task set before that claim is solid.

---

## 7. Suggested next steps (not started)

Do not run these until Tom says go. They spend API money.

### 18-task OpenAI runs, Luna medium then Sol medium

`--honest` is the Claude comparison. On this tip it is **refused** with OpenAI (`ValueError: --honest is the Claude comparison. Refusing to combine it with OpenAI.` in `bench/openai_run.py`). The 18-task set is still available as `--split honest` (the three tuned tasks plus the fifteen held-out tasks). `--warm-replay` is also refused on the OpenAI path, so these would be cold-only.

Verified by printing the plan with no `--execute` (no network, no spend). The plan lists all 18 task ids, the four arms, effort medium, per-run cap $5, project cap $20, and `project_spent_usd` $1.330861.

From the box, in the checkout at `b33989a`, with the venv activated:

```bash
source .venv/bin/activate
python -m bench.probe --execute --provider openai --model gpt-6-luna --effort medium --split honest --arms script_first,playwright_mcp,stagehand,browser_use
python -m bench.probe --execute --provider openai --model gpt-6.1-sol --effort medium --split honest --arms script_first,playwright_mcp,stagehand,browser_use
```

Cost planning estimate, **not a measurement**: the 3-task medium runs cost $0.0079 (Luna) and $0.0961 (Sol). A naive 6× scale (18 tasks vs 3) is about $0.05 and $0.58, which is under $1 each, but held-out tasks can be more expensive than the tuned trio, so treat "<$1 each" as a planning figure. The $5 per-run cap and the $20 project cap (with $1.33 already on the ledger) still apply.

### PR #30 Claude probe

A Sonnet 5.5 `--honest` probe of [PR #30](https://github.com/advcode118/alexs-computeruseoptimisation/pull/30) ("Start Chrome while the model writes and check evidence the script returns") has been waiting on Tom. The planning figure for that probe is about $3. It would charge the Claude ledger (currently $26.02 of $50). It has not been run.

---

## 8. Source files

| What | Where |
| --- | --- |
| This write-up | `docs/TEST_RESULTS.md` |
| Effort-sweep rows | `docs/results/2026-11-10/probe_20261110_214520.jsonl` |
| Sol medium rows | `docs/results/2026-11-10/probe_20261110_215922.jsonl` |
| Luna medium rows | `docs/results/2026-11-10/probe_20261110_220242.jsonl` |
| Sweep / medium logs (local, gitignored `*.log`) | `openai-sweep-pr36c.log`, `openai-medium-gpt-6.1-sol-pr36.log`, `openai-medium-gpt-6-luna-pr36.log` |
| Claude PR #18 / #23 / #27 rows (local, gitignored `bench/runs/`) | `probe_20261110_134217.jsonl`, `probe_20261110_143130.jsonl`, `probe_20261110_152617.jsonl` |
| Claude logs (local, gitignored) | `honest-live.log`, `honest-live-pr23.log`, `honest-live-pr27.log` |
| OpenAI ledger (local, not in git) | `~/.cu-optimisation/openai-spend.json` |
| Claude ledger (local, not in git) | `/workspace/cu-probe-tip-v6/bench/results/spend.json` |
| Older project history (stale spend figure) | `docs/HISTORY.md` |
