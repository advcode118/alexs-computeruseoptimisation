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
SHA-256: `7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`.
