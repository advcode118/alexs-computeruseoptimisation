#!/usr/bin/env python3
"""CLI entry point for running the benchmark.

Usage:
    # Run all tasks (requires ANTHROPIC_API_KEY)
    python -m bench.run

    # Run only fixture tasks
    python -m bench.run --fixtures-only

    # Run only WebVoyager tasks
    python -m bench.run --webvoyager-only

    # Dry run (no API key needed, shows what would be run)
    python -m bench.run --dry-run

    # Run with visible browser
    python -m bench.run --no-headless

    # Use a specific model
    python -m bench.run --model claude-sonnet-4-20250514
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

from bench.harness import BenchmarkHarness, run_benchmark
from bench.tasks import BENCHMARK_TASKS, get_fixture_tasks, get_webvoyager_tasks
from bench.summarize import generate_markdown_report, TaskSummary


def dry_run_output(tasks: list[dict]) -> str:
    """Generate dry-run output showing what would be run."""
    lines = [
        "# Benchmark Dry Run",
        "",
        f"Would run {len(tasks)} tasks:",
        "",
    ]

    for task in tasks:
        lines.append(f"- **{task['id']}**: {task['description'][:60]}...")
        lines.append(f"  - Start URL: {task['start_url'][:60]}...")
        if "check_url_contains" in task:
            lines.append(f"  - Success: URL contains '{task['check_url_contains']}'")
        elif "check_text" in task:
            lines.append(f"  - Success: Text present: {task['check_text']}")
        elif "judge_prompt" in task:
            lines.append(f"  - Success: LLM judge with prompt")
        lines.append("")

    lines.extend([
        "## Configuration",
        "",
        f"- ANTHROPIC_API_KEY: {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'NOT SET'}",
        f"- Model: {os.environ.get('BENCH_MODEL', 'claude-sonnet-4-20250514')}",
        "",
        "To run the benchmark:",
        "```bash",
        "export ANTHROPIC_API_KEY=your-key-here",
        "python -m bench.run",
        "```",
    ])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mcp-turbo benchmark")
    parser.add_argument(
        "--fixtures-only",
        action="store_true",
        help="Run only fixture tasks (no network needed)",
    )
    parser.add_argument(
        "--webvoyager-only",
        action="store_true",
        help="Run only WebVoyager tasks",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without running",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model to use",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=30,
        help="Maximum steps per task",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (defaults to bench/runs/<timestamp>.jsonl)",
    )

    args = parser.parse_args()

    if args.fixtures_only:
        tasks = get_fixture_tasks()
    elif args.webvoyager_only:
        tasks = get_webvoyager_tasks()
    else:
        tasks = BENCHMARK_TASKS

    if args.dry_run:
        print(dry_run_output(tasks))
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        print()
        print("To run the benchmark, set your API key:")
        print("  export ANTHROPIC_API_KEY=your-key-here")
        print()
        print("Or run a dry-run to see what would be executed:")
        print("  python -m bench.run --dry-run")
        sys.exit(1)

    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"Running benchmark with {len(tasks)} tasks")
    print(f"Model: {args.model}")
    print(f"Headless: {not args.no_headless}")
    print(f"Max steps: {args.max_steps}")
    print(f"Run ID: {run_id}")
    print()

    results = asyncio.run(run_benchmark(
        tasks=tasks,
        api_key=api_key,
        model=args.model,
        headless=not args.no_headless,
        run_id=run_id,
    ))

    summaries = [
        TaskSummary(
            task_id=r.task_id,
            success=r.success,
            total_steps=r.total_steps,
            total_wall_ms=r.total_wall_ms,
            total_model_ms=r.total_model_ms,
            total_tool_ms=r.total_tool_ms,
            total_other_ms=r.total_other_ms,
            total_input_tokens=r.total_input_tokens,
            total_output_tokens=r.total_output_tokens,
            total_snapshot_tokens=r.total_snapshot_tokens,
            error=r.error,
        )
        for r in results
    ]

    report = generate_markdown_report(summaries, title=f"Benchmark Results - {run_id}")
    print()
    print(report)

    runs_dir = Path(__file__).parent / "runs"
    report_file = runs_dir / f"{run_id}_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    main()
