"""The agent-facing list must not contain the hidden split."""

from pathlib import Path

from bench.catalog import agent_tasks, format_agent_list
from bench.scoring import load_holdout

ROOT = Path(__file__).resolve().parents[1]

_AGENT_FILES = (
    "loop/planner.py",
    "loop/engine.py",
    "loop/browser.py",
    "loop/actions.py",
    "loop/cli.py",
    "loop/server.py",
    "loop/README.md",
    "bench/catalog.py",
    "bench/cli.py",
    "bench/runner.py",
    "bench/checks.py",
    "bench/rates.py",
    "bench/__init__.py",
    "bench/__main__.py",
    "bench/README.md",
    "bench/baseline_agent.py",
    "bench/keys.py",
    "bench/flags.py",
    "bench/experiments.py",
    "bench/stats.py",
    "bench/LOG.md",
    "bench/PRODUCT.md",
)


def _agent_corpus() -> str:
    parts = [format_agent_list()]
    for rel in _AGENT_FILES:
        parts.append((ROOT / rel).read_text(encoding="utf-8"))
    for path in (ROOT / "loop").rglob("*"):
        if path.is_file() and "router" in path.name.lower():
            parts.append(path.read_text(encoding="utf-8"))
    for path in (ROOT / "bench" / "public").rglob("*"):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_holdout_is_twenty_percent_and_stays_off_the_agent_list():
    public = agent_tasks()
    hidden = load_holdout()
    assert len(public) == 24
    assert len(hidden) == 6
    assert len(public) + len(hidden) == 30
    assert {task.id for task in public}.isdisjoint({task.id for task in hidden})
    assert all(not task.holdout for task in public)
    assert all(task.holdout for task in hidden)

    corpus = _agent_corpus()
    for task in hidden:
        assert task.id not in corpus
        assert task.instruction not in corpus

    scorer = (ROOT / "bench" / "scoring.py").read_text(encoding="utf-8")
    for task in hidden:
        assert task.id not in scorer
        assert task.instruction not in scorer
    assert "load_holdout()" in (ROOT / "bench" / "scoring.py").read_text(encoding="utf-8").split("def score", 1)[1]


def test_agent_tasks_read_only_the_public_directory(monkeypatch):
    import bench.catalog as catalog

    seen = []
    original = catalog._load_directory

    def spy(directory, **kwargs):
        seen.append(directory.name)
        return original(directory, **kwargs)

    monkeypatch.setattr(catalog, "_load_directory", spy)
    catalog.agent_tasks()
    assert seen == ["public"]


def test_list_command_does_not_load_hidden_tasks():
    import inspect

    from bench import cli

    assert "load_holdout" not in inspect.getsource(cli.cmd_list)
    assert "score" in inspect.getsource(cli.cmd_run)


def test_every_task_is_a_local_page_with_a_code_check():
    tasks = agent_tasks() + load_holdout()
    ids = [task.id for task in tasks]
    assert len(ids) == len(set(ids))
    assert any(task.page == "replay" for task in tasks)
    assert any(task.page == "fixture" for task in tasks)
    for task in tasks:
        assert task.page in {"fixture", "replay"}
        assert task.fixture.is_file()
        assert task.fixture.suffix == ".html"
        assert task.fixture.resolve().as_uri().startswith("file:")
        kind = task.check["kind"]
        assert kind in {"dom", "url", "fields"}
        if kind == "dom":
            assert task.check.get("text") or task.check.get("texts")
        elif kind == "url":
            assert task.check.get("contains") or task.check.get("contains_all")
        else:
            assert task.check["fields"]
        folded = task.instruction.lower()
        assert "http://" not in folded
        assert "https://" not in folded


def test_fixtures_do_not_point_at_live_sites():
    for path in (ROOT / "bench").rglob("*.html"):
        text = path.read_text(encoding="utf-8").lower()
        assert "http://" not in text
        assert "https://" not in text
