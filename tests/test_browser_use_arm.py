"""browser-use 1.0 local baseline. Fixtures only. No browser, no network, no API key."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from backends.playwright_mcp import PLAYWRIGHT_MCP_VERSION as BACKEND_MCP
from bench.arms import (
    ARM_BROWSER_USE,
    ARM_PLAYWRIGHT,
    ARM_STAGEHAND,
    ARMS,
    BASELINE_ARMS,
    SELECTABLE_ARMS,
    arm_needs_claude,
    build_client,
    prompt_for,
)
from bench.browser_use_arm import (
    BROWSER_USE_MAX_STEPS,
    BROWSER_USE_VERSION,
    LOCAL_BROWSER,
    PAGE_TEXT_EXPRESSION,
    BrowserUseClient,
    read_page,
    run_browser_use_task,
    task_text,
)
from bench.budget import PROJECT_BUDGET_USD, ModelNotAllowed, SpendLedger, estimate_usd
from bench.harness import PLAYWRIGHT_MCP_VERSION as HARNESS_MCP
from bench.probe import execute_probe, main, plan_probe
from bench.tasks import BENCHMARK_TASKS, get_held_out_tasks
from proxy.child import PLAYWRIGHT_MCP_VERSION as CHILD_MCP

ROOT = Path(__file__).resolve().parents[1]
_JUDGE_KEYS = ("url_contains", "path_suffix", "answer_equals_selector", "answer_in_text")


class _Result:
    def __init__(self, text: str, *, steps: int = 2, cost_usd: float = 999.0):
        self.text = text
        self.usage = {"input": 100, "output": 10, "requests": steps}
        self.cost_usd = cost_usd
        self.steps = steps

    def final_result(self):
        return self.text

    def number_of_steps(self):
        return self.steps


class _World:
    def __init__(self, page_url: str = "", page_text: str = "", claim: str | None = None):
        self.calls = []
        self.page_url = page_url
        self.page_text = page_text
        self.page_selector_text = ""
        self.claim = claim
        self.stopped = 0

    def loader(self):
        world = self

        class Browser:
            def __init__(self, kind, *, headless, keep_alive):
                world.calls.append(("browser", kind, headless, keep_alive))
                self.kind = kind
                self.page_url = world.page_url
                self.page_text = world.page_text
                self.page_selector_text = world.page_selector_text
                self.stopped = False

            async def stop(self):
                self.stopped = True
                world.stopped += 1

        class LLM:
            def __init__(self, model, *, api_key):
                world.calls.append(("llm", model, api_key))
                self.model = model

        class Agent:
            def __init__(self, task, *, llm, browser, web_search, extend_system_message):
                world.calls.append(
                    ("agent", task, llm.model, browser.kind, web_search, extend_system_message)
                )
                self.browser = browser
                self.task = task

            async def run(self, max_steps):
                world.calls.append(("run", max_steps))
                return _Result(world.claim if world.claim is not None else self.task)

        return Agent, Browser, LLM


def _secrets(task: dict) -> list[str]:
    found = []
    answer = task.get("expected_answer")
    if isinstance(answer, str) and answer:
        found.append(answer)
    check = task.get("check_text")
    if isinstance(check, str):
        found.append(check)
    elif isinstance(check, list):
        found.extend(str(item) for item in check)
    markers = task.get("end_markers") or {}
    if isinstance(markers, dict):
        for key in _JUDGE_KEYS:
            value = markers.get(key)
            if isinstance(value, str) and value:
                found.append(value)
    return found


def test_browser_use_is_a_baseline_and_the_default_probe_stays_four():
    assert ARMS == ("playwright_mcp", "diff_fast_act", "macro_replay", "stagehand")
    assert BASELINE_ARMS == (ARM_PLAYWRIGHT, ARM_STAGEHAND, ARM_BROWSER_USE)
    assert ARM_BROWSER_USE in SELECTABLE_ARMS
    assert ARM_BROWSER_USE not in ARMS
    assert arm_needs_claude("browser_use") is True
    assert arm_needs_claude("browser_use", no_model_only=True) is True
    assert HARNESS_MCP == CHILD_MCP == BACKEND_MCP == "0.0.84"
    assert BROWSER_USE_VERSION == "1.0.0"
    assert LOCAL_BROWSER == "chromium"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f"browser-use=={BROWSER_USE_VERSION}" in pyproject
    for path in (
        ROOT / "bench" / "browser_use_arm.py",
        ROOT / "bench" / "arms.py",
        ROOT / "bench" / "probe.py",
        ROOT / "pyproject.toml",
        ROOT / "proxy" / "child.py",
        ROOT / "bench" / "harness.py",
    ):
        assert "0.0.85" not in path.read_text(encoding="utf-8")
    assert "browser_use" not in sys.modules
    prompt = prompt_for("browser_use")
    assert "REPL" in prompt
    assert "Chrome DevTools Protocol" in prompt
    assert "selector_text" not in prompt
    assert "bu-fast" not in prompt
    client = build_client("browser_use", headless=True)
    assert isinstance(client, BrowserUseClient)
    try:
        asyncio.run(client.start())
    except RuntimeError as exc:
        assert "Playwright" in str(exc)
    else:
        raise AssertionError("start launched a client")


def test_prompts_carry_the_task_and_not_the_judge_fields():
    prompt = prompt_for("browser_use")
    tasks = list(BENCHMARK_TASKS) + get_held_out_tasks()
    assert tasks
    for task in tasks:
        text = task_text(task)
        assert text == f"Task: {task['description']}\n\nStart URL: {task['start_url']}"
        visible = task["description"] + "\n" + task["start_url"]
        assert "selector_text" not in text
        assert "selector_text" not in prompt
        assert "answer_equals_selector" not in text
        assert "answer_equals_selector" not in prompt
        for secret in _secrets(task):
            assert secret not in prompt, task["id"]
            if secret not in visible:
                assert secret not in text, task["id"]
    assert "selector_text" not in PAGE_TEXT_EXPRESSION
    for task in tasks:
        for secret in _secrets(task):
            assert secret not in PAGE_TEXT_EXPRESSION


def test_local_agent_uses_the_bench_model_and_the_page_not_the_claim():
    task = next(item for item in BENCHMARK_TASKS if item["id"] == "wv_wikipedia_search")
    world = _World(page_url="https://en.wikipedia.org/wiki/Ada_Lovelace", page_text="")
    row = asyncio.run(
        run_browser_use_task(
            task,
            api_key="local-test-not-sent",
            headless=True,
            loader=world.loader,
        )
    )
    kinds = [call[0] for call in world.calls]
    assert kinds == ["browser", "llm", "agent", "run"]
    assert world.calls[0] == ("browser", "chromium", True, True)
    assert world.calls[1][1] == "claude-sonnet-5-5"
    assert world.calls[1][2] == "local-test-not-sent"
    agent = world.calls[2]
    assert agent[1] == task_text(task)
    assert "Ada_Lovelace" not in agent[1]
    assert task["expected_answer"] not in agent[1]
    assert "local-test-not-sent" not in agent[1]
    assert agent[3] == "chromium"
    assert agent[4] is False
    assert agent[5] == prompt_for("browser_use")
    assert world.calls[3] == ("run", BROWSER_USE_MAX_STEPS)
    assert world.stopped == 1
    assert row["success"] is True
    assert row["page_url"].endswith("Ada_Lovelace")
    assert row["model"] == "claude-sonnet-5-5"
    assert row["browser"] == "chromium"
    assert row["browser_use"] == "1.0.0"
    assert row["claude"] is True
    assert row["usd"] == estimate_usd(100, 10)
    assert row["usd"] != 999
    assert row["steps"] == 2

    claimed = {
        "id": "fixture_packing_add",
        "description": "Add an item to the packing list",
        "start_url": "https://example.test/start",
        "check_text": "milk",
        "expected_answer": "milk appears in the list",
    }
    quiet = _World(
        page_url="https://example.test/start",
        page_text="",
        claim="milk appears in the list",
    )
    missed = asyncio.run(
        run_browser_use_task(claimed, api_key="local-test-not-sent", loader=quiet.loader)
    )
    assert missed["success"] is False
    assert "milk" not in quiet.calls[2][1]
    assert quiet.stopped == 1

    def refuse(*args, **kwargs):
        del args, kwargs
        raise AssertionError("loader called")

    try:
        asyncio.run(
            run_browser_use_task(claimed, api_key="local-test-not-sent", model="claude-opus-4-7", loader=refuse)
        )
    except ModelNotAllowed:
        pass
    else:
        raise AssertionError("opus was accepted")
    unset = asyncio.run(run_browser_use_task(claimed, api_key="  ", loader=refuse))
    assert unset["skipped"] is True
    assert unset["success_reason"] == "ANTHROPIC_API_KEY unset"


def test_a_failed_run_still_stops_and_hides_the_exception_text():
    world = _World()

    def loader():
        agent_cls, browser_cls, llm_cls = world.loader()

        class Boom(agent_cls):
            async def run(self, max_steps):
                del max_steps
                raise RuntimeError("Ada_Lovelace selector_text")

        return Boom, browser_cls, llm_cls

    row = asyncio.run(
        run_browser_use_task(
            {"id": "t", "description": "Open the start page", "start_url": "https://example.test/"},
            api_key="local-test-not-sent",
            loader=loader,
        )
    )
    assert row["success"] is False
    assert row["success_reason"] == "browser_use run failed: RuntimeError"
    assert "Ada_Lovelace" not in row["success_reason"]
    assert "selector_text" not in row["success_reason"]
    assert world.stopped == 1

    def missing():
        raise ImportError("Ada_Lovelace")

    skipped = asyncio.run(
        run_browser_use_task(
            {"id": "t", "description": "Open the start page", "start_url": "https://example.test/"},
            api_key="local-test-not-sent",
            loader=missing,
        )
    )
    assert skipped["skipped"] is True
    assert skipped["success_reason"] == "browser-use==1.0.0 is not installed"
    assert "Ada_Lovelace" not in skipped["success_reason"]


def test_landed_page_comes_from_the_local_tab(monkeypatch):
    calls = []

    def request(name, payload, timeout):
        calls.append(("request", name, payload, timeout))
        return {"targetId": "tab-1", "url": "https://example.test/finished-page"}

    def cdp(name, method, session_id=None, **params):
        calls.append(("cdp", name, method, session_id, params))
        if method == "Target.attachToTarget":
            return {"sessionId": "sid-1"}
        return {"result": {"value": "milk on the page"}}

    monkeypatch.setattr("bench.browser_use_arm._daemon_request_fn", lambda: request)
    monkeypatch.setattr("bench.browser_use_arm._daemon_cdp_fn", lambda: cdp)

    class Browser:
        def __init__(self):
            self.name = "local-daemon"

    url, text, marked = asyncio.run(read_page(Browser()))
    assert url == "https://example.test/finished-page"
    assert text == "milk on the page"
    assert marked == ""
    assert calls[0] == ("request", "local-daemon", {"meta": "current_tab"}, 5)
    assert calls[1][2] == "Target.attachToTarget"
    assert calls[2][2] == "Runtime.evaluate"
    assert calls[2][4]["expression"] == PAGE_TEXT_EXPRESSION
    assert "selector_text" not in json.dumps(calls)

    def marked_cdp(name, method, session_id=None, **params):
        calls.append(("cdp", name, method, session_id, params))
        if method == "Target.attachToTarget":
            return {"sessionId": "sid-1"}
        expression = params.get("expression")
        if expression == PAGE_TEXT_EXPRESSION:
            return {"result": {"value": "Fixture Story"}}
        return {"result": {"value": "Fixture Story"}}

    monkeypatch.setattr("bench.browser_use_arm._daemon_cdp_fn", lambda: marked_cdp)
    calls.clear()
    url, text, marked = asyncio.run(read_page(Browser(), selector="a.top"))
    assert url == "https://example.test/finished-page"
    assert text == "Fixture Story"
    assert marked == "Fixture Story"
    expressions = [item[4].get("expression") for item in calls if item[0] == "cdp" and item[2] == "Runtime.evaluate"]
    assert expressions[0] == PAGE_TEXT_EXPRESSION
    assert "a.top" in expressions[1]
    assert "selector_text" not in expressions[1]


def test_hacker_news_passes_only_when_the_live_title_matches():
    from bench.browser_use_arm import selector_expression

    task = next(item for item in BENCHMARK_TASKS if item["id"] == "wv_hackernews_top")
    landed = _World(
        page_url="https://news.ycombinator.com/",
        page_text="Fixture Story\nSecond Story",
        claim="Fixture Story",
    )
    landed.page_selector_text = "Fixture Story"
    row = asyncio.run(run_browser_use_task(task, api_key="local-test-not-sent", loader=landed.loader))
    assert row["success"] is True
    assert ".titleline" not in landed.calls[2][1]
    assert "selector_text" not in landed.calls[2][1]
    assert ".titleline" not in PAGE_TEXT_EXPRESSION
    assert "selector_text" not in selector_expression(task["end_markers"]["answer_equals_selector"])

    second = _World(
        page_url="https://news.ycombinator.com/",
        page_text="Fixture Story\nSecond Story",
        claim="Second Story",
    )
    second.page_selector_text = "Fixture Story"
    missed = asyncio.run(run_browser_use_task(task, api_key="local-test-not-sent", loader=second.loader))
    assert missed["success"] is False

    bare = _World(
        page_url="https://news.ycombinator.com/",
        page_text="Fixture Story",
        claim="Fixture Story",
    )
    unread = asyncio.run(run_browser_use_task(task, api_key="local-test-not-sent", loader=bare.loader))
    assert unread["success"] is False

    sentence = _World(
        page_url="https://news.ycombinator.com/",
        page_text="Fixture Story\nSecond Story",
        claim='The top story on Hacker News is "Fixture Story".',
    )
    sentence.page_selector_text = "Fixture Story"
    said = asyncio.run(run_browser_use_task(task, api_key="local-test-not-sent", loader=sentence.loader))
    assert said["success"] is False
    assert said["success_reason"] == "answer is not the marked value"
    assert said["claimed_answer"] == 'The top story on Hacker News is "Fixture Story".'
    assert said["expected_value"] == "Fixture Story"

    denied = _World(
        page_url="https://news.ycombinator.com/",
        page_text="Fixture Story\nSecond Story",
        claim="The top story is Second Story.",
    )
    denied.page_selector_text = "Fixture Story"
    other = asyncio.run(run_browser_use_task(task, api_key="local-test-not-sent", loader=denied.loader))
    assert other["success"] is False
    assert other["success_reason"] == "answer is not the marked value"
    assert other["claimed_answer"] == "The top story is Second Story."
    assert other["expected_value"] == "Fixture Story"


def test_probe_selects_the_arm_without_a_live_run(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    plan = plan_probe(arms="playwright_mcp,stagehand,browser_use")
    assert plan["execute"] is False
    assert plan["arms"] == ["playwright_mcp", "stagehand", "browser_use"]
    assert plan["claude_arms"] == ["playwright_mcp", "stagehand", "browser_use"]
    assert plan["outer_model"] == "claude-sonnet-5-5"
    assert plan["baseline_arms"] == ["playwright_mcp", "stagehand", "browser_use"]
    assert "Browser('chromium')" in plan["browser_isolation"]["browser_use"]
    assert "0.0.84" in plan["browser_isolation"]["playwright_mcp"]
    assert plan_probe()["arms"] == list(ARMS)
    assert "browser_use" in plan_probe()["available_arms"]
    assert plan_probe(arms="browser_use", warm_replay=True)["warm_arms"] == [
        "macro_replay",
        "diff_fast_act",
    ]
    opted = plan_probe(no_model_only=True, arms="browser_use,stagehand")
    assert opted["claude_arms"] == ["browser_use", "stagehand"]
    assert opted["no_model_arms"] == []
    assert main(["--arms", "playwright_mcp,stagehand,browser_use"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["execute"] is False
    assert printed["arms"] == ["playwright_mcp", "stagehand", "browser_use"]


def test_probe_run_stays_on_the_fake_loader(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    def explode():
        raise AssertionError("browser-use imported")

    monkeypatch.setattr("bench.browser_use_arm.load_browser_use", explode)
    monkeypatch.setattr(
        "bench.harness.PlaywrightMCPClient.start",
        lambda self: (_ for _ in ()).throw(AssertionError("playwright started")),
    )

    async def claude_blocked(*args, **kwargs):
        del args, kwargs
        raise AssertionError("outer claude loop")

    monkeypatch.setattr("bench.probe.run_claude_arm", claude_blocked)
    SpendLedger.seed(tmp_path / "spend.json").save()
    cold = asyncio.run(
        execute_probe(
            spend_path=tmp_path / "spend.json",
            runs_dir=tmp_path / "runs",
            arms=(ARM_BROWSER_USE,),
        )
    )
    assert len(cold) == 3
    assert all(row["arm"] == "browser_use" and row["skipped"] for row in cold)
    assert all("ANTHROPIC_API_KEY unset" in row["success_reason"] for row in cold)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    world = _World(page_url="https://example.test/finished-page", page_text="plain page")
    monkeypatch.setattr("bench.browser_use_arm.load_browser_use", world.loader)
    ledger_path = tmp_path / "live-spend.json"
    SpendLedger.seed(ledger_path).save()
    rows = asyncio.run(
        execute_probe(
            spend_path=ledger_path,
            runs_dir=tmp_path / "live",
            arms=(ARM_BROWSER_USE,),
            warm_replay=True,
        )
    )
    assert [row["arm"] for row in rows] == ["browser_use", "browser_use", "browser_use"]
    assert all(row["claude"] is True for row in rows)
    assert all(row["model"] == "claude-sonnet-5-5" for row in rows)
    assert world.stopped == 3
    recorded = json.loads(ledger_path.read_text(encoding="utf-8"))
    fresh = SpendLedger.seed(tmp_path / "fresh.json")
    assert recorded["running_total_usd"] == round(
        fresh.running_total_usd + 3 * estimate_usd(100, 10),
        6,
    )

    capped = tmp_path / "capped.json"
    ledger = SpendLedger.seed(capped)
    ledger.record_task(run_id="probe", task_id="already", input_tokens=14_000_000, output_tokens=0)
    assert ledger.running_total_usd >= PROJECT_BUDGET_USD
    ledger.save()
    before = len(world.calls)
    blocked = asyncio.run(
        execute_probe(
            spend_path=capped,
            runs_dir=tmp_path / "capped",
            arms=(ARM_BROWSER_USE,),
        )
    )
    assert world.calls[before:] == []
    assert all(row["skipped"] for row in blocked)
    assert all("40" in row["success_reason"] for row in blocked)
