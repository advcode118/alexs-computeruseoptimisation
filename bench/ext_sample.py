"""Deterministic external pool and model-free, screenshot-free browser pre-screen.

Run python -m bench.ext_sample. Existing site evidence is reused on restart.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from bench.tasks import get_all_tasks

SEED = 20261116
ROOT = Path(__file__).resolve().parents[1]
HOMEPAGES = json.loads((ROOT / "bench/ext_sources/mind2web_homepages.json").read_text())
SITE_ALIASES = {"steampowered.com": ("steam",)}
SOURCES = ("Mind2Web-Live", "WebWalkerQA", "WebVoyager", "AssistantBench", "Mind2Web")
QUOTAS = {"heldout4": dict(zip(SOURCES, (55, 50, 15, 10, 0))),
          "extdev": dict(zip(SOURCES, (16, 16, 5, 3, 0)))}
MULTI_SUFFIXES = {"herokuapp.com", "github.io", "co.uk", "ac.uk", "gov.uk", "gov.au", "blogspot.com", "netlify.app", "vercel.app"}


def registrable(host: str) -> str:
    labels = host.casefold().strip(".").split(".")
    return ".".join(labels[-3:] if ".".join(labels[-2:]) in MULTI_SUFFIXES else labels[-2:])


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def assigned_set(site: str) -> str:
    return "extdev" if int(digest(f"{SEED}:site:{site}"), 16) % 4 == 0 else "heldout4"


def existing_sites() -> set[str]:
    sites = set()
    for task in get_all_tasks():
        if task.get("id", "").startswith(("extdev_", "heldout4_", "ho4_")):
            continue
        hosts = [urlsplit(task.get("start_url", "")).hostname]
        marker = (task.get("end_markers") or {}).get("host")
        hosts.extend(marker if isinstance(marker, (list, tuple)) else [marker])
        sites.update(registrable(host) for host in hosts if host)
    return sites


def read_rows(path: Path):
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line]
    return json.loads(path.read_text())


def normalize(directory: Path) -> list[dict]:
    rows = []

    def add(source, source_id, text, url, key, **extra):
        assert isinstance(text, str) and text
        assert urlsplit(url).scheme in ("http", "https") and urlsplit(url).hostname, (source, source_id, url)
        rows.append(dict(source=source, source_id=str(source_id), task_text=text,
                         start_url=url, site=registrable(urlsplit(url).hostname), source_key=key, **extra))

    for filename in ("mind2web-live_train_20240528.json", "mind2web-live_test_20241024.json"):
        for row in read_rows(directory / filename):
            add(SOURCES[0], f"{filename}:{row['index']}", row["task"],
                row["evaluation"][0]["content"]["url"], row["evaluation"])
    for i, row in enumerate(read_rows(directory / "ww_main.jsonl")):
        add(SOURCES[1], f"main:{i}", row["question"], row["root_url"],
            {"answer": row["answer"], "info": row["info"]}, lang=row["info"]["lang"])
    refs = read_rows(directory / "wv_ref.json")
    for row in read_rows(directory / "wv.jsonl"):
        index = int(row["id"].rsplit("--", 1)[1])
        ref = refs.get(row["web_name"])
        answer = next((item for item in ref["answers"] if item["id"] == index), None) if ref else None
        add(SOURCES[2], row["id"], row["ques"], row["web"],
            {"answer": answer, "notice": ref.get("notice") if ref else None})
    for row in read_rows(directory / "ab_dev.jsonl"):
        first = row["gold_url"].split()[0]
        parts = urlsplit(first)
        add(SOURCES[3], row["id"], row["task"], f"{parts.scheme}://{parts.netloc}/",
            {"answer": row["answer"], "gold_url": row["gold_url"]},
            non_text_edits=[{"field": "start_url", "rule": "site root of first gold_url", "original": first}])
    homes = read_rows(directory / "mind2web_homepages.json")
    for row in read_rows(directory / "mind2web_train_slim.jsonl"):
        add(SOURCES[4], row["annotation_id"], row["confirmed_task"], homes[row["website"]],
            dict(row), non_text_edits=[{"field": "start_url", "rule": "website-name to homepage mapping in mind2web_homepages.json", "original": row["website"]}])
    assert len({(r["source"], r["source_id"]) for r in rows}) == len(rows)
    return rows


def classify(status, title: str, text: str, error: str = "") -> str:
    content = (title + "\n" + text).casefold()
    if status in (404, 410) or any(word in error for word in ("ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_REFUSED", "ERR_ADDRESS_UNREACHABLE")):
        return "site_gone_or_content_gone"
    if re.search(r"domain (?:is )?for sale|buy this domain|sedo domain parking|this domain is parked|hugedomains\.com", content):
        return "site_gone_or_content_gone"
    if error and not text.strip():
        return "unreachable"
    challenge = re.search(r"verify (?:that )?you are human|access denied|just a moment|checking your browser|enable javascript and cookies to continue", content)
    vendor_challenge = re.search(r"captcha|perimeterx|akamai|cloudflare", content) and (status in (403, 429, 503) or len(text) < 1000)
    if challenge or vendor_challenge or len(text.strip()) < 40 or status in (403, 429, 503):
        return "captcha_or_bot_block"
    if error or status is None or status >= 400:
        return "unreachable"
    return "ok"


class BrowserScreen:
    def __init__(self, browser):
        self.browser = browser

    async def __call__(self, url: str) -> dict:
        context = await self.browser.new_context()
        page = await context.new_page()
        status, error, title, text = None, "", "", ""
        try:
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                status = response.status if response else None
                await page.wait_for_timeout(2000)
            except Exception as exc:
                error = str(exc).split("Call log:")[0].strip()
            try:
                title = await page.title()
                text = await page.locator("body").inner_text(timeout=5000)
            except Exception as exc:
                error = error or str(exc).split("Call log:")[0].strip()
            return dict(start_url=url, final_url=page.url, status=status, title=title,
                        text=text[:200], text_length=len(text), error=error,
                        classification=classify(status, title, text, error),
                        checked_at=datetime.now(timezone.utc).isoformat())
        finally:
            await context.close()


async def sample(rows, screen, cache, save_cache, used=None, quotas=None):
    used = existing_sites() if used is None else used
    quotas = QUOTAS if quotas is None else quotas
    ledger, candidates = [], {name: [] for name in quotas}
    for source in SOURCES:
        ordered = sorted((row for row in rows if row["source"] == source),
                         key=lambda row: digest(f"{SEED}:{source}:{row['source_id']}"))
        for rank, row in enumerate(ordered, 1):
            site = row["site"]
            name = assigned_set(site)
            reason = None
            if site in used:
                reason = "domain_overlap"
            elif source == "WebWalkerQA" and row["lang"] != "en":
                reason = "non_english"
            evidence = None
            if reason is None:
                if site not in cache:
                    cache[site] = await screen(row["start_url"])
                    save_cache(cache)
                evidence = cache[site]
                if evidence["classification"] != "ok":
                    reason = "unreachable"
            entry = dict(source=source, source_id=row["source_id"], site=site, set=name,
                         rank=rank, seed=SEED, disposition="excluded" if reason else "accepted_candidate", reason=reason)
            if evidence:
                entry["reachability"] = evidence
            ledger.append(entry)
            if reason is None:
                candidates[name].append(dict(row, **entry))
    return ledger, candidates


def task_fingerprint(text, site="", start_url=""):
    def normal(value):
        return re.sub(r"[\W_]+", " ", value.casefold()).strip()

    value = normal(text)
    hosts = {site, (urlsplit(start_url).hostname or "").removeprefix("www.")}
    labels = {normal(host) for host in hosts if host}
    labels.update(normal(host.rsplit(".", 1)[0]) for host in hosts if "." in host)
    labels.update(normal(name) for name, url in HOMEPAGES.items()
                  if registrable(urlsplit(url).hostname or "") == site)
    labels.update(normal(name) for name in SITE_ALIASES.get(site, ()))
    for label in sorted(labels, key=len, reverse=True):
        for preposition in (" in ", " on "):
            suffix = preposition + label
            if value.endswith(suffix):
                return value[:-len(suffix)].strip()
    return value


def effective_authoring_decisions(decisions):
    """Latest decision wins; original ledger lines remain available for audit."""
    return list({(row["source"], row["source_id"]): row for row in decisions}.values())


def authoring_reserve(rows, decisions):
    """Walk unreviewed ranks; caller appends each manual decision before resuming.

    Existing decisions are honored; appended revisions supersede earlier lines.
    Only kept tasks consume the site cap. Quotas
    are authoring targets, not reserve truncation; Mind2Web is fill-only last.
    """
    seen = {(row["source"], row["source_id"]) for row in decisions}
    by_key = {(row["source"], row["source_id"]): row for row in rows}
    for source in SOURCES:
        for row in sorted((r for r in rows if r["source"] == source), key=lambda r: r["rank"]):
            if (source, row["source_id"]) in seen:
                continue
            fingerprint = task_fingerprint(row.get("task_text", ""), row["site"], row.get("start_url", ""))
            active = effective_authoring_decisions(decisions)
            duplicate = next((decision for decision in active
                              if decision["disposition"] == "kept"
                              and (accepted := by_key.get((decision["source"], decision["source_id"])))
                              and fingerprint
                              and task_fingerprint(accepted.get("task_text", ""), accepted["site"], accepted.get("start_url", "")) == fingerprint), None)
            if duplicate:
                yield dict(row, duplicate_of=duplicate["task_id"]), "duplicate_task"
                continue
            count = sum(d["site"] == row["site"] and d["disposition"] == "kept" for d in active)
            yield row, "site_cap" if count >= 3 else None


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/results/ext_sample_20261116")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = normalize(ROOT / "bench/ext_sources")
    write_jsonl(args.output / "pool.jsonl", rows)
    cache_path = args.output / "reachability_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    def save_cache(value):
        cache_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        # Default local browser settings, as in script_first and the heldout3 verifiers.
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = await pw.chromium.launch(headless=True)
        browser_version = browser.version
        try:
            ledger, candidates = await sample(rows, BrowserScreen(browser), cache, save_cache)
        finally:
            await browser.close()
    write_jsonl(args.output / "screening.jsonl", ledger)
    for name, selected in candidates.items():
        write_jsonl(args.output / f"candidates_{name}.jsonl", selected)
    metadata = dict(seed=SEED, quotas=QUOTAS, site_cap=3, site_cap_applies_to="accepted_tasks_only", source_order=SOURCES,
                    procedure_revision="STEP 3, before heldout4 authoring: untruncated ranked reserve; accepted-only site cap; Mind2Web train fill-only last; existing extdev decisions frozen",
                    reserve_policy="all eligible reachable rows; no candidate site cap or quota truncation",
                    duplicate_policy="case/punctuation/whitespace normalized task text; strip trailing site/domain/brand suffix; exclude against accepted tasks, recording their task IDs",
                    factual_key_policy="multi-page factual answers retained as partial keys; computed answers and ungradeable UI end states remain no_checkable_key with separate sub-reasons; revisions append to ledger",
                    fill_order=SOURCES, heldout4_authoring_started=False,
                    browser_version=browser_version, headless=True, browser_settings="Playwright defaults; chrome channel, Chromium fallback; fresh context per site",
                    overlap_sites=sorted(existing_sites()), pool_rows=len(rows))
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"SEED={SEED}; untruncated ranked reserve; cap=3 ACCEPTED tasks per site; Mind2Web fill-only")
    print("set         source           reachable  quota")
    for name in QUOTAS:
        counts = Counter(row["source"] for row in candidates[name])
        for source in SOURCES:
            print(f"{name:11} {source:16} {counts[source]:9} {QUOTAS[name][source]:6}")
    print("Exclusions:")
    for reason, count in sorted(Counter(row["reason"] for row in ledger if row["reason"]).items()):
        print(f"  {reason}: {count}")
    print("Unreachable detail:")
    for reason, count in sorted(Counter(row["reachability"]["classification"] for row in ledger if row["reason"] == "unreachable").items()):
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
