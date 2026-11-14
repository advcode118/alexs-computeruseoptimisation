"""Offline catalog invariants for dev4nav; never open a browser or call a model."""

import re
from collections import Counter

from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict
from bench.tasks import DEV4_NAV_TASK_IDS, get_all_tasks, resolve_task_split, tasks_for_split
from tests.test_dev3 import USED_HOSTS, _hosts, registrable


def test_dev4nav_split_has_twelve_read_tasks():
    tasks = tasks_for_split("dev4nav")
    assert resolve_task_split("dev4nav") == "dev4nav"
    ids = [task["id"] for task in tasks]
    assert tuple(ids) == DEV4_NAV_TASK_IDS and len(set(ids)) == 12
    catalog_ids = [task["id"] for task in get_all_tasks()]
    assert all(catalog_ids.count(task_id) == 1 for task_id in ids)
    assert Counter(task_id.split("_")[1] for task_id in ids) == {"value": 8, "title": 4}
    for task in tasks:
        markers = task["end_markers"]
        assert task["start_url"].startswith("https://")
        assert markers["answer_in_text"] == task["expected_answer"]
        assert markers["url_contains"] not in task["start_url"], task["id"]
        assert "https://" not in task["description"]
        assert not re.search(r"(?<!\w)" + re.escape(task["expected_answer"]) + r"(?!\w)", task["description"], re.I), task["id"]


def test_dev4nav_sites_are_new_and_at_most_two_each():
    per_site = Counter()
    for task in tasks_for_split("dev4nav"):
        sites = {registrable(host) for host in _hosts(task)}
        per_site.update(sites)
    assert max(per_site.values()) <= 2, per_site.most_common(3)
    used = {registrable(host) for host in USED_HOSTS}
    for name in ("probe", "dev", "held-out", "heldout2", "dev3"):
        for task in tasks_for_split(name):
            used.update(registrable(host) for host in _hosts(task))
    assert not used & set(per_site), sorted(used & set(per_site))


def test_dev4nav_markers_require_the_value_not_a_heading():
    for task in tasks_for_split("dev4nav"):
        markers = task["end_markers"]
        host = markers["host"] if isinstance(markers["host"], str) else markers["host"][0]
        end = "https://" + host + markers["url_contains"]
        if not end.endswith(markers["path_suffix"]):
            end += markers["path_suffix"]
        evidence = PageEvidence(url=end, h1="Unrelated page heading", text="Unrelated page heading\n" + task["expected_answer"])
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=task["expected_answer"])).verdict == "PASS", task["id"]
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=evidence.h1)).verdict == "FAIL", task["id"]
