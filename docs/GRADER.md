# Frozen post-run grader

`bench/grade.py` is the stdlib-only, frozen page grader. It copies the original
URL, host, deny, search-results, token-boundary, deterministic shared-end-state,
and claimed-evidence rules; it imports no runtime/controller code. All arms use
this same grader through the probe delegates (endpoint also uses its evidence
verdict directly). Arm names, prompts, models and strategies do not affect it.
Runtime self-checks keep their separate helpers and must not import this module.

## Answer spans

Both `answer_in_text` and `answer_equals_selector` use these rules:

* Normalisation is unchanged: whitespace collapses and Unicode case folds.
* Reject a stripped raw answer longer than `3 * len(marker) + 40` characters
  with reason **answer too long**, code `answer_too_long`. For selector tasks,
  “marker” means the stripped live selector text, not the CSS selector.
  The factor accommodates light formatting; 40 characters allow a short label
  even for tiny values. This is a conservative dump guard, not evidence of truth.
* Keep a chain of candidates: the stripped raw answer first, then every
  successive reduction. Repeatedly remove whitespace, matched straight/curly quotes or backticks,
  markdown `**`, `__`, `*`, `_`, and trailing `. , ; : !`.
  Remove at most one sentence frame: optional `the`/`a`, then 1–6 alphabetic
  words, then `is`, `are`, `was`, `were`, or `: `, then the value. Matching is
  case-insensitive; punctuation/digits in prefix words are not accepted. The
  closed verb list and six-word bound permit labels, not arbitrary paraphrases.
  Wrappers around the resulting value are stripped too. No list syntax or
  trailing clause is removed; any remainder must itself satisfy the span rules.
* For `answer_in_text`, a candidate must contain the marker at the existing token
  boundary. Its normalised length minus the normalised marker length must be
  at most `max(8, len(normalised marker))`, otherwise `answer_too_long`.
  Eight characters allow a little context for tiny values; the proportional
  allowance permits a short local span for longer ones, not a page dump.
* A passing candidate must occur in normalised page text. For selector tasks it
  must equal the normalised live selector text, or that text with trailing
  `. , ; : !` stripped. Any candidate satisfying all applicable checks passes;
  reductions never discard a literally correct candidate. Missing page reads remain
  UNKNOWN, never PASS. Wrong values and ungrounded returned evidence still fail.

The deny/search/claimed-URL/host/URL/empty-answer checks keep their order; the
claimed key-text/value gate still only downgrades a would-be pass.

## Task-key extensions

All arms use the same optional task fields. `grade_observation` copies these
fields into the evidence markers; callers using `evidence_verdict` directly
can supply them in its marker dictionary. Existing tasks need no new fields.

* `full_answer: str` replaces the marker as the reference for both the raw
  `3 * len(reference) + 40` bound and the normalised-excess bound. It does not
  change literal matching or grounding by itself. Without it the old marker
  bounds remain in force.
* `answer_parts: list[str]` opts into individually grounded parts instead of
  one contiguous answer span. One stripped candidate must contain every part
  at token boundaries, within both reference bounds. The literal marker is
  implicitly required too, even if omitted from the list. Every required part
  must independently appear at token boundaries in normalised page text.
  Missing page reads remain UNKNOWN. Empty/malformed part keys without a
  usable marker fail; no part-mode exception permits an unbounded page dump.
* `url_answer_ok: True` permits a URL-only answer instead of the text checks
  and text-length bounds. Matched quotes, angle brackets, backticks, Markdown
  link wrappers and a trailing period are allowed, but surrounding prose is
  not. Both the answer URL and the live final URL must satisfy the same
  positive URL markers (host, URL token, suffix, query); canonical evidence
  alone cannot permit a wrong live final page. Claimed-evidence checks remain.
  Without this explicit flag, URL answers receive the old answer-text checks.

When an expected URL string contains `?`, both the deterministic URL check and
the evidence URL matcher retain their respective prefix/path matching rules
and compare decoded query parameters as an order-independent subset. Extra
parameters are allowed; values are case-sensitive after percent/plus decoding.
Blank values and repeated pairs are preserved. Expected strings without `?`
retain their existing substring behaviour. Claimed/live URL identity rules
are unchanged.

Search-results pages are still denied unless the expected URL key itself
matches the search-results detector. The exception applies to both URL checks
and returned-evidence validation; explicit task deny tokens still apply.

## Runtime gate and freeze procedure

`grade.grade_observation` returns the arm-neutral page grade. The probe's
`grade_observation` applies script_first's existing own-verdict-must-be-PASS
gate on top; completion False also blocks success. Probe rows already record
`page_answer_success`/`page_answer_reason` independently of `success`, so no
duplicate `page_grade_pass` field is needed. Neither page-grade diagnostic is
controller input.

`tests/test_grade_frozen.py` pins SHA-256 of the exact source bytes. To change
the grader, review the rule change deliberately, update its contract tests,
run `sha256sum bench/grade.py`, update the test constant, and record the reason
and new hash here. Current freeze: bounded spans plus task-key full-reference
bounds, grounded parts, opt-in URL answers, decoded query subsets and explicit
search-target exceptions. These changes do not alter runtime self-checks or
retroactively regrade saved measurements.
SHA-256: `7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`
(superseded by the scorer v2 freeze below).

## Scorer v2 (18 Nov 2026)

Scorer v2 applies to tasks that carry a `key_v2` dict: today the 40 extdev
tasks (`bench/keys_extdev_v2.py`, attached in `bench/tasks_extdev.py`). Every
other task keeps the v1 rules above unchanged. The v1 extdev keys
(`end_markers`, `full_answer`, `answer_parts`, `url_answer_ok`) stay in
`bench/tasks_extdev.py` and are still tested with the v1 rules. Every key change,
with the page fact it rests on, is listed in
[KEY_CHANGES](results/scorer_v2_20261118/KEY_CHANGES.md).

Why: the v1 extdev keys agreed with the hand labels on 44 of 109 rows. They
judged page tasks ("find thrill rides") by the words in the answer, judged
question tasks ("who chaired…?") by the URL of one page, and required verbatim
sentences for summaries. Per-row reasons are in
[DISAGREEMENTS](results/scorer_v2_20261118/DISAGREEMENTS.md).

### 1. Decide the deliverable

Read the task description. The key records the result as `deliverable`.

| Deliverable | The task… | Examples | What is graded |
|---|---|---|---|
| `answer` | asks a question, or asks to look up, summarise or write down facts | "Who chaired…?", "summarise the strengths", "look up the IPA and an example sentence" | The answer against the key's facts. The final page only has to be on the task's site; any page on it, including its search page, is fine. |
| `page` | asks to open, show, browse or find a page, set filters or a sort, add to a cart, or reach a contact form | "Find thrill rides…", "Show most played games…", "add all DLC to cart" | The final URL (and, when the key says so, the page text) against the accepted pages. The answer only has to pass checks 6–8 below. |
| `both` | asks for a page state and a reported value | "find career openings in marketing", "list some filters on the results page", "submit and report the message" | Both of the above. |

Why the page is not evidence for `answer` tasks: the key's facts were checked
on the source page, so matching them is the evidence. A right answer read from
another page of the same site (an article instead of the press release) is right.

### 2. Checks, in order

The first check that fails decides. Reason strings are what the grader prints.

1. The key is well formed, else FAIL `invalid v2 key` (fail closed).
2. The final URL is http(s), else FAIL `no final page`.
3. `page`/`both` only: the final URL contains no deny token (default `/signin`,
   `/login`, `/sorry/`) and is not a site-search results page unless the key
   sets `allow_search`. Else FAIL `the page is denied (…)`.
4. A URL the script itself returned must be the live page (v1 rule), else FAIL
   `claimed URL does not match the live page`.
5. The final host equals, or is a subdomain of, a key host, else FAIL
   `the final page is on the wrong host`.
6. The answer is not empty, else FAIL `empty answer`. An agent that reports
   nothing has not finished.
7. The answer is not a failure report, else FAIL `answer reports failure`.
   Grader test (on the normalised answer): starts with "task failed" or
   "failed", or contains "I could not / couldn't / was unable to / am unable to /
   cannot / can't / did not manage to", or "unable to find / access / complete /
   locate / verify / load / open / submit / apply".
8. Dump guard: the raw answer is at most `3 × len(reference) + 300`
   characters, else FAIL `answer too long`. `reference` is the key's written
   model answer, i.e. a complete correct answer (a list task's reference is the
   list). A page dump or a list of guesses does not pass on length.
9. `page`/`both`: the final URL matches at least one accepted page. If none
   matches but one could only be decided from page text that was not read:
   UNKNOWN `page text was not read` (UNKNOWN is never a pass). Else FAIL
   `the final page is not an accepted page`.
10. `answer`/`both`: every fact is in the answer, else FAIL
    `answer misses a required fact`.
11. Script-return gate (v1 rule): key text or values the script returned must
    be on the page, else FAIL `returned evidence is not on the page`.
12. PASS: `the answer matches the key` / `the final page matches the key`.

After the page grade, the v1 gates still apply unchanged: completion False
blocks a pass, and script_first's own verdict must be PASS (probe and
`bench/regrade.py`). v2 grades the live URL only; it does not use the
canonical href.

### 3. Answer formats and facts

A fact is a list of accepted forms; one form must appear in the answer.

* **Normalisation (formatting only):** ™ ® © `*` and backticks are dropped;
  Unicode NFKC; every dash (‐ ‑ ‒ – — ― −) becomes `-`; curly quotes become
  straight; spaces around a dash between digits are removed (`19 – 25` →
  `19-25`); a comma thousands separator between digits is removed
  (`1,000` → `1000`); whitespace collapses; case folds.
* **Token boundaries (v1 rule):** a form may not continue into a letter or
  digit, or through a decimal point: `1000` is not in `10000`, `2.7` is not in
  `2.75`, `Galdo` is not in `Galdós`.
* **Extra text is allowed** (labels, context, a source link, a table), within the
  dump guard. Order does not matter.
* **Accepted forms are listed, not inferred.** Names may omit a suffix only when
  the key lists the shorter form (`Jimmy Butler` for `Jimmy Butler III`); dates
  are accepted in the renderings the key lists (`May 23-28, 2004`,
  `23-28 May 2004`). There is no numeric tolerance: a number must equal the key
  at the key's precision (`32.0`; thousands separators aside). A human grader
  should accept any unambiguous rendering of the same name, date or number;
  the grader accepts only listed ones, so it can falsely reject an unlisted
  rendering but not falsely accept one.
* **All-of forms:** a form can itself be a list that must all appear
  (`["King Denas", "Obelax", "Halfdan"]`).
* **List answers:** "list some X" uses `{"any": [...], "min": n}`: at least `n`
  different listed forms must appear. Every other multi-part question needs
  every fact.
* **Partial answers fail.** An answer with some facts but not all, or the
  right page with a failure report, is not a pass. "Partial" in hand labels
  counts as not correct.
* **Known gap:** an answer that hedges between candidates ("A or B") is wrong
  to a human; the grader only limits it through the dump guard and the facts.

### 4. URL evidence (accepted pages)

An accepted page is a dict; every field it has must hold.

* `path`: case-insensitive, percent-decoded path test. `path_mode` is
  `contains` (default), `prefix` or `suffix`.
* `url_contains`: the v1 raw URL substring test (also sees query and
  fragment); used by derived keys.
* `query`: each named parameter must have a value meeting its condition:
  `any` (exact value in the list), `has` (an item of a comma list, e.g. Amazon
  `rh`), `contains` (case-insensitive substring, any listed word), `prefix`,
  `max`/`min` (numeric). Parameters the key does not name are ignored: tabs,
  tracking ids, paging and sort do not matter unless keyed.
* `query_nonempty`: the URL has a query string.
* `stay_nights`: `checkout − checkin` (or `check_out − check_in`) in nights.
* `text`: phrases that must appear in the page text (same normalisation), for
  end states a URL cannot show (cart contents, a sort label).

A key lists several pages when the task allows several end states ("any Six
Flags park in Texas"; Steam's cart page or its add-to-cart confirmation).
Relative dates ("next month") are fixed to the run month in the key.

### 5. Keys

`key_v2` fields: `deliverable`, `host` (string or list), `pages`, `facts`,
`reference`, optional `deny`, `allow_search`, and `basis` (documentation only).
Keys are judge-only: the prompt builder reads only `description` and
`start_url` (tested with a `key_v2` sentinel), and runtime modules still do not
import `bench/grade.py`.

**Derived keys (validation only).** For a task with no hand-written v2 key, a
v2 key can be derived mechanically from its v1 markers
(`docs/results/scorer_v2_20261118/heldout/derive_keys.py`): `host` from the v1
host; one accepted page from `url_contains`/`path_suffix`/`query_nonempty`;
one fact per v1 answer part (or the marker); `both` when there is a page and a
fact, else whichever exists; `reference` = v1 full answer, else marker; v1 deny
list. Production grading of non-extdev tasks does not use derived keys.

### 6. Freeze

Scorer v2 adds `evidence_verdict_v2` and makes `shared_end_state` and
`grade_observation` use it when a task has `key_v2`; v1 code paths are
unchanged. Contract tests: `tests/test_grade_v2.py` and
`tests/test_extdev.py::test_v2_key_reference_passes_and_decoys_fail`.
Previous SHA-256: `7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`.
SHA-256: `5f459309a799a7f3a6b6b309cb8beb3b51f9b0cf7bb37bb5ec542a5c4a914bde`.
