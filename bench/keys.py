"""Load the live loop's Nebius and Claude keys. Never print the secrets."""

from __future__ import annotations

import os
from pathlib import Path

from loop.actions import PlannerError

_PROVIDER_KEYS = ("NEBIUS_API_KEY", "ANTHROPIC_API_KEY")


def live_env_path() -> Path | None:
    """The env file the live loop already uses. Both providers live there."""
    override = os.environ.get("BENCH_ENV_FILE")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.append(Path.home() / "Projects" / "nebiustaskwipe" / "backend" / ".env")
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_live_keys() -> dict:
    """Put Nebius and Claude keys into the process. Return which ones are set.

    Values already in the environment stay as they are. The returned dict has
    no secrets.
    """
    path = live_env_path()
    if path is not None:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key or not value:
                continue
            if not os.environ.get(key):
                os.environ[key] = value
    present = {name: bool(os.environ.get(name)) for name in _PROVIDER_KEYS}
    if not any(present.values()):
        raise PlannerError(
            "Neither NEBIUS_API_KEY nor ANTHROPIC_API_KEY is present. "
            "A counted bench needs the live loop env file."
        )
    return {
        "env_file_loaded": path is not None,
        "nebius": present["NEBIUS_API_KEY"],
        "anthropic": present["ANTHROPIC_API_KEY"],
    }


def redact(text: str) -> str:
    """Remove loaded secrets from a string before it is logged."""
    cleaned = text
    for name in ("NEBIUS_API_KEY", "ANTHROPIC_API_KEY", "LOOP_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY"):
        value = os.environ.get(name) or ""
        if len(value) >= 8:
            cleaned = cleaned.replace(value, "[redacted]")
    return cleaned
