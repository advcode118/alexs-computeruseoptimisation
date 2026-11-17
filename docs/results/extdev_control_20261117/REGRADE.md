| Arm / sample | Valid n | Passes; rate [site-clustered 95% CI] | Paired delta vs best arm, pp [95% CI] | Median wall_ms | Mean wall_ms | P90 wall_ms | Mean USD | False accepts / claims |
|---|---:|---|---|---:|---:|---:|---:|---|
| browser_use default, paired | 22 | 5/22; 22.73% [0.00, 41.67] | 0.00 [0.00, 0.00] | 26540.26 | 29455.11 | 54878.14 | 0.074627 | 17/22 |
| browser_use ultrafast, paired | 22 | 5/22; 22.73% [0.00, 41.67] | 0.00 [0.00, 0.00] | 27658.92 | 25295.52 | 35355.66 | 0.053288 | 17/22 |
| script_first, paired | 22 | 1/22; 4.55% [0.00, 13.64] | -18.18 [-34.62, 0.00] | 9638.07 | 10267.33 | 15496.32 | 0.009620 | 5/6 |
| cascade, paired | 22 | 4/22; 18.18% [0.00, 34.62] | -4.55 [-13.64, 0.00] | 25022.14 | 25126.49 | 38067.98 | 0.050565 | 5/6 stage-1 PASS; 1/2 accepted by gate |
| playwright_mcp | **0** | **infra failure: Chrome missing, 0 valid rows** | N/A | N/A | N/A | N/A | N/A | N/A |
| browser_use ultrafast, all 40 (supplemental) | 40 | 6/40; 15.00% [2.56, 29.27] | N/A: different sample | 27658.92 | 32220.88 | 59687.70 | 0.077470 | 34/40 |

Best arm: **browser_use ultrafast**; best baseline: **browser_use ultrafast** (highest pass rate, then lower mean wall).
Cascade vs best baseline: **-4.55 pp [-13.64, 0.00]**;
mean wall difference **-169.03 ms [-8417.80, 7499.17]**.
Within 2 pp with lower mean wall: **no at the point estimate**.
This is not an established noninferiority/accuracy result; bootstrap limitations and key coverage caveats remain.

### Cascade stage split and false accepts

| Stage | Rows | Share | New passes |
|---|---:|---:|---:|
| script | 2 | 9.09% | 1 |
| browser_use | 20 | 90.91% | 3 |

Stage-1 false accepts: 5/6 final self-check PASS claims;
precision-gate false accepts: 1/2. Stage-1 replay uses the saved
self-check payload, not the fallback final page. All six payloads retain page text;
four handed-off cases remain snapshot reconstructions, not independent post-script grade reads.

Cascade gains NBA leaders and Nets navigation. It remains one task behind both baselines:
ICSE 2004 now passes for both baselines via separately grounded date/chair parts,
but cascade ended at `http://www.icse-conferences.org/2004/org_ctte.htm`, not the keyed `/history.html`.
Thus the 4.55 pp deficit misses the 2 pp criterion despite a 169 ms lower mean wall time.
The 90.91% fallback rate still limits speed gains. The accepted Nets script is now a pass;
the accepted SpotHero contact result remains a false accept.

### Every extdev flip (old recorded → new frozen grade)

| File | Arm | Task | Flip | Old reason | New reason |
|---|---|---|---|---|---|
| raw/probe_20261117_012232.jsonl | browser_use | extdev_value_nba_2021_leaders | FAIL → PASS | answer too long | URL contains '/nba/stats/_/season/2021/seasontype/2' |
| raw/probe_20261117_012232.jsonl | cascade | extdev_value_nba_2021_leaders | FAIL → PASS | answer too long | URL contains '/nba/stats/_/season/2021/seasontype/2' |
| raw/probe_20261117_012232.jsonl | browser_use | extdev_value_icse_2004_chair | FAIL → PASS | answer is not in the page text | URL contains '/history.html' |
| raw/probe_20261117_012232.jsonl | browser_use | extdev_nav_nets_schedule | FAIL → PASS | answer does not satisfy the marker | URL contains '/nba/team/schedule/_/name/bkn/brooklyn-nets' |
| raw/probe_20261117_012232.jsonl | script_first | extdev_nav_nets_schedule | FAIL → PASS | answer does not satisfy the marker | URL contains '/nba/team/schedule/_/name/bkn/brooklyn-nets' |
| raw/probe_20261117_012232.jsonl | cascade | extdev_nav_nets_schedule | FAIL → PASS | answer does not satisfy the marker | URL contains '/nba/team/schedule/_/name/bkn/brooklyn-nets' |
| raw/probe_20261117_015118.jsonl | browser_use | extdev_value_nba_2021_leaders | FAIL → PASS | answer too long | URL contains '/nba/stats/_/season/2021/seasontype/2' |
| raw/probe_20261117_015118.jsonl | browser_use | extdev_value_icse_2004_chair | FAIL → PASS | answer is not in the page text | URL contains '/history.html' |
| raw/probe_20261117_015118.jsonl | browser_use | extdev_nav_nets_schedule | FAIL → PASS | answer does not satisfy the marker | URL contains '/nba/team/schedule/_/name/bkn/brooklyn-nets' |
| raw/probe_20261117_015118.jsonl | browser_use | extdev_nav_commuter_benefits | FAIL → PASS | answer does not satisfy the marker | URL contains '/solutions/commuter-benefits' |

Flip totals: {"raw/probe_20261117_012232.jsonl / browser_use": 3, "raw/probe_20261117_012232.jsonl / cascade": 2, "raw/probe_20261117_012232.jsonl / script_first": 1, "raw/probe_20261117_015118.jsonl / browser_use": 4}.
All other extdev outcomes are unchanged, including smoke (0/3 passes) and MCP (0 valid rows).
NBA flips use full-reference bounds plus grounded parts; ICSE 2004 flips use separately grounded date/chair parts;
Nets/commuter flips use the explicit URL-answer flag. No outcome flips are due solely to query-subset matching.

### Older saved data

`python tools/regrade.py --out docs/results/regrade_20261117` covered 53 sources with arm rows.
Against regrade_20261116: 50 common source hashes match;
31 pre-existing flips remain unchanged. New older-data flips: 0;
removed older-data flips: 0; hidden-split flip summaries are unchanged.
**No older data is affected.** Every common per-source arm group is identical.
The global report lists 41 raw-recorded→current flips: the previous 31 plus the 10 extdev flips above.
See [global report](../regrade_20261117/report.md) and [machine-readable comparison](../regrade_20261117/diff_vs_20261116.json).
