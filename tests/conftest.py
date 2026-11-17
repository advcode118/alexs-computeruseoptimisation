"""Keep the replay cache out of the repo during the suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_replay_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("REPLAY_CACHE_PATH", str(tmp_path / "replay-cache.sqlite"))
