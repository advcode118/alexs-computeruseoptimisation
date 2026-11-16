# Grounded segments: opt-in prototype plan (CU_SF_SEGMENTS=1)

Base: `t3/grounded-segments-astra-opus` on `t3/tip4` (b5b74b3). Baseline suite: 992 passed, 1 skipped. Design only, nothing run live.

## Goal and scope
One flag, `CU_SF_SEGMENTS=1`, adds five things to the generic script_first loop. All of them reuse `run_script`, `look`, `page_snapshot`, `runtime_verdict`, the grounded repair, and the existing caps.
1. **Compact observation.** The existing `look` tool, with `url` optional (no URL means the current page). At most 2 looks per task.
2. **Bounded segments.** `run_script(final:false)` runs part of the task. The run then continues without a completion gate.
3. **Readiness and postconditions.** Optional `expect` checks that the model writes. The harness polls them on the trusted page before the script's trailing `page.evaluate` steps run.
4. **Receipts and local recovery.** Every script result carries a structured `receipt`. After a failure, recovery inspects the current page before writing a continuation. The controller never automatically replays a segment; revised model-written code may still repeat effects.
5. **Stricter completion gate.** Only a `final` segment can PASS: its `runtime_verdict` must pass and every one of its `expect` checks must hold. Checks can only turn PASS into FAIL. They never turn a FAIL into a PASS.

Out of scope: an unrestricted code runtime, grammar changes, a semantic cache redesign, Stagehand, new specialists, per-site rules, and live probes.

## Flag rules (no conflicting behaviour)
- `segments_enabled()` (in `bench/segments.py`) is `CU_SF_SEGMENTS == "1"` and not `CU_SF_REPAIR=blind`. Legacy mode wins, and the row logs `segment_mode: "off:legacy"`.
- **Flag off.** The default prompt, the tool schemas, the result text, the cache, and the logs are byte-for-byte what tip4 produces. If a model sends `final` or `expect` anyway, the client ignores them.
- **`CU_SF_STRATEGY`.** Active segment mode selects the generic segment controller instead of specialist strategies. This isolates the experiment and makes its model-call budget unambiguous. Legacy mode still wins; when segments are off, specialist precedence is unchanged.
- **`CU_SF_LOOK`.** Without the segments flag, nothing changes. With it, look is on whether or not `CU_SF_LOOK` is set: 2 looks, and the URL is optional.
- **`CU_SF_MAX_REPAIRS`** still caps repairs. Segments never raise that cap.

## API contract (exact fields)
The `run_script` input schema adds these fields, but only when the flag is on:
```
code:   string (required, unchanged)
final:  boolean, default true. false = a segment; more scripts follow.
expect: optional array, at most 4 items. Each item has exactly one key:
        {"url_contains": str} | {"text": str} | {"gone_text": str} | {"control": {"name": str, "role"?: str}}
        strings: 1..200 non-whitespace chars. control = page.get_by_role(role, name=..., exact=True) or get_by_text(name, exact=True), with exactly one visible match.
```
Defaults: a missing `final` means true. A present `final` must be a boolean. Malformed arguments fail before any browser action, returning an unsuccessful receipt with an invalid check. Unsupported/extra check keys, too many checks, empty strings, and ambiguous controls fail closed.

The result is the JSON line from `format_run_result`, plus a new optional `receipt=` parameter, stored under the key `"receipt"`. `model_visible_script_result` shows the receipt to the model. The receipt has no page text, no `selector_text`, and no marker values:
```
receipt = {
  "segment": int (1-based count of run_script calls run), "final": bool,
  "ok": bool, "steps_run": int, "steps_total": int,
  "failed_step": {"index": int (1-based), "source": str<=200, "error": str<=300} | null,
  "mutations_run": [ {"index": int, "op": "click|fill|press|check|uncheck|select|key|back"} ],
  "url_before": str, "url_after": str, "moved": bool,
  "checks": [ {"kind": str, "arg": str, "ok": bool, "waited_ms": int} ],
   "wait_ms_left": int, "segments_left": int, "looks_left": int,
   "effects_uncertain": bool
}
```
Mutation ops come from completed parsed `TaskStep`s: helper `cu.click/fill/press`, locator click, fill, press, check, uncheck, and selectOption, `keyboard.*`, and `goBack`. These are issued operations, not proof of persisted effects. A failed action may already have emitted input; arbitrary evaluate code may mutate state. Set `effects_uncertain` conservatively and tell recovery to inspect the current state before deciding what to retry.

## Execution (Astra A, client side)
- `run_on_page(page, source, *, end_markers=None, before_tail=None)`. When `before_tail` is given, the client splits the steps into a body and a tail, where the tail is the run of trailing `evaluate` steps. It runs the body, awaits `before_tail()` (the `expect` poll), then runs the tail, then calls `_finish_page`. If `before_tail` is None, the old code path runs. Reads, timeouts, and claims are unchanged.
- **Polling.** Every 100 ms, up to `SEG_WAIT_S=3.0` per segment and `SEG_WAIT_TASK_S=10.0` per task, shared by all checks rather than per check. The task budget lives on the client as `segment_wait_left`. Bound individual reads to the remaining deadline. Read errors never satisfy `gone_text`. A check that never holds is recorded false; the tail still runs for evidence. Recheck every expectation once after the tail: a condition satisfied before evaluate may no longer hold afterward. Preserve a readiness failure even if the final check later succeeds.
- **First-script fast path.** A `final` script with no `expect` does no extra reads: `url_before` is `page.url`, which is free. So a known one-shot task costs the same as on tip4.
- `ScriptFirstClient.call_tool` builds the receipt from the step list and run state. Helpers and constants live in `bench/segments.py`: `segments_enabled`, `parse_segment_args(args) -> (final, checks, errors)`, `poll_checks(page, checks, budget_s) -> list`, `build_receipt(...)`, `mutations_run(steps, done)`, `gate_final(verdict, receipt) -> EvidenceVerdict`, `segment_continue_text(receipt, snapshot)`, and `segment_repair_note(receipt)`. `look` accepts `{}` when the flag is on. Add `reset_segments()` to the client, called by the harness at task start; initialize `segment_index=0`, `segment_wait_left=SEG_WAIT_TASK_S`, `segment_looks=0` and the per-task deadline. Construct these defaults at client creation too for direct-tool tests.

## Harness rules (Astra B, `bench/harness.py` only)
Constants live in `bench/segments.py`: `SEG_MAX_SCRIPTS=6` (segments and repairs together), `SEG_MAX_CALLS=8` model calls, `SEG_MAX_LOOKS=2`, `SEG_WALL_S=45.0` from `generic_start`. With the flag on, `turn_limit = min(self.max_steps, SEG_MAX_CALLS)`. The probe must choose the segment call limit instead of the legacy four-call entry budget when enabled. Check deadline before model/tool admission and after model return; do not start actions after expiry. Bound script/browser work to remaining time and preserve an honest timeout receipt. An already-issued provider call can finish beyond the admission deadline; record its usage and document this distinction.
- **Non-final segment, ok, all checks hold.** There is no `runtime_verdict` and no gate, and `last_verdict` and `end_state` are left as they were. The tool result is the receipt plus `segment_continue_text`, which includes `page_snapshot(task)` between the existing `SNAPSHOT_BEGIN` and `SNAPSHOT_END` markers. `drop_old_snapshots` runs. A counter `segments_acked += 1` is incremented. The extra-script refusal becomes `finished_first = script_calls >= 1 and script_calls > repairs_sent + segments_acked`.
- **Non-final segment that fails** (a step threw, or a check is false). This is a local repair against `repairs_sent` and `max_repairs`. Its reason identifies the failed step/check. Prepend `segment_repair_note(receipt)`: completed steps are retained, failed input may have taken effect, inspect the snapshot before retrying. Never automatically replay a script or advise unconditionally restarting a mutation.
- **Final segment.** Run `script_runtime_verdict` and then `gate_final`. PASS stops, FAIL takes the grounded repair path, UNKNOWN stops. Expectations only downgrade; they cannot establish semantic correctness or turn a failed runtime verdict into success.
- **Progress and stall.** Continue on changed trusted page content, successful issued mutations, existing URL/action progress, or a previously failed check now holding. Two no-progress scripts stop continuation, but never replace a gated final PASS. Exact failed requests cannot repeat. Repeat keys preserve literal whitespace, finality and expectations. Successful progressing non-final requests may repeat, bounded by the hard script/call budgets.
- **Decision boundaries.** After every admitted look or non-final/failed script, answer all remaining queued calls with `Not run` and require a fresh model decision from the returned state.
- **Caps.** A script past `SEG_MAX_SCRIPTS`, past the wall budget, or past the repair cap gets the existing refusal text and a stop. A third look is refused, as now. `task_failed` is unchanged.
- **Completion gate.** `success=True` only through a final segment's gated PASS on an http(s) page. Missing/malformed receipts fail closed in active segment mode. `TASK_COMPLETE` prose, a look, or a non-final segment can never set success. Pending failed expectations are not waived by a subsequent bare completion claim.
- **Counting.** Every model call and every look or segment tool call goes through the existing `model_calls`, token, `total_tool_ms`, and `StepMetrics` accounting, with no shortcut. Wait time is part of `tool_ms`.
- **Cache.** Disable cache lookup, replay, patching and saving in active segment mode for this cold-task prototype. Existing entries cannot preserve segment expectations/provenance and could bypass the new checks or replay mutations. The ordinary default cache path is unchanged. One-shot execution still needs one model call and no added page snapshot; state-aware caching is a later experiment.
- **Markers.** `mcp_client.end_markers = {}` stays as it is. Segments read no `tasks.py` fields apart from the description and `start_url`. `tests/test_script_cache.py::test_the_live_run_never_reads_the_answer_key` gains a segment-mode case.

**Logging.** `TaskResult` gains `segment_mode: str` (`"on"`, `"off"`, or `"off:legacy"`) and `segments: list[dict]` (receipts, plus verdict/reason where checked). Serialize the additional fields only when the experiment was requested, so default rows remain unchanged. `script_turns` keeps final scripts and repairs only. Keep parsed script actions, tool calls and model calls distinct, and count every segment's actions rather than only the last one. Probe and saved result metadata report cache/specialist bypass for this experiment.

## Prompt (Astra A, `bench/arms.py`)
With the flag on, `prompt_for` appends `_SEGMENT_LINES` and replaces the first bullet ("The first script must finish the task...") with: "If you know the whole path, send one script that finishes the task (final is true by default). If you do not, send a short final:false segment, read the receipt and page, then continue. Use expect for what must be on the page before the evidence is read." The lines contain no sites, selectors, or answers, and `tests/test_prompt_audit.py` must walk the new prompt, the continue text, and the repair note.

## Ownership
- **Astra A:** the new `bench/segments.py`. In `bench/script_first.py`: `run_on_page` `before_tail`, the `call_tool` receipt, the schema in `tools_for_claude`, `look` without a URL, and the `format_run_result` receipt. The prompt in `bench/arms.py`. Tests in `tests/test_segments.py`, covering the units and the client against real headless Chromium.
- **Astra B:** `bench/harness.py` (the loop, the cache gate, and the TaskResult fields), `bench/probe.py` row fields, and `tests/test_segments_harness.py` (a fake model with a real `ScriptFirstClient` on `page.route` fixtures). B codes against the contract above and stubs `bench/segments.py` until A lands.
- **Parent:** merges A then B, runs the full suite with the flag off (it must stay 992 passed, 1 skipped, plus the new tests), the prompt audit, and the marker test. Updates `NOTES.md`. No live probe without Tom's go.

## Decisive local tests (headless Chromium, `page.route` fixtures, fake model)
1. **Flag off is identical.** `prompt_for`, `tools_for_claude`, and the `run_task` rows match tip4. `final:false` sent anyway still gets the second script refused.
2. **Readiness.** The fixture inserts `Price: 42` after 600 ms. A final script with `expect:[{"text":"Price:"}]` passes. The same script without `expect` fails. `waited_ms` is between 500 and 3000.
3. **Wizard.** Segment 1 is `final:false` (fill, click Next). The receipt lists the mutations and `moved`. Segment 2 is final and passes. `model_calls == 2`; an existing cache is never read or written.
4. **No replay.** Step 3 of 4 throws after a fill and a submit click. A server-side counter shows exactly 1 POST after recovery. The repair text names step 3, and the continuation passes.
5. **Observe or check is not completion.** A non-final segment whose checks all hold, followed by `TASK_COMPLETE`, fails. A look followed by `TASK_COMPLETE` also fails.
6. **The gate only downgrades.** A final script whose runtime verdict is PASS but whose `expect` fails gives FAIL. No case turns a FAIL into a PASS.
7. **Caps.** An endless run of non-final segments stops at 6 scripts or 8 calls. Expectations that never hold total no more than 10 s of waiting. The wall cap is tested with a patched clock.
8. **Accounting.** The summed fake usage equals the result totals, and `model_calls` equals the fake's calls, including looks.
9. **Markers.** With segment mode on, reading the task's markers raises. That covers both the run and repair text.
10. **One-shot.** A first final script that passes gives `model_calls == 1`, and `page_snapshot` is never called.
11. **OpenAI schema.** `openai_client` converts the nested `expect` schema. The test runs offline.
12. **Input/evidence integrity.** Malformed arguments cause zero actions; two same-name visible controls do not satisfy a control check; a failed page read cannot satisfy absence; a tail that removes the required text cannot pass a stale expectation.

## Foreseeable regressions
- The model splits tasks it could have done in one script, which costs more calls and seconds. Measure the one-shot rate and the median wall time against the flag off on dev sets only.
- `expect` written to match the answer (`text` = the guessed value) could hide a wrong page. It cannot cause a pass, though, because the gate only downgrades and `runtime_verdict` still checks the evidence.
- The receipt adds about 150 tokens to every result. It is shown only with the flag on.
- The rule allowing identical non-final segments could loop. The stall and cap rules bound it.
- Consumers of `script_turns` or `steps[-1]` may misread a run that ends on a segment. Keep `steps[-1]` the last run_script, as now.
- **Existing issue, not changed with the flag off:** tip4's default cache saves a passing *repair* script, which continues from the current page, as the whole task. The fingerprint and patch path usually catch it. The parent should decide separately whether to fix it on the default path.
