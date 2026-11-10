"""Offline evidence judge. No browser, no network, no model call."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bench.arms import prompt_for
from bench.budget import LedgerMissing
from bench.harness import BenchmarkHarness
from bench.judge import check_url_contains
from bench.probe import main, probe_tasks
from bench.script_first import (
    PASS,
    ClaimedEvidence,
    PageEvidence,
    ScriptFirstClient,
    evidence_verdict,
    format_run_result,
)
from bench.tasks import HELD_OUT_TASK_IDS, get_held_out_tasks, markers_for_task

FIXTURES = Path(__file__).parent / "fixtures" / "evidence"
WIKI = markers_for_task("wv_wikipedia_search")
HN = markers_for_task("wv_hackernews_top")
ARTICLE = "https://en.wikipedia.org/wiki/Ada_Lovelace"
ENCODED = "https://en.wikipedia.org/wiki/Ada%20Lovelace"
SEARCH = "https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace"
CHARLES = "https://en.wikipedia.org/wiki/Charles_Babbage"


def _verdict(markers, url="", *, canonical="", title="", text="", selector="", claim_url="", answer=""):
    return evidence_verdict(
        markers,
        PageEvidence(
            url=url,
            title=title,
            canonical=canonical,
            text=text,
            selector_text=selector,
        ),
        ClaimedEvidence(url=claim_url, answer=answer),
    )


def _scored_is_real(verdict, url, canonical=""):
    if not verdict.scored_url:
        assert not url and not canonical
        return
    assert verdict.scored_url in {url, canonical}


def test_lenient_pages_fail_and_the_scored_url_is_not_rewritten():
    cases = [
        ("main page", _verdict(WIKI, "https://en.wikipedia.org/wiki/Main_Page"), "FAIL"),
        ("search page", _verdict(WIKI, SEARCH), "FAIL"),
        (
            "title names another article",
            _verdict(WIKI, CHARLES, title="Ada Lovelace - Wikipedia", text="Charles Babbage"),
            "FAIL",
        ),
        (
            "claimed url differs",
            _verdict(WIKI, CHARLES, text="Charles Babbage", claim_url=ARTICLE),
            "FAIL",
        ),
        (
            "empty answer",
            _verdict(
                markers_for_task("ho_wiki_eiffel_city"),
                "https://en.wikipedia.org/wiki/Eiffel_Tower",
                text="The Eiffel Tower is in Paris.",
                answer="",
            ),
            "FAIL",
        ),
        (
            "made-up answer",
            _verdict(
                markers_for_task("ho_wiki_eiffel_city"),
                "https://en.wikipedia.org/wiki/Eiffel_Tower",
                text="The Eiffel Tower is in Paris.",
                answer="Napoleon",
            ),
            "FAIL",
        ),
        (
            "hn story two",
            _verdict(
                HN,
                "https://news.ycombinator.com/",
                text="First Story\nSecond Story",
                selector="First Story",
                answer="Second Story",
            ),
            "FAIL",
        ),
        (
            "hn answer off-site",
            _verdict(
                HN,
                "https://example.com/story",
                text="First Story",
                selector="First Story",
                answer="First Story",
            ),
            "FAIL",
        ),
        ("empty evidence", _verdict(WIKI), "FAIL"),
    ]
    for name, verdict, expected in cases:
        assert verdict.verdict == expected, name
        assert verdict.verdict != PASS
    search = _verdict(WIKI, SEARCH)
    _scored_is_real(search, SEARCH)
    assert search.scored_url == SEARCH
    assert check_url_contains(SEARCH, "Ada_Lovelace").success is False
    titled = _verdict(WIKI, CHARLES, title="Ada Lovelace - Wikipedia")
    assert titled.scored_url == CHARLES
    assert "Ada_Lovelace" not in titled.scored_url


def test_real_pages_pass_without_rewriting_the_url():
    encoded = _verdict(WIKI, ENCODED, title="Ada Lovelace - Wikipedia", text="Ada Lovelace")
    assert encoded.verdict == PASS
    assert encoded.scored_url == ENCODED
    _scored_is_real(encoded, ENCODED)

    canonical = _verdict(
        WIKI,
        "https://en.wikipedia.org/?curid=401",
        canonical=ARTICLE,
        title="Ada Lovelace - Wikipedia",
        text="Ada Lovelace",
        claim_url=ARTICLE,
    )
    assert canonical.verdict == PASS
    assert canonical.scored_url == ARTICLE
    _scored_is_real(canonical, "https://en.wikipedia.org/?curid=401", ARTICLE)

    spaced = _verdict(
        HN,
        "https://news.ycombinator.com/",
        text="Show HN\nSecond Story",
        selector="Show HN",
        answer="Show HN  \n",
    )
    assert spaced.verdict == PASS
    assert spaced.scored_url == "https://news.ycombinator.com/"


def test_saved_snapshot_passes_in_one_step(tmp_path):
    saved = json.loads((FIXTURES / "wikipedia_encoded.json").read_text(encoding="utf-8"))
    hn = json.loads((FIXTURES / "hackernews_top.json").read_text(encoding="utf-8"))

    def _run(task_id, snapshot):
        page = snapshot["page"]
        claim = snapshot["claimed"]

        async def call_tool(name, arguments, nth):
            del name, arguments, nth
            return (
                format_run_result(
                    ok=True,
                    url=page["url"],
                    step_count=1,
                    title=page["title"],
                    canonical=page.get("canonical", ""),
                    h1=page.get("h1", ""),
                    text=page["text"],
                    selector_text=page.get("selector_text", ""),
                    claimed=claim,
                ),
                1.0,
            )

        from tests.test_script_first import _done_reply, _script_harness, _tool_reply

        harness, model, client = _script_harness(
            tmp_path,
            [_tool_reply("goto"), _tool_reply("repair"), _done_reply()],
            call_tool,
            max_steps=4,
        )
        result = asyncio.run(
            harness.run_task(
                task_id=task_id,
                task_description=snapshot["description"],
                start_url=snapshot["start_url"],
            )
        )
        assert client.calls == 1
        assert len(model.seen) == 1
        assert "END_STATE_FAILED" not in json.dumps(model.seen)
        assert result.success is True
        assert result.end_state == PASS
        assert result.total_steps == 1
        assert result.steps[-1].page_url == page["url"]
        verdict = _verdict(
            markers_for_task(task_id),
            page["url"],
            canonical=page.get("canonical", ""),
            title=page.get("title", ""),
            text=page["text"],
            selector=page.get("selector_text", ""),
            claim_url=claim.get("url", ""),
            answer=claim.get("answer", ""),
        )
        assert verdict.verdict == PASS
        assert verdict.scored_url in {page["url"], page.get("canonical", "")}

    _run("wv_wikipedia_search", saved)
    _run("wv_hackernews_top", hn)


def test_unknown_is_logged_and_is_not_a_success(tmp_path):
    from tests.test_script_first import _done_reply, _script_harness, _tool_reply

    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return format_run_result(ok=True, url="https://example.com/page", step_count=1, text="hello"), 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("read"), _tool_reply("again"), _done_reply()],
        call_tool,
        max_steps=4,
    )
    result = asyncio.run(
        harness.run_task(
            task_id="not-a-catalog-task",
            task_description="Read the page",
            start_url="https://example.com/",
        )
    )
    assert client.calls == 1
    assert result.success is False
    assert result.end_state == "UNKNOWN"
    assert result.success_reason.startswith("UNKNOWN")
    assert "END_STATE_FAILED" not in json.dumps(model.seen)
    saved = harness.save_result(result, "unknown-run")
    line = json.loads(saved.read_text(encoding="utf-8").splitlines()[-1])
    assert line["end_state"] == "UNKNOWN"
    assert line["success"] is False


def test_prompt_has_no_probe_answers_and_held_out_tasks_stay_judge_only():
    prompt = prompt_for("script_first")
    description = ScriptFirstClient().tools_for_claude()[0]["description"]
    leaked = (
        "Ada_Lovelace",
        "heapq.html",
        ".titleline",
        "news.ycombinator.com",
        "Eiffel_Tower",
        "1706.03762",
        "rust-lang/rust",
        "answer_equals_selector",
        "custname",
        "Unavailable For Legal Reasons",
        "9.3.1",
        "ch04-02-references-and-borrowing",
        "selectors-4",
        "lang_vacuum.html",
        "http-status-codes",
    )
    for secret in leaked:
        assert secret not in prompt
        assert secret not in description
    held = get_held_out_tasks()
    assert len(held) >= 5
    assert [task["id"] for task in held] == list(HELD_OUT_TASK_IDS)
    probe_ids = {task["id"] for task in probe_tasks()}
    assert probe_ids.isdisjoint(HELD_OUT_TASK_IDS)
    for task in held:
        assert task["end_markers"]
        blob = json.dumps(task["end_markers"])
        assert blob not in prompt
        assert blob not in description


def test_live_probe_refuses_when_the_ledger_is_missing(monkeypatch, tmp_path, capsys):
    missing = tmp_path / "no-ledger.json"
    monkeypatch.setenv("CU_SPEND_LEDGER", str(missing))
    assert main([]) == 2
    assert "invent a starting total" in capsys.readouterr().err
    assert not missing.exists()
    assert main(["--execute", "--arms", "script_first"]) == 2
    assert not missing.exists()
    with __import__("pytest").raises(LedgerMissing):
        from bench.budget import SpendLedger

        SpendLedger.load(missing)
