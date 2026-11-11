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
from dataclasses import dataclass, field
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

# controls is the fingerprint's role/name list. model_visible_script_result strips it.
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
    controls
  };
}"""

from bench.script_helpers import HelperCall, is_helper_call, parse_helper_call, run_helper, wrap_evaluate
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
        if body.casefold().startswith("return "):
            returned = _normalize_stmt(body[len("return ") :])
            if returned.casefold().startswith("page.evaluate"):
                body = returned
        if _is_wait_statement(body):
            continue
        if body.casefold().startswith("page.evaluate"):
            steps.append(_parse_evaluate(body, index))
            continue
        helper_body = body[len("await ") :].strip() if body.casefold().startswith("await ") else body
        if is_helper_call(helper_body):
            steps.append(TaskStep(kind="helper", line=index, source=body, helper=parse_helper_call(body, index)))
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
    # Machine-readable FAIL reason from runtime_verdict. Not part of equality.
    code: str = field(default="", compare=False)


# runtime_verdict FAIL codes. A hard FAIL has nothing a second opinion could read.
FAIL_SCRIPT_ERROR = "script_error"
FAIL_EMPTY_EVIDENCE = "empty_evidence"
FAIL_NO_WEB_PAGE = "no_web_page"
FAIL_CLAIMED_URL = "claimed_url_mismatch"
FAIL_START_PAGE_NO_RETURN = "start_page_no_return"
FAIL_NO_RETURN = "no_return"
FAIL_ANSWER_NOT_IN_TEXT = "answer_not_in_text"
FAIL_RETURN_NOT_TEXT = "return_not_text"
FAIL_EVIDENCE_NOT_ON_PAGE = "evidence_not_on_page"
HARD_FAIL_CODES = frozenset({FAIL_EMPTY_EVIDENCE, FAIL_NO_WEB_PAGE, FAIL_START_PAGE_NO_RETURN})


def is_soft_fail(verdict: "EvidenceVerdict | None", payload: dict | None, page_url: str = "") -> bool:
    """A coded runtime FAIL on a live http(s) page that has some text."""
    if verdict is None or verdict.verdict != FAIL or not verdict.code:
        return False
    if verdict.code in HARD_FAIL_CODES:
        return False
    data = payload if isinstance(payload, dict) else {}
    live = page_url or (data.get("url") if isinstance(data.get("url"), str) else "")
    text = data.get("text") if isinstance(data.get("text"), str) else ""
    return _http(live) and bool(text.strip())


def overturned_verdict(verdict: "EvidenceVerdict") -> "EvidenceVerdict":
    """script_first's own PASS after the Decisions second opinion accepted a soft FAIL."""
    return EvidenceVerdict(
        PASS,
        f"second opinion accepted the end state (runtime check said: {verdict.reason})",
        verdict.scored_url,
        verdict.code,
    )


def _http(url: str) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _fold_token(value: str) -> str:
    text = unquote(value or "").replace("_", " ").replace("-", " ").replace("+", " ")
    return " ".join(text.split()).casefold()


def _norm_answer(value: str) -> str:
    return " ".join((value or "").split()).casefold()


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
        return EvidenceVerdict(FAIL, "returned value is not text", scored, FAIL_RETURN_NOT_TEXT)
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
            return EvidenceVerdict(FAIL, "returned evidence is not on the page", scored, FAIL_EVIDENCE_NOT_ON_PAGE)
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


def runtime_verdict(
    trusted: PageEvidence,
    claimed: ClaimedEvidence | None = None,
    *,
    script_ok: bool = True,
    script_error: str = "",
    start_url: str = "",
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
        return EvidenceVerdict(FAIL, f"the script stopped before it finished ({detail or 'error'})", scored, FAIL_SCRIPT_ERROR)
    if not has_page and not has_body:
        return EvidenceVerdict(FAIL, "empty evidence", "", FAIL_EMPTY_EVIDENCE)
    if not has_page:
        return EvidenceVerdict(FAIL, "the script did not end on a web page", "", FAIL_NO_WEB_PAGE)
    if _http(claimed.url) and not _same_page(claimed.url, live) and not (
        canonical and _same_page(claimed.url, canonical)
    ):
        return EvidenceVerdict(FAIL, "claimed URL does not match the live page", scored, FAIL_CLAIMED_URL)
    answer = (claimed.answer or "").strip()
    returned_any = bool(answer or (claimed.key_text or "").strip() or any(v.strip() for v in claimed.values))
    if not returned_any:
        # The prompt asks every script to return an answer or a phrase from the page.
        if _http(start_url) and _same_page(live, start_url):
            return EvidenceVerdict(
                FAIL, "the script ended on the start page and returned nothing", live, FAIL_START_PAGE_NO_RETURN
            )
        return EvidenceVerdict(FAIL, "the script returned no answer or key_text", scored, FAIL_NO_RETURN)
    if answer:
        if not page_text.strip():
            return EvidenceVerdict(UNKNOWN, "page text was not read", scored)
        if _norm_answer(answer) not in _norm_answer(page_text):
            return EvidenceVerdict(FAIL, "answer is not in the page text", scored, FAIL_ANSWER_NOT_IN_TEXT)
    problem = _returned_problem(claimed, page_text, scored)
    if problem is not None:
        return problem
    return EvidenceVerdict(PASS, "the script finished and its evidence is on the live page", scored)


def script_runtime_verdict(result_text: str, page_url: str, start_url: str = "") -> tuple[EvidenceVerdict, dict]:
    """Judge one run_script result without the task's markers."""
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
    )
    return verdict, payload


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


_HIDDEN_RESULT_KEYS = ("selector_text", "controls")


def model_visible_script_result(result_text: str) -> str:
    """The run_script result the model may see.

    selector_text is the judge's own read of answer_equals_selector. controls
    is the role/name list the cache fingerprint hashes. A model message
    must not include either.
    """
    lines = (result_text or "").splitlines()
    if not lines:
        return result_text or ""
    first = lines[0].strip()
    if not first.startswith("{"):
        return result_text
    try:
        payload = json.loads(first)
    except json.JSONDecodeError:
        return result_text
    if not isinstance(payload, dict) or not any(key in payload for key in _HIDDEN_RESULT_KEYS):
        return result_text
    for key in _HIDDEN_RESULT_KEYS:
        payload.pop(key, None)
    lines[0] = json.dumps(payload)
    return "\n".join(lines)


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
    )


def _note_extract(extracted: list[str], claimed: dict, value) -> dict:
    parsed = _claim_from_value(value)
    if parsed:
        for key, item in parsed.items():
            if item and not claimed.get(key):
                claimed[key] = item
        if parsed.get("answer"):
            extracted.append(parsed["answer"])
        return claimed
    text = _coerce_extract(value)
    if text:
        extracted.append(text)
        if not claimed.get("answer"):
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
    end_markers: dict | None = None,
) -> str:
    """Run the whole script on a Playwright page. No settle between actions.

    Goto waits for DOMContentLoaded. Wait lines were already dropped. An
    evaluate return value is the script's claim. After the script the harness
    reads the live URL, canonical link, h1, and main text itself.
    """
    steps = parse_task_script(source)
    done = 0
    extracted: list[str] = []
    claimed: dict = {}
    try:
        for step in steps:
            value = await _run_step_on_page(page, step)
            done += 1
            if step.kind == "evaluate":
                claimed = _note_extract(extracted, claimed, value)
    except ScriptError:
        raise
    except Exception as exc:
        return await _finish_page(
            page,
            ok=False,
            step_count=done,
            error=str(exc),
            extracted=extracted,
            claimed=claimed,
            end_markers=end_markers,
            wait_for_commit=True,
        )
    return await _finish_page(
        page,
        ok=True,
        step_count=len(steps),
        error="",
        extracted=extracted,
        claimed=claimed,
        end_markers=end_markers,
        wait_for_commit=bool(steps) and steps[-1].kind != "goto",
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
    if any(step.kind in {"locator", "helper"} for step in steps):
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
            }
        ]

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
            text = await run_on_page(self._page, code, end_markers=self.end_markers)
        except ScriptError as exc:
            text = format_run_result(ok=False, url=_page_url(self._page), step_count=0, error=str(exc))
        elapsed_ms = (time.perf_counter() - start) * 1000
        return text, elapsed_ms
