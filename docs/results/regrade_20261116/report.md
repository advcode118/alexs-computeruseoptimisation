# Offline frozen-grader re-grade

## Method

Reproduce from the repository root: `python tools/regrade.py --out docs/results/regrade_20261116`.

Rules: [GRADER](../../GRADER.md); timing: [MEASUREMENT](../../MEASUREMENT.md).
Frozen grader SHA-256: `0e65aecefd0d99f2313b6124495014f7ac2bd7acfb1e9c190a625eec12241752`.

Discovery covers current docs/results JSONLs, latest saved paths from git log --all
(remote-only files read with git show), and the sanitized #82 pilot JSON export.
One version per path is counted, not every historical revision. Repeated runs remain
separate observations: these are descriptive pooled rates, not independent-task estimates.

Task splits/markers come from current bench/tasks*.py, not filenames or saved split labels.
Skipped rows are excluded. Version-2 rows with saved grade_page_text (including empty text)
use grade.grade_observation plus script-first's end_state==PASS gate. Legacy no-answer-marker
rows are unaffected; non-answer failures and failed own-verdict gates remain failures.
Legacy answer-side checks call the frozen evidence_verdict on synthetic text containing
all frozen reduction candidates: this neutralizes page membership, never claims to recover it.
Old passes imply page membership. A saved selector truth also implies page membership.
Answer-related old text-marker failures that now satisfy the span rules are potential
fail->pass only, not new passes, because actual page text is missing. Missing truth/claims
or failure reasons are not invented. Categories and potential counts are in regrade.json.

Per-file old pass counts cover all non-skipped rows; new pass counts cover known grades.
Dataset old/new rates and delta use the SAME re-gradable subset (R); unknowns are not failures.
'Raw absent' dataset rows denote aggregate-only files, not zero attempts or a 0% pass rate.
Heldout3 is aggregate-only in both outputs: no task ids, answers or per-row records.

The #82 segments pilot is docs/PR_INTEGRATION_20261116/pilot_20261116.md:
baseline/observe/segments, partial repetition 1. Sanitized pilot_rows.json (63 rows) IS
in the repository; raw JSONLs remain on Windows/gitignored. Missing answer/reason fields
in that export limit re-grading; the interrupted row is ungraded, not a failure.

## Per-source tables

### docs/results/2026-11-10/probe_20261110_214520.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `dfed5d6bf6a5f215b52ec4a7a712c33cd6642fe9e35882c9ff02aa6a8cf5e51b`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | dev | 8 | 8 | 8 | 8 | 0 | 0 | — | 0 |
| playwright_mcp | dev | 8 | 8 | 8 | 8 | 0 | 0 | — | 0 |
| script_first | dev | 8 | 8 | 8 | 8 | 0 | 0 | — | 0 |
| stagehand | dev | 8 | 8 | 7 | 7 | 0 | 0 | — | 0 |

### docs/results/2026-11-10/probe_20261110_215922.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `4ce3fe4ccdd9fcabd936aa2363d94bebf78d3b760dd0341636a683cdf3d6e9db`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | dev | 3 | 3 | 2 | 2 | 0 | 0 | — | 0 |
| playwright_mcp | dev | 3 | 3 | 2 | 2 | 0 | 0 | — | 0 |
| script_first | dev | 3 | 3 | 3 | 3 | 0 | 0 | — | 0 |
| stagehand | dev | 3 | 3 | 2 | 2 | 0 | 0 | — | 0 |

### docs/results/2026-11-10/probe_20261110_220242.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `6df57914af2c27963fc3be987fb34f1ecaeefc063d1ecd295283d8c2914ac67c`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | dev | 3 | 3 | 2 | 3 | 0 | 1 | — | 0 |
| playwright_mcp | dev | 3 | 3 | 2 | 2 | 0 | 0 | — | 0 |
| script_first | dev | 3 | 3 | 3 | 3 | 0 | 0 | — | 0 |
| stagehand | dev | 3 | 3 | 2 | 2 | 0 | 0 | — | 0 |

### docs/results/form_specialist_20261114/dev3_off.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `59d6223d985c6d43da1b7bb296d25259c4899115ce51ca557fd14968883d99e1`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 6 | 6 | 4 | 3 | 1 | 0 | — | 0 |

### docs/results/form_specialist_20261114/dev3_on.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `9be6c9bc3b91eacb2f0d36e6f03a7e015872c7d1afcfdc7503b2bcec56e4375e`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 6 | 6 | 6 | 5 | 1 | 0 | — | 0 |

### docs/results/form_specialist_20261114/dev4form_off.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `e567872ebefa250aeacdb04ce6675408158ad05ea1dfd6aae43abc2d3d3e79e5`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev4form | 12 | 12 | 2 | 2 | 0 | 0 | — | 0 |

### docs/results/form_specialist_20261114/dev4form_on.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `e89a5916ea7de12f868aa909911ab18f5143a953fc69eb375b4bba9c3ac14ace`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev4form | 12 | 12 | 9 | 8 | 1 | 0 | — | 0 |

### docs/results/form_specialist_20261114/held-out_off.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `edc05fb949cca646e89210170f189436c92bee253e9e0254a54467e912eacc21`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 6 | 6 | 2 | 2 | 0 | 0 | — | 0 |

### docs/results/form_specialist_20261114/held-out_on.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `347abb8e71c85a95ab57bcaee3cd7475e1adf6d6509b611aa4c4074d1e9d5acd`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 6 | 6 | 3 | 3 | 0 | 0 | — | 0 |

### docs/results/form_specialist_20261114/heldout2_off.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `f1302995c49b8de14a79429e73449eda94e019ddaae9b65cc7b0131fa1c105fe`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 2 | 2 | 1 | 1 | 0 | 0 | — | 0 |

### docs/results/form_specialist_20261114/heldout2_on.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `6fbcb8cb2324acb83d7ab0485c51fd05e1652146ad918569011fa0f2838a2060`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 2 | 2 | 2 | 2 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_013521.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `9e9cf4cb875d6e0b502ff2ee3d8dc16d13d8fafffb9563860c521d1104a5f7ed`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 20 | 20 | 14 | 14 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_013754.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `8ac638dfd48ef1f24732cc2f732c18e1999bedb3686c78034db88980684700f5`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | heldout2 | 20 | 20 | 20 | 20 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_014409.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `12de3357c40367e83e8b5b0c0787e476d6dd6e21039f91ab5cbdb77a0639992a`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | heldout2 | 20 | 20 | 20 | 20 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_015006.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `8ffa83ddabf38a818a5356ff316367b97f50e6d14671e8ca4e8567276b3d96e6`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 20 | 20 | 16 | 16 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_015231.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `7e64fab1169cc1d7d12230bdd8d85e6fd11fb045e75c2eeab74b268b10ab3aff`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 20 | 20 | 13 | 13 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_015509.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `fa2b511a76d1e26f8680f2eedf2d796910f925bd32d5b2b8dc9d6bb3d8b2e81e`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | heldout2 | 20 | 20 | 20 | 20 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_101338.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `68607373e3a8996f0a7971dae4ba9b48c04eed935a38b4655e74c6eb2214c5cb`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | heldout2 | 20 | 20 | 20 | 20 | 0 | 0 | — | 0 |
| playwright_mcp | heldout2 | 20 | 20 | 10 | 10 | 0 | 0 | — | 0 |

### docs/results/heldout2_tip2_20261113/probe_20261113_105059.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `08226f14d0bd937a72936498b9d9941f376e8797d7acd6025ea9fcc3bab476c4`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| playwright_mcp | heldout2 | 20 | 20 | 20 | 20 | 0 | 0 | — | 0 |

### docs/results/heldout_luna_medium_20261111.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `eafd43bf61152926e949fcb0325ca2a4b93f0cc38365b21448f8cc5babaee4e9`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | held-out | 50 | 49 | 40 | 40 | 0 | 0 | not re-gradable: needs page text (would pass if marker is on the page): 1 | 0 |
| playwright_mcp | held-out | 50 | 50 | 28 | 28 | 0 | 0 | — | 0 |
| script_first | held-out | 50 | 50 | 27 | 27 | 0 | 0 | — | 0 |

### docs/results/heldout_sol_medium_20261111.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `33d3516c7ff6dae6f2515ebd75743be95cf2144b83c49cfe61ecf9b0e8b6d6df`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| browser_use | held-out | 50 | 50 | 41 | 41 | 0 | 0 | — | 0 |
| playwright_mcp | held-out | 50 | 50 | 38 | 38 | 0 | 0 | — | 0 |
| script_first | held-out | 50 | 50 | 37 | 37 | 0 | 0 | — | 0 |

### docs/results/nav_reader_20261114_post.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `dd585d91c947d5b502ff7a46bab84f766008e5fae9a2f981a53b4ce534bb79cf`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 42 | 42 | 33 | 32 | 1 | 0 | — | 0 |
| script_first | dev4nav | 12 | 12 | 9 | 9 | 0 | 0 | — | 0 |

### docs/results/nav_reader_20261114_pre.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `bf2c1cb5c6a69886a655328b899e134af7175e59cc6fbadc18bfbf641061ce4a`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 144 | 144 | 113 | 103 | 10 | 0 | — | 0 |
| script_first | dev4nav | 36 | 36 | 25 | 23 | 2 | 0 | — | 0 |
| script_first | held-out | 32 | 32 | 20 | 20 | 0 | 0 | — | 0 |
| script_first | heldout2 | 16 | 16 | 12 | 12 | 0 | 0 | — | 0 |

### docs/results/strategy_spa_20261114/dev3_off_first.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `a1ca0a9daa07237d9ddec7c13bbacc4c8849203c67b2b8c09b8e78ef01c2872d`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 4 | 4 | 3 | 3 | 0 | 0 | — | 0 |

### docs/results/strategy_spa_20261114/dev3_on_first.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `6853590797a831ba4debf9b576a8eb5ca4927689e970d565bf0546d12edc78bc`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 4 | 4 | 3 | 3 | 0 | 0 | — | 0 |

### docs/results/strategy_spa_20261114/dev4spa_off_final.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `96a916ba90431629022a1a637bdd0450049fe9551be34e4b7bbf9e60b7c26251`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev4spa | 12 | 12 | 10 | 10 | 0 | 0 | — | 0 |

### docs/results/strategy_spa_20261114/dev4spa_off_first.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `152894ffb3440dacb6a3bd66f6bf81fdd36750a0894a69577ef9fed5ba76b09e`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev4spa | 12 | 12 | 10 | 10 | 0 | 0 | — | 0 |

### docs/results/strategy_spa_20261114/dev4spa_on_final.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `5fcd2160b6c94886916f33e2582872d0e24232701ed1cd74b965b362001b4fb2`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev4spa | 12 | 12 | 11 | 11 | 0 | 0 | — | 0 |

### docs/results/strategy_spa_20261114/dev4spa_on_first.jsonl

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `b90b16a23328689b2f18528ecd1b4246d1f1a86ff9fdbe3357568db39f34af83`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev4spa | 12 | 12 | 10 | 10 | 0 | 0 | — | 0 |

### docs/results/decisions_off_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `4c7aeffbf81aebb60d7ef0ee0a3e156405aeb1992c0e6c2dbe161033b399e2b0`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 30 | 30 | 0 | 0 | — | 0 |

### docs/results/decisions_on_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `74259ad24ae017d13f06ae777231f0db9b45b3273f67dd9ed1d007cfe95d82c4`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 33 | 33 | 0 | 0 | — | 0 |

### docs/results/decisions_shadow_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `6344ebef7dc609e237f7e411a74658b0835fb0a10b89acb89e7b557b1c229b95`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 28 | 28 | 0 | 0 | — | 0 |

### docs/results/robust_executor_20261114/paired_dev3.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `c6686ba8a30cfaa4c6e064dfe4a7ed90361333750d70dabbdc4863e6370a5132`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 80 | 80 | 61 | 56 | 5 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_partial_A2_heldout2_221225.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `46e15cd2c3d13b9ff386ff764f237e7a2bbd91641f8f414a02d945081d41e5c2`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 6 | 6 | 1 | 1 | 0 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_210925.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `0713d4d5a4a185e38ba0910a0467b9ade63271e436198760ad8816f77ebb2d99`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 20 | 20 | 14 | 14 | 0 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_211214.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `d924f6042c24a808762af70390a7ece639473e120accd9879716cebb157b67a2`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 38 | 37 | 1 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_213141.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `d050b7136a88e9c475709f362b6153654c242c834f5bd7fbbc26e8c822528f99`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 20 | 20 | 15 | 15 | 0 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_214621.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `0f5e0556f595a0371a4bae0f6d2cf963d97d80630afb5444148491f1fbe063ed`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 20 | 20 | 17 | 16 | 1 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_214914.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `8c546af4ec1485d4ba8ee48be290ca8e205b264a5545ddcc446ff67fc5fcf7b6`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 37 | 36 | 1 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_215659.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `5052afad46b730cc6dd4269aad3c1c50af7c4ed825394ca4d27dc73cc1cb0316`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | heldout2 | 20 | 20 | 15 | 15 | 0 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_220037.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `41f13af0473713254abe1e64709e77313b3914a4a48732855aded4ac3ea35f29`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 36 | 36 | 0 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_221244.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `b79cbcc0f0c0833e4ca3d6bd033bfaf0493177d8d4583c4316fc3208eae5b9e2`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 38 | 38 | 0 | 0 | — | 0 |

### docs/results/robust_executor_20261114/recovered_probe_20261113_221300.jsonl

Branch: `origin/t3/robust-executor`; commit: `74f434edec976e286f5dd2c7bbcd837a4f19094b`; SHA-256: `8c9e38138021235ada886513592522ee45580a9ca596b1a0305773b5b3d5e224`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 40 | 40 | 26 | 22 | 4 | 0 | — | 0 |

### docs/results/rules_off_run1_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `11e15fc6e4dbb76c0819f65c6c43d8b7a42b646923980153b648e1b7a71fb071`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 31 | 31 | 0 | 0 | — | 0 |

### docs/results/rules_off_run2_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `a1efc016028bed2a4d63122951d6dd761d4e167536d0284f2c6f0f9a648aa54f`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 36 | 34 | 2 | 0 | — | 0 |

### docs/results/rules_off_run3_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `5a0de7f2b3fc411291d0f2d62c7fc194ca1eee0ed71ac482c3e01ce6a555f578`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 31 | 31 | 0 | 0 | — | 0 |

### docs/results/rules_on_run1_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `0356b4f7b094f363b8ae3868f935387a56e7570b6eaddc0a15a234e1c838a7a9`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 29 | 29 | 0 | 0 | — | 0 |

### docs/results/rules_on_run2_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `0785706600ab07a09158416df4c2cd2532c562f22cc12a2e62354f98c8206467`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 35 | 35 | 0 | 0 | — | 0 |

### docs/results/rules_on_run3_luna_medium_20261111.jsonl

Branch: `origin/t3/decisions-second-opinion`; commit: `6b59b525ea279041158b5fc2d320594cdb11261e`; SHA-256: `8f77eac3c106444d2ba33dde0e86db0eb965f5a61c631fbcc86472203b95d0d9`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | held-out | 50 | 50 | 37 | 37 | 0 | 0 | — | 0 |

### docs/PR_INTEGRATION_20261116/pilot/pilot_rows.json

Branch: `devin/1794871306-frozen-grader`; commit: `2e00538af89745b9469b8eb272de308b4ddcf6c9`; SHA-256: `2aa4e7046b1f52447f6bc178b86d6e56a0e53ae403bb29ae819816f5e082ff25`.

| Arm | Split | Rows | Re-gradable | Old pass | New pass | P→F | F→P | Not re-gradable (reason: count) | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| script_first | dev3 | 36 | 27 | 31 | 23 | 0 | 0 | not re-gradable: claimed answer was not saved: 8; not re-gradable: failure reason was not saved: 1 | 0 |
| script_first | dev4form | 15 | 5 | 7 | 0 | 0 | 0 | not re-gradable: claimed answer was not saved: 7; not re-gradable: failure reason was not saved: 2; not re-gradable: interrupted/ungraded row: 1 | 0 |
| script_first | dev4spa | 12 | 4 | 8 | 0 | 0 | 0 | not re-gradable: claimed answer was not saved: 8 | 0 |

## Dataset-level summary

Rates are percentages on the matched re-gradable subset, not all recorded rows.

| Dataset | Arm | Rows | R | Old pass (R) | New pass (R) | Old % | New % | Δ pp | Not re-gradable | Potential F→P | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Nov 10 | browser_use | 14 | 14 | 12 | 13 | 85.71 | 92.86 | 7.14 | 0 | 0 | 0 |
| Nov 10 | playwright_mcp | 14 | 14 | 12 | 12 | 85.71 | 85.71 | 0.00 | 0 | 0 | 0 |
| Nov 10 | script_first | 14 | 14 | 14 | 14 | 100.00 | 100.00 | 0.00 | 0 | 0 | 0 |
| Nov 10 | stagehand | 14 | 14 | 11 | 11 | 78.57 | 78.57 | 0.00 | 0 | 0 | 0 |
| dev3 | script_first | 326 | 326 | 249 | 227 | 76.38 | 69.63 | -6.75 | 0 | 0 | 0 |
| dev4form | script_first | 24 | 24 | 11 | 10 | 45.83 | 41.67 | -4.17 | 0 | 0 | 0 |
| dev4nav | script_first | 48 | 48 | 34 | 32 | 70.83 | 66.67 | -4.17 | 0 | 0 | 0 |
| dev4spa | script_first | 48 | 48 | 41 | 41 | 85.42 | 85.42 | 0.00 | 0 | 0 | 0 |
| heldout (Nov 11 Luna/Sol) | browser_use | 100 | 99 | 81 | 81 | 81.82 | 81.82 | 0.00 | 1 | 1 | 0 |
| heldout (Nov 11 Luna/Sol) | playwright_mcp | 100 | 100 | 66 | 66 | 66.00 | 66.00 | 0.00 | 0 | 0 | 0 |
| heldout (Nov 11 Luna/Sol) | script_first | 794 | 794 | 528 | 524 | 66.50 | 65.99 | -0.50 | 0 | 0 | 0 |
| heldout2 | browser_use | 80 | 80 | 80 | 80 | 100.00 | 100.00 | 0.00 | 0 | 0 | 0 |
| heldout2 | playwright_mcp | 40 | 40 | 30 | 30 | 75.00 | 75.00 | 0.00 | 0 | 0 | 0 |
| heldout2 | script_first | 166 | 166 | 120 | 119 | 72.29 | 71.69 | -0.60 | 0 | 0 | 0 |
| heldout3 interim | browser_use | raw absent | 0 | — | — | — | — | — | raw absent | — | — |
| heldout3 interim | script_first | raw absent | 0 | — | — | — | — | — | raw absent | — | — |
| pilot | script_first | 63 | 36 | 23 | 23 | 63.89 | 63.89 | 0.00 | 27 | 0 | 0 |
| val3 | script_first | raw absent | 0 | — | — | — | — | — | raw absent | — | — |

## Flipped rows (excluding heldout3)

| Task | File | Arm | Direction | Old reason | New reason / code | Answer (≤120 chars) |
|---|---|---|---|---|---|---|
| wv_hackernews_top | docs/results/2026-11-10/probe_20261110_220242.jsonl | browser_use | fail->pass | answer is not the marked value | the page evidence matches the markers / the_page_evidence_matches_the_markers | The top Hacker News story is “.name Grandfathered.” |
| dev3_form_guru99_register | docs/results/form_specialist_20261114/dev3_off.jsonl | script_first | pass->fail | URL contains '/test/newtours/register' | answer too long / answer_too_long | Thank you for registering. You may now sign-in using the user name and password you've just entered. |
| dev3_form_guru99_register | docs/results/form_specialist_20261114/dev3_on.jsonl | script_first | pass->fail | URL contains '/test/newtours/register' | answer too long / answer_too_long | Thank you for registering. You may now sign-in using the user name and password you've just entered. |
| dev4_form_giga_percent | docs/results/form_specialist_20261114/dev4form_on.jsonl | script_first | pass->fail | URL contains 'percentage-calculator.php' | answer too long / answer_too_long | Result 17.50% of 368 is 64.40 |
| dev3_value_khronos_gl46 | docs/results/nav_reader_20261114_post.jsonl | script_first | pass->fail | URL contains '/opengl/' | answer too long / answer_too_long | OpenGL 4.6 at a Glance  The OpenGL 4.6 and OpenGL Shading Language 4.60 Specifications were released on July 31, 2017 |
| dev3_value_commonmark_028 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains 'spec.commonmark.org' | answer too long / answer_too_long | 0.30 (2021-06-19) (view changes \| test cases) 0.29 (2019-04-06) (view changes \| test cases) 0.28 (2017-08-01) (view chan |
| dev3_value_khronos_gl46 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains '/opengl/' | answer too long / answer_too_long | OpenGL 4.6 and OpenGL Shading Language 4.60 Specifications were released on July 31, 2017. |
| dev3_value_mslearn_decimal | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains '/builtin-types/floating-point-numeric-types' | answer too long / answer_too_long | decimal	±1.0 x 10-28 to ±7.9228 x 1028	28-29 digits	16 bytes	System.Decimal |
| dev3_value_commonmark_028 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains 'spec.commonmark.org' | answer too long / answer_too_long | 0.28 (2017-08-01) (view changes \| test cases) |
| dev3_value_commonmark_028 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains 'spec.commonmark.org' | answer too long / answer_too_long | 0.28 (2017-08-01) (view changes \| test cases) |
| dev3_value_exif_gpsaltref | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains '/TagNames/GPS.html' | answer too long / answer_too_long | Tag ID	Tag Name	Writable	Values / Notes 0x0000	GPSVersionID	int8u[4]:	  0x0001	GPSLatitudeRef	string[2]	(tags 0x0001-0x0 |
| dev3_value_mslearn_decimal | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains '/builtin-types/floating-point-numeric-types' | answer too long / answer_too_long | decimal	±1.0 x 10-28 to ±7.9228 x 1028	28-29 digits	16 bytes	System.Decimal |
| dev3_value_commonmark_028 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains 'spec.commonmark.org' | answer too long / answer_too_long | 0.28 (2017-08-01) (view changes \| test cases) |
| dev3_value_commonmark_028 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains 'spec.commonmark.org' | answer too long / answer_too_long | (2017-08-01) (view changes \| test cases) |
| dev3_value_mysql_mediumint | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains '/doc/refman/8.4/en/storage-requirements.html' | answer too long / answer_too_long | MEDIUMINT	3 bytes |
| dev4nav_value_gradle_java21 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains '/userguide/compatibility.html' | answer too long / answer_too_long | 8.5 and after |
| dev4nav_value_gradle_java21 | docs/results/nav_reader_20261114_pre.jsonl | script_first | pass->fail | URL contains '/userguide/compatibility.html' | answer too long / answer_too_long | 8.5 and after |
| dev3_value_mysql_mediumint | docs/results/robust_executor_20261114/paired_dev3.jsonl | script_first | pass->fail | URL contains '/doc/refman/8.4/en/storage-requirements.html' | answer too long / answer_too_long | MEDIUMINT	3 bytes |
| dev3_value_fileformat_snowman | docs/results/robust_executor_20261114/paired_dev3.jsonl | script_first | pass->fail | URL contains '/info/unicode/char/2603/' | answer too long / answer_too_long | UTF-8 (hex)	0xE2 0x98 0x83 (e29883) UTF-8 (binary)	11100010:10011000:10000011 |
| dev3_value_khronos_gl46 | docs/results/robust_executor_20261114/paired_dev3.jsonl | script_first | pass->fail | URL contains '/opengl/' | answer too long / answer_too_long | . OpenGL exposes all the features of the latest graphics hardware.  LATEST FEATURES AND EXTENSIONS  OpenGL 4.6 at a Glan |
| dev3_form_formy_complete | docs/results/robust_executor_20261114/paired_dev3.jsonl | script_first | pass->fail | URL contains '/thanks' | answer too long / answer_too_long | FORMY Form Components  Thanks for submitting your form The form was successfully submitted! |
| dev3_spa_demoqa_origin | docs/results/robust_executor_20261114/paired_dev3.jsonl | script_first | pass->fail | URL contains '/tabs' | answer too long / answer_too_long | Latin professor at Hampden-Sydney College in Virginia, looked up one of the more obscure Latin words, consectetur, from  |
| ho_httpbin_customer_form | docs/results/robust_executor_20261114/recovered_probe_20261113_211214.jsonl | script_first | pass->fail | URL contains 'httpbin.org/post' | answer too long / answer_too_long | custname": "Taylor Example", |
| ho2_value_color_rebecca | docs/results/robust_executor_20261114/recovered_probe_20261113_214621.jsonl | script_first | pass->fail | URL contains '/colors/colors_names.asp' | answer too long / answer_too_long | RebeccaPurple  #663399 Red  #FF0000 RosyBrown  #BC8F8F RoyalBlue  #4169E1 SaddleBrown  #8B4513 Salmon  #FA8072 Sa |
| ho_table_iana_https | docs/results/robust_executor_20261114/recovered_probe_20261113_214914.jsonl | script_first | pass->fail | URL contains 'service-names-port-numbers' | answer too long / answer_too_long | https	443	tcp	http protocol over TLS/SSL	IESG	IETF Chair		2021-10-01	RFC 9110 |
| dev3_value_fileformat_snowman | docs/results/robust_executor_20261114/recovered_probe_20261113_221300.jsonl | script_first | pass->fail | URL contains '/info/unicode/char/2603/' | answer too long / answer_too_long | UTF-8 (hex)	0xE2 0x98 0x83 (e29883) |
| dev3_value_khronos_gl46 | docs/results/robust_executor_20261114/recovered_probe_20261113_221300.jsonl | script_first | pass->fail | URL contains '/opengl/' | answer too long / answer_too_long | OpenGL 4.6 at a Glance  The OpenGL 4.6 and OpenGL Shading Language 4.60 Specifications were released on July 31, 2017.   |
| dev3_value_mslearn_decimal | docs/results/robust_executor_20261114/recovered_probe_20261113_221300.jsonl | script_first | pass->fail | URL contains '/builtin-types/floating-point-numeric-types' | answer too long / answer_too_long | decimal	±1.0 x 10-28 to ±7.9228 x 1028	28-29 digits	16 bytes	System.Decimal |
| dev3_form_guru99_register | docs/results/robust_executor_20261114/recovered_probe_20261113_221300.jsonl | script_first | pass->fail | URL contains '/test/newtours/register' | answer too long / answer_too_long | Thank you for registering. You may now sign-in using the user name and password you've just entered. |
| ho_form_httpbin_phone | docs/results/rules_off_run2_luna_medium_20261111.jsonl | script_first | pass->fail | URL contains '://httpbin.org/post' | answer too long / answer_too_long | {   "args": {},   "headers": {     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/jxl,image/avif |
| ho_find_wiki_gold | docs/results/rules_off_run2_luna_medium_20261111.jsonl | script_first | pass->fail | URL contains '/wiki/Gold' | answer too long / answer_too_long | Atomic number (Z)	79 |

### Heldout3 flip aggregates only

| Direction | Reason code | Count |
|---|---|---:|
| — | no re-gradable flips | 0 |

## Wall time (as recorded; milliseconds)

Legacy browser_use included browser launch, grade read AND grading; script_first excluded
launch/read but overlapped launch with model writing; MCP/proxy/Stagehand excluded launch/read
AND the initial task peek. None is comparable to version 2 without the missing components.
Only rows with saved components are corrected: browser_use subtracts launch/read (an estimate
with unknown grading overhead), MCP adds saved peek_ms; version-2 rows are already normalized.
Script-first overlap cannot be reconstructed. No fields means no correction, not zero overhead.

| Arm | Split | Rows with wall | Recorded median | Recorded mean | Derived rows | Derived median | Derived mean | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| browser_use | dev | 14 | 11660.10 | 14323.54 | 0 | — | — | {"not re-derivable from saved fields": 14} |
| browser_use | held-out | 100 | 16952.19 | 18846.24 | 0 | — | — | {"not re-derivable from saved fields": 100} |
| browser_use | heldout2 | 80 | 17694.24 | 18074.37 | 0 | — | — | {"not re-derivable from saved fields": 80} |
| playwright_mcp | dev | 14 | 10807.29 | 10915.53 | 0 | — | — | {"not re-derivable from saved fields": 14} |
| playwright_mcp | held-out | 100 | 13606.99 | 15425.54 | 0 | — | — | {"not re-derivable from saved fields": 100} |
| playwright_mcp | heldout2 | 40 | 14996.84 | 16465.72 | 0 | — | — | {"not re-derivable from saved fields": 40} |
| script_first | dev | 14 | 3714.86 | 3999.74 | 0 | — | — | {"not re-derivable from saved fields": 14} |
| script_first | dev3 | 362 | 6826.65 | 9260.18 | 0 | — | — | {"not re-derivable from saved fields": 362} |
| script_first | dev4form | 38 | 15814.69 | 18112.58 | 0 | — | — | {"not re-derivable from saved fields": 38, "wall not saved": 1} |
| script_first | dev4nav | 48 | 9101.33 | 9469.35 | 0 | — | — | {"not re-derivable from saved fields": 48} |
| script_first | dev4spa | 60 | 7345.08 | 10096.94 | 0 | — | — | {"not re-derivable from saved fields": 60} |
| script_first | held-out | 794 | 4956.64 | 6782.59 | 0 | — | — | {"not re-derivable from saved fields": 794} |
| script_first | heldout2 | 166 | 5189.55 | 7092.20 | 0 | — | — | {"not re-derivable from saved fields": 166} |
| stagehand | dev | 14 | 44469.90 | 47551.40 | 0 | — | — | {"not re-derivable from saved fields": 14} |

## Not re-gradable files

- `docs/results/heldout3_20261113/interim_luna_sf2_bu1.json`: not re-gradable: raw rows not in repo.
  - `bench/runs/probe_20261113_110106.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_112234.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_122151.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_130842.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_133452.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_210518.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_220832.jsonl` — SHA-256: `not recorded`.
- `docs/results/heldout3_20261113/interim_sol_sf1.json`: not re-gradable: raw rows not in repo.
  - `bench/runs/probe_20261113_110106.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_112234.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_122151.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_130842.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_133452.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_210518.jsonl` — SHA-256: `not recorded`.
  - `bench/runs/probe_20261113_220832.jsonl` — SHA-256: `not recorded`.
- `docs/results/val3_gates_20261114/repair.json`: not re-gradable: raw rows not in repo.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_024016.jsonl` — SHA-256: `50a7801f3fab2b8d20414c88a31647f765460a4b6c2471ee92009e95a0619b88`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_025419.jsonl` — SHA-256: `8ced50233ece56d8fadc7b4a583818c2b7fbcabc52a852e117acc76f8fbe4361`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_030745.jsonl` — SHA-256: `2207591c9f0a918db7b5ba8c48b1c88bcca8f921d06e72d45e4baad3d2885b12`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_023318.jsonl` — SHA-256: `562f1aaa8397ee6ec254d671e9d0c4b9ac5c05ad1943a37542bae0c61b749787`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_024643.jsonl` — SHA-256: `4c86649893a55a6ed31862a85a0c11dbb5f83eaff62d32b508dbc0de59a4436c`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_025956.jsonl` — SHA-256: `20e1f9f26d5e653c75960d6bd472934e8587f87a621f622ae138776d1ddfce48`.
- `docs/results/val3_gates_20261114/verifier.json`: not re-gradable: raw rows not in repo.
  - `C:\Users\epicd\Projects\cuo-before\bench\runs\probe_20261114_144613.jsonl` — SHA-256: `bde8422c481881d70b900317125d5bea7615c3022c5498faa5ce2a8fd4a2330a`.
  - `C:\Users\epicd\Projects\cuo-before\bench\runs\probe_20261114_150051.jsonl` — SHA-256: `2c624f5ba7d19a75e254200398ed68253e7e24f7615d4d5706b9ea5f2ce02a2b`.
  - `C:\Users\epicd\Projects\cuo-before\bench\runs\probe_20261114_151552.jsonl` — SHA-256: `a0b07adf220d90e53cb2a9bda54a7f3c2d4e5e2cf5b761540bda68510ca87b8a`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_143819.jsonl` — SHA-256: `90808f34c91aca10d4af16de346ec13a304426c1c8bd7be6d4e985171433ea78`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_145344.jsonl` — SHA-256: `d292a0bc83b3eefd5eb4a5da3fd7fa84d9e323ed09ebe4314d9f08aff5d36b74`.
  - `C:\Users\epicd\Projects\cuo-tip3\bench\runs\probe_20261114_150725.jsonl` — SHA-256: `ebd6d85974fa49ad8dfb899a952de422fad71408acdc902d4ca00a3f27dfb4d4`.
- `docs/results/tip4_gate_20261114/aggregate.json`: not re-gradable: raw rows not in repo.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_163936.jsonl` — SHA-256: `85d7e943896644e06c778cd12e03972c9ead3eea2a2b17ae7c0321bc6c7a0b12`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_165726.jsonl` — SHA-256: `3600f610bbab752cb41b684749ad6af4b352389733ae3c4c721991c5613fea23`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_171632.jsonl` — SHA-256: `75f0dbd75399d39bbac32aa8c42b131bd2a6c488ae56e26ada7a2b88363380fb`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_164715.jsonl` — SHA-256: `f563b7daf1c897ff0ecc3422d7da74259cabf4b7b1b8dd556536cc38173d5ca5`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_170535.jsonl` — SHA-256: `6bb687964cce5d39b81d6a20907a48ad222286f355885120f0f5151ae2fb3f69`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_172459.jsonl` — SHA-256: `5f294c5a544ece7dcb83e00611c0bd553de1a7cf63815f5c6f5e7e31db6ee018`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_173452.jsonl` — SHA-256: `57ed5401ee55a65be9b00c56486df4df2a72048022f50b58c8ced47091fb770b`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_174405.jsonl` — SHA-256: `315b7cbb3b7c464fd2040388a5be0351c11afa268bb0e920ff5d001d0a330860`.
  - `C:\Users\epicd\.t3\worktrees\computeruseoptimisation\t3-3a87c58e-4cfc2720f96b0431\bench\runs\probe_20261114_175309.jsonl` — SHA-256: `8dad144fb0bb6a3acb7f5b7903127502414d74f464bcdb9ec1fd810fa736421b`.
- `docs/results/tip4_gate_20261114/spend.json`: no gradable rows (metadata only).
- `docs/results/search_20261114/author_attempt1.jsonl`: no gradable rows (branch `origin/t3/strategy-search`, commit `9c6f391b647f9536756e9846739a4a93b8e0617c`).
- `docs/results/search_20261114/author_attempt2.jsonl`: no gradable rows (branch `origin/t3/strategy-search`, commit `9c6f391b647f9536756e9846739a4a93b8e0617c`).
