"""Backend over the current page script.

Refs are data-cu-ref attributes from loop.browser.observe. Bounds are omitted;
that script does not report a box. When a ref is missing from the page, act
finds one control with the same role and name and stamps the ref onto it.
"""

from __future__ import annotations

from core.backend import Capabilities, Element, Locator, Snapshot, refind_element, resolve_locator
from loop.actions import ActionError
from loop.browser import BrowserSession, act, observe


class DomBackend:
    def __init__(self, session: BrowserSession):
        self.session = session
        self._snapshot = Snapshot(app="browser", elements=())
        self._previous: dict[str, Element] = {}

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            semantic_actions=True,
            events=False,
            screenshots=True,
            coordinate_input=False,
            source="dom",
        )

    def observe(self, scope: str | None = None) -> Snapshot:
        del scope
        page = self._page()
        observation = observe(page)
        elements = _elements_from_observation(observation)
        self._previous = {element.id: element for element in self._snapshot.elements}
        self._snapshot = Snapshot(
            elements=elements,
            app="browser",
            window=observation.title,
            url=observation.url,
            title=observation.title,
        )
        return self._snapshot

    def act(self, action: object) -> None:
        page = self._page()
        ref = getattr(action, "ref", None)
        if isinstance(ref, str) and ref and page.locator(f'[data-cu-ref="{ref}"]').count() == 0:
            self._stamp(page, ref)
        act(page, action)

    def settle(self, prev: Snapshot | None = None, timeout: float = 3.0) -> Snapshot:
        del prev
        page = self._page()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=max(1, int(timeout * 1000)))
        except Exception:
            pass
        return self.observe()

    def refind(self, element: Element) -> Element | None:
        return refind_element(element, self._snapshot.elements)

    def resolve(self, locator: Locator) -> Element | None:
        return resolve_locator(
            locator,
            self._snapshot.elements,
            app=self._snapshot.app,
            window=self._snapshot.window,
        )

    def _page(self):
        if self.session.page is None:
            raise ActionError("The browser is not open.")
        return self.session.page

    def _stamp(self, page, ref: str) -> None:
        """Put ref back on the one control that still has this role and name."""
        identity = self._previous.get(ref)
        if identity is None:
            identity = next((element for element in self._snapshot.elements if element.id == ref), None)
        if identity is None or not identity.name.strip():
            return
        try:
            locator = page.get_by_role(identity.role, name=identity.name, exact=True)
            count = locator.count()
        except Exception:
            return
        if count != 1:
            raise ActionError(
                f"stale ref {ref} for {identity.role} {identity.name!r}. Matched {count} controls."
            )
        locator.evaluate("(node, id) => node.setAttribute('data-cu-ref', id)", ref)


def _elements_from_observation(observation) -> tuple[Element, ...]:
    elements: list[Element] = []
    seen: set[str] = set()
    for control in observation.controls:
        seen.add(control.ref)
        elements.append(
            Element(
                id=control.ref,
                role=control.role,
                name=control.name,
                value=control.value,
                source="dom",
            )
        )
    for line in observation.html.splitlines():
        role, separator, rest = line.partition("\t")
        name, separator, ref = rest.partition("\t")
        if not separator or not ref or ref in seen:
            continue
        seen.add(ref)
        elements.append(Element(id=ref, role=role.strip(), name=name.strip(), source="dom"))
    return tuple(elements)
