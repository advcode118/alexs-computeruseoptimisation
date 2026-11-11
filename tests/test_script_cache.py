"""Cached-script tier for script_first. No browser, no network, no model call."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bench.arms import SCRIPT_FIRST_MAX_CALLS, prompt_for
from bench.harness import BenchmarkHarness
from bench.script_cache import (
    PATCH_PROMPT,
    PATCH_TOOL,
    TIER_CACHE_HIT,
    TIER_FRESH,
    TIER_PATCHED,
    ScriptCache,
    apply_patch,
    page_fingerprint,
    patch_request,
)
from bench.script_first import (
    _PAGE_EVIDENCE_JS,
    FAIL,
    PASS,
    UNKNOWN,
    EvidenceVerdict,
    ScriptFirstClient,
    format_run_result,
    model_visible_script_result,
    script_verdict,
)
from bench.tasks import markers_for_task, task_message

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "evidence" / "wikipedia_encoded.json").read_text(encoding="utf-8")
)
TASK_ID = "wv_wikipedia_search"
DESCRIPTION = FIXTURE["description"]
START = FIXTURE["start_url"]
LINK = "Ada Lovelace"
RENAMED = "Ada Lovelace (mathematician)"
EVIDENCE = 'page.evaluate(() => ({url: location.href, title: document.title, h1: document.querySelector("h1")?.innerText, answer: ""}))'
CLICK_SCRIPT = "\n".join(
    [
        f"await page.goto({json.dumps(START)});",
        f'await page.getByRole("link", {{ name: "{LINK}" }}).click();',
        f"await {EVIDENCE};",
    ]
)

# The live article URL. The fixture also records the percent-encoded form.
# The shared check reads this URL, which contains the catalog token.
_ARTICLE_URL = "https://en.wikipedia.org/wiki/Ada_Lovelace"

_STATES = {
    "main": {
        "url": START,
        "title": "Wikipedia, the free encyclopedia",
        "canonical": START,
        "h1": "Main Page",
        "text": "Welcome to Wikipedia. From today's featured article: {link}",
    },
    "article": {**FIXTURE["page"], "url": _ARTICLE_URL},
    "babbage": {
        "url": "https://en.wikipedia.org/wiki/Charles_Babbage",
        "title": "Charles Babbage - Wikipedia",
        "canonical": "https://en.wikipedia.org/wiki/Charles_Babbage",
        "h1": "Charles Babbage",
        "text": "Charles Babbage was an English polymath.",
    },
}


class _Link:
    def __init__(self, page, name):
        self.page = page
        self.name = name

    async def click(self, **kwargs):
        self.page.log.append(("click", self.name))
        target = self.page.links.get(self.name) if self.page.state == "main" else None
        if target is None:
            raise TimeoutError(f'Timeout {kwargs.get("timeout")}ms exceeded waiting for link "{self.name}"')
        self.page.state = target


class _WikiPage:
    """Main_Page with links by visible name. Today's names can differ from the cached ones."""

    def __init__(self, links: dict):
        self.links = links
        self.state = ""
        self.log: list = []
        self.controls = None

    @property
    def url(self):
        return _STATES[self.state]["url"] if self.state else "about:blank"

    def _view(self) -> dict:
        view = dict(_STATES[self.state])
        view["text"] = view["text"].format(link=" | ".join(self.links))
        if self.controls is not None:
            view["controls"] = list(self.controls)
        return view

    def get_by_role(self, role, name=None):
        del role
        return _Link(self, name or "")

    async def goto(self, url, **kwargs):
        del kwargs
        self.log.append(("goto", url))
        if url in {FIXTURE["page"]["url"], _ARTICLE_URL}:
            self.state = "article"
            return
        for key, state in _STATES.items():
            if state["url"] == url:
                self.state = key
                return
        raise AssertionError(f"unexpected goto {url}")

    async def title(self):
        return self._view()["title"] if self.state else ""

    async def evaluate(self, source):
        view = self._view()
        if source == _PAGE_EVIDENCE_JS:
            return view
        return {"url": view["url"], "title": view["title"], "h1": view["h1"], "answer": view["h1"]}


def _evidence_script_collects_controls(source: str) -> bool:
    """True when the live read builds a controls list and returns it."""
    marker = "return {"
    start = source.rfind(marker)
    if start < 0:
        return False
    before, after = source[:start], source[start:]
    return "querySelectorAll(" in before and "controls.push(" in before and "controls" in after


class _EvidencePage(_WikiPage):
    """Returns control roles and names only when the evidence script actually reads them."""

    async def evaluate(self, source):
        if source == _PAGE_EVIDENCE_JS:
            view = self._view()
            if not _evidence_script_collects_controls(source):
                view.pop("controls", None)
            return view
        view = self._view()
        return {"url": view["url"], "title": view["title"], "h1": view["h1"], "answer": view["h1"]}


class _Model:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    async def create_message(self, messages, tools, system=None, max_tokens=4096):
        del max_tokens
        self.calls.append({"messages": messages, "tools": tools, "system": system})
        if not self.replies:
            raise AssertionError("unexpected model call")
        return self.replies.pop(0), 1.0


def _usage() -> dict:
    return {"input_tokens": 3, "output_tokens": 2}


def _script_reply(code: str) -> dict:
    return {
        "content": [{"type": "tool_use", "id": "s", "name": "run_script", "input": {"code": code}}],
        "stop_reason": "tool_use",
        "usage": _usage(),
    }


def _patch_reply(step: int, code: str) -> dict:
    return {
        "content": [{"type": "tool_use", "id": "p", "name": "patch_step", "input": {"step": step, "code": code}}],
        "stop_reason": "tool_use",
        "usage": _usage(),
    }


def _text_reply(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "usage": _usage()}


def _run(tmp_path, page, replies, *, task_id=TASK_ID):
    harness = BenchmarkHarness(
        api_key="local-test",
        runs_dir=tmp_path,
        arm="script_first",
        max_steps=SCRIPT_FIRST_MAX_CALLS,
        script_cache=ScriptCache(tmp_path / "script_cache.json"),
    )
    model = _Model(replies)
    harness.anthropic = model
    harness.mcp_client = ScriptFirstClient(page=page)
    result = asyncio.run(
        harness.run_task(task_id=task_id, task_description=DESCRIPTION, start_url=START)
    )
    return result, model, harness.script_cache


def _seed(tmp_path) -> ScriptCache:
    result, model, cache = _run(tmp_path, _WikiPage({LINK: "article"}), [_script_reply(CLICK_SCRIPT)])
    assert result.success is True
    assert result.end_state == PASS
    assert result.tier == TIER_FRESH
    assert result.model_calls == 1
    assert len(model.calls) == 1
    assert len(cache) == 1
    return cache


def test_cache_hit_passes_with_zero_model_calls(tmp_path):
    cache = _seed(tmp_path)
    stored = json.loads(cache.path.read_text(encoding="utf-8"))["entries"]
    entry = next(iter(stored.values()))
    assert set(entry) == {"intent", "site", "url_pattern", "script", "step_count", "saved_at", "fingerprint"}
    assert entry["fingerprint"].startswith("en.wikipedia.org|")
    assert entry["site"] == "en.wikipedia.org"
    assert entry["url_pattern"] == "https://en.wikipedia.org/*"
    assert entry["step_count"] == 3
    markers = markers_for_task(TASK_ID)
    assert markers["url_contains"] not in json.dumps(entry)
    assert "Special:Search" not in json.dumps(entry)

    page = _WikiPage({LINK: "article"})
    result, model, _cache = _run(tmp_path, page, [])
    assert model.calls == []
    assert result.model_calls == 0
    assert result.total_input_tokens == 0 and result.total_output_tokens == 0
    assert result.success is True
    assert result.end_state == PASS
    assert result.tier == TIER_CACHE_HIT
    assert result.total_steps == 1
    assert result.script_steps == 3
    assert result.steps[-1].page_url == _ARTICLE_URL
    assert page.log == [("goto", START), ("click", LINK)]

    saved = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path, arm="script_first").save_result(result, "warm")
    line = json.loads(saved.read_text(encoding="utf-8").splitlines()[-1])
    assert line["tier"] == TIER_CACHE_HIT
    assert line["model_calls"] == 0
    assert line["script_steps"] == 3


def test_changed_controls_are_a_miss_only_when_the_live_read_returns_them(tmp_path):
    """A same-host page with different roles and names is not a cache hit.

    The fake page withholds controls unless the evidence script builds and
    returns that list. A script that never reads them leaves both fingerprints
    empty, and the replay would stay a hit.
    """
    original = [{"role": "link", "name": LINK}, {"role": "link", "name": "About"}]
    changed = [{"role": "link", "name": LINK}, {"role": "link", "name": "Contact"}]
    first = _EvidencePage({LINK: "article"})
    first.controls = original
    seeded, _model, cache = _run(tmp_path, first, [_script_reply(CLICK_SCRIPT)])
    assert seeded.tier == TIER_FRESH
    stored = cache.lookup(DESCRIPTION, START)
    assert stored is not None
    assert stored.fingerprint != page_fingerprint("en.wikipedia.org", None)

    second = _EvidencePage({LINK: "article"})
    second.controls = changed
    fix = f'page.getByRole("link", {{ name: "{LINK}" }}).click()'
    result, model, cache = _run(tmp_path, second, [_patch_reply(2, fix)])
    assert result.tier != TIER_CACHE_HIT
    prompt = model.calls[0]["messages"][0]["content"]
    assert "live page fingerprint does not match the cached page" in prompt
    assert "Contact" not in prompt
    assert "selector_text" not in prompt
    assert cache.lookup(DESCRIPTION, START).fingerprint != stored.fingerprint


def test_fingerprint_mismatch_is_one_patch_and_not_a_hit(tmp_path):
    """The judge can pass and the replay is still a miss when the page shape changed."""
    original = [{"role": "link", "name": LINK}, {"role": "link", "name": "About"}]
    changed = [{"role": "link", "name": LINK}, {"role": "link", "name": "Contact"}]
    first = _WikiPage({LINK: "article"})
    first.controls = original
    seeded, _model, cache = _run(tmp_path, first, [_script_reply(CLICK_SCRIPT)])
    assert seeded.tier == TIER_FRESH
    stored = cache.lookup(DESCRIPTION, START)
    assert stored is not None and stored.fingerprint.startswith("en.wikipedia.org|")

    second = _WikiPage({LINK: "article"})
    second.controls = changed
    fix = f'page.getByRole("link", {{ name: "{LINK}" }}).click()'
    result, model, cache = _run(tmp_path, second, [_patch_reply(2, fix)])
    assert len(model.calls) == 1
    assert model.calls[0]["tools"] == [PATCH_TOOL]
    assert "live page fingerprint does not match the cached page" in model.calls[0]["messages"][0]["content"]
    assert result.success is True
    assert result.tier == TIER_PATCHED
    assert result.model_calls == 1
    assert cache.lookup(DESCRIPTION, START).fingerprint != stored.fingerprint

    third = _WikiPage({LINK: "article"})
    third.controls = changed
    again, model, _cache = _run(tmp_path, third, [])
    assert model.calls == []
    assert again.model_calls == 0
    assert again.tier == TIER_CACHE_HIT
    assert again.success is True


def test_stale_selector_triggers_exactly_one_patch_call(tmp_path):
    _seed(tmp_path)
    fix = f'page.getByRole("link", {{ name: "{RENAMED}" }}).click()'
    result, model, cache = _run(tmp_path, _WikiPage({RENAMED: "article"}), [_patch_reply(2, fix)])

    assert len(model.calls) == 1
    call = model.calls[0]
    assert call["tools"] == [PATCH_TOOL]
    assert call["system"] == PATCH_PROMPT
    prompt = call["messages"][0]["content"]
    assert f'2. page.getByRole("link", {{ name: "{LINK}" }}).click()' in prompt
    assert "Step 2 threw" in prompt
    assert RENAMED in prompt
    markers = markers_for_task(TASK_ID)
    assert markers["url_contains"] not in prompt
    assert all(token not in prompt for token in markers["deny"] if token != "Main_Page")

    assert result.success is True
    assert result.end_state == PASS
    assert result.tier == TIER_PATCHED
    assert result.model_calls == 1
    assert result.total_steps == 2
    assert result.script_steps == 3
    assert RENAMED in cache.lookup(DESCRIPTION, START).script

    again, model, _cache = _run(tmp_path, _WikiPage({RENAMED: "article"}), [])
    assert model.calls == []
    assert again.tier == TIER_CACHE_HIT
    assert again.success is True


def test_failed_patch_falls_back_to_fresh(tmp_path):
    _seed(tmp_path)
    still_wrong = 'page.getByRole("link", { name: "Ada Lovelace (writer)" }).click()'
    fresh = f'await page.goto({json.dumps(FIXTURE["page"]["url"])});\nawait {EVIDENCE};'
    result, model, cache = _run(
        tmp_path,
        _WikiPage({RENAMED: "article"}),
        [_patch_reply(2, still_wrong), _script_reply(fresh)],
    )

    assert len(model.calls) == 2
    assert model.calls[0]["tools"] == [PATCH_TOOL]
    assert model.calls[1]["system"] == prompt_for("script_first")
    assert model.calls[1]["messages"] == [{"role": "user", "content": task_message(DESCRIPTION, START)}]
    assert result.success is True
    assert result.end_state == PASS
    assert result.tier == TIER_FRESH
    assert result.model_calls == 2
    assert result.total_steps == 3
    assert result.script_steps == 2
    assert [step.step_number for step in result.steps] == [1, 2, 3]
    assert cache.lookup(DESCRIPTION, START).script.startswith(f'page.goto({json.dumps(FIXTURE["page"]["url"])})')


def test_a_wrong_page_replay_is_a_hit_that_fails_the_grade(tmp_path):
    """No answer key on replay. A self-consistent wrong page is a visible graded failure."""
    _seed(tmp_path)
    result, model, cache = _run(
        tmp_path,
        _WikiPage({LINK: "babbage"}),
        [_text_reply("TASK_FAILED")],
    )
    assert model.calls == []
    assert result.tier == TIER_CACHE_HIT
    assert result.end_state == PASS
    from bench.probe import grade_observation
    from bench.tasks import task_by_id

    last = result.steps[-1]
    ok, reason, _shared, _why = grade_observation(
        task_by_id(TASK_ID),
        last.page_url,
        last.page_text,
        answer=last.claimed_answer,
        run_verdict=result.end_state,
    )
    assert ok is False, reason


def test_the_live_run_never_reads_the_answer_key(tmp_path, monkeypatch):
    """Tripwire: script_first finishes with markers_for_task unavailable until the grade read."""
    def refuse(task_id):
        raise AssertionError(f"the live run read the answer key for {task_id}")

    async def no_grade_read(self, task_id, steps):
        del self, task_id, steps

    monkeypatch.setattr("bench.tasks.markers_for_task", refuse)
    monkeypatch.setattr(BenchmarkHarness, "_read_shared_page", no_grade_read)
    result, _model, _cache = _run(tmp_path, _WikiPage({LINK: "article"}), [_script_reply(CLICK_SCRIPT)])
    assert result.end_state == PASS


def test_fail_scripts_are_never_cached(tmp_path):
    fail_dir = tmp_path / "fail"
    fail_dir.mkdir()
    stay = f"await page.goto({json.dumps(START)});\nawait {EVIDENCE};"
    result, _model, cache = _run(
        fail_dir,
        _WikiPage({LINK: "article"}),
        [_script_reply(stay), _script_reply(stay), _text_reply("TASK_COMPLETE")],
    )
    assert result.end_state == FAIL
    assert result.success is False
    assert len(cache) == 0
    assert not cache.path.exists()

    unknown_dir = tmp_path / "unknown"
    unknown_dir.mkdir()
    # A task with no markers is cached on the live check alone, as it would be
    # for a real user. The answer key never decides what is saved.
    result, _model, cache = _run(
        unknown_dir,
        _WikiPage({LINK: "article"}),
        [_script_reply(CLICK_SCRIPT), _text_reply("TASK_COMPLETE")],
        task_id="not-a-catalog-task",
    )
    assert result.end_state == PASS
    assert len(cache) == 1

    direct = ScriptCache(tmp_path / "direct.json")
    for verdict in (EvidenceVerdict(FAIL, "x", START), EvidenceVerdict(UNKNOWN, "x", START), None):
        assert direct.save(DESCRIPTION, START, CLICK_SCRIPT, verdict) is False
    assert len(direct) == 0
    assert direct.save(DESCRIPTION, START, CLICK_SCRIPT, EvidenceVerdict(PASS, "ok", START)) is True
    assert direct.lookup(DESCRIPTION, "https://de.wikipedia.org/wiki/Main_Page") is None


def test_pass_script_is_stored_without_an_added_goto(tmp_path):
    """A PASS that did not navigate is stored as that script, not a new goto."""
    cache = ScriptCache(tmp_path / "exact.json")
    source = f"await {EVIDENCE};"
    assert cache.save(DESCRIPTION, START, source, EvidenceVerdict(PASS, "ok", START)) is True
    stored = cache.lookup(DESCRIPTION, START)
    assert stored is not None
    assert stored.script == EVIDENCE
    assert "page.goto" not in stored.script
    assert stored.step_count == 1


def test_warm_probe_reuses_one_new_cache_and_reports_tiers(monkeypatch, tmp_path):
    from bench.budget import SpendLedger
    from bench.probe import BOX_COMMANDS, cold_summary, empty_row, execute_probe, plan_probe, warm_summary

    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    caches: list = []

    async def fake_claude(arm, task, **kwargs):
        caches.append(kwargs.get("script_cache"))
        row = empty_row(arm, task["id"], reason="stub", skipped=False)
        row.update(claude=True, success=True, tier=TIER_FRESH if len(caches) <= 3 else TIER_CACHE_HIT)
        row.update(model_calls=1 if row["tier"] == TIER_FRESH else 0, steps=1, wall_ms=5.0)
        row["replay_hit"] = row["tier"] == TIER_CACHE_HIT
        return row

    monkeypatch.setattr("bench.probe.run_claude_arm", fake_claude)
    SpendLedger.seed(tmp_path / "spend.json").save()
    rows = asyncio.run(
        execute_probe(
            spend_path=tmp_path / "spend.json",
            runs_dir=tmp_path / "runs",
            warm_replay=True,
            arms=("script_first",),
        )
    )
    assert [(row["arm"], row["pass"]) for row in rows] == [("script_first", "cold")] * 3 + [
        ("script_first", "warm")
    ] * 3
    assert len(caches) == 6 and all(cache is caches[0] for cache in caches)
    assert isinstance(caches[0], ScriptCache)
    assert caches[0].path.parent == tmp_path / "runs"
    cold = cold_summary(rows)["script_first"]
    warm = warm_summary(rows)["script_first"]
    assert cold["tiers"] == {"cache_hit": 0, "patched": 0, "fresh": 3}
    assert warm["tiers"] == {"cache_hit": 3, "patched": 0, "fresh": 0}
    assert set(cold_summary(rows)) == {"script_first"}
    assert "script_first" not in warm_summary([{**row, "pass": "cold"} for row in rows])
    assert warm["model_calls"] == 0
    assert warm["replay_hit_rate"] == 1
    assert any("--arms script_first --warm-replay" in command for command in BOX_COMMANDS)
    assert plan_probe(arms="script_first", warm_replay=True)["warm_arms"][-1] == "script_first"


def test_patch_replaces_only_the_named_step():
    script = "\n".join(['page.goto("https://a.example/")', 'page.getByText("Old").click()', EVIDENCE])
    patched = apply_patch(script, 2, 'page.getByText("New").click()')
    assert patched.splitlines() == ['page.goto("https://a.example/")', 'page.getByText("New").click()', EVIDENCE]
    for step, code in ((0, "page.goto('https://a.example/')"), (4, EVIDENCE), (2, "fetch('x')")):
        try:
            apply_patch(script, step, code)
        except Exception as exc:
            assert type(exc).__name__ == "ScriptError"
        else:
            raise AssertionError(f"patch {step} should be refused")


def _marker_strings(markers: dict) -> list[str]:
    found: list[str] = []
    for key, value in markers.items():
        found.append(str(key))
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, (list, tuple)):
            found.extend(str(item) for item in value if str(item))
    return found


def _model_visible(calls: list[dict]) -> str:
    chunks = []
    for call in calls:
        chunks.append(json.dumps(call.get("messages")))
        system = call.get("system")
        if isinstance(system, str):
            chunks.append(system)
    return "\n".join(chunks)


def test_fail_repair_hides_selector_text_and_judge_markers(tmp_path):
    """A FAIL repair still uses selector_text, and the model never sees it."""
    secret = "JUDGE-ONLY-TOP-TITLE-9f3a"
    description = "Go to Hacker News and identify the title of the top story"
    start_url = "https://news.ycombinator.com/"
    page_text = "A different visible story"
    markers = markers_for_task("wv_hackernews_top")
    raw = format_run_result(
        ok=True,
        url=start_url,
        step_count=1,
        title="Hacker News",
        text=page_text,
        selector_text=secret,
        extracted=["wrong story"],
        claimed={"url": start_url, "answer": "wrong story"},
    )
    verdict, payload = script_verdict(markers, raw, start_url)
    assert verdict.verdict == FAIL
    assert payload.get("selector_text") == secret
    stripped = model_visible_script_result(raw)
    assert secret not in stripped
    assert "selector_text" not in stripped
    named = format_run_result(
        ok=True,
        url=start_url,
        step_count=1,
        title="Docs",
        text="documentation",
        controls=[
            {"role": "link", "name": "heapq.html"},
            {"role": "link", "name": "/library/heapq.html"},
            {"role": "link", "name": ".titleline"},
        ],
    )
    hidden = model_visible_script_result(named)
    assert "heapq.html" not in hidden
    assert "/library/heapq.html" not in hidden
    assert ".titleline" not in hidden
    assert "controls" not in hidden
    assert json.loads(named.splitlines()[0])["controls"][0]["name"] == "heapq.html"
    note = patch_request(
        description=description,
        start_url=start_url,
        script=EVIDENCE,
        payload=payload,
        verdict=verdict,
    )
    assert secret not in note
    assert "selector_text" not in note
    assert markers["answer_equals_selector"] not in note
    assert "wrong story" not in note

    class Model:
        def __init__(self):
            self.seen: list[dict] = []
            self._replies = [
                _script_reply('page.goto("https://news.ycombinator.com/")'),
                _text_reply("TASK_FAILED"),
            ]

        async def create_message(self, messages, tools, system=None, max_tokens=4096):
            del tools, max_tokens
            self.seen.append({"messages": messages, "system": system})
            return self._replies.pop(0), 1.0

    class Client:
        def tools_for_claude(self):
            return [{"name": "run_script", "description": "run", "input_schema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            del name, arguments
            return raw, 1.0

    harness = BenchmarkHarness(
        api_key="local-test",
        runs_dir=tmp_path,
        arm="script_first",
        max_steps=SCRIPT_FIRST_MAX_CALLS,
    )
    model = Model()
    harness.anthropic = model
    harness.mcp_client = Client()
    result = asyncio.run(
        harness.run_task(task_id="wv_hackernews_top", task_description=description, start_url=start_url)
    )
    assert result.end_state == FAIL
    assert result.success is False
    assert len(model.seen) == 2
    visible = _model_visible(model.seen)
    assert "END_STATE_FAILED" in visible
    allowed = "\n".join([description, start_url, "Hacker News", page_text, prompt_for("script_first")])
    for marker in _marker_strings(markers):
        if marker and marker not in allowed:
            assert marker not in visible, marker
    assert secret not in visible
    assert "selector_text" not in visible
    assert result.steps[0].selector_text == secret
    saved = json.loads(harness.save_result(result, "leak").read_text(encoding="utf-8").splitlines()[-1])
    assert saved["steps"][0]["selector_text"] == secret
