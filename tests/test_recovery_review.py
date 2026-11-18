import asyncio
import json

import pytest
from playwright.async_api import async_playwright

from bench.recovery import ActionGate, classify_task
from bench.script_first import run_on_page
from bench.harness import self_check_record
from bench.recovery import evaluate_checkpoints, plan_checkpoints
from types import SimpleNamespace


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


@pytest.mark.parametrize('description,approval', [
    ('Find her article and confirm you are on her article page', False),
    ('Confirm that the title is correct', False),
    ('Confirm order', True), ('Confirm payment', True), ('Confirm purchase', True),
])
def test_verification_is_not_commit_intent(description, approval):
    assert classify_task(description, {}).needs_approval is approval


@pytest.mark.parametrize('key', ['Tab', 'Escape', 'ArrowDown', 'Enter', 'Space'])
def test_unfocused_global_keyboard(key):
    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content('<input aria-label="Query">')
            payload = json.loads((await run_on_page(page, f'page.keyboard.press("{key}")')).splitlines()[0])
            assert payload['ok'], payload.get('error')
            if key == 'Tab':
                assert await page.get_by_label('Query').evaluate('el => el === document.activeElement')
            await browser.close()
    asyncio.run(run())


def test_filled_checkpoint_survives_self_check_record():
    payload = {'url': 'https://example.org/', 'controls': [{'role': 'textbox', 'name': 'Query', 'value': 'Guide'}]}
    record = self_check_record(payload, payload['url'], payload['url'], SimpleNamespace(verdict='PASS', reason=''))
    checkpoints = plan_checkpoints('Fill "Guide"', classify_task('Fill "Guide"', {}))
    assert all(result['passed'] for result in evaluate_checkpoints(checkpoints, record['payload']))
    assert 'controls' not in record['payload']


@pytest.mark.parametrize('description,password,focused,allowed', [
    ('Read the page', True, True, False),
    ('Log in and read', True, True, True),
    ('Read the page', False, True, True),
    ('Read the page', True, False, True),
])
def test_keyboard_typing_respects_password_approval(description, password, focused, allowed):
    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(f'<input type="{"password" if password else "text"}" aria-label="Field">')
            field = page.get_by_label('Field')
            if focused:
                await field.focus()
            gate = ActionGate(description=description)
            payload = json.loads((await run_on_page(page, 'page.keyboard.type("demo")', gate=gate)).splitlines()[0])
            assert payload['ok'] is allowed
            assert bool(payload.get('blocked_actions')) is not allowed
            assert await field.input_value() == ('demo' if allowed and focused else '')
            await browser.close()
    asyncio.run(run())
