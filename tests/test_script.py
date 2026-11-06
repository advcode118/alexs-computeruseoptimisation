"""Playwright-style locator scripts. No API key and no network."""

from __future__ import annotations

import asyncio
import json

import pytest

from loop.planner import ClaudePlanner, FastClient
import proxy.segment as segment
from proxy.replay import cache_key, load_sequence
from proxy.script import ScriptError, parse_script
from proxy.segment import dispatch
from tests.test_replay_cache import (
    ARTICLE,
    SEARCH,
    SEARCH_TASK,
    FakeChild,
    _payload,
    _search_key,
)


SCRIPT = """
// fill then click
await page.getByRole("textbox", { name: "Search Wikipedia" }).fill("Ada Lovelace");
page.getByRole('button', { name: 'Search', exact: true }).click()
"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbid(*_args, **_kwargs):
        raise AssertionError("network call")

    monkeypatch.setattr("loop.planner._post_json", forbid)
    monkeypatch.setattr("loop.planner._post_chat", forbid)
    monkeypatch.setattr("loop.planner._post_anthropic", forbid)
    monkeypatch.setattr(ClaudePlanner, "plan", forbid)
    monkeypatch.setattr(FastClient, "plan", forbid)
    monkeypatch.setattr(segment, "decide", forbid)
    for key in ("ANTHROPIC_API_KEY", "NEBIUS_API_KEY", "OPENAI_API_KEY", "LOOP_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_parser_accepts_locator_lines_and_rejects_code():
    actions = parse_script(SCRIPT)
    assert [(item.finder, item.role, item.name, item.op, item.value) for item in actions] == [
        ("role", "textbox", "Search Wikipedia", "fill", "Ada Lovelace"),
        ("role", "button", "Search", "click", ""),
    ]
    label = parse_script('page.getByLabel("Item").fill("milk")')
    assert label[0].finder == "label"
    assert label[0].value == "milk"
    with pytest.raises(ScriptError):
        parse_script('page.evaluate(() => document.title)')
    with pytest.raises(ScriptError):
        parse_script('page.goto("https://example.test")')
    with pytest.raises(ScriptError):
        parse_script("page.getByRole('button', { name: 'Go' }).click()\n" * 5, max_lines=4)


def test_fast_act_runs_a_script_without_decide():
    child = FakeChild([SEARCH, SEARCH, ARTICLE])
    result = asyncio.run(
        dispatch(child, "fast_act", {"task": SEARCH_TASK, "script": SCRIPT})
    )
    body = _payload(result)
    assert body["ok"] is True
    assert body["tier"] == "script"
    assert body["model_calls"] == 0
    assert body["needs_model"] is False
    assert body["actions"] == ["fill e4 'Ada Lovelace'", "click e5"]
    assert body["diff"]
    assert "full_snapshot_chars" in body
    assert body.get("settle") == "quiet"
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_type",
        "browser_evaluate",
        "browser_snapshot",
        "browser_click",
        "browser_evaluate",
        "browser_snapshot",
    ]
    assert "const quietMs = 500" in child.calls[2][1]["function"]


def test_a_bad_script_does_not_touch_the_page():
    child = FakeChild([SEARCH])
    result = asyncio.run(
        dispatch(child, "fast_act", {"task": SEARCH_TASK, "script": "page.evaluate(() => 1)"})
    )
    body = _payload(result)
    assert body["ok"] is False
    assert child.calls == []
    assert "evaluate" in body["summary"]


def test_a_failed_script_line_leaves_the_finished_steps(tmp_path):
    child = FakeChild([SEARCH, ARTICLE])
    result = asyncio.run(
        dispatch(
            child,
            "do_task_segment",
            {"task": SEARCH_TASK, "script": SCRIPT},
            env_path=str(tmp_path / "missing.env"),
        )
    )
    body = _payload(result)
    assert body["ok"] is False
    assert body["tier"] == ""
    assert body["model_calls"] == 0
    assert body["actions"] == ["fill e4 'Ada Lovelace'"]
    assert "no button" in body["summary"].casefold() or "named 'Search'" in body["summary"]
    assert not (tmp_path / "replay-cache.sqlite").exists()


def test_a_segment_script_is_learned_for_a_later_replay(tmp_path, monkeypatch):
    child = FakeChild([SEARCH, SEARCH, ARTICLE])
    result = asyncio.run(
        dispatch(
            child,
            "do_task_segment",
            {"task": SEARCH_TASK, "script": SCRIPT},
            env_path=str(tmp_path / "missing.env"),
        )
    )
    body = _payload(result)
    assert body["tier"] == "script"
    stored = load_sequence(tmp_path / "replay-cache.sqlite", *_search_key())
    assert stored is not None
    assert [step["tool"] for step in stored["actions"]] == ["browser_type", "browser_click"]
    assert "e4" not in json.dumps(stored)

    def forbid_script(*_args, **_kwargs):
        raise AssertionError("script parser during replay")

    monkeypatch.setattr(segment, "parse_script", forbid_script)
    replayed = FakeChild([SEARCH, SEARCH, ARTICLE])
    again = asyncio.run(
        dispatch(
            replayed,
            "do_task_segment",
            {"task": SEARCH_TASK},
            env_path=str(tmp_path / "missing.env"),
        )
    )
    payload = _payload(again)
    assert payload["tier"] == "replay"
    assert payload["model_calls"] == 0
    assert payload["actions"] == ["fill e4 'Ada Lovelace'", "click e5"]
    assert cache_key(SEARCH_TASK, __import__("proxy.page", fromlist=["observation_from_tool_text"]).observation_from_tool_text(SEARCH)[0])
