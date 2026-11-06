"""Observation is a view of a Snapshot. The engine reads that view."""

from __future__ import annotations

from typing import Protocol

from core.backend import Snapshot
from loop.actions import Control, Observation


class ObservationSource(Protocol):
    def observe(self) -> Observation:
        """Read the current page."""


def observation_from_snapshot(snapshot: Snapshot) -> Observation:
    """Controls and role/name/ref lines for the no-model route.

    The html lines are what html_tree reads. Every element with an id is included,
    in tree order.
    """
    controls: list[Control] = []
    lines: list[str] = []
    for element in snapshot.elements:
        if not element.id:
            continue
        name = element.name.replace("\t", " ")
        controls.append(Control(element.id, element.role, name, element.value))
        lines.append(f"{element.role}\t{name}\t{element.id}")
    return Observation(
        url=snapshot.url,
        title=snapshot.title,
        controls=controls,
        html="\n".join(lines),
    )
