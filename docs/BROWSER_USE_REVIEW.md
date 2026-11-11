# What script_first can take from browser-use 1.0

Reviewed 10 Nov 2026 from the open-source tree at tag `1.0.1`, commit `693ddd2069d50b41baa3dd48335c9a2265379db8` (https://github.com/browser-use/browser-use). The same-day `1.0.0` tag already contains `AxHelpers`. No harness code changes in this note. No live probe was run for it. The top ideas are not implemented here.

browser-use 1.0 is a Pydantic AI agent. The model writes Python into one persistent REPL. The REPL drives Chrome through the browser-harness daemon and raw CDP. `mode='ultrafast'` adds accessibility-tree ids. Our `browser_use` arm already runs that library on local Chrome with `claude-sonnet-5-5`. It does not pass `mode=`. `Agent.__init__` (`browser_use/agent/service.py`) turns ultrafast on only for the gateway aliases `bu-fast` and `bu-ultrafast`. `ChatAnthropic` stays on `mode='default'`. The seconds below are that default REPL, not ultrafast.

## Measured timings

Honest probe on PR #18 (`cursor/honest-live-probe-6b25` at `f89b16a`). Probe spend $3.24. Ledger now $19.884194. These are the only timings used here. Differences of those reported figures are arithmetic, not a new run. Comments inside browser-use (a model call "~1 s", a headless `mouseMoved` of "~5 s", an OpenAI stored response "170–320 ms" later, Google Flights 0/3 versus 3/3) are their notes. They are not measurements of this probe.

Cold, 18 tasks:

| Arm | Passes | Mean | Median | Shape |
| --- | --- | --- | --- | --- |
| script_first | 17/18 | 2.85s | 2.81s | 17 one-shot, 1 repair |
| browser_use | 17/18 | 4.76s | 4.39s | default REPL, local CDP |
| playwright_mcp | 18/18 | 5.71s | 3.86s | |
| stagehand | 17/18 | 13.42s | 5.75s | |

script_first warm replay: 17/18 at 1.80s mean / 1.22s median.

Cold script_first mean is 1.91s under the browser_use mean (4.76 − 2.85). Warm mean is 1.05s under cold script_first (2.85 − 1.80). Warm median is 1.59s under the cold median (2.81 − 1.22). The fastest measured path is a judged script with no model call. The next fastest cold path is one Playwright script. The persistent REPL, already wired up as an arm, is slower on both mean and median.

A grading mismatch means these pass counts are not yet one rule. Wall time is still wall time. Passes are not.

- script_first is a pass only when `end_state == PASS` from `evidence_verdict` (`bench/probe.py` `run_claude_arm`). A FAIL is not rescued by the URL or text check. UNKNOWN is a failure, and it does not ask for a repair.
- playwright_mcp and stagehand pass when the harness says so and, if the task has `check_url_contains` or `check_text`, `deterministic_success` agrees. The model can end the task itself.
- browser_use passes only through `browser_use_arm._judge`, which calls `deterministic_success` on the live URL and body text. There is no evidence verdict, no claimed answer, and no `selector_text` check.

17/18 against 18/18 is three rules. These numbers are not a reason to soften `evidence_verdict`, to treat UNKNOWN as a pass, or to let a substring check override a FAIL.

## Where the speed actually is

On this set the model round trip is the clock. M0, recorded in `docs/HISTORY.md`, was 87% model time. script_first spends one call on 17 of 18 cold passes: `_SCRIPT_FIRST_PROMPT` in `bench/arms.py` tells the model to finish in one `run_script`, and the runner does not settle or snapshot between actions. browser-use's own `AX_PROMPT` says the same thing in one sentence: each model call is costly, so chain the work you already know into one `python` call. script_first already does that, and it skips the look that a REPL loop takes before it can act.

Warm replay is faster still because `ScriptCache` runs a script that `evidence_verdict` already passed, with no model call, and judges it again. browser-use's `checkpoint()` stores a partial JSON result for a crashed run. It is not a replayed script. Nothing in this review beats the measured 1.80s / 1.22s path.

## The six mechanisms

### 1. Prompt caching

**Where.** `build_agent` in `browser_use/agent/loop.py`. For an Anthropic model, if the caller did not set `cache`, it sets `settings['cache'] = True`. The comment records why: Anthropic caches nothing unless asked, and their `cache_read` had been 0 on every Claude run. Pydantic AI's unified cache flag caches the system prompt, the tool definitions, and the conversation so far. `usage_and_cost` in the same file sums `cache_read` and `cache_write`. A caller-supplied `anthropic_cache*` or `cache` value is left alone.

The OpenAI Responses branch of `build_agent` sets `openai_store` false. Their comment says a stored response came back 170–320 ms later. This harness calls Anthropic. That branch is not our path.

**Wall time.** Unmeasured here. A cache hit still runs the model. The 1.05s mean gap from cold 2.85s to warm 1.80s is the whole call disappearing, which a cache hit does not do. The piece a hit can move is prefill of the stable prefix, on the second and later requests inside the cache window. The first task of a process pays the write. `_SCRIPT_FIRST_PROMPT` is short, so the slice of the 2.81s one-shot median is small. Across a probe the same prefix is sent on every cold script, on the one repair, and on a warm patch.

**Our harness.** `bench/` sets no Anthropic cache breakpoint (no `cache_control` anywhere under `bench/`). The stable prefix is `_SCRIPT_FIRST_PROMPT` plus the `run_script` tool schema, and `PATCH_PROMPT` plus `patch_step` on the warm miss. Task text and page evidence stay uncached. The evidence judge does not read token bills. Caching the prefix does not change PASS, FAIL, or UNKNOWN.

**Licence.** Reimplement the breakpoint. `build_agent` is MIT (`Copyright (c) 2024 Gregor Zunic`, in the browser-use `LICENSE`) and is bound to Pydantic AI. Copying it would drag that agent in. A later change is a cache marker on our own system prompt and tool schema.

### 2. How page state is built

**Where.** Two different builders.

Default mode, which the probe ran: `SYSTEM_PROMPT` in `browser_use/agent/prompt.py` tells the model to call `cdp('Accessibility.getFullAXTree')` and filter the nodes in Python before printing. The library does not build that tree for it. `page_info()` is the browser-harness helper, documented there as `{url, title, w, h, sx, sy, pw, ph}` or `{dialog}`. `browser_use/repl/page_info.py` `install` only wraps it so a new document has an `<html>` element first. The prompt also says not to spend a turn on a lone `js()`, `page_info()`, or `screenshot()`.

Ultrafast: `AxHelpers.state` in `browser_use/ax.py` builds one capped string. `state(max=3000)` settles, then `_capture` calls `Accessibility.getFullAXTree` on the main frame and each same-process child frame. The walk prints `[backendDOMNodeId] role "name"`, heading lines, and visible text. `VISIBLE_JS` drops text that `checkVisibility` says is hidden, so an opacity-0 banner is not reported as success. A `*` marks ids that were absent from `self.last` on the previous print. `worker.main` in `browser_use/repl/worker.py` calls `bu.state()` in the cell's `finally` when `bu.acted` is set, so the action's result is in that cell's output and the next model turn is not a look.

**Wall time.** Default-mode state is inside the 4.76s / 4.39s arm: the model writes the read. Ultrafast's automatic print has no timing on these 18 tasks. Putting a look before the first script would add a model turn on the 17 one-shots. Those one-shots are the 2.81s median. The repair is 1 of 18, so a richer failure line cannot move that median.

**Our harness.** On a FAIL the model already receives `format_run_result`: live URL, title, h1, page text capped at 4000 characters, and the script's own `claimed` values. `model_visible_script_result` then drops `selector_text` and `controls`, and `repair_request` adds the FAIL reason and the URL again. `patch_request` sends URL, title, h1, and 2000 characters of text, and leaves `selector_text` and the claim out of that prompt. Copying title and text into `repair_request` repeats the tool result. The field browser-use prints and this harness withholds is the role/name list (`controls`), because `page_fingerprint` hashes it. `selector_text` is the judge's read of `answer_equals_selector` and stays out of the model message. Showing `controls` on the repair would reverse that rule. This probe does not show that the hidden list cost the one repair.

`AxHelpers.settle` waits until the document is parsed, in-flight requests older than 1.5s are ignored, and the DOM has been quiet for `quiet_ms` (default 80), with an 800ms cap on an action and a longer cap while `readyState` is `loading`. script_first dropped per-action waits. Navigation waits for DOMContentLoaded. Adding this settle on the hot path spends time the runner currently does not spend. The proxy settle loop was parked because it did not remove model round trips.

**Licence.** `AxHelpers` is a Python port of Browser Use Pi's `src/ax.ts` (the module docstring says so) and ships under the same MIT notice. Copying `state` copies that port. A later failure string, if one is needed, comes from the `_PAGE_EVIDENCE_JS` fields the model is already allowed to see. `SYSTEM_PROMPT` and `AX_PROMPT` stay in their repo. Pasting them would also tell the model to grade itself, which fights `evidence_verdict`.

### 3. Ultrafast accessibility-tree ids

**Where.** `AxHelpers` in `browser_use/ax.py`, installed when `BU_MODE=ultrafast` (`Repl._start` in `browser_use/repl/session.py`, `worker._install`). `state` records `backendDOMNodeId` for roles in `CONTROLS` and for focusable named nodes. `click(id)` and `type(id, text)` resolve that id: `DOM.scrollIntoViewIfNeeded`, then `_point` via `DOM.resolveNode` and `Runtime.callFunctionOn`, then `Input.dispatchMouseEvent` press and release. `_click_at` sends no `mouseMoved`. Their comment says a background headless tab answers `mouseMoved` after about 5 seconds. `type` focuses the node, selects all, and inserts text. CDP commands also take `backendNodeId` directly (`AX_PROMPT`). Ids are Chrome backend node ids. `AX_PROMPT` says they expire after navigation.

`Agent.__init__` records their own eval note: Google Flights was 0/3 in default mode and 3/3 in ultrafast. That is their note, not this probe.

**Wall time.** No ultrafast number on these 18 tasks. The 2.81s median is one-shot scripts that prefer `page.goto` of the finished URL, so they never need a live id. Ids can matter on the single repair, and only when that repair continues on the same document and a role/name locator was the miss. They cannot move the one-shot median. The 5-second `mouseMoved` note is not visible in that 2.81s median, so script_first is not sitting on it.

**Our harness.** A live id belongs in one repair's page read, if a later change adds it. It does not belong in `ScriptCache` or in `page_fingerprint`. The fingerprint is host plus a hash of role/name pairs, which survive navigation. An id does not. The stored script stays Playwright (`page.goto`, `getByRole`, `getByLabel`, `getByText`, `getByPlaceholder`, `page.evaluate`). The evidence judge keeps reading the live page. An id is a way to act, not a way to score.

**Licence.** Reimplement a "resolve this backend node id and click its box" helper if a later PR has a measured miss that needs it. Copying `AxHelpers` means copying the Pi port and taking a dependency on the browser-harness daemon. MIT allows the copy if the copyright and permission notice travel with it. The effort is the port, not the licence.

### 4. Direct CDP

**Where.** `Browser` and `_daemon_cdp` in `browser_use/browser/browser.py`. `_daemon_cdp` sends one command through `_daemon_request`, which calls `browser_harness._ipc`. In the worker, `_install` does `from browser_harness.helpers import *` and wraps the agent's `cdp()` as `agent_cdp`. `Browser('chromium')` is the local Chrome our arm already constructs (`run_browser_use_task`). The websocket and the daemon live in browser-harness 0.1.13, the pin in browser-use's `pyproject.toml`. This review did not read that package's source. Its `LICENSE` on GitHub main is MIT, Copyright (c) 2026 Browser Use.

**Wall time.** The arm that already uses this driver measured 4.76s mean / 4.39s median, against Playwright script_first at 2.85s / 2.81s. There is no split of Playwright overhead inside the 2.85s. Swapping the one-shot runner from Playwright to raw CDP has no supporting speed number. The driver is not what makes the 4.76s arm slower. The extra model turns are.

**Our harness.** script_first runs the Playwright Python API (`ScriptFirstClient`, locators, `page.evaluate`). playwright_mcp stays on `@playwright/mcp`. A CDP daemon would be a new transport under the same script and the same judge. The cached script would still be Playwright source, or the cache format would change and every stored script would miss. That is a large change for an unmeasured gain.

**Licence.** Leave the daemon as a dependency of the existing `browser_use` arm. Do not vendor browser-harness into this repo. A reimplementation of `_daemon_cdp` is a second CDP client beside Playwright. MIT would allow copying `_daemon_cdp` with the notice. The symbol is a thin wrapper. The daemon it calls is the other project.

### 5. The persistent REPL

**Where.** `Repl` in `browser_use/repl/session.py` starts `python -m browser_use.repl.worker` and talks JSON lines over a localhost socket. `worker.main` builds one `ns` dict and `exec`s every cell into it, so variables, imports, and functions survive. A normal Python or CDP error is returned in the cell result and the namespace stays (`SYSTEM_PROMPT`). A timeout kills the worker. `RESTARTED` in `session.py` says Python variables are then gone and the browser, files, and checkpoints survive. `python` in `browser_use/agent/loop.py` is the one tool. It runs `repl.call('exec', code, timeout)`. `Session` in that file is the Pydantic AI deps object, not the REPL. Cells are sequential (`Tool(python, sequential=True)` in `build_agent`).

**Wall time.** This is the architecture of the 4.76s / 4.39s arm. Moving the cold path onto it would spend the 1.91s mean gap. The session across cells is what makes a multi-step loop possible. script_first already chains the whole task in one script, which is the part of the design that is fast. The browser for one task already stays up across the single repair: one `BenchmarkHarness` per task, two scripts at most.

**Our harness.** Keep `run_script` as one Playwright script. Keep the warm tier as `ScriptCache`: store only after PASS, replay with no model call, one `patch_step` when the replay fails. A Python namespace that accumulates across tasks would let a later script see an earlier page's variables. The cache key is task intent plus site (`cache_key`), and the fingerprint is the live control list. A leftover REPL variable is not a substitute for either check.

**Licence.** Reimplement nothing here. `Repl` and `worker.main` are the agent. Copying them copies browser-use. MIT would require the notice for any substantial copy. The `browser_use` arm already imports the library. That is the right place for this session model.

### 6. Retries and repair

**Where.** Three different mechanisms, all in `browser_use/agent/loop.py` unless noted.

- `BrowserLoop.on_model_request_error` retries one transient provider failure per run (`provider_retried`). Rate limit, overload, 5xx, dropped connection. It waits for `Retry-After`, capped at 60s, and it will not sleep into the delivery turn. It does not retry when the provider SDK already retried (the comment names OpenAI and Anthropic `max_retries=2`).
- `check_delivery` allows one repair of a placeholder result or a link to a file that is not in the workspace (`checked_delivery`). On the last request it delivers the bad result anyway and logs. `check_split_delivery` refuses a finish that shares its response with another tool call, once per run.
- `TOOL_RETRIES` in `browser_use/tools.py` is `1_000_000`. A rejected `python` call is given back to the model. `max_steps` is the bound. The worker catches the exception, keeps `ns`, and returns the error text. `SYSTEM_PROMPT` says a failed call may have run part way, so the model should inspect and must not automatically replay uncertain actions.

**Wall time.** On the 17 one-shot passes, none of this runs. A provider retry adds latency only when a request failed. It can save a task that would otherwise die on a 5xx. It does not lower the 2.81s median. `check_delivery`'s last-step accept would count an empty delivery as success. That changes the score. It is not a speed feature.

**Our harness.** script_first already has one repair: `repair_request`, sent only on FAIL, at most once (`repairs_sent < 1` in `bench/harness.py`). UNKNOWN does not repair. A cached miss gets one `patch_step`, which replaces one numbered step. The PASS-only store matches their "do not automatically replay uncertain actions": a script that mutated and then failed is not written as a hit. `ScriptCache` replays only a script the judge passed, and the replay is judged again.

Keep that shape. A provider retry belongs in the HTTP client, once, and only for a transport or 5xx failure that returned no tool call. It must not retry a FAIL, and it must not turn UNKNOWN into a second script.

**Licence.** Reimplement a single transient retry if a later probe shows requests dying on 5xx. Do not copy `BrowserLoop` or `check_delivery`. The last-step accept is the behaviour this harness refuses: a weak delivery is not a pass.

## Rank by speed gain per effort

None of the six approaches the measured warm path (1.80s mean / 1.22s median). The rank is among changes that are smaller than that, using the cold gap of 1.91s mean as the cost of adopting the REPL.

| Rank | Idea | Expected wall time | Effort |
| --- | --- | --- | --- |
| 1 | Anthropic cache breakpoint on the stable prompt and tool schema | A small, unmeasured slice of prefill on every call after the first. Does not remove the call. The 1.05s cold-to-warm mean gap is the call going away. | Low. One marker on our own prompt. No judge change. |
| 2 | backend node ids on the one FAIL repair | Cannot move the 2.81s median. The repair is 1 of 18, and only if a locator missed on the current document. Ultrafast has no timing on this set. The FAIL tool result already has URL, title, h1, and text. | Medium. Ids stay out of `ScriptCache`. `controls` stays off the model message unless a later review changes that rule on purpose. |
| 3 | Their capped state print, as a second copy of the page | About zero. `format_run_result` already returns the page. An extra look before the first script adds a turn to the 17 one-shots. | Low to do, and the speed cost of doing it on the cold path is a model turn. |
| 4 | One transient provider retry | No change on the 17 one-shot successes. Adds time only when a request failed with no tool call. | Low, and easy to get wrong. Must not retry a FAIL or repair an UNKNOWN. |
| 5 | Replace Playwright with the direct CDP daemon | The CDP arm measured 4.76s / 4.39s. No separate measurement of Playwright overhead inside 2.85s. | High. New transport, same scripts, same judge. browser-harness stays a dependency of the baseline arm. |
| 6 | Persistent REPL as the cold path | The measured REPL is 1.91s mean slower (4.76 − 2.85) and 1.58s median slower (4.39 − 2.81). | High. This is the `browser_use` arm. It already exists. |

Rank 1 is the only item that can touch the 17 one-shots without adding a turn. Rank 2 is a conditional pass-rate change on one task, and it is not a reason to show `selector_text`. Ranks 5 and 6 are how the slower arm is built.

## What a later implementation would change

A follow-up that takes rank 1 sets an Anthropic cache breakpoint on the stable system prompt and the tool schema for `run_script` and `patch_step`. Task text, page evidence, and judge markers stay outside it. The ledger keeps pricing tokens at $3/$15 per million. Cache reads are still input tokens. They are not free in the ledger unless the bill says so, and this note does not change the price.

A follow-up that takes rank 2 needs a measured repair whose locator missed on the current page. It leaves `evidence_verdict` on PASS / FAIL / UNKNOWN. UNKNOWN still does not repair. A FAIL still repairs once. `selector_text` stays in the judge and out of the model message. `controls` stays out of the model message unless that follow-up says why the fingerprint list should be visible.

This PR does neither. It does not change the harness, the judge, the cache, or the probe. It does not merge.
