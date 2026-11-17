"""The four computer-use arms share timeouts, a browser, the probe model, and one page read."""

from __future__ import annotations

import asyncio
from pathlib import Path

from bench.fairness import (
    ACTION_TIMEOUT_MS,
    ARM_RUN_TIMEOUT_S,
    BROWSER,
    EVALUATE_TIMEOUT_S,
    LAND_TIMEOUT_S,
    MODEL_HTTP_TIMEOUT_S,
    NAV_TIMEOUT_MS,
    PAGE_READ_TIMEOUT_S,
    SETTLE_TIMEOUT_MS,
    chrome_launch_attempts,
)
from bench.harness import playwright_mcp_args
from bench.openai_spend import OpenAIModelNotAllowed, assert_openai_model
from bench.script_first import _PAGE_EVIDENCE_JS, marked_selector_source

ROOT = Path(__file__).resolve().parents[1]


def test_shared_timeouts_are_the_longer_ones():
    assert MODEL_HTTP_TIMEOUT_S == 120
    assert NAV_TIMEOUT_MS == 60_000
    assert ACTION_TIMEOUT_MS == 30_000
    assert EVALUATE_TIMEOUT_S == 30
    assert SETTLE_TIMEOUT_MS == 3_000
    assert LAND_TIMEOUT_S == 3.0
    assert PAGE_READ_TIMEOUT_S == EVALUATE_TIMEOUT_S
    assert ARM_RUN_TIMEOUT_S == 30 * MODEL_HTTP_TIMEOUT_S
    assert ARM_RUN_TIMEOUT_S > 1700


def test_playwright_mcp_uses_chrome_and_the_shared_timeouts():
    args = playwright_mcp_args(headless=True, snapshot_mode="full")
    assert args[:3] == ["npx", "@playwright/mcp@0.0.84", "--isolated"]
    assert "--user-data-dir" not in args
    assert args[args.index("--browser") + 1] == BROWSER == "chrome"
    assert args[args.index("--timeout-action") + 1] == str(ACTION_TIMEOUT_MS)
    assert args[args.index("--timeout-navigation") + 1] == str(NAV_TIMEOUT_MS)
    assert args[args.index("--timeout-settle") + 1] == str(SETTLE_TIMEOUT_MS)


def test_playwright_arms_share_the_chrome_launch():
    assert chrome_launch_attempts(True)[0]["channel"] == "chrome"
    assert "channel" not in chrome_launch_attempts(True)[1]
    for name in ("bench/script_first.py", "bench/stagehand_local.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "chrome_launch_attempts" in text
        assert '{"channel": "chrome"' not in text


def test_page_text_call_is_the_same_function():
    from bench.browser_use_arm import PAGE_TEXT_EXPRESSION, selector_expression

    assert PAGE_TEXT_EXPRESSION == f"({_PAGE_EVIDENCE_JS})()"
    selector = ".titleline a"
    assert selector_expression(selector) == f"({marked_selector_source(selector)})()"
    assert "selector_text" not in PAGE_TEXT_EXPRESSION
    assert "selector_text" not in selector_expression(selector)


def test_openai_model_stays_the_probe_model():
    assert assert_openai_model("gpt-6.1-sol") == "gpt-6.1-sol"
    assert assert_openai_model("gpt-6-luna") == "gpt-6-luna"
    try:
        assert_openai_model("gpt-6-sol")
    except OpenAIModelNotAllowed:
        return
    raise AssertionError("an OpenAI model outside the two allowed names was accepted")


def test_browser_use_is_given_the_probe_model(monkeypatch):
    from tests.test_browser_use_arm import _World
    from bench.browser_use_arm import run_browser_use_task

    monkeypatch.setattr("bench.browser_use_arm.google_chrome_executable", lambda: None)
    world = _World(page_url="https://example.test/done", page_text="visible")
    row = asyncio.run(
        run_browser_use_task(
            {"id": "t", "description": "Read the page", "start_url": "https://example.test/"},
            api_key="local-test-not-sent",
            model="gpt-6-luna",
            provider="openai",
            effort="low",
            loader=world.loader,
        )
    )
    assert world.calls[1][1] == "gpt-6-luna"
    assert row["model"] == "gpt-6-luna"
    assert world.calls[0][1] == "chromium"
    assert world.calls[0][4] is None
    assert world.calls[3] == ("run", 30, ARM_RUN_TIMEOUT_S)
