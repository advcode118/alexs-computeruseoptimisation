"""Synthetic evidence only: never reveal heldout3 examples in test output."""

import json
from pathlib import Path

import pytest

from bench import grade, regrade


def test_prohibited_sources_are_filtered_before_read_or_import():
    assert regrade.allowed_source("docs/results/extdev/raw.jsonl")
    assert not regrade.allowed_source("docs/results/candidates_heldout4.jsonl")
    assert not regrade.allowed_source("bench/tasks_HELDOUT4.py")


@pytest.fixture
def catalog():
    return {
        "text": {"task": {"id": "text", "check_text": "2021-10-01",
                          "end_markers": {"answer_in_text": "2021-10-01"}}, "split": "dev3", "hidden": False},
        "selector": {"task": {"id": "selector", "end_markers": {"answer_equals_selector": "#answer"}},
                     "split": "dev5title", "hidden": False},
        "url": {"task": {"id": "url", "check_url_contains": "/done", "end_markers": {"url_contains": "/done"}},
                "split": "dev4nav", "hidden": False},
        "PRIVATE_TASK": {"task": {"id": "PRIVATE_TASK", "end_markers": {"answer_equals_selector": "#answer"}},
                         "split": "heldout3a", "hidden": True},
    }


def row(**kwargs):
    return {"arm": "script_first", "task_id": "text", "success": True, "end_state": "PASS",
            "claimed_answer": "2021-10-01", "success_reason": "the page evidence matches the markers", **kwargs}


@pytest.mark.parametrize("answer,truth,markers,passed,code", [
    ("2021-10-01", "", {"answer_in_text": "2021-10-01"}, True, ""),
    ("The revision date is 2021-10-01.", "", {"answer_in_text": "2021-10-01"}, True, ""),
    ('**"2021-10-01"**', "", {"answer_in_text": "2021-10-01"}, True, ""),
    ("x" * 100 + "2021-10-01", "", {"answer_in_text": "2021-10-01"}, False, "answer_too_long"),
    ("many extra page words 2021-10-01", "", {"answer_in_text": "2021-10-01"}, False, "answer_too_long"),
    ("2022-10-01", "", {"answer_in_text": "2021-10-01"}, False, "answer_does_not_satisfy_the_marker"),
    ('"The title is PRIVATE_VALUE."', "PRIVATE_VALUE", {"answer_equals_selector": "#answer"}, True, ""),
    ("Your request was received", "Your request was received.", {"answer_equals_selector": "#answer"}, True, ""),
    ("wrong", "truth", {"answer_equals_selector": "#answer"}, False, "answer_is_not_the_marked_value"),
    ("", "truth", {"answer_equals_selector": "#answer"}, False, "empty_answer"),
])
def test_answer_side_reuses_frozen_rules(answer, truth, markers, passed, code):
    verdict = regrade.answer_span(markers, answer, truth)
    assert (verdict.verdict == grade.PASS) is passed
    if code:
        assert verdict.code == code


@pytest.mark.parametrize("success", [True, False])
def test_no_answer_marker_unaffected(catalog, success):
    result = regrade.regrade_row(row(task_id="url", success=success, end_state="UNKNOWN"), catalog)
    assert result["new"] is success
    assert result["category"] == "unaffected (no answer marker)"


def test_skips_unknown_tasks_and_ungraded(catalog):
    assert regrade.regrade_row(row(skipped=True), catalog)["category"] == "skipped"
    assert regrade.regrade_row(row(task_id="unknown"), catalog)["category"] == "not re-gradable: task not found"
    assert regrade.regrade_row(row(success=None), catalog)["category"] == "not re-gradable: interrupted/ungraded row"


@pytest.mark.parametrize("arm", ["script_first", "playwright_mcp", "browser_use", "stagehand"])
def test_old_pass_short_span_and_dump(catalog, arm):
    assert regrade.regrade_row(row(arm=arm), catalog)["new"] is True
    result = regrade.regrade_row(row(arm=arm, claimed_answer="page " * 100 + "2021-10-01"), catalog)
    assert result["new"] is False
    assert result["code"] == "answer_too_long"


@pytest.mark.parametrize("reason", ["the page is on the wrong host", "the page is denied (search)",
                                    "the URL marker does not match the live page", "empty evidence", "empty answer",
                                    "run failed: RuntimeError", "returned evidence is not on the page"])
def test_old_non_answer_failures_stay_failed(catalog, reason):
    result = regrade.regrade_row(row(success=False, success_reason=reason), catalog)
    assert result["new"] is False
    assert result["category"] == "unchanged (non-answer failure)"


@pytest.mark.parametrize("reason", regrade.ANSWER_REASONS)
def test_old_answer_failure_still_bad(catalog, reason):
    result = regrade.regrade_row(row(success=False, success_reason=reason, claimed_answer="wrong"), catalog)
    assert result["new"] is False
    assert result["code"] == "answer_does_not_satisfy_the_marker"


def test_selector_failure_recovers_and_text_failure_is_only_potential(catalog):
    result = regrade.regrade_row(row(task_id="selector", success=False, success_reason="answer is not the marked value",
                                    expected_value="PRIVATE_VALUE", claimed_answer='"The title is PRIVATE_VALUE."'), catalog)
    assert result["new"] is True
    result = regrade.regrade_row(row(success=False, success_reason="answer is not in the page text",
                                    claimed_answer="The revision date is 2021-10-01."), catalog)
    assert result["new"] is None
    assert result["potential_fail_to_pass"]
    assert "needs page text" in result["category"]


@pytest.mark.parametrize("state", ["FAIL", "UNKNOWN", ""])
def test_own_gate_blocks_answer_recovery(catalog, state):
    result = regrade.regrade_row(row(success=False, end_state=state, success_reason="answer is not in the page text"), catalog)
    assert result["new"] is False
    assert result["code"] == "own_verdict_not_PASS"


def test_missing_selector_claim_and_failure_reason(catalog):
    assert "truth was not saved" in regrade.regrade_row(row(task_id="selector"), catalog)["category"]
    missing = row()
    del missing["claimed_answer"]
    assert "claimed answer was not saved" in regrade.regrade_row(missing, catalog)["category"]
    assert "failure reason was not saved" in regrade.regrade_row(row(success=False, success_reason=""), catalog)["category"]


@pytest.mark.parametrize("page,gate,completed,expected", [("2021-10-01", "PASS", True, True),
    ("", "PASS", True, False), ("wrong", "PASS", True, False),
    ("2021-10-01", "FAIL", True, False), ("2021-10-01", "PASS", False, False)])
def test_full_v2_regrade_with_claim_gate_empty_page_and_completion(catalog, page, gate, completed, expected):
    saved = row(success=False, wall_clock_version=2, grade_page_text=page, grade_url="https://example.test/done",
                grade_completed=completed, end_state=gate,
                grade_claim={"answer": "2021-10-01", "url": "https://example.test/done"})
    result = regrade.regrade_row(saved, catalog)
    assert result["category"] == "full re-grade"
    assert result["new"] is expected


def test_wrappers_non_arm_rows_and_pilot():
    assert regrade.unpack(json.dumps({"row": row()}))[0]["task_id"] == "text"
    assert regrade.unpack(json.dumps({"kind": "openai_report", **row()})) == []
    assert regrade.unpack('{"kind":"note"}') == []
    assert regrade.unpack(json.dumps([{"task_id": "text", "success": None}]), jsonl=False, pilot=True)[0]["arm"] == "script_first"


@pytest.mark.parametrize("arm,extra,expected", [("browser_use", {}, None),
    ("browser_use", {"browser_launch_ms": 7, "grade_read_ms": 11}, 82),
    ("script_first", {"browser_launch_ms": 7, "grade_read_ms": 11}, None),
    ("playwright_mcp", {"browser_launch_ms": 7, "grade_read_ms": 11}, None),
    ("playwright_mcp", {"browser_launch_ms": 7, "grade_read_ms": 11, "peek_ms": 3}, 103),
    ("browser_use", {"wall_clock_version": 2}, 100)])
def test_wall_time_honesty(arm, extra, expected):
    assert regrade.normalized_wall({"arm": arm, "wall_ms": 100, **extra})[0] == expected


def test_report_suppresses_hidden_details_in_both_formats_and_matches_denominators(tmp_path, catalog):
    (tmp_path / "bench").mkdir()
    (tmp_path / "bench/grade.py").write_text("frozen")
    rows = [row(task_id="PRIVATE_TASK", success=False, success_reason="answer is not the marked value",
                expected_value="PRIVATE_ANSWER", claimed_answer='"The title is PRIVATE_ANSWER."'),
            row(task_id="PRIVATE_TASK", claimed_answer="PRIVATE_DUMP " * 100, expected_value="PRIVATE_ANSWER"),
            row(success=False, success_reason="answer does not satisfy the marker"), row(skipped=True), row()]
    report = regrade.build_report(tmp_path, [{"path": "source.jsonl", "branch": "test", "commit": "abc", "sha256": "hash",
                                            "data": "\n".join(json.dumps(r) for r in rows)}], catalog)
    for rendered in (regrade.markdown(report), json.dumps(report)):
        assert "PRIVATE_TASK" not in rendered
        assert "PRIVATE_ANSWER" not in rendered
        assert "PRIVATE_DUMP" not in rendered
    assert sum(r["count"] for r in report["heldout3_flips"]) == 2
    group = next(r for r in report["datasets"] if r["dataset"] == "dev3")
    assert group["regradable"] == 1
    assert group["potential_fail_to_pass"] == 1
    assert group["skipped"] == 1
    assert group["old_rate"] == group["new_rate"] == 100


def test_aggregate_metadata_sources_and_no_raw_dataset(tmp_path):
    directory = tmp_path / "docs/results/val3_gate"
    directory.mkdir(parents=True)
    (tmp_path / "bench").mkdir()
    (tmp_path / "bench/grade.py").write_text("frozen")
    (directory / "aggregate.json").write_text(json.dumps({"sources": [{"path": "C:/raw.jsonl", "sha256": "hash"}]}))
    report = regrade.build_report(tmp_path, [], {})
    assert report["not_regradable_files"][0]["references"] == [{"path": "C:/raw.jsonl", "sha256": "hash"}]
    assert report["datasets"][0]["raw_rows_missing"]
    assert "raw absent" in regrade.markdown(report)


def test_catalog_loads_every_specialized_task_and_split():
    catalog = regrade.task_catalog()
    assert {"heldout3a", "heldout3b", "heldout3c", "heldout3d", "val3", "dev3", "dev4nav", "dev4form", "dev4spa",
            "dev5title", "heldout2", "held-out", "dev"} <= {entry["split"] for entry in catalog.values()}
    assert all(entry["hidden"] for entry in catalog.values() if entry["split"].startswith("heldout3"))


def test_discovery_reads_remote_git_blobs_and_current_files_once(tmp_path, monkeypatch):
    current = tmp_path / "docs/results/current.jsonl"
    current.parent.mkdir(parents=True)
    current.write_text(json.dumps(row()))
    remote = "docs/results/remote.jsonl"
    calls = []

    def git(root, *args):
        calls.append(args)
        if args[:2] == ("rev-parse", "HEAD"):
            return "head\n"
        if args[:2] == ("branch", "--show-current"):
            return "local\n"
        if args[0] == "for-each-ref":
            return "origin/t3/robust-executor\n"
        if args[:3] == ("log", "--all", "--format="):
            return "docs/results/current.jsonl\n" + remote + "\n"
        if args[0] == "log":
            return "savedcommit\n"
        if args[0] == "branch":
            return "origin/t3/robust-executor\n"
        if args[0] == "rev-parse":
            return "tipcommit\n"
        if args[0] == "ls-tree":
            return remote
        if args[0] == "show":
            assert args[1] == "tipcommit:" + remote
            return json.dumps(row())
        raise AssertionError(args)

    monkeypatch.setattr(regrade, "git", git)
    sources = regrade.discover(tmp_path)
    assert len(sources) == 2
    assert sources[1]["branch"] == "origin/t3/robust-executor"
    assert sources[1]["commit"] == "tipcommit"
    assert any(args[0] == "show" for args in calls)
