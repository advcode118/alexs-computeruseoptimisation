"""Bench harness tests. No network and no model calls."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bench.budget import (
    LedgerMissing,
    default_spend_path,
    PRIOR_INPUT_TOKENS,
    PRIOR_OUTPUT_TOKENS,
    BudgetExceeded,
    ModelNotAllowed,
    SpendLedger,
    assert_allowed_model,
    estimate_usd,
)
from bench.harness import (
    DEFAULT_MODEL,
    MAX_SNAPSHOT_CHARS,
    AnthropicClient,
    BenchmarkHarness,
    PlaywrightMCPClient,
    TaskResult,
    cap_messages_for_model,
    encode_ndjson,
    estimate_tokens,
    execute_benchmark_tasks,
    extract_page_snapshot,
    run_benchmark,
    snapshot_tokens_for,
)
from bench.judge import llm_judge
from bench.replay_shortcuts import (
    HANDMADE_SNAPSHOT_NOTE,
    load_snapshots_from_run,
    parse_aria_snapshot_to_observation,
)
from bench.run import build_parser


def _result(task_id: str, input_tokens: int = 0, output_tokens: int = 0) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        task_description="d",
        success=True,
        success_reason="ok",
        total_steps=1,
        total_wall_ms=1,
        total_model_ms=1,
        total_tool_ms=0,
        total_other_ms=0,
        total_input_tokens=input_tokens,
        total_output_tokens=output_tokens,
        total_snapshot_tokens=0,
    )


def _navigate_page() -> str:
    body = "\n".join(
        [
            '- searchbox "Search Wikipedia" [ref=e4]',
            '- button "Search" [ref=e5]',
            *[f'- link "Item {i}" [ref=e{i}]' for i in range(20, 500)],
        ]
    )
    preamble = (
        "### Ran Playwright code\n```js\n"
        "await page.goto('https://en.wikipedia.org/wiki/Main_Page');\n```\n"
        "### Page\n"
    )
    return (
        preamble
        + "- Page URL: https://en.wikipedia.org/wiki/Main_Page\n"
        + "- Page Title: Wikipedia\n"
        + "### Snapshot\n```yaml\n"
        + body
        + "\n```\n"
    )


def _find_page() -> str:
    return (
        '### Matches\n'
        '- link "Ada Lovelace" [ref=e12]\n'
        '- link "Ada Lovelace Award" [ref=e20]\n'
    )


class _Stdin:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    async def drain(self) -> None:
        return None


def test_ndjson_framing_skips_notifications_and_content_length_lines():
    async def run() -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(
            b"Content-Length: 999\r\n"
            b'{"jsonrpc":"2.0","method":"notifications/message","params":{"data":"hi"}}\n'
            b'{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",'
            b'"capabilities":{},"serverInfo":{"name":"playwright","version":"0.0.84"}}}\n'
            b'{"jsonrpc":"2.0","method":"notifications/tools/list_changed"}\n'
            b'{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"browser_navigate",'
            b'"description":"go","inputSchema":{"type":"object","properties":{}}}]}}\n'
        )
        reader.feed_eof()
        client = PlaywrightMCPClient()
        stdin = _Stdin()
        client.process = SimpleNamespace(stdin=stdin, stdout=reader, stderr=None)
        await client._initialize()
        raw = b"".join(stdin.chunks)
        assert b"Content-Length" not in raw
        assert b"content-length" not in raw.lower()
        lines = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
        assert lines[0]["method"] == "initialize"
        assert lines[0]["id"] == 1
        assert lines[1] == {"jsonrpc": "2.0", "method": "notifications/initialized"}
        assert "id" not in lines[1]
        assert lines[2]["method"] == "tools/list"
        assert client.tools[0]["name"] == "browser_navigate"

    asyncio.run(run())
    note = encode_ndjson({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.endswith(b"\n")
    assert b"Content-Length" not in note


def test_navigate_and_find_count_as_snapshot_tokens():
    navigate = _navigate_page()
    find = _find_page()
    assert "snapshot" not in navigate.lower()[:100]
    assert "snapshot" not in find.lower()
    assert snapshot_tokens_for("browser_navigate", navigate) == estimate_tokens(navigate)
    assert snapshot_tokens_for("browser_find", find) == estimate_tokens(find)
    assert snapshot_tokens_for("browser_navigate_back", "landed") == estimate_tokens("landed")

    late_action = ("x" * 120) + '\n### Snapshot\n- button "Go" [ref=e1]\n'
    assert "snapshot" not in late_action.lower()[:100]
    assert snapshot_tokens_for("browser_click", late_action) == estimate_tokens(late_action)
    assert snapshot_tokens_for("browser_snapshot", '- button "Go" [ref=e1]\n') > 0
    assert snapshot_tokens_for("browser_console_messages", "No console messages.") == 0


def test_history_and_snapshot_size_are_capped_for_the_model():
    messages: list[dict] = [{"role": "user", "content": "TASK-KEEP"}]
    for index in range(8):
        messages.append({"role": "assistant", "content": [{"type": "text", "text": f"a{index}"}]})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"t{index}",
                        "content": f"r{index}" + ("z" * 9000),
                    }
                ],
            }
        )
    capped = cap_messages_for_model(messages)
    blob = json.dumps(capped)
    assert capped[0]["content"] == "TASK-KEEP"
    assert len(capped) == 1 + 12
    assert "a0" not in blob
    assert "a1" not in blob
    assert "a2" in blob
    assert "a7" in blob
    last = capped[-1]["content"][0]["content"]
    assert len(last) <= MAX_SNAPSHOT_CHARS
    assert last.endswith("[snapshot truncated]")
    assert len(messages[-1]["content"][0]["content"]) > MAX_SNAPSHOT_CHARS


def test_run_saves_the_full_page_and_caps_what_the_model_sees(tmp_path: Path):
    navigate = _navigate_page()
    find = _find_page()
    responses = [
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "browser_navigate",
                    "input": {"url": "https://en.wikipedia.org/wiki/Main_Page"},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 4},
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "t2",
                    "name": "browser_find",
                    "input": {"text": "Ada"},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 12, "output_tokens": 4},
        },
        {
            "content": [{"type": "text", "text": "TASK_COMPLETE"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 8, "output_tokens": 3},
        },
    ]

    class FakeModel:
        def __init__(self) -> None:
            self.seen: list = []
            self._responses = list(responses)

        async def create_message(self, messages, tools, system=None, max_tokens=4096):
            del tools, system, max_tokens
            self.seen.append(messages)
            return self._responses.pop(0), 2.0

    class FakeMCP:
        def __init__(self) -> None:
            self._results = [navigate, find]

        def tools_for_claude(self):
            return [{"name": "browser_navigate", "description": "go", "input_schema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            del name, arguments
            return self._results.pop(0), 5.0

    model = FakeModel()
    harness = BenchmarkHarness(api_key="local-test", runs_dir=tmp_path / "runs")
    harness.snapshot_dir = harness.runs_dir / "run42" / "snapshots"
    harness.anthropic = model
    harness.mcp_client = FakeMCP()

    result = asyncio.run(
        harness.run_task(
            task_id="wv_wikipedia_search",
            task_description="Search Wikipedia for Ada Lovelace",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
        )
    )

    assert result.total_snapshot_tokens == estimate_tokens(navigate) + estimate_tokens(find)
    assert result.steps[0].tool_name == "browser_navigate"
    assert result.steps[0].snapshot_tokens == estimate_tokens(navigate)
    assert result.steps[1].tool_name == "browser_find"
    assert result.steps[1].snapshot_tokens == estimate_tokens(find)
    assert "[snapshot truncated]" in json.dumps(model.seen[1])
    assert "e499" not in json.dumps(model.seen[1])

    saved = sorted(harness.snapshot_dir.glob("*.json"))
    assert len(saved) == 2
    first = json.loads(saved[0].read_text(encoding="utf-8"))
    second = json.loads(saved[1].read_text(encoding="utf-8"))
    assert "e499" in first["snapshot_text"]
    assert first["model_tool_name"] == "browser_find"
    assert first["url"] == "https://en.wikipedia.org/wiki/Main_Page"
    assert first["source"] == "run"
    assert second["model_tool_name"] is None
    assert "[ref=e12]" in second["snapshot_text"]
    assert extract_page_snapshot(navigate) == first["snapshot_text"]

    observation = parse_aria_snapshot_to_observation(
        first["snapshot_text"],
        url=first["url"],
        title=first["title"],
    )
    assert any(control.ref == "e4" for control in observation.controls)

    run_file = harness.save_result(result, "run42")
    loaded = load_snapshots_from_run(run_file)
    assert len(loaded) == 2
    assert all(item.snapshot_text.strip() for item in loaded)
    assert loaded[0].model_tool_name == "browser_find"


def test_prior_spend_is_the_recorded_m0_total():
    usd = estimate_usd(PRIOR_INPUT_TOKENS, PRIOR_OUTPUT_TOKENS)
    assert PRIOR_INPUT_TOKENS == 3_200_000
    assert PRIOR_OUTPUT_TOKENS == 3_000
    assert usd == pytest.approx(9.645)
    assert 9 < usd < 11

    data = json.loads(default_spend_path().read_text(encoding="utf-8"))
    assert data["tasks"] == []
    assert data["model"] == "claude-sonnet-5-5"
    assert "opus" not in json.dumps(data).lower()
    assert data["prior"]["input_tokens"] == 3_200_000
    assert data["prior"]["output_tokens"] == 3000
    assert data["prior"]["usd"] == pytest.approx(9.645)
    assert data["recorded_extra_usd"] == 0
    assert data["running_total_usd"] == pytest.approx(9.645)
    assert "4/5" in data["prior"]["note"]
    assert "94.8" in data["prior"]["note"]

    ledger = SpendLedger.load()
    assert ledger.tasks == []
    assert ledger.recorded_extra_usd == 0
    assert ledger.running_total_usd == pytest.approx(9.645)
    assert ledger.allows_another_task()


def test_a_temp_ledger_can_round_trip_an_extra_total(tmp_path: Path):
    path = tmp_path / "boxed.json"
    ledger = SpendLedger.seed(path)
    ledger.recorded_extra_usd = 3.267192
    ledger.recompute()
    ledger.save()
    loaded = SpendLedger.load(path)
    assert loaded.running_total_usd == pytest.approx(12.912192)
    assert loaded.recorded_extra_usd == pytest.approx(3.267192)


def test_a_missing_ledger_is_not_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    missing = tmp_path / "absent.json"
    monkeypatch.setenv("CU_SPEND_LEDGER", str(missing))
    with pytest.raises(LedgerMissing) as caught:
        SpendLedger.load()
    assert not missing.exists()
    assert "invent a starting total" in str(caught.value)
    assert str(missing) in str(caught.value)


def test_running_total_updates_and_stops_before_the_next_task(tmp_path: Path):
    path = tmp_path / "spend.json"
    ledger = SpendLedger.seed(path)
    usd = ledger.record_task(run_id="r", task_id="small", input_tokens=1000, output_tokens=100)
    assert usd == pytest.approx(0.0045)
    assert ledger.running_total_usd == pytest.approx(9.6495)
    ledger.save()
    assert SpendLedger.load(path).running_total_usd == pytest.approx(9.6495)

    class FakeHarness:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def run_task(self, task_id, task_description, start_url, expected_answer=None, judge_prompt=None):
            del task_description, start_url, expected_answer, judge_prompt
            self.calls.append(task_id)
            if task_id != "first":
                raise AssertionError(task_id)
            return _result("first", input_tokens=11_000_000, output_tokens=0)

        def save_result(self, result, run_id):
            del result, run_id
            return path

    stop_ledger = SpendLedger.seed(tmp_path / "stop.json")
    fake = FakeHarness()
    tasks = [
        {"id": "first", "description": "one", "start_url": "https://example.com"},
        {"id": "second", "description": "two", "start_url": "https://example.com"},
    ]
    with pytest.raises(BudgetExceeded) as caught:
        asyncio.run(execute_benchmark_tasks(fake, tasks, stop_ledger, "run1"))
    assert fake.calls == ["first"]
    assert [item.task_id for item in caught.value.results] == ["first"]
    saved = SpendLedger.load(tmp_path / "stop.json")
    assert saved.aborted is True
    assert saved.running_total_usd > 40
    assert [item["task_id"] for item in saved.tasks] == ["first"]
    assert saved.prior["label"] == "M0 measurement already spent"


def test_over_budget_does_not_start_the_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "spend.json"
    ledger = SpendLedger.seed(path)
    ledger.record_task(run_id="r", task_id="already", input_tokens=11_000_000, output_tokens=0)
    ledger.save()

    def start(self):
        raise AssertionError("browser started")

    monkeypatch.setattr(PlaywrightMCPClient, "start", start)
    with pytest.raises(BudgetExceeded):
        asyncio.run(
            run_benchmark(
                [{"id": "next", "description": "d", "start_url": "https://example.com"}],
                model=DEFAULT_MODEL,
                api_key="local-test",
                spend_path=path,
                runs_dir=tmp_path / "runs",
            )
        )


def test_opus_and_retired_sonnet_are_refused_before_http(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    called = {"http": 0}

    def urlopen(*args, **kwargs):
        del args, kwargs
        called["http"] += 1
        raise AssertionError("http")

    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    with pytest.raises(ModelNotAllowed):
        AnthropicClient("local-test", model="claude-opus-4-6")
    with pytest.raises(ModelNotAllowed, match="retired"):
        assert_allowed_model("claude-sonnet-4-20250514")
    with pytest.raises(ModelNotAllowed):
        assert_allowed_model("claude-sonnet-4-6")

    client = AnthropicClient("local-test")
    client.model = "claude-opus-4-7"
    with pytest.raises(ModelNotAllowed):
        asyncio.run(client.create_message([{"role": "user", "content": "hi"}], []))

    judge = llm_judge("task", "answer", {}, "done", api_key="local-test", model="claude-opus-4-6")
    assert judge.success is False
    assert "Opus" in judge.reason
    assert called["http"] == 0

    def start(self):
        raise AssertionError("browser started")

    monkeypatch.setattr(PlaywrightMCPClient, "start", start)
    with pytest.raises(ModelNotAllowed):
        asyncio.run(
            run_benchmark(
                [{"id": "x", "description": "y", "start_url": "https://example.com"}],
                model="claude-opus-4-6",
                spend_path=tmp_path / "spend.json",
                runs_dir=tmp_path / "runs",
            )
        )
    assert not (tmp_path / "spend.json").exists()


def test_default_model_is_claude_sonnet_5_5():
    assert DEFAULT_MODEL == "claude-sonnet-5-5"
    assert build_parser().get_default("model") == "claude-sonnet-5-5"
    assert "20250514" not in DEFAULT_MODEL
    assert DEFAULT_MODEL != "claude-sonnet-4-6"


def test_handmade_figure_stays_the_five_file_set():
    assert "40%" in HANDMADE_SNAPSHOT_NOTE
    assert "50%" in HANDMADE_SNAPSHOT_NOTE
    assert "hand-made" in HANDMADE_SNAPSHOT_NOTE
    report = Path(__file__).parent.joinpath("runs", "shortcut_replay_output.md").read_text(encoding="utf-8")
    assert "40%" in report
    assert "50%" in report
    assert "hand-made" in report
    assert len(list(Path(__file__).parent.joinpath("snapshots").glob("*.json"))) == 5
