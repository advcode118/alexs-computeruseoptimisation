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


def test_navigation_task_on_start_page_answering_its_heading_fails():
    task = "From the Example docs home, open the guide page about widgets."
    page = _page(url=START, title="Example Docs", h1="Example Docs", text="Example Docs\nGuides")
    v = _verdict(task, page, ClaimedEvidence(answer="Example Docs"))
    assert v.verdict == FAIL
    assert "start page" in v.reason


def test_start_page_value_that_is_not_its_heading_passes():
    # "Read the top story" is answered on the start page itself.
    task = "Read the top story on the Example news front page"
    page = _page(url=START, title="Example News", h1="Example News", text="Example News\nFirst story title\nSecond")
    v = _verdict(task, page, ClaimedEvidence(answer="First story title"))
    assert v.verdict == PASS


# Answers taken from the wrong part of a table

TABLE = "Type\tSize\nTINYWIDGET\t1 unit\nMIDWIDGET\t3 units\n\nIn some stores MIDWIDGET and BIGWIDGET take 4 units each."


def test_answer_outside_the_row_the_task_names_fails():
    task = "In the widget manual, open the size table and report how much space a MIDWIDGET needs."
    page = _page(text=TABLE)
    v = _verdict(task, page, ClaimedEvidence(answer="In some stores MIDWIDGET and BIGWIDGET take 4 units each."))
    assert v.verdict == FAIL
    assert "table row for MIDWIDGET" in v.reason


def test_answer_from_the_named_row_passes():
    task = "In the widget manual, open the size table and report how much space a MIDWIDGET needs."
    v = _verdict(task, _page(text=TABLE), ClaimedEvidence(answer="3 units"))
    assert v.verdict == PASS


def test_item_named_in_the_page_title_is_the_subject_not_a_row():
    task = "Open the MIDWIDGET page and report its colour code."
    page = _page(title="MIDWIDGET", h1="MIDWIDGET", text="Name\tMIDWIDGET\nColour\tteal\nSee also: blue")
    v = _verdict(task, page, ClaimedEvidence(answer="teal"))
    assert v.verdict == PASS


def test_row_label_from_the_asked_clause_must_hold_the_answer():
    task = "Open the shopping table and report the total shown at the bottom of the list."
    page = _page(text="Item\tPrice\nApple\t150\nPear\t180\nTotal\t330")
    assert _verdict(task, page, ClaimedEvidence(answer="150")).verdict == FAIL
    assert _verdict(task, page, ClaimedEvidence(answer="330")).verdict == PASS


def test_returned_row_with_a_label_the_task_does_not_name_fails():
    task = "Open the character page and report its encoding in hex."
    page = _page(text="Encoding (hex)\t0xE2 0x98\nEncoding (binary)\t1110 0010")
    v = _verdict(task, page, ClaimedEvidence(answer="Encoding (binary)\t1110 0010"))
    assert v.verdict == FAIL
    assert "labelled Encoding (binary)" in v.reason
    ok = _verdict(task, page, ClaimedEvidence(answer="Encoding (hex)\t0xE2 0x98"))
    assert ok.verdict == PASS


# Headings and fragments


def test_section_heading_returned_as_a_value_fails():
    task = "Open the manual page for the widget command and report the one-line entry under its Name heading."
    page = _page(
        title="widget(1) manual",
        h1="widget(1) manual",
        headings=("widget(1) manual", "Name", "Synopsis", "Description"),
        text="Name\nwidget - build widgets\nSynopsis\nwidget [options]",
    )
    v = _verdict(task, page, ClaimedEvidence(answer="Synopsis"))
    assert v.verdict == FAIL
    assert "heading on the page" in v.reason
    assert _verdict(task, page, ClaimedEvidence(answer="widget - build widgets")).verdict == PASS


def test_heading_is_fine_when_the_task_asks_for_a_heading():
    task = "Open section 9.4 of the widget manual and report its full numbered section heading."
    page = _page(h1="9.4 Widget Parts", headings=("9.4 Widget Parts",), text="9.4 Widget Parts\nA part is ...")
    assert _verdict(task, page, ClaimedEvidence(answer="9.4 Widget Parts")).verdict == PASS


def test_fragment_of_a_longer_value_fails():
    task = "Open the widget types table and report the precision listed for decimal."
    page = _page(text="Type\tRange\tPrecision\ndecimal\t1 to 9\t28-29 digits")
    v = _verdict(task, page, ClaimedEvidence(answer="29 digits"))
    assert v.verdict == FAIL
    assert "part of a longer value" in v.reason
    assert _verdict(task, page, ClaimedEvidence(answer="28-29 digits")).verdict == PASS


def test_headings_stay_out_of_the_model_view():
    from bench.script_first import format_run_result, model_visible_script_result, trusted_from_payload, script_result_payload

    text = format_run_result(ok=True, url=LIVE, step_count=1, text=BODY, headings=["Widgets", "Usage"])
    assert trusted_from_payload(script_result_payload(text)).headings == ("Widgets", "Usage")
    assert '"headings"' not in model_visible_script_result(text)


def test_row_returned_without_its_label_cell_is_judged_on_the_page_row():
    task = "Open the status code registry and report the description listed for status code 451."
    page = _page(text="Value\tDescription\tReference\n450\tBlocked\tRFC 1\n451\tUnavailable For Legal Reasons\tRFC 7725")
    v = _verdict(task, page, ClaimedEvidence(answer="Unavailable For Legal Reasons\tRFC 7725"))
    assert v.verdict == PASS


def test_heading_task_ignores_rows_labelled_by_other_clause_words():
    task = "Open the ebook page for the novel. Report the full main heading, including the author credit."
    page = _page(
        title="Widget Tales by Ada Example",
        h1="Widget Tales by Ada Example",
        text="Widget Tales by Ada Example\nAuthor\tExample, Ada, 1900-1990\nTitle\tWidget Tales",
    )
    v = _verdict(task, page, ClaimedEvidence(answer="Widget Tales by Ada Example"))
    assert v.verdict == PASS


def test_title_answer_must_share_a_word_with_the_document_title():
    task = "Open the abstract page for the widget paper and report the paper title."
    page = _page(title="[1234.5678] Widgets Are All You Need", h1="Computer Science > Language", text="Computer Science > Language\nWidgets Are All You Need")
    v = _verdict(task, page, ClaimedEvidence(answer="Computer Science > Language"))
    assert v.verdict == FAIL
    assert "document title" in v.reason
    assert _verdict(task, page, ClaimedEvidence(answer="Widgets Are All You Need")).verdict == PASS


def test_title_rule_ignores_a_title_named_after_a_comma():
    task = "Open the standard's page and report its status designation, not the document's title."
    page = _page(title="RFC 9999: Widget Transport", text="Status: Internet Standard")
    assert _verdict(task, page, ClaimedEvidence(answer="Internet Standard")).verdict == PASS


def test_search_results_end_page_fails_for_a_value_task():
    task = "Search the archive for the widget paper and report the paper title. Do not stop on the search results."
    page = _page(url="https://docs.example.org/search/?query=widget", title="Search | Example", text="Widget Paper One\nWidget Paper Two")
    v = _verdict(task, page, ClaimedEvidence(answer="Widget Paper One"))
    assert v.verdict == FAIL
    assert "search results page" in v.reason


def test_search_results_page_is_fine_when_the_task_asks_about_results():
    task = "Search the archive for widgets and report how many results it finds."
    page = _page(url="https://docs.example.org/search/?query=widget", text="Showing 1-50 of 812 results")
    assert _verdict(task, page, ClaimedEvidence(answer="812")).verdict == PASS


def test_field_label_answer_fails():
    task = "Submit the form and report the name of the multiline field as the result page echoes it."
    page = _page(text="Comment:\ncomments")
    v = _verdict(task, page, ClaimedEvidence(answer="Comment:"))
    assert v.verdict == FAIL
    assert "field label" in v.reason
