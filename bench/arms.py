"""Benchmark arms. The outer model is claude-sonnet-5-5. Opus is never used.

The competitive probe drives every arm with that outer model. plain Playwright
MCP is the weak comparison. Stagehand's snapshot/run/screenshot tools are the
one that matters. browser_use is the browser-use 1.0 baseline beside those
two: the model writes Python in one REPL on local Chrome over CDP, with the
same model string. It is selected with --arms. The default four stay put.
diff_fast_act and macro_replay expose the proxy: settle, a compact diff,
fast_act with a script, and do_task_segment. Those tools do not call Claude.
The outer loop does.

no_model_only is optional. It runs the two proxy arms through decide() with
no outer model. That path is not the competitive measurement. It cannot
close the Stagehand gap on open WebVoyager tasks. Nebius is used only when
a key is already set, and only inside do_task_segment's existing fallback.
"""

from __future__ import annotations

import sys

ARM_PLAYWRIGHT = "playwright_mcp"
ARM_DIFF = "diff_fast_act"
ARM_REPLAY = "macro_replay"
ARM_STAGEHAND = "stagehand"
ARM_SCRIPT_FIRST = "script_first"
ARM_ENDPOINT = "endpoint"
ARM_BROWSER_USE = "browser_use"

# The default probe stays these four. script_first, endpoint, and browser_use
# are selected with --arms. browser_use is a baseline beside plain Playwright
# MCP and Stagehand, not one of the four.
ARMS = (ARM_PLAYWRIGHT, ARM_DIFF, ARM_REPLAY, ARM_STAGEHAND)
# Stagehand is cut for now (11 Nov 2026). It is still selectable with --arms stagehand.
BASELINE_ARMS = (ARM_PLAYWRIGHT, ARM_BROWSER_USE)
SELECTABLE_ARMS = ARMS + (ARM_SCRIPT_FIRST, ARM_ENDPOINT, ARM_BROWSER_USE)
# One script and a completion turn. A repair may use the spare calls.
# Moving the page does not add a turn.
SCRIPT_FIRST_MAX_CALLS = 4
# A FAIL gets a grounded repair: the live page, the failed step, and how far
# the script got. Up to SCRIPT_FIRST_MAX_REPAIRS of them, each continuing from
# the current page, while the task is under SCRIPT_FIRST_REPAIR_BUDGET_S of
# wall time. A first script that passes never reaches any of this.
SCRIPT_FIRST_MAX_REPAIRS = 3
SCRIPT_FIRST_REPAIR_BUDGET_S = 30.0
SCRIPT_FIRST_MAX_SCRIPTS = 1 + SCRIPT_FIRST_MAX_REPAIRS
SCRIPT_FIRST_HARD_CAP = SCRIPT_FIRST_MAX_SCRIPTS + 2

# The proxy arms can still finish through decide(), replay, or a locator
# script when no_model_only is requested. The competitive probe does not.
NO_MODEL_CAPABLE = frozenset({ARM_DIFF, ARM_REPLAY})

_DIFF_PROMPT = """You are a browser automation agent. Tools include fast_act, do_task_segment, and the forwarded Playwright tools.

Guidelines:
- Prefer one fast_act script over many tiny steps. Pass script when you can write the locator lines yourself, for example page.getByRole("button", { name: "Search" }).click().
- After an action the tool returns a compact diff (full_snapshot_chars and diff_chars). Do not take a full snapshot after a diff was returned.
- A full-page browser_snapshot after a diff is counted as model_ignores_tools. Use the diff, or a targeted snapshot with a target, instead.
- When the task is complete, respond with TASK_COMPLETE.
- If you cannot complete the task, respond with TASK_FAILED and explain why.

Be efficient - try to complete the task in as few steps as possible."""

_REPLAY_PROMPT = """You are a browser automation agent. Tools include do_task_segment, fast_act, and the forwarded Playwright tools.

Guidelines:
- Prefer one do_task_segment, or one script, over many tiny browser_click, browser_type, and browser_snapshot steps. A stored sequence for this domain and page can replay with no model call.
- You may pass script, one Playwright locator action per line, instead of a structured action list.
- After an action the tool returns a compact diff. Do not take a full snapshot after a diff was returned. That call is counted as model_ignores_tools.
- When the task is complete, respond with TASK_COMPLETE.
- If you cannot complete the task, respond with TASK_FAILED and explain why.

Be efficient - one do_task_segment call is better than a click and a snapshot per step."""

_STAGEHAND_PROMPT = """You are a browser automation agent. The tools are snapshot, run, and screenshot. They match Stagehand's tool surface and run on local Playwright.

Guidelines:
- snapshot reads the interactive elements and labels them with ids.
- Prefer one run script over many tiny steps: page.getByRole("button", { name: "Search" }).click(). One run call may contain several lines. Structured actions are accepted and are the weaker choice.
- page.goto("https://...") is allowed inside run. Do not use page.evaluate.
- run returns a compact diff. Do not take a full snapshot after a diff was returned. That snapshot is counted as model_ignores_tools.
- screenshot is a rendered image and is not inlined into the conversation. Use it only when the text snapshot cannot answer.
- When the task is complete, respond with TASK_COMPLETE.
- If you cannot complete the task, respond with TASK_FAILED and explain why.

Be efficient - batch the browser steps into one run call."""

_SCRIPT_FIRST_PROMPT = """You are a browser automation agent. Use run_script to automate the browser.

Guidelines:
- The first script must finish the task. Call run_script once. Do not plan a second script.
- The end URL must be the finished page the task named. Do not stop on the start URL, and do not stop on a search-results URL when the task named a specific page.
- Prefer one page.goto of the finished page over clicking through the site. Put the whole navigation in the same script.
- A start page or a search-results page is not the finished page. Leave it for the page that holds the asked value.
- Allowed: page.goto("https://..."), page.locator, page.getByRole, page.getByLabel, page.getByText, page.getByPlaceholder (locators may use .first()/.nth()), cu.click("visible name"), cu.fill("visible name", "text"), cu.press("visible name", "Enter"), and page.evaluate(() => { ... }) with a page-context function.
- cu.click, cu.fill, and cu.press act on the one control with that visible name.
- End every script with one page.evaluate that returns evidence from the live page:
  page.evaluate(() => ({url: location.href, title: document.title, h1: document.querySelector("h1")?.innerText, key_text: "", values: [], answer: ""}))
  Put a phrase that is on the page in key_text and the value the task asked for in answer. cu.claim inside page.evaluate returns that object.
- Do not call page.waitForTimeout, page.waitForLoadState, page.waitForSelector, or networkidle. The runner drops those lines and does not settle or snapshot between actions.
- Do not click, type, or snapshot one element at a time.
- browser_run_code_unsafe is not a tool. Do not ask for it.
- If the tool result says END_STATE_FAILED, it shows the live page, the step that failed, and how far the script got. The browser stays on that page. Send one script that continues from there (or page.goto to start over), using the names and links shown.
- If the result already satisfies the task, the run stops. Do not call run_script again and do not send a separate completion turn. If it cannot be done, call task_failed({reason: string}).

Be efficient - one script that finishes the task. A repair only after END_STATE_FAILED."""

_ENDPOINT_PROMPT = """A direct read of the task start URL uses no model.

A miss falls through to the script_first arm. This arm does not launch a browser."""

_BROWSER_USE_PROMPT = """You are a browser automation agent. You write Python in one persistent REPL. The REPL drives the local Chrome already attached, over the Chrome DevTools Protocol.

Guidelines:
- Stay on that local browser.
- Finish the task that was given, then stop.
- When the task is complete, finish with the value it asked for.
- If it cannot be done, finish and say the task failed.

Be efficient - write the steps in the REPL, then stop."""


def arm_needs_claude(arm: str, *, no_model_only: bool = False) -> bool:
    """True when this arm is driven by the outer Claude model.

    Competitive runs pass no_model_only False, so every arm needs Claude.
    no_model_only True leaves diff_fast_act and macro_replay on decide().
    """
    if arm not in SELECTABLE_ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if arm == ARM_ENDPOINT:
        return False
    if no_model_only and arm in NO_MODEL_CAPABLE:
        return False
    return True


def prompt_for(arm: str) -> str:
    """System prompt for the outer model. Proxy arms still refuse Opus."""
    from bench.harness import SYSTEM_PROMPT

    if arm == ARM_PLAYWRIGHT:
        return SYSTEM_PROMPT
    if arm == ARM_DIFF:
        return _DIFF_PROMPT
    if arm == ARM_REPLAY:
        return _REPLAY_PROMPT
    if arm == ARM_STAGEHAND:
        return _STAGEHAND_PROMPT
    if arm == ARM_SCRIPT_FIRST:
        return _SCRIPT_FIRST_PROMPT
    if arm == ARM_ENDPOINT:
        return _ENDPOINT_PROMPT
    if arm == ARM_BROWSER_USE:
        return _BROWSER_USE_PROMPT
    raise ValueError(f"unknown arm {arm!r}")


def build_client(arm: str, *, headless: bool = True):
    """The tool client for this arm. Stagehand stays on local Playwright."""
    if arm not in SELECTABLE_ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if arm == ARM_ENDPOINT:
        from bench.endpoint import EndpointClient

        return EndpointClient()
    if arm == ARM_SCRIPT_FIRST:
        from bench.script_first import ScriptFirstClient

        return ScriptFirstClient(headless=headless)
    if arm == ARM_STAGEHAND:
        from bench.stagehand_local import StagehandLocalClient

        return StagehandLocalClient(headless=headless)
    if arm == ARM_BROWSER_USE:
        from bench.browser_use_arm import BrowserUseClient

        return BrowserUseClient(headless=headless)
    from bench.harness import PlaywrightMCPClient

    if arm == ARM_PLAYWRIGHT:
        return PlaywrightMCPClient(headless=headless, snapshot_mode="full")
    return PlaywrightMCPClient(headless=headless, argv=[sys.executable, "-m", "proxy"])
