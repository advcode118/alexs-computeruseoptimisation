"""One fail-closed grade for every arm. No browser, no network, no model call."""

from __future__ import annotations

import asyncio
import json

from bench.harness import StepMetrics, TaskResult, spoken_claim
from bench.probe import grade_arm, shared_end_state
from bench.script_first import format_run_result, mcp_evaluate_value
from bench.tasks import markers_for_task

HN = "https://news.ycombinator.com/"
EIFFEL = "https://en.wikipedia.org/wiki/Eiffel_Tower"
ARTICLE = "https://en.wikipedia.org/wiki/Ada_Lovelace"


def _hn_task() -> dict:
    return {
        "id": "wv_hackernews_top",
        "description": "Go to Hacker News and identify the title of the top story",
        "start_url": HN,
        "end_markers": markers_for_task("wv_hackernews_top"),
    }


def _eiffel_task() -> dict:
    task = {
        "id": "ho_wiki_eiffel_city",
        "description": "Open the Wikipedia article for the Eiffel Tower and report the city it stands in",
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "check_text": "Paris",
        "end_markers": markers_for_task("ho_wiki_eiffel_city"),
    }
    return task


def _wiki_task() -> dict:
    return {
        "id": "wv_wikipedia_search",
        "description": "Search Wikipedia for Ada Lovelace",
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "check_url_contains": "Ada_Lovelace",
        "end_markers": markers_for_task("wv_wikipedia_search"),
    }


def test_hacker_news_check_is_the_live_title():
    task = _hn_task()
    missing, why = shared_end_state(task, HN, "Fixture Story")
    assert missing is False
    assert missing is not None
    assert why != "no deterministic check; LLM judge was not called"

    stayed, stayed_why = shared_end_state(task, HN, "Fixture Story", answer="Fixture Story")
    assert stayed is False
    assert "empty" in stayed_why or "not" in stayed_why

    second, _second_why = shared_end_state(
        task,
        HN,
        "Fixture Story\nSecond Story",
        selector_text="Fixture Story",
        answer="Second Story",
        page_text="Fixture Story\nSecond Story",
    )
    assert second is False

    matched, matched_why = shared_end_state(
        task,
        HN,
        "",
        selector_text="Fixture Story",
        answer="Fixture Story\n",
        page_text="Fixture Story\nSecond Story",
    )
    assert matched is True
    assert "Fixture Story" not in task["description"]


def test_signals_must_agree_and_unknown_is_not_success():
    eiffel = _eiffel_task()
    wiki = _wiki_task()

    disagreed, reason, shared_ok, shared_reason = grade_arm(
        eiffel,
        EIFFEL,
        "The Eiffel Tower is a wrought-iron lattice tower.",
        evidence="PASS",
        evidence_reason="the page evidence matches the markers",
    )
    assert shared_ok is False
    assert disagreed is False
    assert reason == "Missing text: ['Paris']"
    assert "Paris" in shared_reason

    agreed, agree_reason, agree_ok, _agree_shared = grade_arm(
        eiffel,
        EIFFEL,
        "The tower stands in Paris.",
        evidence="PASS",
    )
    assert agree_ok is True
    assert agreed is True
    assert "Paris" in agree_reason

    unknown, unknown_reason, unknown_ok, _unknown_shared = grade_arm(
        eiffel,
        EIFFEL,
        "The tower stands in Paris.",
        evidence="UNKNOWN",
        evidence_reason="UNKNOWN: page text was not read",
    )
    assert unknown_ok is True
    assert unknown is False
    assert unknown_reason.startswith("UNKNOWN")

    judge_fail, fail_reason, fail_ok, _fail_shared = grade_arm(
        wiki,
        ARTICLE,
        "",
        evidence="FAIL",
        evidence_reason="answer does not satisfy the marker",
    )
    assert fail_ok is True
    assert judge_fail is False
    assert fail_reason == "answer does not satisfy the marker"

    word, word_reason, word_ok, _word_shared = grade_arm(
        _hn_task(),
        HN,
        "Fixture Story",
        completed=True,
        completion_reason="Task completed successfully",
    )
    assert word_ok is False
    assert word is False
    assert word_reason != "Task completed successfully"

    unfinished, _unfinished_reason, url_ok, _url_shared = grade_arm(
        wiki,
        ARTICLE,
        "",
        completed=False,
        completion_reason="Max steps reached",
    )
    assert url_ok is True
    assert unfinished is False

    finished, _finished_reason, finished_ok, _finished_shared = grade_arm(
        wiki,
        ARTICLE,
        "",
        completed=True,
        completion_reason="Task completed successfully",
    )
    assert finished_ok is True
    assert finished is True

    absent, absent_reason, absent_ok, _absent_shared = grade_arm(
        {"id": "open", "description": "Open the page", "start_url": "https://example.test/"},
        "https://example.test/",
        "hello",
        completed=True,
        completion_reason="Task completed successfully",
    )
    assert absent_ok is None
    assert absent is False
    assert absent_reason == "no shared end-state check"


def _result(
    task_id: str,
    *,
    success: bool,
    reason: str,
    end_state: str,
    url: str,
    snapshot: str,
    answer: str = "",
    page_text: str = "",
    selector: str = "",
    key_text: str = "",
    values: tuple[str, ...] = (),
    claimed_url: str = "",
    claimed_title: str = "",
    rejected: bool = False,
) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        task_description="task",
        success=success,
        success_reason=reason,
        total_steps=1,
        total_wall_ms=1.0,
        total_model_ms=1.0,
        total_tool_ms=0.0,
        total_other_ms=0.0,
        total_input_tokens=1,
        total_output_tokens=1,
        total_snapshot_tokens=0,
        end_state=end_state,
        steps=[
            StepMetrics(
                step_number=1,
                tool_name="run_script",
                tool_args={},
                tool_result_size=1,
                snapshot_tokens=0,
                model_time_ms=1.0,
                tool_time_ms=0.0,
                input_tokens=1,
                output_tokens=1,
                snapshot_text=snapshot,
                page_url=url,
                selector_text=selector,
                claimed_answer=answer,
                page_text=page_text,
                claimed_url=claimed_url,
                claimed_title=claimed_title,
                claimed_key_text=key_text,
                claimed_values=values,
                claimed_rejected=rejected,
            )
        ],
    )


def test_probe_grade_uses_the_same_rule_for_both_arms(monkeypatch, tmp_path):
    from bench.probe import run_claude_arm

    class Peek:
        async def call_tool(self, name, arguments):
            del name, arguments
            return "short", 0.0

    async def fake_setup(self):
        self.mcp_client = Peek()

    async def fake_teardown(self):
        return None

    monkeypatch.setattr("bench.harness.BenchmarkHarness.setup", fake_setup)
    monkeypatch.setattr("bench.harness.BenchmarkHarness.teardown", fake_teardown)

    eiffel = _eiffel_task()
    hn = _hn_task()

    async def script_pass(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="the page evidence matches the markers",
            end_state="PASS",
            url=EIFFEL,
            snapshot="The Eiffel Tower is a wrought-iron lattice tower.",
            answer="Paris",
            page_text="The Eiffel Tower is in Paris.",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", script_pass)
    row = asyncio.run(
        run_claude_arm("script_first", eiffel, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert row["success"] is True
    assert "Paris" in row["success_reason"]
    assert row["substring_success"] is True
    assert row["end_state"] == "PASS"

    async def script_without_paris(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="the page evidence matches the markers",
            end_state="PASS",
            url=EIFFEL,
            snapshot="The Eiffel Tower is a wrought-iron lattice tower.",
            answer="Paris",
            page_text="The Eiffel Tower is a wrought-iron lattice tower.",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", script_without_paris)
    missing = asyncio.run(
        run_claude_arm("script_first", eiffel, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert missing["success"] is False
    assert missing["success_reason"] == "Missing text: ['Paris']"
    assert missing["substring_success"] is False
    assert missing["end_state"] == "PASS"

    async def script_hn(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="the page evidence matches the markers",
            end_state="PASS",
            url=HN,
            snapshot="",
            answer="Fixture Story",
            page_text="Fixture Story\nSecond Story",
            selector="Fixture Story",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", script_hn)
    hit = asyncio.run(
        run_claude_arm("script_first", hn, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert hit["success"] is True
    assert hit["end_state"] == "PASS"

    async def playwright_word(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="Task completed successfully",
            end_state="",
            url=HN,
            snapshot="Fixture Story",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", playwright_word)
    spoken = asyncio.run(
        run_claude_arm("playwright_mcp", hn, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert spoken["success"] is False
    assert spoken["success_reason"] != "Task completed successfully"

    async def playwright_url(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="Task completed successfully",
            end_state="",
            url=ARTICLE,
            snapshot="",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", playwright_url)
    page = asyncio.run(
        run_claude_arm(
            "stagehand",
            _wiki_task(),
            api_key="local-test-not-sent",
            headless=True,
            runs_dir=tmp_path,
        )
    )
    assert page["success"] is True


def test_a_wrong_but_consistent_answer_stops_and_fails_the_grade(tmp_path):
    """The reported RFC miss: judge FAIL, two steps, model stopped, no cache write.

    The judge already failed. The model then ended the turn. That is not a
    harness miss to turn into a pass, and the answer stays out of the repair.
    """
    from tests.test_script_first import _script_harness, _tool_reply

    class Cache:
        def __init__(self):
            self.saved = 0

        def lookup(self, description, start_url):
            del description, start_url
            return None

        def save(self, *args, **kwargs):
            del args, kwargs
            self.saved += 1

        def drop(self, *args, **kwargs):
            del args, kwargs
            return None

    async def call_tool(name, arguments, nth):
        del name, arguments
        if nth == 1:
            body = format_run_result(
                ok=True,
                url="https://www.rfc-editor.org/",
                step_count=1,
                text="RFC index",
            )
        else:
            body = format_run_result(
                ok=True,
                url="https://www.rfc-editor.org/rfc/rfc9110.html",
                step_count=2,
                text="9.3.2 POST",
                claimed={"answer": "9.3.2"},
            )
        return body, 1.0

    stopped = {
        "content": [{"type": "text", "text": "I am stopping."}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("open"), _tool_reply("repair"), stopped],
        call_tool,
        max_steps=4,
    )
    cache = Cache()
    harness.script_cache = cache
    result = asyncio.run(
        harness.run_task(
            task_id="ho_rfc9110_get_section",
            task_description="Open RFC 9110 and report the section number of the section that defines the GET method.",
            start_url="https://www.rfc-editor.org/",
        )
    )
    seen = json.dumps(model.seen)
    # The first script ended on the start page with nothing returned: one
    # legitimate repair. The second is wrong (9.3.2, not 9.3.1) but consistent
    # with its own page, so the live check, which has no answer key, stops.
    assert client.calls == 2
    assert result.total_steps == 2
    assert seen.count("END_STATE_FAILED") == 1
    assert result.end_state == "PASS"
    assert cache.saved == 1
    # The final grade has the answer key and fails it.
    from bench.probe import grade_observation
    from bench.tasks import task_by_id

    last = result.steps[-1]
    ok, reason, _shared, _why = grade_observation(
        task_by_id("ho_rfc9110_get_section"),
        last.page_url,
        "9.3.2 POST",
        answer="9.3.2",
        run_verdict=result.end_state,
    )
    assert ok is False, reason
    assert "9.3.1" not in seen
    assert "9.3.1" not in harness.system_prompt
    assert "selector_text" not in seen
    assert "rfc9110" not in harness.system_prompt


def test_spoken_claim_drops_the_completion_token():
    assert spoken_claim("TASK_COMPLETE") == ""
    assert spoken_claim("Fixture Story\nTASK_COMPLETE") == "Fixture Story"
    assert spoken_claim("The top story is Fixture Story. TASK_COMPLETE") == "The top story is Fixture Story."
    payload = json.dumps({"text": "Fixture Story\nSecond Story", "selector": "Fixture Story"}, indent=2)
    raw = f"### Result\n{payload}\n### Ran Playwright code\n```js\nawait page.evaluate()\n```\n"
    assert mcp_evaluate_value(raw)["selector"] == "Fixture Story"
    assert "Second Story" in mcp_evaluate_value(raw)["text"]


def test_playwright_and_stagehand_record_the_same_claim(monkeypatch, tmp_path):
    """TASK_COMPLETE text is the claim, and the live selector is the same check.

    A bare completion is still an empty answer. A sentence that is not the
    title fails the shared check. The selector stays out of the model transcript.
    """
    from bench.probe import run_claude_arm

    hn = _hn_task()
    marked = {"text": "Fixture Story\nSecond Story", "selector": "Fixture Story"}

    class Page:
        url = HN

        async def title(self):
            return "Hacker News"

        async def evaluate(self, source):
            if "canonical" in source:
                return {
                    "url": HN,
                    "title": "Hacker News",
                    "canonical": "",
                    "h1": "",
                    "text": marked["text"],
                    "controls": [],
                }
            if "titleline" in source:
                return marked["selector"]
            return ""

    class Model:
        def __init__(self, tool_name: str, final: str):
            self.tool_name = tool_name
            self.final = final
            self.seen = []
            self._turn = 0

        async def create_message(self, messages, tools, system=None, max_tokens=4096):
            del tools, max_tokens
            self.seen.append({"messages": messages, "system": system})
            self._turn += 1
            if self._turn == 1:
                return (
                    {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "t1",
                                "name": self.tool_name,
                                "input": {"url": HN},
                            }
                        ],
                        "stop_reason": "tool_use",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    },
                    1.0,
                )
            return (
                {
                    "content": [{"type": "text", "text": self.final}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
                1.0,
            )

    class Client:
        def __init__(self, *, page):
            self._page = page
            self.tools = [
                {"name": "browser_navigate"},
                {"name": "browser_evaluate"},
                {"name": "run"},
                {"name": "snapshot"},
            ]
            self.calls = []

        def tools_for_claude(self):
            return [
                {"name": tool["name"], "description": "tool", "input_schema": {"type": "object"}}
                for tool in self.tools
                if tool["name"] != "browser_evaluate"
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "browser_evaluate":
                payload = json.dumps(marked, indent=2)
                return f"### Result\n{payload}\n### Ran Playwright code\n```js\ncode\n```\n", 1.0
            return f"- Page URL: {HN}\nshort page\n", 1.0

    def install(model, client):
        async def fake_setup(self):
            self.mcp_client = client
            self.anthropic = model

        async def fake_teardown(self):
            return None

        monkeypatch.setattr("bench.harness.BenchmarkHarness.setup", fake_setup)
        monkeypatch.setattr("bench.harness.BenchmarkHarness.teardown", fake_teardown)

    same, _same_reason, _, _ = grade_arm(
        hn,
        HN,
        "",
        completed=True,
        selector_text="Fixture Story",
        answer="Fixture Story",
        page_text="Fixture Story\nSecond Story",
    )
    assert same is True

    rows = {}
    for arm, tool, page in (
        ("playwright_mcp", "browser_navigate", None),
        ("stagehand", "run", Page()),
    ):
        model = Model(tool, "Fixture Story\nTASK_COMPLETE")
        client = Client(page=page)
        install(model, client)
        row = asyncio.run(
            run_claude_arm(arm, hn, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
        )
        blob = json.dumps(model.seen)
        assert ".titleline" not in blob
        assert "selector_text" not in blob
        assert row["success"] is True
        assert row["success_reason"] == "the page evidence matches the markers"
        rows[arm] = row["success_reason"]
        if arm == "playwright_mcp":
            assert any(name == "browser_evaluate" for name, _args in client.calls)
            assert ".titleline" in client.calls[-1][1]["function"]

    assert rows["playwright_mcp"] == rows["stagehand"]

    model = Model("browser_navigate", "The top story is Fixture Story.\nTASK_COMPLETE")
    install(model, Client(page=None))
    sentence = asyncio.run(
        run_claude_arm("playwright_mcp", hn, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert sentence["success"] is False
    assert sentence["success_reason"] == "answer is not the marked value"
    assert sentence["claimed_answer"] == "The top story is Fixture Story."
    assert sentence["expected_value"] == "Fixture Story"
    assert ".titleline" not in json.dumps(model.seen)

    model = Model("browser_navigate", "Other Story\nTASK_COMPLETE")
    install(model, Client(page=None))
    missed = asyncio.run(
        run_claude_arm("playwright_mcp", hn, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert missed["success"] is False
    assert missed["success_reason"] == "answer is not the marked value"
    assert "empty answer" not in missed["success_reason"]

    model = Model("browser_navigate", "TASK_COMPLETE")
    install(model, Client(page=None))
    bare = asyncio.run(
        run_claude_arm("playwright_mcp", hn, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert bare["success"] is False
    assert bare["success_reason"] == "empty answer"


def test_rfc_heading_stays_in_the_page_text_and_the_judge_does_not_soften():
    """The RFC body prefix has no section number. The heading on that page does.

    A wrong section still fails with the same reason. The answer is not a prompt.
    """
    from bench.script_first import (
        FAIL,
        PASS,
        ClaimedEvidence,
        PageEvidence,
        _PAGE_EVIDENCE_JS,
        evidence_verdict,
        page_text_from_evidence,
    )
    from bench.tasks import markers_for_task

    assert "h1, h2, h3, h4, h5, h6" in _PAGE_EVIDENCE_JS
    body = "Abstract " * 900
    assert "9.3.1" not in body[:4000]
    text = page_text_from_evidence(
        {
            "headings": [
                "9.2.3. Methods and Caching",
                "9.3. Method Definitions",
                "9.3.1. GET",
                "9.3.2. HEAD",
            ],
            "text": body,
        }
    )
    assert text.index("9.3.1") < 4000
    assert "9.3.1" in text
    markers = markers_for_task("ho_rfc9110_get_section")
    url = "https://www.rfc-editor.org/rfc/rfc9110.html"
    passed = evidence_verdict(markers, PageEvidence(url=url, text=text), ClaimedEvidence(answer="9.3.1"))
    assert passed.verdict == PASS
    wrong = evidence_verdict(markers, PageEvidence(url=url, text=text), ClaimedEvidence(answer="9.3.2"))
    assert wrong.verdict == FAIL
    assert wrong.reason == "answer does not satisfy the marker"
    prefix = evidence_verdict(
        markers,
        PageEvidence(url=url, text=body[:4000]),
        ClaimedEvidence(answer="9.3.1"),
    )
    assert prefix.verdict == FAIL
    assert prefix.reason == "answer is not in the page text"


def test_padded_hacker_news_sentence_fails():
    """The claim is the live title. Case and spacing may differ. A sentence does not."""
    task = _hn_task()
    title = "Fixture Story"
    page = f"{title}\nSecond Story"
    padded = f'The top story on Hacker News is "{title}".'
    ok, why = shared_end_state(
        task,
        HN,
        page,
        selector_text=title,
        answer=padded,
        page_text=page,
    )
    assert ok is False
    assert why == "answer is not the marked value"

    spaced, spaced_why = shared_end_state(
        task,
        HN,
        page,
        selector_text=title,
        answer="  fixture   story  ",
        page_text=page,
    )
    assert spaced is True
    assert spaced_why == "the page evidence matches the markers"

    quoted, quoted_why = shared_end_state(
        task,
        HN,
        page,
        selector_text=title,
        answer=f'"{title}"',
        page_text=page,
    )
    assert quoted is False
    assert quoted_why == "answer is not the marked value"

    wrong, wrong_why = shared_end_state(
        task,
        HN,
        page,
        selector_text="Fixture Story",
        answer="The top story is Second Story.",
        page_text=page,
    )
    assert wrong is False
    assert wrong_why == "answer is not the marked value"

    negated, negated_why = shared_end_state(
        task,
        HN,
        page,
        selector_text="Fixture Story",
        answer="The top story is not Fixture Story.",
        page_text=page,
    )
    assert negated is False
    assert negated_why == "answer is not the marked value"

    partial, partial_why = shared_end_state(
        task,
        HN,
        page,
        selector_text="Fixture Story",
        answer="Fixture",
        page_text=page,
    )
    assert partial is False
    assert partial_why == "answer is not the marked value"

    extra, extra_why = shared_end_state(
        task,
        HN,
        page,
        selector_text="Fixture Story",
        answer="Fixture Story and Second Story",
        page_text=page,
    )
    assert extra is False
    assert extra_why == "answer is not the marked value"


def test_every_arm_grades_the_same_page_text_and_logs_the_live_value(monkeypatch, tmp_path):
    """The snapshot is not the shared check. Both arms log the claim and the live title."""
    from bench.probe import run_claude_arm

    class Peek:
        async def call_tool(self, name, arguments):
            del name, arguments
            return "short", 0.0

    async def fake_setup(self):
        self.mcp_client = Peek()

    async def fake_teardown(self):
        return None

    monkeypatch.setattr("bench.harness.BenchmarkHarness.setup", fake_setup)
    monkeypatch.setattr("bench.harness.BenchmarkHarness.teardown", fake_teardown)

    eiffel = _eiffel_task()
    hn = _hn_task()

    async def body_has_paris(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="Task completed successfully",
            end_state="PASS",
            url=EIFFEL,
            snapshot="The Eiffel Tower is a wrought-iron lattice tower.",
            answer="Paris",
            page_text="The Eiffel Tower is in Paris.",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", body_has_paris)
    rows = {}
    for arm in ("script_first", "playwright_mcp", "stagehand"):
        row = asyncio.run(
            run_claude_arm(arm, eiffel, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
        )
        assert row["success"] is True, arm
        assert "Paris" in row["success_reason"]
        assert row["claimed_answer"] == "Paris"
        rows[arm] = row["success"]
    assert rows["script_first"] is rows["playwright_mcp"] is rows["stagehand"] is True

    async def snapshot_only(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="Task completed successfully",
            end_state="",
            url=EIFFEL,
            snapshot="The tower stands in Paris.",
            answer="Paris",
            page_text="",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", snapshot_only)
    for arm in ("script_first", "playwright_mcp"):
        missed = asyncio.run(
            run_claude_arm(arm, eiffel, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
        )
        assert missed["success"] is False, arm
        assert missed["success_reason"] == "Missing text: ['Paris']"

    async def spoken_title(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="Task completed successfully",
            end_state="PASS",
            url=HN,
            snapshot="not the page",
            answer="Fixture Story",
            page_text="Fixture Story\nSecond Story",
            selector="Fixture Story",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", spoken_title)
    for arm in ("playwright_mcp", "script_first"):
        hit = asyncio.run(
            run_claude_arm(arm, hn, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
        )
        assert hit["success"] is True, arm
        assert hit["claimed_answer"] == "Fixture Story"
        assert hit["expected_value"] == "Fixture Story"

    async def empty_claim(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="Task completed successfully",
            end_state="PASS",
            url=EIFFEL,
            snapshot="The tower stands in Paris.",
            answer="",
            page_text="The tower stands in Paris.",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", empty_claim)
    for arm in ("script_first", "stagehand"):
        bare = asyncio.run(
            run_claude_arm(arm, eiffel, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
        )
        assert bare["success"] is False, arm
        assert bare["success_reason"] == "empty answer"
        assert bare["claimed_answer"] == ""


def _packing_tasks() -> list[dict]:
    from bench.tasks import FIXTURE_TASKS

    return [dict(task) for task in FIXTURE_TASKS]


def test_script_first_fail_or_unknown_fails_a_page_that_would_pass(monkeypatch, tmp_path):
    """script_first's own FAIL or UNKNOWN is a fail, even when the page check would pass.

    The two packing tasks are decided by the text on the page. That text is
    present here. The run verdict still has to be PASS. Other arms still use
    their completion bit.
    """
    from bench.probe import run_claude_arm

    class Peek:
        async def call_tool(self, name, arguments):
            del name, arguments
            return "short", 0.0

    async def fake_setup(self):
        self.mcp_client = Peek()

    async def fake_teardown(self):
        return None

    monkeypatch.setattr("bench.harness.BenchmarkHarness.setup", fake_setup)
    monkeypatch.setattr("bench.harness.BenchmarkHarness.teardown", fake_teardown)

    pages = {
        "fixture_packing_add": "milk",
        "fixture_packing_multi": "socks and a toothbrush",
    }
    for task in _packing_tasks():
        async def own_fail(
            self,
            task_id,
            task_description,
            start_url,
            expected_answer=None,
            judge_prompt=None,
            check_url_contains=None,
            page=pages[task["id"]],
            landed=task["start_url"],
        ):
            del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
            return _result(
                task_id,
                success=True,
                reason="claimed URL does not match the live page",
                end_state="FAIL",
                url=landed,
                snapshot=page,
                answer="milk",
                page_text=page,
            )

        async def own_unknown(
            self,
            task_id,
            task_description,
            start_url,
            expected_answer=None,
            judge_prompt=None,
            check_url_contains=None,
            page=pages[task["id"]],
            landed=task["start_url"],
        ):
            del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
            return _result(
                task_id,
                success=True,
                reason="Max steps reached",
                end_state="UNKNOWN",
                url=landed,
                snapshot=page,
                answer="milk",
                page_text=page,
            )

        monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", own_fail)
        failed = asyncio.run(
            run_claude_arm("script_first", task, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
        )
        assert failed["success"] is False, task["id"]
        assert failed["success_reason"] == "claimed URL does not match the live page"
        assert failed["end_state"] == "FAIL"

        monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", own_unknown)
        unknown = asyncio.run(
            run_claude_arm("script_first", task, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
        )
        assert unknown["success"] is False, task["id"]
        assert unknown["success_reason"] == "UNKNOWN: Max steps reached"
        assert unknown["end_state"] == "UNKNOWN"

    passed_page = pages["fixture_packing_add"]
    packing = _packing_tasks()[0]

    async def other_done(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="Task completed successfully",
            end_state="",
            url=packing["start_url"],
            snapshot=passed_page,
            answer="milk",
            page_text=passed_page,
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", other_done)
    other = asyncio.run(
        run_claude_arm("playwright_mcp", packing, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert other["success"] is True

    async def other_stopped(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=False,
            reason="Max steps reached",
            end_state="",
            url=packing["start_url"],
            snapshot=passed_page,
            answer="milk",
            page_text=passed_page,
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", other_stopped)
    stopped = asyncio.run(
        run_claude_arm("stagehand", packing, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert stopped["success"] is False
    assert stopped["success_reason"] == "Max steps reached"


def test_script_evidence_missing_from_the_page_fails(monkeypatch, tmp_path):
    """URL, key text, and values have to be on the live page. A PASS verdict does not skip that."""
    from bench.probe import run_claude_arm

    class Peek:
        async def call_tool(self, name, arguments):
            del name, arguments
            return "short", 0.0

    async def fake_setup(self):
        self.mcp_client = Peek()

    async def fake_teardown(self):
        return None

    monkeypatch.setattr("bench.harness.BenchmarkHarness.setup", fake_setup)
    monkeypatch.setattr("bench.harness.BenchmarkHarness.teardown", fake_teardown)

    task = _packing_tasks()[0]
    page = "milk is on the packing list"
    live = "https://example.test/packing"

    async def missing(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="the page evidence matches the markers",
            end_state="PASS",
            url=live,
            snapshot=page,
            answer="milk",
            page_text=page,
            key_text="wool socks",
            values=("toothbrush",),
            claimed_title="Packing list",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", missing)
    row = asyncio.run(
        run_claude_arm("script_first", task, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert row["success"] is False
    assert row["success_reason"] == "returned evidence is not on the page"
    assert row["end_state"] == "PASS"

    async def wrong_url(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="the page evidence matches the markers",
            end_state="PASS",
            url=live,
            snapshot=page,
            answer="milk",
            page_text=page,
            claimed_url="https://example.test/elsewhere",
            claimed_title="Packing list",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", wrong_url)
    mismatched = asyncio.run(
        run_claude_arm("script_first", task, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert mismatched["success"] is False
    assert mismatched["success_reason"] == "claimed URL does not match the live page"

    async def present(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None, check_url_contains=None):
        del self, task_description, start_url, expected_answer, judge_prompt, check_url_contains
        return _result(
            task_id,
            success=True,
            reason="the page evidence matches the markers",
            end_state="PASS",
            url=live,
            snapshot=page,
            answer="milk",
            page_text=page,
            key_text="milk",
            values=("packing list",),
            claimed_url=live,
            claimed_title="Packing list",
        )

    monkeypatch.setattr("bench.harness.BenchmarkHarness.run_task", present)
    kept = asyncio.run(
        run_claude_arm("script_first", task, api_key="local-test-not-sent", headless=True, runs_dir=tmp_path)
    )
    assert kept["success"] is True


def test_eiffel_script_is_cached_only_when_the_page_contains_paris(tmp_path, monkeypatch):
    from bench.script_cache import ScriptCache
    from bench.script_first import PASS, format_run_result
    from tests.test_script_first import _script_harness, _tool_reply

    url = "https://en.wikipedia.org/wiki/Eiffel_Tower"
    description = "Open the Wikipedia article for the Eiffel Tower and report the city it stands in"
    start = "https://en.wikipedia.org/wiki/Main_Page"

    def _run(directory, text: str, replies: list):
        async def call_tool(name, arguments, nth):
            del name, arguments, nth
            return (
                format_run_result(
                    ok=True,
                    url=url,
                    step_count=1,
                    title="Eiffel Tower",
                    text=text,
                    claimed={"answer": "Paris"},
                ),
                1.0,
            )

        harness, _model, _client = _script_harness(directory, replies, call_tool, max_steps=4)
        harness.script_cache = ScriptCache(directory / "scripts.json")
        result = asyncio.run(
            harness.run_task(
                task_id="ho_wiki_eiffel_city",
                task_description=description,
                start_url=start,
            )
        )
        return harness, result

    kept_code = "await page.evaluate(() => document.title);"
    kept, result = _run(
        tmp_path / "keep",
        "The Eiffel Tower stands in Paris, France.",
        [_tool_reply(kept_code)],
    )
    assert result.end_state == PASS
    assert result.success is True
    assert len(kept.script_cache) == 1
    stored = kept.script_cache.lookup(description, start)
    assert stored is not None
    assert stored.script == "page.evaluate(() => document.title)"
    assert "Paris" not in stored.script
    assert "Eiffel_Tower" not in stored.script

    import bench.probe as probe

    real_check = probe.shared_check_passes
    monkeypatch.setattr(probe, "shared_check_passes", lambda *args, **kwargs: False)
    denied, denied_result = _run(
        tmp_path / "deny",
        "The Eiffel Tower stands in Paris, France.",
        [_tool_reply("open")],
    )
    assert denied_result.end_state == PASS
    assert len(denied.script_cache) == 0

    monkeypatch.setattr(probe, "shared_check_passes", real_check)
    missed, missed_result = _run(
        tmp_path / "miss",
        "The Eiffel Tower is a wrought-iron lattice tower.",
        [_tool_reply("open"), _tool_reply("repair")],
    )
    assert missed_result.end_state == "FAIL"
    assert missed_result.success is False
    assert len(missed.script_cache) == 0
