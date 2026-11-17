"""Seal heldout4 with live Playwright observations and the byte-pinned grader.

No models are used. Each invocation is an independent run; existing output
files are never overwritten and results are never merged across runs.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from bench import grade
from bench.ext_sample import effective_authoring_decisions
from bench.tasks import tasks_for_split

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/ext_sample_20261116"
LEDGER = RESULTS / "authoring_heldout4.jsonl"
GRADER_SHA = "7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24"
WRONG_ANSWER = "deliberatelyincorrectbenchmarkvalue"
DECOY = "https://example.com/"


@dataclass
class Observation:
    url: str
    text: str = ""
    selector_text: str = ""
    title: str = ""
    channels: list = field(default_factory=list)
    selector_checks: dict = field(default_factory=dict)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_ledger():
    return effective_authoring_decisions(
        json.loads(line) for line in LEDGER.read_text().splitlines() if line
    )


async def settle(page):
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    await page.wait_for_function(
        "() => !!document.body && !!document.body.innerText.trim()", timeout=15000
    )


async def goto(page, url):
    response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    if response is not None and response.status >= 400:
        raise RuntimeError(f"HTTP {response.status}: {url}")
    await settle(page)


async def run_steps(page, steps, artifact_dir, task_id):
    artifacts = []
    for index, step in enumerate(steps):
        action = step["action"]
        if action == "wait":
            await page.wait_for_timeout(step["value"])
            continue
        if action == "pdf":
            path = artifact_dir / f"{task_id}_{index}.pdf"
            data = await page.pdf(path=str(path), landscape=True, print_background=True)
            artifacts.append({"path": str(path.relative_to(ROOT)), "bytes": len(data),
                              "sha256": hashlib.sha256(data).hexdigest(),
                              "media_type": "application/pdf"})
            continue
        locator = (
            page.locator(step["selector"]).first if "selector" in step else
            page.get_by_role(step.get("role", "button"), name=re.compile(step["name"])).first
        )
        if step.get("optional") and not await locator.is_visible():
            continue
        if action == "click" and step.get("popup"):
            async with page.context.expect_page() as popup:
                await locator.click()
            page = await popup.value
            await page.wait_for_load_state("domcontentloaded")
        elif action == "click":
            await locator.click()
        elif action == "fill":
            await locator.fill(step["value"])
        elif action == "press":
            await locator.press(step["value"])
        elif action == "select":
            await locator.select_option(step["value"])
        elif action == "select_label":
            await locator.select_option(label=step["value"])
        elif action == "hover":
            await locator.hover()
        elif action == "check":
            await locator.check()
        elif action == "uncheck":
            await locator.uncheck()
        else:
            raise ValueError(f"Unsupported reproducer action: {action}")
        if page.context.pages[-1] != page:
            page = page.context.pages[-1]
            await page.wait_for_url(lambda url: str(url) != "about:blank")
        await settle(page)
    return page, artifacts


async def observe(page, task):
    title = await page.title()
    if re.search(r"just a moment|access denied|verify you are human|captcha", title, re.I):
        raise RuntimeError(f"Site challenge: {title}")
    challenge = page.locator('iframe[title="Verification system"]')
    if await challenge.count() and await challenge.first.is_visible():
        raise RuntimeError("Visible site-verification iframe blocks the requested state")
    body = await page.locator("body").inner_text()
    if re.search(r"enter the characters seen in the image|pardon our interruption|"
                 r"verify (?:that )?you are (?:a )?human|press & hold", body[:500], re.I):
        raise RuntimeError("Site-verification page rather than the requested state")
    texts = [body]
    channels = ["rendered_body"]
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            element = await frame.frame_element()
            if await element.is_visible():
                text = await frame.locator("body").inner_text(timeout=3000)
                if text.strip():
                    texts.append(text)
                    channels.append("rendered_child_frame")
        except Exception:
            continue
    if "link_attribute_evidence" in task.get("grader_flags", []):
        hrefs = await page.locator("a[href]").evaluate_all(
            "els => els.filter(e => e.getClientRects().length && "
            "getComputedStyle(e).visibility !== 'hidden').map(e => e.href)"
        )
        texts.extend(hrefs)
        channels.append("visible_link_targets")
    checks = {}
    for part, selector in task.get("answer_part_selectors", {}).items():
        locator = page.locator(selector).first
        value = ""
        if await locator.count():
            value = await locator.evaluate("""e => {
                const v = e.tagName === 'OPTION' ? e.parentElement : e;
                if (!v.getClientRects().length || getComputedStyle(v).visibility === 'hidden') return '';
                return 'value' in e && e.tagName !== 'OPTION' ? e.value : e.innerText;
            }""")
        checks[part] = " ".join(value.casefold().split()) == " ".join(part.casefold().split())
        texts.append(value)
    if checks:
        channels.append("visible_selected_controls")
    selector = task.get("end_markers", {}).get("answer_equals_selector", "")
    selector_text = ""
    if selector:
        locator = page.locator(selector).first
        if await locator.count():
            selector_text = await locator.evaluate("e => 'value' in e ? e.value : e.innerText")
    return Observation(page.url, "\n".join(texts), selector_text, title, channels, checks)


def grade_observation(task, observation, answer):
    ok, reason, _, _ = grade.grade_observation(
        task, observation.url, observation.text, answer=answer,
        selector_text=observation.selector_text,
    )
    if ok and not all(observation.selector_checks.values()):
        return False, "required persisted/selected UI value does not match"
    return ok, reason


def control(task, observation, answer, name):
    ok, reason = grade_observation(task, observation, answer)
    return {"name": name, "correctly_failed": not ok and "UNKNOWN" not in reason,
            "reason": reason, "observed_url": observation.url}


async def key_observation(page, task, decision, artifact_dir):
    artifacts = []
    setup = decision.get("key_setup")
    if setup:
        if isinstance(setup, dict):
            await goto(page, setup["url"])
            page, made = await run_steps(page, setup["steps"], artifact_dir, task["id"] + "_setup")
        else:
            await goto(page, task["start_url"])
            steps = decision["repro_steps"]
            if setup == "ua_egift_card":
                steps = steps[:-1]
            elif setup != "gamestop_two_ps50":
                raise ValueError(f"Unsupported key setup: {setup}")
            page, made = await run_steps(page, steps, artifact_dir, task["id"] + "_setup")
        artifacts.extend(made)
    downloads = []
    downloaded = asyncio.Event()

    def received(download):
        downloads.append(download)
        downloaded.set()

    page.on("download", received)
    try:
        await goto(page, decision["final_url"])
    except Exception as exc:
        if "Download is starting" not in str(exc):
            raise
        await asyncio.wait_for(downloaded.wait(), timeout=15)
        download = downloads[-1]
        path = artifact_dir / f"{task['id']}_download"
        await download.save_as(path)
        artifacts.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                          "sha256": sha(path), "observed_url": download.url})
        return Observation(download.url, channels=["browser_download_event"]), artifacts
    page, made = await run_steps(page, decision.get("key_steps", []), artifact_dir, task["id"] + "_key")
    artifacts.extend(made)
    return await observe(page, task), artifacts


async def verify_task(browser, task, decision, decoy, artifact_dir):
    row = {"id": task["id"], "key": False, "key_reason": "not checked",
           "reproducer": "NONE", "grader_flags": task["grader_flags"],
           "negatives": [control(task, decoy, task["full_answer"], "wrong_host")], "errors": []}
    for phase in ("key", "reproducer"):
        if phase == "reproducer" and task["reproducer"] == "none":
            continue
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(15000)
        try:
            if phase == "key":
                observation, artifacts = await key_observation(page, task, decision, artifact_dir)
            else:
                await goto(page, task["start_url"])
                page, artifacts = await run_steps(page, decision["repro_steps"], artifact_dir, task["id"] + "_repro")
                observation = await observe(page, task)
            ok, reason = grade_observation(task, observation, task["full_answer"])
            row[phase + "_reason"] = reason
            row[phase + "_observation"] = asdict(observation)
            row[phase + "_artifacts"] = artifacts
            if phase == "key":
                row["key"] = ok
                row["negatives"].append(control(task, observation, WRONG_ANSWER, "wrong_answer"))
            else:
                row["reproducer"] = "PASS" if ok else "FAIL"
                if not ok and "page text" in reason and "pdf_evidence" in task["grader_flags"]:
                    row["reproducer"] = "BLOCKED_BY_GRADER"
        except Exception as exc:
            reason = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
            row[phase + "_reason"] = reason
            row["errors"].append({"phase": phase, "error": reason})
            if phase == "reproducer":
                row["reproducer"] = "ERROR"
        finally:
            await context.close()
    return row


def summarize(tasks, decisions, rows):
    exclusions = [d for d in decisions if d["disposition"] == "excluded"]
    scripts = sum(t["reproducer"] == "script" for t in tasks)
    statuses = Counter(r["reproducer"] for r in rows)
    negatives = [c for row in rows for c in row["negatives"]]
    return {
        "tasks": len(tasks), "keys_pass": sum(r["key"] for r in rows), "scripts": scripts,
        "reproducer_statuses": dict(statuses), "reproducer_none": len(tasks) - scripts,
        "reproducer_pass_rate": statuses["PASS"] / scripts if scripts else None,
        "negative_controls": len(negatives), "negatives_failed": sum(c["correctly_failed"] for c in negatives),
        "tasks_with_negative": sum(any(c["correctly_failed"] for c in r["negatives"]) for r in rows),
        "full": sum(t["key_scope"] == "full" for t in tasks),
        "partial": sum(t["key_scope"] == "partial" for t in tasks),
        "sources": dict(Counter(t["source"] for t in tasks)),
        "kinds": dict(Counter(t["kind"] for t in tasks)),
        "grader_flags": dict(Counter(f for t in tasks for f in t["grader_flags"])),
        "exclusions": dict(Counter(d["reason"] for d in exclusions)),
        "no_checkable_key": dict(Counter(
            "computed" if "computed:" in d["note"] else "ungradeable_end_state"
            for d in exclusions if d["reason"] == "no_checkable_key"
        )),
        "drop_candidates": [r["id"] for r in rows if not r["key"] or
                            not r["negatives"] or not all(c["correctly_failed"] for c in r["negatives"])],
        "reproducer_problems": [r["id"] for r in rows if r["reproducer"] not in {"PASS", "NONE"}],
    }


async def main(output, concurrency):
    if sha(ROOT / "bench/grade.py") != GRADER_SHA:
        raise RuntimeError("Grader hash does not match the seal pin")
    if output.exists():
        raise FileExistsError(f"Preserve prior run evidence; choose another --output: {output}")
    tasks = tasks_for_split("heldout4")
    decisions = read_ledger()
    by_id = {d["task_id"]: d for d in decisions if d["disposition"] == "kept"}
    artifact_dir = RESULTS / (output.stem + "_artifacts")
    artifact_dir.mkdir(exist_ok=False)
    metadata = {"record_type": "run", "started_at": datetime.now(timezone.utc).isoformat(),
                "grader_sha256": GRADER_SHA, "task_module_sha256": sha(ROOT / "bench/tasks_heldout4.py"),
                "ledger_sha256": sha(LEDGER), "verifier_sha256": sha(Path(__file__)),
                "task_ids": [t["id"] for t in tasks], "concurrency": concurrency}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await goto(page, DECOY)
        decoy = await observe(page, {})
        await context.close()
        semaphore = asyncio.Semaphore(concurrency)
        site_locks = {}
        with output.open("x") as file:
            file.write(json.dumps(metadata) + "\n")
            file.flush()

            async def one(task):
                site = by_id[task["id"]]["site"]
                lock = site_locks.setdefault(site, asyncio.Lock())
                async with lock, semaphore:
                    row = await verify_task(browser, task, by_id[task["id"]], decoy, artifact_dir)
                    file.write(json.dumps(row, ensure_ascii=False) + "\n")
                    file.flush()
                    print(f"{task['id']}: key={'PASS' if row['key'] else 'FAIL'}; "
                          f"reproducer={row['reproducer']}; "
                          f"negatives={sum(c['correctly_failed'] for c in row['negatives'])}/{len(row['negatives'])}", flush=True)
                    return row

            rows = await asyncio.gather(*(one(task) for task in tasks))
        await browser.close()
    result = {**metadata, "completed_at": datetime.now(timezone.utc).isoformat(),
              "summary": summarize(tasks, decisions, rows)}
    output.with_suffix(".summary.json").write_text(json.dumps(result, indent=2) + "\n")
    summary = result["summary"]
    print(f"Key checks: {summary['keys_pass']}/{len(tasks)} PASS")
    print(f"Reproducers: {summary['reproducer_statuses'].get('PASS', 0)}/{summary['scripts']} PASS; "
          f"{summary['reproducer_none']} none; statuses={summary['reproducer_statuses']}")
    print(f"Negatives: {summary['negatives_failed']}/{summary['negative_controls']} correctly FAIL; "
          f"{summary['tasks_with_negative']}/{len(tasks)} tasks covered")
    print(f"Full/partial: {summary['full']}/{summary['partial']}")
    print(json.dumps(summary, sort_keys=True))
    print(f"Run evidence: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RESULTS / (
        "verification_heldout4_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".jsonl"))
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be positive")
    asyncio.run(main(args.output, args.concurrency))
