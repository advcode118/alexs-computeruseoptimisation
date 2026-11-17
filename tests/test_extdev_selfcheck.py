"""Reproduce experiment 3 without relabelling intermediate scripts."""

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

DIRECTORY = Path(__file__).resolve().parents[1] / "docs/results/extdev_selfcheck_20261117"


@pytest.fixture
def replay():
    spec = importlib.util.spec_from_file_location("extdev_selfcheck", DIRECTORY / "replay.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reproduce_saved_script_scores(tmp_path):
    result = subprocess.run([sys.executable, str(DIRECTORY / "replay.py"), "--output-dir", str(tmp_path)],
                            capture_output=True, text=True, check=True)
    assert "not human spot-checked; indicative only" in result.stdout
    for filename in ("scripts.csv", "results.json", "sources.json"):
        assert (tmp_path / filename).read_bytes() == (DIRECTORY / filename).read_bytes()
    report = json.loads((tmp_path / "results.json").read_text())
    assert (report["dev_rows"], report["dev_scripts"], report["extdev_rows"], report["extdev_scripts"]) == (149, 316, 22, 35)
    assert report["extdev_row_labels"] == {"correct": 3, "partial": 5, "wrong": 14}
    assert (report["dev_reference_saved_precision"]["TP"], report["dev_reference_saved_precision"]["FP"]) == (85, 5)
    assert report["model_calls"] == report["browser_runs"] == 0
    for dataset, variant, expected in (
        ("dev_val_grader", "runtime_scope", (16, 6, 71, 177)),
        ("dev_val_grader", "precision_all", (13, 1, 74, 182)),
        ("extdev_strict_AI", "runtime_scope", (3, 1, 0, 12)),
        ("extdev_partial_positive_AI", "runtime_scope", (4, 0, 4, 8)),
    ):
        count = report["scores"][dataset][variant]
        assert tuple(count[key] for key in ("TP", "FP", "FN", "TN")) == expected
    for name, variants in report["scores"].items():
        for count in variants.values():
            assert sum(count[key] for key in ("TP", "FP", "FN", "TN")) == (270 if name == "dev_val_grader" else 16)
            assert count["unlabelled"] == (46 if name == "dev_val_grader" else 19)
    with (tmp_path / "scripts.csv").open() as handle:
        rows = [row for row in csv.DictReader(handle) if row["dataset"] == "extdev"]
    assert sum(row["saved_verdict"] == "PASS" for row in rows) == 6
    assert all(not row["truth"] for row in rows if row["truth_note"].startswith("intermediate"))


def test_partial_truth_policy_and_empty_metrics(replay):
    rows = [{"truth": "correct", "v": True}, {"truth": "partial", "v": True},
            {"truth": "wrong", "v": False}, {"truth": None, "v": True}]
    strict = replay.metrics(rows, "v")
    inclusive = replay.metrics(rows, "v", True)
    assert (strict["TP"], strict["FP"], strict["unlabelled"]) == (1, 1, 1)
    assert (inclusive["TP"], inclusive["FP"]) == (2, 0)
    assert replay.metrics([], "v")["precision"] is None
    assert replay.metrics([], "v")["recall"] is None


def test_tightenings_read_only_visible_evidence(replay):
    check = {"page_url": "https://example.test/team", "payload": {
        "ok": True, "steps": 1, "title": "Team schedule", "text": "A grounded answer",
        "claimed": {"answer": "A grounded answer"}}}
    assert replay.candidate_rules("Find team schedule", check) == {"grounding": True, "no_dump": True, "scope": True}
    check["payload"]["claimed"]["answer"] = "not on page\n" * 20
    rules = replay.candidate_rules("Find team schedule", check)
    assert not rules["grounding"] and not rules["no_dump"]
    assert replay.candidate_rules("", {}) == {"grounding": False, "no_dump": True, "scope": False}
    predicted, verdict, *_ = replay.predictions("Find team schedule", {}, [])
    assert verdict == "UNKNOWN" and not any(predicted.values())


@pytest.mark.parametrize("term", ["18.2.0", "dependency-tree", "example.test", "source_insights", "C++17"])
def test_scope_preserves_punctuated_terms_without_evidence_limit(replay, term):
    description = f"Find {term} dependency missing unrelated"
    check = {"page_url": "https://example.invalid/", "payload": {
        "title": " ".join(f"noise{i}" for i in range(20)) + f" {term.upper()}.",
        "h1": "Dependency"}}
    assert replay.candidate_rules(description, check)["scope"]
    check["payload"]["title"] = " ".join(replay.re.findall(r"[A-Za-z0-9]+", term))
    assert not replay.candidate_rules(description, check)["scope"]
