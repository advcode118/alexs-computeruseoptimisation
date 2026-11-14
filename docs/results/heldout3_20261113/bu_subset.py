"""Run a heldout3 probe on a fixed ~25% subset of the tasks (used for the browser_use runs after 14 Nov 23:00).

The subset is fixed by rule, not by results: group the task ids by (set, kind), order each group by
sha256 of the id, join the groups in sorted order and take every fourth id. The frozen bench code is
not changed; this only filters the task list that bench.probe would load. Usage:
    python docs/results/heldout3_20261113/bu_subset.py [--list] <bench.probe args>
"""
import hashlib
import sys

sys.path.insert(0, ".")
import bench.probe as probe  # noqa: E402
from bench.tasks import HELDOUT3_TASK_IDS  # noqa: E402


def subset_ids() -> list[str]:
    groups: dict[tuple[str, str], list[str]] = {}
    for tid in HELDOUT3_TASK_IDS:
        parts = tid.split("_")
        groups.setdefault((parts[0], parts[1]), []).append(tid)
    joined: list[str] = []
    for key in sorted(groups):
        joined += sorted(groups[key], key=lambda t: hashlib.sha256(t.encode()).hexdigest())
    return joined[::4]


KEEP = set(subset_ids())
_full = probe.probe_tasks


def _subset(split=None):
    tasks = _full(split)
    return [task for task in tasks if task["id"] in KEEP]


probe.probe_tasks = _subset

import bench.openai_run as openai_run  # noqa: E402  (the OpenAI path loads tasks itself)

_full_openai = openai_run.tasks_for_split
openai_run.tasks_for_split = lambda split=None: [t for t in _full_openai(split) if t["id"] in KEEP]

if __name__ == "__main__":
    if sys.argv[1:2] == ["--list"]:
        print(len(KEEP), "of", len(HELDOUT3_TASK_IDS))
        sys.exit(0)
    sys.exit(probe.main(sys.argv[1:]))
