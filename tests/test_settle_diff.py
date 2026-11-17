"""Shared Stagehand settle policy. No API key, browser, or network."""

from __future__ import annotations


from proxy.settle import (
    FAST_CAP_MS,
    FAST_QUIET_MS,
    QUIET_MS,
    SETTLE_TIMEOUT_MS,
    configured_quiet_ms,
    configured_timeout_ms,
    decide_settle,
    mutation_is_meaningful,
    parse_settle_result,
    plan_settle,
    settle_source,
)


def test_default_quiet_wait_is_500ms(monkeypatch):
    assert QUIET_MS == 500
    assert SETTLE_TIMEOUT_MS == 3000
    assert "const quietMs = 500" in settle_source()
    assert "const timeoutMs = 3000" in settle_source()
    assert configured_quiet_ms() == 500
    assert configured_timeout_ms() == 3000
    monkeypatch.setenv("SETTLE_QUIET_MS", "250")
    monkeypatch.setenv("SETTLE_TIMEOUT_MS", "4000")

    source = settle_source(configured_quiet_ms(), configured_timeout_ms())
    assert "const quietMs = 250" in source
    assert "const timeoutMs = 4000" in source
    monkeypatch.setenv("SETTLE_QUIET_MS", "nope")
    assert configured_quiet_ms() == 500


def test_settle_times_out_while_the_page_keeps_mutating():
    events = [(time_ms, True) for time_ms in range(0, 2000, 50)]
    assert decide_settle(events, quiet_ms=100, timeout_ms=1500) == "timeout"
    assert decide_settle([], quiet_ms=100, timeout_ms=1500) == "quiet"
    parsed = parse_settle_result('### Result\n{"settled": false, "reason": "timeout"}')
    assert parsed == {"settled": False, "reason": "timeout"}


def test_settle_ignores_mutations_that_do_not_change_the_tree():
    assert mutation_is_meaningful({"type": "attributes", "attribute": "style", "tag": "div"}) is False
    assert mutation_is_meaningful({"type": "attributes", "attribute": "class", "tag": "div"}) is False
    assert mutation_is_meaningful({"type": "attributes", "attribute": "data-id", "tag": "div"}) is False
    assert mutation_is_meaningful({"type": "childList", "tag": "script"}) is False
    assert mutation_is_meaningful({"type": "childList", "tag": "div"}) is True
    assert mutation_is_meaningful({"type": "attributes", "attribute": "aria-expanded", "tag": "button"}) is True
    # style/class/script noise does not push a quiet page out to the timeout
    noisy = [(0, True), (40, False), (80, False), (500, False), (1200, False)]
    assert decide_settle(noisy, quiet_ms=100, timeout_ms=1500) == "quiet"


def test_fast_path_does_not_skip_a_page_that_is_still_mutating():
    """A short page keeps the 500ms quiet window while meaningful mutations continue."""
    mutating = [(time_ms, True) for time_ms in range(0, 1500, 40)]
    reason, end = plan_settle(
        mutating,
        quiet_ms=500,
        timeout_ms=1500,
        short=True,
        network_quiet_ms=0,
    )
    assert reason == "timeout"
    assert end == 1500
    assert end > FAST_CAP_MS
    assert decide_settle(mutating, quiet_ms=500, timeout_ms=1500, short=True, network_quiet_ms=0) == "timeout"

    stopped = [(time_ms, True) for time_ms in range(0, 200, 40)]
    reason, end = plan_settle(stopped, quiet_ms=500, timeout_ms=3000, short=True)
    assert reason == "quiet"
    assert end == 160 + 500

    reason, end = plan_settle(
        stopped,
        quiet_ms=500,
        timeout_ms=3000,
        short=True,
        network_quiet_ms=400,
    )
    assert reason == "quiet"
    assert end == 400 + FAST_QUIET_MS
    assert end < 160 + 500

    reason, end = plan_settle([], quiet_ms=500, timeout_ms=3000, short=True)
    assert reason == "quiet"
    assert end == FAST_CAP_MS
    assert end < 500

    reason, end = plan_settle([], quiet_ms=500, timeout_ms=3000, short=False)
    assert reason == "quiet"
    assert end == 500
    assert "const fastCapMs = 100" in settle_source()
    assert "const quietMs = 500" in settle_source()
