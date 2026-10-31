"""One planner call returns a batch of browser actions.

The fake planner needs no API key. The model planner is a router:
a direct click from the page HTML when one role and name is unique,
one fast OpenAI-compatible call for an ambiguous short list, and
Claude when the HTML has no unique target, and on one retry after a failed assertion.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request

from loop.actions import (
    ActionBatch,
    ActionError,
    AssertText,
    AssertTitle,
    Click,
    Control,
    Fill,
    Goto,
    Observation,
    PlannerError,
    parse_batch,
)

DEMO_TASK = "Add milk to the packing list"
_ITEM_RE = re.compile(r"add\s+(.+?)\s+to\s+the\s+packing\s+list", re.IGNORECASE)

# Smallest Claude that returned this action batch reliably (Haiku 4.5).
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
# Small Nebius models. An empty NEBIUS_FAST_MODEL races these and keeps the first valid batch.
FAST_CANDIDATES = (
    "deepseek-ai/DeepSeek-V4.1-Flash-1017",
    "Qwen/Qwen3-30B-A3B-Instruct-2507",
)
STEP5_ENV_PATH = "/cursor/stores/self/docs/step5.env.example"
_STEP5_KEYS = (
    "ANTHROPIC_API_KEY",
    "NEBIUS_API_KEY",
    "NEBIUS_BASE_URL",
    "NEBIUS_FAST_MODEL",
)
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

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
    "Set done to true when the task is finished, with an empty actions list. "
    "If the observation is not the task page, goto start_url first."
)

_FAST_SYSTEM = (
    "You pick one browser batch from a short list of controls. "
    "Several may share a role and name. Reply with JSON only, no markdown. Schema: "
    '{"reason":"short","done":false,"actions":['
    '{"type":"click","ref":"e2"},'
    '{"type":"fill","ref":"e1","text":"milk"}'
    '],"assertion":{"type":"text","text":"expected"}}. '
    "assertion may be null. Its type is url, title, or text. "
    "Use only refs from the controls list. Do not invent a url. Prefer click or fill."
)


def parse_item(task: str) -> str:
    match = _ITEM_RE.search(task.strip())
    if not match:
        return "milk"
    return match.group(1).strip().strip(".")


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


def find_ref(observation: Observation, *, role: str, name: str) -> str | None:
    matches = matching_controls(observation, role=role, name=name)
    if not matches:
        return None
    return matches[0].ref


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
    if previous_observation.url != observation.url:
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


_SEARCH_TASK = re.compile(r"\bsearch\b", re.IGNORECASE)
_FOR_QUERY = re.compile(r"\bfor\s+(.+?)(?:\s+and\b|[?.!]|$)", re.IGNORECASE)


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
    if len(unique) != 1:
        return None
    return unique[0]


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
        assertion = AssertTitle(named.name) if re.search(r"\btitle\b", task, re.IGNORECASE) else None
        done = assertion is not None
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
    if not isinstance(content, str):
        raise PlannerError("Model response did not include a message.")
    text = content.strip()
    if not text:
        raise PlannerError("Model response did not include a message.")
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


def _last_assertion_ok(history: list[dict]) -> bool:
    if not history:
        return False
    assertion = history[-1].get("assertion")
    return isinstance(assertion, dict) and assertion.get("ok") is True


def interpret_model_content(content: object, history: list[dict]) -> ActionBatch:
    """A missing reply after a passed assertion means the task is done.

    Some models set message content to null and leave the text in reasoning.
    Calling strip on that null crashed the cycle after the assertion passed.
    """
    if not isinstance(content, str) or not content.strip():
        if _last_assertion_ok(history):
            return ActionBatch("Done.", [], None, True)
        raise PlannerError("Model response did not include a message.")
    return parse_model_content(content)


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
        return interpret_model_content(content, history)

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


def _secret_from_headers(headers: dict) -> str:
    auth = headers.get("Authorization", "")
    if isinstance(auth, str) and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    api_key = headers.get("x-api-key", "")
    if isinstance(api_key, str):
        return api_key
    return ""


def _redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def _post_json(url: str, headers: dict, payload: dict) -> dict:
    secret = _secret_from_headers(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = _redact(exc.read().decode(errors="replace")[:300], secret)
        raise PlannerError(f"Model request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise PlannerError(f"Model request failed: {_redact(str(exc.reason), secret)}") from exc


def _post_chat(url: str, headers: dict, payload: dict) -> str | None:
    body = _post_json(url, headers, payload)
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PlannerError("Model response did not include a message.") from exc
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    return None


def _post_anthropic(url: str, headers: dict, payload: dict) -> str:
    body = _post_json(url, headers, payload)
    content = body.get("content")
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    if not parts:
        raise PlannerError("Model response did not include a message.")
    return "".join(parts)


def load_step5_env(path: str | None = None) -> dict[str, str]:
    """Read the step-5 key file when it exists, otherwise the environment."""
    file_path = STEP5_ENV_PATH if path is None else path
    if file_path and os.path.isfile(file_path):
        values = {key: "" for key in _STEP5_KEYS}
        with open(file_path, encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text or text.startswith("#") or "=" not in text:
                    continue
                key, value = text.split("=", 1)
                key = key.strip()
                if key in values:
                    values[key] = value.strip().strip('"').strip("'")
        return values
    return {key: os.environ.get(key, "") for key in _STEP5_KEYS}


def select_soonest_model(candidates: tuple[str, ...] | list[str], probe) -> str:
    """Return the candidate whose probe returns true first.

    probe(model) is true when that model returned a valid action batch.
    """
    if not candidates:
        raise PlannerError("No fast model is configured.")
    winner: dict[str, str | None] = {"model": None}
    ready = threading.Event()
    lock = threading.Lock()

    def run(model: str) -> None:
        try:
            ok = bool(probe(model))
        except Exception:
            ok = False
        if not ok:
            return
        with lock:
            if winner["model"] is None:
                winner["model"] = model
                ready.set()

    threads = [threading.Thread(target=run, args=(model,), daemon=True) for model in candidates]
    for thread in threads:
        thread.start()
    ready.wait(timeout=45)
    if winner["model"] is None:
        raise PlannerError("No fast model returned valid JSON.")
    return str(winner["model"])


class FastClient:
    """One OpenAI-compatible call over a short control list. No vision."""

    kept_model = ""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "",
        transport=None,
        candidates: tuple[str, ...] | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport or _post_chat
        self.candidates = FAST_CANDIDATES if candidates is None else candidates
        self._custom_candidates = candidates is not None

    def reset(self) -> None:
        return None

    def plan(self, task: str, controls: list[Control], history: list[dict]) -> ActionBatch:
        if not controls:
            raise PlannerError("The fast tier needs a short list of controls.")
        model = self._model()
        payload = {
            "model": model,
            "temperature": 0,
            "max_tokens": 500,
            "messages": [
                {"role": "system", "content": _FAST_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": task,
                            "controls": [control.to_dict() for control in controls],
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
        return interpret_model_content(content, history)

    def _model(self) -> str:
        if self.model:
            return self.model
        if not self._custom_candidates and FastClient.kept_model:
            self.model = FastClient.kept_model
            return self.model
        chosen = select_soonest_model(self.candidates, self._probe)
        if not self._custom_candidates:
            FastClient.kept_model = chosen
        self.model = chosen
        return chosen

    def _probe(self, model: str) -> bool:
        payload = {
            "model": model,
            "temperature": 0,
            "max_tokens": 200,
            "messages": [
                {"role": "system", "content": _FAST_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        'Return a batch that clicks Add. '
                        'controls: [{"ref":"e2","role":"button","name":"Add","value":""}]'
                    ),
                },
            ],
        }
        try:
            content = self.transport(
                f"{self.base_url}/chat/completions",
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                payload,
            )
            parse_model_content(content)
        except PlannerError:
            return False
        return True


class ClaudePlanner:
    """One Anthropic messages call. Used for the planner tier."""

    def __init__(self, *, api_key: str, model: str, fixture_url: str = "", transport=None):
        self.api_key = api_key
        self.model = model
        self.fixture_url = fixture_url
        self.transport = transport or _post_anthropic

    def reset(self) -> None:
        return None

    def plan(self, task: str, observation: Observation, history: list[dict]) -> ActionBatch:
        payload = {
            "model": self.model,
            "max_tokens": 800,
            "temperature": 0,
            "system": _SYSTEM,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": task,
                            "start_url": self.fixture_url,
                            "observation": observation.to_dict(),
                            "history": history[-6:],
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
        content = self.transport(
            _ANTHROPIC_URL,
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload,
        )
        return interpret_model_content(content, history)


class Router:
    """Direct click, fast list, or Claude. The engine calls this before plan."""

    use_router = True

    def __init__(self, claude: ClaudePlanner, fast: FastClient):
        self.claude = claude
        self.fast = fast

    def reset(self) -> None:
        self.claude.reset()
        self.fast.reset()

    @classmethod
    def from_env(cls, fixture_url: str, path: str | None = None) -> "Router":
        values = load_step5_env(path)
        anthropic = values.get("ANTHROPIC_API_KEY", "")
        nebius = values.get("NEBIUS_API_KEY", "")
        if not anthropic:
            raise PlannerError(
                "The planner tier needs ANTHROPIC_API_KEY. Use the fake planner to run with no key."
            )
        if not nebius:
            raise PlannerError(
                "The fast tier needs NEBIUS_API_KEY. Use the fake planner to run with no key."
            )
        base_url = values.get("NEBIUS_BASE_URL") or "https://api.studio.nebius.com/v1"
        return cls(
            claude=ClaudePlanner(api_key=anthropic, model=CLAUDE_MODEL, fixture_url=fixture_url),
            fast=FastClient(api_key=nebius, base_url=base_url, model=values.get("NEBIUS_FAST_MODEL", "")),
        )


def make_planner(name: str, fixture_url: str):
    if name == "fake":
        return FakePlanner(fixture_url)
    if name == "model":
        return Router.from_env(fixture_url)
    raise PlannerError(f"unknown planner: {name}")
