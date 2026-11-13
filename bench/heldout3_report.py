"""Blind aggregates for the heldout3 script_first comparison.

Reads probe JSONL and prints totals only. It never prints a task id, a per-task
row, an answer, a URL, or a failure reason. It does not start a browser and it
does not call a model.

Units are fractions (0.20 is 20 percentage points). For each model the paired
difference is script_first minus browser_use: each task's pass rate is the mean
over its paired runs, then those per-task differences are averaged. The 95% CI
is a percentile bootstrap of 10,000 resamples clustered by site. A resample
draws sites with replacement and keeps every task on each drawn site.

Site is the registrable domain of the task start_url from bench/tasks.py and
any bench/tasks_heldout3_*.py. The rule is the last two host labels, unless the
last two are a common two-part suffix (co.uk, ac.uk, gov.uk, com.au, and the
other suffixes listed below), in which case the last three labels are used.
That list is not the public suffix list.

Self-check precision is P(graded pass | script_first end_state PASS) and recall
is P(end_state PASS | graded pass), pooled over paired script_first rows.
Dollar cost is total usd divided by total graded passes. Median wall time is
the median across tasks of each task's mean wall_ms over paired runs.

The hybrid, on each paired run, trusts script_first only when its own end_state
is PASS. Any other end_state (FAIL, UNKNOWN, or empty) falls back to
browser_use:

- pass when (end_state PASS and script_first graded pass) or (end_state is not
  PASS and browser_use graded pass);
- usd and wall_ms add the browser_use cost only when end_state is not PASS.

Decision labels follow docs/HELDOUT3_PLAN.md. The headline accuracy label and
the self-check bar use the primary model: a model whose name contains "luna",
or the only model in the files. Cheaper, faster, and hybrid-worth-building are
met only when every model in the files meets that bar. Fewer than 120 tasks on
any model is a pilot. The labels are still computed; a pilot is not a claim.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import statistics
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

SEED = 20261113
N_RESAMPLES = 10_000
PILOT_MIN_TASKS = 120
MARGIN = 0.10
PRECISION_BAR = 0.75
CHEAPER_RATIO = 0.5
FASTER_RATIO = 0.5
HYBRID_COST_RATIO = 0.6
HYBRID_RATE_SLACK = 0.02

ARM_SCRIPT = "script_first"
ARM_BROWSER = "browser_use"
BAR_SELF_CHECK = "The self-check is fit to use"
BAR_CHEAPER = "Cheaper"
BAR_FASTER = "Faster"
BAR_HYBRID = "Hybrid worth building"
BAR_NAMES = (BAR_SELF_CHECK, BAR_CHEAPER, BAR_FASTER, BAR_HYBRID)

# Common country-code second levels. Not a copy of the public suffix list.
_MULTI_PART_SUFFIXES = frozenset(
    {
        "ac.uk",
        "co.uk",
        "gov.uk",
        "ltd.uk",
        "me.uk",
        "net.uk",
        "nhs.uk",
        "org.uk",
        "plc.uk",
        "police.uk",
        "sch.uk",
        "com.au",
        "net.au",
        "org.au",
        "edu.au",
        "gov.au",
        "asn.au",
        "id.au",
        "co.nz",
        "net.nz",
        "org.nz",
        "govt.nz",
        "ac.nz",
        "school.nz",
        "co.jp",
        "ne.jp",
        "or.jp",
        "ac.jp",
        "go.jp",
        "com.br",
        "net.br",
        "org.br",
        "gov.br",
        "edu.br",
        "co.za",
        "org.za",
        "web.za",
        "gov.za",
        "ac.za",
        "net.za",
        "com.mx",
        "org.mx",
        "gob.mx",
        "edu.mx",
        "net.mx",
        "co.in",
        "net.in",
        "org.in",
        "ac.in",
        "gov.in",
        "gen.in",
        "firm.in",
        "ind.in",
        "com.sg",
        "net.sg",
        "org.sg",
        "edu.sg",
        "gov.sg",
        "com.hk",
        "net.hk",
        "org.hk",
        "edu.hk",
        "gov.hk",
        "com.tw",
        "net.tw",
        "org.tw",
        "edu.tw",
        "gov.tw",
        "co.kr",
        "ne.kr",
        "or.kr",
        "ac.kr",
        "go.kr",
        "com.cn",
        "net.cn",
        "org.cn",
        "gov.cn",
        "ac.cn",
        "com.tr",
        "net.tr",
        "org.tr",
        "gov.tr",
        "edu.tr",
        "co.il",
        "org.il",
        "ac.il",
        "gov.il",
        "net.il",
        "com.ar",
        "net.ar",
        "org.ar",
        "gov.ar",
        "co.id",
        "or.id",
        "ac.id",
        "go.id",
        "web.id",
        "com.my",
        "net.my",
        "org.my",
        "gov.my",
        "edu.my",
        "com.ph",
        "net.ph",
        "org.ph",
        "gov.ph",
        "com.pk",
        "net.pk",
        "org.pk",
        "gov.pk",
        "com.ng",
        "org.ng",
        "gov.ng",
        "co.th",
        "ac.th",
        "go.th",
        "or.th",
        "in.th",
        "com.vn",
        "net.vn",
        "org.vn",
        "gov.vn",
        "edu.vn",
        "com.co",
        "net.co",
        "nom.co",
        "gov.co",
        "com.pe",
        "gob.pe",
        "org.pe",
        "com.eg",
        "org.eg",
        "gov.eg",
        "edu.eg",
        "co.ke",
        "or.ke",
        "ac.ke",
        "go.ke",
        "com.sa",
        "net.sa",
        "org.sa",
        "gov.sa",
        "com.ua",
        "net.ua",
        "org.ua",
        "gov.ua",
        "com.pl",
        "net.pl",
        "org.pl",
        "gov.pl",
    }
)


class Skips(NamedTuple):
    no_arm: int = 0
    other_arm: int = 0
    incomplete: int = 0
    outside_task_list: int = 0


class Parsed(NamedTuple):
    file_index: int
    model: str
    arm: str
    task_id: str
    success: bool
    end_state: str
    usd: float
    wall: float


class Observation(NamedTuple):
    sf_success: bool
    bu_success: bool
    sf_end: str
    sf_usd: float
    bu_usd: float
    sf_wall: float
    bu_wall: float


class TaskStats(NamedTuple):
    site: str
    n: int
    sf_passes: int
    bu_passes: int
    hy_passes: int
    joint: int
    prec_den: int
    rec_den: int
    sf_usd: float
    bu_usd: float
    hy_usd: float
    sf_wall: float
    bu_wall: float
    hy_wall: float


def registrable_domain(url: str) -> str | None:
    """Last two host labels, or last three when the tail is a two-part suffix."""
    text = url.strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    host = urlsplit(text).hostname
    if not host:
        return None
    host = host.lower().rstrip(".")
    if _is_ip(host):
        return host
    labels = [part for part in host.split(".") if part]
    if len(labels) <= 2:
        return ".".join(labels) if labels else None
    suffix = ".".join(labels[-2:])
    if suffix in _MULTI_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return suffix


def _is_ip(host: str) -> bool:
    if ":" in host:
        return True
    parts = host.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        number = int(part)
        if number > 255:
            return False
    return True


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Linear percentile. pct is 0-100. An empty sample is None."""
    if not values:
        return None
    ordered = sorted(float(item) for item in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def normalize_end_state(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    if text in {"PASS", "FAIL", "UNKNOWN"}:
        return text
    return ""


def score_hybrid(
    sf_end: object,
    sf_success: bool,
    bu_success: bool,
    sf_usd: float,
    bu_usd: float,
    sf_wall: float,
    bu_wall: float,
) -> tuple[bool, float, float]:
    """Hybrid pass, usd, and wall for one paired run."""
    fallback = normalize_end_state(sf_end) != "PASS"
    passed = bu_success if fallback else sf_success
    cost = sf_usd + (bu_usd if fallback else 0.0)
    wall = sf_wall + (bu_wall if fallback else 0.0)
    return passed, cost, wall


def load_task_urls(heldout_dir: Path | None = None) -> dict[str, str]:
    """task id to start_url from bench.tasks and tasks_heldout3_*.py."""
    urls: dict[str, str] = {}
    import bench.tasks as tasks

    _collect_module(tasks, urls)
    directory = Path(tasks.__file__).resolve().parent if heldout_dir is None else heldout_dir
    for path in sorted(directory.glob("tasks_heldout3_*.py")):
        _collect_module(_load_module(path), urls)
    return urls


def _collect_module(module: object, urls: dict[str, str]) -> None:
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        _walk_tasks(value, urls, 0)


def _walk_tasks(value: object, urls: dict[str, str], depth: int) -> None:
    if depth > 4:
        return
    if isinstance(value, dict):
        task_id = value.get("id")
        start = value.get("start_url")
        if isinstance(task_id, str) and task_id and isinstance(start, str) and start:
            urls[task_id] = start
            return
        for item in value.values():
            _walk_tasks(item, urls, depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _walk_tasks(item, urls, depth + 1)


def _load_module(path: Path):
    name = f"bench._heldout3_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load task definitions from {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def read_jsonl(path: Path) -> list[dict]:
    """Objects from one JSONL file. The line text is never repeated on error."""
    if not path.is_file():
        _die(f"not a file: {path.name}")
    rows: list[dict] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                _die(f"{path.name}:{line_no}: invalid JSON")
            if isinstance(data, dict):
                rows.append(data)
    return rows


def read_task_list(path: Path) -> set[str]:
    if not path.is_file():
        _die(f"task list not found: {path.name}")
    found: set[str] = set()
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            text = line.split("#", 1)[0].strip()
            if text:
                found.add(text)
    return found


def _parse_files(
    files: Sequence[Sequence[Mapping]],
    task_ids: set[str] | None,
) -> tuple[dict[str, list[Parsed]], Skips]:
    grouped: dict[str, list[Parsed]] = {}
    no_arm = other_arm = incomplete = outside = 0
    for file_index, rows in enumerate(files):
        for row in rows:
            arm = row.get("arm")
            if not isinstance(arm, str) or not arm.strip():
                no_arm += 1
                continue
            arm = arm.strip()
            if arm not in (ARM_SCRIPT, ARM_BROWSER):
                other_arm += 1
                continue
            parsed = _parse_row(row, file_index, arm)
            if parsed is None:
                incomplete += 1
                continue
            if task_ids is not None and parsed.task_id not in task_ids:
                outside += 1
                continue
            grouped.setdefault(parsed.model, []).append(parsed)
    return grouped, Skips(no_arm, other_arm, incomplete, outside)


def _parse_row(row: Mapping, file_index: int, arm: str) -> Parsed | None:
    model = row.get("model")
    task_id = row.get("task_id")
    if not isinstance(model, str) or not model.strip():
        return None
    if not isinstance(task_id, str) or not task_id.strip():
        return None
    success = _as_bool(row.get("success"))
    if success is None:
        return None
    usd = 0.0 if "usd" not in row or row.get("usd") in (None, "") else _as_float(row.get("usd"))
    wall = 0.0 if "wall_ms" not in row or row.get("wall_ms") in (None, "") else _as_float(row.get("wall_ms"))
    if usd is None or wall is None:
        return None
    return Parsed(
        file_index=file_index,
        model=model.strip(),
        arm=arm,
        task_id=task_id.strip(),
        success=success,
        end_state=normalize_end_state(row.get("end_state")),
        usd=usd,
        wall=wall,
    )


def _first_by_task(rows: Sequence[Parsed]) -> tuple[dict[str, Parsed], int]:
    chosen: dict[str, Parsed] = {}
    dupes = 0
    for row in rows:
        if row.task_id in chosen:
            dupes += 1
            continue
        chosen[row.task_id] = row
    return chosen, dupes


def _pair_model(rows: Sequence[Parsed]) -> tuple[dict[str, list[Observation]], int, int, int]:
    """Pair script_first and browser_use by file order within one model.

    Each input file is one run. Files that contain an arm are that arm's runs,
    in the order the files were given. Run k of script_first is paired with
    run k of browser_use. Rows on the longer arm, rows whose task is missing
    on the other side, and duplicate rows in one file are dropped.
    """
    by_file: dict[tuple[int, str], list[Parsed]] = {}
    for row in rows:
        by_file.setdefault((row.file_index, row.arm), []).append(row)
    sf_files = [index for index, arm in sorted(by_file) if arm == ARM_SCRIPT]
    bu_files = [index for index, arm in sorted(by_file) if arm == ARM_BROWSER]
    n_pair = min(len(sf_files), len(bu_files))
    dropped = 0
    for index in sf_files[n_pair:]:
        dropped += len(by_file[(index, ARM_SCRIPT)])
    for index in bu_files[n_pair:]:
        dropped += len(by_file[(index, ARM_BROWSER)])
    paired: dict[str, list[Observation]] = {}
    for slot in range(n_pair):
        sf_map, sf_dupes = _first_by_task(by_file[(sf_files[slot], ARM_SCRIPT)])
        bu_map, bu_dupes = _first_by_task(by_file[(bu_files[slot], ARM_BROWSER)])
        dropped += sf_dupes + bu_dupes
        both = set(sf_map).intersection(bu_map)
        dropped += len(set(sf_map) - both)
        dropped += len(set(bu_map) - both)
        for task_id in both:
            sf = sf_map[task_id]
            bu = bu_map[task_id]
            paired.setdefault(task_id, []).append(
                Observation(
                    sf_success=sf.success,
                    bu_success=bu.success,
                    sf_end=sf.end_state,
                    sf_usd=sf.usd,
                    bu_usd=bu.usd,
                    sf_wall=sf.wall,
                    bu_wall=bu.wall,
                )
            )
    return paired, dropped, len(sf_files), len(bu_files)


def _task_stats(site: str, runs: Sequence[Observation]) -> TaskStats:
    sf_passes = bu_passes = hy_passes = 0
    joint = prec_den = rec_den = 0
    sf_usd = bu_usd = hy_usd = 0.0
    sf_wall = bu_wall = hy_wall = 0.0
    for run in runs:
        passed, cost, wall = score_hybrid(
            run.sf_end,
            run.sf_success,
            run.bu_success,
            run.sf_usd,
            run.bu_usd,
            run.sf_wall,
            run.bu_wall,
        )
        sf_usd += run.sf_usd
        bu_usd += run.bu_usd
        hy_usd += cost
        sf_wall += run.sf_wall
        bu_wall += run.bu_wall
        hy_wall += wall
        if run.sf_success:
            sf_passes += 1
            rec_den += 1
        if run.bu_success:
            bu_passes += 1
        if passed:
            hy_passes += 1
        if run.sf_end == "PASS":
            prec_den += 1
            if run.sf_success:
                joint += 1
    return TaskStats(
        site=site,
        n=len(runs),
        sf_passes=sf_passes,
        bu_passes=bu_passes,
        hy_passes=hy_passes,
        joint=joint,
        prec_den=prec_den,
        rec_den=rec_den,
        sf_usd=sf_usd,
        bu_usd=bu_usd,
        hy_usd=hy_usd,
        sf_wall=sf_wall,
        bu_wall=bu_wall,
        hy_wall=hy_wall,
    )


def _site_for(task_id: str, catalog: Mapping[str, str], unknown: dict[str, str]) -> str:
    url = catalog.get(task_id)
    if url:
        domain = registrable_domain(url)
        if domain:
            return domain
    existing = unknown.get(task_id)
    if existing is not None:
        return existing
    label = f"unlisted-{len(unknown) + 1}"
    unknown[task_id] = label
    return label


def _prepare(
    files: Sequence[Sequence[Mapping]],
    *,
    sites: Mapping[str, str] | None,
    task_ids: set[str] | None,
) -> tuple[dict[str, list[TaskStats]], dict[str, int], dict[str, tuple[int, int]], Skips]:
    grouped, skips = _parse_files(files, task_ids)
    catalog = load_task_urls() if sites is None else dict(sites)
    unknown: dict[str, str] = {}
    tasks_by_model: dict[str, list[TaskStats]] = {}
    dropped_by_model: dict[str, int] = {}
    runs_by_model: dict[str, tuple[int, int]] = {}
    for model in sorted(grouped):
        paired, dropped, n_sf, n_bu = _pair_model(grouped[model])
        stats: list[TaskStats] = []
        for task_id, runs in paired.items():
            site = _site_for(task_id, catalog, unknown)
            stats.append(_task_stats(site, runs))
        tasks_by_model[model] = stats
        dropped_by_model[model] = dropped
        runs_by_model[model] = (n_sf, n_bu)
    return tasks_by_model, dropped_by_model, runs_by_model, skips


def _point_estimates(tasks: Sequence[TaskStats]) -> dict[str, float | None]:
    count = len(tasks)
    diff = sf = bu = hy = 0.0
    joint = prec_den = rec_den = 0
    for task in tasks:
        diff += (task.sf_passes - task.bu_passes) / task.n
        sf += task.sf_passes / task.n
        bu += task.bu_passes / task.n
        hy += task.hy_passes / task.n
        joint += task.joint
        prec_den += task.prec_den
        rec_den += task.rec_den
    return {
        "diff": diff / count,
        "sf": sf / count,
        "bu": bu / count,
        "hy": hy / count,
        "precision": (joint / prec_den) if prec_den else None,
        "recall": (joint / rec_den) if rec_den else None,
    }


def _bootstrap(
    tasks: Sequence[TaskStats],
    *,
    clustered: bool,
    n_resamples: int,
    seed: int,
) -> dict[str, tuple[float | None, float | None]]:
    if clustered:
        by_site: dict[str, list[TaskStats]] = {}
        for task in tasks:
            by_site.setdefault(task.site, []).append(task)
        groups = [by_site[site] for site in sorted(by_site)]
    else:
        groups = [[task] for task in tasks]
    keys = ("diff", "sf", "bu", "hy", "precision", "recall")
    buckets: dict[str, list[float]] = {key: [] for key in keys}
    if not groups:
        return {key: (None, None) for key in keys}
    rng = random.Random(seed)
    n_groups = len(groups)
    for _ in range(n_resamples):
        sample: list[TaskStats] = []
        for _group in range(n_groups):
            sample.extend(groups[rng.randrange(n_groups)])
        point = _point_estimates(sample)
        for key in keys:
            value = point[key]
            if value is not None:
                buckets[key].append(value)
    return {
        key: (percentile(values, 2.5), percentile(values, 97.5)) if values else (None, None)
        for key, values in buckets.items()
    }


def _per_pass(total: float, passes: int) -> float | None:
    if passes <= 0:
        return None
    return total / passes


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _median_task_mean(tasks: Sequence[TaskStats], kind: str) -> float | None:
    if not tasks:
        return None
    values: list[float] = []
    for task in tasks:
        if kind == "sf":
            values.append(task.sf_wall / task.n)
        elif kind == "bu":
            values.append(task.bu_wall / task.n)
        else:
            values.append(task.hy_wall / task.n)
    return float(statistics.median(values))


def _ci_block(point: float | None, interval: tuple[float | None, float | None]) -> dict:
    low, high = interval
    if point is None or low is None or high is None:
        return {"estimate": point, "ci95": None}
    return {"estimate": point, "ci95": [low, high]}


def accuracy_label(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "inconclusive"
    if high < 0:
        return "behind"
    if low > 0:
        return "ahead"
    return "inconclusive"


def within_margin_label(low: float | None) -> str:
    if low is None:
        return "no"
    return "yes" if low > -MARGIN else "no"


def _ci_low(block: Mapping) -> float | None:
    ci = block.get("ci95")
    if not ci:
        return None
    return ci[0]


def _at_most(left: float | None, right: float | None, fraction: float) -> bool:
    if left is None or right is None:
        return False
    return left <= fraction * right


def _hybrid_bar_met(hybrid_low: float | None, bu_rate: float | None, hy_usd: float | None, bu_usd: float | None) -> bool:
    if hybrid_low is None or bu_rate is None or hy_usd is None or bu_usd is None:
        return False
    if not (hybrid_low > bu_rate - HYBRID_RATE_SLACK):
        return False
    return hy_usd <= HYBRID_COST_RATIO * bu_usd


def _met(flag: bool) -> str:
    return "met" if flag else "not met"


def _model_block(
    tasks: Sequence[TaskStats],
    *,
    dropped: int,
    n_sf: int,
    n_bu: int,
    n_resamples: int,
    seed: int,
) -> dict:
    point = _point_estimates(tasks) if tasks else {key: None for key in ("diff", "sf", "bu", "hy", "precision", "recall")}
    intervals = _bootstrap(tasks, clustered=True, n_resamples=n_resamples, seed=seed)
    sf_passes = sum(task.sf_passes for task in tasks)
    bu_passes = sum(task.bu_passes for task in tasks)
    hy_passes = sum(task.hy_passes for task in tasks)
    sf_usd = _per_pass(sum(task.sf_usd for task in tasks), sf_passes)
    bu_usd = _per_pass(sum(task.bu_usd for task in tasks), bu_passes)
    hy_usd = _per_pass(sum(task.hy_usd for task in tasks), hy_passes)
    sf_wall = _median_task_mean(tasks, "sf")
    bu_wall = _median_task_mean(tasks, "bu")
    hy_wall = _median_task_mean(tasks, "hy")
    diff_ci = intervals["diff"]
    low, high = diff_ci
    precision = _ci_block(point["precision"], intervals["precision"])
    hybrid = _ci_block(point["hy"], intervals["hy"])
    bars = {
        BAR_SELF_CHECK: _met(_ci_low(precision) is not None and _ci_low(precision) >= PRECISION_BAR),
        BAR_CHEAPER: _met(_at_most(sf_usd, bu_usd, CHEAPER_RATIO)),
        BAR_FASTER: _met(_at_most(sf_wall, bu_wall, FASTER_RATIO)),
        BAR_HYBRID: _met(_hybrid_bar_met(_ci_low(hybrid), point["bu"], hy_usd, bu_usd)),
    }
    return {
        "tasks": len(tasks),
        "sites": len({task.site for task in tasks}),
        "runs_script_first": n_sf,
        "runs_browser_use": n_bu,
        "runs_paired": min(n_sf, n_bu),
        "rows_dropped_missing_pairs": dropped,
        "paired_diff": _ci_block(point["diff"], diff_ci),
        "accuracy": accuracy_label(low, high),
        "within_10pp_margin": within_margin_label(low),
        "pass_rate": {
            ARM_SCRIPT: _ci_block(point["sf"], intervals["sf"]),
            ARM_BROWSER: _ci_block(point["bu"], intervals["bu"]),
        },
        "self_check": {
            "precision": precision,
            "recall": _ci_block(point["recall"], intervals["recall"]),
        },
        "usd_per_passed_task": {
            ARM_SCRIPT: sf_usd,
            ARM_BROWSER: bu_usd,
            "ratio_sf_over_bu": _ratio(sf_usd, bu_usd),
        },
        "median_wall_ms": {
            ARM_SCRIPT: sf_wall,
            ARM_BROWSER: bu_wall,
            "ratio_sf_over_bu": _ratio(sf_wall, bu_wall),
        },
        "hybrid": {
            "pass_rate": hybrid,
            "usd_per_passed_task": hy_usd,
            "ratio_to_bu": _ratio(hy_usd, bu_usd),
            "median_wall_ms": hy_wall,
        },
        "bars": bars,
    }


def select_primary(names: Sequence[str]) -> str | None:
    luna = sorted(name for name in names if "luna" in name.casefold())
    if luna:
        return luna[0]
    if len(names) == 1:
        return names[0]
    return None


def _headline_bars(models: Mapping[str, dict], primary: str | None) -> dict[str, str]:
    if not models:
        return {name: "not met" for name in BAR_NAMES}
    blocks = [models[name] for name in sorted(models)]
    self_check = "not met"
    if primary is not None:
        self_check = models[primary]["bars"][BAR_SELF_CHECK]
    cheaper = _met(all(block["bars"][BAR_CHEAPER] == "met" for block in blocks))
    faster = _met(all(block["bars"][BAR_FASTER] == "met" for block in blocks))
    hybrid = _met(all(block["bars"][BAR_HYBRID] == "met" for block in blocks))
    return {
        BAR_SELF_CHECK: self_check,
        BAR_CHEAPER: cheaper,
        BAR_FASTER: faster,
        BAR_HYBRID: hybrid,
    }


def build_report(
    files: Sequence[Sequence[Mapping]],
    *,
    sites: Mapping[str, str] | None = None,
    task_ids: set[str] | None = None,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
) -> dict:
    """Aggregate report. `sites` maps task id to start URL and replaces the catalog."""
    if n_resamples < 1:
        raise ValueError("n_resamples must be at least 1")
    tasks_by_model, dropped_by_model, runs_by_model, skips = _prepare(
        files, sites=sites, task_ids=task_ids
    )
    models: dict[str, dict] = {}
    for model, tasks in tasks_by_model.items():
        if not tasks and runs_by_model[model] == (0, 0):
            continue
        n_sf, n_bu = runs_by_model[model]
        models[model] = _model_block(
            tasks,
            dropped=dropped_by_model[model],
            n_sf=n_sf,
            n_bu=n_bu,
            n_resamples=n_resamples,
            seed=seed,
        )
    primary = select_primary(list(models))
    if primary is None:
        accuracy = "inconclusive"
        margin = "no"
        primary_tasks = 0
        primary_sites = 0
        primary_sf = 0
        primary_bu = 0
        primary_paired = 0
    else:
        block = models[primary]
        accuracy = block["accuracy"]
        margin = block["within_10pp_margin"]
        primary_tasks = block["tasks"]
        primary_sites = block["sites"]
        primary_sf = block["runs_script_first"]
        primary_bu = block["runs_browser_use"]
        primary_paired = block["runs_paired"]
    task_counts = [block["tasks"] for block in models.values()]
    pilot = (not task_counts) or any(count < PILOT_MIN_TASKS for count in task_counts)
    return {
        "seed": seed,
        "resamples": n_resamples,
        "pilot": pilot,
        "primary_model": primary,
        "accuracy": accuracy,
        "within_10pp_margin": margin,
        "bars": _headline_bars(models, primary),
        "counts": {
            "tasks": primary_tasks,
            "sites": primary_sites,
            "runs_script_first": primary_sf,
            "runs_browser_use": primary_bu,
            "runs_paired": primary_paired,
            "rows_dropped_missing_pairs": sum(dropped_by_model.values()),
            "rows_skipped_no_arm": skips.no_arm,
            "rows_skipped_other_arm": skips.other_arm,
            "rows_skipped_incomplete": skips.incomplete,
            "rows_outside_task_list": skips.outside_task_list,
        },
        "models": models,
    }


def diff_ci(
    files: Sequence[Sequence[Mapping]],
    *,
    sites: Mapping[str, str] | None = None,
    clustered: bool,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
) -> list[float | None]:
    """Paired-difference CI for a single-model file set. Tests compare clustering."""
    tasks_by_model, _, _, _ = _prepare(files, sites=sites, task_ids=None)
    if len(tasks_by_model) != 1:
        raise ValueError("diff_ci expects one model")
    tasks = next(iter(tasks_by_model.values()))
    low, high = _bootstrap(tasks, clustered=clustered, n_resamples=n_resamples, seed=seed)["diff"]
    return [low, high]


def _fmt(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _fmt_ci(value: object) -> str:
    if not value:
        return "none"
    low, high = value
    return f"[{_fmt(low)}, {_fmt(high)}]"


def render_report(report: Mapping) -> str:
    """Text form of the aggregate report. Labels and totals only."""
    lines = [
        f"seed: {_fmt(report['seed'])}",
        f"resamples: {_fmt(report['resamples'])}",
        f"pilot: {_fmt(report['pilot'])}",
        f"primary_model: {_fmt(report['primary_model'])}",
        f"accuracy: {report['accuracy']}",
        f"within_10pp_margin: {report['within_10pp_margin']}",
    ]
    for name in BAR_NAMES:
        lines.append(f"bar {name}: {report['bars'][name]}")
    counts = report["counts"]
    for key in (
        "tasks",
        "sites",
        "runs_script_first",
        "runs_browser_use",
        "runs_paired",
        "rows_dropped_missing_pairs",
        "rows_skipped_no_arm",
        "rows_skipped_other_arm",
        "rows_skipped_incomplete",
        "rows_outside_task_list",
    ):
        lines.append(f"counts {key}: {_fmt(counts[key])}")
    for model, block in report["models"].items():
        lines.append(f"model {model}")
        lines.extend(_render_model(block))
    return "\n".join(lines)


def _render_model(block: Mapping) -> list[str]:
    diff = block["paired_diff"]
    precision = block["self_check"]["precision"]
    recall = block["self_check"]["recall"]
    sf = block["pass_rate"][ARM_SCRIPT]
    bu = block["pass_rate"][ARM_BROWSER]
    hybrid = block["hybrid"]["pass_rate"]
    usd = block["usd_per_passed_task"]
    wall = block["median_wall_ms"]
    lines = [
        f"  tasks: {_fmt(block['tasks'])}",
        f"  sites: {_fmt(block['sites'])}",
        f"  runs_script_first: {_fmt(block['runs_script_first'])}",
        f"  runs_browser_use: {_fmt(block['runs_browser_use'])}",
        f"  runs_paired: {_fmt(block['runs_paired'])}",
        f"  rows_dropped_missing_pairs: {_fmt(block['rows_dropped_missing_pairs'])}",
        f"  paired_diff: {_fmt(diff['estimate'])}",
        f"  paired_diff_ci95: {_fmt_ci(diff['ci95'])}",
        f"  accuracy: {block['accuracy']}",
        f"  within_10pp_margin: {block['within_10pp_margin']}",
        f"  pass_rate_script_first: {_fmt(sf['estimate'])}",
        f"  pass_rate_script_first_ci95: {_fmt_ci(sf['ci95'])}",
        f"  pass_rate_browser_use: {_fmt(bu['estimate'])}",
        f"  pass_rate_browser_use_ci95: {_fmt_ci(bu['ci95'])}",
        f"  self_check_precision: {_fmt(precision['estimate'])}",
        f"  self_check_precision_ci95: {_fmt_ci(precision['ci95'])}",
        f"  self_check_recall: {_fmt(recall['estimate'])}",
        f"  self_check_recall_ci95: {_fmt_ci(recall['ci95'])}",
        f"  usd_per_passed_task_script_first: {_fmt(usd[ARM_SCRIPT])}",
        f"  usd_per_passed_task_browser_use: {_fmt(usd[ARM_BROWSER])}",
        f"  usd_ratio_sf_over_bu: {_fmt(usd['ratio_sf_over_bu'])}",
        f"  median_wall_ms_script_first: {_fmt(wall[ARM_SCRIPT])}",
        f"  median_wall_ms_browser_use: {_fmt(wall[ARM_BROWSER])}",
        f"  wall_ratio_sf_over_bu: {_fmt(wall['ratio_sf_over_bu'])}",
        f"  hybrid_pass_rate: {_fmt(hybrid['estimate'])}",
        f"  hybrid_pass_rate_ci95: {_fmt_ci(hybrid['ci95'])}",
        f"  hybrid_usd_per_passed_task: {_fmt(block['hybrid']['usd_per_passed_task'])}",
        f"  hybrid_usd_ratio_to_bu: {_fmt(block['hybrid']['ratio_to_bu'])}",
        f"  hybrid_median_wall_ms: {_fmt(block['hybrid']['median_wall_ms'])}",
    ]
    for name in BAR_NAMES:
        lines.append(f"  bar {name}: {block['bars'][name]}")
    return lines


def _row(
    arm: str,
    task_id: str,
    success: bool,
    *,
    model: str,
    end_state: str = "",
    usd: float = 1.0,
    wall_ms: float = 1.0,
    extra: Mapping | None = None,
) -> dict:
    row = {
        "arm": arm,
        "model": model,
        "task_id": task_id,
        "success": success,
        "end_state": end_state,
        "usd": usd,
        "wall_ms": wall_ms,
    }
    if extra:
        row.update(extra)
    return row


def _known_effect_files() -> tuple[list[list[dict]], tuple[str, ...]]:
    """Every task is script_first = browser_use + 0.2, with costs that clear the bars."""
    model = "gpt-6-luna"
    task_ids = tuple(f"zz-known-{index}" for index in range(6))
    files: list[list[dict]] = []
    secret = {
        "success_reason": "because-zz-secret-reason",
        "claimed_answer": "zz-secret-answer",
        "page_url": "https://zz-secret.example/path",
    }
    for run in range(5):
        rows: list[dict] = []
        bu_success = run != 4
        for task_id in task_ids:
            rows.append(
                _row(
                    ARM_SCRIPT,
                    task_id,
                    True,
                    model=model,
                    end_state="PASS",
                    usd=1.0,
                    wall_ms=10.0,
                    extra=secret,
                )
            )
            rows.append(
                _row(
                    ARM_BROWSER,
                    task_id,
                    bu_success,
                    model=model,
                    usd=10.0,
                    wall_ms=100.0,
                    extra=secret,
                )
            )
        files.append(rows)
    return files, task_ids


def _hybrid_files() -> tuple[list[list[dict]], tuple[str, ...]]:
    model = "synthetic"
    first = "zz-hybrid-1"
    second = "zz-hybrid-2"
    rows = [
        _row(ARM_SCRIPT, first, True, model=model, end_state="PASS", usd=2.0, wall_ms=100.0),
        _row(ARM_BROWSER, first, False, model=model, usd=4.0, wall_ms=50.0),
        _row(ARM_SCRIPT, second, False, model=model, end_state="FAIL", usd=2.0, wall_ms=100.0),
        _row(ARM_BROWSER, second, True, model=model, usd=4.0, wall_ms=400.0),
    ]
    return [rows], (first, second)


def _cluster_files() -> tuple[list[list[dict]], dict[str, str]]:
    """One site of identical +1 tasks and one site of identical -1 tasks."""
    model = "synthetic"
    sites: dict[str, str] = {}
    rows: list[dict] = []
    for index in range(20):
        task_id = f"zz-alpha-{index}"
        sites[task_id] = "https://alpha.test/item"
        rows.append(_row(ARM_SCRIPT, task_id, True, model=model, end_state="PASS"))
        rows.append(_row(ARM_BROWSER, task_id, False, model=model))
    for index in range(20):
        task_id = f"zz-beta-{index}"
        sites[task_id] = "https://beta.test/item"
        rows.append(_row(ARM_SCRIPT, task_id, False, model=model, end_state="FAIL"))
        rows.append(_row(ARM_BROWSER, task_id, True, model=model))
    return [rows], sites


def run_self_test() -> tuple[str, int]:
    """Synthetic checks. The returned text has aggregates only."""
    failures: list[str] = []
    known_files, known_ids = _known_effect_files()
    known = build_report(known_files)
    known_diff = known["models"]["gpt-6-luna"]["paired_diff"]
    if known["accuracy"] != "ahead":
        failures.append("known-effect-label")
    if known_diff["estimate"] is None or abs(known_diff["estimate"] - 0.2) > 1e-9:
        failures.append("known-effect-diff")
    ci = known_diff["ci95"]
    if not ci or abs(ci[0] - 0.2) > 1e-9 or abs(ci[1] - 0.2) > 1e-9 or not (ci[0] > 0):
        failures.append("known-effect-ci")
    if known["resamples"] != N_RESAMPLES:
        failures.append("resamples")

    hybrid_files, hybrid_ids = _hybrid_files()
    hybrid = build_report(hybrid_files, sites={})
    hybrid_block = hybrid["models"]["synthetic"]["hybrid"]
    if hybrid_block["pass_rate"]["estimate"] != 1.0:
        failures.append("hybrid-pass-rate")
    if hybrid_block["usd_per_passed_task"] != 4.0:
        failures.append("hybrid-usd")
    if hybrid_block["ratio_to_bu"] != 0.5:
        failures.append("hybrid-ratio")
    if hybrid_block["median_wall_ms"] != 300.0:
        failures.append("hybrid-wall")

    cluster_files, cluster_sites = _cluster_files()
    clustered = diff_ci(cluster_files, sites=cluster_sites, clustered=True)
    unclustered = diff_ci(cluster_files, sites=cluster_sites, clustered=False)
    if None in clustered or None in unclustered:
        failures.append("cluster-ci")
        clustered_width = None
        unclustered_width = None
    else:
        clustered_width = clustered[1] - clustered[0]
        unclustered_width = unclustered[1] - unclustered[0]
        if not (clustered_width > unclustered_width and clustered_width > 1.5 and unclustered_width < 1.2):
            failures.append("cluster-wider")

    wider = (
        clustered_width is not None
        and unclustered_width is not None
        and clustered_width > unclustered_width
    )
    text = "\n".join(
        [
            "known_effect",
            render_report(known),
            "hybrid_example",
            render_report(hybrid),
            "cluster_check",
            f"clustered_ci_width: {_fmt(clustered_width)}",
            f"unclustered_ci_width: {_fmt(unclustered_width)}",
            f"clustered_wider: {_fmt(wider)}",
        ]
    )
    forbidden = (
        *known_ids,
        *hybrid_ids,
        "zz-alpha-",
        "zz-beta-",
        "zz-known-",
        "zz-hybrid-",
        "because-zz-secret-reason",
        "zz-secret-answer",
        "zz-secret.example",
        "alpha.test",
        "beta.test",
    )
    for token in forbidden:
        if token in text:
            failures.append("blind")
            text = text.replace(token, "[redacted]")
    status = "self-test: ok" if not failures else "self-test: failed " + ",".join(failures)
    return text + "\n" + status, (0 if not failures else 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Blind aggregate report for heldout3. Prints totals only."
    )
    parser.add_argument("logs", nargs="*", type=Path, help="Probe JSONL files, one run each, in run order.")
    parser.add_argument("--tasks", type=Path, help="Task ids to keep, one per line. Other rows are excluded.")
    parser.add_argument("--json", type=Path, help="Also write the aggregates as JSON.")
    parser.add_argument("--self-test", action="store_true", help="Check the report on synthetic data.")
    args = parser.parse_args(argv)
    if args.self_test:
        if args.logs or args.tasks or args.json:
            print("self-test does not take logs, --tasks, or --json", file=sys.stderr)
            return 2
        text, code = run_self_test()
        print(text)
        return code
    if not args.logs:
        parser.error("pass probe JSONL files, or --self-test")
    files = [read_jsonl(path) for path in args.logs]
    task_ids = read_task_list(args.tasks) if args.tasks else None
    report = build_report(files, task_ids=task_ids)
    print(render_report(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
