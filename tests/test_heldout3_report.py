"""Offline checks for the heldout3 aggregate report. No network and no model call."""

from __future__ import annotations

import json

import pytest

from bench.heldout3_report import (
    BAR_CHEAPER,
    BAR_FASTER,
    BAR_HYBRID,
    BAR_SELF_CHECK,
    N_RESAMPLES,
    PILOT_MIN_TASKS,
    SEED,
    build_report,
    diff_ci,
    load_task_urls,
    main,
    percentile,
    registrable_domain,
    render_report,
    score_hybrid,
)

SCRIPT = "script_first"
BROWSER = "browser_use"


def _row(arm, task_id, success, *, model="m", end_state="", usd=1.0, wall_ms=1.0, **extra):
    row = {
        "arm": arm,
        "model": model,
        "task_id": task_id,
        "success": success,
        "end_state": end_state,
        "usd": usd,
        "wall_ms": wall_ms,
    }
    row.update(extra)
    return row


def _blob(report) -> str:
    return render_report(report) + "\n" + json.dumps(report)


def test_registrable_domain_last_two_labels_and_two_part_suffixes():
    assert registrable_domain("https://en.wikipedia.org/wiki/Main_Page") == "wikipedia.org"
    assert registrable_domain("https://docs.python.org/3/") == "python.org"
    assert registrable_domain("https://news.ycombinator.com/") == "ycombinator.com"
    assert registrable_domain("https://developer.mozilla.org/en-US/") == "mozilla.org"
    assert registrable_domain("https://www.bbc.com/weather") == "bbc.com"
    assert registrable_domain("https://www.bbc.co.uk/news") == "bbc.co.uk"
    assert registrable_domain("https://news.cam.ac.uk/a") == "cam.ac.uk"
    assert registrable_domain("https://www.service.gov.uk/find") == "service.gov.uk"
    assert registrable_domain("https://www.example.com.au/x") == "example.com.au"
    assert registrable_domain("https://example.com") == "example.com"
    assert registrable_domain("http://localhost:8080/foo") == "localhost"
    assert registrable_domain("https://127.0.0.1/x") == "127.0.0.1"
    assert registrable_domain("file:///C:/fixture/packing.html") is None


def test_catalog_and_heldout3_modules_supply_start_urls(tmp_path):
    urls = load_task_urls()
    assert registrable_domain(urls["wv_wikipedia_search"]) == "wikipedia.org"
    assert registrable_domain(urls["wv_wikipedia_link"]) == "wikipedia.org"
    assert registrable_domain(urls["wv_bbc_weather"]) == "bbc.com"
    assert registrable_domain(urls["wv_hackernews_top"]) == "ycombinator.com"
    module = tmp_path / "tasks_heldout3_wave.py"
    module.write_text(
        "TASKS = [\n"
        "    {'id': 'zz-heldout3-uk', 'start_url': 'https://www.cam.ac.uk/'},\n"
        "]\n",
        encoding="utf-8",
    )
    loaded = load_task_urls(tmp_path)
    assert registrable_domain(loaded["zz-heldout3-uk"]) == "cam.ac.uk"
    assert registrable_domain(loaded["wv_python_docs"]) == "python.org"


def test_shared_suffix_is_one_site_and_ids_stay_out_of_the_report():
    files = [
        [
            _row(SCRIPT, "zz-a", True, end_state="PASS", model="m"),
            _row(BROWSER, "zz-a", False, model="m"),
            _row(SCRIPT, "zz-b", True, end_state="PASS", model="m"),
            _row(BROWSER, "zz-b", False, model="m"),
            _row(SCRIPT, "zz-c", False, end_state="FAIL", model="m"),
            _row(BROWSER, "zz-c", True, model="m"),
        ]
    ]
    sites = {
        "zz-a": "https://www.cam.ac.uk/a",
        "zz-b": "https://news.cam.ac.uk/b",
        "zz-c": "https://example.com/c",
    }
    report = build_report(files, sites=sites, n_resamples=20)
    block = report["models"]["m"]
    assert block["tasks"] == 3
    assert block["sites"] == 2
    blob = _blob(report)
    for token in ("zz-a", "zz-b", "zz-c", "cam.ac.uk", "example.com"):
        assert token not in blob


def test_real_catalog_tasks_share_a_site_without_leaking_ids():
    files = [
        [
            _row(SCRIPT, "wv_wikipedia_search", True, end_state="PASS"),
            _row(BROWSER, "wv_wikipedia_search", False),
            _row(SCRIPT, "wv_wikipedia_link", True, end_state="PASS"),
            _row(BROWSER, "wv_wikipedia_link", True),
            _row(SCRIPT, "wv_bbc_weather", False, end_state="FAIL"),
            _row(BROWSER, "wv_bbc_weather", True),
        ]
    ]
    report = build_report(files, n_resamples=20)
    assert report["counts"]["tasks"] == 3
    assert report["counts"]["sites"] == 2
    blob = _blob(report)
    assert "wv_wikipedia_search" not in blob
    assert "wv_wikipedia_link" not in blob
    assert "wv_bbc_weather" not in blob
    assert "wikipedia.org" not in blob
    assert "bbc.com" not in blob


def test_unknown_tasks_are_separate_sites():
    files = [
        [
            _row(SCRIPT, "zz-one", True, end_state="PASS"),
            _row(BROWSER, "zz-one", False),
            _row(SCRIPT, "zz-two", False, end_state="FAIL"),
            _row(BROWSER, "zz-two", True),
        ]
    ]
    report = build_report(files, sites={}, n_resamples=10)
    assert report["models"]["m"]["tasks"] == 2
    assert report["models"]["m"]["sites"] == 2


def test_known_effect_ci_is_ahead():
    files = []
    for run in range(5):
        rows = []
        for index in range(8):
            rows.append(_row(SCRIPT, f"zz-effect-{index}", True, end_state="PASS", model="solo"))
            rows.append(_row(BROWSER, f"zz-effect-{index}", run != 4, model="solo"))
        files.append(rows)
    report = build_report(files, sites={}, n_resamples=N_RESAMPLES, seed=SEED)
    diff = report["models"]["solo"]["paired_diff"]
    assert diff["estimate"] == pytest.approx(0.2)
    assert diff["ci95"][0] == pytest.approx(0.2)
    assert diff["ci95"][1] == pytest.approx(0.2)
    assert report["accuracy"] == "ahead"
    assert report["within_10pp_margin"] == "yes"
    assert report["resamples"] == 10_000
    assert report["seed"] == SEED
    blob = _blob(report)
    assert "zz-effect-" not in blob


def test_identical_site_cluster_widens_the_interval():
    sites = {}
    rows = []
    for index in range(20):
        task_id = f"zz-plus-{index}"
        sites[task_id] = "https://plus.example/item"
        rows.append(_row(SCRIPT, task_id, True, end_state="PASS"))
        rows.append(_row(BROWSER, task_id, False))
    for index in range(20):
        task_id = f"zz-minus-{index}"
        sites[task_id] = "https://minus.example/item"
        rows.append(_row(SCRIPT, task_id, False, end_state="FAIL"))
        rows.append(_row(BROWSER, task_id, True))
    files = [rows]
    clustered = diff_ci(files, sites=sites, clustered=True, n_resamples=N_RESAMPLES, seed=SEED)
    unclustered = diff_ci(files, sites=sites, clustered=False, n_resamples=N_RESAMPLES, seed=SEED)
    clustered_width = clustered[1] - clustered[0]
    unclustered_width = unclustered[1] - unclustered[0]
    assert clustered_width > 1.5
    assert unclustered_width < 1.2
    assert clustered_width > unclustered_width


def test_hybrid_arithmetic_on_two_tasks():
    files = [
        [
            _row(SCRIPT, "zz-h1", True, end_state="PASS", usd=2.0, wall_ms=100.0),
            _row(BROWSER, "zz-h1", False, usd=4.0, wall_ms=50.0),
            _row(SCRIPT, "zz-h2", False, end_state="FAIL", usd=2.0, wall_ms=100.0),
            _row(BROWSER, "zz-h2", True, usd=4.0, wall_ms=400.0),
        ]
    ]
    report = build_report(files, sites={}, n_resamples=30)
    block = report["models"]["m"]
    hybrid = block["hybrid"]
    assert hybrid["pass_rate"]["estimate"] == 1.0
    assert hybrid["pass_rate"]["ci95"] == [1.0, 1.0]
    assert hybrid["usd_per_passed_task"] == 4.0
    assert hybrid["ratio_to_bu"] == 0.5
    assert hybrid["median_wall_ms"] == 300.0
    assert block["pass_rate"][SCRIPT]["estimate"] == 0.5
    assert block["pass_rate"][BROWSER]["estimate"] == 0.5
    assert block["paired_diff"]["estimate"] == 0.0
    assert block["usd_per_passed_task"][BROWSER] == 8.0
    blob = _blob(report)
    assert "zz-h1" not in blob
    assert "zz-h2" not in blob


def test_hybrid_falls_back_unless_end_state_is_pass():
    assert score_hybrid("PASS", True, False, 2, 9, 10, 90) == (True, 2, 10)
    assert score_hybrid("PASS", False, True, 4, 8, 4, 8) == (False, 4, 4)
    assert score_hybrid("FAIL", False, True, 2, 4, 100, 400) == (True, 6, 500)
    assert score_hybrid("UNKNOWN", False, True, 3, 5, 7, 11) == (True, 8, 18)
    assert score_hybrid("", True, False, 1, 9, 1, 9) == (False, 10, 10)
    assert score_hybrid("pass", True, False, 1, 1, 1, 1) == (True, 1, 1)


def test_self_check_precision_and_recall():
    # One task, four runs: precision 1/2, recall 1/2.
    files = []
    ends = [("PASS", True), ("PASS", False), ("FAIL", True), ("FAIL", False)]
    for end_state, success in ends:
        files.append(
            [
                _row(SCRIPT, "zz-check", success, end_state=end_state, model="m"),
                _row(BROWSER, "zz-check", False, model="m"),
            ]
        )
    report = build_report(files, sites={}, n_resamples=20)
    check = report["models"]["m"]["self_check"]
    assert check["precision"]["estimate"] == pytest.approx(0.5)
    assert check["recall"]["estimate"] == pytest.approx(0.5)
    assert check["precision"]["ci95"][0] == pytest.approx(0.5)
    assert report["bars"][BAR_SELF_CHECK] == "not met"


def test_decision_labels_for_exact_intervals():
    def report_for(sf_success, bu_success, model="solo"):
        rows = [
            _row(SCRIPT, "zz-label", sf_success, end_state="PASS" if sf_success else "FAIL", model=model),
            _row(BROWSER, "zz-label", bu_success, model=model),
        ]
        return build_report([rows], sites={}, n_resamples=15)

    ahead = report_for(True, False)
    assert ahead["accuracy"] == "ahead"
    assert ahead["within_10pp_margin"] == "yes"

    behind = report_for(False, True)
    assert behind["models"]["solo"]["paired_diff"]["estimate"] == -1.0
    assert behind["accuracy"] == "behind"
    assert behind["within_10pp_margin"] == "no"

    files = []
    # Five runs, script_first passes 4 and browser_use passes 5: difference -0.2.
    # A second construction with difference -0.05 needs more runs; use 20 runs
    # where script_first fails one and browser_use fails none: diff = -0.05.
    for run in range(20):
        files.append(
            [
                _row(SCRIPT, "zz-margin", run != 0, end_state="PASS", model="solo"),
                _row(BROWSER, "zz-margin", True, model="solo"),
            ]
        )
    close = build_report(files, sites={}, n_resamples=15)
    assert close["models"]["solo"]["paired_diff"]["estimate"] == pytest.approx(-0.05)
    assert close["accuracy"] == "behind"
    assert close["within_10pp_margin"] == "yes"

    tied = report_for(True, True)
    assert tied["accuracy"] == "inconclusive"
    assert tied["within_10pp_margin"] == "yes"


def test_bars_use_luna_for_self_check_and_every_model_for_cost():
    def both(model, sf_usd, sf_wall, bu_usd, bu_wall):
        return [
            _row(SCRIPT, "zz-bar", True, end_state="PASS", model=model, usd=sf_usd, wall_ms=sf_wall),
            _row(BROWSER, "zz-bar", True, model=model, usd=bu_usd, wall_ms=bu_wall),
        ]

    # Every Luna task has the same +0.2 difference, so the clustered interval
    # stays above 0. Sol is tied and no cheaper, so the shared cost bars fail.
    luna_files = []
    sol_files = []
    for run in range(5):
        luna_rows = []
        sol_rows = []
        for index in range(4):
            luna_rows.append(
                _row(SCRIPT, f"zz-luna-{index}", True, end_state="PASS", model="gpt-6-luna", usd=1, wall_ms=10)
            )
            luna_rows.append(
                _row(BROWSER, f"zz-luna-{index}", run != 4, model="gpt-6-luna", usd=10, wall_ms=100)
            )
            sol_rows.append(
                _row(SCRIPT, f"zz-sol-{index}", True, end_state="PASS", model="gpt-6.1-sol", usd=10, wall_ms=100)
            )
            sol_rows.append(
                _row(BROWSER, f"zz-sol-{index}", True, model="gpt-6.1-sol", usd=10, wall_ms=100)
            )
        luna_files.append(luna_rows)
        sol_files.append(sol_rows)
    report = build_report(luna_files + sol_files, sites={}, n_resamples=20)
    assert report["primary_model"] == "gpt-6-luna"
    assert report["accuracy"] == "ahead"
    assert report["models"]["gpt-6.1-sol"]["accuracy"] == "inconclusive"
    assert report["models"]["gpt-6-luna"]["bars"][BAR_CHEAPER] == "met"
    assert report["models"]["gpt-6.1-sol"]["bars"][BAR_CHEAPER] == "not met"
    assert report["bars"][BAR_CHEAPER] == "not met"
    assert report["bars"][BAR_FASTER] == "not met"
    assert report["bars"][BAR_SELF_CHECK] == "met"
    assert report["bars"][BAR_SELF_CHECK] == report["models"]["gpt-6-luna"]["bars"][BAR_SELF_CHECK]

    cheap = both("gpt-6-luna", 1, 10, 10, 100)
    report = build_report([cheap], sites={}, n_resamples=20)
    # Both arms pass, so the difference is inconclusive, but the cost bars hold.
    # Hybrid equals script_first because the self-check passed, and browser_use
    # also passed, so the hybrid rate clears the 2pp slack and the 0.6 cost ratio.
    assert report["bars"][BAR_CHEAPER] == "met"
    assert report["bars"][BAR_FASTER] == "met"
    assert report["bars"][BAR_HYBRID] == "met"
    assert report["accuracy"] == "inconclusive"

    costly = [
        _row(SCRIPT, "zz-cost", False, end_state="FAIL", model="gpt-6-luna", usd=10, wall_ms=10),
        _row(BROWSER, "zz-cost", True, model="gpt-6-luna", usd=10, wall_ms=100),
    ]
    report = build_report([costly], sites={}, n_resamples=20)
    assert report["bars"][BAR_HYBRID] == "not met"


def test_pairing_follows_arm_order_and_counts_missing_pairs():
    files = [
        [_row(SCRIPT, "zz-a", True, end_state="PASS")],
        [_row(BROWSER, "zz-a", False)],
        [_row(BROWSER, "zz-a", True)],
        [_row(SCRIPT, "zz-a", False, end_state="FAIL")],
        [_row(SCRIPT, "zz-a", True, end_state="PASS")],
    ]
    report = build_report(files, sites={}, n_resamples=10)
    block = report["models"]["m"]
    assert block["runs_script_first"] == 3
    assert block["runs_browser_use"] == 2
    assert block["runs_paired"] == 2
    assert block["rows_dropped_missing_pairs"] == 1
    assert block["pass_rate"][SCRIPT]["estimate"] == 0.5
    assert block["pass_rate"][BROWSER]["estimate"] == 0.5
    assert block["tasks"] == 1

    same_file = [
        [
            _row(SCRIPT, "zz-a", True, end_state="PASS"),
            _row(SCRIPT, "zz-a", False, end_state="FAIL"),
            _row(BROWSER, "zz-a", False),
            _row(SCRIPT, "zz-b", True, end_state="PASS"),
            _row(BROWSER, "zz-only-bu", True),
        ]
    ]
    report = build_report(same_file, sites={}, n_resamples=10)
    block = report["models"]["m"]
    assert block["tasks"] == 1
    assert block["rows_dropped_missing_pairs"] == 3
    assert block["paired_diff"]["estimate"] == 1.0


def test_task_list_excludes_rows_before_pairing(tmp_path):
    files = [
        [
            _row(SCRIPT, "zz-keep", True, end_state="PASS"),
            _row(BROWSER, "zz-keep", False),
            _row(SCRIPT, "zz-drop", False, end_state="FAIL"),
            _row(BROWSER, "zz-drop", True),
        ]
    ]
    report = build_report(files, sites={}, task_ids={"zz-keep"}, n_resamples=10)
    assert report["models"]["m"]["tasks"] == 1
    assert report["counts"]["rows_outside_task_list"] == 2
    assert report["counts"]["rows_dropped_missing_pairs"] == 0

    listed = tmp_path / "tasks.txt"
    listed.write_text("# comment\nzz-keep\n\n", encoding="utf-8")
    log = tmp_path / "run.jsonl"
    with log.open("w", encoding="utf-8") as handle:
        for row in files[0]:
            handle.write(json.dumps(row) + "\n")
        handle.write(json.dumps({"kind": "arm_report", "report": {}}) + "\n")
        handle.write(json.dumps(_row("playwright_mcp", "zz-keep", True)) + "\n")
        handle.write(json.dumps({"arm": "script_first", "model": "m"}) + "\n")
    out = tmp_path / "out.json"
    assert main([str(log), "--tasks", str(listed), "--json", str(out)]) == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["counts"]["tasks"] == 1
    assert saved["counts"]["rows_outside_task_list"] == 2
    assert saved["counts"]["rows_skipped_no_arm"] == 1
    assert saved["counts"]["rows_skipped_other_arm"] == 1
    assert saved["counts"]["rows_skipped_incomplete"] == 1
    blob = out.read_text(encoding="utf-8")
    assert "zz-keep" not in blob
    assert "zz-drop" not in blob


def test_output_omits_answers_urls_and_reasons(capsys, tmp_path):
    secret_id = "zz-SECRET-task"
    reason = "because-SECRET-reason"
    answer = "SECRET-answer-value"
    url = "https://secret.example/hidden"
    log = tmp_path / "probe.jsonl"
    log.write_text(
        json.dumps(
            _row(
                SCRIPT,
                secret_id,
                True,
                end_state="PASS",
                success_reason=reason,
                claimed_answer=answer,
                page_url=url,
            )
        )
        + "\n"
        + json.dumps(_row(BROWSER, secret_id, False, page_url=url))
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    assert main([str(log), "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    saved = out.read_text(encoding="utf-8")
    for token in (secret_id, reason, answer, url, "secret.example", "hidden"):
        assert token not in printed
        assert token not in saved
    report = json.loads(saved)
    assert report["accuracy"] == "ahead"


def test_invalid_json_does_not_echo_the_line(capsys, tmp_path):
    log = tmp_path / "bad.jsonl"
    log.write_text('{"task_id": "zz-SECRET-task"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        main([str(log)])
    assert caught.value.code == 2
    err = capsys.readouterr().err
    assert "invalid JSON" in err
    assert "zz-SECRET-task" not in err


def test_pilot_threshold_is_120_tasks():
    def files_for(count):
        rows = []
        for index in range(count):
            rows.append(_row(SCRIPT, f"zz-n-{index}", True, end_state="PASS"))
            rows.append(_row(BROWSER, f"zz-n-{index}", False))
        return [rows]

    small = build_report(files_for(PILOT_MIN_TASKS - 1), sites={}, n_resamples=2)
    large = build_report(files_for(PILOT_MIN_TASKS), sites={}, n_resamples=2)
    assert PILOT_MIN_TASKS == 120
    assert small["pilot"] is True
    assert large["pilot"] is False
    assert large["counts"]["tasks"] == 120
    assert large["accuracy"] == "ahead"


def test_empty_input_is_inconclusive():
    report = build_report([[]], n_resamples=5)
    assert report["models"] == {}
    assert report["accuracy"] == "inconclusive"
    assert report["within_10pp_margin"] == "no"
    assert report["pilot"] is True
    assert all(value == "not met" for value in report["bars"].values())
    assert report["counts"]["rows_dropped_missing_pairs"] == 0


def test_percentile_interpolates():
    assert percentile([1.0], 2.5) == 1.0
    assert percentile([], 50) is None
    # rank = 3 * 0.5 = 1.5, halfway between the 2nd and 3rd sorted values.
    assert percentile([10, 20, 30, 40], 50) == pytest.approx(25)


def test_self_test_flag(capsys):
    assert main(["--self-test"]) == 0
    printed = capsys.readouterr().out
    assert "accuracy: ahead" in printed
    assert "paired_diff: 0.200000" in printed
    assert "hybrid_usd_per_passed_task: 4.000000" in printed
    assert "hybrid_usd_ratio_to_bu: 0.500000" in printed
    assert "clustered_wider: yes" in printed
    assert "self-test: ok" in printed
    assert "zz-known-" not in printed
    assert "zz-hybrid-" not in printed
    assert "zz-secret" not in printed
    assert main(["--self-test", "probe.jsonl"]) == 2


def test_rebase_arm_swaps_in_the_named_baseline():
    from bench.heldout3_report import rebase_arm

    rows = [
        {"arm": "script_first", "task_id": "t"},
        {"arm": "browser_use", "task_id": "t"},
        {"arm": "playwright_mcp", "task_id": "t"},
    ]
    out = rebase_arm(rows, "playwright_mcp")
    assert [r["arm"] for r in out] == ["script_first", "browser_use"]
    assert rows[2]["arm"] == "playwright_mcp"
