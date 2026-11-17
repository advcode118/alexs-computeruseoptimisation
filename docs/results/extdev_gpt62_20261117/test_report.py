import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("gpt62_labels", Path(__file__).with_name("build_labels.py"))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_empty():
    assert report.join_labels([], {}) == []
    assert report.summarize([])["mean_ms"] is None


def test_join_and_summary():
    row = dict(task_id="a", model="m", success=False, success_reason="key mismatch",
               wall_ms=100, usd=.2, steps=2)
    joined = report.join_labels([row, {"task_id": "skip", "skipped": True}],
                                {"a": ("correct", "saved evidence")})
    result = report.summarize(joined)
    assert result == dict(n=1, correct=1, partial=0, grader_pass=0,
                          mean_ms=100, median_ms=100, p90_ms=100, usd=.2)


def test_coverage_and_invalid_labels():
    row = dict(task_id="a", model="m", success=True, success_reason="ok",
               wall_ms=100, usd=.2, steps=2)
    for raw, labels in (([row], {}), ([row, row], {"a": ("correct", "")}),
                        ([row], {"a": ("maybe", "")})):
        with pytest.raises(AssertionError):
            report.join_labels(raw, labels)
