"""Print per-task fields from saved probe logs.

This command does not start a browser and does not measure anything. Every
number it prints is a field already stored in the file. A row marked sketch
is a fixture, not a probe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def load_rows(path: Path) -> list[dict]:
    """Task rows from one JSONL file. Summary lines are not measurements."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            if not isinstance(data, dict) or not data.get("task_id") or not data.get("arm"):
                continue
            rows.append(data)
    return rows


def log_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("probe_*.jsonl"))
    return []


def _shown(row: dict, key: str) -> str:
    if key not in row or row[key] in ("", None):
        return "-"
    value = row[key]
    if key == "usd":
        return f"{float(value):.6f}"
    if key == "wall_ms":
        return str(value)
    return str(value)


def render(rows: list[dict]) -> str:
    """Per-task wall time, steps, tier, and the sum of saved dollars per arm."""
    lines: list[str] = []
    if rows and all(row.get("sketch") for row in rows):
        lines.append("sketch fixture, not a probe")
    arms: list[str] = []
    for row in rows:
        arm = str(row.get("arm"))
        if arm not in arms:
            arms.append(arm)
    for arm in arms:
        subset = [row for row in rows if row.get("arm") == arm]
        lines.append(f"arm {arm}")
        saved = 0.0
        for row in subset:
            phase = row.get("pass") or "-"
            lines.append(
                f"  {phase} {row.get('task_id')} wall_ms={_shown(row, 'wall_ms')} "
                f"steps={_shown(row, 'steps')} tier={_shown(row, 'tier')} usd={_shown(row, 'usd')}"
                + (f" effort={_shown(row, 'effort')}" if "effort" in row else "")
                + (f" model={_shown(row, 'model')}" if row.get("provider") == "openai" else "")
            )
            if "usd" in row and row["usd"] not in ("", None):
                saved += float(row["usd"])
        lines.append(f"  sum of usd in this file: {saved:.6f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(arg in {"--execute", "--no-headless", "--browser"} or arg.startswith("--arm") for arg in args):
        print("report reads saved logs and does not run a browser", file=sys.stderr)
        return 2
    target = Path(args[0]) if args else RUNS_DIR
    files = log_files(target)
    if not files:
        print(f"no saved probe logs at {target}")
        return 0
    rows: list[dict] = []
    for path in files:
        rows.extend(load_rows(path))
    if not rows:
        print(f"no task rows in {target}")
        return 0
    print(render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
