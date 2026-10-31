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


def test_parse_batch_maps_every_named_field():
    fills = [{"role": "textbox", "name": f"Field {index}", "text": f"v{index}"} for index in range(1, 13)]
    batch = parse_batch(
        {
            "reason": "fill the form",
            "done": True,
            "fills": fills,
            "submit": {"role": "button", "name": "Submit order"},
            "assertion": {"type": "all", "texts": ["v1", "v12"]},
        }
    )
    assert len(batch.actions) == 13
    assert batch.actions[-1].name == "Submit order"
    assert batch.assertion.texts == ("v1", "v12")


def test_direct_form_is_one_batch_without_a_model():
    from loop.actions import Control, Observation
    from loop.planner import direct_batch

    controls = [Control(f"e{index}", "textbox", f"Field {index}", "") for index in range(1, 5)]
    controls.append(Control("e9", "button", "Submit order", ""))
    task = "\n".join(
        [
            "Fill and submit the form.",
            "Field 1: one",
            "Field 2: two",
            "Field 3: three",
            "Field 4: four",
        ]
    )
    batch = direct_batch(task, Observation("https://example.test/form", "Form", controls), [])
    assert batch is not None
    assert len(batch.actions) == 5
    assert batch.done is True


def test_find_ref_requires_a_unique_name():
    from loop.actions import Control, Observation
    from loop.planner import find_ref

    controls = [
        Control("e1", "link", "heapq", ""),
        Control("e2", "link", "heapq.heapify", ""),
        Control("e3", "textbox", "Customer name:", ""),
        Control("e4", "textbox", "Quick search", ""),
        Control("e5", "textbox", "Quick search", ""),
    ]
    observation = Observation("https://example.test", "Docs", controls)
    assert find_ref(observation, role="link", name="heapq.heapify") == "e2"
    assert find_ref(observation, role="link", name="heapq") == "e1"
    assert find_ref(observation, role="textbox", name="Customer name") == "e3"
    assert find_ref(observation, role="textbox", name="Quick search") == "e4"


def test_choose_parses_a_visible_option():
    batch = parse_batch(
        {
            "reason": "set the dropdown",
            "done": False,
            "actions": [{"type": "choose", "role": "combobox", "name": "Size", "option": "Medium"}],
        }
    )
    assert batch.actions[0].option == "Medium"
    assert batch.actions[0].name == "Size"
    pressed = parse_batch({"actions": [{"type": "key", "key": "Enter", "ref": "e1"}]})
    assert pressed.actions[0].key == "Enter"


def test_ordinary_language_is_left_for_the_model():
    from loop.actions import Control, Observation
    from loop.planner import direct_batch

    observation = Observation(
        "https://en.wikipedia.org/wiki/Main_Page",
        "Wikipedia, the free encyclopedia",
        [
            Control("e1", "link", "Wikipedia", ""),
            Control("e2", "textbox", "Search Wikipedia", ""),
            Control("e3", "button", "Search", ""),
        ],
    )
    task = (
        "Look up the Countess of Lovelace on English Wikipedia, "
        "open her article, and open the section about her childhood."
    )
    assert direct_batch(task, observation, []) is None


def test_model_planner_requires_a_key(monkeypatch):
    monkeypatch.delenv("LOOP_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(PlannerError):
        ModelPlanner.from_env()


def test_model_planner_records_token_usage():
    from loop.actions import Observation
    from loop.planner import _usage_counts

    assert _usage_counts({"usage": {"prompt_tokens": 5, "completion_tokens": 2}}) == {
        "input": 5,
        "output": 2,
    }
    assert _usage_counts({"usage": {"input_tokens": 7, "output_tokens": 1}}) == {
        "input": 7,
        "output": 1,
    }
    assert _usage_counts({}) == {"input": 0, "output": 0}

    def transport(url, headers, payload):
        del url, headers, payload
        return {
            "content": json.dumps({"reason": "done", "done": True, "actions": []}),
            "usage": {"input": 11, "output": 4},
        }

    planner = ModelPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="gpt-4o-mini",
        transport=transport,
    )
    planner.plan("Add milk", Observation("https://example.test", "Packing list", []), [])
    assert planner.calls == 1
    assert planner.input_tokens == 11
    assert planner.output_tokens == 4
