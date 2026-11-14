"""CU_SF_STRATEGY=nav,form,spa together: switches, routing precedence, and off == tip3. Offline only."""
import asyncio
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from bench import strategy_form, strategy_nav, strategy_spa
from bench.harness import BenchmarkHarness
from bench.script_first import ScriptFirstClient
from tests.test_script_cache import CLICK_SCRIPT, DESCRIPTION, LINK, START, TASK_ID, _Model, _script_reply, _WikiPage

GOLDEN = Path(__file__).parent / "fixtures" / "strategy_off_tip3.json"
STAY = "\n".join([
    f"await page.goto({json.dumps(START)});",
    'await page.evaluate(() => ({url: location.href, title: document.title, '
    'h1: document.querySelector("h1")?.innerText, answer: ""}));',
])
SHELL = strategy_spa.HtmlSignals(status=200, html_chars=900, text_chars=12, scripts=4, app_root=True)
SERVER_PAGE = strategy_spa.HtmlSignals(status=200, html_chars=40000, text_chars=9000, scripts=4)


class Model(_Model):
    async def create_message(self, messages, tools, system=None, max_tokens=4096, **kwargs):
        self.calls.append({"messages": messages, "tools": tools, "system": system, "kwargs": kwargs})
        if not self.replies:
            raise AssertionError("unexpected model call")
        return self.replies.pop(0), 1.0


def _run(replies):
    with tempfile.TemporaryDirectory() as tmp:
        harness = BenchmarkHarness(api_key="offline", runs_dir=Path(tmp), arm="script_first")
        model = Model(replies)
        harness.anthropic = model
        harness.mcp_client = ScriptFirstClient(page=_WikiPage({LINK: "article"}))
        return asyncio.run(harness.run_task(TASK_ID, DESCRIPTION, START)), model


def _fingerprint(result, model) -> dict:
    """Everything but timings: verdicts, steps, tokens, and a hash of every message the model saw."""
    import hashlib

    steps = [[s.tool_name, json.dumps(s.tool_args, sort_keys=True, default=str), s.page_url, s.claimed_answer,
              (s.self_check or {}).get("verdict"), (s.self_check or {}).get("reason")] for s in result.steps]
    return {
        "success": result.success, "end_state": result.end_state, "tier": result.tier,
        "model_calls": result.model_calls, "script_steps": result.script_steps, "error": result.error,
        "repair_sent": result.repair_sent, "repair_reply": result.repair_reply,
        "turn_verdicts": [turn[0] for turn in result.script_turns],
        "tokens": [result.total_input_tokens, result.total_output_tokens, result.total_cached_tokens],
        "steps": steps,
        "model_seen_sha": hashlib.sha256(json.dumps(model.calls, sort_keys=True, default=str).encode()).hexdigest(),
        "strategy": result.strategy,
    }


TOUCHED: list = []


def _forbid(*names):
    def boom(*args, **kwargs):
        TOUCHED.append(names)  # spa swallows errors, so the call is recorded as well as raised
        raise AssertionError("a specialist ran with CU_SF_STRATEGY unset")
    return boom


@pytest.mark.parametrize("raw", [None, "", "  ", "navx,forms,spa2"])
def test_off_matches_tip3_exactly(monkeypatch, raw):
    """The golden file was made by running these scenarios on t3/tip3 (b9ac977), before any specialist merge."""
    if raw is None:
        monkeypatch.delenv("CU_SF_STRATEGY", raising=False)
    else:
        monkeypatch.setenv("CU_SF_STRATEGY", raw)
    monkeypatch.setattr(strategy_form, "run_form_strategy", _forbid())
    monkeypatch.setattr(strategy_form, "claims", _forbid())
    monkeypatch.setattr(strategy_spa, "fetch_html", _forbid())
    monkeypatch.setattr(strategy_spa, "run_spa", _forbid())
    monkeypatch.setattr(strategy_nav, "claims", _forbid())
    monkeypatch.setattr(strategy_nav, "read_after_pass", _forbid())
    TOUCHED.clear()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    got = {
        "pass_first": _fingerprint(*_run([_script_reply(CLICK_SCRIPT)])),
        "repair_then_pass": _fingerprint(*_run([_script_reply(STAY), _script_reply(CLICK_SCRIPT)])),
    }
    assert got == golden
    assert TOUCHED == []


@pytest.mark.parametrize("raw,on", [
    ("nav,form,spa", {"nav", "form", "spa"}),
    (" NAV , Form ,spa ", {"nav", "form", "spa"}),
    ("form", {"form"}),
    ("spa,nav", {"nav", "spa"}),
    ("", set()),
])
def test_one_comma_list_switches_each_specialist(monkeypatch, raw, on):
    monkeypatch.setenv("CU_SF_STRATEGY", raw)
    got = {name for name, flag in (("nav", strategy_nav.enabled()), ("form", strategy_form.strategy_enabled()),
                                   ("spa", strategy_spa.spa_enabled())) if flag}
    assert got == on


def test_the_routers_overlap_on_real_task_text():
    """Why a precedence is needed: some task texts are claimed by two routers."""
    convert = "Use the converter to convert 10 miles to kilometres and report the result."
    assert strategy_form.claims(convert) and strategy_nav.claims(convert)
    reveal = "Click the Reveal button and report the colour that appears."
    assert strategy_nav.claims(reveal) and strategy_spa.route_task(reveal, SERVER_PAGE).claim
    assert not strategy_spa.is_app_shell(SERVER_PAGE) and strategy_spa.is_app_shell(SHELL)
    fill = "Fill in the contact form with the name Sam and report the confirmation message."
    assert strategy_form.claims(fill) and not strategy_nav.claims(fill)


class Recorder:
    def __init__(self):
        self.calls = []

    def nav_read(self):
        async def read(**kwargs):
            self.calls.append("nav")
            return strategy_nav.ReadOutcome(verdict=kwargs["verdict"], payload=kwargs["payload"], label="nav:kept")
        return read

    def spa_run(self):
        async def run(page, model, *, task, start_url, provider, outcome):
            self.calls.append("spa")
            outcome.reason = "no answer appeared"
            return outcome
        return run


@pytest.fixture
def all_on(monkeypatch):
    monkeypatch.setenv("CU_SF_STRATEGY", "nav,form,spa")
    rec = Recorder()
    monkeypatch.setattr(strategy_nav, "claims", lambda description: True)
    monkeypatch.setattr(strategy_nav, "read_after_pass", rec.nav_read())
    monkeypatch.setattr(strategy_spa, "run_spa", rec.spa_run())
    monkeypatch.setattr(strategy_spa, "route_task",
                        lambda description, signals: strategy_spa.Route(True, "cue 'click'", signals))
    return monkeypatch, rec


def test_form_work_goes_to_form_and_nothing_else(all_on):
    monkeypatch, rec = all_on

    async def form_gives_up(harness, description, start_url):
        rec.calls.append("form")
        return strategy_form.FormOutcome(claimed=True, reason="no usable form", model_calls=1,
                                         input_tokens=7, output_tokens=3)
    monkeypatch.setattr(strategy_form, "run_for_harness", form_gives_up)
    monkeypatch.setattr(strategy_spa, "fetch_html", _forbid())
    result, _model = _run([_script_reply(CLICK_SCRIPT)])
    assert rec.calls == ["form"]  # no spa fetch or run, and no nav read on the generic fallback
    assert result.success and result.strategy == "form:fallback"
    assert result.model_calls == 2 and result.total_input_tokens == 10


def test_a_value_read_goes_to_nav_when_spa_has_only_a_text_cue(all_on):
    monkeypatch, rec = all_on
    monkeypatch.setattr(strategy_form, "claims", lambda description: False)
    monkeypatch.setattr(strategy_spa, "fetch_html", lambda url: SERVER_PAGE)
    result, _model = _run([_script_reply(CLICK_SCRIPT)])
    assert rec.calls == ["nav"]
    assert result.success and result.strategy == "nav:kept"
    assert "deferred to nav" in result.strategy_detail["route"]
    assert result.strategy_detail["claimed"] is False


def test_spa_takes_an_app_shell_first_and_nav_reads_after_its_fallback(all_on):
    monkeypatch, rec = all_on
    monkeypatch.setattr(strategy_form, "claims", lambda description: False)
    monkeypatch.setattr(strategy_spa, "fetch_html", lambda url: SHELL)
    result, _model = _run([_script_reply(CLICK_SCRIPT)])
    assert rec.calls == ["spa", "nav"]
    assert result.success and result.strategy == "spa_fallback+nav:kept"


def test_spa_alone_still_claims_on_a_text_cue(monkeypatch):
    """Without nav, spa keeps its own router: a cue on a server-rendered page is enough."""
    monkeypatch.setenv("CU_SF_STRATEGY", "spa")
    rec = Recorder()
    monkeypatch.setattr(strategy_spa, "fetch_html", lambda url: SERVER_PAGE)
    monkeypatch.setattr(strategy_spa, "run_spa", rec.spa_run())

    async def nothing():
        return None
    harness = SimpleNamespace(_begin_browser_launch=lambda: None, _wait_for_browser=nothing,
                              mcp_client=SimpleNamespace(_page=object()), anthropic=object(), provider="openai")
    reveal = "Click the Reveal button and report the colour that appears."
    outcome = asyncio.run(strategy_spa.maybe_run_spa(harness, task_description=reveal, start_url="https://fixture.test/"))
    assert outcome.claimed and rec.calls == ["spa"]
    deferred = asyncio.run(strategy_spa.maybe_run_spa(harness, task_description=reveal,
                                                      start_url="https://fixture.test/", defer_to_nav=True))
    assert not deferred.claimed and rec.calls == ["spa"]
