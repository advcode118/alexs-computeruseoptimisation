"""Opt-in public-page verification for heldout3a. Not an agent run or an LLM probe.

Run ``python -m bench.verify_heldout3_a``. Headless Chromium does each task
without a model, then the real evidence grader scores the page. A wrong page
and a wrong value must fail.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split


def _open_url(task: dict) -> str:
    markers = task["end_markers"]
    token = markers["url_contains"]
    if token.startswith("/"):
        return "https://" + markers["host"] + token
    path = markers["path_suffix"]
    if not path.startswith("/"):
        path = "/" + path
    url = "https://" + markers["host"] + path
    if token.startswith("#"):
        return url + token
    if token not in url:
        return url + ("&" if "?" in url else "?") + token
    return url


async def _real_page(page, response) -> int:
    assert response is not None and response.status == 200, (
        page.url, response.status if response else None
    )
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


async def _click(page, selector: str):
    link = page.locator(selector).first
    await link.wait_for(state="attached")
    async with page.expect_navigation(wait_until="domcontentloaded", timeout=45000):
        await link.click()


async def _search(page, query: str, href_part: str):
    box = page.locator('input[name="q"]').first
    await box.wait_for()
    await box.fill(query)
    async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
        await box.press("Enter")
    if href_part in page.url and "search" not in urlsplit(page.url).path.casefold():
        return
    link = page.locator(
        f'#search-results a[href*="{href_part}"], .search li a[href*="{href_part}"]'
    ).first
    await link.wait_for(timeout=20000)
    async with page.expect_navigation(wait_until="domcontentloaded", timeout=45000):
        await link.click()


async def _submit_absent(page, task: dict):
    evidence = await collect_page_evidence(page)
    assert task["expected_answer"] not in (evidence.text or ""), task["id"]
    verdict = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=task["expected_answer"]))
    assert verdict.verdict == "FAIL", (task["id"], "answer already passed before submit", verdict)


async def _interact(page, task: dict):
    task_id = task["id"]
    if task_id == "ho3a_nav_man_execve":
        await _click(page, 'a[href$="dir_section_2.html"]')
        await _click(page, 'a[href$="/execve.2.html"]')
        return None
    if task_id == "ho3a_nav_freebsd_jails":
        await _click(page, 'a[href="https://docs.freebsd.org/en/books/handbook/"]')
        await _click(page, 'a[href*="/books/handbook/jails/"]')
        return None
    if task_id == "ho3a_nav_ecma_script":
        await _click(page, 'a[href*="/publications-and-standards/standards/"]')
        await _click(page, 'a[href*="/standards/ecma-262"]')
        return None
    if task_id == "ho3a_nav_llvm_parser":
        await _click(page, 'a[href="https://llvm.org/docs/"]')
        await _click(page, 'a[href*="LangImpl02.html"]')
        return None
    if task_id == "ho3a_nav_julia_missing":
        await _click(page, 'a[href="https://docs.julialang.org/"]')
        await _click(page, 'a[href*="/manual/missing/"]')
        return None
    if task_id == "ho3a_nav_cmake_library":
        await _click(page, 'a[href="https://cmake.org/documentation/"]')
        await _click(page, 'a[href$="/cmake/help/latest/"]')
        await _click(page, 'a[href$="cmake-commands.7.html"]')
        await _click(page, 'a[href$="/command/add_library.html"]')
        return None
    if task_id == "ho3a_nav_haskell_expressions":
        await _click(page, 'a[href$="/documentation/"]')
        await _click(page, 'a[href*="onlinereport/haskell2010/"]')
        await _click(page, 'a[href*="haskellch3.html"]')
        return None
    if task_id == "ho3a_nav_lua_coroutines":
        await _click(page, 'a[href$="/docs.html"]')
        await _click(page, 'a[href$="/manual/5.5/"]')
        await _click(page, 'a[href*="manual.html#2.6"]')
        return None
    if task_id == "ho3a_search_llvm_lexicon":
        await _search(page, "Lexicon", "Lexicon.html")
        return None
    if task_id == "ho3a_search_kernel_sysrq":
        await _search(page, "sysrq", "sysrq.html")
        return None
    if task_id == "ho3a_search_cmake_custom_target":
        await _search(page, "custom target", "add_custom_target.html")
        return None
    if task_id == "ho3a_search_debian_chmod":
        box = page.locator('input[name="q"]').first
        await box.fill("chmod")
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
            await box.press("Enter")
        return None
    if task_id == "ho3a_form_bonigarcia_received":
        await page.locator('[name="my-text"]').fill("Ada")
        await _submit_absent(page, task)
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
            await page.get_by_role("button", name="Submit").click()
        return None
    if task_id == "ho3a_form_bonigarcia_login":
        await page.locator('[name="username"]').fill("user")
        await page.locator('[name="password"]').fill("user")
        await _submit_absent(page, task)
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
            await page.get_by_role("button", name="Submit").click()
        return None
    if task_id == "ho3a_form_httpbingo_type":
        await page.goto("https://httpbingo.org/forms/post", wait_until="domcontentloaded")
        await page.locator('[name="custname"]').fill("Ada Example")
        await page.locator('[name="custtel"]').fill("555-0100")
        await page.locator('[name="custemail"]').fill("ada@example.com")
        await page.locator('[name="size"][value="medium"]').check()
        await _submit_absent(page, task)
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
            await page.locator("button, input[type=submit]").first.click()
        return None
    if task_id == "ho3a_form_globalsqa_sent":
        await page.goto("https://www.globalsqa.com/samplepagetest/", wait_until="domcontentloaded")
        await page.locator("#g2599-name").fill("Ada Example")
        await page.locator("#g2599-email").fill("ada@example.com")
        await page.locator("textarea[name='g2599-comment']").fill("Hello from the checker")
        await _submit_absent(page, task)
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
            await page.locator("form button, form input[type=submit]").last.click()
        return None
    if task_id == "ho3a_title_freebsd_handbook":
        await _click(page, 'a[href="https://docs.freebsd.org/en/books/handbook/"]')
        return None
    if task_id == "ho3a_title_debian_policy":
        await _click(page, 'a[href*="/doc/devel-manuals"]')
        await _click(page, 'a[href$="/doc/debian-policy/"]')
        return None
    if task_id == "ho3a_title_ietf_intro":
        await _click(page, 'a[href*="/about/introduction"]')
        return None
    opened = await page.goto(_open_url(task), wait_until="domcontentloaded")
    await _real_page(page, opened)
    return None


def _slash_variant(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path[:-1] or "/" if parts.path.endswith("/") else parts.path + "/"
    return parts._replace(path=path).geturl()


async def _js_source_lacks_answer(browser, url: str, answer: str) -> None:
    context = await browser.new_context(java_script_enabled=False)
    page = await context.new_page()
    page.set_default_timeout(30000)
    try:
        await page.goto(url, wait_until="domcontentloaded")
        html = await page.content()
        assert answer.casefold() not in html.casefold(), (url, "answer was in the no-script HTML")
    finally:
        await context.close()


async def verify() -> None:
    rows = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(3)

        async def check(task: dict):
            async with semaphore:
                context = await browser.new_context()
                page = await context.new_page()
                page.set_default_timeout(45000)
                try:
                    start = await page.goto(task["start_url"], wait_until="domcontentloaded")
                    start_status = await _real_page(page, start)
                    await _interact(page, task)
                    if task["id"].startswith("ho3a_js_"):
                        await page.wait_for_timeout(1500)
                        await _js_source_lacks_answer(browser, page.url.split("#")[0], task["expected_answer"])
                    evidence = await collect_page_evidence(page)
                    answer = task["expected_answer"]
                    assert answer in (evidence.text or ""), (
                        task["id"], "answer absent", page.url, (evidence.text or "")[:240]
                    )
                    verdict = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=answer))
                    assert verdict.verdict == "PASS", (task["id"], page.url, verdict)
                    wrong_value = evidence_verdict(
                        task["end_markers"], evidence, ClaimedEvidence(answer="not-the-right-value")
                    )
                    assert wrong_value.verdict == "FAIL", (task["id"], "wrong value passed", wrong_value)
                    wrong_page = evidence_verdict(
                        task["end_markers"],
                        replace(evidence, url="https://example.com/not-the-right-page"),
                        ClaimedEvidence(answer=answer),
                    )
                    assert wrong_page.verdict == "FAIL", (task["id"], "wrong page passed", wrong_page)
                    slashed = evidence_verdict(
                        task["end_markers"],
                        replace(evidence, url=_slash_variant(evidence.url)),
                        ClaimedEvidence(answer=answer),
                    )
                    assert slashed.verdict == "PASS", (task["id"], "slash variant failed", evidence.url, slashed)
                    if "#" not in evidence.url:
                        hashed = evidence_verdict(
                            task["end_markers"],
                            replace(evidence, url=evidence.url + "#section"),
                            ClaimedEvidence(answer=answer),
                        )
                        assert hashed.verdict == "PASS", (task["id"], "fragment failed", hashed)
                    h1_check = "not applicable"
                    h1 = (evidence.h1 or "").strip()
                    if task["id"].startswith("ho3a_value_"):
                        assert h1, (task["id"], "value page has no h1")
                        assert answer.casefold() not in h1.casefold(), (task["id"], h1)
                    if h1 and answer.casefold() not in h1.casefold():
                        negative = evidence_verdict(
                            task["end_markers"], evidence, ClaimedEvidence(answer=h1)
                        )
                        assert negative.verdict == "FAIL", (task["id"], "first h1 accepted", negative)
                        h1_check = "FAIL"
                    elif h1:
                        h1_check = "heading is the answer"
                    print(f"{task['id']}: {start_status}, {page.url}, {verdict.verdict}, h1={h1_check}", flush=True)
                    return task["id"], start_status, page.url, verdict.verdict, h1_check
                finally:
                    await context.close()

        try:
            rows = await asyncio.gather(*(check(task) for task in tasks_for_split("heldout3a")))
        finally:
            await browser.close()

    lines = [
        "# Heldout3a public-page verification", "",
        f"Verified {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} with local headless Chromium.", "",
        "This is page and marker validation, not an agent benchmark. No model calls and no bench probes were run.",
        "Each task was done in headless Chromium, then graded with evidence_verdict.",
        "A wrong value and a wrong host failed for every task. Directory URLs also passed with the trailing slash toggled, and pages without a required fragment passed with an added fragment.",
        "Value answers are not the first h1. JavaScript tasks were absent from the no-script HTML.", "",
        "Reproduce: `python -m bench.verify_heldout3_a` (public network; no model calls).", "",
        "| Task id | Start status | End URL | Verdict | First-h1 claim |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {task_id} | {status} | {url} | {verdict} | {negative} |"
        for task_id, status, url, verdict, negative in rows
    )
    lines.extend([
        "", "## Candidates dropped before finalization", "",
        "- ISO Open Browsing Platform: Cloudflare challenge in headless Chromium.",
        "- packages.debian.org search: an interstitial challenge page.",
        "- GNU libc manual and MicroPython docs: HTTP 403.",
        "- computer-database.gatling.io: the name did not resolve.",
        "- Maven Central artifact page: HTTP 403.",
        "- Matplotlib's search field stayed hidden, so it was not used as a site search.",
        "- Godot and MongoDB doc search did not expose a result link in time.",
        "- MySQL's search left for search.oracle.com, outside the a–m domain rule.",
        "- MongoDB's BSON size sentence sat past the grader's text cap.",
        "- angular.dev, Ant Design, MUI, Ionic, Chakra, Lit, and Elm already contained the sample string in the no-script HTML, so they were not used as script-only pages.",
    ])
    Path("docs/HELDOUT3A_VERIFY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(verify())
