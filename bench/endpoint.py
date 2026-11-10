"""Direct read of a task start URL.

The transport's URL is the URL the evidence judge sees. This module copies
that string and does not rewrite it. It does not launch a browser. A miss
is returned to the caller, which runs script_first.
"""

from __future__ import annotations

from html.parser import HTMLParser

from bench.script_first import PASS, ClaimedEvidence, PageEvidence, evidence_verdict

_TITLELINE_ANCHOR = ".titleline a"
_VOID = {"link", "meta", "br", "img", "hr", "input", "source", "wbr"}


class EndpointError(RuntimeError):
    """The endpoint arm refused to open a network connection or a browser."""


class EndpointClient:
    """Placeholder client. The probe never starts it."""

    async def start(self) -> None:
        raise EndpointError("endpoint does not launch a browser")

    async def stop(self) -> None:
        return None

    def tools_for_claude(self) -> list[dict]:
        return []


class _Reader(HTMLParser):
    """Title, h1, canonical href, visible text, and one optional selector."""

    def __init__(self, selector: str):
        super().__init__(convert_charrefs=True)
        self.selector = selector
        self.title = ""
        self.h1 = ""
        self.canonical = ""
        self.selector_text = ""
        self._text: list[str] = []
        self._mode: list[str] = []
        self._skip = 0
        self._open: list[bool] = []
        self._anchor: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, void=tag.lower() in _VOID)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, void=True)

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], *, void: bool) -> None:
        name = tag.lower()
        attr = {key.lower(): value or "" for key, value in attrs}
        if name in {"script", "style", "noscript"}:
            self._skip += 1
            if not void:
                self._open.append(False)
            return
        classes = set(attr.get("class", "").split())
        own = "titleline" in classes
        if name == "link" and "canonical" in attr.get("rel", "").lower() and not self.canonical:
            self.canonical = attr.get("href", "")
        if not void:
            inside = own or any(self._open)
            if (
                self.selector == _TITLELINE_ANCHOR
                and name == "a"
                and inside
                and self._anchor is None
                and not self.selector_text
            ):
                self._anchor = []
            self._open.append(own)
            if name == "title" and not self.title:
                self._mode.append("title")
            elif name == "h1" and not self.h1:
                self._mode.append("h1")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
            if self._open:
                self._open.pop()
            return
        if self._mode and self._mode[-1] == "title" and name == "title":
            self._mode.pop()
        elif self._mode and self._mode[-1] == "h1" and name == "h1":
            self._mode.pop()
        if name == "a" and self._anchor is not None and not self.selector_text:
            self.selector_text = " ".join("".join(self._anchor).split())
            self._anchor = None
        if self._open:
            self._open.pop()

    def handle_data(self, data: str) -> None:
        if self._skip or not data:
            return
        if self._mode and self._mode[-1] == "title" and not self.title:
            self.title += data
        elif self._mode and self._mode[-1] == "h1" and not self.h1:
            self.h1 += data
        else:
            self._text.append(data)
        if self._anchor is not None:
            self._anchor.append(data)

    @property
    def text(self) -> str:
        return " ".join("".join(self._text).split())


def page_from_html(url: str, html: str, *, selector: str = "") -> dict:
    """Read a fetched document. `url` is stored byte for byte."""
    if not isinstance(url, str):
        raise EndpointError("the transport returned no URL")
    reader = _Reader(selector)
    reader.feed(html or "")
    reader.close()
    page = {
        "url": url,
        "title": " ".join(reader.title.split()),
        "canonical": reader.canonical.strip(),
        "h1": " ".join(reader.h1.split()),
        "text": reader.text,
        "selector_text": reader.selector_text,
    }
    if page["url"] != url:
        raise EndpointError("endpoint rewrote the fetched URL")
    return page


def fetch_start_url(url: str, *, opener, selector: str = "") -> dict:
    """GET `url` through `opener`. No opener means no network and no browser."""
    if opener is None:
        raise EndpointError("refusing to open a network connection")
    response = opener(url)
    final = response.geturl()
    if not isinstance(final, str):
        raise EndpointError("the transport returned no URL")
    body = response.read()
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    return page_from_html(final, body, selector=selector)


def judge_page(task: dict, page: dict) -> tuple:
    """Judge one fetched page. The live URL is the transport URL, unchanged."""
    raw = page.get("url") if isinstance(page.get("url"), str) else ""
    evidence = PageEvidence(
        url=raw,
        title=page.get("title") if isinstance(page.get("title"), str) else "",
        canonical=page.get("canonical") if isinstance(page.get("canonical"), str) else "",
        h1=page.get("h1") if isinstance(page.get("h1"), str) else "",
        text=page.get("text") if isinstance(page.get("text"), str) else "",
        selector_text=page.get("selector_text") if isinstance(page.get("selector_text"), str) else "",
    )
    if evidence.url != raw:
        raise EndpointError("endpoint rewrote the URL the judge sees")
    markers = dict(task.get("end_markers") or {})
    claimed = ClaimedEvidence(answer=evidence.selector_text) if evidence.selector_text else ClaimedEvidence()
    verdict = evidence_verdict(markers, evidence, claimed)
    allowed = {item for item in (evidence.url, evidence.canonical) if item}
    if verdict.scored_url and verdict.scored_url not in allowed:
        raise EndpointError("the scored URL is not the live URL or the canonical href")
    hit = verdict.verdict == PASS and raw.startswith(("http://", "https://"))
    row = {
        "arm": "endpoint",
        "task_id": task.get("id") or "",
        "success": hit,
        "success_reason": verdict.reason,
        "end_state": verdict.verdict,
        "page_url": raw,
        "scored_url": verdict.scored_url,
        "skipped": False,
        "wall_ms": 0.0,
        "steps": 1 if raw else 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0.0,
        "model_ignores_tools": 0,
        "no_model": True,
        "replay_hit": False,
        "tier": "endpoint" if hit else "",
        "model_calls": 0,
        "script_steps": 0,
        "claude": False,
        "endpoint_miss": not hit,
    }
    return verdict, evidence, row


async def run_endpoint_task(task: dict, page: dict, *, fallback):
    """Return an endpoint hit, or whatever `fallback` returns for script_first."""
    _verdict, evidence, row = judge_page(task, page)
    if row["success"]:
        return row
    followed = await fallback(task)
    followed = dict(followed)
    followed["arm"] = "script_first"
    followed["endpoint_miss"] = True
    followed["endpoint_url"] = evidence.url
    return followed
