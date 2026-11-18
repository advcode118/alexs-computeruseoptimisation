"""Run the pre-registered probe command on a subset of extval task ids (deviation 1, README).

    python docs/results/paired_run_20261118/run_subset.py TASK_ID [TASK_ID ...] -- <bench.probe args>

Only the task list is filtered; every other argument goes to bench.probe unchanged.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main(argv):
    split = argv.index("--")
    wanted, probe_args = argv[:split], argv[split + 1:]
    import bench.openai_run as openai_run
    from bench.probe import main as probe_main

    original = openai_run._tasks

    def subset(*args, **kwargs):
        tasks = [task for task in original(*args, **kwargs) if task["id"] in wanted]
        assert [t["id"] for t in tasks] == [w for w in wanted if w in {t["id"] for t in tasks}] and len(tasks) == len(wanted), tasks
        return tasks

    openai_run._tasks = subset
    return probe_main(probe_args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
