"""Replay cache for do_task_segment. No API key and no network.

The child is a fake. A stored sequence is replayed by role and name.
decide() and the model stay out of a matching replay. A failed step falls
back to decide(), then the cheap client only when one was supplied.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from loop.planner import ClaudePlanner, FastClient
from proxy.page import observation_from_tool_text
import proxy.segment as segment
from proxy.replay import DEFAULT_CACHE_PATH, cache_key, load_sequence, resolve_cache_path
from proxy.segment import dispatch

SEARCH_TASK = "Search Wikipedia for Ada Lovelace and confirm the article title."
PACK_TASK = "Add milk to the packing list"
OTHER_TASK = "Read the Wikipedia main page headline"


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
SEARCH_NEW_REFS = _page(
    "https://en.wikipedia.org/wiki/Main_Page",
    "Wikipedia, the free encyclopedia",
    '- textbox "Search Wikipedia" [ref=e40]\n- button "Search" [ref=e50]',
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
NO_BUTTON = _page(
    "https://en.wikipedia.org/wiki/Main_Page",
    "Wikipedia, the free encyclopedia",
    '- textbox "Search Wikipedia" [ref=e4]',
)
WRONG = _page(
    "https://en.wikipedia.org/wiki/Main_Page",
    "Wikipedia, the free encyclopedia",
    '- heading "Welcome" [ref=e1]',
)
OTHER_DOMAIN = _page(
    "https://example.test/wiki",
    "Wikipedia, the free encyclopedia",
    '- textbox "Search Wikipedia" [ref=e4]\n- button "Search" [ref=e5]',
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


class ClickErrorChild(FakeChild):
    async def call_tool(self, name, arguments):
        if name == "browser_click":
            self.calls.append((name, arguments or {}))
            return {"content": [{"type": "text", "text": "click failed"}], "isError": True}
        return await FakeChild.call_tool(self, name, arguments)


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


def _segment(child, task: str, tmp_path, **kwargs) -> dict:
    result = asyncio.run(
        dispatch(
            child,
            "do_task_segment",
            {"task": task},
            env_path=str(tmp_path / "missing.env"),
            **kwargs,
        )
    )
    return _payload(result)


def _cache(tmp_path):
    return tmp_path / "replay-cache.sqlite"


def _search_key():
    observation, _yaml = observation_from_tool_text(SEARCH)
    return cache_key(SEARCH_TASK, observation)


def _count_decide(monkeypatch):
    seen = {"n": 0}
    real = segment.decide

    def wrapped(*args, **kwargs):
        seen["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(segment, "decide", wrapped)
    return seen


def _forbid_model(monkeypatch):
    def forbid_decide(*_args, **_kwargs):
        raise AssertionError("decide() during replay")

    def forbid_plan(*_args, **_kwargs):
        raise AssertionError("model call")

    monkeypatch.setattr(segment, "decide", forbid_decide)
    monkeypatch.setattr(FastClient, "plan", forbid_plan)


def test_cache_key_uses_domain_task_and_roles_not_refs():
    first, _yaml = observation_from_tool_text(SEARCH)
    shifted, _yaml = observation_from_tool_text(SEARCH_NEW_REFS)
    other, _yaml = observation_from_tool_text(OTHER_DOMAIN)
    assert cache_key(SEARCH_TASK, first) == cache_key(SEARCH_TASK, shifted)
    domain, task, shape = cache_key(SEARCH_TASK, first)
    assert domain == "en.wikipedia.org"
    assert task == "search wikipedia for ada lovelace and confirm the article title"
    assert shape == "button\tsearch\ntextbox\tsearch wikipedia"
    assert "e4" not in shape and "e40" not in shape
    assert cache_key(SEARCH_TASK, other)[0] == "example.test"
    assert cache_key(OTHER_TASK, first) != cache_key(SEARCH_TASK, first)


def test_sequence_is_recorded_only_after_do_task_segment_succeeds(tmp_path):
    missed = _segment(FakeChild([PACKING]), PACK_TASK, tmp_path)
    assert missed["status"] == "stopped"
    assert not _cache(tmp_path).exists()

    child = FakeChild([SEARCH, ARTICLE])
    body = _segment(child, SEARCH_TASK, tmp_path)
    assert body["ok"] is True
    assert body["tier"] == "direct"
    assert body["model_calls"] == 0
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_type",
        "browser_evaluate",
        "browser_click",
        "browser_evaluate",
        "browser_snapshot",
    ]
    stored = load_sequence(_cache(tmp_path), *_search_key())
    assert stored is not None
    assert stored["actions"] == [
        {
            "tool": "browser_type",
            "role": "textbox",
            "name": "Search Wikipedia",
            "value": "Ada Lovelace",
        },
        {"tool": "browser_click", "role": "button", "name": "Search", "value": ""},
    ]
    assert stored["assertions"] == [{"type": "title", "text": "Ada Lovelace", "after": 2}]
    blob = json.dumps(stored)
    assert "e4" not in blob and "e5" not in blob and '"ref"' not in blob


def test_fast_act_does_not_write_the_replay_cache(tmp_path):
    child = FakeChild([SEARCH, ARTICLE])
    result = asyncio.run(dispatch(child, "fast_act", {"task": SEARCH_TASK}))
    body = _payload(result)
    assert body["ok"] is True
    assert not _cache(tmp_path).exists()


def test_replay_runs_with_no_model_and_refinds_when_refs_differ(tmp_path, monkeypatch):
    recorded = _segment(FakeChild([SEARCH, ARTICLE]), SEARCH_TASK, tmp_path)
    assert recorded["tier"] == "direct"
    _forbid_model(monkeypatch)
    client = FastClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        transport=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("transport")),
    )
    child = FakeChild([SEARCH_NEW_REFS, SEARCH_NEW_REFS, ARTICLE])
    body = _segment(child, SEARCH_TASK, tmp_path, client=client)
    assert body["ok"] is True
    assert body["status"] == "done"
    assert body["tier"] == "replay"
    assert body["needs_model"] is False
    assert body["model_calls"] == 0
    assert body["url"] == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert body["actions"] == ["fill e40 'Ada Lovelace'", "click e50"]
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_type",
        "browser_evaluate",
        "browser_snapshot",
        "browser_click",
        "browser_evaluate",
        "browser_snapshot",
    ]
    assert child.calls[1][1] == {
        "target": "e40",
        "element": 'textbox "Search Wikipedia"',
        "text": "Ada Lovelace",
    }
    assert child.calls[4][1]["target"] == "e50"
    stored = load_sequence(_cache(tmp_path), *_search_key())
    assert stored is not None
    assert "e40" not in json.dumps(stored)


def test_replay_falls_back_when_a_step_cannot_be_refound(tmp_path, monkeypatch):
    _segment(FakeChild([SEARCH, ARTICLE]), SEARCH_TASK, tmp_path)
    seen = _count_decide(monkeypatch)
    seen_page = {}
    real = segment.decide

    def wrapped(*args, **kwargs):
        seen_page["observation"] = args[1]
        return real(*args, **kwargs)

    monkeypatch.setattr(segment, "decide", wrapped)
    sent = []

    def transport(url, headers, payload):
        sent.append((url, headers, payload))
        return json.dumps(
            {
                "reason": "The search button is gone.",
                "done": True,
                "actions": [],
                "assertion": None,
            }
        )

    client = FastClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        transport=transport,
    )
    child = FakeChild([SEARCH, NO_BUTTON])
    body = _segment(child, SEARCH_TASK, tmp_path, client=client)
    assert seen["n"] == 1
    assert body["ok"] is True
    assert body["tier"] == "fast"
    assert body["model_calls"] == 1
    assert body["actions"] == ["fill e4 'Ada Lovelace'"]
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_type",
        "browser_evaluate",
        "browser_snapshot",
    ]
    assert len(sent) == 1
    assert sent[0][0] == "https://example.test/v1/chat/completions"
    assert "anthropic" not in sent[0][0]
    kept = load_sequence(_cache(tmp_path), *_search_key())
    assert kept is not None
    assert [step["tool"] for step in kept["actions"]] == ["browser_type", "browser_click"]
    # The page stays on the post-type snapshot. decide() sees that page, not a rewind.
    fallen = seen_page["observation"]
    assert fallen.url == "https://en.wikipedia.org/wiki/Main_Page"
    assert [control.role for control in fallen.controls] == ["textbox"]
    missing, _yaml = observation_from_tool_text(NO_BUTTON)
    assert load_sequence(_cache(tmp_path), *cache_key(SEARCH_TASK, missing)) is None


def test_replay_falls_back_when_the_action_fails(tmp_path, monkeypatch):
    _segment(FakeChild([SEARCH, ARTICLE]), SEARCH_TASK, tmp_path)
    seen = _count_decide(monkeypatch)
    _forbid_model_plan(monkeypatch)
    child = ClickErrorChild([SEARCH, SEARCH, SEARCH])
    body = _segment(child, SEARCH_TASK, tmp_path)
    assert seen["n"] == 1
    assert body["ok"] is False
    assert body["status"] == "failed"
    assert body["tier"] == "direct"
    assert body["model_calls"] == 0
    assert "click failed" in body["summary"]
    assert [name for name, _args in child.calls].count("browser_click") == 2


def test_replay_falls_back_when_an_assertion_fails(tmp_path, monkeypatch):
    _segment(FakeChild([SEARCH, ARTICLE]), SEARCH_TASK, tmp_path)
    seen = _count_decide(monkeypatch)
    _forbid_model_plan(monkeypatch)
    child = FakeChild([SEARCH, SEARCH, WRONG])
    body = _segment(child, SEARCH_TASK, tmp_path)
    assert seen["n"] == 1
    assert body["ok"] is False
    assert body["status"] == "stopped"
    assert body["needs_model"] is True
    assert body["tier"] == "planner"
    assert body["model_calls"] == 0
    assert "NEBIUS_API_KEY" in body["summary"]
    assert [name for name, _args in child.calls] == [
        "browser_snapshot",
        "browser_type",
        "browser_evaluate",
        "browser_snapshot",
        "browser_click",
        "browser_evaluate",
        "browser_snapshot",
    ]


def test_replay_does_not_cross_domain_or_task(tmp_path, monkeypatch):
    _segment(FakeChild([SEARCH, ARTICLE]), SEARCH_TASK, tmp_path)
    seen = _count_decide(monkeypatch)
    other = _segment(FakeChild([OTHER_DOMAIN, ARTICLE]), SEARCH_TASK, tmp_path)
    assert seen["n"] == 1
    assert other["tier"] == "direct"
    assert other["ok"] is True
    headline = _segment(FakeChild([SEARCH]), OTHER_TASK, tmp_path)
    assert seen["n"] == 2
    assert headline["status"] == "stopped"
    assert headline["tier"] == "planner"


def test_cache_path_argument_overrides_the_environment(tmp_path, monkeypatch):
    chosen = tmp_path / "chosen.sqlite"
    body = _segment(FakeChild([SEARCH, ARTICLE]), SEARCH_TASK, tmp_path, cache_path=chosen)
    assert body["ok"] is True
    assert chosen.exists()
    assert not _cache(tmp_path).exists()
    observation, _yaml = observation_from_tool_text(SEARCH)
    assert load_sequence(chosen, *cache_key(SEARCH_TASK, observation)) is not None
    monkeypatch.delenv("REPLAY_CACHE_PATH", raising=False)
    monkeypatch.setattr("proxy.replay.DEFAULT_CACHE_PATH", tmp_path / "from-default.sqlite")
    assert resolve_cache_path(None) == tmp_path / "from-default.sqlite"
    assert resolve_cache_path(chosen) == chosen
    assert DEFAULT_CACHE_PATH.name == "replay-cache.sqlite"


def test_default_cache_file_is_gitignored():
    ignore = (DEFAULT_CACHE_PATH.parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "proxy/replay-cache.sqlite" in ignore
    assert DEFAULT_CACHE_PATH.parent.name == "proxy"


def test_softened_key_replays_reordered_controls_for_a_normalized_task(tmp_path, monkeypatch):
    _segment(FakeChild([SEARCH, ARTICLE]), SEARCH_TASK, tmp_path)
    _forbid_model(monkeypatch)
    reordered = _page(
        "https://en.wikipedia.org/wiki/Main_Page",
        "Wikipedia, the free encyclopedia",
        '- button "Search" [ref=e9]\n- generic [ref=e3]\n- textbox "Search Wikipedia" [ref=e8]',
    )
    extra = _page(
        "https://en.wikipedia.org/wiki/Main_Page",
        "Wikipedia, the free encyclopedia",
        '- textbox "Search Wikipedia" [ref=e4]\n- button "Search" [ref=e5]\n- link "Log in" [ref=e6]',
    )
    same, _yaml = observation_from_tool_text(SEARCH)
    moved, _yaml = observation_from_tool_text(reordered)
    grown, _yaml = observation_from_tool_text(extra)
    assert cache_key("  SEARCH WIKIPEDIA FOR ADA LOVELACE AND CONFIRM THE ARTICLE TITLE. ", moved) == cache_key(
        SEARCH_TASK, same
    )
    assert cache_key(SEARCH_TASK, grown) != cache_key(SEARCH_TASK, same)
    child = FakeChild([reordered, reordered, ARTICLE])
    body = _segment(
        child,
        "  search wikipedia for ada lovelace and confirm the article title. ",
        tmp_path,
    )
    assert body["ok"] is True
    assert body["tier"] == "replay"
    assert body["model_calls"] == 0
    assert body["actions"] == ["fill e8 'Ada Lovelace'", "click e9"]


def _forbid_model_plan(monkeypatch):
    def wrapped(*_args, **_kwargs):
        raise AssertionError("model call")

    monkeypatch.setattr(FastClient, "plan", wrapped)
