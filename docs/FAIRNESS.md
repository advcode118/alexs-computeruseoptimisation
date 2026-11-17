# Fairness of the four arms

`playwright_mcp`, `script_first`, `stagehand`, and `browser_use` share one set of timeouts, one browser, the model string the probe was given, and one page-text read. This is the choice where those arms used to differ. Grading is unchanged: `grade_observation`, the Hacker News exact title match, `script_first`'s own `PASS`, and the shared page check are the same checks as `b33989acd2bc53201c98acb6997ba85639e0a7ad`.

## Timeouts

The shared wait is the longer one.

| Wait | Shared value | Why this one |
| --- | --- | --- |
| Model HTTP | 120s | `AnthropicClient` and the OpenAI client already waited 120s. browser-use's cell timeout is 120s. Its Chat classes reject a timeout argument, so Claude stays `ChatAnthropic(model, api_key=...)` and OpenAI stays `ChatOpenAI` with `reasoning_effort`. |
| Navigation | 60000ms | Playwright MCP's navigation default. `script_first` waited 10s. `stagehand` used Playwright's 30s default. |
| Action | 30000ms | Playwright's default, which `stagehand` already used. `script_first` and Playwright MCP waited 5s. |
| Evaluate and page read | 30s | Playwright's default. `script_first` stopped an evaluate at 5s. The browser-use tab read stopped at 5s. |
| Landing and settle | 3000ms | `stagehand`'s settle cap. `script_first` stopped the landing read at 0.8s and still does not run the per-click settle loop. Playwright MCP's settle default was 0.5s. |
| browser-use run | 3600s | `Agent.run` defaults to 1700s. `playwright_mcp` and `stagehand` have no run cap and allow 30 steps. Thirty steps at the 120s model wait is the longer budget. `script_first` keeps its own call cap. That cap is not a timeout. |

The constants live in `bench/fairness.py`. Process shutdown still waits 5s. That is not a task timeout.

## Browser

The shared browser is Google Chrome.

`script_first` and `stagehand` both call `chrome_launch_attempts`: channel `chrome`, then bundled Chromium if Chrome will not launch. Each arm still gets its own profile directory. `playwright_mcp` passes `--browser chrome` and does not pass `--user-data-dir` (`@playwright/mcp@0.0.84` rejects that together with `--isolated`).

browser-use's fresh-profile launcher is `Browser('chromium')`. `Browser('chrome')` attaches to the already-open Chrome and refuses `headless`, so it is not used. When Google Chrome is installed, `executable_path` is that binary, the same Chrome Playwright's chrome channel launches. When it is not installed, browser-use keeps its own fallback and the row records `chromium`.

## Model string

The probe passes one model string into every arm.

On the Claude path that string is `claude-sonnet-5-5`. Nothing else is accepted, and the Claude request is unchanged. On the OpenAI path the string is the model the probe was given, `gpt-6.1-sol` or `gpt-6-luna`. No other OpenAI model is accepted, and none is filled in when the probe did not name one.

## Page text

The function is `_PAGE_EVIDENCE_JS`. The call is `evaluate` of that function, then `evaluate` of `marked_selector_source` for the marked element. `read_shared_evidence` is that call. A Playwright page and Playwright MCP both go through `read_marked_page`, which uses it. browser-use uses it too. CDP `Runtime.evaluate` needs an expression, so the same function is sent as `({function})()`. A dict is the evidence object. A string is body text. `text_from_page_read` assembles both.

`script_first` still reads the page at the end of its own script for its `PASS`. The harness does not replace that text when it is already present. The shared check still requires that `PASS` and the shared page check.
