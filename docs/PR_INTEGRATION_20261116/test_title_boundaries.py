"""Synthetic boundary checks, independent of development/held-out task catalogs."""
import pytest

from bench.harness import _clean_url, page_url_from_result
from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict, runtime_verdict

START = "https://cedar.example/"
LIVE = START + "entry"


@pytest.mark.parametrize("url", [
    LIVE + "_(entry)", LIVE + "[entry]", LIVE + "{entry}", LIVE + "_((entry))",
])
def test_balanced_url_roundtrips_through_harness_parser(url):
    assert _clean_url(url + ").") == url
    assert page_url_from_result("- Page URL: " + url) == url


def test_long_key_spacing_is_runtime_only_and_final_grade_stays_strict():
    page = PageEvidence(url=LIVE, title="Entry", text="Alpha beta\ngammadelta epsilon")
    claim = ClaimedEvidence(key_text="Alpha beta gamma delta epsilon")
    assert runtime_verdict(page, claim, start_url=START).verdict == "PASS"
    grade = evidence_verdict({"host": "cedar.example", "url_contains": "/entry"}, page, claim)
    assert grade.verdict == "FAIL"
    assert "returned evidence" in grade.reason


def test_short_key_and_returned_values_keep_exact_matching():
    page = PageEvidence(url=LIVE, title="Entry", text="Alpha beta\ngammadelta epsilon")
    for claim in (
        ClaimedEvidence(key_text="gamma delta"),
        ClaimedEvidence(values=("Alpha beta gamma delta epsilon",)),
        ClaimedEvidence(answer="Alpha beta gamma delta epsilon"),
    ):
        assert runtime_verdict(page, claim, start_url=START).verdict == "FAIL"


def test_site_first_title_accepts_entry_but_rejects_site():
    page = PageEvidence(url=LIVE, title="Cedar - Quiet River", h1="Quiet River", text="Cedar\nQuiet River\nby Pat")
    kwargs = {"start_url": START, "task": "Open the tutorial and report the tutorial's title.", "asks_value": True}
    assert runtime_verdict(page, ClaimedEvidence(answer="Quiet River"), **kwargs).verdict == "PASS"
    assert runtime_verdict(page, ClaimedEvidence(answer="Cedar"), **kwargs).verdict == "FAIL"
