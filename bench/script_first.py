"""Whole-task Playwright script arm. No per-click settle and no snapshot loop.

The outer model emits one short script. This module runs it on local Chrome
through the Playwright Python API. A page.evaluate sequence can also be
driven through MCP browser_evaluate. browser_run_code_unsafe is rejected
and is not a tool.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from bench.judge import is_search_results_url

# Navigation waits for DOMContentLoaded, not load or networkidle.
# A click or Enter returns before the next document is current. This wait
# is only the landing read, not the proxy settle loop.
_NAV_TIMEOUT_MS = 10000
_ACTION_TIMEOUT_MS = 5000
_EVALUATE_TIMEOUT_S = 5
_LAND_TIMEOUT_S = 0.8
# Headings are kept in front of the body. A 4000-character body prefix
# dropped RFC section headings that sit further down the same page.
_PAGE_TEXT_CAP = 8000

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

# Controls also feed the cache fingerprint. Navigation hints are shown only on FAIL.
_PAGE_EVIDENCE_JS = r"""() => {
  const link = document.querySelector('link[rel="canonical"]');
  const h1 = document.querySelector("h1");
  const root = document.querySelector("main") || document.body;
  const raw = root ? (root.innerText || root.textContent || "") : "";
  const selector = [
    "a[href]",
    "button",
    "input:not([type='hidden'])",
    "textarea",
    "select",
    "[role='button']",
    "[role='link']",
    "[role='textbox']",
    "[role='checkbox']",
    "[role='radio']",
    "[role='combobox']",
    "[role='tab']",
    "[contenteditable='true']"
  ].join(",");
  const controls = [];
  const seen = new Set();
  for (const node of document.querySelectorAll(selector)) {
    if (controls.length >= 40) break;
    if (node.getAttribute("aria-hidden") === "true") continue;
    const tag = node.tagName.toLowerCase();
    let role = node.getAttribute("role") || "";
    if (!role) {
      if (tag === "a") role = "link";
      else if (tag === "button") role = "button";
      else if (tag === "textarea") role = "textbox";
      else if (tag === "select") role = "combobox";
      else if (tag === "input") {
        const type = (node.getAttribute("type") || "text").toLowerCase();
        if (type === "checkbox") role = "checkbox";
        else if (type === "radio") role = "radio";
        else if (type === "button" || type === "submit" || type === "reset") role = "button";
        else role = "textbox";
      } else role = tag;
    }
    let name = node.getAttribute("aria-label") || "";
    if (!name && node.getAttribute("aria-labelledby")) {
      name = node.getAttribute("aria-labelledby").split(/\s+/).map((id) => {
        const label = document.getElementById(id);
        return label ? (label.innerText || label.textContent || "").trim() : "";
      }).filter(Boolean).join(" ");
    }
    if (!name && node.labels && node.labels.length) {
      name = Array.from(node.labels).map((label) => (label.innerText || label.textContent || "").trim()).filter(Boolean).join(" ");
    }
    if (!name) {
      name = (node.innerText || node.textContent || node.getAttribute("placeholder") || node.getAttribute("title") || "").trim();
    }
    name = name.replace(/\s+/g, " ").replace(/\t/g, " ").slice(0, 80);
    role = role.replace(/\s+/g, " ").slice(0, 40);
    if (!name) continue;
    const pair = role + "\n" + name;
    if (seen.has(pair)) continue;
    seen.add(pair);
    controls.push({ role, name });
  }
  const links = [];
  const seenHrefs = new Set();
  const anchors = Array.from(document.querySelectorAll("a[href]"));
  anchors.sort((a, b) => Number(!!b.closest("main, article, [role='main']")) - Number(!!a.closest("main, article, [role='main']")));
  for (const node of anchors) {
    if (links.length >= 40) break;
    if (node.closest('[hidden], [aria-hidden="true"]')) continue;
    if (!node.getClientRects().length) continue;
    const style = getComputedStyle(node);
    if (style.visibility === "hidden" || style.visibility === "collapse" || style.display === "none") continue;
    const text = (node.innerText || "").replace(/\s+/g, " ").trim();
    if (!text) continue;
    let href;
    try { href = new URL(node.getAttribute("href"), document.baseURI).href; }
    catch { continue; }
    if (/^(javascript|mailto):/i.test(href) || seenHrefs.has(href)) continue;
    seenHrefs.add(href);
    links.push([text.slice(0, 160), href]);
  }
  return {
    url: location.href,
    title: document.title || "",
    // Attribute text. The IDL property resolves relative and protocol-relative hrefs.
    canonical: link ? (link.getAttribute("href") || "") : "",
    h1: h1 ? (h1.innerText || h1.textContent || "") : "",
    text: raw.slice(0, 8000),
    headings: Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).slice(0, 400).map((node) => {
      return (node.innerText || node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160);
    }).filter(Boolean),
    controls,
    links
  };
}"""

from bench.script_helpers import HelperCall, is_helper_call, parse_helper_call, run_helper, wrap_evaluate
from bench.stagehand_local import context_browser
from bench.script_grammar import BrowserAction, GRAMMAR_HINT, action_kind, browser_locator, parse_browser_action
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
    action: ScriptAction | BrowserAction | None = None
    helper: HelperCall | None = None


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
        raise ScriptError(f"line {line}: page.evaluate is the only evaluate form; {GRAMMAR_HINT}")
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
        raise ScriptError(f"{banned.strip()} is not part of this script; {GRAMMAR_HINT}")
    steps: list[TaskStep] = []
    for index, stmt in enumerate(_statements(text), 1):
        body = _normalize_stmt(stmt)
        if body.casefold().startswith("return "):
            returned = _normalize_stmt(body[len("return ") :])
            if returned.casefold().startswith("page.evaluate"):
                body = returned
            else:
                raise ScriptError(f"line {index}: top-level return is not supported; {GRAMMAR_HINT}")
        if body.casefold().startswith("page.evaluate"):
            steps.append(_parse_evaluate(body, index))
            continue
        helper_body = body[len("await ") :].strip() if body.casefold().startswith("await ") else body
        if is_helper_call(helper_body):
            steps.append(TaskStep(kind="helper", line=index, source=body, helper=parse_helper_call(body, index)))
            continue
        try:
            if body.startswith("page.goto"):
                action = parse_script(" ".join(body.split()), allow_goto=True, max_lines=1)[0]
                kind = "goto"
            else:
                action = parse_browser_action(body, index)
                kind = action_kind(action)
        except ScriptError as exc:
            raise ScriptError(f"{exc}; {GRAMMAR_HINT}") from exc
        if kind == "wait":
            continue
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


@dataclass(frozen=True)
class PageEvidence:
    """What the harness read from the live page. Not the model's claim."""

    url: str = ""
    title: str = ""
    canonical: str = ""
    h1: str = ""
    text: str = ""
    selector_text: str = ""
    controls: tuple[str, ...] = ()
    links: tuple[tuple[str, str], ...] = ()
    # Page headings, h1 to h6. The self-check reads them; the model never sees this field.
    headings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimedEvidence:
    """Values the script returned. Checked against the live page, never trusted alone."""

    url: str = ""
    title: str = ""
    h1: str = ""
    answer: str = ""
    key_text: str = ""
    values: tuple[str, ...] = ()
    rejected: bool = False


@dataclass(frozen=True)
class EvidenceVerdict:
    """PASS, FAIL, or UNKNOWN. scored_url is the live URL or the canonical href."""

    verdict: str
    reason: str
    scored_url: str


def _http(url: str) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _fold_token(value: str) -> str:
    text = unquote(value or "").replace("_", " ").replace("-", " ").replace("+", " ")
    return " ".join(text.split()).casefold()


def _norm_answer(value: str) -> str:
    return " ".join((value or "").split()).casefold()


# Dash variants the runtime check folds to "-": hyphen, non-breaking hyphen,
# figure dash, en dash, em dash, horizontal bar, minus sign.
_DASH_FOLD = str.maketrans({c: "-" for c in "‐‑‒–—―−"})


def _norm_runtime(value: str) -> str:
    """_norm_answer plus dash folding, for runtime_verdict only (not the grade).

    Non-breaking and other Unicode spaces already fold through str.split().
    """
    return _norm_answer((value or "").translate(_DASH_FOLD))


def _phrase_at_boundary(marker: str, text: str) -> bool:
    """True when the folded marker is in the folded text at token boundaries.

    Case and spacing fold the same way as _norm_answer. A marker that starts
    or ends on a letter or digit may not continue into one on that side, and a
    number may not continue through a decimal or version point (443 is not in
    4430 or 9.3.443, 9.3.1 is not in 9.3.10).
    """
    needle = _norm_answer(marker)
    hay = _norm_answer(text)
    if not needle:
        return False
    start = hay.find(needle)
    while start != -1:
        end = start + len(needle)
        before = hay[start - 1] if start else ""
        after = hay[end] if end < len(hay) else ""
        ok = True
        if needle[0].isalnum() or needle[0] == "_":
            if before.isalnum() or before == "_":
                ok = False
            elif needle[0].isdigit() and before in ".," and start >= 2 and hay[start - 2].isdigit():
                ok = False
        if ok and (needle[-1].isalnum() or needle[-1] == "_"):
            if after.isalnum() or after == "_":
                ok = False
            elif needle[-1].isdigit() and after in ".," and end + 1 < len(hay) and hay[end + 1].isdigit():
                ok = False
        if ok:
            return True
        start = hay.find(needle, start + 1)
    return False


def _host_name(url: str) -> str:
    if not _http(url):
        return ""
    return urlsplit(url).netloc.casefold()


def _host_ok(url: str, host) -> bool:
    if not host:
        return True
    if not _http(url):
        return False
    names = host if isinstance(host, (list, tuple)) else [host]
    netloc = _host_name(url)
    for item in names:
        needle = str(item or "").casefold().strip()
        if not needle:
            continue
        if netloc == needle or netloc.endswith("." + needle):
            return True
    return False


def _marker_in_url(url: str, token: str) -> bool:
    if not _http(url) or not token:
        return False
    if token.casefold() in url.casefold():
        return True
    decoded = unquote(url)
    if token.casefold() in decoded.casefold():
        return True
    return _fold_token(token) in _fold_token(decoded)


def _path_suffix_ok(url: str, suffix: str) -> bool:
    if not suffix:
        return True
    if not _http(url):
        return False
    path = unquote(urlsplit(url).path)
    return path.endswith(suffix)


def _deny_hit(url: str, deny) -> str:
    if not url:
        return ""
    raw = url.casefold()
    decoded = unquote(url).casefold()
    folded = _fold_token(decoded)
    for token in deny or []:
        if not token:
            continue
        needle = str(token)
        if needle.casefold() in raw or needle.casefold() in decoded:
            return needle
        if _fold_token(needle) and _fold_token(needle) in folded:
            return needle
    return ""


def _same_page(left: str, right: str) -> bool:
    if not _http(left) or not _http(right):
        return False
    if left.strip() == right.strip():
        return True
    a = urlsplit(left)
    b = urlsplit(right)
    if a.netloc.casefold() != b.netloc.casefold():
        return False

    def norm_path(path: str) -> str:
        text = unquote(path).casefold().replace("_", " ").replace("-", " ")
        parts = [" ".join(part.split()) for part in text.split("/")]
        return "/".join(parts).rstrip("/")

    if norm_path(a.path) != norm_path(b.path):
        return False
    return unquote(a.query).casefold() == unquote(b.query).casefold()


def _url_matches(url: str, markers: dict) -> bool:
    if not _http(url):
        return False
    if is_search_results_url(url) or _deny_hit(url, markers.get("deny") or []):
        return False
    if not _host_ok(url, markers.get("host")):
        return False
    token = markers.get("url_contains") or ""
    if token and not _marker_in_url(url, token):
        return False
    if not _path_suffix_ok(url, markers.get("path_suffix") or ""):
        return False
    if markers.get("query_nonempty") and not urlsplit(url).query.strip():
        return False
    return True


def _positive_url(markers: dict) -> bool:
    return bool(
        markers.get("url_contains") or markers.get("path_suffix") or markers.get("query_nonempty")
    )


def _scored_url(live: str, canonical: str, markers: dict) -> str:
    """The live URL, or the canonical href, byte for byte. Never a rewritten URL."""
    if _http(live) and _url_matches(live, markers):
        return live
    if _http(canonical) and _url_matches(canonical, markers) and not (
        _http(live) and (is_search_results_url(live) or _deny_hit(live, markers.get("deny") or []))
    ):
        return canonical
    if _http(live):
        return live
    if _http(canonical):
        return canonical
    return ""


def _coerce_values(raw) -> tuple[tuple[str, ...], bool]:
    """String values from a script return. The bool is True when a value is not text."""
    if raw is None or raw == "" or raw == [] or raw == ():
        return (), False
    if isinstance(raw, bool):
        return (), True
    if isinstance(raw, (str, int, float)):
        raw = [raw]
    elif isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, (list, tuple)):
        return (), True
    kept: list[str] = []
    for item in raw:
        if isinstance(item, bool) or item is None:
            return (), True
        if isinstance(item, str):
            text = " ".join(item.split())
        elif isinstance(item, (int, float)):
            text = str(item)
        else:
            return (), True
        if not text:
            continue
        if len(text) > 400:
            text = text[:400]
        kept.append(text)
        if len(kept) > 20:
            return (), True
    return tuple(kept), False


def _text_field(value) -> tuple[str, bool]:
    if value is None or value == "":
        return "", False
    if isinstance(value, bool):
        return "", True
    if isinstance(value, str):
        return value.strip(), False
    if isinstance(value, (int, float)):
        return str(value), False
    return "", True


def _claim_from_value(value) -> dict:
    if isinstance(value, dict):
        data = value
    elif isinstance(value, str):
        text = value.strip()
        data = None
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                data = parsed
        if data is None:
            if text:
                return {"answer": text}
            return {}
    else:
        return {}
    picked = {}
    rejected = bool(data.get("rejected"))
    for key in ("url", "title", "h1", "answer", "key_text"):
        text, bad = _text_field(data.get(key))
        if bad:
            rejected = True
        elif text:
            picked[key] = text
    values, bad_values = _coerce_values(data.get("values"))
    if bad_values:
        rejected = True
    elif values:
        picked["values"] = list(values)
    if rejected:
        picked["rejected"] = True
    return picked


def evidence_verdict(
    markers: dict | None,
    trusted: PageEvidence,
    claimed: ClaimedEvidence | None = None,
) -> EvidenceVerdict:
    """PASS, FAIL, or UNKNOWN from judge markers and the harness's page read.

    Only FAIL is concrete enough to ask for a repair. UNKNOWN is not a pass.
    The scored URL is the live URL or the canonical href, unchanged.
    key_text and values are the script's own return. They have to appear in
    the live page text. They never turn a miss into a pass.
    """
    markers = dict(markers or {})
    claimed = claimed or ClaimedEvidence()
    live = (trusted.url or "").strip()
    canonical = (trusted.canonical or "").strip()
    if not _http(canonical):
        canonical = ""
    scored = _scored_url(live, canonical, markers)
    page_text = trusted.text or ""
    has_page = _http(live) or _http(canonical)
    has_body = bool(page_text.strip() or (trusted.title or "").strip() or (trusted.h1 or "").strip())

    if not has_page and not has_body and not (claimed.answer or claimed.url):
        return EvidenceVerdict(FAIL, "empty evidence", "")

    if _http(live) and (is_search_results_url(live) or _deny_hit(live, markers.get("deny") or [])):
        why = _deny_hit(live, markers.get("deny") or []) or "search"
        return EvidenceVerdict(FAIL, f"the page is denied ({why})", live)

    if _http(claimed.url) and not _same_page(claimed.url, live) and not (
        canonical and _same_page(claimed.url, canonical)
    ):
        return EvidenceVerdict(FAIL, "claimed URL does not match the live page", scored or live)

    host = markers.get("host") or ""
    if host and has_page:
        candidates = [item for item in (live, canonical) if _http(item)]
        if candidates and not any(_host_ok(item, host) for item in candidates):
            return EvidenceVerdict(FAIL, "the page is on the wrong host", scored)

    needs_url = _positive_url(markers)
    url_ok = _url_matches(live, markers) or (bool(canonical) and _url_matches(canonical, markers))
    if needs_url and has_page and not url_ok:
        return EvidenceVerdict(FAIL, "the URL marker does not match the live page", scored)

    answer_in_text = markers.get("answer_in_text") or ""
    selector = markers.get("answer_equals_selector") or ""
    answer = (claimed.answer or "").strip()

    def gate(result: EvidenceVerdict) -> EvidenceVerdict:
        if result.verdict == FAIL:
            return result
        problem = _returned_problem(claimed, page_text, result.scored_url)
        return problem if problem is not None else result

    if selector or answer_in_text:
        if not answer:
            return EvidenceVerdict(FAIL, "empty answer", scored)
        if selector:
            truth = (trusted.selector_text or "").strip()
            if not truth or not page_text.strip():
                return gate(EvidenceVerdict(UNKNOWN, "page text was not read", scored))
            # Exact title only. Case and spacing are ignored. A sentence around
            # the title fails, and the title has to be on the live page.
            if _norm_answer(answer) != _norm_answer(truth):
                return EvidenceVerdict(FAIL, "answer is not the marked value", scored)
            if _norm_answer(answer) not in _norm_answer(page_text):
                return EvidenceVerdict(FAIL, "answer is not in the page text", scored)
        if answer_in_text:
            if not page_text.strip():
                return gate(EvidenceVerdict(UNKNOWN, "page text was not read", scored))
            if _norm_answer(answer) not in _norm_answer(page_text):
                return EvidenceVerdict(FAIL, "answer is not in the page text", scored)
            if not _phrase_at_boundary(str(answer_in_text), answer):
                return EvidenceVerdict(FAIL, "answer does not satisfy the marker", scored)
        if needs_url and not url_ok:
            return EvidenceVerdict(FAIL, "the URL marker does not match the live page", scored)
        if (not needs_url) or url_ok:
            if host and not any(_host_ok(item, host) for item in (live, canonical) if _http(item)):
                return EvidenceVerdict(FAIL, "the page is on the wrong host", scored)
            return gate(EvidenceVerdict(PASS, "the page evidence matches the markers", scored))

    if needs_url and url_ok:
        return gate(EvidenceVerdict(PASS, "the URL marker matches the live page", scored))
    if needs_url and not has_page:
        return EvidenceVerdict(FAIL, "empty evidence", "")
    if has_page or has_body:
        return gate(EvidenceVerdict(UNKNOWN, "the markers are not decisive", scored))
    return EvidenceVerdict(FAIL, "empty evidence", "")


def _returned_problem(claimed: ClaimedEvidence, page_text: str, scored: str) -> EvidenceVerdict | None:
    """FAIL or UNKNOWN when the script's own return disagrees with the live page.

    A return that matches, or a script that returned none of these fields,
    leaves the marker verdict alone. This does not call a model.
    """
    if claimed.rejected:
        return EvidenceVerdict(FAIL, "returned value is not text", scored)
    needed = []
    key = (claimed.key_text or "").strip()
    if key:
        needed.append(key)
    needed.extend(item for item in claimed.values if item.strip())
    if not needed:
        return None
    if not (page_text or "").strip():
        return EvidenceVerdict(UNKNOWN, "page text was not read", scored)
    folded = _norm_answer(page_text)
    for item in needed:
        if _norm_answer(item) not in folded:
            return EvidenceVerdict(FAIL, "returned evidence is not on the page", scored)
    return None


def _evidence_from_claim(claimed: dict) -> ClaimedEvidence:
    values, bad_values = _coerce_values(claimed.get("values"))
    key_text, bad_key = _text_field(claimed.get("key_text"))
    return ClaimedEvidence(
        url=claimed.get("url") or "",
        title=claimed.get("title") or "",
        h1=claimed.get("h1") or "",
        answer=claimed.get("answer") or "",
        key_text=key_text,
        values=values,
        rejected=bool(claimed.get("rejected")) or bad_values or bad_key,
    )


def check_returned_evidence(
    markers: dict | None,
    trusted: PageEvidence,
    returned,
) -> EvidenceVerdict:
    """Check the evidence object a script returned. No model call.

    `trusted` is the live page. `returned` is the script's object. UNKNOWN
    is not a pass. Text the script returned has to be on that page.
    """
    if isinstance(returned, ClaimedEvidence):
        claimed = returned
    else:
        claimed = _evidence_from_claim(_claim_from_value(returned))
    return evidence_verdict(markers, trusted, claimed)


def trusted_from_payload(payload: dict | None, *, url: str = "", title: str = "") -> PageEvidence:
    data = payload if isinstance(payload, dict) else {}
    live = url or (data.get("url") if isinstance(data.get("url"), str) else "")
    return PageEvidence(
        url=live or "",
        title=title or (data.get("title") if isinstance(data.get("title"), str) else ""),
        canonical=data.get("canonical") if isinstance(data.get("canonical"), str) else "",
        h1=data.get("h1") if isinstance(data.get("h1"), str) else "",
        text=data.get("text") if isinstance(data.get("text"), str) else "",
        selector_text=data.get("selector_text") if isinstance(data.get("selector_text"), str) else "",
        headings=tuple(h for h in data.get("headings") or () if isinstance(h, str)),
    )


def claimed_from_payload(payload: dict | None) -> ClaimedEvidence:
    data = payload if isinstance(payload, dict) else {}
    raw = data.get("claimed") if isinstance(data.get("claimed"), dict) else {}
    claimed: dict = {}
    for key in ("url", "title", "h1", "answer", "key_text"):
        item = raw.get(key)
        if isinstance(item, str) and item.strip():
            claimed[key] = item.strip()
    values, bad_values = _coerce_values(raw.get("values"))
    if bad_values or raw.get("rejected"):
        claimed["rejected"] = True
    elif values:
        claimed["values"] = list(values)
    extracted = data.get("extracted")
    texts: list[str] = []
    if isinstance(extracted, str) and extracted.strip():
        texts = [extracted.strip()]
    elif isinstance(extracted, list):
        texts = [str(item).strip() for item in extracted if str(item).strip()]
    for text in reversed(texts):
        parsed = _claim_from_value(text)
        for key in ("url", "title", "h1", "answer", "key_text", "values"):
            if parsed.get(key) and not claimed.get(key):
                claimed[key] = parsed[key]
        if parsed.get("rejected"):
            claimed["rejected"] = True
        if claimed.get("answer") or claimed.get("url") or claimed.get("key_text") or claimed.get("values"):
            break
    if not claimed.get("answer") and texts:
        last = texts[-1]
        if not last.startswith("{"):
            claimed["answer"] = last
    return _evidence_from_claim(claimed)


# The description only. Markers and the expected answer are not read.
# "find the page" opens a page. The other shapes ask for a value to return.
_REPORT_VERB = re.compile(r"\b(?:report|identify)\b", re.IGNORECASE)
_GIVE_OR_TELL = re.compile(
    r"\b(?:give|tell)\s+(?:me\s+|us\s+)?(?:the|a|an|its|their|that|this)\b",
    re.IGNORECASE,
)
_NAME_OR_STATE = re.compile(
    r"\b(?:name|state)\s+(?:the|a|an|its|their)\b",
    re.IGNORECASE,
)
_VALUE_QUESTION = re.compile(
    r"\b(?:what|which|who)\b|\bhow\s+(?:many|much)\b",
    re.IGNORECASE,
)
_FIND = re.compile(r"\bfind\b", re.IGNORECASE)
_FIND_PAGE = re.compile(
    r"\bfind\s+(?:the\s+|a\s+|an\s+)?(?:page|article|section|documentation|document)\b",
    re.IGNORECASE,
)


_OPEN = re.compile(r"\bopen\b", re.IGNORECASE)


def task_asks_value(description: str) -> bool:
    """True when the task text asks for a value, not only a page to open."""
    text = " ".join((description or "").split())
    if not text:
        return False
    if text.endswith("?"):
        return True
    if _REPORT_VERB.search(text) or _GIVE_OR_TELL.search(text) or _NAME_OR_STATE.search(text):
        return True
    if _VALUE_QUESTION.search(text):
        return True
    # "find X and open its page" asks for a page, like "search for X and open it".
    if _FIND.search(text) and not _FIND_PAGE.search(text) and not _OPEN.search(text):
        return True
    return False


# Precision checks for a self-PASS. They read the task text, the live page and
# the claim. Never the task's markers or expected answer.
_ERROR_PAGE = re.compile(
    r"\b(?:page|content|file|document)\s+(?:was\s+)?not\s+found\b"
    r"|\b404\b"
    r"|^\s*not\s+found\s*$"
    r"|\bpage\s+(?:does\s+not|doesn't|cannot\s+be\s+found|could\s+not\s+be\s+found)",
    re.IGNORECASE,
)
# The clause that names the asked value starts at one of these.
_ASK_START = re.compile(
    r"\b(?:report|give|tell|state|what|which|who)\b|\bhow\s+(?:many|much|long|big|large|old)\b",
    re.IGNORECASE,
)
# An asked value named by one of these words is a quantity, date or version.
_QUANTITY_WORD = re.compile(
    r"\bhow\s+(?:many|much|long|big|large|old)\b"
    r"|\b(?:total|count|number|date|year|version|price|cost|diameter|radius|size|length|width|height|"
    r"weight|mass|storage|amount|percentage|percent|population|age|duration|temperature|speed|hexadecimal|"
    r"distance|area|volume)\b",
    re.IGNORECASE,
)
_STRONG_ASK = re.compile(
    r"\b(?:report|give|tell|state)\b|\b(?:what|which|who)\b|\bhow\s+(?:many|much)\b",
    re.IGNORECASE,
)


def _asked_clause(task: str) -> str:
    """The last sentence that asks, from its first ask word to the sentence end."""
    text = " ".join((task or "").split())
    for sentence in reversed(re.split(r"(?<=[.;!?])\s+", text)):
        match = _ASK_START.search(sentence)
        if match:
            return sentence[match.start():].rstrip(".;!? ")
    return ""


def precision_hits(
    trusted: PageEvidence,
    claimed: ClaimedEvidence,
    *,
    task: str,
    start_url: str = "",
    asks_value: bool = False,
    earlier: tuple = (),
) -> list[tuple[str, str]]:
    """Every precision rule that fires on a run the plain check would PASS, in order: (rule, reason).

    Each reason is shown to the model in the repair turn, so it says what to do.
    """
    hits: list[tuple[str, str]] = []
    live = (trusted.url or "").strip()
    for part in (trusted.title, trusted.h1):
        error = _ERROR_PAGE.search(" ".join(part.split())) if part else None
        # A page about the error itself ("HTTP 404") is the asked page when the task names that error.
        if error and not _phrase_at_boundary(error.group(0).strip(), task or ""):
            hits.append((
                "error_page",
                "the live page is an error page (" + " ".join(part.split())[:80] + "); "
                "open the real page from a link on the site instead of guessing its URL",
            ))
            break
    on_start = _http(start_url) and _same_page(live, start_url)
    answer = (claimed.answer or "").strip()
    start_heading = any(
        part and answer and _norm_runtime(answer) == _norm_runtime(part) for part in (trusted.title, trusted.h1)
    )
    if on_start and not asks_value and (not answer or start_heading):
        hits.append(("start_page", "the script is still on the start page; follow the link to the page the task asks for"))
    if not answer or not asks_value:
        return hits
    clause = _asked_clause(task)
    if is_search_results_url(live) and not _RESULTS_ASK.search(clause):
        hits.append((
            "search_results",
            "the script ended on a search results page; "
            "open the matching result and read the value on its own page",
        ))
    if answer.endswith(":") and len(answer) <= 60:
        hits.append((
            "field_label",
            f"the answer {answer[:60]} is a field label, not its value; "
            "return the value shown next to that label",
        ))
    asked = _asked_object(clause)
    if re.search(r"\btitle\b", asked, re.IGNORECASE) and not re.search(r"\bheading\b", asked, re.IGNORECASE):
        title_words = _content_words(trusted.title or "")
        # Only a breadcrumb-shaped answer: an item on a container page may share no word with the tab title.
        if title_words and _BREADCRUMB.search(answer) and not (_content_words(answer) & title_words):
            hits.append((
                "title_overlap",
                "the task asks for a title and the answer shares no word with the page's document title; "
                "return the title of the item itself, not a site, section or breadcrumb heading",
            ))
    site = _site_name(trusted)
    if site and _norm_runtime(answer) == site and not _ORG_OBJECT.search(asked):
        hits.append((
            "site_name",
            "the answer is the site's own name, not the asked value; "
            "return the title or value of the item this page is about",
        ))
    if earlier and _FORM_TASK.search(task or "") and _seen_before_submit(answer, live, earlier, start_url):
        hits.append((
            "form_seen_before",
            "the answer was already on this page before the form was submitted, so it is not the result; "
            "submit the form, then return the new message that appears after submitting",
        ))
    wrong_row = _wrong_row_label(answer, task, trusted.text or "")
    if wrong_row and not _PLURAL_ASK.search(clause):
        hits.append((
            "wrong_row",
            f"the answer is a table row labelled {wrong_row[:60]}, which the task does not ask about; "
            "return only the value cell from the row the task names",
        ))
    if (
        _STRONG_ASK.search(task or "")
        and len(_norm_runtime(answer)) >= 3
        and _phrase_at_boundary(_norm_runtime(answer), _norm_runtime(task))
        and not _choice_option(answer, task)
    ):
        hits.append((
            "task_echo",
            "the answer only repeats words from the task; "
            "read the asked value itself from the page, next to its label",
        ))
    if on_start and start_heading and _MOVE.search(task or ""):
        hits.append((
            "start_heading",
            "the answer is the start page's own heading and the script is still on the start page; "
            "finish the steps the task asks for, then read the result",
        ))
    if clause and _asks_quantity(clause) and not _has_quantity(answer, task):
        hits.append((
            "quantity_digit",
            "the task asks for a number, date or version and the answer has no digits of its own; "
            "read the value next to its label on the page",
        ))
    # An item in the title, h1 or URL is the page's subject, not one row of it.
    subject = _norm_runtime(" ".join((trusted.title or "", trusted.h1 or "", unquote(live))))
    rows = [
        row
        for row in _item_rows(task, trusted.text or "", labels=not _TITLE_OBJECT.search(_asked_object(clause)))
        if _norm_runtime(row[0]) not in subject
    ]
    if (
        rows
        and not any(_answer_in_row(answer, row, item) for item, row in rows)
        and _off_row_evidence(answer, rows, trusted.text or "")
    ):
        item = rows[0][0]
        hits.append((
            "item_row",
            f"the page has a table row for {item} and the answer is not from that row; "
            f"return the value cell from the row for {item}",
        ))
    heading = _heading_answer(answer, trusted, clause)
    if heading:
        hits.append((
            "heading_value",
            f"the answer is a heading on the page ({heading[:80]}), not the asked value; "
            "return the value or text under that heading instead",
        ))
    # One short value only: a block, row or sentence cut mid-word is a loose extract, not a cut value.
    if (
        "\n" not in answer
        and "\t" not in answer
        and len(answer.split()) <= 6
        and _only_inside_token(answer, trusted.text or "")
    ):
        hits.append((
            "token_fragment",
            "the answer is only part of a longer value on the page; "
            "return the whole value as written there",
        ))
    return hits


def precision_problem(
    trusted: PageEvidence,
    claimed: ClaimedEvidence,
    *,
    task: str,
    start_url: str = "",
    asks_value: bool = False,
    earlier: tuple = (),
) -> str:
    """Why a run the plain check would PASS still looks wrong. Empty when none applies."""
    hits = precision_hits(
        trusted, claimed, task=task, start_url=start_url, asks_value=asks_value, earlier=earlier
    )
    return hits[0][1] if hits else ""


# The asked clause wants several items: a row or list answer is fine there.
_PLURAL_ASK = re.compile(r"\b(?:list|all|every|each|lines|rows|values|items|entries|both)\b", re.IGNORECASE)
# Words that end the asked object ("the codename of ...", "the entry under ...").
_OBJECT_END = re.compile(
    r"\b(?:of|for|in|on|at|from|under|that|which|who|shown|listed|given|as|with|to|by|written|where|when|"
    r"exactly|it|its|they|their|between|after|before|near|next)\b",
    re.IGNORECASE,
)
_TITLE_OBJECT = re.compile(r"\b(?:title|heading|headline|name|caption|label|subject|header)s?\b", re.IGNORECASE)


def _wrong_row_label(answer: str, task: str, page_text: str = "") -> str:
    """The label of a returned table row when no returned row is labelled with the task's own words.

    A tab-separated answer is one or more rows. Each is judged on the full page
    row that contains it, so a row returned without its first cell keeps its
    label. A row is right when one of its cells uses only task words.
    Empty when the answer is not a row, or one row is labelled that way.
    """
    rows = [line for line in (answer or "").splitlines() if "\t" in line]
    if not rows:
        return ""
    known = set(re.findall(r"[a-z0-9]+", _norm_runtime(task)))
    headers = _header_lines(page_text)
    page_rows = [line for i, line in enumerate((page_text or "").splitlines()) if "\t" in line and i not in headers]
    # Only when the page has a data row labelled with the task's own words: then a better row exists.
    # Without one the row was picked by a relation ("the cheapest"), which words cannot check.
    if not any(_task_word_row(row, known) for row in page_rows):
        return ""
    labels = []
    for line in rows:
        folded = _norm_runtime(line)
        full = next((row for row in page_rows if folded and folded in _norm_runtime(row)), line)
        cells = [" ".join(cell.split()) for cell in full.split("\t") if cell.strip()]
        for cell in cells:
            words = re.findall(r"[a-z0-9]+", _norm_runtime(cell))
            if words and all(word in known for word in words) and any(len(w) >= 3 or w.isdigit() for w in words):
                return ""
        label = cells[0] if cells else ""
        labels.append(label if any(ch.isalnum() for ch in label) else "(no label)")
    return labels[0]


def _task_word_row(row: str, known: set[str]) -> bool:
    """A row with a cell made only of task words, one of them a real word."""
    for cell in row.split("\t"):
        words = re.findall(r"[a-z0-9]+", _norm_runtime(cell))
        if words and all(word in known for word in words) and any(len(w) >= 3 or w.isdigit() for w in words):
            return True
    return False


def _asked_object(clause: str) -> str:
    """The noun phrase right after the ask word: 'report the scene heading exactly' -> 'the scene heading'."""
    match = _ASK_START.match(clause or "")
    rest = clause[match.end():] if match else (clause or "")
    rest = rest.strip()
    first = re.match(r"\S+\s*", rest)
    # Skip one leading word so "report its title" keeps "its title"; then stop at a preposition.
    head = first.group(0) if first else ""
    end = _OBJECT_END.search(rest, len(head))
    rest = rest[: end.start()] if end else rest
    return rest.split(",")[0].strip()


def _heading_answer(answer: str, trusted: PageEvidence, clause: str) -> str:
    """The heading the answer equals, when the task asks for something other than a title or heading."""
    asked = _asked_object(clause)
    if not clause or _TITLE_OBJECT.search(asked) or _SECTION_OBJECT.search(asked):
        return ""
    folded = _norm_runtime(answer.rstrip(":"))
    for part in (trusted.title, trusted.h1, *trusted.headings):
        text = (part or "").strip()
        if text and _norm_runtime(text.rstrip(":").replace("\uf0c1", "")) == folded:
            return text
    return ""


# Asked objects whose value is a heading on the page ("which section ...").
_SECTION_OBJECT = re.compile(
    r"\b(?:section|chapter|part|category|tab|topic|step|menu|option|module|unit|lesson)s?\b", re.IGNORECASE
)
# Asked objects whose value can be the site's own name ("the publisher").
_ORG_OBJECT = re.compile(
    r"\b(?:publisher|organi[sz]ation|company|site|website|owner|maintainer|brand|project|provider|vendor|"
    r"platform|operator|host)s?\b",
    re.IGNORECASE,
)


def _choice_option(answer: str, task: str) -> bool:
    """The task offers the answer as one of its options: "X or Y", "X, Y or Z", "between X and Y"."""
    needle = _norm_runtime(answer)
    hay = _norm_runtime(task)
    if not needle or not re.search(r"\b(?:or|between|either)\b", hay):
        return False
    start = hay.find(needle)
    while start != -1:
        before = hay[:start].rstrip()
        after = hay[start + len(needle):].lstrip()
        # The answer sits next to the choice words: after "or"/"between"/"and"/",", or before "or"/"and"/",".
        if re.search(r"(?:\bor|\beither|\bbetween|\band|,)(?:\s+(?:the|a|an))?$", before) or re.match(
            r"(?:or|and)\b|,", after
        ):
            return True
        start = hay.find(needle, start + 1)
    return False


def _glued(ch: str, beyond: str) -> bool:
    """True when ch joins two parts of one token (a letter or digit, or a joiner before one)."""
    if not ch:
        return False
    if ch.isalnum() or ch == "_":
        return True
    return ch in "-./" and bool(beyond) and (beyond.isalnum())


def _only_inside_token(answer: str, page_text: str) -> bool:
    """Every place the answer occurs on the page continues a longer token on one side."""
    needle = _norm_runtime(answer)
    hay = _norm_runtime(page_text)
    if len(needle) < 2 or not needle[0].isalnum() or not needle[-1].isalnum():
        return False
    start = hay.find(needle)
    if start == -1:
        return False
    while start != -1:
        end = start + len(needle)
        before = hay[start - 1] if start else ""
        before2 = hay[start - 2] if start >= 2 else ""
        after = hay[end] if end < len(hay) else ""
        after2 = hay[end + 1] if end + 1 < len(hay) else ""
        if not _glued(before, before2) and not _glued(after, after2):
            return False
        start = hay.find(needle, start + 1)
    return True


_RESULTS_ASK = re.compile(r"\b(?:results?|matches|hits|search)\b", re.IGNORECASE)


_FORM_TASK = re.compile(r"\b(?:submit|send|register|sign\s+up|purchase|book|fill\s+in|complete)\b", re.IGNORECASE)
_TITLE_SEPARATOR = re.compile(r"\s+[|·—–-]\s+|\s+/\s+")


def _site_name(trusted: PageEvidence) -> str:
    """The folded site-name part of the document title ("Entry - Site"), or empty.

    Only a title with a separator has one, and the part has to be short.
    """
    parts = [part.strip() for part in _TITLE_SEPARATOR.split(trusted.title or "") if part.strip()]
    if len(parts) < 2:
        return ""
    site = _norm_runtime(parts[-1])
    return site if 0 < len(site.split()) <= 4 else ""


def _seen_before_submit(answer: str, live: str, earlier, start_url: str = "") -> bool:
    """An earlier script of this run stopped on this same page, the start page, and its text already held the answer.

    Only the start page: a stopped script that had already left it may have
    submitted, so a confirmation it saw there can be the real result.
    """
    needle = _norm_runtime(answer)
    if len(needle) < 3 or not (_http(start_url) and _same_page(live, start_url)):
        return False
    for page in earlier:
        if page.stopped and _same_page(page.url, live) and needle in _norm_runtime(page.text):
            return True
    return False


def _content_words(text: str) -> set[str]:
    """Lower-case words of three or more letters, or numbers, from a title or answer."""
    return {w for w in re.findall(r"[a-z0-9]+", _norm_runtime(text)) if len(w) >= 3 or w.isdigit()}


_TOKEN = re.compile(r"[^\s,;:()\"'“”‘’]+")


# Quantity nouns count only in the asked object; "how many" anywhere in the asked clause.
_HOW_MANY = re.compile(r"\bhow\s+(?:many|much|long|big|large|old)\b", re.IGNORECASE)
# Quantities written as words. General English, not tied to any task.
_NUMBER_WORD = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
    r"thousand|million|billion|none|no|nil|nothing|free|once|twice|single|dozen|half|unlimited)\b",
    re.IGNORECASE,
)
# A breadcrumb or path: "Section > Subsection", "A / B", "A » B".
_BREADCRUMB = re.compile(r"\s(?:>|›|»|/|::)\s")
# The task asks the run to move or act before it reads the value.
_MOVE = re.compile(
    r"\b(?:open|go|navigate|follow|click|search|submit|send|select|choose|switch|visit|enter|fill|type|press|"
    r"book|purchase|register|sign|log|filter|sort|expand|scroll|convert|calculate|add)\b",
    re.IGNORECASE,
)


def _asks_quantity(clause: str) -> bool:
    """The asked value is a number, date or version: by "how many", or by a quantity noun in the asked object."""
    return bool(_HOW_MANY.search(clause or "") or _QUANTITY_WORD.search(_asked_object(clause)))


def _has_quantity(answer: str, task: str) -> bool:
    """The answer states a quantity of its own: a new digit, a digit beside new words, or a number word."""
    if _has_new_digit(answer, task) or _NUMBER_WORD.search(answer or ""):
        return True
    if not any(ch.isdigit() for ch in answer or ""):
        return False
    # "12 credits" for "visitors aged 12": the digit is shared, the value around it is new.
    known = {tok.casefold().strip(".") for tok in _TOKEN.findall(task or "")}
    return any(
        tok.casefold().strip(".") not in known and any(ch.isalpha() for ch in tok) for tok in _TOKEN.findall(answer)
    )


def _has_new_digit(answer: str, task: str) -> bool:
    """A digit in an answer token that the task text does not already contain."""
    known = {tok.casefold().strip(".") for tok in _TOKEN.findall(task or "")}
    for tok in _TOKEN.findall(answer or ""):
        if any(ch.isdigit() for ch in tok) and tok.casefold().strip(".") not in known:
            return True
    return False


# A named item: an identifier-like word in the task (all caps, inner capital, or
# letters mixed with digits or underscores), never a plain word.
_ITEM = re.compile(r"\b(?=[A-Za-z_]*[A-Z0-9_])[A-Za-z][A-Za-z0-9_]*[A-Z0-9_][A-Za-z0-9_]*\b")


def _task_items(task: str) -> set[str]:
    items = set()
    for match in _ITEM.finditer(task or ""):
        word = match.group(0)
        inner_cap = any(ch.isupper() for ch in word[1:])
        mixed = any(ch.isdigit() or ch == "_" for ch in word) and any(ch.isalpha() for ch in word)
        if len(word) >= 3 and (inner_cap or mixed):
            items.add(word.casefold())
    return items


def _item_rows(task: str, page_text: str, *, labels: bool = True) -> list[tuple[str, list[str]]]:
    """Table rows (tab-separated lines) labelled with something the task names.

    An identifier-like item may be in any cell. A plain word from the asked
    clause counts only as the row's first cell (its label), and only when the
    row also has a value cell.
    """
    items = _task_items(task)
    label_words = {
        word.casefold()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", _asked_clause(task))
        if word.casefold() not in _LABEL_STOP
    } if labels else set()
    if not items and not label_words:
        return []
    found = []
    headers = _header_lines(page_text)
    for index, line in enumerate((page_text or "").splitlines()):
        if "\t" not in line or index in headers:
            continue
        cells = [" ".join(cell.split()) for cell in line.split("\t")]
        filled = [cell for cell in cells if cell]
        if len(filled) < 2:
            continue
        if filled[0].casefold() in label_words:
            found.append((filled[0], cells))
            continue
        for cell in cells:
            if cell.casefold() in items:
                found.append((cell, cells))
                break
    return found


# Words of the asked clause that never label a data row.
_LABEL_STOP = {
    "report", "give", "tell", "state", "what", "which", "who", "how", "many", "much", "the", "its", "their",
    "and", "for", "from", "with", "that", "this", "shown", "listed", "given", "written", "exactly", "page",
    "full", "main", "value", "number", "name", "line", "text", "entry", "item", "items",
}


def _off_row_evidence(answer: str, rows: list[tuple[str, list[str]]], page_text: str) -> bool:
    """Positive evidence the answer came from the wrong place: it names the row's item, or it is a cell of another row.

    An answer from elsewhere on the page (a legend, a note) with neither may be
    about another attribute, so the table does not judge it.
    """
    folded = _norm_runtime(answer)
    if any(_norm_runtime(item) in folded for item, _cells in rows):
        return True
    named = [cells for _item, cells in rows]
    headers = _header_lines(page_text)
    for index, line in enumerate((page_text or "").splitlines()):
        if "\t" not in line or index in headers:
            continue
        cells = [" ".join(cell.split()) for cell in line.split("\t")]
        if cells in named:
            continue
        if any(_norm_runtime(cell) == folded for cell in cells if cell):
            return True
    return False


def _header_lines(page_text: str) -> set[int]:
    """Indexes of table header lines: a tab-separated line with no digit that starts a table.

    It starts one when the line before is not a row, or is a row with another
    number of cells (two tables printed back to back).
    """
    lines = (page_text or "").splitlines()
    found = set()
    for index, line in enumerate(lines):
        if "\t" not in line or any(ch.isdigit() for ch in line):
            continue
        before = lines[index - 1] if index else ""
        after = lines[index + 1] if index + 1 < len(lines) else ""
        if "\t" not in before or before.count("\t") != line.count("\t"):
            found.add(index)
        elif any(ch.isdigit() for ch in before) and "\t" in after and any(ch.isdigit() for ch in after):
            # A wordy row between numeric rows of the same width: a repeated or second header.
            found.add(index)
    return found


def _answer_in_row(answer: str, cells: list[str], item: str) -> bool:
    """The answer shares a value cell with this row (the item's own cell does not count)."""
    folded = _norm_runtime(answer)
    for cell in cells:
        value = _norm_runtime(cell)
        if not value or value == _norm_runtime(item):
            continue
        if value in folded or (len(folded) >= 2 and folded in value):
            return True
    return False


def runtime_verdict(
    trusted: PageEvidence,
    claimed: ClaimedEvidence | None = None,
    *,
    script_ok: bool = True,
    script_error: str = "",
    start_url: str = "",
    asks_value: bool = False,
    task: str = "",
    earlier: tuple = (),
) -> EvidenceVerdict:
    """The live check script_first runs on itself. No task markers, no model call.

    A real user has no answer key, so this uses only what the run can see:
    whether the script finished, the live page, and whether what the script
    claimed is really on that page. The final grade still applies the task's
    markers to every arm. A PASS here is never a graded pass by itself.
    """
    claimed = claimed or ClaimedEvidence()
    live = (trusted.url or "").strip()
    canonical = (trusted.canonical or "").strip()
    if not _http(canonical):
        canonical = ""
    scored = canonical if canonical and not _http(live) else live
    page_text = trusted.text or ""
    has_page = _http(live) or bool(canonical)
    has_body = bool(page_text.strip() or (trusted.title or "").strip() or (trusted.h1 or "").strip())

    if not script_ok:
        detail = " ".join((script_error or "").split())[:200]
        return EvidenceVerdict(FAIL, f"the script stopped before it finished ({detail or 'error'})", scored)
    if not has_page and not has_body:
        return EvidenceVerdict(FAIL, "empty evidence", "")
    if not has_page:
        return EvidenceVerdict(FAIL, "the script did not end on a web page", "")
    if _http(claimed.url) and not _same_page(claimed.url, live) and not (
        canonical and _same_page(claimed.url, canonical)
    ):
        return EvidenceVerdict(FAIL, "claimed URL does not match the live page", scored)
    answer = (claimed.answer or "").strip()
    if asks_value and not answer:
        return EvidenceVerdict(
            FAIL,
            "the task asks for a value and the script returned no answer",
            scored,
        )
    returned_any = bool(answer or (claimed.key_text or "").strip() or any(v.strip() for v in claimed.values))
    if not returned_any:
        # The prompt asks every script to return an answer or a phrase from the page.
        if _http(start_url) and _same_page(live, start_url):
            return EvidenceVerdict(FAIL, "the script ended on the start page and returned nothing", live)
        return EvidenceVerdict(FAIL, "the script returned no answer or key_text", scored)
    rule = ""
    # The URL and title/h1 rules never pass a script that stayed on the start page.
    moved = not (_http(start_url) and _same_page(live, start_url))
    if answer:
        if moved and _http(answer) and (_same_page(answer, live) or (canonical and _same_page(answer, canonical))):
            # The answer is the live page's own URL: nothing to find in the text.
            rule = "the answer is the live page URL"
        else:
            needle = _norm_runtime(answer)
            in_text = bool(page_text.strip()) and needle in _norm_runtime(page_text)
            if in_text and _norm_answer(answer) not in _norm_answer(page_text):
                rule = "the answer is in the page text once dashes fold"
            elif not in_text and moved and any(needle in _norm_runtime(part) for part in (trusted.title, trusted.h1) if part):
                rule = "the answer is in the page title or h1"
            elif not page_text.strip():
                return EvidenceVerdict(UNKNOWN, "page text was not read", scored)
            elif not in_text:
                return EvidenceVerdict(FAIL, "answer is not in the page text", scored)
    problem = _returned_problem(claimed, page_text, scored)
    if problem is not None:
        return problem
    if task:
        reason = precision_problem(
            trusted, claimed, task=task, start_url=start_url, asks_value=asks_value, earlier=earlier
        )
        if reason:
            return EvidenceVerdict(FAIL, reason, scored)
    if rule:
        return EvidenceVerdict(PASS, f"the script finished and {rule}", scored)
    return EvidenceVerdict(PASS, "the script finished and its evidence is on the live page", scored)


def script_runtime_verdict(
    result_text: str,
    page_url: str,
    start_url: str = "",
    *,
    asks_value: bool = False,
    task: str = "",
    earlier: list | tuple = (),
) -> tuple[EvidenceVerdict, dict]:
    """Judge one run_script result without the task's markers.

    `earlier` holds the payloads of the scripts this run already ran, oldest first.
    """
    from bench.harness import page_field

    payload = script_result_payload(result_text)
    title = page_field(result_text, "Title")
    if not title and isinstance(payload.get("title"), str):
        title = payload["title"]
    ok = payload.get("ok")
    error = payload.get("error") if isinstance(payload.get("error"), str) else ""
    verdict = runtime_verdict(
        trusted_from_payload(payload, url=page_url, title=title),
        claimed_from_payload(payload),
        script_ok=ok is not False,
        script_error=error,
        start_url=start_url,
        asks_value=asks_value,
        task=task,
        earlier=tuple(_earlier_page(item) for item in earlier or () if isinstance(item, dict)),
    )
    return verdict, payload


@dataclass(frozen=True)
class EarlierPage:
    """The page an earlier script of this run ended on. No grade fields."""

    url: str = ""
    text: str = ""
    stopped: bool = False


def _earlier_page(payload: dict) -> EarlierPage:
    return EarlierPage(
        url=payload.get("url") if isinstance(payload.get("url"), str) else "",
        text=payload.get("text") if isinstance(payload.get("text"), str) else "",
        stopped=payload.get("ok") is False,
    )


def script_verdict(markers: dict | None, result_text: str, page_url: str) -> tuple[EvidenceVerdict, dict]:
    """Judge one run_script result. page_url is the live URL the harness read back."""
    from bench.harness import page_field

    payload = script_result_payload(result_text)
    title = page_field(result_text, "Title")
    if not title and isinstance(payload.get("title"), str):
        title = payload["title"]
    verdict = evidence_verdict(
        markers,
        trusted_from_payload(payload, url=page_url, title=title),
        claimed_from_payload(payload),
    )
    return verdict, payload


def repair_request(url: str, reason: str) -> str:
    """One short ask for a corrected script. The harness sends this at most once."""
    shown = url if url else "(empty)"
    return (
        "END_STATE_FAILED: "
        f"{reason}. Current URL: {shown}. "
        "Send one corrected script that finishes the task. "
        "The end URL must be the finished page the task asked for. "
        "The script must leave the start page and any search-results page for the page that holds the asked value. "
        "cu.click, cu.fill, and cu.press take a visible name. "
        "cu.claim belongs inside page.evaluate. "
        "Return any title or answer with page.evaluate in that same script. "
        "Do not repeat the same script."
    )


# Read only after a script FAILs, so the first-script path never pays for it.
# Visible elements only, with the names cu.click/getByRole/getByLabel match.
_REPAIR_SNAPSHOT_JS = r"""(terms) => {
  const clean = (s, n) => (s || "").replace(/\s+/g, " ").trim().slice(0, n);
  const shown = (el) => {
    if (!el || !el.getClientRects || !el.getClientRects().length) return false;
    if (el.closest('[hidden], [aria-hidden="true"], [inert]')) return false;
    const st = getComputedStyle(el);
    return st.visibility !== "hidden" && st.visibility !== "collapse" && st.display !== "none";
  };
  const roleOf = (el) => {
    const explicit = el.getAttribute("role");
    if (explicit) return explicit.split(/\s+/)[0];
    const tag = el.tagName.toLowerCase();
    if (tag === "a") return "link";
    if (tag === "button" || tag === "summary") return "button";
    if (tag === "textarea") return "textbox";
    if (tag === "select") return el.multiple ? "listbox" : "combobox";
    if (tag === "input") {
      const t = (el.getAttribute("type") || "text").toLowerCase();
      if (["button", "submit", "reset", "image"].includes(t)) return "button";
      if (t === "checkbox" || t === "radio") return t;
      if (t === "search") return "searchbox";
      if (t === "range") return "slider";
      if (t === "number") return "spinbutton";
      return "textbox";
    }
    return tag;
  };
  const nameOf = (el) => {
    let name = el.getAttribute("aria-label") || "";
    if (!name && el.getAttribute("aria-labelledby")) {
      name = el.getAttribute("aria-labelledby").split(/\s+/).map((id) => {
        const node = document.getElementById(id);
        return node ? (node.innerText || node.textContent || "") : "";
      }).join(" ");
    }
    if (!name && el.labels && el.labels.length) {
      name = Array.from(el.labels).map((l) => l.innerText || l.textContent || "").join(" ");
    }
    const tag = el.tagName.toLowerCase();
    if (!name && tag === "input" && ["button", "submit", "reset"].includes((el.type || "").toLowerCase())) name = el.value || "";
    if (!name && !["input", "textarea", "select"].includes(tag)) name = el.innerText || el.textContent || "";
    if (!name) {
      const img = el.querySelector && el.querySelector("img[alt]");
      name = el.getAttribute("title") || (img ? img.getAttribute("alt") : "") || "";
    }
    return clean(name, 70);
  };
  const shortHref = (el) => {
    try {
      const u = new URL(el.getAttribute("href"), document.baseURI);
      if (/^(javascript|mailto|tel):/i.test(u.href)) return "";
      return u.origin === location.origin ? (u.pathname + u.search + u.hash) : u.href;
    } catch (e) { return ""; }
  };
  const boxName = (el) => {
    let name = el.getAttribute("aria-label") || "";
    if (!name && el.getAttribute("aria-labelledby")) {
      const node = document.getElementById(el.getAttribute("aria-labelledby").split(/\s+/)[0]);
      name = node ? (node.innerText || node.textContent || "") : "";
    }
    if (!name) {
      const head = el.querySelector("h1, h2, h3, h4, legend");
      name = head ? (head.innerText || "") : "";
    }
    return clean(name || el.getAttribute("id") || el.getAttribute("name") || "", 60);
  };
  const fieldOf = (el) => {
    const tag = el.tagName.toLowerCase();
    const type = tag === "input" ? (el.getAttribute("type") || "text").toLowerCase() : tag;
    const out = { role: roleOf(el), name: nameOf(el), type };
    const ph = el.getAttribute("placeholder");
    if (ph) out.placeholder = clean(ph, 50);
    if (el.required) out.required = true;
    if (el.disabled) out.disabled = true;
    if (type === "checkbox" || type === "radio") out.checked = !!el.checked;
    else if (tag === "select") {
      out.options = Array.from(el.options).slice(0, 12).map((o) => clean(o.text, 40));
      if (el.selectedIndex >= 0 && el.options[el.selectedIndex]) out.value = clean(el.options[el.selectedIndex].text, 40);
    } else if (type !== "password" && el.value) out.value = clean(el.value, 60);
    // No accessible name: cu.fill cannot find it, so give a CSS locator instead.
    if (!out.name) {
      if (el.id) out.locator = "#" + CSS.escape(el.id);
      else if (el.getAttribute("name")) out.locator = tag + '[name="' + clean(el.getAttribute("name"), 40) + '"]';
    }
    if (el.willValidate && !el.checkValidity()) out.invalid = clean(el.validationMessage, 80) || "invalid";
    else if (el.getAttribute("aria-invalid") === "true") out.invalid = "aria-invalid";
    return out;
  };
  const isField = (el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === "input") return !["hidden", "button", "submit", "reset", "image"].includes((el.getAttribute("type") || "").toLowerCase());
    return tag === "textarea" || tag === "select";
  };
  const used = new Set();
  const dialogs = [];
  for (const d of document.querySelectorAll('dialog[open], [role="dialog"], [role="alertdialog"], [aria-modal="true"]')) {
    if (dialogs.length >= 2 || !shown(d)) continue;
    const buttons = [];
    for (const b of d.querySelectorAll('button, [role="button"], a[href], input[type="submit"], input[type="button"]')) {
      if (buttons.length >= 6 || !shown(b)) continue;
      const n = nameOf(b);
      if (n) buttons.push(n);
      used.add(b);
    }
    dialogs.push({ name: boxName(d), text: clean(d.innerText, 240), buttons });
  }
  const alerts = [];
  for (const a of document.querySelectorAll('[role="alert"], [role="status"], [aria-live="assertive"], [aria-live="polite"], .invalid-feedback, .error, .alert')) {
    if (alerts.length >= 5 || !shown(a)) continue;
    const t = clean(a.innerText, 160);
    if (t && !alerts.includes(t)) alerts.push(t);
  }
  const forms = [];
  const formFields = (root, inForm) => {
    const fields = [];
    for (const el of root.querySelectorAll("input, textarea, select")) {
      if (fields.length >= 12) break;
      if (!isField(el) || !shown(el) || (!inForm && el.form) || used.has(el)) continue;
      used.add(el);
      fields.push(fieldOf(el));
    }
    const submits = [];
    for (const b of root.querySelectorAll('button, input[type="submit"], input[type="button"], [role="button"]')) {
      if (submits.length >= 4 || !shown(b) || (!inForm && b.form) || used.has(b)) continue;
      const n = nameOf(b);
      used.add(b);
      if (n) submits.push(n);
    }
    return { fields, submits };
  };
  for (const f of document.forms) {
    if (forms.length >= 4 || !shown(f)) continue;
    const { fields, submits } = formFields(f, true);
    if (!fields.length) continue;
    forms.push({ name: boxName(f), fields, buttons: submits });
  }
  const loose = [];
  for (const el of document.querySelectorAll("input, textarea, select")) {
    if (loose.length >= 8) break;
    if (!isField(el) || el.form || used.has(el) || !shown(el)) continue;
    used.add(el);
    loose.push(fieldOf(el));
  }
  if (loose.length) forms.push({ name: "(fields outside a form)", fields: loose, buttons: [] });
  const main = document.querySelector('main, [role="main"], article') || document.body;
  const vh = window.innerHeight || 800;
  const items = [];
  const seen = new Set();
  const sel = 'a[href], button, summary, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [role="option"], [role="checkbox"], [role="switch"], input[type="submit"], input[type="button"]';
  let order = 0;
  for (const el of document.querySelectorAll(sel)) {
    order += 1;
    if (used.has(el) || !shown(el)) continue;
    const name = nameOf(el);
    if (!name) continue;
    const role = roleOf(el);
    const href = role === "link" && el.hasAttribute("href") ? shortHref(el) : "";
    const key = role + "|" + name + "|" + href;
    if (seen.has(key)) continue;
    seen.add(key);
    const r = el.getBoundingClientRect();
    const inMain = main !== document.body && main.contains(el);
    const inView = r.top < vh && r.bottom > 0;
    const chrome = !!el.closest('nav, header, footer, aside, [role="navigation"], [role="banner"], [role="contentinfo"]');
    items.push({ role, name, href, rank: (inMain ? 0 : 2) + (inView ? 0 : 1) + (chrome ? 2 : 0), order });
  }
  items.sort((a, b) => a.rank - b.rank || a.order - b.order);
  const tables = [];
  for (const t of document.querySelectorAll("table")) {
    if (tables.length >= 3 || !shown(t)) continue;
    const rows = t.rows;
    if (!rows || rows.length < 2) continue;
    const cells = (row) => Array.from(row.cells).slice(0, 8).map((c) => clean(c.innerText, 30));
    const cap = t.caption ? clean(t.caption.innerText, 60) : "";
    tables.push({ caption: cap, rows: rows.length, head: cells(rows[0]), first: cells(rows[1]) });
  }
  const headings = [];
  for (const h of document.querySelectorAll("h1, h2, h3")) {
    if (headings.length >= 12) break;
    if (!shown(h)) continue;
    const t = clean(h.innerText, 80);
    if (t) headings.push(h.tagName.toLowerCase() + " " + t);
  }
  return {
    url: location.href,
    title: clean(document.title, 120),
    headings,
    dialogs,
    alerts,
    forms,
    elements: items.slice(0, 36).map((i) => ({ role: i.role, name: i.name, href: i.href })),
    more_elements: Math.max(0, items.length - 36),
    tables,
    matches: (() => {
      // Page lines that share words or numbers with the task, wherever they sit on the page.
      const list = (terms || []).filter((t) => t);
      if (!list.length || !main) return [];
      const scored = [];
      const raw = (main.innerText || "").split(/\r?\n/);
      for (let i = 0; i < raw.length && i < 6000; i++) {
        const line = raw[i].replace(/\s+/g, " ").trim();
        if (!line || line.length < 2) continue;
        const low = line.toLowerCase();
        let score = 0, first = -1;
        for (const t of list) {
          let at = -1;
          if (/^[0-9]/.test(t)) {
            const m = new RegExp("(^|[^0-9])" + t.replace(/[^a-z0-9]/g, (c) => "\\" + c) + "(?![0-9])").exec(low);
            if (m) { at = m.index + m[1].length; score += 2; }
          } else {
            at = low.indexOf(t);
            if (at >= 0) score += 1;
          }
          if (at >= 0 && (first < 0 || at < first)) first = at;
        }
        if (score < 2) continue;
        const start = line.length > 200 ? Math.max(0, first - 60) : 0;
        scored.push({ score, i, line: line.slice(start, start + 200) });
      }
      scored.sort((a, b) => b.score - a.score || a.i - b.i);
      const out = [];
      for (const item of scored) {
        if (out.length >= 8) break;
        if (!out.includes(item.line)) out.push(item.line);
      }
      return out;
    })(),
    text: clean(main ? main.innerText : "", 1500)
  };
}"""

_SNAPSHOT_CAP = 5000
_TERM_STOP = frozenset(
    "that this with from what which when where there their then than into onto your about after before "
    "page site open find give tell show report name state value values return answer task text link "
    "click visit search using under over each some only also does have will would should could".split()
)


def task_terms(description: str, limit: int = 12) -> list[str]:
    """Numbers and longer words from the task text, for matching page lines. No site knowledge."""
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#_-]*", description or ""):
        word = token.strip(".-_").casefold()
        if not word or word in terms:
            continue
        if any(ch.isdigit() for ch in word) or (len(word) >= 4 and word not in _TERM_STOP):
            terms.append(word)
        if len(terms) >= limit:
            break
    return terms


def _q(text) -> str:
    return json.dumps(str(text or ""), ensure_ascii=False)


def format_page_snapshot(data: dict | None, *, cap: int = _SNAPSHOT_CAP) -> str:
    """Render the repair snapshot as short lines a weak model can copy names from."""
    if not isinstance(data, dict) or not data:
        return ""
    lines = [f"url: {data.get('url') or '(none)'}", f"title: {data.get('title') or ''}"]
    headings = [h for h in data.get("headings") or [] if isinstance(h, str)]
    if headings:
        lines.append("headings: " + " | ".join(headings))
    for dialog in data.get("dialogs") or []:
        if not isinstance(dialog, dict):
            continue
        buttons = ", ".join(_q(b) for b in dialog.get("buttons") or [])
        lines.append(f"OPEN DIALOG {_q(dialog.get('name'))}: {dialog.get('text') or ''}" + (f" buttons: {buttons}" if buttons else ""))
    alerts = [a for a in data.get("alerts") or [] if isinstance(a, str)]
    if alerts:
        lines.append("messages: " + " | ".join(_q(a) for a in alerts))
    for form in data.get("forms") or []:
        if not isinstance(form, dict):
            continue
        lines.append(f"form {_q(form.get('name'))}:")
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            parts = [f"  {field.get('role') or 'field'} {_q(field.get('name'))}", f"type={field.get('type') or ''}"]
            if not field.get("name") and field.get("locator"):
                parts[0] = f"  {field.get('role') or 'field'} (no name) page.locator({_q(field['locator'])})"
            for key in ("placeholder", "value"):
                if field.get(key):
                    parts.append(f"{key}={_q(field[key])}")
            if field.get("options"):
                parts.append("options=[" + ", ".join(_q(o) for o in field["options"]) + "]")
            if "checked" in field:
                parts.append(f"checked={'yes' if field['checked'] else 'no'}")
            for flag in ("required", "disabled"):
                if field.get(flag):
                    parts.append(flag)
            if field.get("invalid"):
                parts.append(f"INVALID: {field['invalid']}")
            lines.append(" ".join(parts))
        buttons = form.get("buttons") or []
        if buttons:
            lines.append("  buttons: " + ", ".join(_q(b) for b in buttons))
    elements = [e for e in data.get("elements") or [] if isinstance(e, dict)]
    if elements:
        lines.append("visible elements (role \"name\" -> href):")
        for element in elements:
            line = f"  {element.get('role') or ''} {_q(element.get('name'))}"
            if element.get("href"):
                line += f" -> {element['href']}"
            lines.append(line)
        more = int(data.get("more_elements") or 0)
        if more:
            lines.append(f"  ...and {more} more")
    matches = [m for m in data.get("matches") or [] if isinstance(m, str) and m.strip()]
    if matches:
        lines.append("page lines that match words in the task:")
        lines.extend(f"  {m}" for m in matches)
    for table in data.get("tables") or []:
        if not isinstance(table, dict):
            continue
        label = f" {_q(table.get('caption'))}" if table.get("caption") else ""
        lines.append(
            f"table{label} ({table.get('rows')} rows): header {table.get('head')} first row {table.get('first')}"
        )
    text = data.get("text") if isinstance(data.get("text"), str) else ""
    head = "\n".join(lines)
    room = cap - len(head) - len("\ntext: ")
    if text and room > 80:
        lines.append("text: " + text[:room])
    rendered = "\n".join(lines)
    return rendered[:cap]


def look_enabled() -> bool:
    """The opt-in look tool. Off unless CU_SF_LOOK=1, so the default arm is unchanged."""
    import os

    return os.environ.get("CU_SF_LOOK", "") == "1"


LOOK_TOOL = {
    "name": "look",
    "description": (
        "Open a URL and return a compact view of that page: headings, forms with their fields, "
        "visible links and buttons with their names, and lines that match the task. "
        "No check runs. Use it at most once, only when you do not know the page's controls "
        "or where the value is; then send run_script, which starts from that page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "http(s) URL to open."}},
        "required": ["url"],
    },
}


SNAPSHOT_BEGIN = "--- PAGE NOW ---"
SNAPSHOT_END = "--- END PAGE ---"
_SNAPSHOT_DROPPED = "(older page snapshot dropped; see the newest one)"


def failed_step_note(code: str, payload: dict | None) -> str:
    """Which step of the script stopped it, and how far it got. No page read."""
    payload = payload if isinstance(payload, dict) else {}
    done = int(payload.get("steps") or 0)
    error = payload.get("error") if isinstance(payload.get("error"), str) else ""
    try:
        steps = parse_task_script(code or "")
    except ScriptError as exc:
        return f"Your script did not parse, so nothing ran: {' '.join(str(exc).split())[:300]}"
    total = len(steps)
    if payload.get("ok") is False:
        detail = " | ".join(line.strip() for line in error.splitlines()[:3] if line.strip())[:300]
        if done < total:
            source = " ".join(steps[done].source.split())[:200]
            return (
                f"Your script ran {done} of {total} steps. Step {done + 1} failed: `{source}`"
                + (f" Error: {detail}" if detail else "")
                + ". The steps after it did not run."
            )
        return f"Your script stopped after {done} of {total} steps." + (f" Error: {detail}" if detail else "")
    return f"Your script ran all {total} steps without an error."


def _claimed_note(payload: dict | None) -> str:
    claimed = payload.get("claimed") if isinstance(payload, dict) else None
    if not isinstance(claimed, dict):
        return "It returned no evidence object."
    parts = []
    for key in ("answer", "key_text"):
        value = claimed.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{key}={_q(value.strip()[:120])}")
    if not parts:
        return "It returned an empty answer and key_text."
    return "It returned " + ", ".join(parts) + "."


def _reason_hint(reason: str) -> str:
    """What the self-check's FAIL reason asks of the next script. Keyed on runtime_verdict's wording."""
    text = (reason or "").casefold()
    if "not on the" in text or "not in the page text" in text:
        return (
            "answer must be the value the task asks for, copied exactly from where it sits next to its label "
            "on the page. If that value is not on this page, this is the wrong page: open the right one. "
            "Do not swap in other text from this page just to match."
        )
    if "not text" in text:
        return "Return answer and key_text as strings and values as a list of strings."
    if "returned no answer" in text:
        return "Put the asked value in answer, copied exactly from the page."
    if "start page" in text or "did not end on a web page" in text:
        return "The script has to leave the start page for the page that holds the asked value."
    if "claimed url" in text:
        return "Return url: location.href, not a URL you typed."
    return ""


def grounded_repair_request(
    reason: str,
    *,
    code: str,
    payload: dict | None,
    snapshot: str,
    repair_number: int,
    max_repairs: int,
) -> str:
    """A repair ask that shows the live page, the failed step, and how far the script got."""
    hint = _reason_hint(reason)
    lines = [
        f"END_STATE_FAILED (repair {repair_number} of {max_repairs}): {reason}.",
        failed_step_note(code, payload) + " " + _claimed_note(payload) + (" " + hint if hint else ""),
        "The browser is still on the page below. Your next script starts from this page: "
        "continue from here, or page.goto a URL to start over.",
        SNAPSHOT_BEGIN,
        snapshot or "(the page could not be read)",
        SNAPSHOT_END,
        "Send one script that finishes the task. Use the names, labels and links shown above; "
        "do not guess selectors that are not on this page. Fix the step that failed. "
        "End with the page.evaluate evidence object and put the asked value in answer. "
        "Do not repeat a script that already ran. If the task cannot be done, call task_failed.",
    ]
    return "\n".join(lines)


def drop_old_snapshots(messages: list[dict]) -> None:
    """Replace the page snapshot in earlier tool results with a short stub, in place."""
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = block.get("content")
            if not isinstance(text, str) or SNAPSHOT_BEGIN not in text:
                continue
            head, _, rest = text.partition(SNAPSHOT_BEGIN)
            _, _, tail = rest.partition(SNAPSHOT_END)
            block["content"] = head + SNAPSHOT_BEGIN + "\n" + _SNAPSHOT_DROPPED + "\n" + SNAPSHOT_END + tail


def normalized_script(code: str) -> str:
    return "".join((code or "").split())


def repair_outcome_key(verdict, payload: dict | None) -> tuple:
    """Two scripts with this same key failed the same way on the same page."""
    payload = payload if isinstance(payload, dict) else {}
    claimed = payload.get("claimed") if isinstance(payload.get("claimed"), dict) else {}
    return (
        str(payload.get("url") or ""),
        getattr(verdict, "reason", ""),
        payload.get("ok") is not False,
        str(claimed.get("answer") or ""),
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
    canonical: str = "",
    h1: str = "",
    text: str = "",
    selector_text: str = "",
    claimed: dict | None = None,
    controls: list | tuple | None = None,
    links: list | tuple | None = None,
    headings: list | tuple | None = None,
) -> str:
    """JSON for the live page plus Stagehand-style goto prose.

    `url` is the browser's URL. It is not rewritten. `- Page URL:` is last.
    """
    payload: dict = {"ok": ok, "url": url, "steps": step_count}
    if error:
        payload["error"] = error
    shown = [item for item in (extracted or []) if str(item).strip()]
    if shown:
        payload["extracted"] = shown
    if title:
        payload["title"] = title
    if canonical:
        payload["canonical"] = canonical
    if h1:
        payload["h1"] = h1
    if text:
        payload["text"] = text[:_PAGE_TEXT_CAP]
    if selector_text:
        payload["selector_text"] = selector_text
    shown_controls = []
    for item in controls or ():
        if isinstance(item, str) and "\t" in item:
            role, name = item.split("\t", 1)
            if name.strip():
                shown_controls.append({"role": role, "name": name})
        elif isinstance(item, dict) and str(item.get("name") or "").strip():
            shown_controls.append({"role": str(item.get("role") or ""), "name": str(item.get("name") or "")})
    if shown_controls:
        payload["controls"] = shown_controls
    if links:
        payload["links"] = [list(pair) for pair in links[:40]]
    shown_headings = [" ".join(h.split())[:160] for h in headings or () if isinstance(h, str) and h.strip()]
    if shown_headings:
        payload["headings"] = shown_headings[:60]
    if claimed:
        kept = {}
        for key in ("url", "title", "h1", "answer", "key_text"):
            item = claimed.get(key)
            if isinstance(item, str) and item.strip():
                kept[key] = item.strip()
        values, bad_values = _coerce_values(claimed.get("values"))
        if bad_values or claimed.get("rejected"):
            kept["rejected"] = True
        elif values:
            kept["values"] = list(values)
        if kept:
            payload["claimed"] = kept
    lines = [json.dumps(payload)]
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        lines.append(f"Ran goto {url}.")
    if shown:
        shown_text = " | ".join(shown)
        if len(shown_text) > 500:
            shown_text = shown_text[:500]
        lines.append(f"Extracted: {shown_text}")
    if title:
        lines.append(f"- Page Title: {title}")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        lines.append(f"- Page URL: {url}")
    return "\n".join(lines)


_HIDDEN_RESULT_KEYS = ("selector_text", "headings")


def budget_script_result(result_text: str, limit: int) -> str:
    """Keep repair lines first and trim only page text, never serialized JSON."""
    lines = (result_text or "").splitlines()
    repairs = [line for line in lines if line.startswith("END_STATE_FAILED:")]
    rest = [line for line in lines if not line.startswith("END_STATE_FAILED:")]
    if not rest:
        return result_text
    try:
        payload = json.loads(rest[0])
    except (ValueError, TypeError):
        return result_text
    if not isinstance(payload, dict) or not {"ok", "steps"} <= payload.keys():
        return result_text

    def render():
        return "\n".join([*repairs, json.dumps(payload), *rest[1:]])

    rendered = render()
    if len(rendered) <= limit:
        return rendered
    text = payload.get("text", "")
    text = text if isinstance(text, str) else ""
    marker = "[text truncated]"
    payload["text"] = marker
    if len(render()) > limit:
        raise ValueError("Script result metadata exceeds tool-result budget; refusing to cut JSON")
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        payload["text"] = text[:mid] + marker
        if len(render()) <= limit:
            low = mid
        else:
            high = mid - 1
    payload["text"] = text[:low] + marker
    return render()


def model_visible_script_result(
    result_text: str,
    *,
    failed: bool = False,
    limit: int | None = None,
    hide_page: bool = False,
) -> str:
    """The run_script result the model may see.

    selector_text is judge-only. Failed results may include trusted links and
    role/name controls; PASS and UNKNOWN results do not expose these hints.
    hide_page also drops the page text: a grounded repair snapshot follows.
    """
    if limit is None:
        from bench.harness import MAX_SNAPSHOT_CHARS

        limit = MAX_SNAPSHOT_CHARS - 300
    lines = (result_text or "").splitlines()
    if not lines:
        return result_text or ""
    json_index = next((i for i, line in enumerate(lines) if line.startswith("{")), None)
    if json_index is None:
        return result_text
    first = lines[json_index].strip()
    if not first.startswith("{"):
        return result_text
    try:
        payload = json.loads(first)
    except json.JSONDecodeError:
        return result_text
    if not isinstance(payload, dict):
        return result_text
    for key in _HIDDEN_RESULT_KEYS:
        payload.pop(key, None)
    if hide_page:
        payload.pop("text", None)
    if not failed:
        payload.pop("links", None)
        payload.pop("controls", None)
    else:
        for key, count in (("links", 40), ("controls", 30)):
            items = payload.get(key)
            if isinstance(items, list):
                payload[key] = items[:count]
            else:
                payload.pop(key, None)
        # Keep navigation hints ahead of page text. If the hints alone cannot
        # fit, drop trailing entries (never cut a label/href or its JSON).
        page_text = payload.get("text")
        payload["text"] = "[text truncated]"
        while True:
            lines[json_index] = json.dumps(payload)
            if len("\n".join(lines)) <= limit:
                break
            candidates = [key for key in ("links", "controls") if payload.get(key)]
            if not candidates:
                break  # The budgeter fails closed if other metadata cannot fit.
            largest = max(candidates, key=lambda key: len(json.dumps(payload[key])))
            payload[largest].pop()
        if page_text is None:
            payload.pop("text", None)
        else:
            payload["text"] = page_text
    lines[json_index] = json.dumps(payload)
    return budget_script_result("\n".join(lines), limit)


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


async def _wait_for_landed(page, before: str) -> None:
    """Wait until a click's navigation is the current document.

    The predicate is "the URL changed". It does not rewrite the URL and it
    does not treat a title as the target page.
    """
    wait = getattr(page, "wait_for_url", None)
    if not callable(wait):
        return

    def arrived(live: str) -> bool:
        current = str(live or "")
        return current.startswith(("http://", "https://")) and current != before

    try:
        result = wait(arrived)
        if asyncio.iscoroutine(result):
            await asyncio.wait_for(result, timeout=_LAND_TIMEOUT_S)
    except Exception:
        return


async def _evaluate_value(page, source: str):
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return None
    try:
        value = evaluate(source)
        if asyncio.iscoroutine(value):
            value = await asyncio.wait_for(value, timeout=_EVALUATE_TIMEOUT_S)
    except Exception:
        return None
    return value


def page_text_from_evidence(data: dict | None) -> str:
    """The page the script left: headings, then the body, capped.

    The evidence judge and the shared check both read this string. A heading
    that is on the page stays in the text when the body prefix is only the
    abstract. The judge's rules are unchanged.
    """
    raw = data if isinstance(data, dict) else {}
    lines = []
    headings = raw.get("headings") if isinstance(raw.get("headings"), list) else []
    for item in headings:
        if isinstance(item, str) and item.strip():
            lines.append(" ".join(item.split()))
    body = raw.get("text") if isinstance(raw.get("text"), str) else ""
    if lines:
        text = "\n".join(lines)
        if body.strip():
            text = f"{text}\n{body}"
    else:
        text = body
    return text[:_PAGE_TEXT_CAP]


def text_from_page_read(value) -> str:
    """Page text from the shared read.

    A string is the body. A dict is the evidence object page_text_from_evidence
    already assembles, headings then body. Every arm uses this after the run.
    """
    if isinstance(value, str):
        return page_text_from_evidence({"text": value})
    if isinstance(value, dict):
        return page_text_from_evidence(value)
    return ""


def mcp_evaluate_value(result_text: str):
    """JSON value from a browser_evaluate response. None when it is not JSON."""
    text = result_text or ""
    body: list[str] = []
    capture = False
    saw_result = False
    for line in text.splitlines():
        if line.startswith("### "):
            if capture:
                break
            capture = line.strip() == "### Result"
            saw_result = saw_result or capture
            continue
        if capture:
            if not body and line.startswith("```"):
                continue
            if line.strip() == "```":
                break
            body.append(line)
    raw = "\n".join(body).strip() if saw_result else text.strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.startswith("```")).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _client_tool_names(client) -> set[str]:
    tools = getattr(client, "tools", None)
    if not isinstance(tools, list):
        return set()
    names = set()
    for tool in tools:
        if isinstance(tool, dict) and isinstance(tool.get("name"), str):
            names.add(tool["name"])
    return names


def marked_selector_source(selector: str) -> str:
    """The live value of answer_equals_selector. Judge data, not a model prompt."""
    literal = json.dumps(selector or "")
    return (
        "() => { const selector = "
        + literal
        + "; const el = selector ? document.querySelector(selector) : null; "
        + 'if (!el) return ""; return (el.innerText || el.textContent || "").trim(); }'
    )


def _marked_from_evaluate(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("selector", "selector_text"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return ""


async def read_marked_page(client, selector: str) -> tuple[str, str]:
    """Page text and the live selector, the same read for every arm.

    A page object uses collect_page_evidence. Playwright MCP evaluates the
    same page-evidence function, then the same selector read. An arm that
    cannot read returns empty strings. This is not a model prompt.
    """
    page = getattr(client, "_page", None)
    if page is not None:
        try:
            evidence = await collect_page_evidence(page, selector=selector)
        except Exception:
            return "", ""
        return evidence.text, evidence.selector_text
    if "browser_evaluate" not in _client_tool_names(client):
        return "", ""
    call = getattr(client, "call_tool", None)
    if not callable(call):
        return "", ""
    try:
        result = await call("browser_evaluate", {"function": _PAGE_EVIDENCE_JS})
    except Exception:
        return "", ""
    raw = result[0] if isinstance(result, tuple) else result
    page_text = text_from_page_read(mcp_evaluate_value(str(raw or "")))
    if not selector:
        return page_text, ""
    try:
        result = await call("browser_evaluate", {"function": marked_selector_source(selector)})
    except Exception:
        return page_text, ""
    raw = result[0] if isinstance(result, tuple) else result
    return page_text, _marked_from_evaluate(mcp_evaluate_value(str(raw or "")))


async def collect_page_evidence(page, *, selector: str = "") -> PageEvidence:
    """Read the live page. The script's return value is not used here."""
    url = _page_url(page)
    title = await _read_title(page)
    raw = await _evaluate_value(page, _PAGE_EVIDENCE_JS)
    data = raw if isinstance(raw, dict) else {}
    if not _http(url):
        candidate = data.get("url") if isinstance(data.get("url"), str) else ""
        if _http(candidate):
            url = candidate
    if not title and isinstance(data.get("title"), str):
        title = data["title"]
    selector_text = ""
    if selector:
        found = await _evaluate_value(page, marked_selector_source(selector))
        if isinstance(found, str):
            selector_text = found.strip()
    text = page_text_from_evidence(data)
    canonical = data.get("canonical") if isinstance(data.get("canonical"), str) else ""
    h1 = data.get("h1") if isinstance(data.get("h1"), str) else ""
    pairs: list[str] = []
    raw_controls = data.get("controls") if isinstance(data.get("controls"), list) else []
    for item in raw_controls:
        if isinstance(item, dict):
            role = str(item.get("role") or "")
            name = str(item.get("name") or "")
        elif isinstance(item, str) and "\t" in item:
            role, name = item.split("\t", 1)
        else:
            continue
        if name.strip():
            pairs.append(f"{role}\t{name}")
    return PageEvidence(
        url=url,
        title=title,
        canonical=canonical.strip(),
        h1=h1.strip(),
        text=text,
        selector_text=selector_text,
        controls=tuple(pairs),
        links=tuple(
            (item[0], item[1]) for item in data.get("links", [])
            if isinstance(item, (list, tuple)) and len(item) == 2
            and all(isinstance(value, str) for value in item)
        )[:40],
        headings=tuple(
            " ".join(item.split()) for item in data.get("headings") or [] if isinstance(item, str) and item.strip()
        )[:60],
    )


def _note_extract(extracted: list[str], claimed: dict, value) -> dict:
    parsed = _claim_from_value(value)
    if parsed:
        for key, item in parsed.items():
            if item:
                claimed[key] = item
        if parsed.get("answer"):
            extracted.append(parsed["answer"])
        return claimed
    text = _coerce_extract(value)
    if text:
        extracted.append(text)
        claimed["answer"] = text
    return claimed


async def _finish_page(
    page,
    *,
    ok: bool,
    step_count: int,
    error: str,
    extracted: list[str],
    claimed: dict,
    end_markers: dict | None,
    wait_for_commit: bool,
) -> str:
    """Read the live page after the script. The URL is not rewritten."""
    if wait_for_commit:
        await _wait_for_landed(page, _page_url(page))
    selector = ""
    if end_markers:
        selector = str(end_markers.get("answer_equals_selector") or "")
    evidence = await collect_page_evidence(page, selector=selector)
    return format_run_result(
        ok=ok,
        url=evidence.url,
        step_count=step_count,
        error=error,
        extracted=extracted,
        title=evidence.title,
        canonical=evidence.canonical,
        h1=evidence.h1,
        text=evidence.text,
        selector_text=evidence.selector_text,
        claimed=claimed,
        controls=evidence.controls,
        links=evidence.links,
        headings=evidence.headings,
    )


def _page_url(page) -> str:
    url = getattr(page, "url", "") or ""
    return url if isinstance(url, str) else ""


async def _run_step_on_page(page, step: TaskStep):
    if step.kind == "evaluate":
        return await asyncio.wait_for(
            page.evaluate(wrap_evaluate(step.function)),
            timeout=_EVALUATE_TIMEOUT_S,
        )
    if step.kind == "helper":
        if step.helper is None:
            raise ScriptError(f"line {step.line}: missing helper")
        await run_helper(page, step.helper, timeout_ms=_ACTION_TIMEOUT_MS)
        return None
    action = step.action
    if action is None:
        raise ScriptError(f"line {step.line}: missing action")
    if action.op == "goto":
        await page.goto(action.value, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        return None
    if action.finder == "page":
        if action.op == "click":
            await page.click(action.name, timeout=_ACTION_TIMEOUT_MS)
        elif action.op == "fill":
            await page.fill(action.name, action.value, timeout=_ACTION_TIMEOUT_MS)
        elif action.op == "press":
            await page.press(action.name, action.value, timeout=_ACTION_TIMEOUT_MS)
        elif action.op == "goBack":
            await page.go_back(wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        elif action.op == "title":
            return await asyncio.wait_for(page.title(), timeout=1.0)
        elif action.op == "url":
            return _page_url(page)
        else:
            raise ScriptError(f"line {step.line}: unsupported page action {action.op}")
        return None
    if action.finder == "keyboard":
        # Keyboard methods have no Playwright timeout argument.
        if action.op == "press":
            pending = page.keyboard.press(action.value)
        elif action.op == "type":
            pending = page.keyboard.type(action.value)
        else:
            raise ScriptError(f"line {step.line}: unsupported keyboard action {action.op}")
        await asyncio.wait_for(pending, timeout=_ACTION_TIMEOUT_MS / 1000)
        return None
    locator = browser_locator(page, action)
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
    elif action.op == "selectOption":
        await locator.select_option(action.value, timeout=_ACTION_TIMEOUT_MS)
    elif action.op == "textContent":
        return await locator.text_content(timeout=_ACTION_TIMEOUT_MS)
    elif action.op == "innerText":
        return await locator.inner_text(timeout=_ACTION_TIMEOUT_MS)
    elif action.op == "getAttribute":
        return await locator.get_attribute(action.value, timeout=_ACTION_TIMEOUT_MS)
    else:
        raise ScriptError(f"line {step.line}: unsupported action {action.op}")
    return None


async def run_on_page(
    page,
    source: str,
    *,
    end_markers: dict | None = None,
) -> str:
    """Run the whole script on a Playwright page. No settle between actions.

    Goto waits for DOMContentLoaded. Wait lines were already dropped.
    Evaluate claims take precedence over top-level reads; reads are a fallback
    only when no evaluate supplied an answer or key_text. After the script the
    harness reads the live URL, canonical link, h1, and main text itself.
    """
    steps = parse_task_script(source)
    done = 0
    extracted: list[str] = []
    claimed: dict = {}
    read_claimed: dict = {}
    ok, error = True, ""
    try:
        for step in steps:
            value = await _run_step_on_page(page, step)
            done += 1
            if step.kind == "evaluate":
                claimed = _note_extract(extracted, claimed, value)
            elif step.kind == "read":
                read_claimed = _note_extract(extracted, read_claimed, value)
    except ScriptError:
        raise
    except Exception as exc:
        ok, error = False, str(exc)
    if not (claimed.get("answer") or claimed.get("key_text")):
        claimed = {**read_claimed, **claimed}
    return await _finish_page(
        page,
        ok=ok,
        step_count=done,
        error=error,
        extracted=extracted,
        claimed=claimed,
        end_markers=end_markers,
        wait_for_commit=not ok or (bool(steps) and steps[-1].kind != "goto"),
    )


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
    if any(step.kind not in {"goto", "evaluate"} for step in steps):
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
                await _mcp_text(
                    call_tool,
                    "browser_evaluate",
                    {"function": wrap_evaluate(step.function)},
                )
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
        self.end_markers: dict = {}
        # The task text for the opt-in look tool's matching lines. The harness sets it.
        self.look_task = ""
        self._playwright = None
        self._browser = None
        self._context = None
        self._profile_dir: str | None = None
        self._launch_task: asyncio.Task | None = None

    def tools_for_claude(self) -> list[dict]:
        return [
            {
                "name": "run_script",
                "description": (
                    "Run one Playwright script that finishes the whole task in this call. "
                    "The end URL must already be the finished page, not a search-results URL. "
                    "End with page.evaluate(() => ({url: location.href, title: document.title, "
                    "h1: document.querySelector('h1')?.innerText, key_text: '', values: [], answer: ''})). "
                    "Put a phrase that is on the page in key_text, the asked-for values in values, "
                    "and the requested value in answer. cu.claim inside page.evaluate returns that object. "
                    "cu.click, cu.fill, and cu.press take an accessible name and act on the one control with that name. "
                    "The runner checks the returned object against the live page. "
                    "Do not call page.waitForTimeout, page.waitForLoadState, or networkidle. "
                    "Allowed lines are page.goto, page.getByRole, page.getByLabel, "
                    "page.getByText, page.getByPlaceholder, cu.click, cu.fill, cu.press, "
                    "and page.evaluate with a page-context function. The runner does not settle or snapshot "
                    "between actions and drops wait lines. "
                    "browser_run_code_unsafe is not available. "
                    "The runner reads the live page itself after the script. "
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
            },
            {
                "name": "task_failed",
                "description": "Stop the task when it cannot be completed and explain why.",
                "input_schema": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                },
            }
        ] + ([dict(LOOK_TOOL)] if look_enabled() else [])

    def begin_launch(self) -> asyncio.Future:
        """Launch local Chrome if it is not already up.

        A second call shares the same launch. This does not navigate, so the
        URL the judge scores is still the page the script leaves open.
        """
        if self._launch_task is not None and not self._launch_task.done():
            return self._launch_task
        if self._page is not None:
            done = asyncio.get_running_loop().create_future()
            done.set_result(None)
            return done
        self._launch_task = asyncio.create_task(self._open_browser())
        return self._launch_task

    async def start(self) -> None:
        await self.begin_launch()

    async def _open_browser(self) -> None:
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

    async def _look(self, arguments: dict, start: float) -> tuple[str, float]:
        url = str(arguments.get("url") or "").strip()
        error = ""
        if _http(url):
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
            except Exception as exc:
                error = " ".join(str(exc).split())[:200]
        elif url:
            error = "look needs an http(s) URL"
        snapshot, _ms = await self.page_snapshot(self.look_task)
        lines = [f"LOOK (no check ran){': ' + error if error else ''}", SNAPSHOT_BEGIN, snapshot or "(the page could not be read)", SNAPSHOT_END]
        lines.append("Now send run_script. It starts from this page.")
        return "\n".join(lines), (time.perf_counter() - start) * 1000

    async def page_snapshot(self, task: str = "") -> tuple[str, float]:
        """The compact repair snapshot of the live page, and the ms it took."""
        start = time.perf_counter()
        if self._page is None:
            return "", 0.0
        source = "() => (" + _REPAIR_SNAPSHOT_JS + ")(" + json.dumps(task_terms(task)) + ")"
        raw = await _evaluate_value(self._page, source)
        data = raw if isinstance(raw, dict) else {}
        if data and not _http(str(data.get("url") or "")):
            data["url"] = _page_url(self._page) or data.get("url")
        if not data:
            url = _page_url(self._page)
            data = {"url": url, "title": await _read_title(self._page)} if url else {}
        return format_page_snapshot(data), (time.perf_counter() - start) * 1000

    async def call_tool(self, name: str, arguments: dict | None) -> tuple[str, float]:
        if name == "browser_run_code_unsafe":
            raise ScriptError("browser_run_code_unsafe is not available")
        if self._page is None:
            raise RuntimeError("script_first client is not started")
        start = time.perf_counter()
        if name == "look" and look_enabled():
            return await self._look(arguments or {}, start)
        if name != "run_script":
            return f"unknown tool {name}", 0.0
        code = (arguments or {}).get("code") or (arguments or {}).get("script") or ""
        try:
            text = await run_on_page(self._page, code, end_markers=self.end_markers)
        except ScriptError as exc:
            text = format_run_result(ok=False, url=_page_url(self._page), step_count=0, error=str(exc))
        elapsed_ms = (time.perf_counter() - start) * 1000
        return text, elapsed_ms
