"""Opt-in public-page verification, not an agent run or an LLM probe.

Run ``python -m bench.verify_heldout2`` to refresh docs/HELDOUT2_VERIFY.md.
Only local headless Chromium and the deterministic evidence grader are used.
Search tasks exercise the site's search UI; demo forms are filled and submitted.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split


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


async def _interact(page, task: dict):
    task_id = task["id"]
    if task_id == "ho2_form_expand_ticket":
        await page.locator('[name="ContactName"]').fill("Alex Example")
        await page.locator('[name="contactnumber"]').fill("012-3456789")
        await page.locator('[name="pickupdate"]').fill("2030-01-15")
        await page.locator('[name="payment"]').select_option("card")
        async with page.expect_navigation() as navigation:
            await page.get_by_role("button", name="Register", exact=True).click()
        return await navigation.value
    if task_id == "ho2_form_calculator_sum":
        # This demo renders the submitted server calculation on the same URL.
        before = await collect_page_evidence(page)
        assert evidence_verdict(task["end_markers"], before, ClaimedEvidence(answer="42")).verdict == "FAIL"
        await page.locator("#number1").fill("17")
        await page.locator("#number2").fill("25")
        await page.locator("#function").select_option("plus")
        async with page.expect_response(lambda r: "/internalapi/simple-calculator" in r.url and r.request.method == "POST") as calculation:
            await page.get_by_role("button", name="Calculate", exact=True).click()
        assert (await calculation.value).status == 200
        await page.get_by_text("42", exact=True).wait_for()
        return None
    if task_id.startswith("ho2_search_"):
        sphinx = task_id == "ho2_search_sphinx_toctree"
        query = "toctree" if sphinx else "blueprints"
        suffix = "directives.html" if sphinx else "blueprints/"
        search = page.locator('input[name="q"]').first
        await search.fill(query)
        async with page.expect_navigation() as navigation:
            await search.press("Enter")
        await _real_page(page, await navigation.value)
        result = page.locator(f'#search-results a[href*="{suffix}"], .search-results a[href*="{suffix}"]').first
        await result.wait_for()
        async with page.expect_navigation() as navigation:
            await result.click()
        return await navigation.value
    markers = task["end_markers"]
    return await page.goto("https://" + markers["host"] + markers["url_contains"], wait_until="domcontentloaded")


async def verify() -> None:
    rows = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(4)

        async def check(task: dict):
            async with semaphore:
                context = await browser.new_context()
                page = await context.new_page()
                page.set_default_timeout(45000)
                try:
                    start = await page.goto(task["start_url"], wait_until="domcontentloaded")
                    start_status = await _real_page(page, start)
                    response = await _interact(page, task)
                    if response is not None:
                        await _real_page(page, response)
                    evidence = await collect_page_evidence(page)
                    answer = task["expected_answer"]
                    # Literal presence, independent of the grader's case/space folding.
                    assert answer in evidence.text, (task["id"], "answer absent from runner evidence", evidence.text[:300])
                    verdict = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=answer))
                    assert verdict.verdict == "PASS", (task["id"], verdict)
                    h1_check = "not a value task"
                    if task["end_markers"].get("answer_in_text"):
                        first_h1 = await page.locator("h1").first.inner_text()
                        assert first_h1.strip(), (task["id"], "no first h1 for negative control")
                        if " ".join(first_h1.split()).casefold() == answer.casefold():
                            h1_check = "same as requested heading"
                        else:
                            negative = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=first_h1))
                            assert negative.verdict == "FAIL", (task["id"], "first h1 accepted", negative)
                            h1_check = "FAIL"
                    print(f"{task['id']}: {start_status}, {page.url}, {verdict.verdict}, h1={h1_check}", flush=True)
                    return task["id"], start_status, page.url, verdict.verdict, h1_check
                finally:
                    await context.close()

        try:
            rows = await asyncio.gather(*(check(task) for task in tasks_for_split("heldout2")))
        finally:
            await browser.close()

    lines = [
        "# Heldout2 public-page verification", "",
        f"Verified {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} with local headless Chromium.", "",
        "This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.",
        "Authored using only AGENTS.md, bench/tasks.py, bench/probe.py, and the evidence grading/collection helpers in bench/script_first.py; no results, failure taxonomy, notes, temporary-directory files, or other branches were read.", "",
        "Mix: 8 navigation, 8 value reports (including 2 title headings), 2 site searches, 2 submitted public demo forms.",
        "All start pages returned HTTP 200 with real content and no challenge indicators. All navigated end pages returned HTTP 200. The calculator stays on its start URL and its calculation POST returned 200.",
        "Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.",
        "For value/form answers different from the first h1, that h1 was separately claimed and had to grade FAIL. The two title tasks explicitly request the heading itself, so that negative control does not apply.",
        "Searches used each site's search form and followed a result. Both forms were filled and submitted; the calculator answer also failed its marker before submission.", "",
        "Reproduce: `python -m bench.verify_heldout2` (public network access; no model calls).", "",
        "| Task id | Start status | End URL | Verdict | First-h1 claim |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {task_id} | {status} | {url} | {verdict} | {negative} |" for task_id, status, url, verdict, negative in rows)
    lines.extend([
        "", "## Candidates dropped before finalization", "",
        "- GNU GPL/coreutils pages: repeated connection resets/timeouts and an HTTP 429 in headless Chromium.",
        "- Python Packaging User Guide site search: no visible matching result appeared within the verification timeout; replaced with Flask's working site search.",
        "- nginx keepalive timeout value: the value was outside the runner's capped trusted text, so it could not be verified by the required grading path.",
        "- RFC directory URL (`/rfc/`): HTTP 404; the task starts at the working RFC Editor home instead.",
    ])
    Path("docs/HELDOUT2_VERIFY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(verify())
