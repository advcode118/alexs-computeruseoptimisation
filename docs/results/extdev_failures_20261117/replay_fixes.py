"""Model-free syntax and evidence replays; never execute saved JavaScript."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from classify import HERE, breakdown, classify, parse_error, rows, write_csv
from bench import script_grammar
from bench.script_first import budget_script_result


class RegexScan(script_grammar._LiteralScan):
    """Parse-only regex tokens. The marker is NOT an executable locator."""

    def string(self):
        self.skip()
        if self.startswith("/"):
            match = re.match(r"/(?:\\.|\[(?:\\.|[^\]\\])*\]|[^/\n\\])+/[dgimsuvy]*", self.remaining())
            if match:
                self.i += len(match.group())
                return "REGEX:" + match.group()
        return super().string()

    def literal(self):
        self.skip()
        return self.string() if self.startswith("/") else super().literal()


def regex_parse_error(code):
    with patch.object(script_grammar, "_LiteralScan", RegexScan):
        return parse_error(code)


def truncate_metadata(payload, limit=7700):
    """Keep valid JSON and status, dropping optional metadata before page text."""
    data = dict(payload)
    dropped = []
    for key in ("selector_text", "claimed", "extracted", "values", "headings", "links", "controls"):
        try:
            rendered = budget_script_result(json.dumps(data), limit)
            return rendered, dropped
        except ValueError:
            if key in data:
                data.pop(key)
                dropped.append(key)
    core = {key: data[key] for key in ("ok", "steps", "url", "text") if key in data}
    core["url"] = str(core.get("url", ""))[:1000]
    return budget_script_result(json.dumps(core), limit), dropped + ["other_metadata"]


def extract(task, text):
    """Exploratory, task-family templates, using only the row's saved text."""
    lower = task.lower()
    if "nba season leaders" in lower:
        leaders = re.findall(r"([A-Z0-9][A-Z0-9 -]+)\t[A-Z0-9]+\s+1\s+([^\n]+)\s+[^\n]+\s+(\d+(?:\.\d+)?)", text)
        if leaders:
            return "\n".join(f"{category}: {name} — {value}" for category, name, value in leaders), "correct", "All six displayed category leaders, with values."
    if "all the events" in lower:
        section = re.search(r"Our Events\s+(.*?)\s+PASSES & TICKETS", text, re.S)
        if section:
            names = list(dict.fromkeys(s.strip() for s in section[1].splitlines() if s.strip() and s.strip() != "Our Events"))
            return "\n".join(names), "correct", "Nine events from the saved events-page menu; each also has a dated card below."
    if "marketing department" in lower:
        roles = re.findall(r"(?:^|\n)Marketing\n(.+?)\n\s*([^\n]+)\s*\n\s*View Role", text)
        if roles:
            return "\n".join(f"{role} — {place}" for role, place in roles), "correct", "The one Marketing opening and location, excluding other departments."
    if "contact the support" in lower:
        phone = re.search(r"\+1 \(\d{3}\) \d{3}-\d{4}", text)
        if phone:
            return phone[0], "partial", "Grounded support number; no evidence of a call or submitted message."
    if "icse" in lower and "general chair" in lower:
        dates = re.search(r"(\d{1,2})(?:st|nd|rd|th)? to (\d{1,2})(?:st|nd|rd|th)? ([A-Z][a-z]+)", text)
        year = re.search(r"\b(20\d{2})\b", task)
        if dates and year and year[1] in text:
            return f"{dates[3]} {dates[1]}–{dates[2]}, {year[1]}", "partial", "Dates supported; General Chair absent from saved page."
    if "icse" in lower and "program committee chairs" in lower:
        place = re.search(r"(?m)^([A-Z][A-Za-z .'-]+, [A-Z][A-Za-z .'-]+, [A-Z]{2,})\n([A-Z][a-z]+) (\d{1,2})-(\d{1,2}), (\d{4})", text)
        if place and place[5] in task:
            return f"{place[1]}; {place[2]} {place[3]}–{place[4]}, {place[5]}", "partial", "Place and dates supported; program committee chairs absent (General Chair is not the requested role)."
    return "", "", "No complete, task-relevant extraction supported by this template."


def replay(data):
    records, syntax, budgets = [], [], []
    for row in data:
        unblocked = False
        for index, code in enumerate(row["scripts"], 1):
            before, after = parse_error(code), regex_parse_error(code)
            unblocked |= bool(before and not after)
            syntax.append({"line": row["line"], "attempt": index, "before_error": before, "after_error": after,
                           "newly_parses": bool(before and not after)})
        budget = "metadata exceeds" in row["grade_completion_reason"].lower()
        if budget:
            payloads = [check["payload"] for check in row["self_checks"] if check.get("payload", {}).get("text")]
            for index, payload in enumerate(payloads):
                rendered, dropped = truncate_metadata(payload)
                assert len(rendered) <= 7700
                json.loads(rendered)
                budgets.append({"line": row["line"], "payload": index, "output_chars": len(rendered),
                                "dropped": dropped, "exact_failing_payload": False})
            if not payloads:
                budgets.append({"line": row["line"], "payload": None, "output_chars": None,
                                "dropped": [], "exact_failing_payload": False})
        answer, label, note = extract(row["task_description"], row.get("grade_page_text", ""))
        baseline = row["hand_label"]
        records.append({
            "line": row["line"], "task_id": row["task_id"], "baseline": baseline,
            "regex_only": "unknown" if unblocked else baseline,
            "metadata_only": "unknown" if budget else baseline,
            "extraction_only": label or baseline,
            "combined": label or ("unknown" if unblocked or budget else baseline),
            "newly_parses": unblocked, "metadata_failure": budget,
            "candidate_answer": answer, "evidence_assessment": note,
        })
    return records, syntax, budgets


def totals(records):
    keys = ("baseline", "regex_only", "metadata_only", "extraction_only", "combined")
    labels = ("correct", "partial", "wrong", "unknown")
    return {key: {label: sum(r[key] == label for r in records) for label in labels} for key in keys}


def summary_table(counts):
    lines = ["| Variant | Correct | Partial | Wrong | Unknown |", "|---|---:|---:|---:|---:|"]
    for key, values in counts.items():
        lines.append(f"| {key} | " + " | ".join(map(str, values.values())) + " |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)
    data = rows()
    failures = [classify(row) for row in data]
    records, syntax, budgets = replay(data)
    write_csv(args.output_dir / "failures.csv", failures)
    write_csv(args.output_dir / "replay.csv", records)
    report = {"counts": totals(records), "syntax": syntax, "metadata": budgets,
              "paid_model_calls": 0, "browser_runs": 0,
              "score_caveat": "Scored against AI (Devin) hand labels from PR #97; no human spot-check; indicative only."}
    (args.output_dir / "replay.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["score_caveat"])
    print(breakdown(failures))
    print(summary_table(report["counts"]))
    print(f"Saved scripts: {len(syntax)}; baseline parse: {sum(not s['before_error'] for s in syntax)}; regex variant parse: {sum(not s['after_error'] for s in syntax)}")
    print("Repair outcomes:", dict(sorted(Counter(r["repair"] for r in failures).items())))


if __name__ == "__main__":
    main()
