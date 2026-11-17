"""Opt-in public-page verification for dev5title, not an agent run or an LLM probe.

Run ``python -m bench.verify_dev5_title``. It drives local headless Chromium
from each task's start page to its end state by following links, then grades
the page with the probe's own grader. Each task also has negative checks: the
right answer on the start page, and a plausible wrong title on the end page,
must both fail. No model calls.
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
    "dev5_title_tldp_conditionals": ['a[href="chap_07.html"]'],
    "dev5_title_openssl_req": ['a[href$="/man1/openssl-req/"]'],
    "dev5_title_docsrs_deserialize": ['a[href="trait.Deserialize.html"]'],
    "dev5_title_gitlab_ciyaml": ['a[href="/ci/yaml/"]'],
    "dev5_title_scala_control": ['a[href="/scala3/book/control-structures.html"]'],
    "dev5_title_ruby_comparable": ['a[href="./Comparable.html"]'],
    "dev5_title_qt_qstring": ['a[href="qstring.html"]'],
    "dev5_title_fastapi_numeric": ['a[href$="/tutorial/path-params-numeric-validations/"]'],
    "dev5_title_celery_periodic": ['a[href="periodic-tasks.html"]'],
    "dev5_title_meson_deps": ['a[href="Dependencies.html"]'],
    "dev5_title_gentoo_disks": ['a[href="/wiki/Handbook:AMD64/Installation/Disks"]'],
    "dev5_title_gtk_button": ['a[href="class.Button.html"]'],
    "dev5_title_cran_bayes": ['a[href="Bayesian.html"]'],
    "dev5_title_wikisource_raven": ['a[href$="/wiki/The_Raven_(Poe)"]'],
    "dev5_title_leaflet_cluster": ['a[href="plugins.html"]'],
    "dev5_title_gimp_tones": ['a[href$="/tutorials/community/Luminosity_Masks/"]'],
    "dev5_title_celery_whatsnew50": ['a[href="whatsnew-5.0.html"]'],
}

# A plausible wrong title: a neighbouring item, section or chapter. Claimed on the end page, it must grade FAIL.
WRONG = {
    "dev5_title_tldp_conditionals": "Chapter 8. Writing interactive scripts",
    "dev5_title_openssl_req": "openssl-x509 - Certificate display and signing command",
    "dev5_title_docsrs_deserialize": "Trait Deserializer",
    "dev5_title_gitlab_ciyaml": "Get started with GitLab CI/CD",
    "dev5_title_scala_control": "Domain Modeling",
    "dev5_title_ruby_comparable": "module Enumerable",
    "dev5_title_qt_qstring": "QStringList Class",
    "dev5_title_fastapi_numeric": "Path Parameters",
    "dev5_title_celery_periodic": "Calling Tasks",
    "dev5_title_meson_deps": "Build options",
    "dev5_title_gentoo_disks": "Installing the stage file",
    "dev5_title_gtk_button": "GtkToggleButton",
    "dev5_title_cran_bayes": "Bayesian Statistics",
    "dev5_title_wikisource_raven": "The Raven and Other Poems",
    "dev5_title_leaflet_cluster": "PruneCluster",
    "dev5_title_gimp_tones": "Layer Masks",
    "dev5_title_celery_whatsnew50": "Celery 5.7 (Collider)",
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
    tasks = [task for task in tasks_for_split("dev5title") if not ids or task["id"] in ids]
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
