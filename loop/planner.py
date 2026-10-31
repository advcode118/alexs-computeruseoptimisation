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
from datetime import date
from urllib.parse import urlparse

from loop.actions import (
    ActionBatch,
    ActionError,
    AssertAll,
    AssertText,
    AssertTitle,
    AssertUrl,
    AssertValues,
    Click,
    ClickNamed,
    Fill,
    FillNamed,
    Goto,
    Observation,
    PlannerError,
    Press,
    parse_batch,
)

DEMO_TASK = "Add milk to the packing list"
_ITEM_RE = re.compile(r"add\s+(.+?)\s+to\s+the\s+packing\s+list", re.IGNORECASE)

_SYSTEM = (
    "You are a browser planner. You receive one observation and return one JSON object, no markdown. "
    "Map every field in this response. Do not leave fields for a later call. Schema: "
    '{"reason":"short","done":false,'
    '"fills":[{"role":"textbox","name":"Customer name","text":"Ada"}],'
    '"submit":{"role":"button","name":"Submit order"},'
    '"actions":[{"type":"click","role":"link","name":"heapq"}],'
    '"later":[{"type":"click","role":"link","name":"Priority Queue Implementation Notes"}],'
    '"assertion":{"type":"title","text":"expected"}}. '
    "fills, submit, actions, later, and assertion may be omitted. "
    "Use the accessible name from the observation. Prefer role and name over refs. "
    "A ref is only valid on this page. Steps whose control is not in the observation go in later, by role and name. "
    "For a form, fills lists every textbox, and every checkbox or radio the task selects, plus submit. "
    "The task is ordinary language. Map it onto the accessible names in the observation. "
    "One response sets every field the task asks for. Leave unrelated controls alone. "
    "A response that sets only one of those fields is wrong. "
    "A combobox lists options. Set it with "
    '{"type":"choose","role":"combobox","name":"Dropdown","option":"Two"}. '
    "The option is the visible label. Do not fill a combobox. "
    "If a control has invalid, the last value was rejected. Pick a different value that satisfies that message. "
    "Time fields use HH:MM. "
    "A search field is a textbox even when a suggestion list is open. "
    "Fill it and press Enter in the same response. Do not click Search, and do not choose the search field. "
    "Press Enter in a search box. Do not click a Search button under a suggestion list. "
    "If an option names a place or choice the task asks for, click that option. "
    "Checkbox and radio text can be empty. Do not submit when the task says not to. "
    "assertion type is url, title, text, all, or value. "
    "value checks are {\"type\":\"value\",\"checks\":[{\"role\":\"textbox\",\"name\":\"Password\",\"text\":\"secret\"}]}. "
    "all checks are {\"type\":\"all\",\"texts\":[\"one\",\"two\"]}. "
    "Set done to true only when the task's final check can pass after this batch. "
    "A url assertion must be a short fragment copied from the observation url. Do not invent a path. "
    "When you resubmit after an invalid field, set done true and assert the confirmation URL in that same response. "
    "If history shows a failed assertion or a stale ref, use the new observation and do not repeat the failed action. "
    "If the page has no controls, return a goto in this response. "
    "An empty action list is valid only when done is true. "
    "Set done to true in the same response as the action that finishes the task."
)


def parse_item(task: str) -> str:
    match = _ITEM_RE.search(task.strip())
    if not match:
        return "milk"
    return match.group(1).strip().strip(".")


_DASHES = str.maketrans({"—": "-", "–": "-", "−": "-"})
_TEXT_ROLES = {"textbox", "searchbox"}
_SEARCH_RE = re.compile(
    r"search(?:\s+[\w-]+){0,4}\s+for\s+(.+?)(?=,|\.|\s+and\b|\s+then\b|\s+open\b|$)",
    re.IGNORECASE,
)
_SEARCH_QUOTED_RE = re.compile(
    r"""search(?:\s+[\w-]+){0,6}\s+["']([^"']+)["']""",
    re.IGNORECASE,
)
_DEST_RE = re.compile(
    r"(https?://[^\s\"'<>]+|(?:[a-z0-9-]+\.)+(?:co\.uk|com|org|net|edu|gov|io|uk)(?:/[^\s\"',)]*)?)",
    re.IGNORECASE,
)
_OPEN_RE = re.compile(
    r"open\s+(?:the\s+)?(?:section\s+|link\s+|page\s+|article\s+)?(.+?)(?=\s+and\b|\s+then\b|[.,]|$)",
    re.IGNORECASE,
)
_LABEL_VALUE_RE = re.compile(r"^([^:]{2,80}):\s*(.+)$")
_OPEN_STOP = {
    "a",
    "an",
    "about",
    "article",
    "her",
    "his",
    "it",
    "its",
    "link",
    "page",
    "section",
    "that",
    "the",
    "their",
    "them",
    "this",
}


def norm_name(text: str) -> str:
    text = text.translate(_DASHES).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(":").strip()


def _role_ok(wanted: str, actual: str) -> bool:
    if wanted == actual:
        return True
    if wanted in _TEXT_ROLES and actual in _TEXT_ROLES:
        return True
    return wanted in ("combobox", "select") and actual in ("combobox", "select")


def find_ref(observation: Observation, *, role: str, name: str) -> str | None:
    needle = norm_name(name)
    if not needle:
        return None
    exact = [
        control
        for control in observation.controls
        if _role_ok(role, control.role) and norm_name(control.name) == needle
    ]
    pool = exact
    if not pool:
        pool = [
            control
            for control in observation.controls
            if _role_ok(role, control.role)
            and min(len(needle), len(norm_name(control.name))) >= 4
            and (needle in norm_name(control.name) or norm_name(control.name) in needle)
        ]
    if not pool:
        named = [control for control in observation.controls if norm_name(control.name) == needle]
        if len(named) == 1:
            return named[0].ref
        return None
    if len(pool) == 1 or len({norm_name(control.name) for control in pool}) == 1:
        return pool[0].ref
    return None


def _search_query(task: str) -> str | None:
    quoted = _SEARCH_QUOTED_RE.search(task)
    if quoted:
        query = quoted.group(1).strip()
        if query:
            return query
    match = _SEARCH_RE.search(task)
    if not match:
        return None
    query = match.group(1).strip(" .\"'")
    return query or None


def _task_destination(task: str) -> str | None:
    for match in _DEST_RE.finditer(task):
        if match.start() > 0 and task[match.start() - 1] == "@":
            continue
        raw = match.group(0).rstrip(".,)")
        if raw.lower().startswith("http"):
            return raw
        return "https://" + raw
    return None


def _host(url: str) -> str:
    parsed = url if "://" in url else "https://" + url
    host = (urlparse(parsed).hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host


def _same_site(current: str, dest: str) -> bool:
    cur = _host(current)
    target = _host(dest)
    if not cur or not target:
        return False
    if cur != target and not cur.endswith("." + target) and not target.endswith("." + cur):
        return False
    path = (urlparse(dest if "://" in dest else "https://" + dest).path or "").rstrip("/")
    if not path:
        return True
    return path.lower() in (urlparse(current).path or "").lower()


def _query_in_url(query: str, url: str) -> bool:
    folded = url.lower().replace("_", " ").replace("-", " ")
    return query.lower() in folded


def _result_link(observation: Observation, query: str):
    needle = norm_name(query)
    if len(needle) < 3:
        return None
    matches = []
    for control in observation.controls:
        if control.role not in ("link", "option"):
            continue
        name = norm_name(control.name)
        if name == needle or name.startswith(needle + " ") or name.startswith(needle + " -"):
            matches.append(control)
    if not matches:
        return None
    matches.sort(key=lambda control: len(norm_name(control.name)))
    return matches[0]


_INVENTED_RE = re.compile(
    r"\b(made[- ]up|fake|dummy|fictional|imaginary|placeholder)\b",
    re.IGNORECASE,
)


def _synthetic(name: str) -> str:
    """A stand-in value for a field the task asked us to invent."""
    label = norm_name(name)
    if "mail" in label:
        return "ada@example.com"
    if "time" in label:
        return "12:00"
    if any(token in label for token in ("phone", "tel", "mobile")):
        return "555-0100"
    if "name" in label:
        return "Ada Lovelace"
    if "address" in label or "street" in label:
        return "1 Example Street"
    if "city" in label:
        return "London"
    return "sample"


def _value_for(task: str, name: str) -> str | None:
    label = norm_name(name)
    for line in task.splitlines():
        match = _LABEL_VALUE_RE.match(line.strip())
        if match and norm_name(match.group(1)) == label:
            return match.group(2).strip()
    return None


def _mentioned(task: str, name: str) -> bool:
    label = norm_name(name)
    if len(label) < 3:
        return False
    return label in norm_name(task)


def _phrase_hit(observation: Observation, phrase: str):
    """A link whose name contains every content word in the phrase."""
    words = [
        word
        for word in re.findall(r"[a-z0-9]+", phrase.lower())
        if word not in _OPEN_STOP and word != "section"
    ]
    if not words:
        return None
    found = []
    for control in observation.controls:
        if control.role not in ("link", "button"):
            continue
        name_words = re.findall(r"[a-z0-9]+", control.name.lower())
        if all(word in name_words for word in words):
            found.append(control)
    if not found:
        return None
    found.sort(key=lambda control: (len(norm_name(control.name)), norm_name(control.name)))
    best = found[0]
    if (
        len(found) > 1
        and len(norm_name(found[1].name)) == len(norm_name(best.name))
        and norm_name(found[1].name) != norm_name(best.name)
    ):
        return None
    return best


def _open_phrases(task: str) -> list[str]:
    phrases = []
    for match in _OPEN_RE.finditer(task):
        phrase = match.group(1).strip()
        words = re.findall(r"[a-z0-9]+", phrase.lower())
        if not words or all(word in _OPEN_STOP for word in words):
            continue
        if phrase.lower() in ("the module", "module", "a result", "the result"):
            continue
        phrases.append(phrase)
    return phrases


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm_name(text)).strip("-")


def _open_assertion(phrase: str):
    parts = re.split(r"\s+[—–−-]\s+", phrase, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        return AssertTitle(parts[1].strip())
    if len(phrase.split()) >= 4:
        return AssertUrl(_slug(phrase))
    return AssertTitle(phrase)


def _module_name(observation: Observation, query: str) -> str | None:
    prefix = norm_name(query)
    candidates = []
    for control in observation.controls:
        if control.role != "link":
            continue
        name = norm_name(control.name)
        if name == prefix or name.startswith(prefix + " ") or name.startswith(prefix + " -"):
            if name[len(prefix):len(prefix) + 1] == ".":
                continue
            candidates.append(control)
    if not candidates:
        return None
    candidates.sort(key=lambda control: len(control.name), reverse=True)
    return candidates[0].name


def _task_button(task: str, observation: Observation):
    """The longest control whose accessible name is written in the task."""
    folded = norm_name(task)
    matches = []
    for control in observation.controls:
        if control.role not in ("button", "link"):
            continue
        label = norm_name(control.name)
        if len(label) < 10 or label not in folded:
            continue
        matches.append(control)
    if not matches:
        return None
    matches.sort(key=lambda control: len(norm_name(control.name)), reverse=True)
    if len(matches) > 1 and len(norm_name(matches[0].name)) == len(norm_name(matches[1].name)):
        return None
    return matches[0]


def direct_form(task: str, observation: Observation) -> ActionBatch | None:
    if not re.search(r"\b(fill|submit)\b", task, re.IGNORECASE):
        return None
    if _search_query(task):
        return None
    do_not_submit = re.search(r"do not submit", task, re.IGNORECASE) is not None
    invent = _INVENTED_RE.search(task) is not None
    text_fields = [control for control in observation.controls if control.role in _TEXT_ROLES]
    if not text_fields:
        return None
    actions = []
    checks = []
    for control in text_fields:
        value = _value_for(task, control.name)
        if value is None and invent:
            value = _synthetic(control.name)
        if value is None:
            return None
        actions.append(FillNamed(control.role, control.name, value))
        checks.append((control.role, control.name, value))
    picked_radio = False
    for control in observation.controls:
        if control.role in ("checkbox", "radio") and _mentioned(task, control.name):
            actions.append(ClickNamed(control.role, control.name))
            if control.role == "radio":
                picked_radio = True
    if invent and not picked_radio:
        first_radio = next((control for control in observation.controls if control.role == "radio"), None)
        if first_radio is not None:
            actions.append(ClickNamed(first_radio.role, first_radio.name))
    texts = tuple(text for _, _, text in checks)
    if do_not_submit:
        return ActionBatch(
            "Fill every named field.",
            actions,
            AssertValues(tuple(checks)),
            True,
        )
    if re.search(r"\bsubmit\b", task, re.IGNORECASE) is None:
        return None
    submit = next(
        (
            control
            for control in observation.controls
            if control.role == "button" and "submit" in norm_name(control.name)
        ),
        None,
    )
    if submit is None:
        return None
    actions.append(ClickNamed(submit.role, submit.name))
    return ActionBatch(
        "Fill every named field and submit.",
        actions,
        AssertAll(texts),
        True,
    )


def _search_batch(task: str, observation: Observation, query: str) -> ActionBatch | None:
    """Search, or open a result that is already on the page. None leaves the step to the model."""
    more = bool(_open_phrases(task)) or "open the module" in task.lower()
    result = _result_link(observation, query)
    if result is not None:
        role = "link" if result.role == "link" else result.role
        return ActionBatch(
            f"Open {query}.",
            [ClickNamed(role, result.name)],
            None if more else AssertTitle(query),
            not more,
        )
    boxes = [
        control
        for control in observation.controls
        if control.role in _TEXT_ROLES and "search" in control.name.lower()
    ]
    if not boxes:
        return None
    box = boxes[0]
    if norm_name(box.value) == norm_name(query):
        return None
    # Enter submits the field. A Search button under the suggestion list times out.
    return ActionBatch(
        f"Search for {query}.",
        [Fill(box.ref, query), Press("Enter", box.ref)],
        None if more else AssertTitle(query),
        not more,
    )


def direct_batch(task: str, observation: Observation, history: list[dict]) -> ActionBatch | None:
    """One batch from unique role-and-name matches. No model call."""
    del history
    form = direct_form(task, observation)
    if form is not None:
        return form
    dest = _task_destination(task)
    if dest and not _same_site(observation.url, dest):
        return ActionBatch(f"Open {dest}.", [Goto(dest)], None, False)
    query = _search_query(task)
    if (
        query
        and query.lower() in observation.title.lower()
        and "open the module" not in task.lower()
        and not _open_phrases(task)
    ):
        return ActionBatch(f"The title contains {query}.", [], AssertTitle(query), True)
    named = _task_button(task, observation) if query is None else None
    if named is not None and not _open_phrases(task):
        return ActionBatch(f"Use {named.name}.", [ClickNamed(named.role, named.name)], None, True)
    if query and not _query_in_url(query, observation.url):
        searching = _search_batch(task, observation, query)
        if searching is not None:
            return searching
    phrases = _open_phrases(task)
    for phrase in reversed(phrases):
        hit = _phrase_hit(observation, phrase)
        if hit is None:
            continue
        assertion = AssertUrl(_slug(hit.name)) if len(hit.name.split()) == 1 else _open_assertion(hit.name)
        return ActionBatch(
            f"Open {phrase}.",
            [ClickNamed(hit.role, hit.name)],
            assertion,
            True,
        )
    if query and "open the module" in task.lower() and _query_in_url(query, observation.url):
        module = _module_name(observation, query)
        if module and find_ref(observation, role="link", name=module):
            return ActionBatch(
                f"Open the {query} module.",
                [ClickNamed("link", module)],
                None,
                False,
            )
    if named is not None and query is None:
        return ActionBatch(
            f"Use {named.name}.",
            [ClickNamed(named.role, named.name)],
            None,
            False,
        )
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
    start = text.find("{")
    if start < 0:
        raise PlannerError("Model did not return JSON.")
    try:
        data, _end = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise PlannerError(f"Model did not return JSON: {exc}") from exc
    try:
        return parse_batch(data)
    except ActionError as exc:
        raise PlannerError(str(exc)) from exc


class ModelPlanner:
    """One chat completion per cycle. Any OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        transport=None,
        api_style: str = "openai",
        system: str | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport or _post_chat
        self.api_style = api_style
        self.system = system or _SYSTEM
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0

    def reset(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0

    def plan(self, task: str, observation: Observation, history: list[dict]) -> ActionBatch:
        self.calls += 1
        user = json.dumps(
            {
                "task": task,
                "today": date.today().isoformat(),
                "observation": observation.to_dict(),
                "history": history[-6:],
            },
            ensure_ascii=False,
        )
        if self.api_style == "anthropic":
            raw = self.transport(
                f"{self.base_url}/messages",
                {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                {
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": self.system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            return parse_model_content(self._take_content(raw))
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 8192,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": user},
            ],
        }
        raw = self.transport(
            f"{self.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload,
        )
        return parse_model_content(self._take_content(raw))

    def _take_content(self, raw: object) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
            self.input_tokens += int(usage.get("input") or 0)
            self.output_tokens += int(usage.get("output") or 0)
            self.cached_input_tokens += int(usage.get("cached_input") or 0)
            content = raw.get("content")
            if isinstance(content, str) and content.strip():
                return content
        raise PlannerError("Model response did not include a message.")

    @classmethod
    def from_env(cls, system: str | None = None, *, provider: str | None = None) -> "ModelPlanner":
        """Nebius is the live loop's primary. Claude is the fallback provider."""
        nebius = os.environ.get("NEBIUS_API_KEY") or ""
        anthropic = os.environ.get("ANTHROPIC_API_KEY") or ""
        loop_key = os.environ.get("LOOP_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        choice = provider or ""
        if choice == "anthropic":
            if not anthropic:
                raise PlannerError("ANTHROPIC_API_KEY is not present.")
            return cls(
                api_key=anthropic,
                base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
                model=os.environ.get("FALLBACK_MODEL") or "claude-sonnet-5-5",
                api_style="anthropic",
                system=system,
            )
        if nebius and choice != "openai":
            return cls(
                api_key=nebius,
                base_url=os.environ.get("LOOP_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
                model=os.environ.get("LOOP_MODEL") or os.environ.get("RUN_MODEL") or "deepseek-ai/DeepSeek-V4-Pro-0813",
                system=system,
            )
        if anthropic and not loop_key:
            return cls(
                api_key=anthropic,
                base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
                model=os.environ.get("FALLBACK_MODEL") or "claude-sonnet-5-5",
                api_style="anthropic",
                system=system,
            )
        if not loop_key:
            raise PlannerError(
                "The model planner needs NEBIUS_API_KEY, ANTHROPIC_API_KEY, LOOP_API_KEY, or OPENAI_API_KEY."
            )
        return cls(
            api_key=loop_key,
            base_url=os.environ.get("LOOP_BASE_URL", "https://api.openai.com/v1"),
            model=os.environ.get("LOOP_MODEL", "gpt-4o-mini"),
            system=system,
        )


def _usage_counts(body: dict) -> dict[str, int]:
    usage = body.get("usage")
    empty = {"input": 0, "output": 0, "cached_input": 0}
    if not isinstance(usage, dict):
        return empty
    raw_out = usage.get("completion_tokens", usage.get("output_tokens", 0))
    cached = 0
    if "cache_read_input_tokens" in usage:
        raw_in = usage.get("input_tokens", 0)
        cached = usage.get("cache_read_input_tokens") or 0
    else:
        raw_in = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        details = usage.get("prompt_tokens_details")
        if "prompt_cache_hit_tokens" in usage:
            cached = usage.get("prompt_cache_hit_tokens") or 0
        elif isinstance(details, dict):
            cached = details.get("cached_tokens") or 0
        try:
            raw_in = int(raw_in or 0) - int(cached or 0)
        except (TypeError, ValueError):
            return empty
    try:
        return {
            "input": max(0, int(raw_in or 0)),
            "output": max(0, int(raw_out or 0)),
            "cached_input": max(0, int(cached or 0)),
        }
    except (TypeError, ValueError):
        return empty


def _redact(text: str) -> str:
    cleaned = text
    for name in ("NEBIUS_API_KEY", "ANTHROPIC_API_KEY", "LOOP_API_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(name) or ""
        if len(value) >= 8:
            cleaned = cleaned.replace(value, "[redacted]")
    return cleaned


def _jsonish(text: str) -> bool:
    start = text.find("{")
    end = text.rfind("}")
    return start >= 0 and end > start


def _message_text(body: dict) -> str:
    if isinstance(body.get("content"), list):
        parts = [item.get("text", "") for item in body["content"] if isinstance(item, dict)]
        text = "".join(parts).strip()
        if text:
            return text
    message = None
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        message = None
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        for key in ("reasoning_content", "reasoning"):
            extra = message.get(key)
            if isinstance(extra, str) and extra.strip() and _jsonish(extra):
                return extra
    raise PlannerError("Model response did not include a message.")


def _post_chat(url: str, headers: dict, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = _redact(exc.read().decode(errors="replace")[:300])
        raise PlannerError(f"Model request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise PlannerError(f"Model request failed: {_redact(str(exc.reason))}") from exc
    return {"content": _message_text(body), "usage": _usage_counts(body)}


def make_planner(name: str, fixture_url: str):
    if name == "fake":
        return FakePlanner(fixture_url)
    if name == "model":
        return ModelPlanner.from_env()
    raise PlannerError(f"unknown planner: {name}")
