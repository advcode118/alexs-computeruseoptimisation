"""Segment controller integration: fake providers and routed local Chromium only."""

from __future__ import annotations

import asyncio
import copy
import json
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from bench.harness import BenchmarkHarness, MAX_SNAPSHOT_CHARS
from bench.script_first import SNAPSHOT_BEGIN, SNAPSHOT_END, ScriptFirstClient


ORIGIN = "http://127.0.0.1:48123"
START = ORIGIN + "/start"
DESCRIPTION = "Go through the wizard and report its code."
EVIDENCE = """await page.evaluate(() => ({url: location.href, answer: document.querySelector('#answer').innerText}));"""
DONE = "<title>Wizard receipt</title><h1>Wizard receipt</h1><p id='answer'>receipt-73</p>"
USAGE = {"input_tokens": 11, "output_tokens": 7, "cached_tokens": 3,
         "cache_write_30m_tokens": 1, "cache_write_12h_tokens": 0}


def tool(name: str, args: dict) -> dict:
    return {"content": [{"type": "tool_use", "id": "call", "name": name, "input": args}],
            "stop_reason": "tool_use", "usage": dict(USAGE)}


def script(code: str, **kwargs) -> dict:
    return tool("run_script", {"code": code, **kwargs})


def prose(text: str = "TASK_COMPLETE receipt-73") -> dict:
    return {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "usage": dict(USAGE)}


class Model:
    def __init__(self, replies: list[dict], on_call=None):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.on_call = on_call

    async def create_message(self, messages, tools, **kwargs):
        self.calls.append(copy.deepcopy({"messages": messages, "tools": tools, **kwargs}))
        if self.on_call:
            self.on_call()
        if not self.replies:
            raise AssertionError("unexpected model call")
        return self.replies.pop(0), 1.0


@pytest.fixture(autouse=True)
def segment_environment(monkeypatch):
    monkeypatch.setenv("CU_SF_SEGMENTS", "1")
    for name in ("CU_SF_REPAIR", "CU_SF_MAX_REPAIRS", "CU_SF_STRATEGY", "CU_SF_LOOK"):
        monkeypatch.delenv(name, raising=False)


@asynccontextmanager
async def local_page(html: str = DONE):
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()

            async def route(request):
                if request.request.url.startswith(ORIGIN + "/"):
                    await request.fulfill(body=html, content_type="text/html")
                else:
                    await request.abort()

            await page.route("**/*", route)
            yield page
        finally:
            await browser.close()


def harness_for(tmp_path, page, replies, *, client=None, model=None, max_steps=8, cache=None):
    harness = BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path,
                               max_steps=max_steps, script_cache=cache)
    harness.anthropic = model or Model(replies)
    harness.mcp_client = client or ScriptFirstClient(page=page)
    return harness


async def run(harness):
    return await harness.run_task("synthetic-segments", DESCRIPTION, START,
                                  expected_answer="GRADE_ONLY_SECRET", check_url_contains="GRADE_ONLY_SECRET")


def assert_usage(result, count):
    assert result.model_calls == count
    assert result.total_input_tokens == 11 * count
    assert result.total_output_tokens == 7 * count
    assert result.total_cached_tokens == 3 * count
    assert result.total_cache_write_30m_tokens == count
    assert result.total_tool_ms >= sum(step.tool_time_ms for step in result.steps) - 0.01


def test_wizard_bypasses_cache_specialists_and_live_markers(tmp_path, monkeypatch):
    touched = []

    def forbidden(*args, **kwargs):
        touched.append("forbidden")
        raise AssertionError("cache/specialist accessed")

    cache = SimpleNamespace(lookup=forbidden, save=forbidden, drop=forbidden)
    monkeypatch.setenv("CU_SF_STRATEGY", "form,nav,spa")
    monkeypatch.setattr("bench.strategy_form.run_for_harness", forbidden)
    monkeypatch.setattr("bench.strategy_spa.maybe_run_spa", forbidden)
    monkeypatch.setattr("bench.strategy_nav.claims", forbidden)
    grading = False
    marker_reads = []
    original_grade = BenchmarkHarness._read_shared_page

    def markers(task_id):
        assert grading, "live execution read answer key"
        marker_reads.append(task_id)
        return {"answer_equals_selector": "#answer"}

    async def grade(self, task_id, steps):
        nonlocal grading
        grading = True
        try:
            await original_grade(self, task_id, steps)
        finally:
            grading = False

    monkeypatch.setattr("bench.tasks.markers_for_task", markers)
    monkeypatch.setattr(BenchmarkHarness, "_read_shared_page", grade)
    html = """<title>Wizard</title><h1>Stage 1</h1><label>Name<input id="name"></label>
        <button onclick="history.pushState({},'', '/stage2'); document.body.innerHTML=
        '<h1>Stage 2</h1><button onclick=&quot;location.href=\\'/done\\'&quot;>Finish</button>'">Next</button>"""

    async def check():
        async with local_page(html) as page:
            await page.route(ORIGIN + "/done", lambda route: route.fulfill(body=DONE, content_type="text/html"))
            first = f"""await page.goto('{START}');
                await page.getByLabel('Name').fill('Pat');
                await page.getByRole('button', {{name: 'Next'}}).click();"""
            second = "await page.getByRole('button', {name: 'Finish'}).click();\n" + EVIDENCE
            harness = harness_for(tmp_path, page, [
                script(first, final=False, expect=[{"text": "Stage 2"}]), script(second),
            ], cache=cache)
            # A reused client starts every task with fresh segment budgets.
            harness.mcp_client.segment_index = 99
            harness.mcp_client.segment_looks = 99
            harness.mcp_client.segment_wait_left = 0
            result = await run(harness)
            assert result.success, result.success_reason
            assert result.segment_mode == "on" and result.end_state == "PASS"
            assert not result.repair_sent
            assert_usage(result, 2)
            assert len(result.segments) == 2 and result.segments[0]["segment"] == 1
            assert result.segments[0]["final"] is False and "verdict" not in result.segments[0]
            assert result.segments[0]["moved"]
            assert [m["op"] for m in result.segments[0]["mutations_run"]] == ["fill", "click"]
            assert result.script_steps == 5
            assert [t[0] for t in result.script_turns] == ["PASS"]
            shown = json.dumps(harness.anthropic.calls)
            assert "Stage 2" in shown and SNAPSHOT_BEGIN in shown and SNAPSHOT_END in shown
            assert "GRADE_ONLY_SECRET" not in shown and "selector_text" not in shown
            assert marker_reads == ["synthetic-segments"] and not touched
            saved = json.loads(harness.save_result(result, "local").read_text().splitlines()[0])
            assert saved["segment_cache"] == saved["segment_specialists"] == "disabled"
            assert saved["segments"] == result.segments
    asyncio.run(check())


@pytest.mark.parametrize("queued_script", [False, True])
def test_partial_submit_failure_recovers_without_replaying_post(tmp_path, monkeypatch, queued_script):
    # Keep the real actionability timeout: a 250 ms cap could time out Submit
    # before it emitted input on Windows, testing a different recovery scenario.
    html = """<title>Order</title><h1>Order form</h1><form onsubmit="event.preventDefault();
        fetch('/submit',{method:'POST'}).then(() => { history.pushState({},'', '/receipt');
        document.body.innerHTML='<h1>Saved</h1><p id=answer>receipt-73</p>'; });">
        <label>Name<input name="name"></label><button>Submit</button></form>"""

    async def check():
        async with local_page(html) as page:
            posts = []

            async def submit(route):
                posts.append(route.request.method)
                await route.fulfill(body="saved")

            await page.route(ORIGIN + "/submit", submit)
            await page.goto(START)
            first = """await page.getByLabel('Name').fill('Pat');
                await page.getByRole('button', {name: 'Submit'}).click();
                await page.getByRole('button', {name: 'Missing'}).click();
                """ + EVIDENCE
            first_reply = script(first, final=False)
            if queued_script:
                pending = script(f"await page.goto('{START}');\n" + first, final=False)["content"][0]
                pending["id"] = "queued-replay"
                first_reply["content"].append(pending)
            harness = harness_for(tmp_path, page, [
                first_reply, script(EVIDENCE, expect=[{"text": "Saved"}]),
            ])
            result = await run(harness)
            assert result.success, result.success_reason
            assert posts == ["POST"]
            failed = result.segments[0]
            assert failed["ok"] is False and failed["failed_step"]["index"] == 3
            assert failed["steps_run"] == 2 and failed["effects_uncertain"]
            assert len(failed["mutations_run"]) == 2
            recovery = json.dumps(harness.anthropic.calls[1]["messages"]).lower()
            assert "step 3" in recovery and "saved" in recovery
            assert "already" in recovery and "inspect" in recovery
            if queued_script:
                assert "not run." in recovery
            assert result.repair_sent and result.repair_reply == "script"
            assert_usage(result, 2)
    asyncio.run(check())


@pytest.mark.parametrize("first", ["look", "segment", "failed-check"])
def test_observations_segments_and_checks_cannot_finish_with_prose(tmp_path, monkeypatch, first):
    monkeypatch.setattr("bench.segments.SEG_WAIT_S", 0.01)

    async def check():
        async with local_page() as page:
            if first == "look":
                initial = tool("look", {"url": START})
            else:
                initial = script(f"await page.goto('{ORIGIN}/done');", final=False,
                                 expect=[{"text": "missing" if first == "failed-check" else "receipt-73"}])
            harness = harness_for(tmp_path, page, [initial, prose()])
            result = await run(harness)
            assert not result.success and result.end_state != "PASS"
            assert_usage(result, 2)
    asyncio.run(check())


def test_one_shot_pass_never_takes_a_snapshot(tmp_path, monkeypatch):
    async def forbidden(*args):
        raise AssertionError("one-shot path took snapshot")

    monkeypatch.setattr(ScriptFirstClient, "page_snapshot", forbidden)

    async def check():
        async with local_page() as page:
            harness = harness_for(tmp_path, page, [script(f"await page.goto('{ORIGIN}/done');\n" + EVIDENCE)])
            result = await run(harness)
            assert result.success, result.success_reason
            assert_usage(result, 1)
            assert result.total_snapshot_tokens == 0 and result.segments[0]["checks"] == []
    asyncio.run(check())


@pytest.mark.parametrize("wrong_answer", [False, True])
def test_final_expectations_only_downgrade(tmp_path, monkeypatch, wrong_answer):
    monkeypatch.setenv("CU_SF_MAX_REPAIRS", "0")
    if not wrong_answer:
        monkeypatch.setattr("bench.segments.SEG_WAIT_S", 0.01)

    async def check():
        async with local_page() as page:
            evidence = EVIDENCE if not wrong_answer else "await page.evaluate(() => ({answer: 'invented'}));"
            harness = harness_for(tmp_path, page, [
                script(f"await page.goto('{ORIGIN}/done');\n" + evidence,
                       expect=[{"text": "receipt-73" if wrong_answer else "not present"}]),
            ])
            result = await run(harness)
            assert not result.success and result.end_state == "FAIL"
            assert result.segments[0]["checks"][0]["ok"] is wrong_answer
            assert_usage(result, 1)
    asyncio.run(check())


@pytest.mark.parametrize("looks", [0, 2])
def test_script_and_call_caps_count_every_segment(tmp_path, looks):
    async def check():
        async with local_page() as page:
            replies = [tool("look", {"url": START}) for _ in range(looks)]
            replies += [script(f"await page.goto('{ORIGIN}/stage/{i}');", final=False) for i in range(8)]
            harness = harness_for(tmp_path, page, replies, max_steps=30)
            result = await run(harness)
            assert not result.success
            assert len(result.segments) == result.script_steps == 6
            assert result.total_steps == 6 + looks
            assert_usage(result, 6 + looks)
            assert result.script_turns == []
            for request in harness.anthropic.calls:
                for message in request["messages"]:
                    if isinstance(message["content"], list):
                        for block in message["content"]:
                            if block["type"] == "tool_result":
                                assert len(block["content"]) <= MAX_SNAPSHOT_CHARS
                                if block["content"].startswith("{"):
                                    json.loads(block["content"].splitlines()[0])
    asyncio.run(check())


def test_third_look_and_lower_caller_budget_stop_before_tool(tmp_path):
    async def check():
        async with local_page() as page:
            harness = harness_for(tmp_path, page, [tool("look", {"url": START})] * 3)
            result = await run(harness)
            assert not result.success and result.model_calls == 3
            assert result.total_steps == 2 and harness.mcp_client.segment_looks == 2
            harness = harness_for(tmp_path, page, [
                script(f"await page.goto('{ORIGIN}/stage/{i}');", final=False) for i in range(5)
            ], max_steps=2)
            result = await run(harness)
            assert_usage(result, 2)
            assert len(result.segments) == 2 and not result.success
    asyncio.run(check())


def test_identical_nonfinal_code_only_repeats_while_it_progresses(tmp_path):
    html = """<title>Wizard</title><h1>Wizard</h1>
        <button onclick="history.pushState({},'', '/stage/'+(++window.n))">Next</button>
        <p id="answer">receipt-73</p><script>window.n=0</script>"""

    async def check():
        async with local_page(html) as page:
            await page.goto(START)
            next_code = "await page.getByRole('button', {name: 'Next'}).click();"
            harness = harness_for(tmp_path, page, [
                script(next_code, final=False), script(next_code, final=False), script(EVIDENCE),
            ])
            result = await run(harness)
            assert result.success and result.model_calls == 3, result.success_reason
            assert await page.evaluate("window.n") == 2
            # A read-only repeat gets one chance after its initial observed progress.
            harness = harness_for(tmp_path, page, [script(EVIDENCE, final=False)] * 3)
            result = await run(harness)
            assert not result.success and "exact script" in result.success_reason
            assert result.model_calls == 3 and len(result.segments) == 2
    asyncio.run(check())


def test_two_consecutive_no_progress_scripts_stop(tmp_path):
    async def check():
        async with local_page() as page:
            replies = [script(f"await page.goto('{ORIGIN}/steady');\n"
                              f"await page.evaluate(() => {i});", final=False) for i in range(5)]
            harness = harness_for(tmp_path, page, replies)
            result = await run(harness)
            assert not result.success and result.end_state == "FAIL"
            assert result.success_reason == "no progress"
            assert result.model_calls == len(result.segments) == 3
    asyncio.run(check())


@pytest.mark.parametrize("where", ["before-model", "after-model", "after-launch"])
def test_deadline_admissions_and_issued_model_usage(tmp_path, monkeypatch, where):
    clock = [time.perf_counter()]
    monkeypatch.setattr("bench.harness.time", SimpleNamespace(perf_counter=lambda: clock[0]))
    if where == "before-model":
        monkeypatch.setattr("bench.segments.SEG_WALL_S", 0.0)

    async def check():
        async with local_page() as page:
            model = Model([script(f"await page.goto('{ORIGIN}/done');\n" + EVIDENCE)],
                          on_call=(lambda: clock.__setitem__(0, clock[0] + 46)) if where == "after-model" else None)
            harness = harness_for(tmp_path, page, [], model=model)
            if where == "after-launch":
                async def delayed_launch():
                    clock[0] += 46
                harness._wait_for_browser = delayed_launch
            result = await run(harness)
            assert not result.success and result.end_state == "UNKNOWN"
            assert page.url == "about:blank" and result.steps == []
            assert_usage(result, 0 if where == "before-model" else 1)
            assert harness.mcp_client.segment_index == 0
    asyncio.run(check())


def test_browser_timeout_keeps_partial_receipt_and_stops_next_action(tmp_path, monkeypatch):
    monkeypatch.setattr("bench.segments.SEG_WALL_S", 0.15)

    async def check():
        async with local_page() as page:
            await page.goto(START)
            harness = harness_for(tmp_path, page, [script(
                "await page.evaluate(() => new Promise(resolve => setTimeout(() => resolve('late'), 2000)));\n"
                f"await page.goto('{ORIGIN}/must-not-run');", final=False,
            )])
            result = await run(harness)
            assert not result.success and result.model_calls == 1
            assert page.url == START
            assert len(result.steps) == len(result.segments) == 1
            receipt = result.segments[0]
            assert receipt["ok"] is False and receipt["steps_run"] == 0
            assert receipt["failed_step"]["index"] == 1 and receipt["effects_uncertain"]
            assert result.total_tool_ms >= 100 and result.total_wall_ms < 1500
            assert not result.repair_sent
    asyncio.run(check())


def test_existing_repair_cap_and_malformed_arguments_are_counted(tmp_path, monkeypatch):
    monkeypatch.setenv("CU_SF_MAX_REPAIRS", "1")

    async def check():
        async with local_page() as page:
            harness = harness_for(tmp_path, page, [
                script(f"await page.goto('{ORIGIN}/must-not-run');", final="false"),
                script(f"await page.goto('{ORIGIN}/done');\n"
                       "await page.evaluate(() => ({answer: 'invented'}));"),
                script(EVIDENCE),
            ])
            result = await run(harness)
            assert not result.success and result.end_state == "FAIL"
            assert len(result.segments) == 2 and result.script_steps == 2
            assert result.segments[0]["url_after"] == "about:blank"
            assert result.segments[0]["steps_run"] == 0 and result.segments[0]["ok"] is False
            assert result.repair_sent and result.repair_reply == "script"
            assert_usage(result, 2)
    asyncio.run(check())


@pytest.mark.parametrize("broken", ["missing", "wrong-final", "invalid-check", "wrong-url", "wrong-looks"])
def test_broken_receipt_fails_closed(tmp_path, broken):
    class BrokenReceiptClient(ScriptFirstClient):
        async def call_tool(self, name, args):
            raw, ms = await super().call_tool(name, args)
            lines = raw.splitlines()
            payload = json.loads(lines[0])
            if broken == "missing":
                del payload["receipt"]
            elif broken == "wrong-final":
                payload["receipt"]["final"] = False
            elif broken == "wrong-url":
                payload["receipt"]["url_after"] = ORIGIN + "/other"
            elif broken == "wrong-looks":
                payload["receipt"]["looks_left"] = 0
            else:
                payload["receipt"]["checks"] = [{"ok": True}]
            return "\n".join([json.dumps(payload), *lines[1:]]), ms

    async def check():
        async with local_page() as page:
            harness = harness_for(tmp_path, page, [script(f"await page.goto('{ORIGIN}/done');\n" + EVIDENCE)],
                                  client=BrokenReceiptClient(page=page))
            result = await run(harness)
            assert not result.success and result.end_state == "FAIL"
            assert "receipt" in result.success_reason and not result.repair_sent
    asyncio.run(check())


@pytest.mark.parametrize("legacy", [False, True])
def test_flag_off_and_legacy_keep_original_completion_and_rows(tmp_path, monkeypatch, legacy):
    if legacy:
        monkeypatch.setenv("CU_SF_REPAIR", "blind")
    else:
        monkeypatch.delenv("CU_SF_SEGMENTS")

    async def check():
        async with local_page() as page:
            harness = harness_for(tmp_path, page, [script(f"await page.goto('{ORIGIN}/done');\n" + EVIDENCE,
                                                        final=False, expect=[{"text": "missing"}])])
            result = await run(harness)
            assert result.success and result.model_calls == 1
            assert result.segments == []
            saved = json.loads(harness.save_result(result, "legacy" if legacy else "off").read_text().splitlines()[0])
            if legacy:
                assert saved["segment_mode"] == "off:legacy"
                assert "segment_cache" not in saved
            else:
                assert "segment_mode" not in saved and "segments" not in saved
    asyncio.run(check())


def test_openai_probe_uses_eight_calls_and_serializes_segment_fields(tmp_path, monkeypatch):
    from bench.openai_client import OpenAIClient
    from bench.probe import run_claude_arm

    requests = []
    replies = [tool("look", {"url": START})] * 2
    replies += [script(f"await page.goto('{ORIGIN}/stage/{i}');", final=False) for i in range(1, 6)]
    replies += [script(f"await page.goto('{ORIGIN}/done');\n" + EVIDENCE,
                       expect=[{"control": {"name": "Wizard receipt", "role": "heading"}}])]

    def transport(url, headers, body):
        requests.append(copy.deepcopy(body))
        block = replies.pop(0)["content"][0]
        return json.dumps({"output": [{
            "type": "function_call", "call_id": f"c{len(requests)}", "name": block["name"],
            "arguments": json.dumps(block["input"]),
        }], "usage": {"input_tokens": 11, "output_tokens": 7,
                       "input_tokens_details": {"cached_tokens": 3}}})

    async def check():
        async with local_page() as page:
            async def setup(self):
                assert self.max_steps == 8
                self.mcp_client = ScriptFirstClient(page=page)
                self.anthropic = OpenAIClient("offline", "gpt-6-luna", "medium", transport=transport)

            monkeypatch.setattr(BenchmarkHarness, "setup", setup)
            row = await run_claude_arm(
                "script_first", {"id": "synthetic-segments", "description": DESCRIPTION,
                                 "start_url": START, "check_text": "receipt-73"},
                api_key="offline", headless=True, runs_dir=tmp_path, provider="openai",
                model="gpt-6-luna", effort="medium",
            )
            assert row["success"], row["success_reason"]
            assert row["model_calls"] == len(requests) == 8
            assert row["input_tokens"] == 88 and row["output_tokens"] == 56 and row["cached_tokens"] == 24
            assert row["segment_mode"] == "on" and len(row["segments"]) == 6
            assert row["segment_cache"] == row["segment_specialists"] == "disabled"
            assert row["script_steps"] == 7
            schema = next(t["parameters"] for t in requests[0]["tools"] if t["name"] == "run_script")
            assert "expect" in schema["properties"] and "final" in schema["properties"]
            assert row["provider"] == "openai" and row["claude"] is False
    asyncio.run(check())


def test_same_url_wizard_and_final_read_are_not_stalls(tmp_path):
    html = """<title>Wizard</title><h1>Phase 1</h1><label>Name<input></label>
        <button onclick="document.querySelector('h1').innerText='Phase 2';
        document.querySelector('label').firstChild.textContent='Email';
        this.setAttribute('onclick', `document.querySelector('h1').innerText='Phase 3';
        document.querySelector('label').remove(); this.innerText='Confirm';
        this.setAttribute('onclick', 'document.body.innerHTML=&quot;<h1>Receipt</h1><p id=answer>receipt-73</p>&quot;')`)">Next</button>"""

    async def check():
        async with local_page(html) as page:
            await page.goto(ORIGIN + "/wizard")
            harness = harness_for(tmp_path, page, [
                script("page.getByLabel('Name').fill('Pat'); page.getByRole('button', {name:'Next'}).click();", final=False),
                script("page.getByLabel('Email').fill('pat@example.test'); page.getByRole('button', {name:'Next'}).click();", final=False),
                script("page.getByRole('button', {name:'Confirm'}).click();\n" + EVIDENCE),
            ])
            result = await run(harness)
            assert result.success, result.success_reason
            assert result.model_calls == 3 and page.url == ORIGIN + "/wizard"
        async with local_page() as page:
            await page.goto(ORIGIN + "/done")
            harness = harness_for(tmp_path, page, [
                script("page.evaluate(() => document.title)", final=False),
                script("page.evaluate(() => document.querySelector('h1').innerText)", final=False),
                script(EVIDENCE),
            ])
            result = await run(harness)
            assert result.success, result.success_reason
            assert result.model_calls == 3
    asyncio.run(check())


@pytest.mark.parametrize("boundary", ["look", "segment"])
def test_successful_observation_boundary_refuses_queued_mutations(tmp_path, boundary):
    html = """<title>Wizard</title><h1>Wizard</h1><button onclick="
        fetch('/submit',{method:'POST'}); document.querySelector('#answer').innerText='receipt-73'">Submit</button>
        <p id="answer">pending</p>"""

    async def check():
        async with local_page(html) as page:
            posts = []
            async def submit(route):
                posts.append(route.request.method)
                await route.fulfill(body="saved")
            await page.route(ORIGIN + "/submit", submit)
            await page.goto(ORIGIN + "/wizard")
            submit_code = "page.getByRole('button', {name:'Submit'}).click()"
            first = tool("look", {}) if boundary == "look" else script(submit_code, final=False)
            queued = script(f"page.goto('{ORIGIN}/wizard'); {submit_code}", final=False)["content"][0]
            queued["id"] = "queued-mutation"
            first["content"].append(queued)
            final = f"{submit_code};\n{EVIDENCE}" if boundary == "look" else EVIDENCE
            harness = harness_for(tmp_path, page, [first, script(final)])
            result = await run(harness)
            assert result.success, result.success_reason
            assert posts == ["POST"]
            feedback = harness.anthropic.calls[1]["messages"][-1]["content"]
            skipped = next(block for block in feedback if block["tool_use_id"] == "queued-mutation")
            assert skipped["content"].startswith("Not run.")
            assert result.model_calls == 2
            assert len(result.segments) == (1 if boundary == "look" else 2)
    asyncio.run(check())


def test_added_expectation_allows_readiness_repair(tmp_path, monkeypatch):
    monkeypatch.setattr("bench.script_first._LAND_TIMEOUT_S", 0.01)
    html = """<title>Receipt</title><h1>Receipt</h1><p id=answer></p>
        <script>setTimeout(() => answer.innerText='receipt-73', 600)</script>"""

    async def check():
        async with local_page(html) as page:
            code = f"page.goto('{ORIGIN}/done');\n" + EVIDENCE
            harness = harness_for(tmp_path, page, [
                script(code), script(code, expect=[{"text": "receipt-73"}]),
            ])
            result = await run(harness)
            assert result.success, result.success_reason
            assert result.repair_sent and result.model_calls == 2
            assert result.segments[1]["checks"][0]["ok"]
    asyncio.run(check())


def test_failed_moved_segment_cannot_repeat_verbatim(tmp_path):
    async def check():
        async with local_page() as page:
            code = f"page.goto('{ORIGIN}/done'); page.evaluate(() => {{ throw new Error('after navigation') }})"
            harness = harness_for(tmp_path, page, [script(code, final=False)] * 2)
            result = await run(harness)
            assert not result.success and "exact script" in result.success_reason
            assert result.model_calls == 2 and len(result.segments) == 1
    asyncio.run(check())


@pytest.mark.parametrize("honest", [False, True])
def test_segment_probe_never_schedules_a_paid_warm_pass(tmp_path, monkeypatch, honest):
    from bench.budget import LAST_RECORDED_TOTAL_USD
    from bench.probe import execute_probe, plan_probe

    # Planning and scheduling only; the task runner and ledger are synthetic.
    ledger = SimpleNamespace(running_total_usd=LAST_RECORDED_TOTAL_USD, save=lambda: None)
    monkeypatch.setattr("bench.probe.SpendLedger.load", lambda *args: ledger)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-not-sent")
    monkeypatch.setattr("bench.probe.probe_tasks", lambda *args: [{"id": "synthetic", "description": DESCRIPTION, "start_url": START}])
    calls = []
    async def fake(arm, task, **kwargs):
        calls.append(arm)
        assert kwargs["script_cache"] is None
        return {"arm": arm, "task_id": task["id"], "success": True,
                "steps": 1, "wall_ms": 1, "claude": False}, kwargs["probe_spent"]
    monkeypatch.setattr("bench.probe._run_one", fake)
    plan = plan_probe(arms="script_first", warm_replay=True, honest=honest)
    assert "script_first" not in plan["warm_arms"]
    rows = asyncio.run(execute_probe(arms="script_first", warm_replay=True, honest=honest,
                                    runs_dir=tmp_path))
    assert calls.count("script_first") == 1
    assert all(row["pass"] == "cold" for row in rows)


@pytest.mark.parametrize("mode", ["off", "on", "off:legacy"])
def test_openai_dry_plan_reports_effective_segment_configuration(monkeypatch, mode):
    from bench.openai_run import plan_openai_probe

    monkeypatch.setenv("CU_SF_SEGMENTS", "0" if mode == "off" else "1")
    if mode == "off:legacy":
        monkeypatch.setenv("CU_SF_REPAIR", "blind")
    monkeypatch.setattr("bench.openai_run._tasks", lambda *args, **kwargs: [{"id": "synthetic"}])
    plan = plan_openai_probe(
        arms=("script_first",), split="dev3", sweep=False, model="gpt-6-luna", effort="medium",
        one_task=False, no_model_only=False, warm_replay=False, honest=False,
    )
    assert plan["execute"] is False and plan["network"] == "refused"
    if mode == "off":
        assert "segment_mode" not in plan
    else:
        assert plan["segment_mode"] == mode
    if mode == "on":
        assert plan["segment_max_calls"] == 8
        assert plan["segment_warm_replay"] == plan["segment_cache"] == "disabled"


def test_nonfinal_script_output_is_available_for_the_next_decision(tmp_path):
    async def check():
        async with local_page() as page:
            harness = harness_for(tmp_path, page, [
                script(f"page.goto('{ORIGIN}/done'); page.evaluate(() => ({{answer: 'derived-only-value'}}))", final=False),
                script(EVIDENCE),
            ])
            result = await run(harness)
            assert result.success, result.success_reason
            shown = harness.anthropic.calls[1]["messages"][-1]["content"][0]["content"]
            header = json.loads(shown.splitlines()[0])
            assert "derived-only-value" in header["script_output"]
            assert header["script_output_truncated"] is False
            assert "derived-only-value" not in result.steps[0].page_text
    asyncio.run(check())
