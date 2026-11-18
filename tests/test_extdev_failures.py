"""Saved-row experiment 2: no browser, model, grader, or network required."""

import csv
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

DIRECTORY = Path(__file__).resolve().parents[1] / "docs/results/extdev_failures_20261117"


@pytest.fixture
def replay_module(monkeypatch):
    monkeypatch.syspath_prepend(str(DIRECTORY))
    spec = importlib.util.spec_from_file_location("extdev_failure_replay", DIRECTORY / "replay_fixes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_saved_row_commands(tmp_path):
    for script in ("classify.py", "replay_fixes.py"):
        result = subprocess.run(
            [sys.executable, str(DIRECTORY / script), "--output-dir", str(tmp_path)],
            capture_output=True, text=True, check=True,
        )
        assert "grammar_rejection" in result.stdout
    with (tmp_path / "failures.csv").open() as handle:
        failures = list(csv.DictReader(handle))
    assert len(failures) == 22
    assert Counter(row["hand_label"] for row in failures) == {"correct": 3, "partial": 5, "wrong": 14}
    assert Counter(row["primary"] for row in failures)["grammar_rejection"] == 6
    report = json.loads((tmp_path / "replay.json").read_text())
    assert all(sum(counts.values()) == 22 for counts in report["counts"].values())
    assert report["counts"]["combined"] == {"correct": 6, "partial": 4, "wrong": 5, "unknown": 7}
    assert report["paid_model_calls"] == report["browser_runs"] == 0
    assert len(report["syntax"]) == 35
    assert sum(s["newly_parses"] for s in report["syntax"]) == 7
    for filename in ("failures.csv", "replay.csv", "replay.json"):
        assert (tmp_path / filename).read_bytes() == (DIRECTORY / filename).read_bytes()


def test_regex_probe_is_parse_only(replay_module):
    code = "await page.getByRole('link', {name: /2004/}).click();"
    assert replay_module.parse_error(code)
    assert not replay_module.regex_parse_error(code)
    assert replay_module.parse_error(code)
    assert replay_module.regex_parse_error("not a script")
    assert replay_module.regex_parse_error("")
    assert replay_module.regex_parse_error("await page.evaluate(() => fetch('/x'));")


def test_budget_preserves_json_and_reports_loss(replay_module):
    for payload in (
        {"ok": True, "steps": 1, "text": "short"},
        {"ok": True, "steps": 1, "text": "page " * 10000, "claimed": {"answer": "a" * 9000}},
        {"ok": False, "steps": 0, "error": "e" * 20000, "url": "u" * 20000},
        {"ok": True, "steps": 0, "text": ""},
    ):
        rendered, dropped = replay_module.truncate_metadata(payload)
        assert len(rendered) <= 7700
        assert json.loads(rendered)["ok"] == payload["ok"]
        if "claimed" in payload:
            assert "claimed" in dropped


def test_extractions_are_evidence_limited(replay_module):
    data = replay_module.rows()
    outputs = {row["line"]: replay_module.extract(row["task_description"], row["grade_page_text"]) for row in data}
    assert outputs[7][0].count(" — ") == 6
    assert len(outputs[79][0].splitlines()) == 9
    assert outputs[83][0] == "Marketing Analyst — Chicago, IL"
    assert outputs[23][1] == outputs[31][1] == outputs[39][1] == "partial"
    for row in data:
        assert replay_module.extract(row["task_description"], "")[0] == ""
        assert replay_module.extract(row["task_description"], "No relevant evidence")[0] == ""
    assert replay_module.extract("", "")[0] == ""
