"""Keep the replay cache out of the repo during the suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_replay_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("REPLAY_CACHE_PATH", str(tmp_path / "replay-cache.sqlite"))


@pytest.fixture(autouse=True)
def no_start_page_fetch(monkeypatch):
    """Offline suite: script_first's start-page summary never touches the network."""
    monkeypatch.setenv("CU_PAGE_SUMMARY", "0")
