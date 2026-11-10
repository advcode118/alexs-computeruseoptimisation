"""Cached-script tier for script_first.

A script is stored only after the evidence judge said PASS on the live page.
A stored script is replayed with no model call and judged again every time.
When the replay fails, the model gets one turn to patch the failing step.

Entries hold the task intent, the site, the start URL pattern, and the
model's own script. Judge markers and expected answers are never stored and
never shown in the patch prompt.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.parse import urlsplit

from bench.script_first import PASS, EvidenceVerdict, parse_task_script
from proxy.script import ScriptError

TIER_CACHE_HIT = "cache_hit"
TIER_PATCHED = "patched"
TIER_FRESH = "fresh"

_PATCH_PAGE_TEXT_CAP = 2000

PATCH_TOOL = {
    "name": "patch_step",
    "description": (
        "Replace one numbered step of the cached script. code is the new Playwright "
        "line or lines for that step only. Every other step stays as it is."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "step": {"type": "integer", "description": "1-based number of the step to replace."},
            "code": {"type": "string", "description": "Replacement for that step."},
        },
        "required": ["step", "code"],
    },
}

PATCH_PROMPT = """You are a browser automation agent. A cached Playwright script for this task failed when it was replayed.

Guidelines:
- Call patch_step once. Replace only the step that broke. Do not rewrite the other steps.
- Allowed: page.goto("https://..."), page.getByRole, page.getByLabel, page.getByText, page.getByPlaceholder, cu.click("visible name"), cu.fill("visible name", "text"), cu.press("visible name", "Enter"), and page.evaluate(() => cu.claim({answer: "", key_text: "", values: []})) with a page-context function.
- Use the current page to pick a locator or URL that exists now.
- Do not call page.waitForTimeout, page.waitForLoadState, page.waitForSelector, or networkidle.
- If no single step can be fixed, reply with TASK_FAILED."""


def task_intent(description: str) -> str:
    return " ".join((description or "").split()).casefold().rstrip(".!?")


def site_of(start_url: str) -> str:
    parts = urlsplit(start_url or "")
    return parts.netloc.casefold()


def url_pattern_for(start_url: str) -> str:
    parts = urlsplit(start_url or "")
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc.casefold()}/*"


def cache_key(description: str, start_url: str) -> str:
    raw = f"{task_intent(description)}\n{site_of(start_url)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _control_pairs(controls) -> list[str]:
    pairs: list[str] = []
    if not controls:
        return pairs
    for item in controls:
        role = ""
        name = ""
        if isinstance(item, str):
            role, sep, name = item.partition("\t")
            if not sep:
                continue
        elif isinstance(item, dict):
            role = str(item.get("role") or "")
            name = str(item.get("name") or "")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            role, name = str(item[0]), str(item[1])
        else:
            continue
        role = " ".join(role.split()).casefold()
        name = " ".join(name.split()).casefold()
        if name:
            pairs.append(f"{role}\t{name}")
    return sorted(set(pairs))


def page_fingerprint(host: str, controls) -> str:
    """Host plus a stable hash of roles and names. Order and blank names are ignored."""
    body = "\n".join(_control_pairs(controls))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    return f"{(host or '').casefold()}|{digest}"


def fingerprint_from_payload(payload: dict | None, start_url: str) -> str:
    data = payload if isinstance(payload, dict) else {}
    url = data.get("url") if isinstance(data.get("url"), str) else ""
    return page_fingerprint(site_of(url) or site_of(start_url), data.get("controls"))


def script_steps(source: str) -> list[str]:
    """One source line per runnable step. Wait lines are already dropped."""
    return [step.source for step in parse_task_script(source)]


def replayable_script(source: str, start_url: str) -> str:
    """The script that passed, one step per line.

    Wait lines are already dropped, so this is the script the judge saw.
    A goto is kept only when that script had one. The start URL is not
    inserted: a step the judge never ran must not be cached as a pass.
    """
    del start_url
    lines = [step.source for step in parse_task_script(source)]
    text = "\n".join(lines)
    parse_task_script(text)
    return text


def apply_patch(source: str, step: int, code: str) -> str:
    """Replace step `step` (1-based) with `code`. Raises ScriptError when the result does not parse."""
    lines = script_steps(source)
    if not isinstance(step, int) or isinstance(step, bool) or not 1 <= step <= len(lines):
        raise ScriptError(f"patch step {step!r} is not in the script")
    replacement = script_steps(code) if (code or "").strip() else []
    patched = lines[: step - 1] + replacement + lines[step:]
    if not patched:
        raise ScriptError("patch leaves no steps")
    text = "\n".join(patched)
    parse_task_script(text)
    return text


def failing_step(payload: dict, step_total: int) -> int:
    """The step that threw, or 0 when every step ran."""
    if payload.get("ok") is False and payload.get("error"):
        done = int(payload.get("steps") or 0)
        return min(step_total, done + 1) if step_total else 0
    return 0


def patch_request(
    *,
    description: str,
    start_url: str,
    script: str,
    payload: dict,
    verdict: EvidenceVerdict,
) -> str:
    """The one patch turn: cached script, the error, and the live page read.

    selector_text and the claimed values are not shown. They are judge data.
    """
    lines = script_steps(script)
    numbered = "\n".join(f"{index}. {line}" for index, line in enumerate(lines, 1))
    broken = failing_step(payload, len(lines))
    if broken:
        failure = f"Step {broken} threw: {str(payload.get('error') or '').strip()}"
    else:
        failure = f"All {len(lines)} steps ran. END_STATE_FAILED: {verdict.reason}."
    text = payload.get("text") if isinstance(payload.get("text"), str) else ""
    page = [
        f"URL: {payload.get('url') or '(empty)'}",
        f"Title: {payload.get('title') or ''}",
        f"H1: {payload.get('h1') or ''}",
        "Text:",
        text[:_PATCH_PAGE_TEXT_CAP],
    ]
    return (
        f"Task: {description}\n\nStart URL: {start_url}\n\n"
        f"Cached script:\n{numbered}\n\n"
        f"Replay failure: {failure}\n\n"
        "Current page:\n" + "\n".join(page)
    )


@dataclass(frozen=True)
class CachedScript:
    key: str
    intent: str
    site: str
    url_pattern: str
    script: str
    step_count: int
    saved_at: float
    fingerprint: str = ""


class ScriptCache:
    """A JSON file of scripts that passed the evidence judge."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        entries = data.get("entries") if isinstance(data, dict) else None
        return entries if isinstance(entries, dict) else {}

    def _write(self, entries: dict) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps({"version": 1, "entries": entries}, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            return False
        return True

    def lookup(self, description: str, start_url: str) -> CachedScript | None:
        key = cache_key(description, start_url)
        raw = self._load().get(key)
        if not isinstance(raw, dict):
            return None
        pattern = raw.get("url_pattern") or ""
        if not pattern or not fnmatchcase((start_url or "").casefold(), pattern.casefold()):
            return None
        script = raw.get("script")
        if not isinstance(script, str) or not script.strip():
            return None
        return CachedScript(
            key=key,
            intent=str(raw.get("intent") or ""),
            site=str(raw.get("site") or ""),
            url_pattern=pattern,
            script=script,
            step_count=int(raw.get("step_count") or 0),
            saved_at=float(raw.get("saved_at") or 0.0),
            fingerprint=raw.get("fingerprint") if isinstance(raw.get("fingerprint"), str) else "",
        )

    def save(
        self,
        description: str,
        start_url: str,
        script: str,
        verdict: EvidenceVerdict,
        *,
        controls=None,
        landed_url: str = "",
    ) -> bool:
        """Store a script that the evidence judge passed. Anything else is refused."""
        if verdict is None or verdict.verdict != PASS:
            return False
        pattern = url_pattern_for(start_url)
        if not pattern:
            return False
        try:
            text = replayable_script(script, start_url)
        except ScriptError:
            return False
        entries = self._load()
        key = cache_key(description, start_url)
        host = site_of(landed_url) or site_of(start_url)
        entries[key] = {
            "intent": task_intent(description),
            "site": site_of(start_url),
            "url_pattern": pattern,
            "script": text,
            "step_count": len(script_steps(text)),
            "saved_at": time.time(),
            "fingerprint": page_fingerprint(host, controls),
        }
        return self._write(entries)

    def drop(self, description: str, start_url: str) -> None:
        entries = self._load()
        if entries.pop(cache_key(description, start_url), None) is not None:
            self._write(entries)

    def __len__(self) -> int:
        return len(self._load())
