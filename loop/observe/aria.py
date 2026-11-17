"""Parse a @playwright/mcp 0.0.84 accessibility snapshot into a Snapshot.

Lines look like `- button "Search" [ref=e12]`. A frame ref is `f1e12`.
`--snapshot-boxes` adds `[box=x,y,width,height]`. Action tools take that ref
as `target`. Nodes without a ref, `text:` lines, and `/url:` lines are not elements.
"""

from __future__ import annotations

import re

from core.backend import Bounds, Element, Snapshot

_ROLE_RE = re.compile(r"^([A-Za-z][\w-]*)(.*)$", re.DOTALL)
_VALUE_RE = re.compile(r'\bvalue="((?:\\.|[^"\\])*)"')
_BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
_FENCE_RE = re.compile(r"```(?:ya?ml)?\s*\n(.*?)```", re.DOTALL)
_FORM_ROLES = {"textbox", "searchbox", "combobox", "spinbutton"}


def parse_aria_snapshot(
    text: str,
    *,
    url: str = "",
    title: str = "",
    app: str = "browser",
) -> Snapshot:
    """Parse snapshot YAML into elements. url and title come from the caller."""
    body = _snapshot_body(text)
    elements: list[Element] = []
    # indent, path segment
    stack: list[tuple[int, str]] = []
    focused_id: str | None = None
    for raw in body.splitlines():
        if not raw.strip() or raw.strip() == "..." or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if not line.startswith("- "):
            continue
        content = line[2:].strip()
        if content.startswith("text:") or content.startswith("/"):
            continue
        parsed = _parse_node(content)
        if parsed is None:
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = tuple(segment for _, segment in stack)
        role, name = parsed["role"], parsed["name"]
        segment = f"{role}:{name}" if name else role
        stack.append((indent, segment))
        ref = parsed["ref"]
        if not ref:
            continue
        states = parsed["states"]
        element = Element(
            id=ref,
            role=role,
            name=name,
            value=parsed["value"],
            bounds=parsed["bounds"],
            states=states,
            path=path,
            source="aria",
        )
        elements.append(element)
        if focused_id is None and ("active" in states or "focused" in states):
            focused_id = ref
    return Snapshot(
        elements=tuple(elements),
        app=app,
        window=title,
        url=url,
        title=title,
        focused_id=focused_id,
    )


def _snapshot_body(text: str) -> str:
    fenced = _FENCE_RE.search(text)
    if fenced:
        return fenced.group(1)
    return text


def _parse_node(content: str) -> dict | None:
    match = _ROLE_RE.match(content)
    if match is None:
        return None
    role = match.group(1)
    rest = match.group(2).lstrip()
    name = ""
    if rest.startswith('"'):
        name, rest = _read_quoted(rest)
    value = ""
    value_match = _VALUE_RE.search(rest)
    if value_match:
        value = _unescape(value_match.group(1))
        rest = rest[: value_match.start()] + rest[value_match.end() :]
    ref = ""
    bounds = None
    states: list[str] = []
    for bracket in _BRACKET_RE.finditer(rest):
        inside = bracket.group(1).strip()
        if not inside:
            continue
        if "=" in inside:
            key, raw_value = inside.split("=", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if key == "ref":
                ref = raw_value
            elif key == "box":
                bounds = _parse_box(raw_value)
        else:
            states.append(inside)
    rest = _BRACKET_RE.sub("", rest).strip()
    if rest.startswith(":"):
        text = rest[1:].strip()
        if text and role in _FORM_ROLES and not value:
            value = text
        elif text and not name:
            name = text
    name = name.replace("\t", " ").replace("\n", " ").strip()
    return {
        "role": role,
        "name": name,
        "value": value,
        "ref": ref,
        "bounds": bounds,
        "states": tuple(states),
    }


def _read_quoted(text: str) -> tuple[str, str]:
    chars: list[str] = []
    index = 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            if index + 1 < len(text):
                chars.append(text[index + 1])
                index += 2
                continue
        if char == '"':
            return "".join(chars), text[index + 1 :]
        chars.append(char)
        index += 1
    return "".join(chars), ""


def _unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\\\", "\\")


def _parse_box(value: str) -> Bounds | None:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        return None
    try:
        x, y, width, height = (float(part) for part in parts)
    except ValueError:
        return None
    return Bounds(x, y, width, height)
