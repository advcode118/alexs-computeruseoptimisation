"""The forgiving executor on a real headless Chrome. No network and no model.

Each test loads a small local page with set_content and runs a script through
run_on_page. Skipped when Playwright's Chromium cannot start.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from bench.script_first import ScriptFirstClient, _empty_claim, parse_task_script, run_on_page
from bench.script_helpers import wrap_evaluate
from bench.script_resolve import side_effect_free

CLAIM = 'page.evaluate(() => cu.claim({answer: document.querySelector("#out")?.innerText || ""}))'


async def _with_page(html: str, script: str) -> dict:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - depends on the machine
            pytest.skip(f"Chromium is not available: {exc}")
        try:
            page = await browser.new_page()
            await page.set_content(html)
            text = await run_on_page(page, script)
            return json.loads(text.splitlines()[0])
        finally:
            await browser.close()


def run(html: str, script: str) -> dict:
    return asyncio.run(_with_page(html, script))


def answer(payload: dict) -> str:
    return (payload.get("claimed") or {}).get("answer", "")


def test_click_prefers_the_exact_visible_name_and_breaks_ties_in_document_order():
    html = """
    <button style="display:none" onclick="out.innerText='hidden'">Go</button>
    <button onclick="out.innerText='go further'">Go further</button>
    <a href="#" onclick="out.innerText='first go'; return false">Go</a>
    <button onclick="out.innerText='second go'">Go</button>
    <div id="out"></div>
    """
    payload = run(html, f'cu.click("Go"); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "first go"


def test_fill_finds_a_field_by_label_placeholder_aria_or_nearby_text():
    html = """
    <label for="a">E-mail address</label><input id="a">
    <input placeholder="Search docs" id="b">
    <input aria-label="Quantity" id="c">
    <table><tr><td>Telephone:</td><td><input id="d"></td></tr></table>
    <div id="out"></div>
    """
    script = """
    cu.fill("Email address", "x@example.com");
    cu.fill("Search", "flex");
    cu.fill("quantity", "3");
    cu.fill("Telephone", "555");
    page.evaluate(() => cu.claim({answer: ["a","b","c","d"].map(id => document.getElementById(id).value).join("|")}))
    """
    payload = run(html, script)
    assert payload["ok"] is True, payload
    assert answer(payload) == "x@example.com|flex|3|555"


def test_submit_names_a_forms_submit_button_and_a_bare_field_id_is_a_name():
    html = """
    <form onsubmit="out.innerText='sum ' + (Number(number1.value) + Number(number2.value)); return false">
      <input id="number1" name="number1"><input id="number2" name="number2">
      <button class="btn" type="submit"> Register </button>
    </form>
    <div id="out"></div>
    """
    payload = run(html, f'cu.fill("Number 1", "17"); cu.fill("Number 2", "25"); cu.click("Submit"); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "sum 42"


def test_a_miss_lists_the_visible_controls_for_the_repair_turn():
    html = '<button>Save draft</button><button>Publish now</button><input placeholder="Title">'
    payload = run(html, 'cu.click("Delete everything")')
    assert payload["ok"] is False
    assert "no control named 'Delete everything'" in payload["error"]
    assert "Publish now" in payload["error"]


def test_a_control_rendered_late_is_found_and_the_result_read_after_it_renders():
    html = """
    <div id="out"></div>
    <script>
      setTimeout(() => {
        const b = document.createElement("button");
        b.textContent = "Load results";
        b.onclick = () => setTimeout(() => { document.getElementById("out").innerText = "42 results"; }, 400);
        document.body.appendChild(b);
      }, 700);
    </script>
    """
    payload = run(html, f'cu.click("Load results"); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "42 results"


def test_a_consent_overlay_is_dismissed_before_the_click():
    html = """
    <button onclick="out.innerText='clicked'">Continue reading</button>
    <div id="out"></div>
    <div id="cookie-banner" style="position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.5)">
      <p>We use cookies.</p><button onclick="this.parentElement.remove()">Accept all</button>
    </div>
    """
    payload = run(html, f'cu.click("Continue reading"); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "clicked"


def test_locator_lines_take_a_regex_name_and_the_first_visible_of_several():
    html = """
    <a href="#" onclick="out.innerText='refs'; return false">4.2 References and Borrowing</a>
    <p class="note" style="display:none">Note</p><p class="note">Note</p>
    <div id="out"></div>
    """
    script = f"""
    page.getByRole("link", {{name: /references and borrowing/i}}).click();
    page.locator("p.note").textContent();
    {CLAIM}
    """
    payload = run(html, script)
    assert payload["ok"] is True, payload
    assert answer(payload) == "refs"


def test_a_helper_name_may_be_a_regex():
    html = '<a href="#" onclick="out.innerText=\'book\'; return false">Frankenstein; or, The Modern Prometheus by Shelley</a><div id="out"></div>'
    payload = run(html, f"cu.click(/frankenstein; or, the modern prometheus/i); {CLAIM}")
    assert payload["ok"] is True, payload
    assert answer(payload) == "book"


def test_a_role_locator_with_no_match_falls_back_to_the_visible_name():
    html = '<div role="button" tabindex="0" onclick="out.innerText=\'sent\'">Submit order</div><div id="out"></div>'
    payload = run(html, f'page.getByRole("link", {{name: "Submit order"}}).click(); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "sent"


def test_select_option_matches_a_label_loosely_and_a_bare_locator_only_waits():
    html = """
    <label for="p">Payment</label>
    <select id="p"><option value="">Choose</option><option value="cc">Credit card</option><option value="pp">PayPal</option></select>
    <div id="out"></div>
    """
    script = """
    page.getByText("Payment").first();
    page.getByLabel("Payment").selectOption({label: "card"});
    page.evaluate(() => cu.claim({answer: document.getElementById("p").value}))
    """
    payload = run(html, script)
    assert payload["ok"] is True, payload
    assert answer(payload) == "cc"
    clicked = run(html, 'cu.click("PayPal"); page.evaluate(() => cu.claim({answer: document.getElementById("p").value}))')
    assert answer(clicked) == "pp", clicked


def test_search_helper_types_into_the_search_box_and_submits_its_form():
    html = """
    <input placeholder="Your name">
    <form role="search" onsubmit="out.innerText='searched ' + q.value; return false">
      <input id="q" name="q" type="search"><button>Go</button>
    </form>
    <div id="out"></div>
    """
    payload = run(html, f'cu.search("borrowing"); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "searched borrowing"


def test_enter_in_a_field_that_does_nothing_clicks_the_form_submit_button():
    html = """
    <form onsubmit="out.innerText='posted ' + n.value; return false">
      <label>Number <input id="n" onkeydown="if (event.key === 'Enter') event.preventDefault()"></label>
      <button type="submit">Calculate</button>
    </form>
    <div id="out"></div>
    """
    payload = run(html, f'cu.fill("Number", "7"); cu.press("Number", "Enter"); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "posted 7"


def test_cu_text_reads_the_value_next_to_a_label_header_or_term():
    html = """
    <dl><dt>Status</dt><dd>Internet Standard</dd></dl>
    <table><tr><th>Population</th><td>1,234</td></tr></table>
    <p><b>Capital:</b> Paris</p>
    <table><thead><tr><th>Code</th><th>Name</th></tr></thead><tbody><tr><td>201</td><td>Created</td></tr></tbody></table>
    """
    script = 'page.evaluate(() => cu.claim({answer: [cu.text("Status"), cu.text("population"), cu.text("Capital"), cu.text("Name")].join("|")}))'
    payload = run(html, script)
    assert answer(payload) == "Internet Standard|1,234|Paris|Created"


def test_reads_wait_for_a_value_rendered_late_but_actions_are_never_repeated():
    html = """
    <div id="out"></div>
    <script>setTimeout(() => { document.getElementById("out").innerText = "ready"; }, 600);</script>
    """
    payload = run(html, CLAIM)
    assert answer(payload) == "ready"
    assert side_effect_free('() => document.querySelector("#out").innerText')
    assert not side_effect_free('() => document.querySelector("button").click()')
    assert not side_effect_free('() => { document.querySelector("form").requestSubmit(); }')
    assert _empty_claim({"answer": "", "key_text": "", "values": []})
    assert not _empty_claim({"answer": "", "key_text": "phrase", "values": []})
    assert "cu.text = function" in wrap_evaluate('() => cu.text("Status")')


def test_grammar_accepts_the_forms_weak_scripts_write():
    steps = parse_task_script(
        """
        await page.getByRole('link', {name: /older posts|next/i}).last().click();
        await page.getByText('toctree', {exact: false}).first();
        await page.getByLabel('Payment').selectOption({label: 'Card'});
        await page.locator('select#size').selectOption(['M']);
        await page.getByTitle('Home').click();
        await page.check('#agree');
        cu.search('blueprints');
        """
    )
    kinds = [(step.kind, step.action.op if step.action else step.helper.op) for step in steps]
    assert kinds == [
        ("locator", "click"),
        ("locator", "selectOption"),
        ("locator", "selectOption"),
        ("locator", "click"),
        ("page", "check"),
        ("helper", "search"),
    ]
    assert steps[0].action.pattern.flags == "i"
    assert json.loads(steps[1].action.option) == {"label": "Card"}


class _PreloadPage:
    def __init__(self):
        self.url = "about:blank"
        self.gotos = []

    async def goto(self, url, **kwargs):
        self.gotos.append(url)
        self.url = url

    async def title(self):
        return "Start"

    async def evaluate(self, source, *args):
        return {"url": self.url, "title": "Start", "text": "Start page", "answer": "Start page"}


def test_the_first_script_reuses_the_preloaded_start_page_and_a_repair_does_not():
    page = _PreloadPage()
    client = ScriptFirstClient(page=page)

    async def go():
        client.preload("https://example.com/start")
        first, _ = await client.call_tool(
            "run_script",
            {"code": 'page.goto("https://example.com/start/"); page.evaluate(() => ({answer: "Start page"}))'},
        )
        second, _ = await client.call_tool(
            "run_script",
            {"code": 'page.goto("https://example.com/start"); page.evaluate(() => ({answer: "Start page"}))'},
        )
        return first, second

    first, second = asyncio.run(go())
    assert page.gotos == ["https://example.com/start", "https://example.com/start"]
    assert json.loads(first.splitlines()[0])["steps"] == 2
    assert json.loads(second.splitlines()[0])["steps"] == 2


def test_a_different_first_goto_ignores_the_preload():
    page = _PreloadPage()
    client = ScriptFirstClient(page=page)

    async def go():
        client.preload("https://example.com/start")
        await asyncio.sleep(0)
        return await client.call_tool(
            "run_script",
            {"code": 'page.goto("https://example.com/deep/page"); page.evaluate(() => ({answer: "Start page"}))'},
        )

    asyncio.run(go())
    assert page.gotos[-1] == "https://example.com/deep/page"


def test_strict_matching_fails_on_two_different_exact_matches_and_lists_them(monkeypatch):
    import bench.script_resolve as resolve_module

    monkeypatch.setattr(resolve_module, "STRICT_MATCH", True)
    html = """
    <a href="/a" onclick="out.innerText='a'; return false">Details</a>
    <a href="/b" onclick="out.innerText='b'; return false">Details</a>
    <button onclick="out.innerText='save'">Save changes</button>
    <div id="out"></div>
    """
    payload = run(html, f'cu.click("Details"); {CLAIM}')
    assert payload["ok"] is False
    assert "2 controls match 'Details'" in payload["error"]
    payload = run(html, f'cu.click("Save"); {CLAIM}')
    assert payload["ok"] is True, payload
    assert answer(payload) == "save"
