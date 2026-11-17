# heldout4 sealed verification

**128 registered tasks**, authored as 130 ranked tasks and sealed after two
separately preserved full runs. Two tasks failed the final key check and are
explicitly dropped. The 128 survivors all pass their key and both negative
controls in **full run 2 alone**. No earlier-run result rescues a failure.
No ranked additions or targeted verification runs were needed (128 ≥ 120).
No paid model/API calls or live benchmark-arm runs were made: local Playwright,
plain HTTP and local PDF extraction only.

## Base, pin and seal

- Branch: `devin/1794909426-heldout4-seal`, rebased onto fetched main
  `abdf56b048e93b14e2b7074ba848eefda41fc660` after PR #89.
- Fixed grader from the base, unchanged:
  `7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`.
- **Final `bench/tasks_heldout4.py` SHA-256:**
  **`1f9bfa1f77afaf4080da2cff5bbfc70511e3ec3aafce20c98b95ae63939462a3`**.
- Full run 1 input task-module SHA: `277c47d484c3a179c48c656f15ae1790dfc5e38b9500a19752979cc8b0d3d006`.
- Full run 2 input task-module SHA: `46dec4049e6cf64bc9f3b4fdd1b9e9154b0d956036b89ed12e57aa1bdfb542ea`.

The final module hash includes all 130 authored records plus the explicit
`HELDOUT4_DROPPED_TASK_IDS` registry; only 128 enter `heldout4`. The only module
change after run 2 is recording those drops. All surviving keys are identical
to the keys tested in run 2. Run metadata also pins the ledger and verifier.

## Full run 1 — 2026-11-17T10:07:24.475868+00:00

Command: `python -m bench.verify_heldout4` in the authoring virtualenv.
This run preceded the instruction to move the integration-based topic branch
onto main; the grader pin was identical.

```text
Key checks: 101/130 PASS
Reproducers: 14/19 PASS; 111 none; statuses={'PASS': 14, 'FAIL': 2, 'NONE': 111, 'ERROR': 3}
Negatives: 259/259 correctly FAIL; 130/130 tasks covered
Full/partial: 124/6
```

Reproducer rate: 14/19 = 73.68%, including failures/errors in the denominator.
Zero were classified blocked by grader. One key-setup error prevented a
wrong-answer control, but every task had its real wrong-host control.

Evidence, never merged with run 2:

- `results/ext_sample_20261116/verification_heldout4_20261117T100724469791Z.jsonl`
- the adjacent `.summary.json` and `_artifacts/` directory
- `results/ext_sample_20261116/verification_heldout4_full_1.log`

Twenty missing-page-part failures included eighteen multi-page factual keys.
The fixed grader checks every scored part on the final observation, not on a
union of other pages. The lead authorized partial final-page scoring with
explicit unscored parts before run 2. This was not a change to the grader.

## Authorized revisions before run 2

All 29 revisions append superseding ledger lines, with before/after task and
setup fields in `key_revision`. All original lines remain intact. For the
eighteen multi-page keys, `full_answer`, `expected_answer` and the entire
`answer_part_sources` remain unchanged. Only final-page parts are scored;
other required facts and source URLs are retained in `unscored_parts`.
Those keys are explicitly partial and flagged `multi_page_parts`.
The legacy answer marker is a scored final-page literal, never an unscored fact.

| Task | Recorded correction |
| --- | --- |
| `ho4_search_pizza_six_nearby` | Search-recognizable path and required query subset replace a bare query fragment; date remains an incidental UI default. |
| `ho4_form_boston_parking_button` | Read the visible generated-code textarea value after real UI generation; body.innerText omits dynamically assigned textarea values. |
| `ho4_form_ua_egift_card_100` | Establish complete anonymous cart/editor session through recorded UI steps; read actual final cart state without discarding the editor by another navigation; require exact final URL and message readback. |
| `ho4_form_uk_english_euros` | Bind selected language/currency by actual option values, not exact emoji-prefixed display-label equality; still read visible selected labels. |
| `ho4_value_acl_2024_subsidy_deadlines` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_sigchi_fy25_expense_reduction` | Align legacy answer marker with literal parts present in both full reference and live page; all scored facts retained. |
| `ho4_value_ash_66_abstract_session_information` | Use the already authored final-page alternative containing Abstract Sessions, rather than the program-search landing page without that literal; retain historical-date limitation explicitly as partial. |
| `ho4_value_acl_2023_subsidies_workshops` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_ion_rescue_navigation_awards` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_fall_guys_two_powerups` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_schlageter_vldb_bibliography` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_igg_art_and_ocean_charity` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_acl_2023_six_program_chairs` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_fall_guys_creative_features` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_ion_early_achievement_researchers` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_aoe_historical_campaign_figures` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_cigre_2025_full_paper_deadlines` | Verifier extracts real browser-downloaded PDF text with pypdf; preserves download bytes/hash and source URL, without substituting authored text. |
| `ho4_value_poms_fellows_2011_2022` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_myth_of_empires_s3_promo_gathering` | Align legacy answer marker with literal parts present in both full reference and live page; all scored facts retained. |
| `ho4_value_webconf_2024_deepfakes_llm_day` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_nime_2024_vietnamese_korean_instruments` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_fall_guys_winter_blunderland` | Use literal ordinal dates 12th/15th from page and unchanged full reference, rather than numeric substrings rejected by token-boundary checks. |
| `ho4_value_playstation_2025_samurai_games` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_aoe_iv_malian_japanese_units` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_myth_of_empires_unconventional_resources` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_civ_vii_tecumseh_shawnee_synergy` | Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_nmun_nyc_deadlines` | No required literal on the current yearless position-paper page: use the already authored 2025 archive PDF alternative supporting its two historical position-paper literals. Authorized multi-page partial key: score only final-page literals; preserve full reference, all part provenance and explicit unscored_parts; no pooled page text. |
| `ho4_value_coursera_berkeley_engineering_deadline` | Align legacy answer marker with literal parts present in both full reference and live page; all scored facts retained. |
| `ho4_form_ikea_tempe_store_events` | Support recorded URL-only key setup; bind selected-store button to its literal part instead of comparing the whole prose reference to a button label. |

Two obvious authored final-page alternatives were used: the ASH program page
for its session-type literal (with historical-date limitation still explicit),
and the linked 2025 NMUN background-guide PDF when the current yearless page
contained none of its required literals. PDF text is extracted from the actual
browser download using `pypdf` (now a declared dependency), never from stored
authored answers. Visible control values are read only from actual controls;
selected options are validated by their real option value, including when the
display label has a flag emoji. Anonymous cart keys prepare real UI state;
independent reproducers use fresh contexts. No checkout/payment/post was sent.

### Explicitly unscored parts (partial keys only)

- `ho4_value_acl_2024_subsidy_deadlines`: `July 9th, 2024, 23:59 (AoE)` — https://2024.aclweb.org/calls/subsidies/
- `ho4_value_acl_2023_subsidies_workshops`: `May 31, 2023` — https://2023.aclweb.org/calls/subsidies/
- `ho4_value_ion_rescue_navigation_awards`: `Major Geoffrey A. Laing` — https://www.ion.org/awards/2000-Superior-Achievement-Laing.cfm
- `ho4_value_fall_guys_two_powerups`: `Bean Ball` — https://www.fallguys.com/news/fall-guys-power-party-update
- `ho4_value_schlageter_vldb_bibliography`: `VLDB 2000` — https://www.vldb.org/dblp/db/indices/a-tree/s/Schlageter:Gunter.html
- `ho4_value_igg_art_and_ocean_charity`: `Jiang` — https://www.igg.com/charity/?pageno=4
- `ho4_value_acl_2023_six_program_chairs`: `Yun-Nung` — https://2023.aclweb.org/calls/tutorials/; `Chen` — https://2023.aclweb.org/calls/tutorials/; `Margot Mieskes` — https://2023.aclweb.org/calls/tutorials/; `Siva Reddy` — https://2023.aclweb.org/calls/tutorials/
- `ho4_value_fall_guys_creative_features`: `Buttons` — https://www.fallguys.com/news/fall-guys-fall-force-update?lang=en-US
- `ho4_value_ion_early_achievement_researchers`: `Tyler` — https://www.ion.org/awards/2023-Early-Achievement.cfm; `Reid` — https://www.ion.org/awards/2023-Early-Achievement.cfm
- `ho4_value_aoe_historical_campaign_figures`: `Rajendra Chola` — https://www.ageofempires.com/games/aoeiide/dynasties-of-india/
- `ho4_value_poms_fellows_2011_2022`: `Chris Tang` — https://www.poms.org/node/403
- `ho4_value_webconf_2024_deepfakes_llm_day`: `Jeannie` — https://www2024.thewebconf.org/program/keynotes/; `Paterson` — https://www2024.thewebconf.org/program/keynotes/
- `ho4_value_nime_2024_vietnamese_korean_instruments`: `đàn Bầu` — https://nime.org/proc/nime2024_65/index.html
- `ho4_value_playstation_2025_samurai_games`: `Ghost of Yōtei` — https://www.playstation.com/en-us/, https://www.playstation.com/en-us/games/ghost-of-yotei/, https://blog.playstation.com/2025/11/19/new-game-plus-comes-to-ghost-of-yotei-november-24/
- `ho4_value_aoe_iv_malian_japanese_units`: `Musofadi Gunner` — https://www.ageofempires.com/games/age-of-empires-iv/civilizations/malians/
- `ho4_value_myth_of_empires_unconventional_resources`: `KongMing Lantern` — https://www.mythofempires.com/newsall/news/2024/0815/625.html; `copper coins` — https://www.mythofempires.com/newsall/news/2024/0815/625.html; `honor points` — https://www.mythofempires.com/newsall/news/2024/0815/625.html; `beast lord related items` — https://www.mythofempires.com/newsall/news/2024/0815/625.html
- `ho4_value_civ_vii_tecumseh_shawnee_synergy`: `Nicaakiyakoolaakwe` — https://civilization.2k.com/civ-vii/game-guide/leaders/tecumseh/
- `ho4_value_nmun_nyc_deadlines`: `15 February` — https://www.nmun.org/conferences/new-york/register-and-plan-your-trip/plan-your-trip/hotel-information.html#main

These parts remain required by the natural-language question but **are not
enforced by the current partial key**. Passing a partial key is not proof of a
complete response to all parts of that question.

## Full run 2 (last full run) — 2026-11-17T10:41:33.228861+00:00

Command: `python -m bench.verify_heldout4 --output
docs/results/ext_sample_20261116/verification_heldout4_full_2.jsonl`.

```text
Key checks: 128/130 PASS
Reproducers: 15/19 PASS; 111 none; statuses={'PASS': 15, 'NONE': 111, 'ERROR': 4}
Negatives: 260/260 correctly FAIL; 130/130 tasks covered
Full/partial: 106/24
```

Reproducer rate: 15/19 = 78.95%; zero blocked by grader.

**Reporting error:** the command exited 1 only after writing all 130 unique
task records, the complete summary and the four lines above. Its last
`print(output.relative_to(ROOT))` rejected the relative CLI output path:
`ValueError: ... is not in the subpath ... OR one path is relative and the other
is absolute.` The reporter now prints the supplied path without that invalid
conversion; regression tests cover relative and external absolute output paths.
No task result was recomputed, replaced or merged, and **no third full run**
was made for this non-grading reporting fix.

- `results/ext_sample_20261116/verification_heldout4_full_2.jsonl`
- `results/ext_sample_20261116/verification_heldout4_full_2.summary.json`
- `results/ext_sample_20261116/verification_heldout4_full_2.log` (includes traceback)
- `results/ext_sample_20261116/verification_heldout4_full_2_artifacts/`

Read physical newline-delimited JSON records by iterating the file, not by
Unicode `str.splitlines()`: real page text can contain Unicode separators in
otherwise valid JSON strings.

## Drops and final registered population

Both drops have append-only `disposition: dropped`, reason
`ungradeable_end_state`, `drop_run` and exact `drop_key_reason` fields:

- `ho4_form_boston_parking_button`: generated code had the requested company,
  dimensions and radius, but its live link pointed to the generator page
  (`/how-to-add-parking-info-to-your-website?distance=15`), not the keyed Navy
  Yard destination. This is not labelled a proven site bug; the recorded
  setup did not establish the required output.
- `ho4_form_ikea_tempe_store_events`: event-page literals appeared, but the
  selected-store control readback did not exactly match `Tempe, AZ`. A UI label
  versus binding issue is not ruled out. The task is dropped rather than
  relaxing the failing persisted-state check after the last run.

No key/negative failures remain in the final registered subset:

```text
Registered tasks: 128 (130 authored; 2 dropped)
Keys: 128/128 PASS
Negatives: 256/256 correctly FAIL; 128/128 tasks covered
Reproducers: 15/18 PASS; 110 none; 3 ERROR
Full/partial: 104/24
```

This subset is drawn exclusively from run 2, not a separate run. Its machine
readable manifest is
`results/ext_sample_20261116/verification_heldout4_sealed_subset.summary.json`.
Final reproducer pass rate: **15/18 = 83.33%**, errors included.

The three retained reproducer errors are JetBlue `Locator.fill`, SoundCloud
`Locator.click`, and Trainline `Locator.select_option` timeouts (15 seconds).
Each task's independent key and negatives passed in run 2. Their UI/selector/
readiness causes are unverified; they are not counted as successful reproducers
or automatically blamed on sites. Trainline's key succeeded but its separate
reproducer timed out, so its observed browser/UI variability remains explicit.
No targeted reruns were merged to hide this variability.

### Sources, kinds, scope and intent

| Registered source | Count |
| --- | ---: |
| `AssistantBench` | 3 |
| `Mind2Web-Live` | 67 |
| `WebVoyager` | 8 |
| `WebWalkerQA` | 50 |

The authored counts were Mind2Web-Live 69, WebWalkerQA 50, WebVoyager 8 and
AssistantBench 3. Unfilled WebVoyager/AssistantBench quota slots were filled in
fixed source/rank order by 14 additional Mind2Web-Live tasks. Mind2Web train
remained fill-only and was not needed. Dropping two Mind2Web-Live tasks leaves
the registered counts above; authoring order and original decisions are intact.

| Registered kind | Count |
| --- | ---: |
| `filter` | 20 |
| `form` | 2 |
| `multisite` | 1 |
| `nav` | 29 |
| `search` | 5 |
| `spa` | 2 |
| `value` | 69 |

Full/partial **104/24**; script/none **18/110**. All eighteen multi-page partials
survive. Filters, forms, SPA state, cross-site intent and the real map/PDF
artifact task remain included; length or lack of a script was not an exclusion.
The registered set uses 60 registrable sites, with at most three tasks
per site and no overlap with any other split, including extdev. Extra key and
provenance fields never enter task prompts (covered by offline tests).

### Effective manual/automatic exclusions (before sealing drops)

| Reason | Count |
| --- | ---: |
| `captcha_or_bot_block` | 29 |
| `duplicate_task` | 3 |
| `login` | 16 |
| `no_checkable_key` | 12 |
| `payment` | 3 |
| `site_cap` | 325 |
| `site_gone_or_content_gone` | 76 |
| `volatile_lt_1day` | 26 |

`no_checkable_key` subreasons: **computed 12; ungradeable_end_state 0**.
The **two sealing drops** above are separately counted as
`ungradeable_end_state`, not retroactively rewritten into manual exclusions.
No factual multi-page task was excluded for being multi-page.

One judgement: the Resy/X share task was excluded for the authenticated account
needed to publish a post. The anonymous X intent stayed blank even on a
readiness trial; its blank-render cause is unverified, not an observed login
wall. No account creation or post was attempted.

### Registered grader flags

| Flag | Count |
| --- | ---: |
| `artifact_output` | 1 |
| `cart_quantity` | 1 |
| `compound_answer` | 61 |
| `download_end_state` | 2 |
| `form_value_evidence` | 2 |
| `length_cap` | 35 |
| `link_attribute_evidence` | 1 |
| `multi_page_parts` | 18 |
| `non_unique_answer` | 6 |
| `nonfinal_or_nontext_evidence` | 29 |
| `pdf_evidence` | 2 |
| `search_results_url` | 4 |
| `url_only_answer` | 51 |

These are retained authoring/audit flags, not automatic grader blocks or passes.
The fixed grader is unchanged. No expected answer was inserted into live page
observations, and supporting-page text was never pooled into the final page.

## Offline checks and environment

Live browser runs used the existing authoring virtualenv (Python 3.10,
Playwright 1.65.2 and pypdf 7.1.0). Offline suite execution uses the supported
Python 3.11.18 environment installed with `pip install -e '.[dev]'`.
The full-suite output is recorded below. The source snapshots
including the raw CRLF files are not modified by sealing.

### Offline suite history

Command: `python -m pytest -q bench/test_harness.py tests`, Python 3.11.18,
with model API credentials cleared from the child environment.

Initial full suite:

```text
6 failed, 1180 passed, 1 skipped in 61.57s (0:01:01)
```

Five failures came from Node not being on the new environment's PATH. The
environment was repaired once by loading Playwright's installed Node v26.13.1
onto the persistent checking shell's PATH; no replay or production code changed.
The full suite after that environment repair:

```text
FAILED tests/test_answer_required.py::test_task_asks_value_precision_on_every_task
1 failed, 1185 passed, 1 skipped in 64.61s (0:01:04)
```

Its exact assertion is `n=523 tp=329 fp=21 fn=143 tn=30 precision=94%
recall=70%`. Every one of the 21 false positives is a newly registered heldout4
task with `answer_type: url` and `url_answer_ok: True`; the base-only catalog
has zero false positives under the unchanged oracle. The old offline
`_ground_truth()` helper defines any bare URL key with no text marker as
non-value, whereas these keys explicitly use the URL itself as the answer.
The description-only runtime heuristic predicts an answer is needed.

The lead approved a test-only oracle extension: explicit `url_answer_ok: True`
URL answers are answer-required, while legacy bare navigation URLs retain their
old behavior. Regression coverage includes explicit, legacy, false-flag, empty
and whitespace cases. No precision assertion was relaxed. No classifier,
grader, descriptions or score keys were changed for this compatibility fix.

The lead supplied `docs/HELDOUT4_PLAN.md`; it is committed as supplied, without
edits. All counts in its "Set as written" section agree with this report.

Final full suite after that approved test-only change:

```text
1187 passed, 1 skipped in 60.58s (0:01:00)
```

Raw output: `results/ext_sample_20261116/heldout4_pytest_final.log`.
The task-module seal and fixed-grader pin remain unchanged.
