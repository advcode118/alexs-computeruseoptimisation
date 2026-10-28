"""One planner call returns a batch of browser actions.

The fake planner needs no API key. The model planner is a single
OpenAI-compatible chat completion (default model gpt-4o-mini).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from loop.actions import (
    ActionBatch,
    ActionError,
    AssertText,
    AssertTitle,
    Click,
    Fill,
    Goto,
    Observation,
    PlannerError,
    parse_batch,
)

DEMO_TASK = "Add milk to the packing list"
_ITEM_RE = re.compile(r"add\s+(.+?)\s+to\s+the\s+packing\s+list", re.IGNORECASE)

_SYSTEM = (
    "You are a browser planner. You receive one observation and return one batch. "
    "Reply with JSON only, no markdown. Schema: "
    '{"reason":"short","done":false,"actions":['
    '{"type":"goto","url":"https://example.com"},'
    '{"type":"click","ref":"e1"},'
    '{"type":"fill","ref":"e1","text":"milk"},'
    '{"type":"press","key":"Enter","ref":"e1"},'
    '{"type":"scroll","direction":"down","amount":400}'
    '],"assertion":{"type":"text","text":"expected"}}. '
    "assertion may be null. Its type is url, title, or text. "
    "Use only refs from the observation. Keep the batch to a few actions. "
    "Set done to true when the task is finished, with an empty actions list."
)


def parse_item(task: str) -> str:
    match = _ITEM_RE.search(task.strip())
    if not match:
        return "milk"
    return match.group(1).strip().strip(".")


def find_ref(observation: Observation, *, role: str, name: str) -> str | None:
    needle = name.lower()
    for control in observation.controls:
        if control.role == role and needle in control.name.lower():
            return control.ref
    return None


class FakePlanner:
    """Scripted packing-list task so the loop runs with no API key."""

    def __init__(self, fixture_url: str):
        self.fixture_url = fixture_url
        self.phase = 0

    def reset(self) -> None:
        self.phase = 0

    def plan(self, task: str, observation: Observation, history: list[dict]) -> ActionBatch:
        del history
        item = parse_item(task)
        if self.phase == 0:
            self.phase = 1
            if not _on_fixture(observation, self.fixture_url):
                return ActionBatch(
                    reason="Open the packing list.",
                    actions=[Goto(self.fixture_url)],
                    assertion=AssertTitle("Packing list"),
                    done=False,
                )
        if self.phase == 1:
            self.phase = 2
            textbox = find_ref(observation, role="textbox", name="Item")
            button = find_ref(observation, role="button", name="Add")
            if textbox is None or button is None:
                return ActionBatch(
                    reason="The packing-list controls are not on this page.",
                    actions=[],
                    assertion=None,
                    done=True,
                )
            return ActionBatch(
                reason=f"Type {item} and add it.",
                actions=[Fill(textbox, item), Click(button)],
                assertion=AssertText(item),
                done=False,
            )
        return ActionBatch(
            reason=f"{item} is on the list.",
            actions=[],
            assertion=None,
            done=True,
        )


class ScriptPlanner:
    """Replay a fixed list of batches. Used by tests."""

    def __init__(self, batches: list[ActionBatch]):
        self.batches = list(batches)
        self.index = 0

    def reset(self) -> None:
        self.index = 0

    def plan(self, task: str, observation: Observation, history: list[dict]) -> ActionBatch:
        del task, observation, history
        if self.index >= len(self.batches):
            return ActionBatch("No further scripted steps.", [], None, True)
        batch = self.batches[self.index]
        self.index += 1
        return batch


def _on_fixture(observation: Observation, fixture_url: str) -> bool:
    url = observation.url.split("#", 1)[0]
    if url == fixture_url:
        return True
    return url.endswith("/fixture") or url.endswith("packing.html")


def parse_model_content(content: str) -> ActionBatch:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlannerError(f"Model did not return JSON: {exc}") from exc
    try:
        return parse_batch(data)
    except ActionError as exc:
        raise PlannerError(str(exc)) from exc


class ModelPlanner:
    """One chat completion per cycle. Any OpenAI-compatible endpoint."""

    def __init__(self, *, api_key: str, base_url: str, model: str, transport=None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport or _post_chat

    def reset(self) -> None:
        return None

    def plan(self, task: str, observation: Observation, history: list[dict]) -> ActionBatch:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": task,
                            "observation": observation.to_dict(),
                            "history": history[-6:],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        content = self.transport(
            f"{self.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload,
        )
        return parse_model_content(content)

    @classmethod
    def from_env(cls) -> "ModelPlanner":
        api_key = os.environ.get("LOOP_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        if not api_key:
            raise PlannerError(
                "The model planner needs LOOP_API_KEY or OPENAI_API_KEY. "
                "Use the fake planner to run with no key."
            )
        return cls(
            api_key=api_key,
            base_url=os.environ.get("LOOP_BASE_URL", "https://api.openai.com/v1"),
            model=os.environ.get("LOOP_MODEL", "gpt-4o-mini"),
        )


def _post_chat(url: str, headers: dict, payload: dict) -> str:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise PlannerError(f"Model request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise PlannerError(f"Model request failed: {exc.reason}") from exc
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PlannerError("Model response did not include a message.") from exc


def make_planner(name: str, fixture_url: str):
    if name == "fake":
        return FakePlanner(fixture_url)
    if name == "model":
        return ModelPlanner.from_env()
    raise PlannerError(f"unknown planner: {name}")
