import json
import time

import pytest

from loop.actions import ActionBatch, ActionError, Click, Control, Observation, PlannerError, parse_batch
from loop.planner import (
    CLAUDE_MODEL,
    ClaudePlanner,
    FastClient,
    ModelPlanner,
    Router,
    find_ref,
    interpret_model_content,
    load_step5_env,
    matching_controls,
    parse_item,
    parse_model_content,
    route_decision,
    select_soonest_model,
)


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


def _controls():
    return [
        Control("e1", "textbox", "Item", ""),
        Control("e2", "button", "Add", ""),
        Control("e3", "button", "Add extra", ""),
    ]


def test_find_ref_is_the_first_match_and_the_router_counts():
    observation = Observation("https://example.test/list", "Packing list", _controls())
    assert find_ref(observation, role="button", name="Add") == "e2"
    assert [control.ref for control in matching_controls(observation, role="button", name="Add")] == ["e2", "e3"]
    previous = Observation("https://example.test/home", "Home", [Control("e9", "button", "Add", "")])
    batch = ActionBatch("The add button is next.", [Click("e9")], None, False)
    tier, short = route_decision(
        first=False,
        retry=False,
        previous_batch=batch,
        previous_observation=previous,
        observation=observation,
    )
    assert tier == "fast"
    assert [control.ref for control in short] == ["e2", "e3"]

    unique = Observation(
        "https://example.test/next",
        "Next",
        [Control("e4", "button", "Next", ""), Control("e5", "textbox", "Item", "")],
    )
    named = ActionBatch("Go on.", [Click("e8")], None, False)
    earlier = Observation("https://example.test/home", "Home", [Control("e8", "button", "Next", "")])
    tier, short = route_decision(
        first=True,
        retry=False,
        previous_batch=named,
        previous_observation=earlier,
        observation=unique,
    )
    assert tier == "planner"
    tier, short = route_decision(
        first=False,
        retry=True,
        previous_batch=named,
        previous_observation=earlier,
        observation=unique,
    )
    assert tier == "planner"
    tier, short = route_decision(
        first=False,
        retry=False,
        previous_batch=named,
        previous_observation=earlier,
        observation=unique,
    )
    assert tier == "direct"
    assert short[0].ref == "e4"

    again = Observation(earlier.url, "Home", [Control("e8", "button", "Next", "")])
    tier, short = route_decision(
        first=False,
        retry=False,
        previous_batch=named,
        previous_observation=earlier,
        observation=again,
    )
    assert tier == "fast"


def test_null_model_content_finishes_after_a_passed_assertion():
    history = [
        {
            "reason": "Add milk.",
            "actions": ["fill e1 'milk'", "click e2"],
            "done": False,
            "assertion": {"ok": True, "detail": "page contains 'milk'"},
        }
    ]
    batch = interpret_model_content(None, history)
    assert batch.done is True
    assert batch.actions == []
    with pytest.raises(PlannerError) as caught:
        interpret_model_content(None, [])
    assert "strip" not in str(caught.value)
    with pytest.raises(PlannerError):
        parse_model_content(None)


def test_fast_client_sends_the_short_list_once():
    seen = []

    def transport(url, headers, payload):
        seen.append((url, headers, payload))
        return json.dumps(
            {"reason": "click add", "done": False, "actions": [{"type": "click", "ref": "e2"}], "assertion": None}
        )

    client = FastClient(api_key="test-key", base_url="https://example.test/v1/", model="fast-test", transport=transport)
    controls = [Control("e2", "button", "Add", ""), Control("e3", "button", "Add", "")]
    batch = client.plan("Add milk", controls, [])
    assert len(seen) == 1
    url, headers, payload = seen[0]
    assert url == "https://example.test/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert payload["model"] == "fast-test"
    body = json.dumps(payload)
    assert "test-key" not in body
    user = json.loads(payload["messages"][1]["content"])
    assert [control["ref"] for control in user["controls"]] == ["e2", "e3"]
    assert "e1" not in payload["messages"][1]["content"]
    assert batch.actions[0].ref == "e2"


def test_empty_fast_model_keeps_the_soonest_valid_json():
    def probe(model):
        if model == "slow-bad":
            time.sleep(0.4)
            return False
        if model == "slow-ok":
            time.sleep(0.4)
            return True
        return model == "quick"

    assert select_soonest_model(("slow-bad", "slow-ok", "quick"), probe) == "quick"

    FastClient.kept_model = ""
    calls = []

    def transport(url, headers, payload):
        del url, headers
        calls.append(payload["model"])
        if payload["model"] == "slow-bad":
            time.sleep(0.4)
            return "not json"
        return json.dumps({"reason": "ok", "done": True, "actions": [], "assertion": None})

    try:
        client = FastClient(
            api_key="test-key",
            base_url="https://example.test/v1",
            model="",
            transport=transport,
            candidates=("slow-bad", "quick"),
        )
        batch = client.plan("Add milk", [Control("e2", "button", "Add", "")], [])
        assert client.model == "quick"
        assert batch.done is True
        assert "test-key" not in json.dumps(calls)
        client.plan("Add milk", [Control("e2", "button", "Add", "")], [])
        assert calls.count("quick") >= 2
    finally:
        FastClient.kept_model = ""


def test_claude_planner_uses_a_fake_transport():
    seen = {}

    def transport(url, headers, payload):
        seen["url"] = url
        seen["headers"] = headers
        seen["payload"] = payload
        return json.dumps({"reason": "done", "done": True, "actions": [], "assertion": None})

    planner = ClaudePlanner(api_key="test-ant", model=CLAUDE_MODEL, fixture_url="https://example.test/fixture", transport=transport)
    batch = planner.plan("Add milk", Observation("about:blank", "", []), [])
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "test-ant"
    assert seen["payload"]["model"] == CLAUDE_MODEL
    assert "test-ant" not in json.dumps(seen["payload"])
    user = json.loads(seen["payload"]["messages"][0]["content"])
    assert user["start_url"] == "https://example.test/fixture"
    assert batch.done is True


def test_router_env_file_beats_the_environment_and_hides_the_key(tmp_path, monkeypatch):
    secret = "secret-nebius-key"
    path = tmp_path / "step5.env"
    path.write_text(
        "ANTHROPIC_API_KEY=file-ant\nNEBIUS_API_KEY=file-nebius\nNEBIUS_BASE_URL=https://example.test/v1\nNEBIUS_FAST_MODEL=kept-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-ant")
    monkeypatch.setenv("NEBIUS_API_KEY", secret)
    values = load_step5_env(str(path))
    assert values["ANTHROPIC_API_KEY"] == "file-ant"
    assert values["NEBIUS_FAST_MODEL"] == "kept-model"
    router = Router.from_env("https://example.test/fixture", str(path))
    assert router.use_router is True
    assert router.claude.model == CLAUDE_MODEL
    assert router.fast.model == "kept-model"
    assert router.fast.api_key == "file-nebius"

    missing = tmp_path / "missing.env"
    missing.write_text(f"NEBIUS_API_KEY={secret}\n", encoding="utf-8")
    with pytest.raises(PlannerError) as caught:
        Router.from_env("https://example.test/fixture", str(missing))
    assert secret not in str(caught.value)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-ant")
    monkeypatch.setenv("NEBIUS_API_KEY", "env-nebius")
    monkeypatch.setenv("NEBIUS_FAST_MODEL", "env-model")
    fallback = load_step5_env(str(tmp_path / "absent.env"))
    assert fallback["ANTHROPIC_API_KEY"] == "env-ant"
    assert fallback["NEBIUS_FAST_MODEL"] == "env-model"
