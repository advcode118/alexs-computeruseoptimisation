"""Opt-in public-page verification, not an agent run or an LLM probe.

Run ``python -m bench.verify_heldout3_d`` to refresh docs/HELDOUT3D_VERIFY.md.
Pass task ids as arguments to check only those (the report is then not written).
Only local headless Chromium and the deterministic evidence grader are used.
Every task is driven by clicks, typing and form submits from its start page.
Each task also has negative controls that must grade FAIL.
"""

from __future__ import annotations

import asyncio
import os
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
    "ho3d_value_rcsb_1tup_resolution": "86.84",
    "ho3d_value_pokemondb_pikachu_total": "90",
    "ho3d_value_nobel_1922_affiliation": "Copenhagen, Denmark",
    "ho3d_value_tailwind_text_base_leading": "calc(1.25 / 0.875)",
    "ho3d_value_playwright_test_timeout": "5",
    "ho3d_value_sklearn_logreg_max_iter": "1000",
    "ho3d_value_pytorch_dropout_p": "False",
    "ho3d_value_webscraper_table_tim": "@dunno",
    "ho3d_value_rahulshetty_sql_price": "30",
    "ho3d_value_pandas_head_default": "tail",
    "ho3d_form_uitap_sampleapp": "Log Out",
    "ho3d_form_uitap_textinput": "Button",
    "ho3d_form_scrapingcourse_login": "$52",
    "ho3d_form_pokeapi_pikachu": "pikachu",
    "ho3d_form_qa_practice_input": "Result",
    "ho3d_form_qa_practice_email": "Result",
    "ho3d_spa_scrapingcourse_hero": "$52",
    "ho3d_spa_uitap_ajax": "Data loaded",
    "ho3d_spa_todomvc_count": "3 items left",
    "ho3d_spa_scrapingcourse_infinite": "$52",
    "ho3d_title_pokemondb_after_pikachu": "Pikachu",
    "ho3d_title_euler_after_palindrome": "Largest Palindrome Product",
    "ho3d_title_vue_after_intro": "Introduction",
    "ho3d_title_ocaml_datatypes": "Values and Functions",
}

# Real wrong pages beyond the start page: a step short, a neighbour, or a results page.
DECOYS = {
    "ho3d_nav_nobel_physics_1921_facts": [
        "https://www.nobelprize.org/prizes/physics/1921/summary/",
        "https://www.nobelprize.org/prizes/physics/1922/bohr/facts/",
    ],
    "ho3d_nav_vue_conditional": ["https://vuejs.org/guide/introduction.html", "https://vuejs.org/guide/essentials/list.html"],
    "ho3d_nav_euler_pythagorean": ["https://projecteuler.net/archives", "https://projecteuler.net/problem=90"],
    "ho3d_nav_webscraper_priciest_touch": [
        "https://webscraper.io/test-sites/e-commerce/allinone/phones/touch",
        "https://webscraper.io/test-sites/e-commerce/allinone/product/80",
    ],
    "ho3d_nav_openbsd_pf_shortcuts": ["https://www.openbsd.org/faq/pf/index.html", "https://www.openbsd.org/faq/pf/filter.html"],
    "ho3d_nav_react_first_component": [
        "https://react.dev/learn/describing-the-ui",
        "https://react.dev/learn/importing-and-exporting-components",
    ],
    "ho3d_nav_ocaml_loops": ["https://ocaml.org/docs/language", "https://ocaml.org/docs/lists"],
    "ho3d_nav_nextjs_fetching": [
        "https://nextjs.org/docs/app/getting-started",
        "https://nextjs.org/docs/app/getting-started/mutating-data",
    ],
    "ho3d_nav_pokemondb_mewtwo": ["https://pokemondb.net/pokedex/national", "https://pokemondb.net/pokedex/mew"],
    "ho3d_nav_nim_strutils": ["https://nim-lang.org/docs/lib.html", "https://nim-lang.org/docs/strformat.html"],
    "ho3d_value_rcsb_1tup_resolution": ["https://www.rcsb.org/structure/1TUQ"],
    "ho3d_value_pokemondb_pikachu_total": ["https://pokemondb.net/pokedex/raichu"],
    "ho3d_value_nobel_1922_affiliation": ["https://www.nobelprize.org/prizes/physics/1922/summary/"],
    "ho3d_value_tailwind_text_base_leading": ["https://tailwindcss.com/docs/line-height"],
    "ho3d_value_playwright_test_timeout": ["https://playwright.dev/docs/intro"],
    "ho3d_value_sklearn_logreg_max_iter": [
        "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegressionCV.html",
        "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html",
    ],
    "ho3d_value_pytorch_dropout_p": ["https://docs.pytorch.org/docs/stable/generated/torch.nn.Dropout2d.html"],
    "ho3d_value_webscraper_table_tim": ["https://webscraper.io/test-sites/tables/tables-without-thead"],
    "ho3d_value_pandas_head_default": ["https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.tail.html"],
    "ho3d_search_videolan_cli": [
        "https://wiki.videolan.org/index.php?search=command+line&title=Special%3ASearch&fulltext=Search",
        "https://wiki.videolan.org/Windows_command-line_help/",
    ],
    "ho3d_search_pandas_read_csv": [
        "https://pandas.pydata.org/docs/search.html?q=read_csv",
        "https://pandas.pydata.org/docs/reference/api/pandas.read_table.html",
    ],
    "ho3d_search_sklearn_random_forest": [
        "https://scikit-learn.org/stable/search.html?q=RandomForestClassifier",
        "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html",
    ],
    "ho3d_search_openbsd_man_pledge": ["https://man.openbsd.org/unveil", "https://man.openbsd.org/?query=pledge&apropos=1"],
    "ho3d_search_pytorch_conv2d": [
        "https://docs.pytorch.org/docs/stable/search.html?q=Conv2d",
        "https://docs.pytorch.org/docs/stable/generated/torch.nn.Conv1d.html",
    ],
    "ho3d_search_pokemondb_bulbasaur": ["https://pokemondb.net/search?q=bulbasaur", "https://pokemondb.net/pokedex/ivysaur"],
    "ho3d_form_pokeapi_pikachu": ["https://pokeapi.co/api/v2/pokemon/pikachu"],
    "ho3d_spa_scrapingcourse_hero": ["https://www.scrapingcourse.com/infinite-scrolling"],
    "ho3d_title_pokemondb_after_pikachu": ["https://pokemondb.net/pokedex/pikachu"],
    "ho3d_title_euler_after_palindrome": ["https://projecteuler.net/problem=4"],
    "ho3d_title_vue_after_intro": ["https://vuejs.org/guide/introduction.html"],
    "ho3d_title_ocaml_datatypes": ["https://ocaml.org/docs/values-and-functions"],
}

# Other correct end URLs. The finished page's evidence at these URLs must still PASS.
# Every task is also checked with a #fragment on its finished URL.
VARIANTS = {
    "ho3d_nav_nobel_physics_1921_facts": ["https://www.nobelprize.org/prizes/physics/1921/einstein/facts"],
    "ho3d_nav_vue_conditional": ["https://vuejs.org/guide/essentials/conditional"],
    "ho3d_nav_euler_pythagorean": ["https://projecteuler.net/problem=9?x=1"],
    "ho3d_nav_openbsd_pf_shortcuts": ["https://www.openbsd.org/faq/pf/shortcuts.html"],
    "ho3d_nav_react_first_component": ["https://react.dev/learn/your-first-component/"],
    "ho3d_nav_ocaml_loops": ["https://ocaml.org/docs/loops-recursion/"],
    "ho3d_nav_nextjs_fetching": ["https://nextjs.org/docs/app/getting-started/fetching-data/"],
    "ho3d_nav_pokemondb_mewtwo": ["https://pokemondb.net/pokedex/mewtwo/"],
    "ho3d_nav_nim_strutils": ["https://nim-lang.org/docs/strutils.html"],
    "ho3d_value_rcsb_1tup_resolution": ["https://www.rcsb.org/structure/1tup", "https://www.rcsb.org/structure/1TUP/"],
    "ho3d_value_pokemondb_pikachu_total": ["https://pokemondb.net/pokedex/pikachu/"],
    "ho3d_value_nobel_1922_affiliation": ["https://www.nobelprize.org/prizes/physics/1922/bohr/facts"],
    "ho3d_value_playwright_test_timeout": ["https://playwright.dev/docs/test-timeouts/"],
    "ho3d_value_sklearn_logreg_max_iter": [
        "https://scikit-learn.org/1.9/modules/generated/sklearn.linear_model.LogisticRegression.html",
    ],
    "ho3d_value_pytorch_dropout_p": ["https://pytorch.org/docs/stable/generated/torch.nn.Dropout.html"],
    "ho3d_value_webscraper_table_tim": ["https://webscraper.io/test-sites/tables/tables-semantically-correct/"],
    "ho3d_search_videolan_cli": ["https://wiki.videolan.org/VLC_command-line_help"],
    "ho3d_search_pandas_read_csv": [
        "https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html#pandas.read_csv",
        "https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html",
    ],
    "ho3d_search_sklearn_random_forest": [
        "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html#sklearn.ensemble.RandomForestClassifier",
    ],
    "ho3d_search_openbsd_man_pledge": ["https://man.openbsd.org/pledge.2", "https://man.openbsd.org/OpenBSD-current/man2/pledge.2"],
    "ho3d_search_pytorch_conv2d": ["https://docs.pytorch.org/docs/2.15/generated/torch.nn.Conv2d.html"],
    "ho3d_form_scrapingcourse_login": ["https://www.scrapingcourse.com/dashboard/"],
    "ho3d_spa_scrapingcourse_hero": ["https://www.scrapingcourse.com/javascript-rendering/"],
    "ho3d_spa_todomvc_count": ["https://todomvc.com/examples/react/dist/index.html", "https://todomvc.com/examples/react/dist/#/active"],
    "ho3d_title_pokemondb_after_pikachu": ["https://pokemondb.net/pokedex/raichu/"],
    "ho3d_title_euler_after_palindrome": ["https://projecteuler.net/problem=5?x=1"],
    "ho3d_title_vue_after_intro": ["https://vuejs.org/guide/quick-start"],
    "ho3d_title_ocaml_datatypes": ["https://ocaml.org/docs/basic-data-types/"],
}

# The start page is already the finished page here, so only the decoy is a wrong page.
START_IS_FINISHED = {
    "ho3d_value_rcsb_1tup_resolution",
    "ho3d_value_tailwind_text_base_leading",
    "ho3d_value_playwright_test_timeout",
    "ho3d_value_rahulshetty_sql_price",
    "ho3d_form_uitap_sampleapp",
    "ho3d_form_uitap_textinput",
    "ho3d_form_pokeapi_pikachu",
    "ho3d_form_qa_practice_input",
    "ho3d_form_qa_practice_email",
    "ho3d_spa_scrapingcourse_hero",
    "ho3d_spa_uitap_ajax",
    "ho3d_spa_todomvc_count",
    "ho3d_spa_scrapingcourse_infinite",
}

# Text from the answer's row that must be missing when the finished page loads without JavaScript.
SCRIPT_ONLY = {
    "ho3d_spa_scrapingcourse_hero": "Hero Hoodie",
    "ho3d_form_scrapingcourse_login": "Teton Pullover Hoodie",
}

DEBUG = bool(os.environ.get("HO3D_DEBUG"))


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


async def _search(page, box, query: str, result) -> None:
    await box.first.fill(query)
    await _submit(page, lambda: box.first.press("Enter"))
    if result is not None:
        await _follow(page, result)


async def _sphinx_search(page, button, query: str, result) -> None:
    """Open a Sphinx docs search field, search, and follow a result from the live results list."""
    await button.first.click()
    box = page.locator("input[name='q']:visible")
    await box.first.fill(query)
    await _submit(page, lambda: box.first.press("Enter"))
    await _follow(page, result)


def _scroll_prices_js() -> str:
    return "Array.from(document.querySelectorAll('.product-item, .product, [class*=product]')).length"


async def _interact(page, task: dict) -> None:
    task_id = task["id"]
    if task_id == "ho3d_nav_nobel_physics_1921_facts":
        await _follow(page, page.locator("a[href$='/prizes/physics/1921/einstein/']"))
        await _follow(page, _link(page, "Facts"))
    elif task_id == "ho3d_value_nobel_1922_affiliation":
        await _follow(page, _link(page, "Niels Bohr"))
        await _follow(page, _link(page, "Facts"))
    elif task_id == "ho3d_nav_vue_conditional":
        await _follow(page, page.locator("a[href^='/guide/introduction']:visible"))
        await _follow(page, page.locator("a[href^='/guide/essentials/conditional']"))
    elif task_id == "ho3d_nav_euler_pythagorean":
        await _follow(page, page.locator("a[href='archives']"))
        await _follow(page, _link(page, "Special Pythagorean Triplet"))
    elif task_id == "ho3d_title_euler_after_palindrome":
        await _follow(page, _link(page, "Smallest Multiple"))
    elif task_id == "ho3d_nav_webscraper_priciest_touch":
        await _follow(page, _link(page, "Phones"))
        await _follow(page, _link(page, "Touch"))
        pods = page.locator(".thumbnail")
        count = await pods.count()
        prices = [float((await pods.nth(i).locator(".price").inner_text()).strip().strip("$")) for i in range(count)]
        top = max(prices)
        assert prices.count(top) == 1, ("tied price", prices)
        await _follow(page, pods.nth(prices.index(top)).locator("a.title"))
    elif task_id == "ho3d_nav_openbsd_pf_shortcuts":
        await _follow(page, _link(page, "FAQ"))
        await _follow(page, _link(page, "PF User's Guide"))
        await _follow(page, _link(page, "Shortcuts for Creating Rulesets"))
    elif task_id == "ho3d_nav_react_first_component":
        await _follow(page, page.locator("a[href='/learn/describing-the-ui']:visible"))
        await _follow(page, page.locator("a[href='/learn/your-first-component']:visible"))
    elif task_id == "ho3d_nav_ocaml_loops":
        await _follow(page, page.locator("a[href='/docs/language']:visible"))
        await _follow(page, page.locator("a[href='/docs/loops-recursion']:visible"))
    elif task_id == "ho3d_title_ocaml_datatypes":
        await _follow(page, page.locator("a[href='/docs/basic-data-types']:visible"))
    elif task_id == "ho3d_nav_nextjs_fetching":
        await _follow(page, page.locator("a[href='/docs/app']:visible"))
        await _follow(page, page.locator("a[href='/docs/app/getting-started']:visible"))
        await _follow(page, page.locator("a[href='/docs/app/getting-started/fetching-data']:visible"))
    elif task_id == "ho3d_nav_pokemondb_mewtwo":
        await _follow(page, page.locator("a[href='/pokedex']:visible"))
        await _follow(page, page.locator("a[href='/pokedex/national']:visible"))
        await _follow(page, page.locator("a.ent-name[href='/pokedex/mewtwo']"))
    elif task_id == "ho3d_nav_nim_strutils":
        await _follow(page, page.locator("a[href='documentation.html']"))
        await _follow(page, _link(page, "Standard Library"))
        await _follow(page, page.locator("a[href='strutils.html']"))
    elif task_id == "ho3d_value_rcsb_1tup_resolution":
        await page.get_by_text("Resolution:").first.wait_for()
    elif task_id == "ho3d_value_pokemondb_pikachu_total":
        await _follow(page, page.locator("a.ent-name[href='/pokedex/pikachu']"))
    elif task_id == "ho3d_value_tailwind_text_base_leading":
        await page.get_by_text("text-base", exact=True).first.wait_for()
    elif task_id == "ho3d_value_playwright_test_timeout":
        await page.get_by_text("Test timeout", exact=False).first.wait_for()
    elif task_id == "ho3d_value_sklearn_logreg_max_iter":
        await _follow(page, page.locator("a[href$='sklearn.linear_model.LogisticRegression.html']"))
    elif task_id == "ho3d_value_pytorch_dropout_p":
        await _follow(page, page.locator("a[href$='generated/torch.nn.Dropout.html']"))
    elif task_id == "ho3d_value_webscraper_table_tim":
        await _follow(page, _link(page, "Semantically correct tables"))
    elif task_id == "ho3d_value_rahulshetty_sql_price":
        await page.get_by_text("Web Table Example").first.wait_for()
    elif task_id == "ho3d_value_pandas_head_default":
        await _follow(page, page.locator("a[href$='pandas.DataFrame.head.html']"))
    elif task_id == "ho3d_search_videolan_cli":
        await _search(page, page.locator("input[name='search']"), "command line",
                      page.locator(".mw-search-result-heading a[href='/VLC_command-line_help/']"))
    elif task_id == "ho3d_search_pandas_read_csv":
        await _sphinx_search(page, page.locator("button.search-button-field"), "read_csv",
                             page.locator("#search-results a[href*='reference/api/pandas.read_csv.html']"))
    elif task_id == "ho3d_search_sklearn_random_forest":
        await _sphinx_search(page, page.locator("button.search-button__button"), "RandomForestClassifier",
                             page.locator("#search-results a[href*='sklearn.ensemble.RandomForestClassifier.html']"))
    elif task_id == "ho3d_search_openbsd_man_pledge":
        await _search(page, page.locator("input[name='query']"), "pledge", None)
    elif task_id == "ho3d_search_pytorch_conv2d":
        await _sphinx_search(page, page.locator("button.search-button__button, button.search-button-field"), "Conv2d",
                             page.locator("#search-results a[href*='torch.nn.Conv2d.html']"))
    elif task_id == "ho3d_search_pokemondb_bulbasaur":
        box = page.locator("input[name='q']:visible, input[type='search']:visible")
        await _search(page, box, "Bulbasaur", page.locator("a[href='https://pokemondb.net/pokedex/bulbasaur'], a[href='/pokedex/bulbasaur']"))
    elif task_id == "ho3d_form_uitap_sampleapp":
        await page.locator("input[name='UserName']").fill("Alex")
        await page.locator("input[name='Password']").fill("pwd")
        await page.locator("#login").click()
        await page.get_by_text("Welcome, Alex!").wait_for()
    elif task_id == "ho3d_form_uitap_textinput":
        await page.locator("#newButtonName").fill("Renamed")
        await page.locator("#updatingButton").click()
        await page.locator("#updatingButton", has_text="Renamed").wait_for()
    elif task_id == "ho3d_form_scrapingcourse_login":
        await page.locator("#email").fill("admin@example.com")
        await page.locator("#password").fill("password")
        await _submit(page, lambda: page.locator("#submit-button").click())
        await page.get_by_text("Teton Pullover Hoodie").wait_for()
    elif task_id == "ho3d_form_pokeapi_pikachu":
        await page.locator("#url-input").fill("pokemon/pikachu")
        await page.get_by_role("button", name="Submit", exact=True).click()
        await page.get_by_text("Resource for pikachu").wait_for()
    elif task_id == "ho3d_form_qa_practice_input":
        await page.locator("input[name='text_string']").fill("hello_world")
        await _submit(page, lambda: page.locator("input[name='text_string']").press("Enter"))
    elif task_id == "ho3d_form_qa_practice_email":
        await page.locator("input[name='email']").fill("alex@example.com")
        await _submit(page, lambda: page.locator("input[name='email']").press("Enter"))
    elif task_id == "ho3d_spa_scrapingcourse_hero":
        await page.get_by_text("Hero Hoodie", exact=True).wait_for()
    elif task_id == "ho3d_spa_uitap_ajax":
        await page.locator("#ajaxButton").click()
        await page.get_by_text("Data loaded with AJAX get request.").wait_for(timeout=30000)
    elif task_id == "ho3d_spa_todomvc_count":
        box = page.locator("input.new-todo")
        for name in ("one", "two", "three"):
            await box.fill(name)
            await box.press("Enter")
        await page.locator("li", has_text="two").locator("input.toggle").check()
        await page.get_by_text("2 items left").first.wait_for()
    elif task_id == "ho3d_spa_scrapingcourse_infinite":
        for _ in range(8):
            await page.mouse.wheel(0, 4000)
            await page.wait_for_timeout(600)
    elif task_id == "ho3d_title_pokemondb_after_pikachu":
        await _follow(page, page.locator("a[href='/pokedex/raichu']").first)
    elif task_id == "ho3d_title_vue_after_intro":
        await _follow(page, page.locator("a.pager-link.next, a[href^='/guide/quick-start']:visible"))
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


async def verify(only: list[str] | None = None) -> list[tuple]:
    tasks = tasks_for_split("heldout3d")
    if only:
        tasks = [task for task in tasks if task["id"] in only]
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
                    if DEBUG:
                        print(f"DEBUG {task['id']}: {evidence.url} :: {evidence.text[:400]!r}", flush=True)
                    # Literal presence, independent of the grader's case/space folding.
                    assert answer in evidence.text, (task["id"], "answer absent from runner evidence", evidence.url, evidence.text[:300])
                    verdict = evidence_verdict(markers, evidence, ClaimedEvidence(answer=answer))
                    assert verdict.verdict == "PASS", (task["id"], verdict)

                    negatives = []
                    wrong_pages = [] if task["id"] in START_IS_FINISHED else [start_evidence]
                    for decoy in DECOYS.get(task["id"], []):
                        wrong_pages.append(await _evidence_at(context, decoy))
                    for wrong_page in wrong_pages:
                        wrong_page_verdict = evidence_verdict(markers, wrong_page, ClaimedEvidence(answer=answer))
                        assert wrong_page_verdict.verdict == "FAIL", (task["id"], "wrong page accepted", wrong_page.url, wrong_page_verdict)
                    if task["id"] in START_IS_FINISHED:
                        # The page before the action must not already show the answer in the graded form.
                        before = evidence_verdict(markers, start_evidence, ClaimedEvidence(answer=answer))
                        if answer in start_evidence.text:
                            assert before.verdict == "FAIL" or task["id"] in {
                                "ho3d_value_rcsb_1tup_resolution", "ho3d_value_tailwind_text_base_leading",
                                "ho3d_value_playwright_test_timeout", "ho3d_value_rahulshetty_sql_price",
                            }, (task["id"], "answer already on the start page", before)
                    negatives.append(f"{len(wrong_pages)} wrong pages FAIL")
                    variants = [page.url.split("#")[0] + "#ho3d", *VARIANTS.get(task["id"], [])]
                    for variant in variants:
                        moved = replace(evidence, url=variant, canonical="")
                        variant_verdict = evidence_verdict(markers, moved, ClaimedEvidence(answer=answer))
                        assert variant_verdict.verdict == "PASS", (task["id"], "correct URL variant rejected", variant, variant_verdict)
                    negatives.append(f"{len(variants)} URL variants PASS")
                    wrong_checks = len(wrong_pages)
                    if task["id"] in WRONG_VALUES:
                        wrong = WRONG_VALUES[task["id"]]
                        assert wrong in evidence.text, (task["id"], "wrong value is not on the page", wrong)
                        wrong_verdict = evidence_verdict(markers, evidence, ClaimedEvidence(answer=wrong))
                        assert wrong_verdict.verdict == "FAIL", (task["id"], "wrong value accepted", wrong_verdict)
                        negatives.append("wrong value FAIL")
                        wrong_checks += 1
                    assert wrong_checks >= 1, (task["id"], "no negative check")
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
        print(f"{task_id}: ERROR {type(error).__name__}: {str(error)[:500]}", flush=True)
    rows = [result for result in results if not isinstance(result, BaseException)]
    print(f"heldout3d verify: {len(rows)}/{len(tasks)} PASS; every negative control FAIL and every URL variant PASS", flush=True)
    if failures:
        sys.exit(1)
    if not only:
        _write_report(rows)
    return rows


def _write_report(rows: list[tuple]) -> None:
    lines = [
        "# Heldout3d public-page verification", "",
        f"Verified {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} with local headless Chromium.", "",
        "This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.",
        "Mix: 10 multi-step navigation, 10 value reports, 6 site searches, 6 submitted demo forms, 4 JavaScript-rendered pages, 4 page-title reports.",
        "Each task was driven from its start page by clicks, typing and form submits. Every page on the way returned HTTP 200 with no challenge page.",
        "Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.",
        "Negative controls: the correct answer claimed on real wrong pages (the start page unless it is the finished page, plus listed decoys such as the page one step short, a neighbouring page, or the site's results page) must FAIL; a wrong value that is on the finished page must FAIL; for script-rendered tasks the answer's row must be absent when the page loads without JavaScript.",
        "URL controls: the finished page's evidence must still PASS at its URL with a #fragment and at listed equivalent URLs (trailing slash, no extension, mobile host, other docs version).", "",
        "Reproduce: `python -m bench.verify_heldout3_d` (public network access; no model calls).", "",
        "| Task id | Start status | End URL | Verdict | Controls |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {task_id} | {status} | {url} | {verdict} | {negative} |" for task_id, status, url, verdict, negative in rows)
    Path("docs/HELDOUT3D_VERIFY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(verify(sys.argv[1:] or None))
