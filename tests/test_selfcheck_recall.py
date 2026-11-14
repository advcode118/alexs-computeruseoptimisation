"""Recall of script_first's narrowed precision rules.

Each rule that was narrowed gets a correct answer it used to reject and now
accepts, next to the wrong answer it still has to catch. Fictional pages only;
none of these is a benchmark task.
"""

from __future__ import annotations

import json

from bench.script_first import (
    FAIL,
    PASS,
    ClaimedEvidence,
    PageEvidence,
    precision_hits,
    runtime_verdict,
    script_runtime_verdict,
    task_asks_value,
)

START = "https://docs.example.org/"
LIVE = "https://docs.example.org/guide/widgets.html"


def _page(**kw) -> PageEvidence:
    base = {"url": LIVE, "title": "Widgets - Example Docs", "h1": "Widgets", "text": "Widgets"}
    base.update(kw)
    return PageEvidence(**base)


def _verdict(task: str, page: PageEvidence, answer: str, start: str = START):
    return runtime_verdict(
        page, ClaimedEvidence(answer=answer), start_url=start, asks_value=task_asks_value(task), task=task
    )


def _rules(task: str, page: PageEvidence, answer: str, start: str = START) -> list[str]:
    hits = precision_hits(
        page, ClaimedEvidence(answer=answer), task=task, start_url=start, asks_value=task_asks_value(task)
    )
    return [name for name, _ in hits]


# quantity_digit: a number word or a digit beside new words is a quantity of its own.


def test_quantity_in_words_passes_and_prose_still_fails():
    task = "Open the widgets guide and report how many spare parts come in the box."
    page = _page(text="Spare parts: three\nEvery widget ships in a sturdy box with a manual.")
    assert _verdict(task, page, "three").verdict == PASS
    v = _verdict(task, page, "Every widget ships in a sturdy box with a manual.")
    assert v.verdict == FAIL
    assert "has no digits" in v.reason


def test_shared_digit_with_new_words_passes_and_a_bare_echoed_digit_still_fails():
    task = "Open the price list and report the price for groups of 12."
    page = _page(text="Groups of 12: 40 credits\nGroups of 20: 60 credits\nGroup size 12")
    assert _verdict(task, page, "40 credits").verdict == PASS
    page = _page(text="Groups of 12\nPrice: 12 credits")
    assert _verdict(task, page, "12 credits").verdict == PASS
    assert "quantity_digit" in _rules(task, _page(text="Group size 12"), "12")


def test_quantity_noun_outside_the_asked_object_is_ignored():
    task = "Open the catalogue and report the name of the author of The Long Year."
    assert "quantity_digit" not in _rules(task, _page(text="Author: Mara Vale"), "Mara Vale")
    task = "Open the catalogue and report the year The Long Year was published."
    assert "quantity_digit" in _rules(task, _page(text="Published: last spring"), "last spring")


# title_overlap: only a breadcrumb-shaped answer.


def test_title_rule_fires_only_on_a_breadcrumb_answer():
    task = "Open the collection and report the title of the first exhibition."
    page = _page(title="Collections Portal", text="Home > Exhibitions\nFirst exhibition: Summer Light")
    assert _verdict(task, page, "Summer Light").verdict == PASS
    v = _verdict(task, page, "Home > Exhibitions")
    assert v.verdict == FAIL
    assert "document title" in v.reason


# form_seen_before: only when the earlier stopped script was still on the start page.


def test_confirmation_seen_by_a_stopped_script_off_the_start_page_passes():
    task = "Complete the booking form and report the confirmation heading."
    done = "https://docs.example.org/confirm"
    earlier = ({"ok": False, "url": done, "text": "Booking received", "error": "timeout"},)
    payload = {"ok": True, "url": done, "title": "Confirm", "text": "Booking received", "claimed": {"answer": "Booking received"}}
    v, _ = script_runtime_verdict(json.dumps(payload), done, START, asks_value=True, task=task, earlier=earlier)
    assert v.verdict == PASS
    # On the start page the same history still fails.
    earlier = ({"ok": False, "url": START, "text": "Book now\nBooking received", "error": "timeout"},)
    payload = dict(payload, url=START, text="Book now\nBooking received")
    v, _ = script_runtime_verdict(json.dumps(payload), START, START, asks_value=True, task=task, earlier=earlier)
    assert v.verdict == FAIL
    assert "before the form was submitted" in v.reason


# start_heading: only when the task asks the run to move or act first.


def test_start_heading_rule_needs_a_task_that_moves():
    page = _page(url=START, title="Example Docs", h1="Example Docs", text="Example Docs\nGuides")
    assert _verdict("Report the main heading of this page.", page, "Example Docs").verdict == PASS
    v = _verdict("Open the widgets guide and report the heading it shows.", page, "Example Docs")
    assert v.verdict == FAIL
    assert "start page" in v.reason


# wrong_row: only when another data row is labelled with the task's words.


def test_relational_row_choice_passes_and_a_named_wrong_row_still_fails():
    task = "Open the fare guide and report the entry for the cheapest service."
    page = _page(text="Service\tFare\nLocal\t5 credits\nExpress\t9 credits")
    assert _verdict(task, page, "Local\t5 credits").verdict == PASS
    task = "Open the character page and report its encoding in hex."
    page = _page(text="Encoding (hex)\t0xE2 0x98\nEncoding (binary)\t1110 0010")
    assert "wrong_row" in _rules(task, page, "Encoding (binary)\t1110 0010")


# item_row: header rows are not data rows, and the answer needs positive off-row evidence.


def test_header_of_a_table_printed_after_another_table_is_not_a_data_row():
    task = "Open the record types registry and report the mnemonic in the CODE column for value 28."
    text = "Earlier table\n65535\t0xFFFF\tReserved\t\nCODE\tValue\tMeaning\tReference\nAAAA\t28\tIPv6 address\tRFC 3596"
    assert _verdict(task, _page(text=text), "AAAA").verdict == PASS


def test_answer_from_a_legend_beside_a_table_passes_but_another_row_cell_fails():
    task = "Open the network page and report the port of the HTTPX row."
    text = "Name\tPort\nHTTPX\t80\nSMTPX\t25\nLegend: badges are blue"
    assert _verdict("Open the network page and report the badge colour for HTTPX.", _page(text=text), "blue").verdict == PASS
    v = _verdict(task, _page(text=text), "25")
    assert v.verdict == FAIL
    assert "table row for HTTPX" in v.reason


# token_fragment: one value only.


def test_multi_line_block_is_not_judged_as_a_fragment():
    task = "Open the colour list and report the hex value listed for Teal."
    text = "Tan\t#D2B48C\nTeal\t#008080\nThistle\t#D8BFD8\nTomato"
    answer = "Teal\n#008080\nThistle\n#D8BFD8\nTom"
    assert "token_fragment" not in _rules(task, _page(text=text), answer)
    assert "token_fragment" in _rules(task, _page(text="Teal is #008080"), "0080")


def test_long_cut_sentence_holding_the_value_is_not_judged_as_a_fragment():
    task = "Open the telescope page and report the diameter of the small telescopes."
    text = "four main telescopes of 8.2m diameter and four small 1.8m diameter telescopes. They can work together."
    answer = "diameter and four small 1.8m diameter telescopes. They ca"
    assert "token_fragment" not in _rules(task, _page(text=text), answer)
    assert "token_fragment" not in _rules(task, _page(text="Teal\t#008080\t12 bytes"), "08080\t12")


# error_page: a page about the error the task names.


def test_page_about_the_named_error_code_passes():
    task = "Open the reference page for HTTP status 404 and report its short description."
    page = _page(title="404 Not Found - HTTP reference", h1="404 Not Found", text="404 Not Found\nThe server cannot find the resource.")
    assert _verdict(task, page, "The server cannot find the resource.").verdict == PASS
    task = "Open the reference page for the widget method and report its short description."
    assert _verdict(task, _page(title="404 - not found", text="Widgets moved."), "Widgets moved.").verdict == FAIL


# task_echo: an option the task offers is a real answer.


def test_choice_option_from_the_task_passes_and_a_plain_echo_still_fails():
    page = _page(text="Heavy Widget: 12 kg\nLight Widget: 3 kg\nHeavier: Heavy Widget")
    task = "Open the widgets guide. Which is heavier, the Light Widget or the Heavy Widget?"
    assert _verdict(task, page, "Heavy Widget").verdict == PASS
    task = "Open the widgets guide and report the maximum load of a Heavy Widget."
    assert "task_echo" in _rules(task, page, "Heavy Widget")


# heading_value: a section-type object is answered by a heading.


def test_section_heading_answers_a_which_section_question():
    page = _page(headings=("Widgets", "Installation", "Safety"), text="Installation\nUnpack it.\nSafety\nWear gloves.")
    task = "Open the widgets guide and report which section covers gloves."
    assert _verdict(task, page, "Safety").verdict == PASS
    task = "Open the widgets guide and report the advice given about gloves."
    assert "heading_value" in _rules(task, page, "Safety")


# site_name: the publisher can be the site itself.


def test_site_name_answers_a_publisher_question():
    page = _page(title="Widget handbook - ExampleDocs", text="ExampleDocs\nWidget handbook\nPublished by ExampleDocs")
    assert _verdict("Open the widget handbook and report its publisher.", page, "ExampleDocs").verdict == PASS
    assert "site_name" in _rules("Open the widget handbook and report its subtitle.", page, "ExampleDocs")
