"""OpenAI probe plan and execution. The Claude probe does not call this.

A single run uses one model on every selected arm and the same task split
as Claude. A sweep uses both models, every accepted effort, and one task.
The plan path does not construct a client.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from bench.arms import ARM_BROWSER_USE, arm_needs_claude
from bench.openai_spend import (
    ALLOWED_OPENAI_MODELS,
    DEFAULT_EFFORT,
    OPENAI_PROJECT_BUDGET_USD,
    OPENAI_RUN_BUDGET_USD,
    OPENAI_SWEEP_BUDGET_USD,
    EffortNotAllowed,
    OpenAIModelNotAllowed,
    OpenAISpendLedger,
    PriceUnknown,
    assert_effort,
    assert_openai_model,
    cap_statement,
    default_openai_spend_path,
    efforts_for,
    probe_command,
    rates_for_report,
    sweep_cell_command,
    sweep_cells,
    sweep_command,
    sweep_task_ids,
)
from bench.tasks import tasks_for_split


def _key_is_set() -> bool:
    import os

    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _tasks(split: str, *, one_task: bool) -> list[dict]:
    from bench.probe import probe_tasks

    catalog = probe_tasks(split)
    if not one_task:
        return catalog
    wanted = set(sweep_task_ids([task["id"] for task in catalog]))
    return [task for task in catalog if task["id"] in wanted]


def _commands(sweep: bool) -> list[str]:
    commands = [
        probe_command("gpt-6.1-sol", DEFAULT_EFFORT),
        probe_command("gpt-6-luna", DEFAULT_EFFORT),
        sweep_command(),
    ]
    if sweep:
        commands.extend(sweep_cell_command(cell["model"], cell["effort"]) for cell in sweep_cells())
    return commands


def plan_openai_probe(
    *,
    arms: tuple[str, ...],
    split: str,
    sweep: bool,
    model: str | None,
    effort: str | None,
    one_task: bool,
    no_model_only: bool,
    warm_replay: bool,
    honest: bool,
) -> dict:
    """The plan only. No browser, no client, no ledger write."""
    if honest:
        raise ValueError("--honest is the Claude comparison. Refusing to combine it with OpenAI.")
    if no_model_only:
        raise ValueError("--no-model-only does not run an OpenAI model. Refusing.")
    if warm_replay:
        raise ValueError("--warm-replay is not part of the OpenAI run. Refusing.")
    request = resolve_openai_request(
        provider="openai",
        model=model or "",
        effort=effort or "",
        sweep=sweep,
        one_task=one_task,
    )
    cells = sweep_cells() if request["sweep"] else ({"model": request["model"], "effort": request["effort"]},)
    models = []
    for cell in cells:
        if cell["model"] not in models:
            models.append(cell["model"])
    tasks = _tasks(split, one_task=request["one_task"])
    ledger = OpenAISpendLedger.read()
    return {
        "execute": False,
        "provider": "openai",
        "mode": "sweep" if request["sweep"] else "outer_openai",
        "split": split,
        "tasks": [task["id"] for task in tasks],
        "arms": list(arms),
        "outer_model": None if request["sweep"] else cells[0]["model"],
        "models": models,
        "effort": None if request["sweep"] else cells[0]["effort"],
        "efforts": [cell["effort"] for cell in cells],
        "allowed_models": list(ALLOWED_OPENAI_MODELS),
        "efforts_by_model": {name: list(efforts_for(name)) for name in ALLOWED_OPENAI_MODELS},
        "cells": [dict(cell) for cell in cells],
        "same_model_on_every_arm": True,
        "openai_api_key": "set" if _key_is_set() else "unset",
        "per_run_cap_usd": OPENAI_RUN_BUDGET_USD,
        "sweep_cap_usd": OPENAI_SWEEP_BUDGET_USD if request["sweep"] else None,
        "project_cap_usd": OPENAI_PROJECT_BUDGET_USD,
        "project_spent_usd": ledger.running_total_usd,
        "prices_usd_per_mtok": {name: rates_for_report(name) for name in ALLOWED_OPENAI_MODELS},
        "cap": cap_statement(),
        "measured_run_usd": None,
        "network": "refused",
        "box_commands": _commands(request["sweep"]),
        "checks": "the same URL, text, and evidence checks as the Claude path",
    }


def resolve_openai_request(
    *,
    provider: str,
    model: str,
    effort: str,
    sweep: bool,
    one_task: bool,
) -> dict:
    """Validate flags. The Claude path rejects an OpenAI sweep or an effort."""
    if provider not in ("anthropic", "openai"):
        raise ValueError(f"unknown provider {provider!r}")
    if provider == "anthropic":
        if sweep or one_task:
            raise ValueError("The effort sweep is an OpenAI run. Pass --provider openai.")
        if effort:
            raise EffortNotAllowed("Claude does not take --effort.")
        if model and model != "claude-sonnet-5-5":
            from bench.budget import assert_allowed_model

            assert_allowed_model(model)
        return {"provider": "anthropic", "sweep": False, "one_task": False}
    if sweep and model:
        raise OpenAIModelNotAllowed("--sweep-effort runs both models. Refusing a single --model with it.")
    if sweep and effort:
        raise EffortNotAllowed("--sweep-effort covers every accepted effort. Refusing a single --effort with it.")
    if sweep:
        return {"provider": "openai", "sweep": True, "one_task": True, "model": None, "effort": None}
    if not model:
        raise OpenAIModelNotAllowed(
            f"An OpenAI run needs --model. Accepted models are {list(ALLOWED_OPENAI_MODELS)}."
        )
    chosen = assert_openai_model(model)
    name = assert_effort(chosen, effort or DEFAULT_EFFORT)
    return {
        "provider": "openai",
        "sweep": False,
        "one_task": bool(one_task),
        "model": chosen,
        "effort": name,
    }


def _stamp(row: dict, *, model: str, effort: str) -> dict:
    row["provider"] = "openai"
    row["model"] = model
    row["effort"] = effort
    row["claude"] = False
    return row


def _record(row: dict, ledger: OpenAISpendLedger, *, arm: str, model: str, effort: str) -> None:
    spent_tokens = int(row.get("input_tokens") or 0) + int(row.get("output_tokens") or 0)
    if row.get("skipped") or not spent_tokens:
        row["usd"] = 0.0 if row.get("skipped") else float(row.get("usd") or 0.0)
        return
    recorded = ledger.record_task(
        run_id="probe",
        task_id=f"{arm}:{row.get('task_id')}:{effort}",
        model=model,
        effort=effort,
        input_tokens=int(row.get("input_tokens") or 0),
        output_tokens=int(row.get("output_tokens") or 0),
        cached_tokens=int(row.get("cached_tokens") or 0),
        cache_write_30m_tokens=int(row.get("cache_write_30m_tokens") or 0),
        cache_write_12h_tokens=int(row.get("cache_write_12h_tokens") or 0),
    )
    row["usd"] = recorded
    if not ledger.allows_project():
        ledger.mark_aborted(
            f"OpenAI project total ${ledger.running_total_usd:.2f} would pass "
            f"${OPENAI_PROJECT_BUDGET_USD:.0f}."
        )
    ledger.save()


async def _one(
    arm: str,
    task: dict,
    cell: dict,
    *,
    api_key: str,
    headless: bool,
    destination: Path,
    ledger: OpenAISpendLedger,
    rows: list[dict],
    sink=None,
) -> None:
    from bench.probe import empty_row, run_claude_arm

    cell_model = cell["model"]
    cell_effort = cell["effort"]
    try:
        if not arm_needs_claude(arm):
            row = empty_row(arm, task["id"], reason=f"{arm} is not an OpenAI computer-use arm")
        elif arm == ARM_BROWSER_USE:
            from bench.browser_use_arm import run_browser_use_task

            row = await run_browser_use_task(
                task,
                api_key=api_key,
                headless=headless,
                model=cell_model,
                provider="openai",
                effort=cell_effort,
            )
        else:
            row = await run_claude_arm(
                arm,
                task,
                api_key=api_key,
                headless=headless,
                runs_dir=destination,
                provider="openai",
                model=cell_model,
                effort=cell_effort,
            )
    except PriceUnknown as exc:
        ledger.note_unpriced_call(str(exc))
        raise
    _stamp(row, model=cell_model, effort=cell_effort)
    try:
        _record(row, ledger, arm=arm, model=cell_model, effort=cell_effort)
    except PriceUnknown as exc:
        ledger.note_unpriced_call(str(exc))
        raise
    row["pass"] = "cold"
    _keep(rows, row, sink)


def _keep(rows: list[dict], row: dict, sink) -> None:
    """Remember the row and write it now. An abort later still has this line."""
    rows.append(row)
    if sink is not None:
        sink(row)


def _skip(rows: list[dict], arm: str, task: dict, cell: dict, reason: str, sink=None) -> None:
    from bench.probe import empty_row

    row = empty_row(arm, task["id"], reason=reason)
    _stamp(row, model=cell["model"], effort=cell["effort"])
    row["pass"] = "cold"
    _keep(rows, row, sink)


async def execute_openai_probe(
    *,
    arms: tuple[str, ...],
    split: str,
    sweep: bool,
    model: str | None,
    effort: str | None,
    one_task: bool,
    headless: bool,
    spend_path: Path | None,
    runs_dir: Path | None,
    no_model_only: bool,
    warm_replay: bool,
    honest: bool,
) -> list[dict]:
    """Run the matrix. Stops at $5 per cell, $15 per sweep, and $20 on the ledger."""
    import os

    from bench.probe import ProbeRefused, RUNS_DIR, arm_report

    if honest or no_model_only or warm_replay:
        raise ProbeRefused("Refusing an OpenAI run with --honest, --no-model-only, or --warm-replay.")
    request = resolve_openai_request(
        provider="openai",
        model=model or "",
        effort=effort or "",
        sweep=sweep,
        one_task=one_task,
    )
    cells = sweep_cells() if request["sweep"] else ({"model": request["model"], "effort": request["effort"]},)
    tasks = _tasks(split, one_task=request["one_task"])
    ledger = OpenAISpendLedger.read(spend_path or default_openai_spend_path())
    opening_allowance = ledger.cover_unrecorded_call()
    if not ledger.allows_project():
        raise ProbeRefused(
            f"OpenAI project total ${ledger.running_total_usd:.2f} has reached "
            f"${OPENAI_PROJECT_BUDGET_USD:.0f}. Refusing before any task."
        )
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ProbeRefused("OPENAI_API_KEY unset. Refusing before any browser or model call.")
    destination = runs_dir or RUNS_DIR
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = destination / f"probe_{stamp}.jsonl"
    handle = out.open("w", encoding="utf-8")

    def sink(row: dict) -> None:
        handle.write(json.dumps(row) + "\n")
        handle.flush()

    rows: list[dict] = []
    sweep_spent = opening_allowance
    sweep_cap = OPENAI_SWEEP_BUDGET_USD if request["sweep"] else None
    carried_allowance = opening_allowance

    try:
        for cell in cells:
            cell_spent = carried_allowance
            carried_allowance = 0.0
            for task in tasks:
                for arm in arms:
                    if cell_spent >= OPENAI_RUN_BUDGET_USD:
                        _skip(
                            rows,
                            arm,
                            task,
                            cell,
                            f"OpenAI run spend ${cell_spent:.2f} has reached ${OPENAI_RUN_BUDGET_USD:.0f}",
                            sink,
                        )
                        continue
                    if sweep_cap is not None and sweep_spent >= sweep_cap:
                        _skip(
                            rows,
                            arm,
                            task,
                            cell,
                            f"sweep spend ${sweep_spent:.2f} has reached ${sweep_cap:.0f}",
                            sink,
                        )
                        continue
                    if not ledger.allows_project():
                        _skip(
                            rows,
                            arm,
                            task,
                            cell,
                            (
                                f"OpenAI project total ${ledger.running_total_usd:.2f} "
                                f"has reached ${OPENAI_PROJECT_BUDGET_USD:.0f}"
                            ),
                            sink,
                        )
                        continue
                    before = len(rows)
                    await _one(
                        arm,
                        task,
                        cell,
                        api_key=api_key,
                        headless=headless,
                        destination=destination,
                        ledger=ledger,
                        rows=rows,
                        sink=sink,
                    )
                    for row in rows[before:]:
                        spent = float(row.get("usd") or 0)
                        cell_spent = round(cell_spent + spent, 6)
                        sweep_spent = round(sweep_spent + spent, 6)
        handle.write(
            json.dumps(
                {
                    "kind": "openai_report",
                    "provider": "openai",
                    "sweep": request["sweep"],
                    "cells": [dict(cell) for cell in cells],
                    "per_run_cap_usd": OPENAI_RUN_BUDGET_USD,
                    "sweep_cap_usd": sweep_cap,
                    "project_cap_usd": OPENAI_PROJECT_BUDGET_USD,
                    "measured_run_usd": None,
                    "report": arm_report(rows, arms),
                }
            )
            + "\n"
        )
        handle.flush()
    finally:
        handle.close()
    return rows
