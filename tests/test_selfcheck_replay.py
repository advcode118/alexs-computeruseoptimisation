"""Offline replay must not fabricate independent labels from gated success."""
from bench.selfcheck_replay import by_check, confusion, grade_check, replay_check


def test_missing_dynamic_selector_is_ungraded_not_a_false_accept():
    task = {"end_markers": {"answer_equals_selector": ".picked"}}
    check = {"page_url": "https://fixture.example/", "payload": {"text": "First\nSecond", "claimed": {"answer": "First"}}}
    assert grade_check(task, check) is None
    unit = {"before": "PASS", "after": "FAIL", "after_reason": "a rule", "graded": None}
    assert confusion([unit], "before")["precision"] is None
    assert confusion([unit], "after")["recall"] is None
    assert confusion([unit], "after")["ungraded_scripts"] == 1
    assert by_check([unit]) == {}
    check["payload"]["selector_text"] = "First"
    assert grade_check(task, check) is True
    check["payload"]["selector_text"] = "Second"
    assert grade_check(task, check) is False


def test_saved_correct_digitless_answer_is_a_real_false_reject():
    task = {"description": "Report the price of admission.", "end_markers": {"answer_equals_selector": ".price"}}
    check = {
        "page_url": "https://fixture.example/ticket", "start_url": "https://fixture.example/",
        "payload": {"ok": True, "url": "https://fixture.example/ticket", "text": "Price: Complimentary",
                    "claimed": {"answer": "Complimentary"}, "selector_text": "Complimentary"},
    }
    assert grade_check(task, check) is True
    verdict = replay_check(task["description"], check)
    assert verdict.verdict == "FAIL"
    counts = confusion([{"after": verdict.verdict, "graded": True}], "after")
    assert counts["self_fail_graded_pass"] == 1
    assert counts["recall"] == 0.0
    # Judge-only labels do not influence the runtime replay.
    check["payload"]["selector_text"] = "8 credits"
    assert replay_check(task["description"], check) == verdict
