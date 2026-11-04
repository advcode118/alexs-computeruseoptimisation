"""Shared types for a UI backend. No browser and no desktop APIs."""

from core.backend import (
    Backend,
    Bounds,
    Capabilities,
    Element,
    Locator,
    Screen,
    Snapshot,
    refind_element,
    resolve_locator,
)

__all__ = [
    "Backend",
    "Bounds",
    "Capabilities",
    "Element",
    "Locator",
    "Screen",
    "Snapshot",
    "refind_element",
    "resolve_locator",
]
