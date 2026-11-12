"""Fail if the rendered site still carries retired probe claims."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    ROOT / "app",
    ROOT / "data" / "progress.ts",
    ROOT / "data" / "format.ts",
    ROOT / "README.md",
    ROOT / ".github" / "readme",
]
BANNED = [
    r"18/18",
    r"(?<!\d)3\.18",
    r"(?<!\d)1\.46",
    r"(?<!\d)2\.98",
    r"Sonnet",
    r"Origin",
    r"PR #",
    r"warm replay",
    r"diff_fast_act",
    r"macro_replay",
    r'id="history"',
    r'id="loop"',
    r"Background",
    r"parked",
    r"untested",
    r"Claude call",
    r"One Claude",
    r"(?<!\d)5\.25s",
    r"(?<!\d)6\.03s",
    r"(?<!\d)12\.54",
]


def files():
    for path in PATHS:
        if path.is_file():
            yield path
            continue
        for child in path.rglob("*"):
            if child.is_file() and child.suffix in {".tsx", ".ts", ".md", ".svg", ".css"}:
                yield child


def main() -> None:
    hits: list[str] = []
    for path in files():
        text = path.read_text(encoding="utf-8")
        for phrase in BANNED:
            if re.search(phrase, text):
                hits.append(f"{path.relative_to(ROOT)}: {phrase}")
    stagehand = []
    for path in files():
        text = path.read_text(encoding="utf-8")
        if "Stagehand" in text and "Stagehand is outside this comparison" not in text:
            stagehand.append(str(path.relative_to(ROOT)))
    measured = json.loads((ROOT / "data" / "measured.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    luna = next(run for run in measured["heldOut"] if run["model"] == "gpt-6-luna")
    sol = next(run for run in measured["heldOut"] if run["model"] == "gpt-6.1-sol")
    hero = (ROOT / ".github" / "readme" / "hero.svg").read_text(encoding="utf-8")
    for arm, _label in (
        ("script_first", "script_first"),
        ("playwright_mcp", "Playwright MCP"),
        ("browser_use", "browser-use"),
    ):
        for run, name in ((luna, "luna"), (sol, "sol")):
            block = run["arms"][arm]
            passed = f"{block['pass']}/50"
            median = f"{block['all']['medianS']:.2f}s"
            p90 = f"{block['all']['p90S']:.2f}s"
            cost = f"${block['usd']:.4f}"
            if arm == "script_first" and passed not in readme:
                hits.append(f"README missing {name} {passed}")
            for label, needle, haystack in (
                ("median", median, readme),
                ("p90", p90, readme),
                ("cost", cost, readme),
                ("hero median", median, hero),
                ("hero pass", passed, hero),
            ):
                if needle not in haystack:
                    hits.append(f"{name} {arm} {label} {needle} missing")
    if measured["rules"]["offPasses"] != [31, 36, 31] or "31, 36 and 31" not in readme:
        hits.append("README missing plain-rule passes 31, 36 and 31")
    if measured["rules"]["onPasses"] != [29, 35, 37] or "29, 35 and 37" not in readme:
        hits.append("README missing Decisions passes 29, 35 and 37")
    if "$3.2185" not in readme or "26.022488" not in readme:
        hits.append("README missing a recorded ledger figure")
    if hits or stagehand:
        print("\n".join(hits + [f"Stagehand outside the allowed sentence: {item}" for item in stagehand]))
        raise SystemExit(1)
    print("site copy has no retired probe claims")


if __name__ == "__main__":
    main()
