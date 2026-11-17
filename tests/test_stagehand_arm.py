"""Stagehand arm and the unlaunched probe. No browser, no API key, no network."""

from __future__ import annotations

import asyncio
import json

from bench.arms import ARMS, arm_needs_claude, prompt_for
from bench.budget import SpendLedger
from bench.harness import BenchmarkHarness, page_url_from_result, playwright_mcp_args
from bench.judge import check_url_contains
from bench.probe import (
    BOX_COMMANDS,
    claude_block_reason,
    main,
    plan_probe,
    snapshot_is_huge,
)
from bench.stagehand_local import (
    StagehandLocalClient,
    actions_to_script,
    append_stagehand_url,
    context_browser,
    describe_backend,
    stagehand_page_url,
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
    assert ARMS == ("script_first", "browser_use", "playwright_mcp")
    assert arm_needs_claude("playwright_mcp") is True
    assert arm_needs_claude("stagehand") is True
    assert "getByRole" in prompt_for("stagehand")
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
    assert plan["claude_arms"] == list(ARMS)
    assert plan["warm_arms"] == ["script_first"]
    assert plan["outer_model"] == "claude-sonnet-5-5"
    assert plan["claude_budget_usd"] == 2.0
    assert plan["project_spent_usd"] == SpendLedger.load().running_total_usd
    assert plan["box_commands"] == list(BOX_COMMANDS)
    assert "--warm-replay" in plan["box_commands"][2]
    assert plan["warm_replay"] is False
    assert plan["huge_snapshot_uses_body_length_only"] is True
    assert plan["browser_isolation"]["playwright_mcp"].startswith("--isolated only")
    assert "rejects --user-data-dir" in plan["browser_isolation"]["playwright_mcp"]
    assert "--user-data-dir" in plan["browser_isolation"]["stagehand"]
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
    assert "opus" not in json.dumps(printed).lower()


def test_each_arm_launch_is_a_private_browser():
    """Sequential arms must not share the Playwright MCP profile lock."""
    plain = playwright_mcp_args(headless=True, snapshot_mode="full")
    assert plain[:3] == ["npx", "@playwright/mcp@0.0.84", "--isolated"]
    assert "--user-data-dir" not in plain
    assert "--headless" in plain


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


class _ArticlePage(_Page):
    """Click navigation updates page.url the way Playwright does."""

    def __init__(self, explode: bool = False):
        super().__init__()
        self.url = "https://en.wikipedia.org/wiki/Main_Page"
        self.explode = explode

    async def goto(self, url):
        self.url = url
        self.log.append(("goto", url))

    def get_by_role(self, role, name=None):
        del role
        return _ArticleLocator(self, name or "")


class _ArticleLocator:
    def __init__(self, page: _ArticlePage, name: str):
        self.page = page
        self.name = name

    async def click(self):
        self.page.log.append(("click", self.name))
        self.page.url = "https://en.wikipedia.org/wiki/Ada_Lovelace"
        if self.page.explode:
            raise RuntimeError("click timed out")

    async def fill(self, value):
        self.page.log.append(("fill", self.name, value))


def test_stagehand_click_navigation_is_not_an_empty_url():
    page = _ArticlePage()
    client = StagehandLocalClient(page=page)
    text, _ms = asyncio.run(
        client.call_tool("run", {"code": 'page.getByRole("button", { name: "Search" }).click()'})
    )
    assert "Ran goto https://en.wikipedia.org/wiki/Main_Page" not in text
    url = page_url_from_result(text)
    assert url == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert check_url_contains(url, "Ada_Lovelace").success is True
    assert '"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"' in text
    assert "Ran goto https://en.wikipedia.org/wiki/Ada_Lovelace." in text
    assert "- Page URL: https://en.wikipedia.org/wiki/Ada_Lovelace" in text


def test_stagehand_live_url_wins_over_the_script_goto_and_a_failed_click():
    page = _ArticlePage()
    client = StagehandLocalClient(page=page)
    text, _ms = asyncio.run(
        client.call_tool(
            "run",
            {
                "code": (
                    'page.goto("https://en.wikipedia.org/wiki/Main_Page")\n'
                    'page.getByRole("button", { name: "Search" }).click()'
                )
            },
        )
    )
    assert page_url_from_result(text) == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    failed = _ArticlePage(explode=True)
    client = StagehandLocalClient(page=failed)
    text, _ms = asyncio.run(
        client.call_tool("run", {"code": 'page.getByRole("button", { name: "Search" }).click()'})
    )
    assert text.startswith("run failed:")
    assert page_url_from_result(text) == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert stagehand_page_url(failed) == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert append_stagehand_url("settle: quiet", "") == "settle: quiet"


def test_page_url_from_result_reads_every_stagehand_location():
    quoted = 'run failed: page.goto("https://en.wikipedia.org/wiki/Ada_Lovelace")'
    assert page_url_from_result(quoted) == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    single = "run failed: page.goto('https://docs.python.org/3/library/heapq.html')"
    assert page_url_from_result(single) == "https://docs.python.org/3/library/heapq.html"
    escaped = '{"url": "https:\\/\\/en.wikipedia.org\\/wiki\\/Ada_Lovelace"}'
    assert page_url_from_result(escaped) == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    mixed = (
        "Ran goto https://en.wikipedia.org/wiki/Main_Page; click Search.\n"
        '{"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"}\n'
        "- Page URL: https://en.wikipedia.org/wiki/Ada_Lovelace\n"
    )
    assert page_url_from_result(mixed) == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    kept = "- Page URL: https://news.ycombinator.com/\nRan goto https://example.com/.\n"
    assert page_url_from_result(kept) == "https://news.ycombinator.com/"
    assert page_url_from_result("settle: quiet\n(unchanged)\nfull_snapshot_chars: 40001\n") == ""


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
