"""Catalog checks for the new form-only development split."""
from collections import Counter
from urllib.parse import urlsplit

from bench.tasks import tasks_for_split
from bench.verify_dev4_form import WRONG


def test_twelve_new_forms_and_negative_checks():
    tasks = tasks_for_split("dev4form")
    assert len(tasks) == 12
    assert len({t["id"] for t in tasks}) == 12
    assert set(WRONG) == {t["id"] for t in tasks}
    assert max(Counter(urlsplit(t["start_url"]).hostname for t in tasks).values()) <= 2
    for task in tasks:
        assert task["expected_answer"] not in task["description"]
        assert task["id"].startswith("dev4_form_")


def test_openai_only_kind_filter(monkeypatch):
    from bench.openai_run import _tasks
    monkeypatch.setenv("CU_PROBE_ONLY_KIND", "form")
    tasks = _tasks("dev3", one_task=False)
    assert len(tasks) == 6 and all(t["id"].split("_")[1] == "form" for t in tasks)
