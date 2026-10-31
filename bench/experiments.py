"""Flagged planners. Replay traces stay out of the repo."""

from __future__ import annotations

from loop.actions import ActionBatch, ClickNamed, FillNamed, ChooseNamed, PlannerError
from loop.planner import ModelPlanner


class HandoffPlanner:
    """A smaller model plans. A bigger one plans after an assertion has failed."""

    def __init__(self, small: ModelPlanner, big: ModelPlanner):
        self.small = small
        self.big = big
        self.model = small.model

    def reset(self) -> None:
        self.small.reset()
        self.big.reset()

    @property
    def calls(self) -> int:
        return self.small.calls + self.big.calls

    @property
    def input_tokens(self) -> int:
        return self.small.input_tokens + self.big.input_tokens

    @property
    def output_tokens(self) -> int:
        return self.small.output_tokens + self.big.output_tokens

    @property
    def cached_input_tokens(self) -> int:
        return self.small.cached_input_tokens + self.big.cached_input_tokens

    def plan(self, task: str, observation, history: list[dict]) -> ActionBatch:
        stuck = any(
            isinstance(item, dict) and isinstance(item.get("assertion"), dict) and item["assertion"].get("ok") is False
            for item in history
        )
        if stuck:
            self.model = self.big.model
            return self.big.plan(task, observation, history)
        self.model = self.small.model
        return self.small.plan(task, observation, history)


class ReplayPlanner:
    """Replay named steps. No model call. A missing step ends the task."""

    def __init__(self, steps: list[dict]):
        self.steps = list(steps)
        self.index = 0
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0
        self.model = None

    def reset(self) -> None:
        self.index = 0
        self.calls = 0

    def plan(self, task: str, observation, history: list[dict]) -> ActionBatch:
        del task, observation, history
        if self.index >= len(self.steps):
            return ActionBatch("Replay finished.", [], None, True)
        step = self.steps[self.index]
        self.index += 1
        action = _step_action(step)
        done = self.index >= len(self.steps)
        return ActionBatch("Replay a cached action.", [action], None, done)


def make_candidate_planner(*, handoff: bool) -> ModelPlanner | HandoffPlanner:
    if not handoff:
        return ModelPlanner.from_env()
    small = ModelPlanner.from_env()
    try:
        big = ModelPlanner.from_env(provider="anthropic")
    except PlannerError:
        return small
    if big.model == small.model and big.api_style == small.api_style:
        return small
    return HandoffPlanner(small, big)


def _step_action(step: dict):
    kind = step.get("type")
    if kind == "fill":
        return FillNamed(step["role"], step["name"], step["text"])
    if kind == "click":
        return ClickNamed(step["role"], step["name"])
    if kind == "choose":
        return ChooseNamed(step["role"], step["name"], step["option"])
    raise PlannerError("A replay step is not a named action.")
