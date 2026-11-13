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
# Moving the page does not add a turn. The harness will not run a third script.
SCRIPT_FIRST_MAX_CALLS = 4
SCRIPT_FIRST_MAX_SCRIPTS = 2
SCRIPT_FIRST_HARD_CAP = 6

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

The first script must finish the task. Write one script for the whole task and call run_script once. You cannot see the page, so name things by the text a person sees on it.

Write the script:
- Go to a page with page.goto("https://..."). If you are sure of the URL of the page that holds the answer, go straight there. If not, go to the start URL and click or search your way there.
- Act with visible names: cu.click("Sign in"), cu.fill("Email", "a@b.c"), cu.press("Email", "Enter"). A button or link text, a label, a placeholder, or a clear part of one works. If several controls match, the first visible one is used.
- cu.search("words") types into the site's own search box and submits it. Then cu.click the result you want.
- The runner waits for each control to appear and for the page to settle after each action. Do not call page.waitForTimeout, page.waitForLoadState, page.waitForSelector, or networkidle; those lines are dropped.
- Allowed: page.goto, cu.click, cu.fill, cu.press, cu.search, page.locator, page.getByRole, page.getByLabel, page.getByText, page.getByPlaceholder (locators may use .first()/.nth() and a /regex/i name), and page.evaluate(() => { ... }) with a page-context function.
- End with one page.evaluate that reads the answer from the live page and returns it with cu.claim:
  page.evaluate(() => cu.claim({key_text: "a short phrase read from the page", answer: "the value the task asked for"}))
  cu.claim adds the url, title, and h1 itself. Read values from the page; do not type them from memory. cu.text("Label") returns the text shown next to a label, table header, or term, for example answer: cu.text("Population").
- The end page must be the page that holds the asked value. A start page or a search-results page is not the finished page unless the task asks for the results.
- browser_run_code_unsafe is not a tool. Do not ask for it.

After the script:
- If the tool result says END_STATE_FAILED, send one corrected script that lands on the finished page. Use the names listed in the error. Do not send a second repair.
- If the result already satisfies the task, the run stops. Do not call run_script again. If it cannot be done, call task_failed({reason: string}).

Be efficient - one script, at most one repair, then stop."""

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
