"""Offline extdev provenance, split, partial-key and grading invariants."""

import asyncio
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from bench.browser_use_arm import task_text
from bench.ext_sample import QUOTAS, SOURCES, authoring_reserve, effective_authoring_decisions, task_fingerprint
from bench.grade import ClaimedEvidence, PageEvidence, evidence_verdict, grade_observation
from bench.tasks import EXTDEV_TASK_IDS, get_all_tasks, resolve_task_split, task_message, tasks_for_split
from tests.test_dev3 import registrable

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/ext_sample_20261116"
KINDS = {"nav", "value", "search", "filter", "spa", "multisite"}
EXCLUSIONS = {"login", "payment", "captcha_or_bot_block", "site_gone_or_content_gone", "volatile_lt_1day", "no_checkable_key", "site_cap", "duplicate_task"}


def read(name):
    return [json.loads(line) for line in (RESULTS / name).read_text().splitlines()]


def sites(task):
    hosts = {urlsplit(task["start_url"]).hostname}
    marker = task["end_markers"]["host"]
    hosts.update(marker if isinstance(marker, list) else [marker])
    return {registrable(host) for host in hosts if host}


def test_schema_ids_split_and_provenance():
    tasks = tasks_for_split("extdev")
    assert resolve_task_split("extdev") == "extdev"
    assert tuple(t["id"] for t in tasks) == EXTDEV_TASK_IDS
    assert len(tasks) == len(set(EXTDEV_TASK_IDS)) == 40
    catalog = Counter(t["id"] for t in get_all_tasks())
    candidates = {(r["source"], r["source_id"]): r for r in read("candidates_extdev.jsonl")}
    for task in tasks:
        assert task["id"].startswith("extdev_") and catalog[task["id"]] == 1
        assert task["kind"] in KINDS and task["id"].split("_")[1] == task["kind"]
        assert {"description", "start_url", "expected_answer", "check_url_contains", "end_markers", "source", "source_id", "licence", "text_edits", "reproducer", "key_scope", "unchecked_fragments"} <= task.keys()
        candidate = candidates[task["source"], task["source_id"]]
        assert task["description"] == candidate["task_text"]
        assert task["start_url"] == candidate["start_url"]
        assert task["text_edits"] == []
        assert task["licence"] == ("CC-BY-4.0" if task["source"] in {"Mind2Web-Live", "Mind2Web"} else "Apache-2.0")
        assert task["reproducer"] in {"script", "none"}
        assert task["key_scope"] in {"full", "partial"}
        assert isinstance(task["unchecked_fragments"], list)
        assert bool(task["unchecked_fragments"]) == (task["key_scope"] == "partial")
        assert all(isinstance(s, str) and s for s in task["unchecked_fragments"])
        assert {"host", "url_contains", "deny", "answer_in_text"} <= task["end_markers"].keys()
        assert task["expected_answer"] == task["end_markers"]["answer_in_text"]
        assert task["check_url_contains"] == task["end_markers"]["url_contains"]


def test_site_cap_and_disjoint_from_every_other_catalog_task_and_heldout4():
    tasks = tasks_for_split("extdev")
    used = set().union(*(sites(t) for t in tasks))
    counts = Counter(site for task in tasks for site in sites(task))
    assert max(counts.values()) <= 3
    for task in get_all_tasks():
        if task["id"] in EXTDEV_TASK_IDS:
            continue
        hosts = {urlsplit(task.get("start_url", "")).hostname}
        host = (task.get("end_markers") or {}).get("host")
        hosts.update(host if isinstance(host, (list, tuple)) else [host])
        assert used.isdisjoint(registrable(h) for h in hosts if h), task["id"]
    assert used.isdisjoint(r["site"] for r in read("candidates_heldout4.jsonl"))


def test_effective_authoring_decisions_and_preserved_history():
    candidates = read("candidates_extdev.jsonl")
    history = read("authoring_extdev.jsonl")
    original = read("authoring_extdev_step2.jsonl")
    assert history[:len(original)] == original
    ledger = effective_authoring_decisions(history)
    key = lambda r: (r["source"], r["source_id"], r["site"], r["rank"])
    assert set(map(key, ledger)) <= set(map(key, candidates))
    assert len(ledger) == len(set(map(key, ledger)))
    tasks = {t["id"]: t for t in tasks_for_split("extdev")}
    for row in ledger:
        assert row["note"] and "\n" not in row["note"]
        if row["disposition"] == "excluded":
            assert row["reason"] in EXCLUSIONS
            if row["reason"] == "no_checkable_key":
                assert row["note"].startswith(("computed:", "ungradeable_end_state:"))
            if row["reason"] == "duplicate_task":
                accepted = next(t for task_id, t in tasks.items() if task_id in row["note"])
                candidate = next(r for r in candidates if key(r) == key(row))
                assert task_fingerprint(candidate["task_text"], candidate["site"], candidate["start_url"]) == task_fingerprint(accepted["description"], candidate["site"], accepted["start_url"])
        else:
            assert row["disposition"] == "kept" and not row["reason"]
            task = tasks[row["task_id"]]
            assert row["key_scope"] == task["key_scope"]
            assert row["unchecked_fragments"] == task["unchecked_fragments"]
    assert len([r for r in ledger if r["disposition"] == "kept"]) == len(tasks)
    assert "Quota fill audit" in next(r["note"] for r in ledger if r.get("task_id") == "extdev_value_hf_tei_strengths")
    revised = [r for r in ledger if r["note"].startswith("revised:")]
    assert len(revised) == 5
    assert all(r["disposition"] == "kept" and r["key_scope"] == "partial" for r in revised)
    assert len([r for r in ledger if r["reason"] == "no_checkable_key" and r["note"].startswith("computed:")]) == 4
    assert len([r for r in ledger if r["reason"] == "no_checkable_key" and r["note"].startswith("ungradeable_end_state:")]) == 7


def test_authoring_history_replays_quotas_rank_order_and_accepted_only_caps():
    candidates = read("candidates_extdev.jsonl")
    original = read("authoring_extdev_step2.jsonl")
    history = read("authoring_extdev.jsonl")
    latest = {(r["source"], r["source_id"]): r for r in effective_authoring_decisions(history)}
    decisions = [r for r in original if not r["note"].startswith("multi_page_answer:")]
    additions = []

    def accept(row, automatic):
        decision = latest[row["source"], row["source_id"]]
        if automatic:
            assert decision["reason"] == automatic
        additions.append(decision)
        decisions.append(decision)

    def count(source=None):
        return sum(r["disposition"] == "kept" and (source is None or r["source"] == source) for r in decisions)

    for source in SOURCES[:-1]:
        for row, automatic in authoring_reserve(candidates, decisions):
            if row["source"] != source:
                continue
            if count(source) >= QUOTAS["extdev"][source]:
                break
            accept(row, automatic)
    for row, automatic in authoring_reserve(candidates, decisions):
        if count() == 40:
            break
        accept(row, automatic)
    assert count() == 40
    assert additions == effective_authoring_decisions(history[len(original):])


@pytest.mark.parametrize("task", tasks_for_split("extdev"), ids=lambda t: t["id"])
def test_existing_grader_normal_empty_wrong_and_decoy_cases(task):
    from bench.verify_extdev import negative_url, reference_answer, synthetic_reference

    final = next(r["final_url"] for r in effective_authoring_decisions(read("authoring_extdev.jsonl")) if r.get("task_id") == task["id"])
    text = "\n".join(task.get("answer_parts") or [reference_answer(task)])
    assert synthetic_reference(task, final)[0] is True
    assert grade_observation(task, final, text, answer="")[0] is False
    assert grade_observation(task, final, text, answer="Wrong value")[0] is False
    assert grade_observation(task, negative_url(task, final), text, answer=reference_answer(task))[0] is False
    assert grade_observation(task, "", "", answer="")[0] is False
    if task.get("url_answer_ok"):
        assert task["kind"] == "nav"
        assert grade_observation(task, final, text, answer=final)[0] is True
    if "answer_parts" in task:
        assert task["answer_parts"] == [task["expected_answer"], *task["unchecked_fragments"]]
        assert task["full_answer"] == "; ".join(task["answer_parts"])


def test_corrected_keys_preserve_history_and_query_parameter_order():
    history = read("authoring_extdev.jsonl")
    revisions = [r for r in history if r["note"].startswith("rekeyed:")]
    assert len(revisions) == 5
    for revision in revisions:
        prior = next(r for r in history if r.get("task_id") == revision["task_id"])
        assert prior is not revision and prior["final_url"] == revision["previous_key"]["final_url"]
    task = next(t for t in tasks_for_split("extdev") if t["id"].endswith("green_xbox_controller"))
    evidence = PageEvidence(url="https://www.amazon.com/s?rh=p_72%3A1248885011&k=Xbox+Wireless+controller+green", text=task["expected_answer"])
    assert evidence_verdict(task["end_markers"], evidence, ClaimedEvidence(answer=task["expected_answer"])).verdict == "PASS"


def test_new_answer_keys_only_reuse_authored_values_and_conservative_page_flags():
    tasks = tasks_for_split("extdev")
    assert sum("answer_parts" in t for t in tasks) == 30
    assert sum("full_answer" in t for t in tasks) == 32
    flagged = {t["id"].removeprefix("extdev_nav_") for t in tasks if t.get("url_answer_ok")}
    assert flagged == {"ronaldo_world_cup_stats", "nets_schedule", "spothero_marketing",
                       "eventbrite_planning", "commuter_benefits"}
    for task in tasks:
        if "full_answer" in task:
            assert task["full_answer"] == "; ".join(task.get("answer_parts") or [task["expected_answer"]])
        if task.get("url_answer_ok"):
            assert task["kind"] == "nav"


def test_prompt_boundary_selects_only_description_and_start_url():
    task = dict(tasks_for_split("extdev")[0])
    expected = task_message(task["description"], task["start_url"])
    for field in ("end_markers", "source", "source_id", "licence", "text_edits", "reproducer", "key_scope", "unchecked_fragments", "full_answer", "answer_parts", "url_answer_ok"):
        task[field] = "PRIVATE_JUDGE_ONLY_SENTINEL"
    assert task_text(task) == expected
    assert "PRIVATE_JUDGE_ONLY_SENTINEL" not in task_text(task)


def test_verifier_summary_and_errors_are_not_successful_negatives():
    from bench.verify_extdev import grade, reproduce, summary

    task = tasks_for_split("extdev")[0]
    row = {"key": False, "reproducer": False, "negatives": []}
    result = summary([row], [task])
    assert result[:3] == ["Key checks: 0/1 PASS", "Reproducers: 0/1 PASS; 0 none", "Negatives: 0/2 correctly FAIL"]

    class BrokenPage:
        async def goto(self, *args, **kwargs):
            raise RuntimeError("network unavailable")

    with pytest.raises(RuntimeError, match="network unavailable"):
        asyncio.run(reproduce(BrokenPage(), task))
    assert callable(grade)
