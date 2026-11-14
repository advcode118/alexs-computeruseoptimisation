"""Precision checks in script_first's runtime self-check.

Each check reads only the task text, the live page and the script's claim.
None of these pages or tasks is a benchmark task.
"""

from __future__ import annotations

import json

from bench.script_first import (
    FAIL,
    PASS,
    ClaimedEvidence,
    PageEvidence,
    precision_problem,
    runtime_verdict,
    script_runtime_verdict,
    task_asks_value,
)

START = "https://docs.example.org/"
LIVE = "https://docs.example.org/guide/widgets.html"
BODY = "Widgets\nA widget holds parts. Maximum load: 12 kg. Released 2019-04-02.\nVersion 2.4.1"


def _page(**kw) -> PageEvidence:
    base = {"url": LIVE, "title": "Widgets - Example Docs", "h1": "Widgets", "text": BODY}
    base.update(kw)
    return PageEvidence(**base)


def _verdict(task: str, page: PageEvidence, claim: ClaimedEvidence, start: str = START):
    return runtime_verdict(page, claim, start_url=start, asks_value=task_asks_value(task), task=task)


# Error pages


def test_404_title_fails_even_when_key_text_is_on_the_page():
    task = "From the Example docs home, open the guide page about widgets."
    page = _page(title="404 - Content not found", h1="Page not found", text="Page not found. Widgets")
    v = _verdict(task, page, ClaimedEvidence(key_text="Widgets"))
    assert v.verdict == FAIL
    assert "error page" in v.reason


def test_not_found_h1_alone_fails():
    task = "From the Example docs home, open the guide page about widgets."
    v = _verdict(task, _page(h1="Not Found", text="Not Found Widgets"), ClaimedEvidence(key_text="Widgets"))
    assert v.verdict == FAIL


def test_title_that_mentions_an_error_class_still_passes():
    task = "From the Example docs home, open the reference page for FileNotFoundError."
    page = _page(title="FileNotFoundError - Example Docs", h1="FileNotFoundError", text="FileNotFoundError is raised")
    v = _verdict(task, page, ClaimedEvidence(key_text="FileNotFoundError is raised"))
    assert v.verdict == PASS


# Navigation task still on the start page


def test_navigation_task_on_start_page_fails_even_with_key_text():
    task = "From the Example docs home, open the guide page about widgets."
    page = _page(url=START, title="Example Docs", h1="Example Docs", text="Example Docs\nGuides\nWidgets")
    v = _verdict(task, page, ClaimedEvidence(key_text="Example Docs"))
    assert v.verdict == FAIL
    assert "start page" in v.reason


def test_value_task_may_answer_on_the_start_page():
    task = "On the Example docs home, report the maximum load of a widget."
    page = _page(url=START)
    v = _verdict(task, page, ClaimedEvidence(answer="12 kg"))
    assert v.verdict == PASS


def test_navigation_task_that_moved_passes():
    task = "From the Example docs home, open the guide page about widgets."
    v = _verdict(task, _page(), ClaimedEvidence(key_text="A widget holds parts."))
    assert v.verdict == PASS


# Answer that only repeats the task


def test_answer_that_repeats_the_task_words_fails():
    task = "On the Example docs, open the widgets guide and report the maximum load of a Heavy Widget."
    page = _page(text=BODY + "\nHeavy Widget")
    v = _verdict(task, page, ClaimedEvidence(answer="Heavy Widget"))
    assert v.verdict == FAIL
    assert "repeats words from the task" in v.reason


def test_site_name_answer_to_a_title_question_fails():
    task = "On Example Docs, open the widgets guide and report the entry's title."
    page = _page(h1="Example Docs", text="Example Docs\n" + BODY)
    v = _verdict(task, page, ClaimedEvidence(answer="Example Docs"))
    assert v.verdict == FAIL


def test_named_item_on_a_find_only_task_still_passes():
    # "find the package named X" asks for no reported value: echoing X is fine.
    task = "Use the package search to find the package named widgets and open its package page."
    page = _page(h1="widgets", text="widgets\n" + BODY)
    v = _verdict(task, page, ClaimedEvidence(answer="widgets"))
    assert v.verdict == PASS


def test_answer_with_extra_words_beyond_the_task_passes():
    task = "Fill in the form with the name Alex Example, submit it, and report the name line shown."
    page = _page(text="Name:Alex Example\nEmail:alex@example.com")
    v = _verdict(task, page, ClaimedEvidence(answer="Name:Alex Example"))
    assert v.verdict == PASS


# Quantity questions need a digit


def test_quantity_question_answered_without_digits_fails():
    task = "On the Example docs, open the widgets guide and report the total shown at the bottom."
    page = _page(text=BODY + "\nTotal 858\nThe total is correct")
    v = _verdict(task, page, ClaimedEvidence(answer="The total is correct"))
    assert v.verdict == FAIL
    assert "has no digits" in v.reason


def test_quantity_question_with_digits_passes():
    task = "On the Example docs, open the widgets guide and report the release date of widgets."
    v = _verdict(task, _page(), ClaimedEvidence(answer="2019-04-02"))
    assert v.verdict == PASS


def test_quantity_word_before_the_ask_clause_is_ignored():
    # "mobile number" is input, the asked value is a message without digits.
    task = "Fill in the form with mobile number 0123456789. Submit it and report the confirmation message."
    page = _page(text="Thanks for submitting the form")
    v = _verdict(task, page, ClaimedEvidence(answer="Thanks for submitting the form"))
    assert v.verdict == PASS


def test_non_quantity_question_without_digits_passes():
    task = "On the Example docs, open the widgets guide and report the name of the widget's author."
    page = _page(text=BODY + "\nAuthor: Ada Example")
    v = _verdict(task, page, ClaimedEvidence(answer="Ada Example"))
    assert v.verdict == PASS


# Wiring


def test_checks_are_off_without_task_text():
    page = _page(url=START, title="404 Not Found", text="Not Found")
    v = runtime_verdict(page, ClaimedEvidence(key_text="Not Found"), start_url=START)
    assert v.verdict == PASS


def test_precision_problem_is_empty_for_a_good_run():
    task = "On the Example docs, open the widgets guide and report its version."
    assert precision_problem(_page(), ClaimedEvidence(answer="2.4.1"), task=task, start_url=START, asks_value=True) == ""


def test_script_runtime_verdict_passes_task_through():
    task = "From the Example docs home, open the guide page about widgets."
    payload = {"ok": True, "url": START, "title": "Example Docs", "text": "Example Docs", "claimed": {"key_text": "Example Docs"}}
    v, _ = script_runtime_verdict(json.dumps(payload), START, START, asks_value=False, task=task)
    assert v.verdict == FAIL
    assert "start page" in v.reason


# Task shape


def test_find_and_open_is_a_navigation_task():
    assert not task_asks_value("Use the package search to find the package named widgets and open its package page.")
    assert task_asks_value("Use the package search to find the package named widgets and report its version.")
    assert task_asks_value("Find the latest version of widgets.")
