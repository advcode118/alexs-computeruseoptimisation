"""browser-use 1.0 baseline. Local Chrome over CDP, same bench model.

The library's defaults are a cloud browser and the bu-fast gateway model.
This arm passes Browser('chromium') and ChatAnthropic('claude-sonnet-5-5').
The model writes Python in one persistent REPL. The task text is the
description and the start URL. Judge fields stay on the judge.

Playwright MCP is a different arm and stays pinned at 0.0.84.
"""

from __future__ import annotations

import asyncio
import json
import time

from bench.arms import ARM_BROWSER_USE, prompt_for
from bench.budget import ALLOWED_MODEL, assert_allowed_model, estimate_usd
from bench.probe import grade_observation
from bench.script_first import _PAGE_EVIDENCE_JS, text_from_page_read

BROWSER_USE_VERSION = "1.0.0"
LOCAL_BROWSER = "chromium"
BROWSER_USE_MAX_STEPS = 30
# The same page-evidence read script_first uses, as one CDP expression.
# It does not carry the task, the answer, or the judge selector.
PAGE_TEXT_EXPRESSION = f"({_PAGE_EVIDENCE_JS})()"


class BrowserUseClient:
    """Not a Playwright client. The probe runs the browser-use agent itself."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def start(self) -> None:
        raise RuntimeError("browser_use does not start a Playwright client")

    async def stop(self) -> None:
        return None

    def tools_for_claude(self) -> list[dict]:
        return []


def task_text(task: dict) -> str:
    """What the model reads. Description and start URL only."""
    description = task.get("description") if isinstance(task.get("description"), str) else ""
    start_url = task.get("start_url") if isinstance(task.get("start_url"), str) else ""
    return f"Task: {description}\n\nStart URL: {start_url}"


def load_browser_use():
    """Import browser-use 1.0. Tests pass their own loader and never call this."""
    import browser_use

    return browser_use.Agent, browser_use.Browser, browser_use.ChatAnthropic


def _daemon_request_fn():
    from browser_use.browser.browser import _daemon_request

    return _daemon_request


def _daemon_cdp_fn():
    from browser_use.browser.browser import _daemon_cdp

    return _daemon_cdp


def _explicit_page(browser) -> tuple[str, str, str] | None:
    data = getattr(browser, "__dict__", None)
    if not isinstance(data, dict):
        return None
    if "page_url" not in data and "page_text" not in data:
        return None
    url = data.get("page_url")
    text = text_from_page_read(data.get("page_text"))
    selector = data.get("page_selector_text")
    return (
        url if isinstance(url, str) else "",
        text,
        selector if isinstance(selector, str) else "",
    )


def selector_expression(selector: str) -> str:
    """Judge-only read of one element. The string is not a model prompt."""
    literal = json.dumps(selector)
    return (
        "(function(){ const el = document.querySelector("
        + literal
        + '); return el ? (el.innerText || el.textContent || "").trim() : ""; })()'
    )


def _page_text(name: str, target: str) -> str:
    try:
        cdp = _daemon_cdp_fn()
        attached = cdp(name, "Target.attachToTarget", targetId=target, flatten=True)
        session = attached.get("sessionId") if isinstance(attached, dict) else None
        if not isinstance(session, str) or not session:
            return ""
        value = cdp(
            name,
            "Runtime.evaluate",
            session,
            expression=PAGE_TEXT_EXPRESSION,
            returnByValue=True,
        )
        result = value.get("result") if isinstance(value, dict) else None
        raw = result.get("value") if isinstance(result, dict) else ""
        return text_from_page_read(raw)
    except Exception:
        return ""


def _marked_text(name: str, target: str, selector: str) -> str:
    try:
        cdp = _daemon_cdp_fn()
        attached = cdp(name, "Target.attachToTarget", targetId=target, flatten=True)
        session = attached.get("sessionId") if isinstance(attached, dict) else None
        if not isinstance(session, str) or not session:
            return ""
        value = cdp(
            name,
            "Runtime.evaluate",
            session,
            expression=selector_expression(selector),
            returnByValue=True,
        )
        result = value.get("result") if isinstance(value, dict) else None
        text = result.get("value") if isinstance(result, dict) else ""
        return text if isinstance(text, str) else ""
    except Exception:
        return ""


def _page_from_daemon(name: str, selector: str = "") -> tuple[str, str, str]:
    own = _daemon_request_fn()(name, {"meta": "current_tab"}, 5)
    url = ""
    target = None
    if isinstance(own, dict):
        raw = own.get("url")
        url = raw if isinstance(raw, str) else ""
        target = own.get("targetId")
    text = _page_text(name, target) if isinstance(target, str) and target else ""
    marked = ""
    if selector and isinstance(target, str) and target:
        marked = _marked_text(name, target, selector)
    return url, text, marked


async def read_page(browser, *, selector: str = "") -> tuple[str, str, str]:
    """Landed URL, page text, and an optional judge-only element read.

    A test double can set page_url, page_text, and page_selector_text.
    """
    explicit = _explicit_page(browser)
    if explicit is not None:
        return explicit
    data = getattr(browser, "__dict__", None)
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name:
        return "", "", ""
    try:
        return await asyncio.to_thread(_page_from_daemon, name, selector)
    except Exception:
        return "", "", ""


def _base_row(task_id: str) -> dict:
    return {
        "arm": ARM_BROWSER_USE,
        "task_id": task_id,
        "success": False,
        "success_reason": "",
        "skipped": False,
        "wall_ms": 0.0,
        "steps": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0.0,
        "model_ignores_tools": 0,
        "no_model": False,
        "replay_hit": False,
        "claude": False,
        "model": ALLOWED_MODEL,
        "browser": LOCAL_BROWSER,
        "browser_use": BROWSER_USE_VERSION,
        "page_url": "",
    }


def _usage(result) -> tuple[int, int, int]:
    usage = getattr(result, "usage", None)
    if not isinstance(usage, dict):
        usage = {}
    steps = getattr(result, "number_of_steps", None)
    count = steps() if callable(steps) else getattr(result, "steps", 0)
    return int(usage.get("input") or 0), int(usage.get("output") or 0), int(count or 0)


def _reported_answer(result) -> str:
    """The agent's final text. It is not a pass by itself."""
    final = getattr(result, "final_result", None)
    if callable(final):
        try:
            value = final()
        except Exception:
            value = None
        if isinstance(value, str):
            return value.strip()
    text = getattr(result, "text", None)
    return text.strip() if isinstance(text, str) else ""


def _task_selector(task: dict) -> str:
    markers = task.get("end_markers") if isinstance(task.get("end_markers"), dict) else {}
    selector = (markers or {}).get("answer_equals_selector")
    return selector if isinstance(selector, str) else ""


def _judge(task: dict, url: str, text: str, *, selector_text: str = "", answer: str = "") -> tuple[bool, str]:
    """The same post-run grade as the other arms. The LLM judge is not called."""
    ok, reason, _shared_ok, _shared_reason = grade_observation(
        task,
        url,
        text,
        selector_text=selector_text,
        answer=answer,
    )
    return ok, reason


async def _stop(browser) -> None:
    if browser is None:
        return
    stop = getattr(browser, "stop", None)
    if not callable(stop):
        return
    try:
        await stop()
    except Exception:
        return


async def run_browser_use_task(
    task: dict,
    *,
    api_key: str,
    headless: bool = True,
    model: str = ALLOWED_MODEL,
    loader=None,
) -> dict:
    """One task. Local Chrome, bench model. No cloud browser and no gateway model."""
    chosen = assert_allowed_model(model)
    row = _base_row(str(task.get("id") or ""))
    if not str(api_key or "").strip():
        row["skipped"] = True
        row["success_reason"] = "ANTHROPIC_API_KEY unset"
        return row
    started = time.perf_counter()
    browser = None
    try:
        agent_cls, browser_cls, llm_cls = (loader or load_browser_use)()
        browser = browser_cls(LOCAL_BROWSER, headless=headless, keep_alive=True)
        llm = llm_cls(chosen, api_key=api_key)
        agent = agent_cls(
            task_text(task),
            llm=llm,
            browser=browser,
            web_search=False,
            extend_system_message=prompt_for(ARM_BROWSER_USE),
        )
        result = await agent.run(max_steps=BROWSER_USE_MAX_STEPS)
        url, text, selector_text = await read_page(browser, selector=_task_selector(task))
        answer = _reported_answer(result)
        success, reason = _judge(
            task,
            url,
            text,
            selector_text=selector_text,
            answer=answer,
        )
        incoming, outgoing, steps = _usage(result)
        row.update(
            {
                "success": success,
                "success_reason": reason,
                "skipped": False,
                "wall_ms": (time.perf_counter() - started) * 1000,
                "steps": steps,
                "input_tokens": incoming,
                "output_tokens": outgoing,
                "usd": estimate_usd(incoming, outgoing),
                "claude": True,
                "page_url": url,
                "claimed_answer": answer,
                "expected_value": selector_text,
            }
        )
        return row
    except ImportError:
        row["skipped"] = True
        row["success_reason"] = f"browser-use=={BROWSER_USE_VERSION} is not installed"
        row["wall_ms"] = (time.perf_counter() - started) * 1000
        return row
    except Exception as exc:
        row["success_reason"] = f"browser_use run failed: {type(exc).__name__}"
        row["wall_ms"] = (time.perf_counter() - started) * 1000
        return row
    finally:
        await _stop(browser)
