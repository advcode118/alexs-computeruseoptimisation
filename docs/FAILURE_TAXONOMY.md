# Failure taxonomy

This note groups outcomes in one OpenAI sweep log, `probe_20261110_235837.jsonl`. The run's HEAD was `b33989acd2bc53201c98acb6997ba85639e0a7ad`. The log is not in the git tree (`bench/runs/` is ignored). Every count below is from that file. This is one Wikipedia task across two models and four efforts, not the 18-task set. Counts from earlier Claude probes are not used here.

## What the file contains

The file has 33 lines.

32 lines are task rows. Each one is `task_id` `wv_wikipedia_search`, `provider` `openai`, and `pass` `cold`. On all 32, `skipped` is false, `claude` is false, `no_model` is false, `replay_hit` is false, and `model_ignores_tools` is 0.

The models are `gpt-6-luna` (16 rows) and `gpt-6.1-sol` (16 rows). The efforts are `low`, `medium`, `high`, and `xhigh` (8 rows each). The arms are `script_first`, `playwright_mcp`, `stagehand`, and `browser_use` (8 rows each). Each of the eight model/effort cells has one row per arm.

The last line has `kind` `openai_report` and `sweep` true. It is not a task attempt. Its `measured_run_usd` is null. Its `cells` list is those eight model/effort pairs. Its per-arm `success_count` / `attempted` are script_first 8/8, playwright_mcp 8/8, stagehand 7/8, and browser_use 8/8, the same split as the task rows. It also records `per_run_cap_usd` 5.0, `sweep_cap_usd` 15.0, and `project_cap_usd` 20.0.

The 32 task-row `usd` fields sum to 0.157381.

## Groups

### Passed: URL contains Ada_Lovelace

31 rows. `success` is true. `success_reason` is `URL contains 'Ada_Lovelace'`.

| arm | passed / rows |
| --- | --- |
| script_first | 8/8 |
| playwright_mcp | 8/8 |
| stagehand | 7/8 |
| browser_use | 8/8 |

| model | passed / rows |
| --- | --- |
| gpt-6-luna | 15/16 |
| gpt-6.1-sol | 16/16 |

| effort | passed / rows |
| --- | --- |
| low | 7/8 |
| medium | 8/8 |
| high | 8/8 |
| xhigh | 8/8 |

All eight `browser_use` rows set `page_url` to `https://en.wikipedia.org/wiki/Ada_Lovelace`. Those eight rows have no `substring_success` field. The other 23 passing rows set `substring_success` true with the same Ada_Lovelace reason. The missing field is not another failure: `success` is true on all eight.

### Failed: page stayed on the Wikipedia main page

1 row. `success` is false.

- arm: `stagehand`
- model: `gpt-6-luna`
- effort: `low`
- `success_reason`: `URL 'https://en.wikipedia.org/wiki/Main_Page' does not contain 'Ada_Lovelace'`
- `substring_success`: false, with that same reason
- `claimed_answer`: empty
- `end_state`: empty
- steps: 5
- model_calls: 6
- wall_ms: 80959.9222159959
- usd: 0.000513
- no `page_url` field

The other three arms in that cell (`script_first`, `playwright_mcp`, `browser_use`) passed. Every other model/effort cell passed on all four arms.

No other failure reason appears in the file.
