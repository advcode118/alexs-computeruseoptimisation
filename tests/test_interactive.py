"""InteractiveStage: mocked models only. Real Chrome only against local fixture sites."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from bench.interactive import INTERACTIVE_MAX_CALLS, SEGMENT_MAX_STEPS, run_interactive
from bench.recovery import TaskProfile, configure_gate, plan_checkpoints
from bench.script_first import ScriptFirstClient
from tests.test_recovery import side_effect_server  # noqa: F401  (pytest fixture)
from tests.test_script_cache import DESCRIPTION, EVIDENCE, LINK, START, TASK_ID, _WikiPage

TEXT = TaskProfile("text", "read", False, ("read intent",))
VISUAL = TaskProfile("visual", "read", False, ("visual task",))
DOM = TaskProfile("dom", "read", False, ("interactive controls",))
WIKI_TASK = {"id": TASK_ID, "description": DESCRIPTION, "start_url": START}
GOOD = f'page.getByRole("link", {{ name: "{LINK}" }}).click();\nawait {EVIDENCE};'


def _segment(code, call_id="s"):
    return {"content": [{"type": "tool_use", "id": call_id, "name": "run_script", "input": {"code": code}}],
            "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 4, "cached_tokens": 2}}


def _broken(n):
    return _segment(f'page.getByRole("link", {{ name: "No such link {n}" }}).click();', f"b{n}")


class _Model:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def create_message(self, messages, tools, system=None, max_tokens=4096, tool_choice=None):
        self.calls.append({"messages": json.loads(json.dumps(messages)), "tools": tools,
                           "system": system, "tool_choice": tool_choice})
        if not self.replies:
            raise AssertionError("model called past the cap")
        return self.replies.pop(0), 5.0


def _harness(page, replies, description=DESCRIPTION, profile=TEXT):
    client = ScriptFirstClient(page=page)
    configure_gate(client, description=description, profile=profile)
    return SimpleNamespace(mcp_client=client, anthropic=_Model(replies), provider="anthropic")


def _main_page():
    page = _WikiPage({LINK: "article"})
    page.state = "main"
    return page


def _no_markers(monkeypatch):
    def refuse(*args):
        raise AssertionError("interactive stage read task markers")
    monkeypatch.setattr("bench.tasks.markers_for_task", refuse)


def test_recovers_broken_script_within_cap(monkeypatch):
    _no_markers(monkeypatch)
    harness = _harness(_main_page(), [_broken(1), _segment(GOOD)])
    out = asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT,
                                      checkpoints=plan_checkpoints(WIKI_TASK, TEXT), reason="self-check FAIL"))
    assert out["success"] and out["end_state"] == "PASS"
    assert out["model_calls"] == 2 <= INTERACTIVE_MAX_CALLS
    assert len(harness.anthropic.calls) == 2
    assert out["final_url"] == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert out["input_tokens"] == 20 and out["output_tokens"] == 8 and out["cached_tokens"] == 4
    # Each call after the first sees the live page after the previous segment.
    second = json.dumps(harness.anthropic.calls[1]["messages"])
    assert "--- PAGE NOW ---" in second and "Main Page" in second
    assert harness.anthropic.calls[0]["tool_choice"] == {"type": "any"}
    assert [check["verdict"] for check in out["self_checks"]] == ["FAIL", "PASS"]


def test_answer_key_never_reaches_the_model():
    task = {**WIKI_TASK, "end_markers": {"answer_equals_selector": "#CANARY-SELECTOR", "answer_equals": "CANARY-ANSWER"}}
    harness = _harness(_main_page(), [_broken(1), _segment(GOOD)])
    asyncio.run(run_interactive(task, harness=harness, profile=TEXT, checkpoints=[], reason='FAIL "CANARY-CLAIM"'))
    sent = json.dumps([call["messages"] for call in harness.anthropic.calls]) + json.dumps(harness.anthropic.calls[0]["system"])
    assert "CANARY" not in sent


def test_stops_at_exactly_four_calls():
    replies = [_broken(n) for n in range(INTERACTIVE_MAX_CALLS + 2)]
    harness = _harness(_main_page(), replies)
    out = asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT,
                                      checkpoints=plan_checkpoints(WIKI_TASK, TEXT), reason="self-check FAIL"))
    assert out["model_calls"] == INTERACTIVE_MAX_CALLS == 4
    assert len(harness.anthropic.calls) == 4 and len(harness.anthropic.replies) == 2
    assert not out["success"] and "call cap" in out["success_reason"]
    assert len(out["segments"]) == 4


def test_refused_segments_also_count_toward_the_cap():
    long_code = "\n".join([f'await page.goto("{START}");'] * (SEGMENT_MAX_STEPS + 1))
    harness = _harness(_main_page(), [_segment(long_code, f"l{n}") for n in range(INTERACTIVE_MAX_CALLS + 1)])
    out = asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT, checkpoints=[], reason="x"))
    assert out["model_calls"] == len(harness.anthropic.calls) == 4
    assert not out["success"] and "call cap" in out["success_reason"]


def test_long_segment_is_refused_without_running():
    page = _main_page()
    long_code = "\n".join([f'await page.goto("{START}");'] * (SEGMENT_MAX_STEPS + 1))
    harness = _harness(page, [_segment(long_code), _segment(GOOD)])
    out = asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT,
                                      checkpoints=[], reason="self-check FAIL"))
    assert not any(entry[0] == "goto" for entry in page.log)
    assert out["segments"][0]["refused"] and out["success"] and out["model_calls"] == 2


def test_task_failed_and_no_tool_end_the_stage():
    failed = {"content": [{"type": "tool_use", "id": "f", "name": "task_failed", "input": {"reason": "not here"}}],
              "usage": {"input_tokens": 1, "output_tokens": 1}}
    out = asyncio.run(run_interactive(WIKI_TASK, harness=_harness(_main_page(), [failed, _segment(GOOD)]),
                                      profile=TEXT, checkpoints=[], reason="x"))
    assert out["model_calls"] == 1 and not out["success"] and out["end_state"] == "FAIL"
    prose = {"content": [{"type": "text", "text": "done"}], "usage": {"input_tokens": 1, "output_tokens": 1}}
    out = asyncio.run(run_interactive(WIKI_TASK, harness=_harness(_main_page(), [prose, _segment(GOOD)]),
                                      profile=TEXT, checkpoints=[], reason="x"))
    assert out["model_calls"] == 1 and not out["success"]


def test_checkpoints_evaluated_after_every_segment():
    task = dict(WIKI_TASK, description='Search Wikipedia for "Ada Lovelace"')
    profile = TEXT
    harness = _harness(_main_page(), [_broken(1), _segment(GOOD)], description=task["description"])
    out = asyncio.run(run_interactive(task, harness=harness, profile=profile,
                                      checkpoints=plan_checkpoints(task, profile), reason="x"))
    assert len(out["checkpoints"]) == len(out["segments"]) == 2
    kinds = [{c["kind"]: c["passed"] for c in segment} for segment in out["checkpoints"]]
    assert kinds[0] == {"no_blocked_action": True, "text_present": False}
    assert kinds[1] == {"no_blocked_action": True, "text_present": True}
    # Unmet goal checks are fed back to the model with the snapshot.
    assert "text_present" in json.dumps(harness.anthropic.calls[1]["messages"])


class _ShotPage(_WikiPage):
    def __init__(self, links):
        super().__init__(links)
        self.shots = 0

    async def screenshot(self, **kwargs):
        self.shots += 1
        return b"\xff\xd8jpeg"


@pytest.mark.parametrize("profile,shots", [(TEXT, 0), (DOM, 0), (VISUAL, 2)])
def test_screenshot_only_for_visual_profiles(profile, shots):
    page = _ShotPage({LINK: "article"})
    page.state = "main"
    harness = _harness(page, [_broken(1), _segment(GOOD)], profile=profile)
    asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=profile, checkpoints=[], reason="x"))
    assert page.shots == shots
    images = [b for call in harness.anthropic.calls for m in call["messages"] if isinstance(m["content"], list)
              for b in m["content"] if b.get("type") == "image"]
    assert bool(images) == bool(shots)
    if shots:
        # Only the newest screenshot stays in the transcript.
        last = harness.anthropic.calls[-1]["messages"]
        assert sum(1 for m in last if isinstance(m["content"], list) for b in m["content"] if b.get("type") == "image") == 1


@pytest.mark.parametrize("attempt", [
    'page.getByRole("button", {name: "Place order"}).click();',
    'cu.click("Place order");',
    'page.locator("#commit").click();',
    'page.getByLabel("Name").press("Enter");',
    'page.evaluate(() => document.forms[0].requestSubmit());',
    'page.evaluate(() => document.querySelector("#commit").click());',
])
def test_gate_cannot_be_bypassed(side_effect_server, attempt):  # noqa: F811
    base, requests = side_effect_server

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(f"{base}/checkout.html")
                task = {"id": "local", "description": "Read the account details heading", "start_url": f"{base}/checkout.html"}
                harness = _harness(page, [_segment(attempt), _segment(GOOD)], description=task["description"])
                out = await run_interactive(task, harness=harness, profile=TEXT, checkpoints=plan_checkpoints(task, TEXT), reason="x")
                assert out["needs_approval"] and not out["success"] and out["end_state"] == "UNKNOWN"
                assert "needs approval" in out["success_reason"]
                assert out["model_calls"] == 1 and len(harness.anthropic.replies) == 1
                assert out["blocked_actions"]
                assert out["checkpoints"][-1][0] == {"kind": "no_blocked_action", "value": "", "passed": False}
                await asyncio.sleep(0.2)
                assert not any(method == "POST" or path.startswith("/effect") for method, path in requests)
            finally:
                await browser.close()
    asyncio.run(run())


def test_task_approved_login_and_read_controls_still_work(side_effect_server):  # noqa: F811
    base, requests = side_effect_server

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(f"{base}/login.html")
                task = {"id": "local", "description": "Log in with demo/demo and read the secure area", "start_url": f"{base}/login.html"}
                login = 'cu.fill("Username", "demo"); cu.fill("Password", "demo"); cu.click("Login");'
                harness = _harness(page, [_segment(login)] + [_broken(n) for n in range(3)], description=task["description"])
                out = await run_interactive(task, harness=harness, profile=TEXT, checkpoints=[], reason="x")
                assert not out["blocked_actions"] and not out["needs_approval"]
                assert ("POST", "/authenticate") in requests

                await page.set_content('<form action="/search"><input aria-label="q" name="q"><button>Apply filters</button></form>')
                read = 'cu.fill("q", "rides"); page.getByRole("button", {name: "Apply filters"}).click();'
                harness = _harness(page, [_segment(read)] + [_broken(n) for n in range(3)], description="Find the thrill rides")
                out = await run_interactive({"id": "local", "description": "Find the thrill rides", "start_url": base},
                                            harness=harness, profile=TEXT, checkpoints=[], reason="x")
                assert not out["blocked_actions"] and not out["needs_approval"]
                assert out["segments"][0]["ok"]
            finally:
                await browser.close()
    asyncio.run(run())


def test_openai_adapter_sends_images():
    from bench.openai_client import responses_input

    items = responses_input([{"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "c1", "content": "page"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}},
    ]}])
    assert items[0] == {"type": "function_call_output", "call_id": "c1", "output": "page"}
    assert items[1] == {"role": "user", "content": [{"type": "input_image", "image_url": "data:image/jpeg;base64,QUJD"}]}


def _cascade(tmp_path, monkeypatch, case="recover", provider="anthropic", model=None):
    """run_cascade_task with a real ScriptFirstClient on a fake page, a saved script result and a mock model."""
    from bench.cascade import run_cascade_task
    from bench.tasks import task_by_id
    from tests.test_script_cache import CLICK_SCRIPT, _run, _script_reply

    result, _, _ = _run(tmp_path, _WikiPage({LINK: "article"}), [_script_reply(CLICK_SCRIPT)])
    if case != "accepted":
        result.steps[-1].self_check["verdict"] = "FAIL"
    page = _main_page()
    model = model or _Model([_broken(1), _segment(GOOD)])

    class Harness:
        browser_launch_ms = 0

        def __init__(self, **kwargs):
            assert kwargs["remote_debugging"]
            self.provider = kwargs["provider"]
            self.model = "gpt-6.1-sol" if self.provider == "openai" else "claude-sonnet-5-5"
            self.effort = "medium" if self.provider == "openai" else None
            self.mcp_client = ScriptFirstClient(page=page)
            self.anthropic = model

        async def setup(self):
            pass

        async def teardown(self):
            pass

        async def run_task(self, *args, **kwargs):
            if case == "blocked_state":
                self.mcp_client.gate.record_block("needs approval: test")
            return result

    monkeypatch.setattr("bench.harness.BenchmarkHarness", Harness)
    monkeypatch.setattr("bench.cascade.ground_start_page", lambda *a, **k: {})
    if case == "approval":
        monkeypatch.setattr("bench.cascade.classify_task", lambda *a: TaskProfile("dom", "irreversible", True, ("commit intent",)))

    def no_browser_use(*a, **k):
        raise AssertionError("interactive fallback started browser_use")
    monkeypatch.setattr("bench.cascade.run_recovery", no_browser_use)
    graded_task = task_by_id(TASK_ID)
    assert graded_task["start_url"] == START
    row = asyncio.run(run_cascade_task(graded_task, api_key="mock", runs_dir=tmp_path, provider=provider,
                                       fallback="interactive"))
    return row, model, result


@pytest.mark.parametrize("case", ["recover", "approval", "blocked_state", "accepted"])
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_cascade_interactive_row(tmp_path, monkeypatch, case, provider):
    row, model, result = _cascade(tmp_path, monkeypatch, case, provider)
    ran = case == "recover"
    assert len(model.calls) == (2 if ran else 0)
    assert set(row["stage_wall_ms"]) == {"grounding", "script", "interactive"}
    assert set(row["stage_model_calls"]) == set(row["stage_usd"]) == set(row["stage_tokens"]) == {"script", "interactive"}
    assert row["stage_model_calls"] == {"script": 1, "interactive": 2 if ran else 0}
    assert row["model_calls"] == sum(row["stage_model_calls"].values())
    for key in ("input_tokens", "output_tokens", "cached_tokens"):
        assert row[key] == sum(stage[key] for stage in row["stage_tokens"].values())
    assert row["stage_tokens"]["interactive"]["input_tokens"] == (20 if ran else 0)
    assert row["usd"] == pytest.approx(sum(row["stage_usd"].values()))
    assert (row["stage_usd"]["interactive"] > 0) == ran
    assert (row["stage_wall_ms"]["interactive"] > 0) == ran
    assert row["wall_ms"] >= sum(row["stage_wall_ms"].values()) - 2
    if ran:
        assert row["answered_by"] == "interactive" and row["end_state"] == "PASS"
        assert row["final_url"] == "https://en.wikipedia.org/wiki/Ada_Lovelace"
        assert row["success"] is True, row["success_reason"]
        assert len(row["interactive_checkpoints"]) == len(row["interactive_segments"]) == 2
    elif case == "accepted":
        assert row["answered_by"] == "script"
    else:
        assert row["answered_by"] == "none" and row["handoff_reason"].startswith("needs approval")
        assert row["success"] is False
    from bench.probe import arm_report
    assert arm_report([row], ("cascade",))


def test_fallback_cli_accepts_interactive_and_defaults_to_it(monkeypatch, capsys):
    import inspect

    from bench.cascade import run_cascade_task
    from bench.probe import main

    seen = []

    async def execute(**kwargs):
        seen.append(kwargs["fallback"])
        return []
    monkeypatch.setattr("bench.probe.execute_probe", execute)
    assert main(["--execute", "--arms", "cascade", "--fallback", "interactive"]) == 0
    assert main(["--execute", "--arms", "cascade"]) == 0
    assert seen == ["interactive", "interactive"]
    assert inspect.signature(run_cascade_task).parameters["fallback"].default == "interactive"


def test_precision_check_rejects_a_self_check_pass(monkeypatch):
    seen = []

    def reject(description, record):
        seen.append(record["verdict"])
        return False, "search_results_url"
    monkeypatch.setattr("bench.cascade.precision_check", reject)
    replies = [_segment(GOOD)] + [_segment(f"await {EVIDENCE};", f"e{n}") for n in range(INTERACTIVE_MAX_CALLS - 1)]
    harness = _harness(_main_page(), replies)
    out = asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT, checkpoints=[], reason="x"))
    assert seen == ["PASS"] * 4 and out["model_calls"] == 4 and not out["success"]
    # A capped run ends on its last verdict, not a generic FAIL: PASS that was not accepted is UNKNOWN.
    assert out["end_state"] == "UNKNOWN" and "search_results_url" in out["success_reason"]
    assert "did not accept this end state: search_results_url" in json.dumps(harness.anthropic.calls[1]["messages"])


def test_raw_page_text_stays_hidden_behind_the_snapshot():
    harness = _harness(_main_page(), [_broken(1), _segment(GOOD)])
    asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT, checkpoints=[], reason="x"))
    feedback = json.dumps(harness.anthropic.calls[1]["messages"][-1])
    assert "--- PAGE NOW ---" in feedback and "Welcome to Wikipedia" not in feedback


class _FlakyModel(_Model):
    async def create_message(self, *args, **kwargs):
        if len(self.calls) == 1:
            self.calls.append({})
            raise RuntimeError("HTTP 529 overloaded")
        return await super().create_message(*args, **kwargs)


def test_model_error_keeps_usage_and_ends_the_stage():
    harness = _harness(_main_page(), [_broken(1), _segment(GOOD)])
    harness.anthropic = _FlakyModel([_broken(1), _segment(GOOD)])
    out = asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT, checkpoints=[], reason="x"))
    assert out["end_state"] == "FAIL" and "interactive error: RuntimeError" in out["success_reason"]
    assert out["model_calls"] == 1 and out["input_tokens"] == 10


def test_unpriced_model_reply_is_not_swallowed():
    from bench.openai_spend import PriceUnknown

    class Unpriced(_Model):
        async def create_message(self, *args, **kwargs):
            raise PriceUnknown("unknown usage field")
    harness = _harness(_main_page(), [])
    harness.anthropic = Unpriced([])
    with pytest.raises(PriceUnknown):
        asyncio.run(run_interactive(WIKI_TASK, harness=harness, profile=TEXT, checkpoints=[], reason="x"))


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_interactive_stage_cost_and_steps_are_exact(tmp_path, monkeypatch, provider):
    from bench.budget import estimate_usd
    from bench.openai_spend import price_usd

    three = _segment(f'await page.goto("{START}");\n' + GOOD)
    row, _, result = _cascade(tmp_path, monkeypatch, "recover", provider, model=_Model([_broken(1), three]))
    expected = price_usd("gpt-6.1-sol", 20, 8, 4, 0, 0) if provider == "openai" else estimate_usd(20, 8)
    assert row["stage_usd"]["interactive"] == pytest.approx(expected)
    # Executed steps only: the broken segment ran 0 steps, the good one 3 (not 2 segments).
    assert row["steps"] == result.total_steps + 3
    # Fields graded on the script stage are recomputed or cleared for the interactive end state.
    assert row["grade_completed"] is None
    assert row["page_answer_success"] is True and row["grade_url"] == row["final_url"]


def test_interactive_grade_read_is_outside_the_timer(tmp_path, monkeypatch):
    import bench.cascade as cascade

    original = cascade._grade_interactive

    async def slow_grade(*args, **kwargs):
        await asyncio.sleep(1.0)
        return await original(*args, **kwargs)
    monkeypatch.setattr(cascade, "_grade_interactive", slow_grade)
    row, _, _ = _cascade(tmp_path, monkeypatch, "recover")
    assert row["stage_wall_ms"]["interactive"] < 1000
    assert row["wall_ms"] < sum(row["stage_wall_ms"].values()) + 1000


def test_model_error_in_interactive_still_returns_a_charged_row(tmp_path, monkeypatch):
    model = _FlakyModel([_broken(1), _segment(GOOD)])
    row, _, _ = _cascade(tmp_path, monkeypatch, "recover", "openai", model=model)
    assert row["stage_model_calls"]["interactive"] == 1
    assert row["input_tokens"] == row["stage_tokens"]["script"]["input_tokens"] + 10
    assert row["success"] is False and row["answered_by"] == "none"
    assert "interactive error" in row["grade_completion_reason"]
    # The script stage graded the article page; the interactive end state is the main page.
    assert row["page_answer_success"] is False and "Main_Page" in row["final_url"]


def test_late_gate_block_is_never_answered_by_interactive(tmp_path, monkeypatch):
    import bench.interactive as interactive

    original = interactive.run_interactive

    async def late_block(task, *, harness, **kwargs):
        out = await original(task, harness=harness, **kwargs)
        harness.mcp_client.gate.record_block("needs approval: late binding")
        return out
    monkeypatch.setattr(interactive, "run_interactive", late_block)
    row, _, _ = _cascade(tmp_path, monkeypatch, "recover")
    assert row["answered_by"] == "none" and row["success"] is False
    assert row["handoff_reason"].startswith("needs approval") and row["blocked_actions"]
