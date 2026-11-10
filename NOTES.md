# Onboarding notes: script_first and the end-state check

Base: `t3/base` at a5a4224 (Origin PRs #18-#20). Written 2026-11-09. No live probe run.

## Test suite status

`python -m pytest -q bench/test_harness.py tests` gives **167 passed, 11 failed**. None of the failures is a logic bug. They come from files and packages this worktree doesn't have:

| Cause | Failing tests |
|---|---|
| `bench/snapshots/` and `bench/runs/` are gitignored and absent | test_aria x2, test_bench snapshot files, test_harness handmade figure |
| `bench/results/spend.json` is a fresh seed ($9.645), but tests expect $12.912192 | test_harness prior spend, test_script_first $2 stop, test_stagehand_arm x2 |
| `anyio` not installed (pulled in by `proxy/server.py`) | test_proxy lists tools |
| `.gitignore` lacks `proxy/replay-cache.sqlite` | test_replay_cache gitignored |
| Needs a local Chrome | test_loop attached chrome |

**Spend ledger warning.** The `spend.json` in this worktree says $9.645. The tests assume $12.91 and the brief says about $16.64. `bench/results/` is gitignored, so each worktree seeds its own ledger. A probe run from here would check the $50 cap against the wrong total. Before any probe, copy the real ledger in, or make `DEFAULT_SPEND_PATH` point at one shared file.

## How a script_first run flows

1. `python -m bench.probe --execute --arms ...` (`bench/probe.py`). `probe_tasks()` picks `wv_wikipedia_search`, `wv_python_docs` and `wv_hackernews_top` from `bench/tasks.py`. The script_first run is capped at $2 (`SCRIPT_FIRST_CLAUDE_BUDGET_USD`).
2. `run_harness_row` → `BenchmarkHarness.run_task` (`bench/harness.py`, ~L700-1000). For script_first, `build_client` (`bench/arms.py`) returns `ScriptFirstClient` (`bench/script_first.py:732`). It exposes one tool, `run_script`, and the system prompt is `_SCRIPT_FIRST_PROMPT` (`arms.py:73`).
3. The model sends one `run_script(code)`. `parse_task_script` turns it into steps (goto / getBy* actions / `page.evaluate`) and silently drops wait lines (new in #20). `run_on_page` executes the steps in one Playwright page. `_finish_page` then:
   - waits up to 0.8s for the URL to "land" (`_wait_for_landed`),
   - **replaces** the URL with `scored_page_url(...)`,
   - on tasks with no URL check (HN), reads `.titleline a` itself (`_capture_visible_answer`) when the script returned no text.
4. `format_run_result` returns a JSON line plus `- Page URL:`. The harness reads it back with `page_url_from_result`.
5. End-state check (harness ~L880-945): `end_state_failure(...)` + `missing_page_text(...)`. On failure it adds `repair_request` to the tool result, which costs a second model call (the "false-repair tax"). On pass with a URL or an answer, it sets `success=True` and `stop_after_tools`, so no completion turn is needed.
6. Probe scoring (`probe.py:349`): `deterministic_success` runs `check_url_contains` / `check_text` on `result.steps[-1].page_url`. HN has neither, so `result.success` (the harness's own verdict) is final.

## Where the end-state check lives

- `bench/script_first.py`: `scored_page_url`, `_denied_page`, `_title_names_target`, `end_state_failure`, `missing_page_text`, `repair_request`, `next_script_first_limit`.
- `bench/harness.py` ~L734-945 (script_first branch) and L991 (the TASK_COMPLETE path).
- The final judge is `bench/judge.py` (`check_url_contains`, `check_text_present`, `llm_judge`), called through `probe.deterministic_success`.

## What PR #20 changes (and the risks it adds)

The changes:
- Wait or settle lines are dropped. There's a 0.8s landing wait instead of networkidle.
- `scored_page_url`: accepts percent-encoded paths, `?title=` params, or a `document.title` that names the target, then **rewrites the URL** into the form the judge expects. Examples: `.../wiki/Ada_Lovelace`, `docs.python.org/3/library/<expect>.html`.
- `missing_page_text`: a no-URL task with an empty `extracted` triggers one repair.
- A passing first script ends the task immediately (no TASK_COMPLETE turn), and a second script after a pass is refused.
- The prompt now lists the answers to the probe tasks: the exact Ada_Lovelace URL, the heapq URL, and the HN selector.

Judge-softening and benchmark-gaming risks. These need review before any probe:
1. **The judge scores a synthesized URL.** The harness sets `page_url = last_url = scored`, and that becomes `steps[-1].page_url`, which `check_url_contains` scores. Take a python.org page whose title starts with "heapq" and whose path doesn't end in `.html`: it gets reported as `/3/library/heapq.html` whatever the real URL was. The stop-check and the final judge share the same rewritten value, so they can't disagree. That means the judge isn't independent any more.
2. **HN success is "any text".** The harness itself reads `.titleline a`, `has_answer` → `success=True`, and nothing checks the text against the page or the task. A first script that never reached HN, but whose final page has any `.titleline`, passes.
3. **`check_url_contains` accepts search URLs that contain the token.** For example, `Special:Search?search=Ada_Lovelace` passes, by design ("same bar as Stagehand"). That's lenient in its own right.
4. **The prompt is tuned to the three probe tasks.** The 1-step scripts may come from the hints, not from the method. Measure against held-out tasks (MDN, arXiv, GitHub, `wv_wikipedia_link`) as well.

So clearing ~3.1s with 1-step scripts on this tip would not yet count as a real win.

## Step 2 plan: evidence-based end-state check

Goal: zero false repairs, with a judge that is **not** softer than `bench/judge.py` today, and stricter than #20.

Design:
- **The script returns evidence.** The prompt asks every script to end with
  `page.evaluate(() => ({url: location.href, title: document.title, h1: document.querySelector("h1")?.innerText, answer: ...}))`.
  The prompt keeps no task-specific URLs or selectors.
- **The harness reads trusted page data itself**, after the script and in the same page: `page.url`, `document.title`, `link[rel=canonical]`, the first `h1`, and capped `innerText`. The model's claims are only hints. Every check runs on trusted data.
- **Task markers in `tasks.py`** (judge side, never shown to the model). Examples:
  - `{"url_contains": "Ada_Lovelace", "host": "en.wikipedia.org", "deny": ["Special:Search", "Main_Page"]}`
  - `{"url_contains": "heapq", "path_suffix": "/library/heapq.html"}`
  - HN: `{"host": "news.ycombinator.com", "answer_equals_selector": ".titleline a"}`, which the harness evaluates to get the true top title.
- **Matching rules.** URL markers match the live URL or the canonical href after percent-decoding. That's real page data, not a rewrite. The scored URL is always one of those two strings, byte for byte. The answer must appear in the trusted `innerText` and satisfy the marker.
- **Tri-state verdict: PASS / FAIL(reason) / UNKNOWN.** Only FAIL with concrete evidence (wrong host, a denied page, a marker mismatch) triggers a repair. UNKNOWN means no repair, and the final judge decides. That separates "the stop-check can't tell" from "the task failed", and it removes the false-repair tax without passing anything extra.
- **Delete `scored_page_url`'s rewriting** and `_capture_visible_answer`. The harness doesn't produce answers for the model.

Files to touch:
- `bench/tasks.py`: add `end_markers` to each WebVoyager task.
- `bench/script_first.py`: add `collect_page_evidence(page)` and `evidence_verdict(task_markers, trusted, claimed)`. Remove the URL rewriting and the harness-side HN capture. `format_run_result` carries the trusted fields.
- `bench/harness.py` (script_first branch): use the verdict for repair and stop decisions. Never overwrite `page_url` / `last_url` with a derived URL.
- `bench/probe.py`: `deterministic_success` uses the same trusted fields and markers. Keep reporting the old substring result next to it for comparability.
- `bench/arms.py`: rewrite `_SCRIPT_FIRST_PROMPT` around the evidence-return contract and drop the per-task answers.
- `tests/test_evidence_judge.py` (new, offline): a table of (task, trusted page state, claimed evidence) → expected verdict. Must-FAIL cases:
  - Main_Page
  - `Special:Search?search=Ada_Lovelace`
  - the title names the target but the URL is another article
  - a claimed URL that differs from the live URL
  - an answer not present in `innerText`
  - the HN answer is story #2
  - the HN answer was taken while the page is not HN
  - empty evidence

  Plus an invariant test: the scored URL ∈ {live url, canonical}. Must-PASS cases:
  - a percent-encoded article URL
  - a canonical redirect
  - the correct HN title with trailing whitespace

  Also replay saved real page states from `bench/snapshots` once those files are restored.

Who does what:
- Design of the verdict and markers, plus review of the diff for leniency: Claude Opus 5.5 / Fable 5.2 (medium).
- Implementation, tests, and fixing the ledger/gitignore/anyio test failures: Cursor Grok 4.7 (high, fast off).

Then re-probe (~$2, with Tom's go) and report per-task wall time and step count for all three arms, plus the held-out tasks.

## Step 3: cached-script tier (offline only, no probe run)

Code: `bench/script_cache.py`, plus `BenchmarkHarness._cached_script_tier` and the `--warm-replay` pass in `bench/probe.py`.

- **Saving.** A script is saved only when the evidence judge said PASS on that exact script. The key is the task intent (the description, normalized) plus the site (the start URL's host). The entry also records the start URL pattern `scheme://host/*`. An entry holds the intent, site, pattern, the model's script (one step per line), the step count and a timestamp. It never holds markers or answers.
- **Replay.** A matching task runs the cached script first with no model call. The result goes through the same `script_verdict` → `evidence_verdict` path as the fresh loop. Only PASS on a live URL counts as `cache_hit`.
- **Patch.** A FAIL, UNKNOWN, or a thrown step triggers one model turn with the `patch_step` tool. The model sees the numbered cached script, the failure (which step threw, or the verdict reason) and the live page's URL, title, h1 and text. It never sees `selector_text`, claimed values or markers. The patched script is re-judged; a PASS is `patched` and replaces the entry.
- **Fresh.** Otherwise the entry is dropped and the normal fresh loop runs unchanged. Its PASS script is saved.
- **Results.** Results carry `tier` (cache_hit / patched / fresh), `model_calls` and `script_steps`. The probe's warm summary adds tier counts for script_first.
- **Probe.** The probe makes a new cache file per run, `bench/runs/script_cache_<stamp>.json`. The cold pass stays cold. Command (not run): `ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms script_first --warm-replay`.

The fresh-loop leak is closed. On a FAIL the judge still reads `selector_text`, and the run log still records it, but the tool result sent back with the repair request does not. The same holds for the patch turn. A model message must not gain `answer_equals_selector`, the selector, or any other marker value that is not already the live page, the task text, or the standing system prompt.
