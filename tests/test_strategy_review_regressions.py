"""PR80 review regressions: synthetic pages/models only, no benchmark data."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from bench import harness as hm, strategy_form as form, strategy_spa as spa
from bench.script_first import format_run_result
from bench.selfcheck_replay import build_units, confusion

START = "https://fixture.example/"
URL = START + "catalog"


class Model:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = 0

    async def create_message(self, *_args, **_kwargs):
        self.calls += 1
        return next(self.replies), 1.0


def reply(name, action):
    return {"content": [{"type": "tool_use", "id": "step", "name": name, "input": action}],
            "usage": {"input_tokens": 7, "output_tokens": 3}}


class Client:
    def __init__(self, results):
        self.results = iter(results)

    def tools_for_claude(self):
        return []

    async def call_tool(self, *_args):
        return next(self.results), 1.0


async def noop(*_args, **_kwargs):
    pass


def test_nav_after_failed_script_preserves_paid_usage(tmp_path, monkeypatch):
    from tests.test_strategy_nav import FakePage

    monkeypatch.setenv("CU_SF_STRATEGY", "nav")
    monkeypatch.setenv("CU_SF_NAV_MF", "0")
    monkeypatch.setenv("CU_SF_NAV_READ", "always")
    monkeypatch.delenv("CU_SF_REPAIR", raising=False)
    model = Model([
        reply("run_script", {"code": "first"}), reply("run_script", {"code": "second"}),
        {"content": [{"type": "text", "text": '{"line":1,"value":"Mara Vale"}'}],
         "usage": {"input_tokens": 7, "output_tokens": 3}},
    ])
    harness = hm.BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path)
    harness._read_shared_page = noop
    harness.anthropic = model
    harness.mcp_client = Client([
        format_run_result(ok=False, url=URL, text="Loading catalogue", step_count=1, error="timeout"),
        format_run_result(ok=True, url=URL, title="Catalogue", text="Author: Mara Vale",
                          step_count=1, claimed={"answer": "Mara Vale"}),
    ])
    harness.mcp_client._page = FakePage({"url": URL, "title": "Catalogue", "text": "Author: Mara Vale"})
    result = asyncio.run(harness.run_task("synthetic", "Report the author of the selected book.", START))
    assert result.success, result.error
    assert result.model_calls == model.calls == 3
    assert result.total_input_tokens == 21 and result.total_output_tokens == 9


def test_nav_history_normalization_does_not_bypass_the_earlier_page_check():
    from bench.strategy_nav import _recheck

    payload = {"url": URL, "title": "Catalogue", "text": "Author: Mara Vale",
               "ok": True, "claimed": {"answer": "Mara Vale"}}
    verdict = _recheck(payload, URL, START, "Report the author of the selected book.",
                       earlier=[dict(payload, ok=False)])
    assert verdict.verdict == "FAIL"
    assert "before the form was submitted" in verdict.reason


@pytest.mark.parametrize("delay", [0, 31])
def test_form_fallback_preserves_generic_repair_budget(tmp_path, monkeypatch, delay):
    clock = [0.0]
    monkeypatch.setenv("CU_SF_STRATEGY", "form")
    monkeypatch.delenv("CU_SF_REPAIR", raising=False)

    async def specialize(*_args):
        clock[0] += delay
        return form.FormOutcome(claimed=True, reason="no usable form", model_calls=1,
                                input_tokens=7, output_tokens=3)

    monkeypatch.setattr(hm, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    monkeypatch.setattr(form, "run_for_harness", specialize)
    harness = hm.BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path)
    harness._read_shared_page = noop
    harness.anthropic = Model([reply("run_script", {"code": "first"}), reply("run_script", {"code": "second"})])
    harness.mcp_client = Client([
        format_run_result(ok=True, url=URL, text="Result: 42", step_count=1, claimed={"answer": "missing"}),
        format_run_result(ok=True, url=URL, text="Result: 42", step_count=1, claimed={"answer": "42"}),
    ])
    result = asyncio.run(harness.run_task("synthetic", "Report the result.", START))
    assert result.success and result.repair_sent
    assert harness.anthropic.calls == 2 and result.model_calls == 3
    assert result.total_input_tokens == 21
    assert result.total_wall_ms >= delay * 1000


def test_metadata_only_form_check_is_ungraded():
    outcome = form.FormOutcome(passed=True, claimed=True, answer="Request saved", final_url=URL,
        page_text="Request saved", reason="the answer appeared after the submit",
        steps=[form.FormStep(action={"action": "done"}, result="", page_url=URL)])
    steps = []
    form.append_steps(outcome, steps)
    rows = [{"_file": "synthetic", "task_id": "synthetic", "self_checks": [steps[-1].self_check]}]
    units = build_units(rows, {"synthetic": {"description": "Submit and report the confirmation.",
                                           "check_text": "Request saved"}})
    assert units[0]["graded"] is None
    assert units[0]["after"] == "UNKNOWN"
    for key in ("before", "after"):
        metrics = confusion(units, key)
        assert metrics["graded_scripts"] == 0 and metrics["ungraded_scripts"] == 1
        assert metrics["precision"] is None and metrics["recall"] is None


def test_empty_but_recorded_page_evidence_still_counts_as_a_failed_grade():
    from bench.selfcheck_replay import grade_check

    task = {"description": "Report the confirmation.", "check_text": "Request saved"}
    assert grade_check(task, {"page_url": URL, "payload": {"text": ""}}) is False
    assert grade_check(task, {"page_url": URL}) is None


def test_spa_ids_are_assigned_and_ambiguous_live_matches_are_refused(monkeypatch):
    monkeypatch.setattr(spa, "settle", noop)

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content('''
                  <button data-cu-id="7" onclick="window.chosen='delete'">Delete record</button>
                  <button data-cu-id="7" onclick="window.chosen='reveal'">Reveal value</button>
                  <div id="shadow"></div>
                  <script>
                    window.__cuNextId = "untrusted";
                    document.querySelector('#shadow').attachShadow({mode:'open'}).innerHTML =
                      '<button data-cu-id="7">Shadow button</button>';
                  </script>''')
                view = await spa.observe(page)
                ids = {c["id"] for c in view.controls}
                assert len(ids) == len(view.controls) == 3
                assert all(type(n) is int for n in ids)
                target = next(c["id"] for c in view.controls if c["name"] == "Reveal value")
                result = await spa.run_actions(page, None, [{"do": "click", "id": target}], allowed_ids=ids)
                assert not result.error
                assert await page.evaluate("window.chosen") == "reveal"
                # A collision introduced after observation must not pick the first match.
                await page.evaluate("""id => {
                    window.chosen = '';
                    document.querySelector('button').setAttribute('data-cu-id', String(id));
                }""", target)
                result = await spa.run_actions(page, None, [{"do": "click", "id": target}], allowed_ids=ids)
                assert result.error and not result.done
                assert await page.evaluate("window.chosen") == ""
            finally:
                await browser.close()

    asyncio.run(run())


@pytest.mark.parametrize("native_submit", [False, True])
def test_preview_cannot_stand_in_for_form_submission(native_submit):
    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page()
                html = """<form onsubmit="event.preventDefault(); window.submits=(window.submits||0)+1;
                    document.querySelector('output').textContent='Request saved'">
                  <label>Name<input required></label>
                  <button type="button" onclick="document.querySelector('output').textContent='Preview ready'">Preview</button>
                  <button type="submit">Send</button></form><output></output>"""
                await page.route("https://fixture.example/**", lambda route: route.fulfill(body=html, content_type="text/html"))
                model = Model([
                    reply("form_step", {"action": "fill", "fields": [{"n": 1, "value": "Sam"}],
                                        "press": 3 if native_submit else 2}),
                    reply("form_step", {"action": "done", "answer": "Request saved" if native_submit else "Preview ready"}),
                ])
                outcome = await form.run_form_strategy(page, model, "Submit the form and report the confirmation.", URL)
                assert outcome.passed is native_submit, outcome.reason
                assert await page.evaluate("window.submits||0") == int(native_submit)
                assert outcome.model_calls == 2 and outcome.input_tokens == 14
            finally:
                await browser.close()

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["orphan", "invalid_form_owner", "valid_external_owner"])
def test_submit_needs_a_real_native_form_owner(mode):
    """A type=submit button with no native owner (orphan, or form= naming no form) is not a submit."""
    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page()
                field = "<label>Name<input required></label>"
                attr = {"orphan": "", "invalid_form_owner": 'form="missing"', "valid_external_owner": 'form="real"'}[mode]
                button = f"""<button type="submit" {attr}
                    onclick="document.querySelector('output').textContent='Preview ready'">Preview</button>"""
                body = field + button if mode == "orphan" else f'<form id="real">{field}{button}</form>'
                html = body + """<output></output><script>window.submits = 0;
                  document.addEventListener('submit', e => { e.preventDefault(); window.submits++;
                    document.querySelector('output').textContent='Request saved'; });</script>"""
                await page.route("https://fixture.example/**", lambda route: route.fulfill(body=html, content_type="text/html"))
                valid = mode == "valid_external_owner"
                model = Model([
                    reply("form_step", {"action": "fill", "fields": [{"n": 1, "value": "Sam"}], "press": 2}),
                    reply("form_step", {"action": "done", "answer": "Request saved" if valid else "Preview ready"}),
                ])
                outcome = await form.run_form_strategy(page, model, "Submit the form and report the confirmation.", URL)
                assert outcome.passed is valid, outcome.reason
                assert await page.evaluate("window.submits") == int(valid)
            finally:
                await browser.close()

    asyncio.run(run())
