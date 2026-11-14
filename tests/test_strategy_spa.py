"""SPA contract tests: real DOM locally, fake model, no network or API calls."""

import asyncio
import json

import pytest

from bench import strategy_spa as spa
from bench.harness import BenchmarkHarness
from bench.probe import filter_task_kinds
from bench.script_first import ScriptFirstClient


def test_router_uses_html_not_framework_name_alone():
    shell = spa.html_signals('<div id="root"></div><script src="/app.js"></script>')
    assert spa.route_task("Report the release version", shell).claim
    ssr = spa.html_signals('<div id="root">' + 'Rendered article. ' * 100 + '</div><script></script>')
    assert not spa.route_task("Report the release version", ssr).claim
    assert spa.route_task("Expand the details and report the value", ssr).claim
    assert not spa.route_task("Submit the registration form", shell).claim
    assert not spa.route_task("Search for a guide", shell).claim
    assert not spa.route_task("Report the release version", spa.html_signals('<script></script>', 403)).claim
    assert not spa.route_task("Report the release version", spa.HtmlSignals(error="timeout")).claim


def test_answer_rejects_unchanged_chrome_and_unperformed_action():
    start = spa.PageView(title="Dashboard | Example", site="Example", lines=["Example", "Status", "Ready"])
    final = spa.PageView(title=start.title, site=start.site, lines=["Example", "Status", "Ready", "Complete"], chrome={"Example"})
    check = lambda answer, acted: spa.answer_problem(answer, task="Click the switch and report status",
        start=start, final=final, appeared=["Complete"], acted=acted)
    assert check("Example", True)
    assert check("Ready", True)
    assert check("Complete", False)
    assert not check("Complete", True)
    assert check("Invented", True)


def test_kind_filter_is_explicit_and_refuses_empty_selection():
    tasks = [{"id": "x_spa_one"}, {"id": "x_js_two"}, {"id": "x_form_three"}]
    assert filter_task_kinds(tasks) is tasks
    assert filter_task_kinds(tasks, "spa,js") == tasks[:2]
    with pytest.raises(ValueError, match="no tasks"):
        filter_task_kinds(tasks, "missing")


async def _with_page(test):
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await test(page)
        finally:
            await browser.close()


def test_hidden_label_late_controls_state_diff_and_stale_ids():
    async def check(page):
        await page.set_content('''<label for="done">Pay utility bill</label>
            <input id="done" type="checkbox" style="opacity:0" onchange="out.innerText=this.checked?'1 item left':'2 items left'">
            <div><input id="adjacent" type="checkbox" style="opacity:0"><label>Buy supplies</label></div>
            <p id="out">2 items left</p><div id="links"></div><div id="results"></div>
            <script>links.innerHTML=Array.from({length:180},(_,i)=>`<a href="#">Navigation ${i}</a>`).join(' ')</script>''')
        net = spa.NetworkWatch(page)
        try:
            before = await spa.observe(page, task="Pay utility bill")
            box = next(c for c in before.controls if c["role"] == "checkbox")
            assert box["name"] == "Pay utility bill"
            result = await spa.run_actions(page, net, [{"do": "check", "id": box["id"]}])
            assert not result.error
            after = await spa.observe(page)
            assert "1 item left" in spa.new_lines(before, after)
            assert next(c for c in after.controls if c["id"] == box["id"])["state"] == "checked"
            adjacent = next(c for c in after.controls if c["name"] == "Buy supplies")
            assert adjacent["role"] == "checkbox"
            result = await spa.run_actions(page, net, [{"do": "check", "id": adjacent["id"]}])
            assert not result.error and await page.locator("#adjacent").is_checked()
            await page.evaluate("results.innerHTML='<a href=\"#flat\">Array.flat</a>'")
            view = await spa.observe(page, task="Open Array.flat")
            assert any(c["name"] == "Array.flat" for c in view.controls)
            await page.locator("#done").evaluate("el => el.remove()")
            stale = await spa.run_actions(page, net, [{"do": "check", "id": box["id"]}])
            assert "no longer" in stale.error
            unshown = await spa.run_actions(page, net, [{"do": "click", "id": 999}], allowed_ids={1})
            assert "not in the observation" in unshown.error
        finally:
            net.detach()
    asyncio.run(_with_page(check))


def test_settle_waits_for_late_render_and_caps_continuous_mutation():
    async def check(page):
        await page.set_content('<div id="out"></div>')
        await page.evaluate("setTimeout(() => out.innerText='The result has rendered', 140)")
        await spa.settle(page, None, cap_ms=1200, quiet_ms=80, min_text=10)
        assert "result has rendered" in (await spa.observe(page)).lines[0]
        await page.evaluate("window.timer=setInterval(() => out.innerText=String(Date.now()), 20)")
        elapsed = await spa.settle(page, None, cap_ms=250, quiet_ms=80)
        assert 200 <= elapsed < 1000
        await page.evaluate("clearInterval(timer)")
    asyncio.run(_with_page(check))


class Model:
    def __init__(self, fallback=False):
        self.calls = []
        self.fallback = fallback

    async def create_message(self, messages, tools, **kwargs):
        self.calls.append(messages)
        if tools[0]["name"] == "page_step":
            if self.fallback:
                data = {"status": "fail"}
            elif len(self.calls) == 1:
                import re
                control = re.search(r'\[(\d+)\] button "Reveal"', messages[0]["content"])
                data = {"status": "act", "actions": [{"do": "click", "id": int(control[1])}]}
            else:
                data = {"status": "answer", "answer": "Azure"}
            name = "page_step"
        else:
            name = "run_script"
            data = {"code": 'await page.goto("https://fixture.test/");\n'
                'await page.getByRole("button", { name: "Reveal" }).click();\n'
                'await page.evaluate(() => ({answer: document.querySelector("#answer").innerText}));'}
        return {"content": [{"type": "tool_use", "id": "step", "name": name, "input": data}],
                "usage": {"input_tokens": 10, "output_tokens": 5}}, 1.0


@pytest.mark.parametrize("fallback", [False, True])
def test_harness_success_or_fallback_is_blind_and_accounts_all_calls(tmp_path, monkeypatch, fallback):
    monkeypatch.setenv("CU_SF_STRATEGY", "other,spa")
    monkeypatch.setattr(spa, "fetch_html", lambda url: spa.HtmlSignals())
    def forbidden(*args):
        raise AssertionError("live run read answer key")
    monkeypatch.setattr("bench.tasks.markers_for_task", forbidden)
    async def no_grade(*args):
        pass
    monkeypatch.setattr(BenchmarkHarness, "_read_shared_page", no_grade)

    async def check(page):
        await page.route("https://fixture.test/**", lambda route: route.fulfill(body='''
            <title>Palette demo</title><h1>Palette</h1><p>Choose a color to reveal its value.</p>
            <button onclick="answer.innerText='Azure'">Reveal</button><p id="answer"></p>''', content_type="text/html"))
        model = Model(fallback)
        harness = BenchmarkHarness(arm="script_first", runs_dir=tmp_path)
        harness.provider = "openai"
        harness.anthropic = model
        harness.mcp_client = ScriptFirstClient(page=page)
        result = await harness.run_task("not-in-catalog", "Click Reveal and report the color", "https://fixture.test/",
                                        expected_answer="SECRET", check_url_contains="SECRET")
        assert result.success and result.end_state == "PASS"
        assert result.strategy == ("spa_fallback" if fallback else "spa")
        assert result.model_calls == 2
        assert result.total_input_tokens == 20 and result.total_output_tokens == 10
        assert result.steps[-1].claimed_answer == "Azure"
        assert "SECRET" not in json.dumps(model.calls)
    asyncio.run(_with_page(check))


def test_off_does_no_routing_or_page_work(monkeypatch):
    monkeypatch.delenv("CU_SF_STRATEGY", raising=False)
    assert not asyncio.run(spa.maybe_run_spa(object(), task_description="Click a tab", start_url="https://fixture.test")).claimed
