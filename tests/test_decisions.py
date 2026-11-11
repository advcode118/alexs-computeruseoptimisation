"""Decisions second opinion for script_first. Offline: fake clients and transports only."""

from __future__ import annotations

import asyncio
import inspect
import json
import time

import pytest

from bench.decisions import (
    MODE_OFF,
    MODE_ON,
    MODE_SHADOW,
    PAGE_TEXT_CAP,
    DecisionsClient,
    DecisionsOpinion,
    decisions_payload,
    payload_from_run,
    parse_mode,
)
from bench.harness import BenchmarkHarness
from bench.openai_spend import OpenAISpendLedger, PriceUnknown, price_decisions_usd
from bench.script_first import (
    FAIL,
    FAIL_ANSWER_NOT_IN_TEXT,
    FAIL_START_PAGE_NO_RETURN,
    PASS,
    format_run_result,
    is_soft_fail,
    script_runtime_verdict,
)

START = "https://en.wikipedia.org/wiki/Main_Page"
ARTICLE = "https://en.wikipedia.org/wiki/Ada_Lovelace"
TASK = "Open the Wikipedia article about Ada Lovelace and report its URL"
SECRET_ANSWER = "SECRET-EXPECTED-ANSWER"
SECRET_URL = "SECRET-URL-TOKEN"
SECRET_SELECTOR = "SECRET-SELECTOR-TEXT"


class FakeDecisions:
    def __init__(
        self,
        p_done: float | None = 0.95,
        p_answer: float = 0.9,
        ok: bool = True,
        delay: float = 0.0,
        p_needed: float | None = None,
    ):
        self.p_done = p_done
        self.p_answer = p_answer
        # None models a refusal: the answer_needed question comes back unanswered.
        self.p_needed = p_needed
        self.ok = ok
        self.delay = delay
        self.bodies: list[dict] = []

    async def ask(self, payload: dict) -> DecisionsOpinion:
        self.bodies.append(payload)
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.ok:
            return DecisionsOpinion(ok=False, elapsed_ms=1.0, error="timeout")
        probabilities = {"answer_ok": self.p_answer}
        if self.p_needed is not None:
            probabilities["answer_needed"] = self.p_needed
        if self.p_done is not None:
            probabilities["task_done"] = self.p_done
        usage = {
            "input_tokens": 1000,
            "output_tokens": 0,
            "cached_tokens": 0,
            "cache_write_30m_tokens": 0,
            "cache_write_12h_tokens": 0,
        }
        return DecisionsOpinion(
            ok=True, elapsed_ms=2.0, probabilities=probabilities, choice="done", usage=usage, usd=0.0001
        )


def _wrong_answer(url: str = ARTICLE, nth: int = 1) -> str:
    """A soft FAIL: a web page with text, but the returned answer is not on it."""
    return format_run_result(
        ok=True,
        url=url,
        step_count=nth,
        title="Ada Lovelace - Wikipedia",
        h1="Ada Lovelace",
        text="Ada Lovelace was an English mathematician.",
        selector_text=SECRET_SELECTOR,
        claimed={"answer": "Charles Babbage"},
    )


def _good(nth: int = 2) -> str:
    return format_run_result(
        ok=True,
        url=ARTICLE,
        step_count=nth,
        title="Ada Lovelace - Wikipedia",
        text="Ada Lovelace was an English mathematician.",
        claimed={"key_text": "Ada Lovelace"},
    )


def _no_answer(nth: int = 1) -> str:
    """A soft FAIL with nothing returned: on the right page, but the script gave back no answer."""
    return format_run_result(
        ok=True,
        url=ARTICLE,
        step_count=nth,
        title="Ada Lovelace - Wikipedia",
        h1="Ada Lovelace",
        text="Ada Lovelace was an English mathematician.",
    )


def _start_page_nothing(nth: int = 1) -> str:
    return format_run_result(ok=True, url=START, step_count=nth, title="Wikipedia", text="Welcome to Wikipedia")


def _tool_reply(code: str) -> dict:
    return {
        "content": [{"type": "tool_use", "id": "t", "name": "run_script", "input": {"code": code}}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _done_reply() -> dict:
    return {
        "content": [{"type": "text", "text": "TASK_COMPLETE"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _run(tmp_path, results, *, mode=None, client=None, replies=None):
    replies = replies or [_tool_reply("go"), _tool_reply("fix"), _done_reply()]

    class FakeModel:
        def __init__(self):
            self._replies = list(replies)
            self.seen: list = []

        async def create_message(self, messages, tools, system=None, max_tokens=4096):
            self.seen.append(json.loads(json.dumps(messages)))
            return self._replies.pop(0), 1.0

    class FakeMCP:
        def __init__(self):
            self.calls = 0

        def tools_for_claude(self):
            return [{"name": "run_script", "description": "run", "input_schema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            self.calls += 1
            return results[min(self.calls, len(results)) - 1], 1.0

    kwargs = {}
    if mode is not None:
        kwargs["decisions_check"] = mode
    if client is not None:
        kwargs["decisions_client"] = client
    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path, arm="script_first", max_steps=4, **kwargs)
    model = FakeModel()
    harness.anthropic = model
    harness.mcp_client = FakeMCP()
    result = asyncio.run(
        harness.run_task(
            task_id="t1",
            task_description=TASK,
            start_url=START,
            expected_answer=SECRET_ANSWER,
            check_url_contains=SECRET_URL,
        )
    )
    return result, model


def _repairs(model) -> int:
    return json.dumps(model.seen).count("END_STATE_FAILED")


def test_an_answer_not_on_the_page_is_a_soft_fail_and_the_start_page_is_hard():
    url_answer = format_run_result(
        ok=True, url=ARTICLE, step_count=1, title="Ada Lovelace - Wikipedia", text="Ada.", claimed={"answer": ARTICLE}
    )
    assert script_runtime_verdict(url_answer, ARTICLE, START)[0].verdict == PASS
    verdict, payload = script_runtime_verdict(_wrong_answer(), ARTICLE, START)
    assert verdict.verdict == FAIL and verdict.code == FAIL_ANSWER_NOT_IN_TEXT
    assert is_soft_fail(verdict, payload, ARTICLE)
    hard, hard_payload = script_runtime_verdict(_start_page_nothing(), START, START)
    assert hard.code == FAIL_START_PAGE_NO_RETURN
    assert not is_soft_fail(hard, hard_payload, START)
    empty, empty_payload = script_runtime_verdict("", "", START)
    assert empty.verdict == FAIL and not is_soft_fail(empty, empty_payload, "")


def test_high_probability_overturns_and_sends_no_repair(tmp_path):
    client = FakeDecisions(p_done=0.95)
    result, model = _run(tmp_path, [_wrong_answer()], mode=MODE_ON, client=client)
    assert result.success is True and result.end_state == PASS
    assert _repairs(model) == 0
    assert len(model.seen) == 1
    assert len(client.bodies) == 1
    assert result.decisions["decisions_overturned"] is True
    assert result.decisions["decisions_p_task_done"] == 0.95
    assert result.decisions["decisions_fail_code"] == FAIL_ANSWER_NOT_IN_TEXT
    assert result.first_runtime_code == FAIL_ANSWER_NOT_IN_TEXT
    assert result.first_runtime_reason == "answer is not in the page text"


def test_low_probability_repairs_as_today(tmp_path):
    client = FakeDecisions(p_done=0.4)
    result, model = _run(tmp_path, [_wrong_answer(), _good()], mode=MODE_ON, client=client)
    assert _repairs(model) == 1
    assert result.decisions["decisions_overturned"] is False
    assert result.decisions["decisions_p_task_done"] == 0.4
    off, off_model = _run(tmp_path, [_wrong_answer(), _good()])
    assert model.seen == off_model.seen
    assert result.success == off.success


@pytest.mark.parametrize("p_done", [0.89, None])
def test_below_threshold_or_missing_answer_does_not_overturn(tmp_path, p_done):
    result, model = _run(tmp_path, [_wrong_answer(), _good()], mode=MODE_ON, client=FakeDecisions(p_done=p_done))
    assert _repairs(model) == 1
    assert result.decisions["decisions_overturned"] is False


def test_timeout_and_error_fall_back_to_the_repair(tmp_path):
    def slow(url, headers, payload, timeout_s):
        time.sleep(0.5)
        return "{}"

    def broken(url, headers, payload, timeout_s):
        raise OSError("connection refused")

    off, off_model = _run(tmp_path, [_wrong_answer(), _good()])
    for transport in (slow, broken):
        client = DecisionsClient("k", timeout_s=0.05, transport=transport)
        result, model = _run(tmp_path, [_wrong_answer(), _good()], mode=MODE_ON, client=client)
        assert model.seen == off_model.seen
        assert result.success == off.success
        assert result.decisions["decisions_errors"] == 1
        assert result.decisions["decisions_overturned"] is False
    assert result.decisions["decisions_error"].startswith("OSError")


def test_no_answer_is_a_soft_fail():
    verdict, payload = script_runtime_verdict(_no_answer(), ARTICLE, START)
    assert verdict.verdict == FAIL and is_soft_fail(verdict, payload, ARTICLE)


def test_no_answer_when_one_is_needed_is_not_overturned_and_gets_the_targeted_repair(tmp_path):
    client = FakeDecisions(p_done=0.95, p_needed=0.9)
    result, model = _run(tmp_path, [_no_answer(), _good()], mode=MODE_ON, client=client)
    assert result.decisions["decisions_overturned"] is False
    assert result.decisions["decisions_p_answer_needed"] == 0.9
    assert result.decisions["decisions_blocked"] == "answer_needed"
    assert _repairs(model) == 1
    sent = json.dumps(model.seen)
    assert "the page looks right but the script returned no answer" in sent
    assert "without navigating away" in sent
    for secret in (SECRET_ANSWER, SECRET_URL, SECRET_SELECTOR):
        assert secret not in sent
    assert "answer_needed" in [q["name"] for q in client.bodies[0]["questions"]]


def test_no_answer_when_none_is_needed_is_overturned(tmp_path):
    client = FakeDecisions(p_done=0.95, p_needed=0.2)
    result, model = _run(tmp_path, [_no_answer()], mode=MODE_ON, client=client)
    assert result.success is True and result.end_state == PASS
    assert _repairs(model) == 0
    assert result.decisions["decisions_overturned"] is True
    assert result.decisions["decisions_blocked"] == ""


def test_no_answer_and_answer_needed_refused_is_not_overturned(tmp_path):
    client = FakeDecisions(p_done=0.95, p_needed=None)
    result, model = _run(tmp_path, [_no_answer(), _good()], mode=MODE_ON, client=client)
    assert result.decisions["decisions_overturned"] is False
    assert result.decisions["decisions_p_answer_needed"] is None
    assert result.decisions["decisions_blocked"] == "answer_needed_unknown"
    assert "the page looks right but the script returned no answer" in json.dumps(model.seen)


def test_returned_answer_with_low_answer_ok_is_not_overturned(tmp_path):
    client = FakeDecisions(p_done=0.95, p_answer=0.4)
    result, model = _run(tmp_path, [_wrong_answer(), _good()], mode=MODE_ON, client=client)
    assert result.decisions["decisions_overturned"] is False
    assert result.decisions["decisions_blocked"] == "answer_not_ok"
    assert _repairs(model) == 1
    assert "the returned answer does not answer the task" in json.dumps(model.seen)


def test_below_threshold_keeps_the_stock_repair_wording(tmp_path):
    result, model = _run(tmp_path, [_no_answer(), _good()], mode=MODE_ON, client=FakeDecisions(p_done=0.4, p_needed=0.9))
    assert result.decisions["decisions_blocked"] == "below_threshold"
    off, off_model = _run(tmp_path, [_no_answer(), _good()])
    assert model.seen == off_model.seen


def test_shadow_estimate_uses_the_same_rule(tmp_path):
    needed = FakeDecisions(p_done=0.95, p_needed=0.9)
    shadow, _ = _run(tmp_path, [_no_answer(), _good()], mode=MODE_SHADOW, client=needed)
    assert shadow.decisions["decisions_would_overturn"] is False
    assert shadow.decisions["decisions_blocked"] == "answer_needed"
    not_needed = FakeDecisions(p_done=0.95, p_needed=0.1)
    shadow, _ = _run(tmp_path, [_no_answer(), _good()], mode=MODE_SHADOW, client=not_needed)
    assert shadow.decisions["decisions_would_overturn"] is True


def test_off_makes_no_call_and_the_requests_are_unchanged(tmp_path):
    client = FakeDecisions()
    plain, plain_model = _run(tmp_path, [_wrong_answer(), _good()])
    off, off_model = _run(tmp_path, [_wrong_answer(), _good()], mode=MODE_OFF, client=client)
    assert client.bodies == []
    assert off_model.seen == plain_model.seen
    assert off.decisions == {"decisions_check": "off"}
    assert off.success == plain.success and off.end_state == plain.end_state


def test_hard_fails_are_never_sent(tmp_path):
    client = FakeDecisions(p_done=1.0)
    result, model = _run(tmp_path, [_start_page_nothing(), _good()], mode=MODE_ON, client=client)
    assert client.bodies == []
    assert _repairs(model) == 1
    assert result.decisions["decisions_overturned"] is False


def test_shadow_changes_nothing_and_asks_after_the_clock(tmp_path):
    client = FakeDecisions(p_done=0.95, delay=0.3)
    off, off_model = _run(tmp_path, [_wrong_answer(), _good()])
    shadow, shadow_model = _run(tmp_path, [_wrong_answer(), _good()], mode=MODE_SHADOW, client=client)
    assert shadow_model.seen == off_model.seen
    assert shadow.success == off.success and shadow.end_state == off.end_state
    # One ask at the soft FAIL the run saw, one at the end state.
    assert len(client.bodies) == 2
    assert shadow.decisions["decisions_would_overturn"] is True
    assert shadow.decisions["decisions_overturned"] is False
    assert shadow.decisions["decisions_post_clock"] is True
    assert shadow.total_wall_ms < 300


def test_on_asks_answer_ok_after_the_clock_on_a_plain_pass(tmp_path):
    passing = format_run_result(
        ok=True,
        url=ARTICLE,
        step_count=1,
        title="Ada Lovelace - Wikipedia",
        text="Ada Lovelace was an English mathematician.",
        claimed={"answer": "Ada Lovelace"},
    )
    client = FakeDecisions(p_answer=0.7)
    result, model = _run(tmp_path, [passing], mode=MODE_ON, client=client)
    assert result.success is True and len(model.seen) == 1
    assert len(client.bodies) == 1
    assert [q["name"] for q in client.bodies[0]["questions"]] == ["answer_ok"]
    assert result.decisions["decisions_end_p_answer_ok"] == 0.7


def test_payload_cannot_take_and_does_not_carry_the_answer_key(tmp_path):
    for function in (decisions_payload, payload_from_run):
        names = set(inspect.signature(function).parameters)
        assert not any(
            word in name for name in names for word in ("marker", "expected", "check_url", "selector", "judge")
        ), names
    client = FakeDecisions(p_done=0.95)
    _run(tmp_path, [_wrong_answer(), _good()], mode=MODE_SHADOW, client=client)
    _run(tmp_path, [_wrong_answer()], mode=MODE_ON, client=client)
    sent = json.dumps(client.bodies)
    for secret in (SECRET_ANSWER, SECRET_URL, SECRET_SELECTOR, "end_markers", "selector_text"):
        assert secret not in sent
    evidence = client.bodies[-1]["input"][0]["content"][1]["data"]
    assert set(evidence) == {
        "task",
        "start_url",
        "live_url",
        "page_title",
        "page_h1",
        "script_answer",
        "script_key_text",
        "runtime_check",
        "page_text_start",
    }


def test_payload_shape_and_page_text_cap():
    body = decisions_payload(
        task_description="t",
        start_url=START,
        live_url=ARTICLE,
        title="x",
        h1="x",
        answer="",
        key_text="",
        runtime_reason="r",
        page_text="a" * 50_000,
    )
    assert body["model"] == "gpt-6-luna"
    assert [q["type"] for q in body["questions"]] == ["predicate", "choice"]
    assert len(body["input"][0]["content"][1]["data"]["page_text_start"]) == PAGE_TEXT_CAP


def test_client_parses_answers_and_prices_usage():
    reply = {
        "answers": [
            {"type": "predicate", "name": "task_done", "probability": 0.93},
            {"type": "refusal", "name": "answer_ok"},
            {
                "type": "choice",
                "name": "failure_class",
                "choice": "done",
                "confidence": 0.8,
                "probabilities": [{"value": "done", "probability": 0.8}],
            },
        ],
        "model": "gpt-6-luna",
        "usage": {
            "input_tokens": 2000,
            "input_tokens_details": {"cached_tokens": 1000, "cache_write_tokens": 0},
            "output_tokens": 3,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 2003,
        },
    }
    client = DecisionsClient("k", transport=lambda *args: json.dumps(reply))
    opinion = asyncio.run(client.ask({"model": "gpt-6-luna", "input": "x", "questions": []}))
    assert opinion.ok and opinion.p("task_done") == 0.93 and opinion.p("answer_ok") is None
    assert opinion.choice == "done"
    # 1,000 uncached at $0.10/M plus 1,000 cached at $0.01/M; output is free.
    assert opinion.usd == pytest.approx(0.00011)
    reply["usage"]["surprise"] = 1
    unpriced = asyncio.run(client.ask({"model": "gpt-6-luna", "input": "x", "questions": []}))
    assert not unpriced.ok and unpriced.unpriced
    other = asyncio.run(client.ask({"model": "gpt-6.1-sol", "input": "x", "questions": []}))
    assert not other.ok


def test_ledger_prices_decisions_and_reads_back(tmp_path):
    assert price_decisions_usd(100_000) == pytest.approx(0.01)
    assert price_decisions_usd(100_000, cached_tokens=100_000) == pytest.approx(0.001)
    assert price_decisions_usd(100_000, cache_write_30m_tokens=100_000) == pytest.approx(0.0125)
    # Above 272k input tokens the long-context rate doubles input.
    assert price_decisions_usd(1_000_000) == pytest.approx(0.2)
    assert price_decisions_usd(1000, output_tokens=10_000) == pytest.approx(0.0001)
    with pytest.raises(PriceUnknown):
        price_decisions_usd(10, cached_tokens=20)
    ledger = OpenAISpendLedger(path=tmp_path / "openai.json")
    usd = ledger.record_decisions(run_id="r", task_id="script_first:t:decisions", input_tokens=2000, calls=2)
    ledger.save()
    again = OpenAISpendLedger.read(tmp_path / "openai.json")
    assert again.running_total_usd == pytest.approx(usd) == pytest.approx(0.0002)
    assert again.tasks[0]["kind"] == "decisions"


def test_probe_record_adds_decisions_and_keeps_an_unpriced_call(tmp_path):
    from bench.openai_run import _record

    ledger = OpenAISpendLedger(path=tmp_path / "openai.json")
    row = {
        "task_id": "t1",
        "input_tokens": 1000,
        "output_tokens": 10,
        "decisions_calls": 1,
        "decisions_input_tokens": 2000,
    }
    _record(row, ledger, arm="script_first", model="gpt-6-luna", effort="medium")
    assert [task.get("kind") for task in ledger.tasks] == [None, "decisions"]
    assert row["decisions_usd"] == pytest.approx(0.0002)
    assert row["usd"] == pytest.approx(ledger.running_total_usd)
    bad = dict(row, decisions_unpriced="Usage has unrecognized fields")
    with pytest.raises(PriceUnknown):
        _record(bad, ledger, arm="script_first", model="gpt-6-luna", effort="medium")


def test_mode_flag_and_provider_guard(monkeypatch):
    assert parse_mode("ON") == MODE_ON
    with pytest.raises(ValueError):
        parse_mode("maybe")
    monkeypatch.delenv("CU_DECISIONS_CHECK", raising=False)
    with pytest.raises(ValueError):
        BenchmarkHarness(api_key="local-test", arm="script_first", decisions_check="on")
    other = BenchmarkHarness(api_key="local-test", arm="playwright_mcp", decisions_check="on")
    assert other.decisions_check == MODE_OFF


def test_live_smoke_refuses_without_live_flag_or_key(monkeypatch):
    from bench import decisions_smoke

    def no_network(*args, **kwargs):
        raise AssertionError("the smoke must not send anything")

    monkeypatch.setattr(decisions_smoke, "_run", no_network)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert decisions_smoke.main([]) == 2
    monkeypatch.delenv("OPENAI_API_KEY")
    assert decisions_smoke.main(["--live"]) == 2


def test_report_marks_runs_with_the_check_on():
    from bench.report import render

    base = {"arm": "script_first", "task_id": "a", "usd": 0.001, "provider": "openai", "model": "gpt-6-luna"}
    on = render([dict(base, decisions_check="on", decisions_calls=1, decisions_overturned=True)])
    off = render([dict(base, decisions_check="off")])
    assert "decisions=on overturned" in on and "decisions check on: calls=1" in on
    assert "decisions" not in off
