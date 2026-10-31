"""Switches for one change at a time. The bench keeps a flag only when it wins."""

from __future__ import annotations

# The direct role-and-name path, batched actions, a warm browser, and the
# accessibility tree are already how this loop runs. Replay, handoff, and
# prompt caching start off until a measured run keeps them.
DEFAULTS = {
    "direct_match": True,
    "batch_actions": True,
    "warm_browser": True,
    "a11y_before_image": True,
    "replay": False,
    "handoff": False,
    "prompt_cache": False,
}
