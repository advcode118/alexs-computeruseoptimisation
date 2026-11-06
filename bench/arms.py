"""Benchmark arms. The outer model is claude-sonnet-5-5. Opus is never used.

The competitive probe drives every arm with that outer model. plain Playwright
MCP is the weak comparison. Stagehand's snapshot/run/screenshot tools are the
one that matters. diff_fast_act and macro_replay expose the proxy: settle,
a compact diff, fast_act with a script, and do_task_segment. Those tools do
not call Claude. The outer loop does.

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

# The default probe stays these four. script_first is selected with --arms.
ARMS = (ARM_PLAYWRIGHT, ARM_DIFF, ARM_REPLAY, ARM_STAGEHAND)
SELECTABLE_ARMS = ARMS + (ARM_SCRIPT_FIRST,)
# One script, one repair, a completion turn, and room for a turn that is
# still moving the page. The harness will not run a third script.
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

_SCRIPT_FIRST_PROMPT = """You are a browser automation agent. You get one tool, run_script.

Guidelines:
- Write one short Playwright script that finishes the whole task. The end URL must be the page the task asked for, or that page's search results. Do not stop on the start URL.
- Wikipedia: leave Main_Page. Fill the search box, submit the search, and finish on the article URL (it contains the article title, such as Ada_Lovelace) or on the search-results URL. Main_Page is not done.
- Hacker News: one script opens the site and reads the top story title with page.evaluate. Then reply with that title and TASK_COMPLETE. Do not open stories one by one.
- Allowed: page.goto("https://..."), page.getByRole, page.getByLabel, page.getByText, page.getByPlaceholder, and page.evaluate(() => { ... }) with a page-context function.
- Do not click, type, or snapshot one element at a time. The runner does not settle or snapshot between actions.
- browser_run_code_unsafe is not a tool. Do not ask for it.
- Call run_script. If the tool result says END_STATE_FAILED, send one corrected script. Do not send a second repair.
- On the turn after a script that reached the right page, respond with TASK_COMPLETE. If it cannot be done, respond with TASK_FAILED. Do not put TASK_COMPLETE in the same message as the tool call.

Be efficient - one script, at most one repair, then stop."""


def arm_needs_claude(arm: str, *, no_model_only: bool = False) -> bool:
    """True when this arm is driven by the outer Claude model.

    Competitive runs pass no_model_only False, so every arm needs Claude.
    no_model_only True leaves diff_fast_act and macro_replay on decide().
    """
    if arm not in SELECTABLE_ARMS:
        raise ValueError(f"unknown arm {arm!r}")
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
    raise ValueError(f"unknown arm {arm!r}")


def build_client(arm: str, *, headless: bool = True):
    """The tool client for this arm. Stagehand stays on local Playwright."""
    if arm not in SELECTABLE_ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if arm == ARM_SCRIPT_FIRST:
        from bench.script_first import ScriptFirstClient

        return ScriptFirstClient(headless=headless)
    if arm == ARM_STAGEHAND:
        from bench.stagehand_local import StagehandLocalClient

        return StagehandLocalClient(headless=headless)
    from bench.harness import PlaywrightMCPClient

    if arm == ARM_PLAYWRIGHT:
        return PlaywrightMCPClient(headless=headless, snapshot_mode="full")
    return PlaywrightMCPClient(headless=headless, argv=[sys.executable, "-m", "proxy"])
