# Failure taxonomy

This note groups failures recorded in `bench/runs/probe_*.jsonl` or in fixtures under `tests`. It was read from commit `98fcfeaf576788d8163de4624c6088f3997af312`. No probe was run.

## Probe logs

`bench/runs/probe_*.jsonl` is absent.

The directory `bench/runs/` at that commit contains `shortcut_replay_output.md` only. That file is not a `probe_*.jsonl` log, so it is not a source for the groups below. `.gitignore` ignores `bench/runs/`. No commit in this clone adds a `probe_*.jsonl` path.

## Fixtures under tests

### `tests/fixtures/probe_sketch.jsonl`

The file contains these four lines:

```json
{"sketch": true, "arm": "script_first", "task_id": "wv_wikipedia_search", "pass": "cold", "wall_ms": 1111, "steps": 7, "tier": "sketch", "usd": 0.001}
{"sketch": true, "arm": "script_first", "task_id": "wv_python_docs", "pass": "cold", "wall_ms": 2222, "steps": 4, "tier": "fresh", "usd": 0.002}
{"sketch": true, "arm": "stagehand", "task_id": "wv_wikipedia_search", "pass": "cold", "wall_ms": 3333, "steps": 5, "tier": "", "usd": 0.004}
{"kind": "warm_summary", "warm": {"script_first": {"wall_ms": 99999}}}
```

The first three lines set `"sketch"` to true and `"pass"` to `"cold"`. The fourth line is a `warm_summary` and has no task id. None of the four lines has a success field, a failure field, an error field, or a reason. The `wall_ms`, `steps`, and `usd` values above are the fields stored in this sketch file.

### `tests/fixtures/evidence/hackernews_top.json`

Page evidence for "Read the top Hacker News story". Start URL `https://news.ycombinator.com/`. Page title "Hacker News". Claimed answer `Show HN: a small public demo` followed by a newline. No failure field.

### `tests/fixtures/evidence/wikipedia_encoded.json`

Page evidence for "Search Wikipedia for Ada Lovelace". Start URL `https://en.wikipedia.org/wiki/Main_Page`. Page URL `https://en.wikipedia.org/wiki/Ada%20Lovelace`. Canonical URL `https://en.wikipedia.org/wiki/Ada_Lovelace`. Claimed answer `Ada Lovelace`. No failure field.

### `tests/replay/packing-page.json`

Replay descriptor `packing-page`, version 1. Start URL `loop/fixture/packing.html`. End URL `packing.html`, title "Packing list", text "Packing list". No failure field.

### `tests/snapshots/playwright_todos.txt`

An ARIA snapshot of a todos page: a search box "Search Wikipedia", a textbox "Query" whose value is `Ada Lovelace`, two todo items, and a button "OK". No failure record.

## Groups

There are no groups. The probe logs are absent, and the fixtures under `tests` record no failure, so this file assigns no failure class, count, or timing.
