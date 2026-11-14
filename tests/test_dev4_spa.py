"""Offline catalog invariants for dev4spa; never open a browser or call a model."""

import re
from collections import Counter
from urllib.parse import urlsplit

from bench.tasks import DEV4_SPA_TASK_IDS, get_all_tasks, resolve_task_split, tasks_for_split
from bench.verify_dev4_spa import RENDER_ONLY, WRONG

# Hosts other task sets used before dev4spa was written (from used_hosts.txt, 14 Nov 2026).
_TAKEN = {"demoqa.com", "devdocs.io", "letcode.in", "package.elm-lang.org", "seleniumbase.io", "qaplayground.dev"}


def test_dev4spa_has_twelve_unique_complete_tasks():
    tasks = tasks_for_split("dev4spa")
    assert resolve_task_split("dev4spa") == "dev4spa"
    ids = [task["id"] for task in tasks]
    assert len(ids) == len(set(ids)) == 12 and tuple(ids) == DEV4_SPA_TASK_IDS
    catalog = [task["id"] for task in get_all_tasks()]
    assert all(catalog.count(task_id) == 1 for task_id in ids)
    assert {task_id.split("_")[1] for task_id in ids} <= {"spa", "js"}
    for task in tasks:
        markers = task["end_markers"]
        assert task["start_url"].startswith("https://")
        assert markers["answer_in_text"] == task["expected_answer"]
        assert task["check_url_contains"] == markers["url_contains"]
        assert "https://" not in task["description"]
        assert not re.search(r"(?<!\w)" + re.escape(task["expected_answer"]) + r"(?!\w)", task["description"], re.I), task["id"]
        assert task["expected_answer"] not in task["start_url"]
        assert WRONG[task["id"]] != task["expected_answer"]


def test_dev4spa_uses_at_most_two_tasks_per_site_and_fresh_hosts():
    hosts = [urlsplit(task["start_url"]).hostname.removeprefix("www.") for task in tasks_for_split("dev4spa")]
    assert max(Counter(hosts).values()) <= 2
    assert not set(hosts) & _TAKEN
    assert set(RENDER_ONLY) <= set(DEV4_SPA_TASK_IDS)
