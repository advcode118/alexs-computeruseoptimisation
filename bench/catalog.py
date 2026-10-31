"""Tasks the planner and the router may read.

Prompts built for the agent use agent_tasks(). That list is the public split.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_KINDS = {"dom", "url", "fields"}


@dataclass(frozen=True)
class Task:
    id: str
    instruction: str
    fixture: Path
    check: dict
    page: str
    holdout: bool = False


def _load_directory(directory: Path, *, holdout: bool) -> list[Task]:
    payload = json.loads((directory / "tasks.json").read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{directory.name} tasks.json must be a list")
    tasks = []
    seen: set[str] = set()
    for item in payload:
        task_id = str(item["id"])
        if task_id in seen:
            raise ValueError(f"duplicate task id {task_id}")
        seen.add(task_id)
        fixture = directory / "fixtures" / item["fixture"]
        check = item["check"]
        if not isinstance(check, dict) or check.get("kind") not in _KINDS:
            raise ValueError(f"{task_id} needs a dom, url, or fields check")
        if not fixture.is_file():
            raise ValueError(f"{task_id} is missing {fixture.name}")
        instruction = str(item["instruction"]).strip()
        if not instruction:
            raise ValueError(f"{task_id} has an empty instruction")
        tasks.append(
            Task(
                id=task_id,
                instruction=instruction,
                fixture=fixture,
                check=check,
                page=str(item.get("page", "fixture")),
                holdout=holdout,
            )
        )
    return tasks


def agent_tasks() -> list[Task]:
    """Public tasks. This is the list a prompt may include."""
    return _load_directory(Path(__file__).resolve().parent / "public", holdout=False)


def format_agent_list() -> str:
    """Text of the agent-facing list: ids and instructions, nothing else."""
    return "\n\n".join(f"{task.id}\n{task.instruction}" for task in agent_tasks())
