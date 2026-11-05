"""Stagehand arm and the unlaunched probe. No browser, no API key, no network."""

from __future__ import annotations

import asyncio
import json

from bench.arms import ARMS, arm_needs_claude, prompt_for
from bench.budget import DEFAULT_SPEND_PATH
from bench.harness import BenchmarkHarness, playwright_mcp_args
from bench.probe import (
    BOX_COMMANDS,
    PROBE_CLAUDE_BUDGET_USD,
    claude_block_reason,
    empty_row,
    execute_probe,
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
    assert arm_needs_claude("diff_fast_act") is True
    assert arm_needs_claude("macro_replay") is True
    assert arm_needs_claude("diff_fast_act", no_model_only=True) is False
    assert arm_needs_claude("macro_replay", no_model_only=True) is False
    assert arm_needs_claude("stagehand", no_model_only=True) is True
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
    assert plan["mode"] == "outer_claude"
    assert plan["claude_arms"] == ["playwright_mcp", "diff_fast_act", "macro_replay", "stagehand"]
    assert plan["no_model_arms"] == []
    assert plan["no_model_only_arms"] == ["diff_fast_act", "macro_replay"]
    assert plan["outer_model"] == "claude-sonnet-4-6"
    assert plan["claude_budget_usd"] == PROBE_CLAUDE_BUDGET_USD == 5.0
    assert plan["project_spent_usd"] == 11.054514
    assert plan["box_commands"] == list(BOX_COMMANDS)
    assert "--isolated" in plan["browser_isolation"]["playwright_mcp"]
    assert "--user-data-dir" in plan["browser_isolation"]["stagehand"]
    opted = plan_probe(no_model_only=True)
    assert opted["mode"] == "no_model_only"
    assert opted["claude_arms"] == ["playwright_mcp", "stagehand"]
    assert opted["no_model_arms"] == ["diff_fast_act", "macro_replay"]
    assert snapshot_is_huge("x" * 40_001) is True
    assert snapshot_is_huge("short") is False
    assert snapshot_is_huge('{"full_snapshot_chars": 40001, "diff_chars": 12}') is True
    assert snapshot_is_huge("full_snapshot_chars: 40000\ndiff_chars: 8") is False
    assert claude_block_reason(5.0, 9.645)
    assert claude_block_reason(0.0, 40.0)
    assert claude_block_reason(4.9, 9.645) is None
    assert main([]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["execute"] is False
    assert printed["claude_arms"] == ["playwright_mcp", "diff_fast_act", "macro_replay", "stagehand"]
    assert "opus" not in json.dumps(printed).lower()


def test_each_arm_launch_is_a_private_browser(tmp_path, monkeypatch):
    """Sequential arms must not share the Playwright MCP profile lock."""
    import os

    from proxy.child import DEFAULT_CHILD_ARGV, NdjsonChild

    monkeypatch.delenv("PLAYWRIGHT_MCP_PROXY_CHILD", raising=False)

    plain = playwright_mcp_args(
        headless=True,
        snapshot_mode="full",
        user_data_dir=str(tmp_path / "plain"),
    )
    assert plain[:5] == [
        "npx",
        "@playwright/mcp@0.0.84",
        "--isolated",
        "--user-data-dir",
        str(tmp_path / "plain"),
    ]
    assert "--headless" in plain
    assert DEFAULT_CHILD_ARGV[2] == "--isolated"
    first = NdjsonChild()
    second = NdjsonChild()
    first_dir = first._owned_profile
    second_dir = second._owned_profile
    try:
        assert first_dir and second_dir and first_dir != second_dir
        assert first.argv[first.argv.index("--user-data-dir") + 1] == first_dir
        assert "--isolated" in second.argv
        assert "ms-playwright" not in first_dir
        explicit = NdjsonChild(["python", "-c", "pass"])
        assert explicit._owned_profile is None
    finally:
        asyncio.run(first.stop())
        asyncio.run(second.stop())
    assert not os.path.isdir(first_dir)
    assert not os.path.isdir(second_dir)


def test_competitive_probe_uses_outer_claude_for_the_proxy_arms(monkeypatch, tmp_path):
    """diff_fast_act and macro_replay are not the decide()-only path."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    seen: list[tuple[str, str]] = []

    async def fake_claude(arm, task, **kwargs):
        del kwargs
        seen.append(("claude", arm))
        row = empty_row(arm, task["id"], reason="stub", skipped=False)
        row["claude"] = True
        return row

    async def fake_no_model(arm, task, **kwargs):
        del task, kwargs
        seen.append(("no_model", arm))
        raise AssertionError(arm)

    monkeypatch.setattr("bench.probe.run_claude_arm", fake_claude)
    monkeypatch.setattr("bench.probe.run_no_model_arm", fake_no_model)
    rows = asyncio.run(
        execute_probe(spend_path=tmp_path / "spend.json", runs_dir=tmp_path / "runs")
    )
    assert len(rows) == 12
    assert [arm for _kind, arm in seen] == [
        arm for _task in range(3) for arm in ARMS
    ]
    assert all(kind == "claude" for kind, _arm in seen)
    recorded = json.loads(DEFAULT_SPEND_PATH.read_text(encoding="utf-8"))
    assert recorded["running_total_usd"] == 11.054514
    assert recorded["prior"]["usd"] == 9.645


def test_no_model_only_is_optional_and_not_the_competitive_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    seen: list[tuple[str, str]] = []

    async def fake_claude(arm, task, **kwargs):
        del kwargs
        seen.append(("claude", arm))
        row = empty_row(arm, task["id"], reason="stub", skipped=False)
        row["claude"] = True
        return row

    async def fake_no_model(arm, task, **kwargs):
        del kwargs
        seen.append(("no_model", arm))
        return empty_row(arm, task["id"], reason="decide", skipped=False, no_model_only=True)

    monkeypatch.setattr("bench.probe.run_claude_arm", fake_claude)
    monkeypatch.setattr("bench.probe.run_no_model_arm", fake_no_model)
    asyncio.run(
        execute_probe(
            spend_path=tmp_path / "spend.json",
            runs_dir=tmp_path / "runs",
            no_model_only=True,
        )
    )
    assert seen.count(("no_model", "diff_fast_act")) == 3
    assert seen.count(("no_model", "macro_replay")) == 3
    assert seen.count(("claude", "playwright_mcp")) == 3
    assert seen.count(("claude", "stagehand")) == 3
    assert ("claude", "diff_fast_act") not in seen
    assert ("claude", "macro_replay") not in seen
