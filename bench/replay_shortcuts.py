"""Offline replay of snapshots through the no-model shortcut logic.

This script:
1. Loads saved snapshots from benchmark runs
2. Converts them to the Observation type used by the router
3. Runs them through html_shortcut and route_decision
4. Reports hit rate and whether the shortcut action matched the model's action

The five JSON files in bench/snapshots/ are hand-made. Replaying those files
is the 40% hit / 50% match figure (2 of 5 fired, 1 of those 2 matched).
A benchmark run writes real page snapshots under bench/runs/<run_id>/snapshots/.
Replay that directory when you want a measurement on real pages. This module
does not publish a new hit rate for those pages.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loop.actions import ActionBatch, Click, Fill, Observation
from loop.decide import html_shortcut, route_decision
from loop.observe.aria import parse_aria_snapshot
from loop.observe.base import observation_from_snapshot


@dataclass
class SnapshotRecord:
    """A recorded snapshot from a benchmark run."""
    task_id: str
    step_number: int
    snapshot_text: str
    model_action: str | None
    model_tool_name: str | None
    model_tool_args: dict
    url: str = "https://example.com"
    title: str = "Page"


@dataclass
class ReplayResult:
    """Result of replaying a snapshot through shortcuts."""
    task_id: str
    step_number: int
    shortcut_fired: bool
    shortcut_tier: str | None
    shortcut_action: str | None
    model_action: str | None
    matched: bool | None


def parse_aria_snapshot_to_observation(
    snapshot_text: str,
    url: str = "https://example.com",
    title: str = "Page",
) -> Observation:
    """Parse @playwright/mcp ARIA YAML snapshot into an Observation.

    Snapshot format is lines like:
    - button "Search" [ref=e12]
    - textbox "Query" [ref=e5]
    - link "Home" [ref=e1]
    """
    snapshot = parse_aria_snapshot(snapshot_text, url=url, title=title)
    return observation_from_snapshot(snapshot)


def action_to_string(batch: ActionBatch | None) -> str | None:
    """Convert an ActionBatch to a simple string representation."""
    if batch is None:
        return None
    if not batch.actions:
        return "done" if batch.done else "none"

    parts = []
    for action in batch.actions:
        if isinstance(action, Click):
            parts.append(f"click:{action.ref}")
        elif isinstance(action, Fill):
            parts.append(f"fill:{action.ref}:{action.text}")
        else:
            parts.append(action.summary())
    return ",".join(parts)


def model_action_to_string(tool_name: str, tool_args: dict) -> str:
    """Convert model tool call to string for comparison."""
    if tool_name == "browser_click":
        target = tool_args.get("target", tool_args.get("ref", "?"))
        return f"click:{target}"
    elif tool_name == "browser_type":
        target = tool_args.get("target", tool_args.get("ref", "?"))
        text = tool_args.get("text", "")
        return f"fill:{target}:{text}"
    elif tool_name == "browser_fill":
        target = tool_args.get("target", tool_args.get("ref", "?"))
        text = tool_args.get("value", tool_args.get("text", ""))
        return f"fill:{target}:{text}"
    elif tool_name == "browser_navigate":
        return f"goto:{tool_args.get('url', '?')}"
    elif tool_name == "browser_snapshot":
        return "snapshot"
    else:
        return f"{tool_name}:{json.dumps(tool_args)}"


def actions_match(shortcut: str | None, model: str | None) -> bool | None:
    """Check if shortcut action matches model action."""
    if shortcut is None:
        return None
    if model is None:
        return None
    if shortcut == "none" or shortcut == "done":
        return False

    shortcut_clean = shortcut.split(",")[0].lower()
    model_clean = model.split(",")[0].lower()

    shortcut_parts = shortcut_clean.split(":")
    model_parts = model_clean.split(":")

    if shortcut_parts[0] != model_parts[0]:
        return False

    if shortcut_parts[0] == "click" and len(shortcut_parts) > 1 and len(model_parts) > 1:
        return shortcut_parts[1] == model_parts[1]

    if shortcut_parts[0] == "fill" and len(shortcut_parts) > 2 and len(model_parts) > 2:
        return shortcut_parts[1] == model_parts[1]

    return shortcut_clean == model_clean


HANDMADE_SNAPSHOT_NOTE = (
    "These 5 files are hand-made snapshots. "
    "2 of 5 shortcuts fired (40% hit) and 1 of those 2 matched (50% match). "
    "That figure is this set only. Real page snapshots are saved under "
    "bench/runs/<run_id>/snapshots/ during a run."
)


TASK_DESCRIPTIONS = {
    "wv_wikipedia_search": "Search Wikipedia for Ada Lovelace and confirm you are on her article page",
    "wv_arxiv_search": "Search arXiv for 'attention is all you need' and identify the first author",
    "fixture_packing_add": "Add 'milk' to the packing list",
}


def replay_snapshot(
    snapshot: SnapshotRecord,
    task_description: str = "",
    previous_batch: ActionBatch | None = None,
    previous_observation: Observation | None = None,
) -> ReplayResult:
    """Replay a single snapshot through the shortcut logic.

    For step 1, route_decision always returns 'planner' because first=True.
    The shortcut logic is designed for subsequent steps where the model
    has already established context. We still run step 1 through html_shortcut
    to see if it could have fired.
    """
    if not task_description:
        task_description = TASK_DESCRIPTIONS.get(snapshot.task_id, "")

    obs = parse_aria_snapshot_to_observation(snapshot.snapshot_text, url=snapshot.url, title=snapshot.title)

    shortcut_batch = html_shortcut(
        task_description,
        obs,
        previous_batch=previous_batch,
        previous_observation=previous_observation,
    )

    if shortcut_batch is not None:
        shortcut_action = action_to_string(shortcut_batch)
        shortcut_tier = "html_shortcut"
    else:
        tier, controls = route_decision(
            first=snapshot.step_number == 1,
            retry=False,
            previous_batch=previous_batch,
            previous_observation=previous_observation,
            observation=obs,
        )
        shortcut_tier = tier
        if tier == "direct" and controls:
            shortcut_action = f"click:{controls[0].ref}"
        else:
            shortcut_action = None

    model_action = None
    if snapshot.model_tool_name:
        model_action = model_action_to_string(
            snapshot.model_tool_name,
            snapshot.model_tool_args,
        )

    shortcut_fired = shortcut_action is not None
    matched = actions_match(shortcut_action, model_action) if shortcut_fired else None

    return ReplayResult(
        task_id=snapshot.task_id,
        step_number=snapshot.step_number,
        shortcut_fired=shortcut_fired,
        shortcut_tier=shortcut_tier,
        shortcut_action=shortcut_action,
        model_action=model_action,
        matched=matched,
    )


def load_snapshots_from_run(run_file: Path) -> list[SnapshotRecord]:
    """Load page snapshots captured during a run.

    Prefers ``<run_id>/snapshots/*.json`` next to the JSONL. Those files are
    the pages saved while the run was going. The next model action is stored
    on the file when the model took one. Otherwise uses ``snapshot_text`` on
    each step, which is the page that tool returned.
    """
    sidecar = run_file.parent / run_file.stem / "snapshots"
    if sidecar.is_dir() and any(sidecar.glob("*.json")):
        return load_snapshots_from_dir(sidecar)

    snapshots = []
    with open(run_file, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            task_id = data["task_id"]
            for step in data.get("steps", []):
                text = (step.get("snapshot_text") or "").strip()
                if not text:
                    continue
                snapshots.append(SnapshotRecord(
                    task_id=task_id,
                    step_number=step.get("step_number", 1),
                    snapshot_text=text,
                    model_action=None,
                    model_tool_name=step.get("model_tool_name") or step.get("tool_name"),
                    model_tool_args=step.get("model_tool_args") or step.get("tool_args") or {},
                    url=step.get("page_url") or step.get("url") or "https://example.com",
                    title=step.get("page_title") or step.get("title") or "Page",
                ))
    return snapshots


def load_snapshots_from_dir(snapshots_dir: Path) -> list[SnapshotRecord]:
    """Load snapshots from a directory of snapshot files."""
    snapshots = []

    for snapshot_file in sorted(snapshots_dir.glob("*.json")):
        with open(snapshot_file, encoding="utf-8") as f:
            data = json.loads(f.read())

        snapshots.append(SnapshotRecord(
            task_id=data.get("task_id", snapshot_file.stem),
            step_number=data.get("step_number", 1),
            snapshot_text=data.get("snapshot_text", ""),
            model_action=data.get("model_action"),
            model_tool_name=data.get("model_tool_name"),
            model_tool_args=data.get("model_tool_args") or {},
            url=data.get("url") or "https://example.com",
            title=data.get("title") or "Page",
        ))

    return snapshots


def generate_replay_report(results: list[ReplayResult]) -> str:
    """Generate markdown report of replay results."""
    total = len(results)
    fired = sum(1 for r in results if r.shortcut_fired)
    matched = sum(1 for r in results if r.matched is True)
    mismatched = sum(1 for r in results if r.matched is False)

    lines = [
        "# Shortcut Replay Report",
        "",
        "## Summary",
        "",
        f"- **Total Snapshots**: {total}",
        f"- **Shortcut Fired**: {fired} ({100 * fired / total:.0f}%)" if total else "- **Shortcut Fired**: 0",
        f"- **Matched Model Action**: {matched}" if fired else "",
        f"- **Mismatched**: {mismatched}" if fired else "",
        "",
        "## Details",
        "",
        "| Task | Step | Shortcut Fired | Tier | Shortcut Action | Model Action | Match |",
        "|------|------|----------------|------|-----------------|--------------|-------|",
    ]

    for r in results:
        fired_str = "✓" if r.shortcut_fired else "✗"
        tier = r.shortcut_tier or "-"
        shortcut = r.shortcut_action or "-"
        model = r.model_action or "-"
        match_str = "✓" if r.matched is True else ("✗" if r.matched is False else "-")

        lines.append(
            f"| {r.task_id} | {r.step_number} | {fired_str} | {tier} | "
            f"{shortcut[:30]} | {model[:30]} | {match_str} |"
        )

    return "\n".join(lines)


def main() -> None:
    """CLI entry point."""
    snapshots_dir = Path(__file__).parent / "snapshots"
    handmade = False

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.is_dir():
            snapshots = load_snapshots_from_dir(path)
            handmade = path.resolve() == snapshots_dir.resolve()
        else:
            snapshots = load_snapshots_from_run(path)
    elif snapshots_dir.exists():
        snapshots = load_snapshots_from_dir(snapshots_dir)
        handmade = True
    else:
        print("Usage: python -m bench.replay_shortcuts <snapshots_dir|run_file.jsonl>")
        print(f"No snapshots found in {snapshots_dir}")
        sys.exit(1)

    if handmade:
        print(HANDMADE_SNAPSHOT_NOTE)
        print()

    if not snapshots:
        print("No snapshots found to replay")
        sys.exit(1)

    results = []
    for snapshot in snapshots:
        result = replay_snapshot(snapshot, task_description="")
        results.append(result)

    report = generate_replay_report(results)
    print(report)


if __name__ == "__main__":
    main()
