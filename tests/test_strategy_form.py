"""Form mechanics and harness isolation on local, synthetic pages; no API or public network."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from bench import strategy_form as form
from bench.harness import BenchmarkHarness
from bench.script_first import ScriptFirstClient


class Model:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.calls = []

    async def create_message(self, messages, tools, **kwargs):
        self.calls.append(json.dumps(messages))
        action = next(self.actions)
        if callable(action):
            action = action(messages)
        return {"content": [{"type": "tool_use", "id": str(len(self.calls)),
                             "name": "form_step", "input": action}],
                "usage": {"input_tokens": 7, "output_tokens": 3, "cached_tokens": 2}}, 1.0


@pytest.mark.parametrize("text,wanted", [
    ("Fill in the enquiry form with my name and report the confirmation.", True),
    ("Calculate 12 percent of 450 and report the result.", True),
    ("Use site search to find the form documentation and report its title.", False),
    ("Read the contact address and report it.", False),
])
def test_router(text, wanted):
    assert form.claims(text) is wanted


def test_option_matching_refuses_ambiguity():
    assert form.match_option(["North America", "North Europe"], "North") == -1
    assert form.match_option(["North America", "North Europe"], "north europe") == 1


@pytest.mark.parametrize("answer,before,after,fresh,ok", [
    ("Booked", "Book now", "Booked", ["Booked"], True),
    ("Booked", "Already Booked", "Booked", ["Booked"], False),
    ("Booked", "Book now", "Booked", [], False),
    ("Missing", "Book now", "Booked", ["Booked"], False),
    ("Invalid email", "Book now", "Invalid email", ["Invalid email"], False),
    ("Booked", "Book now", "Booked\nError: declined", ["Booked", "Error: declined"], False),
])
def test_new_result_end_check(answer, before, after, fresh, ok):
    assert form.check_answer(answer, after, [before], fresh)[0] is ok


def test_disabled_and_unclaimed_do_not_touch_browser(monkeypatch):
    harness = SimpleNamespace(arm="script_first")  # no browser or model attributes
    monkeypatch.delenv("CU_SF_STRATEGY", raising=False)
    assert asyncio.run(form.run_for_harness(harness, "Submit the form and report it", "unused")) is None
    monkeypatch.setenv("CU_SF_STRATEGY", "other,FORM")
    assert asyncio.run(form.run_for_harness(harness, "Read the page title", "unused")) is None
    harness.arm = "playwright_mcp"
    assert asyncio.run(form.run_for_harness(harness, "Submit the form and report it", "unused")) is None


def test_native_fields_schema_and_readback():
    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            await page.set_content('''<form id="main">
              <label for="name">Name</label><input id="name" required>
              <label>Email<input type="email" required></label>
              <input type="number" aria-label="Count" min="1">
              <input type="date" placeholder="Date">
              <select aria-label="Region"><option>West</option><option>East</option></select>
              <fieldset><legend>Plan</legend><label><input type="radio" name="plan">Basic</label>
                <label><input type="radio" name="plan">Full</label></fieldset>
              <label><input type="checkbox">Accept</label><button>Send</button></form>
              <form><input required aria-label="Unrelated"><button>Other submit</button></form>''')
            schema = await form.read_schema(page, [])
            by_label = {item["label"]: item for item in schema["fields"]}
            assert set(by_label) == {"Name", "Email", "Count", "Date", "Region", "Plan", "Accept", "Unrelated"}
            values = [{"n": by_label[k]["n"], "value": v} for k, v in {
                "Name": "Sam", "Email": "sam@example.test", "Count": "5", "Date": "2030-06-04",
                "Region": "East", "Plan": "Full", "Accept": "on"}.items()]
            assert not await form.fill_fields(page, schema, values)
            assert not await form.invalid_fields(page, 0)  # unrelated required field is irrelevant
            assert await page.locator('input[type=date]').input_value() == "2030-06-04"
            assert await page.locator('input[type=radio]').nth(1).is_checked()
            assert await page.locator('input[type=checkbox]').is_checked()
            assert form.submit_problem(schema, values, schema["controls"][1]["n"])
            assert not form.submit_problem(schema, values, schema["controls"][0]["n"])
            await browser.close()
    asyncio.run(run())


@pytest.mark.parametrize("mode,expected", [
    ("delayed", True), ("stale", False), ("validation", False),
    ("wrong_control", False), ("invalid", False), ("bad_field", False),
])
def test_submit_provenance(mode, expected, monkeypatch):
    # Real browser events, delayed render, invalid controls and misleading existing results.
    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            result = "Invalid email" if mode == "validation" else "Request saved"
            html = '''<form onsubmit="event.preventDefault(); document.querySelector('output').textContent='Processing';
              setTimeout(() => document.querySelector('output').textContent=RESULT, 500)">
              <label>Name<input required></label><button>Send</button></form>
              <a href="#help">Help</a><output>INITIAL</output>'''
            html = html.replace("RESULT", "'" + result + "'").replace("INITIAL", "Request saved" if mode == "stale" else "")
            await page.route("https://fixture.test/**", lambda route: route.fulfill(body=html, content_type="text/html"))
            action = {"action": "fill", "fields": [{"n": 99 if mode == "bad_field" else 1,
                       "value": "" if mode == "invalid" else "Sam"}], "press": 3 if mode == "wrong_control" else 2}
            model = Model([action, {"action": "done", "answer": result}])
            outcome = await form.run_form_strategy(page, model, "Fill in the form with Sam and report the result.", "https://fixture.test/")
            assert outcome.passed is expected, outcome.reason
            assert outcome.model_calls == 2
            assert outcome.input_tokens == 14
            await browser.close()
    asyncio.run(run())


def test_harness_specialist_accounting_and_grader_blindness(tmp_path, monkeypatch):
    monkeypatch.setenv("CU_SF_STRATEGY", "form")
    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            html = '''<form onsubmit="event.preventDefault(); document.querySelector('output').textContent='Request saved'">
              <label>Name<input></label><button>Send</button></form><output></output>'''
            await page.route("https://fixture.test/**", lambda route: route.fulfill(body=html, content_type="text/html"))
            model = Model([{"action": "fill", "fields": [{"n": 1, "value": "Sam"}], "press": 2},
                           {"action": "done", "answer": "Request saved"}])
            harness = BenchmarkHarness(api_key="offline", runs_dir=tmp_path, arm="script_first")
            harness.anthropic = model
            harness.mcp_client = ScriptFirstClient(page=page)
            def markers(_task_id):
                assert len(model.calls) == 2  # only the post-run grade may read the key
                return {"answer_in_text": "SECRET_ANSWER"}
            monkeypatch.setattr("bench.tasks.markers_for_task", markers)
            result = await harness.run_task("synthetic_form", "Fill in the form with Sam and report the result.", "https://fixture.test/")
            assert result.success and result.strategy == "form"
            assert result.model_calls == 2 and result.total_input_tokens == 14
            assert result.total_output_tokens == 6 and result.total_cached_tokens == 4
            assert result.steps[-1].claimed_answer == "Request saved"
            assert "SECRET_ANSWER" not in "".join(model.calls)
            await browser.close()
    asyncio.run(run())


def test_fallback_keeps_usage_and_generic_path(tmp_path, monkeypatch):
    from tests.test_script_cache import _WikiPage, _script_reply, CLICK_SCRIPT, DESCRIPTION, START, LINK
    monkeypatch.setenv("CU_SF_STRATEGY", "form")
    async def give_up(*args):
        return form.FormOutcome(reason="no usable form", model_calls=1, input_tokens=7, output_tokens=3)
    monkeypatch.setattr(form, "run_for_harness", give_up)
    harness = BenchmarkHarness(api_key="offline", runs_dir=tmp_path, arm="script_first")
    from tests.test_script_cache import _Model
    harness.anthropic = _Model([_script_reply(CLICK_SCRIPT)])
    harness.mcp_client = ScriptFirstClient(page=_WikiPage({LINK: "article"}))
    result = asyncio.run(harness.run_task("wv_wikipedia_search", DESCRIPTION, START))
    assert result.success and result.strategy == "form:fallback"
    assert result.model_calls == 2 and result.total_input_tokens == 10


def test_correct_native_validation_then_submit():
    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            html = '''<form onsubmit="event.preventDefault(); document.querySelector('output').textContent='Request saved'">
              <label>Email<input type="email" required></label><button>Send</button></form><output></output>'''
            await page.route("https://fixture.test/**", lambda route: route.fulfill(body=html, content_type="text/html"))
            model = Model([
                {"action": "fill", "fields": [{"n": 1, "value": "not-an-email"}], "press": 2},
                {"action": "fill", "fields": [{"n": 1, "value": "sam@example.test"}], "press": 2},
                {"action": "done", "answer": "Request saved"},
            ])
            outcome = await form.run_form_strategy(page, model, "Submit the form and report the result.", "https://fixture.test/")
            assert outcome.passed and outcome.model_calls == 3
            assert "BROWSER BLOCKED" in outcome.steps[0].result
            assert "Request saved" not in outcome.steps[0].result
            await browser.close()
    asyncio.run(run())
