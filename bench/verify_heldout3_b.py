"""Opt-in public-page verification, not an agent run or an LLM probe.

Run ``python -m bench.verify_heldout3_b`` to refresh docs/HELDOUT3B_VERIFY.md.
Only local headless Chromium and the deterministic evidence grader are used.
Every task is driven by clicks, typing and form submits from its start page.
Each task also has negative controls that must grade FAIL.
"""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split

# A value that is on the finished page but is not the requested one.
WRONG_VALUES = {
    "ho3b_value_nssdc_mars_mass": "0.330",
    "ho3b_value_jpl_neptune_radius": "24764",
    "ho3b_value_oracle_char_default": "0L",
    "ho3b_value_numpy_interval_num": "endpoint=True",
    "ho3b_value_php_pad_default": "STR_PAD_LEFT",
    "ho3b_value_rubygems_rails_ruby": ">= 1.8.11",
    "ho3b_value_oeis_catalan_formerly": "M1459",
    "ho3b_value_spdx_zero_clause": "AAL",
    "ho3b_form_practice_login": "Congratulations student",
    "ho3b_form_wdu_contact": "Back to Homepage",
    "ho3b_form_saucedemo_jacket": "$29.99",
    "ho3b_form_scrapethissite_hockey": "181",
    "ho3b_spa_quotes_simile": "Albert Einstein",
    "ho3b_spa_swagger_upload_path": "/pet/{petId}",
    "ho3b_spa_scrapethissite_oscars": "Mad Max: Fury Road",
    "ho3b_title_xkcd_after_mom": "Random",
    "ho3b_title_books_priciest_poetry": "Poetry",
    "ho3b_title_typescript_after_basics": "The Basics",
}

# Real wrong pages beyond the start page: a step short, a neighbour, or a results page.
DECOYS = {
    "ho3b_nav_xkcd_mom": ["https://xkcd.com/archive/", "https://xkcd.com/328/"],
    "ho3b_nav_wikidata_death_country": ["https://www.wikidata.org/wiki/Q159288", "https://www.wikidata.org/wiki/Q145"],
    "ho3b_nav_books_cheapest_travel": [
        "https://books.toscrape.com/catalogue/category/books/travel_2/index.html",
        "https://books.toscrape.com/catalogue/1000-places-to-see-before-you-die_1/index.html",
    ],
    "ho3b_nav_oracle_lambda": [
        "https://docs.oracle.com/javase/tutorial/java/javaOO/index.html",
        "https://docs.oracle.com/javase/tutorial/java/javaOO/anonymousclasses.html",
    ],
    "ho3b_nav_nssdc_jovian_moons": [
        "https://nssdc.gsfc.nasa.gov/planetary/planetfact.html",
        "https://nssdc.gsfc.nasa.gov/planetary/factsheet/jupiterfact.html",
    ],
    "ho3b_nav_typescript_refining": [
        "https://www.typescriptlang.org/docs/handbook/intro.html",
        "https://www.typescriptlang.org/docs/handbook/2/everyday-types.html",
    ],
    "ho3b_nav_tcl_sort_command": [
        "https://www.tcl-lang.org/man/tcl8.6/TclCmd/contents.htm",
        "https://www.tcl-lang.org/man/tcl8.6/TclCmd/lsearch.htm",
    ],
    "ho3b_nav_osm_bench_tag": [
        "https://wiki.openstreetmap.org/wiki/Key:amenity",
        "https://wiki.openstreetmap.org/wiki/Tag:leisure%3Dpicnic_table",
    ],
    "ho3b_value_nssdc_mars_mass": [
        "https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html",
        "https://nssdc.gsfc.nasa.gov/planetary/factsheet/planet_table_ratio.html",
    ],
    "ho3b_value_jpl_neptune_radius": ["https://ssd.jpl.nasa.gov/sats/phys_par/"],
    "ho3b_value_numpy_interval_num": ["https://numpy.org/doc/stable/reference/generated/numpy.logspace.html"],
    "ho3b_value_php_pad_default": ["https://www.php.net/manual/en/function.str-repeat.php"],
    "ho3b_value_rubygems_rails_ruby": ["https://rubygems.org/gems/rails/versions/7.0.0.rc1"],
    "ho3b_value_oeis_catalan_formerly": ["https://oeis.org/search?q=A000108"],
    "ho3b_search_oeis_triangular": ["https://oeis.org/search?q=1%2C+3%2C+6%2C+10%2C+15%2C+21%2C+28%2C+36", "https://oeis.org/A000290"],
    "ho3b_search_scipy_curve_fit": [
        "https://docs.scipy.org/doc/scipy/search.html?q=curve_fit",
        "https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html",
    ],
    "ho3b_search_wiktionary_rain_scent": [
        "https://en.wiktionary.org/w/index.php?search=scent+of+rain&title=Special%3ASearch&ns0=1",
        "https://en.wiktionary.org/wiki/petricor",
    ],
    "ho3b_search_rubygems_nokogiri": ["https://rubygems.org/search?query=nokogiri", "https://rubygems.org/gems/rails"],
    "ho3b_spa_quotes_simile": ["https://quotes.toscrape.com/js/page/2/", "https://quotes.toscrape.com/"],
    "ho3b_spa_swagger_upload_path": ["https://petstore.swagger.io/v2/swagger.json"],
    "ho3b_spa_scrapethissite_oscars": ["https://www.scrapethissite.com/pages/ajax-javascript/?ajax=true&year=2015"],
    "ho3b_title_xkcd_after_mom": ["https://xkcd.com/327/"],
}

# Other correct end URLs. The finished page's evidence at these URLs must still PASS.
# Every task is also checked with a #fragment on its finished URL.
VARIANTS = {
    "ho3b_nav_xkcd_mom": ["https://m.xkcd.com/327/"],
    "ho3b_nav_wikidata_death_country": ["https://m.wikidata.org/wiki/Q30"],
    "ho3b_nav_books_cheapest_travel": [
        "https://books.toscrape.com/catalogue/the-road-to-little-dribbling-adventures-of-an-american-in-britain-notes-from-a-small-island-2_277/",
    ],
    "ho3b_nav_tcl_sort_command": ["https://tcl-lang.org/man/tcl8.6/TclCmd/lsort.htm"],
    "ho3b_nav_osm_bench_tag": ["https://wiki.openstreetmap.org/wiki/Tag:amenity=bench"],
    "ho3b_value_nssdc_mars_mass": ["https://nssdc.gsfc.nasa.gov/planetary/factsheet/"],
    "ho3b_value_numpy_interval_num": ["https://numpy.org/doc/2.5/reference/generated/numpy.linspace.html"],
    "ho3b_value_php_pad_default": ["https://php.net/manual/en/function.str-pad.php"],
    "ho3b_value_spdx_zero_clause": ["https://spdx.org/licenses/index.html", "https://spdx.org/licenses/0BSD.html"],
    "ho3b_search_scipy_curve_fit": ["https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.optimize.curve_fit.html"],
    "ho3b_spa_quotes_simile": ["https://quotes.toscrape.com/js/page/1/"],
    "ho3b_spa_swagger_upload_path": ["https://petstore.swagger.io/#/pet/uploadFile", "https://petstore.swagger.io/index.html"],
    "ho3b_spa_scrapethissite_oscars": ["https://www.scrapethissite.com/pages/ajax-javascript/"],
    "ho3b_title_xkcd_after_mom": ["https://m.xkcd.com/328/"],
    "ho3b_title_books_priciest_poetry": ["https://books.toscrape.com/catalogue/slow-states-of-collapse-poems_960/"],
}

# The start page is already the finished page here, so only the decoy is a wrong page.
START_IS_FINISHED = {"ho3b_spa_quotes_simile", "ho3b_spa_swagger_upload_path"}

# Text from the answer's row that must be missing when the finished page loads without JavaScript.
SCRIPT_ONLY = {
    "ho3b_spa_quotes_simile": "Steve Martin",
    "ho3b_spa_swagger_upload_path": "/pet/{petId}/uploadImage",
    "ho3b_spa_scrapethissite_oscars": "The Revenant",
    "ho3b_form_saucedemo_jacket": "Sauce Labs Fleece Jacket",
}


async def _real_page(page, response) -> int:
    if response is None:
        # Client-side route change: the document was not reloaded, so fetch the new URL's status.
        response = await page.context.request.get(page.url)
    assert response.status == 200, (page.url, response.status)
    await page.wait_for_function("document.body && document.body.innerText.trim().length > 20", timeout=20000)
    body = await page.locator("body").inner_text()
    title = (await page.title()).casefold()
    assert len(body.strip()) > 20, (page.url, "empty/error page")
    assert not any(token in title for token in ("just a moment", "attention required", "access denied", "recaptcha")), page.url
    assert not any(token in body.casefold() for token in (
        "verify you are human", "checking your browser before accessing",
        "performing security verification", "enable javascript and cookies to continue", "too many requests",
    )), page.url
    assert await page.locator("#challenge-running, #challenge-stage, iframe[src*='challenges.cloudflare.com']").count() == 0, page.url
    return response.status


async def _follow(page, locator):
    """Click a link and wait for the page it opens.

    A hidden menu link, or one an overlay keeps from taking the click, is followed by its href.
    """
    link = locator.first
    await link.wait_for(state="attached")
    response = None
    clicked = False
    if await link.is_visible():
        before = page.url
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=20000) as navigation:
                await link.click(timeout=10000)
            response = await navigation.value
            clicked = page.url != before
        except PlaywrightTimeoutError:
            clicked = False
    if not clicked:
        href = await link.get_attribute("href")
        response = await page.goto(urljoin(page.url, href), wait_until="domcontentloaded")
    await _real_page(page, response)
    return response


async def _submit(page, action):
    async with page.expect_navigation(wait_until="domcontentloaded") as navigation:
        await action()
    response = await navigation.value
    await _real_page(page, response)
    return response


def _link(page, name: str):
    return page.get_by_role("link", name=name, exact=True)


async def _click_book_by_price(page, category: str, pick) -> None:
    await _follow(page, _link(page, category))
    pods = page.locator("article.product_pod")
    prices = [float((await pods.nth(i).locator(".price_color").inner_text()).strip("£")) for i in range(await pods.count())]
    target = prices.index(pick(prices))
    assert prices.count(prices[target]) == 1, (category, "tied price")
    await _follow(page, pods.nth(target).locator("h3 a"))


async def _search(page, box, query: str, result) -> None:
    await box.first.fill(query)
    await _submit(page, lambda: box.first.press("Enter"))
    if result is not None:
        await _follow(page, result)


async def _interact(page, task: dict) -> None:
    task_id = task["id"]
    if task_id == "ho3b_nav_xkcd_mom":
        await _follow(page, _link(page, "Archive"))
        await _follow(page, _link(page, "Exploits of a Mom"))
    elif task_id == "ho3b_title_xkcd_after_mom":
        await _follow(page, _link(page, "Exploits of a Mom"))
        await _follow(page, page.locator("a[rel='next']"))
    elif task_id == "ho3b_nav_wikidata_death_country":
        await _follow(page, page.locator("#P20 .wikibase-snakview-value a"))
        await _follow(page, page.locator("#P17 .wikibase-snakview-value a"))
    elif task_id == "ho3b_nav_books_cheapest_travel":
        await _click_book_by_price(page, "Travel", min)
    elif task_id == "ho3b_title_books_priciest_poetry":
        await _click_book_by_price(page, "Poetry", max)
    elif task_id == "ho3b_nav_oracle_lambda":
        await _follow(page, _link(page, "Learning the Java Language"))
        await _follow(page, page.locator("a", has_text="Classes and Objects"))
        await _follow(page, _link(page, "Lambda Expressions"))
    elif task_id == "ho3b_value_oracle_char_default":
        await _follow(page, _link(page, "Primitive Data Types"))
    elif task_id == "ho3b_nav_nssdc_jovian_moons":
        await _follow(page, page.locator("a[href$='/planetary/planetfact.html']"))
        await _follow(page, page.get_by_role("link", name="Jovian System Image"))
    elif task_id == "ho3b_value_nssdc_mars_mass":
        await _follow(page, page.locator("a", has_text="Table of Planetary Facts - Metric Units"))
    elif task_id == "ho3b_nav_typescript_refining":
        await _follow(page, _link(page, "Handbook"))
        await _follow(page, _link(page, "Narrowing"))
    elif task_id == "ho3b_title_typescript_after_basics":
        await _follow(page, _link(page, "Everyday Types"))
    elif task_id == "ho3b_nav_tcl_sort_command":
        await _follow(page, _link(page, "Tcl Commands"))
        await _follow(page, _link(page, "lsort"))
    elif task_id == "ho3b_nav_osm_bench_tag":
        await _follow(page, _link(page, "amenity"))
        await _follow(page, _link(page, "bench"))
    elif task_id == "ho3b_value_jpl_neptune_radius":
        await _follow(page, page.locator("a[href$='/planets/phys_par.html']"))
    elif task_id == "ho3b_value_numpy_interval_num":
        await _follow(page, _link(page, "numpy.linspace"))
    elif task_id == "ho3b_value_php_pad_default":
        await _follow(page, _link(page, "str_pad"))
    elif task_id == "ho3b_value_rubygems_rails_ruby":
        await _follow(page, page.get_by_role("link", name=re.compile(r"Show all versions", re.I)))
        await _follow(page, page.locator("a[href='/gems/rails/versions/7.0.0']"))
    elif task_id == "ho3b_value_oeis_catalan_formerly":
        box = page.locator("input[name='q']")
        await _search(page, box, "A000108", None)
        if not page.url.rstrip("/").endswith("/A000108"):
            await _follow(page, page.locator("a[href='/A000108']"))
    elif task_id == "ho3b_value_spdx_zero_clause":
        await _follow(page, page.locator("a[href='https://spdx.org/licenses/']:visible"))
    elif task_id == "ho3b_search_oeis_triangular":
        await _search(page, page.locator("input[name='q']"), "1, 3, 6, 10, 15, 21, 28, 36", page.locator("a[href='/A000217']"))
    elif task_id == "ho3b_search_scipy_curve_fit":
        await page.locator("button.search-button-field").first.click()
        box = page.locator("input[name='q']:visible")
        await _search(page, box, "curve_fit", page.locator("#search-results a[href$='generated/scipy.optimize.curve_fit.html']"))
    elif task_id == "ho3b_search_wiktionary_rain_scent":
        box = page.locator("#searchInput")
        await _search(page, box, "scent of rain", page.locator(".mw-search-result-heading a[href='/wiki/petrichor']"))
    elif task_id == "ho3b_search_rubygems_nokogiri":
        await _search(page, page.locator("input[name='query']"), "nokogiri", page.locator("a[href='/gems/nokogiri']"))
    elif task_id == "ho3b_form_practice_login":
        await page.locator("#username").fill("student")
        await page.locator("#password").fill("Password123")
        await _submit(page, lambda: page.locator("#submit").click())
    elif task_id == "ho3b_form_wdu_contact":
        await page.locator("[name='first_name']").fill("Alex")
        await page.locator("[name='last_name']").fill("Example")
        await page.locator("[name='email']").fill("alex@example.com")
        await page.locator("[name='message']").fill("Hello from a test")
        await page.locator("input[type='submit']").click()
        await page.get_by_text("Thank You for your Message!").first.wait_for()
    elif task_id == "ho3b_form_saucedemo_jacket":
        await page.locator("#user-name").fill("standard_user")
        await page.locator("#password").fill("secret_sauce")
        await page.locator("#login-button").click()
        await page.wait_for_url("**/inventory.html")
        await page.get_by_text("Sauce Labs Fleece Jacket", exact=True).wait_for()
    elif task_id == "ho3b_form_scrapethissite_hockey":
        await page.locator("input[name='q']").fill("Detroit Red Wings")
        await _submit(page, lambda: page.locator("input[name='q']").press("Enter"))
    elif task_id == "ho3b_spa_quotes_simile":
        await page.get_by_text("simile", exact=True).wait_for()
    elif task_id == "ho3b_spa_swagger_upload_path":
        await page.get_by_text("uploads an image").first.wait_for()
    elif task_id == "ho3b_spa_scrapethissite_oscars":
        await _link(page, "2015").click()
        await page.locator("td.film-title", has_text="The Revenant").wait_for()
    else:
        raise AssertionError(f"no steps for {task_id}")


async def _evidence_at(context, url: str, *, javascript: bool = True):
    page = await context.new_page()
    try:
        response = await page.goto(url, wait_until="domcontentloaded")
        # A static SPA host may answer a deep link with 404 plus the app shell; only decoys must be real pages.
        if javascript:
            assert response is not None and response.status == 200, (url, response.status if response else None)
            await page.wait_for_timeout(1500)
        return await collect_page_evidence(page)
    finally:
        await page.close()


async def verify() -> list[tuple]:
    tasks = tasks_for_split("heldout3b")
    rows = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(4)

        async def check(task: dict):
            async with semaphore:
                context = await browser.new_context()
                page = await context.new_page()
                page.set_default_timeout(45000)
                markers = task["end_markers"]
                answer = task["expected_answer"]
                try:
                    start = await page.goto(task["start_url"], wait_until="domcontentloaded")
                    start_status = await _real_page(page, start)
                    start_evidence = await collect_page_evidence(page)
                    await _interact(page, task)
                    evidence = await collect_page_evidence(page)
                    # Literal presence, independent of the grader's case/space folding.
                    assert answer in evidence.text, (task["id"], "answer absent from runner evidence", evidence.text[:300])
                    verdict = evidence_verdict(markers, evidence, ClaimedEvidence(answer=answer))
                    assert verdict.verdict == "PASS", (task["id"], verdict)

                    negatives = []
                    wrong_pages = [] if task["id"] in START_IS_FINISHED else [start_evidence]
                    for decoy in DECOYS.get(task["id"], []):
                        wrong_pages.append(await _evidence_at(context, decoy))
                    for wrong_page in wrong_pages:
                        wrong_page_verdict = evidence_verdict(markers, wrong_page, ClaimedEvidence(answer=answer))
                        assert wrong_page_verdict.verdict == "FAIL", (task["id"], "wrong page accepted", wrong_page.url, wrong_page_verdict)
                    negatives.append(f"{len(wrong_pages)} wrong pages FAIL")
                    variants = [page.url.split("#")[0] + "#ho3b", *VARIANTS.get(task["id"], [])]
                    for variant in variants:
                        moved = replace(evidence, url=variant, canonical="")
                        variant_verdict = evidence_verdict(markers, moved, ClaimedEvidence(answer=answer))
                        assert variant_verdict.verdict == "PASS", (task["id"], "correct URL variant rejected", variant, variant_verdict)
                    negatives.append(f"{len(variants)} URL variants PASS")
                    if task["id"] in WRONG_VALUES:
                        wrong = WRONG_VALUES[task["id"]]
                        assert wrong in evidence.text, (task["id"], "wrong value is not on the page", wrong)
                        wrong_verdict = evidence_verdict(markers, evidence, ClaimedEvidence(answer=wrong))
                        assert wrong_verdict.verdict == "FAIL", (task["id"], "wrong value accepted", wrong_verdict)
                        negatives.append("wrong value FAIL")
                    if task["id"] in SCRIPT_ONLY:
                        no_js_context = await browser.new_context(java_script_enabled=False)
                        try:
                            bare = await _evidence_at(no_js_context, page.url, javascript=False)
                        finally:
                            await no_js_context.close()
                        assert SCRIPT_ONLY[task["id"]] in evidence.text, (task["id"], "row text missing with JavaScript")
                        assert SCRIPT_ONLY[task["id"]] not in bare.text, (task["id"], "row visible without JavaScript")
                        negatives.append("absent without JS")
                    print(f"{task['id']}: {start_status}, {page.url}, {verdict.verdict}, {'; '.join(negatives)}", flush=True)
                    return task["id"], start_status, page.url, verdict.verdict, "; ".join(negatives)
                finally:
                    await context.close()

        try:
            results = await asyncio.gather(*(check(task) for task in tasks), return_exceptions=True)
        finally:
            await browser.close()

    failures = [(task["id"], result) for task, result in zip(tasks, results) if isinstance(result, BaseException)]
    for task_id, error in failures:
        print(f"{task_id}: ERROR {type(error).__name__}: {str(error)[:400]}", flush=True)
    rows = [result for result in results if not isinstance(result, BaseException)]
    print(f"heldout3b verify: {len(rows)}/{len(tasks)} PASS; every negative control FAIL and every URL variant PASS", flush=True)
    if failures:
        sys.exit(1)
    _write_report(rows)
    return rows


def _write_report(rows: list[tuple]) -> None:
    lines = [
        "# Heldout3b public-page verification", "",
        f"Verified {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} with local headless Chromium.", "",
        "This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.",
        "Mix: 8 multi-step navigation, 8 value reports, 4 site searches, 4 submitted demo forms, 3 JavaScript-rendered pages, 3 page-title reports.",
        "Each task was driven from its start page by clicks, typing and form submits. Every page on the way returned HTTP 200 with no challenge page.",
        "Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.",
        "Negative controls: the correct answer claimed on real wrong pages (the start page unless it is the finished page, plus listed decoys such as the page one step short, a neighbouring page, or the site's results page) must FAIL; a wrong value that is on the finished page must FAIL; for script-rendered tasks the answer's row must be absent when the page loads without JavaScript.",
        "URL controls: the finished page's evidence must still PASS at its URL with a #fragment and at listed equivalent URLs (trailing slash or index.html, mobile host, unencoded path, other docs version).", "",
        "Reproduce: `python -m bench.verify_heldout3_b` (public network access; no model calls).", "",
        "| Task id | Start status | End URL | Verdict | Controls |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {task_id} | {status} | {url} | {verdict} | {negative} |" for task_id, status, url, verdict, negative in rows)
    Path("docs/HELDOUT3B_VERIFY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(verify())
