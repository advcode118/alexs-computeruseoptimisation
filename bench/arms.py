"""Benchmark arms for script-first execution and browser baselines."""

from __future__ import annotations


ARM_PLAYWRIGHT = "playwright_mcp"
ARM_STAGEHAND = "stagehand"
ARM_SCRIPT_FIRST = "script_first"
ARM_BROWSER_USE = "browser_use"

ARMS = (ARM_SCRIPT_FIRST, ARM_BROWSER_USE, ARM_PLAYWRIGHT)
BASELINE_ARMS = (ARM_PLAYWRIGHT, ARM_BROWSER_USE)
SELECTABLE_ARMS = ARMS + (ARM_STAGEHAND,)
# One script, one repair, and completion turns.
SCRIPT_FIRST_MAX_CALLS = 4
# A FAIL gets a grounded repair: the live page, the failed step, and how far
# the script got. Up to SCRIPT_FIRST_MAX_REPAIRS of them, each continuing from
# the current page, while the task is under SCRIPT_FIRST_REPAIR_BUDGET_S of
# wall time. A first script that passes never reaches any of this.
SCRIPT_FIRST_MAX_REPAIRS = 1
SCRIPT_FIRST_REPAIR_BUDGET_S = 30.0
SCRIPT_FIRST_MAX_SCRIPTS = 1 + SCRIPT_FIRST_MAX_REPAIRS
SCRIPT_FIRST_HARD_CAP = SCRIPT_FIRST_MAX_SCRIPTS + 2


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

_BROWSER_USE_PROMPT = """You are a browser automation agent. You write Python in one persistent REPL. The REPL drives the local Chrome already attached, over the Chrome DevTools Protocol.

Guidelines:
- Stay on that local browser.
- Finish the task that was given, then stop.
- When the task is complete, finish with the value it asked for.
- If it cannot be done, finish and say the task failed.

Be efficient - write the steps in the REPL, then stop."""


def arm_needs_claude(arm: str) -> bool:
    """All selectable arms use an outer model."""
    if arm not in SELECTABLE_ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    return True


def prompt_for(arm: str) -> str:
    """System prompt for the outer model."""
    from bench.harness import SYSTEM_PROMPT

    if arm == ARM_PLAYWRIGHT:
        return SYSTEM_PROMPT
    if arm == ARM_STAGEHAND:
        return _STAGEHAND_PROMPT
    if arm == ARM_SCRIPT_FIRST:
        return _SCRIPT_FIRST_PROMPT
    if arm == ARM_BROWSER_USE:
        return _BROWSER_USE_PROMPT
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
    if arm == ARM_BROWSER_USE:
        from bench.browser_use_arm import BrowserUseClient

        return BrowserUseClient(headless=headless)
    from bench.harness import PlaywrightMCPClient

    if arm == ARM_PLAYWRIGHT:
        return PlaywrightMCPClient(headless=headless, snapshot_mode="full")
    raise ValueError(f"unknown arm {arm!r}")
