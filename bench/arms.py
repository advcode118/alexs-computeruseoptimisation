"""Benchmark arms. The outer model, when one is used, is claude-sonnet-4-6.

plain Playwright MCP is the weak comparison. Stagehand's snapshot/run/screenshot
tools are the one that matters. diff_fast_act and macro_replay are the proxy:
the tools themselves do not call Claude. Nebius is used only when a key is
already set, and only inside do_task_segment's existing fallback.
"""

from __future__ import annotations

import sys

ARM_PLAYWRIGHT = "playwright_mcp"
ARM_DIFF = "diff_fast_act"
ARM_REPLAY = "macro_replay"
ARM_STAGEHAND = "stagehand"

ARMS = (ARM_PLAYWRIGHT, ARM_DIFF, ARM_REPLAY, ARM_STAGEHAND)

# These two need an outer model to choose tools. The proxy arms can finish a
# task through decide(), replay, or a locator script with no Claude call.
CLAUDE_ARMS = frozenset({ARM_PLAYWRIGHT, ARM_STAGEHAND})

_DIFF_PROMPT = """You are a browser automation agent. Tools include fast_act, do_task_segment, and the forwarded Playwright tools.

Guidelines:
- Prefer fast_act for one obvious action. Pass script when you can write the locator lines yourself, for example page.getByRole("button", { name: "Search" }).click().
- After an action the tool returns a compact diff (full_snapshot_chars and diff_chars). Do not call browser_snapshot if you already have that diff.
- A full-page browser_snapshot after a diff is wasted. Use the diff, or a targeted snapshot with a target, instead.
- When the task is complete, respond with TASK_COMPLETE.
- If you cannot complete the task, respond with TASK_FAILED and explain why.

Be efficient - try to complete the task in as few steps as possible."""

_REPLAY_PROMPT = """You are a browser automation agent. Tools include do_task_segment, fast_act, and the forwarded Playwright tools.

Guidelines:
- Prefer do_task_segment for the whole sub-task. A stored sequence for this domain and page can replay with no model call.
- You may pass script, one Playwright locator action per line, instead of a structured action list.
- After an action the tool returns a compact diff. Do not call browser_snapshot if you already have that diff.
- When the task is complete, respond with TASK_COMPLETE.
- If you cannot complete the task, respond with TASK_FAILED and explain why.

Be efficient - one do_task_segment call is better than a click and a snapshot per step."""

_STAGEHAND_PROMPT = """You are a browser automation agent. The tools are snapshot, run, and screenshot. They match Stagehand's tool surface and run on local Playwright.

Guidelines:
- snapshot reads the interactive elements and labels them with ids.
- Prefer run with a short Playwright-style script: page.getByRole("button", { name: "Search" }).click(). One run call may contain several lines. Structured actions are accepted and are the weaker choice.
- page.goto("https://...") is allowed inside run. Do not use page.evaluate.
- run returns a compact diff. Do not call snapshot again if that diff is enough.
- screenshot is a rendered image and is not inlined into the conversation. Use it only when the text snapshot cannot answer.
- When the task is complete, respond with TASK_COMPLETE.
- If you cannot complete the task, respond with TASK_FAILED and explain why.

Be efficient - batch the browser steps into one run call."""


def arm_needs_claude(arm: str) -> bool:
    """True when the arm cannot act without the outer Claude model."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    return arm in CLAUDE_ARMS


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
    raise ValueError(f"unknown arm {arm!r}")


def build_client(arm: str, *, headless: bool = True):
    """The tool client for this arm. Stagehand stays on local Playwright."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if arm == ARM_STAGEHAND:
        from bench.stagehand_local import StagehandLocalClient

        return StagehandLocalClient(headless=headless)
    from bench.harness import PlaywrightMCPClient

    if arm == ARM_PLAYWRIGHT:
        return PlaywrightMCPClient(headless=headless, snapshot_mode="full")
    return PlaywrightMCPClient(headless=headless, argv=[sys.executable, "-m", "proxy"])
