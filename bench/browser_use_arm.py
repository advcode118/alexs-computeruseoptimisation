"""browser-use 1.0 baseline. Local Chrome over CDP, the probe's model.

The library's defaults are a cloud browser and the bu-fast gateway model.
This arm passes Browser('chromium') pointed at Google Chrome when that
binary is installed. 'chromium' is the library's fresh-profile launcher.
Browser('chrome') would attach to the already-open Chrome and refuses
headless, so it is not used. Claude stays ChatAnthropic with the probe's
model string, which is claude-sonnet-5-5. OpenAI stays ChatOpenAI with the
model the probe was given. The model writes Python in one persistent REPL.
The task text is the description and the start URL. Judge fields stay on
the judge.

Playwright MCP is a different arm and stays pinned at 0.0.84.
"""

from __future__ import annotations

import asyncio
import time

from bench.arms import ARM_BROWSER_USE, prompt_for
from bench.budget import ALLOWED_MODEL, assert_allowed_model, estimate_usd
from bench.fairness import ARM_RUN_TIMEOUT_S, PAGE_READ_TIMEOUT_S, google_chrome_executable
from bench.probe import grade_observation
from bench.script_first import (
    _PAGE_EVIDENCE_JS,
    marked_selector_source,
    read_shared_evidence,
    text_from_page_read,
)

BROWSER_USE_VERSION = "1.0.0"
# browser-use's fresh local profile. The executable is Google Chrome when installed.
LOCAL_BROWSER = "chromium"
BROWSER_USE_MAX_STEPS = 30
# CDP Runtime.evaluate needs an expression. The call is still the page-evidence
# function with no arguments, the same function the other arms pass to evaluate.
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


def load_browser_use(provider: str = "anthropic"):
    """Import browser-use 1.0. Tests pass their own loader and never call this."""
    import browser_use

    if provider == "openai":
        chat = getattr(browser_use, "ChatOpenAI", None)
        if chat is None:
            raise ImportError("browser-use ChatOpenAI is not available")
    else:
        chat = browser_use.ChatAnthropic
    return browser_use.Agent, browser_use.Browser, chat


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
    """The shared selector function, invoked for CDP. Not a model prompt."""
    return f"({marked_selector_source(selector)})()"


def _cdp_value(name: str, target: str, expression: str):
    """One Runtime.evaluate. The expression is the shared function call."""
    cdp = _daemon_cdp_fn()
    attached = cdp(name, "Target.attachToTarget", targetId=target, flatten=True)
    session = attached.get("sessionId") if isinstance(attached, dict) else None
    if not isinstance(session, str) or not session:
        return None
    value = cdp(
        name,
        "Runtime.evaluate",
        session,
        expression=expression,
        returnByValue=True,
    )
    result = value.get("result") if isinstance(value, dict) else None
    if not isinstance(result, dict):
        return None
    return result.get("value")


def _page_from_daemon(name: str, selector: str = "") -> tuple[str, str, str]:
    own = _daemon_request_fn()(name, {"meta": "current_tab"}, PAGE_READ_TIMEOUT_S)
    url = ""
    target = None
    if isinstance(own, dict):
        raw = own.get("url")
        url = raw if isinstance(raw, str) else ""
        target = own.get("targetId")
    if not isinstance(target, str) or not target:
        return url, "", ""

    def evaluate(source: str):
        return _cdp_value(name, target, f"({source})()")

    text, marked = asyncio.run(read_shared_evidence(evaluate, selector))
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


def _chat_model(llm_cls, model: str, api_key: str, effort: str | None):
    """Claude calls stay model plus api_key. OpenAI also passes reasoning effort."""
    if effort is None:
        return llm_cls(model, api_key=api_key)
    import inspect

    from bench.openai_spend import EffortNotAllowed

    params = inspect.signature(llm_cls).parameters
    accepts_any = any(item.kind is inspect.Parameter.VAR_KEYWORD for item in params.values())
    if "reasoning_effort" in params or accepts_any:
        return llm_cls(model, api_key=api_key, reasoning_effort=effort)
    if "effort" in params:
        return llm_cls(model, api_key=api_key, effort=effort)
    raise EffortNotAllowed(
        "browser-use chat model does not accept reasoning effort. Refusing to run."
    )


def _token(usage: dict, key: str) -> int | None:
    """One count, or None when the key is absent. A bad value fails closed."""
    from bench.openai_spend import PriceUnknown

    if key not in usage:
        return None
    try:
        value = int(usage[key] or 0)
    except (TypeError, ValueError) as exc:
        raise PriceUnknown("browser-use token counts are not integers. Refusing to price.") from exc
    if value < 0:
        raise PriceUnknown("browser-use token counts are inconsistent. Refusing to price.")
    return value


def _priced_usage(model: str, usage: dict) -> tuple[int, int, int, int, float]:
    """browser-use usage at the published OpenAI rates. Unknown fields fail closed.

    The 1.0 result is input, output, cache_read, cache_write, and requests.
    cache_read is cached input. cache_write is a 30-minute write: this object
    does not split a 12-hour lifetime. Both are slices of input. script_first,
    stagehand, and playwright_mcp do not see this object. They price the
    Responses usage in bench.openai_client.
    """
    from bench.openai_spend import PriceUnknown, price_usd

    if not isinstance(usage, dict):
        raise PriceUnknown("browser-use usage is missing. Refusing to price.")
    allowed = {"input", "output", "requests", "cached", "cached_tokens", "cache_read", "cache_write"}
    extra = set(usage) - allowed
    if extra:
        raise PriceUnknown(
            f"browser-use usage has unrecognized fields {sorted(extra)}. Refusing to price."
        )
    try:
        incoming = int(usage.get("input") or 0)
        outgoing = int(usage.get("output") or 0)
    except (TypeError, ValueError) as exc:
        raise PriceUnknown("browser-use token counts are not integers. Refusing to price.") from exc
    reads = []
    for key in ("cache_read", "cached_tokens", "cached"):
        count = _token(usage, key)
        if count is not None:
            reads.append(count)
    if any(count != reads[0] for count in reads):
        raise PriceUnknown("browser-use cache reads disagree. Refusing to price.")
    cached = reads[0] if reads else 0
    written = _token(usage, "cache_write") or 0
    return incoming, outgoing, cached, written, price_usd(model, incoming, outgoing, cached, written, 0)


async def run_browser_use_task(
    task: dict,
    *,
    api_key: str,
    headless: bool = True,
    model: str = ALLOWED_MODEL,
    loader=None,
    provider: str = "anthropic",
    effort: str | None = None,
) -> dict:
    """One task. Local Chrome, bench model. No cloud browser and no gateway model."""
    if provider == "openai":
        from bench.openai_spend import assert_effort, assert_openai_model

        chosen = assert_openai_model(model)
        chosen_effort = assert_effort(chosen, effort or "")
    elif provider == "anthropic":
        if effort not in (None, ""):
            from bench.openai_spend import EffortNotAllowed

            raise EffortNotAllowed("Claude does not take --effort.")
        chosen = assert_allowed_model(model)
        chosen_effort = None
    else:
        raise ValueError(f"unknown provider {provider!r}")
    row = _base_row(str(task.get("id") or ""))
    if not str(api_key or "").strip():
        row["skipped"] = True
        row["success_reason"] = (
            "OPENAI_API_KEY unset" if provider == "openai" else "ANTHROPIC_API_KEY unset"
        )
        if provider == "openai":
            row["provider"] = "openai"
            row["model"] = chosen
            row["effort"] = chosen_effort
            row["claude"] = False
        return row
    started = time.perf_counter()
    browser = None
    try:
        agent_cls, browser_cls, llm_cls = loader() if loader is not None else load_browser_use() if provider != "openai" else load_browser_use(provider)
        chrome = google_chrome_executable()
        browser = browser_cls(
            LOCAL_BROWSER,
            headless=headless,
            keep_alive=True,
            executable_path=chrome,
        )
        llm = _chat_model(llm_cls, chosen, api_key, chosen_effort)
        agent = agent_cls(
            task_text(task),
            llm=llm,
            browser=browser,
            web_search=False,
            extend_system_message=prompt_for(ARM_BROWSER_USE),
        )
        result = await agent.run(max_steps=BROWSER_USE_MAX_STEPS, timeout=ARM_RUN_TIMEOUT_S)
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
        cached = 0
        usd = estimate_usd(incoming, outgoing)
        written = 0
        if provider == "openai":
            incoming, outgoing, cached, written, usd = _priced_usage(
                chosen, getattr(result, "usage", {}) or {}
            )
        row.update(
            {
                "success": success,
                "success_reason": reason,
                "skipped": False,
                "wall_ms": (time.perf_counter() - started) * 1000,
                "steps": steps,
                "input_tokens": incoming,
                "output_tokens": outgoing,
                "usd": usd,
                "claude": provider != "openai",
                "page_url": url,
                "claimed_answer": answer,
                "expected_value": selector_text,
                "model": chosen,
                "browser": "chrome" if chrome else LOCAL_BROWSER,
            }
        )
        if provider == "openai":
            row["provider"] = "openai"
            row["effort"] = chosen_effort
            row["cached_tokens"] = cached
            row["cache_write_30m_tokens"] = written
            row["cache_write_12h_tokens"] = 0
        return row
    except ImportError:
        row["skipped"] = True
        row["success_reason"] = f"browser-use=={BROWSER_USE_VERSION} is not installed"
        row["wall_ms"] = (time.perf_counter() - started) * 1000
        return row
    except Exception as exc:
        from bench.openai_spend import PriceUnknown

        if isinstance(exc, PriceUnknown):
            raise
        row["success_reason"] = f"browser_use run failed: {type(exc).__name__}"
        row["wall_ms"] = (time.perf_counter() - started) * 1000
        return row
    finally:
        await _stop(browser)
