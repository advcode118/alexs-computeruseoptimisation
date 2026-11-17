# Extdev hand labels vs the frozen grader

Question: on extdev replicate 1, is the low pass rate the agents failing or the grader rejecting right answers?

**Result: mostly the grader and keys.** Of 109 attempted non-MCP rows the frozen grader passes 16; the hand labels call 81 correct. No row the grader passed was labelled wrong.

## What was labelled

All 131 attempted rows from the extdev control (`docs/results/extdev_control_20261117`): 88 default (four arms, 22 tasks), 40 browser_use ultrafast, 3 cascade smoke rows. Model `gpt-6.1-sol`, medium effort, one run. The 72 budget skips are excluded. The 22 Playwright MCP rows are labelled `infra` (Chrome did not launch).

Grader verdicts are the offline re-grade in `regraded_rows.csv` (`bench/grade.py` sha256 `7ff695b5…`). Nothing was re-run; no model or browser call.

## Rubric

Each row was judged from the task description, the saved final URL, the returned answer and the saved page text:

- `correct`: the answer or end state does what the task asks.
- `partial`: part of the task is done, or the saved evidence cannot confirm a required part.
- `wrong`: no answer, wrong answer, or the agent reported failure.
- `infra`: no attempt was possible.

## Agreement

| Sample | n | Grader pass | Hand correct | Hand correct or partial | Grader FAIL but hand correct |
|---|---:|---:|---:|---:|---:|
| All attempts, MCP excluded | 109 | 16 | 81 | 91 | 65 |
| browser_use default, paired 22 | 22 | 5 | 21 | 21 | 16 |
| browser_use ultrafast, paired 22 | 22 | 5 | 21 | 21 | 16 |
| cascade, paired 22 | 22 | 4 | 20 | 22 | 16 |
| script_first, paired 22 | 22 | 1 | 3 | 8 | 2 |
| browser_use ultrafast, all 40 | 40 | 6 | 34 | 37 | 28 |

Grader and strict hand label agree on 44 of 109 rows (40%). Grader pass with hand label not correct: 0.

Why the grader failed the 65 rows labelled correct:

| Grader reason | Rows |
|---|---:|
| Final URL does not contain the keyed URL fragment | 28 |
| Answer does not satisfy the required parts | 17 |
| Answer too long | 15 |
| Answer does not satisfy the marker | 2 |
| Answer part is not in the page text | 2 |
| Final URL is a search page | 1 |

## What this does and does not show

- The extdev pass rates (5/22, 4/22) are not usable as accuracy. On these labels browser_use and the cascade both solve about 20 of 22.
- script_first alone is genuinely weak here: 3 of 22 correct, 14 of 22 wrong. That is not a grading artefact.
- The cascade's two non-correct rows are both `partial`.

## Limits

- One labeller, and it was Devin (an AI agent), not a person. No second labeller, so no inter-rater figure.
- Not blind: the grader verdict and the answer key were visible while labelling.
- Labels rest on saved evidence only. Page text is capped at 8,000 characters; actions (cart, filters) were accepted from the saved page or URL, not re-checked live.
- The rubric is more lenient than the benchmark's source keys in places: an answer reached on a different page than the keyed one counts as correct if the answer itself is right.
- 22 tasks, one run. The counts are too small for a claim.

## Files

- `labels_input.txt`: the labels as written, one line per row (`D` default file, `U` ultrafast file, `S` smoke file, then the line number in `regraded_rows.csv`).
- `hand_labels.csv`: the labels joined to arm, task and grader verdict.
- `agreement.json`: the tables above.
- `build_labels.py`: rebuilds the last two files.

Reproduce from the repository root:

```
python docs/results/extdev_hand_labels_20261117/build_labels.py
```
