"""OpenAI spend for the computer-use bench. Separate from the Claude ledger.

The only model ids are gpt-6.1-sol and gpt-6-luna. Any other id is refused
before a request. Prices are the published Standard text-token rates. A model
with no entry in that table is refused. This file does not read or write the
Claude spend.json.

Standard short context is at most 272,000 input tokens. Above that, the
published long-context rates apply to the whole request: 2x input and cached
input, 1.5x output. This client does not request Fast, Batch, Flex, Ultrafast,
or regional processing, so those prices are not used. Cache-retention writes
(30m / 12h) are not requested. An unrecognized usage field fails closed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

# Official model ids. Nothing else is accepted.
ALLOWED_OPENAI_MODELS = ("gpt-6.1-sol", "gpt-6-luna")

# reasoning.effort values this flag accepts, in sweep order.
# minimal and xhigh are added only when the model page lists them.
# none and max are listed for one or both models and are still refused.
_FLAG_EFFORTS = ("low", "medium", "high", "minimal", "xhigh")
_API_EFFORTS = {
    "gpt-6.1-sol": frozenset({"low", "medium", "high", "xhigh", "max"}),
    "gpt-6-luna": frozenset({"none", "low", "medium", "high", "xhigh", "max"}),
}
DEFAULT_EFFORT = "medium"

# Published Standard prices, USD per 1,000,000 tokens.
# https://developers.openai.com/api/docs/pricing
# https://developers.openai.com/api/docs/models/gpt-6.1-sol
# https://developers.openai.com/api/docs/models/gpt-6-luna
_STANDARD_PRICES = {
    "gpt-6.1-sol": {
        "input_usd_per_mtok": "2",
        "cached_input_usd_per_mtok": "0.1",
        "output_usd_per_mtok": "10",
    },
    "gpt-6-luna": {
        "input_usd_per_mtok": "0.1",
        "cached_input_usd_per_mtok": "0.01",
        "output_usd_per_mtok": "0.5",
    },
}
LONG_CONTEXT_INPUT_TOKENS = 272_000
OPENAI_PROJECT_BUDGET_USD = 20.0
OPENAI_RUN_BUDGET_USD = 5.0
# One sweep is both models at every accepted effort. The ceiling sits at the
# top of the $10–$15 band and under the $20 project cap. Each cell still
# stops at $5. One tuned task per cell keeps the sweep from repeating the
# three-task Claude set at every effort.
OPENAI_SWEEP_BUDGET_USD = 15.0
OPENAI_ARMS = "script_first,playwright_mcp,stagehand,browser_use"
_QUANTUM = Decimal("0.000001")


class OpenAIModelNotAllowed(ValueError):
    """The computer-use model is not gpt-6.1-sol or gpt-6-luna."""


class EffortNotAllowed(ValueError):
    """This model does not accept that reasoning effort."""


class PriceUnknown(RuntimeError):
    """No published price, or the usage object is not one this ledger can price."""


def default_openai_spend_path() -> Path:
    """The OpenAI ledger. CU_OPENAI_SPEND_LEDGER wins. Never the Claude file."""
    override = os.environ.get("CU_OPENAI_SPEND_LEDGER", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cu-optimisation" / "openai-spend.json"


def assert_openai_model(model: str) -> str:
    """Accept the two computer-use ids. Refuse every other name."""
    if not isinstance(model, str):
        raise OpenAIModelNotAllowed(
            f"Refusing model {model!r}. OpenAI computer-use models are {list(ALLOWED_OPENAI_MODELS)}."
        )
    chosen = model.strip()
    if chosen not in ALLOWED_OPENAI_MODELS:
        raise OpenAIModelNotAllowed(
            f"Refusing {chosen!r}. OpenAI computer-use models are {list(ALLOWED_OPENAI_MODELS)}."
        )
    if chosen not in _STANDARD_PRICES:
        raise PriceUnknown(f"No published price for {chosen}. Refusing to run.")
    return chosen


def efforts_for(model: str) -> tuple[str, ...]:
    """low, medium, high, plus minimal or xhigh only when the model page lists them."""
    chosen = assert_openai_model(model)
    api = _API_EFFORTS.get(chosen)
    if not api:
        raise PriceUnknown(f"No published effort list for {chosen}. Refusing to run.")
    return tuple(name for name in _FLAG_EFFORTS if name in api)


def assert_effort(model: str, effort: str) -> str:
    """Refuse an effort the flag does not accept for this model."""
    chosen = assert_openai_model(model)
    if not isinstance(effort, str) or not effort.strip():
        raise EffortNotAllowed(
            f"Refusing effort {effort!r}. {chosen} accepts {list(efforts_for(chosen))}."
        )
    name = effort.strip()
    allowed = efforts_for(chosen)
    if name not in allowed:
        raise EffortNotAllowed(f"Refusing effort {name!r}. {chosen} accepts {list(allowed)}.")
    return name


def published_rates(model: str) -> dict[str, Decimal]:
    """Standard short-context rates. Missing rates fail closed."""
    chosen = assert_openai_model(model)
    raw = _STANDARD_PRICES.get(chosen)
    if not raw:
        raise PriceUnknown(f"No published price for {chosen}. Refusing to run.")
    rates = {key: Decimal(value) for key, value in raw.items()}
    if any(value <= 0 for value in rates.values()):
        raise PriceUnknown(f"Published price for {chosen} is not usable. Refusing to run.")
    return rates


def rates_for_report(model: str) -> dict[str, float]:
    rates = published_rates(model)
    return {key: float(value) for key, value in rates.items()}


def price_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Dollars at the published Standard rates for this usage. No estimated usage."""
    rates = published_rates(model)
    try:
        incoming = int(input_tokens)
        outgoing = int(output_tokens)
        cached = int(cached_tokens)
    except (TypeError, ValueError) as exc:
        raise PriceUnknown("Token counts are not integers. Refusing to price.") from exc
    if incoming < 0 or outgoing < 0 or cached < 0 or cached > incoming:
        raise PriceUnknown("Token counts are inconsistent. Refusing to price.")
    uncached = incoming - cached
    in_rate = rates["input_usd_per_mtok"]
    cached_rate = rates["cached_input_usd_per_mtok"]
    out_rate = rates["output_usd_per_mtok"]
    if incoming > LONG_CONTEXT_INPUT_TOKENS:
        in_rate *= 2
        cached_rate *= 2
        out_rate *= Decimal("1.5")
    amount = (uncached * in_rate + cached * cached_rate + outgoing * out_rate) / Decimal(1_000_000)
    return float(amount.quantize(_QUANTUM, rounding=ROUND_HALF_UP))


def tokens_at_run_cap(model: str) -> dict:
    """How many tokens $5 buys on one axis. Not a measured run."""
    rates = published_rates(model)
    cap = Decimal(str(OPENAI_RUN_BUDGET_USD))
    million = Decimal(1_000_000)

    def tokens(rate: Decimal) -> int:
        return int((cap * million / rate).to_integral_value(rounding=ROUND_HALF_UP))

    return {
        "cap_usd": OPENAI_RUN_BUDGET_USD,
        "context": "standard short context, one side only, no cached tokens",
        "uncached_input_tokens": tokens(rates["input_usd_per_mtok"]),
        "output_tokens": tokens(rates["output_usd_per_mtok"]),
        "measured_run_usd": None,
    }


def sweep_cells() -> tuple[dict, ...]:
    """Luna first, then Sol. Each accepted effort is its own run."""
    cells = []
    for model in ("gpt-6-luna", "gpt-6.1-sol"):
        for effort in efforts_for(model):
            cells.append({"model": model, "effort": effort})
    return tuple(cells)


def sweep_task_ids(task_ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """One task. The check on that task is unchanged.

    Eight runs of the three-task Claude set would be twenty-four task-cells
    before arms. One task per effort is the subset that the $5 cell cap and
    the $15 sweep cap are meant to cover.
    """
    if not task_ids:
        raise ValueError("no tasks")
    return (str(task_ids[0]),)


def probe_command(model: str, effort: str) -> str:
    """One model, one effort, the four computer-use arms, the Claude task split."""
    chosen = assert_openai_model(model)
    name = assert_effort(chosen, effort)
    return (
        'OPENAI_API_KEY="$OPENAI_API_KEY" '
        "python -m bench.probe --execute "
        f"--provider openai --model {chosen} --effort {name} "
        f"--arms {OPENAI_ARMS}"
    )


def sweep_command() -> str:
    """Both models, every accepted effort, one task, inside the sweep cap."""
    return (
        'OPENAI_API_KEY="$OPENAI_API_KEY" '
        "python -m bench.probe --execute "
        "--provider openai --sweep-effort "
        f"--arms {OPENAI_ARMS}"
    )


def sweep_cell_command(model: str, effort: str) -> str:
    """The same cell the sweep runs, as its own process. The $15 ceiling is the sweep command."""
    chosen = assert_openai_model(model)
    name = assert_effort(chosen, effort)
    return (
        'OPENAI_API_KEY="$OPENAI_API_KEY" '
        "python -m bench.probe --execute "
        f"--provider openai --model {chosen} --effort {name} "
        "--sweep-task "
        f"--arms {OPENAI_ARMS}"
    )


def cap_statement() -> dict:
    """What the code can say before any API call. A finished run's bill needs token counts."""
    return {
        "per_run_cap_usd": OPENAI_RUN_BUDGET_USD,
        "sweep_cap_usd": OPENAI_SWEEP_BUDGET_USD,
        "project_cap_usd": OPENAI_PROJECT_BUDGET_USD,
        "measured_run_usd": None,
        "note": (
            "A run's dollar cost is priced from the token counts the API returns. "
            "It is not known before that. A run stops once it has reached $5. "
            "A sweep stops once it has reached $15. The project ledger stops at $20."
        ),
        "usd_5_buys": {model: tokens_at_run_cap(model) for model in ALLOWED_OPENAI_MODELS},
    }


@dataclass
class OpenAISpendLedger:
    """Running OpenAI total. A missing file starts at $0 and is not created until a save."""

    path: Path
    project_budget_usd: float = OPENAI_PROJECT_BUDGET_USD
    tasks: list = field(default_factory=list)
    running_total_usd: float = 0.0
    recorded_extra_usd: float = 0.0
    aborted: bool = False
    abort_reason: str | None = None
    created: bool = False
    model: str = ""
    effort: str = ""
    run_ceiling_usd: float | None = None

    def recompute(self) -> None:
        total = Decimal(str(self.recorded_extra_usd))
        for item in self.tasks:
            total += Decimal(str(item["usd"]))
        self.running_total_usd = float(total.quantize(_QUANTUM, rounding=ROUND_HALF_UP))

    def allows_project(self) -> bool:
        return self.running_total_usd < self.project_budget_usd

    @property
    def budget_usd(self) -> float:
        """The cap the current process is enforcing. The file keeps the $20 project cap."""
        if self.run_ceiling_usd is None:
            return self.project_budget_usd
        return min(self.project_budget_usd, self.run_ceiling_usd)

    def allows_another_task(self) -> bool:
        """False once this run's ceiling or the $20 project cap is reached."""
        if not self.allows_project():
            return False
        if self.run_ceiling_usd is not None and self.running_total_usd >= self.run_ceiling_usd:
            return False
        return True

    def record_task(
        self,
        *,
        run_id: str,
        task_id: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        model: str | None = None,
        effort: str | None = None,
    ) -> float:
        chosen = assert_openai_model(model or self.model)
        name = assert_effort(chosen, effort or self.effort)
        usd = price_usd(chosen, input_tokens, output_tokens, cached_tokens)
        self.tasks.append(
            {
                "run_id": run_id,
                "task_id": task_id,
                "provider": "openai",
                "model": chosen,
                "effort": name,
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "cached_tokens": int(cached_tokens),
                "usd": usd,
            }
        )
        self.recompute()
        return usd

    def mark_aborted(self, reason: str | None = None) -> None:
        self.aborted = True
        self.abort_reason = reason or (
            f"OpenAI total ${self.running_total_usd:.2f} would pass "
            f"${self.project_budget_usd:.0f}."
        )

    def to_dict(self) -> dict:
        return {
            "provider": "openai",
            "project_budget_usd": self.project_budget_usd,
            "per_run_budget_usd": OPENAI_RUN_BUDGET_USD,
            "prices_usd_per_mtok": {model: rates_for_report(model) for model in ALLOWED_OPENAI_MODELS},
            "tasks": self.tasks,
            "recorded_extra_usd": self.recorded_extra_usd,
            "running_total_usd": self.running_total_usd,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2) + "\n"
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)
        self.created = True

    @classmethod
    def read(cls, path: Path | None = None) -> OpenAISpendLedger:
        """Read an existing file or an unsaved zero ledger. Does not create the file."""
        target = Path(path) if path is not None else default_openai_spend_path()
        if not target.exists():
            return cls(path=target)
        data = json.loads(target.read_text(encoding="utf-8"))
        if data.get("provider") not in (None, "openai"):
            raise PriceUnknown(
                f"OpenAI ledger at {target} is not an OpenAI ledger. Refusing to run."
            )
        tasks = list(data.get("tasks") or [])
        for item in tasks:
            if not isinstance(item, dict):
                raise PriceUnknown("OpenAI ledger has a task that is not an object. Refusing to run.")
            assert_openai_model(str(item.get("model") or ""))
            assert_effort(str(item.get("model")), str(item.get("effort") or ""))
        ledger = cls(
            path=target,
            project_budget_usd=float(data.get("project_budget_usd", OPENAI_PROJECT_BUDGET_USD)),
            tasks=tasks,
            recorded_extra_usd=float(data.get("recorded_extra_usd") or 0.0),
            aborted=bool(data.get("aborted", False)),
            abort_reason=data.get("abort_reason"),
            created=True,
        )
        ledger.recompute()
        stored = data.get("running_total_usd")
        if stored is not None and float(stored) > ledger.running_total_usd:
            ledger.recorded_extra_usd = float(
                (
                    Decimal(str(ledger.recorded_extra_usd))
                    + Decimal(str(stored))
                    - Decimal(str(ledger.running_total_usd))
                ).quantize(_QUANTUM, rounding=ROUND_HALF_UP)
            )
            ledger.recompute()
        return ledger
