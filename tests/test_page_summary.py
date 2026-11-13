"""Start-page summary for script_first's first model call. Offline: saved HTML only."""

from __future__ import annotations

import asyncio
import gzip
from pathlib import Path

import pytest

from bench import page_summary as ps

FIXTURES = Path(__file__).parent / "fixtures" / "page_summary"
DOCS_URL = "https://docs.example.test/en/latest/"


def _facts(name: str, url: str = DOCS_URL) -> ps.PageFacts:
    return ps.parse_page((FIXTURES / name).read_text(encoding="utf-8"), url)


def test_docs_page_facts():
    facts = _facts("docs_home.html")
    assert facts.title == "Widget Toolkit — Documentation"
    assert facts.canonical == DOCS_URL
    assert facts.h1 == ["Widget Toolkit¶"]
    assert facts.h2 == ["Get started", "Reference"]
    urls = [url for _text, url in facts.links]
    # Absolute, no in-page anchors, no javascript: or mailto:, nothing from scripts or comments.
    assert "https://docs.example.test/en/latest/tutorial/index.html" in urls
    assert all(u.startswith("https://") for u in urls)
    assert not any("never" in u or "commented" in u or "#" in u for u in urls)
    # An image link is named by its alt text, and a link to the page itself is dropped.
    assert ("Widget Toolkit home", "https://docs.example.test/") in facts.links
    assert "Toggle theme" in facts.buttons


def test_search_form_becomes_a_results_url_template():
    facts = _facts("docs_home.html")
    search = [f for f in facts.forms if ps._is_search_form(f)]
    assert len(search) == 1
    assert ps.search_template(search[0]) == "https://docs.example.test/en/latest/search.html?area=default&q={query}"
    text = ps.summarize(facts, "Use the toolkit's own search box to look up directives")
    assert "- Site search (GET): https://docs.example.test/en/latest/search.html?area=default&q={query}" in text
    # The search form is not listed a second time as an ordinary form.
    assert "- Form:" not in text


def test_links_sharing_task_words_come_first_and_are_deduplicated():
    facts = _facts("docs_home.html")
    ranked = ps.rank_links(facts.links, "Open the reference page for directives", DOCS_URL)
    text, url, score = ranked[0]
    assert url.endswith("/usage/directives.html") and score > 0
    assert [u for _t, u, _s in ranked].count(url) == 1


def test_site_name_words_do_not_rank():
    # "widget" and "toolkit" name the site in every link; "layout" names the target.
    links = [(f"Widget Toolkit part {i}", f"https://widget-toolkit.example.test/p{i}") for i in range(12)]
    links.append(("Layout grids", "https://widget-toolkit.example.test/layout"))
    ranked = ps.rank_links(links, "On the Widget Toolkit site, open the layout guide", "https://widget-toolkit.example.test/")
    assert ranked[0][1].endswith("/layout")
    assert all(score == 0 for _t, _u, score in ranked[1:])


def test_ordinal_words_match_page_numbers():
    facts = _facts("blog_index.html", "https://blog.example.test/news/")
    ranked = ps.rank_links(facts.links, "From the news index, open the second page of posts.", facts.url)
    assert ranked[0][1] == "https://blog.example.test/news/page/2/"
    # The best text wins for a URL linked twice.
    assert ranked[0][0] in ("2", "Older posts")


def test_search_input_type_search_with_button():
    facts = _facts("blog_index.html", "https://blog.example.test/news/")
    text = ps.summarize(facts, "search the news for launch")
    assert "- Site search (GET): https://blog.example.test/?s={query}" in text


def test_form_fields_labels_and_submit():
    facts = _facts("login.html", "https://members.example.test/login")
    text = ps.summarize(facts, "Sign in with the account on the page")
    assert "- Form: POST https://members.example.test/authenticate" in text
    assert 'text name="username" label "Username"' in text
    assert 'password name="password" label "Password"' in text
    assert 'select name="size" label "Size" options: Small, Medium, Large' in text
    assert 'checkbox name="remember" label "Remember me"' in text
    assert 'textarea name="notes" label "Anything else?"' in text
    assert "submit: Log in" in text
    assert "Site search" not in text


def test_javascript_shell_has_no_summary():
    fetched = ps.Fetched(url="https://app.example.test/", final_url="https://app.example.test/", status=200,
                         html=(FIXTURES / "spa_shell.html").read_text(encoding="utf-8"))
    summary = ps.summary_from_fetch(fetched, "anything")
    assert summary.status == "no content" and summary.text == ""


def test_failed_fetch_has_no_summary():
    summary = ps.summary_from_fetch(ps.Fetched(url="https://x.example.test/", status=403, error="http 403"), "t")
    assert summary.status == "http 403" and summary.text == ""


def test_summary_stays_small_on_a_huge_page():
    rows = "".join(f'<li><a href="/item/{i}">Item number {i} with a long descriptive name</a></li>' for i in range(5000))
    html = f"<html><head><title>Big</title></head><body><h1>Big</h1><ul>{rows}</ul></body></html>"
    facts = ps.parse_page(html, "https://big.example.test/")
    text = ps.summarize(facts, "open item number 4321")
    assert len(text) <= ps.MAX_SUMMARY_CHARS + 20
    links = [line for line in text.splitlines() if line.startswith("  ") and " -> " in line]
    assert len(links) <= ps.MAX_LINKS


def test_summary_names_no_host_but_the_page():
    text = ps.summarize(_facts("docs_home.html"), "open the tutorial")
    hosts = {part.split("/")[2] for part in text.split() if part.startswith("https://")}
    assert hosts <= {"docs.example.test", "elsewhere.example.test"}


def test_decode_gzip_and_meta_charset():
    body = '<meta charset="iso-8859-1"><p>caf\xe9</p>'.encode("latin-1")
    assert "café" in ps._decode(gzip.compress(body), "gzip", "text/html")


def test_switch(monkeypatch):
    monkeypatch.setenv(ps.ENV_SWITCH, "0")
    assert not ps.enabled()
    assert ps.start_for_arm("script_first", "https://x.example.test/", "t") is None
    assert ps.row_fields(None) == {"page_summary": "off"}
    monkeypatch.setenv(ps.ENV_SWITCH, "1")
    assert ps.enabled()
    monkeypatch.delenv(ps.ENV_SWITCH)
    assert ps.enabled()


def test_other_arms_never_fetch(monkeypatch):
    monkeypatch.setenv(ps.ENV_SWITCH, "1")
    for arm in ("browser_use", "playwright_mcp", "stagehand", "endpoint"):
        assert ps.start_for_arm(arm, "https://x.example.test/", "t") is None


def test_await_summary_respects_the_deadline():
    async def go():
        loop = asyncio.get_running_loop()
        never = loop.create_future()
        summary = await ps.await_summary(never, deadline_s=0.05)
        assert summary.status == "timeout" and summary.text == ""
        assert summary.waited_ms < 1000
        off = await ps.await_summary(None)
        assert off.status == "off"

    asyncio.run(go())


def test_start_summary_never_raises_on_a_bad_url(monkeypatch):
    def boom(url, timeout):
        raise OSError("network down")

    monkeypatch.setattr(ps.urllib.request, "urlopen", boom)

    async def go():
        summary = await ps.await_summary(ps.start_summary("https://x.example.test/", "t"))
        assert summary.text == "" and "OSError" in summary.status

    asyncio.run(go())


@pytest.mark.parametrize("name", ["docs_home.html", "login.html", "blog_index.html"])
def test_summary_ends_with_the_usage_line(name):
    text = ps.summarize(_facts(name), "task")
    assert text.splitlines()[-1].startswith("Use it:")


def _fresh_run(tmp_path, monkeypatch, switch: str):
    """One fresh script_first run on the offline wiki double, no cache entry."""
    from tests.test_script_cache import CLICK_SCRIPT, _WikiPage, _run, _script_reply, LINK

    monkeypatch.setenv(ps.ENV_SWITCH, switch)
    fetched: list[str] = []

    def fake_build(url, task, timeout=ps.FETCH_TIMEOUT_S):
        fetched.append(url)
        return ps.Summary(status=ps.STATUS_OK, text="Start page, read over HTTP: fixture", ms=5.0)

    monkeypatch.setattr(ps, "build_summary", fake_build)
    result, model, _cache = _run(tmp_path, _WikiPage({LINK: "article"}), [_script_reply(CLICK_SCRIPT)])
    return result, model, fetched


def test_harness_puts_the_summary_in_model_call_one(tmp_path, monkeypatch):
    from bench.tasks import task_message
    from tests.test_script_cache import DESCRIPTION, START

    result, model, fetched = _fresh_run(tmp_path, monkeypatch, "1")
    assert fetched == [START]
    first = model.calls[0]["messages"][0]["content"]
    assert first == task_message(DESCRIPTION, START) + "\n\nStart page, read over HTTP: fixture"
    assert result.success is True


def test_harness_off_sends_the_unchanged_task_message(tmp_path, monkeypatch):
    from bench.tasks import task_message
    from tests.test_script_cache import DESCRIPTION, START

    _result, model, fetched = _fresh_run(tmp_path, monkeypatch, "0")
    assert fetched == []
    assert model.calls[0]["messages"][0]["content"] == task_message(DESCRIPTION, START)
