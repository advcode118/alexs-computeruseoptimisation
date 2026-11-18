# Scorer v2: grader vs label agreement

Strict agreement: grader PASS ⇔ label `correct`; `partial` counts as not correct.
"Final" grades are what `bench/regrade.py` reports (page grade plus script_first's
own-verdict gate); "page" grades leave that runtime gate out. Machine-readable:
`agreement.json`; per row: `extdev_rows.csv`, `heldout_rows.csv`.
Reproduce: `python docs/results/scorer_v2_20261118/agreement.py`.

## Summary

| Set | Labels | n | Grader | Agree | Strict agreement | False accepts | False rejects |
|---|---|---:|---|---:|---:|---:|---:|
| extdev | original (Devin, not blind) | 109 | v1 (7ff695b5) | 44 | 40.4% | 0 | 65 |
| extdev | original (Devin, not blind) | 109 | **v2** | 108 | **99.1%** | **1** (U31) | 0 |
| extdev | corrected (1 row, below) | 109 | **v2** | 109 | **100.0%** | **0** | 0 |
| held-out | blind Opus labeller | 55 | v1 | 50 | 90.9% | 0 | 5 |
| held-out | blind Opus labeller | 55 | **v2** (derived keys) | 51 | **92.7%** | **0** | 4 |

Page grade only (no own-verdict gate): extdev v2 108/109 original, 109/109
corrected; held-out v2 52/55 (94.5%, 0 false accepts), v1 51/55.

**Read the extdev numbers as in-sample.** The v2 rules and keys were written while
reading these 109 rows, their labels and the label notes. 99% there shows the
rules can express the labels; it is not evidence that they generalise. The
held-out number is the test, and it is weak in a different way (next section).

## Confusion tables

Extdev, v2 final vs original labels:

| | correct | partial | wrong |
|---|---:|---:|---:|
| PASS | 81 | 1 | 0 |
| FAIL | 0 | 9 | 18 |

Extdev, v2 final vs corrected labels:

| | correct | partial | wrong |
|---|---:|---:|---:|
| PASS | 82 | 0 | 0 |
| FAIL | 0 | 9 | 18 |

Extdev, v1 final vs original labels (baseline):

| | correct | partial | wrong |
|---|---:|---:|---:|
| PASS | 16 | 0 | 0 |
| FAIL | 65 | 10 | 18 |

Held-out, v2 final vs blind labels (the labeller used no `partial`):

| | correct | wrong |
|---|---:|---:|
| PASS | 27 | 0 |
| FAIL | 4 | 24 |

Held-out, v1 final vs blind labels: PASS|correct 26, FAIL|correct 5, FAIL|wrong 24.

## Label correction (extdev)

| Row | Task | Original | Corrected | Why |
|---|---|---|---|---|
| U31 | ironhide_arcade_gdc | partial | correct | Answer "Kingdom Rush; Junkworld" is the WebWalkerQA source answer "Kingdom Rush and Junkworld" (articles 42 and 307). The label was partial only because the saved final page (`News/2023?page=2`) does not show the GDC prize; the v2 rule does not require the answer's page for an answer task. |

No label was corrected towards *less* credit: under the written rules no
`correct` label is too lenient. That is a statement about the rules, so the rule
choices that decide it are listed next.

## Rule choices that decide labels

These v2 rules agree with the lenient parts of the (non-blind) extdev rubric. A
stricter rubric would flip these rows from PASS to FAIL:

* **Answer tasks may end on any page of the site** (20 rows): D13, D32, D40,
  D41, D44, D45, D48, D53, D56, D61, U4, U11, U12 (site search page), U14, U16,
  U24, U27, U30, U31, U37. Keeping v1's "the keyed URL" for answer tasks would
  put extdev agreement at 88/109 (81%).
* **Answers on a page that shows a security check** (U32, U35): the answer equals
  the key verbatim; the saved page is Cambridge's verification screen.
* **Alternative end states cited from saved pages** (10 rows): D9 (Steam
  add-to-cart confirmation, not the cart page), D80/U20 (Six Flags Over Texas;
  also on a `?event-type=groups` tab), D77 (Fiesta Texas, groups tab: query tabs
  are ignored), D85/U22 (other Amazon search words and extra filters), U38
  (a tiny-home listing page, not the search page), U40 (fixed 7-night December
  dates instead of a flexible week), D81/D84/U21 (careers list, not the role page).
* **Item answers without the filter page** (D13, U4, U24): any cited 4-star
  Times Square hotel or 4+-star Sam Harris paperback; the filter URL is not
  required. D16 (Millennium Hotel Broadway) stays FAIL: no saved page shows its
  star rating.
* **Same-site disagreement** (D40): ICSE's own history page says May 19-24, 2002;
  the committee page says May 19-25. Both are accepted.

The partial/wrong rows still fail: dumps (D83 by the dump guard; D79 by the
own-verdict gate), unconfirmed Amazon rating filter ids (D87, D88), a checkpoint
page (U36), missing steps (U33), names without values (D7), dates without the
chair (D31), failure reports (D25, U7, U34) and wrong answers (U29).

## Held-out set

* **Selection** (committed before labelling, `heldout/selection.json`): 55
  de-duplicated rows, 41 tasks, about 35 sites, from dev3, dev4form, dev4spa,
  held-out (Nov 11) and heldout2 runs in `docs/results/form_specialist_20261114`
  and `docs/results/strategy_spa_20261114` — every non-extdev row in the repo whose
  last self-check read page text at the row's own final URL. Never heldout3 or
  heldout4. Selection SHA-256
  `4037b8db86fdd3ae37c46593e7ed1a793729fbeb31368bd24a66818abe3b0184`.
* **Keys:** derived mechanically from the v1 markers (`heldout/derive_keys.py`,
  `heldout/derived_keys.json`), frozen in commit `aa9bda7` together with the
  rules, before the labels existed. No held-out key was written or edited by hand.
* **Labeller:** one Claude Opus subagent, given only task, final URL, answer,
  page text and the frozen rubric (`heldout/labeller_rubric.md` = GRADER.md v2
  sections 1-4). No keys, verdicts or earlier labels. Labels committed
  (`5117d94`) before agreement was computed; computed once, no tuning after.
* **The 4 held-out false rejects:**
  * H02 (blazedemo purchase): page grade PASS; only script_first's own verdict
    (FAIL) blocks it. Runtime gate, not the scorer.
  * H21 (Roman numerals): the script returned a URL that is not the live page;
    the kept v1 rule fails it.
  * H52 (Selenium form): the v1 marker "Received!" is stale; the page now says
    "Form submitted". The derived key inherits the stale marker.
  * H54 (w3schools form): the script's returned evidence is not on the page;
    the kept v1 script-return rule fails it.

## Limits

* Held-out rows are all script_first runs on form and SPA demo sites with short
  exact values. v1 already agrees 90.9% there, so the set shows that v2 adds no
  false accepts on other tasks, but it barely tests the rules that changed most
  (answer tasks off the keyed page, list answers, alternative end states).
* The held-out labeller used no `partial`; the extdev labeller did.
* While building the selection I printed a one-line list of the held-out task
  ids, answers and final URLs (before writing the rules). The held-out keys are
  mechanical, so this could not tune keys, but it was not a fully blind setup
  for the rule author.
* One labeller per set, both AI. Extdev labels were written by Devin, not blind
  (it saw the v1 verdicts and keys). No second labeller, so no inter-rater figure.
* 109 + 55 rows, one run each; site- and task-clustered, so the percentages
  have wide uncertainty.
