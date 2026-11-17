"""Offline interpretation of saved rows; the frozen grader remains untouched."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib
import json
from pathlib import Path
import re
import statistics
import subprocess

from bench import grade, tasks
from bench.arms import SELECTABLE_ARMS


ANSWER_REASONS = (
    "answer is not in the page text", "answer does not satisfy the marker",
    "answer is not the marked value", "answer too long",
    "answer does not match the marked value", "answer does not match the selector",
)


def answer_span(markers: dict, answer: str, selector_text: str = "") -> grade.EvidenceVerdict:
    """Check only answer constraints, NOT the historical page or URL.

    Synthetic text supplies every reduction candidate so page membership cannot
    reject an answer. All reductions, bounds and comparisons run in grade.py.
    """
    selected = {k: v for k, v in markers.items()
                if k in ("answer_in_text", "answer_equals_selector")}
    if selected.get("answer_equals_selector") and not selector_text.strip() and answer.strip():
        return grade.EvidenceVerdict(grade.UNKNOWN, "selector truth was not saved", "")
    text = "\n".join((*grade._answer_candidates(answer), selector_text,
                      str(selected.get("answer_in_text") or "")))
    return grade.evidence_verdict(
        selected, grade.PageEvidence(url="https://offline.invalid/", text=text,
                                     selector_text=selector_text),
        grade.ClaimedEvidence(answer=answer),
    )


def task_catalog() -> dict:
    catalog = {t["id"]: {"task": t, "split": "other", "hidden": False}
               for t in tasks.BENCHMARK_TASKS}
    for split, ids in (("dev", tasks.DEV_TASK_IDS), ("held-out", tasks.HELD_OUT_TASK_IDS),
                       ("heldout2", tasks.HELDOUT2_TASK_IDS)):
        for task_id in ids:
            catalog[task_id]["split"] = split
    for path in sorted(Path(tasks.__file__).parent.glob("tasks_*.py")):
        if not allowed_source(path):
            continue
        module = importlib.import_module("bench." + path.stem)
        split = path.stem.removeprefix("tasks_").replace("_", "")
        for name, value in vars(module).items():
            if name.endswith("_TASKS") and isinstance(value, list):
                for task in value:
                    catalog[task["id"]] = {"task": task, "split": split,
                                           "hidden": split.startswith("heldout3")}
    return catalog


def regrade_row(row: dict, catalog: dict) -> dict:
    task_id = row.get("task_id", "")
    entry = catalog.get(task_id)
    result = {"arm": row["arm"], "split": entry["split"] if entry else "unknown",
              "hidden": bool(entry and entry["hidden"]), "old": bool(row.get("success")),
              "new": None, "category": "", "reason": "", "code": "",
              "skipped": bool(row.get("skipped")), "potential_fail_to_pass": False}

    def finish(new, category, reason="", code=""):
        result.update(new=new, category=category, reason=reason, code=code)
        return result

    if result["skipped"]:
        return finish(None, "skipped")
    if row.get("success") is None:
        return finish(None, "not re-gradable: interrupted/ungraded row")
    if entry is None:
        return finish(None, "not re-gradable: task not found")
    task = entry["task"]
    markers = task.get("end_markers") or {}
    if row.get("wall_clock_version", 0) >= 2 and "grade_page_text" in row:
        claim = row.get("grade_claim")
        if isinstance(claim, dict):
            claim = grade.ClaimedEvidence(**claim)
        success, reason, _, _ = grade.grade_observation(
            task, row.get("grade_url", ""), row["grade_page_text"],
            selector_text=row.get("grade_selector_text", ""),
            answer=row.get("claimed_answer", ""), claimed=claim,
            completed=row.get("grade_completed"),
            completion_reason=row.get("grade_completion_reason", ""),
        )
        if row["arm"] == "script_first" and row.get("end_state") != grade.PASS:
            success, reason = False, "own verdict is not PASS"
        code = next((s.replace(" ", "_") for s in ANSWER_REASONS if s == reason),
                    "full_grade_pass" if success else "full_grade_fail")
        return finish(success, "full re-grade", reason, code)
    if not (markers.get("answer_in_text") or markers.get("answer_equals_selector")):
        return finish(result["old"], "unaffected (no answer marker)", row.get("success_reason", ""))
    if row["arm"] == "script_first" and row.get("end_state") != grade.PASS:
        return finish(False, "unchanged (own-verdict gate)", "own verdict is not PASS", "own_verdict_not_PASS")
    old_reason = row.get("success_reason") or ""
    if not result["old"] and not any(reason in old_reason.casefold() for reason in ANSWER_REASONS):
        if not old_reason:
            return finish(None, "not re-gradable: failure reason was not saved")
        return finish(False, "unchanged (non-answer failure)", old_reason, "non_answer_failure")
    if "claimed_answer" not in row:
        return finish(None, "not re-gradable: claimed answer was not saved")
    verdict = answer_span(markers, row.get("claimed_answer") or "", row.get("expected_value") or "")
    if verdict.verdict == grade.UNKNOWN:
        return finish(None, "not re-gradable: " + verdict.reason)
    if verdict.verdict == grade.FAIL:
        return finish(False, "answer-side re-grade", verdict.reason, verdict.code)
    if result["old"] or markers.get("answer_equals_selector"):
        return finish(True, "answer-side re-grade", verdict.reason, verdict.code)
    result["potential_fail_to_pass"] = True
    return finish(None, "not re-gradable: needs page text (would pass if marker is on the page)")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8")


def unpack(data: str, *, jsonl=True, pilot=False) -> list[dict]:
    values = [json.loads(line) for line in data.splitlines() if line.strip()] if jsonl else json.loads(data)
    if not isinstance(values, list):
        values = [values]
    rows = []
    for value in values:
        if not isinstance(value, dict):
            continue
        row = value.get("row", value)
        if not isinstance(row, dict) or value.get("kind") == "openai_report":
            continue
        if pilot:
            row = {**row, "arm": "script_first"}
        if row.get("arm") in SELECTABLE_ARMS and row.get("task_id"):
            rows.append(row)
    return rows


def allowed_source(path) -> bool:
    return "heldout4" not in str(path).casefold()


def discover(root: Path) -> list[dict]:
    """One current/latest committed version per path, never checkout branches."""
    sources = []
    current = {p.relative_to(root).as_posix(): p for p in sorted((root / "docs/results").rglob("*.jsonl"))
               if allowed_source(p)}
    head = git(root, "rev-parse", "HEAD").strip()
    branch = git(root, "branch", "--show-current").strip()
    for path, file in current.items():
        sources.append({"path": path, "branch": branch, "commit": head,
                        "data": file.read_text(encoding="utf-8-sig")})
    paths = sorted(set(git(root, "log", "--all", "--format=", "--name-only", "--", "*.jsonl").splitlines()))
    remotes = git(root, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin").splitlines()
    for path in paths:
        if not path or path in current or not path.startswith("docs/results/") or not allowed_source(path):
            continue
        commits = git(root, "log", "--all", "--diff-filter=AM", "--format=%H", "--", path).splitlines()
        if not commits:
            continue
        commit = commits[0]
        containing = git(root, "branch", "-r", "--contains", commit, "--format=%(refname:short)").splitlines()
        branches = sorted(set(containing) & set(remotes))
        # Prefer the named branch's tip when it still contains this path.
        owner = next((b for b in branches if b.endswith(("/decisions-second-opinion", "/robust-executor", "/strategy-search"))), None)
        if owner:
            tip = git(root, "rev-parse", owner).strip()
            exists = git(root, "ls-tree", "--name-only", tip, "--", path).strip()
            if exists:
                commit = tip
        sources.append({"path": path, "branch": owner or ", ".join(branches) or "historical --all",
                        "commit": commit, "data": git(root, "show", f"{commit}:{path}")})
    for path in sorted((root / "docs").rglob("pilot_rows.json")):
        if not allowed_source(path):
            continue
        sources.append({"path": path.relative_to(root).as_posix(), "branch": branch,
                        "commit": head, "data": path.read_text(encoding="utf-8-sig"), "pilot": True})
    for source in sources:
        source["sha256"] = hashlib.sha256(source["data"].encode()).hexdigest()
    return sources


def references(value) -> list[dict]:
    found = []
    if isinstance(value, dict):
        if "path" in value and isinstance(value["path"], str):
            found.append({k: value[k] for k in ("path", "sha256") if k in value})
        for key, child in value.items():
            if key in ("sources", "source_files"):
                if isinstance(child, list):
                    found.extend({"path": item} for item in child if isinstance(item, str))
                elif isinstance(child, dict):
                    found.extend({"path": k, "sha256": v} for k, v in child.items() if isinstance(v, str))
            found.extend(references(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(references(child))
    return list({json.dumps(item, sort_keys=True): item for item in found}.values())


def aggregate_arms(value) -> set[str]:
    arms = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in SELECTABLE_ARMS:
                arms.add(key)
            if key == "arm" and isinstance(child, str) and child in SELECTABLE_ARMS:
                arms.add(child)
            arms.update(aggregate_arms(child))
    elif isinstance(value, list):
        for child in value:
            arms.update(aggregate_arms(child))
    return arms


def aggregate_files(root: Path) -> list[dict]:
    files = []
    for pattern in ("heldout3_20261113/*.json", "val3*/*.json", "tip4*/*.json"):
        for path in sorted((root / "docs/results").glob(pattern)):
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            refs = references(value)
            if not refs and "heldout3_20261113" in str(path):
                manifest = path.parent / "manifest.txt"
                if manifest.exists():
                    refs = [{"path": p, "sha256": "not recorded"} for p in
                            re.findall(r"bench/runs/[^\s()]+\.jsonl", manifest.read_text())]
            files.append({"path": path.relative_to(root).as_posix(),
                          "reason": "not re-gradable: raw rows not in repo" if refs or "heldout3" in str(path)
                          else "no gradable rows (metadata only)", "references": refs,
                          "dataset": "heldout3 interim" if "heldout3" in str(path) else "val3",
                          "arms": sorted(aggregate_arms(value) or {"script_first"})})
    return files


def dataset(path: str, split: str) -> str:
    if "pilot" in path:
        return "pilot"
    if "2026-11-10" in path:
        return "Nov 10"
    if split.startswith("heldout3"):
        return "heldout3 interim"
    return {"held-out": "heldout (Nov 11 Luna/Sol)", "heldout2": "heldout2",
            "val3": "val3", "dev3": "dev3"}.get(split, split if split.startswith("dev4") else "other")


def stats(results: list[dict]) -> dict:
    active = [r for r in results if not r["skipped"]]
    graded = [r for r in active if r["new"] is not None]
    old = sum(r["old"] for r in graded)
    new = sum(r["new"] for r in graded)
    count = len(graded)
    return {"rows": len(results), "regradable": count, "old_pass": sum(r["old"] for r in active),
            "comparable_old_pass": old, "new_pass": new,
            "pass_to_fail": sum(r["old"] and not r["new"] for r in graded),
            "fail_to_pass": sum(not r["old"] and r["new"] for r in graded),
            "not_regradable": dict(Counter(r["category"] for r in active if r["new"] is None)),
            "categories": dict(Counter(r["category"] for r in results)),
            "potential_fail_to_pass": sum(r["potential_fail_to_pass"] for r in active),
            "skipped": len(results) - len(active),
            "old_rate": 100 * old / count if count else None,
            "new_rate": 100 * new / count if count else None,
            "delta_pp": 100 * (new - old) / count if count else None}


def normalized_wall(row: dict) -> tuple[float | None, str]:
    wall = row.get("wall_ms")
    if not isinstance(wall, (int, float)):
        return None, "wall not saved"
    if row.get("wall_clock_version", 0) >= 2:
        return wall, "version 2"
    if row["arm"] == "browser_use" and all(k in row for k in ("browser_launch_ms", "grade_read_ms")):
        return wall - row["browser_launch_ms"] - row["grade_read_ms"], "launch/read corrected estimate; grading overhead unknown"
    if row["arm"] in ("playwright_mcp", "diff_fast_act", "macro_replay", "stagehand") and all(
        k in row for k in ("browser_launch_ms", "grade_read_ms", "peek_ms")
    ):
        return wall + row["peek_ms"], "peek corrected estimate"
    return None, "not re-derivable from saved fields"


def build_report(root: Path, sources: list[dict], catalog: dict) -> dict:
    per_source, flips, hidden_flips = [], [], Counter()
    grouped, timings = defaultdict(list), defaultdict(list)
    unavailable = aggregate_files(root)
    for source in sources:
        rows = unpack(source["data"], jsonl=not source.get("pilot"), pilot=source.get("pilot", False))
        identity = {k: v for k, v in source.items() if k != "data"}
        if not rows:
            unavailable.append({**identity, "reason": "no gradable rows", "references": []})
            continue
        local_groups = defaultdict(list)
        for row in rows:
            result = regrade_row(row, catalog)
            split = result["split"]
            local_groups[(row["arm"], split)].append(result)
            grouped[(dataset(source["path"], split), row["arm"])].append(result)
            if not result["skipped"]:
                timings[(row["arm"], split)].append(row)
            if result["new"] is not None and not result["skipped"] and result["old"] != result["new"]:
                direction = "pass->fail" if result["old"] else "fail->pass"
                if result["hidden"]:
                    hidden_flips[(direction, result["code"])] += 1
                else:
                    flips.append({"task_id": row["task_id"], "file": source["path"], "arm": row["arm"],
                                  "direction": direction, "old_reason": row.get("success_reason") or "not saved",
                                  "new_reason": result["reason"], "code": result["code"],
                                  "answer": str(row.get("claimed_answer") or "")[:120]})
        per_source.append({**identity, "groups": [{"arm": arm, "split": split, **stats(results)}
                                                 for (arm, split), results in sorted(local_groups.items())]})
    timing = []
    for (arm, split), rows in sorted(timings.items()):
        walls = [r["wall_ms"] for r in rows if isinstance(r.get("wall_ms"), (int, float))]
        corrected = [normalized_wall(r) for r in rows]
        derived = [value for value, _ in corrected if value is not None]
        timing.append({"arm": arm, "split": split, "recorded_rows": len(walls),
                       "recorded_mean_ms": statistics.mean(walls) if walls else None,
                       "recorded_median_ms": statistics.median(walls) if walls else None,
                       "derived_rows": len(derived),
                       "derived_mean_ms": statistics.mean(derived) if derived else None,
                       "derived_median_ms": statistics.median(derived) if derived else None,
                       "status": dict(Counter(status for _, status in corrected))})
    datasets = [{"dataset": name, "arm": arm, **stats(results)}
                for (name, arm), results in sorted(grouped.items())]
    missing_groups = defaultdict(list)
    for source in unavailable:
        if source["reason"] == "not re-gradable: raw rows not in repo":
            for arm in source["arms"]:
                missing_groups[(source["dataset"], arm)].append(source["path"])
    for (name, arm), paths in sorted(missing_groups.items()):
        if (name, arm) not in grouped:
            datasets.append({"dataset": name, "arm": arm, **stats([]), "raw_rows_missing": paths})
    datasets.sort(key=lambda r: (r["dataset"], r["arm"]))
    return {"grader_sha256": hashlib.sha256((root / "bench/grade.py").read_bytes()).hexdigest(),
            "command": "python tools/regrade.py --out <output-directory>",
            "sources": per_source,
            "datasets": datasets,
            "flipped_rows": flips,
            "heldout3_flips": [{"direction": direction, "code": code, "count": count}
                                for (direction, code), count in sorted(hidden_flips.items())],
            "timing": timing, "not_regradable_files": unavailable}


def cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def number(value) -> str:
    return "—" if value is None else f"{value:.2f}"


def markdown(report: dict) -> str:
    lines = ["# Offline frozen-grader re-grade", "", "## Method", "",
             "Reproduce from the repository root: `" + report["command"] + "`.", "",
             "Rules: [GRADER](../../GRADER.md); timing: [MEASUREMENT](../../MEASUREMENT.md).",
             "Frozen grader SHA-256: `" + report["grader_sha256"] + "`.", "",
             "Discovery covers current docs/results JSONLs, latest saved paths from git log --all",
             "(remote-only files read with git show), and the sanitized #82 pilot JSON export.",
             "One version per path is counted, not every historical revision. Repeated runs remain",
             "separate observations: these are descriptive pooled rates, not independent-task estimates.", "",
             "Task splits/markers come from current bench/tasks*.py, not filenames or saved split labels.",
             "Skipped rows are excluded. Version-2 rows with saved grade_page_text (including empty text)",
             "use grade.grade_observation plus script-first's end_state==PASS gate. Legacy no-answer-marker",
             "rows are unaffected; non-answer failures and failed own-verdict gates remain failures.",
             "Legacy answer-side checks call the frozen evidence_verdict on synthetic text containing",
             "all frozen reduction candidates: this neutralizes page membership, never claims to recover it.",
             "Old passes imply page membership. A saved selector truth also implies page membership.",
             "Answer-related old text-marker failures that now satisfy the span rules are potential",
             "fail->pass only, not new passes, because actual page text is missing. Missing truth/claims",
             "or failure reasons are not invented. Categories and potential counts are in regrade.json.", "",
             "Per-file old pass counts cover all non-skipped rows; new pass counts cover known grades.",
             "Dataset old/new rates and delta use the SAME re-gradable subset (R); unknowns are not failures.",
             "'Raw absent' dataset rows denote aggregate-only files, not zero attempts or a 0% pass rate.",
             "Heldout3 is aggregate-only in both outputs: no task ids, answers or per-row records.", "",
             "The #82 segments pilot is docs/PR_INTEGRATION_20261116/pilot_20261116.md:",
             "baseline/observe/segments, partial repetition 1. Sanitized pilot_rows.json (63 rows) IS",
             "in the repository; raw JSONLs remain on Windows/gitignored. Missing answer/reason fields",
             "in that export limit re-grading; the interrupted row is ungraded, not a failure.", "",
             "## Per-source tables", ""]
    for source in report["sources"]:
        lines.extend(["### " + source["path"], "", f"Branch: `{source['branch']}`; commit: `{source['commit']}`; SHA-256: `{source['sha256']}`.", "",
                      "| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |",
                      "|---|---|---:|---:|---:|---:|---:|---:|---|---:|"])
        for group in source["groups"]:
            reasons = "; ".join(f"{k}: {v}" for k, v in group["not_regradable"].items()) or "—"
            lines.append("| " + " | ".join(cell(v) for v in (group["arm"], group["split"], group["rows"], group["regradable"],
                         group["old_pass"], group["new_pass"], group["pass_to_fail"], group["fail_to_pass"], reasons, group["skipped"])) + " |")
        lines.append("")
    lines.extend(["## Dataset-level summary", "", "Rates are percentages on the matched re-gradable subset, not all recorded rows.", "",
                  "| Dataset | Arm | Rows | R | Old pass (R) | New pass (R) | Old % | New % | Δ pp | Not re-gradable | Potential F→P | Skipped |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for group in report["datasets"]:
        if group.get("raw_rows_missing"):
            lines.append(f"| {group['dataset']} | {group['arm']} | raw absent | 0 | — | — | — | — | — | raw absent | — | — |")
            continue
        lines.append("| " + " | ".join(cell(v) for v in (group["dataset"], group["arm"], group["rows"], group["regradable"],
                     group["comparable_old_pass"], group["new_pass"], number(group["old_rate"]), number(group["new_rate"]),
                     number(group["delta_pp"]), sum(group["not_regradable"].values()), group["potential_fail_to_pass"], group["skipped"])) + " |")
    lines.extend(["", "## Flipped rows (excluding heldout3)", "",
                  "| Task | File | Arm | Direction | Old reason | New reason / code | Answer (≤120 chars) |", "|---|---|---|---|---|---|---|"])
    for row in report["flipped_rows"]:
        lines.append("| " + " | ".join(cell(row[k]) for k in ("task_id", "file", "arm", "direction", "old_reason")) +
                     " | " + cell(row["new_reason"] + " / " + row["code"]) + " | " + cell(row["answer"]) + " |")
    lines.extend(["", "### Heldout3 flip aggregates only", "", "| Direction | Reason code | Count |", "|---|---|---:|"])
    for row in report["heldout3_flips"]:
        lines.append(f"| {row['direction']} | {cell(row['code'])} | {row['count']} |")
    if not report["heldout3_flips"]:
        lines.append("| — | no re-gradable flips | 0 |")
    lines.extend(["", "## Wall time (as recorded; milliseconds)", "",
                  "Legacy browser_use included browser launch, grade read AND grading; script_first excluded",
                  "launch/read but overlapped launch with model writing; MCP/proxy/Stagehand excluded launch/read",
                  "AND the initial task peek. None is comparable to version 2 without the missing components.",
                  "Only rows with saved components are corrected: browser_use subtracts launch/read (an estimate",
                  "with unknown grading overhead), MCP adds saved peek_ms; version-2 rows are already normalized.",
                  "Script-first overlap cannot be reconstructed. No fields means no correction, not zero overhead.", "",
                  "| Arm | Split | Rows with wall | Recorded median | Recorded mean | Derived rows | Derived median | Derived mean | Status |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---|"])
    for row in report["timing"]:
        values = (row["arm"], row["split"], row["recorded_rows"], number(row["recorded_median_ms"]), number(row["recorded_mean_ms"]),
                  row["derived_rows"], number(row["derived_median_ms"]), number(row["derived_mean_ms"]), json.dumps(row["status"], sort_keys=True))
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines.extend(["", "## Not re-gradable files", ""])
    for source in report["not_regradable_files"]:
        provenance = f" (branch `{source['branch']}`, commit `{source['commit']}`)" if source.get("branch") else ""
        lines.append(f"- `{source['path']}`: {source['reason']}{provenance}.")
        for ref in source.get("references", []):
            lines.append(f"  - `{ref['path']}` — SHA-256: `{ref.get('sha256', 'not recorded')}`.")
    return "\n".join(lines) + "\n"
