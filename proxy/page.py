"""Turn a Playwright MCP tool result into an observation and a short paragraph.

The child is started with --snapshot-mode none, so the page is whatever
browser_snapshot returned. url and title are the "- Page URL:" and
"- Page Title:" lines. The accessibility tree is the fenced snapshot.
"""

from __future__ import annotations

import re

from loop.actions import Control, Observation
from loop.observe.aria import parse_aria_snapshot

_PAGE_FIELD = re.compile(r"(?m)^- Page ([A-Za-z]+):\s*(.+?)\s*$")
_SNAPSHOT_FENCE = re.compile(
    r"### Snapshot\s*```(?:ya?ml)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_PARAGRAPH_LIMIT = 500
_VISIBLE_CONTROLS = 8


def tool_text(result: dict) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts)


def page_field(text: str, label: str) -> str:
    for match in _PAGE_FIELD.finditer(text or ""):
        if match.group(1).lower() == label.lower():
            return match.group(2).strip()
    return ""


def snapshot_yaml(text: str) -> str:
    fenced = _SNAPSHOT_FENCE.search(text or "")
    if fenced:
        return fenced.group(1).strip()
    lines: list[str] = []
    for line in (text or "").splitlines():
        if line.strip().startswith("- Page "):
            continue
        if "[ref=" in line:
            lines.append(line)
    return "\n".join(lines).strip()


def observation_from_tool_text(text: str) -> tuple[Observation, str]:
    """Observation for decide(), plus the YAML passed to the action backend."""
    yaml = snapshot_yaml(text)
    url = page_field(text, "URL")
    title = page_field(text, "Title")
    parsed = parse_aria_snapshot(yaml, url=url, title=title)
    controls = [
        Control(element.id, element.role, element.name, element.value)
        for element in parsed.elements
        if element.id
    ]
    html = "\n".join(f"{control.role}\t{control.name}\t{control.ref}" for control in controls)
    return Observation(url or parsed.url, title or parsed.title, controls, html=html), yaml


def page_paragraph(observation: Observation) -> str:
    """One paragraph: title, url, and a few visible control names."""
    title = observation.title.strip() or "Untitled page"
    url = observation.url.strip() or "an unknown url"
    seen: list[str] = []
    for control in observation.controls:
        name = re.sub(r"\s+", " ", control.name).strip()
        if not name:
            continue
        label = f"{control.role} {name}" if control.role else name
        if label in seen:
            continue
        seen.append(label)
        if len(seen) == _VISIBLE_CONTROLS:
            break
    visible = ", ".join(seen) if seen else "no named controls"
    text = f"{title} ({url}). Visible: {visible}."
    if len(text) <= _PARAGRAPH_LIMIT:
        return text
    return text[: _PARAGRAPH_LIMIT - 3].rstrip() + "..."
