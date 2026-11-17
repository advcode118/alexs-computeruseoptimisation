# Probe measurement, version 2

Rows with `wall_clock_version: 2` use one timer, launch reported separately:
`wall_ms` begins when the browser is ready, before opening the start URL or
doing any task/model work. It stops when the arm's run loop returns, before
the independent grade read and grading. Browser setup is `browser_launch_ms`;
post-run page reads are `grade_read_ms`. Cleanup is outside both intervals.
Failed launches have zero wall time and report the attempted launch duration;
run failures and oversized-snapshot skips report the interval actually run.

Coverage includes every `ARMS` entry (`playwright_mcp`, `diff_fast_act`,
`macro_replay`, `stagehand`) and the selectable `script_first` and `browser_use`.
MCP startup warms a blank tab because starting the server alone does not launch
Chrome. The initial task navigation/peek is timed, not startup. Script-first
waits for launch before its model call, including cached/specialist/segment
controller paths: model writing no longer overlaps browser launch. Browser-use
explicitly starts its browser before constructing/running its agent. Proxy
no-model runs follow the same boundaries.

`endpoint` is browserless: `browser_launch_ms` and `grade_read_ms` are zero.
Its wall interval is the HTTP fetch, ending before grading; `endpoint_fetch_ms`
also records that fetch. A fallback row uses script-first's browser interval
and records the preceding fetch separately, not in browser wall time.

Graded rows persist post-run `grade_url`, `grade_page_text`,
`grade_page_text_truncated`, `grade_selector_text`, and `claimed_answer`.
The text is the actual grade input (including the existing shared reader's
headings/body assembly and 8,000-character bound), capped on storage at 50,000
characters; the truncation flag describes storage truncation, not DOM length.
These are never model/controller inputs. Script/controller rows also persist
`grade_claim`, completion state/reason, and `end_state` for replaying the
claimed-evidence and own-verdict gates. Ungraded skip/error rows use empty
evidence fields. Older rows without version 2 are not timing-comparable.
