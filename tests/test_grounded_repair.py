"""Grounded multi-turn repair for script_first. Offline, no model, no browser."""

from __future__ import annotations

import asyncio
import json

from bench.arms import SCRIPT_FIRST_MAX_REPAIRS, SCRIPT_FIRST_MAX_SCRIPTS
from bench.harness import BenchmarkHarness
from bench.script_first import (
    SNAPSHOT_BEGIN,
    SNAPSHOT_END,
    EvidenceVerdict,
    drop_old_snapshots,
    failed_step_note,
    format_page_snapshot,
    format_run_result,
    grounded_repair_request,
    model_visible_script_result,
    normalized_script,
    repair_outcome_key,
    task_terms,
)

GOTO = "await page.goto('https://example.org/a')"
CLICK = "await page.getByRole('button', { name: 'Go' }).click()"
EVAL = "page.evaluate(() => ({url: location.href, answer: 'x'}))"


def _snapshot_data() -> dict:
    return {
        "url": "https://example.org/form",
        "title": "Order",
        "headings": ["h1 Place an order"],
        "dialogs": [{"name": "Cookies", "text": "We use cookies", "buttons": ["Accept all"]}],
        "alerts": ["Please enter a valid date."],
        "forms": [
            {
                "name": "order",
                "fields": [
                    {"role": "textbox", "name": "Contact name", "type": "text", "required": True, "value": "Al"},
                    {"role": "combobox", "name": "Payment", "type": "select", "options": ["Cash", "Card"]},
                    {"role": "textbox", "name": "Date", "type": "date", "invalid": "Please fill out this field."},
                    {"role": "textbox", "name": "", "type": "text", "locator": 'input[name="zip"]'},
                ],
                "buttons": ["Submit"],
            }
        ],
        "elements": [{"role": "link", "name": "Docs", "href": "/docs/"}],
        "more_elements": 5,
        "tables": [{"caption": "Codes", "rows": 3, "head": ["Value", "Type"], "first": ["28", "AAAA"]}],
        "text": "Place an order " * 400,
    }


def test_snapshot_shows_names_fields_dialogs_and_stays_small():
    text = format_page_snapshot(_snapshot_data(), cap=2000)
    assert len(text) <= 2000
    assert 'OPEN DIALOG "Cookies"' in text and '"Accept all"' in text
    assert 'textbox "Contact name" type=text value="Al" required' in text
    assert 'options=["Cash", "Card"]' in text
    assert "INVALID: Please fill out this field." in text
    assert """textbox (no name) page.locator("input[name=\\"zip\\"]")""" in text
    assert 'link "Docs" -> /docs/' in text and "...and 5 more" in text
    assert 'messages: "Please enter a valid date."' in text
    assert "table \"Codes\" (3 rows)" in text
    assert "text: Place an order" in text


def test_snapshot_of_nothing_is_empty():
    assert format_page_snapshot(None) == ""
    assert format_page_snapshot({}) == ""


def test_failed_step_note_names_the_step_and_the_error():
    code = "\n".join([GOTO, CLICK, EVAL])
    payload = {"ok": False, "steps": 1, "error": "Locator.click: Timeout 5000ms exceeded.\nCall log:\n  - waiting"}
    note = failed_step_note(code, payload)
    assert "ran 1 of 3 steps" in note
    assert "Step 2 failed" in note and "getByRole('button', { name: 'Go' })" in note
    assert "Timeout 5000ms exceeded." in note
    assert failed_step_note(code, {"ok": True, "steps": 3}) == "Your script ran all 3 steps without an error."
    assert "did not parse" in failed_step_note("this is not a script(", {"ok": False, "steps": 0})


def test_grounded_request_carries_reason_step_claim_and_snapshot():
    code = "\n".join([GOTO, EVAL])
    payload = {"ok": True, "steps": 2, "claimed": {"answer": "42"}}
    text = grounded_repair_request(
        "answer is not in the page text",
        code=code,
        payload=payload,
        snapshot="url: https://example.org/a",
        repair_number=2,
        max_repairs=3,
    )
    assert text.startswith("END_STATE_FAILED (repair 2 of 3): answer is not in the page text.")
    assert 'answer="42"' in text
    assert SNAPSHOT_BEGIN in text and SNAPSHOT_END in text
    assert "starts from this page" in text


def test_drop_old_snapshots_keeps_everything_else():
    body = "head\n" + SNAPSHOT_BEGIN + "\nurl: big page\n" + SNAPSHOT_END + "\ntail"
    messages = [
        {"role": "user", "content": "task"},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": body}]},
    ]
    drop_old_snapshots(messages)
    content = messages[1]["content"][0]["content"]
    assert "big page" not in content
    assert content.startswith("head\n" + SNAPSHOT_BEGIN) and content.endswith(SNAPSHOT_END + "\ntail")
    assert messages[0]["content"] == "task"


def test_hide_page_drops_page_text_links_and_controls():
    raw = format_run_result(
        ok=True,
        url="https://example.org/a",
        step_count=1,
        text="secret body",
        links=[("Docs", "https://example.org/docs")],
        controls=["button\tGo"],
    )
    shown = json.loads(model_visible_script_result(raw, failed=False, hide_page=True).splitlines()[0])
    assert "text" not in shown and "links" not in shown and "controls" not in shown


def test_outcome_key_and_normalized_script():
    verdict = EvidenceVerdict("FAIL", "answer is not in the page text", "")
    one = repair_outcome_key(verdict, {"url": "https://a/", "ok": True, "claimed": {"answer": "1"}})
    two = repair_outcome_key(verdict, {"url": "https://a/", "ok": True, "claimed": {"answer": "2"}})
    assert one != two
    assert normalized_script("a;\n  b") == normalized_script("a; b")


# --- harness loop -----------------------------------------------------------


class _Model:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen: list = []

    async def create_message(self, messages, tools, system=None, max_tokens=4096, **kwargs):
        self.seen.append(json.loads(json.dumps(messages)))
        return self.replies.pop(0), 1.0


class _Client:
    """Each run_script returns the next canned result. page_snapshot is counted."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = 0
        self.snapshots = 0
        self.tasks: list = []

    def tools_for_claude(self):
        return [{"name": "run_script", "description": "run", "input_schema": {"type": "object"}}]

    async def call_tool(self, name, arguments):
        self.calls += 1
        return self.results.pop(0), 1.0

    async def page_snapshot(self, task=""):
        self.tasks.append(task)
        self.snapshots += 1
        return f"url: https://example.org/now{self.snapshots}\ntitle: Now", 1.0


def _reply(code: str) -> dict:
    return {
        "content": [{"type": "tool_use", "id": f"t{abs(hash(code))}", "name": "run_script", "input": {"code": code}}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _fail(url: str, answer: str = "") -> str:
    # No answer on a value task: the self-check FAILs.
    claimed = {"answer": answer} if answer else {"key_text": "nothing"}
    return format_run_result(ok=True, url=url, step_count=2, text="page body", claimed=claimed)


def _pass(url: str) -> str:
    return format_run_result(ok=True, url=url, step_count=2, text="the value is 42", claimed={"answer": "42"})


def _run(model, client, *, budget=None, monkeypatch=None, tmp_path=None):
    harness = BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path, max_steps=4)
    harness.anthropic = model
    harness.mcp_client = client
    if budget is not None:
        monkeypatch.setattr("bench.arms.SCRIPT_FIRST_REPAIR_BUDGET_S", budget)
    return asyncio.run(harness.run_task("t", "What is the value? Report it.", "https://example.org/"))


def _code(n: int) -> str:
    return f"await page.goto('https://example.org/{n}')\n{EVAL}"


def test_first_pass_never_reads_a_snapshot(tmp_path):
    model = _Model([_reply(_code(1))])
    client = _Client([_pass("https://example.org/1")])
    result = _run(model, client, tmp_path=tmp_path)
    assert result.success is True and result.end_state == "PASS"
    assert client.snapshots == 0 and len(model.seen) == 1
    assert result.repair_sent is False


def test_grounded_repair_then_pass_on_a_later_turn(tmp_path):
    model = _Model([_reply(_code(1)), _reply(_code(2)), _reply(_code(3))])
    client = _Client([_fail("https://example.org/1"), _fail("https://example.org/2"), _pass("https://example.org/3")])
    result = _run(model, client, tmp_path=tmp_path)
    assert result.success is True and result.end_state == "PASS"
    assert client.calls == 3 and client.snapshots == 2
    last_seen = json.dumps(model.seen[-1])
    assert "repair 2 of 3" in last_seen
    # The first snapshot was replaced by a stub; the newest one is in full.
    assert "now1" not in last_seen and "now2" in last_seen
    # A grounded result does not carry the raw page text any more.
    assert "page body" not in last_seen


def test_repairs_stop_at_the_cap(tmp_path):
    codes = [_code(n) for n in range(1, SCRIPT_FIRST_MAX_SCRIPTS + 2)]
    model = _Model([_reply(c) for c in codes])
    client = _Client([_fail(f"https://example.org/{n}") for n in range(1, SCRIPT_FIRST_MAX_SCRIPTS + 2)])
    result = _run(model, client, tmp_path=tmp_path)
    assert client.calls == SCRIPT_FIRST_MAX_SCRIPTS
    assert client.snapshots == SCRIPT_FIRST_MAX_REPAIRS
    assert len(model.seen) == SCRIPT_FIRST_MAX_SCRIPTS
    assert result.success is False and result.end_state == "FAIL"


def test_repeated_script_is_not_run_again(tmp_path):
    model = _Model([_reply(_code(1)), _reply(_code(1))])
    client = _Client([_fail("https://example.org/1")])
    result = _run(model, client, tmp_path=tmp_path)
    assert client.calls == 1 and len(model.seen) == 2
    assert result.success is False and result.end_state == "FAIL"


def test_no_repair_after_the_wall_budget(tmp_path, monkeypatch):
    model = _Model([_reply(_code(1))])
    client = _Client([_fail("https://example.org/1")])
    result = _run(model, client, budget=0.0, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert client.calls == 1 and client.snapshots == 0 and len(model.seen) == 1
    assert result.success is False and result.end_state == "FAIL"


def test_task_terms_keep_numbers_and_long_words():
    terms = task_terms("What is the reason phrase for HTTP status 201? Report it.")
    assert "201" in terms and "reason" in terms and "phrase" in terms and "status" in terms
    assert "what" not in terms and "report" not in terms and "is" not in terms


def test_snapshot_lists_lines_that_match_the_task():
    text = format_page_snapshot({"url": "https://example.org/", "matches": ["201 Created", "  "]})
    assert "page lines that match words in the task:\n  201 Created" in text


def test_the_snapshot_reader_gets_the_task(tmp_path):
    model = _Model([_reply(_code(1)), _reply(_code(2))])
    client = _Client([_fail("https://example.org/1"), _pass("https://example.org/2")])
    _run(model, client, tmp_path=tmp_path)
    assert client.tasks == ["What is the value? Report it."]


def test_same_failure_three_times_ends_the_repairs(tmp_path):
    model = _Model([_reply(_code(n)) for n in range(1, 6)])
    client = _Client([_fail("https://example.org/same") for _ in range(5)])
    result = _run(model, client, tmp_path=tmp_path)
    assert client.calls == 3 and client.snapshots == 2
    assert result.success is False and result.end_state == "FAIL"


def test_look_is_off_by_default(monkeypatch):
    from bench.arms import _SCRIPT_FIRST_PROMPT, prompt_for
    from bench.script_first import ScriptFirstClient

    monkeypatch.delenv("CU_SF_LOOK", raising=False)
    assert [t["name"] for t in ScriptFirstClient().tools_for_claude()] == ["run_script", "task_failed"]
    assert prompt_for("script_first") == _SCRIPT_FIRST_PROMPT
    monkeypatch.setenv("CU_SF_LOOK", "1")
    assert "look" in [t["name"] for t in ScriptFirstClient().tools_for_claude()]
    assert "look(url)" in prompt_for("script_first")


def test_a_look_does_not_use_up_a_turn(tmp_path):
    look = {
        "content": [{"type": "tool_use", "id": "l1", "name": "look", "input": {"url": "https://example.org/"}}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    codes = [_code(n) for n in range(1, 5)]
    model = _Model([look] + [_reply(c) for c in codes])

    class LookClient(_Client):
        async def call_tool(self, name, arguments):
            if name == "look":
                return "LOOK (no check ran)", 1.0
            return await super().call_tool(name, arguments)

    client = LookClient([_fail(f"https://example.org/{n}") for n in range(1, 4)] + [_pass("https://example.org/4")])
    result = _run(model, client, tmp_path=tmp_path)
    assert client.calls == 4 and result.success is True


def test_repair_hint_follows_the_fail_reason():
    def ask(reason):
        return grounded_repair_request(reason, code=GOTO, payload={"ok": True, "steps": 1}, snapshot="url: x",
                                       repair_number=1, max_repairs=3)

    assert "next to its label" in ask("returned evidence is not on the page")
    assert "next to its label" in ask("answer is not in the page text")
    assert "Put the asked value in answer" in ask("the task asks for a value and the script returned no answer")
    assert "as strings" in ask("returned value is not text")
    assert "leave the start page" in ask("the script ended on the start page and returned nothing")
    assert "location.href" in ask("claimed URL does not match the live page")
    assert "copy them" not in ask("the script stopped before it finished (Timeout)")


def test_blind_mode_is_tip2_one_blind_repair(tmp_path, monkeypatch):
    monkeypatch.setenv("CU_SF_REPAIR", "blind")
    model = _Model([_reply(_code(n)) for n in range(1, 5)] + [_reply(_code(9))])
    client = _Client([_fail(f"https://example.org/{n}") for n in range(1, 5)])
    result = _run(model, client, tmp_path=tmp_path)
    assert client.snapshots == 0
    seen = json.dumps(model.seen[1])
    assert "END_STATE_FAILED: " in seen and SNAPSHOT_BEGIN not in seen
    # One repair: a third script is refused, never run.
    assert client.calls == 2
    assert result.success is False


def test_max_repairs_env_caps_grounded_repairs(tmp_path, monkeypatch):
    monkeypatch.setenv("CU_SF_MAX_REPAIRS", "1")
    model = _Model([_reply(_code(n)) for n in range(1, 5)])
    client = _Client([_fail(f"https://example.org/{n}") for n in range(1, 5)])
    result = _run(model, client, tmp_path=tmp_path)
    assert client.calls == 2 and client.snapshots == 1 and len(model.seen) == 2
    assert result.end_state == "FAIL"


def test_script_turns_record_each_verdict_and_time(tmp_path):
    model = _Model([_reply(_code(1)), _reply(_code(2))])
    client = _Client([_fail("https://example.org/1"), _pass("https://example.org/2")])
    result = _run(model, client, tmp_path=tmp_path)
    assert [turn[0] for turn in result.script_turns] == ["FAIL", "PASS"]
    assert result.script_turns[0][1] <= result.script_turns[1][1]
