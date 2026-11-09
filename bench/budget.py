"""Project spend for the bench harness.

The outer model id is claude-sonnet-5-5. The ledger still prices tokens at
the recorded rate of $3 per million input tokens and $15 per million output
tokens. Repricing at the Sonnet 5.5 list price ($2 / $10) would change
running_total_usd, so this file does not. The prior total is the recorded M0
usage: 3.2M input tokens and 3k output tokens, which is $9.645, about $10.
That entry is the measurement already spent. It is not a new run.

The operator envelope is $50. A run aborts at $40.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# Claude API id from the Sonnet 5.5 model page. No date suffix.
ALLOWED_MODEL = "claude-sonnet-5-5"
RETIRED_MODEL = "claude-sonnet-4-20250514"
FORMER_MODEL = "claude-sonnet-4-6"
# Messages API version used with claude-sonnet-5-5. Not sent by this checkout.
ANTHROPIC_VERSION = "2026-10-21"
# Recorded ledger rate. Sonnet 5.5 list price is $2 / $10. Applying that
# here would move running_total_usd, so the recorded rate stays.
INPUT_USD_PER_MTOK = 3.0
OUTPUT_USD_PER_MTOK = 15.0
# Abort. The operator envelope is $50; the run stops at $40.
PROJECT_BUDGET_USD = 40.0

# Recorded M0 totals. "3.2M" and "3k" are the figures from that measurement.
PRIOR_INPUT_TOKENS = 3_200_000
PRIOR_OUTPUT_TOKENS = 3_000

def default_spend_path() -> Path:
    """One shared ledger for every worktree.

    CU_SPEND_LEDGER wins. Otherwise the file is
    %USERPROFILE%\\.cu-optimisation\\spend.json on Windows and
    ~/.cu-optimisation/spend.json elsewhere. A missing file is not created.
    """
    override = os.environ.get("CU_SPEND_LEDGER", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cu-optimisation" / "spend.json"


class ModelNotAllowed(ValueError):
    """The bench calls claude-sonnet-5-5 and nothing else."""


class LedgerMissing(FileNotFoundError):
    """A live run will not start without the shared spend ledger."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(
            f"Spend ledger not found at {path}. "
            "Refusing to run live without it. "
            "Set CU_SPEND_LEDGER to the shared spend.json "
            f"(default {Path.home() / '.cu-optimisation' / 'spend.json'}). "
            "This process will not invent a starting total."
        )


class BudgetExceeded(RuntimeError):
    """The running project total would pass the budget, so the run stops."""

    def __init__(
        self,
        running_total_usd: float,
        results: list,
        budget_usd: float = PROJECT_BUDGET_USD,
    ):
        self.running_total_usd = running_total_usd
        self.results = results
        self.budget_usd = budget_usd
        super().__init__(
            f"Stopped: project total ${running_total_usd:.2f} would pass "
            f"the ${budget_usd:.0f} budget."
        )


def assert_allowed_model(model: str) -> str:
    """Accept claude-sonnet-5-5. Refuse Opus, Sonnet 4.6, and the retired id."""
    if not isinstance(model, str):
        raise ModelNotAllowed(f"Refusing model {model!r}. The bench model is {ALLOWED_MODEL}.")
    chosen = model.strip()
    if "opus" in chosen.lower():
        raise ModelNotAllowed(
            f"Refusing {chosen}. The bench model is {ALLOWED_MODEL}. Opus is never used."
        )
    if chosen == FORMER_MODEL:
        raise ModelNotAllowed(
            f"Refusing {FORMER_MODEL}. The bench model is {ALLOWED_MODEL}."
        )
    if chosen == RETIRED_MODEL:
        raise ModelNotAllowed(
            f"Refusing {RETIRED_MODEL}. That model is retired. The bench model is {ALLOWED_MODEL}."
        )
    if chosen != ALLOWED_MODEL:
        raise ModelNotAllowed(f"Refusing {chosen}. The bench model is {ALLOWED_MODEL}.")
    return ALLOWED_MODEL


def estimate_usd(input_tokens: int, output_tokens: int) -> float:
    """Dollars from token counts times the recorded ledger rate.

    The rate stays $3/MTok input and $15/MTok output so the recorded
    running total does not move. Sonnet 5.5 list price is $2 / $10.
    """
    return (
        int(input_tokens) * INPUT_USD_PER_MTOK
        + int(output_tokens) * OUTPUT_USD_PER_MTOK
    ) / 1_000_000


def prior_record() -> dict:
    """M0 spend already on the books. Token counts are the recorded totals."""
    usd = round(estimate_usd(PRIOR_INPUT_TOKENS, PRIOR_OUTPUT_TOKENS), 6)
    return {
        "label": "M0 measurement already spent",
        "model": ALLOWED_MODEL,
        "input_tokens": PRIOR_INPUT_TOKENS,
        "output_tokens": PRIOR_OUTPUT_TOKENS,
        "usd": usd,
        "tasks_succeeded": "4/5",
        "steps": 36,
        "wall_s": 94.8,
        "model_time_pct": 87,
        "tool_time_pct": 13,
        "tasks_started": 5,
        "tasks_in_suite": 12,
        "note": (
            "Computed from the recorded M0 totals of 3.2M input tokens and 3k output tokens "
            "at the recorded ledger rate ($3/MTok input, $15/MTok output). "
            "That is $9.645, about $10. 4/5 tasks succeeded, 36 steps, 94.8s, "
            "model time 87%, tools 13%, stopped after 5 of 12 tasks. "
            "This is that measurement, not a new run. The outer model id is "
            "claude-sonnet-5-5. The recorded total is not repriced."
        ),
    }


@dataclass
class SpendLedger:
    """Running project total in the shared CU_SPEND_LEDGER file."""

    path: Path
    model: str = ALLOWED_MODEL
    budget_usd: float = PROJECT_BUDGET_USD
    input_usd_per_mtok: float = INPUT_USD_PER_MTOK
    output_usd_per_mtok: float = OUTPUT_USD_PER_MTOK
    prior: dict = field(default_factory=prior_record)
    tasks: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    running_total_usd: float = 0.0
    # Probe dollars already spent that are not a token line in tasks.
    # The M0 prior stays $9.645. This is added on top and must not be dropped.
    recorded_extra_usd: float = 0.0
    recorded_probe: dict = field(default_factory=dict)
    aborted: bool = False
    abort_reason: str | None = None

    def __post_init__(self) -> None:
        self.input_usd_per_mtok = INPUT_USD_PER_MTOK
        self.output_usd_per_mtok = OUTPUT_USD_PER_MTOK
        self.recompute()

    def recompute(self) -> None:
        incoming = int(self.prior.get("input_tokens", 0)) + sum(
            int(item["input_tokens"]) for item in self.tasks
        )
        outgoing = int(self.prior.get("output_tokens", 0)) + sum(
            int(item["output_tokens"]) for item in self.tasks
        )
        self.input_tokens = incoming
        self.output_tokens = outgoing
        self.running_total_usd = round(
            estimate_usd(incoming, outgoing) + float(self.recorded_extra_usd),
            6,
        )

    def allows_another_task(self) -> bool:
        """False once the project total has reached the budget."""
        return self.running_total_usd < self.budget_usd

    def record_task(
        self,
        *,
        run_id: str,
        task_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        usd = round(estimate_usd(input_tokens, output_tokens), 6)
        self.tasks.append(
            {
                "run_id": run_id,
                "task_id": task_id,
                "model": self.model,
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "usd": usd,
            }
        )
        self.recompute()
        return usd

    def mark_aborted(self) -> None:
        self.aborted = True
        self.abort_reason = (
            f"Project total ${self.running_total_usd:.2f} would pass "
            f"the ${self.budget_usd:.0f} budget."
        )

    def to_dict(self) -> dict:
        payload = {
            "model": self.model,
            "budget_usd": self.budget_usd,
            "prices": {
                "input_usd_per_mtok": self.input_usd_per_mtok,
                "output_usd_per_mtok": self.output_usd_per_mtok,
            },
            "prior": self.prior,
            "tasks": self.tasks,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "recorded_extra_usd": self.recorded_extra_usd,
            "running_total_usd": self.running_total_usd,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }
        if self.recorded_probe:
            payload["recorded_probe"] = self.recorded_probe
        return payload

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2) + "\n"
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)

    @classmethod
    def seed(cls, path: Path) -> SpendLedger:
        return cls(path=path, prior=prior_record(), tasks=[])

    @classmethod
    def load(cls, path: Path | None = None) -> SpendLedger:
        """Read an existing ledger. Never seeds a missing file."""
        target = Path(path) if path is not None else default_spend_path()
        if not target.exists():
            raise LedgerMissing(target)
        data = json.loads(target.read_text(encoding="utf-8"))
        model = assert_allowed_model(data.get("model", ALLOWED_MODEL))
        return cls(
            path=target,
            model=model,
            budget_usd=float(data.get("budget_usd", PROJECT_BUDGET_USD)),
            prior=data.get("prior") or prior_record(),
            tasks=list(data.get("tasks") or []),
            recorded_extra_usd=float(data.get("recorded_extra_usd") or 0.0),
            recorded_probe=dict(data.get("recorded_probe") or {}),
            aborted=bool(data.get("aborted", False)),
            abort_reason=data.get("abort_reason"),
        )
