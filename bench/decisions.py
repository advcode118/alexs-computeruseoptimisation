"""OpenAI Decisions API as a second opinion on script_first's soft FAILs.

`POST /v1/decisions` answers independent questions about one input with
probabilities. Only gpt-6-luna is supported. script_first asks it at the
point where it is about to spend a repair turn: if the page already finishes
the task, the repair is skipped.

The input is only what the run itself can see. The payload builder takes
named fields and has no parameter for task markers, an expected answer, or
check_url_contains. The post-run grade never reads anything from here.

Any error, refusal, or timeout is "no opinion" and the caller does exactly
what it does without this module. Tests pass a transport and open no socket.

Request and response shape: https://developers.openai.com/api/docs/guides/decisions
and https://developers.openai.com/api/reference/resources/decisions/methods/create
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

OPENAI_DECISIONS_URL = "https://api.openai.com/v1/decisions"
DECISIONS_MODEL = "gpt-6-luna"

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_ON = "on"
DECISIONS_MODES = (MODE_OFF, MODE_SHADOW, MODE_ON)

DEFAULT_TIMEOUT_S = 1.5
# A wrong accept is a wrong answer. A wrong reject costs one repair turn.
DEFAULT_ACCEPT_THRESHOLD = 0.90
# About 1,500 tokens. Long enough for the lead of an article, a docs page
# heading block or a package page's summary, which is where the held-out
# answers sit. Short enough to keep a call near $0.0002 and the input small
# for latency. The runtime check already searched the full text.
PAGE_TEXT_CAP = 6000
FIELD_CAP = 500

Q_TASK_DONE = "task_done"
Q_ANSWER_OK = "answer_ok"
Q_FAILURE_CLASS = "failure_class"

_FAILURE_CLASSES = (
    ("done", "The browser is on the page the task asked for and the task is finished."),
    ("wrong_page", "The browser is on a different page from the one the task asked for."),
    ("step_missing", "The browser is on the right site or page but a step of the task is not done yet."),
    ("blocked", "A login wall, error page, captcha or consent screen stops the task."),
)

_CONTEXT = (
    "A browser automation script ran one task in a real browser. "
    "The JSON below is what the run itself saw when it ended: the task, the start URL, "
    "the live URL, the page title and first heading, what the script returned, "
    "the reason a simple string check rejected it, and the start of the page text. "
    "The string check only tests whether returned text appears verbatim in the page text, "
    "so it can reject a correct end state."
)

_TASK_DONE = (
    "The browser has finished the task: it is on the page the task asked for and, "
    "if the task asks for information, that page contains it."
)
_ANSWER_OK = "The returned answer correctly answers the task."
_FAILURE_CLASS = "Which best describes where the run ended?"


def _cap(value, limit: int = FIELD_CAP) -> str:
    text = value if isinstance(value, str) else ""
    return " ".join(text.split())[:limit]


def decisions_payload(
    *,
    task_description: str,
    start_url: str,
    live_url: str,
    title: str,
    h1: str,
    answer: str,
    key_text: str,
    runtime_reason: str,
    page_text: str,
    ask_task_done: bool = True,
    ask_class: bool = True,
    page_text_cap: int = PAGE_TEXT_CAP,
) -> dict:
    """The request body. Only run-visible fields. No answer key can be passed in."""
    evidence = {
        "task": _cap(task_description, 2000),
        "start_url": _cap(start_url),
        "live_url": _cap(live_url),
        "page_title": _cap(title),
        "page_h1": _cap(h1),
        "script_answer": _cap(answer),
        "script_key_text": _cap(key_text),
        "runtime_check": _cap(runtime_reason),
        "page_text_start": (page_text or "")[: max(0, int(page_text_cap))],
    }
    questions: list[dict] = []
    if ask_task_done:
        questions.append({"type": "predicate", "name": Q_TASK_DONE, "instructions": _TASK_DONE})
    if evidence["script_answer"]:
        questions.append({"type": "predicate", "name": Q_ANSWER_OK, "instructions": _ANSWER_OK})
    if ask_class:
        questions.append(
            {
                "type": "choice",
                "name": Q_FAILURE_CLASS,
                "instructions": _FAILURE_CLASS,
                "choices": [{"value": value, "description": text} for value, text in _FAILURE_CLASSES],
            }
        )
    return {
        "model": DECISIONS_MODEL,
        "input": [
            {
                "role": "user",
                "type": "message",
                "content": [
                    {"type": "input_text", "text": _CONTEXT},
                    {"type": "input_json", "data": evidence},
                ],
            }
        ],
        "questions": questions,
    }


def payload_from_run(
    *,
    task_description: str,
    start_url: str,
    run_payload: dict | None,
    page_url: str,
    runtime_reason: str,
    ask_task_done: bool = True,
    ask_class: bool = True,
) -> dict:
    """Pick the run-visible fields out of a run_script payload. selector_text is never read."""
    from bench.script_first import claimed_from_payload

    data = run_payload if isinstance(run_payload, dict) else {}
    claimed = claimed_from_payload(data)

    def text(key: str) -> str:
        item = data.get(key)
        return item if isinstance(item, str) else ""

    return decisions_payload(
        task_description=task_description,
        start_url=start_url,
        live_url=page_url or text("url"),
        title=text("title"),
        h1=text("h1"),
        answer=claimed.answer,
        key_text=claimed.key_text,
        runtime_reason=runtime_reason,
        page_text=text("text"),
        ask_task_done=ask_task_done,
        ask_class=ask_class,
    )


@dataclass
class DecisionsOpinion:
    """One call. ok False means no opinion: the caller acts as if it never asked."""

    ok: bool
    elapsed_ms: float = 0.0
    probabilities: dict = field(default_factory=dict)
    choice: str = ""
    usage: dict | None = None
    usd: float = 0.0
    error: str = ""
    unpriced: str = ""

    def p(self, name: str) -> float | None:
        value = self.probabilities.get(name)
        return float(value) if isinstance(value, (int, float)) else None


def _post_decisions(url: str, headers: dict, payload: dict, timeout_s: float) -> str:
    import urllib.request

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.read().decode()


def parse_answers(body: dict) -> tuple[dict, str]:
    """Predicate probabilities by name, and the failure-class choice. Refusals are skipped."""
    if not isinstance(body, dict):
        raise ValueError("Decisions response is not an object.")
    if body.get("error"):
        raise ValueError("Decisions response carried an error.")
    answers = body.get("answers")
    if not isinstance(answers, list):
        raise ValueError("Decisions response has no answers list.")
    probabilities: dict = {}
    choice = ""
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        name = answer.get("name")
        kind = answer.get("type")
        if kind == "predicate" and isinstance(name, str):
            value = answer.get("probability")
            if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
                probabilities[name] = float(value)
        elif kind == "choice" and name == Q_FAILURE_CLASS:
            picked = answer.get("choice")
            choice = picked if isinstance(picked, str) else ""
    return probabilities, choice


class DecisionsClient:
    """gpt-6-luna only. Hard timeout. Never raises to the caller."""

    def __init__(self, api_key: str, *, timeout_s: float = DEFAULT_TIMEOUT_S, transport=None):
        self.api_key = api_key
        self.timeout_s = float(timeout_s)
        self.transport = transport or _post_decisions
        self.base_url = OPENAI_DECISIONS_URL

    async def ask(self, payload: dict) -> DecisionsOpinion:
        from bench.openai_client import normalize_usage
        from bench.openai_spend import PriceUnknown, price_decisions_usd

        if payload.get("model") != DECISIONS_MODEL:
            return DecisionsOpinion(ok=False, error=f"refusing model {payload.get('model')!r}")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        start = time.perf_counter()

        def send() -> str:
            return self.transport(self.base_url, headers, payload, self.timeout_s)

        try:
            loop = asyncio.get_running_loop()
            raw = await asyncio.wait_for(loop.run_in_executor(None, send), timeout=self.timeout_s)
        except asyncio.TimeoutError:
            return DecisionsOpinion(
                ok=False, elapsed_ms=(time.perf_counter() - start) * 1000, error="timeout"
            )
        except Exception as exc:  # noqa: BLE001 - any failure is "no opinion"
            return DecisionsOpinion(
                ok=False,
                elapsed_ms=(time.perf_counter() - start) * 1000,
                error=f"{type(exc).__name__}: {exc}"[:200],
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        try:
            body = json.loads(raw)
        except (TypeError, ValueError) as exc:
            return DecisionsOpinion(ok=False, elapsed_ms=elapsed_ms, error=f"bad JSON: {exc}"[:200])
        # Price first. A billed call whose usage cannot be priced is kept for
        # the ledger and gives no opinion.
        try:
            usage = normalize_usage(body.get("usage") if isinstance(body, dict) else None)
            usd = price_decisions_usd(
                usage["input_tokens"],
                usage["output_tokens"],
                usage["cached_tokens"],
                usage["cache_write_30m_tokens"],
                usage["cache_write_12h_tokens"],
            )
        except PriceUnknown as exc:
            return DecisionsOpinion(ok=False, elapsed_ms=elapsed_ms, error="unpriced", unpriced=str(exc))
        try:
            probabilities, choice = parse_answers(body)
        except ValueError as exc:
            return DecisionsOpinion(ok=False, elapsed_ms=elapsed_ms, usage=usage, usd=usd, error=str(exc))
        return DecisionsOpinion(
            ok=True,
            elapsed_ms=elapsed_ms,
            probabilities=probabilities,
            choice=choice,
            usage=usage,
            usd=usd,
        )


def empty_record(mode: str) -> dict:
    """Row fields. Off runs carry only the mode, so they read as off in every report."""
    record: dict = {"decisions_check": mode}
    if mode == MODE_OFF:
        return record
    record.update(
        {
            "decisions_calls": 0,
            "decisions_ms": 0.0,
            "decisions_errors": 0,
            "decisions_error": "",
            "decisions_p_task_done": None,
            "decisions_p_answer_ok": None,
            "decisions_class": "",
            "decisions_overturned": False,
            "decisions_fail_code": "",
            "decisions_usd": 0.0,
            "decisions_input_tokens": 0,
            "decisions_output_tokens": 0,
            "decisions_cached_tokens": 0,
            "decisions_cache_write_30m_tokens": 0,
            "decisions_cache_write_12h_tokens": 0,
            "decisions_unpriced": "",
            "decisions_post_clock": False,
        }
    )
    return record


def note_opinion(record: dict, opinion: DecisionsOpinion, *, post_clock: bool) -> None:
    """Add one call to the row. A later call's probabilities replace an earlier one's."""
    record["decisions_calls"] += 1
    record["decisions_ms"] = round(record["decisions_ms"] + opinion.elapsed_ms, 3)
    if post_clock:
        record["decisions_post_clock"] = True
    if opinion.unpriced:
        record["decisions_unpriced"] = opinion.unpriced
    if not opinion.ok:
        record["decisions_errors"] += 1
        record["decisions_error"] = opinion.error
    if opinion.usage:
        record["decisions_usd"] = round(record["decisions_usd"] + opinion.usd, 6)
        record["decisions_input_tokens"] += opinion.usage["input_tokens"]
        record["decisions_output_tokens"] += opinion.usage["output_tokens"]
        record["decisions_cached_tokens"] += opinion.usage["cached_tokens"]
        record["decisions_cache_write_30m_tokens"] += opinion.usage["cache_write_30m_tokens"]
        record["decisions_cache_write_12h_tokens"] += opinion.usage["cache_write_12h_tokens"]
    if opinion.ok:
        for name, key in ((Q_TASK_DONE, "decisions_p_task_done"), (Q_ANSWER_OK, "decisions_p_answer_ok")):
            value = opinion.p(name)
            if value is not None:
                record[key] = value
        if opinion.choice:
            record["decisions_class"] = opinion.choice


def should_accept(opinion: DecisionsOpinion, threshold: float) -> bool:
    """Overturn only on a real opinion at or above the accept threshold."""
    if not opinion.ok:
        return False
    value = opinion.p(Q_TASK_DONE)
    return value is not None and value >= threshold


def parse_mode(value: str) -> str:
    chosen = (value or MODE_OFF).strip().lower()
    if chosen not in DECISIONS_MODES:
        raise ValueError(f"--decisions-check must be one of {list(DECISIONS_MODES)}, not {value!r}.")
    return chosen
