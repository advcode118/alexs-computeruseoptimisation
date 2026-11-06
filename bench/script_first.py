"""Whole-task Playwright script arm. No per-click settle and no snapshot loop.

The outer model emits one short script. This module runs it on local Chrome
through the Playwright Python API. A page.evaluate sequence can also be
driven through MCP browser_evaluate. browser_run_code_unsafe is rejected
and is not a tool.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from dataclasses import dataclass

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


def parse_task_script(source: str) -> list[TaskStep]:
    """Parse a whole-task script. Raises ScriptError before the page is touched."""
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


def format_run_result(*, ok: bool, url: str, step_count: int, error: str = "") -> str:
    """JSON url plus Stagehand-style goto prose, so the existing judge can read it."""
    payload: dict = {"ok": ok, "url": url, "steps": step_count}
    if error:
        payload["error"] = error
    lines = [json.dumps(payload)]
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        lines.append(f"Ran goto {url}.")
    return "\n".join(lines)


def _page_url(page) -> str:
    url = getattr(page, "url", "") or ""
    return url if isinstance(url, str) else ""


async def _run_step_on_page(page, step: TaskStep) -> None:
    if step.kind == "evaluate":
        await page.evaluate(step.function)
        return
    action = step.action
    if action is None:
        raise ScriptError(f"line {step.line}: missing action")
    if action.op == "goto":
        await page.goto(action.value)
        return
    locator = _locator(page, action)
    if action.op == "click":
        await locator.click()
    elif action.op == "fill":
        await locator.fill(action.value)
    elif action.op == "press":
        await locator.press(action.value)
    elif action.op == "check":
        await locator.check()
    elif action.op == "uncheck":
        await locator.uncheck()
    else:
        raise ScriptError(f"line {step.line}: unsupported action {action.op}")


async def run_on_page(page, source: str) -> str:
    """Run the whole script on a Playwright page. No settle between actions."""
    steps = parse_task_script(source)
    done = 0
    try:
        for step in steps:
            await _run_step_on_page(page, step)
            done += 1
    except ScriptError:
        raise
    except Exception as exc:
        return format_run_result(ok=False, url=_page_url(page), step_count=done, error=str(exc))
    return format_run_result(ok=True, url=_page_url(page), step_count=len(steps))


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
        self._playwright = None
        self._browser = None
        self._context = None
        self._profile_dir: str | None = None

    def tools_for_claude(self) -> list[dict]:
        return [
            {
                "name": "run_script",
                "description": (
                    "Run one short Playwright script for the whole task. "
                    "Allowed lines are page.goto, page.getByRole, page.getByLabel, "
                    "page.getByText, page.getByPlaceholder, and page.evaluate with a "
                    "page-context function. The runner does not settle or snapshot "
                    "between actions. browser_run_code_unsafe is not available."
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
            text = await run_on_page(self._page, code)
        except ScriptError as exc:
            text = format_run_result(ok=False, url=_page_url(self._page), step_count=0, error=str(exc))
        elapsed_ms = (time.perf_counter() - start) * 1000
        return text, elapsed_ms
