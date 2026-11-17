"""ObservationSource for the data-cu-ref page script."""

from __future__ import annotations

from loop.actions import ActionError, Observation
from loop.browser import BrowserSession, observe


class DomSource:
    """Reads the page the browser session already has open."""

    def __init__(self, session: BrowserSession):
        self.session = session

    def observe(self) -> Observation:
        if self.session.page is None:
            raise ActionError("The browser is not open.")
        return observe(self.session.page)
