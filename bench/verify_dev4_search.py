"""Model-free task author verification; never imported by the live strategy.

Run through probe_slot.sh. Checks the unchanged grader at start, search
results and destination. Saves every attempt, including failures, as JSONL.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter

from playwright.async_api import async_playwright

from bench.script_first import collect_page_evidence
from bench.tasks_dev4_search import DEV4_SEARCH_TASKS
from bench.verify_dev3 import _grade, _real_page


# Author-only routes: all begin at the task start and submit the site's search.
ROUTES = [
    ('input[name="keywords"]', "ripgrep", None),
    ('input[name="keywords"]', "jq", None),
    ('input[name="search"]', "Manual:Job queue", None),
    ('input[name="search"]', "Help:Namespaces", None),
    ('input[name="q"]', "selectors", None),
    ('input[name="q"]', "requests responses", None),
    ('input[name="q"]', "units quantities", None),
    ('input[name="q"]', "data tables", None),
    ('input[data-md-component="search-query"]', "validators", 'label[for="__search"]'),
    ('input[data-md-component="search-query"]', "serialization", 'label[for="__search"]'),
    ('input[data-md-component="search-query"]', "background tasks", 'label[for="__search"]'),
    ('input[data-md-component="search-query"]', "cors", 'label[for="__search"]'),
]


async def check(browser, task, route):
    started = perf_counter()
    row = {"task_id": task["id"], "ok": False}
    context = await browser.new_context(viewport={"width": 1366, "height": 900})
    page = await context.new_page()
    page.set_default_timeout(20000)
    try:
        response = await page.goto(task["start_url"], wait_until="domcontentloaded")
        await _real_page(page, response)
        answer = task["expected_answer"]
        assert not _grade(task, await collect_page_evidence(page), answer), "start passed"
        box, query, trigger = route
        if trigger:
            await page.locator(trigger).first.click()
        field = page.locator(box + ":visible").first
        if "ubuntu" in task["id"]:
            await page.locator('select[name="suite"]').first.select_option("noble")
        await field.fill(query)
        if not trigger:
            await field.press("Enter")
        path = task["end_markers"]["path_suffix"]
        await page.wait_for_function("path => location.pathname.endsWith(path) || [...document.querySelectorAll('a[href]')].some(a => a.href.includes(path) && a.getClientRects().length)", arg=path)
        evidence = await collect_page_evidence(page)
        # An exact-title search may legitimately redirect straight to the article.
        redirected = _grade(task, evidence, answer)
        if not redirected:
            assert not _grade(task, evidence, answer), "results passed"
            href = await page.evaluate("path => [...document.querySelectorAll('a[href]')].find(a => a.href.includes(path) && a.getClientRects().length).getAttribute('href')", path)
            await page.locator('a[href=' + json.dumps(href) + ']:visible').first.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_function("() => document.body.innerText.length > 100")
        await _real_page(page)
        evidence = await collect_page_evidence(page)
        assert _grade(task, evidence, answer), f"end rejected: {evidence.url}"
        assert answer.casefold() in (evidence.title + ' ' + evidence.h1 + ' ' + evidence.text).casefold(), "title absent"
        row.update(ok=True, url=evidence.url, start_rejected=True, search_redirect=redirected)
    except Exception as exc:
        row.update(error=str(exc)[:1200], url=page.url)
    finally:
        row["wall_s"] = round(perf_counter() - started, 3)
        await context.close()
    return row


async def main(output, ids):
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for task, route in zip(DEV4_SEARCH_TASKS, ROUTES):
                if ids and task["id"] not in ids:
                    continue
                row = await check(browser, task, route)
                rows.append(row)
                with output.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
                print(json.dumps(row), flush=True)
        finally:
            await browser.close()
    passed = sum(row["ok"] for row in rows)
    print(f"TOTAL {passed}/{len(rows)} passed", flush=True)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.output, args.ids)))
