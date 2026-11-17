"""Arm-neutral, key-driven grading extensions; no live pages or model calls."""

import pytest

from bench import grade, probe
from bench.browser_use_arm import _judge


URL = "https://example.org/stats"
PARTS = ["Stephen Curry", "Russell Westbrook", "Clint Capela"]
FULL = "Points: Stephen Curry; Assists: Russell Westbrook; Rebounds: Clint Capela"
PAGE = "Stephen Curry\n32.0\nRussell Westbrook\n11.7\nClint Capela\n14.3"
TASK = {
    "check_url_contains": "/stats",
    "end_markers": {"host": "example.org", "url_contains": "/stats", "answer_in_text": "Russell Westbrook"},
    "full_answer": FULL,
    "answer_parts": PARTS,
}


def result(task=TASK, answer=FULL, text=PAGE, url=URL, **kwargs):
    return grade.grade_observation(task, url, text, answer=answer, **kwargs)


def test_full_list_parts_pass_without_one_contiguous_page_span():
    assert grade._norm_answer(FULL) not in grade._norm_answer(PAGE)
    assert result()[0] is True
    assert result(answer=f'**"{FULL}"**.')[0] is True
    markers = {**TASK["end_markers"], "full_answer": FULL, "answer_parts": PARTS}
    assert grade.evidence_verdict(markers, grade.PageEvidence(url=URL, text=PAGE),
                                  grade.ClaimedEvidence(answer=FULL)).verdict == grade.PASS


@pytest.mark.parametrize("answer", ["", FULL.replace("Stephen Curry", ""), FULL.replace("Clint Capela", "Clint CapelaX")])
def test_missing_or_nonboundary_part_fails(answer):
    assert result(answer=answer)[0] is False


def test_marker_is_required_even_when_omitted_from_parts_key():
    task = {**TASK, "answer_parts": ["Stephen Curry", "Clint Capela"]}
    assert result(task, answer="Stephen Curry; Clint Capela")[0] is False
    assert result(task)[0] is True


def test_each_part_must_be_grounded_individually():
    assert result(text=PAGE.replace("Clint Capela", "Other player"))[1] == "answer part is not in the page text"
    assert result(text=PAGE.replace("Clint Capela", "Clint CapelaX"))[0] is False
    assert result(text="")[1] == "UNKNOWN is not success"


@pytest.mark.parametrize("parts", ["Stephen Curry", [""], [1]])
def test_malformed_parts_fail_closed(parts):
    assert result({**TASK, "answer_parts": parts})[1] == "invalid answer parts key"


def test_empty_parts_still_require_marker_or_fail_closed():
    task = {**TASK, "answer_parts": []}
    assert result(task, answer="Russell Westbrook")[0] is True
    assert result({"check_url_contains": "/stats", "answer_parts": []}, answer="anything")[1] == "empty answer parts key"


def test_full_reference_changes_both_bounds_without_parts():
    answer = "Russell Westbrook " + "x" * 90
    task = {"check_url_contains": "/stats", "end_markers": TASK["end_markers"]}
    assert result(task, answer=answer, text=answer)[1] == "answer too long"
    assert result({**task, "full_answer": answer}, answer=answer, text=answer)[0] is True
    shorter = "Russell Westbrook " + "x" * 40
    assert len(shorter) < 3 * len("Russell Westbrook") + 40
    assert result(task, answer=shorter, text=shorter)[1] == "answer too long"
    assert result({**task, "full_answer": shorter}, answer=shorter, text=shorter)[0] is True


def test_full_reference_does_not_remove_span_grounding_without_parts():
    task = {k: v for k, v in TASK.items() if k != "answer_parts"}
    assert result(task)[1] == "answer is not in the page text"


def test_raw_over_full_bound_and_whole_page_dump_fail():
    overlong = FULL + "x" * (2 * len(FULL) + 41)
    assert result(answer=overlong, text=overlong)[1] == "answer too long"
    dump = FULL + "\nUnrelated page navigation and promotions. " * 30
    assert result(answer=dump, text=dump)[1] == "answer too long"


def test_normalized_excess_uses_full_reference_in_parts_mode():
    expanded = FULL + " extra" * 15
    assert len(expanded) < 3 * len(FULL) + 40
    assert result(answer=expanded, text=expanded)[1] == "answer too long"


def test_legacy_parts_without_full_reference_keep_marker_bound():
    task = {k: v for k, v in TASK.items() if k != "full_answer"}
    answer = FULL + " more details" * 3
    assert result(task, answer=answer, text=answer)[1] == "answer too long"


@pytest.mark.parametrize("wrapper", ["{}", '"{}"', "<{}>", "`{}`", "[Schedule]({})", "'{}'."])
def test_url_answer_opt_in_and_light_wrappers(wrapper):
    task = {"check_url_contains": "/stats", "end_markers": TASK["end_markers"], "url_answer_ok": True}
    assert result(task, answer=wrapper.format(URL), text="")[0] is True
    assert result({**task, "url_answer_ok": False}, answer=wrapper.format(URL))[0] is False


@pytest.mark.parametrize("answer", ["https://example.org/wrong", "https://evil.test/stats", "Opened " + URL,
                                  "[Schedule](https://example.org/wrong)"])
def test_url_answer_rejects_wrong_target_or_surrounding_prose(answer):
    task = {**TASK, "url_answer_ok": True}
    assert result(task, answer=answer)[0] is False


def test_url_answer_requires_live_target_and_preserves_claim_checks():
    task = {**TASK, "url_answer_ok": True}
    assert result(task, answer=URL, url="https://example.org/wrong")[0] is False
    claim = grade.ClaimedEvidence(answer=URL, key_text="Invented evidence")
    assert result(task, answer=URL, claimed=claim)[1] == "returned evidence is not on the page"
    assert result({"end_markers": {"host": "example.org"}, "url_answer_ok": True}, answer=URL)[0] is False
    assert result({"check_url_contains": "/stats", "url_answer_ok": True}, answer=URL)[0] is True


def test_url_answer_checks_suffix_and_query_and_can_return_normal_text():
    task = {"check_url_contains": "/stats", "url_answer_ok": True,
            "end_markers": {**TASK["end_markers"], "path_suffix": "/stats", "query_nonempty": True}}
    assert result(task, answer=URL + "?page=1", url=URL + "?page=2")[0] is True
    assert result(task, answer=URL, url=URL + "?page=2")[0] is False
    assert result(task, answer=URL + "/other?page=1", url=URL + "?page=2")[0] is False
    assert result({**TASK, "url_answer_ok": True})[0] is True


@pytest.mark.parametrize("actual,ok", [
    ("/events?page=1&end_date=2027-07-31&start_date=2027-07-10", True),
    ("/events?start_date=2027-07-11&end_date=2027-07-31", False),
    ("/events?start_date=2027-07-10", False),
    ("/other?start_date=2027-07-10&end_date=2027-07-31", False),
])
def test_query_subset_in_both_url_checkers(actual, ok):
    expected = "/events?start_date=2027-07-10&end_date=2027-07-31"
    live = "https://example.org" + actual
    assert grade.check_url_contains(live, expected).success is ok
    task = {"check_url_contains": expected,
            "end_markers": {"host": "example.org", "url_contains": expected, "answer_in_text": "Events"}}
    assert grade.evidence_verdict(task["end_markers"], grade.PageEvidence(url=live, text="Events"),
                                  grade.ClaimedEvidence(answer="Events")).verdict == (grade.PASS if ok else grade.FAIL)
    assert result(task, answer="Events", text="Events", url=live)[0] is ok


@pytest.mark.parametrize("actual,ok", [
    ("/stats?name=Alice+Smith&tag=a&tag=a&empty=", True),
    ("/stats?name=Alice%20Smith&tag=a&tag=a&empty=", True),
    ("/stats?name=alice+Smith&tag=a&tag=a&empty=", False),
    ("/stats?name=Alice+Smith&tag=a&empty=", False),
    ("/stats?name=Alice+Smith&tag=a&tag=a", False),
])
def test_query_values_decode_but_keep_case_blank_and_duplicate_requirements(actual, ok):
    expected = "/stats?tag=a&name=Alice%20Smith&tag=a&empty="
    url = "https://example.org" + actual
    assert grade.check_url_contains(url, expected).success is ok
    assert grade._url_matches(url, {"url_contains": expected}) is ok


@pytest.mark.parametrize("path", ["/search?q=Peru", "/search.html?q=Peru", "/wiki/Special:Search?search=Peru",
                                 "/index.php?search=Peru"])
def test_explicit_search_target_passes_even_with_script_claim(path):
    url = "https://example.org" + path
    task = {"check_url_contains": path, "end_markers": {"host": "example.org", "url_contains": path,
                                                         "answer_in_text": "Peru"}}
    assert result(task, answer="Peru", text="Peru", url=url)[0] is True
    claim = grade.ClaimedEvidence(url=url, answer="Peru", key_text="Peru")
    assert result(task, answer="Peru", text="Peru", url=url, claimed=claim)[0] is True
    assert result({**task, "url_answer_ok": True}, answer=url, url=url)[0] is True
    assert grade.check_url_contains(url, path).success is True


def test_search_exception_is_key_driven_not_a_global_allow():
    detail = {"check_url_contains": "/press/news", "end_markers": {"host": "example.org", "url_contains": "/press/news", "answer_in_text": "Peru"}}
    live = "https://example.org/search?q=Peru"
    assert result(detail, answer="Peru", text="Peru", url=live)[1].startswith("URL is a search page")
    task = {"check_url_contains": "/search?q=Peru", "end_markers": {"url_contains": "/search?q=Peru", "deny": ["/search"]}}
    assert result(task, url=live)[0] is False
    assert result({"check_url_contains": "/search?q=Peru"}, url=live)[0] is True


@pytest.mark.parametrize("arm", ["script_first", "cascade", "browser_use", "playwright_mcp"])
def test_key_extensions_are_arm_neutral(arm):
    task = {**TASK, "arm": arm}
    assert probe.grade_observation(task, URL, PAGE, answer=FULL, run_verdict="PASS")[0] is True
    assert _judge(task, URL, PAGE, answer=FULL)[0] is True
    assert result(task, answer=FULL.replace("Clint Capela", "Other"))[0] is False
