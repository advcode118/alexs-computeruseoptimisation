"""Opt-in, model-free live verification: python -m bench.verify_extdev.

Only Playwright Chromium and the existing deterministic evidence grader run.
The authoring ledger supplies independently derived final URLs. No model client,
inference endpoint, paid API, credentials, or benchmark probe is invoked.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright

from bench.ext_sample import effective_authoring_decisions
from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/results/ext_sample_20261116/authoring_extdev.jsonl"
REPORT = ROOT / "docs/EXTDEV_VERIFY.md"


async def settle(page):
    await page.wait_for_timeout(1800)


async def goto(page, url):
    response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    if response is not None and response.status >= 400:
        raise RuntimeError(f"HTTP {response.status}: {url}")
    await settle(page)


async def click_link(page, suffix):
    link = page.locator(f'a[href$="{suffix}"]:visible').first
    await link.click()
    await settle(page)


async def dismiss_cookies(page):
    for name in ("Accept Default Settings", "Accept All", "Accept all cookies", "Reject All"):
        button = page.get_by_role("button", name=name, exact=True)
        if await button.count() and await button.first.is_visible():
            await button.first.click()


async def reproduce(page, task):
    """Use only start-page navigation and UI actions, never final-page goto."""
    await goto(page, task["start_url"])
    await dismiss_cookies(page)
    task_id = task["id"]
    if task["end_markers"]["host"] == "booking.com":
        dismiss = page.get_by_role("button", name="Dismiss sign-in info.", exact=True)
        try:
            await dismiss.wait_for(state="visible", timeout=3500)
        except PlaywrightTimeoutError:
            pass
        else:
            await dismiss.click()
    if task_id.endswith(("greatamerica_thrill", "frontiercity_family")):
        park, category = (
            ("greatamerica", "Thrill") if task_id.endswith("greatamerica_thrill")
            else ("frontiercity", "Family")
        )
        await click_link(page, "/select-park")
        name = "Visit Six Flags Great America" if park == "greatamerica" else "Visit Frontier City"
        await page.get_by_role("button", name=name, exact=True).click()
        await settle(page)
        await click_link(page, "/" + park + "/attractions")
        await page.locator("#header-filter-category").select_option(label=category, force=True)
    elif task_id.endswith("dota_dlc_cart"):
        search = page.get_by_placeholder("Search the store", exact=True)
        await search.fill("Dota 2")
        await search.press("Enter")
        await settle(page)
        await page.locator('a.search_result_row[href*="/app/570/"]').first.click()
        await settle(page)
        await page.get_by_text("Add all DLC to Cart", exact=True).click()
        await page.get_by_text(re.compile(r"View My Cart")).click()
    elif task_id.endswith("spothero_contact"):
        await click_link(page, "/contact")
    elif task_id.endswith("fiestatexas_events"):
        await click_link(page, "/select-park")
        await page.get_by_role("button", name="Visit Six Flags Fiesta Texas", exact=True).click()
        await settle(page)
        await click_link(page, "/fiestatexas/events")
    elif task_id.endswith("spothero_marketing"):
        await click_link(page, "/careers")
        await page.get_by_role("tab", name=re.compile("Marketing")).click()
        await settle(page)
        await page.get_by_role("link", name="View Role", exact=True).first.click()
    elif task_id.endswith("commuter_benefits"):
        await click_link(page, "/solutions/commuter-benefits")
    elif task_id.endswith(("amazon_puppy_food", "green_xbox_controller")):
        query = "dog food for puppies" if task_id.endswith("amazon_puppy_food") else "Xbox Wireless controller green"
        search = page.locator("#twotabsearchtextbox")
        await search.fill(query)
        await search.press("Enter")
        await settle(page)
        await page.get_by_role("link", name=re.compile(r"4 Stars.*Up")).first.click()
        await settle(page)
        if task_id.endswith("amazon_puppy_food"):
            await page.locator("#s-result-sort-select").select_option("price-asc-rank")
    elif task_id.endswith("booking_parent"):
        await page.locator('a[href*="/content/about"]:visible').first.click()
    elif task_id.endswith("icse_2004_chair"):
        await click_link(page, "history.html")
    elif task_id.endswith("icse_duplicate_statement"):
        await click_link(page, "organization.html")
        await click_link(page, "duplicate.html")
    elif task_id.endswith("cambridge_giddy"):
        await click_link(page, "/thesaurus/")
        search = page.locator("#searchword")
        await search.fill("feel giddy")
        await search.press("Enter")
    elif task_id.endswith("cambridge_sustainability"):
        search = page.locator("#searchword")
        await search.fill("sustainability")
        await search.press("Enter")
        await settle(page)
        await page.get_by_text("in more languages", exact=True).click()
        await page.get_by_text("in French", exact=True).click()
    elif task_id.endswith("booking_la_filters"):
        await page.locator('a[href*="/city/us/los-angeles.html"]:visible').first.click()
    else:
        raise ValueError(f"No reproducer registered: {task_id}")
    await settle(page)


async def grade(page, task, answer):
    if (urlsplit(page.url).hostname or "").removeprefix("www.") == "booking.com":
        await page.wait_for_function(
            """() => {
                const root = document.querySelector('main') || document.body;
                return !!root && !!(root.innerText || root.textContent || '').trim();
            }""",
            timeout=15000,
        )
    evidence = await collect_page_evidence(page)
    verdict = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=answer))
    return verdict.verdict, verdict.reason


def negative_url(task, final_url):
    if task["end_markers"]["host"] == "dictionary.cambridge.org":
        return "https://example.com/"
    return "https://example.com/" if task["start_url"].rstrip("/") == final_url.rstrip("/") else task["start_url"]


async def verify_task(browser, task, final_url):
    row = {"id": task["id"], "key": False, "reproducer": None, "negatives": [], "errors": []}
    context = await browser.new_context()
    page = await context.new_page()
    page.set_default_timeout(15000)
    try:
        # A cart URL cannot recreate cookies. Seed it through the actual UI,
        # then check the final URL by direct navigation in that same session.
        if task["id"].endswith("dota_dlc_cart"):
            await reproduce(page, task)
        elif task["end_markers"]["host"] == "amazon.com":
            await goto(page, task["start_url"])
        await goto(page, final_url)
        if task["id"].endswith("steam_daily_players"):
            await page.get_by_text("By Current Players", exact=True).click()
            await page.get_by_text("By Daily Players", exact=True).click()
            await settle(page)
        verdict, reason = await grade(page, task, task["expected_answer"])
        row["key"] = verdict == "PASS"
        if not row["key"]:
            row["errors"].append(f"key: {verdict}: {reason}")
        wrong = "An unrelated answer, not the requested value"
        verdict, reason = await grade(page, task, wrong)
        row["negatives"].append(verdict == "FAIL")
        if verdict != "FAIL":
            row["errors"].append(f"wrong value: {verdict}: {reason}")
        await goto(page, negative_url(task, final_url))
        verdict, reason = await grade(page, task, task["expected_answer"])
        row["negatives"].append(verdict == "FAIL")
        if verdict != "FAIL":
            row["errors"].append(f"start-page decoy: {verdict}: {reason}")
    except Exception as exc:
        row["errors"].append(f"key/negative exception: {type(exc).__name__}: {str(exc).splitlines()[0]}")
    finally:
        await context.close()
    if task["reproducer"] == "script":
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(15000)
        row["reproducer"] = False
        try:
            await reproduce(page, task)
            verdict, reason = await grade(page, task, task["expected_answer"])
            row["reproducer"] = verdict == "PASS"
            if verdict != "PASS":
                row["errors"].append(f"reproducer: {verdict}: {reason}")
        except Exception as exc:
            row["errors"].append(f"reproducer exception: {type(exc).__name__}: {str(exc).splitlines()[0]}")
        finally:
            await context.close()
    return row


def summary(rows, tasks):
    key_count = sum(row["key"] for row in rows)
    scripts = sum(task["reproducer"] == "script" for task in tasks)
    repro_count = sum(row["reproducer"] is True for row in rows)
    negatives = sum(sum(row["negatives"]) for row in rows)
    return [
        f"Key checks: {key_count}/{len(tasks)} PASS",
        f"Reproducers: {repro_count}/{scripts} PASS; {len(tasks) - scripts} none",
        f"Negatives: {negatives}/{2 * len(tasks)} correctly FAIL",
        f"Partial keys: {sum(task['key_scope'] == 'partial' for task in tasks)}/{len(tasks)}",
    ]


def write_report(rows, tasks, ledger):
    counts = Counter(task["source"] for task in tasks)
    excluded = Counter(row["reason"] for row in ledger if row["disposition"] == "excluded")
    uncheckable = Counter(row["note"].split(":", 1)[0] for row in ledger if row.get("reason") == "no_checkable_key")
    lines = [
        "# extdev model-free verification", "",
        f"Generated {datetime.now(timezone.utc).isoformat()}. Run `python -m bench.verify_extdev`.", "",
        "Only local Playwright bundled Chromium (headless, default fresh contexts, matching the existing verifiers) and the unchanged deterministic grader run. No probe/model/API call.", "",
        "## Authoring and shortfall", "",
        f"The expanded reserve contains 442 extdev candidates. There are {len(ledger)} effective authoring decisions; the walk stops at exactly 40 accepted tasks. Descriptions remain verbatim and all text_edits are empty. All retained keys were derived on live pages rather than trusting source reference answers.", "",
        "Source quotas were attempted in Mind2Web-Live, WebWalkerQA, WebVoyager, AssistantBench order, then shortfalls filled in that order with Mind2Web train last. Only accepted tasks consume the three-per-site cap. Seed, ranking and site assignment are unchanged. The original 50 STEP-2 ledger lines are preserved, followed by superseding revised decisions for all five former multi-page exclusions. Statistics use the latest decision per source/id, not historical exclusions.", "",
        f"Kept by source: `{dict(counts)}`. Kinds: `{dict(Counter(t['kind'] for t in tasks))}`.",
        f"Manual exclusions: `{dict(excluded)}`. See [the complete ledger](results/ext_sample_20261116/authoring_extdev.jsonl) for individual decisions and sub-reasons.", "",
        f"no_checkable_key sub-reasons: `{dict(uncheckable)}`. Duplicate exclusions name their already-accepted task ID. Duplicate matching normalizes case/punctuation/whitespace and removes trailing site/domain/brand suffixes, including Steam's public brand alias.", "",
        "## Key policy and limitations", "",
        "Factual multi-page answers are retained. Compound/multi-page tasks use one specific literal fragment plus its page URL as a partial key; other fragments are audit-only unchecked_fragments, never checked by grading or sent to prompts. A partial PASS does not verify the full answer. Only truly computed answers and explicitly authorized ungradeable UI end states remain no_checkable_key. Search URLs rejected by is_search_results_url and submitted values without readable traces are not replaced by upstream/incomplete keys.", "",
        "The five re-admitted tasks check final fragments on the 2022 Rovio report, 2023 sustainability report, and Ironhide articles 370, 98 and 307. Their other-page facts stay unchecked. Ironhide's April 2023 source is a free-game promotion, not a new release; its source wording is retained with this limitation in the ledger. Previously provisional Rovio campaign/Topgolf fills are skipped at the accepted-site cap after re-admission; no original kept task is dropped.", "",
        "Dota's cart key requires session state: the verifier first genuinely adds all cartable DLC via the UI, then directly reloads the cart URL for the key check. A separate fresh context runs the reported reproducer. No cookies are persisted and checkout is never submitted. Cart prices are not keyed.", "",
        "Steam's daily-player view has visible selected-metric text but no persistent deep link: the key check loads the charts page directly, then selects By Daily Players before grading. Reload resets it to By Current Players. This is a UI-state key, not a player-count or game-ranking quotation. Amazon key checks establish a normal start-page session before direct final-URL navigation; no browser fingerprints, headers or cookies are forged. Reproducer none is used for archive/article discovery or heavy/legacy dynamic UI.", "",
        "The new Airbnb tiny-home search uses the United States as one permissible location for anywhere, with one adult, two pets and the next April 10–12 (2027). The castle query encodes Europe, a week in December (next month at authoring), and the price ceiling, not a live nightly quotation. Eventbrite's exercise query encodes the next July 10–31 (2027). These keys check search criteria, not available inventory or result counts; relative-month keys require refresh after November 2026.", "",
        "The first expanded-set full run found five key failures (35/40 keys, 12/13 reproducers) and three blocked Cambridge root decoys (77/80 negatives). Its unmerged evidence is preserved in verification_extdev_step3_initial.jsonl. Five append-only rekeyed ledger lines retain that key history. Hugging Face's full AutoClass example lies beyond the unchanged 8,000-character evidence window; the official TensorFlow Serving guide supplies the literal from_pt=True flag in readable evidence, with other steps kept unchecked. Booking's About page supplies the parent-company fact in main content rather than an excluded homepage footer. Airbnb keys couple their COMPLETE filter URLs to main-content property-type captions rather than excluded date-header text. Amazon's rating-facet marker tolerates query ordering and still requires /s plus the complete green-controller name. No grading code changed.", "",
        "Six Flags keys encode park and selected category, not fluctuating operating hours or ride availability. Booking's Los Angeles directory exposes stable filter labels without dated availability or prices being keyed. The Times Square page preserves hotel/class=4 filtering; two-adult occupancy is unchecked. Airbnb's legacy category URL still renders mansions in Europe; Any month and 3 guests are recorded but unchecked. Source 2024 flexible-date parameters are not used as a fixed stay. ICSE's historical source uses HTTP, preserved verbatim.", "",
        "## Prompt isolation audit", "",
        "bench/browser_use_arm.py:task_text selects only description/start_url and calls bench.tasks.task_message. bench/harness.py builds user messages through task_message(description, start_url); run_task discards expected_answer/judge_prompt. The live script_first runtime receives empty end_markers. No whole-task-dictionary prompt serialization was found. Provenance, key_scope and unchecked_fragments stay outside those inputs. No prompt or grading code was changed.", "",
        "## Results", "", "```text", *summary(rows, tasks), "```", "",
        "A second full run passed all 40 keys but encountered the late Booking sign-in overlay and three blocked Cambridge neighboring-article decoys (11/13 reproducers, 77/80 negatives); it is preserved in verification_extdev_step3_keyfix.jsonl. Booking reproducers now await/dismiss the observed optional sign-in overlay, then click genuine homepage links: About Booking.com or Los Angeles hotels. No final-page URL is injected by a reproducer. Cambridge second-page requests repeatedly returned HTTP 403, so its second control deliberately uses an unrelated host rather than counting blocked content as a successful negative. Each Cambridge task still has a wrong-answer negative on its actual, readable final article.", "",
        "Each negative is a wrong answer on the final page and the correct answer on a live decoy. The start page is normally the decoy; Cambridge and tasks that start on their final page use example.com as a wrong-host control. Exceptions are failures, never successful negative controls. Results above are one fresh full run over all 40 final tasks after key/reproducer revisions, not merged targeted rechecks. Earlier full attempts are retained explicitly, not presented as passing runs.", "",
        "| Task | Direct key | Reproducer | Negative controls |", "|---|---|---|---|",
    ]
    for row in rows:
        repro = "none" if row["reproducer"] is None else "PASS" if row["reproducer"] else "FAIL"
        lines.append(f"| {row['id']} | {'PASS' if row['key'] else 'FAIL'} | {repro} | {sum(row['negatives'])}/2 |")
    errors = [(row["id"], err) for row in rows for err in row["errors"]]
    if errors:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{task_id}`: {error}" for task_id, error in errors)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main(ids=()):
    tasks = tasks_for_split("extdev")
    if ids:
        unknown = set(ids) - {task["id"] for task in tasks}
        if unknown:
            raise ValueError(f"Unknown task IDs: {sorted(unknown)}")
        tasks = [task for task in tasks if task["id"] in ids]
    ledger = effective_authoring_decisions([json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()])
    finals = {row["task_id"]: row["final_url"] for row in ledger if row["disposition"] == "kept"}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(3)

        async def run(task):
            async with semaphore:
                row = await verify_task(browser, task, finals[task["id"]])
                print(json.dumps(row, ensure_ascii=False), flush=True)
                return row

        rows = await asyncio.gather(*(run(task) for task in tasks))
        await browser.close()
    if not ids:
        write_report(rows, tasks, ledger)
        (LEDGER.parent / "verification_extdev.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )
    print("\n".join(summary(rows, tasks)), flush=True)
    return 0 if all(row["key"] and row["reproducer"] is not False and len(row["negatives"]) == 2 and all(row["negatives"]) and not row["errors"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
