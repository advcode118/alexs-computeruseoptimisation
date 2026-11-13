# Browser-agent architectures: what is best, and what script_first should do

Research note, 13 Nov 2026. No code changed, no model calls, no browser launched. Sources: the installed `browser-use` 1.0.3 package on this machine, this repo (`bench/script_first.py`, `bench/arms.py`, `bench/harness.py`, `bench/browser_use_arm.py`, `docs/HISTORY.md`, `docs/BROWSER_USE_REVIEW.md`), the saved non-heldout3 run rows in `docs/results/` (heldout, 11 Nov; heldout2, 13 Nov), and the web pages listed in the Sources section. Every web source was read on **13 Nov 2026**. Our own 138-task numbers are as given in the brief.

---

## One-page summary

**1. browser_use is not reliable because it has a better model or a judge. It is reliable because it looks before it acts.** The 1.0.3 package we run is a code-writing agent, like script_first. The model writes Python cells against raw CDP in a persistent REPL (`browser_use/agent/loop.py`, `agent/prompt.py`). It has no judge: `use_judge` and `judge_llm` were removed in 1.0 (`agent/service.py`). What it does that script_first does not: it sees the result of each cell before writing the next one. Its prompt says to "verify the actual outcome after every mutation". Every system that leads a public benchmark observes the page before it commits an action: Playwright MCP refs, Stagehand v4 `snapshot`, Browser Use ultrafast `bu.state()`, Jev's element table, and Skyvern's planner plus validator. **No leading system writes the whole task blind.** Our failure numbers match that. Only 31% of first scripts pass, and half of all failures end on the wrong page. Those are guessing errors, not execution errors.

**2. The clock is model turns × seconds per turn, and on our models a turn costs about 3–3.5 s.** In our saved rows, browser_use on `gpt-6-luna` takes a median of 5 model calls and 18.3 s. script_first takes 1 call. That gives about 3.5 s per call, almost all of browser_use's 20 s. Fast systems win one of two ways. They take fewer turns (code that chains several actions), or they make each turn very cheap (Jev Ultrafast: a hosted special-purpose policy at 178 ms per decision, about 7 s for a Google Flights search, n = 3). We cannot buy a 200 ms policy, so **our budget is about 2 model calls at the median to stay under 10 s.** The design has to spend those 2 calls on grounded decisions, not on blind guesses plus repair.

**3. "Fast path, then fall back" works only if the fallback starts warm.** Skim (Princeton/Microsoft, May 2026) is the closest published design to our hybrid. A cheap direct-URL HTTP path is checked by a small verifier and falls back to a full agent (BrowserUse among them) *started from the URL the fast path reached*. It reports 33.4% lower median latency and 1.9× lower cost with no accuracy loss. Its fast path covers only 12.6–45.3% of tasks, and its verifier precision is only 82%. Our fallback reaches 89% at a 20 s mean because it starts browser_use cold after the full script_first cost. The lesson is to warm-start the fallback and trigger it earlier, not to drop the fallback.

**4. Public leaderboards cannot pick our architecture for us.** WebVoyager is saturated and self-reported (99.19% at the top, with tasks filtered out). Browser Use's 97% on Online-Mind2Web is self-reported with its own agentic judge. The independent HAL harness puts the best Online-Mind2Web run at 42.3%. Almost nobody publishes seconds per task. Published LLM judges reach only about 70% precision on web trajectories (AgentRewardBench). Rule-based checks are more precise (83.8%) but miss successes. **Our paired A/B on our own tasks is the only number we should trust.** Our rule-based self-check already sits in the high-precision, lower-recall corner where the literature says rules land.

**5. The cheapest accuracy wins come from site structure the model never sees today.** That means real link hrefs, the site's own search form (its GET action URL and input name), and the page's real h1. Several papers report gains from turning sites into direct URLs or tools instead of click paths: WALT ("a search call replaces 8+ fragile UI steps"), Beyond Browsing (API-plus-browsing hybrid 38.9% vs 14.8% browsing-only on WebArena), Skim's URL templates, and WebNavigator's "teleport". These map directly onto our two worst types, site search (22%) and wrong page (half of failures).

### Recommendation in one paragraph

Choose **(B), a different core: "observe once, then script"**. It keeps script_first's executor, grammar and rule-based self-check. The first model call should see a compact *page card* of the start page, built from a parallel HTTP fetch while Chrome launches, or from Chrome's accessibility tree when the page is rendered by JavaScript. It should not write blind. After the script runs, a FAIL gets a snapshot of the landed page and up to two more grounded turns. Anything still failing goes to a **warm** browser_use that starts on the current page. Target on `gpt-6-luna`: about 1.6 model calls on average, a median of about 8 s, a mean of about 10 s, and about 90–93% pass, rising to 95% with the warm fallback. Those are estimates, not measurements; the experiments below test them. Of the two bets already in flight, (a) the snapshot plus multi-turn repair is the right bet, but the snapshot also needs to reach the *first* turn. (b) The forgiving executor is a smaller bet: it cannot fix wrong-page failures, and fuzzy matching can raise false accepts.

---

## 1. What leads today, and how far to trust it

| Benchmark | Top numbers found | Who reports | Trust |
| --- | --- | --- | --- |
| WebVoyager (643 tasks, 15 live sites) | browser-control (Fable 5) 99.19% (610/615 after 4 exclusions), Alumnium 98.5%, Surfer 2 97.1%, Magnitude 93.9%, Browser Use 89.1%, Skyvern 2.0 85.85% (Steel aggregator, updated 11 Oct 2026) | Mostly self-reported; filtered task sets; graders differ | **Low.** Saturated. The aggregator itself says gaps "can reflect setup choices". An independent 2026 audit found Operator at 68.6% against the 87% OpenAI reported (arXiv 2603.29020). |
| Online-Mind2Web (300 tasks, 136 sites) | Browser Use Cloud `bu-max` 97% (25 Mar 2026, agentic judge on the Claude Agent SDK); GPT-5.4 CU 93% (no public data); UI-TARS-2 88%; Stagehand (Sonnet 4.5) 55%; Operator 61% | Browser Use's own post | **Low to medium.** Self-reported, with the vendor's own judge "aligned with humans". |
| Online-Mind2Web on HAL (independent harness) | SeeAct + GPT-5 medium 42.33%; Browser-Use + Sonnet 4 40.0% | Princeton HAL | **Medium-high** for the ranking. The models are old (2025), there are no timings, and HAL flags its cost column as overstated up to 2×. |
| Online-Mind2Web paper | LLM-as-judge reaches about 85% agreement with humans; earlier results showed "over-optimism" | Xue et al., COLM 2025 | **High** for the judge-leniency point. |
| WebArena (812 tasks, self-hosted) | WebTactix 74.3%, OpAgent 71.6% (Jan 2026), WebNavigator 72.9% (multi-site), Surfer 2 69.6%; human 78.2% | Self-reported; Steel aggregator | **Medium.** Reproducible environment, but different site types from ours. |
| Web Bench (Halluminate/Skyvern, 2,454 tasks) | Read tasks: 5 of 7 agents above 70%. Write tasks: best 46.6% (Skyvern 2.0) | Independent-ish (May 2025) | **Medium.** Old. Useful for one point: write and form tasks take 2–5× more steps and fail far more often. |
| Speed or latency | Browser Use cloud agent 68 s per task on Online-Mind2Web vs 225–330 s for vendor CUAs (Oct 2025); Jev Ultrafast 7.1 s on one task (n = 3); Skim: off-the-shelf agent median LLM 4.7 s and browser action 6.6 s per task | All vendor or paper self-reports | **Low.** No independent latency leaderboard exists. |

What this means for us. Every public number is on harder, longer tasks than ours, and our tasks are mostly reads. On reads, everyone is above 70%. Our browser_use control already reaches 96%. **The bar is set by our own baseline, not by a leaderboard.** Also, the browser-use team now ranks *browser tools for coding agents* by tasks per 10M tokens: Browser Harness 4.7, Playwright MCP 2.3 (vendor-run, unknown task set). That is a sign the field has moved toward the "model writes code against a thin harness" shape that script_first already has.

## 2. How the leading systems are built

### browser-use 1.0.3 (read from the installed package)

- **Loop.** A Pydantic AI agent with one tool, `python(code)`, plus the delivery tools `finish` and `finish_from_repl` (`agent/loop.py`). Each model response runs one Python cell in a persistent REPL worker (`repl/worker.py`, `repl/session.py`). Variables survive between cells. Cells run in order (`Tool(python, sequential=True)`). Cell output is capped at 12,000 characters (`MAX_OUTPUT_CHARS`), and each cell times out at 120 s (`cell_timeout_s`). Our arm caps it at 30 steps.
- **Page representation, default mode** (what our arm runs, because `ChatOpenAI` is not a gateway alias, `agent/service.py:293-295`). The library sends **no page state at all**. The model reads the page itself: `page_info()`, `js(...)`, and the prompt's advice to use `cdp('Accessibility.getFullAXTree')` and filter it in Python before printing (`agent/prompt.py`). The prompt also tells it to chain work: "Every call is a full model turn: do not spend one on a lone js(), page_info(), list_tabs() or screenshot() peek."
- **Element indexing.** Chrome `backendDOMNodeId`s from the AX tree. In default mode the model clicks through `DOM.getBoxModel` and `click_at_xy`. In `mode='ultrafast'` (`ax.py`), `bu.state()` prints `[id] role "name" = value` lines plus headings and visible text, and `*` marks ids that are new since the last look. `bu.click(id)` and `bu.type(id, text)` act on those ids. After any cell that acted, the state is **printed automatically**, so the next turn never has to be a "look" turn. Their own note: Google Flights went from 0/3 in default mode to 3/3 in ultrafast (`agent/service.py:293`).
- **Done and "judge".** No judge model. `finish(result, success=...)` ends the run. `check_delivery` refuses an empty or placeholder delivery once, and `check_split_delivery` refuses a finish that shares a response with another call. The system prompt asks the model to "verify it against observed evidence" and to tell apart "discovered, attempted, fetched and verified". Verification happens inside the same cells, so it costs no extra turns.
- **Why it is reliable on a small model.** (1) It observes before committing. (2) It can always run another cell after a surprise: retries are unbounded and only `max_steps` stops it (`TOOL_RETRIES = 1_000_000`). (3) It reads what it needs with `js()` instead of guessing, so the answer comes from the live DOM. (4) It never has to guess a URL: it can click what it saw.
- **Where the 20 s goes.** In our saved rows (`docs/results/heldout_*_20261111.jsonl` and `heldout2_tip2_20261113/`), browser_use on `gpt-6-luna` used a median of 5 model calls (mean 5.8), 18.3 s median wall time, and about 18.6k input tokens. script_first used 1 call (mean 1.4) and 884 input tokens. At about 3.5 s per call, the turns explain about 15–18 s. The rest is daemon and Chrome start-up and the REPL worker start. A turn does not get cheap just because its prompt is cached: the cost is reasoning plus output tokens. Browser Use's own numbers (Oct 2025): 1,000 input tokens cost about 29 ms, while 10 output tokens cost about 63 ms.
- **Fairness note for our benchmark.** Our arm runs browser_use in `default` mode. The library's authors evaluate their fast models in `ultrafast`. A reviewer could say our baseline is not its fastest configuration. See experiment 7.

### Others

- **Playwright MCP** (microsoft/playwright-mcp README). An accessibility snapshot of roles and names with element refs. Each action is one tool call that names a ref, with `--snapshot-mode full|none`. It also ships `browser_run_code_unsafe`, which runs a Playwright snippet. Our measurement on `gpt-6-luna`: 64% pass, 6 calls median, 13.7 s median, about 32.6k input tokens. One call per action is the slow shape.
- **Stagehand.** v3 used `act/observe/extract`. A hybrid AX tree plus DOM, where the LLM returns an XPath, a method and arguments, and the run is deterministic. Actions are cached to disk and replayed with no model call, re-inferred if the selector breaks (docs.stagehand.dev). **v4 (Browserbase blog, 9 Sep 2026) dropped that.** It is now a Chrome extension with three MCP tools: `run` (model-written **Playwright** code, transpiled to Stagehand calls), `snapshot` (pruned DOM plus AX) and `screenshot`. Their reason: the act/observe hybrid "filled context windows" on long tasks. They claim "2× faster than Playwright" and "80% more token efficient", with no benchmark named. Online-Mind2Web: 55–65% (Browser Use's table).
- **Skyvern 2.0.** Planner → actor → validator. Their own progression: a single prompt at about 45%, about 68.7% with the planner, 85.85% with the validator, on GPT-4o and GPT-4o-mini. The ~45% baseline is from a secondary source. 8 WebVoyager tasks were removed and dates were updated. No timings.
- **Jev Ultrafast** (browser-use + TypeSafe, MIT, README). Each turn sees a numbered table of visible controls (at most 250) with up to 6,000 characters of text, no screenshot. The policy picks an operation and a target from a fixed menu in one round trip (median 178 ms). A small text model writes typed text only. `DONE` is not trusted: `verify()` checks the page itself. Results: 7.1 s on Google Flights, 2.8 s on Wikipedia, 3/3 runs, and the README says outright that this is "not a general reliability benchmark". The design is now "ultrafast mode" in browser-use.
- **Vision and computer-use agents** (Surfer 2, Magnitude, OpenAI CUA, Gemini CU). Screenshots to coordinates, often with a separate grounding model and a validator. They lead WebVoyager (Surfer 2 97.1%, Magnitude 93.9% at an average of **15.5 steps** per task) but are slow and costly ("Surfer 2 runs are extremely costly", H Company). Vendor CUAs took 225–330 s per Online-Mind2Web task (Browser Use, Oct 2025). This is the wrong direction for speed on text-heavy public sites.
- **Distillation and action-space research.** AgentOccam (ICLR 2025): trimming observations to concise Markdown and removing rare actions gave +26.6 points on WebArena, with no planner. Browser Use: actions of about 10–15 output tokens, with screenshots only when needed (each adds about 0.8 s).
- **Top research systems.** WebNavigator (an offline site graph, then "retrieve-reason-teleport", 72.9% on WebArena multi-site). WALT (learn the site's own search, filter and sort as tools: 1.3–1.4× fewer steps, +10–30% success). SkillWeaver and Agent Workflow Memory (reuse distilled skills and workflows across tasks). Beyond Browsing (APIs first, browser as backup). All of them get speed and accuracy by **removing navigation guesswork**.

### Comparison table

| Architecture | Page representation | Action format | Model calls per task | Reported accuracy | Reported time / cost | Source, date read | Trust |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **script_first (ours)** | None (blind) | One whole-task script, restricted Playwright-like grammar | 1 median, 1.4 mean | 53% (luna), 88% (sol) on 138 tasks | 7.3 s median, $0.0005 | This repo | High (measured) |
| **browser_use 1.0.3, default mode (our control)** | Whatever the model prints (AX filtered in Python, `js()` reads) | Python cells over raw CDP | 5 median, 5.8 mean (luna) | 96% (luna) | 20 s median, 25 s mean, $0.0013 | Installed source plus our rows | High (measured) |
| browser-use ultrafast / `bu-max` cloud | Auto-printed AX state with backendNodeId refs, `*` for new | Python plus `bu.click(id)` and `bu.type(id)` | n/a | 97% Online-Mind2Web (own judge) | n/a | [BU blog](https://browser-use.com/posts/online-mind2web-benchmark), 25 Mar 2026 | Low-medium (self-reported) |
| Browser Use cloud agent (Oct 2025) | Indexed DOM, screenshots only when needed | Short JSON actions, about 3 s per step | n/a | 65.7% Online-Mind2Web | 68 s per task | [BU speed post](https://browser-use.com/posts/speed-matters), 9 Oct 2025 | Low (self-reported) |
| Jev Ultrafast | Numbered control table ≤250, ≤6k chars of text | Multiple-choice op plus target id | 1 per action, 178 ms each | 3/3 on one task | 7.1 s Flights, 2.8 s Wikipedia | [README](https://github.com/browser-use/jev-ultrafast), 2026 | Low (n = 3) |
| Playwright MCP | AX snapshot with refs | One tool call per action | 6 median (our luna rows) | 64% (our luna rows) | 13.7 s median | [repo](https://github.com/microsoft/playwright-mcp) plus our rows | High for our setup |
| Stagehand v3 | Hybrid AX plus DOM → XPath | act/observe/extract, disk cache replay | 1 per act or extract; 0 on a cache hit | 55–65% Online-Mind2Web | "<100 ms cached" (secondary, unverified) | [docs](https://docs.stagehand.dev/v3/basics/act) | Low |
| Stagehand v4 | Pruned DOM plus AX `snapshot` | Model-written Playwright, transpiled | n/a | n/a | "2× faster than Playwright" (benchmark unnamed) | [Browserbase](https://browserbase.com/blog/evolving-computer-use-with-code), 9 Sep 2026 | Low |
| Skyvern 2.0 | Vision plus DOM | Planner → actor → validator | n/a | 85.85% WebVoyager (8 tasks removed) | n/a | [Skyvern](https://www.skyvern.com/blog/skyvern-2-0-webvoyager-benchmark-results/), updated 30 Sep 2026 | Medium-low |
| Magnitude | Pure vision | Coordinates | 15.5 steps on average | 93.9% WebVoyager | n/a | [Steel](https://leaderboard.steel.dev/leaderboards/webvoyager.md), 11 Oct 2026 | Low |
| Surfer 2 (H) | Vision, with grounding (Holo) and a validator | ReAct, hierarchical | n/a | 97.1% WebVoyager, 69.6% WebArena | "extremely costly" | [arXiv 2510.19949](https://arxiv.org/html/2510.19949v2) | Low-medium |
| Skim (research) | HTTP-fetched cleaned HTML on the fast path | Synthesized URL, then small-model extraction, then verifier, then warm fallback | Several small calls; fallback to a full agent | Equal or better than backbone (BrowserUse 45.6 vs 45.0) | −33.4% median latency, 1.9× cheaper; fast-path hit 12.6–45.3%; verifier precision 82% | [arXiv 2605.16565](https://arxiv.org/html/2605.16565v2), May 2026 | Medium |
| Beyond Browsing (research) | API docs plus browsing | API calls, browser as backup | n/a | 38.9% hybrid vs 14.8% browsing-only (WebArena) | n/a | [arXiv 2410.16464](https://arxiv.org/html/2410.16464v3), v3 Jun 2025 | Medium |
| WALT (research) | Browsing | Learned site tools (search, filter, sort) | 1.3–1.4× fewer steps | +10–30% success | n/a | [arXiv 2510.01524](https://arxiv.org/html/2510.01524v1) | Medium |
| AgentOccam (research) | Concise Markdown | Pruned action set | n/a | +26.6 points on WebArena | about 25% fewer tokens per step | [arXiv 2410.13825](https://arxiv.org/html/2410.13825v2) | Medium |

## 3. Speed techniques: who uses them, the gain, and the accuracy cost

| Technique | Who | Reported gain | Accuracy cost | For us |
| --- | --- | --- | --- | --- |
| Many actions per model turn (code, or multi-action) | browser-use (Python cells), Stagehand v4 (`run`), script_first | browser-use's prompt: "each model call costs ~1 s, so chain everything into one python call" | None if the model saw the page first; large if it did not (our 31% first-script pass) | Keep it, but ground it |
| Element-ref snapshot that makes a step cheap | Playwright MCP, browser-use ultrafast, Jev | Jev: 1,092 → 101 browser protocol calls, median 9.45 → 7.09 s (n = 6) | Refs go stale after navigation (AX_PROMPT says so) | Use refs only inside one script on one document; fall back to visible names |
| Auto-printed state after an action | browser-use ultrafast | Removes "look" turns (their Google Flights 0/3 → 3/3) | None reported | This is what the repair snapshot should be |
| Skip the browser: HTTP fetch, URL templates, APIs | Skim, Beyond Browsing, WALT, WebNavigator | Skim: −33% latency, 1.9× cheaper; WALT: 1.3–1.4× fewer steps | Skim: verifier precision 82%; hit rate only 12.6–45.3% | Use HTTP to *observe* (page card), not to *answer* without a browser |
| Action or workflow caching and replay | Stagehand v3, AWM, SkillWeaver, our `ScriptCache` | Cached act needs no model call; our warm replay was 1.80 s vs 2.85 s cold (PR #18 era, `BROWSER_USE_REVIEW.md`) | Stale cache → replay fails → full cost plus the miss | Only helps repeated tasks; our benchmark is fresh tasks. Not the main lever. |
| Speculative or parallel execution | Speculative Actions (ICLR 2026), Jev (speculative target heads) | Up to 55% next-action prediction; no seconds figure in the abstract | Lossless by design; costs extra calls | One cheap form: launch Chrome and fetch the page while the model thinks (already partly done) |
| Small-model routing with escalation | Skim (small extractor plus verifier), Jev (small text model) | Skim: 11.5× cheaper verifier per call | Naively swapping small models into a ReAct loop "drops average task success by 60%" (Skim §2.3) | Escalate on a FAIL; don't route blindly |
| Prompt caching | browser-use (Anthropic `cache=True`; OpenAI `store=False`), OpenAI automatic caching ≥1,024 tokens | Prefill only; Browser Use measures input at about 29 ms per 1k tokens | None | Our script prompt is about 884 tokens, *under* OpenAI's 1,024-token automatic minimum. A page card pushes it over; put the stable prefix first. Small gain. |
| Fewer output tokens | Browser Use (10–15-token actions) | Output is about 215× costlier per token than input in time | None | Short scripts: `goto(href)` beats click chains |
| Warm browser | Every cloud vendor | Unmeasured here | None | Measure Chrome start-up as part of the split (experiment 8) |
| Streaming, early execution of partial output | No primary source found that measures it for web agents | **Unverified** | Risky with a whole-task script (a later line can change an earlier one) | Skip for now |

## 4. Verification and false accepts

- **How the good systems decide "done".** browser-use: the model's own `finish(success=…)`, after it has looked at the evidence in the same cells, with a guard against empty or placeholder deliveries. No extra model turn. Skyvern: a validator role (+17 points by its own account). Jev: an external `verify()` per task. Skim: a lightweight verifier model at 82.0% precision and 86.2% recall, about 1 s per call.
- **How good judges are.** AgentRewardBench (2025, 1,302 expert-labelled trajectories): no LLM judge does better than about 70% precision. Rule-based checks reach 83.8% precision and 55.9% recall. Online-Mind2Web's judge reaches about 85% agreement with humans. **A judge model costs 1–3 s and still accepts many wrong results.** Our rule-based check (about 10% false accepts) already matches or beats that.
- **Why our title tasks reach 25% false accepts** (inferred from `runtime_verdict`, not measured row by row). A non-URL answer passes when it appears *anywhere* in the page text (`needle in _norm_runtime(page_text)`). A title claimed while sitting on a list, search-results or category page is almost always somewhere in that page's text, so the check passes on the wrong page. The fix is a rule, not a judge: for a title or name answer, require a match with the harness-read h1, `document.title`, or the main heading, and refuse a pass on a page that looks like a results list. That trades some recall for precision, as the literature predicts.
- **Cost of verification in time.** The rule check costs 0 s. A model judge adds a turn, 3 s or more on our models. Don't add one on the hot path. If one is ever used, use it only on borderline cases (UNKNOWN), never as the main gate.

## 5. The answer: A, B or C?

**(A) Keep script_first and add mechanisms.** This is not enough on its own. A blind first script is the root cause behind both the 31% first-pass rate and the "half the failures are on the wrong page" number. Repairs after the fact cost a full turn each and start from a wrong page.

**(C) Wrap browser_use and make it faster.** This is the safest route to accuracy, but it is unlikely to reach the speed target on `gpt-6-luna`. Even in ultrafast mode, a reasonable floor is about 3 calls × about 3.5 s plus start-up, roughly 12 s median, against a target of under 10 s. Run it as a control (experiment 7). If it lands at 95% or better in about 10 s or less, adopt it.

**(B) Recommended: "observe once, then script" with grounded repair and a warm fallback.** It keeps our grammar, executor, self-check and cost profile. It changes what the model sees.

### Request flow

```
t=0     ├─ launch / take warm Chrome ────────────────────────────┐
        └─ HTTP GET start_url (100–300 ms, Skim's figure)        │
t≈0.4s  page card from HTML (no model): title, h1, main text ≤1.5k chars,
        links (text → absolute href, ≤80), GET forms (action URL + input
        names + labels → a ready "search URL template"), <link rel=canonical>.
        If HTML looks JS-rendered (tiny text, SPA root, blocked/403):
        wait for Chrome, goto, take compact AX snapshot instead (+1–2 s).
CALL 1  task + page card → one script (same grammar; goto must use a seen href
        or the form template where possible; ends with the evidence evaluate)
        ~3 s
RUN     execute in Chrome (Chrome is ready by now) ~1–2 s
CHECK   runtime_verdict + stricter title/name rule (0 s)
        PASS → done                                     (≈ 5–7 s)
        FAIL/UNKNOWN → CALL 2: failure reason + compact snapshot of the LANDED
        page (AX refs, headings, ≤3k chars text, links) → next script segment
        that continues from the current page (not from scratch) ~3 s + run
        PASS → done                                     (≈ 9–11 s)
        FAIL → CALL 3 (same shape)                      (≈ 13–15 s)
        FAIL → warm fallback: browser_use started on the current page and
        browser, with the page card in its task text; or stop and report fail.
```

### Estimates per task type (`gpt-6-luna`; estimates, not measurements)

| Type | Today | Calls (mean) | Median s | Expected pass | Why it should move |
| --- | --- | --- | --- | --- | --- |
| value | 72% | 1.3 | 6–7 | 90–95% | The page card shows real hrefs, so no URL guessing |
| navigate | 61% | 1.2 | 6 | 90–95% | Same |
| title | 54% (25% false accepts) | 1.4 | 7 | 88–94% | Hrefs plus the stricter title rule |
| site search | 22% | 1.7 | 7–9 | 75–90% | The GET form template gives the exact results URL; call 2 sees the results list and picks the item |
| form | 45% | 2.0 | 9–10 | 80–90% | Labels and input names seen before writing; snapshot after submit |
| JavaScript pages | 38% | 2.2 | 10–12 | 75–88% | AX snapshot instead of HTML; a second grounded turn after render |
| **all** | 53% | about 1.6 | about 8 | about 88–93% (95% with the warm fallback) | |

Mean time should land around 10–11 s, about 40–45% of browser_use's 25 s mean. Cost should stay well under browser_use's: page cards add about 1–3k input tokens per call.

### What would prove it wrong

1. Experiment 1 shows that a page card in call 1 does **not** raise first-script self-check passes from 31% to at least 55% on luna (on dev tasks). Then observation is not the bottleneck, and (C) moves ahead.
2. HTTP page cards are unusable (blocked, empty or JS-only) on more than 30% of our sites, and the AX fallback adds more than 2 s. Then the speed case collapses to "wait for Chrome then observe", and the median estimate rises by about 2 s.
3. Calls with page cards take more than about 4.5 s each (input growth, or the model reasoning longer). Then 2 calls no longer fit in 10 s.
4. The grounded loop plateaus below about 85% at 3 calls. Then browser_use's advantage is open-ended exploration, not first sight, and (C) is the better base.
5. browser_use ultrafast (experiment 7) reaches 95% or better at about 10 s median or less. Then wrap it.

### Verdict on the two bets already in flight

- **(a) Page snapshot plus multi-turn repair: right bet, incomplete.** It turns the repair from a blind retry into a grounded step, which is browser_use's real advantage. But two thirds of the cost is the *first* script being blind. Make the same snapshot or page card available to call 1, and continue from the landed page rather than rewriting from the start. Keep the snapshot compact (AgentOccam's lesson), and print it automatically after the script (browser-use ultrafast's lesson). Keep `selector_text` and every judge-only field out of it, as `BROWSER_USE_REVIEW.md` already requires.
- **(b) More forgiving step executor: secondary bet.** It can lift forms (45%) and JavaScript pages (38%) where the failure is a strict name match or a missing settle. It does nothing for wrong-page failures (half of all failures). Two guardrails apply. Fuzzy matching must never pick between two candidates silently; fail with the candidate list, which is good input for call 2. And measure false accepts before and after, because a wrong click that lands on *some* page with text can pass the current text-contains rule. A short settle (browser-use's `AxHelpers.settle`: DOM quiet 80 ms, 800 ms cap) after actions that change the page is the most likely single win inside (b).

## 6. Top experiments, ranked (each about one day; live runs need Tom's go and use dev or val sets only, never heldout3)

| # | Experiment | Target failure number | Method | Pass bar |
| --- | --- | --- | --- | --- |
| 1 | **Stricter title and name rule in `runtime_verdict`** | Title false accepts 25%; about 10% overall | **Offline, $0.** Replay saved non-heldout3 rows: for a name or title answer, require a match with h1, `document.title`, or a heading; FAIL on results-list pages (many sibling links, search params in the URL). Count verdict flips against the grade. | Title false accepts ≤5% while losing ≤5 points of true passes |
| 2 | **Page card in call 1** (HTTP fetch, distil, no model) | First-script pass 31%; wrong page 50% of failures | Build `page_card(url)` offline and unit-test it on saved HTML. Then one dev run, script_first with and without the card, same tasks, paired. | First-script self-check pass ≥55% (luna); median wall time +≤0.7 s |
| 3 | **Search via the form template** | Site search 22% | The page card emits `search_url_template` from GET forms (and OpenSearch `<link rel=search>` where present). The prompt says to use it for site search. Test the extractor offline on saved start pages, then run search tasks only. | Search ≥60% at 1–2 calls |
| 4 | **Grounded continuation** (bet a, extended) | Overall 53%; repairs that start over | On FAIL, send a compact snapshot of the landed page; the next script continues from the current page; up to 2 extra calls. | Luna ≥85% overall with mean calls ≤2.0 |
| 5 | **Warm-start fallback** | Fallback mean time 20 s | Hand browser_use the live browser and current URL plus the page card, or use the grounded loop as the fallback and keep browser_use as the last resort. | Hybrid ≥89% at mean ≤12 s |
| 6 | **Settle after page-changing actions** (inside bet b) | Forms 45%; JavaScript 38% | After click, press or fill on a control that triggers navigation or XHR: wait for DOM quiet 80 ms, capped at 800 ms. No other waits. | +15 points on form and JavaScript tasks; median wall time +≤0.5 s |
| 7 | **Control: browser_use `mode='ultrafast'`** | Decides between B and C; benchmark fairness | Same model, same effort (medium, no sweeps), same tasks; only the mode changes. | If ≥95% at ≤10 s median, switch to (C) |
| 8 | **Time split** | Where script_first's 7.3 s goes | **Offline from logged timestamps** if present (model, Chrome start, goto, script, check); otherwise add timing fields in a later code PR. | Know whether Chrome start or model time dominates before buying a warm pool |

Order of work: 1 and 8 are free and offline, so do them first. 2 and 3 share the page-card code. 4 is bet (a). 5 is needed for the 95% target. 7 is the control that keeps us honest.

## 7. Where the evidence is thin

- No independent latency benchmark exists for web agents. Every time-per-task figure outside our own runs is vendor-reported, often on one task.
- Browser Use's 97% and every WebVoyager figure above 90% are self-reported with the reporter's own judge or filtered task sets.
- Skim gives no per-backbone latency in its text; the BrowserUse figures are only in charts. Its fast-path accuracy is not broken out.
- Stagehand v4's "2× faster" has no named benchmark. Per-step Stagehand and Skyvern speeds in blog roundups have no source.
- I found no primary measurement of streaming or early execution for web agents. That is marked unverified.
- Not verified at the primary source: Yutori's "Hark 97.7% on Online-Mind2Web" (search snippet only); the Skyvern ~45% single-prompt baseline (secondary source); Magnitude's planner and grounder split.
- The per-type estimates in section 5 are my projections from the mechanisms and from browser_use's gap. They are what experiments 2–5 measure.
- The diagnosis of title false accepts (text-contains on list pages) comes from reading `runtime_verdict`, not from counting rows. Experiment 1 checks it.

## Sources (all read 13 Nov 2026)

Local: `browser_use` 1.0.3 at `site-packages/browser_use/` (`agent/loop.py`, `agent/prompt.py`, `agent/service.py`, `ax.py`, `tools.py`, `repl/session.py`); this repo's `bench/` files, `docs/HISTORY.md`, `docs/BROWSER_USE_REVIEW.md`; run rows in `docs/results/heldout_*_20261111.jsonl` and `docs/results/heldout2_tip2_20261113/`.

Web:
- Browser Use, "Online-Mind2Web benchmark" (25 Mar 2026): https://browser-use.com/posts/online-mind2web-benchmark
- Browser Use, "Speed matters" (9 Oct 2025): https://browser-use.com/posts/speed-matters
- Browser Use benchmarks page (Oct–Nov 2026): https://browser-use.com/benchmarks
- Jev Ultrafast README: https://github.com/browser-use/jev-ultrafast ; source tour (29 Sep 2026): https://pyshine.com/Jev-Ultrafast-Browser-Agent-Source-Tour/
- Steel WebVoyager leaderboard (updated 11 Oct 2026): https://leaderboard.steel.dev/leaderboards/webvoyager.md
- Princeton HAL Online-Mind2Web: https://hal.cs.princeton.edu/online_mind2web
- Xue et al., "An Illusion of Progress?" (COLM 2025): https://arxiv.org/abs/2504.01382
- Operator WebVoyager audit (Mar 2026): https://arxiv.org/html/2603.29020
- Skim, speculative execution for web agents (May 2026): https://arxiv.org/html/2605.16565v2
- Beyond Browsing: API-based web agents: https://arxiv.org/html/2410.16464v3
- WALT: https://arxiv.org/html/2510.01524v1 ; Agent Workflow Memory: https://icml.cc/virtual/2025/poster/45496 ; SkillWeaver: https://arxiv.org/abs/2504.07079
- WebNavigator: https://www.alphaxiv.org/overview/2603.20366
- AgentOccam: https://arxiv.org/html/2410.13825v2
- AgentRewardBench: https://arxiv.org/abs/2504.08942
- Speculative Actions (ICLR 2026): https://arxiv.org/abs/2510.04371
- Skyvern 2.0 (updated 30 Sep 2026): https://www.skyvern.com/blog/skyvern-2-0-webvoyager-benchmark-results/
- Web Bench (May 2025): https://www.halluminate.ai/blog/benchmark
- Stagehand v4, "Evolving computer use with code" (9 Sep 2026): https://browserbase.com/blog/evolving-computer-use-with-code ; Stagehand v3 docs: https://docs.stagehand.dev/v3/basics/act
- Playwright MCP: https://github.com/microsoft/playwright-mcp
- Surfer 2: https://arxiv.org/html/2510.19949v2
- OpenAI prompt caching guide: https://developers.openai.com/api/docs/guides/prompt-caching
- WebArena aggregations (Jun 2026): https://leaderboard.steel.dev/leaderboards/webarena ; OpAgent: https://arxiv.org/html/2602.13559
