"""Opt-in public-page verification for dev4nav, not an agent run or an LLM probe.

Run ``python -m bench.verify_dev4_nav``. It drives local headless Chromium
from each task's start page to its end state by following links, then grades
the page with the probe's own grader. Each task also has negative checks: the
right answer on the start page, and a wrong value on the end page, must both
fail. No model calls.
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

from bench.verify_dev3 import _follow, _grade, _real_page
from bench.script_first import collect_page_evidence
from bench.tasks import tasks_for_split

# Links followed from the start page, in order. Each entry is a CSS selector.
ROUTES = {
    "dev4nav_value_wireshark_srcport": ['a[href="t/tcp.html"], a[href$="/t/tcp.html"]'],
    "dev4nav_value_lua_51": ['a[href*="about.html"]', 'a[href*="versions.html"]'],
    "dev4nav_value_nano_justify": ['a[href*="cheatsheet.html"]'],
    "dev4nav_value_openssh_90": ['a[href="releasenotes.html"]'],
    "dev4nav_value_gradle_java21": ['a[href*="compatibility.html"]'],
    "dev4nav_value_elixir_otp119": ['a[href="compatibility-and-deprecations.html"]'],
    "dev4nav_value_netbsd_90": ['a[href^="formal.html"]'],
    "dev4nav_value_countrycode_iceland": ['a[href="/iceland"]'],
    "dev4nav_title_lua_metatables": ['a[href="manual.html#2.4"]'],
    "dev4nav_title_elixir_genserver": ['a[href="GenServer.html"]'],
    "dev4nav_title_wireshark_capture": ['a[href="ChapterCapture.html"]'],
    "dev4nav_title_putty_pscp": ['a[href*="latest/htmldoc"]', 'a[href^="Chapter5.html"]'],
}

# A plausible wrong value: a neighbouring cell or line. Claimed on the end page, it must grade FAIL.
WRONG = {
    "dev4nav_value_wireshark_srcport": "Unsigned integer (32 bits)",
    "dev4nav_value_lua_51": "20 Feb 2006",
    "dev4nav_value_nano_justify": "Ctrl+J",
    "dev4nav_value_openssh_90": "2022-04-09",
    "dev4nav_value_gradle_java21": "8.4",
    "dev4nav_value_elixir_otp119": "27 - 29",
    "dev4nav_value_netbsd_90": "February 14, 2021",
    "dev4nav_value_countrycode_iceland": "IS",
    "dev4nav_title_lua_metatables": "2.3 – Error Handling",
    "dev4nav_title_elixir_genserver": "GenServer",
    "dev4nav_title_wireshark_capture": "Chapter 5. File Input, Output, And Printing",
    "dev4nav_title_putty_pscp": "Chapter 4: Configuring PuTTY",
}


async def check(browser, task: dict) -> tuple:
    context = await browser.new_context(viewport={"width": 1366, "height": 900})
    page = await context.new_page()
    page.set_default_timeout(45000)
    try:
        start = await page.goto(task["start_url"], wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        start_status = await _real_page(page, start)
        start_evidence = await collect_page_evidence(page)
        answer = task["expected_answer"]
        assert not _grade(task, start_evidence, answer), (task["id"], "start page passed")
        for selector in ROUTES[task["id"]]:
            await _follow(page, selector)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1000)
        await _real_page(page)
        evidence = await collect_page_evidence(page)
        assert " ".join(answer.split()) in " ".join(evidence.text.split()), (
            task["id"], "answer absent from runner evidence", evidence.text[:300])
        assert _grade(task, evidence, answer), (task["id"], "grader rejected the end state", evidence.url)
        wrong = WRONG[task["id"]]
        assert not _grade(task, evidence, wrong), (task["id"], "wrong value accepted", wrong)
        return task["id"], start_status, evidence.url, "PASS", "FAIL", "FAIL"
    finally:
        await context.close()


async def verify(ids: list[str]) -> int:
    tasks = [task for task in tasks_for_split("dev4nav") if not ids or task["id"] in ids]
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
