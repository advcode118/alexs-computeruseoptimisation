"""Stagehand arm and the unlaunched probe. No browser, no API key, no network."""

from __future__ import annotations

import asyncio
import json

from bench.arms import ARMS, arm_needs_claude, prompt_for
from bench.harness import BenchmarkHarness
from bench.probe import (
    PROBE_CLAUDE_BUDGET_USD,
    claude_block_reason,
    main,
    plan_probe,
    snapshot_is_huge,
)
from bench.stagehand_local import (
    StagehandLocalClient,
    actions_to_script,
    describe_backend,
)
from proxy.script import parse_script


class _Locator:
    def __init__(self, log: list, name: str):
        self.log = log
        self.name = name

    async def click(self):
        self.log.append(("click", self.name))

    async def fill(self, value):
        self.log.append(("fill", self.name, value))

    async def press(self, value):
        self.log.append(("press", self.name, value))

    async def check(self):
        self.log.append(("check", self.name))

    async def uncheck(self):
        self.log.append(("uncheck", self.name))


class _Page:
    def __init__(self):
        self.log: list = []

    def get_by_role(self, role, name=None):
        del role
        return _Locator(self.log, name or "")

    def get_by_label(self, name):
        return _Locator(self.log, name)

    def get_by_text(self, name):
        return _Locator(self.log, name)

    def get_by_placeholder(self, name):
        return _Locator(self.log, name)

    async def goto(self, url):
        self.log.append(("goto", url))

    async def evaluate(self, source):
        if "quietMs" in source or "MutationObserver" in source:
            return '{"settled": true, "reason": "quiet"}'
        return {"chars": 24, "nodes": [{"role": "button", "name": "Add"}, {"role": "textbox", "name": "Item"}]}

    async def screenshot(self, type="png"):
        del type
        return b"png-bytes"


def test_arms_share_the_outer_model_and_stagehand_stays_local(monkeypatch):
    monkeypatch.delenv("BROWSERBASE_API_KEY", raising=False)
    monkeypatch.delenv("BROWSERBASE_PROJECT_ID", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ARMS == ("playwright_mcp", "diff_fast_act", "macro_replay", "stagehand")
    assert arm_needs_claude("playwright_mcp") is True
    assert arm_needs_claude("stagehand") is True
    assert arm_needs_claude("diff_fast_act") is False
    assert arm_needs_claude("macro_replay") is False
    assert "getByRole" in prompt_for("stagehand")
    assert "do_task_segment" in prompt_for("macro_replay")
    assert "fast_act" in prompt_for("diff_fast_act")
    assert "browser_snapshot" in prompt_for("playwright_mcp")
    backend = describe_backend()
    assert backend["backend"] == "local"
    assert backend["browserbase"] == "unset"
    harness = BenchmarkHarness(api_key="local-test", arm="stagehand")
    assert harness.model == "claude-sonnet-4-6"
    assert [tool["name"] for tool in StagehandLocalClient().tools_for_claude()] == [
        "snapshot",
        "run",
        "screenshot",
    ]


def test_run_accepts_a_playwright_script_and_a_structured_list():
    page = _Page()
    client = StagehandLocalClient(page=page)
    text, _ms = asyncio.run(
        client.call_tool(
            "run",
            {"code": 'page.getByLabel("Item").fill("milk")\npage.getByRole("button", { name: "Add" }).click()'},
        )
    )
    assert ("fill", "Item", "milk") in page.log
    assert ("click", "Add") in page.log
    assert "settle: quiet" in text
    assert "diff_chars:" in text
    assert "full_snapshot_chars:" in text
    script = actions_to_script(
        [
            {"op": "goto", "url": "https://example.com/"},
            {"op": "fill", "role": "textbox", "name": "Item", "value": "socks"},
        ]
    )
    parsed = parse_script(script, allow_goto=True)
    assert parsed[0].op == "goto"
    assert parsed[1].op == "fill"
    assert parsed[1].value == "socks"


def test_probe_plan_does_not_execute_and_caps_claude(capsys):
    plan = plan_probe()
    assert plan["execute"] is False
    assert plan["tasks"] == ["wv_wikipedia_search", "wv_python_docs", "wv_hackernews_top"]
    assert plan["claude_arms"] == ["playwright_mcp", "stagehand"]
    assert plan["no_model_arms"] == ["diff_fast_act", "macro_replay"]
    assert plan["outer_model"] == "claude-sonnet-4-6"
    assert plan["claude_budget_usd"] == PROBE_CLAUDE_BUDGET_USD == 5.0
    assert plan["project_spent_usd"] == 9.645
    assert snapshot_is_huge("x" * 40_001) is True
    assert snapshot_is_huge("short") is False
    assert claude_block_reason(5.0, 9.645)
    assert claude_block_reason(0.0, 40.0)
    assert claude_block_reason(4.9, 9.645) is None
    assert main([]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["execute"] is False
    assert "opus" not in json.dumps(printed).lower()
