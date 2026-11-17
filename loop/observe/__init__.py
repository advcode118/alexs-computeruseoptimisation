"""Ways to read a page into an Observation."""

from loop.observe.aria import parse_aria_snapshot
from loop.observe.base import ObservationSource, observation_from_snapshot
from loop.observe.dom import DomSource

__all__ = [
    "DomSource",
    "ObservationSource",
    "observation_from_snapshot",
    "parse_aria_snapshot",
]
