"""Frozen, stdlib-only post-run page grader. See docs/GRADER.md."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qsl, unquote, urlsplit

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"


@dataclass
class JudgeResult:
    """Result of judging a task."""
    success: bool
    reason: str
    confidence: float


def is_search_results_url(url: str) -> bool:
    """True for a results page, including Special:Search?search=Ada_Lovelace.

    A query that merely contains the token is not the finished article.
    """
    if not isinstance(url, str) or not url:
        return False
    raw = url.strip()
    decoded = unquote(raw).casefold()
    if "special:search" in decoded or "special%3asearch" in raw.casefold():
        return True
    parts = urlsplit(raw)
    path = unquote(parts.path).casefold()
    trimmed = path.rstrip("/")
    if trimmed.endswith("/search") or trimmed.endswith("/search.html") or "/search.html" in path:
        return True
    query = unquote(parts.query).casefold()
    if trimmed.endswith("index.php") and (
        query.startswith("search=") or query.startswith("search%3d") or "&search=" in f"&{query}"
    ):
        return True
    return False


def check_url_contains(current_url: str, expected: str) -> JudgeResult:
    """Check if URL contains expected string.

    Search-results URLs fail unless the expected key itself targets search.
    """
    if is_search_results_url(current_url) and not is_search_results_url(expected):
        return JudgeResult(
            success=False,
            reason=f"URL is a search page: '{current_url}'",
            confidence=1.0,
        )
    if _query_url_matches(current_url, expected, normalized=False):
        return JudgeResult(
            success=True,
            reason=f"URL contains '{expected}'",
            confidence=1.0,
        )
    return JudgeResult(
        success=False,
        reason=f"URL '{current_url}' does not contain '{expected}'",
        confidence=1.0,
    )


def check_text_present(page_text: str, expected: str | list[str]) -> JudgeResult:
    """Check if expected text(s) are present on the page."""
    if isinstance(expected, str):
        expected = [expected]

    missing = []
    for text in expected:
        if text.lower() not in page_text.lower():
            missing.append(text)

    if not missing:
        return JudgeResult(
            success=True,
            reason=f"All expected text found: {expected}",
            confidence=1.0,
        )
    return JudgeResult(
        success=False,
        reason=f"Missing text: {missing}",
        confidence=1.0,
    )


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

    @property
    def code(self) -> str:
        if self.reason.startswith("the page is denied"):
            return "page_denied"
        return self.reason.replace(" ", "_")


def _http(url: str) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _fold_token(value: str) -> str:
    text = unquote(value or "").replace("_", " ").replace("-", " ").replace("+", " ")
    return " ".join(text.split()).casefold()


def _norm_answer(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def _answer_candidates(answer: str) -> tuple[str, ...]:
    pairs = (("**", "**"), ("__", "__"), ('"', '"'), ("'", "'"),
             ("“", "”"), ("‘", "’"), ("`", "`"), ("*", "*"), ("_", "_"))
    framed = False
    answer = answer.strip()
    candidates = [answer]
    while True:
        previous = answer
        answer = answer.strip().rstrip(".,;:!").strip()
        if answer != previous:
            candidates.append(answer)
            continue
        for left, right in pairs:
            if len(answer) >= len(left) + len(right) and answer.startswith(left) and answer.endswith(right):
                answer = answer[len(left):-len(right)].strip()
                break
        else:
            if not framed:
                match = re.fullmatch(
                    r"(?i)(?:(?:the|a)\s+)?[^\W\d_]+(?:\s+[^\W\d_]+){0,5}"
                    r"(?:\s+(?:is|are|was|were)\s+|:\s+)(.+)",
                    answer,
                )
                if match:
                    answer = match[1]
                    framed = True
        if answer == previous:
            return tuple(candidates)
        candidates.append(answer)


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
    if "?" in token:
        return _query_url_matches(url, token, normalized=True)
    if token.casefold() in url.casefold():
        return True
    decoded = unquote(url)
    if token.casefold() in decoded.casefold():
        return True
    return _fold_token(token) in _fold_token(decoded)


def _query_url_matches(url: str, expected: str, *, normalized: bool) -> bool:
    if "?" not in expected:
        return _marker_in_url(url, expected) if normalized else expected.lower() in url.lower()
    prefix = expected.split("?", 1)[0]
    actual_prefix = url.split("?", 1)[0].split("#", 1)[0]
    path_ok = not prefix or (
        _marker_in_url(actual_prefix, prefix) if normalized else prefix.lower() in actual_prefix.lower()
    )
    actual = Counter(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    required = Counter(parse_qsl(urlsplit(expected).query, keep_blank_values=True))
    return path_ok and all(actual[pair] >= count for pair, count in required.items())


def _search_denied(url: str, markers: dict) -> bool:
    return is_search_results_url(url) and not is_search_results_url(markers.get("url_contains") or "")


def _task_markers(task: dict) -> dict:
    markers = dict(task["end_markers"]) if isinstance(task.get("end_markers"), dict) else {}
    for key in ("full_answer", "answer_parts", "url_answer_ok"):
        if key in task:
            markers[key] = task[key]
    expected = task.get("check_url_contains") or ""
    if not markers.get("url_contains") and expected and (
        markers.get("url_answer_ok") is True or is_search_results_url(expected)
    ):
        markers["url_contains"] = task["check_url_contains"]
    return markers


def _answer_url(answer: str) -> str:
    pairs = (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’"), ("`", "`"), ("<", ">"))
    value = answer.strip()
    while True:
        previous = value
        value = value.rstrip(".").strip()
        for left, right in pairs:
            if len(value) >= 2 and value.startswith(left) and value.endswith(right):
                value = value[len(left):-len(right)].strip()
                break
        link = re.fullmatch(r"\[[^\]\r\n]*\]\((https?://[^\s<>]+)\)", value)
        if link:
            value = link[1]
        if value == previous:
            break
    return value if re.fullmatch(r"https?://[^\s<>\"`]+", value) else ""


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
    if _search_denied(url, markers) or _deny_hit(url, markers.get("deny") or []):
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
        _http(live) and (_search_denied(live, markers) or _deny_hit(live, markers.get("deny") or []))
    ):
        return canonical
    if _http(live):
        return live
    if _http(canonical):
        return canonical
    return ""


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

    if _http(live) and (_search_denied(live, markers) or _deny_hit(live, markers.get("deny") or [])):
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

    if markers.get("url_answer_ok") is True:
        answer_url = _answer_url(answer)
        if answer_url:
            if needs_url and _url_matches(answer_url, markers) and _url_matches(live, markers):
                return gate(EvidenceVerdict(PASS, "the URL answer matches the expected page", live))
            return EvidenceVerdict(FAIL, "the URL answer does not match the expected page", scored)

    parts = markers.get("answer_parts")
    if selector or answer_in_text or parts is not None:
        if not answer:
            return EvidenceVerdict(FAIL, "empty answer", scored)
        marker = str(answer_in_text) if answer_in_text else (trusted.selector_text or "").strip()
        reference = markers.get("full_answer", marker)
        if not isinstance(reference, str):
            return EvidenceVerdict(FAIL, "invalid full answer key", scored)
        reference_length = len(_norm_answer(reference))
        if len(answer) > 3 * len(reference) + 40:
            return EvidenceVerdict(FAIL, "answer too long", scored)
        candidates = _answer_candidates(answer)
        if parts is not None:
            if not isinstance(parts, list) or any(not isinstance(part, str) or not part.strip() for part in parts):
                return EvidenceVerdict(FAIL, "invalid answer parts key", scored)
            required = list(parts)
            if marker and marker not in required:
                required.append(marker)
            if not required:
                return EvidenceVerdict(FAIL, "empty answer parts key", scored)
            if selector and not marker:
                return gate(EvidenceVerdict(UNKNOWN, "page text was not read", scored))
            candidates = tuple(
                core for core in candidates if all(_phrase_at_boundary(part, core) for part in required)
            )
            if not candidates:
                return EvidenceVerdict(FAIL, "answer does not satisfy the required parts", scored)
            candidates = tuple(
                core for core in candidates
                if len(_norm_answer(core)) - reference_length <= max(8, reference_length)
            )
            if not candidates:
                return EvidenceVerdict(FAIL, "answer too long", scored)
            if not page_text.strip():
                return gate(EvidenceVerdict(UNKNOWN, "page text was not read", scored))
            if not all(_phrase_at_boundary(part, page_text) for part in required):
                return EvidenceVerdict(FAIL, "answer part is not in the page text", scored)
        elif selector:
            truth = (trusted.selector_text or "").strip()
            if not truth or not page_text.strip():
                return gate(EvidenceVerdict(UNKNOWN, "page text was not read", scored))
            truths = {_norm_answer(truth), _norm_answer(truth.rstrip(".,;:!"))}
            candidates = tuple(core for core in candidates if _norm_answer(core) in truths)
            if not candidates:
                return EvidenceVerdict(FAIL, "answer is not the marked value", scored)
            candidates = tuple(core for core in candidates if _norm_answer(core) in _norm_answer(page_text))
            if not candidates:
                return EvidenceVerdict(FAIL, "answer is not in the page text", scored)
        if answer_in_text and parts is None:
            if not page_text.strip():
                return gate(EvidenceVerdict(UNKNOWN, "page text was not read", scored))
            candidates = tuple(core for core in candidates if _phrase_at_boundary(str(answer_in_text), core))
            if not candidates:
                return EvidenceVerdict(FAIL, "answer does not satisfy the marker", scored)
            candidates = tuple(
                core for core in candidates
                if len(_norm_answer(core)) - reference_length <= max(8, reference_length)
            )
            if not candidates:
                return EvidenceVerdict(FAIL, "answer too long", scored)
            if not any(_norm_answer(core) in _norm_answer(page_text) for core in candidates):
                return EvidenceVerdict(FAIL, "answer is not in the page text", scored)
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


def _returned_problem(
    claimed: ClaimedEvidence, page_text: str, scored: str
) -> EvidenceVerdict | None:
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
        norm = _norm_answer(item)
        if norm not in folded:
            return EvidenceVerdict(FAIL, "returned evidence is not on the page", scored)
    return None


# ---------------------------------------------------------------------------
# Scorer v2: tasks that carry a `key_v2` dict. See docs/GRADER.md, "Scorer v2".
# Tasks without key_v2 keep every v1 rule above, byte for byte.
# ---------------------------------------------------------------------------

V2_DELIVERABLES = ("answer", "page", "both")
V2_DEFAULT_DENY = ("/signin", "/login", "/sorry/")
_V2_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_V2_QUOTES = {ord("‘"): "'", ord("’"): "'", ord("“"): '"', ord("”"): '"'}
_V2_DROP = dict.fromkeys(map(ord, "™®©*`"), None)
_V2_FAILURE = re.compile(
    r"^\s*(?:task failed|failed\b)"
    r"|\bi (?:could not|couldn't|was unable to|am unable to|cannot|can't|did not manage to)\b"
    r"|\bunable to (?:find|access|complete|locate|verify|load|open|submit|apply)\b"
)


def _fold_v2(value: str) -> str:
    """Formatting-only normalisation for v2 fact matching."""
    text = (value or "").translate(_V2_DROP)
    text = unicodedata.normalize("NFKC", text).translate(_V2_DASHES).translate(_V2_QUOTES)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    text = re.sub(r"(?<=\d)\s*-\s*(?=\d)", "-", text)
    return " ".join(text.split()).casefold()


def _v2_alternatives(fact) -> tuple[list[list[str]], int] | None:
    """[[all-of strings], ...] alternatives and the minimum distinct matches."""
    if isinstance(fact, dict):
        options, minimum = fact.get("any"), fact.get("min", 1)
    else:
        options, minimum = fact, 1
    if not isinstance(options, list) or not options or not isinstance(minimum, int) or minimum < 1:
        return None
    groups = []
    for option in options:
        group = [option] if isinstance(option, str) else option
        if not isinstance(group, list) or not group or any(
            not isinstance(item, str) or not item.strip() for item in group
        ):
            return None
        groups.append(group)
    if minimum > len(groups):
        return None
    return groups, minimum


def _v2_key_problem(key) -> bool:
    if not isinstance(key, dict) or key.get("deliverable") not in V2_DELIVERABLES:
        return True
    host = key.get("host")
    hosts = host if isinstance(host, list) else [host]
    if not hosts or any(not isinstance(item, str) or not item.strip() for item in hosts):
        return True
    if not isinstance(key.get("reference"), str) or not key["reference"].strip():
        return True
    pages, facts = key.get("pages"), key.get("facts")
    if key["deliverable"] in ("page", "both"):
        if not isinstance(pages, list) or not pages or any(
            not isinstance(p, dict) or not (p.get("path") or p.get("url_contains")) for p in pages
        ):
            return True
    if key["deliverable"] in ("answer", "both"):
        if not isinstance(facts, list) or not facts or any(_v2_alternatives(f) is None for f in facts):
            return True
    return False


def _v2_number(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _v2_condition(values: list[str], condition) -> bool:
    if not isinstance(condition, dict) or not values:
        return False
    for value in values:
        ok = True
        if "any" in condition:
            ok = ok and value in condition["any"]
        if "has" in condition:
            ok = ok and condition["has"] in value.split(",")
        if "contains" in condition:
            words = condition["contains"]
            words = [words] if isinstance(words, str) else words
            ok = ok and any(word.casefold() in value.casefold() for word in words)
        if "prefix" in condition:
            ok = ok and value.startswith(condition["prefix"])
        if "max" in condition or "min" in condition:
            number = _v2_number(value)
            ok = ok and number is not None
            if ok and "max" in condition:
                ok = number <= condition["max"]
            if ok and "min" in condition:
                ok = number >= condition["min"]
        if ok:
            return True
    return False


def _v2_nights(params: dict) -> int | None:
    def first(*names):
        for name in names:
            if params.get(name):
                return params[name][0]
        return ""

    try:
        start = date.fromisoformat(first("checkin", "check_in"))
        end = date.fromisoformat(first("checkout", "check_out"))
    except ValueError:
        return None
    return (end - start).days


def _v2_page_matches(url: str, text: str, page: dict) -> bool | None:
    """True/False for a URL pattern; None when it needs page text that was not read."""
    parts = urlsplit(url)
    path = unquote(parts.path).casefold()
    wanted = str(page.get("path") or "").casefold()
    mode = page.get("path_mode", "contains")
    if mode == "prefix" and not path.startswith(wanted):
        return False
    if mode == "suffix" and not path.endswith(wanted):
        return False
    if mode not in ("prefix", "suffix") and wanted not in path:
        return False
    if page.get("url_contains") and not _marker_in_url(url, str(page["url_contains"])):
        return False
    if page.get("query_nonempty") and not parts.query.strip():
        return False
    params: dict[str, list[str]] = {}
    for name, value in parse_qsl(parts.query, keep_blank_values=True):
        params.setdefault(name, []).append(value)
    for name, condition in (page.get("query") or {}).items():
        if not _v2_condition(params.get(name, []), condition):
            return False
    if "stay_nights" in page and _v2_nights(params) != page["stay_nights"]:
        return False
    phrases = page.get("text") or []
    if phrases:
        if not (text or "").strip():
            return None
        folded = _fold_v2(text)
        if not all(_phrase_at_boundary(_fold_v2(p), folded) for p in phrases):
            return False
    return True


def _v2_fact_ok(answer: str, fact) -> bool:
    groups, minimum = _v2_alternatives(fact)
    folded = _fold_v2(answer)
    hits = sum(all(_phrase_at_boundary(_fold_v2(item), folded) for item in group) for group in groups)
    return hits >= minimum


def evidence_verdict_v2(
    key: dict,
    trusted: PageEvidence,
    claimed: ClaimedEvidence | None = None,
) -> EvidenceVerdict:
    """PASS, FAIL, or UNKNOWN for a v2 key. Checks run in the documented order."""
    claimed = claimed or ClaimedEvidence()
    live = (trusted.url or "").strip()
    answer = (claimed.answer or "").strip()
    page_text = trusted.text or ""
    if _v2_key_problem(key):
        return EvidenceVerdict(FAIL, "invalid v2 key", live)
    deliverable = key["deliverable"]
    needs_page = deliverable in ("page", "both")
    if not _http(live):
        return EvidenceVerdict(FAIL, "no final page", "")
    if needs_page:
        deny = key.get("deny", list(V2_DEFAULT_DENY))
        hit = _deny_hit(live, deny)
        if hit:
            return EvidenceVerdict(FAIL, f"the page is denied ({hit})", live)
        if is_search_results_url(live) and not key.get("allow_search"):
            return EvidenceVerdict(FAIL, "the page is denied (search)", live)
    if _http(claimed.url) and not _same_page(claimed.url, live):
        return EvidenceVerdict(FAIL, "claimed URL does not match the live page", live)
    if not _host_ok(live, key["host"]):
        return EvidenceVerdict(FAIL, "the final page is on the wrong host", live)
    if not answer:
        return EvidenceVerdict(FAIL, "empty answer", live)
    if _V2_FAILURE.search(_fold_v2(answer)):
        return EvidenceVerdict(FAIL, "answer reports failure", live)
    if len(answer) > 3 * len(key["reference"]) + 300:
        return EvidenceVerdict(FAIL, "answer too long", live)
    if needs_page:
        results = [_v2_page_matches(live, page_text, page) for page in key["pages"]]
        if True not in results:
            if None in results:
                return EvidenceVerdict(UNKNOWN, "page text was not read", live)
            return EvidenceVerdict(FAIL, "the final page is not an accepted page", live)
    if deliverable in ("answer", "both"):
        if not all(_v2_fact_ok(answer, fact) for fact in key["facts"]):
            return EvidenceVerdict(FAIL, "answer misses a required fact", live)
    reason = "the answer matches the key" if deliverable == "answer" else "the final page matches the key"
    problem = _returned_problem(claimed, page_text, live)
    return problem if problem is not None else EvidenceVerdict(PASS, reason, live)


def _v2_task_verdict(task: dict, url: str, text: str, selector_text: str, claim) -> EvidenceVerdict:
    return evidence_verdict_v2(
        task["key_v2"], PageEvidence(url=url, text=text or "", selector_text=selector_text), claim,
    )


def deterministic_success(task: dict, url: str, text: str) -> tuple[bool | None, str]:
    """URL and text checks only. The LLM judge is not called."""
    if task.get("check_url_contains"):
        result = check_url_contains(url, task["check_url_contains"])
        return result.success, result.reason
    if task.get("check_text"):
        result = check_text_present(text, task["check_text"])
        return result.success, result.reason
    return None, "no deterministic check; LLM judge was not called"


def _grade_claim(answer: str, claimed):
    """The claim the shared check sees. A bare answer stays an answer-only claim."""

    if claimed is None:
        return ClaimedEvidence(answer=answer or "")
    if answer and not claimed.answer:
        return ClaimedEvidence(
            url=claimed.url,
            title=claimed.title,
            h1=claimed.h1,
            answer=answer,
            key_text=claimed.key_text,
            values=claimed.values,
            rejected=claimed.rejected,
        )
    return claimed


def _live_return_failure(url: str, text: str, claimed, *, expected_url: str = "") -> str:
    """Why the script's own return is not on the live page. Empty when it is.

    URL, key text, and values are the live-page evidence check. A claim that
    returned none of them leaves the task's own check alone. Title rides along
    on the same object. UNKNOWN is not a failure here.
    """
    if claimed is None:
        return ""
    returned = bool(
        claimed.rejected
        or (claimed.key_text or "").strip()
        or any((item or "").strip() for item in claimed.values)
        or (claimed.url or "").startswith(("http://", "https://"))
    )
    if not returned:
        return ""

    markers = {"url_contains": expected_url} if is_search_results_url(expected_url) else {}
    verdict = evidence_verdict(markers, PageEvidence(url=url, text=text), claimed)
    if verdict.verdict == FAIL:
        return verdict.reason
    return ""


def shared_end_state(
    task: dict,
    url: str,
    text: str,
    *,
    selector_text: str = "",
    answer: str = "",
    page_text: str = "",
    claimed=None,
) -> tuple[bool | None, str]:
    """The one shared check. A missing check is None, which is not a pass.

    URL and text checks use the same strings they always have. A task whose
    end state is the live value of answer_equals_selector, and which has no
    URL or text check, is decided by that read. An empty read is a failure.
    A script return (URL, title, key text, values) is checked against that
    same page. Text that is not on the page fails the check.
    """
    claim = _grade_claim(answer, claimed)
    body = page_text or text
    if isinstance(task.get("key_v2"), dict):
        verdict = _v2_task_verdict(task, url, body, selector_text, claim)
        return verdict.verdict == PASS, verdict.reason
    markers = _task_markers(task)
    checked, reason = deterministic_success(task, url, text)
    if checked is not None:
        if checked is True:
            problem = _live_return_failure(
                url, body, claim,
                expected_url=markers.get("url_contains") or task.get("check_url_contains") or "",
            )
            if problem:
                return False, problem
        return checked, reason
    if not (markers or {}).get("answer_equals_selector"):
        return None, reason

    verdict = evidence_verdict(
        markers,
        PageEvidence(url=url, text=body, selector_text=selector_text),
        claim,
    )
    if verdict.verdict == PASS:
        return True, verdict.reason
    return False, verdict.reason


def grade_arm(
    task: dict,
    url: str,
    text: str,
    *,
    evidence: str | None = None,
    evidence_reason: str = "",
    completed: bool | None = None,
    completion_reason: str = "",
    selector_text: str = "",
    answer: str = "",
    page_text: str = "",
    claimed=None,
) -> tuple[bool, str, bool | None, str]:
    """One rule for every arm. Pass only when the applicable signals agree.

    The shared check must be True. None and False are failures. When the arm
    has an evidence verdict, that verdict must be PASS. UNKNOWN is not a pass.
    `completed` is the harness completion bit for arms that have one. True is
    not a pass by itself. False blocks a pass. None means the arm has no such bit.
    """
    shared_ok, shared_reason = shared_end_state(
        task,
        url,
        text,
        selector_text=selector_text,
        answer=answer,
        page_text=page_text,
        claimed=claimed,
    )
    if shared_ok is not True:
        if shared_ok is None:
            return False, "no shared end-state check", shared_ok, shared_reason
        return False, shared_reason, shared_ok, shared_reason
    if evidence is not None and evidence != "PASS":
        if evidence == "UNKNOWN":
            reason = evidence_reason if evidence_reason.startswith("UNKNOWN") else "UNKNOWN is not success"
            return False, reason, shared_ok, shared_reason
        return False, evidence_reason or "evidence judge did not pass", shared_ok, shared_reason
    if completed is False:
        return False, completion_reason or "the run did not finish", shared_ok, shared_reason
    return True, shared_reason, shared_ok, shared_reason


def grade_observation(
    task: dict,
    url: str,
    text: str,
    *,
    selector_text: str = "",
    answer: str = "",
    completed: bool | None = None,
    completion_reason: str = "",
    claimed=None,
) -> tuple[bool, str, bool | None, str]:
    """The one grade for every arm.

    `text` is the page text read after the run. A task with end markers gets
    one evidence verdict from that read and the full claim. A task with no
    markers gets no marker gate. UNKNOWN is not a pass. TASK_COMPLETE is not
    a pass by itself: `completed` False still blocks, and True does not.
    Runtime verdict gating is applied by the caller, above this page grade.
    """
    claim = _grade_claim(answer, claimed)
    markers = _task_markers(task)
    evidence = None
    evidence_reason = ""
    if isinstance(task.get("key_v2"), dict):
        verdict = _v2_task_verdict(task, url, text, selector_text, claim)
        evidence, evidence_reason = verdict.verdict, verdict.reason
    elif markers:
        verdict = evidence_verdict(
            markers,
            PageEvidence(url=url, text=text or "", selector_text=selector_text),
            claim,
        )
        evidence = verdict.verdict
        evidence_reason = verdict.reason
    return grade_arm(
        task,
        url,
        text or "",
        evidence=evidence,
        evidence_reason=evidence_reason,
        completed=completed,
        completion_reason=completion_reason,
        selector_text=selector_text,
        answer=claim.answer,
        page_text=text or "",
        claimed=claim,
    )


def grade_page_answer(
    task: dict,
    url: str,
    text: str,
    *,
    selector_text: str = "",
    answer: str = "",
    claimed=None,
) -> tuple[bool, str]:
    """Post-run page/answer grade, independent of runtime/completion gating.

    Use the identical marker and shared evidence checks as the final grade.
    This diagnostic must never feed back into the run or its model messages.
    """
    ok, reason, _shared, _shared_reason = grade_observation(
        task, url, text, selector_text=selector_text, answer=answer, claimed=claimed,
    )
    return ok, reason
