import asyncio

import pytest

from bench.browser_use_arm import _attach_target
from bench.cascade import _page_target_id
from bench.script_first import ScriptFirstClient


def test_warm_handoff_preserves_target_and_page_state():
    browser_use = pytest.importorskip("browser_use")

    async def run():
        client = ScriptFirstClient(headless=True, remote_debugging=True)
        browser = None
        try:
            await client.start()
            await client._page.goto("data:text/html,<title>Handoff</title><input id='value'>")
            await client._page.locator("#value").fill("preserved state")
            target = await _page_target_id(client._page)
            browser = browser_use.Browser(cdp_url=client.cdp_url, keep_alive=True)
            await browser.start()
            initial = await asyncio.to_thread(_attach_target, browser, target)
            assert initial["targetId"] == target
            assert initial["url"] == client._page.url
            assert browser._local is None
            await browser.start()
            from browser_use.browser.browser import _daemon_cdp, _daemon_request

            current = await asyncio.to_thread(_daemon_request, browser.name, {"meta": "current_tab"}, 5)
            assert current["targetId"] == target
            value = await asyncio.to_thread(
                _daemon_cdp, browser.name, "Runtime.evaluate",
                expression="document.querySelector('#value').value", returnByValue=True,
            )
            assert value["result"]["value"] == "preserved state"
        finally:
            if browser is not None:
                await browser.stop()
            await client.stop()

    asyncio.run(run())


def test_attach_wrong_target_is_refused(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr("bench.browser_use_arm._daemon_cdp_fn", lambda: lambda *a, **k: {"sessionId": "s"})
    monkeypatch.setattr("bench.browser_use_arm._daemon_request_fn", lambda: lambda *a, **k: {"targetId": "wrong"})
    browser = SimpleNamespace(name="mock", remember_tab=lambda: None)
    with pytest.raises(RuntimeError, match="handoff target"):
        _attach_target(browser, "expected")
