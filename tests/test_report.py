"""The report command prints saved fields. It does not run a browser or a probe."""

from __future__ import annotations

from pathlib import Path

from bench.report import main, render, load_rows

FIXTURE = Path(__file__).parent / "fixtures" / "probe_sketch.jsonl"


def test_report_prints_saved_fields_and_refuses_a_browser(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )
    source = Path(__file__).resolve().parents[1].joinpath("bench", "report.py").read_text(encoding="utf-8")
    assert "playwright" not in source
    assert "execute_probe" not in source

    assert main(["--execute"]) == 2
    assert "does not run a browser" in capsys.readouterr().err

    rows = load_rows(FIXTURE)
    assert all(row.get("sketch") for row in rows)
    text = render(rows)
    assert "sketch fixture, not a probe" in text
    assert "wall_ms=1111" in text
    assert "steps=7" in text
    assert "tier=sketch" in text
    assert "usd=0.001000" in text
    assert "wall_ms=2222" in text
    assert "steps=4" in text
    assert "tier=fresh" in text
    assert "usd=0.002000" in text
    assert "sum of usd in this file: 0.003000" in text
    assert "arm stagehand" in text
    assert "tier=-" in text
    assert "usd=0.004000" in text
    assert "99999" not in text

    assert main([str(FIXTURE)]) == 0
    printed = capsys.readouterr().out
    assert "wall_ms=1111" in printed
    assert "99999" not in printed

    empty = tmp_path / "runs"
    empty.mkdir()
    assert main([str(empty)]) == 0
    assert "no saved probe logs" in capsys.readouterr().out
