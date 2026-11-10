"""Saved-page replay. No browser, no network, and no model call.

script_first and the cu helpers run against a HAR fixture. The grade is the
shared observation grade, including the script's own verdict and the claim
it returned. A URL that was not saved is refused before any connection.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from bench.offline_replay import OfflineError, book_from_data, load_book, replay_manifest, replay_script
from bench.tasks import task_by_id

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "replay"
ARTICLE = "https://en.wikipedia.org/wiki/Ada_Lovelace"
SEARCH = "https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace"
PACKING = "https://fixture.local/packing.html"


def test_har_and_saved_page_load_without_a_network():
    book = load_book(FIXTURES / "wiki-search.har")
    assert book.html_for(ARTICLE).startswith("<!DOCTYPE html>")
    assert book.html_for("https://example.com/missing") is None
    saved = book_from_data({"url": PACKING, "html": "<html><title>Packing list</title></html>"})
    assert saved.html_for(PACKING) == "<html><title>Packing list</title></html>"
    with pytest.raises(OfflineError, match="duplicate"):
        book_from_data(
            {
                "pages": [
                    {"url": PACKING, "html": "<p>one</p>"},
                    {"url": PACKING, "html": "<p>two</p>"},
                ]
            }
        )


def test_wiki_helpers_land_on_the_saved_article_and_pass_the_shared_grade():
    run = replay_manifest(FIXTURES / "wiki-search.json")
    assert run.page_url == ARTICLE
    assert run.ok is True
    assert run.steps == 4
    assert run.verdict == "PASS"
    assert run.success is True
    assert run.shared_ok is True
    assert run.success is (run.verdict == "PASS" and run.shared_ok is True)
    assert "mathematician" in run.text
    assert run.model_calls == 0
    assert run.input_tokens == 0
    assert run.output_tokens == 0
    assert run.usd == 0.0
    assert run.error == ""
    assert 0 < run.wall_ms < 30000


def test_a_saved_search_url_still_fails_the_grade():
    book = load_book(FIXTURES / "wiki-search.har")
    task = task_by_id("wv_wikipedia_search")
    script = """
    page.goto("https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace");
    page.evaluate(() => cu.claim({answer: "Ada Lovelace", key_text: "Ada Lovelace", values: ["Ada Lovelace"]}));
    """
    run = replay_script(book, script, task)
    assert run.page_url == SEARCH
    assert ARTICLE not in run.page_url
    assert run.verdict == "FAIL"
    assert run.success is False
    assert run.model_calls == 0
    assert run.usd == 0.0


def test_packing_helpers_add_the_item_and_do_not_loosen_an_unknown_verdict():
    run = replay_manifest(FIXTURES / "packing.json")
    assert run.page_url == PACKING
    assert run.ok is True
    assert "milk" in run.text
    assert run.verdict == "UNKNOWN"
    assert run.success is False
    assert run.model_calls == 0
    assert run.usd == 0.0
    assert 0 < run.wall_ms < 30000
    book = load_book(FIXTURES / "packing.har")
    task = task_by_id("fixture_packing_add")
    pressed = replay_script(
        book,
        """
        page.goto("https://fixture.local/packing.html");
        cu.fill("Item", "milk");
        cu.press("Item", "Enter");
        page.evaluate(() => cu.claim({answer: "milk", key_text: "milk", values: ["milk"]}));
        """,
        task,
    )
    assert pressed.ok is True
    assert "milk" in pressed.text
    assert pressed.success is False
    assert pressed.verdict == "UNKNOWN"


def test_an_unsaved_url_and_a_page_fetch_do_not_open_a_socket(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("offline replay opened a socket")

    monkeypatch.setattr(socket, "create_connection", refuse)

    class Guard(socket.socket):
        def connect(self, *args, **kwargs):
            raise AssertionError("offline replay opened a socket")

        def connect_ex(self, *args, **kwargs):
            raise AssertionError("offline replay opened a socket")

    monkeypatch.setattr(socket, "socket", Guard)
    book = load_book(FIXTURES / "wiki-search.har")
    task = task_by_id("wv_wikipedia_search")
    missing = replay_script(book, 'page.goto("https://example.com/not-saved");', task)
    assert missing.ok is False
    assert missing.success is False
    assert "example.com" not in missing.page_url
    assert "no saved page" in missing.error
    assert missing.model_calls == 0
    hostile = book_from_data(
        {
            "url": "https://fixture.local/fetch.html",
            "html": "<html><body><script>fetch('https://example.com/live')</script></body></html>",
        }
    )
    blocked = replay_script(hostile, 'page.goto("https://fixture.local/fetch.html");', task)
    assert blocked.ok is False
    assert blocked.success is False
    assert "does not open a network connection" in blocked.error
