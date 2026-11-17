"""Model-free sampler tests; no network or browser required."""

import asyncio
from collections import Counter
from pathlib import Path

import pytest

from bench.ext_sample import (
    QUOTAS, SEED, SOURCES, assigned_set, classify, digest, existing_sites,
    authoring_reserve, effective_authoring_decisions, normalize, registrable, sample, task_fingerprint,
)


def test_registrable_matches_dev3():
    from tests.test_dev3 import registrable as reference

    for host in ("www.example.co.uk", "example.org", "a.github.io", "WWW.EXAMPLE.COM."):
        assert registrable(host) == reference(host)


def test_raw_pool_is_complete_verbatim_and_has_keys():
    import json

    directory = Path(__file__).resolve().parents[1] / "bench/ext_sources"
    rows = normalize(directory)
    assert Counter(row["source"] for row in rows) == dict(zip(SOURCES, (542, 680, 643, 33, 1009)))
    originals = [json.loads(line) for line in (directory / "ab_dev.jsonl").read_text().splitlines()]
    by_id = {r["source_id"]: r for r in rows if r["source"] == "AssistantBench"}
    for original in originals:
        row = by_id[original["id"]]
        assert row["task_text"] == original["task"]
        assert row["source_key"]["gold_url"] == original["gold_url"]
        assert row["non_text_edits"] and row["start_url"].endswith("/")
    for row in rows:
        assert row["source_key"]
        assert assigned_set(row["site"]) == ("extdev" if int(digest(f"{SEED}:site:{row['site']}"), 16) % 4 == 0 else "heldout4")
    assert "wikipedia.org" in existing_sites()


@pytest.mark.parametrize("status,title,text,error,expected", [
    (200, "Home", "Useful human written content " * 10, "", "ok"),
    (200, "Home", "Documentation about Cloudflare " * 100, "", "ok"),
    (200, "", "", "", "captcha_or_bot_block"),
    (403, "Access Denied", "Please verify you are human", "", "captcha_or_bot_block"),
    (503, "Just a moment", "Cloudflare challenge", "", "captcha_or_bot_block"),
    (404, "Missing", "Not found", "", "site_gone_or_content_gone"),
    (410, "Gone", "", "", "site_gone_or_content_gone"),
    (200, "Domain for sale", "Buy this domain " * 10, "", "site_gone_or_content_gone"),
    (None, "", "", "net::ERR_NAME_NOT_RESOLVED", "site_gone_or_content_gone"),
    (None, "", "", "net::ERR_TIMED_OUT", "unreachable"),
])
def test_classify(status, title, text, error, expected):
    assert classify(status, title, text, error) == expected


def test_sample_order_caps_overlap_language_quota_and_cache():
    rows = []
    for source in SOURCES:
        for i in range(100):
            site = f"example{i}.org"
            for j in range(4):
                rows.append(dict(source=source, source_id=f"{i}:{j}", site=site,
                                 start_url=f"https://{site}/{j}", lang="de" if i == 1 else "en"))
    calls, saves = [], []

    async def screen(url):
        calls.append(url)
        return {"classification": "site_gone_or_content_gone" if "example2.org" in url else "ok"}

    cache = {}
    quotas = {name: {source: 2 for source in SOURCES} for name in QUOTAS}
    ledger, candidates = asyncio.run(sample(rows, screen, cache, lambda c: saves.append(len(c)), {"example0.org"}, quotas))
    assert {r["reason"] for r in ledger} >= {"domain_overlap", "non_english", None}
    assert not {"site_cap", "quota_full"} & {r["reason"] for r in ledger}
    assert len(calls) == len(cache) == len(saves)
    assert max(Counter(r["site"] for group in candidates.values() for r in group).values()) > 3
    assert {r["site"] for r in candidates["extdev"]}.isdisjoint(r["site"] for r in candidates["heldout4"])
    for name, group in candidates.items():
        assert group
        for source in SOURCES:
            selected = [r for r in group if r["source"] == source]
            assert [r["rank"] for r in selected] == sorted(r["rank"] for r in selected)
    again = asyncio.run(sample(list(reversed(rows)), screen, cache, lambda c: None, {"example0.org"}, quotas))
    assert again == (ledger, candidates)
    assert len(calls) == len(cache)


def test_empty_and_unreachable_pool():
    async def screen(url):
        return {"classification": "captcha_or_bot_block"}

    assert asyncio.run(sample([], screen, {}, lambda c: None, set())) == ([], {"extdev": [], "heldout4": []})
    row = dict(source=SOURCES[0], source_id="1", site="example.org", start_url="https://example.org")
    ledger, candidates = asyncio.run(sample([row], screen, {}, lambda c: None, set()))
    assert ledger[0]["reason"] == "unreachable"
    assert ledger[0]["reachability"]["classification"] == "captcha_or_bot_block"
    assert not any(candidates.values())


def test_authoring_cap_counts_only_accepted_and_preserves_old_decisions():
    rows = [dict(source=SOURCES[0], source_id=str(i), site="example.org", rank=i) for i in range(1, 7)]
    decisions = [dict(rows[0], disposition="excluded", reason="login")]
    walk = authoring_reserve(rows, decisions)
    for expected in (2, 3, 4):
        row, reason = next(walk)
        assert row["rank"] == expected and reason is None
        decisions.append(dict(row, disposition="kept"))
    for expected in (5, 6):
        row, reason = next(walk)
        assert row["rank"] == expected and reason == "site_cap"
        decisions.append(dict(row, disposition="excluded", reason=reason))
    assert list(walk) == []
    assert list(authoring_reserve([], decisions)) == []
    assert QUOTAS["extdev"]["Mind2Web"] == QUOTAS["heldout4"]["Mind2Web"] == 0


def test_mind2web_slim_is_train_only_five_fields_and_homepage_mapping_is_recorded():
    import hashlib
    import json

    directory = Path(__file__).resolve().parents[1] / "bench/ext_sources"
    path = directory / "mind2web_train_slim.jsonl"
    provenance = json.loads((directory / "mind2web_train_provenance.json").read_text())
    assert provenance["split"] == "train" and provenance["rows"] == 1009
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance["sha256"]
    for line in path.read_text().splitlines():
        assert set(json.loads(line)) == {"annotation_id", "confirmed_task", "website", "domain", "subdomain"}
    for row in normalize(directory):
        if row["source"] == "Mind2Web":
            assert row["non_text_edits"][0]["field"] == "start_url"
            assert row["source_id"] == row["source_key"]["annotation_id"]
            assert row["task_text"] == row["source_key"]["confirmed_task"]


def test_authoring_automatically_excludes_duplicates_of_existing_and_new_keeps():
    def row(source, rank, text):
        return dict(source=source, source_id=str(rank), rank=rank,
                    site="steampowered.com", start_url="https://store.steampowered.com/", task_text=text)

    original = row(SOURCES[0], 1, "Find Dota 2 game and add all DLC to cart in store.steampowered")
    duplicate = row(SOURCES[-1], 1, "  FIND Dota 2 game, and add ALL dlc to cart!!! ")
    distinct = row(SOURCES[-1], 2, "Show multiplayer games on store.steampowered.com.")
    another = row(SOURCES[-1], 3, "show multiplayer games")
    decisions = [dict(original, disposition="kept", task_id="extdev_spa_dota_dlc_cart")]
    walk = authoring_reserve([original, duplicate, distinct, another], decisions)
    candidate, reason = next(walk)
    assert reason == "duplicate_task" and candidate["duplicate_of"] == "extdev_spa_dota_dlc_cart"
    decisions.append(dict(candidate, disposition="excluded", reason=reason))
    candidate, reason = next(walk)
    assert candidate == distinct and reason is None
    decisions.append(dict(candidate, disposition="kept", task_id="extdev_filter_multiplayer"))
    candidate, reason = next(walk)
    assert reason == "duplicate_task" and candidate["duplicate_of"] == "extdev_filter_multiplayer"
    assert list(walk) == []
    assert task_fingerprint("", "example.com") == ""
    assert task_fingerprint("Visit a park in New York", "sixflags.com").endswith("in new york")
    assert task_fingerprint("Open my inventory", "steampowered.com") != task_fingerprint("Open my reviews", "steampowered.com")
    assert task_fingerprint("Find Dota 2 in Steam!", "steampowered.com") == "find dota 2"


def test_superseded_decisions_do_not_consume_caps_or_create_duplicates():
    rows = [dict(source=SOURCES[0], source_id=str(i), rank=i, site="example.com",
                 start_url="https://example.com/", task_text=f"Task {i}") for i in range(4)]
    decisions = [dict(row, disposition="kept", task_id=f"task_{i}") for i, row in enumerate(rows[:3])]
    decisions.append(dict(rows[0], disposition="excluded", reason="no_checkable_key"))
    assert len(effective_authoring_decisions(decisions)) == 3
    assert list(authoring_reserve(rows, decisions)) == [(rows[3], None)]
    decisions.append(dict(rows[0], disposition="kept", task_id="revised_task_0"))
    assert list(authoring_reserve(rows, decisions)) == [(rows[3], "site_cap")]
    duplicate = dict(rows[3], task_text="TASK 0!!! on example.com")
    candidate, reason = next(authoring_reserve(rows[:3] + [duplicate], decisions))
    assert reason == "duplicate_task" and candidate["duplicate_of"] == "revised_task_0"
