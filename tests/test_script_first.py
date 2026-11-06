"""script_first arm. No browser launch, no API key, no network."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bench.arms import (
    ARM_SCRIPT_FIRST,
    ARMS,
    SCRIPT_FIRST_MAX_CALLS,
    arm_needs_claude,
    build_client,
    prompt_for,
)
from bench.budget import ALLOWED_MODEL, DEFAULT_SPEND_PATH, PROJECT_BUDGET_USD
from bench.harness import BenchmarkHarness, StepMetrics, TaskResult, page_url_from_result
from bench.judge import check_url_contains
from bench.probe import (
    PROBE_CLAUDE_BUDGET_USD,
    SCRIPT_FIRST_CLAUDE_BUDGET_USD,
    claude_block_reason,
    empty_row,
    execute_probe,
    main,
    plan_probe,
)
from bench.script_first import (
    ScriptFirstClient,
    format_run_result,
    parse_task_script,
    run_on_mcp,
    run_on_page,
)
from proxy.script import ScriptError


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
        self.url = "about:blank"

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
        self.url = url
        self.log.append(("goto", url))

    async def evaluate(self, source):
        self.log.append(("evaluate", source))
        if "heapq" in source:
            self.url = "https://docs.python.org/3/library/heapq.html"
        if "quietMs" in source or "MutationObserver" in source:
            raise AssertionError("script_first settled")


def test_script_first_is_selectable_and_uses_sonnet_5_5():
    assert ARM_SCRIPT_FIRST not in ARMS
    assert arm_needs_claude("script_first") is True
    assert arm_needs_claude("script_first", no_model_only=True) is True
    prompt = prompt_for("script_first")
    assert "run_script" in prompt
    assert "page.evaluate" in prompt
    assert "browser_run_code_unsafe is not a tool" in prompt
    client = build_client("script_first")
    assert isinstance(client, ScriptFirstClient)
    names = [tool["name"] for tool in client.tools_for_claude()]
    assert names == ["run_script"]
    assert "browser_run_code_unsafe" not in names
    source = Path(__file__).resolve().parents[1].joinpath("bench", "script_first.py").read_text(encoding="utf-8")
    assert "settle_playwright_page" not in source
    assert "browser_run_code_unsafe(" not in source
    harness = BenchmarkHarness(api_key="local-test", arm="script_first")
    assert harness.model == ALLOWED_MODEL == "claude-sonnet-5-5"
    assert harness.max_steps == 30


def test_locator_script_runs_without_a_settle_loop():
    page = _Page()
    script = """
    await page.goto("https://en.wikipedia.org/wiki/Main_Page");
    await page.getByRole("textbox", { name: "Search Wikipedia" }).fill("Ada Lovelace");
    page.getByRole("button", { name: "Search" }).click();
    """
    text = asyncio.run(run_on_page(page, script))
    assert [item[0] for item in page.log] == ["goto", "fill", "click"]
    assert ("evaluate",) not in [(item[0],) for item in page.log]
    assert "quietMs" not in text
    url = page_url_from_result(text)
    assert url == "https://en.wikipedia.org/wiki/Main_Page"
    assert check_url_contains(url, "Main_Page").success is True
    steps = parse_task_script(script)
    assert [step.kind for step in steps] == ["goto", "locator", "locator"]


def test_page_evaluate_sequence_updates_the_url_the_judge_reads():
    page = _Page()
    script = """
    await page.goto("https://docs.python.org/3/");
    await page.evaluate(() => {
      location.href = "https://docs.python.org/3/library/heapq.html";
    });
    """
    text = asyncio.run(run_on_page(page, script))
    assert page.log[0] == ("goto", "https://docs.python.org/3/")
    assert page.log[1][0] == "evaluate"
    assert "location.href" in page.log[1][1]
    assert "MutationObserver" not in page.log[1][1]
    url = page_url_from_result(text)
    assert url == "https://docs.python.org/3/library/heapq.html"
    assert check_url_contains(url, "heapq").success is True
    assert text.startswith("{")
    assert "Ran goto https://docs.python.org/3/library/heapq.html." in text


def test_unsafe_script_does_not_touch_the_page():
    page = _Page()
    for script in (
        'page.evaluate(() => browser_run_code_unsafe)',
        'await page.goto("https://example.com");\nbrowser_run_code_unsafe',
        'page.evaluate(() => eval("1"))',
    ):
        try:
            asyncio.run(run_on_page(page, script))
        except ScriptError:
            pass
        assert page.log == []
    client = ScriptFirstClient(page=page)
    text, _ms = asyncio.run(client.call_tool("run_script", {"code": "page.evaluate(() => require('fs'))"}))
    assert page.log == []
    assert json.loads(text.splitlines()[0])["ok"] is False


def test_mcp_evaluate_path_never_calls_the_unsafe_tool():
    calls: list[tuple[str, dict]] = []

    async def call_tool(name, arguments):
        if name == "browser_run_code_unsafe":
            raise AssertionError(name)
        calls.append((name, arguments))
        if name == "browser_navigate":
            return f"- Page URL: {arguments['url']}\n", 1.0
        if arguments.get("function") == "() => location.href":
            return "https://news.ycombinator.com/", 1.0
        return "null", 1.0

    script = """
    await page.goto("https://news.ycombinator.com/");
    await page.evaluate(() => document.querySelector(".titleline").innerText);
    """
    text = asyncio.run(run_on_mcp(call_tool, script))
    assert [name for name, _args in calls] == [
        "browser_navigate",
        "browser_evaluate",
        "browser_evaluate",
    ]
    assert "browser_snapshot" not in [name for name, _args in calls]
    url = page_url_from_result(text)
    assert url == "https://news.ycombinator.com/"
    assert check_url_contains(url, "news.ycombinator.com").success is True
    calls.clear()
    try:
        asyncio.run(run_on_mcp(call_tool, 'page.getByRole("button", { name: "Search" }).click()'))
    except ScriptError as exc:
        assert "page.evaluate" in str(exc)
    else:
        raise AssertionError("locator script must not run on the MCP evaluate path")
    assert calls == []


def test_probe_plan_selects_script_first_and_stops_at_two_dollars(capsys):
    plan = plan_probe(arms="playwright_mcp,script_first,stagehand")
    assert plan["execute"] is False
    assert plan["arms"] == ["playwright_mcp", "script_first", "stagehand"]
    assert plan["tasks"] == ["wv_wikipedia_search", "wv_python_docs", "wv_hackernews_top"]
    assert plan["outer_model"] == "claude-sonnet-5-5"
    assert plan["claude_budget_usd"] == SCRIPT_FIRST_CLAUDE_BUDGET_USD == 2.0
    assert plan["project_budget_usd"] == PROJECT_BUDGET_USD == 40.0
    assert plan["script_first_claude_budget_usd"] == 2.0
    assert "no per-click settle" in plan["browser_isolation"]["script_first"]
    default = plan_probe()
    assert default["arms"] == list(ARMS)
    assert default["claude_budget_usd"] == PROBE_CLAUDE_BUDGET_USD == 5.0
    assert default["outer_model"] == "claude-sonnet-5-5"
    assert "script_first" in default["box_commands"][-1]
    assert claude_block_reason(2.0, 12.91, budget_usd=2.0)
    assert claude_block_reason(1.9, 12.91, budget_usd=2.0) is None
    assert claude_block_reason(0.0, 40.0, budget_usd=2.0)
    assert main(["--arms", "playwright_mcp,script_first,stagehand"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["execute"] is False
    assert printed["claude_budget_usd"] == 2.0
    assert printed["outer_model"] == "claude-sonnet-5-5"
    assert "opus" not in json.dumps(printed).lower()
    assert main(["--arms", "nope"]) == 2


def test_script_first_execute_path_stops_after_two_dollars(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    seen: list[str] = []

    async def fake_claude(arm, task, **kwargs):
        del kwargs
        seen.append(arm)
        row = empty_row(arm, task["id"], reason="stub", skipped=False)
        row["claude"] = True
        if arm == "script_first":
            row["usd"] = 2.0
            row["input_tokens"] = 1
            row["output_tokens"] = 1
        return row

    monkeypatch.setattr("bench.probe.run_claude_arm", fake_claude)
    monkeypatch.setattr("bench.probe.run_no_model_arm", fake_claude)
    rows = asyncio.run(
        execute_probe(
            spend_path=tmp_path / "spend.json",
            runs_dir=tmp_path / "runs",
            arms=("playwright_mcp", "script_first", "stagehand"),
        )
    )
    assert [row["arm"] for row in rows] == ["playwright_mcp", "script_first", "stagehand"] * 3
    assert rows[0]["skipped"] is False
    assert rows[1]["arm"] == "script_first" and rows[1]["skipped"] is False
    assert rows[2]["skipped"] is True
    assert "$2" in rows[2]["success_reason"]
    assert all(row["skipped"] for row in rows[3:])
    assert seen == ["playwright_mcp", "script_first"]
    recorded = json.loads(DEFAULT_SPEND_PATH.read_text(encoding="utf-8"))
    assert recorded["running_total_usd"] == 12.912192
    assert recorded["model"] == "claude-sonnet-5-5"


def test_run_claude_arm_caps_script_first_calls_and_keeps_the_url(monkeypatch, tmp_path):
    seen: list[int] = []

    async def fake_setup(self):
        return None

    async def fake_teardown(self):
        return None

    async def fake_run_task(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None):
        del task_id, task_description, start_url, expected_answer, judge_prompt
        seen.append(self.max_steps)
        assert self.model == "claude-sonnet-5-5"
        return TaskResult(
            task_id="wv_wikipedia_search",
            task_description="search",
            success=True,
            success_reason="done",
            total_steps=1,
            total_wall_ms=12.0,
            total_model_ms=10.0,
            total_tool_ms=2.0,
            total_other_ms=0.0,
            total_input_tokens=4,
            total_output_tokens=2,
            total_snapshot_tokens=0,
            steps=[
                StepMetrics(
                    step_number=1,
                    tool_name="run_script",
                    tool_args={},
                    tool_result_size=10,
                    snapshot_tokens=0,
                    model_time_ms=10.0,
                    tool_time_ms=2.0,
                    input_tokens=4,
                    output_tokens=2,
                    page_url="https://en.wikipedia.org/wiki/Ada_Lovelace",
                )
            ],
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.setup", fake_setup)
    monkeypatch.setattr("bench.harness.BenchmarkHarness.teardown", fake_teardown)
    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", fake_run_task)
    from bench.probe import run_claude_arm

    row = asyncio.run(
        run_claude_arm(
            "script_first",
            {
                "id": "wv_wikipedia_search",
                "description": "Search Wikipedia",
                "start_url": "https://en.wikipedia.org/wiki/Main_Page",
                "check_url_contains": "Ada_Lovelace",
            },
            api_key="local-test-not-sent",
            headless=True,
            runs_dir=tmp_path,
        )
    )
    assert seen == [SCRIPT_FIRST_MAX_CALLS]
    assert row["success"] is True
    assert row["steps"] == 1
    assert row["wall_ms"] == 12.0
    assert row["usd"] > 0
    assert row["claude"] is True
    prose = format_run_result(ok=True, url="https://en.wikipedia.org/wiki/Ada_Lovelace", step_count=1)
    assert page_url_from_result(prose) == "https://en.wikipedia.org/wiki/Ada_Lovelace"


def test_harness_keeps_the_script_url_for_the_judge(tmp_path):
    prose = format_run_result(
        ok=True,
        url="https://en.wikipedia.org/wiki/Ada_Lovelace",
        step_count=2,
    )
    responses = [
        {
            "content": [{"type": "tool_use", "id": "t1", "name": "run_script", "input": {"code": "page.goto()"}}],
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

    class FakeClient:
        def tools_for_claude(self):
            return [{"name": "run_script", "description": "run", "input_schema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            del name, arguments
            return prose, 1.0

    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path, arm="script_first")
    harness.anthropic = FakeModel()
    harness.mcp_client = FakeClient()
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
        )
    )
    assert result.steps[-1].page_url == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert check_url_contains(result.steps[-1].page_url, "Ada_Lovelace").success is True
    assert result.success is True
