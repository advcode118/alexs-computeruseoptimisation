# Runtime candidates #74, #76, #77 against tip4 and PR82

Read-only review, 16 Nov 2026. No tests, probes, git mutation or ledger access.
Baseline `t3/tip4` = `b5b74b3f9d74f0b87dd5cf9a170b8c2b4af496b5`; PR82 =
`d4f9d03abe278ebad44d1391cc67b4d3b83b8005` (`CU_SF_SEGMENTS=1`, opt-in).
All three candidates fork from `bec55ab` (tip3 docs; runtime `56fbcab`) and
are **not** ancestors of tip4. Their merge parents (`t3/dev3-set`, `t3/tip3`)
are already in tip4, so each brings only the commits listed below. Evidence
read: PR bodies, branch docs, dev-only aggregate JSON and code. No
heldout3/heldout4/val3 data was opened. #77's `recovered_partial_A2_heldout2`
file was not opened either.

## Verdict summary

| PR | Head | Live dev evidence | Default changed? | Verdict |
|---|---|---|---|---|
| #74 observe-first | `69275669c66948c32d82c4bf20cbc3d730ba8167` | 3 pairs × 40 dev3, Luna medium | No (`CU_PAGE_SUMMARY=1`) | **Integrate opt-in. Recheck at the post-fix head on tip4.** It is the best-evidenced candidate. |
| #76 strategy-search | `9c6f391b647f9536756e9846739a4a93b8e0617c` | **None.** Author reference routes passed 2/12, then 6/12. | No (`CU_SF_STRATEGY=search`) | **Hold. Unmeasured.** The trigger and self-check have problems (below). |
| #77 robust-executor | `74f434edec976e286f5dd2c7bbcd837a4f19094b` | 1 pair × 40 dev3, Luna medium | **Yes**: prompt, resolver and preload with no flag | **Do not merge as a bundle.** It changes defaults and races the tip4 specialists. Split out the grammar part, then measure. |

## #74 observe-first: helps on dev; keep opt-in

**Mechanism.** `bench/page_summary.py` makes an HTTP GET of `start_url` on a
daemon thread at `wall_start`. The fetch has a 1.5 s deadline and limits on
bytes and decoded size. The parsed summary (title, h1/h2, task-ranked links,
GET search template, forms, buttons) is appended to `messages[0]` before model
call 1. Any failure falls back to the blind path. Off by default, and
`tests/conftest.py` forces it off in the suite. It uses the task text and the
live page only, never markers.

**Commits.** `f2a3d68c2f64e562ca11a37c7498cc20496b28a3` (summary),
`408a4e14d6fbc9b8a745852921887c7ae4916125` (fetch tightened, suite offline),
`43c8142cbd74c4dbfa7be8d08c934bbaad3f5180` (opt-in and bounded delivery: **the
measured revision**), `018ea294e2e4f02d6b94a299436ecd0c69b7ad97` (bounded
decompression: **after the measurement, not live-tested**),
`69275669c66948c32d82c4bf20cbc3d730ba8167` (evidence and docs only).

**Evidence (actual, dev3, at `43c8142` on tip3).**

| | Off | On |
|---|---:|---:|
| Final graded passes | 99/120 | 109/120 |
| Pairs | 33 / 34 / 32 | 35 / 37 / 37 |
| False accepts (self-PASS, grade fail) | 9 | 2 |
| One-script stopped and graded | 30 | 55 |
| Mean wall time | 9.34 s | 8.29 s |
| Recorded USD | $0.079320 | $0.056617 |

Strengths: the gain held in all three pairs with the order balanced. False
accepts fell, and first-script success nearly doubled. Limits: dev3 is a tune
set, repeats are not independent tasks, and the timings come from a shared
machine. Summaries were usable in only 87/120 rows (15 no-content, 6 × 403, 3
cert, 9 timeouts). The earlier pair, before grounded repair existed, gained only
26→29 with the same 3/3 false accepts. Nothing has been measured with tip4's
specialists or PR82's segments.

**Integration conflicts.**
- tip4: 1 textual conflict in `bench/harness.py` (wall_start block). `probe.py`
  changes on both sides but merges cleanly.
- PR82: 1 conflict at the same spot (`generic_start = wall_start`). To resolve,
  keep both: start the future after `generic_start`. Check that PR82's segment
  loop still builds its first message from `messages[0]` after the summary is
  appended.
- Semantic: the summary fetch starts even when form, spa or nav then takes the
  task, so the fetch is wasted. tip4's `strategy_spa.fetch_html` makes a second
  GET of the same URL, which adds to 403/rate-limit exposure. Not a blocker; the
  two fetches can be shared later.
- No judge weakening: the grade and markers are untouched, and the summary is
  live-page data only. The summary is not marked as untrusted page text, unlike
  the strategy prompts. Minor.

**Targeted tests.** `tests/test_page_summary.py tests/test_observe_first_report.py
tests/test_grounded_repair.py tests/test_script_cache.py tests/test_prompt_audit.py`,
plus tip4's `tests/test_strategy_combined.py tests/test_strategy_review_regressions.py`
and, if PR82 is merged, `tests/test_segments_harness.py`. The answer-key guard
`tests/test_script_cache.py::test_the_live_run_never_reads_the_answer_key` is
mandatory.

**Minimal ablation (later, Luna or Sol medium only).** On the integration head,
dev3 × 40, `CU_PAGE_SUMMARY` 0 vs 1, everything else fixed. Run 2 pairs with the
order alternated (off/on, on/off). This re-validates `018ea29` and runs it on
tip4. Estimated about $0.05 per pair on Luna, from the recorded $0.0007/row.
Optional third cell if PR82 lands: summary on with `CU_SF_SEGMENTS=1`, to test
redundancy (both address the blind first script). Accept if the final-pass
delta stays ≥ 0 in both pairs and false accepts do not rise.

## #76 strategy-search: unmeasured; hold

**Mechanism.** `bench/strategy_search.py` runs before the generic path when
`CU_SF_STRATEGY` contains `search` and `claims(task)` is true. It uses at most
2 small model "choose" calls (box, query and filters, then a result from real
links). It submits via `requestSubmit`, navigates to the chosen href and runs
`landed_ok`. A miss returns to `about:blank` and the generic fresh path,
keeping the spend.

**Commits.** `8f85f8e77b2edb03abde412afbe6e099fc204190` (12 dev4search tasks
plus verifier), `4cedd8c9b119f329f8beecb64f1f654901966f78` (specialist),
`9c6f391b647f9536756e9846739a4a93b8e0617c` (checkpoint scripts only).

**Evidence.** None for agent performance. `docs/STRATEGY_SEARCH.md` still says
"Pending paired measurements; no performance claim yet." The author routes
passed 2/12 (attempt 1) and 6/12 (attempt 2). All six astropy, pydantic and
fastapi tasks failed the author's own reproducer, so half the new task set is
not shown to be passable. The 48 offline tests are unit evidence only.

**Grounding and overfit findings.**
1. **The trigger matches the task template.** `claims()` needs the literal word
   `search`. Every dev4search description has *"Use the site's search and open
   the actual page…"* appended (`bench/tasks_dev4_search.py`). On dev4search the
   claim rate is 100% by construction. Real tasks that don't say "search" never
   reach the specialist. Tasks that mention search incidentally ("search
   utility") do.
2. **The self-check is weak.** `landed_ok` builds a claim with
   `answer=evidence.url`. `runtime_verdict`'s same-page URL rule then passes any
   page that is not the start page. The only other checks are "not a
   search-results URL/h1" and "selected href == live/canonical". Nothing checks
   the content against the task. A wrong result the model picks becomes a
   self-PASS, and the run ends with `tier="search"` and no generic retry, so it
   counts as a wrong accept. The final grade stays independent (no grade
   weakening), but the false-accept risk is high and untested.
3. No per-site selectors, URLs or catalog in the module: it stays generic. The
   per-site risk lies in the task set: 6 sites × 2 tasks, written by the same
   agent, with JS-search docs sites failing.
4. Inputs without a `<form>` are filled but never submitted. It relies on
   autocomplete links appearing.

**Redundancy.** tip4 `strategy_form` already says the "search specialist owns
site search", so a precedence slot is reserved. #74's summary already offers a
GET search template, and #77 adds `cu.search`. That makes three overlapping
search routes. PR82 segments (look → continue) also cover search followed by a
results pick.

**Conflicts with tip4 and PR82.** 12 textual conflict hunks: `harness.py` ×2
(the dispatch block now sits in tip4's form→spa precedence chain),
`probe.py` ×4, `tasks.py` ×5 (next to the tip4 dev4nav/form/spa splits) and
`openai_run.py` ×1 (`only_kind`). The same 12 conflict against PR82. This is a
re-implementation on tip4, not a merge. Its order relative to spa and nav would
need defining.

**If pursued.** Make the specialist's PASS require answer or key-text content
grounding, or let it hand off to the generic verifier, before any live run.
Then do one dev pair on only the 6 author-verified dev4search tasks plus any
dev3 tasks with search intent, with `CU_SF_STRATEGY=nav,form,spa` vs
`nav,form,spa,search`. Report wrong accepts as the primary safety metric.
Tests: `tests/test_strategy_search.py tests/test_dev4_search.py
tests/test_strategy_combined.py tests/test_strategy_form.py
tests/test_grounded_repair.py tests/test_script_cache.py`.
`docs/results/search_20261114/checkpoint.py` also schedules heldout2 and
held-out runs. Do not reuse it as written; scope runs to dev.

## #77 robust-executor: mixed; changes defaults; do not merge as a bundle

**Commits.** `5c4f9aa72979ad73cd961f71ce2e43769863f613` (forgiving resolver,
settle waits, wider grammar, start-page preload),
`a3095d12beffaf3854bc156de65427ef5b97b74b` (regex names, option clicks, prompt
prefers goto), `617dd74d92f7d3a30cf7923b7521f0fbb4939400` (evidence),
`e9c8673d10a87a03d88303685a964c9ec2595a9b` (`STRICT_MATCH=True`; the measured
head), `74f434edec976e286f5dd2c7bbcd837a4f19094b` (docs and hold decision).

**Evidence (actual, dev3, 1 pair, `e9c8673` vs tip3 `bec55ab`).**

| | tip3 | robust |
|---|---:|---:|
| Final graded passes | 28/40 | 33/40 |
| Wrong accepts | 4 | 6 |
| One-script stopped and graded | 12 | 10 |
| Median / mean / p90 s | 7.02 / 9.01 / 15.76 | 5.90 / 6.97 / 13.32 |
| USD | $0.024972 | $0.023257 |

The +5 is **inside the observed run-to-run noise**. The same tip3 runtime
scored 28/40 here and 32–34/40 in #74's three off arms. One pair cannot
separate +5 from variance. Wrong accepts rose and one-script passes fell. The
author's own recommendation is to hold.

**Ambiguity scrutiny.**
- The "strict 8/8 vs fuzzy 4/8" synthetic result compares #77's resolver with
  and without its own strict flag. **It does not compare against tip3.** tip3
  already refused ambiguous names: `test_an_ambiguous_name_does_not_fall_through_to_another_role`
  asserted the "2 matches for link named 'Go'" failure. #77 **deletes** that
  test and `test_click_fill_and_press_use_the_one_matching_control` from
  `tests/test_script_helpers.py`.
- The new resolver is **looser than tip3** in ways strictness does not undo.
  It accepts partial names (≥60% word overlap) when no visible exact hit
  exists and the runner-up is >10 below. It accepts clicks on plain-text
  elements and their nearest control ancestor (`"text in control"`/`"text"`).
  It fills the *next* field found within three ancestors of matching text
  (`fieldNear`). It retries a missing name for up to 3 s. These plausibly
  explain the extra wrong accepts: an action on the wrong control followed by a
  self-PASS.
- In strict mode a `/regex/` name counts every regex hit as exact
  (`re ? c.raw > 0`), so most regex names on busy pages become ambiguous.
  Identical names are no longer deduplicated, so header and footer copies of a
  link now fail. These fail safe but cost repairs.
- Hidden-only matches: the pool needs visible elements, so a high-scoring
  hidden pick can survive while the pool is empty. Low risk; it times out.

**Default changes, no flag.** `_SCRIPT_FIRST_PROMPT` is rewritten (adds
`cu.search`, `cu.text`, regex names, "the runner waits"). `STRICT_MATCH` is a
module constant. The harness always calls `mcp_client.preload(start_url)`.
Merging would change the tip4 default arm and break the
"strategies-off is tip3" guarantee recorded in `80f7433`.

**Blocker: preload race with tip4 specialists.** `preload()`
(`bench/script_first.py` on the branch, around line 2928) does
`asyncio.ensure_future(page.goto(start_url))` in the script_first setup block.
On tip4 the form, spa and nav specialists (and #76 search) then `goto` on the
**same** `self.mcp_client._page` while that navigation is in flight. That can
abort navigations and leave a nondeterministic start state. It needs gating to
run only once no specialist claims the task, or to await the preload first.
tip4 has no textual conflict here, which hides the problem.

**Conflicts with PR82.** 3 hunks in `bench/script_first.py`. `run_on_page`'s
step loop (#77: `_use_preload`, settle after page-changing steps) collides with
PR82's `before_tail`/`_ScriptRunState` segment state. The browser state init
(`_preload` vs `reset_segments`) collides too. Both rewrite the same executor
loop, so this is a semantic merge.

**Possibly useful pieces.** The offline parse check is real evidence for the
grammar: the historical dev3 first scripts parse 32/40 on tip3 and 39/40 on the
robust grammar (`offline.json`). Parsing is not execution. `script_grammar.py`
widening, `cu.text` and settle-after-goto-before-read are the candidates to
isolate behind a flag (for example `CU_SF_EXECUTOR=robust`), with tip3's
deleted ambiguity tests restored. Leave partial-name and near-text field
resolution off unless a separate measurement shows they do not add wrong
accepts.

**Tests if split.** `tests/test_script_resolve.py tests/test_script_helpers.py
tests/test_script_first.py tests/test_grounded_repair.py tests/test_prompt_audit.py
tests/test_strategy_combined.py tests/test_strategy_review_regressions.py`
(+ `tests/test_segments*.py` with PR82). Add one test that preload never runs
while a specialist owns the page.

**Ablation (only after splitting and adding the flag).** dev3 × 40 on the
integration head, flag off vs on, at least 2 pairs with the order alternated.
Primary metrics: wrong accepts and one-script graded passes. A final-pass
delta smaller than about 6/40 per pair is not distinguishable from the noise
seen above.

## Answers to the parent

- **Helps (dev evidence):** #74 only, opt-in. Merge `69275669` (or the four
  runtime commits plus docs), resolve the single harness hunk, and recheck at
  the post-`018ea29` head on tip4.
- **Neutral or unknown:** #76. It has no measurement, half its task set is
  unverified, the trigger matches the task template, and the self-check lets
  any landed page pass.
- **Mixed, negative on safety:** #77 as a bundle (+5 final within noise, +2
  wrong accepts, −2 one-script passes). It changes defaults and races the
  specialists. Hold.
- **Redundancy:** #74, #76, #77 (`cu.search` and preload) and PR82 all target
  the blind first script or the search step. Measure each candidate on top of
  the integrated tip4 (plus PR82 if merged), not on tip3.
- No candidate touches `bench/judge.py`, markers or the post-run grade. The
  weakening risk is in runtime self-PASS (#76 `landed_ok`, #77 loose
  resolution), which would show up as wrong accepts.
- Every number above is a dev-set measurement or a unit or offline check. None
  is an accuracy result on a held-out set.
