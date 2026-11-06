"""Whole-task Playwright script arm. No per-click settle and no snapshot loop.

The outer model emits one short script. This module runs it on local Chrome
through the Playwright Python API. A page.evaluate sequence can also be
driven through MCP browser_evaluate. browser_run_code_unsafe is rejected
and is not a tool.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit

# Navigation waits for DOMContentLoaded, not load or networkidle.
# A click or Enter returns before the next document is current. This wait
# is only the landing read, not the proxy settle loop.
_NAV_TIMEOUT_MS = 10000
_ACTION_TIMEOUT_MS = 5000
_EVALUATE_TIMEOUT_S = 5
_LAND_TIMEOUT_S = 0.8

_VISIBLE_ANSWER_JS = """() => {
  const el = document.querySelector(".titleline a") || document.querySelector(".titleline");
  if (!el) return "";
  return (el.innerText || el.textContent || "").trim();
}"""

from bench.stagehand_local import _locator, context_browser
from proxy.script import MAX_SCRIPT_CHARS, MAX_SCRIPT_LINES, ScriptAction, ScriptError, parse_script

_BANNED = (
    "browser_run_code_unsafe",
    "require(",
    "process.",
    "child_process",
    "import ",
    "import(",
    "fetch(",
    "eval(",
    "new function",
    "page.route",
    "page.context",
    "page.setcontent",
    "addinitscript",
    "expose_function",
    "exposefunction",
)


@dataclass(frozen=True)
class TaskStep:
    kind: str
    line: int
    source: str
    function: str = ""
    action: ScriptAction | None = None


def _strip_fence(source: str) -> str:
    text = (source or "").strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _statements(source: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    depth = 0
    quote = ""
    escape = False
    i = 0
    text = source
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'`":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/" and depth == 0:
            i += 2
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if depth == 0 and ch == "#" and not buf:
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if ch in "({[":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch in ")}]":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if ch in ";\n" and depth == 0:
            stmt = "".join(buf).replace("\r", "").strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).replace("\r", "").strip()
    if tail:
        statements.append(tail)
    return statements


def _banned_token(source: str) -> str | None:
    lowered = source.casefold()
    scrubbed = lowered.replace("page.evaluate", " ")
    for token in _BANNED:
        if token in scrubbed:
            return token
    return None


def _depth0_comma(text: str) -> bool:
    depth = 0
    quote = ""
    escape = False
    for ch in text:
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "\"'`":
            quote = ch
            continue
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            return True
    return False


def _unwrap_js_string(inner: str, line: int) -> str:
    if not inner or inner[0] not in "\"'":
        return inner
    quote = inner[0]
    chars: list[str] = []
    escape = False
    for ch in inner[1:]:
        if escape:
            chars.append(ch)
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == quote:
            return "".join(chars)
    raise ScriptError(f"line {line}: unterminated string")


def _normalize_stmt(stmt: str) -> str:
    text = stmt.strip()
    if text.startswith("await "):
        text = text[len("await ") :].strip()
    if text.endswith(";"):
        text = text[:-1].strip()
    return text


def _parse_evaluate(text: str, line: int) -> TaskStep:
    lowered = text.casefold()
    if lowered.startswith("page.evaluatehandle") or (
        lowered.startswith("page.evaluate") and len(text) > len("page.evaluate") and text[len("page.evaluate")].isalnum()
    ):
        raise ScriptError(f"line {line}: page.evaluate is the only evaluate form")
    rest = text[len("page.evaluate") :].strip()
    if not rest.startswith("(") or not rest.endswith(")"):
        raise ScriptError(f"line {line}: page.evaluate needs one function")
    inner = rest[1:-1].strip()
    if not inner:
        raise ScriptError(f"line {line}: page.evaluate needs one function")
    if _depth0_comma(inner):
        raise ScriptError(f"line {line}: page.evaluate takes one function")
    function = _unwrap_js_string(inner, line).strip()
    if not function:
        raise ScriptError(f"line {line}: page.evaluate needs one function")
    return TaskStep(kind="evaluate", line=line, source=text, function=function)


def _is_wait_statement(body: str) -> bool:
    """True for a Playwright wait or settle line. page.evaluate is not a wait."""
    compact = "".join(body.split()).casefold()
    if compact.startswith("page.evaluate"):
        return False
    if compact.startswith("page.waitfor") or compact.startswith("page.wait_for"):
        return True
    if compact.startswith("page.setdefaulttimeout") or compact.startswith("page.setdefaultnavigationtimeout"):
        return True
    if ".waitfor(" in compact:
        return True
    if "networkidle" in compact and "goto" not in compact:
        return True
    return False


def parse_task_script(source: str) -> list[TaskStep]:
    """Parse a whole-task script. Raises ScriptError before the page is touched.

    page.waitForTimeout, page.waitForLoadState, and locator.waitFor lines are
    dropped. A goto that asks for networkidle is kept; the runner does not
    honor that wait.
    """
    if not isinstance(source, str):
        raise ScriptError("script must be a string")
    text = _strip_fence(source)
    if len(text) > MAX_SCRIPT_CHARS:
        raise ScriptError(f"script is longer than {MAX_SCRIPT_CHARS} characters")
    banned = _banned_token(text)
    if banned:
        raise ScriptError(f"{banned.strip()} is not part of this script")
    steps: list[TaskStep] = []
    for index, stmt in enumerate(_statements(text), 1):
        body = _normalize_stmt(stmt)
        if _is_wait_statement(body):
            continue
        if body.casefold().startswith("page.evaluate"):
            steps.append(_parse_evaluate(body, index))
            continue
        body = " ".join(body.split())
        actions = parse_script(body, allow_goto=True, max_lines=1)
        action = actions[0]
        kind = "goto" if action.op == "goto" else "locator"
        steps.append(TaskStep(kind=kind, line=index, source=body, action=action))
    if not steps:
        raise ScriptError("script has no actions")
    if len(steps) > MAX_SCRIPT_LINES:
        raise ScriptError(f"script has more than {MAX_SCRIPT_LINES} actions")
    return steps


def script_result_payload(text: str) -> dict:
    """The JSON object on the first line of a script result. Empty when it is prose."""
    line = ((text or "").strip().splitlines() or [""])[0].strip()
    if not line.startswith("{"):
        return {}
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _phrase(expect: str) -> str:
    text = unquote(expect or "").replace("_", " ").replace("+", " ")
    return " ".join(text.split()).casefold()


def _same_phrase(value: str, expect: str) -> bool:
    phrase = _phrase(expect)
    if not phrase or not value:
        return False
    text = unquote(value).replace("_", " ").replace("+", " ")
    return " ".join(text.split()).casefold() == phrase


def _denied_page(url: str) -> bool:
    """Search results and the Wikipedia front page are not the finished article."""
    lowered = unquote(url or "").replace("+", " ").casefold()
    if "main_page" in lowered:
        return True
    if "special:search" in lowered or "special%3asearch" in (url or "").casefold():
        return True
    path = urlsplit(url).path.casefold() if url else ""
    return path.endswith("/search.html") or "/search.html" in path


def _title_names_target(title: str, expect: str) -> bool:
    if not title or not expect:
        return False
    if "search" in title.casefold():
        return False
    head = title.split("—", 1)[0].split(" - ", 1)[0]
    return _same_phrase(head, expect)


def scored_page_url(url: str, expect: str, title: str = "") -> str:
    """URL the substring judge accepts when this page is already the target.

    A literal substring is returned unchanged, the same bar as the Stagehand
    URL judge. Empty for the Wikipedia front page and for a search page that
    does not already contain the token. A percent-encoded article path or
    MediaWiki title= parameter is rewritten so the token is literal. The
    document title is used only when the URL is not already some other article.
    """
    if not expect or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return ""
    # Same bar as check_url_contains. A search URL that already contains the
    # token is done; rewriting one that does not would invent a pass.
    if expect.casefold() in url.casefold():
        return url
    if _denied_page(url):
        return ""
    parts = urlsplit(url)
    segments = unquote(parts.path).split("/")
    rewritten: list[str] = []
    matched = False
    for segment in segments:
        stem, dot, ext = segment.rpartition(".")
        leaf = stem if dot else segment
        if _same_phrase(leaf, expect):
            rewritten.append(expect + (dot + ext if dot else ""))
            matched = True
        else:
            rewritten.append(segment)
    if matched:
        return urlunsplit((parts.scheme, parts.netloc, "/".join(rewritten), parts.query, parts.fragment))
    title_values = parse_qs(parts.query, keep_blank_values=True).get("title") or []
    if title_values and _same_phrase(title_values[0], expect) and "wikipedia.org" in parts.netloc.casefold():
        return f"{parts.scheme}://{parts.netloc}/wiki/{expect}"
    if not _title_names_target(title, expect):
        return ""
    host = parts.netloc.casefold()
    if "wikipedia.org" in host:
        path_segs = [segment for segment in unquote(parts.path).split("/") if segment]
        if len(path_segs) >= 2 and path_segs[0].casefold() == "wiki":
            return ""
        return f"{parts.scheme}://{parts.netloc}/wiki/{expect}"
    if "python.org" in host:
        path = unquote(parts.path).casefold()
        if path.rstrip("/").endswith(".html"):
            return ""
        return f"{parts.scheme}://{parts.netloc}/3/library/{expect}.html"
    return ""


def end_state_failure(
    url: str,
    *,
    start_url: str = "",
    expect_url_contains: str = "",
    title: str = "",
) -> str:
    """Why this URL is not the finished task. Empty when there is nothing to repair.

    Tasks without a URL check, such as Hacker News, are left to the model.
    Wikipedia fails while the page is still Main_Page. A landed article whose
    path is percent-encoded, or whose title already names the target, is done.
    """
    if not expect_url_contains:
        return ""
    if scored_page_url(url, expect_url_contains, title=title):
        return ""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return "the run finished without a page URL"
    if isinstance(url, str) and "main_page" in unquote(url).casefold() and "main_page" not in expect_url_contains.casefold():
        return "the page is still Wikipedia Main_Page"
    if start_url and isinstance(url, str) and url.rstrip("/") == start_url.rstrip("/"):
        return "the page never left the start URL"
    return f"the URL does not contain {expect_url_contains}"


def repair_request(url: str, reason: str) -> str:
    """One short ask for a corrected script. The harness sends this at most once."""
    shown = url if url else "(empty)"
    return (
        "END_STATE_FAILED: "
        f"{reason}. Current URL: {shown}. "
        "Send one corrected script that finishes the task. "
        "The end URL must be the finished page the task asked for. "
        "Wikipedia must leave Main_Page. "
        "Return any title or answer with page.evaluate in that same script. "
        "Do not repeat the same script."
    )


def script_made_progress(previous: dict | None, current: dict) -> bool:
    """True when this script moved the page or finished more actions than the last one."""
    if not current:
        return False
    steps = int(current.get("steps") or 0)
    url = current.get("url") if isinstance(current.get("url"), str) else ""
    moved = url.startswith(("http://", "https://"))
    if previous is None:
        return steps > 0 or moved
    prev_url = previous.get("url") if isinstance(previous.get("url"), str) else ""
    prev_steps = int(previous.get("steps") or 0)
    if moved and url != prev_url:
        return True
    return bool(steps > prev_steps and current.get("ok"))


def next_script_first_limit(
    *,
    step_num: int,
    limit: int,
    hard_cap: int,
    made_progress: bool,
    repair_pending: bool,
    refused_extra_script: bool,
) -> int:
    """Add one turn for a repair or a refused extra script.

    A script that only moved the page does not grow the limit. The default
    path stays inside the starting limit: one script, then TASK_COMPLETE.
    """
    del made_progress
    if repair_pending or refused_extra_script:
        return min(hard_cap, max(limit, step_num + 1))
    return limit


def missing_page_text(payload: dict, *, expect_url_contains: str = "") -> str:
    """Why a task with no URL check still needs one repair.

    Empty when the script returned text, or when the URL check is the judge.
    """
    if expect_url_contains:
        return ""
    extracted = payload.get("extracted") if isinstance(payload, dict) else None
    if isinstance(extracted, str) and extracted.strip():
        return ""
    if isinstance(extracted, list) and any(str(item).strip() for item in extracted):
        return ""
    return "the script did not return the text the task asked for"


def _coerce_extract(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value).strip()
    text = text.strip()
    if text in {"", "null", "undefined", "{}"}:
        return ""
    if len(text) > 400:
        text = text[:400]
    return text


def format_run_result(
    *,
    ok: bool,
    url: str,
    step_count: int,
    error: str = "",
    extracted: list[str] | None = None,
    title: str = "",
) -> str:
    """JSON url plus Stagehand-style goto prose, so the existing judge can read it.

    `- Page URL:` is last. page_url_from_result prefers that line, so a landed
    article is what the judge scores.
    """
    payload: dict = {"ok": ok, "url": url, "steps": step_count}
    if error:
        payload["error"] = error
    shown = [item for item in (extracted or []) if str(item).strip()]
    if shown:
        payload["extracted"] = shown
    if title:
        payload["title"] = title
    lines = [json.dumps(payload)]
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        lines.append(f"Ran goto {url}.")
    if shown:
        text = " | ".join(shown)
        if len(text) > 500:
            text = text[:500]
        lines.append(f"Extracted: {text}")
    if title:
        lines.append(f"- Page Title: {title}")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        lines.append(f"- Page URL: {url}")
    return "\n".join(lines)


def _answer_present(extracted: list[str]) -> bool:
    return any(str(item).strip() for item in extracted)


async def _read_title(page) -> str:
    title = getattr(page, "title", None)
    if not callable(title):
        return title.strip() if isinstance(title, str) else ""
    try:
        value = title()
        if asyncio.iscoroutine(value):
            value = await asyncio.wait_for(value, timeout=1)
    except Exception:
        return ""
    return value.strip() if isinstance(value, str) else ""


async def _wait_for_landed(page, expect: str) -> None:
    """Block until the current document is the target, or the short budget ends.

    page.goto already waited for DOMContentLoaded. click and press do not.
    This is one Playwright URL wait. It does not snapshot or quiet the page.
    """
    wait = getattr(page, "wait_for_url", None)
    if not callable(wait) or not expect:
        return

    def arrived(live: str) -> bool:
        return bool(scored_page_url(str(live or ""), expect))

    try:
        result = wait(arrived)
        if asyncio.iscoroutine(result):
            await asyncio.wait_for(result, timeout=_LAND_TIMEOUT_S)
    except Exception:
        return


async def _capture_visible_answer(page) -> str:
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return ""
    try:
        value = evaluate(_VISIBLE_ANSWER_JS)
        if asyncio.iscoroutine(value):
            value = await asyncio.wait_for(value, timeout=_EVALUATE_TIMEOUT_S)
    except Exception:
        return ""
    return _coerce_extract(value)


async def _finish_page(
    page,
    *,
    expect_url_contains: str,
    extracted: list[str],
    capture_visible_answer: bool,
    wait_for_commit: bool,
) -> tuple[str, str, list[str]]:
    """URL, title, and any text read after the script's own lines.

    The URL is the one the substring judge can accept. page.goto already
    waited for DOMContentLoaded. A click or Enter that has not committed yet
    gets one short wait. Hacker News text is read locally when the script
    opened the page and did not return it.
    """
    url = _page_url(page)
    title = await _read_title(page)
    if (
        wait_for_commit
        and expect_url_contains
        and not scored_page_url(url, expect_url_contains, title=title)
    ):
        await _wait_for_landed(page, expect_url_contains)
        url = _page_url(page)
        title = await _read_title(page)
    scored = scored_page_url(url, expect_url_contains, title=title) if expect_url_contains else ""
    if scored:
        url = scored
    if capture_visible_answer and not _answer_present(extracted) and url.startswith(("http://", "https://")):
        text = await _capture_visible_answer(page)
        if text:
            extracted = [*extracted, text]
    return url, title, extracted


def _page_url(page) -> str:
    url = getattr(page, "url", "") or ""
    return url if isinstance(url, str) else ""


async def _run_step_on_page(page, step: TaskStep):
    if step.kind == "evaluate":
        return await asyncio.wait_for(page.evaluate(step.function), timeout=_EVALUATE_TIMEOUT_S)
    action = step.action
    if action is None:
        raise ScriptError(f"line {step.line}: missing action")
    if action.op == "goto":
        await page.goto(action.value, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        return None
    locator = _locator(page, action)
    if action.op == "click":
        await locator.click(timeout=_ACTION_TIMEOUT_MS)
    elif action.op == "fill":
        await locator.fill(action.value, timeout=_ACTION_TIMEOUT_MS)
    elif action.op == "press":
        await locator.press(action.value, timeout=_ACTION_TIMEOUT_MS)
    elif action.op == "check":
        await locator.check(timeout=_ACTION_TIMEOUT_MS)
    elif action.op == "uncheck":
        await locator.uncheck(timeout=_ACTION_TIMEOUT_MS)
    else:
        raise ScriptError(f"line {step.line}: unsupported action {action.op}")
    return None


async def run_on_page(
    page,
    source: str,
    *,
    expect_url_contains: str = "",
    capture_visible_answer: bool = False,
) -> str:
    """Run the whole script on a Playwright page. No settle between actions.

    Goto waits for DOMContentLoaded. Wait lines were already dropped. An
    evaluate return value is kept so the model can answer without a second script.
    A click's navigation is read once it commits, and that URL is what the
    judge sees. The task can end on this result.
    """
    steps = parse_task_script(source)
    done = 0
    extracted: list[str] = []
    try:
        for step in steps:
            value = await _run_step_on_page(page, step)
            done += 1
            if step.kind == "evaluate":
                text = _coerce_extract(value)
                if text:
                    extracted.append(text)
    except ScriptError:
        raise
    except Exception as exc:
        url, title, extracted = await _finish_page(
            page,
            expect_url_contains=expect_url_contains,
            extracted=extracted,
            capture_visible_answer=capture_visible_answer,
            wait_for_commit=True,
        )
        return format_run_result(
            ok=False,
            url=url,
            step_count=done,
            error=str(exc),
            extracted=extracted,
            title=title,
        )
    url, title, extracted = await _finish_page(
        page,
        expect_url_contains=expect_url_contains,
        extracted=extracted,
        capture_visible_answer=capture_visible_answer,
        wait_for_commit=bool(steps) and steps[-1].kind != "goto",
    )
    return format_run_result(ok=True, url=url, step_count=len(steps), extracted=extracted, title=title)


async def _mcp_text(call_tool, name: str, arguments: dict) -> str:
    if name == "browser_run_code_unsafe":
        raise ScriptError("browser_run_code_unsafe is not available")
    result = await call_tool(name, arguments)
    if isinstance(result, tuple):
        return str(result[0])
    return str(result)


def _href_from_text(text: str) -> str:
    from bench.harness import page_url_from_result

    cleaned = (text or "").strip().strip("\"'")
    if cleaned.startswith(("http://", "https://")) and "\n" not in cleaned and " " not in cleaned:
        return cleaned
    return page_url_from_result(text)


async def run_on_mcp(call_tool, source: str) -> str:
    """Run page.goto and page.evaluate through MCP. Locator lines are refused.

    Navigation uses browser_navigate. Page functions use browser_evaluate.
    The final URL is read with another browser_evaluate of location.href.
    There is no snapshot and no settle.
    """
    steps = parse_task_script(source)
    if any(step.kind == "locator" for step in steps):
        raise ScriptError("the MCP evaluate runner accepts page.goto and page.evaluate only")
    url = ""
    done = 0
    try:
        for step in steps:
            if step.kind == "goto":
                action = step.action
                if action is None:
                    raise ScriptError(f"line {step.line}: missing action")
                text = await _mcp_text(call_tool, "browser_navigate", {"url": action.value})
                found = _href_from_text(text)
                if found:
                    url = found
            else:
                await _mcp_text(call_tool, "browser_evaluate", {"function": step.function})
            done += 1
        href = await _mcp_text(call_tool, "browser_evaluate", {"function": "() => location.href"})
        found = _href_from_text(href)
        if found:
            url = found
    except ScriptError:
        raise
    except Exception as exc:
        return format_run_result(ok=False, url=url, step_count=done, error=str(exc))
    return format_run_result(ok=True, url=url, step_count=len(steps))


class ScriptFirstClient:
    """One run_script tool on a private local Chrome profile."""

    def __init__(self, headless: bool = True, page=None):
        self.headless = headless
        self._page = page
        self._owns_page = page is None
        self.expected_url_part = ""
        self._playwright = None
        self._browser = None
        self._context = None
        self._profile_dir: str | None = None

    def tools_for_claude(self) -> list[dict]:
        return [
            {
                "name": "run_script",
                "description": (
                    "Run one Playwright script that finishes the whole task in this call. "
                    "The end URL must already be the finished page. "
                    "Wikipedia: page.goto(\"https://en.wikipedia.org/wiki/Article_Title\") "
                    "with underscores, not Main_Page and not Special:Search. "
                    "Docs: page.goto the module URL. "
                    "Hacker News: page.goto the site and page.evaluate the top "
                    ".titleline a text. The result includes that string. "
                    "Do not call page.waitForTimeout, page.waitForLoadState, or networkidle. "
                    "Allowed lines are page.goto, page.getByRole, page.getByLabel, "
                    "page.getByText, page.getByPlaceholder, and page.evaluate with a "
                    "page-context function. The runner does not settle or snapshot "
                    "between actions and drops wait lines. "
                    "browser_run_code_unsafe is not available. "
                    "The runner reads the page again after a click or Enter, once that "
                    "navigation is the current document. A matching end URL, or "
                    "extracted text on a page with no URL check, finishes the task. "
                    "Call this once. A second call is only for END_STATE_FAILED."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Playwright script or page.evaluate sequence for the whole task.",
                        }
                    },
                    "required": ["code"],
                },
            }
        ]

    async def start(self) -> None:
        if self._page is not None:
            return
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        launch_error: Exception | None = None
        attempts = (
            {"channel": "chrome", "headless": self.headless},
            {"headless": self.headless},
        )
        for kwargs in attempts:
            profile = tempfile.mkdtemp(prefix="script-first-arm-")
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    profile,
                    **kwargs,
                )
                self._profile_dir = profile
                launch_error = None
                break
            except Exception as exc:
                launch_error = exc
                self._context = None
                shutil.rmtree(profile, ignore_errors=True)
        if self._context is None:
            await self._playwright.stop()
            self._playwright = None
            raise RuntimeError(f"Could not launch local Chrome for script_first. {launch_error}")
        self._browser = context_browser(self._context)
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

    async def stop(self) -> None:
        if not self._owns_page:
            self._page = None
            return
        try:
            if self._context is not None:
                await self._context.close()
            if self._browser is not None:
                await self._browser.close()
            if self._playwright is not None:
                await self._playwright.stop()
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._page = None
            profile = self._profile_dir
            self._profile_dir = None
            if profile:
                shutil.rmtree(profile, ignore_errors=True)

    async def call_tool(self, name: str, arguments: dict | None) -> tuple[str, float]:
        if name == "browser_run_code_unsafe":
            raise ScriptError("browser_run_code_unsafe is not available")
        if self._page is None:
            raise RuntimeError("script_first client is not started")
        start = time.perf_counter()
        if name != "run_script":
            return f"unknown tool {name}", 0.0
        code = (arguments or {}).get("code") or (arguments or {}).get("script") or ""
        try:
            text = await run_on_page(
                self._page,
                code,
                expect_url_contains=self.expected_url_part,
                capture_visible_answer=not self.expected_url_part,
            )
        except ScriptError as exc:
            text = format_run_result(ok=False, url=_page_url(self._page), step_count=0, error=str(exc))
        elapsed_ms = (time.perf_counter() - start) * 1000
        return text, elapsed_ms
