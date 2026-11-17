"""Backend over @playwright/mcp 0.0.84 snapshot text.

This does not spawn the server. observe() is the last snapshot loaded.
act() records the tool call the server would receive. Click and type take
`target`. A ref that is missing, or reused for a different role and name,
is replaced when one current element has the old role and name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.backend import Capabilities, Element, Locator, Snapshot, refind_element, resolve_locator
from loop.actions import ActionError, Click, Fill, Goto, Press, Scroll
from loop.observe.aria import parse_aria_snapshot

PLAYWRIGHT_MCP_VERSION = "0.0.84"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, object]
    repaired: bool = False


class PlaywrightMcpBackend:
    def __init__(self):
        self._snapshot = Snapshot(app="browser", elements=())
        self._previous: dict[str, Element] = {}
        self.calls: list[ToolCall] = []

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            semantic_actions=True,
            events=False,
            screenshots=False,
            coordinate_input=False,
            source="aria",
        )

    def load_snapshot(self, text: str, *, url: str = "", title: str = "") -> Snapshot:
        self._previous = {element.id: element for element in self._snapshot.elements}
        self._snapshot = parse_aria_snapshot(text, url=url, title=title)
        return self._snapshot

    def observe(self, scope: str | None = None) -> Snapshot:
        del scope
        return self._snapshot

    def act(self, action: object) -> None:
        self.calls.append(self.tool_call(action))

    def settle(self, prev: Snapshot | None = None, timeout: float = 3.0) -> Snapshot:
        """No child process yet, so settle is the snapshot already loaded."""
        del prev, timeout
        return self._snapshot

    def refind(self, element: Element) -> Element | None:
        return refind_element(element, self._snapshot.elements)

    def resolve(self, locator: Locator) -> Element | None:
        return resolve_locator(
            locator,
            self._snapshot.elements,
            app=self._snapshot.app,
            window=self._snapshot.window,
        )

    def tool_call(self, action: object) -> ToolCall:
        if isinstance(action, Goto):
            return ToolCall("browser_navigate", {"url": action.url})
        if isinstance(action, Click):
            target, repaired, element = self._resolve_target(action.ref)
            return ToolCall("browser_click", _target_args(target, element), repaired)
        if isinstance(action, Fill):
            target, repaired, element = self._resolve_target(action.ref)
            arguments = _target_args(target, element)
            arguments["text"] = action.text
            return ToolCall("browser_type", arguments, repaired)
        if isinstance(action, Press):
            return ToolCall("browser_press_key", {"key": action.key})
        if isinstance(action, Scroll):
            raise ActionError(f"Playwright MCP {PLAYWRIGHT_MCP_VERSION} has no scroll tool.")
        raise ActionError(f"unknown action: {action!r}")

    def _resolve_target(self, ref: str) -> tuple[str, bool, Element | None]:
        current = {element.id: element for element in self._snapshot.elements}
        live = current.get(ref)
        previous = self._previous.get(ref)
        if live is not None and (previous is None or _same_identity(live, previous)):
            return ref, False, live
        identity = previous
        if identity is None:
            raise ActionError(f"unknown ref {ref}. Observe again; the page may have changed.")
        found = refind_element(identity, self._snapshot.elements)
        if found is None:
            raise ActionError(
                f"stale ref {ref} for {identity.role} {identity.name!r}. "
                "No single role and name match in the latest snapshot."
            )
        return found.id, True, found


def _same_identity(left: Element, right: Element) -> bool:
    left_name = re.sub(r"\s+", " ", left.name).strip().casefold()
    right_name = re.sub(r"\s+", " ", right.name).strip().casefold()
    return left.role.casefold() == right.role.casefold() and left_name == right_name


def _target_args(target: str, element: Element | None) -> dict[str, object]:
    arguments: dict[str, object] = {"target": target}
    if element is not None and element.name.strip():
        arguments["element"] = f'{element.role} "{element.name}"'
    return arguments
