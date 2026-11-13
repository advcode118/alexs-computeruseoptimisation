"""Offline catalog/grade invariants for heldout3b; never open a browser or call a model."""

import re
from collections import Counter
from urllib.parse import urlsplit

from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict
from bench.tasks import HELDOUT3B_TASK_IDS, get_all_tasks, resolve_task_split, tasks_for_split

KINDS = {"nav": 8, "value": 8, "search": 4, "form": 4, "spa": 3, "title": 3}


def _site(host: str) -> str:
    """Registrable name: the label before the public suffix. Every suffix used here is one label."""
    return host.casefold().split(":")[0].split(".")[-2]


def _task_sites(task: dict) -> set[str]:
    hosts = {urlsplit(task["start_url"]).netloc} if task.get("start_url", "").startswith("http") else set()
    host = (task.get("end_markers") or {}).get("host")
    hosts.update(host if isinstance(host, list) else [host] if host else [])
    return {_site(item) for item in hosts if "." in item}


def test_heldout3b_split_has_thirty_unique_complete_tasks():
    tasks = tasks_for_split("heldout3b")
    assert resolve_task_split("heldout3b") == "heldout3b"
    assert len(tasks) == len(HELDOUT3B_TASK_IDS) == 30
    ids = [task["id"] for task in tasks]
    assert tuple(ids) == HELDOUT3B_TASK_IDS
    catalog_ids = [task["id"] for task in get_all_tasks()]
    assert all(catalog_ids.count(task_id) == 1 for task_id in ids)
    assert Counter(task_id.split("_")[1] for task_id in ids) == KINDS
    required = {"id", "description", "start_url", "expected_answer", "check_url_contains", "end_markers"}
    for task in tasks:
        assert re.fullmatch(r"ho3b_[a-z]+_[a-z0-9_]+", task["id"])
        assert required <= task.keys()
        assert all(task[key] for key in required)
        assert task["start_url"].startswith("https://")
        markers = task["end_markers"]
        assert {"host", "url_contains", "path_suffix", "deny"} <= markers.keys()
        assert task["check_url_contains"] in markers["url_contains"]
        assert "https://" not in task["description"]
        assert markers["url_contains"] not in task["description"]
        assert not re.search(r"(?<!\w)" + re.escape(task["expected_answer"]) + r"(?!\w)", task["description"], re.I)


def test_heldout3b_domains_are_new_late_alphabet_and_capped_per_site():
    tasks = tasks_for_split("heldout3b")
    new_ids = set(HELDOUT3B_TASK_IDS)
    old_sites = set().union(*(_task_sites(task) for task in get_all_tasks() if task["id"] not in new_ids))
    per_site = Counter()
    for task in tasks:
        sites = _task_sites(task)
        assert len(sites) == 1, (task["id"], sites)
        site = sites.pop()
        assert "n" <= site[0] <= "z", (task["id"], site)
        assert site not in old_sites, (task["id"], site)
        per_site[site] += 1
    assert max(per_site.values()) <= 3, per_site


def test_heldout3b_does_not_change_existing_splits_or_reuse_end_pages():
    tasks = tasks_for_split("heldout3b")
    new_ids = set(HELDOUT3B_TASK_IDS)
    for name in ("probe", "dev", "held-out", "honest", "heldout2"):
        assert new_ids.isdisjoint(task["id"] for task in tasks_for_split(name))
    ends = [(task["end_markers"]["host"], task["end_markers"]["url_contains"]) for task in tasks]
    assert len(set(ends)) == 30


def test_heldout3b_value_markers_require_the_requested_value_not_a_heading():
    # Synthetic evidence checks marker wiring, not live-page availability.
    # Real pages, wrong pages and wrong values are in bench.verify_heldout3_b.
    for task in tasks_for_split("heldout3b"):
        markers = task["end_markers"]
        kind = task["id"].split("_")[1]
        if kind in ("nav", "search"):
            assert "answer_in_text" not in markers
            continue
        assert markers["answer_in_text"] in task["expected_answer"]
        path = markers["url_contains"] if markers["url_contains"].startswith("/") else "/"
        assert path.endswith(markers["path_suffix"]), task["id"]
        evidence = PageEvidence(
            url="https://" + markers["host"] + path + ("?q=x" if markers.get("query_nonempty") else ""),
            h1="Unrelated page heading",
            text="Unrelated page heading\n" + task["expected_answer"],
        )
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=task["expected_answer"])).verdict == "PASS", task["id"]
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=evidence.h1)).verdict == "FAIL", task["id"]


def test_heldout3b_dry_plan_lists_tasks_without_a_spend_ledger(monkeypatch):
    from bench.probe import LedgerMissing, SpendLedger, plan_probe

    def missing_ledger(*args, **kwargs):
        raise LedgerMissing("No shared ledger on this offline machine")

    monkeypatch.setattr(SpendLedger, "load", missing_ledger)
    plan = plan_probe(split="heldout3b")
    assert plan["execute"] is False
    assert plan["split"] == "heldout3b"
    assert plan["tasks"] == list(HELDOUT3B_TASK_IDS)
    assert plan["project_spent_usd"] is None
