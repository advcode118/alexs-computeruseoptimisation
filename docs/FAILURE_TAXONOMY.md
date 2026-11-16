# Failure taxonomy

Source: the three OpenAI probe logs on branch `docs/our-approach-wording`, `docs/results/2026-11-10/`. Describe them as F1 = `probe_20261110_214520.jsonl` (32 cells + 1 `openai_report` row), F2 = `probe_20261110_215922.jsonl` (12 cells), F3 = `probe_20261110_220242.jsonl` (12 cells). Row numbers are 1-based lines in the file. Every cell has `pass: "cold"`. No probe was run to write this note.

Of 56 cells, 7 have `success: false`. All 7 are listed below; no other rows failed.

The Claude probe logs behind PR #18, #23 and #27 are not in git (`bench/runs/` is gitignored), so they are not covered here. Their failures are only known from the summary in `docs/TEST_RESULTS.md`.

## Groups

| # | Arm | Task | Model / effort | Recorded reason (`success_reason`) | Count | Source (file, row) |
|---|-----|------|----------------|------------------------------------|-------|--------------------|
| G1 | stagehand | wv_wikipedia_search | gpt-6-luna / low | `URL 'https://en.wikipedia.org/wiki/Main_Page' does not contain 'Ada_Lovelace'` | 1 | F1 r3 |
| G2 | playwright_mcp | wv_hackernews_top | gpt-6.1-sol / medium | `answer is not the marked value` | 1 | F2 r10 |
| G2 | stagehand | wv_hackernews_top | gpt-6.1-sol / medium | `answer is not the marked value` | 1 | F2 r11 |
| G2 | browser_use | wv_hackernews_top | gpt-6.1-sol / medium | `answer is not the marked value` | 1 | F2 r12 |
| G2 | browser_use | wv_hackernews_top | gpt-6-luna / medium | `answer is not the marked value` | 1 | F3 r12 |
| G3 | playwright_mcp | wv_hackernews_top | gpt-6-luna / medium | `empty answer` | 1 | F3 r10 |
| G3 | stagehand | wv_hackernews_top | gpt-6-luna / medium | `empty answer` | 1 | F3 r11 |

Counts: G1 = 1, G2 = 4, G3 = 2. Total 7.

## Real failure or artifact?

### G1: Stagehand ended on the Wikipedia main page. Real agent failure.
F1 r3: `claimed_answer` is `""` and the end URL is `Main_Page`, not an `Ada_Lovelace` page. The agent never reached the article. It used 7 model calls, 6 steps and 137,033 ms, against about 50 s for its other cells. The same arm, task and model passed at medium, high and xhigh (F1 r7, r11, r15), so this is a single low-effort miss.

### G2: right title, wrong format. Grading/format artifact, not a wrong answer.
The expected value is `.name Grandfathered`. The rows' `claimed_answer` values:
- F2 r10 (playwright_mcp) and F2 r11 (stagehand): a sentence, "The top story on Hacker News is “.name Grandfathered”."
- F2 r12 (browser_use): the same sentence in markdown bold plus "Source: https://news.ycombinator.com/".
- F3 r12 (browser_use): "The top Hacker News story is “.name Grandfathered.”"

All four contain the correct title. They fail because the shared grader requires an exact match (`docs/TEST_RESULTS.md` §How grading works; commit `1a4a4fe`). It is a strict-format failure, not a wrong answer. script_first passed the same task on both models (F2 r9, F3 r9) by returning the bare title, so the gap on this task is partly answer format, not retrieval.

### G3: empty answer. Real agent failure.
F3 r10 (playwright_mcp) and F3 r11 (stagehand): `claimed_answer` is `""` and `expected_value` is `.name Grandfathered`. Nothing was returned.
- r11 also shows `model_ignores_tools: 1`, 11 model calls, 10 steps and 43,627 ms, so that run was lost in the tool loop.
- r10 has `model_ignores_tools: 0`, 4 model calls, 3 steps. Its record does not say why the answer was empty, so the cause is not known from the row.

## Not covered
- Claude probe failures (PR #18, #23, #27): logs not in git. Their summary reasons in `docs/TEST_RESULTS.md` are `ho_rfc9110_get_section` "Model ended without completing task", `ho_wiki_eiffel_city` missing text `Paris`, and `wv_hackernews_top` "empty answer" / "answer is not the marked value". They are not counted above.
- No row records script_first failing, so there is no script_first group.
