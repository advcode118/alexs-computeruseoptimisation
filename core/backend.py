"""Backend contract: a tree of elements, actions, settle, and refind.

Platform code stays in the backends. This module only describes elements
and finds one again after its id has gone stale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Bounds:
    """Viewport box in CSS pixels. x and y are the top-left corner."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class Element:
    """One node from a UI tree.

    id is the backend's ref for this snapshot. source is dom, aria, ax, or vision.
    path is the ancestor chain from the root, not including this node.
    Each entry is "role" or "role:name".
    """

    id: str
    role: str
    name: str
    value: str = ""
    bounds: Bounds | None = None
    states: tuple[str, ...] = ()
    path: tuple[str, ...] = ()
    source: str = ""


@dataclass(frozen=True)
class Locator:
    """A stored target. nth is the index among the same role, name, and path."""

    role: str
    name: str
    nth: int = 0
    path: tuple[str, ...] = ()
    app: str = ""
    window: str = ""


@dataclass(frozen=True)
class Screen:
    dpi_scale: float = 1.0
    displays: tuple[str, ...] = ()


@dataclass(frozen=True)
class Snapshot:
    """One read of a window or page."""

    elements: tuple[Element, ...] = ()
    app: str = ""
    window: str = ""
    url: str = ""
    title: str = ""
    focused_id: str | None = None
    screen: Screen = field(default_factory=Screen)


@dataclass(frozen=True)
class Capabilities:
    semantic_actions: bool
    events: bool
    screenshots: bool
    coordinate_input: bool
    source: str


class Backend(Protocol):
    """A UI the core can read and drive. observe may take a subtree scope."""

    @property
    def capabilities(self) -> Capabilities: ...

    def observe(self, scope: str | None = None) -> Snapshot: ...

    def act(self, action: object) -> None: ...

    def settle(self, prev: Snapshot | None = None, timeout: float = 3.0) -> Snapshot: ...

    def refind(self, element: Element) -> Element | None: ...

    def resolve(self, locator: Locator) -> Element | None: ...


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().casefold()


def _same_control(left: Element, right: Element) -> bool:
    return left.role.casefold() == right.role.casefold() and _norm(left.name) == _norm(right.name)


def refind_element(element: Element, elements: Sequence[Element]) -> Element | None:
    """Return the live element for one that may have a stale id.

    The same id counts only when the role and name still match, so a reused
    ref is not the old control. Otherwise one exact role and name is the new
    id. The ancestor path breaks a tie. Zero or several matches return none.
    An empty name is not used as a match.
    """
    same_id = next((item for item in elements if item.id == element.id), None)
    if same_id is not None and _same_control(same_id, element):
        return same_id
    if not element.name.strip():
        return None
    matches = [item for item in elements if item is not same_id and _same_control(item, element)]
    if element.path:
        pathed = [item for item in matches if item.path == element.path]
        if len(pathed) == 1:
            return pathed[0]
        if len(pathed) > 1:
            return None
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_locator(
    locator: Locator,
    elements: Sequence[Element],
    *,
    app: str = "",
    window: str = "",
) -> Element | None:
    """Pick the element a stored locator names, or none when it is not unique."""
    if locator.app and app and locator.app != app:
        return None
    if locator.window and window and locator.window != window:
        return None
    if not locator.role or not locator.name.strip():
        return None
    wanted_role = locator.role.casefold()
    wanted_name = _norm(locator.name)
    matches = [
        item
        for item in elements
        if item.role.casefold() == wanted_role and _norm(item.name) == wanted_name
    ]
    if locator.path:
        matches = [item for item in matches if item.path == locator.path]
    if locator.nth < 0 or locator.nth >= len(matches):
        return None
    return matches[locator.nth]
