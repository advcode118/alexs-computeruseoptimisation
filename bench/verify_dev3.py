"""Opt-in public-page verification for dev3, not an agent run or an LLM probe.

Run ``python -m bench.verify_dev3``. It drives local headless Chromium from
each task's start page to its end state with a short Playwright script, then
grades the page with the probe's own grader (grade_observation and
evidence_verdict). Each task also has negative checks: the right answer on the
start page, and a wrong value on the end page, must both fail. No model calls.
"""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from bench.probe import grade_observation
from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split

# Links followed from the start page, in order. Each entry is a CSS selector.
ROUTES = {
    "dev3_nav_ffmpeg_ffprobe": ['a[href$="ffprobe.html"]'],
    "dev3_nav_mit_hamlet": ['a[href*="hamlet/index.html"]', 'a[href*="full.html"]'],
    "dev3_nav_fish_tutorial": ['a[href*="tutorial.html"]'],
    "dev3_nav_godot_gdscript": ['a[href*="scripting/index.html"]', 'a[href*="gdscript/index.html"]', 'a[href*="gdscript_basics.html"]'],
    "dev3_nav_mysql_json": ['a[href*="data-types.html"]', 'a[href$="json.html"]'],
    "dev3_nav_commonmark_030": ['a[href^="https://spec.commonmark.org"]', 'a[href*="0.30/"]'],
    "dev3_nav_freedesktop_desktop_entry": ['a[href*="desktop-entry"]'],
    "dev3_nav_erlang_getting_started": ['a[href*="getting_started.html"]'],
    "dev3_nav_mslearn_keywords": ['a[href*="language-reference/keywords"]'],
    "dev3_nav_express_middleware": ['a[href*="using-middleware"]'],
    "dev3_value_commonmark_028": ['a[href^="https://spec.commonmark.org"]'],
    "dev3_value_ffmpeg_codename": ['a[href*="olddownload.html"]'],
    "dev3_value_mysql_mediumint": ['a[href*="data-types.html"]', 'a[href*="storage-requirements.html"]'],
    "dev3_value_exif_gpsaltref": ['a[href="GPS.html"]'],
    "dev3_value_crummy_bs3": ['a[href="software/"]', 'a[href="/software/BeautifulSoup/"]'],
    "dev3_value_fileformat_snowman": ['a[href*="block/index.htm"]', 'a[href*="miscellaneous_symbols/index.htm"]', 'a[href$="list.htm"]', 'a[href*="char/2603/index.htm"]'],
    "dev3_value_eso_vlt_at": ['a[href*="paranal-observatory/vlt/"]'],
    "dev3_value_khronos_gl46": ['a[href$="/opengl/"]'],
    "dev3_value_mslearn_decimal": ['a[href*="builtin-types/built-in-types"]', 'a[href*="floating-point-numeric-types"]'],
    "dev3_title_adaic_protected": ['a[href*="RM-9-4.html"]'],
    "dev3_title_mit_romeo": ['a[href*="romeo_juliet/index.html"]', 'a[href*="romeo_juliet.2.2.html"]'],
    "dev3_title_die_nl": ['a[href$="/man/1/"], a[href="1/"]', 'a[href="nl"]'],
    "dev3_title_babel_typescript": ['a[href*="babel-preset-typescript"]'],
}

# A plausible wrong value. Claimed on the end page, it must grade FAIL.
WRONG = {
    "dev3_value_commonmark_028": "2016-11-18",
    "dev3_value_ffmpeg_codename": "Riemann",
    "dev3_value_mysql_mediumint": "4 bytes",
    "dev3_value_colorhexa_websafe": "#ff9966",
    "dev3_value_fileformat_snowman": "0xE2 0x98 0x84",
    "dev3_value_exif_gpsaltref": "0x0006",
    "dev3_value_crummy_bs3": "3.2.1",
    "dev3_value_eso_vlt_at": "8.2m",
    "dev3_value_khronos_gl46": "July 31, 2018",
    "dev3_value_mslearn_decimal": "~15-17 digits",
    "dev3_form_demoqa_textbox": "Name:Alex Sample",
    "dev3_form_demoqa_practice": "Thanks for registering",
    "dev3_form_formy_complete": "The form was not submitted",
    "dev3_form_blazedemo_purchase": "Thank you for your booking",
    "dev3_form_aito_contact": "Thanks for getting in touch Alex Sample!",
    "dev3_form_guru99_register": "Registration failed",
    "dev3_title_adaic_protected": "9.5 Intertask Communication",
    "dev3_title_mit_romeo": "SCENE I. A lane by the wall of Capulet's orchard.",
    "dev3_title_die_nl": "nl - number pages of files",
    "dev3_title_babel_typescript": "@babel/preset-flow",
    "dev3_spa_devdocs_flat": "Array.prototype.flatMap()",
    "dev3_spa_elm_repeat": "repeat : a -> Int -> List a",
    "dev3_spa_letcode_total": "848",
    "dev3_spa_demoqa_origin": "Harvard College",
}

# Pages whose answer only appears once JavaScript has run.
JS_ONLY = ("dev3_spa_devdocs_flat", "dev3_spa_elm_repeat", "dev3_spa_letcode_total")


async def _real_page(page, response=None) -> int | None:
    status = response.status if response is not None else None
    if response is not None:
        assert status == 200, (page.url, status)
    body = await page.locator("body").inner_text()
    title = (await page.title()).casefold()
    assert len(body.strip()) > 50, (page.url, "empty/error page")
    assert not any(token in title for token in ("just a moment", "attention required", "access denied", "oh noes")), page.url
    assert not any(token in body.casefold() for token in (
        "verify you are human", "checking your browser before accessing",
        "performing security verification", "enable javascript and cookies to continue",
    )), page.url
    assert await page.locator("#challenge-running, #challenge-stage, iframe[src*='challenges.cloudflare.com']").count() == 0, page.url
    return status


async def _follow(page, selector: str) -> None:
    """Click the first visible matching link. A link inside a closed menu is followed by its href."""
    links = page.locator(selector)
    await links.first.wait_for(state="attached")
    count = await links.count()
    for index in range(count):
        link = links.nth(index)
        if await link.is_visible():
            before = page.url
            try:
                await link.click(timeout=10000)
                await page.wait_for_load_state("domcontentloaded")
                if page.url == before:
                    await page.wait_for_url(lambda url: url != before, timeout=15000)
                return
            except Exception:  # noqa: BLE001 - an overlay or a slow handler; follow the href instead
                if page.url != before:
                    return
            break
    href = await links.first.get_attribute("href")
    await page.goto(urljoin(page.url, href), wait_until="domcontentloaded")


async def _search(page, box: str, query: str, result: str) -> None:
    field = page.locator(box).first
    await field.fill(query)
    await field.press("Enter")
    await page.locator(result).first.wait_for()
    await _follow(page, result)


async def _interact(page, task: dict) -> None:
    task_id = task["id"]
    if task_id in ROUTES:
        for selector in ROUTES[task_id]:
            await _follow(page, selector)
        return
    if task_id == "dev3_value_colorhexa_websafe":
        field = page.locator('input[type="text"], input[type="search"]').first
        await field.fill("ff7f50")
        await field.press("Enter")
        await page.wait_for_url("**/ff7f50")
        return
    if task_id == "dev3_search_metacpan_moose":
        await _search(page, "#metacpan_search-input", "Moose", 'a[href="/pod/Moose"]')
        return
    if task_id == "dev3_search_hex_plug":
        await _search(page, "#nav-search-input:visible, input[name='search']:visible", "plug", 'a[href="/packages/plug"]')
        return
    if task_id == "dev3_search_archlinux_nginx":
        await _search(page, "#id_q", "nginx", 'a[href="/packages/extra/x86_64/nginx/"]')
        return
    if task_id == "dev3_search_godot_signals":
        await _search(page, 'input[name="q"]:visible', "signals", 'a[href$="step_by_step/signals.html"]:visible')
        return
    if task_id == "dev3_search_fileformat_heart":
        # A consent overlay can swallow Enter; submit the site's own search form instead.
        await page.locator('form[action="search.htm"] input[name="q"]').fill("black heart suit")
        async with page.expect_navigation():
            await page.locator('form[action="search.htm"]').evaluate("form => form.requestSubmit()")
        await _follow(page, 'a[href*="2665/index.htm"]')
        return
    if task_id == "dev3_search_erlang_lists":
        await _search(page, "input.search-input", "lists", 'a[href$="stdlib/lists.html"]')
        return
    if task_id == "dev3_form_demoqa_textbox":
        await page.fill("#userName", "Alex Example")
        await page.fill("#userEmail", "alex@example.com")
        await page.click("#submit")
        await page.locator("#output #name").wait_for()
        return
    if task_id == "dev3_form_demoqa_practice":
        await page.fill("#firstName", "Alex")
        await page.fill("#lastName", "Example")
        await page.locator('label[for="gender-radio-3"]').click()
        await page.fill("#userNumber", "0123456789")
        await page.locator("#submit").evaluate("button => button.click()")
        await page.locator(".modal-title").wait_for()
        return
    if task_id == "dev3_form_formy_complete":
        await page.fill("#first-name", "Alex")
        await page.fill("#last-name", "Example")
        await page.fill("#job-title", "Tester")
        await page.click("a.btn.btn-lg.btn-primary")
        await page.wait_for_url("**/thanks")
        await page.get_by_text("successfully submitted").wait_for()
        return
    if task_id == "dev3_form_blazedemo_purchase":
        await page.select_option('select[name="fromPort"]', "Boston")
        await page.select_option('select[name="toPort"]', "London")
        await page.click('input[type="submit"]')
        await page.wait_for_url("**/reserve.php")
        await page.locator('input[type="submit"]').first.click()
        await page.wait_for_url("**/purchase.php")
        await page.fill("#inputName", "Alex Example")
        await page.click('input[type="submit"]')
        await page.wait_for_url("**/confirmation.php")
        return
    if task_id == "dev3_form_aito_contact":
        await page.fill("#name", "Alex Example")
        await page.fill("#email", "alex@example.com")
        await page.fill("#phone", "01234567890")
        await page.fill("#subject", "Booking enquiry")
        await page.fill("#description", "I would like to ask about booking a double room next spring.")
        await page.get_by_role("button", name="Submit").click()
        await page.get_by_text("Thanks for getting in touch").wait_for()
        return
    if task_id == "dev3_form_guru99_register":
        await page.fill('input[name="firstName"]', "Alex")
        await page.fill('input[name="lastName"]', "Example")
        await page.fill('input[name="email"]', "alexexample")
        await page.fill('input[name="password"]', "Demo1234")
        await page.fill('input[name="confirmPassword"]', "Demo1234")
        async with page.expect_navigation():
            await page.locator('input[name="submit"]').click()
        return
    if task_id == "dev3_spa_devdocs_flat":
        await _search(page, 'input[name="q"]', "array.flat", 'a[href="/javascript/global_objects/array/flat"]')
        await page.get_by_text("Array.prototype.flat()").first.wait_for()
        return
    if task_id == "dev3_spa_elm_repeat":
        await _follow(page, 'a[href="/packages/elm/core/latest/"], a[href*="/packages/elm/core/"]')
        await _follow(page, 'a[href*="/packages/elm/core/1.0.5"]')
        await _follow(page, 'a[href="/packages/elm/core/1.0.5/List"]')
        await page.get_by_text("repeat : Int").wait_for()
        return
    if task_id == "dev3_spa_letcode_total":
        await _follow(page, 'a[href="/table"]')
        await page.get_by_text("858", exact=True).wait_for()
        return
    if task_id == "dev3_spa_demoqa_origin":
        await page.get_by_role("tab", name="Origin").click()
        await page.get_by_text("Hampden-Sydney College").wait_for()
        return
    raise AssertionError(f"no reproducer for {task_id}")


def _grade(task: dict, evidence, answer: str) -> bool:
    ok, _reason, _shared, _ = grade_observation(task, evidence.url, evidence.text, answer=answer)
    verdict = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=answer))
    return ok and verdict.verdict == "PASS"


async def _js_only(browser, task: dict, url: str) -> str:
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
        await page.wait_for_timeout(2500)
        start_status = await _real_page(page, start)
        start_evidence = await collect_page_evidence(page)
        answer = task["expected_answer"]
        assert not _grade(task, start_evidence, answer), (task["id"], "start page passed")
        await _interact(page, task)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1000)
        await _real_page(page)
        evidence = await collect_page_evidence(page)
        markers = task["end_markers"]
        if markers.get("answer_in_text"):
            assert answer in evidence.text, (task["id"], "answer absent from runner evidence", evidence.text[:300])
        assert _grade(task, evidence, answer), (task["id"], "grader rejected the end state", evidence.url)
        wrong = WRONG.get(task["id"])
        if wrong is not None:
            assert not _grade(task, evidence, wrong), (task["id"], "wrong value accepted", wrong)
        extra = await _js_only(browser, task, evidence.url) if task["id"] in JS_ONLY else ""
        return task["id"], start_status, evidence.url, "PASS", "FAIL", "FAIL" if wrong else "-", extra
    finally:
        await context.close()


async def verify(ids: list[str]) -> int:
    tasks = [task for task in tasks_for_split("dev3") if not ids or task["id"] in ids]
    failures = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(5)

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
