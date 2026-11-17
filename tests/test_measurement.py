"""Offline timing contracts: deterministic clocks, clients and model replies."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from bench import browser_use_arm, probe
from bench.arms import ARMS, SELECTABLE_ARMS
from bench.measurement import grade_fields
from bench.script_first import format_run_result


URL = "https://example.test/done"
TASK = {"id": "timing", "description": "Open the finished page.",
        "start_url": "https://example.test/start", "check_url_contains": "/done"}


class Clock:
    def __init__(self):
        self.now = 100.0

    def perf_counter(self):
        return self.now

    def add(self, seconds):
        self.now += seconds


class Client:
    def __init__(self, clock, arm, *, fail=False, huge=False):
        self.clock, self.arm = clock, arm
        self.fail, self.huge = fail, huge
        self.ready = False
        self.navigated = False
        self._grade_read_url = ""
        self.tools = [{"name": "browser_evaluate"}]

    async def start(self):
        self.clock.add(7)
        self.ready = True

    def begin_launch(self):
        return asyncio.create_task(self.start())

    async def stop(self):
        self.clock.add(17)


    def tools_for_claude(self):
        return [{"name": "run_script" if self.arm == "script_first" else "finish",
                 "description": "finish", "input_schema": {"type": "object"}}]

    async def call_tool(self, name, args):
        assert self.ready
        if name == "browser_navigate" or (self.arm == "stagehand" and not self.navigated):
            self.clock.add(2)
            self.navigated = True
            return "x" * 200_000 if self.huge else "start snapshot", 2000
        if name == "snapshot":
            return "start snapshot", 0
        if self.arm == "script_first":
            self.clock.add(2)  # start-URL goto inside the first script
            self.navigated = True
        self.clock.add(5)
        if self.fail:
            raise RuntimeError("offline failure")
        if self.arm == "script_first":
            return format_run_result(ok=True, url=URL, step_count=2, title="Finished",
                                     h1="Finished", text="Finished",
                                     claimed={"url": URL, "answer": "Finished"}), 7000
        return json.dumps({"url": URL, "page": "Finished", "cycles": 1}), 5000


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    for module in ("bench.harness", "bench.probe", "bench.browser_use_arm"):
        monkeypatch.setattr(module + ".time", value)

    async def read(client, selector):
        assert client.navigated
        client.clock.add(11)
        client._grade_read_url = URL
        return "Finished", "Finished" if selector else ""

    monkeypatch.setattr("bench.script_first.read_marked_page", read)
    original = probe.grade_observation

    def grade(*args, **kwargs):
        value.add(13)
        return original(*args, **kwargs)

    monkeypatch.setattr(probe, "grade_observation", grade)
    return value


@pytest.mark.parametrize("arm", [*ARMS, "stagehand"])
@pytest.mark.parametrize("outcome", ["normal", "run_error", "grade_error"])
def test_model_arm_wall_boundaries(clock, monkeypatch, tmp_path, arm, outcome):
    client = Client(clock, arm, fail=outcome == "run_error")
    monkeypatch.setattr("bench.arms.build_client", lambda *a, **k: client)
    if outcome == "grade_error":
        async def read(*a, **k):
            clock.add(11)
            raise RuntimeError("grade failed")
        monkeypatch.setattr("bench.script_first.read_marked_page", read)

    class Model:
        def __init__(self, *a, **k):
            self.calls = 0

        async def create_message(self, *a, **k):
            assert client.ready, "model must not overlap launch"
            clock.add(3)
            self.calls += 1
            content = ([{"type": "tool_use", "id": "call", "name": client.tools_for_claude()[0]["name"],
                         "input": {"code": f"await page.goto('{TASK['start_url']}');"}}]
                       if self.calls == 1 else [{"type": "text", "text": "TASK_COMPLETE"}])
            return {"content": content, "usage": {}, "stop_reason": "end_turn"}, 3000

    monkeypatch.setattr("bench.harness.AnthropicClient", Model)
    row = asyncio.run(probe.run_claude_arm(arm, TASK, api_key="offline", headless=True, runs_dir=tmp_path))
    assert row["success"] is (outcome == "normal"), row
    assert row["wall_ms"] == (10_000 if arm == "script_first" or outcome == "run_error" else 13_000)
    assert row["browser_launch_ms"] == 7000
    assert row["wall_clock_version"] == 2
    if outcome == "normal":
        assert row["grade_read_ms"] == 11_000
        assert row["grade_url"] == URL
        assert row["grade_page_text"] == "Finished"
        assert not row["grade_page_text_truncated"]


@pytest.mark.parametrize("outcome", ["normal", "error", "launch_error", "grade_error"])
def test_browser_use_wall_boundaries(clock, monkeypatch, outcome):
    class Browser:
        def __init__(self, *a, **k):
            clock.add(2)
            self.ready = False

        async def start(self):
            clock.add(5)
            if outcome == "launch_error":
                raise RuntimeError("launch failed")
            self.ready = True

        async def stop(self):
            clock.add(17)

    class Agent:
        def __init__(self, *a, browser, **k):
            assert browser.ready

        async def run(self, **k):
            clock.add(2)  # agent's start-URL navigation
            clock.add(5)
            if outcome == "error":
                raise RuntimeError("run failed")
            return SimpleNamespace(text="Finished", usage={}, steps=[])

    async def read(*a, **k):
        clock.add(11)
        if outcome == "grade_error":
            raise RuntimeError("grade read failed")
        return URL, "Finished", ""

    monkeypatch.setattr(browser_use_arm, "read_page", read)
    row = asyncio.run(browser_use_arm.run_browser_use_task(
        TASK, api_key="offline", loader=lambda: (Agent, Browser, lambda *a, **k: None)))
    assert row["success"] is (outcome == "normal"), row
    assert row["wall_ms"] == (0 if outcome == "launch_error" else 7000)
    assert row["browser_launch_ms"] == 7000
    assert row["wall_clock_version"] == 2
    if outcome == "normal":
        assert row["grade_read_ms"] == 11_000
        assert row["grade_url"] == URL
        assert row["claimed_answer"] == "Finished"


def test_evidence_storage_cap_and_empty():
    assert grade_fields()["grade_page_text"] == ""
    assert grade_fields()["grade_page_text_truncated"] is False
    row = grade_fields(URL, "x" * 50_001, "selector", "answer")
    assert len(row["grade_page_text"]) == 50_000
    assert row["grade_page_text_truncated"] is True
    assert row["grade_selector_text"] == "selector"
    assert row["claimed_answer"] == "answer"


def test_all_selectable_arms_are_accounted_for():
    assert set(SELECTABLE_ARMS) == {"playwright_mcp", "stagehand", "script_first", "browser_use", "cascade"}
