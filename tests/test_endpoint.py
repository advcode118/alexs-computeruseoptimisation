"""Endpoint arm. Fixture pages only. No browser and no network."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bench.arms import ARM_ENDPOINT, ARMS, ARM_PLAYWRIGHT, ARM_SCRIPT_FIRST, ARM_STAGEHAND, build_client
from bench.budget import SpendLedger
from bench.endpoint import (
    EndpointError,
    fetch_start_url,
    judge_page,
    page_from_html,
    run_endpoint_task,
)
from bench.probe import execute_probe
from bench.tasks import markers_for_task

MAIN = "https://en.wikipedia.org/wiki/Main_Page"
SEARCH = "https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace"
ARTICLE = "https://en.wikipedia.org/wiki/Ada_Lovelace"
HN = "https://news.ycombinator.com/"
WIKI = {
    "id": "wv_wikipedia_search",
    "start_url": MAIN,
    "description": "Search Wikipedia for 'Ada Lovelace' and confirm you are on her article page",
    "end_markers": markers_for_task("wv_wikipedia_search"),
}
HN_TASK = {
    "id": "wv_hackernews_top",
    "start_url": HN,
    "description": "Go to Hacker News and identify the title of the top story",
    "end_markers": markers_for_task("wv_hackernews_top"),
}

MAIN_HTML = """<html><head>
<link rel="canonical" href="https://en.wikipedia.org/wiki/Ada_Lovelace">
<title>Wikipedia</title></head>
<body><h1>Main Page</h1><p>Welcome</p></body></html>"""

HN_HTML = """<html><head><title>Hacker News</title></head>
<body>
<span class="titleline"><a href="item?id=1">Fixture Story</a></span>
<span class="titleline"><a href="item?id=2">Second Story</a></span>
<p>Fixture Story</p><p>Second Story</p>
</body></html>"""


class _Response:
    def __init__(self, url: str, body: str):
        self._url = url
        self._body = body

    def geturl(self) -> str:
        return self._url

    def read(self) -> bytes:
        return self._body.encode()


def test_endpoint_is_its_own_arm_and_does_not_launch_a_browser():
    assert ARM_ENDPOINT not in {ARM_SCRIPT_FIRST, ARM_PLAYWRIGHT, ARM_STAGEHAND}
    assert ARM_ENDPOINT not in ARMS
    source = Path(__file__).resolve().parents[1].joinpath("bench", "endpoint.py").read_text(encoding="utf-8")
    assert "playwright" not in source
    client = build_client(ARM_ENDPOINT)
    with pytest.raises(EndpointError, match="does not launch a browser"):
        asyncio.run(client.start())


def test_fetch_keeps_the_transport_url_byte_for_byte():
    def opener(url: str) -> _Response:
        assert url == MAIN
        return _Response(url, MAIN_HTML)

    page = fetch_start_url(MAIN, opener=opener)
    assert page["url"] == MAIN
    assert "Ada_Lovelace" not in page["url"]
    assert page["canonical"] == ARTICLE
    verdict, evidence, row = judge_page(WIKI, page)
    assert evidence.url == MAIN
    assert row["page_url"] == MAIN
    assert row["scored_url"] == MAIN
    assert verdict.verdict == "FAIL"
    assert row["arm"] == ARM_ENDPOINT
    assert row["success"] is False
    with pytest.raises(EndpointError, match="network"):
        fetch_start_url(MAIN, opener=None)


def test_search_url_and_wrong_host_are_misses_without_rewriting():
    search = page_from_html(SEARCH, "<html><head><title>Search</title></head><body><p>Ada_Lovelace</p></body></html>")
    verdict, evidence, row = judge_page(WIKI, search)
    assert evidence.url == SEARCH
    assert row["page_url"] == SEARCH
    assert verdict.scored_url == SEARCH
    assert ARTICLE not in row["page_url"]
    assert verdict.verdict == "FAIL"

    wrong = {
        "url": "https://example.com/wiki/Ada_Lovelace",
        "title": "Ada Lovelace - Wikipedia",
        "canonical": "",
        "h1": "Ada Lovelace",
        "text": "Ada Lovelace",
        "selector_text": "",
    }
    verdict, evidence, row = judge_page(WIKI, wrong)
    assert evidence.url == wrong["url"]
    assert row["page_url"] == wrong["url"]
    assert verdict.verdict == "FAIL"
    assert verdict.reason == "the page is on the wrong host"


def test_hacker_news_fixture_hits_and_a_miss_falls_through(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    page = fetch_start_url(HN, opener=lambda url: _Response(url, HN_HTML), selector=".titleline a")
    assert page["url"] == HN
    assert page["selector_text"] == "Fixture Story"

    async def boom(_task):
        raise AssertionError("script_first ran on a hit")

    hit = asyncio.run(run_endpoint_task(HN_TASK, page, fallback=boom))
    assert hit["arm"] == ARM_ENDPOINT
    assert hit["success"] is True
    assert hit["end_state"] == "PASS"
    assert hit["page_url"] == HN
    assert hit["scored_url"] == HN
    assert hit["model_calls"] == 0
    assert hit["endpoint_miss"] is False

    called = []

    async def fallback(task):
        called.append(task["start_url"])
        return {"arm": "playwright_mcp", "task_id": task["id"], "success": True, "page_url": ARTICLE, "claude": False}

    miss = asyncio.run(run_endpoint_task(WIKI, page_from_html(MAIN, MAIN_HTML), fallback=fallback))
    assert called == [MAIN]
    assert miss["arm"] == ARM_SCRIPT_FIRST
    assert miss["endpoint_miss"] is True
    assert miss["endpoint_url"] == MAIN
    assert miss["page_url"] == ARTICLE


def test_probe_refuses_a_live_fetch_and_falls_through_on_a_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))

    def start(self):
        raise AssertionError("browser started")

    monkeypatch.setattr("bench.harness.PlaywrightMCPClient.start", start)
    SpendLedger.seed(tmp_path / "spend.json").save()
    rows = asyncio.run(
        execute_probe(
            spend_path=tmp_path / "spend.json",
            runs_dir=tmp_path / "runs",
            arms=(ARM_ENDPOINT,),
        )
    )
    assert [row["arm"] for row in rows] == [ARM_ENDPOINT, ARM_ENDPOINT, ARM_ENDPOINT]
    assert all(row["skipped"] for row in rows)
    assert all("refusing to open a browser" in row["success_reason"] for row in rows)

    calls = []

    async def fake_claude(arm, task, **kwargs):
        del kwargs
        calls.append((arm, task["id"]))
        return {
            "arm": arm,
            "task_id": task["id"],
            "success": True,
            "success_reason": "fallback",
            "skipped": False,
            "wall_ms": 1.0,
            "steps": 2,
            "input_tokens": 0,
            "output_tokens": 0,
            "usd": 0.0,
            "model_ignores_tools": 0,
            "no_model": False,
            "replay_hit": False,
            "tier": "fresh",
            "model_calls": 1,
            "claude": False,
            "page_url": "https://example.com/script",
        }

    monkeypatch.setattr("bench.probe.run_claude_arm", fake_claude)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")

    def opener(url: str) -> _Response:
        if url == HN:
            return _Response(url, HN_HTML)
        return _Response(url, MAIN_HTML)

    mixed = asyncio.run(
        execute_probe(
            spend_path=tmp_path / "spend.json",
            runs_dir=tmp_path / "mixed",
            arms=(ARM_ENDPOINT,),
            endpoint_opener=opener,
        )
    )
    by_id = {row["task_id"]: row for row in mixed}
    assert by_id["wv_hackernews_top"]["arm"] == ARM_ENDPOINT
    assert by_id["wv_hackernews_top"]["success"] is True
    assert by_id["wv_hackernews_top"]["page_url"] == HN
    assert by_id["wv_wikipedia_search"]["arm"] == ARM_SCRIPT_FIRST
    assert by_id["wv_wikipedia_search"]["endpoint_url"] == "https://en.wikipedia.org/wiki/Main_Page"
    assert by_id["wv_python_docs"]["arm"] == ARM_SCRIPT_FIRST
    assert "wv_hackernews_top" not in {task_id for _arm, task_id in calls}
    assert ("script_first", "wv_wikipedia_search") in calls
    assert ("script_first", "wv_python_docs") in calls
