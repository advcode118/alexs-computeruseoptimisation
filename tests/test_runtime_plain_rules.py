"""Plain rules in runtime_verdict: URL answers, title/h1 answers, folded spaces and dashes."""

from __future__ import annotations

from bench.script_first import FAIL, PASS, UNKNOWN, ClaimedEvidence, PageEvidence, runtime_verdict

LIVE = "https://blog.jquery.com/page/2/"
BODY = "Older posts. jQuery 3.7 released. Read more."


def _page(**kw) -> PageEvidence:
    base = {"url": LIVE, "title": "Page 2 - jQuery Blog", "h1": "jQuery Blog", "text": BODY}
    base.update(kw)
    return PageEvidence(**base)


def test_answer_equal_to_live_url_passes():
    v = runtime_verdict(_page(), ClaimedEvidence(answer=LIVE))
    assert v.verdict == PASS
    assert "live page URL" in v.reason


def test_answer_same_page_with_trailing_slash_difference_passes():
    v = runtime_verdict(_page(), ClaimedEvidence(answer=LIVE.rstrip("/")))
    assert v.verdict == PASS


def test_answer_equal_to_canonical_url_passes():
    page = _page(url="https://blog.jquery.com/page/2/?utm=x", canonical=LIVE)
    v = runtime_verdict(page, ClaimedEvidence(answer=LIVE))
    assert v.verdict == PASS


def test_url_answer_for_a_different_page_still_fails():
    v = runtime_verdict(_page(), ClaimedEvidence(answer="https://blog.jquery.com/page/3/"))
    assert v.verdict == FAIL
    assert v.reason == "answer is not in the page text"


def test_url_answer_on_another_host_still_fails():
    v = runtime_verdict(_page(), ClaimedEvidence(answer="https://example.com/page/2/"))
    assert v.verdict == FAIL


def test_answer_in_title_passes():
    v = runtime_verdict(_page(), ClaimedEvidence(answer="Page 2 - jQuery Blog"))
    assert v.verdict == PASS
    assert "title or h1" in v.reason


def test_answer_in_h1_passes():
    page = _page(h1="Pragma statements supported by SQLite", title="SQLite")
    v = runtime_verdict(page, ClaimedEvidence(answer="Pragma statements supported by SQLite"))
    assert v.verdict == PASS


def test_title_answer_with_middle_dot_and_em_dash():
    title = "sqlite3 — DB-API 2.0 interface for SQLite databases"
    page = _page(title=title, h1="", text="Source code: Lib/sqlite3/")
    v = runtime_verdict(page, ClaimedEvidence(answer="sqlite3 - DB-API 2.0 interface for SQLite databases"))
    assert v.verdict == PASS


def test_dash_variants_fold_in_body_text():
    page = _page(text="Results 2020–2024 − summary", title="", h1="")
    v = runtime_verdict(page, ClaimedEvidence(answer="2020-2024 - summary"))
    assert v.verdict == PASS
    assert "dashes fold" in v.reason


def test_non_breaking_space_folds_both_sides():
    page = _page(text="Struct Vec Copy item path", title="", h1="")
    v = runtime_verdict(page, ClaimedEvidence(answer="Struct Vec\xa0Copy item path"))
    assert v.verdict == PASS
    page = _page(text="Struct Vec\xa0Copy item path", title="", h1="")
    v = runtime_verdict(page, ClaimedEvidence(answer="Struct Vec Copy item path"))
    assert v.verdict == PASS


def test_answer_nowhere_still_fails():
    v = runtime_verdict(_page(), ClaimedEvidence(answer="Paris"))
    assert v.verdict == FAIL
    assert v.reason == "answer is not in the page text"


def test_plain_body_match_keeps_old_reason():
    v = runtime_verdict(_page(), ClaimedEvidence(answer="jQuery 3.7 released"))
    assert v.verdict == PASS
    assert v.reason == "the script finished and its evidence is on the live page"


def test_title_answer_still_needs_returned_evidence_on_page():
    v = runtime_verdict(_page(), ClaimedEvidence(answer="jQuery Blog", key_text="not here at all"))
    assert v.verdict == FAIL
    assert v.reason == "returned evidence is not on the page"


def test_no_page_text_and_answer_not_in_title_is_unknown():
    v = runtime_verdict(_page(text=""), ClaimedEvidence(answer="Paris"))
    assert v.verdict == UNKNOWN


def test_title_and_url_rules_do_not_apply_on_the_start_page():
    page = _page(text="Welcome")
    v = runtime_verdict(page, ClaimedEvidence(answer="jQuery Blog"), start_url=LIVE)
    assert v.verdict == FAIL
    v = runtime_verdict(page, ClaimedEvidence(answer=LIVE), start_url=LIVE)
    assert v.verdict == FAIL
