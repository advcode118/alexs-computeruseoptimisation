import asyncio
import json

import pytest
from playwright.async_api import async_playwright

from bench.recovery import ActionGate
from bench.script_first import run_on_page


@pytest.mark.parametrize('script', [
    'page.getByRole("button", {name: "Continue"}).click()',
    'page.evaluate(() => document.forms[0].requestSubmit())',
])
def test_login_approval_is_form_scoped(script):
    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            requests = []
            async def route(route):
                requests.append(route.request.url)
                await route.fulfill(content_type='text/html', body='<form method="post" action="/effect/checkout"><button>Continue</button></form>')
            await page.route('**/*', route)
            await page.goto('https://example.org/login')
            gate = ActionGate(description='Log in and read')
            payload = json.loads((await run_on_page(page, script, gate=gate)).splitlines()[0])
            assert payload.get('blocked_actions')
            assert requests == ['https://example.org/login']
            await browser.close()
    asyncio.run(run())


@pytest.mark.parametrize('script', ['page.getByLabel("Query").press("Enter")', 'page.keyboard.press("Enter")'])
def test_implicit_submit_checks_default_button(script):
    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content('<form><input aria-label="Query"><button onclick="window.effect=true">Buy</button></form>')
            await page.get_by_label('Query').focus()
            payload = json.loads((await run_on_page(page, script)).splitlines()[0])
            assert payload.get('blocked_actions')
            assert not await page.evaluate('window.effect')
            await browser.close()
    asyncio.run(run())
