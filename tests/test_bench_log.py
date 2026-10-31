import json

from bench.catalog import agent_tasks
from bench.checks import evaluate
from bench.runner import run_tasks
from loop.browser import BrowserSession


def test_code_check_fails_when_the_page_does_not_match():
    task = next(item for item in agent_tasks() if item.id == "pack-milk")
    session = BrowserSession(headless=True)
    page = session.open()
    try:
        page.goto(task.fixture.resolve().as_uri(), wait_until="domcontentloaded")
        ok, _detail = evaluate(page, {"kind": "dom", "selector": "#list", "text": "milk"})
        assert ok is False
        ok, _detail = evaluate(page, {"kind": "url", "contains": "not-the-page"})
        assert ok is False
        ok, _detail = evaluate(page, {"kind": "fields", "fields": [{"name": "Item", "value": "milk"}]})
        assert ok is False
    finally:
        session.close()


def test_one_task_log_records_success_time_steps_and_estimate(tmp_path):
    task = next(item for item in agent_tasks() if item.id == "pack-milk")
    summary = run_tasks([task], planner_name="fake", out_dir=tmp_path)
    record = summary["tasks"][0]
    assert summary["planner"] == "fake"
    assert summary["dollars_are"] == "estimate"
    assert summary["real_model_runs"] == []
    assert record["success"] is True
    assert record["llm_calls"] == 0
    assert record["tokens"]["total"] == 0
    assert record["estimated_dollars"] == 0.0
    assert record["dollars_are"] == "estimate"
    assert record["steps"] >= 1
    assert record["wall_time_s"] >= 0
    assert "instruction" not in record
    assert "check_detail" not in record
    saved = json.loads((tmp_path / "pack-milk.json").read_text(encoding="utf-8"))
    assert saved["success"] is True
    assert saved["check"] == "dom"
