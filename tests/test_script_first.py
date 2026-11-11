"""script_first arm. No browser launch, no API key, no network."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bench.arms import (
    ARM_SCRIPT_FIRST,
    ARMS,
    SCRIPT_FIRST_HARD_CAP,
    SCRIPT_FIRST_MAX_CALLS,
    SCRIPT_FIRST_MAX_SCRIPTS,
    arm_needs_claude,
    build_client,
    prompt_for,
)
from bench.budget import ALLOWED_MODEL, PROJECT_BUDGET_USD, SpendLedger, default_spend_path
from bench.harness import (
    AnthropicClient,
    BenchmarkHarness,
    PlaywrightMCPClient,
    StepMetrics,
    TaskResult,
    message_payload,
    page_url_from_result,
)
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
    ClaimedEvidence,
    PageEvidence,
    ScriptFirstClient,
    evidence_verdict,
    format_run_result,
    next_script_first_limit,
    parse_task_script,
    repair_request,
    run_on_mcp,
    run_on_page,
    script_made_progress,
)
from bench.tasks import markers_for_task
from proxy.script import ScriptError


class _Locator:
    def __init__(self, log: list, name: str):
        self.log = log
        self.name = name

    async def click(self, **kwargs):
        self.log.append(("click", self.name))
        self.timeout = kwargs.get("timeout")

    async def fill(self, value, **kwargs):
        self.log.append(("fill", self.name, value))
        self.timeout = kwargs.get("timeout")

    async def press(self, value, **kwargs):
        self.log.append(("press", self.name, value))
        self.timeout = kwargs.get("timeout")

    async def check(self, **kwargs):
        self.log.append(("check", self.name))
        self.timeout = kwargs.get("timeout")

    async def uncheck(self, **kwargs):
        self.log.append(("uncheck", self.name))
        self.timeout = kwargs.get("timeout")


class _Page:
    def __init__(self):
        self.log: list = []
        self.url = "about:blank"
        self.last_goto_wait = ""

    def get_by_role(self, role, name=None):
        del role
        return _Locator(self.log, name or "")

    def get_by_label(self, name):
        return _Locator(self.log, name)

    def get_by_text(self, name):
        return _Locator(self.log, name)

    def get_by_placeholder(self, name):
        return _Locator(self.log, name)

    async def goto(self, url, **kwargs):
        self.url = url
        self.last_goto_wait = kwargs.get("wait_until") or ""
        self.log.append(("goto", url))

    async def evaluate(self, source):
        self.log.append(("evaluate", source))
        if "heapq" in source:
            self.url = "https://docs.python.org/3/library/heapq.html"
        if "quietMs" in source or "MutationObserver" in source:
            raise AssertionError("script_first settled")
        if "titleline" in source:
            return "Example Story"
        return None


def test_script_first_is_selectable_and_uses_sonnet_5_5():
    assert ARM_SCRIPT_FIRST not in ARMS
    assert arm_needs_claude("script_first") is True
    assert arm_needs_claude("script_first", no_model_only=True) is True
    prompt = prompt_for("script_first")
    assert "run_script" in prompt
    assert "page.evaluate" in prompt
    assert "browser_run_code_unsafe is not a tool" in prompt
    assert "Main_Page" in prompt
    assert "END_STATE_FAILED" in prompt
    assert "one corrected script" in prompt
    assert "does not settle or snapshot" in prompt
    assert "waitForTimeout" in prompt
    assert "The first script must finish" in prompt
    assert "Special:Search" in prompt
    assert "one script" in prompt.casefold()
    assert 3 < SCRIPT_FIRST_MAX_CALLS <= SCRIPT_FIRST_HARD_CAP <= 6
    assert SCRIPT_FIRST_MAX_SCRIPTS == 2
    client = build_client("script_first")
    assert isinstance(client, ScriptFirstClient)
    tools = client.tools_for_claude()
    names = [tool["name"] for tool in tools]
    assert names == ["run_script"]
    assert "waitForTimeout" in tools[0]["description"]
    assert "finished page" in tools[0]["description"]
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
    assert [item[0] for item in page.log[:3]] == ["goto", "fill", "click"]
    assert page.log[-1][0] == "evaluate"
    assert "canonical" in page.log[-1][1]
    assert "MutationObserver" not in page.log[-1][1]
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


def test_wait_lines_are_dropped_and_goto_waits_for_dom_content():
    page = _Page()
    script = """
    await page.goto("https://docs.python.org/3/library/heapq.html", { waitUntil: "networkidle" });
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: "Search" }).waitFor();
    """
    text = asyncio.run(run_on_page(page, script))
    assert page.log[0] == ("goto", "https://docs.python.org/3/library/heapq.html")
    assert page.log[-1][0] == "evaluate"
    assert "canonical" in page.log[-1][1]
    assert page.last_goto_wait == "domcontentloaded"
    assert "networkidle" not in text
    assert "waitFor" not in text
    url = page_url_from_result(text)
    assert check_url_contains(url, "heapq").success is True


def test_evaluate_return_is_visible_without_a_second_script():
    page = _Page()
    script = """
    await page.goto("https://news.ycombinator.com/");
    await page.evaluate(() => document.querySelector(".titleline a").textContent);
    """
    text = asyncio.run(run_on_page(page, script))
    payload = json.loads(text.splitlines()[0])
    assert payload["extracted"] == ["Example Story"]
    assert "Extracted: Example Story" in text
    assert page.last_goto_wait == "domcontentloaded"
    assert [item[0] for item in page.log] == ["goto", "evaluate", "evaluate"]
    assert "titleline" in page.log[1][1]
    assert "canonical" in page.log[-1][1]


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
    assert any(
        "script_first" in command and "--warm-replay" in command for command in default["box_commands"]
    )
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
    shared = default_spend_path()
    before = shared.read_text(encoding="utf-8")
    probe_ledger = tmp_path / "probe-spend.json"
    SpendLedger.seed(probe_ledger).save()
    rows = asyncio.run(
        execute_probe(
            spend_path=probe_ledger,
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
    assert shared.read_text(encoding="utf-8") == before
    recorded = json.loads(probe_ledger.read_text(encoding="utf-8"))
    assert recorded["running_total_usd"] > json.loads(before)["running_total_usd"]
    assert recorded["model"] == "claude-sonnet-5-5"


def test_run_claude_arm_caps_script_first_calls_and_keeps_the_url(monkeypatch, tmp_path):
    seen: list[int] = []

    async def fake_setup(self):
        return None

    async def fake_teardown(self):
        return None

    async def fake_run_task(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del task_id, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        seen.append(self.max_steps)
        assert self.model == "claude-sonnet-5-5"
        return TaskResult(
            task_id="wv_wikipedia_search",
            task_description="search",
            success=True,
            success_reason="done",
            end_state="PASS",
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


def test_end_state_asks_for_one_repair_until_the_url_leaves_main_page():
    markers = markers_for_task("wv_wikipedia_search")
    main = evidence_verdict(
        markers,
        PageEvidence(url="https://en.wikipedia.org/wiki/Main_Page"),
        ClaimedEvidence(),
    )
    assert main.verdict == "FAIL"
    assert "Main_Page" in main.reason
    article = evidence_verdict(
        markers,
        PageEvidence(url="https://en.wikipedia.org/wiki/Ada_Lovelace"),
        ClaimedEvidence(url="https://en.wikipedia.org/wiki/Ada_Lovelace"),
    )
    assert article.verdict == "PASS"
    assert article.scored_url == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    search = evidence_verdict(
        markers,
        PageEvidence(url="https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace"),
        ClaimedEvidence(),
    )
    assert search.verdict == "FAIL"
    assert search.scored_url == "https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace"
    note = repair_request("https://en.wikipedia.org/wiki/Main_Page", main.reason)
    assert note.startswith("END_STATE_FAILED:")
    assert "one corrected script" in note
    assert script_made_progress(None, {"ok": True, "url": "https://news.ycombinator.com/", "steps": 1}) is True
    stuck = {"ok": True, "url": "https://en.wikipedia.org/wiki/Main_Page", "steps": 2}
    assert script_made_progress(stuck, stuck) is False
    assert next_script_first_limit(
        step_num=2,
        limit=2,
        hard_cap=SCRIPT_FIRST_HARD_CAP,
        made_progress=True,
        repair_pending=False,
        refused_extra_script=False,
    ) == 2
    assert next_script_first_limit(
        step_num=1,
        limit=2,
        hard_cap=SCRIPT_FIRST_HARD_CAP,
        made_progress=False,
        repair_pending=True,
        refused_extra_script=False,
    ) == 2
    assert next_script_first_limit(
        step_num=1,
        limit=1,
        hard_cap=SCRIPT_FIRST_HARD_CAP,
        made_progress=True,
        repair_pending=True,
        refused_extra_script=False,
    ) == 2
    assert next_script_first_limit(
        step_num=2,
        limit=4,
        hard_cap=SCRIPT_FIRST_HARD_CAP,
        made_progress=False,
        repair_pending=False,
        refused_extra_script=False,
    ) == 4


def _script_harness(tmp_path, replies, call_tool, max_steps):
    class FakeModel:
        def __init__(self):
            self._replies = list(replies)
            self.seen: list = []

        async def create_message(self, messages, tools, system=None, max_tokens=4096):
            del tools, system, max_tokens
            self.seen.append(messages)
            return self._replies.pop(0), 1.0

    class FakeClient:
        def __init__(self):
            self.calls = 0

        def tools_for_claude(self):
            return [{"name": "run_script", "description": "run", "input_schema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            self.calls += 1
            return await call_tool(name, arguments, self.calls)

    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path, arm="script_first", max_steps=max_steps)
    model = FakeModel()
    client = FakeClient()
    harness.anthropic = model
    harness.mcp_client = client
    return harness, model, client


def _tool_reply(code: str) -> dict:
    return {
        "content": [{"type": "tool_use", "id": "t", "name": "run_script", "input": {"code": code}}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _done_reply(text: str = "TASK_COMPLETE") -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _hn_evidence(answer: str):
    return format_run_result(
        ok=True,
        url="https://news.ycombinator.com/",
        step_count=1,
        title="Hacker News",
        text=f"{answer.strip()}\nSecond story",
        selector_text=answer.strip(),
        extracted=[answer.strip()],
        claimed={"url": "https://news.ycombinator.com/", "answer": answer},
    )


def test_script_first_repairs_a_main_page_script_once(tmp_path):
    async def call_tool(name, arguments, nth):
        del name
        url = "https://en.wikipedia.org/wiki/Main_Page"
        if nth > 1:
            url = "https://en.wikipedia.org/wiki/Ada_Lovelace"
        return format_run_result(ok=True, url=url, step_count=nth), 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("stay"), _tool_reply("article"), _done_reply()],
        call_tool,
        max_steps=3,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
            check_url_contains="Ada_Lovelace",
        )
    )
    assert client.calls == 2
    assert len(model.seen) == 2

    def _asks(messages: list) -> int:
        count = 0
        for message in messages:
            content = message.get("content")
            texts = [content] if isinstance(content, str) else []
            if isinstance(content, list):
                texts.extend(
                    block.get("content", "")
                    for block in content
                    if isinstance(block, dict) and isinstance(block.get("content"), str)
                )
            count += sum(text.count("END_STATE_FAILED") for text in texts)
        return count

    assert _asks(model.seen[0]) == 0
    assert _asks(model.seen[1]) == 1
    assert result.success is True
    assert result.steps[-1].page_url == "https://en.wikipedia.org/wiki/Ada_Lovelace"


def test_script_first_does_not_add_a_turn_after_a_moving_page(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return _hn_evidence("Show HN"), 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("open and read"), _done_reply("Show HN\nTASK_COMPLETE"), _tool_reply("again")],
        call_tool,
        max_steps=2,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_hackernews_top",
            task_description="Read the top Hacker News story",
            start_url="https://news.ycombinator.com/",
        )
    )
    assert client.calls == 1
    assert len(model.seen) == 1
    assert result.total_steps == 1
    assert "END_STATE_FAILED" not in json.dumps(model.seen)
    assert result.success is True
    assert result.success_reason != "Max steps reached"
    assert result.steps[-1].page_url == "https://news.ycombinator.com/"


def test_script_first_stops_when_the_text_is_already_back(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return _hn_evidence("Show HN"), 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("read"), _tool_reply("again"), _done_reply("Show HN\nTASK_COMPLETE")],
        call_tool,
        max_steps=4,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_hackernews_top",
            task_description="Read the top Hacker News story",
            start_url="https://news.ycombinator.com/",
        )
    )
    assert client.calls == 1
    assert len(model.seen) == 1
    assert result.total_steps == 1
    assert "The first script already finished" not in json.dumps(model.seen)
    assert "END_STATE_FAILED" not in json.dumps(model.seen)
    assert result.success is True


def test_script_first_stops_when_the_finished_url_is_already_open(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return format_run_result(ok=True, url="https://en.wikipedia.org/wiki/Ada_Lovelace", step_count=1), 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply('page.goto("https://en.wikipedia.org/wiki/Ada_Lovelace")'), _done_reply()],
        call_tool,
        max_steps=4,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
            check_url_contains="Ada_Lovelace",
        )
    )
    assert client.calls == 1
    assert len(model.seen) == 1
    assert "END_STATE_FAILED" not in json.dumps(model.seen)
    assert result.success is True
    assert result.steps[-1].page_url == "https://en.wikipedia.org/wiki/Ada_Lovelace"


def test_script_first_refuses_a_third_script_and_still_accepts_the_answer(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments
        return format_run_result(ok=True, url="https://news.ycombinator.com/", step_count=nth), 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("a"), _tool_reply("b"), _tool_reply("c"), _done_reply("top story\nTASK_COMPLETE")],
        call_tool,
        max_steps=3,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_hackernews_top",
            task_description="Read the top Hacker News story",
            start_url="https://news.ycombinator.com/",
        )
    )
    assert client.calls == SCRIPT_FIRST_MAX_SCRIPTS == 2
    assert len(model.seen) == 4
    assert "Do not call run_script again" in json.dumps(model.seen)
    assert result.success is False
    assert result.end_state == "FAIL"
    assert result.success_reason != "Max steps reached"


def test_script_first_stops_when_the_repair_stays_on_main_page(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return format_run_result(ok=True, url="https://en.wikipedia.org/wiki/Main_Page", step_count=2), 1.0

    harness, _model, client = _script_harness(
        tmp_path,
        [_tool_reply("a"), _tool_reply("b"), _tool_reply("c"), _done_reply()],
        call_tool,
        max_steps=6,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
            check_url_contains="Ada_Lovelace",
        )
    )
    assert client.calls == 2
    assert result.success is False
    assert "Main_Page" in result.success_reason


def test_encoded_article_url_ends_the_task_without_a_repair(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return format_run_result(ok=True, url="https://en.wikipedia.org/wiki/Ada%20Lovelace", step_count=1), 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("goto"), _tool_reply("repair"), _done_reply()],
        call_tool,
        max_steps=4,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
            check_url_contains="Ada_Lovelace",
        )
    )
    assert client.calls == 1
    assert len(model.seen) == 1
    assert "END_STATE_FAILED" not in json.dumps(model.seen)
    assert result.success is True
    assert result.end_state == "PASS"
    assert result.total_steps == 1
    assert result.steps[-1].page_url == "https://en.wikipedia.org/wiki/Ada%20Lovelace"
    assert check_url_contains(result.steps[-1].page_url, "Ada_Lovelace").success is False


class _LatePage(_Page):
    def __init__(self):
        super().__init__()
        self.url = "https://en.wikipedia.org/wiki/Main_Page"
        self.waits = 0

    async def title(self):
        if "Ada" in self.url:
            return "Ada Lovelace - Wikipedia"
        return "Wikipedia, the free encyclopedia"

    async def wait_for_url(self, predicate, **kwargs):
        del kwargs
        self.waits += 1
        self.url = "https://en.wikipedia.org/wiki/Ada%20Lovelace"
        if not predicate(self.url):
            raise TimeoutError("landed url was not the article")


def test_click_navigation_is_read_after_it_commits():
    page = _LatePage()
    script = 'page.getByRole("combobox", { name: "Search Wikipedia" }).press("Enter")'
    text = asyncio.run(run_on_page(page, script))
    assert page.waits == 1
    assert "MutationObserver" not in text
    assert "quietMs" not in text
    url = page_url_from_result(text)
    assert url == "https://en.wikipedia.org/wiki/Ada%20Lovelace"
    verdict = evidence_verdict(markers_for_task("wv_wikipedia_search"), PageEvidence(url=url), ClaimedEvidence())
    assert verdict.verdict == "PASS"
    assert verdict.scored_url == url
    assert check_url_contains(url, "Ada_Lovelace").success is False


def test_finished_goto_does_not_wait_again():
    page = _LatePage()
    page.waits = 0

    async def count_wait(predicate, **kwargs):
        del predicate, kwargs
        page.waits += 1

    page.wait_for_url = count_wait
    script = 'page.goto("https://en.wikipedia.org/wiki/Ada_Lovelace")'
    text = asyncio.run(run_on_page(page, script))
    assert page.waits == 0
    assert page_url_from_result(text) == "https://en.wikipedia.org/wiki/Ada_Lovelace"


def test_visible_answer_is_not_invented_by_the_harness():
    page = _Page()
    script = 'page.goto("https://news.ycombinator.com/")'
    text = asyncio.run(run_on_page(page, script))
    payload = json.loads(text.splitlines()[0])
    assert "extracted" not in payload
    assert payload["url"] == "https://news.ycombinator.com/"
    assert [item[0] for item in page.log] == ["goto", "evaluate"]
    assert "titleline" not in page.log[-1][1]
    assert "canonical" in page.log[-1][1]


def test_every_arm_rereads_the_page_for_the_grade(monkeypatch):
    """The grade read is the same for every arm, even when a step carries text."""
    from bench.harness import StepMetrics

    calls: list[tuple[str, str]] = []

    async def read_again(client, selector):
        del client
        calls.append(selector)
        return "replacement text", "replacement title"

    monkeypatch.setattr("bench.script_first.read_marked_page", read_again)

    def step() -> StepMetrics:
        return StepMetrics(
            step_number=1,
            tool_name="run_script",
            tool_args={},
            tool_result_size=1,
            snapshot_tokens=0,
            model_time_ms=0.0,
            tool_time_ms=0.0,
            input_tokens=0,
            output_tokens=0,
            page_url="https://news.ycombinator.com/",
            page_text="Show HN\nSecond story",
            selector_text="Show HN",
        )

    for arm in ("script_first", "playwright_mcp"):
        harness = BenchmarkHarness(api_key="local-test", arm=arm)
        harness.mcp_client = object()
        carried = step()
        asyncio.run(harness._read_shared_page("wv_hackernews_top", [carried]))
        assert carried.page_text == "replacement text"
        assert carried.selector_text == "replacement title"
    assert calls == [".titleline a", ".titleline a"]


def test_the_grade_read_is_not_in_the_wall_time(tmp_path, monkeypatch):
    """A slow grade read must not move any arm's clock."""
    import time as _time

    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        body = format_run_result(
            ok=True,
            url="https://en.wikipedia.org/wiki/Ada_Lovelace",
            step_count=1,
            title="Ada Lovelace - Wikipedia",
            h1="Ada Lovelace",
            text="Ada Lovelace was a mathematician.",
        )
        return body, 1.0

    async def slow_read(self, task_id, steps):
        del self, task_id, steps
        _time.sleep(0.4)

    monkeypatch.setattr(BenchmarkHarness, "_read_shared_page", slow_read)
    harness, _model, _client = _script_harness(
        tmp_path,
        [_tool_reply('page.goto("https://en.wikipedia.org/wiki/Ada_Lovelace");'), _done_reply()],
        call_tool,
        max_steps=4,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace and open her article.",
            start_url="https://en.wikipedia.org/",
        )
    )
    assert result.total_wall_ms < 300

def test_script_first_cache_breakpoint_is_sent_and_the_api_is_not_called(monkeypatch, tmp_path):
    """The stable prompt and tool schema carry the breakpoint. The request is not sent."""
    from bench.script_cache import PATCH_PROMPT, PATCH_TOOL

    task = "Task: finish the page"
    tools = ScriptFirstClient().tools_for_claude()
    prompt = prompt_for("script_first")
    body = message_payload(
        "claude-sonnet-5-5",
        [{"role": "user", "content": task}],
        tools,
        prompt,
        4096,
        cache_prefix=True,
    )
    assert body["system"][0]["text"] == prompt
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["tools"][-1]["name"] == "run_script"
    assert body["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in tools[0]
    assert task not in body["system"][0]["text"]
    assert "selector_text" not in json.dumps(body["system"])
    assert "cache_control" not in json.dumps(body["messages"])
    assert task in body["messages"][0]["content"]

    patch = message_payload(
        "claude-sonnet-5-5",
        [{"role": "user", "content": task}],
        [PATCH_TOOL],
        PATCH_PROMPT,
        4096,
        cache_prefix=True,
    )
    assert patch["system"][0]["text"] == PATCH_PROMPT
    assert patch["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert patch["tools"][0]["name"] == "patch_step"
    assert patch["tools"][0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in PATCH_TOOL
    assert task not in patch["system"][0]["text"]
    assert "cache_control" not in json.dumps(patch["messages"])

    plain = message_payload(
        "claude-sonnet-5-5",
        [{"role": "user", "content": task}],
        tools,
        prompt_for("playwright_mcp"),
        4096,
        cache_prefix=False,
    )
    assert isinstance(plain["system"], str)
    assert "cache_control" not in json.dumps(plain)

    sent = {}

    def urlopen(req, timeout=120):
        del timeout
        sent["body"] = json.loads(req.data.decode())
        sent["url"] = req.full_url
        raise RuntimeError("refusing the live API")

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    client = AnthropicClient("local-test-not-sent")
    client.cache_prefix = True
    try:
        asyncio.run(client.create_message([{"role": "user", "content": task}], tools, system=prompt))
    except RuntimeError as exc:
        assert str(exc) == "refusing the live API"
    else:
        raise AssertionError("the request was not built")
    assert sent["url"] == "https://api.anthropic.com/v1/messages"
    assert sent["body"]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert sent["body"]["tools"][-1]["name"] == "run_script"
    assert sent["body"]["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert sent["body"]["system"][0]["text"] == prompt
    assert task not in sent["body"]["system"][0]["text"]

    async def no_browser(self):
        return None

    monkeypatch.setattr(ScriptFirstClient, "start", no_browser)
    monkeypatch.setattr(ScriptFirstClient, "_open_browser", no_browser)
    monkeypatch.setattr(PlaywrightMCPClient, "start", no_browser)
    script_harness = BenchmarkHarness(
        api_key="local-test-not-sent",
        arm="script_first",
        runs_dir=tmp_path / "script",
    )
    other = BenchmarkHarness(
        api_key="local-test-not-sent",
        arm="playwright_mcp",
        runs_dir=tmp_path / "playwright",
    )
    asyncio.run(script_harness.setup())
    asyncio.run(other.setup())
    assert script_harness.anthropic.cache_prefix is True
    assert other.anthropic.cache_prefix is False
    asyncio.run(script_harness.teardown())
    asyncio.run(other.teardown())


def test_chrome_starts_while_the_model_writes_and_the_tool_waits(tmp_path):
    """The launch begins before the model returns and finishes before run_script."""
    order: list[str] = []
    prose = format_run_result(
        ok=True,
        url="https://en.wikipedia.org/wiki/Ada_Lovelace",
        step_count=1,
    )

    class Client:
        def __init__(self):
            self.launch = None

        def begin_launch(self):
            order.append("launch")
            self.launch = asyncio.get_running_loop().create_future()
            return self.launch

        def tools_for_claude(self):
            return [{"name": "run_script", "description": "run", "input_schema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            del name, arguments
            order.append("tool")
            assert self.launch.done()
            return prose, 1.0

    class Model:
        def __init__(self, client):
            self.client = client
            self.calls = 0

        async def create_message(self, messages, tools, system=None, max_tokens=4096):
            del messages, tools, system, max_tokens
            self.calls += 1
            order.append("model")
            assert order[0] == "launch"
            assert not self.client.launch.done()
            self.client.launch.set_result(None)
            return _tool_reply('page.goto("https://en.wikipedia.org/wiki/Ada_Lovelace")'), 1.0

    client = Client()
    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path, arm="script_first", max_steps=2)
    harness.anthropic = Model(client)
    harness.mcp_client = client
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
        )
    )
    assert order == ["launch", "model", "tool"]
    assert result.success is True


def test_script_first_setup_returns_before_chrome_is_open(tmp_path, monkeypatch):
    hold = asyncio.Event()
    order: list[str] = []

    async def open_browser(self):
        order.append("open-start")
        await hold.wait()
        order.append("open-done")

    async def playwright_start(self):
        order.append("playwright-start")

    monkeypatch.setattr(ScriptFirstClient, "_open_browser", open_browser)
    monkeypatch.setattr(PlaywrightMCPClient, "start", playwright_start)

    async def run():
        script = BenchmarkHarness(
            api_key="local-test",
            arm="script_first",
            runs_dir=tmp_path / "script",
        )
        await script.setup()
        await asyncio.sleep(0)
        assert order == ["open-start"]
        assert script._browser_launch is not None
        assert not script._browser_launch.done()
        assert script.anthropic.cache_prefix is True
        hold.set()
        await script.teardown()
        assert order == ["open-start", "open-done"]
        other = BenchmarkHarness(
            api_key="local-test",
            arm="playwright_mcp",
            runs_dir=tmp_path / "playwright",
        )
        await other.setup()
        assert order[-1] == "playwright-start"
        assert other.anthropic.cache_prefix is False
        await other.teardown()

    asyncio.run(run())
