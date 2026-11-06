"""Tests for the benchmark harness components."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench.harness import estimate_tokens, StepMetrics, TaskResult
from bench.judge import check_url_contains, check_text_present, check_title_contains
from bench.replay_shortcuts import (
    parse_aria_snapshot_to_observation,
    action_to_string,
    model_action_to_string,
    actions_match,
    SnapshotRecord,
    replay_snapshot,
)
from bench.summarize import TaskSummary, format_time, format_pct, generate_task_table


class TestEstimateTokens:
    def test_basic_estimate(self):
        assert estimate_tokens("hello") == 1
        assert estimate_tokens("hello world this is a test") == 6

    def test_empty_string(self):
        assert estimate_tokens("") == 1

    def test_long_text(self):
        text = "x" * 400
        assert estimate_tokens(text) == 100


class TestJudge:
    def test_check_url_contains_success(self):
        result = check_url_contains(
            "https://en.wikipedia.org/wiki/Ada_Lovelace",
            "Ada_Lovelace"
        )
        assert result.success is True
        assert result.confidence == 1.0

    def test_check_url_contains_failure(self):
        result = check_url_contains(
            "https://en.wikipedia.org/wiki/Main_Page",
            "Ada_Lovelace"
        )
        assert result.success is False

    def test_check_url_case_insensitive(self):
        result = check_url_contains(
            "https://example.com/ADA_LOVELACE",
            "ada_lovelace"
        )
        assert result.success is True

    def test_check_text_present_single(self):
        result = check_text_present(
            "Ada Lovelace was a mathematician",
            "mathematician"
        )
        assert result.success is True

    def test_check_text_present_multiple(self):
        result = check_text_present(
            "Ada Lovelace was a mathematician and writer",
            ["mathematician", "writer"]
        )
        assert result.success is True

    def test_check_text_present_missing(self):
        result = check_text_present(
            "Ada Lovelace was a mathematician",
            ["mathematician", "programmer"]
        )
        assert result.success is False
        assert "programmer" in result.reason

    def test_check_title_contains(self):
        result = check_title_contains(
            "Ada Lovelace - Wikipedia",
            "Ada Lovelace"
        )
        assert result.success is True


class TestAriaSnapshotParser:
    def test_parse_basic_snapshot(self):
        snapshot = """- button "Search" [ref=e12]
- textbox "Query" [ref=e5]
- link "Home" [ref=e1]"""

        obs = parse_aria_snapshot_to_observation(snapshot, url="https://example.com", title="Test")

        assert len(obs.controls) == 3
        assert obs.controls[0].role == "button"
        assert obs.controls[0].name == "Search"
        assert obs.controls[0].ref == "e12"
        assert obs.controls[1].role == "textbox"
        assert obs.controls[2].role == "link"
        assert "button\tSearch\te12" in obs.html

    def test_parse_nested_snapshot(self):
        snapshot = """- navigation "Site"
  - searchbox "Search Wikipedia" [ref=S1E3]
  - button "Search" [ref=S1E4]"""

        obs = parse_aria_snapshot_to_observation(snapshot)

        assert len(obs.controls) == 2
        assert obs.controls[0].ref == "S1E3"
        assert obs.controls[1].ref == "S1E4"

    def test_parse_empty_name(self):
        snapshot = """- list [ref=e5]
- paragraph [ref=e6]"""

        obs = parse_aria_snapshot_to_observation(snapshot)

        assert len(obs.controls) == 2
        assert obs.controls[0].name == ""
        assert obs.controls[0].role == "list"


class TestActionStringConversion:
    def test_click_action(self):
        from loop.actions import ActionBatch, Click

        batch = ActionBatch("click it", [Click("e5")], None, False)
        assert action_to_string(batch) == "click:e5"

    def test_fill_action(self):
        from loop.actions import ActionBatch, Fill

        batch = ActionBatch("fill it", [Fill("e3", "hello")], None, False)
        assert action_to_string(batch) == "fill:e3:hello"

    def test_done_batch(self):
        from loop.actions import ActionBatch

        batch = ActionBatch("done", [], None, True)
        assert action_to_string(batch) == "done"

    def test_model_action_click(self):
        result = model_action_to_string("browser_click", {"target": "S1E5"})
        assert result == "click:S1E5"

    def test_model_action_type(self):
        result = model_action_to_string("browser_type", {"target": "S1E3", "text": "hello"})
        assert result == "fill:S1E3:hello"


class TestActionsMatch:
    def test_matching_clicks(self):
        assert actions_match("click:e5", "click:e5") is True

    def test_non_matching_clicks(self):
        assert actions_match("click:e5", "click:e6") is False

    def test_matching_fills(self):
        assert actions_match("fill:e3:hello", "fill:e3:hello") is True

    def test_different_actions(self):
        assert actions_match("click:e5", "fill:e5:hello") is False

    def test_none_shortcut(self):
        assert actions_match(None, "click:e5") is None


class TestReplaySnapshot:
    def test_replay_with_searchbox(self):
        snapshot = SnapshotRecord(
            task_id="test",
            step_number=1,
            snapshot_text="""- searchbox "Search Wikipedia" [ref=e4]
- button "Search" [ref=e5]""",
            model_action=None,
            model_tool_name="browser_type",
            model_tool_args={"target": "e4", "text": "Ada Lovelace"},
        )

        result = replay_snapshot(
            snapshot,
            task_description="Search Wikipedia for Ada Lovelace",
        )

        assert result.shortcut_tier is not None


class TestSummarize:
    def test_format_time(self):
        assert format_time(1000) == "1.0s"
        assert format_time(500) == "0.5s"
        assert format_time(15000) == "15.0s"

    def test_format_pct(self):
        assert format_pct(50, 100) == "50%"
        assert format_pct(0, 100) == "0%"
        assert format_pct(100, 0) == "0%"

    def test_generate_task_table(self):
        summaries = [
            TaskSummary(
                task_id="test1",
                success=True,
                total_steps=5,
                total_wall_ms=10000,
                total_model_ms=7000,
                total_tool_ms=2000,
                total_other_ms=1000,
                total_input_tokens=1000,
                total_output_tokens=200,
                total_snapshot_tokens=500,
                error=None,
            )
        ]

        table = generate_task_table(summaries)

        assert "test1" in table
        assert "✓" in table
        assert "70%" in table
        assert "1,000" in table


class TestTaskResult:
    def test_task_result_creation(self):
        result = TaskResult(
            task_id="test",
            task_description="Test task",
            success=True,
            success_reason="Completed",
            total_steps=5,
            total_wall_ms=10000,
            total_model_ms=7000,
            total_tool_ms=2000,
            total_other_ms=1000,
            total_input_tokens=1000,
            total_output_tokens=200,
            total_snapshot_tokens=500,
        )

        assert result.task_id == "test"
        assert result.success is True
        assert result.total_steps == 5


class TestSnapshotFiles:
    def test_sample_snapshots_exist(self):
        snapshots_dir = Path(__file__).parent.parent / "bench" / "snapshots"
        assert snapshots_dir.exists()

        snapshot_files = list(snapshots_dir.glob("*.json"))
        assert len(snapshot_files) >= 3

    def test_sample_snapshots_valid(self):
        snapshots_dir = Path(__file__).parent.parent / "bench" / "snapshots"

        for snapshot_file in snapshots_dir.glob("*.json"):
            with open(snapshot_file) as f:
                data = json.load(f)

            assert "task_id" in data
            assert "snapshot_text" in data
            assert "step_number" in data

            obs = parse_aria_snapshot_to_observation(
                data["snapshot_text"],
                url=data.get("url", "https://example.com"),
                title=data.get("title", "Test"),
            )
            assert len(obs.controls) > 0
