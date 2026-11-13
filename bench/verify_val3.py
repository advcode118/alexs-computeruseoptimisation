"""Opt-in public-page verification of the val3 set, not an agent run or an LLM probe.

Run ``python -m bench.verify_val3``. Only local headless Chromium and the
deterministic graders are used: evidence_verdict and the probe's
grade_observation, on evidence read by the runner's collect_page_evidence.

For every task a reproducer drives the browser to the end state, which must
pass both graders. Two negative controls must fail: the start page (or the
state before the action) claimed with the expected answer, and, for tasks with
an answer marker, a wrong value read off the finished page.

val3 is an aggregate-only gate, so this prints per-task verdicts and the total
only. It does not print answers and writes no report file.
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

from bench.probe import grade_observation
from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split

# Pages a direct goto reproduces (nav, value and title tasks).
END_URLS = {
    "val3_nav_perldoc_regex": "https://perldoc.perl.org/perlre",
    "val3_nav_vimhelp_undo": "https://vimhelp.org/undo.txt.html",
    "val3_nav_nmap_scantypes": "https://nmap.org/book/man-port-scanning-techniques.html",
    "val3_nav_osi_mit": "https://opensource.org/license/mit",
    "val3_nav_sass_modules": "https://sass-lang.com/documentation/at-rules/use/",
    "val3_nav_ruby_newcomers": "https://www.ruby-lang.org/en/documentation/ruby-from-other-languages/",
    "val3_nav_toml_spec": "https://toml.io/en/v1.0.0",
    "val3_nav_zig_features": "https://ziglang.org/learn/overview/",
    "val3_nav_pip_everyday": "https://pip.pypa.io/en/stable/user_guide/",
    "val3_nav_tcpdump_filter": "https://www.tcpdump.org/manpages/pcap-filter.7.html",
    "val3_value_yaml_revision": "https://yaml.org/spec/1.2.2/",
    "val3_value_webelements_gallium": "https://www.webelements.com/gallium/",
    "val3_value_webelements_tungsten": "https://www.webelements.com/tungsten/",
    "val3_value_sep_frege": "https://plato.stanford.edu/entries/frege/",
    "val3_value_periodni_osmium": "https://www.periodni.com/os.html",
    "val3_value_osi_zope": "https://opensource.org/license/zpl-2-0",
    "val3_value_rapidtables_del": "https://www.rapidtables.com/code/text/ascii-table.html",
    "val3_value_ninja_iphone": "https://tutorialsninja.com/demo/index.php?route=product/product&product_id=40",
    "val3_value_ruby_eol": "https://www.ruby-lang.org/en/downloads/branches/",
    "val3_value_tad_acst": "https://www.timeanddate.com/time/zones/acst",
    "val3_title_vite_server": "https://vite.dev/guide/ssr",
    "val3_title_prettier_reasons": "https://prettier.io/docs/why-prettier",
    "val3_title_ninja_laptop": "https://tutorialsninja.com/demo/index.php?route=product/category&path=18",
    "val3_title_zod_first": "https://zod.dev/basics",
}

# Site search: (search box, query, result link href fragment). An empty
# fragment means the site's search jumps straight to the page.
SEARCHES = {
    "val3_search_sep_ockham": ("#search-text", "Ockham", "/entries/ockham/"),
    "val3_search_sqlalchemy_hybrid": ("input[name=q]:visible", "hybrid", "orm/extensions/hybrid.html"),
    "val3_search_pip_reqfiles": ("input[name=q]:visible", "requirements", "reference/requirements-file-format/"),
    "val3_search_psycopg_copy": ("input[name=q]:visible", "COPY", "basic/copy.html"),
    "val3_search_sympy_sets": ("input[name=q]:visible", "solveset", "solvers/solveset.html"),
    "val3_search_perldoc_format": ("#search-input", "sprintf", ""),
}

# Result lists: Sphinx/Furo result containers, else the SEP search results body.
_RESULT_SCOPES = ("#search-results", ".search-results", "ul.search", "main", "#content", ".search_results")


async def _real_page(page, response) -> int:
    assert response is not None and response.status == 200, (
        page.url, response.status if response else None
    )
    # Script-rendered pages fill the body after DOMContentLoaded.
    try:
        await page.wait_for_function("() => (document.body && document.body.innerText.trim().length > 100)", timeout=15000)
    except Exception:  # noqa: BLE001 - the length assertion below reports it
        pass
    body = await page.locator("body").inner_text()
    title = (await page.title()).casefold()
    assert len(body.strip()) > 100, (page.url, "empty/error page")
    assert not any(token in title for token in ("just a moment", "attention required", "access denied")), page.url
    assert not any(token in body.casefold() for token in (
        "verify you are human", "checking your browser before accessing",
        "performing security verification", "enable javascript and cookies to continue",
    )), page.url
    assert await page.locator("#challenge-running, #challenge-stage, iframe[src*='challenges.cloudflare.com']").count() == 0, page.url
    return response.status


async def _goto(page, url: str):
    response = await page.goto(url, wait_until="domcontentloaded")
    await _real_page(page, response)
    return response


async def _search(page, task_id: str):
    box_selector, query, fragment = SEARCHES[task_id]
    box = page.locator(box_selector).first
    await box.fill(query)
    async with page.expect_navigation():
        await box.press("Enter")
    if not fragment:
        await page.wait_for_load_state("domcontentloaded")
        return
    scoped = ", ".join(f'{scope} a[href*="{fragment}"]' for scope in _RESULT_SCOPES)
    result = page.locator(scoped).first
    await result.wait_for()
    async with page.expect_navigation():
        await result.click()
    await page.wait_for_load_state("domcontentloaded")


async def _fails_before_action(page, task: dict) -> None:
    """On the app's own URL, the state before the action must not pass."""
    before = await collect_page_evidence(page)
    verdict, ok = _grade(task, before, task["expected_answer"])
    assert verdict != "PASS" and not ok, "app page passed before the action"


async def _interact(page, task: dict):
    task_id = task["id"]
    if task_id in END_URLS:
        await _goto(page, END_URLS[task_id])
        return
    if task_id in SEARCHES:
        await _search(page, task_id)
        return
    if task_id == "val3_form_qaplayground_register":
        await _goto(page, "https://qaplayground.dev/apps/register-login/")
        await page.locator("#reg-name").fill("Alex Example")
        await page.locator("#reg-email").fill("alex@example.com")
        await page.locator("#reg-password").fill("Practice123")
        await page.locator("#reg-confirm").fill("Practice123")
        await page.locator("#register-submit").click()
        await page.locator("#login-alert.success").wait_for()
        return
    if task_id == "val3_form_trytesting_login":
        await page.locator("#uname").fill("test")
        await page.locator("#pwd").fill("test")
        async with page.expect_navigation():
            await page.locator("input[type=submit][value=Login]").click()
        await page.wait_for_load_state("domcontentloaded")
        return
    if task_id in ("val3_form_tad_duration", "val3_form_tad_dateadd"):
        duration = task_id == "val3_form_tad_duration"
        await _goto(page, "https://www.timeanddate.com/date/duration.html" if duration
                    else "https://www.timeanddate.com/date/dateadd.html")
        fields = dict(d1="1", m1="1", y1="2000", d2="1", m2="1", y2="2024") if duration \
            else dict(d1="1", m1="1", y1="2024", ad="100")
        for name, value in fields.items():
            await page.locator(f"#{name}").fill(value)
        async with page.expect_navigation():
            await page.locator("#subbut2").click()
        await page.wait_for_load_state("domcontentloaded")
        return
    if task_id == "val3_form_sweetshop_account":
        await _goto(page, "https://sweetshop.netlify.app/login")
        await page.locator("#exampleInputEmail").fill("twoorders@sweetshop.local")
        await page.locator("#exampleInputPassword").fill("qwerty")
        await page.locator("#btn_login").click()
        await page.wait_for_url("**/*.html")
        await page.get_by_text("Total spent").first.wait_for()
        return
    if task_id == "val3_form_qaplayground_verify":
        await _goto(page, "https://qaplayground.dev/apps/verify-account/")
        await _fails_before_action(page, task)
        codes = page.locator(".code")
        for index in range(await codes.count()):
            await codes.nth(index).click()
            await codes.nth(index).press("9")
            await page.wait_for_timeout(60)
        await page.get_by_text("Success", exact=True).wait_for()
        return
    if task_id == "val3_spa_seleniumbase_coffee":
        await _goto(page, "https://seleniumbase.io/coffee/")
        await _fails_before_action(page, task)
        await page.locator("[data-test=Cappuccino]").click()
        await page.locator("[data-test=Flat_White]").click()
        await page.get_by_text("Total: $37.00").first.wait_for()
        return
    if task_id == "val3_spa_seleniumbase_button":
        await _goto(page, "https://seleniumbase.io/demo_page")
        await _fails_before_action(page, task)
        await page.locator("#myButton").click()
        await page.get_by_text("This Text is Purple").wait_for()
        return
    if task_id == "val3_spa_sweetshop_basket":
        for name in ("Chocolate Cups", "Bon Bons"):
            await page.locator(".card", has_text=name).get_by_text("Add to Basket").click()
        async with page.expect_navigation():
            await page.locator("a[href='/basket']").first.click()
        await page.get_by_text("£2.00").first.wait_for()
        return
    if task_id == "val3_spa_qaplayground_covered":
        await _goto(page, "https://qaplayground.dev/apps/covered/")
        await _fails_before_action(page, task)
        await page.locator("#fugitive").dispatch_event("click")
        await page.get_by_text("Mission accomplished").wait_for()
        return
    raise AssertionError(f"no reproducer for {task_id}")


def _grade(task: dict, evidence, answer: str) -> tuple[str, bool]:
    verdict = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=answer))
    ok, _reason, _shared_ok, _shared_reason = grade_observation(task, evidence.url, evidence.text, answer=answer)
    return verdict.verdict, ok


def _decoy(task: dict, evidence) -> str:
    """A wrong value read off the finished page: its h1 or title, unless that is the answer."""
    marker = " ".join(task["end_markers"]["answer_in_text"].split()).casefold()
    for candidate in (evidence.h1, evidence.title, "0"):
        text = " ".join((candidate or "").split())
        if text and marker not in text.casefold():
            return text
    return "not the requested value"


async def _check(browser, task: dict) -> tuple[str, bool, str]:
    context = await browser.new_context()
    page = await context.new_page()
    page.set_default_timeout(45000)
    answer = task["expected_answer"]
    try:
        await _goto(page, task["start_url"])
        before = await collect_page_evidence(page)
        start_verdict, start_ok = _grade(task, before, answer)
        assert start_verdict != "PASS" and not start_ok, "start page passed"
        await _interact(page, task)
        evidence = await collect_page_evidence(page)
        # Literal presence, independent of the grader's case and space folding.
        assert answer in evidence.text, "answer absent from runner evidence"
        verdict, ok = _grade(task, evidence, answer)
        assert verdict == "PASS" and ok, f"end state did not pass ({verdict})"
        negative = "wrong page"
        if task["end_markers"].get("answer_in_text"):
            wrong_verdict, wrong_ok = _grade(task, evidence, _decoy(task, evidence))
            assert wrong_verdict == "FAIL" and not wrong_ok, "wrong value passed"
            negative = "wrong page + wrong value"
        return task["id"], True, f"PASS; {negative} FAIL"
    except Exception as exc:  # noqa: BLE001 - one task's failure is reported, not raised
        detail = " ".join(str(exc).split())[:160]
        return task["id"], False, f"{type(exc).__name__}: {detail}"
    finally:
        await context.close()


async def verify(only: list[str] | None = None) -> int:
    tasks = [task for task in tasks_for_split("val3") if not only or task["id"] in only]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(4)

        async def guarded(task):
            async with semaphore:
                return await _check(browser, task)

        try:
            rows = await asyncio.gather(*(guarded(task) for task in tasks))
        finally:
            await browser.close()
    for task_id, ok, note in rows:
        print(f"{'ok  ' if ok else 'FAIL'} {task_id}: {note}", flush=True)
    passed = sum(ok for _task_id, ok, _note in rows)
    print(f"TOTAL {passed}/{len(rows)}", flush=True)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(verify(sys.argv[1:] or None)))
