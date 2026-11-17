# extdev model-free verification

Generated 2026-11-17T01:03:55.001203+00:00. Run `python -m bench.verify_extdev`.

Only local Playwright bundled Chromium (headless, default fresh contexts, matching the existing verifiers) and the unchanged deterministic grader run. No probe/model/API call.

## Authoring and shortfall

The expanded reserve contains 442 extdev candidates. There are 382 effective authoring decisions; the walk stops at exactly 40 accepted tasks. Descriptions remain verbatim and all text_edits are empty. All retained keys were derived on live pages rather than trusting source reference answers.

Source quotas were attempted in Mind2Web-Live, WebWalkerQA, WebVoyager, AssistantBench order, then shortfalls filled in that order with Mind2Web train last. Only accepted tasks consume the three-per-site cap. Seed, ranking and site assignment are unchanged. The original 50 STEP-2 ledger lines are preserved, followed by superseding revised decisions for all five former multi-page exclusions. Statistics use the latest decision per source/id, not historical exclusions.

Kept by source: `{'Mind2Web-Live': 16, 'WebWalkerQA': 12, 'WebVoyager': 9, 'Mind2Web': 3}`. Kinds: `{'filter': 10, 'value': 20, 'spa': 1, 'nav': 8, 'search': 1}`.
Manual exclusions: `{'site_gone_or_content_gone': 5, 'volatile_lt_1day': 62, 'login': 12, 'payment': 1, 'captcha_or_bot_block': 9, 'no_checkable_key': 11, 'site_cap': 235, 'duplicate_task': 7}`. See [the complete ledger](results/ext_sample_20261116/authoring_extdev.jsonl) for individual decisions and sub-reasons.

no_checkable_key sub-reasons: `{'computed': 4, 'ungradeable_end_state': 7}`. Duplicate exclusions name their already-accepted task ID. Duplicate matching normalizes case/punctuation/whitespace and removes trailing site/domain/brand suffixes, including Steam's public brand alias.

## Key policy and limitations

Factual multi-page answers are retained. Compound/multi-page tasks use one specific literal fragment plus its page URL as a partial key; other fragments are audit-only unchecked_fragments, never checked by grading or sent to prompts. A partial PASS does not verify the full answer. Only truly computed answers and explicitly authorized ungradeable UI end states remain no_checkable_key. Search URLs rejected by is_search_results_url and submitted values without readable traces are not replaced by upstream/incomplete keys.

The five re-admitted tasks check final fragments on the 2022 Rovio report, 2023 sustainability report, and Ironhide articles 370, 98 and 307. Their other-page facts stay unchecked. Ironhide's April 2023 source is a free-game promotion, not a new release; its source wording is retained with this limitation in the ledger. Previously provisional Rovio campaign/Topgolf fills are skipped at the accepted-site cap after re-admission; no original kept task is dropped.

Dota's cart key requires session state: the verifier first genuinely adds all cartable DLC via the UI, then directly reloads the cart URL for the key check. A separate fresh context runs the reported reproducer. No cookies are persisted and checkout is never submitted. Cart prices are not keyed.

Steam's daily-player view has visible selected-metric text but no persistent deep link: the key check loads the charts page directly, then selects By Daily Players before grading. Reload resets it to By Current Players. This is a UI-state key, not a player-count or game-ranking quotation. Amazon key checks establish a normal start-page session before direct final-URL navigation; no browser fingerprints, headers or cookies are forged. Reproducer none is used for archive/article discovery or heavy/legacy dynamic UI.

The new Airbnb tiny-home search uses the United States as one permissible location for anywhere, with one adult, two pets and the next April 10–12 (2027). The castle query encodes Europe, a week in December (next month at authoring), and the price ceiling, not a live nightly quotation. Eventbrite's exercise query encodes the next July 10–31 (2027). These keys check search criteria, not available inventory or result counts; relative-month keys require refresh after November 2026.

The first expanded-set full run found five key failures (35/40 keys, 12/13 reproducers) and three blocked Cambridge root decoys (77/80 negatives). Its unmerged evidence is preserved in verification_extdev_step3_initial.jsonl. Five append-only rekeyed ledger lines retain that key history. Hugging Face's full AutoClass example lies beyond the unchanged 8,000-character evidence window; the official TensorFlow Serving guide supplies the literal from_pt=True flag in readable evidence, with other steps kept unchecked. Booking's About page supplies the parent-company fact in main content rather than an excluded homepage footer. Airbnb keys couple their COMPLETE filter URLs to main-content property-type captions rather than excluded date-header text. Amazon's rating-facet marker tolerates query ordering and still requires /s plus the complete green-controller name. No grading code changed.

Six Flags keys encode park and selected category, not fluctuating operating hours or ride availability. Booking's Los Angeles directory exposes stable filter labels without dated availability or prices being keyed. The Times Square page preserves hotel/class=4 filtering; two-adult occupancy is unchecked. Airbnb's legacy category URL still renders mansions in Europe; Any month and 3 guests are recorded but unchecked. Source 2024 flexible-date parameters are not used as a fixed stay. ICSE's historical source uses HTTP, preserved verbatim.

## Prompt isolation audit

bench/browser_use_arm.py:task_text selects only description/start_url and calls bench.tasks.task_message. bench/harness.py builds user messages through task_message(description, start_url); run_task discards expected_answer/judge_prompt. The live script_first runtime receives empty end_markers. No whole-task-dictionary prompt serialization was found. Provenance, key_scope and unchecked_fragments stay outside those inputs. No prompt or grading code was changed.

## Verification history and Booking flakiness

**Booking is flagged as a flaky site.** The requested single full run became
**three full runs**, a deviation from the requested procedure. The full runs
remain separate and their failures are not replaced or merged with targeted
reruns:

| Full run | Direct keys | Reproducers | Correctly failing negatives | Evidence |
|---|---|---|---|---|
| 1 | 35/40 | 12/13 | 77/80 | [Initial](results/ext_sample_20261116/verification_extdev_step3_initial.jsonl) |
| 2 | 40/40 | 11/13 | 77/80 | [After key fixes](results/ext_sample_20261116/verification_extdev_step3_keyfix.jsonl) |
| 3 | 39/40 | 13/13 | 79/80 | [Last full run](results/ext_sample_20261116/verification_extdev.jsonl) |

Full run 3 was **39/40 with empty Booking Times Square evidence**. Both its
direct key and wrong-value negative were `UNKNOWN: page text was not read`.
That task passed the two earlier full runs. Whether the empty evidence was
caused by delayed rendering or blocking was not established.

The subsequent verifier-only readiness change waits up to 15 seconds, only on
Booking URLs, for nonempty text in the same `main`-or-`body` root the existing
grader reads. It does not wait for the expected answer, reload the page, retry
navigation, change markers, change the grader, or count an exception as PASS.
Timeouts remain verification failures. This is bounded handling of the observed
empty-read symptom, not a claim that Booking's flakiness has been eliminated.

Per the follow-up authorization, **only the three Booking tasks were rerun,
three times**, after this change. Tasks were sequential within each trial;
each trial launched fresh bundled Chromium, with fresh contexts for key checks
and independent reproducers. These are targeted follow-ups, not a fourth full
run and not an all-pass replacement for full run 3.

| Booking-only trial | Direct keys | Reproducers | Correctly failing negatives | Evidence |
|---|---|---|---|---|
| 1 | 3/3 PASS | 2/2 PASS; 1 none | 6/6 | [Trial 1](results/ext_sample_20261116/verification_extdev_booking_rerun_1.json) |
| 2 | 3/3 PASS | 2/2 PASS; 1 none | 6/6 | [Trial 2](results/ext_sample_20261116/verification_extdev_booking_rerun_2.json) |
| 3 | 3/3 PASS | 2/2 PASS; 1 none | 6/6 | [Trial 3](results/ext_sample_20261116/verification_extdev_booking_rerun_3.json) |

All three trials covered `extdev_filter_booking_times_square`,
`extdev_search_booking_la_filters`, and `extdev_value_booking_parent`; every
row has an empty errors list. The Times Square task has no scripted reproducer.
The focused offline regression suite after the readiness change reported
`47 passed in 11.23s` (`python -m pytest -q tests/test_extdev.py`).

## Full run 3 results (before Booking readiness handling)

```text
Key checks: 39/40 PASS
Reproducers: 13/13 PASS; 27 none
Negatives: 79/80 correctly FAIL
Partial keys: 18/40
```

A second full run passed all 40 keys but encountered the late Booking sign-in overlay and three blocked Cambridge neighboring-article decoys (11/13 reproducers, 77/80 negatives); it is preserved in verification_extdev_step3_keyfix.jsonl. Booking reproducers now await/dismiss the observed optional sign-in overlay, then click genuine homepage links: About Booking.com or Los Angeles hotels. No final-page URL is injected by a reproducer. Cambridge second-page requests repeatedly returned HTTP 403, so its second control deliberately uses an unrelated host rather than counting blocked content as a successful negative. Each Cambridge task still has a wrong-answer negative on its actual, readable final article.

Each negative is a wrong answer on the final page and the correct answer on a live decoy. The start page is normally the decoy; Cambridge and tasks that start on their final page use example.com as a wrong-host control. Exceptions are failures, never successful negative controls. Results above are one fresh full run over all 40 final tasks after key/reproducer revisions, not merged targeted rechecks. Earlier full attempts are retained explicitly, not presented as passing runs.

| Task | Direct key | Reproducer | Negative controls |
|---|---|---|---|
| extdev_filter_greatamerica_thrill | PASS | PASS | 2/2 |
| extdev_value_nba_2021_leaders | PASS | none | 2/2 |
| extdev_spa_dota_dlc_cart | PASS | PASS | 2/2 |
| extdev_filter_booking_times_square | FAIL | none | 1/2 |
| extdev_filter_frontiercity_family | PASS | PASS | 2/2 |
| extdev_nav_spothero_contact | PASS | PASS | 2/2 |
| extdev_filter_airbnb_europe_mansions | PASS | none | 2/2 |
| extdev_value_icse_2004_chair | PASS | PASS | 2/2 |
| extdev_value_icse_duplicate_statement | PASS | PASS | 2/2 |
| extdev_value_icse_2002_chairs | PASS | none | 2/2 |
| extdev_value_rovio_anniversary | PASS | none | 2/2 |
| extdev_value_apec_tourism_actions | PASS | none | 2/2 |
| extdev_value_apec_peru_arrivals | PASS | none | 2/2 |
| extdev_value_apec_ministers_chair | PASS | none | 2/2 |
| extdev_search_booking_la_filters | PASS | PASS | 2/2 |
| extdev_value_hf_first_user_message | PASS | none | 2/2 |
| extdev_value_hf_tei_strengths | PASS | none | 2/2 |
| extdev_nav_ronaldo_world_cup_stats | PASS | none | 2/2 |
| extdev_nav_nets_schedule | PASS | none | 2/2 |
| extdev_nav_fiestatexas_events | PASS | PASS | 2/2 |
| extdev_nav_spothero_marketing | PASS | PASS | 2/2 |
| extdev_filter_amazon_puppy_food | PASS | PASS | 2/2 |
| extdev_nav_eventbrite_planning | PASS | none | 2/2 |
| extdev_filter_sam_harris_paperback | PASS | none | 2/2 |
| extdev_nav_steam_daily_players | PASS | none | 2/2 |
| extdev_nav_commuter_benefits | PASS | PASS | 2/2 |
| extdev_value_dream_blast_revenue | PASS | none | 2/2 |
| extdev_value_pirate_treasures | PASS | none | 2/2 |
| extdev_value_inclusive_strategy_role | PASS | none | 2/2 |
| extdev_value_ironhide_historical_games | PASS | none | 2/2 |
| extdev_value_ironhide_arcade_gdc | PASS | none | 2/2 |
| extdev_value_cambridge_euphoria | PASS | none | 2/2 |
| extdev_value_hf_pytorch_tensorflow | PASS | none | 2/2 |
| extdev_value_cambridge_gestalt | PASS | none | 2/2 |
| extdev_value_cambridge_innovate | PASS | none | 2/2 |
| extdev_filter_green_xbox_controller | PASS | PASS | 2/2 |
| extdev_value_booking_parent | PASS | PASS | 2/2 |
| extdev_filter_tiny_home_dates | PASS | none | 2/2 |
| extdev_filter_sf_exercise_dates | PASS | none | 2/2 |
| extdev_filter_castles_europe_week | PASS | none | 2/2 |

## Failures

- `extdev_filter_booking_times_square`: key: UNKNOWN: page text was not read
- `extdev_filter_booking_times_square`: wrong value: UNKNOWN: page text was not read
