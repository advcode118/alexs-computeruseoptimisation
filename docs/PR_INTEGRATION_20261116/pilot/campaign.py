"""Fixed-DEV-selection pilot campaign for PR74 (observe-first) and PR82 (segments).

Plan: C:/Users/epicd/AppData/Local/Temp/opencode/pr-integration-pilot-plan.md.
Wraps the audited driver's evaluate(); only load_tasks is narrowed to the frozen
selection. No grader/task mutation. One sequential paid writer.

  python campaign.py select     # writes selection.json (ids + hashes), no network
  python campaign.py run        # sequential rep1 -> stop rule -> rep2
  python campaign.py child ...  # internal: one condition/split/repeat in a fresh process
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
RUNTIME = Path("C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-a4e6c093-af3e2266c4387fe7")
DRIVER = Path("C:/Users/epicd/.t3/worktrees/computeruseoptimisation/t3-3df6dc75-c72ace6f81735bf9/tools/pr_eval.py")
KEY_FILE = Path.home() / ".cu-optimisation" / "openai.key"
LEDGER = Path.home() / ".cu-optimisation" / "openai-spend.json"
SALT = "pr-integration-20261116:"
GROUPS = [("dev3", "dev3_nav_", 4), ("dev3", "dev3_value_", 4), ("dev3", "dev3_search_", 4),
          ("dev4form", "", 6), ("dev4spa", "", 6)]
SPLIT_ORDER = ("dev3", "dev4form", "dev4spa")
CONDITIONS = {
    "baseline": {"CU_PAGE_SUMMARY": "0", "CU_SF_SEGMENTS": "0"},
    "observe": {"CU_PAGE_SUMMARY": "1", "CU_SF_SEGMENTS": "0"},
    "segments": {"CU_PAGE_SUMMARY": "0", "CU_SF_SEGMENTS": "1"},
}
COMMON = {"CU_SF_STRATEGY": "", "CU_SF_LOOK": "0", "CU_SF_REPAIR": "grounded", "CU_SF_MAX_REPAIRS": "3"}
ORDERS = {1: ("baseline", "observe", "segments"), 2: ("segments", "observe", "baseline")}
CATALOG_FILES = ("bench/tasks.py", "bench/tasks_dev3.py", "bench/tasks_dev4_form.py", "bench/tasks_dev4_spa.py")
RUNTIME_FILES = ("harness", "probe", "arms", "script_first", "segments", "openai_client", "openai_spend",
                 "strategy_nav", "strategy_form", "strategy_spa", "page_summary", "selfcheck_replay", "grade")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args) -> str:
    return subprocess.check_output(["git", "-C", str(RUNTIME), *args], text=True).strip()


def frozen_state() -> dict:
    return {
        "runtime_head": git("rev-parse", "HEAD"),
        "runtime_dirty": bool(git("status", "--porcelain")),
        "catalog_sha256": {f: sha(RUNTIME / f) for f in CATALOG_FILES},
        "runtime_sha256": {f"bench/{n}.py": sha(RUNTIME / "bench" / f"{n}.py")
                           for n in RUNTIME_FILES if (RUNTIME / "bench" / f"{n}.py").is_file()},
        "driver_path": str(DRIVER), "driver_sha256": sha(DRIVER),
        "campaign_sha256": sha(Path(__file__)),
    }


def select() -> None:
    out = HERE / "selection.json"
    if out.exists():
        raise SystemExit("selection.json exists; refusing to overwrite")
    sys.path.insert(0, str(RUNTIME))
    from bench.tasks_dev3 import DEV3_TASK_IDS
    from bench.tasks_dev4_form import DEV4_FORM_TASK_IDS
    from bench.tasks_dev4_spa import DEV4_SPA_TASK_IDS
    pools = {"dev3": DEV3_TASK_IDS, "dev4form": DEV4_FORM_TASK_IDS, "dev4spa": DEV4_SPA_TASK_IDS}
    chosen: dict[str, set] = {s: set() for s in SPLIT_ORDER}
    groups = {}
    for split, prefix, n in GROUPS:
        ids = [i for i in pools[split] if i.startswith(prefix)]
        ids.sort(key=lambda i: hashlib.sha256((SALT + i).encode()).hexdigest())
        groups[f"{split}:{prefix or '*'}"] = ids[:n]
        chosen[split].update(ids[:n])
    # Within a split keep the catalog's own order (same order every condition/repeat).
    selection = {s: [i for i in pools[s] if i in chosen[s]] for s in SPLIT_ORDER}
    assert sum(map(len, selection.values())) == 24
    data = {"plan": "C:/Users/epicd/AppData/Local/Temp/opencode/pr-integration-pilot-plan.md",
            "salt": SALT, "groups": groups, "selection": selection, "frozen": frozen_state()}
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))


def load_selection() -> dict:
    data = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
    now = frozen_state()
    frozen = dict(data["frozen"])
    if now != frozen:
        raise SystemExit("Frozen runtime/driver/campaign/catalog state changed; refusing")
    if now["runtime_dirty"]:
        raise SystemExit("Runtime checkout is dirty; refusing")
    return data


def child(cond: str, split: str, rep: int) -> int:
    data = load_selection()
    ids = data["selection"][split]
    want = {**COMMON, **CONDITIONS[cond]}
    if any(os.environ.get(k, "") != v for k, v in want.items()):
        raise SystemExit("Child environment does not match the condition")
    spec = importlib.util.spec_from_file_location("pr_eval", DRIVER)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    original = driver.load_tasks

    def fixed(split_name, task_limit):
        tasks = original(split_name, None)
        by_id = {t["id"]: t for t in tasks}
        missing = [i for i in ids if i not in by_id]
        if missing or split_name != split:
            raise driver.Refused("Frozen selection absent from split")
        return [by_id[i] for i in ids]

    driver.load_tasks = fixed
    output = HERE / f"rep{rep}" / cond / split
    manifest = asyncio.run(driver.evaluate(split=split, task_limit=None, output=output))
    status = json.loads(manifest.read_text(encoding="utf-8"))["status"]
    print(f"{cond} rep{rep} {split}: {status}")
    return 0 if status == "completed" else 2


def child_env(cond: str) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("CU_") and k not in ("OPENAI_API_KEY", "PYTHONPATH")}
    env.update(COMMON)
    env.update(CONDITIONS[cond])
    env["PYTHONPATH"] = str(RUNTIME)
    env["CU_OPENAI_SPEND_LEDGER"] = str(LEDGER)
    env["PYTHONUNBUFFERED"] = "1"
    env["OPENAI_API_KEY"] = KEY_FILE.read_text(encoding="utf-8").strip()  # child env only
    return env


def false_accepts(rep: int, cond: str) -> int:
    n = 0
    for split in SPLIT_ORDER:
        rows = HERE / f"rep{rep}" / cond / split / "rows.jsonl"
        for line in rows.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("end_state") == "PASS" and row.get("success") is False:
                n += 1
    return n


def run() -> int:
    load_selection()
    log = (HERE / "campaign_log.jsonl").open("a", encoding="utf-8")

    def note(**kw):
        log.write(json.dumps(kw) + "\n")
        log.flush()
        print(json.dumps(kw), flush=True)

    active = list(ORDERS[1])
    for rep in (1, 2):
        order = [c for c in ORDERS[rep] if c in active]
        for cond in order:
            for split in SPLIT_ORDER:
                if (HERE / f"rep{rep}" / cond / split).exists():
                    note(event="skip_existing", rep=rep, cond=cond, split=split)
                    continue
                proc = subprocess.run([sys.executable, "-u", str(Path(__file__)), "child", cond, split, str(rep)],
                                      env=child_env(cond), cwd=str(HERE))
                note(event="child_done", rep=rep, cond=cond, split=split, code=proc.returncode)
                if proc.returncode != 0:
                    note(event="campaign_stopped", reason="child not completed", rep=rep, cond=cond, split=split)
                    return 2
        if rep == 1:
            fa = {c: false_accepts(1, c) for c in active}
            dropped = [c for c in ("observe", "segments") if fa[c] - fa["baseline"] > 2]
            active = [c for c in active if c not in dropped]
            note(event="rep1_stop_rule", false_accepts=fa, dropped=dropped)
    note(event="campaign_completed")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "select":
        select()
    elif cmd == "run":
        raise SystemExit(run())
    elif cmd == "child":
        raise SystemExit(child(sys.argv[2], sys.argv[3], int(sys.argv[4])))
