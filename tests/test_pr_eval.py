"""Synthetic request/ledger tests. No real ledger, browser, API or task rows."""

from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import types
from decimal import Decimal

import pytest

from tools import pr_eval as runner
from bench.openai_client import OpenAIClient, responses_payload
from bench.openai_spend import price_usd

MESSAGES = [{"role": "user", "content": "Read the synthetic page"}]
TOOLS = [{"name": "run_script", "description": "Synthetic tool",
          "input_schema": {"type": "object", "properties": {
              "checks": {"type": "array", "items": {"type": "object"}}}}}]
USAGE = {
    "input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
    "input_tokens_details": {
        "cached_tokens": 10, "cache_write_tokens": 40,
        "cache_write_tokens_details": {"ttl_30m_tokens": 15, "ttl_12h_tokens": 25},
    },
    "output_tokens_details": {"reasoning_tokens": 5},
}


def reply(usage=USAGE):
    return json.dumps({"output": [{"type": "message", "content": [
        {"type": "output_text", "text": "synthetic"}]}], "usage": usage})


def payload(model=runner.MODEL):
    return responses_payload(model, MESSAGES, TOOLS, "Synthetic system", 4096, "medium")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline runner tests attempted a network transport")

    monkeypatch.setattr(runner.client_module, "_post_openai", forbidden)
    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    for key in list(os.environ):
        if key in runner.FLAG_CHOICES or key.startswith("CU_SF_") or "DECISIONS" in key:
            monkeypatch.delenv(key)
    monkeypatch.delenv("CU_OPENAI_SPEND_LEDGER", raising=False)


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RECONCILED_TOTAL", Decimal("0.100000"))
    monkeypatch.setattr(runner, "RECONCILED_EXTRA", Decimal("0.010000"))
    path = tmp_path / "openai-spend-20261117.json"
    data = {
        "provider": "openai", "project_budget_usd": 15, "per_run_budget_usd": 5,
        "recorded_extra_usd": 0.010000, "running_total_usd": 0.100000,
        "aborted": False, "abort_reason": None,
        # Historical price/record data intentionally differs from today's rates.
        "prices_usd_per_mtok": {"historical": {"input": 99}},
        "provenance": {"prior_import": "synthetic reconciliation"},
        "tasks": [{"run_id": "historic", "kind": "decisions", "model": "gpt-6-luna",
                   "usd": 0.090000, "unknown_historical_field": "retain"}],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(runner, "canonical_ledger", lambda: path)
    return path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def budget(path, **kwargs):
    result = runner.Budget(path, "synthetic-" + runner.uuid4().hex, **kwargs)
    result.task_id = "dev_synthetic"
    return result


def invoke(transport, model=runner.MODEL, **kwargs):
    client = OpenAIClient("offline-placeholder", model, "medium", transport=transport)
    return asyncio.run(client.create_message(MESSAGES, TOOLS, system="Synthetic system", **kwargs))


def test_reserve_is_durable_before_dispatch_settles_once_and_keeps_history(ledger):
    before = load(ledger)
    guard = budget(ledger)
    original = OpenAIClient.create_message

    def fake(url, headers, body):
        reserved = load(ledger)
        assert len(reserved["tasks"]) == 1
        call = reserved["pr_eval_calls"][-1]
        assert call["status"] == "reserved"
        assert Decimal(str(reserved["recorded_extra_usd"])) == (
            Decimal(str(before["recorded_extra_usd"])) + Decimal(str(call["reserved_usd"]))
        )
        with pytest.raises(runner.Refused, match="locked"):
            with runner.exclusive_writer(ledger):
                pytest.fail("Released whole-run lock during dispatch")
        assert body["max_output_tokens"] == 4096
        assert body["tools"][0]["parameters"] == TOOLS[0]["input_schema"]
        return reply()

    with guard.hold(), runner.budgeted_client(guard, runner.frozen_flags()):
        body, _ = invoke(fake, tool_choice="required")
        assert body["usage"]["cache_write_12h_tokens"] == 25
        with pytest.raises(runner.Refused, match="already settled"):
            guard.settle(guard.calls[0], body["usage"])
    assert OpenAIClient.create_message is original
    after = load(ledger)
    assert after["tasks"][0] == before["tasks"][0]
    assert after["prices_usd_per_mtok"] == before["prices_usd_per_mtok"]
    assert after["provenance"] == before["provenance"]
    assert after["recorded_extra_usd"] == before["recorded_extra_usd"]
    assert len(after["tasks"]) == 2
    assert after["tasks"][-1]["call_id"] == guard.calls[0]["call_id"]
    actual = price_usd(runner.MODEL, **body["usage"])
    assert after["tasks"][-1]["usd"] == actual
    assert Decimal(str(after["running_total_usd"])) == runner.RECONCILED_TOTAL + Decimal(str(actual))


@pytest.mark.parametrize("model", [runner.MODEL, "gpt-6-luna"])
def test_bound_uses_utf8_bytes_framing_worst_cache_and_long_rates(model):
    body = payload(model)
    body["instructions"] = "日本語" * 100
    bound = runner.request_bound(body)
    assert bound["serialized_bytes"] == len(json.dumps(body).encode("utf-8"))
    assert bound["input_tokens"] == bound["serialized_bytes"] + 4096 + 256 * 2
    expected = (
        Decimal(bound["input_rate"]) * bound["input_tokens"]
        + Decimal(bound["output_rate"]) * 4096
    ) / 1_000_000
    assert Decimal(str(bound["usd"])) >= expected
    assert Decimal(str(bound["usd"])) - expected < runner.QUANTUM
    assert bound["input_rate"] == ("0.50" if model == "gpt-6-luna" else "10")
    assert bound["output_rate"] == ("0.75" if model == "gpt-6-luna" else "15.0")


@pytest.mark.parametrize("case", ["timeout", "missing", "unknown", "fraction", "null", "total",
                                  "cache", "negative", "bool", "malformed", "source_error"])
def test_failed_or_unknown_usage_retains_reservation_and_stops(ledger, case):
    usage = copy.deepcopy(USAGE)
    if case == "missing":
        usage = {}
    elif case == "unknown":
        usage["input_tokens_details"]["audio_tokens"] = 1
    elif case == "fraction":
        usage["input_tokens"] = 100.5
    elif case == "null":
        usage["input_tokens_details"] = None
    elif case == "total":
        usage["total_tokens"] = 999
    elif case == "cache":
        usage["input_tokens_details"]["cache_write_tokens"] = 99
    elif case == "negative":
        usage["output_tokens"] = -1
    elif case == "bool":
        usage["input_tokens"] = True
    sent = []

    def fake(*args):
        sent.append(1)
        if case == "timeout":
            raise TimeoutError("SECRET-SENTINEL must not leak")
        if case == "malformed":
            return "{"
        if case == "source_error":
            return json.dumps({"error": "SECRET-SENTINEL", "usage": usage})
        return reply(usage)

    guard = budget(ledger)
    with guard.hold(), runner.budgeted_client(guard, runner.frozen_flags()):
        with pytest.raises(runner.Refused) as caught:
            invoke(fake)
        assert "SECRET-SENTINEL" not in str(caught.value)
        with pytest.raises(runner.Refused):
            invoke(fake)
    assert len(sent) == 1
    saved = load(ledger)
    assert len(saved["tasks"]) == 1
    assert saved["aborted"]
    assert saved["pr_eval_calls"][0]["status"] == "unresolved"
    assert saved["running_total_usd"] > float(runner.RECONCILED_TOTAL)
    with pytest.raises(runner.Refused, match="unresolved"):
        with budget(ledger).hold():
            pass


@pytest.mark.parametrize("axis", ["evaluation", "run", "project"])
def test_cap_refuses_before_transport(ledger, axis, monkeypatch):
    data = load(ledger)
    cap = Decimal("0.000001") if axis == "evaluation" else Decimal("5")
    if axis == "run":
        data["per_run_budget_usd"] = 0.000001
    if axis == "project":
        # Move only the synthetic evaluation origin to isolate the hard $15
        # admission limit; today's real $1.50 evaluation ceiling is stricter.
        monkeypatch.setattr(runner, "RECONCILED_TOTAL", Decimal("14"))
        data["recorded_extra_usd"] += 14.899999
        data["running_total_usd"] = 14.999999
    ledger.write_text(json.dumps(data), encoding="utf-8")
    before = ledger.read_bytes()
    guard = budget(ledger, evaluation_cap=cap)
    with guard.hold(), runner.budgeted_client(guard, runner.frozen_flags()):
        with pytest.raises(runner.Refused, match="reservation"):
            invoke(lambda *a: pytest.fail("cap admitted a request"))
    assert ledger.read_bytes() == before


def test_default_evaluation_cap_does_not_reset_between_runs(ledger):
    data = load(ledger)
    data["recorded_extra_usd"] += 1.5
    data["running_total_usd"] = 1.600000
    ledger.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(runner.Refused, match="cap"):
        with budget(ledger).hold():
            pass
    for bad in ("5.000001", "0", "-1", "NaN", "Infinity"):
        with pytest.raises(runner.Refused):
            budget(ledger, evaluation_cap=bad)


def test_missing_fork_stale_corrupt_and_unresolved_ledgers_refused(ledger):
    original = load(ledger)
    for extra, total in [(1.330861, 12.036672), (1.330861, 14.579971)]:
        data = copy.deepcopy(original)
        data.update(recorded_extra_usd=extra, running_total_usd=total)
        ledger.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(runner.Refused):
            with budget(ledger).hold():
                pass
    data = copy.deepcopy(original)
    data["pr_eval_calls"] = [{"status": "reserved"}]
    ledger.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(runner.Refused, match="unresolved"):
        with budget(ledger).hold():
            pass
    other = ledger.with_name("fork.json")
    other.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(runner.Refused, match="canonical"):
        with budget(other).hold():
            pass
    ledger.unlink()
    with pytest.raises(runner.Refused, match="no zero seed"):
        with budget(ledger).hold():
            pass
    assert not ledger.exists()


@pytest.mark.parametrize("mutate", [
    lambda body: body.update(service_tier="fast"),
    lambda body: body.update(previous_response_id="not-bounded"),
    lambda body: body.update(input=[{"role": "user", "content": [{"type": "input_image"}]}]),
    lambda body: body.update(tools=[{"type": "web_search"}]),
    lambda body: body.update(max_output_tokens=4097),
    lambda body: body.update(reasoning={"effort": "high"}),
    lambda body: body.pop("instructions"),
])
def test_unsupported_request_bodies_fail_closed(mutate):
    body = payload()
    mutate(body)
    with pytest.raises(runner.Refused):
        runner.request_bound(body)


@pytest.mark.parametrize("content", [None, [None], [{"type": "image", "source": {}}],
                                     [{"type": "tool_result", "tool_use_id": "x",
                                       "content": [{"type": "image"}]}]])
def test_source_converter_cannot_silently_drop_unsupported_content(ledger, content):
    client = OpenAIClient("placeholder", runner.MODEL, "medium",
                          transport=lambda *a: pytest.fail("unsupported content was dispatched"))
    before = ledger.read_bytes()
    with budget(ledger).hold() as guard, runner.budgeted_client(guard, runner.frozen_flags()):
        with pytest.raises(runner.Refused):
            asyncio.run(client.create_message([{"role": "user", "content": content}], TOOLS))
    assert ledger.read_bytes() == before


@pytest.mark.parametrize("axis", ["input", "output"])
def test_bound_overrun_records_actual_even_over_cap_then_halts(ledger, axis):
    guard = budget(ledger)
    huge = {"input_tokens": 100_000_000 if axis == "input" else 1,
            "output_tokens": 0 if axis == "input" else 20_000_000}
    with guard.hold(), runner.budgeted_client(guard, runner.frozen_flags()):
        with pytest.raises(runner.Refused, match="exceeded reservation"):
            invoke(lambda *a: reply(huge))
    saved = load(ledger)
    assert saved["aborted"]
    assert saved["pr_eval_calls"][0]["status"] == "overrun"
    assert saved["recorded_extra_usd"] == float(runner.RECONCILED_EXTRA)
    assert saved["tasks"][-1]["usd"] == price_usd(runner.MODEL, **huge)
    # Accounting must not lie by clamping the already-returned charge to $20.
    assert saved["running_total_usd"] > 20


def test_reservation_save_failure_never_dispatches(ledger, monkeypatch):
    guard = budget(ledger)
    with guard.hold(), runner.budgeted_client(guard, runner.frozen_flags()):
        monkeypatch.setattr(runner, "atomic_json", lambda *a: (_ for _ in ()).throw(OSError()))
        with pytest.raises((runner.Refused, OSError)):
            invoke(lambda *a: pytest.fail("unpersisted reservation dispatched"))
    assert len(load(ledger)["tasks"]) == 1


def test_settlement_save_failure_keeps_disk_reservation(ledger, monkeypatch):
    real_save = runner.atomic_json
    saves = 0

    def save(path, data):
        nonlocal saves
        saves += 1
        if saves > 1:
            raise OSError("synthetic disk failure")
        return real_save(path, data)

    guard = budget(ledger)
    with guard.hold(), runner.budgeted_client(guard, runner.frozen_flags()):
        monkeypatch.setattr(runner, "atomic_json", save)
        with pytest.raises((runner.Refused, OSError)):
            invoke(lambda *a: reply())
    saved = load(ledger)
    assert len(saved["tasks"]) == 1
    assert saved["pr_eval_calls"][0]["status"] == "reserved"
    assert saved["recorded_extra_usd"] > float(runner.RECONCILED_EXTRA)
    assert not any("actual_usd" in call for call in guard.calls)


def test_detects_nonparticipating_writer_without_overwrite(ledger):
    guard = budget(ledger)
    with guard.hold():
        changed = ledger.read_text(encoding="utf-8") + " "
        ledger.write_text(changed, encoding="utf-8")
        with pytest.raises(runner.Refused, match="outside"):
            guard.reserve(runner.request_bound(payload()), runner.MODEL)
    assert ledger.read_text(encoding="utf-8") == changed


def test_os_lock_blocks_other_process_and_is_released_after_owner_killed(ledger):
    # Pipe handshake, not timing/sleeps; no browser or network. Tests both
    # lock contention and automatic release when the owner is terminated.
    code = (
        "import sys\nfrom pathlib import Path\n"
        "from tools.pr_eval import exclusive_writer, Refused\n"
        "try:\n"
        " with exclusive_writer(Path(sys.argv[1])):\n"
        "  print('locked', flush=True)\n"
        "  sys.stdin.readline()\n"
        "except Refused:\n"
        " print('refused', flush=True)\n"
    )
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    with runner.exclusive_writer(ledger):
        check = subprocess.run([sys.executable, "-c", code, str(ledger)], input="\n",
                               capture_output=True, text=True, env=env, timeout=10)
        assert check.returncode == 0, check.stderr
        assert check.stdout.strip() == "refused"
    child = subprocess.Popen([sys.executable, "-c", code, str(ledger)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env)
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(runner.Refused, match="locked"):
            with runner.exclusive_writer(ledger):
                pass
    finally:
        child.kill()
        child.communicate(timeout=10)
    with runner.exclusive_writer(ledger):
        pass
    assert ledger.with_suffix(".json.pr-eval.lock").exists()


def test_cancellation_waits_for_transport_before_unlock_and_settles(ledger):
    entered, release = threading.Event(), threading.Event()

    def fake(*args):
        entered.set()
        assert release.wait(5)
        return reply()

    async def run():
        with budget(ledger).hold() as guard, runner.budgeted_client(guard, runner.frozen_flags()):
            client = OpenAIClient("placeholder", runner.MODEL, "medium", transport=fake)
            call = asyncio.create_task(client.create_message(MESSAGES, TOOLS))
            assert await asyncio.to_thread(entered.wait, 5)
            call.cancel()
            with pytest.raises(runner.Refused, match="locked"):
                with runner.exclusive_writer(ledger):
                    pass
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await call
            assert guard.calls[0]["status"] == "settled"
    asyncio.run(run())
    assert len(load(ledger)["tasks"]) == 2


def test_flags_frozen_and_only_medium_selected_model(ledger, monkeypatch):
    guard = budget(ledger)
    flags = runner.frozen_flags()
    with guard.hold(), runner.budgeted_client(guard, flags):
        monkeypatch.setenv("CU_BU_MODE", "ultrafast")
        with pytest.raises(runner.Refused, match="flags changed"):
            invoke(lambda *a: pytest.fail("flag drift dispatched"))
    guard = budget(ledger)
    with guard.hold(), runner.budgeted_client(guard, runner.frozen_flags()):
        with pytest.raises(runner.Refused, match="selected model"):
            invoke(lambda *a: pytest.fail("wrong model dispatched"), model="gpt-6-luna")


def test_older_client_signature_without_tool_choice_is_respected(ledger, monkeypatch):
    original = OpenAIClient.create_message

    async def previous(self, messages, tools, system=None, max_tokens=4096):
        return await original(self, messages, tools, system=system, max_tokens=max_tokens)

    monkeypatch.setattr(OpenAIClient, "create_message", previous)
    with budget(ledger).hold() as guard, runner.budgeted_client(guard, runner.frozen_flags()):
        body, _ = invoke(lambda *a: reply())
        assert body["usage"]["input_tokens"] == 100
    assert OpenAIClient.create_message is previous
    assert len(load(ledger)["tasks"]) == 2


def test_inherited_decisions_or_unknown_flags_refuse_without_printing_values(monkeypatch):
    monkeypatch.setenv("CU_DECISIONS", "SECRET-SENTINEL")
    with pytest.raises(runner.Refused) as caught:
        runner.frozen_flags()
    assert "SECRET-SENTINEL" not in str(caught.value)
    monkeypatch.delenv("CU_DECISIONS")
    monkeypatch.setenv("CU_SF_UNREVIEWED", "SECRET-SENTINEL")
    with pytest.raises(runner.Refused):
        runner.frozen_flags()


def test_only_present_dev_splits_and_positive_smoke_limit(monkeypatch):
    selected = []

    def tasks(split):
        selected.append(split)
        if split == "dev5title":
            raise ValueError("absent")
        return [{"id": "synthetic-a"}, {"id": "synthetic-b"}]

    monkeypatch.setitem(sys.modules, "bench.tasks", types.SimpleNamespace(tasks_for_split=tasks))
    for split in ("dev3", "dev4form", "dev4spa"):
        assert runner.load_tasks(split, 1) == [{"id": "synthetic-a"}]
    with pytest.raises(runner.Refused, match="absent"):
        runner.load_tasks("dev5title", None)
    with pytest.raises(runner.Refused, match="positive"):
        runner.load_tasks("dev3", 0)
    assert selected == ["dev3", "dev4form", "dev4spa", "dev5title"]


def test_plan_is_offline_and_does_not_access_ledger_or_catalog(monkeypatch, capsys):
    load_tasks = runner.load_tasks
    monkeypatch.setattr(runner, "canonical_ledger", lambda: pytest.fail("plan read ledger"))
    monkeypatch.setattr(runner, "load_tasks", lambda *a: pytest.fail("plan read catalog"))
    monkeypatch.setenv("OPENAI_API_KEY", "SECRET-SENTINEL")
    assert runner.main(["--split", "dev4spa", "--task-limit", "1"]) == 0
    output = capsys.readouterr().out
    assert "SECRET-SENTINEL" not in output
    assert json.loads(output)["execute"] is False
    for split in ("heldout3", "heldout4", "val3", "heldout2", "dev"):
        with pytest.raises(SystemExit):
            runner.main(["--split", split])
        with pytest.raises(runner.Refused, match="DEV"):
            load_tasks(split, None)


def test_canonical_override_is_not_a_fork(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("CU_OPENAI_SPEND_LEDGER", str(tmp_path / "fork.json"))
    with pytest.raises(runner.Refused, match="canonical"):
        runner.canonical_ledger()


def test_absolute_entrypoint_uses_pythonpath_from_another_working_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root))
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "pr_eval.py"), "--split", "dev4form", "--task-limit", "1"],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["execute"] is False
    assert not (tmp_path / "bench").exists()


def test_sequential_driver_preserves_grade_reports_calls_and_never_double_records(
    ledger, monkeypatch, tmp_path,
):
    synthetic = [{"id": "dev_synthetic_a"}, {"id": "dev_synthetic_b"}]
    monkeypatch.setattr(runner, "load_tasks", lambda split, limit: synthetic[:limit])
    monkeypatch.setattr(runner, "provenance", lambda: {"revision": "synthetic-sha"})
    monkeypatch.setenv("OPENAI_API_KEY", "SECRET-SENTINEL")
    seen = []
    grade = {"success": False, "success_reason": "original grade", "end_state": "PASS",
             "page_answer_success": False, "self_checks": [{"verdict": "PASS"}],
             "steps": 2, "script_steps": 3, "wall_ms": 17, "usd": 99}

    async def fake_arm(arm, task, **kwargs):
        assert arm == "script_first"
        assert kwargs["script_cache"] is None
        assert (kwargs["provider"], kwargs["model"], kwargs["effort"]) == (
            "openai", runner.MODEL, "medium",
        )
        seen.append(task["id"])
        client = OpenAIClient("placeholder", runner.MODEL, "medium", transport=lambda *a: reply())
        for _ in range(2):
            await client.create_message(MESSAGES, TOOLS)
        return dict(grade, task_id=task["id"], arm=arm)

    # No real bench.probe import, task definitions or browser in this test.
    monkeypatch.setitem(sys.modules, "bench.probe", types.SimpleNamespace(run_claude_arm=fake_arm))
    out = tmp_path / "result"
    path = asyncio.run(runner.evaluate(split="dev3", task_limit=2, output=out))
    manifest = load(path)
    assert manifest["status"] == "completed"
    rows = [json.loads(line) for line in (out / "rows.jsonl").read_text().splitlines()]
    assert seen == ["dev_synthetic_a", "dev_synthetic_b"]
    assert len(load(ledger)["tasks"]) == 5  # One historical + four call charges, no outer task charges.
    assert len({c["call_id"] for c in manifest["calls"]}) == 4
    for row in rows:
        for key, value in grade.items():
            if key != "usd":
                assert row[key] == value
        assert row["harness_usd"] == 99
        assert row["usd"] < 0.01
        assert len(row["call_ids"]) == 2
        assert row["budget_hook_ms"] > 0
        assert "budget-instrumented" in row["wall_label"]
    assert "SECRET-SENTINEL" not in path.read_text() + (out / "rows.jsonl").read_text()


def test_driver_error_row_keeps_reservation_and_does_not_start_next_task(
    ledger, monkeypatch, tmp_path,
):
    monkeypatch.setattr(runner, "load_tasks", lambda *a: [{"id": "dev_a"}, {"id": "dev_b"}])
    monkeypatch.setattr(runner, "provenance", lambda: {"revision": "synthetic-sha"})
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    seen = []

    async def arm(_arm, task, **kwargs):
        seen.append(task["id"])
        client = OpenAIClient("placeholder", runner.MODEL, "medium",
                              transport=lambda *a: reply(None))
        await client.create_message(MESSAGES, TOOLS)
        pytest.fail("Unknown usage returned to the harness")

    monkeypatch.setitem(sys.modules, "bench.probe", types.SimpleNamespace(run_claude_arm=arm))
    out = tmp_path / "error-result"
    manifest = load(asyncio.run(runner.evaluate(split="dev3", task_limit=None, output=out)))
    rows = [json.loads(line) for line in (out / "rows.jsonl").read_text().splitlines()]
    assert seen == ["dev_a"]
    assert manifest["status"] == "stopped"
    assert len(rows) == 1
    assert rows[0]["success"] is None and rows[0]["grade_available"] is False
    assert rows[0]["usd"] == rows[0]["unresolved_reserved_usd"] > 0
    assert rows[0]["actual_usage_usd"] == 0  # Explicitly separate from retained charge.
    assert Decimal(str(manifest["run_charge_usd"])) == Decimal(str(rows[0]["usd"]))
