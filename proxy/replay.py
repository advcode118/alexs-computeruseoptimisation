"""Sqlite cache of action sequences that do_task_segment has already finished.

A row is keyed by the page domain, a normalized task, and an order-independent
set of role/name pairs. Refs, typed values, control order, and controls with
an empty name are not part of the key. The file lives under the repo unless
REPLAY_CACHE_PATH or the cache_path argument points somewhere else.

Tradeoff against the old ordered list: a page whose controls move, or whose
accessible names stay the same while the DOM order changes, now hits. Two
buttons with the same role and name collapse to one entry, so a second
identical control does not change the key. An extra named control (a cookie
banner, a new result link) misses, and two different tasks that normalize to
the same string share a row. Normalization is casefold, collapsed whitespace,
and a stripped trailing period. It does not stem words or drop tokens, so
"search wikipedia" and "search wikiquote" stay apart. A wrong hit replays by
role and name; if a step cannot be refound, the page is left where it stopped
and the caller falls back to decide().
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from loop.actions import Observation

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = REPO_ROOT / "proxy" / "replay-cache.sqlite"
CACHE_ENV = "REPLAY_CACHE_PATH"

_CREATE = """
CREATE TABLE IF NOT EXISTS sequences (
    domain TEXT NOT NULL,
    task TEXT NOT NULL,
    shape TEXT NOT NULL,
    steps TEXT NOT NULL,
    PRIMARY KEY (domain, task, shape)
)
"""


def resolve_cache_path(override: str | os.PathLike[str] | None = None) -> Path:
    """Argument, then REPLAY_CACHE_PATH, then proxy/replay-cache.sqlite."""
    if override is not None and str(override).strip():
        return Path(override)
    env = os.environ.get(CACHE_ENV, "").strip()
    if env:
        return Path(env)
    return DEFAULT_CACHE_PATH


def page_domain(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.netloc:
        return parsed.netloc.casefold()
    if parsed.scheme:
        return parsed.scheme.casefold()
    return ""


def normalize_task(task: str) -> str:
    """Casefold, collapse whitespace, and drop one trailing sentence mark.

    "Search Wikipedia." and "  search wikipedia " share a key. The words
    themselves are kept, so nearby tasks do not collapse together.
    """
    text = re.sub(r"\s+", " ", task or "").strip().casefold()
    return text.rstrip(".!?")


def page_shape(observation: Observation) -> str:
    """Sorted unique role/name lines. Order, refs, and blank names are omitted.

    Duplicate role/name pairs count once. A control with no name is dropped
    because dynamic pages mint those freely. See the module docstring for
    what this misses compared with an ordered list.
    """
    pairs: set[str] = set()
    for control in observation.controls:
        role = re.sub(r"\s+", " ", control.role).strip().casefold()
        name = re.sub(r"\s+", " ", control.name).strip().casefold()
        if not name:
            continue
        pairs.add(f"{role}\t{name}")
    return "\n".join(sorted(pairs))


def cache_key(task: str, observation: Observation) -> tuple[str, str, str]:
    return (page_domain(observation.url), normalize_task(task), page_shape(observation))


def load_sequence(path: Path, domain: str, task: str, shape: str) -> dict | None:
    """The stored steps, or None when the file or the row is missing."""
    if not path.exists():
        return None
    try:
        with sqlite3.connect(path) as conn:
            _ensure(conn)
            row = conn.execute(
                "SELECT steps FROM sequences WHERE domain = ? AND task = ? AND shape = ?",
                (domain, task, shape),
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None or not isinstance(row[0], str):
        return None
    try:
        data = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def store_sequence(path: Path, domain: str, task: str, shape: str, steps: dict) -> None:
    """Insert or replace the sequence for this key. A write error is ignored."""
    payload = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            _ensure(conn)
            conn.execute(
                """
                INSERT INTO sequences (domain, task, shape, steps)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain, task, shape) DO UPDATE SET steps = excluded.steps
                """,
                (domain, task, shape, payload),
            )
    except (sqlite3.Error, OSError):
        return


def _ensure(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE)
