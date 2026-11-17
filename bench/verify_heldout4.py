"""Model-free reproducers and negatives; sealing awaits the PR #88 grader.

There is deliberately no direct-final-page positive key-check path. A real
wrong-host page supplies a negative for every task, including non-scriptable
tasks. Reproduced pages additionally receive a wrong-answer control.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from playwright.async_api import async_playwright

from bench.ext_sample import effective_authoring_decisions
from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/ext_sample_20261116"
LEDGER = RESULTS / "authoring_heldout4.jsonl"
WRONG_ANSWER = "deliberatelyincorrectbenchmarkvalue"
DECOY = "https://example.com/"
SEALING = "DEFERRED: PR #88 grader is not merged; no sealing key checks run"


def read_ledger():
    return effective_authoring_decisions(
        json.loads(line) for line in LEDGER.read_text().splitlines() if line
    )


def goal_url_matches(task, url):
    actual = urlsplit(url)
    hosts = task["end_markers"]["host"]
    hosts = [hosts] if isinstance(hosts, str) else hosts
    if not any(
        (actual.hostname or "").removeprefix("www.") == h.removeprefix("www.")
        for h in hosts
    ):
        return False
    marker = task["check_url_contains"]
    expected = urlsplit(marker)
    if expected.query:
        return (
            unquote(actual.path).startswith(unquote(expected.path))
            and not (
                Counter(parse_qsl(expected.query, keep_blank_values=True))
                - Counter(parse_qsl(actual.query, keep_blank_values=True))
            )
        )
    return unquote(marker).casefold() in unquote(url).casefold()


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
                              "sha256": hashlib.sha256(data).hexdigest()})
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


def control(task, evidence, answer, name):
    result = evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=answer))
    return {"name": name, "verdict": result.verdict, "reason": result.reason,
            "correctly_failed": result.verdict == "FAIL", "observed_url": evidence.url}


def reproduction_status(task, evidence, verdict):
    if not goal_url_matches(task, evidence.url):
        return "FAIL"
    if not evidence.text.strip():
        return "UNKNOWN"
    if re.search(r"just a moment|verify you are human|access denied|captcha", evidence.title, re.I):
        return "SITE_BLOCKED"
    if task["grader_flags"]:
        return "BLOCKED_BY_GRADER"
    return "PASS" if verdict == "PASS" else verdict


async def verify_task(browser, task, decision, decoy, artifact_dir):
    row = {"id": task["id"], "checked_at": datetime.now(timezone.utc).isoformat(),
           "key_check": "DEFERRED", "grader_flags": task["grader_flags"],
           "reproducer": "NONE", "negatives": [], "errors": []}
    row["negatives"].append(control(task, decoy, task["expected_answer"], "wrong_host"))
    if task["reproducer"] == "none":
        return row
    context = await browser.new_context()
    page = await context.new_page()
    page.set_default_timeout(15000)
    try:
        await goto(page, task["start_url"])
        page, artifacts = await run_steps(page, decision["repro_steps"], artifact_dir, task["id"])
        evidence = await collect_page_evidence(
            page, selector=task["end_markers"].get("answer_equals_selector", "")
        )
        result = evidence_verdict(
            task["end_markers"], evidence, ClaimedEvidence(answer=task["expected_answer"])
        )
        row.update(reproducer=reproduction_status(task, evidence, result.verdict),
                   marker_verdict=result.verdict, marker_reason=result.reason,
                   observed_url=evidence.url, title=evidence.title,
                   goal_url_matched=goal_url_matches(task, evidence.url), artifacts=artifacts)
        row["negatives"].append(control(task, evidence, WRONG_ANSWER, "wrong_answer_after_reproducer"))
    except Exception as exc:
        row["reproducer"] = "ERROR"
        row["errors"].append(f"{type(exc).__name__}: {str(exc).splitlines()[0]}")
    finally:
        await context.close()
    return row


def summarize(tasks, decisions, rows):
    exclusions = [d for d in decisions if d["disposition"] == "excluded"]
    scripts = sum(t["reproducer"] == "script" for t in tasks)
    statuses = Counter(r["reproducer"] for r in rows)
    negatives = [c for row in rows for c in row["negatives"]]
    marker_passes = sum(r.get("marker_verdict") == "PASS" for r in rows)
    return {
        "key_checks": SEALING, "tasks": len(tasks), "scripts": scripts,
        "reproducer_statuses": dict(statuses), "marker_passes": marker_passes,
        "marker_pass_rate": marker_passes / scripts if scripts else None,
        "reproducer_none": len(tasks) - scripts,
        "negatives_failed": sum(c["correctly_failed"] for c in negatives),
        "negative_controls": len(negatives),
        "tasks_with_negative": sum(any(c["correctly_failed"] for c in r["negatives"]) for r in rows),
        "current_grader_flagged": sum(bool(t["grader_flags"]) for t in tasks),
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
        "reproducer_problems": [r["id"] for r in rows if r["reproducer"] not in
                                {"PASS", "NONE", "BLOCKED_BY_GRADER"}],
    }


async def main(output):
    tasks = tasks_for_split("heldout4")
    decisions = read_ledger()
    by_id = {d["task_id"]: d for d in decisions if d["disposition"] == "kept"}
    if output.exists():
        raise FileExistsError(f"Preserve prior run evidence; choose a new --output: {output}")
    artifact_dir = RESULTS / "heldout4_artifacts"
    artifact_dir.mkdir(exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await goto(page, DECOY)
        decoy = await collect_page_evidence(page)
        await context.close()
        semaphore = asyncio.Semaphore(3)

        async def run(task):
            async with semaphore:
                row = await verify_task(browser, task, by_id[task["id"]], decoy, artifact_dir)
                print(f"{task['id']}: reproducer={row['reproducer']}; "
                      f"negatives={sum(c['correctly_failed'] for c in row['negatives'])}"
                      f"/{len(row['negatives'])}", flush=True)
                return row

        rows = await asyncio.gather(*(run(task) for task in tasks))
        await browser.close()
    summary = summarize(tasks, decisions, rows)
    with output.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        stream.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
    print(SEALING)
    print("Reproducer statuses:", json.dumps(summary["reproducer_statuses"], sort_keys=True))
    rate = summary["marker_pass_rate"]
    print(f"Reproducer marker gate: {summary['marker_passes']}/{summary['scripts']} PASS; "
          f"rate={rate:.1%}" if rate is not None else "Reproducer marker gate: no scripts")
    print(f"Negatives: {summary['negatives_failed']}/{summary['negative_controls']} correctly FAIL; "
          f"{summary['tasks_with_negative']}/{len(tasks)} tasks have a successful negative")
    for key in ("current_grader_flagged", "full", "partial", "reproducer_none", "sources", "kinds",
                "exclusions", "no_checkable_key", "grader_flags", "reproducer_problems"):
        print(f"{key}: {json.dumps(summary[key], sort_keys=True)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RESULTS / "verification_heldout4.jsonl")
    args = parser.parse_args()
    asyncio.run(main(args.output))
