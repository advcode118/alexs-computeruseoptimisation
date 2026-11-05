"""The outer model re-fetches a full page after a compact diff. No network."""

from __future__ import annotations

import asyncio
import json

from bench.harness import BenchmarkHarness
from proxy.ignores import IgnoreCounter, action_returned_compact_diff, is_full_page_observe
from proxy.segment import dispatch
from tests.test_settle_diff import _Pages


def test_full_page_observe_is_not_a_scoped_snapshot():
    assert is_full_page_observe("browser_snapshot", {}) is True
    assert is_full_page_observe("browser_snapshot", None) is True
    assert is_full_page_observe("snapshot", {}) is True
    assert is_full_page_observe("observe", {}) is True
    assert is_full_page_observe("browser_snapshot", {"target": "e2"}) is False
    assert is_full_page_observe("browser_snapshot", {"depth": 2}) is False
    assert is_full_page_observe("browser_click", {}) is False
    diff = "changed\nfull_snapshot_chars: 100\ndiff_chars: 8\n"
    assert action_returned_compact_diff("browser_click", diff) is True
    assert action_returned_compact_diff("browser_snapshot", diff) is False
    counter = IgnoreCounter()
    assert counter.note_call("browser_click", {}) is False
    counter.note_result("browser_click", diff)
    assert counter.note_call("browser_snapshot", {}) is True
    assert counter.count == 1
    counter.note_result("browser_click", diff)
    assert counter.note_call("browser_snapshot", {"target": "e2", "depth": 1}) is False
    counter.note_result("browser_snapshot", diff)
    assert counter.note_call("browser_snapshot", {}) is True
    assert counter.count == 2


def test_proxy_counts_a_snapshot_that_ignores_the_diff():
    before = '- button "OK" [ref=e2]\n- textbox "Item" [ref=e4]'
    after = '- button "OK" [ref=e2]\n- textbox "Item" [ref=e4]: milk'
    child = _Pages([before, after])
    clicked = asyncio.run(dispatch(child, "browser_click", {"target": "e2"}))
    text = clicked["content"][0]["text"]
    assert "diff_chars:" in text
    assert "settle: quiet" in text
    assert child._ignore_counter.count == 0
    asyncio.run(dispatch(child, "browser_snapshot", {"target": "e4", "depth": 1}))
    assert child._ignore_counter.count == 0
    asyncio.run(dispatch(child, "browser_snapshot", {}))
    assert child._ignore_counter.count == 1


def test_harness_exposes_model_ignores_tools(tmp_path):
    diff = "full_snapshot_chars: 80\ndiff_chars: 10\n~ textbox \"Item\" [ref=e4]: milk"
    responses = [
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "browser_click",
                    "input": {"target": "e4"},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 4, "output_tokens": 2},
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "t2",
                    "name": "browser_snapshot",
                    "input": {},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 4, "output_tokens": 2},
        },
        {
            "content": [{"type": "text", "text": "TASK_COMPLETE"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 3, "output_tokens": 2},
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
            return [{"name": "browser_click", "description": "click", "input_schema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            del name, arguments
            return diff, 1.0

    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path)
    harness.anthropic = FakeModel()
    harness.mcp_client = FakeMCP()
    result = asyncio.run(
        harness.run_task(
            task_id="fixture_packing_add",
            task_description="Add milk",
            start_url="file:///tmp/packing.html",
        )
    )
    assert result.model_ignores_tools == 1
    saved = json.loads(harness.save_result(result, "ignores").read_text(encoding="utf-8"))
    assert saved["model_ignores_tools"] == 1
