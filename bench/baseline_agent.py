"""Frozen baseline: read the page, take one action per model call.

This file is hashed into bench/baseline.json. Do not edit it after that pin.
The tiered loop is the candidate. This agent is not.
"""

from __future__ import annotations

from loop.actions import ActionBatch
from loop.planner import ModelPlanner

SYSTEM_ONE = (
    "You are a browser planner. You receive one observation and return one JSON object, no markdown. "
    "Return exactly one action. Do not fill two fields. Do not click and fill in the same response. "
    'Schema: {"reason":"short","done":false,"actions":[{"type":"fill","role":"textbox","name":"Item","text":"milk"}]}. '
    "Prefer role and name copied from the observation. A ref is only valid on this page. "
    "A search field is a textbox. Fill it in this response. Press Enter in a later response. "
    "Do not click a Search button. "
    "Do not submit when the task says not to. "
    "Checkbox and radio names are clicked, not filled. "
    "A combobox is {\"type\":\"choose\",\"role\":\"combobox\",\"name\":\"Dropdown\",\"option\":\"Two\"}. "
    "Omit assertion. "
    "Set done to true only when this single action completes the task. "
    "If history already did an action, do the next one. Do not repeat a fill that already has the right value."
)


class OneActionPlanner:
    """The model may plan several steps. This agent runs only the first."""

    def __init__(self, inner: ModelPlanner):
        self.inner = inner

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def reset(self) -> None:
        self.inner.reset()

    def plan(self, task: str, observation, history: list[dict]) -> ActionBatch:
        batch = self.inner.plan(task, observation, history)
        if len(batch.actions) <= 1:
            return ActionBatch(batch.reason, list(batch.actions), None, batch.done)
        return ActionBatch(batch.reason, [batch.actions[0]], None, False)


def make_baseline_planner() -> OneActionPlanner:
    return OneActionPlanner(ModelPlanner.from_env(system=SYSTEM_ONE))
