"""An empty answer fails the live check only when the task asks for a value.

The rule reads the task description. It does not read markers or the expected
answer. The corpus check is offline: no browser, no network, no model call.
"""

from __future__ import annotations

from bench.script_first import (
    FAIL,
    PASS,
    ClaimedEvidence,
    PageEvidence,
    format_run_result,
    runtime_verdict,
    script_runtime_verdict,
    task_asks_value,
)
from bench.tasks import get_all_tasks

LIVE = "https://example.com/item"
BODY = "Visible heading and more."


def _page(**kw) -> PageEvidence:
    base = {"url": LIVE, "title": "Example", "h1": "Example", "text": BODY}
    base.update(kw)
    return PageEvidence(**base)


def _empty_claim() -> ClaimedEvidence:
    return ClaimedEvidence(answer="", key_text="Visible heading")


def test_empty_answer_fails_when_the_task_asks_for_a_value():
    verdict = runtime_verdict(_page(), _empty_claim(), asks_value=True)
    assert verdict.verdict == FAIL
    assert verdict.reason == "the task asks for a value and the script returned no answer"


def test_whitespace_answer_fails_when_the_task_asks_for_a_value():
    claim = ClaimedEvidence(answer=" \n\t ", key_text="Visible heading")
    verdict = runtime_verdict(_page(), claim, asks_value=True)
    assert verdict.verdict == FAIL
    assert verdict.reason == "the task asks for a value and the script returned no answer"


def test_empty_answer_keeps_the_old_pass_when_the_task_does_not_ask_for_a_value():
    verdict = runtime_verdict(_page(), _empty_claim(), asks_value=False)
    assert verdict.verdict == PASS
    assert verdict.reason == "the script finished and its evidence is on the live page"


def test_empty_answer_with_nothing_returned_keeps_the_old_fail():
    verdict = runtime_verdict(_page(), ClaimedEvidence(answer=""))
    assert verdict.verdict == FAIL
    assert verdict.reason == "the script returned no answer or key_text"


def test_nonempty_answer_is_unchanged_when_the_task_asks_for_a_value():
    passed = runtime_verdict(_page(), ClaimedEvidence(answer="Visible heading"), asks_value=True)
    assert passed.verdict == PASS
    assert passed.reason == "the script finished and its evidence is on the live page"
    missed = runtime_verdict(_page(), ClaimedEvidence(answer="Paris"), asks_value=True)
    assert missed.verdict == FAIL
    assert missed.reason == "answer is not in the page text"


def test_script_runtime_verdict_forwards_asks_value():
    text = format_run_result(
        ok=True,
        url=LIVE,
        step_count=1,
        title="Example",
        text=BODY,
        claimed={"answer": "  ", "key_text": "Visible heading"},
    )
    failed, _payload = script_runtime_verdict(text, LIVE, asks_value=True)
    assert failed.verdict == FAIL
    assert failed.reason == "the task asks for a value and the script returned no answer"
    kept, _payload = script_runtime_verdict(text, LIVE, asks_value=False)
    assert kept.verdict == PASS


def test_task_asks_value_reads_the_wording_only():
    assert task_asks_value("Report the city it stands in")
    assert task_asks_value("What is the status code?")
    assert task_asks_value("How many downloads did it get")
    assert task_asks_value("Which symbol is listed?")
    assert task_asks_value("Give the exact title")
    assert task_asks_value("Tell me the author")
    assert task_asks_value("Name the field")
    assert task_asks_value("State the port")
    assert task_asks_value("Identify the title of the top story")
    assert task_asks_value("Find the year it was first released")
    assert task_asks_value("Find its weekly download count")
    assert not task_asks_value("Find the page about the heapq module")
    assert not task_asks_value("Find the article for Ada Lovelace")
    assert not task_asks_value("Open the page for the VACUUM statement.")
    assert not task_asks_value("Go to the docs and navigate to the main article")
    assert not task_asks_value("")
    assert not task_asks_value("   ")


def _is_url(text: str) -> bool:
    value = text.strip()
    lowered = value.casefold()
    return lowered.startswith(("http://", "https://", "file://")) or "://" in lowered


def _ground_truth(task: dict) -> bool:
    """end_markers has answer_in_text, or the expected answer is not a URL."""
    markers = task.get("end_markers") or {}
    if str(markers.get("answer_in_text") or "").strip():
        return True
    expected = str(task.get("expected_answer") or "").strip()
    return bool(expected) and not _is_url(expected)


def _navigation_only(task: dict) -> bool:
    """A page to land on, with no text answer in the markers."""
    markers = task.get("end_markers") or {}
    if str(markers.get("answer_in_text") or "").strip():
        return False
    expected = str(task.get("expected_answer") or "").strip().casefold()
    return expected.startswith(("on the ", "on a ", "viewing "))


def test_task_asks_value_precision_on_every_task():
    tasks = get_all_tasks()
    assert tasks
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    false_positives = []
    for task in tasks:
        predicted = task_asks_value(task["description"])
        actual = _ground_truth(task)
        if predicted and actual:
            counts["tp"] += 1
        elif predicted and not actual:
            counts["fp"] += 1
            false_positives.append(task["id"])
        elif not predicted and actual:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
        if _navigation_only(task):
            assert not predicted, task["id"]
    predicted_positive = counts["tp"] + counts["fp"]
    actual_positive = counts["tp"] + counts["fn"]
    precision = 1.0 if predicted_positive == 0 else counts["tp"] / predicted_positive
    recall = 1.0 if actual_positive == 0 else counts["tp"] / actual_positive
    summary = (
        f"n={len(tasks)} tp={counts['tp']} fp={counts['fp']} "
        f"fn={counts['fn']} tn={counts['tn']} "
        f"precision={precision:.0%} recall={recall:.0%} "
        f"false_positives={false_positives}"
    )
    assert counts["fp"] == 0, summary
    assert precision == 1.0, summary
    assert counts["tp"] + counts["fp"] + counts["fn"] + counts["tn"] == len(tasks)
