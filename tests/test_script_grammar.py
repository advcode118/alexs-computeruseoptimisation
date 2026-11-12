"""Generic script_first grammar regressions. Mocks only: no network or LLM."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from bench.script_first import _run_step_on_page, parse_task_script, run_on_mcp, run_on_page
from bench.script_grammar import GRAMMAR_HINT
from proxy.script import MAX_SCRIPT_CHARS, MAX_SCRIPT_LINES, ScriptError, parse_script


REGRESSIONS = json.loads(Path(__file__).with_name("fixtures").joinpath("script_grammar.json").read_text())
STILL_REJECTED = {"const assignment await", "top-level return object", "locator chained filter"}
LOCATORS = [
    ('page.locator(".target")', "css", ".target", ""),
    ('page.getByRole("button", {name: "Target"})', "role", "Target", "button"),
    ('page.getByLabel("Target")', "label", "Target", ""),
    ('page.getByText("Target")', "text", "Target", ""),
    ('page.getByPlaceholder("Target")', "placeholder", "Target", ""),
]
OPS = [
    ("click()", "click", "", None),
    ('fill("hello")', "fill", "hello", None),
    ('press("Enter")', "press", "Enter", None),
    ("check()", "check", "", None),
    ("uncheck()", "uncheck", "", None),
    ('selectOption("CA")', "select_option", "CA", None),
    ("textContent()", "text_content", "", "textContent"),
    ("innerText()", "inner_text", "", "innerText"),
    ('getAttribute("href")', "get_attribute", "href", "getAttribute"),
]
MODIFIERS = [
    ("", ()), (".first()", (("first", 0),)), (".last()", (("last", 0),)),
    (".nth(2)", (("nth", 2),)), (".nth(-1).first()", (("nth", -1), ("first", 0))),
]


def fake_page():
    page = Mock()
    page.url = "https://example.com/catalog"
    locator = Mock()
    page.locator.return_value = locator
    for method in ("get_by_role", "get_by_label", "get_by_text", "get_by_placeholder"):
        getattr(page, method).return_value = locator
    locator.first = locator
    locator.last = locator
    locator.nth.return_value = locator
    for method in ("click", "fill", "press", "check", "uncheck", "select_option"):
        setattr(locator, method, AsyncMock())
    for method, value in (("text_content", "textContent"), ("inner_text", "innerText"), ("get_attribute", "getAttribute")):
        setattr(locator, method, AsyncMock(return_value=value))
    for method in ("goto", "click", "fill", "press", "go_back", "wait_for_url"):
        setattr(page, method, AsyncMock())
    page.title = AsyncMock(return_value="Catalog")
    page.keyboard.press = AsyncMock()
    page.keyboard.type = AsyncMock()
    page.evaluate = AsyncMock(return_value={"url": page.url, "text": "Catalog"})
    return page, locator


@pytest.mark.parametrize("row", REGRESSIONS, ids=lambda row: row["idiom"])
def test_supplied_25_idioms(row):
    if row["idiom"] in STILL_REJECTED:
        with pytest.raises(ScriptError, match="page.evaluate"):
            parse_task_script(row["source"])
        return
    steps = parse_task_script(row["source"])
    assert steps[0].kind == "goto"
    page, _ = fake_page()
    payload = json.loads(asyncio.run(run_on_page(page, row["source"])).splitlines()[0])
    assert payload["ok"] is True
    assert payload["steps"] == len(steps)


def test_regression_counts():
    assert len(REGRESSIONS) == 25
    assert sum(row["accepted"] for row in REGRESSIONS) == 6  # Original parser measurement.
    accepted = []
    for row in REGRESSIONS:
        try:
            parse_task_script(row["source"])
        except ScriptError:
            continue
        accepted.append(row["idiom"])
    assert len(accepted) == 22
    assert set(accepted) == {row["idiom"] for row in REGRESSIONS} - STILL_REJECTED


@pytest.mark.parametrize("locator_source,finder,name,role", LOCATORS)
@pytest.mark.parametrize("modifier,positions", MODIFIERS)
@pytest.mark.parametrize("op,python_op,value,returned", OPS)
def test_locator_actions_map_and_execute(locator_source, finder, name, role, modifier, positions, op, python_op, value, returned):
    source = f"await {locator_source}{modifier}.{op};"
    step, = parse_task_script(source)
    assert step.kind == ("read" if returned else "locator")
    action = step.action
    assert (action.finder, action.name, action.role, action.value) == (finder, name, role, value)
    assert action.op == op.split("(")[0]
    assert action.positions == positions
    page, locator = fake_page()
    assert asyncio.run(_run_step_on_page(page, step)) == returned
    args = (value,) if value else ()
    getattr(locator, python_op).assert_awaited_once_with(*args, timeout=5000)
    if finder == "css":
        page.locator.assert_called_once_with(name)
    elif finder == "role":
        page.get_by_role.assert_called_once_with(role, name=name)
    else:
        getattr(page, f"get_by_{finder}").assert_called_once_with(name)
    if positions and positions[0][0] == "nth":
        locator.nth.assert_called_once_with(positions[0][1])


@pytest.mark.parametrize("prefix,suffix", [("", ""), ("await ", ""), ("", ";"), ("await ", ";")])
@pytest.mark.parametrize("source", [
    'page.locator("a").click()', 'page.getByText("Next").last().innerText()',
    'page.click("text=Next")', 'page.fill("#q", "hello")', 'page.press("#q", "Enter")',
    'page.keyboard.press("Enter")', 'page.keyboard.type("hello")', 'page.goBack()',
    'page.title()', 'page.url()',
])
def test_await_and_semicolon_are_optional(source, prefix, suffix):
    assert len(parse_task_script(prefix + source + suffix)) == 1


@pytest.mark.parametrize("method,python_method", [
    ("getByRole", "get_by_role"), ("getByText", "get_by_text"),
    ("getByLabel", "get_by_label"), ("getByPlaceholder", "get_by_placeholder"),
])
@pytest.mark.parametrize("exact", [True, False, None])
def test_exact_is_propagated(method, python_method, exact):
    option = "" if exact is None else f", exact: {str(exact).lower()}"
    target = f'"button", {{name: "Next"{option}}}' if method == "getByRole" else f'"Next"' + (f', {{exact: {str(exact).lower()}}}' if exact is not None else "")
    step, = parse_task_script(f"page.{method}({target}).first().click()")
    assert step.action.exact is exact
    page, _ = fake_page()
    asyncio.run(_run_step_on_page(page, step))
    kwargs = {} if exact is None else {"exact": exact}
    if method == "getByRole":
        kwargs["name"] = "Next"
    getattr(page, python_method).assert_called_once_with("button" if method == "getByRole" else "Next", **kwargs)


@pytest.mark.parametrize("modifier", ["first", "last", "nth"])
def test_modifier_dispatch_selects_the_correct_locator(modifier):
    page, locator = fake_page()
    selected = Mock()
    selected.click = AsyncMock()
    if modifier == "nth":
        locator.nth.return_value = selected
    else:
        setattr(locator, modifier, selected)
    argument = "2" if modifier == "nth" else ""
    step, = parse_task_script(f'page.locator("a").{modifier}({argument}).click()')
    asyncio.run(_run_step_on_page(page, step))
    selected.click.assert_awaited_once_with(timeout=5000)
    locator.click.assert_not_awaited()


@pytest.mark.parametrize("source,method,args,kind", [
    ('page.click("text=Next")', "click", ("text=Next",), "page"),
    ('page.fill("input[name=q]", "hello")', "fill", ("input[name=q]", "hello"), "page"),
    ('page.press("#q", "Enter")', "press", ("#q", "Enter"), "page"),
    ('page.keyboard.press("Control+A")', "press", ("Control+A",), "keyboard"),
    ('page.keyboard.type("hello")', "type", ("hello",), "keyboard"),
    ('page.goBack()', "go_back", (), "page"),
])
def test_page_and_keyboard_actions(source, method, args, kind):
    step, = parse_task_script(source)
    assert step.kind == kind
    assert step.action.finder == kind
    page, _ = fake_page()
    asyncio.run(_run_step_on_page(page, step))
    target = page.keyboard if kind == "keyboard" else page
    options = {} if kind == "keyboard" else {"timeout": 10000 if method == "go_back" else 5000}
    if method == "go_back":
        options["wait_until"] = "domcontentloaded"
    getattr(target, method).assert_awaited_once_with(*args, **options)
    page.evaluate.assert_not_awaited()


@pytest.mark.parametrize("source,seconds", [
    ('page.keyboard.press("Enter")', 5), ('page.keyboard.type("hello")', 5),
    ('page.title()', 1), ('page.evaluate(() => document.title)', 5),
])
def test_methods_without_playwright_timeouts_keep_runner_bounds(monkeypatch, source, seconds):
    page, _ = fake_page()
    seen = []

    async def wait_for(pending, *, timeout):
        seen.append(timeout)
        return await pending

    monkeypatch.setattr("bench.script_first.asyncio.wait_for", wait_for)
    step, = parse_task_script(source)
    asyncio.run(_run_step_on_page(page, step))
    assert seen == [seconds]


@pytest.mark.parametrize("source,expected", [
    ('page.locator("h1").textContent()', "textContent"),
    ('page.getByText("Catalog").innerText()', "innerText"),
    ('page.getByRole("link", {name: "Next"}).getAttribute("href")', "getAttribute"),
    ('page.title()', "Catalog"), ('page.url()', "https://example.com/catalog"),
])
def test_top_level_reads_are_noted_like_evaluate(source, expected):
    page, _ = fake_page()
    actual = json.loads(asyncio.run(run_on_page(page, source)).splitlines()[0])
    page, _ = fake_page()
    page.evaluate.side_effect = [expected, {"url": page.url, "text": "Catalog"}]
    evaluated = json.loads(asyncio.run(run_on_page(page, 'page.evaluate(() => "same value")')).splitlines()[0])
    assert actual["extracted"] == evaluated["extracted"] == [expected]
    assert actual["claimed"] == evaluated["claimed"]


@pytest.mark.parametrize("returned", [None, "", "x" * 1000, '{"answer": "Catalog"}'])
def test_read_extraction_has_the_same_empty_caps_and_object_rules(returned):
    page, locator = fake_page()
    locator.text_content.return_value = returned
    actual = json.loads(asyncio.run(run_on_page(page, 'page.locator("h1").textContent()')).splitlines()[0])
    page, _ = fake_page()
    page.evaluate.side_effect = [returned, {"url": page.url, "text": "Catalog"}]
    evaluated = json.loads(asyncio.run(run_on_page(page, 'page.evaluate(() => null)')).splitlines()[0])
    assert actual.get("extracted") == evaluated.get("extracted")
    assert actual.get("claimed") == evaluated.get("claimed")


ESCAPES = [
    'const title = await page.title()', 'let x = 1', 'var x = 1', 'title = await page.title()',
    'page.url = "https://example.com"', 'page.locator = () => null',
    'if (true) { page.title(); }', 'for (;;) { page.title(); }', 'while (true) {}',
    'do {} while (true)', 'switch (1) {case 1: break;}', 'try {} catch (e) {}',
    'return {answer: "Catalog"}', 'return\n{answer: "Catalog"}',
    'page.locator("a").evaluate(el => el.textContent)',
    'page.getByText("Next").first().evaluate(el => el.click())',
    'page.locator("a").evaluateAll(els => els.length)',
    'page.$eval("a", el => el.textContent)', 'page.$$eval("a", els => els.length)',
    'page.evaluateHandle(() => document.body)', 'page.locator("a").evaluateHandle(el => el)',
    'page.addScriptTag({content: "alert(1)"})', 'page.addInitScript(() => alert(1))',
    'page.route("**/*", route => route.continue())', 'page.unroute("**/*")',
    'page.context()', 'page.context().newPage()', 'page.exposeFunction("fn", () => 1)',
    'page.expose_function("fn", () => 1)', 'page.exposeBinding("fn", () => 1)',
    'page . route("**/*", () => {})', 'page . context()',
    'page["evaluate"](() => 1)', 'page.constructor.constructor("alert(1)")()',
    'page.keyboard["press"]("Enter")', 'page.keyboard.constructor("x")',
    'page.locator("a").click.call(null)', 'page.locator("a").nth(1 + 1).click()',
    'page.locator(selector).click()', 'page.locator(`a${code}`).click()',
    'page.locator("a").click({timeout: runCode()})', 'page.fill("#q", runCode())',
    'page.locator("a").click(), page.addScriptTag({content: "x"})',
    'page.locator("a").filter({hasText: "Next"}).click()',
    'const x = "networkidle"', 'page.locator("networkidle").evaluate(el => el)',
    'page.waitForTimeout(1).addScriptTag({content: "x"})',
]


@pytest.mark.parametrize("source", ESCAPES)
def test_escape_attempts_rejected_before_any_page_action(source):
    page, _ = fake_page()
    script = 'page.goto("https://example.com");\n' + source
    with pytest.raises(ScriptError) as error:
        asyncio.run(run_on_page(page, script))
    assert GRAMMAR_HINT in str(error.value)
    assert "\n" not in str(error.value)
    assert page.mock_calls == []


@pytest.mark.parametrize("source", [row[0] + ".click()" for row in LOCATORS] + [
    'page.click("a")', 'page.fill("#q", "x")', 'page.press("#q", "Enter")',
    'page.keyboard.press("Enter")', 'page.keyboard.type("x")', 'page.goBack()',
    'page.title()', 'page.url()', 'page.locator("a").innerText()',
])
def test_all_new_forms_keep_script_limits_and_denylist(source):
    assert len(parse_task_script(";".join([source] * MAX_SCRIPT_LINES))) == MAX_SCRIPT_LINES
    with pytest.raises(ScriptError, match="more than"):
        parse_task_script(";".join([source] * (MAX_SCRIPT_LINES + 1)))
    with pytest.raises(ScriptError, match="longer than"):
        parse_task_script(source + " // " + "x" * MAX_SCRIPT_CHARS)
    for token in ("require(", "process.", "child_process", "import ", "import(", "fetch(", "eval(", "new Function", "browser_run_code_unsafe"):
        with pytest.raises(ScriptError, match="not part of this script"):
            parse_task_script(source + " // " + token + " sentinel")


@pytest.mark.parametrize("source", [
    'page.title()', 'page.url()', 'page.goBack()', 'page.keyboard.type("x")',
    'page.click("a")', 'page.locator("a").textContent()',
])
def test_mcp_does_not_treat_new_forms_as_evaluate(source):
    call_tool = AsyncMock()
    with pytest.raises(ScriptError, match="page.goto and page.evaluate only"):
        asyncio.run(run_on_mcp(call_tool, source))
    call_tool.assert_not_awaited()


def test_ignored_options_cannot_disable_timeouts_or_run_code():
    page, locator = fake_page()
    step, = parse_task_script('page.locator("a").click({timeout: 0, force: true})')
    asyncio.run(_run_step_on_page(page, step))
    locator.click.assert_awaited_once_with(timeout=5000)
    assert parse_task_script('page.fill("#q", "networkidle")')[0].action.value == "networkidle"
    with pytest.raises(ScriptError):
        parse_task_script('page.getByText("Next", {exact: "true"}).click()')


def test_role_without_name_and_js_string_literals():
    page, _ = fake_page()
    step, = parse_task_script('page.getByRole("button").last().click()')
    asyncio.run(_run_step_on_page(page, step))
    page.get_by_role.assert_called_once_with("button")
    source = r'''page.locator('input[name="q"]').fill('line\n\u0041\t\x42\\\'')'''
    step, = parse_task_script(source)
    assert step.action.name == 'input[name="q"]'
    assert step.action.value == "line\nA\tB\\'"


def test_proxy_grammar_is_not_extended():
    with pytest.raises(ScriptError):
        parse_script('page.locator("a").click()')
