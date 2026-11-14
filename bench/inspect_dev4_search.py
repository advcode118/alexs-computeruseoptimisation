"""Author-only DOM diagnostics for the new task verifier (no model)."""
import asyncio
import json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for url in ("https://pydantic.dev/docs/validation/latest/get-started/", "https://fastapi.tiangolo.com/"):
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                await page.get_by_role("button", name="Search", exact=True).first.click()
                await page.wait_for_timeout(1000)
                print(json.dumps(await page.locator('input').evaluate_all("es => es.map(e=>({html:e.outerHTML,visible:!!e.getClientRects().length}))")), flush=True)
                await page.locator('input:visible').first.fill("validators" if "pydantic" in url else "background tasks")
                await page.wait_for_timeout(3000)
                data = await page.evaluate("""() => ({url:location.href, controls:[...document.querySelectorAll('input,button,label,[role=button]')].filter(e => /search/i.test([e.outerHTML, e.innerText].join(' '))).map(e=>({html:e.outerHTML.slice(0,700),visible:!!e.getClientRects().length})).slice(0,18), links:[...document.links].filter(a=>/validat|serializ/i.test(a.innerText)).map(a=>({text:a.innerText,href:a.href})).slice(0,20)})""")
                print(json.dumps(data), flush=True)
                await page.close()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
