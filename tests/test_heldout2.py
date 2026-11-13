"""Offline catalog/grade invariants; never open a browser or call a model."""

import re

from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict
from bench.tasks import (
    HELDOUT2_TASK_IDS,
    get_all_tasks,
    resolve_task_split,
    tasks_for_split,
)


def test_heldout2_split_has_twenty_unique_complete_tasks():
    tasks = tasks_for_split("heldout2")
    assert resolve_task_split("heldout2") == "heldout2"
    assert len(tasks) == len(HELDOUT2_TASK_IDS) == 20
    ids = [task["id"] for task in tasks]
    assert len(set(ids)) == 20
    assert tuple(ids) == HELDOUT2_TASK_IDS
    assert all(task_id.startswith("ho2_") for task_id in ids)
    catalog_ids = [task["id"] for task in get_all_tasks()]
    assert all(catalog_ids.count(task_id) == 1 for task_id in ids)
    required = {"id", "description", "start_url", "expected_answer", "check_url_contains", "end_markers"}
    for task in tasks:
        assert required <= task.keys()
        assert all(task[key] for key in required)
        assert task["start_url"].startswith("https://")
        markers = task["end_markers"]
        assert {"host", "url_contains", "deny"} <= markers.keys()
        assert task["check_url_contains"] in markers["url_contains"]
        assert "https://" not in task["description"]
        assert not re.search(r"(?<!\w)" + re.escape(task["expected_answer"]) + r"(?!\w)", task["description"], re.I)
    assert sum(task["id"].startswith("ho2_nav_") for task in tasks) == 8
    assert sum(task["id"].startswith(("ho2_value_", "ho2_title_")) for task in tasks) == 8
    assert sum(task["id"].startswith("ho2_search_") for task in tasks) == 2
    assert sum(task["id"].startswith("ho2_form_") for task in tasks) == 2


def test_heldout2_does_not_change_existing_splits_or_reuse_end_pages():
    tasks = tasks_for_split("heldout2")
    new_ids = set(HELDOUT2_TASK_IDS)
    for name in ("probe", "dev", "held-out", "honest"):
        assert new_ids.isdisjoint(task["id"] for task in tasks_for_split(name))
    old = [task for task in get_all_tasks() if task["id"] not in new_ids]
    ends = [(task["end_markers"]["host"], task["end_markers"].get("path_suffix") or task["end_markers"]["url_contains"]) for task in tasks]
    assert len(set(ends)) == 20
    for task in tasks:
        markers = task["end_markers"]
        end = "https://" + markers["host"] + markers["url_contains"]
        for existing in old:
            previous = existing.get("end_markers") or {}
            if previous.get("url_contains") and previous["url_contains"] in end:
                host = previous.get("host")
                hosts = host if isinstance(host, list) else [host]
                assert not any(markers["host"] == h or markers["host"].endswith("." + h) for h in hosts if h)


def test_heldout2_value_markers_require_the_requested_value_not_a_heading():
    # Synthetic evidence checks marker wiring, not live-page availability.
    # Real-page checks and first-h1 controls are in bench.verify_heldout2.
    for task in tasks_for_split("heldout2"):
        markers = task["end_markers"]
        if not task["id"].startswith("ho2_nav_") and not task["id"].startswith("ho2_search_"):
            assert markers["answer_in_text"] == task["expected_answer"]
            evidence = PageEvidence(
                url="https://" + markers["host"] + markers["url_contains"],
                h1="Unrelated page heading",
                text="Unrelated page heading\n" + task["expected_answer"],
            )
            assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=task["expected_answer"])).verdict == "PASS"
            assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=evidence.h1)).verdict == "FAIL"


def test_heldout2_dry_plan_lists_tasks_without_a_spend_ledger(monkeypatch):
    from bench.probe import LedgerMissing, SpendLedger, plan_probe

    def missing_ledger(*args, **kwargs):
        raise LedgerMissing("No shared ledger on this offline machine")

    monkeypatch.setattr(SpendLedger, "load", missing_ledger)
    plan = plan_probe(split="heldout2")
    assert plan["execute"] is False
    assert plan["split"] == "heldout2"
    assert plan["tasks"] == list(HELDOUT2_TASK_IDS)
    assert plan["project_spent_usd"] is None
