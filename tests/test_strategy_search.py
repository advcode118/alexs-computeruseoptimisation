"""Real DOM fixtures + fake choices; no external network or API calls."""
import asyncio
import json

import pytest
from playwright.async_api import async_playwright

from bench.script_first import PageEvidence
from bench.strategy_search import candidates, claims, enabled, landed_ok, run_search


TASK = "Use the site's search box to find the stable Quartz package and open its documentation page. Do not stop at search results."
START = "https://catalog.test/"


class Choices:
    def __init__(self, responses):
        self.responses = list(responses)
        self.inputs = []

    async def create_message(self, messages, tools, **kwargs):
        self.inputs.append(json.loads(messages[0]["content"]))
        return {"content": [{"type": "tool_use", "name": "choose", "input": self.responses.pop(0)}],
                "usage": {"input_tokens": 100, "output_tokens": 10, "cached_tokens": 20}}, 5.0


def test_router_is_opt_in_and_does_not_take_value_tasks(monkeypatch):
    monkeypatch.delenv("CU_SF_STRATEGY", raising=False)
    assert claims(TASK) and not enabled(TASK)
    monkeypatch.setenv("CU_SF_STRATEGY", "other, search")
    assert enabled(TASK)
    assert not claims("Open the project documentation.")
    assert not claims("Search the catalog and report the package version number.")


def test_candidates_keep_real_links_and_drop_unchanged_sidebar():
    old = {"url": "https://catalog.test/sidebar", "text": "Quartz"}
    new = {"url": "https://catalog.test/stable", "text": "Quartz stable"}
    other = {"url": "https://catalog.test/other", "text": "Other"}
    assert candidates([old, other, new, new], [old], navigated=False, query="Quartz") == [new, other]


def test_landing_rejects_search_page_and_wrong_destination():
    for url in (START, START + "search?q=Quartz", START + "wrong"):
        evidence = PageEvidence(url=url, title="Quartz", h1="Quartz", text="Quartz stable documentation")
        assert not landed_ok(TASK, START, evidence, START + "stable")[0]
    results = PageEvidence(url=START + "search?q=Quartz", title="Results", h1="Search results", text="Quartz stable")
    assert not landed_ok(TASK, START, results, results.url)[0]


async def _exercise(html, responses, search_html=None):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            requests = []

            async def route(req):
                url = req.request.url
                requests.append(url)
                if url == START:
                    body = html
                elif "/search" in url:
                    body = search_html or '<h1>Search results</h1><a href="/stable">Quartz stable</a><a href="/development">Quartz development</a>'
                else:
                    body = '<title>Quartz stable documentation</title><h1>Quartz stable documentation</h1><p>Quartz is a stable package with complete documentation.</p>'
                await req.fulfill(status=200, content_type="text/html", body=body)

            await page.route("https://catalog.test/**", route)
            model = Choices(responses)
            result = await run_search(page, model, TASK, START)
            return result, model, requests, page.url
        finally:
            await browser.close()


def test_native_search_submits_real_form_filters_and_opens_result():
    result, model, requests, url = asyncio.run(_exercise(
        '<form action="/search"><label>Search<input name="q"></label><label>Channel<select name="channel"><option value="dev">Development</option><option value="stable">Stable</option></select></label></form>',
        [{"box": 0, "query": "Quartz", "filters": [{"id": 0, "value": "stable"}]}, {"result": 0}],
    ))
    assert result.success, result.reason
    assert any("q=Quartz" in u and "channel=stable" in u for u in requests)
    assert url == START + "stable"
    assert result.model_calls == 2 and result.usage["input_tokens"] == 200
    assert result.steps[0].tool_args["actions"] == 5
    assert model.inputs[1]["results"][0]["url"] == START + "stable"


def test_js_search_reveals_input_then_uses_new_visible_results():
    html = '''<button onclick="document.querySelector('input').hidden=false">Search</button>
    <a href="/sidebar">Quartz sidebar</a><input type="search" hidden oninput="document.querySelector('section').innerHTML='<a href=/stable>Quartz stable</a>'"><section></section>'''
    result, model, _requests, url = asyncio.run(_exercise(html, [
        {"box": 0, "query": "Quartz", "filters": []}, {"result": 0},
    ]))
    assert result.success, result.reason
    assert url == START + "stable"
    assert [r["url"] for r in model.inputs[1]["results"]] == [START + "stable"]


@pytest.mark.parametrize("choice", [
    {"box": -1, "query": "Quartz", "filters": []},
    {"box": True, "query": "Quartz", "filters": []},
    {"box": 0, "query": "Quartz", "filters": [{"id": 0, "value": "invented"}]},
])
def test_bad_choices_fall_back_and_keep_paid_usage(choice):
    result, _model, requests, url = asyncio.run(_exercise('<form action="/search"><input type="search" name="q"></form>', [choice]))
    assert not result.success
    assert url == "about:blank"
    assert result.model_calls == 1 and result.usage["output_tokens"] == 10
    assert requests == [START]


def test_unrecognized_page_declines_without_a_model_call():
    result, model, _requests, url = asyncio.run(_exercise('<h1>Catalog</h1><input type="password">', []))
    assert not result.success and not model.inputs
    assert result.model_calls == 0 and url == "about:blank"


@pytest.mark.parametrize("flag,claimed,expected_calls", [("", False, 1), ("search", False, 2), ("search", True, 1)])
def test_harness_hook_fallback_costs_and_marker_boundary(tmp_path, monkeypatch, flag, claimed, expected_calls):
    from bench.harness import BenchmarkHarness, StepMetrics
    from bench.strategy_search import SearchOutcome
    import bench.strategy_search as strategy
    import bench.tasks as catalog
    from tests.test_script_cache import _WikiPage, _Model, _script_reply, EVIDENCE, FIXTURE
    from bench.script_first import ScriptFirstClient

    monkeypatch.setenv("CU_SF_STRATEGY", flag)
    calls = []

    async def specialist(page, model, task, start_url, **kwargs):
        calls.append((task, start_url))
        return SearchOutcome(success=claimed, reason="fixture", model_calls=1, model_ms=1,
            usage={"input_tokens": 7, "output_tokens": 3}, actions=2,
            steps=[StepMetrics(1, "search_strategy", {}, 0, 0, 1, 1, 7, 3, page_url=FIXTURE["page"]["url"])])

    def forbidden(*args, **kwargs):
        raise AssertionError("live search accessed judge catalog")

    async def no_grade(*args):
        pass

    monkeypatch.setattr(strategy, "run_search", specialist)
    monkeypatch.setattr(catalog, "markers_for_task", forbidden)
    monkeypatch.setattr(catalog, "task_by_id", forbidden)
    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path, arm="script_first")
    # This existing fake exercises the generic script executor after a decline.
    code = f'page.goto({json.dumps(FIXTURE["page"]["url"])});\n{EVIDENCE};'
    model = _Model([_script_reply(code)])
    harness.anthropic = model
    harness.mcp_client = ScriptFirstClient(page=_WikiPage({}))
    harness._read_shared_page = no_grade
    result = asyncio.run(harness.run_task(task_id="opaque", task_description=TASK, start_url=START))
    assert result.model_calls == expected_calls
    assert bool(calls) == bool(flag)
    assert result.strategy == ("search" if claimed else "search_fallback") if flag else result.strategy == ""
    if flag:
        assert result.total_input_tokens >= 7 and result.total_output_tokens >= 3
    assert len(model.calls) == (0 if claimed else 1)
