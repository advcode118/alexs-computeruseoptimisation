"""Stagehand arm and the unlaunched probe. No browser, no API key, no network."""

from __future__ import annotations

import asyncio
import json

from bench.arms import ARMS, arm_needs_claude, prompt_for
from bench.budget import DEFAULT_SPEND_PATH
from bench.harness import BenchmarkHarness, page_url_from_result, playwright_mcp_args
from bench.judge import check_url_contains
from bench.probe import (
    BOX_COMMANDS,
    PROBE_CLAUDE_BUDGET_USD,
    claude_block_reason,
    empty_row,
    execute_probe,
    main,
    plan_probe,
    snapshot_is_huge,
    warm_summary,
)
from bench.stagehand_local import (
    StagehandLocalClient,
    actions_to_script,
    context_browser,
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
    assert harness.model == "claude-sonnet-5-5"
    tools = StagehandLocalClient().tools_for_claude()
    assert [tool["name"] for tool in tools] == ["snapshot", "run", "screenshot"]
    by_name = {tool["name"]: tool["description"] for tool in tools}
    assert "model_ignores_tools" in by_name["snapshot"]
    assert "Do not take a full snapshot after a diff was returned" in by_name["run"]
    assert "one" in by_name["run"].lower()


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
    assert plan["outer_model"] == "claude-sonnet-5-5"
    assert plan["claude_budget_usd"] == PROBE_CLAUDE_BUDGET_USD == 5.0
    assert plan["project_spent_usd"] == 12.912192
    assert plan["box_commands"] == list(BOX_COMMANDS)
    assert "--warm-replay" in plan["box_commands"][2]
    assert plan["warm_replay"] is False
    assert plan["warm_arms"] == ["macro_replay", "diff_fast_act"]
    assert plan["huge_snapshot_uses_body_length_only"] is True
    assert plan["browser_isolation"]["playwright_mcp"].startswith("--isolated only")
    assert "rejects --user-data-dir" in plan["browser_isolation"]["playwright_mcp"]
    assert "--user-data-dir" in plan["browser_isolation"]["stagehand"]
    opted = plan_probe(no_model_only=True)
    assert opted["mode"] == "no_model_only"
    assert opted["claude_arms"] == ["playwright_mcp", "stagehand"]
    assert opted["no_model_arms"] == ["diff_fast_act", "macro_replay"]
    assert snapshot_is_huge("x" * 40_001) is True
    assert snapshot_is_huge("short") is False
    assert snapshot_is_huge('{"full_snapshot_chars": 40001, "diff_chars": 12}') is False
    assert snapshot_is_huge("full_snapshot_chars: 40000\ndiff_chars: 8") is False
    assert snapshot_is_huge("full_snapshot_chars: 999999\nchanged") is False
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
    from proxy.child import DEFAULT_CHILD_ARGV, NdjsonChild

    monkeypatch.delenv("PLAYWRIGHT_MCP_PROXY_CHILD", raising=False)

    plain = playwright_mcp_args(headless=True, snapshot_mode="full")
    assert plain[:3] == ["npx", "@playwright/mcp@0.0.84", "--isolated"]
    assert "--user-data-dir" not in plain
    assert "--headless" in plain
    assert DEFAULT_CHILD_ARGV[2] == "--isolated"
    assert "--user-data-dir" not in DEFAULT_CHILD_ARGV
    first = NdjsonChild()
    second = NdjsonChild()
    try:
        assert first._owned_profile is None
        assert second._owned_profile is None
        assert "--user-data-dir" not in first.argv
        assert "--user-data-dir" not in second.argv
        assert "--isolated" in first.argv
        assert "--isolated" in second.argv
        assert first.argv != [] and second.argv == first.argv
        explicit = NdjsonChild(["python", "-c", "pass"])
        assert explicit._owned_profile is None
    finally:
        asyncio.run(first.stop())
        asyncio.run(second.stop())


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
    assert recorded["running_total_usd"] == 12.912192
    assert recorded["prior"]["usd"] == 9.645
    assert recorded["recorded_extra_usd"] == 3.267192


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


def test_url_judge_reads_json_url_and_stagehand_goto_prose():
    prose = "Ran goto https://en.wikipedia.org/wiki/Ada_Lovelace.\nsettle: quiet\n"
    url = page_url_from_result(prose)
    assert url == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert check_url_contains(url, "Ada_Lovelace").success is True
    payload = '{"ok": true, "url": "https://docs.python.org/3/library/heapq.html", "diff": "changed"}'
    assert page_url_from_result(payload) == "https://docs.python.org/3/library/heapq.html"
    assert check_url_contains(page_url_from_result(payload), "heapq").success is True
    assert page_url_from_result('- Page URL: https://news.ycombinator.com/\n') == "https://news.ycombinator.com/"
    assert page_url_from_result("settle: quiet\n(unchanged)\nfull_snapshot_chars: 40001\n") == ""
    assert check_url_contains("", "Ada_Lovelace").success is False
    later = page_url_from_result("Ran goto https://example.com/; goto https://docs.python.org/3/library/heapq.html.")
    assert later == "https://docs.python.org/3/library/heapq.html"


def test_later_snapshot_keeps_the_stagehand_url(tmp_path):
    prose = "Ran goto https://en.wikipedia.org/wiki/Ada_Lovelace.\nsettle: quiet\n"
    responses = [
        {
            "content": [{"type": "tool_use", "id": "t1", "name": "run", "input": {"code": "page.goto()"}}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        {
            "content": [{"type": "tool_use", "id": "t2", "name": "snapshot", "input": {}}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        {
            "content": [{"type": "text", "text": "TASK_COMPLETE"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    ]

    class FakeModel:
        def __init__(self):
            self._responses = list(responses)

        async def create_message(self, messages, tools, system=None, max_tokens=4096):
            del messages, tools, system, max_tokens
            return self._responses.pop(0), 1.0

    class FakeMCP:
        def tools_for_claude(self):
            return [
                {"name": "run", "description": "run", "input_schema": {"type": "object"}},
                {"name": "snapshot", "description": "snapshot", "input_schema": {"type": "object"}},
            ]

        async def call_tool(self, name, arguments):
            del arguments
            if name == "run":
                return prose, 1.0
            return "(unchanged)\nfull_snapshot_chars: 12\ndiff_chars: 11\n", 1.0

    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path, arm="stagehand")
    harness.anthropic = FakeModel()
    harness.mcp_client = FakeMCP()
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
        )
    )
    assert result.steps[-1].page_url == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    judged = check_url_contains(result.steps[-1].page_url, "Ada_Lovelace")
    assert judged.success is True


def test_stagehand_reads_browser_as_a_property():
    sentinel = object()

    class Ctx:
        @property
        def browser(self):
            return sentinel

    ctx = Ctx()
    assert context_browser(ctx) is sentinel
    try:
        ctx.browser()
    except TypeError:
        return
    raise AssertionError("context.browser is a property and must not be called")


def test_warm_replay_reruns_the_proxy_arms(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    seen: list[str] = []

    async def fake_claude(arm, task, **kwargs):
        del kwargs
        seen.append(arm)
        row = empty_row(arm, task["id"], reason="stub", skipped=False)
        row["claude"] = True
        row["replay_hit"] = arm == "macro_replay"
        row["wall_ms"] = 10.0
        return row

    async def fake_no_model(arm, task, **kwargs):
        del arm, task, kwargs
        raise AssertionError("warm pass stays on the outer model")

    monkeypatch.setattr("bench.probe.run_claude_arm", fake_claude)
    monkeypatch.setattr("bench.probe.run_no_model_arm", fake_no_model)
    rows = asyncio.run(
        execute_probe(
            spend_path=tmp_path / "spend.json",
            runs_dir=tmp_path / "runs",
            warm_replay=True,
        )
    )
    assert len(rows) == 18
    assert sum(1 for row in rows if row["pass"] == "cold") == 12
    warm = [row for row in rows if row["pass"] == "warm"]
    assert [row["arm"] for row in warm] == ["macro_replay", "diff_fast_act"] * 3
    summary = warm_summary(rows)
    assert summary["macro_replay"]["replay_hits"] == 3
    assert summary["macro_replay"]["replay_hit_rate"] == 1
    assert summary["macro_replay"]["wall_ms"] == 30
    assert summary["diff_fast_act"]["replay_hits"] == 0
    assert summary["diff_fast_act"]["tasks"] == 3
    assert seen.count("macro_replay") == 6
    assert seen.count("diff_fast_act") == 6
    assert seen.count("playwright_mcp") == 3
    assert seen.count("stagehand") == 3
