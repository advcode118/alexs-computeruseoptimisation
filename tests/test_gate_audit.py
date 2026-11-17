import asyncio
import json

from tools.gate_audit import SavedScript, audit, collect, extract_scripts, render


def test_extract_nested_scripts():
    data = {"task_id": "read", "task_description": "Log in and read", "scripts": ["page.title()"], "cache": {"script": "page.url()"}}
    scripts = list(extract_scripts(data, "row"))
    assert [item.code for item in scripts] == ["page.title()", "page.url()"]
    assert all(item.task == "read" for item in scripts)
    assert all(item.description == "Log in and read" for item in scripts)
    assert list(extract_scripts({"scripts": []}, "row")) == []


def test_collect_and_audit(tmp_path):
    (tmp_path / "rows.jsonl").write_text(json.dumps({"task_id": "read", "scripts": [
        'page.goto("https://example.org/"); page.getByRole("button", {name: "Delete"}).click()',
        "not a script",
    ]}) + "\n")
    (tmp_path / "page.json").write_text(json.dumps({"url": "https://example.org/", "html": "<button>Delete</button>"}))
    (tmp_path / "bad.json").write_text("bad")
    scripts, pages, errors = collect(tmp_path)
    assert len(scripts) == 2 and len(errors) == 1
    assert pages["https://example.org/"] == "<button>Delete</button>"
    groups, blocked, rejected, replay_errors = asyncio.run(audit(scripts, pages))
    assert sum(counts["blocked"] for counts in groups.values()) == 1
    assert sum(counts["DOM"] for counts in groups.values()) == 2
    assert "Delete" in blocked[0] and len(rejected) == 1 and not replay_errors
    assert "TOTAL" in render(groups, blocked, rejected, replay_errors, errors)


def test_empty_audit():
    groups, blocked, rejected, failures = asyncio.run(audit([], {}))
    assert not groups and not blocked and not rejected and not failures
