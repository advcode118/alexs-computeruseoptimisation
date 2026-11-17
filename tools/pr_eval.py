"""Small, opt-in DEV evaluation runner. Import/help/plan never dispatch a request.

Run against another checkout with its root on PYTHONPATH. Only this process's
OpenAIClient.create_message is hooked; production clients/graders are untouched.
See docs/PR_INTEGRATION_20261116/runner.md for assumptions and parent-only launch.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING
from uuid import uuid4

from bench import openai_client as client_module
from bench.openai_spend import OpenAISpendLedger, PriceUnknown, price_usd, published_rates

MODEL = "gpt-6.1-sol"
SPLITS = ("dev3", "dev4form", "dev4spa", "dev5title")
RECONCILED_TOTAL = Decimal("0")
RECONCILED_EXTRA = Decimal("0")
DEFAULT_EVALUATION_CAP = Decimal("1.50")
PROJECT_CAP = Decimal("15")
RUN_CAP = Decimal("5")
QUANTUM = Decimal("0.000001")
MAX_OUTPUT = 4096
# An assumption, not a tokenizer/provider guarantee: <=1 token per serialized
# UTF-8 byte, plus 4096 framing tokens and 256 per input item/function schema.
FRAMING_BASE = 4096
FRAMING_PER_ITEM = 256
FLAG_CHOICES = {"CU_BU_MODE": ("", "ultrafast")}


class Refused(PriceUnknown):
    """Safe, static error messages; never include request bodies or secrets."""


def money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except Exception:
        raise Refused("Invalid money value") from None
    if not amount.is_finite() or amount < 0:
        raise Refused("Invalid money value")
    return amount


def canonical_ledger() -> Path:
    target = (Path.home() / ".cu-optimisation" / "openai-spend-20261117.json").resolve()
    override = os.environ.get("CU_OPENAI_SPEND_LEDGER", "").strip()
    if override and Path(override).expanduser().resolve() != target:
        raise Refused("Only the canonical OpenAI ledger is allowed")
    return target


def frozen_flags() -> dict:
    flags = {key: os.environ.get(key, "") for key in FLAG_CHOICES}
    if any(value not in FLAG_CHOICES[key] for key, value in flags.items()):
        raise Refused("Unsupported evaluation flag value")
    for key, value in os.environ.items():
        if key.startswith("CU_SF_") and key not in FLAG_CHOICES:
            raise Refused("Unknown script_first flag; review before evaluation")
        if "DECISIONS" in key and value.lower() not in ("", "0", "off", "false"):
            raise Refused("Decisions must be disabled")
    return flags


def check_flags(flags: dict) -> None:
    if frozen_flags() != flags:
        raise Refused("Evaluation flags changed during the run")


@contextmanager
def exclusive_writer(path: Path):
    """Stable sidecar inode; OS releases ownership on process exit. Never unlink."""
    handle = path.with_suffix(path.suffix + ".pr-eval.lock").open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise Refused("Canonical ledger writer is already locked") from None
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise Refused("Canonical ledger writer is already locked") from None
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def atomic_json(path: Path, data: dict) -> bytes:
    encoded = (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return encoded


class Budget:
    """One ledger owner for a whole run. Historical records/prices are retained."""

    def __init__(self, path: Path, run_id: str, evaluation_cap=DEFAULT_EVALUATION_CAP):
        self.path = path
        self.run_id = run_id
        self.cap = money(evaluation_cap)
        if not 0 < self.cap <= RUN_CAP:
            raise Refused("Evaluation cap must be positive and at most $5")
        self.halted = False
        self.calls: list[dict] = []
        self.hook_ms = 0.0
        self.task_id = ""
        self.held = False

    @contextmanager
    def hold(self):
        if self.path.resolve() != canonical_ledger() or not self.path.is_file():
            raise Refused("Existing canonical ledger required; no zero seed")
        with exclusive_writer(self.path):
            original = self.path.read_bytes()
            self.fingerprint = hashlib.sha256(original).hexdigest()
            self.data = json.loads(original)
            data = self.data
            if data.get("provider") != "openai" or not isinstance(data.get("tasks"), list):
                raise Refused("Malformed canonical ledger")
            extra = money(data.get("recorded_extra_usd"))
            total = extra + sum((money(row["usd"]) for row in data["tasks"]), Decimal(0))
            if total != money(data.get("running_total_usd")):
                raise Refused("Ledger arithmetic mismatch; parent reconciliation required")
            if total < RECONCILED_TOTAL or extra < RECONCILED_EXTRA:
                raise Refused("Ledger is below the evaluation origin")
            if data.get("aborted") or any(
                row.get("status") != "settled" for row in data.get("pr_eval_calls", [])
            ):
                raise Refused("Ledger has an abort or unresolved call; parent review required")
            self.ledger = OpenAISpendLedger(
                path=self.path, tasks=copy.deepcopy(data["tasks"]),
                recorded_extra_usd=float(extra), created=True,
            )
            self.ledger.recompute()
            self.opening = total
            # Fixed evaluation origin prevents resetting the $1.50 with a new
            # invocation/model/checkout/flag. Other new spend consumes it too.
            self.ceiling = min(
                PROJECT_CAP, money(data["project_budget_usd"]),
                RECONCILED_TOTAL + self.cap, self.opening + RUN_CAP,
                self.opening + money(data["per_run_budget_usd"]),
            )
            if total >= self.ceiling:
                raise Refused("Evaluation, run, or project cap has been reached")
            self.held = True
            try:
                yield self
            finally:
                self.held = False

    @property
    def total(self) -> Decimal:
        return money(self.ledger.running_total_usd)

    def save(self):
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != self.fingerprint:
            self.halted = True
            raise Refused("Ledger changed outside the exclusive writer")
        # Do not use ledger.save(): it replaces historical price metadata.
        self.data.update(
            tasks=self.ledger.tasks,
            recorded_extra_usd=self.ledger.recorded_extra_usd,
            running_total_usd=self.ledger.running_total_usd,
            aborted=self.ledger.aborted,
            abort_reason=self.ledger.abort_reason,
        )
        encoded = atomic_json(self.path, self.data)
        self.fingerprint = hashlib.sha256(encoded).hexdigest()

    def reserve(self, bound: dict, model: str) -> dict:
        amount = money(bound["usd"])
        if not self.held:
            raise Refused("Whole-run writer lock is not held")
        if self.halted or self.total + amount > self.ceiling:
            self.halted = True
            raise Refused("Next request reservation exceeds the remaining cap")
        call = {
            "run_id": self.run_id, "call_id": uuid4().hex, "task_id": self.task_id,
            "model": model, "effort": "medium", "status": "reserved",
            "bound": bound, "reserved_usd": float(amount),
        }
        self.ledger.recorded_extra_usd = float(money(self.ledger.recorded_extra_usd) + amount)
        self.ledger.recompute()
        self.data.setdefault("pr_eval_calls", []).append(call)
        self.calls.append(call)
        try:
            self.save()  # Durable reserve precedes dispatch.
        except BaseException:
            self.halted = True
            raise
        return call

    def unresolved(self, call: dict):
        self.halted = True
        call["status"] = "unresolved"
        self.ledger.mark_aborted("PR evaluation request unresolved; reservation retained")
        self.save()

    def settle(self, call: dict, usage: dict):
        if call["status"] != "reserved":
            raise Refused("Call was already settled")
        actual = price_usd(call["model"], **usage)
        bound = call["bound"]
        overrun = (
            usage["input_tokens"] > bound["input_tokens"]
            or usage["output_tokens"] > bound["output_tokens"]
            or money(actual) > money(call["reserved_usd"])
        )
        self.ledger.record_task(
            run_id=self.run_id,
            task_id=f"script_first:{self.task_id}:{call['call_id']}",
            model=call["model"], effort="medium", **usage,
        )
        self.ledger.tasks[-1].update(call_id=call["call_id"], eval_task_id=self.task_id)
        self.ledger.recorded_extra_usd = float(
            money(self.ledger.recorded_extra_usd) - money(call["reserved_usd"])
        )
        self.ledger.recompute()
        overrun = overrun or self.total > self.ceiling
        call.update(status="overrun" if overrun else "settled", actual_usd=actual, usage=usage)
        if overrun:
            self.halted = True
            self.ledger.mark_aborted("PR evaluation reservation bound exceeded")
        try:
            self.save()  # One atomic transition: reserve removed, actual entry added.
        except BaseException:
            # The durable old state is a reservation. Do not advertise settlement
            # in the manifest when its replacement could not be confirmed.
            self.ledger.tasks.pop()
            self.ledger.recorded_extra_usd = float(
                money(self.ledger.recorded_extra_usd) + money(call["reserved_usd"])
            )
            self.ledger.recompute()
            call.update(status="reserved")
            call.pop("actual_usd", None)
            call.pop("usage", None)
            self.halted = True
            raise
        if overrun:
            raise Refused("Returned usage exceeded reservation; actual recorded, run halted")


def request_bound(payload: dict) -> dict:
    allowed = {"model", "instructions", "input", "tools", "max_output_tokens",
               "reasoning", "store", "tool_choice"}
    if set(payload) - allowed or not allowed - {"tool_choice"} <= set(payload):
        raise Refused("Unsupported Responses body fields")
    if (
        payload["model"] not in (MODEL, "gpt-6-luna")
        or payload["reasoning"] != {"effort": "medium"}
        or payload["store"] is not False
        or not isinstance(payload["instructions"], str)
        or payload.get("tool_choice") not in (None, "auto", "required", "none")
    ):
        raise Refused("Unsupported Responses request settings")
    maximum = payload["max_output_tokens"]
    if type(maximum) is not int or not 1 <= maximum <= MAX_OUTPUT:
        raise Refused("Output limit must be an integer from 1 to 4096")
    if not isinstance(payload["input"], list) or not isinstance(payload["tools"], list):
        raise Refused("Only text input and function tools are supported")
    for item in payload["input"]:
        if not isinstance(item, dict):
            raise Refused("Unsupported input item")
        keys = set(item)
        valid = (
            (keys == {"role", "content"} and item["role"] in ("user", "assistant"))
            or (keys == {"type", "call_id", "name", "arguments"} and item["type"] == "function_call")
            or (keys == {"type", "call_id", "output"} and item["type"] == "function_call_output")
        )
        if not valid or not all(isinstance(value, str) for value in item.values()):
            raise Refused("Unsupported input body type or image")
    for tool in payload["tools"]:
        if (
            not isinstance(tool, dict)
            or set(tool) != {"type", "name", "description", "parameters"}
            or tool["type"] != "function"
            or not isinstance(tool["name"], str)
            or not isinstance(tool["description"], str)
            or not isinstance(tool["parameters"], dict)
        ):
            raise Refused("Only plain JSON function schemas are supported")
    try:
        serialized = json.dumps(payload, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise Refused("Request is not plain finite JSON") from None
    incoming = len(serialized) + FRAMING_BASE + FRAMING_PER_ITEM * (
        len(payload["input"]) + len(payload["tools"])
    )
    rates = published_rates(payload["model"])
    # Worst published input class (including 12h writes), long-context factors
    # regardless of actual length; round UP to the ledger's micro-dollar unit.
    in_rate = max(rate for name, rate in rates.items() if name != "output_usd_per_mtok") * 2
    out_rate = rates["output_usd_per_mtok"] * Decimal("1.5")
    usd = ((incoming * in_rate + maximum * out_rate) / 1_000_000).quantize(
        QUANTUM, rounding=ROUND_CEILING,
    )
    return {"usd": float(usd), "input_tokens": incoming, "output_tokens": maximum,
            "serialized_bytes": len(serialized), "input_rate": str(in_rate),
            "output_rate": str(out_rate)}


def strict_usage(raw: dict) -> dict:
    """Validate before the source normalizer can silently default/coerce counts."""
    if not isinstance(raw, dict) or not {"input_tokens", "output_tokens"} <= set(raw):
        raise Refused("Required raw usage counts missing")
    allowed = {
        "input_tokens", "output_tokens", "total_tokens",
        "input_tokens_details", "output_tokens_details",
    }
    if set(raw) - allowed:
        raise Refused("Unknown usage fields")

    def counts(obj, keys):
        if not isinstance(obj, dict) or set(obj) - keys:
            raise Refused("Unknown usage detail fields")
        if any(type(value) is not int or value < 0 for value in obj.values()):
            raise Refused("Usage counts must be nonnegative integers")

    counts({k: raw[k] for k in raw if k.endswith("_tokens")},
           {"input_tokens", "output_tokens", "total_tokens"})
    inputs = raw.get("input_tokens_details", {})
    outputs = raw.get("output_tokens_details", {})
    if not isinstance(inputs, dict):
        raise Refused("Invalid input usage details")
    writes = inputs.get("cache_write_tokens_details", {})
    counts({k: v for k, v in inputs.items() if k != "cache_write_tokens_details"},
           {"cached_tokens", "cache_write_tokens"})
    counts(writes, {"ttl_30m_tokens", "ttl_12h_tokens"})
    counts(outputs, {"reasoning_tokens"})
    if (
        raw.get("total_tokens", raw["input_tokens"] + raw["output_tokens"])
        != raw["input_tokens"] + raw["output_tokens"]
        or outputs.get("reasoning_tokens", 0) > raw["output_tokens"]
    ):
        raise Refused("Inconsistent total or reasoning usage")
    return client_module.normalize_usage(raw)


def validate_messages(messages):
    """Reject source-converter omissions, nested multimodal tool results, images."""
    if not isinstance(messages, list):
        raise Refused("Messages must be a list")
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise Refused("Unsupported message fields")
        role, content = message["role"], message["content"]
        if role not in ("user", "assistant"):
            raise Refused("Unsupported message role")
        if isinstance(content, str):
            continue
        if not isinstance(content, list):
            raise Refused("Unsupported message content")
        for block in content:
            if not isinstance(block, dict):
                raise Refused("Unsupported content block")
            kind = block.get("type")
            if kind == "text":
                valid = set(block) <= {"type", "text"} and isinstance(block.get("text"), str)
            elif kind == "tool_use" and role == "assistant":
                valid = (
                    set(block) == {"type", "id", "name", "input"}
                    and isinstance(block["input"], dict)
                    and isinstance(block["id"], str) and isinstance(block["name"], str)
                )
            elif kind == "tool_result" and role == "user":
                valid = (
                    set(block) <= {"type", "tool_use_id", "content", "is_error"}
                    and isinstance(block.get("tool_use_id"), str)
                    and isinstance(block.get("content"), str)
                )
            else:
                valid = False
            if not valid:
                raise Refused("Unsupported content block or image")


@contextmanager
def budgeted_client(budget: Budget, flags: dict, model=MODEL):
    """Hook only during this run; delegate to the checkout's exact client method."""
    original = client_module.OpenAIClient.create_message
    signature = inspect.signature(original)
    busy = False

    async def create_message(client, *args, **kwargs):
        nonlocal busy
        if busy or budget.halted:
            raise Refused("Concurrent or halted evaluation request refused")
        busy = True
        call = None
        old_transport = client.transport
        started = time.perf_counter()
        try:
            check_flags(flags)
            if client.model != model or client.effort != "medium":
                raise Refused("Only the selected model at medium effort is allowed")
            bound_args = signature.bind(client, *args, **kwargs)
            bound_args.apply_defaults()
            values = dict(bound_args.arguments)
            values.pop("self")
            if set(values) - {"messages", "tools", "system", "max_tokens", "tool_choice"}:
                raise Refused("Unsupported client signature")
            validate_messages(values["messages"])
            if type(values["max_tokens"]) is not int or not 1 <= values["max_tokens"] <= MAX_OUTPUT:
                raise Refused("Output limit must be an integer from 1 to 4096")
            if values["system"] is not None and not isinstance(values["system"], str):
                raise Refused("System instructions must be text")
            payload = client_module.responses_payload(model=model, effort="medium", **values)
            bound = request_bound(payload)
            reserved_json = json.dumps(payload, allow_nan=False)
            call = budget.reserve(bound, model)
            budget.hook_ms += (time.perf_counter() - started) * 1000
            normalized = None
            sent = False

            def transport(url, headers, actual_payload):
                nonlocal normalized, sent
                if (
                    sent or url != client_module.OPENAI_RESPONSES_URL
                    or json.dumps(actual_payload, allow_nan=False) != reserved_json
                ):
                    raise Refused("Transport differs from the reserved request")
                sent = True
                body = old_transport(url, headers, actual_payload)
                parsed = json.loads(body)
                if not isinstance(parsed, dict):
                    raise Refused("Response must be an object")
                normalized = strict_usage(parsed.get("usage"))
                return body

            client.transport = transport
            pending = asyncio.create_task(original(client, *args, **kwargs))
            cancelled = False
            # Cancellation must not release the whole-run lock while the
            # source client's executor-thread HTTP request remains in flight.
            while not pending.done():
                try:
                    await asyncio.shield(pending)
                except asyncio.CancelledError:
                    cancelled = True
            response, elapsed = pending.result()
            started = time.perf_counter()
            if not sent or normalized is None or response.get("usage") != normalized:
                raise Refused("Source client returned unsupported normalized usage")
            budget.settle(call, normalized)
            budget.hook_ms += (time.perf_counter() - started) * 1000
            if cancelled:
                raise asyncio.CancelledError
            return response, elapsed
        except BaseException as exc:
            budget.halted = True
            if call is not None and call["status"] == "reserved":
                budget.unresolved(call)
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, Refused):
                raise
            raise Refused("Request/accounting failed; any persisted reservation is retained") from None
        finally:
            client.transport = old_transport
            busy = False

    client_module.OpenAIClient.create_message = create_message
    try:
        yield
    finally:
        client_module.OpenAIClient.create_message = original


def load_tasks(split: str, task_limit: int | None) -> list[dict]:
    if split not in SPLITS:
        raise Refused("Only the four named DEV splits are allowed")
    if task_limit is not None and task_limit < 1:
        raise Refused("Task limit must be positive")
    from bench.tasks import tasks_for_split

    try:
        tasks = tasks_for_split(split)
    except ValueError:
        raise Refused("Selected DEV split is absent in this checkout") from None
    if not tasks:
        raise Refused("Selected DEV split is empty")
    return tasks[:task_limit] if task_limit else tasks


def provenance() -> dict:
    import bench

    root = Path(bench.__file__).resolve().parent.parent
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
    ).strip()
    dirty = bool(subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain"], text=True,
    ).strip())
    source_names = ("harness", "probe", "arms", "script_first", "openai_client", "openai_spend")
    sources = {f"bench/{name}.py": hashlib.sha256(path.read_bytes()).hexdigest()
               for name in source_names if (path := root / "bench" / f"{name}.py").is_file()}
    return {"revision": revision, "checkout": str(root), "dirty": dirty, "source_sha256": sources,
            "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


async def evaluate(*, split: str, task_limit: int | None, output: Path,
                   model=MODEL, evaluation_cap=DEFAULT_EVALUATION_CAP) -> Path:
    """Parent-only paid entrypoint. Tests replace tasks/arm and use a temp ledger."""
    if model not in (MODEL, "gpt-6-luna"):
        raise Refused("Unsupported evaluation model")
    flags = frozen_flags()
    from bench.probe import run_claude_arm

    tasks = load_tasks(split, task_limit)
    run_id = "pr-eval-" + uuid4().hex
    budget = Budget(canonical_ledger(), run_id, evaluation_cap)
    with budget.hold():
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise Refused("OPENAI_API_KEY is required for an explicit parent launch")
        output.mkdir(parents=True, exist_ok=False)
        manifest_path = output / "manifest.json"
        manifest = {
            **provenance(), "run_id": run_id, "model": model, "effort": "medium",
            "arm": "script_first", "split": split, "flags": flags, "cache": "cold/disabled",
            "tasks": [task["id"] for task in tasks], "task_limit": task_limit,
            "evaluation_origin_usd": float(RECONCILED_TOTAL),
            "evaluation_cap_usd": float(budget.cap), "admission_ceiling_usd": float(budget.ceiling),
            "opening_usd": float(budget.opening), "status": "running",
            "wall_label": "budget-instrumented harness wall; original final grade excluded",
        }
        atomic_json(manifest_path, manifest)
        try:
            with (output / "rows.jsonl").open("x", encoding="utf-8") as sink, budgeted_client(
                budget, flags, model,
            ):
                for task in tasks:  # Intentionally sequential, one cold task at a time.
                    check_flags(flags)
                    budget.task_id = task["id"]
                    begin, before, hooks = time.perf_counter(), len(budget.calls), budget.hook_ms
                    try:
                        row = await run_claude_arm(
                            "script_first", task, api_key=api_key, headless=True,
                            runs_dir=output / "harness", script_cache=None,
                            provider="openai", model=model, effort="medium",
                        )
                        # Preserve the grade, but refuse to label an environment-
                        # mutated task as a valid matched run.
                        try:
                            check_flags(flags)
                        except Refused:
                            row["configuration_drift"] = True
                            budget.halted = True
                    except Exception:
                        row = {"arm": "script_first", "task_id": task["id"], "success": None,
                               "grade_available": False, "error": "Task interrupted; see call accounting"}
                        budget.halted = True
                    calls = budget.calls[before:]
                    actual = sum((money(c["actual_usd"]) for c in calls if "actual_usd" in c), Decimal(0))
                    unresolved = sum((money(c["reserved_usd"]) for c in calls
                                      if c["status"] in ("reserved", "unresolved")), Decimal(0))
                    row.update(
                        run_id=run_id, revision=manifest["revision"], flags=flags,
                        provider="openai", model=model, effort="medium", split=split, **{"pass": "cold"},
                        harness_usd=row.get("usd"), usd=float(actual + unresolved),
                        actual_usage_usd=float(actual), unresolved_reserved_usd=float(unresolved),
                        call_ids=[c["call_id"] for c in calls],
                        budget_hook_ms=budget.hook_ms - hooks,
                        driver_task_wall_ms=(time.perf_counter() - begin) * 1000,
                        wall_label=manifest["wall_label"],
                    )
                    sink.write(json.dumps(row, allow_nan=False) + "\n")
                    sink.flush()
                    os.fsync(sink.fileno())
                    if budget.halted:
                        break
            manifest["status"] = "stopped" if budget.halted else "completed"
        finally:
            if manifest["status"] == "running":
                manifest["status"] = "interrupted"
            manifest.update(closing_usd=float(budget.total), run_charge_usd=float(budget.total - budget.opening),
                            calls=budget.calls, budget_hook_ms=budget.hook_ms)
            atomic_json(manifest_path, manifest)
    return manifest_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicit parent-only paid launch")
    parser.add_argument("--split", choices=SPLITS, default="dev3")
    parser.add_argument("--task-limit", type=int)
    parser.add_argument("--model", choices=(MODEL, "gpt-6-luna"), default=MODEL)
    parser.add_argument("--evaluation-cap-usd", default=str(DEFAULT_EVALUATION_CAP))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        cap = money(args.evaluation_cap_usd)
        if not 0 < cap <= RUN_CAP or (args.task_limit is not None and args.task_limit < 1):
            raise Refused("Invalid cap or task limit")
        if not args.execute:
            print(json.dumps({
                "execute": False, "split": args.split, "task_limit": args.task_limit,
                "model": args.model, "effort": "medium", "flags": frozen_flags(),
                "evaluation_cap_usd": float(cap),
                "evaluation_origin_usd": float(RECONCILED_TOTAL),
                "note": "No ledger/catalog/network access. Parent reconciliation and launch required.",
            }, indent=2))
            return 0
        destination = args.output or Path("bench/runs") / ("pr_eval_" + uuid4().hex)
        path = asyncio.run(evaluate(
            split=args.split, task_limit=args.task_limit, output=destination,
            model=args.model, evaluation_cap=cap,
        ))
        print(path.resolve())
        return 0 if json.loads(path.read_text(encoding="utf-8"))["status"] == "completed" else 2
    except Exception:
        # Transport exception strings can contain credentials, URLs or bodies.
        print("Evaluation refused or interrupted. Inspect the local manifest/call statuses if created.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
