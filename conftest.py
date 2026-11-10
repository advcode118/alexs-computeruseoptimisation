"""Suite-wide isolation. The shared spend ledger is never the developer's file."""

from __future__ import annotations

import pytest

from bench.budget import SpendLedger


@pytest.fixture(autouse=True)
def isolated_spend_ledger(tmp_path, monkeypatch):
    path = tmp_path / "cu-spend.json"
    ledger = SpendLedger.seed(path)
    ledger.save()
    monkeypatch.setenv("CU_SPEND_LEDGER", str(path))
    return path


@pytest.fixture(autouse=True)
def isolated_openai_spend_ledger(tmp_path, monkeypatch):
    path = tmp_path / "openai-spend.json"
    monkeypatch.setenv("CU_OPENAI_SPEND_LEDGER", str(path))
    return path
