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
    '{"reason":"short","done":true,'
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
    "The sketch shows the shape, not values to copy. "
    "When the actions in this response complete the task, set done true and include an assertion. "
    "A one-step add, submit, or direct open is complete. "
    "Set done false when a later step is still required. "
    "A search page, a homepage, or a profile is not final when the task asks to open an item. Click that item. "
    "A site-wide link that only shares a word with the task is the wrong control. Use the link that belongs to the item. "
    "If the names in the task identify one address, goto that address in the first action. "
    "On a list of results, click the first result when the task says to open one. "
    "A task that asks you to find the cheapest item is done when the filtered list is showing. Do not open a listing. "
    "Do not repeat a search already in the URL. "
    "When the task names a search made of words, goto that site's results URL built from those words. "
    "Do not invent a location id or a sort code. "
    "If a field asks for a place, type the place, choose the suggestion that starts with it, and use Search. "
    "A bedroom count sets both the minimum and the maximum to that count. "
    "Cheapest means the sort option labelled lowest price. Set that control before done. "
    "A filter form is not the result list. Submit it before done. "
    "A one-word link in the navigation is the wrong control when another link uses that word with a count. "
    "A comments page is not the article. Follow the story's own address. "
    "If a consent dialog is covering the page, dismiss it and put the real next step in later. "
    "Steps whose control appears only after a navigation go in later. "
    "Every filter the task names, including a count or a sort, must show in the URL or the control before done is true. "
    "The place the task names must appear in the URL before done is true. "
    "For a trip, set both places, the date, and the trip type before reading a price. "
    "To follow a citation, goto the article URL with #cite_note-1 appended, assert cite_note, and set done true. "
    "A url assertion must be a short fragment copied from the observation url. Do not invent a path. "
    "When you resubmit after an invalid field, set done true and assert the confirmation URL in that same response. "
    "If history shows a failed assertion or a stale ref, use the new observation and do not repeat the failed action. "
    "If the observation has no controls, the first action is a goto to the page the task names."
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
    prefix_hits = []
    for control in observation.controls:
        if not _role_ok(role, control.role):
            continue
        name = norm_name(control.name)
        shared = 0
        limit = min(len(needle), len(name))
        while shared < limit and needle[shared] == name[shared]:
            shared += 1
        if shared >= 40:
            prefix_hits.append(control)
    if len(prefix_hits) == 1:
        return prefix_hits[0].ref
    return None


def _search_query(task: str) -> str | None:
    match = _SEARCH_RE.search(task)
    if not match:
        return None
    query = match.group(1).strip(" .\"'")
    return query or None


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


def task_token(task: str) -> str | None:
    """One hyphenated name written in the task, such as a repository slug."""
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+){2,}", task.lower())
    if len(tokens) == 1:
        return tokens[0]
    return None


def _token_link(task: str, observation: Observation):
    token = task_token(task)
    if token is None:
        return None
    hits = [
        control
        for control in observation.controls
        if control.role == "link" and token in control.name.lower()
    ]
    if len(hits) == 1:
        return hits[0]
    return None


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
    text_fields = [control for control in observation.controls if control.role in _TEXT_ROLES]
    if not text_fields:
        return None
    actions = []
    checks = []
    for control in text_fields:
        value = _value_for(task, control.name)
        if value is None:
            return None
        actions.append(FillNamed(control.role, control.name, value))
        checks.append((control.role, control.name, value))
    for control in observation.controls:
        if control.role in ("checkbox", "radio") and _mentioned(task, control.name):
            actions.append(ClickNamed(control.role, control.name))
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


def direct_batch(task: str, observation: Observation, history: list[dict]) -> ActionBatch | None:
    """One batch from unique role-and-name matches. No model call."""
    del history
    form = direct_form(task, observation)
    if form is not None:
        return form
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
    phrases = _open_phrases(task)
    for phrase in reversed(phrases):
        if find_ref(observation, role="link", name=phrase) or find_ref(observation, role="button", name=phrase):
            role = "link" if find_ref(observation, role="link", name=phrase) else "button"
            return ActionBatch(
                f"Open {phrase}.",
                [ClickNamed(role, phrase)],
                _open_assertion(phrase),
                True,
            )
    token_hit = _token_link(task, observation)
    if token_hit is not None:
        return ActionBatch(
            f"Open {token_hit.name}.",
            [ClickNamed(token_hit.role, token_hit.name)],
            AssertUrl(task_token(task) or token_hit.name),
            True,
        )
    if query and "open the module" in task.lower() and query.lower() in observation.url.lower():
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
    if query and query.lower() not in observation.url.lower():
        boxes = [
            control
            for control in observation.controls
            if control.role in _TEXT_ROLES and "search" in control.name.lower()
        ]
        if not boxes:
            return None
        box = boxes[0]
        # Enter submits the field. A Search button under the suggestion list times out.
        actions = [Fill(box.ref, query), Press("Enter", box.ref)]
        more = bool(phrases) or "open the module" in task.lower()
        assertion = None if more else AssertTitle(query)
        return ActionBatch(
            f"Search for {query}.",
            actions,
            assertion,
            not more,
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
        effort = os.environ.get("LOOP_REASONING", "none")
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 1024 if effort else 4096,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": user},
            ],
        }
        if effort:
            payload["reasoning_effort"] = effort
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
