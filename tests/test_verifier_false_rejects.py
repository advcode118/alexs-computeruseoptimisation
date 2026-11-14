"""Hand-written counterexamples, independent of any benchmark task catalog.

Each answer passes the unchanged page/answer grader. The narrowed rules now
accept the fixed ones (CASES and the form/heading cases); the rest still
characterize unresolved false rejects and stay explicit until a supported fix.
"""
from dataclasses import replace

import pytest

from bench.probe import grade_observation, grade_page_answer
from bench.script_first import ClaimedEvidence, EarlierPage, PageEvidence, runtime_verdict

START = "https://fixture.example/"
LIVE = START + "entry"

# rule PR #70 rejected it by, user request, independently correct answer, page title, body
CASES = [
    ("has no digits", "Report how many seats remain.", "none", "Seat inventory", "Seats remaining: none"),
    ("has no digits", "Report the width of the cable.", "two metres", "Cable specifications", "Width: two metres"),
    ("has no digits", "Report the price of admission.", "Free", "Museum admission", "Price: Free"),
    ("has no digits", "Report how much a ticket costs for visitors aged 12.", "12 credits", "Ticket prices", "Ticket price for children: 12 credits"),
    ("has no digits", "Report the name of the author of The Long Year.", "Mara Vale", "Book catalogue", "Author: Mara Vale"),
    ("document title", "Report the title of the first exhibition.", "Summer Light", "Collections Portal", "First exhibition: Summer Light"),
    ("document title", "Report the title of the selected article.", "夜の旅", "Reader Workspace", "Selected article: 夜の旅"),
    ("table row", "Report the entry for the least expensive service.", "Local\t5 credits", "Fare guide", "Service\tFare\nLocal\t5 credits\nExpress\t9 credits"),
    ("table row", "Report the French translation of the word for cat.", "chat", "Language guide", "French\tEnglish\nchat\tcat\nchien\tdog"),
    ("table row for", "Report the colour of the TCP badge in the legend.", "blue", "Network legend", "Protocol\tPort\nTCP\t80\nTCP badge colour: blue"),
]


def marked_task(description):
    return {
        "description": description, "start_url": START,
        "end_markers": {"host": "fixture.example", "answer_equals_selector": ".answer"},
    }


def assert_false_reject(description, answer, page, reason, *, earlier=()):
    claim = ClaimedEvidence(answer=answer)
    task = marked_task(description)
    # The fixture's selector value is recorded independently and stays judge-only.
    good, _ = grade_page_answer(task, page.url, page.text, selector_text=answer, claimed=claim)
    assert good
    verdict = runtime_verdict(page, claim, task=description, start_url=START, asks_value=True, earlier=earlier)
    assert verdict.verdict == "FAIL"
    assert reason in verdict.reason
    final, _, _, _ = grade_observation(
        task, page.url, page.text, selector_text=answer, claimed=claim, run_verdict=verdict.verdict,
    )
    assert final is False
    # Incorrect answers remain incorrect even with a runtime PASS.
    bad, _ = grade_page_answer(task, page.url, page.text, selector_text=answer, answer="Unrelated value")
    assert not bad
    return verdict


def assert_now_accepted(description, answer, page, *, earlier=()):
    claim = ClaimedEvidence(answer=answer)
    task = marked_task(description)
    good, _ = grade_page_answer(task, page.url, page.text, selector_text=answer, claimed=claim)
    assert good
    verdict = runtime_verdict(page, claim, task=description, start_url=START, asks_value=True, earlier=earlier)
    assert verdict.verdict == "PASS", verdict.reason
    final, _, _, _ = grade_observation(
        task, page.url, page.text, selector_text=answer, claimed=claim, run_verdict=verdict.verdict,
    )
    assert final is True
    # Incorrect answers remain incorrect.
    bad, _ = grade_page_answer(task, page.url, page.text, selector_text=answer, answer="Unrelated value")
    assert not bad


@pytest.mark.parametrize("reason,description,answer,title,body", CASES)
def test_former_false_reject_is_now_accepted(reason, description, answer, title, body):
    assert_now_accepted(description, answer, PageEvidence(url=LIVE, title=title, text=body))


def test_repeated_confirmation_after_retry_is_now_accepted():
    # The earlier stopped script had already left the start page, so it may have submitted.
    body = "Your request was received.\nNew reference: BQ-72"
    assert_now_accepted(
        "Submit the revised request and report the confirmation message.",
        "Your request was received.", PageEvidence(url=LIVE, title="Request desk", text=body),
        earlier=(EarlierPage(url=LIVE, text="Your request was received.\nOld reference: BQ-71", stopped=True),),
    )


def test_initial_page_heading_is_accepted_when_the_task_asks_for_no_move():
    assert_now_accepted(
        "Report the main heading on the current page.", "Cedar Observatory",
        PageEvidence(url=START, title="Cedar Observatory", h1="Cedar Observatory", text="Cedar Observatory\nVisitor guide"),
    )


def test_digitless_quantity_outside_the_number_words_is_still_rejected():
    assert_false_reject(
        "Report the price of admission.", "Complimentary",
        PageEvidence(url=LIVE, title="Admission", text="Price: Complimentary"), "has no digits",
    )


def test_same_url_spa_can_complete_navigation():
    page = PageEvidence(url=START, title="Library", text="Library\nSelected chapter: Safety\nWear eye protection")
    description = "Open the safety chapter in this reader."
    claim = ClaimedEvidence(key_text="Wear eye protection")
    task = {"description": description, "check_text": "Selected chapter: Safety"}
    assert grade_page_answer(task, START, page.text, claimed=claim)[0]
    verdict = runtime_verdict(page, claim, start_url=START, task=description)
    assert verdict.verdict == "FAIL"
    assert "start page" in verdict.reason
    assert not grade_observation(task, START, page.text, claimed=claim, run_verdict=verdict.verdict)[0]


def test_report_measures_a_real_runtime_false_reject():
    from bench.heldout3_report import build_report

    description = "Report the price of admission."
    page = PageEvidence(url=LIVE, title="Admission", text="Price: Complimentary")
    task = marked_task(description)
    rows = []
    # One ordinary true accept plus one concrete quantity-digit false reject.
    for answer, body in [("8 credits", "Price: 8 credits"), ("Complimentary", page.text)]:
        current = replace(page, text=body)
        claim = ClaimedEvidence(answer=answer)
        verdict = runtime_verdict(current, claim, start_url=START, task=description, asks_value=True)
        page_ok, _ = grade_page_answer(task, LIVE, body, selector_text=answer, claimed=claim)
        final, _, _, _ = grade_observation(task, LIVE, body, selector_text=answer, claimed=claim, run_verdict=verdict.verdict)
        rows.append([
            {"arm": "script_first", "task_id": "fixture", "model": "offline", "success": final,
             "end_state": verdict.verdict, "page_answer_success": page_ok},
            {"arm": "browser_use", "task_id": "fixture", "model": "offline", "success": True},
        ])
    report = build_report(rows, sites={}, n_resamples=20)
    block = report["models"]["offline"]
    assert block["pass_rate"]["script_first"]["estimate"] == 0.5
    assert block["self_check"]["recall"]["estimate"] == 0.5
    assert block["self_check"]["false_rejects"] == 1
