"""Offline catalog invariants for val3; never open a browser or call a model."""

import re
from collections import Counter
from urllib.parse import urlsplit

from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict
from bench.tasks import VAL3_TASK_IDS, get_all_tasks, resolve_task_split, tasks_for_split

# Private public-suffix entries our hosts can sit under. Each subdomain of
# these is its own registrable domain.
_SHARED_SUFFIXES = {"netlify.app", "github.io", "js.org", "blogspot.com", "co.uk", "gov.uk", "ac.uk", "org.uk"}
_KINDS = {"nav": 10, "value": 10, "search": 6, "form": 6, "title": 4, "spa": 4}


def _registrable(host: str) -> str:
    labels = host.casefold().strip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in _SHARED_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _hosts(task: dict) -> set[str]:
    hosts = {urlsplit(task["start_url"]).hostname or ""}
    marker = (task.get("end_markers") or {}).get("host")
    for item in marker if isinstance(marker, (list, tuple)) else [marker]:
        if item:
            hosts.add(str(item))
    return {host for host in hosts if host}


def _domains(tasks: list[dict]) -> set[str]:
    return {_registrable(host) for task in tasks for host in _hosts(task)}


def test_val3_has_forty_unique_complete_tasks_in_the_kind_mix():
    tasks = tasks_for_split("val3")
    assert resolve_task_split("val3") == "val3"
    assert len(tasks) == len(VAL3_TASK_IDS) == 40
    ids = [task["id"] for task in tasks]
    assert len(set(ids)) == 40
    assert tuple(ids) == VAL3_TASK_IDS
    catalog_ids = [task["id"] for task in get_all_tasks()]
    assert all(catalog_ids.count(task_id) == 1 for task_id in ids)
    kinds = Counter(task_id.split("_")[1] for task_id in ids)
    assert dict(kinds) == _KINDS
    assert all(task_id.startswith(f"val3_{task_id.split('_')[1]}_") for task_id in ids)
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
        assert markers["url_contains"] not in task["description"]
        if markers.get("answer_in_text"):
            assert markers["answer_in_text"] not in task["description"]
        # The start page is a home or section page, not the finished page.
        assert markers["url_contains"].casefold() not in task["start_url"].casefold()


def test_val3_answer_kinds_carry_an_answer_marker():
    for task in tasks_for_split("val3"):
        kind = task["id"].split("_")[1]
        markers = task["end_markers"]
        if kind in ("nav", "search"):
            assert "answer_in_text" not in markers, task["id"]
            continue
        marker = markers["answer_in_text"]
        assert marker.casefold() in task["expected_answer"].casefold(), task["id"]
        # Synthetic evidence checks marker wiring; bench.verify_val3 checks live pages.
        evidence = PageEvidence(
            url="https://" + markers["host"] + "/" + markers["url_contains"].lstrip("/"),
            h1="Unrelated page heading",
            text="Unrelated page heading\n" + task["expected_answer"],
        )
        claim = ClaimedEvidence(answer=task["expected_answer"])
        assert evidence_verdict(markers, evidence, claim).verdict == "PASS", task["id"]
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=evidence.h1)).verdict == "FAIL", task["id"]


def test_val3_sites_are_n_to_z_and_at_most_three_tasks_each():
    tasks = tasks_for_split("val3")
    per_site = Counter()
    for task in tasks:
        domains = {_registrable(host) for host in _hosts(task)}
        assert len(domains) == 1, (task["id"], domains)
        domain = domains.pop()
        assert "n" <= domain[0] <= "z", (task["id"], domain)
        per_site[domain] += 1
    assert max(per_site.values()) <= 3, per_site
    assert len(per_site) >= 25, per_site


def test_val3_shares_no_site_with_the_other_sets():
    ours = _domains(tasks_for_split("val3"))
    for split in ("held-out", "heldout2", "heldout3"):
        theirs = _domains(tasks_for_split(split))
        assert theirs, split
        assert ours.isdisjoint(theirs), (split, sorted(ours & theirs))
    new_ids = set(VAL3_TASK_IDS)
    for name in ("probe", "dev", "held-out", "heldout2", "heldout3", "honest"):
        assert new_ids.isdisjoint(task["id"] for task in tasks_for_split(name))


def test_val3_dry_plan_lists_tasks_without_a_spend_ledger(monkeypatch):
    from bench.probe import LedgerMissing, SpendLedger, plan_probe

    def missing_ledger(*args, **kwargs):
        raise LedgerMissing("No shared ledger on this offline machine")

    monkeypatch.setattr(SpendLedger, "load", missing_ledger)
    plan = plan_probe(split="val3")
    assert plan["execute"] is False
    assert plan["split"] == "val3"
    assert plan["tasks"] == list(VAL3_TASK_IDS)
    assert plan["project_spent_usd"] is None
