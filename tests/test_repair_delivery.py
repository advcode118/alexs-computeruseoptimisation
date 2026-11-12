"""Offline repair delivery and probe tracing; no browser or API calls."""

import asyncio
import json

import pytest

from bench.harness import BenchmarkHarness, MAX_SNAPSHOT_CHARS, cap_messages_for_model, message_payload
from bench.probe import run_claude_arm
from bench.script_first import format_run_result, model_visible_script_result, ScriptFirstClient


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
    assert "tool_choice" not in model.requests[0][2]
    assert model.requests[1][2]["tool_choice"] == {"type": "any"}


def test_long_result_preserves_repair_and_json():
    original = format_run_result(
        ok=False, url="https://example.org", step_count=1,
        text=('quoted " slash \\ newline\n    ' * 1000), title="Example",
    ) + "\nEND_STATE_FAILED: repair now\nEND_STATE_FAILED: another instruction"
    visible = model_visible_script_result(original)
    assert len(visible) <= MAX_SNAPSHOT_CHARS - 300
    lines = visible.splitlines()
    assert lines[:2] == ["END_STATE_FAILED: repair now", "END_STATE_FAILED: another instruction"]
    payload = json.loads(lines[2])
    assert payload["text"].endswith("[text truncated]")
    assert payload["title"] == "Example"
    assert lines[3].startswith("Ran goto")
    messages = [{"role": "user", "content": [{"type": "tool_result", "content": original}]}]
    guarded = cap_messages_for_model(messages, script_first=True)[0]["content"][0]["content"]
    assert len(guarded) <= MAX_SNAPSHOT_CHARS
    assert json.loads(guarded.splitlines()[2])["text"].endswith("[text truncated]")
    assert "[snapshot truncated]" in cap_messages_for_model(messages)[0]["content"][0]["content"]


@pytest.mark.parametrize("provider,choice", [("anthropic", {"type": "any"}), ("openai", "required")])
def test_task_failed_and_repair_only_choice(monkeypatch, tmp_path, provider, choice):
    model = Model([[tool(code="first")], [tool("task_failed", reason="Unavailable")]])
    harness = BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path)
    harness.provider = provider
    harness.anthropic = model
    harness.mcp_client = Client()

    async def noop(*args):
        pass

    monkeypatch.setattr(harness, "_read_shared_page", noop)
    result = asyncio.run(harness.run_task("fixture", "Read page", "https://example.org"))
    assert result.success is False
    assert result.success_reason == "Task failed: Unavailable"
    assert result.repair_reply == "task_failed"
    assert len(result.steps) == 1
    assert "tool_choice" not in model.requests[0][2]
    assert model.requests[1][2]["tool_choice"] == choice


def test_provider_payload_tool_choice():
    from bench.openai_client import responses_payload

    args = ("gpt-6.1-sol", [], ScriptFirstClient().tools_for_claude(), "system", 100, "medium")
    assert "tool_choice" not in responses_payload(*args)
    assert responses_payload(*args, tool_choice="required")["tool_choice"] == "required"
    args = ("claude-sonnet-5-5", [], ScriptFirstClient().tools_for_claude(), "system", 100)
    assert "tool_choice" not in message_payload(*args, cache_prefix=True)
    assert message_payload(*args, cache_prefix=True, tool_choice={"type": "any"})["tool_choice"] == {"type": "any"}


def test_tool_choice_is_cleared_after_repair(monkeypatch, tmp_path):
    model = Model([[tool(code="first")], [tool(code="repair")], [tool("task_failed", reason="Stop")]])
    harness = BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path)
    harness.anthropic = model

    class MovingClient(Client):
        calls = 0

        async def call_tool(self, name, arguments):
            self.calls += 1
            return format_run_result(ok=False, url=f"https://example.org/{self.calls}", step_count=1), 0

    harness.mcp_client = MovingClient()

    async def noop(*args):
        pass

    monkeypatch.setattr(harness, "_read_shared_page", noop)
    asyncio.run(harness.run_task("fixture", "Read page", "https://example.org"))
    assert [request[2].get("tool_choice") for request in model.requests] == [None, {"type": "any"}, None]


def test_oversized_metadata_fails_closed():
    raw = format_run_result(ok=False, url="https://example.org", step_count=1, title="x" * 9000)
    with pytest.raises(ValueError, match="refusing to cut JSON"):
        model_visible_script_result(raw)


def test_no_repair_defaults():
    from bench.harness import TaskResult

    result = TaskResult("fixture", "read", False, "empty", 0, 0, 0, 0, 0, 0, 0, 0)
    assert result.repair_sent is False
    assert result.repair_reply == "none"
