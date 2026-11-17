"""Tests for the benchmark harness components."""

from __future__ import annotations

from bench.harness import estimate_tokens, TaskResult
from bench.judge import check_url_contains, check_text_present, check_title_contains
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
