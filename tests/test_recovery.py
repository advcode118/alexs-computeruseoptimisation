import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from bench.recovery import ActionGate, TaskProfile, classify_task, evaluate_checkpoints, plan_checkpoints
from bench.script_first import ScriptFirstClient, TaskStep, parse_task_script, run_on_page, script_runtime_verdict


@pytest.mark.parametrize("description,grounding,modality,risk,approval", [
    ("Read documentation", {}, "text", "read", False),
    ("Search for a guide", {"links": []}, "dom", "read", False),
    ("Describe the image color", {}, "visual", "read", False),
    ("Add an item", {}, "text", "reversible", False),
    ("Send a message", {}, "text", "irreversible", True),
    ("Read price", {"forms": [{"method": "POST"}]}, "dom", "read", False),
    ("", {"error": "TimeoutError"}, "text", "read", False),
])
def test_classify_task(description, grounding, modality, risk, approval):
    profile = classify_task(description, grounding)
    assert (profile.modality, profile.risk, profile.needs_approval) == (modality, risk, approval)
    assert isinstance(profile.signals, tuple) and profile.signals


def test_checkpoints():
    profile = TaskProfile("dom", "read", False, ())
    planned = plan_checkpoints('Search https://example.org/ for "Guide"', profile)
    evidence = {"url": "https://example.org/", "claimed": {"answer": "Guide"}, "controls": [{"role": "textbox"}]}
    assert all(item["passed"] for item in evaluate_checkpoints(planned, evidence))
    assert not any(item["passed"] for item in evaluate_checkpoints(planned, {"blocked_actions": [{}]}))
    assert evaluate_checkpoints([], {}) == []
    with pytest.raises(ValueError, match="unknown checkpoint"):
        evaluate_checkpoints([{"kind": "bad", "value": ""}], {})


@pytest.mark.parametrize("source,url,allowed", [
    ('page.getByRole("button", {name: "Buy"}).click()', "https://example.org/", False),
    ('page.getByRole("link", {name: "Remove account"}).click()', "https://example.org/", False),
    ('page.getByRole("button", {name: "Search"}).click()', "https://example.org/", True),
    ('page.goto("https://example.org/payment")', "https://example.org/", True),
    ('page.getByLabel("Name").fill("A")', "https://example.org/login", True),
    ('page.title()', "https://example.org/checkout", True),
])
def test_action_gate(source, url, allowed):
    class Locator:
        pass

    page = SimpleNamespace(url=url, get_by_role=lambda *a, **k: Locator())
    result, reason = asyncio.run(ActionGate().check(parse_task_script(source)[0], page))
    assert result is allowed
    assert reason


@pytest.mark.parametrize("function,allowed", [
    ('() => { location = "/guide"; }', True),
    ('() => location.assign("/guide")', True),
    ('() => location.replace("/guide")', True),
    ('() => "text".replace("text", "guide")', True),
    ('() => document.querySelector("a.next").click()', True),
    ('() => document.querySelector("#delete").click()', False),
    ('() => document.querySelector("form").submit()', False),
    ('() => document.querySelector("form").requestSubmit()', False),
    ('() => navigator.sendBeacon("/effect", "x")', False),
    ('() => fetch("/effect", {method: "POST"})', False),
    ('() => { const x = new XMLHttpRequest(); x.open("POST", "/effect"); }', False),
])
def test_evaluate_gate(function, allowed):
    step = TaskStep("evaluate", 1, function, function=function)
    result, _ = asyncio.run(ActionGate().check(step, SimpleNamespace(url="https://example.org/")))
    assert result is allowed


def test_evaluate_real_forms():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                for method, allowed in [("get", True), ("post", False)]:
                    for function in ['() => document.querySelector("form").requestSubmit()',
                                     '() => { const f = document.querySelector("form"); f.requestSubmit(); }',
                                     '() => document.querySelector("button").click()']:
                        await page.set_content(f'<form method="{method}"><input name="q"><button>Search</button></form>')
                        result = json.loads((await run_on_page(page, f'page.evaluate({function})')).splitlines()[0])
                        assert result['ok'] is allowed
                await page.set_content('<button id="commit">Buy</button>')
                function = '() => document.querySelector("#commit").click()'
                result = json.loads((await run_on_page(page, f'page.evaluate({function})')).splitlines()[0])
                assert not result['ok']
            finally:
                await browser.close()
    asyncio.run(run())


@pytest.mark.parametrize('expression', [
    "document.getElementById('commit').click()",
    "document.forms[0].elements[1].click()",
    "HTMLFormElement.prototype.submit.call(document.forms[0])",
    "document.querySelector('#commit').dispatchEvent(new MouseEvent('click',{bubbles:true}))",
])
def test_evaluate_runtime_interception(side_effect_server, expression):
    base, requests = side_effect_server

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f'{base}/checkout.html')
            gate = ActionGate()
            result = json.loads((await run_on_page(page, f'page.evaluate(() => {{ {expression}; }})', gate=gate)).splitlines()[0])
            assert result.get('blocked_actions')
            assert not any(path.startswith('/effect/checkout') for _, path in requests)
            again = json.loads((await run_on_page(page, 'page.title()', gate=gate)).splitlines()[0])
            assert again.get('blocked_actions') == gate.blocked
            await browser.close()
    asyncio.run(run())


def test_mixed_forms_get_submission(side_effect_server):
    base, requests = side_effect_server

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(base)
            await page.set_content('<form action="/search"><input name="q" value="guide"></form>'
                                   '<form method="post" action="/newsletter"></form>')
            result = json.loads((await run_on_page(page, 'page.evaluate(() => document.forms[0].requestSubmit())')).splitlines()[0])
            assert result['ok']
            await page.wait_for_url('**/search?q=guide')
            assert ('GET', '/search?q=guide') in requests
            assert not any(method == 'POST' for method, _ in requests)
            await browser.close()
    asyncio.run(run())


@pytest.mark.parametrize('source', ['page.locator("#commit").press("Enter")',
                                    'page.locator("#commit").press("Space")',
                                    'page.keyboard.press("Enter")', 'page.keyboard.press("Space")'])
def test_keyboard_commit(source):
    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content('<button id="commit" onclick="window.effect=true">Place order</button>')
            await page.locator('#commit').focus()
            result = json.loads((await run_on_page(page, source)).splitlines()[0])
            assert result.get('blocked_actions')
            assert not await page.evaluate('window.effect')
            await browser.close()
    asyncio.run(run())


def test_late_control_and_navigation(side_effect_server):
    base, _ = side_effect_server

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(base)
            await page.set_content('<script>setTimeout(() => { document.body.innerHTML = `<button onclick="this.textContent=\'Done\'">Search</button>`; }, 1300)</script>')
            result = json.loads((await run_on_page(page, 'page.getByRole("button", {name: "Search"}).click()')).splitlines()[0])
            assert result['ok'] and 'Done' in result['text']
            await page.set_content('<a href="/checkout.html">Next</a>')
            result = json.loads((await run_on_page(page, 'page.getByText("Next").click(); page.locator("#commit").click()')).splitlines()[0])
            assert result.get('blocked_actions')
            await browser.close()
    asyncio.run(run())


def test_read_only_sensitive_page_and_links(side_effect_server):
    base, _ = side_effect_server

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f'{base}/checkout.html')
            await page.set_content('<input aria-label="Query"><a href="/guide">Send feedback</a><button>Search</button>')
            for source in ['page.getByLabel("Query").fill("guide")',
                           'page.getByRole("button", {name: "Search"}).click()',
                           'page.getByText("Send feedback").click()']:
                assert json.loads((await run_on_page(page, source)).splitlines()[0])['ok']
            await browser.close()
    asyncio.run(run())


@pytest.mark.parametrize('label', ['Order', 'Checkout', 'Book', 'Reserve', 'Donate', 'Post',
                                  'Publish', 'Apply', 'Cancel', 'Unsubscribe', 'Sign up', 'Submit'])
def test_commit_vocabulary(label):
    allowed, _ = asyncio.run(ActionGate().check(parse_task_script(f'cu.click("{label}")')[0], SimpleNamespace(url='')))
    assert not allowed


def test_malformed_sensitive_url():
    assert not ActionGate()._sensitive('https://[bad')


def test_goal_checkpoints():
    checkpoints = plan_checkpoints('Search https://example.org for "Guide"', TaskProfile('dom', 'read', False, ()))
    evidence = {'url': 'https://example.org/results?q=Guide', 'claimed': {'answer': 'Guide to testing'}}
    assert all(item['passed'] for item in evaluate_checkpoints(checkpoints, evidence))
    evidence = {'url': 'https://example.org/results', 'controls': [{'role': 'textbox', 'value': 'Guide'}]}
    assert all(item['passed'] for item in evaluate_checkpoints(checkpoints, evidence))
    evidence = {'url': 'https://wrong.org', 'text': 'Guide', 'controls': [{'role': 'textbox'}]}
    assert not any(item['passed'] for item in evaluate_checkpoints(checkpoints, evidence) if item['kind'] != 'no_blocked_action')


def test_live_filled_goal_checkpoint():
    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content('<input aria-label="Query"><input type="password" aria-label="Secret" value="hidden">')
            payload = json.loads((await run_on_page(page, 'page.getByLabel("Query").fill("Guide")')).splitlines()[0])
            checkpoints = plan_checkpoints('Fill "Guide"', classify_task('Fill "Guide"', {}))
            assert all(item['passed'] for item in evaluate_checkpoints(checkpoints, payload))
            assert 'hidden' not in json.dumps(payload)
            await browser.close()
    asyncio.run(run())


def test_shared_gate_configuration():
    from bench.recovery import configure_gate

    client = ScriptFirstClient(description='Read')
    original = client.gate
    original.record_block('needs approval: test')
    profile = classify_task('Read', {'forms': [{}]})
    assert configure_gate(client, description='Read', profile=profile) is original
    assert configure_gate(client, description='Read').blocked
    assert client.gate.profile is profile
    assert not configure_gate(client, description='New task').blocked


@pytest.mark.parametrize('description', ['Read the book title', 'Apply filters to search', 'Find the sort order'])
def test_read_task_vocabulary(description):
    assert not classify_task(description, {}).needs_approval


def test_read_submit_controls_and_submitter(side_effect_server):
    base, requests = side_effect_server

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(base)
            for label in ['Apply filters', 'Order by price', 'Submit']:
                await page.set_content(f'<form action="/search"><button>{label}</button></form>')
                payload = json.loads((await run_on_page(page, f'page.getByRole("button", {{name: "{label}"}}).click()')).splitlines()[0])
                assert payload['ok']
            await page.set_content('<form action="/effect/checkout"><button>Buy</button></form>')
            payload = json.loads((await run_on_page(page, 'page.evaluate(() => document.forms[0].requestSubmit(document.querySelector("button")))')).splitlines()[0])
            assert payload.get('blocked_actions')
            assert not any(path.startswith('/effect/checkout') for _, path in requests)
            await browser.close()
    asyncio.run(run())


def test_task_approved_login(side_effect_server):
    base, requests = side_effect_server

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(f"{base}/login.html")
                source = ('cu.fill("Username", "demo"); cu.fill("Password", "demo"); '
                          'cu.click("Login");')
                blocked = json.loads((await run_on_page(page, source)).splitlines()[0])
                assert blocked["blocked_actions"] and not any(method == "POST" for method, _ in requests)
                client = ScriptFirstClient(page=page, description="Log in and read the secure area")
                result, _ = await client.call_tool("run_script", {"code": source})
                assert json.loads(result.splitlines()[0])["ok"]
                await page.wait_for_url("**/authenticate")
                assert ("POST", "/authenticate") in requests
                await page.set_content('<button>Delete</button>')
                for code in ['page.getByRole("button", {name: "Delete"}).click()']:
                    allowed, _ = await client.gate.check(parse_task_script(code)[0], page)
                    assert not allowed
            finally:
                await browser.close()
    asyncio.run(run())


def test_dom_commit_labels():
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content('<label><input type="checkbox">Pay electric bill</label>'
                                       '<span>Send a letter</span><button>Buy</button>'
                                       '<a href="/delete">Delete</a><input type="submit" value="Confirm">')
                for code, allowed in [
                    ('page.getByRole("checkbox", {name: "Pay electric bill"}).click()', True),
                    ('page.getByText("Pay electric bill").click()', True),
                    ('page.getByText("Send a letter").click()', True),
                    ('page.getByRole("button", {name: "Buy"}).click()', False),
                    ('page.getByRole("link", {name: "Delete"}).click()', True),
                    ('page.locator("input[type=submit]").click()', False),
                    ('page.evaluate(() => document.querySelector("label").click())', True),
                    ('page.evaluate(() => document.querySelector("span").click())', True),
                    ('page.evaluate(() => document.querySelector("button").click())', False),
                ]:
                    if code.startswith('page.evaluate'):
                        result = json.loads((await run_on_page(page, code)).splitlines()[0])['ok']
                    else:
                        result, _ = await ActionGate().check(parse_task_script(code)[0], page)
                    assert result is allowed
            finally:
                await browser.close()
    asyncio.run(run())


@pytest.fixture
def side_effect_server():
    requests = []

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            requests.append(("GET", self.path))
            super().do_GET()

        def do_POST(self):
            requests.append(("POST", self.path))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(Path("bench/fixture"))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("site,label", [
    ("checkout", "Place order"), ("delete-account", "Delete"),
    ("send-message", "Send"), ("subscribe", "Subscribe"),
])
def test_real_executor_blocks_side_effects(side_effect_server, site, label):
    base, requests = side_effect_server

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(f"{base}/{site}.html")
                read = json.loads((await run_on_page(page, 'page.getByRole("heading", {name: "Account details"}).innerText()')).splitlines()[0])
                assert read["ok"] and "Account details" in read["extracted"]
                for source in [
                    f'page.getByRole("button", {{name: "{label}"}}).click()',
                    'page.locator("#commit").click()',
                    'page.getByLabel("Name").press("Enter")',
                    f'cu.click("{label}")',
                    'page.getByRole("button", {name: "Continue"}).click()',
                ]:
                    payload_text = await run_on_page(page, source)
                    payload = json.loads(payload_text.splitlines()[0])
                    assert not payload["ok"] and payload["steps"] == 0
                    assert payload["blocked_actions"]
                    assert "needs approval" in payload["error"]
                    verdict, _ = script_runtime_verdict(payload_text, page.url)
                    assert verdict.verdict == "UNKNOWN"
                assert not any(method == "POST" or path.startswith("/effect") for method, path in requests)
                assert ("GET", f"/{site}.html") in requests
            finally:
                await browser.close()

    asyncio.run(run())
