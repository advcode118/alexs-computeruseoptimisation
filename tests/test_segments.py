"""Synthetic segment tests: no model, public site, task definitions, or answer key."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest

from bench.arms import _SCRIPT_FIRST_PROMPT, prompt_for
from bench.openai_client import responses_tools
from bench.script_first import (
    EvidenceVerdict, ScriptFirstClient, format_run_result, model_visible_script_result,
    parse_task_script, run_on_page, script_result_payload, script_runtime_verdict,
)
from bench.segments import (
    SEG_MAX_CALLS, SEG_MAX_LOOKS, SEG_MAX_SCRIPTS, SEG_WAIT_S, SEG_WAIT_TASK_S, SEG_WALL_S,
    build_receipt, gate_final, mutations_run, parse_segment_args, poll_checks,
    segment_continue_text, segment_repair_note, segments_enabled,
)

URL = "http://fixture.test/item"
EVIDENCE = 'page.evaluate(() => ({url: location.href, answer: document.querySelector("#value")?.innerText || ""}))'


@pytest.fixture(autouse=True)
def segment_mode(monkeypatch):
    monkeypatch.setenv("CU_SF_SEGMENTS", "1")
    monkeypatch.delenv("CU_SF_REPAIR", raising=False)
    monkeypatch.delenv("CU_SF_LOOK", raising=False)
    # These tests use local synchronous navigation; avoid paying the unrelated
    # legacy landing wait after every fixture evaluate.
    monkeypatch.setattr("bench.script_first._LAND_TIMEOUT_S", 0.01)


@pytest.fixture(scope="module")
def browser_runner():
    from playwright.async_api import async_playwright

    with asyncio.Runner() as runner:
        async def start():
            driver = await async_playwright().start()
            try:
                try:
                    browser = await driver.chromium.launch(channel="chrome", headless=True)
                except Exception:
                    browser = await driver.chromium.launch(headless=True)
            except BaseException:
                await driver.stop()
                raise
            return driver, browser

        driver, browser = runner.run(start())

        def run(case):
            async def isolated():
                context = await browser.new_context()
                await context.route("**/*", lambda route: route.abort())
                page = await context.new_page()
                try:
                    return await case(page)
                finally:
                    await context.close()
            return runner.run(isolated())

        yield run
        runner.run(browser.close())
        runner.run(driver.stop())


async def fixture(page, html: str, *, navigate: bool = True):
    await page.route("http://fixture.test/**", lambda route: route.fulfill(
        status=200, content_type="text/html", body=html,
    ))
    if navigate:
        await page.goto(URL)


async def script(client, code: str = EVIDENCE, **kwargs) -> dict:
    text, _ = await client.call_tool("run_script", {"code": code, **kwargs})
    return script_result_payload(text)


def test_flag_precedence_and_fixed_caps(monkeypatch):
    assert segments_enabled()
    assert (SEG_MAX_SCRIPTS, SEG_MAX_CALLS, SEG_MAX_LOOKS, SEG_WALL_S) == (6, 8, 2, 45.0)
    assert (SEG_WAIT_S, SEG_WAIT_TASK_S) == (3.0, 10.0)
    monkeypatch.setenv("CU_SF_REPAIR", "blind")
    assert not segments_enabled()
    monkeypatch.delenv("CU_SF_REPAIR")
    monkeypatch.setenv("CU_SF_SEGMENTS", "true")
    assert not segments_enabled()


@pytest.mark.parametrize("args", [
    None, [], {"final": None}, {"final": 0}, {"final": "false"},
    {"expect": None}, {"expect": {}}, {"expect": [{"text": "x"}] * 5},
    {"expect": [{"text": ""}]}, {"expect": [{"text": "  \n"}]},
    {"expect": [{"text": "x" * 201}]}, {"expect": [{"text": 42}]},
    {"expect": [{"text": "yes", "gone_text": "no"}]},
    {"expect": [{"selector": "#value"}]}, {"expect": [False]},
    {"expect": [{"control": {"name": "Next", "exact": False}}]},
    {"expect": [{"control": {"name": "Next", "role": None}}]},
    {"expect": [{"control": {"role": "button"}}]},
])
def test_invalid_args_fail_closed(args):
    _final, _checks, errors = parse_segment_args(args)
    assert errors


def test_valid_arguments_and_schema_conversion(monkeypatch):
    checks = [{"text": "x" * 200}, {"gone_text": "Loading"}, {"url_contains": "/item"},
              {"control": {"role": "button", "name": "Next"}}]
    assert parse_segment_args({"final": False, "expect": checks}) == (False, checks, [])
    assert parse_segment_args({}) == (True, [], [])
    assert parse_segment_args({"expect": [{"control": {"name": "Next"}}]})[2] == []
    tools = ScriptFirstClient().tools_for_claude()
    schema = tools[0]["input_schema"]
    assert schema["required"] == ["code"]
    assert schema["properties"]["final"]["default"] is True
    variants = schema["properties"]["expect"]["items"]["oneOf"]
    assert len(variants) == 4 and all(v["additionalProperties"] is False for v in variants)
    assert variants[-1]["properties"]["control"]["additionalProperties"] is False
    assert tools[-1]["name"] == "look" and tools[-1]["input_schema"]["required"] == []
    assert responses_tools(tools)[0]["parameters"] == schema
    prompt = prompt_for("script_first")
    assert "final:false" in prompt and "three seconds" in prompt
    assert "The first script must finish" not in prompt
    assert "Call this once." not in tools[0]["description"]
    monkeypatch.delenv("CU_SF_SEGMENTS")
    assert prompt_for("script_first") == _SCRIPT_FIRST_PROMPT
    default = ScriptFirstClient().tools_for_claude()
    assert list(default[0]["input_schema"]["properties"]) == ["code"]
    assert [tool["name"] for tool in default] == ["run_script", "task_failed"]
    monkeypatch.setenv("CU_SF_SEGMENTS", "1")
    monkeypatch.setenv("CU_SF_REPAIR", "blind")
    assert ScriptFirstClient().tools_for_claude() == default


def test_mutation_receipt_uses_completed_ops_without_values():
    source = "\n".join([
        'page.goto("http://fixture.test/")', 'cu.fill("Name", "private input")',
        'cu.press("Name", "Enter")', 'cu.click("Next")',
        'page.locator("#agree").check()', 'page.locator("#agree").uncheck()',
        'page.locator("select").selectOption("one")', 'page.keyboard.type("private input")',
        'page.goBack()', 'page.locator("h1").innerText()', EVIDENCE,
    ])
    steps = parse_task_script(source)
    assert [m["op"] for m in mutations_run(steps, 10)] == [
        "fill", "press", "click", "check", "uncheck", "select", "key", "back",
    ]
    receipt = build_receipt(segment=2, final=False, ok=False, steps=steps, done=3, attempted=4,
                            error="stopped", url_before=URL, url_after=URL)
    assert receipt["steps_total"] == 11
    assert receipt["mutations_run"] == [{"index": 2, "op": "fill"}, {"index": 3, "op": "press"}]
    assert receipt["failed_step"]["index"] == 4
    assert receipt["effects_uncertain"]
    assert "private input" not in json.dumps(receipt)
    assert not receipt["moved"] and receipt["segments_left"] == 4
    assert "Step 4 failed" in segment_repair_note(receipt)
    assert "do not replay" in segment_repair_note(receipt)
    assert "not complete" in segment_continue_text(receipt, "current synthetic page")


@pytest.mark.parametrize("status", ["PASS", "FAIL", "UNKNOWN"])
@pytest.mark.parametrize("case", ["valid", "failed_check", "nonfinal", "failed_run", "missing", "malformed"])
def test_gate_only_downgrades(status, case):
    verdict = EvidenceVerdict(status, "runtime reason", URL)
    receipt = build_receipt(ok=True, steps_run=1, steps_total=1, url_after=URL)
    if case == "failed_check":
        receipt["checks"] = [{"kind": "text", "arg": "Ready", "ok": False, "waited_ms": 3}]
    elif case == "nonfinal":
        receipt["final"] = False
    elif case == "failed_run":
        receipt["ok"] = False
    elif case == "missing":
        receipt = None
    elif case == "malformed":
        receipt["checks"] = [{"ok": True}]
    gated = gate_final(verdict, receipt)
    assert gated.scored_url == URL
    if case == "valid" or status == "FAIL":
        assert gated is verdict
    else:
        assert gated.verdict == "FAIL"


def test_receipt_is_model_visible_but_evidence_fields_stay_hidden():
    receipt = build_receipt(ok=True, steps_run=1, steps_total=1, url_after=URL)
    text = format_run_result(ok=True, url=URL, step_count=1, receipt=receipt,
                             text="body", selector_text="judge only", headings=["hidden heading"])
    payload = script_result_payload(model_visible_script_result(text))
    assert payload["receipt"] == receipt
    assert "selector_text" not in payload and "headings" not in payload


@pytest.mark.parametrize("update", [
    {"checks": [{"kind": "control", "arg": "not JSON", "ok": True, "waited_ms": 0}]},
    {"checks": [{"kind": "unknown", "arg": "x", "ok": True, "waited_ms": 0}]},
    {"checks": [{"kind": "text", "arg": "", "ok": True, "waited_ms": 0}]},
    {"mutations_run": [{"index": 2, "op": "click"}]},
    {"moved": False}, {"segment": 0}, {"steps_run": 0, "steps_total": 0},
    {"failed_step": {"index": 0, "source": "bad", "error": "bad"}},
])
def test_gate_rejects_malformed_receipt_details(update):
    receipt = build_receipt(ok=True, steps_run=1, steps_total=1, url_after=URL)
    receipt.update(update)
    assert gate_final(EvidenceVerdict("PASS", "runtime", URL), receipt).verdict == "FAIL"


@pytest.mark.parametrize("source,expected", [
    ('page.goto("http://fixture.test/"); page.evaluate(() => 1); page.evaluate(() => 2)',
     ["goto", "ready", "evaluate", "evaluate", "finish"]),
    ('page.evaluate(() => 1); page.locator("button").click(); page.evaluate(() => 2)',
     ["evaluate", "locator", "ready", "evaluate", "finish"]),
    ('page.goto("http://fixture.test/")', ["goto", "ready", "finish"]),
])
def test_hook_runs_only_before_contiguous_evaluate_tail(monkeypatch, source, expected):
    events = []

    async def step(page, step):
        events.append(step.kind)

    async def ready():
        events.append("ready")

    async def finish(*args, **kwargs):
        events.append("finish")
        return "done"

    monkeypatch.setattr("bench.script_first._run_step_on_page", step)
    monkeypatch.setattr("bench.script_first._finish_page", finish)
    assert asyncio.run(run_on_page(object(), source, before_tail=ready)) == "done"
    assert events == expected
    events.clear()
    asyncio.run(run_on_page(object(), source, before_tail=None))
    assert events == [event for event in expected if event != "ready"]


def test_delayed_content_readiness_precedes_evidence(browser_runner):
    async def case(page):
        html = '<h1>Item</h1><div id="value"></div><script>setTimeout(() => value.innerText = "Price: 42", 600)</script>'
        await fixture(page, html, navigate=False)
        code = f'page.goto("{URL}"); {EVIDENCE}'
        client = ScriptFirstClient(page=page)
        without = await script(client, code)
        verdict, _ = script_runtime_verdict(json.dumps(without), URL, URL, asks_value=True, task="Report the price.")
        assert verdict.verdict == "FAIL"
        client.reset_segments()
        with_expect = await script(client, code, expect=[{"text": "Price:"}])
        receipt = with_expect["receipt"]
        assert receipt["ok"] and 500 <= receipt["checks"][0]["waited_ms"] <= 3000
        assert with_expect["claimed"]["answer"] == "Price: 42"
        verdict, _ = script_runtime_verdict(json.dumps(with_expect), URL, URL, asks_value=True, task="Report the price.")
        assert gate_final(verdict, receipt).verdict == "PASS"
        assert receipt["wait_ms_left"] < 9500
    browser_runner(case)


def test_controls_require_one_visible_exact_match(browser_runner):
    async def case(page):
        await fixture(page, '<button>Next</button><button>Next</button><button style="display:none">Next</button>')
        for check in ({"control": {"name": "Next", "role": "button"}}, {"control": {"name": "Next"}}):
            assert not (await poll_checks(page, [check], 0.05))[0]["ok"]
        await page.evaluate('document.querySelectorAll("button")[1].remove()')
        assert (await poll_checks(page, [{"control": {"name": "Next", "role": "button"}}], 0.1))[0]["ok"]
        assert (await poll_checks(page, [{"control": {"name": "Next"}}], 0.1))[0]["ok"]
        assert not (await poll_checks(page, [{"control": {"name": "Nex", "role": "button"}}], 0.05))[0]["ok"]
    browser_runner(case)


@pytest.mark.parametrize("expect,tail", [
    ({"text": "Ready"}, 'document.querySelector("#ready").remove()'),
    ({"gone_text": "Busy"}, 'document.querySelector("#ready").innerText = "Busy"'),
    ({"control": {"name": "Next", "role": "button"}}, 'document.querySelector("button").remove()'),
])
def test_post_tail_recheck_rejects_stale_expectations(browser_runner, expect, tail):
    async def case(page):
        await fixture(page, '<div id="ready">Ready</div><button>Next</button><div id="value">42</div>')
        code = f'page.evaluate(() => {{ {tail}; return {{url: location.href, answer: "42"}}; }})'
        payload = await script(ScriptFirstClient(page=page), code, expect=[expect])
        receipt = payload["receipt"]
        assert not receipt["ok"] and not receipt["checks"][0]["ok"]
        assert receipt["steps_run"] == receipt["steps_total"] == 1
        assert receipt["failed_step"] is None and receipt["effects_uncertain"]
        assert gate_final(EvidenceVerdict("PASS", "runtime", URL), receipt).verdict == "FAIL"
    browser_runner(case)


def test_late_success_cannot_upgrade_failed_readiness(browser_runner, monkeypatch):
    monkeypatch.setattr("bench.segments.SEG_WAIT_S", 0.2)

    async def case(page):
        await fixture(page, '<div id="value">42</div>')
        code = 'page.evaluate(() => { document.body.append("Ready"); return {answer: "42"}; })'
        payload = await script(ScriptFirstClient(page=page), code, expect=[{"text": "Ready"}])
        assert "Ready" in await page.locator("body").inner_text()
        assert not payload["receipt"]["checks"][0]["ok"] and not payload["receipt"]["ok"]
    browser_runner(case)


def test_tail_execution_does_not_spend_the_shared_poll_allowance(browser_runner, monkeypatch):
    monkeypatch.setattr("bench.segments.SEG_WAIT_S", 0.12)

    async def case(page):
        await fixture(page, '<div>Ready</div><div id="value">42</div>')
        client = ScriptFirstClient(page=page)
        code = 'page.evaluate(() => new Promise(resolve => setTimeout(() => resolve({answer:"42"}), 150)))'
        payload = await script(client, code, expect=[{"text": "Ready"}])
        assert payload["receipt"]["ok"]
        assert payload["receipt"]["checks"][0]["ok"]
        assert client.segment_wait_left > 9.9
    browser_runner(case)


def test_failed_absence_read_never_passes(browser_runner):
    async def case(page):
        await fixture(page, "<p>Busy</p>")
        await page.close()
        check, = await poll_checks(page, [{"gone_text": "Busy"}], 0.05)
        assert check["ok"] is False and check["error"]
    browser_runner(case)


def test_all_slow_reads_share_one_deadline():
    class Page:
        def locator(self, selector):
            return self

        async def inner_text(self):
            await asyncio.Event().wait()

    started = time.perf_counter()
    checks = [{"gone_text": str(n)} for n in range(4)]
    result = asyncio.run(poll_checks(Page(), checks, 0.12))
    elapsed = time.perf_counter() - started
    assert elapsed < 0.3  # Four serial per-check timeouts would exceed 0.48s.
    assert all(not check["ok"] and check["error"] for check in result)


def test_invalid_args_have_zero_browser_side_effects(browser_runner):
    async def case(page):
        await fixture(page, '<input aria-label="Name"><div id="value">42</div>')
        client = ScriptFirstClient(page=page)
        code = f'page.goto("{URL}?changed"); cu.fill("Name", "changed"); {EVIDENCE}'
        for invalid in ({"final": "false"}, {"expect": [{"text": ""}]},
                        {"expect": [{"control": {"name": "Name", "selector": "input"}}]}):
            payload = await script(client, code, **invalid)
            assert not payload["ok"] and not payload["receipt"]["ok"]
            assert payload["receipt"]["checks"][0]["kind"] == "invalid"
            assert payload["receipt"]["steps_run"] == 0
            assert not payload["receipt"]["effects_uncertain"]
            assert payload["receipt"]["mutations_run"] == []
            assert page.url == URL and await page.locator("input").input_value() == ""
        payload = await script(client, "not a script")
        assert not payload["ok"] and payload["receipt"]["steps_run"] == 0
    browser_runner(case)


def test_failed_step_retains_mutations_and_recovery_never_replays(browser_runner, monkeypatch):
    monkeypatch.setattr("bench.script_first._ACTION_TIMEOUT_MS", 100)

    async def case(page):
        posts = []
        await fixture(page, """
            <form onsubmit="event.preventDefault(); window.submits=(window.submits||0)+1;
              fetch('/submit', {method:'POST'});
              history.pushState({},'', '/next'); document.querySelector('#state').innerText='Step two';">
              <input aria-label="Name"><button>Submit</button>
            </form><div id="state"></div><div id="value">42</div>""")

        async def submit(route):
            posts.append(route.request.method)
            await route.fulfill(status=200, body="submitted")

        await page.route("http://fixture.test/submit", submit)
        client = ScriptFirstClient(page=page)
        payload = await script(client, 'cu.fill("Name", "Jo"); cu.click("Submit"); cu.click("Missing"); ' + EVIDENCE,
                               final=False)
        receipt = payload["receipt"]
        assert not receipt["ok"] and receipt["steps_run"] == 2 and receipt["steps_total"] == 4
        assert receipt["failed_step"]["index"] == 3 and receipt["effects_uncertain"]
        assert receipt["mutations_run"] == [{"index": 1, "op": "fill"}, {"index": 2, "op": "click"}]
        assert receipt["moved"] and receipt["url_after"].endswith("/next")
        assert await page.evaluate("window.submits") == 1
        assert posts == ["POST"]
        recovered = await script(client, EVIDENCE, expect=[{"text": "Step two"}])
        assert recovered["receipt"]["ok"] and recovered["receipt"]["segment"] == 2
        assert await page.evaluate("window.submits") == 1
        assert posts == ["POST"]
    browser_runner(case)


def test_failed_input_can_already_have_issued_navigation(browser_runner, monkeypatch):
    monkeypatch.setattr("bench.script_first._ACTION_TIMEOUT_MS", 100)

    async def case(page):
        await fixture(page, '<button onclick="location.href=\'/slow?issued=1\'">Send</button>')
        requests = []
        release = asyncio.Event()

        async def slow(route):
            requests.append(route.request.url)
            await release.wait()
            await route.abort()

        await page.route("http://fixture.test/slow?*", slow)
        client = ScriptFirstClient(page=page)
        client.segment_deadline = time.perf_counter() + 0.3
        try:
            payload = await script(client, 'cu.click("Send")')
            assert requests == ["http://fixture.test/slow?issued=1"]
            receipt = payload["receipt"]
            assert not receipt["ok"] and receipt["steps_run"] == 0
            assert receipt["failed_step"]["index"] == 1
            assert receipt["effects_uncertain"] and not receipt["mutations_run"]
        finally:
            release.set()
    browser_runner(case)


@pytest.mark.parametrize("timeout_kind", ["wall", "evaluate"])
def test_timeout_receipt_retains_partial_execution_and_uncertain_evaluate(browser_runner, monkeypatch, timeout_kind):
    if timeout_kind == "evaluate":
        monkeypatch.setattr("bench.script_first._EVALUATE_TIMEOUT_S", 0.1)

    async def case(page):
        await fixture(page, '<input aria-label="Name"><div id="value">42</div>')
        client = ScriptFirstClient(page=page)

        class ForbiddenMarkers(dict):
            def __bool__(self):
                raise AssertionError("runtime consulted the answer key")

        client.end_markers = ForbiddenMarkers()
        client.segment_deadline = time.perf_counter() + (0.2 if timeout_kind == "wall" else 2.0)
        code = 'cu.fill("Name", "Jo"); page.evaluate(() => { document.body.dataset.issued="yes"; return new Promise(() => {}); })'
        payload = await script(client, code)
        receipt = payload["receipt"]
        assert not receipt["ok"]
        assert ("wall budget" if timeout_kind == "wall" else "TimeoutError") in payload["error"]
        assert receipt["steps_run"] == 1 and receipt["failed_step"]["index"] == 2
        assert receipt["effects_uncertain"]
        assert receipt["mutations_run"] == [{"index": 1, "op": "fill"}]
        assert await page.locator("input").input_value() == "Jo"
        assert await page.evaluate("document.body.dataset.issued") == "yes"
        client.reset_segments()
        assert client.segment_index == client.segment_looks == 0
        assert client.segment_wait_left == SEG_WAIT_TASK_S
        assert (await script(client))["receipt"]["ok"]
    browser_runner(case)


def test_wait_budget_is_shared_across_segments(browser_runner, monkeypatch):
    monkeypatch.setattr("bench.segments.SEG_WAIT_S", 0.12)
    monkeypatch.setattr("bench.segments.SEG_WAIT_TASK_S", 0.25)
    monkeypatch.setattr("bench.segments.SEG_RECHECK_S", 0.01)

    async def case(page):
        await fixture(page, '<div id="value">42</div>')
        client = ScriptFirstClient(page=page)
        for _ in range(5):
            payload = await script(client, expect=[{"text": "Absent"}, {"gone_text": "42"}], final=False)
            assert not payload["ok"]
        assert 0 <= client.segment_wait_left < 0.01
        assert payload["receipt"]["wait_ms_left"] < 10
        assert sum(check["waited_ms"] for check in payload["receipt"]["checks"]) < 30
    browser_runner(case)


def test_no_expect_fast_path_and_flag_off_ignore_extra_arguments(browser_runner, monkeypatch):
    async def case(page):
        await fixture(page, '<div id="value">42</div>')
        client = ScriptFirstClient(page=page)
        client.page_snapshot = AsyncMock(side_effect=AssertionError("unexpected snapshot"))
        original = page.evaluate
        reads = []

        async def evaluate(source, *args, **kwargs):
            reads.append(source)
            return await original(source, *args, **kwargs)

        monkeypatch.setattr(page, "evaluate", evaluate)
        enabled = await script(client)
        enabled_reads = list(reads)
        reads.clear()
        monkeypatch.delenv("CU_SF_SEGMENTS")
        client.end_markers = {}
        disabled = await script(client, final=False, expect="malformed but ignored")
        assert enabled_reads == reads
        assert enabled.pop("receipt")["ok"]
        assert enabled == disabled and "receipt" not in disabled
        client.page_snapshot.assert_not_called()
    browser_runner(case)


def test_look_optional_url_and_caps_and_expired_admission(browser_runner):
    async def case(page):
        await fixture(page, '<h1>Current page</h1><div id="value">42</div>')
        client = ScriptFirstClient(page=page)
        for args in ({}, {"url": URL + "?look"}):
            text, _ = await client.call_tool("look", args)
            assert "Current page" in text and "no check ran" in text
        text, _ = await client.call_tool("look", {"url": URL + "?forbidden"})
        assert "refused" in text and not page.url.endswith("forbidden")
        assert client.segment_looks == 2
        client.segment_deadline = time.perf_counter() - 1
        payload = await script(client, f'page.goto("{URL}?forbidden")')
        assert not payload["receipt"]["ok"] and payload["receipt"]["steps_run"] == 0
        assert not page.url.endswith("forbidden")
        client.reset_segments()
        client.segment_index = SEG_MAX_SCRIPTS
        payload = await script(client, f'page.goto("{URL}?forbidden")')
        assert not payload["receipt"]["ok"] and payload["receipt"]["segments_left"] == 0
        assert not page.url.endswith("forbidden")
    browser_runner(case)


def test_unstarted_client_still_returns_failure_receipt():
    text, _ = asyncio.run(ScriptFirstClient().call_tool("run_script", {"code": EVIDENCE}))
    assert script_result_payload(text)["receipt"]["ok"] is False


def test_repeat_keys_preserve_literal_spaces_and_requested_checks():
    from bench.segments import segment_request_key

    first = {"code": "cu.fill('City', 'NewYork')", "final": False}
    spaced = {"code": "cu.fill('City', 'New York')", "final": False}
    assert segment_request_key(first) != segment_request_key(spaced)
    assert segment_request_key(first) != segment_request_key({**first, "final": True})
    assert segment_request_key(first) != segment_request_key({**first, "expect": [{"text": "Saved"}]})
