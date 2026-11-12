"""Offline repair delivery and probe tracing; no browser or API calls."""

import asyncio

import pytest

from bench.harness import BenchmarkHarness
from bench.probe import run_claude_arm
from bench.script_first import format_run_result


def tool(name="run_script", **arguments):
    return {"type": "tool_use", "id": "call", "name": name, "input": arguments}


class Model:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    async def create_message(self, messages, tools, **kwargs):
        self.requests.append((messages, tools, kwargs))
        return {"content": next(self.replies), "stop_reason": "end_turn"}, 0.0


class Client:
    def tools_for_claude(self):
        return []

    async def call_tool(self, name, arguments):
        assert name == "run_script"
        return format_run_result(
            ok=False, url="https://example.org/page", title="Example", step_count=1,
            error="fixture failure",
        ), 0.0


@pytest.mark.parametrize("reply,kind", [
    ([tool(code="second")], "script"),
    ([{"type": "text", "text": "I am done"}], "prose"),
    ([{"type": "text", "text": "TASK_FAILED: unavailable"}], "task_failed"),
    ([], "none"),
])
def test_probe_traces_actual_repair_reply(monkeypatch, tmp_path, reply, kind):
    model = Model([[tool(code="first")], reply])

    async def setup(self):
        self.anthropic = model
        self.mcp_client = Client()

    async def noop(*args):
        pass

    monkeypatch.setattr(BenchmarkHarness, "setup", setup)
    monkeypatch.setattr(BenchmarkHarness, "teardown", noop)
    monkeypatch.setattr(BenchmarkHarness, "_read_shared_page", noop)
    row = asyncio.run(run_claude_arm(
        "script_first", {"id": "fixture", "description": "Read page", "start_url": "https://example.org"},
        api_key="offline", headless=True, runs_dir=tmp_path,
    ))
    assert row["final_url"] == "https://example.org/page"
    assert row["final_title"] == "Example"
    assert row["scripts"] == (["first", "second"] if kind == "script" else ["first"])
    assert row["repair_sent"] is True
    assert row["repair_reply"] == kind


def test_no_repair_defaults():
    from bench.harness import TaskResult

    result = TaskResult("fixture", "read", False, "empty", 0, 0, 0, 0, 0, 0, 0, 0)
    assert result.repair_sent is False
    assert result.repair_reply == "none"
