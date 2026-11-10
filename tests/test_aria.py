"""Parser tests for @playwright/mcp 0.0.84 snapshots and the saved bench samples."""

import json
import re
from pathlib import Path

import pytest

from bench.replay_shortcuts import parse_aria_snapshot_to_observation
from loop.decide import decide
from loop.actions import Fill
from loop.observe.aria import parse_aria_snapshot
from loop.observe.base import observation_from_snapshot

ROOT = Path(__file__).parent.parent
SAMPLES = ROOT / "bench" / "snapshots"
TODOS = Path(__file__).parent / "snapshots" / "playwright_todos.txt"
REF_RE = re.compile(r"\[ref=([^\]]+)\]")


def _by_id(snapshot):
    return {element.id: element for element in snapshot.elements}


def _saved_sample_files():
    if not SAMPLES.is_dir() or not any(SAMPLES.glob("*.json")):
        pytest.skip("bench/snapshots is gitignored and absent from this worktree")
    return sorted(SAMPLES.glob("*.json"))


def test_saved_samples_keep_every_ref_in_order():
    files = _saved_sample_files()
    assert len(files) >= 5
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        snapshot = parse_aria_snapshot(
            data["snapshot_text"],
            url=data.get("url", ""),
            title=data.get("title", ""),
        )
        assert [element.id for element in snapshot.elements] == REF_RE.findall(data["snapshot_text"])
        assert snapshot.url == data.get("url", "")
        assert snapshot.title == data.get("title", "")
        assert all(element.source == "aria" for element in snapshot.elements)
        observation = observation_from_snapshot(snapshot)
        assert [control.ref for control in observation.controls] == [element.id for element in snapshot.elements]
        assert observation.html.splitlines()[0] == (
            f"{snapshot.elements[0].role}\t{snapshot.elements[0].name}\t{snapshot.elements[0].id}"
        )


def test_saved_samples_match_the_replay_converter():
    files = _saved_sample_files()
    assert len(files) >= 5
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        observation = parse_aria_snapshot_to_observation(
            data["snapshot_text"],
            url=data["url"],
            title=data["title"],
        )
        direct = observation_from_snapshot(
            parse_aria_snapshot(data["snapshot_text"], url=data["url"], title=data["title"])
        )
        assert observation == direct
        assert len(observation.controls) > 0


def test_packing_value_and_wikipedia_paths():
    packing_path = SAMPLES / "packing_filled.json"
    wiki_path = SAMPLES / "wikipedia_search_results.json"
    if not packing_path.is_file() or not wiki_path.is_file():
        pytest.skip("bench/snapshots is gitignored and absent from this worktree")
    packing = json.loads(packing_path.read_text(encoding="utf-8"))
    filled = _by_id(parse_aria_snapshot(packing["snapshot_text"]))
    assert filled["S2E3"].role == "textbox"
    assert filled["S2E3"].name == "Item"
    assert filled["S2E3"].value == "milk"
    assert filled["S2E4"].path == ("form",)

    wiki = json.loads(wiki_path.read_text(encoding="utf-8"))
    results = _by_id(parse_aria_snapshot(wiki["snapshot_text"]))
    assert results["S2E5"].role == "link"
    assert results["S2E5"].name == "Ada Lovelace"
    assert results["S2E5"].path == ("main:Search results", "list:Results", "listitem")
    assert results["S2E1"].path == ("banner:Wikipedia",)


def test_playwright_mcp_snapshot_reads_refs_boxes_and_states():
    text = TODOS.read_text(encoding="utf-8")
    snapshot = parse_aria_snapshot(text, url="https://example.com/todos", title="Todos")
    assert [element.id for element in snapshot.elements] == REF_RE.findall(text)
    elements = _by_id(snapshot)
    assert snapshot.focused_id == "e1"
    assert elements["e1"].states == ("active",)
    home = elements["e3"]
    assert home.role == "link" and home.name == "Home"
    assert home.path == ("generic", "banner:Site")
    assert home.bounds is not None
    assert (home.bounds.x, home.bounds.y, home.bounds.width, home.bounds.height) == (8, 8, 40, 16)
    assert elements["e4"].bounds.x == 100.5
    assert elements["e5"].states == ()
    assert elements["e7"].name == "todos"
    assert elements["e8"].value == ""
    assert elements["e11"].states == ("checked",)
    assert elements["e11"].path == ("generic", "main", "list", "listitem")
    assert elements["e14"].name == "Query"
    assert elements["e14"].value == "Ada Lovelace"
    assert elements["e16"].path == ("generic", "contentinfo")
    assert elements["f1e12"].id == "f1e12"
    assert "text: Buy groceries" not in observation_from_snapshot(snapshot).html
    assert "button\tSearch\te5" in observation_from_snapshot(snapshot).html


def test_fenced_snapshot_and_escaped_name():
    text = """Here is the page.
```yaml
- button "Say \\"hi\\"" [ref=e12] [disabled]
- textbox "Query" [ref=e5]: Ada Lovelace
```
"""
    elements = _by_id(parse_aria_snapshot(text))
    assert elements["e12"].name == 'Say "hi"'
    assert elements["e12"].states == ("disabled",)
    assert elements["e5"].value == "Ada Lovelace"


def test_parsed_html_lines_drive_decide():
    text = '- textbox "Search Wikipedia" [ref=e4]\n- button "Search" [ref=e5]\n'
    observation = observation_from_snapshot(
        parse_aria_snapshot(text, url="https://en.wikipedia.org/", title="Wikipedia")
    )
    outcome = decide("Search Wikipedia for Ada Lovelace and confirm the article title.", observation)
    assert isinstance(outcome.actions[0], Fill)
    assert outcome.actions[0].ref == "e4"
    assert outcome.actions[0].text == "Ada Lovelace"
    assert outcome.actions[1].ref == "e5"
