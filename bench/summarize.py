"""Generate markdown summary tables from benchmark run results."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TaskSummary:
    task_id: str
    success: bool
    total_steps: int
    total_wall_ms: float
    total_model_ms: float
    total_tool_ms: float
    total_other_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_snapshot_tokens: int
    error: str | None
    model_ignores_tools: int = 0
    decisions_check: str = "off"
    decisions_overturned: bool = False


def load_results(run_file: Path) -> list[TaskSummary]:
    """Load results from a JSONL run file."""
    results = []
    with open(run_file, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            results.append(TaskSummary(
                task_id=data["task_id"],
                success=data["success"],
                total_steps=data["total_steps"],
                total_wall_ms=data["total_wall_ms"],
                total_model_ms=data["total_model_ms"],
                total_tool_ms=data["total_tool_ms"],
                total_other_ms=data["total_other_ms"],
                total_input_tokens=data["total_input_tokens"],
                total_output_tokens=data["total_output_tokens"],
                total_snapshot_tokens=data["total_snapshot_tokens"],
                error=data.get("error"),
                model_ignores_tools=int(data.get("model_ignores_tools") or 0),
                decisions_check=str(data.get("decisions_check") or "off"),
                decisions_overturned=bool(data.get("decisions_overturned")),
            ))
    return results


def format_time(ms: float) -> str:
    """Format milliseconds as seconds."""
    return f"{ms / 1000:.1f}s"


def format_pct(part: float, total: float) -> str:
    """Format as percentage."""
    if total == 0:
        return "0%"
    return f"{100 * part / total:.0f}%"


def generate_task_table(results: list[TaskSummary]) -> str:
    """Generate per-task results table."""
    lines = [
        "| Task | Success | Steps | Wall Time | Model % | Tool % | Other % | Input Tok | Output Tok | Snapshot Tok | Ignores |",
        "|------|---------|-------|-----------|---------|--------|---------|-----------|------------|--------------|---------|",
    ]

    for r in results:
        success = "✓" if r.success else "✗"
        wall = format_time(r.total_wall_ms)
        model_pct = format_pct(r.total_model_ms, r.total_wall_ms)
        tool_pct = format_pct(r.total_tool_ms, r.total_wall_ms)
        other_pct = format_pct(r.total_other_ms, r.total_wall_ms)

        lines.append(
            f"| {r.task_id} | {success} | {r.total_steps} | {wall} | "
            f"{model_pct} | {tool_pct} | {other_pct} | "
            f"{r.total_input_tokens:,} | {r.total_output_tokens:,} | {r.total_snapshot_tokens:,} | "
            f"{r.model_ignores_tools} |"
        )

    return "\n".join(lines)


def generate_totals(results: list[TaskSummary]) -> str:
    """Generate totals summary."""
    total_tasks = len(results)
    successful = sum(1 for r in results if r.success)
    success_rate = 100 * successful / total_tasks if total_tasks else 0

    total_wall = sum(r.total_wall_ms for r in results)
    total_model = sum(r.total_model_ms for r in results)
    total_tool = sum(r.total_tool_ms for r in results)
    total_other = sum(r.total_other_ms for r in results)
    total_steps = sum(r.total_steps for r in results)
    total_input = sum(r.total_input_tokens for r in results)
    total_output = sum(r.total_output_tokens for r in results)
    total_snapshot = sum(r.total_snapshot_tokens for r in results)
    total_ignores = sum(r.model_ignores_tools for r in results)

    lines = [
        "## Summary",
        "",
        f"- **Tasks**: {total_tasks}",
        f"- **Success Rate**: {success_rate:.0f}% ({successful}/{total_tasks})",
        f"- **Total Steps**: {total_steps}",
        f"- **Total Wall Time**: {format_time(total_wall)}",
        f"- **Time in Model**: {format_pct(total_model, total_wall)} ({format_time(total_model)})",
        f"- **Time in Tools**: {format_pct(total_tool, total_wall)} ({format_time(total_tool)})",
        f"- **Other Time**: {format_pct(total_other, total_wall)} ({format_time(total_other)})",
        f"- **Total Input Tokens**: {total_input:,}",
        f"- **Total Output Tokens**: {total_output:,}",
        f"- **Total Snapshot Tokens**: {total_snapshot:,}",
        f"- **Model ignores tools**: {total_ignores}",
        "",
    ]
    modes = sorted({r.decisions_check for r in results if r.decisions_check != "off"})
    if modes:
        flipped = sum(1 for r in results if r.decisions_overturned)
        lines[-1:-1] = [f"- **Decisions check**: {', '.join(modes)} (overturned {flipped})"]

    if total_tasks > 0:
        avg_steps = total_steps / total_tasks
        avg_wall = total_wall / total_tasks
        avg_input = total_input / total_tasks
        avg_output = total_output / total_tasks

        lines.extend([
            "### Averages per Task",
            "",
            f"- **Avg Steps**: {avg_steps:.1f}",
            f"- **Avg Wall Time**: {format_time(avg_wall)}",
            f"- **Avg Input Tokens**: {avg_input:,.0f}",
            f"- **Avg Output Tokens**: {avg_output:,.0f}",
            "",
        ])

    return "\n".join(lines)


def generate_markdown_report(results: list[TaskSummary], title: str = "Benchmark Results") -> str:
    """Generate full markdown report."""
    sections = [
        f"# {title}",
        "",
        generate_totals(results),
        "## Per-Task Results",
        "",
        generate_task_table(results),
        "",
    ]

    errors = [(r.task_id, r.error) for r in results if r.error]
    if errors:
        sections.extend([
            "## Errors",
            "",
        ])
        for task_id, error in errors:
            sections.append(f"- **{task_id}**: {error}")
        sections.append("")

    return "\n".join(sections)


def print_summary(run_file: Path) -> None:
    """Print markdown summary for a run file."""
    results = load_results(run_file)
    report = generate_markdown_report(results)
    print(report)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        runs_dir = Path(__file__).parent / "runs"
        run_files = sorted(runs_dir.glob("*.jsonl"))
        if not run_files:
            print("Usage: python -m bench.summarize <run_file.jsonl>")
            print("No run files found in bench/runs/")
            sys.exit(1)
        run_file = run_files[-1]
        print(f"Using most recent run: {run_file.name}\n")
    else:
        run_file = Path(sys.argv[1])

    if not run_file.exists():
        print(f"File not found: {run_file}")
        sys.exit(1)

    print_summary(run_file)


if __name__ == "__main__":
    main()
