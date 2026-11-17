"""Replay a saved page through script_first. No model call and no network.

A HAR 1.2 log, or a saved page JSON object, is the only source of HTML.
page.goto looks up that exact URL and refuses anything that was not saved.
The script and the cu.click, cu.fill, and cu.press helpers then run against
that page. Wall time is the replay itself. model_calls, tokens, and usd stay
at zero.

The grade is grade_observation, including script_first's own verdict and the
claim the script returned. This module does not score the page itself.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

DOM_JS = Path(__file__).with_name("offline_dom.js")
_HTML_TYPES = {"text/html", "application/xhtml+xml"}
_DROPPED_ENV = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "BROWSERBASE_API_KEY")


class OfflineError(RuntimeError):
    """The replay refused a URL that is not in the saved pages."""


@dataclass(frozen=True)
class PageBook:
    """Exact URL to saved HTML. A missing URL is not fetched."""

    pages: dict[str, str]

    def html_for(self, url: str) -> str | None:
        if not isinstance(url, str):
            return None
        return self.pages.get(url)


@dataclass(frozen=True)
class ReplayRun:
    """One offline script_first run. The clock is this process, not a model."""

    wall_ms: float
    model_calls: int
    input_tokens: int
    output_tokens: int
    usd: float
    steps: int
    ok: bool
    verdict: str
    verdict_reason: str
    success: bool
    success_reason: str
    page_url: str
    text: str
    error: str
    shared_ok: bool | None


class _Builder(HTMLParser):
    """HTML to a JSON tree the offline DOM can build. No fetches."""

    _VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "#document", "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, void=tag.lower() in self._VOID)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, void=True)

    def _open(self, tag: str, attrs: list[tuple[str, str | None]], *, void: bool) -> None:
        node = {
            "tag": tag.lower(),
            "attrs": {key.lower(): value or "" for key, value in attrs},
            "children": [],
        }
        self.stack[-1]["children"].append(node)
        if not void:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == name:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1]["children"].append({"text": data})


def parse_html(html: str) -> dict:
    builder = _Builder()
    builder.feed(html or "")
    builder.close()
    return builder.root


def _html_from_content(content: dict) -> str:
    text = content.get("text") if isinstance(content.get("text"), str) else ""
    if content.get("encoding") == "base64":
        try:
            text = base64.b64decode(text).decode("utf-8", errors="replace")
        except (ValueError, TypeError) as exc:
            raise OfflineError("saved page content is not base64") from exc
    return text


def book_from_data(data: dict, *, root: Path | None = None) -> PageBook:
    """HAR 1.2 log, or a saved page with url and html. URLs must be unique."""
    if not isinstance(data, dict):
        raise OfflineError("a saved page must be a JSON object")
    pages: dict[str, str] = {}

    def add(url: str, html: str) -> None:
        if not isinstance(url, str) or not url.strip():
            raise OfflineError("a saved page has no URL")
        if url in pages:
            raise OfflineError(f"duplicate saved page for {url}")
        pages[url] = html if isinstance(html, str) else ""

    log = data.get("log")
    if isinstance(log, dict):
        entries = log.get("entries")
        if not isinstance(entries, list) or not entries:
            raise OfflineError("HAR log has no entries")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            request = entry.get("request") if isinstance(entry.get("request"), dict) else {}
            response = entry.get("response") if isinstance(entry.get("response"), dict) else {}
            content = response.get("content") if isinstance(response.get("content"), dict) else {}
            mime = str(content.get("mimeType") or "").split(";", 1)[0].strip().lower()
            if mime and mime not in _HTML_TYPES:
                continue
            url = request.get("url")
            if not isinstance(url, str):
                raise OfflineError("HAR entry has no URL")
            add(url, _html_from_content(content))
    elif isinstance(data.get("pages"), list):
        for item in data["pages"]:
            if not isinstance(item, dict):
                raise OfflineError("saved page entry is not an object")
            html = item.get("html")
            if not isinstance(html, str):
                name = item.get("file")
                if not isinstance(name, str) or root is None:
                    raise OfflineError("saved page entry has no html")
                html = (root / name).read_text(encoding="utf-8")
            add(str(item.get("url") or ""), html)
    elif isinstance(data.get("html"), str) and isinstance(data.get("url"), str):
        add(data["url"], data["html"])
    else:
        raise OfflineError("not a HAR log or a saved page")
    if not pages:
        raise OfflineError("saved pages are empty")
    return PageBook(pages)


def load_book(path: str | Path) -> PageBook:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfflineError(f"could not read saved pages from {source}") from exc
    return book_from_data(data, root=source.parent)


class _Dom:
    """One Node process. It only sees the HTML this replay hands it."""

    def __init__(self):
        node = shutil.which("node")
        if not node:
            raise OfflineError("node is required to replay a saved page")
        if not DOM_JS.is_file():
            raise OfflineError("offline page DOM is missing")
        env = os.environ.copy()
        for name in _DROPPED_ENV:
            env.pop(name, None)
        self.stderr: list[str] = []
        self.proc = subprocess.Popen(
            [node, "--no-warnings", str(DOM_JS)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._id = 0
        self._drain = threading.Thread(target=self._read_err, daemon=True)
        self._drain.start()

    def _read_err(self) -> None:
        pipe = self.proc.stderr
        if pipe is None:
            return
        try:
            for line in pipe:
                self.stderr.append(line)
        except Exception:
            return

    def call(self, op: str, **payload):
        if self.proc.stdin is None or self.proc.stdout is None:
            raise OfflineError("offline page is closed")
        self._id += 1
        message = {"id": self._id, "op": op, **payload}
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            detail = "".join(self.stderr).strip()
            raise OfflineError(detail or "offline page stopped")
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OfflineError("offline page returned a bad line") from exc
        if data.get("id") != self._id:
            raise OfflineError("offline page response was out of order")
        if not data.get("ok"):
            raise OfflineError(str(data.get("error") or "offline page failed"))
        return data.get("value")

    def close(self) -> None:
        if self.proc.poll() is not None:
            return
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class _Locator:
    def __init__(self, page: "ReplayPage", by: str, role: str, name: str, exact):
        self.page = page
        self.by = by
        self.role = role
        self.name = name
        # cu.click asks for one exact accessible name. An omitted flag stays exact.
        self.exact = True if exact is None else bool(exact)

    def _count(self) -> int:
        value = self.page._dom.call(
            "count",
            by=self.by,
            role=self.role,
            name=self.name,
            exact=self.exact,
        )
        return int(value)

    async def count(self) -> int:
        return self._count()

    async def click(self, **kwargs) -> None:
        del kwargs
        moved = self.page._act_on(self, "click", "")
        self.page._follow_value(moved)

    async def fill(self, value, **kwargs) -> None:
        del kwargs
        self.page._act_on(self, "fill", value)

    async def press(self, value, **kwargs) -> None:
        del kwargs
        moved = self.page._act_on(self, "press", value)
        self.page._follow_value(moved)

    async def check(self, **kwargs) -> None:
        del kwargs
        self.page._act_on(self, "check", "")

    async def uncheck(self, **kwargs) -> None:
        del kwargs
        self.page._act_on(self, "uncheck", "")


class ReplayPage:
    """Playwright-shaped page backed only by a saved book."""

    def __init__(self, book: PageBook):
        self.book = book
        self.url = "about:blank"
        self._dom: _Dom | None = None

    def close(self) -> None:
        if self._dom is not None:
            self._dom.close()
            self._dom = None

    def __enter__(self) -> "ReplayPage":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _engine(self) -> _Dom:
        if self._dom is None:
            self._dom = _Dom()
        return self._dom

    def _load(self, url: str) -> None:
        html = self.book.html_for(url)
        if html is None:
            raise OfflineError(f"offline replay has no saved page for {url}")
        self._engine().call("load", url=url, tree=parse_html(html))
        self.url = url

    def _follow_value(self, moved) -> None:
        if not isinstance(moved, dict):
            return
        href = moved.get("navigate")
        if not isinstance(href, str) or not href:
            return
        self._load(urljoin(self.url, href))

    def _act_on(self, locator: _Locator, action: str, value: str):
        return self._engine().call(
            "act",
            by=locator.by,
            role=locator.role,
            name=locator.name,
            exact=locator.exact,
            action=action,
            value=value,
        )

    def get_by_role(self, role, name=None, exact=None):
        return _Locator(self, "role", str(role or ""), str(name or ""), exact)

    def get_by_label(self, name, exact=None):
        return _Locator(self, "label", "", str(name or ""), exact)

    def get_by_text(self, name, exact=None):
        return _Locator(self, "text", "", str(name or ""), exact)

    def get_by_placeholder(self, name, exact=None):
        return _Locator(self, "placeholder", "", str(name or ""), exact)

    async def goto(self, url, **kwargs) -> None:
        del kwargs
        self._load(url)

    async def title(self) -> str:
        if self._dom is None or self.url == "about:blank":
            return ""
        value = self._dom.call("title")
        return value if isinstance(value, str) else ""

    async def evaluate(self, source):
        return self._engine().call("eval", source=source)


def replay_script(book: PageBook, script: str, task: dict) -> ReplayRun:
    """Run one script on the book and grade it with the shared observation grade.

    The task dict is the catalog task. Markers and checks are not rewritten.
    """
    from bench.probe import grade_observation
    from bench.script_first import claimed_from_payload, run_on_page, script_result_payload, script_verdict

    markers = task.get("end_markers") if isinstance(task.get("end_markers"), dict) else None
    started = time.perf_counter()
    page = ReplayPage(book)
    try:
        result_text = asyncio.run(run_on_page(page, script, end_markers=markers))
    finally:
        page.close()
    wall_ms = (time.perf_counter() - started) * 1000
    payload = script_result_payload(result_text)
    page_url = payload.get("url") if isinstance(payload.get("url"), str) else ""
    verdict, payload = script_verdict(markers or {}, result_text, page_url)
    claim = claimed_from_payload(payload)
    text = payload.get("text") if isinstance(payload.get("text"), str) else ""
    selector = payload.get("selector_text") if isinstance(payload.get("selector_text"), str) else ""
    success, reason, shared_ok, _shared_reason = grade_observation(
        task,
        page_url,
        text,
        selector_text=selector,
        answer=claim.answer,
        completed=None,
        completion_reason=verdict.reason,
        run_verdict=verdict.verdict,
        claimed=claim,
    )
    steps = payload.get("steps")
    return ReplayRun(
        wall_ms=wall_ms,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        usd=0.0,
        steps=int(steps) if isinstance(steps, int) else 0,
        ok=bool(payload.get("ok")),
        verdict=verdict.verdict,
        verdict_reason=verdict.reason,
        success=bool(success),
        success_reason=reason,
        page_url=page_url,
        text=text,
        error=payload.get("error") if isinstance(payload.get("error"), str) else "",
        shared_ok=shared_ok,
    )


def replay_manifest(path: str | Path) -> ReplayRun:
    """Load a manifest, its fixture, and the catalog task. Then replay the script."""
    from bench.tasks import task_by_id

    source = Path(path)
    try:
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfflineError(f"could not read replay manifest {source}") from exc
    if not isinstance(manifest, dict):
        raise OfflineError("replay manifest must be an object")
    fixture = manifest.get("fixture")
    task_id = manifest.get("task_id")
    script = manifest.get("script")
    if not isinstance(fixture, str) or not isinstance(task_id, str) or not isinstance(script, str):
        raise OfflineError("replay manifest needs fixture, task_id, and script")
    task = task_by_id(task_id)
    if task is None:
        raise OfflineError(f"unknown task {task_id}")
    book = load_book(source.parent / fixture)
    return replay_script(book, script, task)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay a saved page through script_first. No model and no network."
    )
    parser.add_argument("manifest", help="JSON file with a HAR or saved page, a task id, and a script")
    args = parser.parse_args(argv)
    try:
        run = replay_manifest(args.manifest)
    except OfflineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(asdict(run), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
