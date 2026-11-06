"""Compact page diff for the Playwright proxy.

The child snapshot is the full accessibility tree. The agent is shown a
pruned first view, then a diff: added, removed, and changed nodes, with the
role, name, and ref. A control that is still on the page keeps the ref from
the previous view, even when Playwright assigns a new one. Unchanged
subtrees are left out.

depth_snapshot_text and find_result_text reproduce the text Playwright MCP
returns for a target/depth snapshot and for browser_find, so a test can
compare sizes without calling the child.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

UNCHANGED = "(unchanged)"
_FENCE = re.compile(
    r"### Snapshot\s*```(?:ya?ml)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_REF = re.compile(r"\[ref=([^\]]+)\]")
_VALUE = re.compile(r'\bvalue="((?:\\.|[^"\\])*)"')
_BRACKET = re.compile(r"\[([^\[\]]*)\]")
_FORM_ROLES = {"textbox", "searchbox", "combobox", "spinbutton"}
_FLATTEN = {"generic", "none", "presentation"}
_KEEP_STATES = {"checked", "disabled", "expanded", "collapsed", "selected", "pressed", "active", "focused"}
_FIND_CONTEXT = 3


@dataclass
class Node:
    role: str
    name: str
    ref: str
    value: str = ""
    states: tuple[str, ...] = ()
    url: str = ""
    texts: tuple[str, ...] = ()
    children: list["Node"] = field(default_factory=list)
    stable: str = ""


@dataclass
class View:
    text: str
    full_chars: int
    diff_chars: int


class PageMemory:
    """Last tree the agent can still address, keyed by the ref we showed."""

    def __init__(self) -> None:
        self.last_nodes: list[Node] | None = None
        self.shown: bool = False
        self.live_for_stable: dict[str, str] = {}

    def reindex(self) -> None:
        mapping: dict[str, str] = {}
        for node in _walk(self.last_nodes or []):
            stable = node.stable or node.ref
            live = node.ref or stable
            if stable:
                mapping[stable] = live
        self.live_for_stable = mapping


def memory_of(child) -> PageMemory:
    memory = getattr(child, "_page_memory", None)
    if isinstance(memory, PageMemory):
        return memory
    memory = PageMemory()
    setattr(child, "_page_memory", memory)
    return memory


def snapshot_body(raw: str) -> str:
    """Accessibility tree, without the Page section or the fence."""
    fenced = _FENCE.search(raw or "")
    if fenced:
        return fenced.group(1).strip("\n")
    lines: list[str] = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("- Page ") or stripped.startswith("###"):
            continue
        if stripped.startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines).strip("\n")


def note_baseline(memory: PageMemory, raw: str) -> None:
    """Remember the first snapshot in a call. Later reads do not replace it."""
    if memory.last_nodes is not None:
        return
    nodes = parse_tree(snapshot_body(raw))
    _assign_fresh(nodes)
    memory.last_nodes = nodes
    memory.shown = False
    memory.reindex()


def show_snapshot(memory: PageMemory, raw: str) -> View:
    """Pruned first view, or a diff against the baseline. Updates the ref map."""
    body = snapshot_body(raw)
    nodes = parse_tree(body)
    full_chars = len(raw or "")
    if memory.last_nodes is None:
        _assign_fresh(nodes)
        text = prune_tree(nodes) or "(empty)"
        memory.last_nodes = nodes
        memory.shown = True
        memory.reindex()
        return View(text, full_chars, len(text))
    diff_text = align_and_diff(memory.last_nodes, nodes)
    pruned = prune_tree(nodes) or "(empty)"
    if diff_text == UNCHANGED and not memory.shown:
        text = pruned
    elif diff_text != UNCHANGED and len(pruned) < len(diff_text):
        text = pruned
    else:
        text = diff_text
    memory.last_nodes = nodes
    memory.shown = True
    memory.reindex()
    return View(text, full_chars, len(text))


def view_result_text(view: View, preface: str = "") -> str:
    """Tool text: optional short action note, the diff, and the two sizes."""
    note = _preface(preface)
    sizes = f"full_snapshot_chars: {view.full_chars}\ndiff_chars: {view.diff_chars}"
    return "\n".join(part for part in (note, view.text, sizes) if part)


def rewrite_arguments(memory: PageMemory, arguments: dict | None) -> dict | None:
    """Send Playwright the live ref for a ref this proxy still advertises."""
    if not isinstance(arguments, dict):
        return arguments
    updated = dict(arguments)
    for key in ("target", "startTarget", "endTarget"):
        value = updated.get(key)
        if not isinstance(value, str):
            continue
        live = memory.live_for_stable.get(value)
        if live and live != value:
            updated[key] = live
    return updated


def full_snapshot_text(yaml: str, *, url: str, title: str) -> str:
    """Text browser_snapshot returns for the whole tree."""
    return _snapshot_response(yaml, url=url, title=title)


def depth_snapshot_text(
    yaml: str,
    *,
    url: str,
    title: str,
    target: str | None,
    depth: int,
) -> str:
    """Text browser_snapshot returns for target and depth."""
    return _snapshot_response(limit_depth(yaml, target=target, depth=depth), url=url, title=title)


def find_result_text(yaml: str, text: str) -> str:
    """Text browser_find returns for a plain-text query."""
    return "### Result\n" + render_find(yaml, text)


def limit_depth(yaml: str, *, target: str | None, depth: int) -> str:
    """Keep lines whose depth from the root (or target) is at most `depth`.

    Depth counts 2-space indent levels, matching Playwright's snapshot depth:
    the target is included, its children are depth 1, and a node whose
    children were cut loses a trailing colon.
    """
    lines = yaml.splitlines()
    start, end, base = 0, len(lines), 0
    if target:
        found = _line_with_ref(lines, target)
        if found is None:
            return yaml
        base = _indent(lines[found])
        start = found
        end = found + 1
        while end < len(lines):
            if lines[end].strip() and _indent(lines[end]) <= base:
                break
            end += 1
    kept: list[tuple[int, str]] = []
    for line in lines[start:end]:
        if not line.strip():
            continue
        relative = (_indent(line) - base) // 2
        if relative <= depth:
            kept.append((relative, line[base:] if len(line) >= base else line.lstrip()))
    rendered: list[str] = []
    for index, (relative, text) in enumerate(kept):
        has_child = index + 1 < len(kept) and kept[index + 1][0] > relative
        stripped = text.rstrip()
        if not has_child and stripped.endswith(":"):
            text = stripped[:-1].rstrip()
        rendered.append(text)
    return "\n".join(rendered)


def render_find(yaml: str, text: str) -> str:
    """browser_find body: matches, three lines of context, path from the root.

    Gaps off the path to a match are marked with `...`. This follows the
    tool in @playwright/mcp 0.0.84 (contextLines = 3).
    """
    lines = yaml.splitlines()
    indents = [_indent(line) for line in lines]
    needle = text.casefold()
    matched = [index for index, line in enumerate(lines) if needle in line.casefold()]
    query = f'"{text}"'
    if not matched:
        return f"No matches found for {query}."
    windows: list[list[int]] = []
    for line_no in matched:
        start = max(0, line_no - _FIND_CONTEXT)
        end = min(len(lines) - 1, line_no + _FIND_CONTEXT)
        if windows and start <= windows[-1][1] + 1:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
    path: set[int] = set()
    for line_no in matched:
        path.add(line_no)
        path.update(_ancestors(lines, indents, line_no))
    snippets: list[str] = []
    for start, end in windows:
        indices = _ancestors(lines, indents, start)
        indices.extend(range(start, end + 1))
        out: list[str] = []
        for position, index in enumerate(indices):
            previous = indices[position - 1] if position else None
            if (
                previous is not None
                and index > previous + 1
                and index not in path
                and previous not in path
            ):
                out.append(" " * indents[index] + "...")
            out.append(lines[index])
        snippets.append("\n".join(out))
    word = "match" if len(matched) == 1 else "matches"
    return f"Found {len(matched)} {word} for {query}:\n\n" + "\n\n----\n\n".join(snippets)


def parse_tree(yaml: str) -> list[Node]:
    roots: list[Node] = []
    stack: list[tuple[int, Node]] = []
    for raw in (yaml or "").splitlines():
        if not raw.strip():
            continue
        indent = _indent(raw)
        content = raw.strip()
        if not content.startswith("- "):
            continue
        body = content[2:].strip()
        if body.startswith("text:"):
            _attach_text(stack, indent, body[len("text:") :].strip())
            continue
        if body.startswith("/url:"):
            _attach_url(stack, indent, body[len("/url:") :].strip())
            continue
        parsed = _parse_content(body)
        if parsed is None:
            continue
        node = Node(
            role=parsed["role"],
            name=parsed["name"],
            ref=parsed["ref"],
            value=parsed["value"],
            states=parsed["states"],
            texts=parsed["texts"],
        )
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)
        stack.append((indent, node))
    return roots


def prune_tree(nodes: list[Node]) -> str:
    """First view: role, name, ref, and state. No boxes, urls, or anonymous wrappers."""
    return "\n".join(_prune_lines(nodes, 0))


def align_and_diff(old: list[Node], new: list[Node]) -> str:
    """Assign stable refs on `new` and describe added, removed, and changed nodes."""
    lines: list[str] = []
    pairs, removed, added = _pair(old, new)
    for old_index, new_index in sorted(pairs, key=lambda pair: pair[1]):
        previous = old[old_index]
        current = new[new_index]
        current.stable = previous.stable or previous.ref
        child_lines = align_and_diff(previous.children, current.children)
        if _signature(previous) != _signature(current):
            lines.append(_format("~", current))
        if child_lines and child_lines != UNCHANGED:
            lines.extend(child_lines.splitlines())
    for index in removed:
        lines.append(_format("-", old[index]))
    for index in added:
        _assign_fresh([new[index]])
        lines.append(_format("+", new[index]))
    if not lines:
        return UNCHANGED
    return "\n".join(lines)


def _snapshot_response(yaml: str, *, url: str, title: str) -> str:
    page = [f"- Page URL: {url}"]
    if title:
        page.append(f"- Page Title: {title}")
    return "\n".join(
        [
            "### Page",
            *page,
            "### Snapshot",
            "```yaml",
            yaml,
            "```",
        ]
    )


def _preface(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned or cleaned == "ok":
        return ""
    if "### Snapshot" in cleaned or len(cleaned) > 500:
        return ""
    return cleaned


def _line_with_ref(lines: list[str], target: str) -> int | None:
    for index, line in enumerate(lines):
        if target in _REF.findall(line):
            return index
    return None


def _ancestors(lines: list[str], indents: list[int], index: int) -> list[int]:
    result: list[int] = []
    indent = indents[index]
    for cursor in range(index - 1, -1, -1):
        if indent <= 0:
            break
        if not lines[cursor].strip():
            continue
        if indents[cursor] < indent:
            result.append(cursor)
            indent = indents[cursor]
    result.reverse()
    return result


def _attach_text(stack: list[tuple[int, Node]], indent: int, text: str) -> None:
    while stack and stack[-1][0] >= indent:
        stack.pop()
    if stack and text:
        parent = stack[-1][1]
        parent.texts = parent.texts + (text,)


def _attach_url(stack: list[tuple[int, Node]], indent: int, url: str) -> None:
    while stack and stack[-1][0] >= indent:
        stack.pop()
    if stack and url:
        stack[-1][1].url = url


def _parse_content(content: str) -> dict | None:
    match = re.match(r"^([A-Za-z][\w-]*)(.*)$", content, re.DOTALL)
    if match is None:
        return None
    role = match.group(1)
    rest = match.group(2).lstrip()
    name = ""
    if rest.startswith('"'):
        name, rest = _read_quoted(rest)
        rest = rest.lstrip()
    value = ""
    value_match = _VALUE.search(rest)
    if value_match:
        value = value_match.group(1).replace('\\"', '"').replace("\\\\", "\\")
        rest = rest[: value_match.start()] + rest[value_match.end() :]
    ref = ""
    states: list[str] = []
    for bracket in _BRACKET.finditer(rest):
        inside = bracket.group(1).strip()
        if not inside or inside.startswith("box=") or inside.startswith("cursor="):
            continue
        if "=" in inside:
            key, raw_value = inside.split("=", 1)
            key = key.strip()
            if key == "ref":
                ref = raw_value.strip()
            elif key == "level":
                states.append(f"level={raw_value.strip()}")
        else:
            states.append(inside)
    rest = _BRACKET.sub("", rest).strip()
    texts: tuple[str, ...] = ()
    if rest.startswith(":"):
        inline = rest[1:].strip()
        if inline and role in _FORM_ROLES and not value:
            value = inline
        elif inline:
            texts = (inline,)
    return {
        "role": role,
        "name": name.replace("\t", " ").replace("\n", " ").strip(),
        "ref": ref,
        "value": value,
        "states": tuple(states),
        "texts": texts,
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


def _signature(node: Node) -> tuple:
    return (node.role, node.name, node.value, node.states, node.url, node.texts)


def _format(mark: str, node: Node) -> str:
    name = f' "{node.name}"' if node.name else ""
    flags = []
    for state in node.states:
        if state in _KEEP_STATES or state.startswith("level="):
            flags.append(f"[{state}]")
    state_text = "".join(f" {flag}" for flag in flags)
    ref = node.stable or node.ref
    value = f": {node.value}" if node.value else ""
    extra = ""
    if mark == "~" and node.texts:
        extra = " text: " + " ".join(node.texts)
    ref_bit = f" [ref={ref}]" if ref else ""
    return f"{mark} {node.role}{name}{state_text}{ref_bit}{value}{extra}".rstrip()


def _prune_lines(nodes: list[Node], indent: int) -> list[str]:
    lines: list[str] = []
    pad = "  " * indent
    for node in nodes:
        anonymous = not node.name and not node.ref
        if anonymous and (node.role in _FLATTEN or node.role == "group"):
            lines.extend(_prune_lines(node.children, indent))
            continue
        if anonymous:
            lines.extend(_prune_lines(node.children, indent))
            continue
        lines.append(pad + _format("-", node))
        lines.extend(_prune_lines(node.children, indent + 1))
    return lines


def _pair(old: list[Node], new: list[Node]) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    used_old: set[int] = set()
    used_new: set[int] = set()
    pairs: list[tuple[int, int]] = []
    by_ref: dict[str, int] = {}
    for index, node in enumerate(old):
        for token in (node.stable, node.ref):
            if token and token not in by_ref:
                by_ref[token] = index
    for index, node in enumerate(new):
        previous = by_ref.get(node.ref)
        if previous is None or previous in used_old:
            continue
        pairs.append((previous, index))
        used_old.add(previous)
        used_new.add(index)
    _pair_by(old, new, pairs, used_old, used_new, lambda node: (node.role, node.name))
    _pair_by(old, new, pairs, used_old, used_new, lambda node: (node.role,))
    removed = [index for index in range(len(old)) if index not in used_old]
    added = [index for index in range(len(new)) if index not in used_new]
    return pairs, removed, added


def _pair_by(old, new, pairs, used_old, used_new, key) -> None:
    old_groups: dict[object, list[int]] = {}
    new_groups: dict[object, list[int]] = {}
    for index, node in enumerate(old):
        if index in used_old:
            continue
        old_groups.setdefault(key(node), []).append(index)
    for index, node in enumerate(new):
        if index in used_new:
            continue
        new_groups.setdefault(key(node), []).append(index)
    for group_key, old_indexes in old_groups.items():
        new_indexes = new_groups.get(group_key, [])
        for old_index, new_index in zip(old_indexes, new_indexes):
            pairs.append((old_index, new_index))
            used_old.add(old_index)
            used_new.add(new_index)


def _assign_fresh(nodes: list[Node]) -> None:
    for node in _walk(nodes):
        node.stable = node.ref


def _walk(nodes: list[Node]):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
