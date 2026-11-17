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
from bench.script_first import TaskStep, parse_task_script, run_on_page, script_runtime_verdict


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
    evidence = {"url": "https://example.org/", "text": "Guide", "controls": [{"role": "textbox"}]}
    assert all(item["passed"] for item in evaluate_checkpoints(planned, evidence))
    assert not any(item["passed"] for item in evaluate_checkpoints(planned, {"blocked_actions": [{}]}))
    assert evaluate_checkpoints([], {}) == []
    with pytest.raises(ValueError, match="unknown checkpoint"):
        evaluate_checkpoints([{"kind": "bad", "value": ""}], {})


@pytest.mark.parametrize("source,url,allowed", [
    ('page.getByRole("button", {name: "Buy"}).click()', "https://example.org/", False),
    ('page.getByRole("link", {name: "Remove account"}).click()', "https://example.org/", False),
    ('page.getByRole("button", {name: "Search"}).click()', "https://example.org/", True),
    ('page.goto("https://example.org/payment")', "https://example.org/", False),
    ('page.getByLabel("Name").fill("A")', "https://example.org/login", False),
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
                    await page.set_content(f'<form method="{method}"><input name="q"><button>Search</button></form>')
                    for function in ['() => document.querySelector("form").requestSubmit()',
                                     '() => document.querySelector("button").click()']:
                        step = TaskStep("evaluate", 1, function, function=function)
                        result, _ = await ActionGate().check(step, page)
                        assert result is allowed
                await page.set_content('<button id="commit">Buy</button>')
                function = '() => document.querySelector("#commit").click()'
                result, _ = await ActionGate().check(TaskStep("evaluate", 1, function, function=function), page)
                assert not result
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
