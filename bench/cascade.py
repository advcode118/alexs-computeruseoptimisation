"""Grounded script execution with a precision gate and warm browser handoff."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import asdict
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from bench.script_first import task_asks_value, task_terms
from bench.recovery import classify_task, evaluate_checkpoints, plan_checkpoints


class _GroundingParser(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.data = {"title": "", "h1": "", "links": [], "forms": []}
        self.capture = None
        self.anchor = None
        self.form = None
        self.first_h1 = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title" or (tag == "h1" and not self.first_h1):
            self.capture = tag
            if tag == "h1":
                self.first_h1 = True
        if tag == "a":
            self.anchor = [a.get("href") or "", ""]
        if tag == "form":
            self.form = {"action": urljoin(self.url, a.get("action") or self.url),
                         "method": (a.get("method") or "get").upper(),
                         "input": "", "hidden": {}, "search": a.get("role") == "search" or "search" in (a.get("action") or "").lower()}
        if tag == "input" and self.form is not None:
            kind, name = (a.get("type") or "text").lower(), a.get("name") or ""
            if kind == "hidden" and name:
                self.form["hidden"][name] = a.get("value") or ""
            if kind in ("text", "search"):
                if not self.form["input"] or kind == "search":
                    self.form["input"] = name
                if kind == "search" or name.lower() in {"q", "query", "search", "s", "k", "term", "keyword", "keywords"}:
                    self.form["search"] = True

    def handle_data(self, data):
        if self.capture:
            self.data[self.capture] += data
        if self.anchor is not None:
            self.anchor[1] += data

    def handle_endtag(self, tag):
        if tag == self.capture:
            self.capture = None
        if tag == "a" and self.anchor is not None:
            href, label = self.anchor
            if href and not href.startswith("#") and urlsplit(href).scheme.lower() not in {"javascript", "mailto"}:
                link = {"href": urljoin(self.url, href), "text": " ".join(label.split())}
                if link not in self.data["links"]:
                    self.data["links"].append(link)
            self.anchor = None
        if tag == "form" and self.form is not None:
            if self.form.pop("search"):
                self.data["forms"].append(self.form)
            self.form = None


def ground_start_page(url, *, timeout=4.0, fetch=None, description="") -> dict:
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with (fetch or urlopen)(request, timeout=timeout) as response:
            if "html" not in response.headers.get("Content-Type", "").lower():
                return {"error": "non-HTML response"}
            html = response.read().decode("utf-8", errors="replace")
        parser = _GroundingParser(url)
        parser.feed(html)
        data = parser.data
        for key in ("title", "h1"):
            data[key] = " ".join(data[key].split())
        if len(data["links"]) > 80:
            terms = set(task_terms(description))
            data["links"].sort(key=lambda link: not bool(terms & set(re.findall(r"\w+", (link["text"] + " " + link["href"]).lower()))))
        data["links"] = data["links"][:80]
        return data
    except Exception as exc:
        return {"error": type(exc).__name__}


def grounding_note(data) -> str:
    if not data or data.get("error"):
        return ""
    lines = ["Start page read by plain HTTP before the run; it may differ from the live page.",
             "Title: " + data.get("title", ""), "H1: " + data.get("h1", "")]
    for form in data.get("forms", []):
        params = {**form["hidden"], form["input"] or "q": "<query>"}
        lines.append(f'{form["method"]} {form["action"]}{"&" if "?" in form["action"] else "?"}' + urlencode(params, safe="<>"))
    lines.extend(f'- {link["text"]} -> {link["href"]}' for link in data.get("links", []))
    return "\n".join(lines)[:6000]


def precision_check(description, self_check_record):
    record = self_check_record or {}
    verdict = record.get("verdict") or "UNKNOWN"
    if verdict != "PASS":
        return False, "self-check " + verdict
    claim = (record.get("payload") or {}).get("claimed") or {}
    answer = str(claim.get("answer") or "").strip()
    live = urlsplit(record.get("page_url") or "")
    segment = live.path.rstrip("/").rsplit("/", 1)[-1].lower()
    if "\n" in answer or "\t" in answer:
        return False, "multiline_answer"
    if len(answer) > 80:
        return False, "long_answer"
    if "/search" in live.path.lower() or "search" in segment or set(parse_qs(live.query, keep_blank_values=True)) & {"q", "query", "search", "s", "k", "keyword", "keywords", "term"}:
        return False, "search_results_url"
    if not task_asks_value(description) and (live.path in ("", "/") or segment in {"index.html", "index.htm", "index.php"}):
        return False, "landing_page"
    claimed = urlsplit(str(claim.get("url") or ""))
    def identity(url):
        return (url.netloc.lower(), url.path.rstrip("/") or "/", url.query)
    if claimed.scheme.lower() in {"http", "https"} and identity(claimed) != identity(live):
        return False, "claimed_url_mismatch"
    return True, "PASS"


def handoff_note(task, current_url, visited_urls, reason):
    from bench.tasks import task_message

    safe = re.sub(r'"[^"]*"|\'[^\']*\'', "", reason)
    allowed = {"multiline_answer", "long_answer", "search_results_url", "landing_page", "claimed_url_mismatch"}
    if safe not in allowed:
        safe = "self-check " + (safe.removeprefix("self-check ").split() or ["UNKNOWN"])[0]
        if safe not in {"self-check PASS", "self-check FAIL", "self-check UNKNOWN"}:
            safe = "self-check UNKNOWN"
    pages = list(dict.fromkeys(visited_urls))[:5]
    return (task_message(task.get("description") or "", task.get("start_url") or "")
            + f"\nA fast scripted attempt ran first and did not confirm the result. The browser is already open on {current_url}; continue from there (navigating is allowed)."
            + "\nPages visited: " + ", ".join(pages) + "\nHandoff reason: " + safe)


async def _page_target_id(page):
    session = await page.context.new_cdp_session(page)
    try:
        return (await session.send("Target.getTargetInfo"))["targetInfo"]["targetId"]
    finally:
        await session.detach()


async def run_recovery(task, *, harness, script, result, reason, row, api_key, headless, provider, browser_use_loader=None):
    from bench.browser_use_arm import _judge, _task_selector, load_browser_use, run_browser_use_task
    from bench.measurement import grade_fields
    from bench.openai_spend import PriceUnknown
    from bench.script_first import read_marked_page

    browser_start = time.perf_counter()
    try:
        loader = browser_use_loader or (lambda: load_browser_use(provider))
        _, browser_cls, _ = loader()
        browser = browser_cls(cdp_url=harness.mcp_client.cdp_url, keep_alive=True)
        current = getattr(harness.mcp_client._page, "url", "") or script.get("final_url", "")
        target_id = await _page_target_id(harness.mcp_client._page)
        receipt = handoff_note(task, current,
            [step.page_url for step in result.steps if step.page_url], reason)
        row.update(handoff_url=current, handoff_target_id=target_id,
                   handoff_cdp_url=harness.mcp_client.cdp_url, handoff_receipt=receipt)
        fallback = await run_browser_use_task(task, api_key=api_key, headless=headless,
            model=harness.model, provider=provider, effort=harness.effort, loader=loader,
            external_browser=browser, external_target_id=target_id, task_text_override=receipt)
    except PriceUnknown:
        raise
    except Exception as exc:
        finished_at = time.perf_counter()
        grade_start = time.perf_counter()
        text, marked = await read_marked_page(harness.mcp_client, _task_selector(task))
        url = getattr(harness.mcp_client, "_grade_read_url", "") or script.get("final_url", "")
        ok, _ = _judge(task, url, text, selector_text=marked)
        fallback = {**grade_fields(url, text, marked, ""), "success": ok,
                    "success_reason": f"browser_use run failed: {type(exc).__name__}",
                    "page_url": url, "_run_finished_at": finished_at,
                    "wall_ms": (finished_at-browser_start)*1000,
                    "grade_read_ms": (time.perf_counter()-grade_start)*1000}
    return fallback, browser_start


async def run_cascade_task(task, *, api_key, headless=True, runs_dir, provider="anthropic", model=None, effort=None, browser_use_loader=None, fallback="browser_use"):
    if fallback not in {"browser_use", "none"}:
        raise ValueError(f"unknown fallback {fallback!r}")
    from bench.arms import SCRIPT_FIRST_MAX_CALLS
    from bench.harness import BenchmarkHarness
    from bench.probe import script_result_row

    harness = BenchmarkHarness(api_key=api_key, headless=headless, runs_dir=runs_dir,
                               arm="script_first", max_steps=SCRIPT_FIRST_MAX_CALLS,
                               script_cache=None, remote_debugging=True,
                               provider=provider, model=model, effort=effort)
    try:
        await harness.setup()
        started = time.perf_counter()
        harness._task_wall_start = started
        grounding = await asyncio.to_thread(ground_start_page, task["start_url"], description=task["description"])
        grounding_ms = (time.perf_counter() - started) * 1000
        profile = classify_task(task["description"], grounding)
        checkpoints = plan_checkpoints(task, profile)
        script_start = time.perf_counter()
        result = await harness.run_task(task["id"], task["description"], task["start_url"], first_message_extra=grounding_note(grounding))
        script_end = time.perf_counter()
        script = script_result_row(task, result, harness, provider=provider,
                                   openai_model=harness.model, openai_effort=harness.effort)
        checks = script.get("self_checks") or []
        blocked = [action for check in checks for action in (check.get("payload") or {}).get("blocked_actions", [])]
        accept, reason = precision_check(task["description"], checks[-1] if checks else {})
        if blocked:
            accept, reason = False, "needs approval: blocked action"
        row = dict(script)
        browser_ms = 0.0
        recovery = {}
        answered = "script" if accept else "none"
        finished = script_end
        if not accept and not blocked and fallback == "browser_use":
            recovery, browser_start = await run_recovery(
                task, harness=harness, script=script, result=result, reason=reason,
                row=row, api_key=api_key, headless=headless, provider=provider,
                browser_use_loader=browser_use_loader)
            finished = recovery.pop("_run_finished_at", time.perf_counter())
            browser_ms = recovery.get("wall_ms", (finished - browser_start) * 1000)
            row.update(recovery)
            row["grade_claim"] = None
            row["grade_completed"] = None
            row["grade_completion_reason"] = ""
            row["final_url"] = recovery.get("page_url", "")
            row["steps"] = script.get("steps", 0) + recovery.get("steps", 0)
            answered = "none" if recovery.get("success_reason", "").startswith("browser_use run failed") or recovery.get("skipped") else "browser_use"
        token_keys = ("input_tokens", "output_tokens", "cached_tokens", "cache_write_30m_tokens", "cache_write_12h_tokens")
        row.update({key: script.get(key, 0) + recovery.get(key, 0) for key in token_keys})
        row.update(arm="cascade", answered_by=answered, handoff_reason="" if accept else reason,
                   profile=asdict(profile), blocked_actions=blocked,
                   checkpoints=[evaluate_checkpoints(checkpoints, check.get("payload") or {}) for check in checks],
                   wall_ms=(finished - started) * 1000 - result.grade_read_ms,
                   stage_wall_ms={"grounding": grounding_ms, "script": (script_end-script_start)*1000-result.grade_read_ms, "browser_use": browser_ms},
                   stage_model_calls={"script": script.get("model_calls", 0), "browser_use": recovery.get("model_calls", 0)},
                   model_calls=script.get("model_calls", 0) + recovery.get("model_calls", 0),
                   stage_usd={"script": script["usd"], "browser_use": recovery.get("usd", 0)},
                   stage_tokens={"script": {key: script.get(key, 0) for key in token_keys}, "browser_use": {key: recovery.get(key, 0) for key in token_keys}},
                   usd=script["usd"] + recovery.get("usd", 0),
                   grounding={"ok": not bool(grounding.get("error")), "error": grounding.get("error", ""), "links": len(grounding.get("links", [])), "forms": len(grounding.get("forms", [])), "h1": grounding.get("h1", "")})
        for key in ("scripts", "self_checks", "task_description", "start_url"):
            row[key] = script.get(key)
        row["browser_launch_ms"] = harness.browser_launch_ms
        row["grade_read_ms"] = result.grade_read_ms + recovery.get("grade_read_ms", 0)
        row["claude"] = provider == "anthropic"
        row["model"] = harness.model
        if provider == "openai":
            row["provider"] = provider
            row["effort"] = harness.effort
        return row
    finally:
        await harness.teardown()
