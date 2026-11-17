# Grounded segments review (CU_SF_SEGMENTS=1)

Reviewer: Opus 5.5 review agent, 15 Nov 2026. This is a static review of the uncommitted tree on `t3/grounded-segments-astra-opus` against b5b74b3. I ran no tests, probes or API calls and read no heldout3/4/val3 per-task data. The scenarios below are reasoned from the code. They have not been executed.

## Parent resolution after the review

The findings below preserve the original static review. The parent subsequently
reproduced B1, B2, M1, M2 and L1 in eight failing synthetic regressions and fixed
them; these fixes were tested locally, not re-reviewed by Opus.

- B1: same-URL interaction/content changes allow continuation; a gated final
  PASS cannot be replaced by the stall heuristic.
- B2: every look/segment is now a decision boundary. Remaining queued calls
  receive `Not run`; successful and failed submission tests count exactly one POST.
- M1/L1: repeat keys preserve literal whitespace, finality and expectations.
  Only successful progressing non-final requests may repeat.
- M2: segment mode excludes script-first from warm scheduling and reports the
  restriction in dry plans; OpenAI dry plans also report the effective mode.
- L2: receipt shape validation is shared; the controller additionally checks
  the requested arguments, execution URL, counts and look budget.
- L4/L5/L6: exhausted wait budget is named in recovery; bounded script output
  is returned for the next decision; the existing `script` alias is supported.
- L3/L7/L8: limitations are documented in `GROUNDED_SEGMENTS.md`. No live API
  schema verification or general accuracy result is claimed.

The first full-suite run also exposed a test-fixture assumption: its 250 ms
actionability cap sometimes timed out Submit before any POST. A focused trace
confirmed this. The test now uses the production timeout and keeps every
original exactly-one-POST/failed-step assertion.

## Verdict
Nothing changes when the flag is off. I found no oracle reads. The cache and specialists are bypassed because of where the dispatch sits (`bench/harness.py:1581`, which comes before the cache at L1642 and the strategies at L1673+). The final gate only ever downgrades a verdict. Invalid arguments run zero actions. Provider tool_result pairing is complete on every path that continues.

Two findings should be fixed before any live run (B1, B2). Two more are worth fixing at the same time (M1, M2). The rest are optional.

## Blockers (fix before a live probe)

### B1. The stall rule overrides a gated final PASS and stops same-URL wizards
`bench/harness.py` `_run_segment_task`: `progress = valid and script_made_progress(previous, payload)`, then `if stalled_scripts >= 2: verdict = EvidenceVerdict(FAIL, "no progress", ...)`. This runs after `gate_final`, so it replaces a PASS. `script_made_progress` (`bench/script_first.py:1930`) counts only two things: a new URL, or more completed steps than the previous script.

Repro (synthetic SPA: one URL, the DOM swaps panels, no pushState):
1. seg1 `final:false`: `getByLabel('Name').fill('A'); getByRole('button',{name:'Next'}).click()`. That is 2 steps with previous=None, so it counts as progress.
2. seg2 `final:false`: `getByLabel('Email').fill('b'); click Next`. 2 steps on the same URL, and 2 is not more than 2, so stalled=1. It is still acked.
3. seg3 `final:true`: `click Confirm; page.evaluate(evidence)`. 2 steps on the same URL, so stalled=2. runtime_verdict and gate_final give PASS, the stall rule replaces it with **FAIL "no progress"**, and the run stops.

The same thing happens to a field-by-field form or a final extraction segment that follows two short same-URL segments. Existing tests use pushState URLs (`tests/test_segments_harness.py:137,318`), so this case is untested.

Minimal repair:
- (a) Apply the stall override only when `verdict is None or verdict.verdict != PASS`. A gated PASS is already stronger evidence than a progress heuristic.
- (b) In segment mode, also count progress when `receipt["ok"]` holds and `receipt["mutations_run"]` is non-empty. A cheaper alternative is to compare the title, h1 and a hash of the page text with the previous segment's. Runaway loops are still bounded by 6 scripts and 8 calls.
- Add a test with a same-URL three-panel wizard.

### B2. Queued tool calls after an acked segment or a look run without grounding (and can replay)
After a non-final ack (`segments_acked += 1`, not stopped, not awaiting_repair), the `for index, call in enumerate(calls)` loop keeps going and runs the next `tool_use` from the same response. The model wrote that call before it saw the receipt or snapshot. `finished_first` lets it through because `scripts == repairs + segments_acked`.

Repro: one response holds `[run_script(final:false, fill + click Submit), run_script(final:false, goto(start) + the same fill + Submit)]`. The first is acked. The second has a different normalized key, so it is not refused, and it runs: **two POSTs**. The no-replay test (`test_partial_submit_failure_recovers_without_replaying_post`) covers only the *failed* first segment, where the queued call correctly gets "Not run". The same gap exists after a `look`, where a queued script runs on a page the model has not seen. It also puts two un-dropped snapshots in one user message, because `drop_old_snapshots(messages)` cannot see the pending `tool_results`.

Minimal repair: in segment mode, after any `run_script` or `look` that does not stop the run, answer the rest of `calls[index+1:]` with the existing "Not run. Inspect the … receipt and current snapshot before continuing." text and break. That matches the failure path and the plan's rule of one observation, then the next segment. Then extend the queued-replay test to the acked case.

## Should fix (same change set)

### M1. The repeat key blocks the main readiness recovery, and the whitespace fold conflates literals
`key = normalized_script(code)` removes all whitespace (`bench/script_first.py:1914`), including inside string literals. It also ignores `final` and `expect`. `repeatable[key] = valid and not final and progress`, so any **final** script leaves its key unrepeatable.

- Repro 1 (the feature's own use case): a final script FAILs because `Price:` has not rendered yet. The model resends the same code with `expect:[{"text":"Price:"}]`. The call is refused ("This exact script already ran without progress") and `stop()` ends the run.
- Repro 2: a final `fill('NewYork')` FAILs, and the repair `fill('New York')` maps to the same key. It is refused and the run stops. This one already exists on the default path, so change it only in segment mode.

Fix: in segment mode, key on `(code.strip(), final, canonical json of parsed checks)`. Better still, fold whitespace only outside quotes.

### M2. `--honest` with segments on runs a second paid cold pass labelled "warm"
`execute_probe` skips building `ScriptCache` in segment mode (`bench/probe.py:1566`), but `honest` forces `warm_replay = True` (`probe.py:407,1535`). The warm loop (`probe.py:1601-1607`) still calls `take(arm, task, "warm", None, 0)` for script_first. That is a full fresh 8-call run per task, and the row says `pass="warm"`. It roughly doubles script_first's Claude spend under the $50 cap, and it makes the warm/cold comparison meaningless.

Fix: when `segment_mode_for(ARM_SCRIPT_FIRST) == "on"`, drop script_first from the warm arms (or refuse warm_replay), and say so in `plan_probe`.

## Optional improvements / low severity

- **L1. A failed segment that moved can be repeated verbatim.** `progress` is true on a URL change even when `ok` is false, so `repeatable[key]` becomes True for a failed `final:false` segment that navigated, such as a click on Submit that went to /confirm before a later step threw. The same code is then accepted as a repair, which replays the completed mutations that the receipt says not to replay. Fix: `repeatable[key] = valid and not final and receipt["ok"] and progress`.
- **L2. The two receipt validators drift.** Harness `_segment_receipt_error` and `segments._valid_receipt` (used by `gate_final`) are mostly consistent: the final bit is compared with the parsed args, checks are matched on kind and arg when ok, `payload.ok is receipt.ok`, `payload.steps == steps_run`, and the segment index equals the harness script count. They differ in four places:
  - The harness accepts the check kind `"invalid"`, but `_valid_receipt` rejects it. A final call with invalid args then FAILs with "missing or malformed segment receipt" rather than the argument error, if runtime_verdict did not FAIL first. It still fails closed; only the reason is misleading.
  - The harness does not enforce `failed_step.index > steps_run` or the 200/300 caps.
  - Neither validator cross-checks `url_after` against the `- Page URL:` line, or `looks_left` against the harness `looks`.
  - Neither can prove that the checks actually ran: the client is trusted.

  Suggest having the harness call `segments._valid_receipt` and keep only the argument-match and payload-match extras, so the next schema change has one place to edit.
- **L3. Expectation limits that should be stated, not judged.**
  - `text`/`gone_text` read `body.innerText`. That skips iframe content, likely skips shadow-DOM content, and matches any substring anywhere on the page: navigation, a search snippet, or a "you searched for X" echo.
  - `url_contains` accepts trivial substrings such as `/`.
  - A `control` check proves that exactly one visible exact match exists, not that it is the right one.
  - Expectations come from the model, so an expectation written to match the guessed answer adds no independent evidence.

  None of these can create a PASS, because the gate only downgrades. A false `gone_text` hold can only *fail to downgrade*, and alternating a check from false to true can reset the stall counter, which the caps still bound. The prompt wording "never proof of semantic correctness" is accurate. Do not describe expectations as verification in any results write-up.
- **L4. The per-task wait budget fails closed silently.** After 10 s of total check time, every later `expect` reads "check budget exhausted" and fails, which spends a repair. `wait_ms_left` is in the receipt, but consider a sentence in the repair note when it is 0.
- **L5. Non-final segments hide their own `page.evaluate` output.** The ack shows only header, receipt and snapshot. That is consistent with "no page text in receipt", but a segment that reads a value in order to choose the next step gets nothing back. This is a design choice, so document it in the prompt.
- **L6. `code` vs `script` alias.** The harness keys on `args.get("code") or args.get("script")`, but `_run_segment` reads only `code`. A `script`-only call fails to parse and still uses up a repair. It is harmless, but it is inconsistent.
- **L7. The OpenAI schema is passed through unchanged.** `responses_tools` sends the nested `items.oneOf` and the `pattern`/`default` keywords unchanged, and the test checks only that pass-through. This is fine for non-strict function tools as far as I know, but it is unverified live. Watch the first OpenAI call for a schema 400 before a full run.
- **L8. Step-level token attribution.** Usage is attached to `calls[0]`'s StepMetrics. If that first call is refused (which stops the run), or the response has no calls, the tokens appear only in the result totals. The totals are correct, but per-step sums can be lower. This is the same as the default path.

## Confirmed OK (checked, no action)
- **Flag off.** Prompt, tools and `format_run_result` are unchanged (the receipt is None). `run_on_page`'s error text is unchanged when `_state` is None. `TaskResult.segment_mode` is not serialized by `save_result`/probe rows when off. `look_enabled()` is unchanged when the flag is unset. `off:legacy` runs the tip4 path.
- **No oracle.** The controller sets `end_markers = {}` and reads only the description and start_url. The post-run `_read_shared_page` is the only grade read.
- **Bounds.** Admission is checked before each model call and tool call and after each model return. The browser wait, the snapshot and `run_on_page` are all bounded by the deadline, and a timeout keeps a partial receipt. Six scripts, eight calls, two looks, and the inherited `max_repairs` are enforced in the harness. The client independently enforces the script limit, the look limit and the deadline.
- **Final precision.** PASS needs `final` + `runtime_verdict` + `gate_final` + an http(s) URL, and each expectation is re-read after the tail. A readiness failure is not erased. Prose, looks and acked segments cannot set success.
- **Invalid arguments.** No browser action runs; the receipt has `steps_run=0`, ok is false, and the call counts against repairs.
- **Partial effects.** `failed_step`, `mutations_run` and `effects_uncertain` are built from issued steps. The harness never auto-replays, and queued calls after a *failed* segment get "Not run".
- **Accounting.** The model call is counted before it is issued, and usage is counted even when an expired call returns. Snapshot ms is added to `tool_ms` and the totals.
