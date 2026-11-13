"""Offline catalog checks for heldout3a. No browser and no model call."""

import re
from urllib.parse import urlsplit

from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict
from bench.tasks import (
    HELDOUT3A_TASK_IDS,
    get_all_tasks,
    resolve_task_split,
    tasks_for_split,
)

_KINDS = {
    "nav": 8,
    "value": 8,
    "search": 4,
    "form": 4,
    "js": 3,
    "title": 3,
}
_PUBLIC_SUFFIX = {"com", "org", "net", "gov", "edu", "io", "dev", "se"}


def _registrable(host: str) -> str:
    name = host.lower().split(":")[0]
    if name.startswith("www."):
        name = name[4:]
    labels = [part for part in name.split(".") if part]
    if len(labels) >= 2 and labels[-1] in _PUBLIC_SUFFIX:
        return labels[-2]
    return labels[0]


def _hosts(task: dict) -> list[str]:
    host = (task.get("end_markers") or {}).get("host") or ""
    if isinstance(host, list):
        return [str(item) for item in host if item]
    return [host] if host else []


def _canonical(task: dict) -> str:
    markers = task["end_markers"]
    host = markers["host"]
    token = markers["url_contains"]
    if token.startswith("/"):
        suffix = markers["path_suffix"]
        return "https://" + host + (suffix if suffix.startswith(token) else token)
    path = markers["path_suffix"]
    if not path.startswith("/"):
        path = "/" + path
    url = "https://" + host + path
    if token.startswith("#"):
        return url + token
    if token not in url:
        return url + ("&" if "?" in url else "?") + token
    return url


def _slash_variant(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path
    if path.endswith("/"):
        path = path[:-1] or "/"
    else:
        path = path + "/"
    return parts._replace(path=path).geturl()


def test_heldout3a_split_lists_thirty_tasks():
    tasks = tasks_for_split("heldout3a")
    assert resolve_task_split("heldout3a") == "heldout3a"
    assert resolve_task_split("heldout3_a") == "heldout3a"
    assert len(tasks) == len(HELDOUT3A_TASK_IDS) == 30
    ids = [task["id"] for task in tasks]
    assert tuple(ids) == HELDOUT3A_TASK_IDS
    assert len(set(ids)) == 30
    catalog = [task["id"] for task in get_all_tasks()]
    assert all(catalog.count(task_id) == 1 for task_id in ids)
    required = {"id", "description", "start_url", "expected_answer", "check_url_contains", "end_markers"}
    for task in tasks:
        assert required <= task.keys()
        assert all(task[key] for key in required)
        assert task["id"].startswith("ho3a_")
        kind = task["id"].split("_")[1]
        assert kind in _KINDS
        assert task["start_url"].startswith("https://")
        assert "https://" not in task["description"]
        markers = task["end_markers"]
        assert {"host", "url_contains", "path_suffix", "deny", "answer_in_text"} <= markers.keys()
        assert task["check_url_contains"] in markers["url_contains"]
        assert markers["answer_in_text"] == task["expected_answer"]
        assert markers["path_suffix"] or markers["url_contains"].startswith("/")
        if markers["path_suffix"]:
            assert markers["path_suffix"] not in task["description"]
            assert markers["path_suffix"] not in task["start_url"]
        assert markers["url_contains"] not in task["description"]
        assert markers["url_contains"] not in task["start_url"]
        assert task["expected_answer"] not in task["start_url"]
        assert not re.search(
            r"(?<!\w)" + re.escape(task["expected_answer"]) + r"(?!\w)",
            task["description"],
            re.I,
        )
    for kind, count in _KINDS.items():
        assert sum(task["id"].startswith(f"ho3a_{kind}_") for task in tasks) == count


def test_heldout3a_domains_are_new_and_start_with_a_through_m():
    tasks = tasks_for_split("heldout3a")
    new_ids = set(HELDOUT3A_TASK_IDS)
    older = [task for task in get_all_tasks() if task["id"] not in new_ids]
    used = set()
    for task in older:
        if task.get("start_url", "").startswith("http"):
            used.add(_registrable(urlsplit(task["start_url"]).netloc))
        for host in _hosts(task):
            used.add(_registrable(host))
    fresh = set()
    for task in tasks:
        names = {_registrable(urlsplit(task["start_url"]).netloc)}
        names.update(_registrable(host) for host in _hosts(task))
        for name in names:
            assert "a" <= name[0] <= "m", (task["id"], name)
            assert name not in used, (task["id"], name)
            fresh.add(name)
    assert fresh.isdisjoint(used)
    for name in ("probe", "dev", "held-out", "honest", "heldout2"):
        assert new_ids.isdisjoint(task["id"] for task in tasks_for_split(name))


def test_heldout3a_markers_accept_slash_and_fragment_and_reject_wrong_pages():
    for task in tasks_for_split("heldout3a"):
        markers = task["end_markers"]
        answer = task["expected_answer"]
        url = _canonical(task)
        evidence = PageEvidence(url=url, h1="Unrelated heading", text="Unrelated heading\n" + answer)
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=answer)).verdict == "PASS", task["id"]
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer="not-the-right-value")).verdict == "FAIL"
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer="Unrelated heading")).verdict == "FAIL"
        wrong = evidence_verdict(
            markers,
            PageEvidence(url="https://example.com/not-the-right-page", h1="Unrelated heading", text=evidence.text),
            ClaimedEvidence(answer=answer),
        )
        assert wrong.verdict == "FAIL", task["id"]
        same_host = urlsplit(url)._replace(path="/not-the-right-page", query="", fragment="").geturl()
        assert evidence_verdict(
            markers,
            PageEvidence(url=same_host, text=evidence.text),
            ClaimedEvidence(answer=answer),
        ).verdict == "FAIL", (task["id"], same_host)
        if "#" not in url:
            hashed = url + "#section"
        else:
            hashed = url
        assert evidence_verdict(
            markers,
            PageEvidence(url=hashed, text=evidence.text),
            ClaimedEvidence(answer=answer),
        ).verdict == "PASS", task["id"]
        # The grader's path_suffix is strict. The live checker loads the
        # slash-toggled form of each directory URL and requires that page to pass.
        if not markers["path_suffix"]:
            # A slash-tolerant marker: both forms pass, a sibling page fails.
            assert evidence_verdict(
                markers,
                PageEvidence(url=_slash_variant(url), text=evidence.text),
                ClaimedEvidence(answer=answer),
            ).verdict == "PASS", task["id"]
            sibling = url.rstrip("/").rsplit("/", 1)[0] + "/not-the-right-page"
            assert evidence_verdict(
                markers,
                PageEvidence(url=sibling, text=evidence.text),
                ClaimedEvidence(answer=answer),
            ).verdict == "FAIL", (task["id"], sibling)
            continue
        child = _slash_variant(url).rstrip("/") + "/not-a-child"
        assert evidence_verdict(
            markers,
            PageEvidence(url=child, text=evidence.text),
            ClaimedEvidence(answer=answer),
        ).verdict == "FAIL", (task["id"], child)


def test_heldout3a_uses_at_most_three_tasks_per_site():
    counts = {}
    for task in tasks_for_split("heldout3a"):
        names = {_registrable(urlsplit(task["start_url"]).netloc)}
        names.update(_registrable(host) for host in _hosts(task))
        for name in names:
            counts[name] = counts.get(name, 0) + 1
    assert max(counts.values()) <= 3, counts


def test_heldout3a_dry_plan_lists_tasks_without_a_spend_ledger(monkeypatch):
    from bench.probe import LedgerMissing, SpendLedger, plan_probe

    def missing_ledger(*args, **kwargs):
        raise LedgerMissing("No shared ledger on this offline machine")

    monkeypatch.setattr(SpendLedger, "load", missing_ledger)
    plan = plan_probe(split="heldout3a")
    assert plan["execute"] is False
    assert plan["split"] == "heldout3a"
    assert plan["tasks"] == list(HELDOUT3A_TASK_IDS)
    assert plan["project_spent_usd"] is None
