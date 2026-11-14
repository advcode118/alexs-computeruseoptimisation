"""Opt-in public-page verification for dev4spa, not an agent run or an LLM probe.

Run ``python -m bench.verify_dev4_spa``. It drives local headless Chromium from
each task's start page to its end state with a short Playwright script, then
grades the page with the probe's own grader (grade_observation and
evidence_verdict). Negative checks: the right answer claimed on the start page
must fail (or, for a page whose answer only needs rendering, the same URL with
JavaScript off must not show it), and a wrong value on the end page must fail.
No model calls.
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

from bench.probe import grade_observation
from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split

# The answer is there once the app renders; no click needed. Checked with JavaScript off instead.
RENDER_ONLY = ("dev4spa_spa_artifacthub_nginx_app", "dev4spa_spa_bundlephobia_reactdom")

# A plausible wrong value. Claimed on the end page, it must grade FAIL.
WRONG = {
    "dev4spa_spa_deps_react_dependency": "js-tokens",
    "dev4spa_spa_deps_requests_urllib3": "<4,>=2.5",
    "dev4spa_js_cypress_todo_left": "2 items left",
    "dev4spa_js_knockout_clicks": "You've clicked 2 times",
    "dev4spa_js_htmx_toyota_models": "Tacoma",
    "dev4spa_js_htmx_tab_two": "Commodo normcore truffaut",
    "dev4spa_spa_docsify_serve": "http://localhost:8080",
    "dev4spa_spa_naiveui_beatles": "Wonderwall",
    "dev4spa_js_jqueryui_section_three": "List item two",
    "dev4spa_spa_artifacthub_nginx_app": "1.24.0",
    "dev4spa_spa_bundlephobia_reactdom": "129.8",
    "dev4spa_js_shoelace_advanced": "This is the general tab panel",
}


async def _real_page(page, response=None) -> None:
    if response is not None:
        assert response.status in (200, 404) or response.status < 400, (page.url, response.status)
    body = await page.locator("body").inner_text()
    title = (await page.title()).casefold()
    assert len(body.strip()) > 50, (page.url, "empty/error page")
    assert not any(token in title for token in ("just a moment", "attention required", "access denied")), page.url
    assert not any(token in body.casefold() for token in (
        "verify you are human", "checking your browser before accessing", "performing security verification",
    )), page.url


async def _interact(page, task: dict) -> None:
    task_id = task["id"]
    answer = task["expected_answer"]
    if task_id == "dev4spa_spa_deps_react_dependency":
        await page.get_by_role("link", name="Dependencies", exact=True).first.click()
        await page.wait_for_url("**/dependencies")
    elif task_id == "dev4spa_spa_deps_requests_urllib3":
        await page.get_by_role("link", name="Requirements", exact=True).first.click()
        await page.wait_for_url("**/requirements")
    elif task_id == "dev4spa_js_cypress_todo_left":
        await page.locator("li", has_text="Pay electric bill").locator("input.toggle").check()
    elif task_id == "dev4spa_js_knockout_clicks":
        button = page.get_by_role("button", name="Click me")
        while await button.is_enabled():
            await button.click()
    elif task_id == "dev4spa_js_htmx_toyota_models":
        await page.locator('select[name="make"]').select_option("toyota")
    elif task_id == "dev4spa_js_htmx_tab_two":
        await page.locator("#tabs").get_by_role("tab", name="Tab 2").click()
    elif task_id == "dev4spa_spa_docsify_serve":
        await page.get_by_role("link", name="Quick start", exact=True).first.click()
        await page.wait_for_url("**#/quickstart")
    elif task_id == "dev4spa_spa_naiveui_beatles":
        await page.get_by_text("the Beatles", exact=True).first.click()
    elif task_id == "dev4spa_js_jqueryui_section_three":
        await page.get_by_text("Section 3", exact=True).click()
    elif task_id in RENDER_ONLY:
        pass
    elif task_id == "dev4spa_js_shoelace_advanced":
        await page.keyboard.press("Escape")
        await page.get_by_role("tab", name="Advanced").first.click()
    else:
        raise AssertionError(f"no reproducer for {task_id}")
    await page.get_by_text(answer, exact=False).first.wait_for(timeout=20000)


def _grade(task: dict, evidence, answer: str) -> bool:
    ok, _reason, _shared, _ = grade_observation(task, evidence.url, evidence.text, answer=answer)
    verdict = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=answer))
    return ok and verdict.verdict == "PASS"


async def _js_off(browser, task: dict, url: str) -> str:
    context = await browser.new_context(java_script_enabled=False)
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        evidence = await collect_page_evidence(page)
        assert task["expected_answer"] not in evidence.text, (task["id"], "answer present without JavaScript")
        assert not _grade(task, evidence, task["expected_answer"]), task["id"]
        return "JS-only"
    finally:
        await context.close()


async def check(browser, task: dict) -> tuple:
    context = await browser.new_context(viewport={"width": 1366, "height": 900})
    page = await context.new_page()
    page.set_default_timeout(45000)
    try:
        start = await page.goto(task["start_url"], wait_until="domcontentloaded")
        answer = task["expected_answer"]
        if task["id"] not in RENDER_ONLY:
            await page.wait_for_timeout(2500)
            await _real_page(page, start)
            start_evidence = await collect_page_evidence(page)
            assert not _grade(task, start_evidence, answer), (task["id"], "start page passed")
        await _interact(page, task)
        await page.wait_for_timeout(800)
        await _real_page(page)
        evidence = await collect_page_evidence(page)
        assert answer in evidence.text, (task["id"], "answer absent from runner evidence", evidence.text[:300])
        assert _grade(task, evidence, answer), (task["id"], "grader rejected the end state", evidence.url)
        assert not _grade(task, evidence, WRONG[task["id"]]), (task["id"], "wrong value accepted")
        extra = await _js_off(browser, task, evidence.url) if task["id"] in RENDER_ONLY else "start FAIL"
        return task["id"], evidence.url, "PASS", "wrong FAIL", extra
    finally:
        await context.close()


async def verify(ids: list[str]) -> int:
    tasks = [task for task in tasks_for_split("dev4spa") if not ids or task["id"] in ids]
    failures = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(4)

        async def guarded(task):
            nonlocal failures
            async with semaphore:
                try:
                    row = await check(browser, task)
                    print("OK  " + " | ".join(str(item) for item in row), flush=True)
                except Exception as error:  # noqa: BLE001 - report and continue
                    failures += 1
                    print(f"BAD {task['id']}: {type(error).__name__}: {str(error)[:300]}", flush=True)

        try:
            await asyncio.gather(*(guarded(task) for task in tasks))
        finally:
            await browser.close()
    print(f"TOTAL {len(tasks) - failures}/{len(tasks)} passed", flush=True)
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(verify(sys.argv[1:])) else 0)
