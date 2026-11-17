"""Offline heldout4 provenance, isolation and sealing contracts; no models."""

import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from bench import tasks_heldout4
from bench.browser_use_arm import task_text
from bench.ext_sample import QUOTAS, SOURCES, authoring_reserve, effective_authoring_decisions, registrable, task_fingerprint
from bench.tasks import get_all_tasks, resolve_task_split, task_message, tasks_for_split
from bench.verify_heldout4 import Observation, control, grade_observation, observe, pdf_text, run_steps, summarize

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/ext_sample_20261116"
EXCLUSIONS = {"login", "payment", "captcha_or_bot_block", "site_gone_or_content_gone",
              "volatile_lt_1day", "no_checkable_key", "site_cap", "duplicate_task"}


def read(name):
    return [json.loads(line) for line in (RESULTS / name).read_text().splitlines()]


def authored():
    return getattr(tasks_heldout4, "ALL_HELDOUT4_TASKS", tasks_heldout4.HELDOUT4_TASKS)


def sites(task):
    hosts = {urlsplit(task.get("start_url", "")).hostname}
    marker = task.get("end_markers", {}).get("host", [])
    hosts.update([marker] if isinstance(marker, str) else marker)
    return {registrable(host) for host in hosts if host}


@pytest.mark.parametrize("stem,count", [
    ("verification_heldout4_20261117T100724469791Z", 4),
    ("verification_heldout4_full_2", 5),
])
def test_artifact_manifests_preserve_capture_hashes_and_sources(stem, count):
    manifest_path = RESULTS / (stem + ".artifacts.json")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_records"] == str((RESULTS / (stem + ".jsonl")).relative_to(ROOT))
    assert "recorded when downloaded or printed" in manifest["hash_provenance"]
    recorded = {}
    with (RESULTS / (stem + ".jsonl")).open() as records:
        for line in records:
            row = json.loads(line)
            for field, entries in row.items():
                if field.endswith("_artifacts"):
                    for entry in entries:
                        source = entry.get("observed_url") or row[field.replace("_artifacts", "_observation")]["url"]
                        recorded[entry["path"]] = (entry["bytes"], entry["sha256"], source)
    assert len(recorded) == len(manifest["artifacts"]) == count
    assert {entry["path"] for entry in manifest["artifacts"]} == set(recorded)
    for entry in manifest["artifacts"]:
        assert (entry["bytes"], entry["sha256"], entry["source_url"]) == recorded[entry["path"]]
        assert urlsplit(entry["source_url"]).scheme in {"http", "https"}
        assert entry["bytes"] > 0
        assert len(bytes.fromhex(entry["sha256"])) == 32
    summary = json.loads((RESULTS / (stem + ".summary.json")).read_text())
    assert summary["artifact_manifest"] == str(manifest_path.relative_to(ROOT))


def test_schema_ids_registration_and_complete_provenance():
    tasks = tasks_for_split("heldout4")
    assert resolve_task_split("heldout4") == "heldout4"
    assert tuple(t["id"] for t in tasks) == tasks_heldout4.HELDOUT4_TASK_IDS
    assert len(authored()) == 130
    assert 120 <= len(tasks) <= 130
    assert len({t["id"] for t in authored()}) == 130
    candidates = {(r["source"], r["source_id"]): r for r in read("candidates_heldout4.jsonl")}
    catalog = Counter(t["id"] for t in get_all_tasks())
    for task in authored():
        assert task["id"].startswith("ho4_")
        assert task["id"].split("_")[1] == task["kind"]
        assert task["kind"] in {"nav", "value", "search", "filter", "form", "spa", "multisite"}
        assert {"description", "start_url", "expected_answer", "full_answer", "answer_parts",
                "answer_type", "end_state", "grader_flags", "url_answer_ok", "end_markers",
                "check_url_contains", "source", "source_id", "licence", "text_edits",
                "reproducer", "key_scope", "answer_part_sources"} <= task.keys()
        candidate = candidates[task["source"], task["source_id"]]
        description = candidate["task_text"]
        for edit in task["text_edits"]:
            assert edit["old"] in description
            description = description.replace(edit["old"], edit["new"])
        assert task["description"] == description
        assert task["start_url"] == candidate["start_url"]
        assert task["licence"] == ("CC-BY-4.0" if task["source"] in {"Mind2Web-Live", "Mind2Web"} else "Apache-2.0")
        assert task["reproducer"] in {"script", "none"}
        assert task["key_scope"] in {"full", "partial"}
        assert "unchecked_fragments" not in task
        assert task["expected_answer"] == task["full_answer"]
        assert task["full_answer"].strip()
        assert task["answer_type"] in {"text", "url"}
        assert task["end_state"] in {"page", "search_results"}
        assert task["url_answer_ok"] is (task["answer_type"] == "url")
        assert isinstance(task["answer_parts"], list)
        assert all(isinstance(p, str) and p.strip() for p in task["answer_parts"])
        assert isinstance(task["grader_flags"], list)
        assert task["grader_flags"] == sorted(set(task["grader_flags"]))
        assert all(isinstance(flag, str) and flag for flag in task["grader_flags"])
        assert task["check_url_contains"] == task["end_markers"]["url_contains"]
        assert "host" in task["end_markers"]
        assert not any("search" in value for value in task["end_markers"]["deny"])
        if task["answer_type"] == "url":
            assert urlsplit(task["full_answer"]).scheme in {"http", "https"}
            assert task["answer_parts"] == []
        else:
            assert task["answer_parts"]
            unscored = task.get("unscored_parts", [])
            assert {s["part"] for s in task["answer_part_sources"]} == set(task["answer_parts"]) | {s["part"] for s in unscored}
            if "multi_page_parts" in task["grader_flags"]:
                assert task["key_scope"] == "partial"
                assert unscored
                assert not set(task["answer_parts"]) & {s["part"] for s in unscored}
                assert all(s in task["answer_part_sources"] for s in unscored)
            for source in task["answer_part_sources"]:
                assert source["urls"]
                assert all(urlsplit(url).scheme in {"http", "https"} for url in source["urls"])
        if task["id"] in tasks_heldout4.HELDOUT4_TASK_IDS:
            assert catalog[task["id"]] == 1


def test_accepted_site_cap_and_disjoint_from_every_other_split_including_extdev():
    all_authored = authored()
    used = set().union(*(sites(t) for t in all_authored))
    counts = Counter(site for task in all_authored for site in sites(task))
    assert max(counts.values()) <= 3
    ids = {t["id"] for t in all_authored}
    for task in get_all_tasks():
        if task["id"] not in ids:
            assert used.isdisjoint(sites(task)), task["id"]
    assert used.isdisjoint(set().union(*(sites(t) for t in tasks_for_split("extdev"))))
    assert used.isdisjoint(r["site"] for r in read("candidates_extdev.jsonl"))


def test_append_only_checkpoint_and_latest_decisions():
    data = (RESULTS / "authoring_heldout4.jsonl").read_bytes()
    assert hashlib.sha256(data[:570280]).hexdigest() == "64b0c462bbd036a73d2ce040ed4b28a35f72d287a995297dd1e748f043cb3c13"
    history = read("authoring_heldout4.jsonl")
    latest = effective_authoring_decisions(history)
    assert len(latest) < len(history)
    for row in latest:
        assert row["note"] and "\n" not in row["note"]
        if row["disposition"] == "excluded":
            assert row["reason"] in EXCLUSIONS
            if row["reason"] == "no_checkable_key":
                assert "computed:" in row["note"]
                assert "ungradeable_end_state:" not in row["note"]
    active = {t["id"] for t in tasks_for_split("heldout4")}
    kept = {r["task_id"] for r in latest if r["disposition"] == "kept"}
    assert active == kept


def test_ranked_quota_then_fill_replay_and_automatic_duplicate_decisions():
    candidates = read("candidates_heldout4.jsonl") + read("candidates_extdev.jsonl")
    history = read("authoring_heldout4.jsonl")
    authoring = [r for r in history if r["disposition"] != "dropped"]
    latest = {(r["source"], r["source_id"]): r for r in effective_authoring_decisions(authoring)}
    decisions = effective_authoring_decisions(read("authoring_extdev.jsonl"))
    kept = []

    def accept(row, automatic):
        decision = latest[row["source"], row["source_id"]]
        if automatic:
            assert decision["reason"] == automatic
            if automatic == "duplicate_task":
                assert row["duplicate_of"] in decision["note"]
        decisions.append(decision)
        if decision["disposition"] == "kept":
            kept.append(decision)

    for source in SOURCES[:-1]:
        for row, automatic in authoring_reserve(candidates, decisions):
            if sum(d["source"] == source for d in kept) >= QUOTAS["heldout4"][source]:
                break
            if row["set"] == "heldout4" and row["source"] == source:
                accept(row, automatic)
    for row, automatic in authoring_reserve(candidates, decisions):
        if len(kept) == 130:
            break
        if row["set"] == "heldout4":
            accept(row, automatic)
    assert {d["task_id"] for d in kept} == {t["id"] for t in authored()}
    by_id = {t["id"]: t for t in authored()}
    for decision in latest.values():
        if decision["reason"] == "duplicate_task":
            duplicate = next(t for task_id, t in by_id.items() if task_id in decision["note"])
            candidate = next(r for r in candidates if (r["source"], r["source_id"]) == (decision["source"], decision["source_id"]))
            assert task_fingerprint(candidate["task_text"], candidate["site"], candidate["start_url"]) == task_fingerprint(duplicate["description"], candidate["site"], duplicate["start_url"])


def test_judge_metadata_never_enters_the_task_prompt_and_interactive_intent_is_kept():
    task = dict(authored()[0])
    expected = task_message(task["description"], task["start_url"])
    for field in set(task) - {"description", "start_url", "id"}:
        task[field] = "PRIVATE_JUDGE_ONLY_SENTINEL"
    assert task_text(task) == expected
    assert "PRIVATE_JUDGE_ONLY_SENTINEL" not in task_text(task)
    ids = {t["id"] for t in authored()}
    assert {"ho4_form_ua_egift_card_100", "ho4_form_uk_english_euros",
            "ho4_value_google_maps_los_angeles_pdf", "ho4_value_nmun_nyc_deadlines",
            "ho4_multisite_tompkins_early_fitness"} <= ids
    assert {"filter", "form", "spa", "multisite"} <= {t["kind"] for t in authored()}


def test_verifier_normal_empty_error_and_negative_contracts():
    task = {"full_answer": "Alpha; Beta", "answer_parts": ["Alpha", "Beta"],
            "check_url_contains": "/goal", "end_markers": {"host": "example.org", "url_contains": "/goal", "answer_in_text": "Alpha"}}
    observed = Observation("https://example.org/goal", "Alpha\nBeta")
    assert grade_observation(task, observed, task["full_answer"])[0] is True
    assert control(task, observed, "Wrong value", "wrong_answer")["correctly_failed"]
    assert not grade_observation(task, Observation("https://example.org/goal"), task["full_answer"])[0]
    assert not control(task, Observation("https://example.org/goal"), task["full_answer"], "unread")["correctly_failed"]
    observed.selector_checks = {"saved message": False}
    assert not grade_observation(task, observed, task["full_answer"])[0]

    class BrokenPage:
        def locator(self, selector):
            raise RuntimeError("browser unavailable")

    with pytest.raises(RuntimeError, match="browser unavailable"):
        asyncio.run(run_steps(BrokenPage(), [{"action": "click", "selector": "button"}], RESULTS, "test"))
    empty = summarize([], [], [])
    assert empty["keys_pass"] == empty["negative_controls"] == 0
    assert empty["reproducer_pass_rate"] is None


def test_dropped_ids_are_not_registered_or_silently_removed_from_authoring():
    dropped = set(tasks_heldout4.HELDOUT4_DROPPED_TASK_IDS)
    assert dropped <= {t["id"] for t in authored()}
    assert dropped.isdisjoint(tasks_heldout4.HELDOUT4_TASK_IDS)
    assert len(tasks_for_split("heldout4")) + len(dropped) == 130


def test_authorized_multi_page_revisions_preserve_full_reference_and_provenance():
    original = json.loads((RESULTS / "verification_heldout4_20261117T100724469791Z.summary.json").read_text())
    assert original["summary"]["tasks"] == 130
    tasks = {t["id"]: t for t in authored()}
    decisions = effective_authoring_decisions(read("authoring_heldout4.jsonl"))
    revisions = [d for d in decisions if d.get("key_revision") and "multi_page_parts" in d.get("grader_flags", [])]
    assert len(revisions) == 18
    for decision in revisions:
        task = tasks[decision["task_id"]]
        changes = decision["key_revision"]["task_changes"]
        assert "full_answer" not in changes
        assert "expected_answer" not in changes
        assert "answer_part_sources" not in changes
        assert set(changes["answer_parts"]["before"]) == set(task["answer_parts"]) | {s["part"] for s in task["unscored_parts"]}


def test_pdf_extraction_normal_empty_and_error(tmp_path, monkeypatch):
    from bench import verify_heldout4

    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class Reader:
        pages = [Page("Real PDF text"), Page(None)]

    monkeypatch.setattr(verify_heldout4, "PdfReader", lambda path: Reader())
    assert pdf_text(tmp_path / "document.pdf") == "Real PDF text\n"
    Reader.pages = []
    assert pdf_text(tmp_path / "empty.pdf") == ""

    def broken(path):
        raise ValueError("invalid PDF")

    monkeypatch.setattr(verify_heldout4, "PdfReader", broken)
    with pytest.raises(ValueError, match="invalid PDF"):
        pdf_text(tmp_path / "broken.pdf")


def test_visible_control_readback_uses_real_values_not_reference_literals():
    from playwright.async_api import async_playwright

    async def check():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content('<select id="locale"><option value="en-gb">🇬🇧 English (UK)</option>'
                                   '<option value="en-us">English (US)</option></select>'
                                   '<textarea id="output">Actual generated code</textarea>')
            task = {"answer_part_selectors": {"English (UK)": "#locale option:checked"},
                    "answer_part_selector_values": {"English (UK)": "en-gb"},
                    "observation_selectors": ["#output"]}
            result = await observe(page, task)
            assert result.selector_checks == {"English (UK)": True}
            assert "Actual generated code" in result.text
            await page.locator("#locale").select_option("en-us")
            assert (await observe(page, task)).selector_checks == {"English (UK)": False}
            await page.locator("#locale").select_option("en-gb")
            await page.locator("#locale").evaluate("e => e.style.display = 'none'")
            assert (await observe(page, task)).selector_checks == {"English (UK)": False}
            assert not (await observe(page, {})).selector_checks
            await browser.close()

    asyncio.run(check())


def test_run_report_accepts_relative_and_external_output_paths(tmp_path, monkeypatch, capsys):
    from bench import verify_heldout4

    class Browser:
        chromium = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def launch(self, **kwargs):
            return self

        async def new_context(self):
            return self

        async def new_page(self):
            return self

        async def close(self):
            pass

    async def noop(*args):
        pass

    async def observation(*args):
        return Observation("https://example.com/", "Decoy page")

    browser = Browser()
    browser.chromium = browser
    monkeypatch.setattr(verify_heldout4, "async_playwright", lambda: browser)
    monkeypatch.setattr(verify_heldout4, "goto", noop)
    monkeypatch.setattr(verify_heldout4, "observe", observation)
    monkeypatch.setattr(verify_heldout4, "tasks_for_split", lambda split: [])
    monkeypatch.setattr(verify_heldout4, "read_ledger", lambda: [])
    monkeypatch.setattr(verify_heldout4, "RESULTS", tmp_path)
    monkeypatch.chdir(tmp_path)
    for output in [Path("relative.jsonl"), tmp_path / "absolute.jsonl"]:
        asyncio.run(verify_heldout4.main(output, 1))
        assert json.loads(output.with_suffix(".summary.json").read_text())["summary"]["tasks"] == 0
    assert "Run evidence: relative.jsonl" in capsys.readouterr().out
    with pytest.raises(FileExistsError, match="Preserve prior run"):
        asyncio.run(verify_heldout4.main(Path("relative.jsonl"), 1))
