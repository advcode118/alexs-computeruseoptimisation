"""A compact summary of script_first's start page for the first model call.

The page is fetched over plain HTTP while Chrome launches, so the model can
write its first script against the page's real links, search form and field
labels instead of guessing them. No browser and no model call is used here.

Every failure (timeout, block, non-HTML, a JavaScript shell with no content)
returns an empty summary, and the caller keeps today's blind path.

CU_PAGE_SUMMARY=1 opts in, so off/on runs use the same code. It is off by default.
"""

from __future__ import annotations

import asyncio
import gzip
import io
import os
import re
import threading
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

ENV_SWITCH = "CU_PAGE_SUMMARY"
FETCH_TIMEOUT_S = 1.5
MAX_HTML_BYTES = 1_500_000
# Parsing costs about 0.5 ms per KB, so a huge page is cut before parsing.
MAX_PARSE_CHARS = 600_000
_STRIP_BLOCKS = re.compile(r"<(script|style|svg)\b.*?</\1\s*>|<!--.*?-->", re.I | re.S)
# Links past this many are not ranked.
MAX_RANKED_LINKS = 1500
MAX_TEXTS_PER_URL = 16
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Caps keep the summary near 1,000-1,500 tokens.
MAX_LINKS = 45
MAX_MATCHED_LINKS = 30
MAX_LINK_TEXT = 70
MAX_H2 = 12
MAX_BUTTONS = 12
MAX_FORMS = 3
MAX_FIELDS = 10
MAX_OPTIONS = 8
MAX_SUMMARY_CHARS = 6000
# Less visible text than this, with few links, reads as a JavaScript shell.
MIN_TEXT_CHARS = 200
MIN_LINKS = 3

STATUS_OK = "ok"
# A normal Chrome navigation. Some sites refuse a request without the Sec-Fetch headers.
_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or that the
    this to was were with which what who whom whose open report page find use using
    then than not do does did stop give value exact from listed list your their
    there here one two all any each also only own very about after before over under
    starting start site official documentation docs home index section chapter
    search look up enter fill submit form click result results type""".split()
)

_SKIP_TEXT_TAGS = frozenset({"script", "style", "noscript", "template", "svg", "head"})
_VOID = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
)
_TEXT_INPUT_TYPES = frozenset({"", "text", "search", "email", "tel", "url", "number", "password", "date"})
_SEARCH_WORDS = ("search", "query", "find")
_SEARCH_NAMES = frozenset({"q", "s", "query", "search", "searchtext", "search_query", "k", "term", "keywords"})


def enabled() -> bool:
    """Explicit opt-in until repeated measurements justify a default change."""
    return os.environ.get(ENV_SWITCH, "0").strip().lower() in {"1", "on", "true", "yes"}


@dataclass
class Fetched:
    url: str
    final_url: str = ""
    status: int = 0
    html: str = ""
    error: str = ""
    ms: float = 0.0


@dataclass
class Field:
    tag: str
    type: str
    name: str
    label: str = ""
    value: str = ""
    options: list[str] = field(default_factory=list)


@dataclass
class Form:
    action: str
    method: str
    role_search: bool = False
    attrs_text: str = ""
    fields: list[Field] = field(default_factory=list)
    submits: list[str] = field(default_factory=list)


@dataclass
class PageFacts:
    url: str
    title: str = ""
    canonical: str = ""
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    forms: list[Form] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)
    text_chars: int = 0


@dataclass
class Summary:
    status: str
    text: str = ""
    ms: float = 0.0
    fetch_ms: float = 0.0
    final_url: str = ""
    # How long model call 1 waited for this summary.
    waited_ms: float = 0.0

    @property
    def chars(self) -> int:
        return len(self.text)


def _clean(text: str) -> str:
    return " ".join(text.split())


class _PageParser(HTMLParser):
    """One pass over the HTML: title, headings, links, forms, buttons, labels."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.facts = PageFacts(url=base_url)
        self._skip = 0
        self._stack: list[str] = []
        self._title: list[str] | None = None
        self._heading: tuple[str, list[str]] | None = None
        self._link: tuple[str, list[str], str] | None = None
        self._label: tuple[str, list[str]] | None = None
        self._button: list[str] | None = None
        self._button_aria = ""
        self._button_depth = 0
        self._option: list[str] | None = None
        self._select: Field | None = None
        self._form: Form | None = None
        self._search_depth: int | None = None
        self._labels_for: dict[str, str] = {}
        self._field_ids: list[tuple[Field, str]] = []
        self._wrapping_label_fields: list[Field] = []
        self._text_chars = 0

    # Text routing -------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if self._skip:
            if self._title is not None:
                self._title.append(data)
            return
        stripped = data.strip()
        if stripped:
            self._text_chars += len(stripped)
        for bucket in (
            self._heading[1] if self._heading else None,
            self._link[1] if self._link else None,
            self._label[1] if self._label else None,
            self._button,
            self._option,
        ):
            if bucket is not None:
                bucket.append(data)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title" and self._title is None and not self.facts.title:
            self._title = []
            self._skip += 1
            self._stack.append(tag)
            return
        if tag in _SKIP_TEXT_TAGS:
            self._skip += 1
            self._stack.append(tag)
            return
        if tag == "link" and "canonical" in a.get("rel", "").lower().split() and a.get("href"):
            self.facts.canonical = urljoin(self.base, a["href"])
        if tag == "base" and a.get("href"):
            self.base = urljoin(self.base, a["href"])
        if self._skip:
            if tag not in _VOID:
                self._stack.append(tag)
            return
        if tag not in _VOID:
            self._stack.append(tag)
        if a.get("role", "").lower() == "search" and self._search_depth is None:
            self._search_depth = len(self._stack)
        if tag in ("h1", "h2"):
            self._heading = (tag, [])
        elif tag == "a" and a.get("href"):
            self._link = (a["href"], [], a.get("aria-label") or a.get("title", ""))
        elif tag == "img" and self._link is not None and a.get("alt"):
            self._link[1].append(" " + a["alt"] + " ")
        elif tag == "label":
            self._label = (a.get("for", ""), [])
        elif tag == "form":
            role_search = a.get("role", "").lower() == "search" or self._search_depth is not None
            attrs_text = " ".join(a.get(k, "") for k in ("id", "class", "name", "aria-label", "action"))
            self._form = Form(
                action=urljoin(self.base, a.get("action") or self.base),
                method=(a.get("method") or "get").lower(),
                role_search=role_search,
                attrs_text=attrs_text,
            )
            self.facts.forms.append(self._form)
        elif tag == "input":
            self._input(a)
        elif tag == "textarea":
            self._add_field(Field("textarea", "textarea", a.get("name", ""), self._attr_label(a)), a)
        elif tag == "select":
            self._select = Field("select", "select", a.get("name", ""), self._attr_label(a))
            self._add_field(self._select, a)
        elif tag == "option" and self._select is not None:
            self._option = []
        elif (tag == "button" or a.get("role", "").lower() == "button") and self._button is None:
            self._button = []
            self._button_depth = len(self._stack)
            self._button_aria = a.get("aria-label", "") or a.get("title", "")
            if tag == "button" and self._form is not None and a.get("type", "submit").lower() == "submit":
                self._button_aria = self._button_aria or "\x00submit"

    def handle_endtag(self, tag):
        if tag not in self._stack:
            return
        while self._stack:
            top = self._stack.pop()
            self._close(top)
            if top == tag:
                break

    def _close(self, tag: str) -> None:
        if tag == "title" and self._title is not None:
            self.facts.title = _clean("".join(self._title))
            self._title = None
            self._skip -= 1
            return
        if tag in _SKIP_TEXT_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._search_depth is not None and len(self._stack) < self._search_depth:
            self._search_depth = None
        if tag in ("h1", "h2") and self._heading and self._heading[0] == tag:
            text = _clean("".join(self._heading[1]))
            if text:
                getattr(self.facts, tag).append(text)
            self._heading = None
        elif tag == "a" and self._link is not None:
            href, parts, aria = self._link
            self._link = None
            text = _clean("".join(parts)) or _clean(aria)
            self._add_link(href, text)
        elif tag == "label" and self._label is not None:
            target, parts = self._label
            self._label = None
            text = _clean("".join(parts))
            if target and text:
                self._labels_for.setdefault(target, text)
            elif text:
                for fld in self._wrapping_label_fields:
                    fld.label = fld.label or text
            self._wrapping_label_fields = []
        elif tag == "option" and self._option is not None and self._select is not None:
            text = _clean("".join(self._option))
            if text:
                self._select.options.append(text)
            self._option = None
        elif tag == "select":
            self._select = None
        elif tag == "form":
            self._form = None
        if self._button is not None and len(self._stack) < self._button_depth:
            text = _clean("".join(self._button))
            aria = self._button_aria
            self._button = None
            self._button_aria = ""
            submit = aria == "\x00submit"
            name = text or ("" if submit else _clean(aria))
            if name:
                self.facts.buttons.append(name)
                if submit and self._form is not None:
                    self._form.submits.append(name)

    # Helpers ------------------------------------------------------------
    @staticmethod
    def _attr_label(a: dict) -> str:
        return _clean(a.get("aria-label") or a.get("placeholder") or a.get("title") or "")

    def _add_field(self, fld: Field, a: dict) -> None:
        if a.get("id"):
            self._field_ids.append((fld, a["id"]))
        if self._label is not None and not self._label[0]:
            self._wrapping_label_fields.append(fld)
        if self._form is not None:
            self._form.fields.append(fld)

    def _input(self, a: dict) -> None:
        kind = a.get("type", "").lower()
        if kind in ("submit", "button", "image", "reset"):
            name = _clean(a.get("value") or a.get("aria-label") or a.get("alt") or "")
            if kind == "image" and not name:
                return
            if kind == "submit" and not name:
                name = "Submit"
            if name:
                self.facts.buttons.append(name)
                if kind in ("submit", "image") and self._form is not None:
                    self._form.submits.append(name)
            return
        fld = Field("input", kind or "text", a.get("name", ""), self._attr_label(a), a.get("value", ""))
        self._add_field(fld, a)

    def _add_link(self, href: str, text: str) -> None:
        href = href.strip()
        low = href.lower()
        if low.startswith(("javascript:", "mailto:", "tel:", "data:")) or low.startswith("#"):
            return
        url = urljoin(self.base, href)
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            return
        url = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
        if _same_doc(url, self.facts.url):
            return
        self.facts.links.append((text[:MAX_LINK_TEXT].strip(), url))

    def finish(self) -> PageFacts:
        self.close()
        for fld, ident in self._field_ids:
            if not fld.label and ident in self._labels_for:
                fld.label = self._labels_for[ident]
        for form in self.facts.forms:
            for fld in form.fields:
                if fld.type in ("checkbox", "radio") and not fld.label:
                    fld.label = fld.value
        self.facts.text_chars = self._text_chars
        return self.facts


def _same_doc(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return pa.netloc == pb.netloc and (pa.path or "/") == (pb.path or "/") and pa.query == pb.query


def parse_page(html: str, url: str) -> PageFacts:
    parser = _PageParser(url)
    try:
        parser.feed(_STRIP_BLOCKS.sub(" ", html)[:MAX_PARSE_CHARS])
    except Exception:  # noqa: BLE001 - a malformed page still gives what was parsed
        pass
    return parser.finish()


# Ranking ----------------------------------------------------------------
def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ers", "ed", "es", "er", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


_ORDINALS = {
    "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
    "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10",
}


def _tokens(text: str) -> set[str]:
    words = [_ORDINALS.get(w, w) for w in re.findall(r"[a-z0-9]+", text.lower())]
    return {_stem(w) for w in words if (len(w) >= 2 or w.isdigit()) and w not in _STOPWORDS}


def _url_tokens(url: str) -> set[str]:
    parts = urlsplit(url)
    return _tokens(f"{parts.path} {parts.query}")


def _match(task_tokens: set[str], tokens: set[str]) -> int:
    """Count task words in tokens. A 5-letter shared prefix counts too."""
    hits = 0
    for t in task_tokens:
        if t in tokens:
            hits += 1
        elif len(t) >= 5 and any(len(w) >= 5 and w[:5] == t[:5] for w in tokens):
            hits += 1
    return hits


# A task word on more than this share of a page's links names the site, not the target.
COMMON_WORD_SHARE = 0.2


def _useful_task_tokens(task: str, entries: list[tuple[set[str], set[str]]], page_url: str) -> set[str]:
    """Task words, without the site's own name and without words on most links."""
    host_words = _tokens(urlsplit(page_url).netloc.replace("-", " ").replace(".", " ")) if page_url else set()
    kept = set()
    for token in _tokens(task):
        if _match({token}, host_words):
            continue
        if len(entries) >= 10:
            share = sum(1 for text, url in entries if _match({token}, text | url)) / len(entries)
            if share > COMMON_WORD_SHARE:
                continue
        kept.add(token)
    return kept


def rank_links(links: list[tuple[str, str]], task: str, page_url: str = "") -> list[tuple[str, str, int]]:
    """De-duplicate by URL, then put links that share words with the task first.

    Text matches count double, URL matches once. A URL linked several times
    keeps its best-scoring text. Ties keep page order.
    """
    texts: dict[str, list[str]] = {}
    for text, url in links:
        if url not in texts:
            if len(texts) >= MAX_RANKED_LINKS:
                continue
            texts[url] = []
        if len(texts[url]) < MAX_TEXTS_PER_URL and text not in texts[url]:
            texts[url].append(text)
    url_tokens = {url: _url_tokens(url) for url in texts}
    text_tokens = {url: [_tokens(t) for t in names] for url, names in texts.items()}
    entries = [(set().union(*text_tokens[url]) if text_tokens[url] else set(), url_tokens[url]) for url in texts]
    task_tokens = _useful_task_tokens(task, entries, page_url)
    scored = []
    for order, (url, names) in enumerate(texts.items()):
        url_score = _match(task_tokens, url_tokens[url])
        best_text, best = "", -1
        for name, tokens in zip(names, text_tokens[url]):
            score = 2 * _match(task_tokens, tokens)
            if score > best or (score == best and not best_text):
                best_text, best = name, score
        scored.append((-(max(best, 0) + url_score), order, best_text, url))
    scored.sort()
    return [(text, url, -neg) for neg, _order, text, url in scored]


def pick_links(links: list[tuple[str, str]], task: str, page_url: str = "") -> list[tuple[str, str]]:
    ranked = rank_links(links, task, page_url)
    matched = [(t, u) for t, u, s in ranked if s > 0][:MAX_MATCHED_LINKS]
    rest = [(t, u) for t, u, s in ranked if s == 0 and t]
    return (matched + rest)[:MAX_LINKS]


# Forms ------------------------------------------------------------------
def _is_search_form(form: Form) -> bool:
    if form.method != "get":
        return False
    texts = [f for f in form.fields if f.tag == "input" and f.type in _TEXT_INPUT_TYPES and f.type != "password"]
    if len(texts) != 1:
        return False
    only = texts[0]
    if not only.name:
        return False
    if form.role_search or only.type == "search" or only.name.lower() in _SEARCH_NAMES:
        return True
    hay = f"{form.attrs_text} {only.label} {only.name}".lower()
    return any(word in hay for word in _SEARCH_WORDS)


def search_template(form: Form) -> str:
    """The GET results URL with the query left as {query}."""
    parts = urlsplit(form.action)
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    query_name = ""
    for fld in form.fields:
        if not fld.name:
            continue
        if fld.tag == "input" and fld.type == "hidden":
            params.append((fld.name, fld.value))
        elif fld.tag == "input" and fld.type in _TEXT_INPUT_TYPES and not query_name:
            query_name = fld.name
    params.append((query_name, "QUERYSLOT"))
    query = urlencode(params).replace("QUERYSLOT", "{query}")
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", query, ""))


def _field_line(fld: Field) -> str:
    bits = [fld.type]
    if fld.name:
        bits.append(f'name="{fld.name}"')
    if fld.label:
        bits.append(f'label "{fld.label[:60]}"')
    if fld.type in ("checkbox", "radio") and fld.value and fld.value != fld.label:
        bits.append(f'value "{fld.value[:30]}"')
    if fld.options:
        shown = ", ".join(o[:30] for o in fld.options[:MAX_OPTIONS])
        more = f" (+{len(fld.options) - MAX_OPTIONS} more)" if len(fld.options) > MAX_OPTIONS else ""
        bits.append(f"options: {shown}{more}")
    return "    - " + " ".join(bits)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


# Summary ----------------------------------------------------------------
def looks_empty(facts: PageFacts) -> bool:
    """Little visible text and almost no links: a JavaScript shell or a block page."""
    return facts.text_chars < MIN_TEXT_CHARS and len(facts.links) < MIN_LINKS


def summarize(facts: PageFacts, task: str) -> str:
    lines = [
        "Start page, read over HTTP before your browser opened (no scripts ran, so the live page may differ):",
        f"- URL: {facts.url}",
    ]
    if facts.title:
        lines.append(f"- Title: {facts.title[:120]}")
    if facts.h1:
        lines.append("- H1: " + " | ".join(h[:100] for h in _dedupe(facts.h1)[:3]))
    h2 = _dedupe(facts.h2)
    if h2:
        lines.append("- H2: " + " | ".join(h[:60] for h in h2[:MAX_H2]))

    search_forms = [f for f in facts.forms if _is_search_form(f)]
    other_forms = [f for f in facts.forms if f not in search_forms and any(fl.name for fl in f.fields)]
    if search_forms:
        lines.append(f"- Site search (GET): {search_template(search_forms[0])}")

    links = pick_links(facts.links, task, facts.url)
    if links:
        lines.append("- Links on this page (text -> URL), task-related first:")
        for text, url in links:
            lines.append(f"  {text or '(no text)'} -> {url}")

    for form in other_forms[:MAX_FORMS]:
        lines.append(f"- Form: {form.method.upper()} {form.action}")
        shown = [fl for fl in form.fields if not (fl.tag == "input" and fl.type == "hidden")]
        for fld in shown[:MAX_FIELDS]:
            lines.append(_field_line(fld))
        if len(shown) > MAX_FIELDS:
            lines.append(f"    - (+{len(shown) - MAX_FIELDS} more fields)")
        if form.submits:
            lines.append("    - submit: " + " | ".join(_dedupe(form.submits)[:3]))

    buttons = _dedupe(facts.buttons)
    if buttons:
        lines.append("- Buttons: " + " | ".join(b[:40] for b in buttons[:MAX_BUTTONS]))

    lines.append(
        "Use it: go straight to a real URL from this list instead of guessing a URL or clicking. "
        "For a site search, fill the search URL above with your query. "
        "For a form, use these field labels."
    )
    text = "\n".join(lines)
    if len(text) > MAX_SUMMARY_CHARS:
        text = text[:MAX_SUMMARY_CHARS].rsplit("\n", 1)[0] + "\n(summary cut)"
    return text


# Fetch ------------------------------------------------------------------
def _inflate_limited(body: bytes, wbits: int) -> bytes:
    decoder = zlib.decompressobj(wbits)
    decoded = decoder.decompress(body, MAX_HTML_BYTES + 1)
    if len(decoded) <= MAX_HTML_BYTES and not decoder.eof:
        raise zlib.error("incomplete deflate stream")
    return decoded


def _decode(body: bytes, encoding: str, content_type: str) -> str:
    encoding = (encoding or "").lower()
    if encoding == "gzip":
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
            body = compressed.read(MAX_HTML_BYTES + 1)
    elif encoding == "deflate":
        try:
            body = _inflate_limited(body, zlib.MAX_WBITS)
        except zlib.error:
            body = _inflate_limited(body, -zlib.MAX_WBITS)
    if len(body) > MAX_HTML_BYTES:
        raise ValueError("decoded body exceeds HTML byte limit")
    charset = ""
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    if match:
        charset = match.group(1)
    else:
        meta = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
        if meta:
            charset = meta.group(1).decode("ascii", "ignore")
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def fetch_html(url: str, timeout: float = FETCH_TIMEOUT_S) -> Fetched:
    """Blocking GET with a browser User-Agent. Never raises."""
    started = time.perf_counter()
    result = Fetched(url=url)
    request = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result.status = response.status
            result.final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type.lower() and content_type:
                result.error = f"not html: {content_type[:40]}"
            else:
                body = response.read(MAX_HTML_BYTES)
                result.html = _decode(body, response.headers.get("Content-Encoding", ""), content_type)
    except urllib.error.HTTPError as exc:
        result.status = exc.code
        result.error = f"http {exc.code}"
    except Exception as exc:  # noqa: BLE001 - any failure falls back to the blind path
        result.error = f"{type(exc).__name__}: {str(exc)[:80]}"
    result.ms = (time.perf_counter() - started) * 1000
    return result


def summary_from_fetch(fetched: Fetched, task: str) -> Summary:
    if fetched.error or not fetched.html:
        return Summary(status=fetched.error or "empty", fetch_ms=fetched.ms, final_url=fetched.final_url)
    facts = parse_page(fetched.html, fetched.final_url or fetched.url)
    if looks_empty(facts):
        return Summary(status="no content", fetch_ms=fetched.ms, final_url=facts.url)
    return Summary(status=STATUS_OK, text=summarize(facts, task), fetch_ms=fetched.ms, final_url=facts.url)


def build_summary(url: str, task: str, timeout: float = FETCH_TIMEOUT_S) -> Summary:
    """Blocking fetch and summary. Never raises."""
    started = time.perf_counter()
    try:
        summary = summary_from_fetch(fetch_html(url, timeout), task)
    except Exception as exc:  # noqa: BLE001
        summary = Summary(status=f"error: {type(exc).__name__}")
    summary.ms = (time.perf_counter() - started) * 1000
    return summary


def start_summary(url: str, task: str, timeout: float = FETCH_TIMEOUT_S) -> asyncio.Future:
    """Start the fetch on a daemon thread and return a future for its Summary.

    A daemon thread, not the loop's executor, so a slow socket never holds up
    the event loop's shutdown.
    """
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    started = time.perf_counter()

    def expire() -> None:
        if not future.done():
            future.set_result(Summary(status="timeout", ms=(time.perf_counter() - started) * 1000))

    # One deadline from launch, including redirects, reading and parsing; not
    # another timeout starting when the first model call is ready to wait.
    deadline = loop.call_later(timeout, expire)
    future.add_done_callback(lambda _future: deadline.cancel())

    def work() -> None:
        summary = build_summary(url, task, timeout)

        def deliver() -> None:
            if not future.done():
                if time.perf_counter() - started >= timeout:
                    expire()
                else:
                    future.set_result(summary)

        try:
            loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            pass

    threading.Thread(target=work, name="page-summary", daemon=True).start()
    return future


def start_for_arm(arm: str, url: str, task: str) -> asyncio.Future | None:
    """Start the summary for script_first when it is switched on. None otherwise."""
    if arm != "script_first" or not enabled() or not url.startswith(("http://", "https://")):
        return None
    return start_summary(url, task)


async def await_summary(future: asyncio.Future | None, deadline_s: float = FETCH_TIMEOUT_S) -> Summary:
    """Wait for the summary, but never past the deadline. Never raises."""
    if future is None:
        return Summary(status="off")
    started = time.perf_counter()
    try:
        summary = await asyncio.wait_for(asyncio.shield(future), timeout=deadline_s)
    except asyncio.TimeoutError:
        summary = Summary(status="timeout", ms=deadline_s * 1000)
    except Exception as exc:  # noqa: BLE001
        summary = Summary(status=f"error: {type(exc).__name__}")
    summary.waited_ms = (time.perf_counter() - started) * 1000
    return summary


def row_fields(summary: Summary | None) -> dict:
    """Probe-row fields. Off runs log status "off"."""
    if summary is None:
        return {"page_summary": "off" if not enabled() else "unused"}
    return {
        "page_summary": summary.status,
        "page_summary_ms": round(summary.ms, 1),
        "page_summary_waited_ms": round(summary.waited_ms, 1),
        "page_summary_chars": summary.chars,
    }
