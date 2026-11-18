"""Offline extval invariants: selection replay, disjointness, site caps, v2 keys, pre-registration hash."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

from bench.browser_use_arm import task_text
from bench.ext_sample import SOURCES, assigned_set, effective_authoring_decisions, registrable, task_fingerprint
from bench.grade import _fold_v2, _phrase_at_boundary, _v2_alternatives, _v2_key_problem, grade_observation
from bench.tasks import EXTDEV_TASK_IDS, EXTVAL_TASK_IDS, get_all_tasks, resolve_task_split, task_message, tasks_for_split

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "docs/results/ext_sample_20261116"
EXTVAL = ROOT / "docs/results/extval_20261118"
QUOTAS = dict(zip(SOURCES, (7, 7, 2, 2, 0)))
TOTAL, SITE_CAP = 18, 2
MANUAL = {"not_read_only", "volatile", "site_gone_or_content_gone", "captcha_or_bot_block", "unverifiable", "no_checkable_key"}
AUTOMATIC = {"catalog_task", "duplicate_task", "site_cap"}


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line.strip()]


def canonical_sha256(tasks):
    rows = [{k: t[k] for k in ("id", "description", "start_url", "key_v2")} for t in tasks]
    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def fingerprint(row):
    return task_fingerprint(row["task_text"], row["site"], row["start_url"])


CANDIDATES = read(SAMPLE / "candidates_extdev.jsonl")
BY_KEY = {(r["source"], r["source_id"]): r for r in CANDIDATES}
LEDGER = read(EXTVAL / "authoring_decisions.jsonl")
DECISIONS = effective_authoring_decisions(LEDGER)
FINAL_URL = {r["task_id"]: r["final_url"] for r in DECISIONS if r["disposition"] == "accepted"}
TASKS = tasks_for_split("extval")


def test_split_ids_and_schema():
    assert resolve_task_split("extval") == "extval"
    assert tuple(t["id"] for t in TASKS) == EXTVAL_TASK_IDS
    assert len(TASKS) == len(set(EXTVAL_TASK_IDS)) == TOTAL
    catalog = Counter(t["id"] for t in get_all_tasks())
    for task in TASKS:
        assert catalog[task["id"]] == 1 and task["id"].startswith(f"extval_{task['kind']}_")
        assert {"description", "start_url", "kind", "source", "source_id", "licence", "text_edits", "key_v2"} <= task.keys()
        row = BY_KEY[task["source"], task["source_id"]]
        assert task["start_url"] == row["start_url"]
        assert task["text_edits"] == [] and task["description"] == row["task_text"]
        assert task["licence"] == ("CC-BY-4.0" if task["source"] in {"Mind2Web-Live", "Mind2Web"} else "Apache-2.0")


def test_ledger_is_complete_and_matches_the_tasks():
    assert all(r["note"] and "\n" not in r["note"] for r in LEDGER)
    assert len(DECISIONS) == len({(r["source"], r["source_id"]) for r in DECISIONS})
    for row in DECISIONS:
        assert (row["source"], row["source_id"]) in BY_KEY and BY_KEY[row["source"], row["source_id"]]["rank"] == row["rank"]
        if row["disposition"] == "accepted":
            assert row["reason"] == "" and row["final_url"].startswith(("http://", "https://"))
        else:
            assert row["disposition"] == "rejected" and row["reason"] in MANUAL | AUTOMATIC
            if row["reason"] in AUTOMATIC and row["reason"] != "catalog_task":
                assert row["note"].startswith("automatic:")
    accepted = [r["task_id"] for r in LEDGER if r["disposition"] == "accepted"]
    assert accepted == list(EXTVAL_TASK_IDS)
    for task in TASKS:
        row = next(r for r in DECISIONS if r.get("task_id") == task["id"])
        assert (row["source"], row["source_id"]) == (task["source"], task["source_id"])


def test_walk_replays_the_preregistered_order_quotas_and_caps():
    """Rebuild the walk from candidates_extdev.jsonl: every decided row, in order, and the automatic reasons."""
    manual = {(r["source"], r["source_id"]): r for r in DECISIONS}
    extdev_kept = {(r["source"], r["source_id"]) for r in effective_authoring_decisions(read(SAMPLE / "authoring_extdev.jsonl"))
                   if r["disposition"] == "kept"}
    catalog = {task_fingerprint(t.get("description", ""), registrable(urlsplit(t.get("start_url", "")).hostname or ""),
                                t.get("start_url", "")) for t in get_all_tasks() if not t["id"].startswith("extval_")}
    catalog.update(fingerprint(r) for name in ("candidates_heldout4.jsonl", "candidates_heldout4_step2.jsonl")
                   for r in read(SAMPLE / name))
    order = [("quota", r) for s in SOURCES[:-1] for r in sorted((r for r in CANDIDATES if r["source"] == s), key=lambda r: r["rank"])]
    order += [("fill", r) for s in SOURCES for r in sorted((r for r in CANDIDATES if r["source"] == s), key=lambda r: r["rank"])]
    walked, accepted = [], []
    for phase, row in order:
        key = (row["source"], row["source_id"])
        if len(accepted) == TOTAL:
            break
        if key in {(w["source"], w["source_id"]) for w in walked}:
            continue
        if phase == "quota" and sum(a["source"] == row["source"] for a in accepted) >= QUOTAS[row["source"]]:
            continue
        decision = manual[key]
        assert decision["phase"] == phase, key
        if key in extdev_kept or fingerprint(row) in catalog:
            assert decision["reason"] == "catalog_task" and decision["note"].startswith("automatic:"), key
        elif any(fingerprint(BY_KEY[a["source"], a["source_id"]]) == fingerprint(row) for a in accepted):
            assert decision["reason"] == "duplicate_task", key
        elif sum(a["site"] == row["site"] for a in accepted) >= SITE_CAP:
            assert decision["reason"] == "site_cap", key
        else:
            assert decision["reason"] not in {"duplicate_task", "site_cap"}, key
            assert decision["reason"] != "catalog_task" or decision["note"].startswith("manual:"), key
        walked.append(decision)
        if decision["disposition"] == "accepted":
            accepted.append(decision)
    assert len(accepted) == TOTAL
    first_lines = list({(r["source"], r["source_id"]): r for r in reversed(LEDGER)}.values())[::-1]
    assert [(r["source"], r["source_id"]) for r in walked] == [(r["source"], r["source_id"]) for r in first_lines]


def test_disjoint_from_catalog_and_heldout4_and_only_extdev_sites():
    others = [t for t in get_all_tasks() if not t["id"].startswith("extval_")]
    other_ids = {t["id"] for t in others}
    other_fps = {task_fingerprint(t.get("description", ""), registrable(urlsplit(t.get("start_url", "")).hostname or ""),
                                  t.get("start_url", "")) for t in others}
    heldout4 = [r for name in ("candidates_heldout4.jsonl", "candidates_heldout4_step2.jsonl") for r in read(SAMPLE / name)]
    extdev = {(t["source"], t["source_id"]) for t in others if t["id"] in EXTDEV_TASK_IDS}
    sites = Counter()
    for task in TASKS:
        row = BY_KEY[task["source"], task["source_id"]]
        assert task["id"] not in other_ids and (task["source"], task["source_id"]) not in extdev
        assert fingerprint(row) not in other_fps
        assert fingerprint(row) not in {fingerprint(r) for r in heldout4}
        hosts = task["key_v2"]["host"] if isinstance(task["key_v2"]["host"], list) else [task["key_v2"]["host"]]
        task_sites = {row["site"], registrable(urlsplit(task["start_url"]).hostname)} | {registrable(h) for h in hosts}
        assert task_sites == {row["site"]}
        assert assigned_set(row["site"]) == "extdev"
        assert row["site"] not in {r["site"] for r in heldout4}
        sites[row["site"]] += 1
    assert max(sites.values()) <= SITE_CAP


def test_keys_are_judge_only():
    for task in TASKS:
        key = task["key_v2"]
        description = _fold_v2(task["description"])
        assert _fold_v2(key["reference"]) not in description
        for fact in key.get("facts", []):
            groups, _ = _v2_alternatives(fact)
            for group in groups:
                assert not all(_phrase_at_boundary(_fold_v2(item), description) for item in group), (task["id"], group)
    task = dict(TASKS[0])
    expected = task_message(task["description"], task["start_url"])
    for field in ("key_v2", "source", "source_id", "licence", "text_edits", "kind"):
        task[field] = "PRIVATE_JUDGE_ONLY_SENTINEL"
    assert task_text(task) == expected and "PRIVATE_JUDGE_ONLY_SENTINEL" not in task_text(task)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t["id"])
def test_v2_key_valid_reference_passes_and_decoys_fail(task):
    key = task["key_v2"]
    assert _v2_key_problem(key) is False
    assert key["deliverable"] in ("answer", "page", "both") and key.get("basis")
    final = FINAL_URL[task["id"]]
    phrases = [p for page in key.get("pages", []) for p in page.get("text", [])]
    text = "\n".join([key["reference"], *phrases])
    parts = urlsplit(final)
    wrong_host = urlunsplit((parts.scheme, "www.example.org", parts.path, parts.query, ""))
    assert grade_observation(task, final, text, answer=key["reference"])[0] is True
    assert grade_observation(task, final, text, answer="")[0] is False
    assert grade_observation(task, final, text, answer="Task failed: I could not finish.")[0] is False
    assert grade_observation(task, final, text, answer="I was unable to find it on the site.")[0] is False
    assert grade_observation(task, wrong_host, text, answer=key["reference"])[0] is False
    assert grade_observation(task, "https://example.com/", text, answer=key["reference"])[0] is False
    assert grade_observation(task, "", "", answer="")[0] is False
    if key["deliverable"] in ("answer", "both"):
        assert grade_observation(task, final, text, answer="Wrong value")[0] is False
        numeric = [f for f in key["facts"] if all(any(re.search(r"\d", item) for item in group) for group in _v2_alternatives(f)[0])]
        if numeric:  # the reference with every digit shifted: right shape, wrong numbers
            shifted = re.sub(r"\d", lambda m: str((int(m.group()) + 1) % 10), key["reference"])
            assert grade_observation(task, final, text, answer=shifted)[0] is False
    if key["deliverable"] in ("page", "both"):
        assert grade_observation(task, task["start_url"], text, answer=key["reference"])[0] is False


NEAR_MISSES = {  # task id -> (final URL, page text, answer): one requirement short of a pass
    "extval_nav_nfl_super_bowl_2015_scoreboard": ("https://www.espn.com/nfl/scoreboard/_/year/2014/seasontype/3/week/4", "Pro Bowl FINAL", "Pro Bowl"),
    "extval_filter_spothero_wheelchair_times_square": ("https://spothero.com/search?kind=destination&id=746&view=dl&spot-id=19488",
                                                        "Amenities Valet Garage - Covered On-Site Staff", "216 W 45th St."),
    "extval_filter_amazon_gaming_desktop": ("https://www.amazon.com/s?k=gaming+desktop&rh=p_n_g-1004209391091%3A5446812011", "", "results"),
    "extval_filter_amazon_womens_hiking_boots": ("https://www.amazon.com/s?k=women%27s+hiking+boots&rh=p_72%3A2661618011%2Cp_n_g-1003509617111%3A32912228011",
                                                 "", "results"),
    "extval_nav_real_madrid_ucl_schedule": ("https://www.espn.com/soccer/team/fixtures/_/id/86/esp.real_madrid", "", "fixtures"),
    "extval_nav_darienlake_gift_shops": ("https://www.sixflags.com/darienlake/rides", "", "rides"),
    "extval_nav_spothero_love_field": ("https://spothero.com/search?kind=airport&id=DFW&airport=true", "", "DFW parking"),
    "extval_value_icse_2002_deadlines": (None, "", "Technical papers: 10 September 2001; doctoral symposium: January 6, 2002"),
    "extval_value_kingdom_rush_prize_comic": (None, "", "A trip to GDC; the Kingdom Rush comic"),
    "extval_value_hf_trainer_parameters": (None, "", "model, args, train_dataset, tokenizer"),
    "extval_value_cambridge_feel_giddy_synonyms": (None, "", "feel dizzy; whirl; spin"),
    "extval_value_cambridge_present_perfect": (None, "", "I've been there a couple of times before. We haven't met before."),
    "extval_value_roviocon_theme_series": (None, "", "Slingshot to Stardom; The Angry Birds Movie 3"),
    "extval_value_junkworld_launch_update": (None, "", "September 22, 2023; Underground Part 2"),
}


@pytest.mark.parametrize("task_id", sorted(NEAR_MISSES))
def test_near_misses_fail(task_id):
    task = next(t for t in TASKS if t["id"] == task_id)
    url, text, answer = NEAR_MISSES[task_id]
    assert grade_observation(task, url or FINAL_URL[task_id], text or answer, answer=answer)[0] is False


def test_preregistered_canonical_hash_matches_readme():
    readme = (EXTVAL / "README.md").read_text(encoding="utf8")
    found = re.findall(r"Canonical SHA-256: `([0-9a-f]{64})`", readme)
    assert found == [canonical_sha256(TASKS)]
    for task_id in EXTVAL_TASK_IDS:
        assert f"`{task_id}`" in readme
        assert f"`{task_id}`" in (EXTVAL / "KEYS.md").read_text(encoding="utf8")
