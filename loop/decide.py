"""No-model routing. No API client and no browser live in this module.

decide() is the step the engine runs before a fast model or Claude.
An ActionBatch is ready to run. A TierDecision still needs a model.
None means this step has no route.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loop.actions import ActionBatch, AssertTitle, Click, Control, Fill, Observation

_SEARCH_TASK = re.compile(r"\bsearch\b", re.IGNORECASE)
_FOR_QUERY = re.compile(r"\bfor\s+(.+?)(?:\s+and\b|[?.!]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class TierDecision:
    """A step that still needs a model. tier is fast or planner."""

    tier: str
    controls: tuple[Control, ...] = ()


def matching_controls(observation: Observation, *, role: str, name: str) -> list[Control]:
    """Every control with this role whose name contains the needle.

    find_ref returns the first of these. The router needs the count.
    """
    needle = name.strip().lower()
    if not needle:
        return []
    return [
        control
        for control in observation.controls
        if control.role == role and needle in control.name.lower()
    ]


def named_targets(batch: ActionBatch, observation: Observation | None) -> list[tuple[str, str]]:
    """Role and name for each ref the batch named, in order."""
    if observation is None:
        return []
    by_ref = {control.ref: control for control in observation.controls}
    found: list[tuple[str, str]] = []
    for action in batch.actions:
        ref = getattr(action, "ref", None)
        if not isinstance(ref, str):
            continue
        control = by_ref.get(ref)
        if control is None or not control.name.strip():
            continue
        pair = (control.role, control.name)
        if pair not in found:
            found.append(pair)
    return found


def _dedupe(controls: list[Control]) -> list[Control]:
    seen: set[str] = set()
    short: list[Control] = []
    for control in controls:
        if control.ref in seen:
            continue
        seen.add(control.ref)
        short.append(control)
    return short


def ambiguous_controls(observation: Observation) -> list[Control]:
    groups: dict[tuple[str, str], list[Control]] = {}
    for control in observation.controls:
        if not control.name.strip():
            continue
        groups.setdefault((control.role, control.name.lower()), []).append(control)
    short: list[Control] = []
    for group in groups.values():
        if len(group) > 1:
            short.extend(group)
    return short


def _repeated_same_page(
    previous_batch: ActionBatch,
    previous_observation: Observation,
    observation: Observation,
    role: str,
    name: str,
) -> bool:
    """The last cycle already clicked this control on this page."""
    previous_url = previous_observation.url.split("#", 1)[0]
    current_url = observation.url.split("#", 1)[0]
    if previous_url != current_url:
        return False
    actions = previous_batch.actions
    if len(actions) != 1 or not isinstance(actions[0], Click):
        return False
    clicked = next((control for control in previous_observation.controls if control.ref == actions[0].ref), None)
    if clicked is None:
        return False
    return clicked.role == role and clicked.name.lower() == name.lower()


def route_decision(
    *,
    first: bool,
    retry: bool,
    previous_batch: ActionBatch | None,
    previous_observation: Observation | None,
    observation: Observation,
) -> tuple[str, list[Control]]:
    """Pick direct, fast, or planner before any model call.

    The page HTML shortcut runs before this. Here, the first cycle and the
    one retry after a failed assertion are planner. A previous batch that
    named a single ref is a direct click only when exactly one current
    control has that role and name.
    """
    if first or retry:
        return "planner", []
    targets: list[tuple[str, str]] = []
    if previous_batch is not None:
        targets = named_targets(previous_batch, previous_observation)
    if len(targets) == 1 and previous_batch is not None and previous_observation is not None:
        role, name = targets[0]
        matches = matching_controls(observation, role=role, name=name)
        if len(matches) == 1 and not _repeated_same_page(
            previous_batch, previous_observation, observation, role, name
        ):
            return "direct", matches
        if len(matches) > 1:
            return "fast", _dedupe(matches)[:8]
    elif len(targets) > 1:
        short: list[Control] = []
        for role, name in targets:
            short.extend(matching_controls(observation, role=role, name=name))
        short = _dedupe(short)
        if short:
            return "fast", short[:8]
    page = ambiguous_controls(observation)
    if page:
        return "fast", _dedupe(page)[:8]
    return "fast", observation.controls[:8]


def _search_query(task: str) -> str | None:
    if _SEARCH_TASK.search(task) is None:
        return None
    match = _FOR_QUERY.search(task)
    if match is None:
        return None
    query = re.sub(r"\s+", " ", match.group(1)).strip(" .")
    return query or None


def html_tree(observation: Observation) -> list[Control]:
    """Control list, then any further role and name the page HTML listed."""
    tree = list(observation.controls)
    seen = {control.ref for control in tree}
    for line in observation.html.splitlines():
        role, separator, rest = line.partition("\t")
        name, separator, ref = rest.partition("\t")
        if not separator or not ref or ref in seen:
            continue
        seen.add(ref)
        tree.append(Control(ref, role.strip(), name.strip(), ""))
    return tree


def _unique_named_click(task: str, tree: list[Control]) -> Control | None:
    task_text = re.sub(r"\s+", " ", task).lower()
    groups: dict[tuple[str, str], list[Control]] = {}
    for control in tree:
        if control.role not in {"link", "button"}:
            continue
        name = re.sub(r"\s+", " ", control.name).strip()
        if len(name) < 8 or name.lower() not in task_text:
            continue
        groups.setdefault((control.role, name.lower()), []).append(control)
    unique = [group[0] for group in groups.values() if len(group) == 1]
    unique.sort(key=lambda control: len(control.name), reverse=True)
    kept: list[Control] = []
    for control in unique:
        name = control.name.strip().lower()
        if any(name != earlier.name.strip().lower() and name in earlier.name.strip().lower() for earlier in kept):
            continue
        kept.append(control)
    if len(kept) != 1:
        return None
    return kept[0]


def _exact_named(tree: list[Control], *, name: str, roles: set[str]) -> list[Control]:
    needle = name.strip().lower()
    if not needle:
        return []
    groups: dict[tuple[str, str], list[Control]] = {}
    for control in tree:
        if control.role not in roles:
            continue
        if control.name.strip().lower() != needle:
            continue
        groups.setdefault((control.role, needle), []).append(control)
    if len(groups) != 1:
        return []
    return next(iter(groups.values()))


def html_shortcut(
    task: str,
    observation: Observation,
    *,
    previous_batch: ActionBatch | None = None,
    previous_observation: Observation | None = None,
) -> ActionBatch | None:
    """Click or search from the page HTML before any model call.

    A unique link or button whose name is already in the task is a click.
    A search task with one search box and one Search button is filled and
    submitted. Several controls with the same role and name stay with the model.
    """
    tree = html_tree(observation)
    query = _search_query(task)
    if query and query.lower() in observation.title.lower():
        return ActionBatch(f"{query} is already the page title.", [], None, True)

    named = _unique_named_click(task, tree)
    if query:
        exact = _exact_named(tree, name=query, roles={"link", "button"})
        if len(exact) == 1:
            named = exact[0]
        elif len(exact) > 1:
            named = None
    if named is not None and previous_batch is not None and previous_observation is not None:
        if _repeated_same_page(previous_batch, previous_observation, observation, named.role, named.name):
            named = None
    if named is not None:
        later = re.search(r"\bthen\s+open\s+(.+?)(?:\.|$)", task, re.IGNORECASE)
        later_name = re.sub(r"\s+", " ", later.group(1)).strip(" .") if later else ""
        opened_later = bool(later_name) and (
            later_name.lower() in named.name.lower() or named.name.lower() in later_name.lower()
        )
        if later_name and not opened_later:
            assertion = None
            done = False
        else:
            assertion = AssertTitle(named.name) if re.search(r"\btitle\b", task, re.IGNORECASE) else None
            done = assertion is not None or opened_later
        return ActionBatch(
            f"The page HTML has one {named.role} named {named.name}.",
            [Click(named.ref)],
            assertion,
            done,
        )

    if not query:
        return None
    boxes = [
        control
        for control in tree
        if control.role == "textbox" and "search" in control.name.lower()
    ]
    buttons = _exact_named(tree, name="Search", roles={"button"})
    if len(boxes) != 1 or len(buttons) != 1:
        return None
    box = boxes[0]
    button = buttons[0]
    return ActionBatch(
        f"The page HTML has one textbox named {box.name}. Search for {query}.",
        [Fill(box.ref, query), Click(button.ref)],
        AssertTitle(query),
        True,
    )


def decide(
    task: str,
    obs: Observation,
    prev_batch: ActionBatch | None = None,
    prev_obs: Observation | None = None,
    retry: bool = False,
    *,
    first: bool | None = None,
) -> ActionBatch | TierDecision | None:
    """Pick the next step without calling a model.

    An ActionBatch is a direct click or the page-HTML shortcut. A TierDecision
    is fast or planner, with the short control list the fast tier may see.
    None means the direct tier had nothing to click.

    first is the opening cycle. When it is omitted, that is no previous batch
    and no previous observation. Pass it from the run history when a previous
    batch exists on the first cycle.
    """
    if first is None:
        first = prev_batch is None and prev_obs is None
    if not retry:
        shortcut = html_shortcut(
            task,
            obs,
            previous_batch=prev_batch,
            previous_observation=prev_obs,
        )
        if shortcut is not None:
            return shortcut
    tier, short = route_decision(
        first=first,
        retry=retry,
        previous_batch=prev_batch,
        previous_observation=prev_obs,
        observation=obs,
    )
    if tier == "direct":
        if not short:
            return None
        control = short[0]
        return ActionBatch(
            reason=f"Click the only {control.role} named {control.name}.",
            actions=[Click(control.ref)],
            assertion=None,
            done=False,
        )
    return TierDecision(tier, tuple(short))
