"""A script's own evidence is checked against the live page. No model call."""

from __future__ import annotations

import asyncio
import json

from bench.arms import prompt_for
from bench.judge import check_url_contains
from bench.script_cache import patch_request
from bench.script_first import (
    FAIL,
    PASS,
    UNKNOWN,
    EvidenceVerdict,
    PageEvidence,
    ScriptFirstClient,
    _PAGE_EVIDENCE_JS,
    check_returned_evidence,
    format_run_result,
    parse_task_script,
    repair_request,
    run_on_page,
    script_verdict,
)
from bench.tasks import markers_for_task
from tests.test_script_first import _done_reply, _script_harness, _tool_reply

ARTICLE = "https://en.wikipedia.org/wiki/Ada_Lovelace"
SEARCH = "https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace"
MAIN = "https://en.wikipedia.org/wiki/Main_Page"
CHARLES = "https://en.wikipedia.org/wiki/Charles_Babbage"
WIKI = markers_for_task("wv_wikipedia_search")
HN = markers_for_task("wv_hackernews_top")
PAGE = "Ada Lovelace was born in 1815."
SECRET = "phrase-the-page-does-not-show"


def _page(url: str, text: str, **claim) -> PageEvidence:
    return PageEvidence(url=url, title="Ada Lovelace - Wikipedia", text=text, **claim)


def test_returned_evidence_is_checked_without_a_model():
    matched = check_returned_evidence(
        WIKI,
        _page(ARTICLE, PAGE),
        {"url": ARTICLE, "key_text": "born in 1815", "values": [1815]},
    )
    assert matched.verdict == PASS
    assert matched.scored_url == ARTICLE

    spaced = check_returned_evidence(
        WIKI,
        _page(ARTICLE, PAGE),
        {"key_text": "born  in\t1815", "values": ["1815"]},
    )
    assert spaced.verdict == PASS

    missing = check_returned_evidence(
        WIKI,
        _page(ARTICLE, PAGE),
        {"key_text": SECRET, "url": ARTICLE},
    )
    assert missing.verdict == FAIL
    assert missing.verdict != PASS
    assert SECRET not in missing.reason
    assert missing.reason == "returned evidence is not on the page"

    absent_value = check_returned_evidence(
        WIKI,
        _page(ARTICLE, PAGE),
        {"values": ["1991"], "key_text": "born in 1815"},
    )
    assert absent_value.verdict == FAIL
    assert "1991" not in absent_value.reason

    nested = check_returned_evidence(
        WIKI,
        _page(ARTICLE, PAGE),
        {"values": [{"year": 1815}], "key_text": "born in 1815"},
    )
    assert nested.verdict == FAIL
    assert nested.reason == "returned value is not text"
    assert "year" not in nested.reason

    flagged = check_returned_evidence(
        WIKI,
        _page(ARTICLE, PAGE),
        {"values": [True]},
    )
    assert flagged.verdict == FAIL
    assert flagged.reason == "returned value is not text"

    unread = check_returned_evidence(
        WIKI,
        PageEvidence(url=ARTICLE),
        {"key_text": "born in 1815"},
    )
    assert unread.verdict == UNKNOWN
    assert unread.verdict != PASS

    # A phrase that is really on the page does not pass a task with no marker.
    undecided = check_returned_evidence(
        {},
        _page(ARTICLE, PAGE),
        {"key_text": "born in 1815", "values": [1815]},
    )
    assert undecided.verdict == UNKNOWN
    assert undecided.verdict != PASS


def test_returned_evidence_cannot_soften_the_judge():
    main = check_returned_evidence(
        WIKI,
        _page(MAIN, "Welcome to Wikipedia"),
        {"key_text": "Welcome", "url": ARTICLE},
    )
    assert main.verdict == FAIL
    assert main.scored_url == MAIN

    search = check_returned_evidence(
        WIKI,
        _page(SEARCH, "Ada Lovelace results"),
        {"key_text": "Ada Lovelace", "values": ["Ada Lovelace"]},
    )
    assert search.verdict == FAIL
    assert search.scored_url == SEARCH
    assert check_url_contains(SEARCH, "Ada_Lovelace").success is False

    other = check_returned_evidence(
        WIKI,
        _page(CHARLES, "Charles Babbage"),
        {"url": ARTICLE, "key_text": "Charles Babbage"},
    )
    assert other.verdict == FAIL
    assert other.reason == "claimed URL does not match the live page"
    assert other.scored_url == CHARLES

    second = check_returned_evidence(
        HN,
        PageEvidence(
            url="https://news.ycombinator.com/",
            text="First Story\nSecond Story",
            selector_text="First Story",
        ),
        {"answer": "Second Story", "key_text": "First Story"},
    )
    assert second.verdict == FAIL
    assert second.reason == "answer is not the marked value"

    bare = check_returned_evidence(WIKI, _page(ARTICLE, PAGE), {"url": ARTICLE})
    assert bare.verdict == PASS


class _LivePage:
    def __init__(self, text: str, returned):
        self.url = "about:blank"
        self.text = text
        self.returned = returned
        self.log: list = []

    async def goto(self, url, **kwargs):
        del kwargs
        self.url = url
        self.log.append(("goto", url))

    async def title(self):
        return "Ada Lovelace - Wikipedia"

    async def evaluate(self, source):
        self.log.append(("evaluate", source))
        if source == _PAGE_EVIDENCE_JS:
            return {
                "url": self.url,
                "title": "Ada Lovelace - Wikipedia",
                "canonical": "",
                "h1": "Ada Lovelace",
                "text": self.text,
            }
        return self.returned


_SCRIPT = """
page.goto("https://en.wikipedia.org/wiki/Ada_Lovelace");
return page.evaluate(() => ({url: location.href, title: document.title, key_text: "born in 1815", values: [1815], answer: ""}));
"""


def test_the_script_return_is_what_the_runner_checks():
    steps = parse_task_script(_SCRIPT)
    assert [step.kind for step in steps] == ["goto", "evaluate"]
    assert steps[1].function.startswith("() =>")

    page = _LivePage(PAGE, {"url": ARTICLE, "key_text": "born in 1815", "values": [1815], "answer": ""})
    text = asyncio.run(run_on_page(page, _SCRIPT, end_markers=WIKI))
    payload = json.loads(text.splitlines()[0])
    assert payload["claimed"]["key_text"] == "born in 1815"
    assert payload["claimed"]["values"] == ["1815"]
    assert payload["url"] == ARTICLE
    verdict, _ = script_verdict(WIKI, text, payload["url"])
    assert verdict.verdict == PASS
    assert verdict.scored_url == ARTICLE

    missed = _LivePage(PAGE, {"url": ARTICLE, "key_text": SECRET, "values": ["1815"]})
    missed_text = asyncio.run(run_on_page(missed, _SCRIPT, end_markers=WIKI))
    missed_payload = json.loads(missed_text.splitlines()[0])
    missed_verdict, _ = script_verdict(WIKI, missed_text, missed_payload["url"])
    assert missed_verdict.verdict == FAIL
    assert SECRET not in missed_verdict.reason

    broken = _LivePage(PAGE, {"url": ARTICLE, "values": [{"year": 1815}]})
    broken_text = asyncio.run(run_on_page(broken, _SCRIPT, end_markers=WIKI))
    broken_verdict, _ = script_verdict(WIKI, broken_text, ARTICLE)
    assert broken_verdict.verdict == FAIL
    assert broken_verdict.reason == "returned value is not text"


def _repair_lines(messages: list) -> list[str]:
    lines: list[str] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            lines.extend(content.splitlines())
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("content"), str):
                    lines.extend(block["content"].splitlines())
    return lines


def test_a_matching_return_stops_without_another_model_call(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return (
            format_run_result(
                ok=True,
                url=ARTICLE,
                step_count=1,
                title="Ada Lovelace - Wikipedia",
                text=PAGE,
                claimed={"url": ARTICLE, "key_text": "born in 1815", "values": [1815]},
            ),
            1.0,
        )

    harness, model, client = _script_harness(tmp_path, [_tool_reply("goto")], call_tool, max_steps=4)
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace",
            start_url=MAIN,
        )
    )
    assert client.calls == 1
    assert len(model.seen) == 1
    assert result.model_calls == 1
    assert result.success is True
    assert result.end_state == PASS


def test_unknown_return_is_not_a_success_and_does_not_call_the_model_again(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return (
            format_run_result(
                ok=True,
                url=ARTICLE,
                step_count=1,
                text=PAGE,
                claimed={"key_text": "born in 1815", "values": [1815]},
            ),
            1.0,
        )

    harness, model, client = _script_harness(tmp_path, [_tool_reply("read")], call_tool, max_steps=4)
    result = asyncio.run(
        harness.run_task(
            task_id="not-a-catalog-task",
            task_description="Read the page",
            start_url="https://example.com/",
        )
    )
    assert client.calls == 1
    assert len(model.seen) == 1
    assert result.model_calls == 1
    assert result.success is False
    assert result.end_state == UNKNOWN
    assert result.success_reason.startswith("UNKNOWN")
    assert "END_STATE_FAILED" not in json.dumps(model.seen)


def test_a_bad_return_repairs_once_without_leaking_into_the_prompt(tmp_path):
    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return (
            format_run_result(
                ok=True,
                url=ARTICLE,
                step_count=1,
                text=PAGE,
                selector_text=".titleline a",
                claimed={"url": ARTICLE, "key_text": SECRET},
            ),
            1.0,
        )

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("goto"), _done_reply()],
        call_tool,
        max_steps=4,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace",
            start_url=MAIN,
        )
    )
    assert client.calls == 1
    assert len(model.seen) == 2
    assert result.success is False
    assert result.end_state == FAIL
    assert result.success_reason == "returned evidence is not on the page"
    assert SECRET not in result.success_reason
    repairs = [line for line in _repair_lines(model.seen[1]) if line.startswith("END_STATE_FAILED")]
    assert repairs
    assert all(SECRET not in line and "selector_text" not in line for line in repairs)
    blob = json.dumps(model.seen)
    assert "selector_text" not in blob
    assert ".titleline" not in blob
    assert SECRET not in harness.system_prompt
    note = repair_request(ARTICLE, result.success_reason)
    assert SECRET not in note
    assert "selector_text" not in note
    hidden = patch_request(
        description="Search Wikipedia for Ada Lovelace",
        start_url=MAIN,
        script='page.goto("https://example.com/")',
        payload={
            "url": ARTICLE,
            "title": "Ada Lovelace - Wikipedia",
            "h1": "Ada Lovelace",
            "text": PAGE,
            "selector_text": ".titleline a",
            "claimed": {"key_text": SECRET, "answer": SECRET},
        },
        verdict=EvidenceVerdict(FAIL, result.success_reason, ARTICLE),
    )
    assert SECRET not in hidden
    assert "selector_text" not in hidden
    assert ".titleline" not in hidden


def test_prompts_ask_for_the_return_and_keep_answers_off_the_model():
    prompt = prompt_for("script_first")
    description = ScriptFirstClient().tools_for_claude()[0]["description"]
    for text in (prompt, description):
        assert "key_text" in text
        assert "values" in text
        assert "selector_text" not in text
        assert "Ada_Lovelace" not in text
        assert "heapq.html" not in text
        assert ".titleline" not in text
        assert SECRET not in text
