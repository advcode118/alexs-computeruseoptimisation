# Exploratory: cascades computed from heldout3 run-1 rows

Not pre-registered, not a claim. Totals only; no per-task rows were read. Computed 13 Nov from Luna script_first run 1, Luna browser_use run 1 and Sol script_first run 1 (138 tasks each). A cascade accepts a stage when its own self-check says PASS, and otherwise moves to the next stage; the last stage is taken as it is. Cost and time are summed over the stages used.

| Path | Pass rate | Dollars per task | Median time | Mean time | 90th percentile |
|---|---|---|---|---|---|
| Luna browser_use alone | 96.4% | 0.00130 | 20.2 s | 24.6 s | 47.8 s |
| Luna script_first alone | 54.3% | 0.00054 | 7.3 s | 8.8 s | 16.4 s |
| Sol script_first alone | 88.4% | 0.00626 | 5.9 s | 8.3 s | 14.2 s |
| Luna script_first, then Luna browser_use | 89.1% | 0.00109 | 7.7 s | 19.7 s | 52.6 s |
| Luna script_first, then Sol script_first | 80.4% | 0.00333 | 7.7 s | 13.1 s | 28.8 s |
| Luna sf, then Sol sf, then Luna browser_use | 86.2% | 0.00344 | 7.7 s | 15.1 s | 31.1 s |
| Sol script_first, then Luna browser_use | 95.7% | 0.00638 | 5.9 s | 10.4 s | 15.4 s |

False accepts (self-check PASS, graded fail): Luna 14 of 138, Sol 6 of 138.

What this shows:
- The median hides the cost of falling back. Luna's hybrid has a 7.7 s median but a 19.7 s mean, close to browser_use's 24.6 s.
- Sol script_first with a Luna browser_use fallback matches browser_use on accuracy at under half its mean time, but costs about 5 times Luna browser_use per task.
- On Luna, false accepts alone cap any cascade at about 90%.
