"""Offline catalog/grade checks. Does not inspect any frozen task set."""
from collections import Counter
from urllib.parse import urlsplit

from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict
from bench.tasks_dev4_search import DEV4_SEARCH_TASKS


def test_only_kind_filter_and_registration():
    import pytest
    from bench.probe import probe_tasks
    from bench.openai_run import _tasks

    assert probe_tasks("dev4search", only_kind="search") == DEV4_SEARCH_TASKS
    assert len(_tasks("dev3", one_task=False, only_kind="search")) == 6
    with pytest.raises(ValueError, match="no tasks"):
        probe_tasks("dev4search", only_kind="missing")


def test_catalog_and_grader_reject_start_results_and_wrong_destination():
    tasks = DEV4_SEARCH_TASKS
    assert len(tasks) == len({t["id"] for t in tasks}) == 12
    hosts = Counter(urlsplit(t["start_url"]).hostname for t in tasks)
    assert len(hosts) == 6 and max(hosts.values()) == 2
    for task in tasks:
        markers = task["end_markers"]
        claim = ClaimedEvidence(answer=task["expected_answer"])
        end = "https://" + markers["host"] + markers["path_suffix"]
        assert markers["path_suffix"] not in task["start_url"]
        assert task["expected_answer"].casefold() not in task["description"].casefold()
        evidence = PageEvidence(url=end, title=task["expected_answer"], text=task["expected_answer"])
        assert evidence_verdict(markers, evidence, claim).verdict == "PASS"
        for url in (task["start_url"], "https://" + markers["host"] + "/search?q=" + markers["path_suffix"], end + "-other"):
            evidence = PageEvidence(url=url, title=task["expected_answer"], text=task["expected_answer"])
            assert evidence_verdict(markers, evidence, claim).verdict == "FAIL"
