"""Offline report must not turn a runtime self-PASS into independent evidence."""

from bench.observe_first_report import distribution, first_grade, task_metrics


def _row():
    return {
        "task_id": "fixture", "success": False, "end_state": "PASS",
        "scripts": ["one", "two"], "wall_ms": 10, "usd": 0.01,
        "final_url": "https://example.test/last", "expected_value": "final only",
        "self_checks": [
            {"page_url": "https://example.test/first", "verdict": "PASS", "payload": {}},
            {"page_url": "https://example.test/last", "verdict": "PASS", "payload": {}},
        ],
    }


def test_intermediate_selector_grade_is_unknown_and_cannot_borrow_final_value():
    task = {"end_markers": {"answer_equals_selector": ".value"}}
    row = _row()
    assert first_grade(row, task) is None
    result = task_metrics(row, task)
    assert result["first_script_self_pass"] is True
    assert result["first_script_graded_pass"] is None
    assert result["graded_pass"] is False


def test_single_script_selector_grade_uses_only_post_run_evidence(monkeypatch):
    import bench.selfcheck_replay as replay

    row = _row()
    row["self_checks"] = [row["self_checks"][-1]]
    seen = []
    monkeypatch.setattr(replay, "grade_check", lambda task, check: seen.append(check) or False)
    assert first_grade(row, {"end_markers": {"answer_equals_selector": ".value"}}) is False
    assert seen[0]["payload"]["selector_text"] == "final only"
    assert "selector_text" not in row["self_checks"][0]["payload"]


def test_navigation_grade_can_be_independent_of_runtime_pass():
    row = _row()
    task = {"end_markers": {"host": "example.test", "path_suffix": "/wrong"}}
    assert first_grade(row, task) is False


def test_old_log_does_not_invent_first_grade():
    row = _row()
    del row["self_checks"]
    assert first_grade(row, {}) is None


def test_old_sole_script_self_pass_preserves_recorded_grade_failure():
    row = _row()
    del row["self_checks"]
    row["scripts"] = ["one"]
    assert first_grade(row, {}) is False
    row["end_state"] = "FAIL"
    assert first_grade(row, {}) is None


def test_latency_distribution_keeps_tail_and_zero():
    assert distribution([0, 10, 20, 100]) == {"n": 4, "median": 15.0, "mean": 32.5, "p90": 76.0}
