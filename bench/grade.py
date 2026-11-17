"""Frozen, stdlib-only post-run page grader. See docs/GRADER.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

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

    Search-results URLs fail even when the token is in the query.
    """
    if is_search_results_url(current_url):
        return JudgeResult(
            success=False,
            reason=f"URL is a search page: '{current_url}'",
            confidence=1.0,
        )
    if expected.lower() in current_url.lower():
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
        marker = str(answer_in_text) if answer_in_text else (trusted.selector_text or "").strip()
        if len(answer) > 3 * len(marker) + 40:
            return EvidenceVerdict(FAIL, "answer too long", scored)
        candidates = _answer_candidates(answer)
        if selector:
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
        if answer_in_text:
            if not page_text.strip():
                return gate(EvidenceVerdict(UNKNOWN, "page text was not read", scored))
            candidates = tuple(core for core in candidates if _phrase_at_boundary(str(answer_in_text), core))
            if not candidates:
                return EvidenceVerdict(FAIL, "answer does not satisfy the marker", scored)
            candidates = tuple(
                core for core in candidates
                if len(_norm_answer(core)) - len(_norm_answer(marker)) <= max(8, len(_norm_answer(marker)))
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


def _live_return_failure(url: str, text: str, claimed) -> str:
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

    verdict = evidence_verdict({}, PageEvidence(url=url, text=text), claimed)
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
    checked, reason = deterministic_success(task, url, text)
    if checked is not None:
        if checked is True:
            problem = _live_return_failure(url, body, claim)
            if problem:
                return False, problem
        return checked, reason
    markers = task.get("end_markers") if isinstance(task.get("end_markers"), dict) else {}
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
    markers = task.get("end_markers") if isinstance(task.get("end_markers"), dict) else {}
    evidence = None
    evidence_reason = ""
    if markers:
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
