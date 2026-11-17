"""Audit saved scripts without models or network: python tools/gate_audit.py."""

import argparse
import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bench.offline_replay import load_book
from bench.recovery import ActionGate
from bench.script_first import _run_step_on_page, parse_task_script
from proxy.script import ScriptError


@dataclass(frozen=True)
class SavedScript:
    source: str
    task: str
    code: str
    start_url: str = ""


def extract_scripts(value, source, task="", start_url=""):
    if isinstance(value, dict):
        task = str(value.get("task_id", value.get("idiom", task)))
        start_url = value.get("start_url", start_url) or ""
        for key, item in value.items():
            if key in {"script", "scripts"}:
                for index, code in enumerate(item if isinstance(item, list) else [item]):
                    if isinstance(code, str) and code.strip():
                        yield SavedScript(f"{source}.{key}[{index}]", task, code, start_url)
            elif key == "source" and "idiom" in value and isinstance(item, str):
                yield SavedScript(source, task, item, start_url)
            else:
                yield from extract_scripts(item, f"{source}.{key}", task, start_url)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from extract_scripts(item, f"{source}[{index}]", task, start_url)


def collect(root):
    scripts, pages, errors = [], {}, []
    for path in sorted(root.rglob("*")):
        if any(part in {".git", ".venv", "node_modules", ".next", "__pycache__"} for part in path.relative_to(root).parts):
            continue
        if path.suffix not in {".json", ".jsonl", ".har"} or not path.is_file():
            continue
        relative = str(path.relative_to(root))
        try:
            if path.suffix == ".jsonl":
                for number, line in enumerate(path.read_text().splitlines(), 1):
                    if line.strip():
                        scripts.extend(extract_scripts(json.loads(line), f"{relative}:{number}"))
            else:
                data = json.loads(path.read_text())
                scripts.extend(extract_scripts(data, relative))
                if isinstance(data, dict) and ("log" in data or "pages" in data or ("url" in data and "html" in data)):
                    pages.update(load_book(path).pages)
        except (ValueError, OSError) as exc:
            errors.append(f"{relative}: {exc}")
    return scripts, pages, errors


async def audit(scripts, pages):
    from playwright.async_api import async_playwright

    groups = defaultdict(Counter)
    blocked, rejected, replay_errors = [], [], []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for saved in scripts:
                path = saved.source.split(":", 1)[0]
                parts = path.split("/")
                group = "/".join(parts[:3] if parts[:2] == ["docs", "results"] else parts[:2])
                counts = groups[group]
                counts["scripts"] += 1
                try:
                    steps = parse_task_script(saved.code)
                except ScriptError as exc:
                    counts["parse rejected"] += 1
                    rejected.append(f"{saved.source} ({saved.task}): {exc}")
                    continue
                lexical = SimpleNamespace(url=saved.start_url)
                page = None
                for step in steps:
                    action = step.action
                    if action and action.op == "goto":
                        if page:
                            await page.close()
                            page = None
                        if action.value in pages:
                            page = await browser.new_page()

                            async def route(request):
                                html = pages.get(request.request.url)
                                if html is None:
                                    await request.abort()
                                else:
                                    await request.fulfill(content_type="text/html", body=html)

                            await page.route("**/*", route)
                    target = page or lexical
                    counts["steps"] += 1
                    counts["DOM" if page else "lexical"] += 1
                    allowed, reason = await ActionGate().check(step, target)
                    if not allowed:
                        counts["blocked"] += 1
                        counts[reason] += 1
                        blocked.append(f"{saved.source} ({saved.task}), line {step.line}: {reason}\n  {step.source}")
                    elif page:
                        try:
                            await _run_step_on_page(page, step)
                        except Exception as exc:
                            replay_errors.append(f"{saved.source}, line {step.line}: {type(exc).__name__}")
                            lexical.url = page.url
                            await page.close()
                            page = None
                    if action and action.op == "goto":
                        lexical.url = action.value
                if page:
                    await page.close()
        finally:
            await browser.close()
    return groups, blocked, rejected, replay_errors


def render(groups, blocked, rejected, replay_errors, errors):
    lines = ["| Source/task set | Scripts | Steps | DOM | Lexical | Parse rejected | Blocked | Reasons |",
             "|---|---:|---:|---:|---:|---:|---:|---|"]
    total = Counter()
    for group, counts in sorted(groups.items()):
        total.update(counts)
        reasons = "; ".join(f"{reason}: {count}" for reason, count in sorted(counts.items()) if reason.startswith("needs approval"))
        lines.append(f"| {group} | {counts['scripts']} | {counts['steps']} | {counts['DOM']} | {counts['lexical']} | {counts['parse rejected']} | {counts['blocked']} | {reasons} |")
    lines.append(f"| TOTAL | {total['scripts']} | {total['steps']} | {total['DOM']} | {total['lexical']} | {total['parse rejected']} | {total['blocked']} | |")
    for title, items in [("Blocked steps", blocked), ("Parse rejections (not gate decisions)", rejected), ("Replay failures (remaining steps lexical)", replay_errors), ("Unreadable inputs", errors)]:
        lines.extend(["", f"## {title}", *items] if items else ["", f"## {title}", "None"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scripts, pages, errors = collect(args.root)
    report = render(*asyncio.run(audit(scripts, pages)), errors)
    if args.output:
        args.output.write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
