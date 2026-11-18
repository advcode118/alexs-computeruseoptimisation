# Labelling rubric (scorer v2, docs/GRADER.md sections 1-4)

You are the key author and the grader at once: there is no answer key. Decide
the deliverable from the task text, then judge from the saved evidence (final
URL, returned answer, saved page text) whether the task was done. Where the
rubric says "the key's facts", use the facts the task asks for, as shown by the
saved page text or, if the page text does not show them, by what you can
reasonably verify. Where the rubric says "accepted pages", use the page the
task asks to reach.

Labels:
- correct: the deliverable is done and every requested fact is right.
- partial: part of the task is done, or the saved evidence cannot confirm a required part.
- wrong: no answer, wrong answer, wrong page, or the agent reported failure.

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

