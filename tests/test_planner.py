import json

import pytest

from loop.actions import ActionError, PlannerError, parse_batch
from loop.planner import ModelPlanner, parse_item, parse_model_content


def test_parse_item_from_the_demo_task():
    assert parse_item("Add milk to the packing list") == "milk"
    assert parse_item("Add wool socks to the packing list.") == "wool socks"
    assert parse_item("something else") == "milk"


def test_parse_batch_accepts_the_five_actions():
    batch = parse_batch(
        {
            "reason": "try the form",
            "done": False,
            "actions": [
                {"type": "goto", "url": "https://example.com"},
                {"type": "fill", "ref": "e1", "text": "milk"},
                {"type": "click", "ref": "e2"},
                {"type": "press", "key": "Enter", "ref": "e1"},
                {"type": "scroll", "direction": "down", "amount": 500},
            ],
            "assertion": {"type": "text", "text": "milk"},
        }
    )
    assert [type(action).__name__ for action in batch.actions] == [
        "Goto",
        "Fill",
        "Click",
        "Press",
        "Scroll",
    ]
    assert batch.assertion.text == "milk"


def test_parse_batch_rejects_a_bad_ref():
    with pytest.raises(ActionError):
        parse_batch({"actions": [{"type": "click", "ref": "button"}]})


def test_model_content_strips_a_fence():
    content = '```json\n{"reason":"done","done":true,"actions":[],"assertion":null}\n```'
    batch = parse_model_content(content)
    assert batch.done is True
    assert batch.actions == []


def test_model_planner_makes_one_call_and_returns_the_batch():
    seen = {}

    def transport(url, headers, payload):
        seen["url"] = url
        seen["headers"] = headers
        seen["payload"] = payload
        return json.dumps(
            {
                "reason": "click add",
                "done": False,
                "actions": [{"type": "click", "ref": "e2"}],
                "assertion": {"type": "title", "text": "Packing list"},
            }
        )

    planner = ModelPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="gpt-4o-mini",
        transport=transport,
    )
    from loop.actions import Observation

    batch = planner.plan("Add milk", Observation("https://example.test", "Packing list", []), [])
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["payload"]["model"] == "gpt-4o-mini"
    assert seen["payload"]["messages"][0]["role"] == "system"
    assert "test-key" not in json.dumps(seen["payload"])
    assert batch.actions[0].ref == "e2"
    assert batch.assertion.text == "Packing list"


def test_model_planner_requires_a_key(monkeypatch):
    monkeypatch.delenv("LOOP_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(PlannerError):
        ModelPlanner.from_env()
