"""fast_act and do_task_segment. No API key and no network.

The child is a fake. The cheap model, when a test supplies one, is a fake
transport. Claude is not called.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from loop.planner import ClaudePlanner, FastClient
from proxy.segment import PROXY_TOOLS, _TINY_STEP_CAP, _WASTED_LOOP_CAP, dispatch, listed_tools

SEARCH_TASK = "Search Wikipedia for Ada Lovelace and confirm the article title."
PACK_TASK = "Add milk to the packing list"


def _page(url: str, title: str, body: str) -> str:
    return (
        "### Page\n"
        f"- Page URL: {url}\n"
        f"- Page Title: {title}\n"
        "### Snapshot\n"
        "```yaml\n"
        f"{body}\n"
        "```\n"
    )


SEARCH = _page(
    "https://en.wikipedia.org/wiki/Main_Page",
    "Wikipedia, the free encyclopedia",
    '- textbox "Search Wikipedia" [ref=e4]\n- button "Search" [ref=e5]',
)
ARTICLE = _page(
    "https://en.wikipedia.org/wiki/Ada_Lovelace",
    "Ada Lovelace - Wikipedia",
    '- heading "Ada Lovelace" [ref=e1]\n- link "Early life" [ref=e2]',
)
PACKING = _page(
    "https://example.test/packing.html",
    "Packing list",
    '- textbox "Item" [ref=e1]\n- button "Add" [ref=e2]',
)
PACKED = _page(
    "https://example.test/packing.html#milk",
    "Packing list",
    '- textbox "Item" [ref=e1]\n- button "Add" [ref=e2]',
)


class FakeChild:
    def __init__(self, pages: list[str] | None = None):
        self.pages = list(pages or [])
        self.calls: list[tuple[str, dict]] = []
        self._shot = 0

    async def call_tool(self, name, arguments):
        args = arguments or {}
        self.calls.append((name, args))
        if name != "browser_snapshot":
            return {"content": [{"type": "text", "text": "ok"}], "isError": False}
        if not self.pages:
            text = ""
        else:
            text = self.pages[min(self._shot, len(self.pages) - 1)]
            if self._shot < len(self.pages) - 1:
                self._shot += 1
        return {"content": [{"type": "text", "text": text}], "isError": False}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbid(*_args, **_kwargs):
        raise AssertionError("network call")

    monkeypatch.setattr("loop.planner._post_json", forbid)
    monkeypatch.setattr("loop.planner._post_chat", forbid)
    monkeypatch.setattr("loop.planner._post_anthropic", forbid)
    monkeypatch.setattr(ClaudePlanner, "plan", forbid)
    for key in ("ANTHROPIC_API_KEY", "NEBIUS_API_KEY", "OPENAI_API_KEY", "LOOP_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def _payload(result: dict) -> dict:
    assert result["content"][0]["type"] == "text"
    return json.loads(result["content"][0]["text"])


def test_tool_descriptions_prefer_a_segment_over_single_steps():
    by_name = {tool["name"]: tool["description"] for tool in PROXY_TOOLS}
    assert set(by_name) == {"fast_act", "do_task_segment"}
    for text in by_name.values():
        assert "do_task_segment" in text
        assert "fast_act" in text
        assert "browser_snapshot" in text
        assert "browser_click" in text
        assert "browser_type" in text
        assert "Do not take a full snapshot after a diff was returned" in text
        assert "model_ignores_tools" in text
        assert "one script or one do_task_segment" in text
    child = [{"name": "browser_click", "description": "Click a ref", "inputSchema": {"type": "object"}}]
    listed = listed_tools(child)
    assert listed[0] == child[0]
    assert [tool["name"] for tool in listed[1:]] == ["fast_act", "do_task_segment"]


def test_fast_act_runs_a_no_model_batch():
    child = FakeChild([SEARCH, ARTICLE])
    result = asyncio.run(dispatch(child, "fast_act", {"task": SEARCH_TASK}))
    body = _payload(result)
    assert result.get("isError") is not True
    assert body["ok"] is True
    assert body["status"] == "done"
    assert body["needs_model"] is False
    assert body["tier"] == "direct"
    assert body["model_calls"] == 0
    assert body["cycles"] == 1
    assert body["url"] == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert "Ada Lovelace" in body["page"]
    assert body["actions"] == ["fill e4 'Ada Lovelace'", "click e5"]
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_type",
        "browser_evaluate",
        "browser_click",
        "browser_evaluate",
        "browser_snapshot",
    ]
    assert child.calls[1][1] == {
        "target": "e4",
        "element": 'textbox "Search Wikipedia"',
        "text": "Ada Lovelace",
    }
    assert child.calls[3][1]["target"] == "e5"


def test_fast_act_returns_a_tier_and_does_not_invent_an_action():
    child = FakeChild([PACKING])
    result = asyncio.run(dispatch(child, "fast_act", {"task": PACK_TASK}))
    body = _payload(result)
    assert result.get("isError") is not True
    assert body["ok"] is False
    assert body["needs_model"] is True
    assert body["tier"] == "planner"
    assert body["actions"] == []
    assert body["model_calls"] == 0
    assert body["cycles"] == 0
    assert [name for name, _args in child.calls] == ["browser_snapshot"]
    assert "No action was taken" in body["summary"]


def test_do_task_segment_finishes_a_search_in_one_call(tmp_path):
    child = FakeChild([SEARCH, ARTICLE])
    result = asyncio.run(
        dispatch(
            child,
            "do_task_segment",
            {"task": SEARCH_TASK},
            env_path=str(tmp_path / "missing.env"),
        )
    )
    body = _payload(result)
    assert result.get("isError") is not True
    assert body["ok"] is True
    assert body["status"] == "done"
    assert body["needs_model"] is False
    assert body["tier"] == "direct"
    assert body["model_calls"] == 0
    assert body["cycles"] == 1
    assert body["url"] == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert "Ada Lovelace" in body["summary"]
    assert "Early life" in body["page"]
    assert body["actions"] == ["fill e4 'Ada Lovelace'", "click e5"]
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_type",
        "browser_evaluate",
        "browser_click",
        "browser_evaluate",
        "browser_snapshot",
    ]


def test_do_task_segment_stops_when_the_cheap_model_is_unavailable(tmp_path):
    child = FakeChild([PACKING])
    result = asyncio.run(
        dispatch(
            child,
            "do_task_segment",
            {"task": PACK_TASK},
            env_path=str(tmp_path / "missing.env"),
        )
    )
    body = _payload(result)
    assert result.get("isError") is not True
    assert body["ok"] is False
    assert body["status"] == "stopped"
    assert body["needs_model"] is True
    assert body["tier"] == "planner"
    assert body["actions"] == []
    assert body["model_calls"] == 0
    assert body["cycles"] == 0
    assert "NEBIUS_API_KEY" in body["summary"]
    assert body["url"] == "https://example.test/packing.html"
    assert "Packing list" in body["page"]
    assert [name for name, _args in child.calls] == ["browser_snapshot"]


def test_do_task_segment_uses_the_cheap_client_and_not_claude():
    seen = []

    def transport(url, headers, payload):
        seen.append((url, headers, payload))
        return json.dumps(
            {
                "reason": "Click Add.",
                "done": True,
                "actions": [{"type": "click", "ref": "e2"}],
                "assertion": None,
            }
        )

    client = FastClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        transport=transport,
    )
    child = FakeChild([PACKING, PACKED])
    result = asyncio.run(dispatch(child, "do_task_segment", {"task": PACK_TASK}, client=client))
    body = _payload(result)
    assert body["ok"] is True
    assert body["tier"] == "fast"
    assert body["model_calls"] == 1
    assert body["actions"] == ["click e2"]
    assert body["url"] == "https://example.test/packing.html#milk"
    assert len(seen) == 1
    assert seen[0][0] == "https://example.test/v1/chat/completions"
    assert "anthropic" not in seen[0][0]
    assert seen[0][1]["Authorization"] == "Bearer test-key"
    assert "test-key" not in json.dumps(seen[0][2])
    sent = json.loads(seen[0][2]["messages"][1]["content"])
    assert [control["ref"] for control in sent["controls"]] == ["e1", "e2"]
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_click",
        "browser_evaluate",
        "browser_snapshot",
    ]


def test_do_task_segment_stops_a_wasted_loop(tmp_path):
    """The same click on an unchanged page stops before max_cycles."""
    calls = {"n": 0}

    def transport(url, headers, payload):
        del url, headers, payload
        calls["n"] += 1
        return json.dumps(
            {
                "reason": "Click Add again.",
                "done": False,
                "actions": [{"type": "click", "ref": "e2"}],
                "assertion": None,
            }
        )

    client = FastClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        transport=transport,
    )
    child = FakeChild([PACKING])
    result = asyncio.run(
        dispatch(
            child,
            "do_task_segment",
            {"task": PACK_TASK, "max_cycles": 8},
            client=client,
            env_path=str(tmp_path / "missing.env"),
        )
    )
    body = _payload(result)
    assert body["ok"] is False
    assert body["status"] == "stopped"
    assert body["cycles"] == _WASTED_LOOP_CAP
    assert body["cycles"] < 8
    assert "wasted loop" in body["summary"]
    assert "one do_task_segment" in body["summary"]
    assert calls["n"] == _WASTED_LOOP_CAP


def test_dispatch_forwards_a_playwright_tool_unchanged():
    child = FakeChild()
    result = asyncio.run(dispatch(child, "browser_navigate", {"url": "https://example.com"}))
    assert child.calls[0] == ("browser_navigate", {"url": "https://example.com"})
    assert [name for name, _args in child.calls] == [
        "browser_navigate",
        "browser_evaluate",
        "browser_snapshot",
    ]
    assert result["isError"] is False
    text = result["content"][0]["text"]
    assert "fast_act" not in text
    assert "full_snapshot_chars:" in text
    assert "diff_chars:" in text
