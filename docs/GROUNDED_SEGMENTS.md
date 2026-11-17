# Grounded script segments

Experimental branch: `t3/grounded-segments-astra-opus`, based on `t3/tip4`
at `b5b74b3`. Enable with `CU_SF_SEGMENTS=1`; the default remains the existing
script-first controller.

## What it does

Keep a known path in one script. When the next action needs information from the
page, execute a non-final segment, inspect its result, and continue in the same
browser session. Each response executes at most one admitted browser tool;
additional queued calls receive `Not run` results so they can be reconsidered
after the fresh observation.

- `look({})` reads the current page. `look({url: "https://example.test/"})`
  navigates before reading.
- `run_script({code: "...", final: false})` executes an intermediate segment.
- `run_script({code: "...", final: true, expect: [...]})` attempts completion.
  Omitting `final` means true.
- `task_failed({reason: "..."})` explicitly ends an unsuccessful task.

Example tool arguments after the relevant controls have been observed:

```json
{
  "code": "page.getByLabel('Name').fill('Pat'); page.getByRole('button', {name:'Next'}).click();",
  "final": false,
  "expect": [{"control": {"role": "button", "name": "Confirm"}}]
}
```

The next model turn sees a compact page snapshot, an execution receipt and a
bounded representation of any script output. It can then issue the next segment
using the controls actually present. A final script returns the usual live-page
evidence object through `page.evaluate`.

## Checks and execution receipts

`expect` accepts up to four single-key objects:

- `{"url_contains": "/receipt"}` — literal substring of the live URL.
- `{"text": "Saved"}` — literal substring of the current document's body text.
- `{"gone_text": "Loading"}` — absence from a successful body-text read.
- `{"control": {"name": "Confirm", "role": "button"}}` — exactly one visible,
  exact-name match; the role is optional.

Strings must be nonblank and at most 200 characters. Invalid inputs fail before
any browser action. All checks share a polling budget; they run before the
contiguous trailing `page.evaluate` statements and are read again afterward.
A late success never erases a failed readiness check. Checks on an evaluate-only
script therefore happen before that evaluate; put mutations in a preceding
segment when their results must appear before extraction.

Every script has a receipt recording completed/attempted steps, possible
mutations, failed step, live URLs, check outcomes and remaining budgets.
`effects_uncertain` means a failed input or evaluate may have changed state;
issued input is not proof of persistence. Recovery inspects the current page
and writes a continuation. The controller does not automatically replay scripts;
identical failed requests are refused. Revised model-written scripts can still
repeat effects, so the receipt is a recovery aid, not an idempotency guarantee.

Successful same-URL interactions and changed observed page content allow
continuation. A final runtime PASS is never overridden by the stall heuristic.
Literal string whitespace, finality and expectations are part of repeat
detection, so adding a readiness condition or correcting an input is possible.

## Completion and limits

Only a final script with successful execution, satisfied expectations and the
existing independent-of-answer-key `runtime_verdict` PASS can finish.
Observations, non-final segments and `TASK_COMPLETE` prose cannot complete a task.
Expectations can downgrade a verdict; they cannot promote one to PASS.
The final benchmark grader and task definitions are unchanged.

Limits per task:

| Resource | Limit |
| --- | --- |
| Executed scripts, including repairs | 6 |
| Model calls | 8, or the caller's smaller limit |
| Explicit looks | 2 |
| Repairs | Existing `CU_SF_MAX_REPAIRS`, default 3 |
| Check time | 3 seconds per segment, 10 seconds total |
| Admission/browser-work deadline | 45 seconds |

An already-issued provider call can return after the admission deadline. Its
usage is counted, and no new browser action is admitted after expiry. Browser
execution and snapshots are bounded by the remaining deadline. Two consecutive
scripts without progress stop continuation; the hard budgets also bound
apparently successful repetitive actions.

Active segment mode bypasses caches and specialist strategies: existing cache
entries do not retain these execution/check contracts. No segment or repair is
saved as a whole-task replay. A known cold one-shot still needs just one model
call and no added page snapshot. Claude `--honest`/`--warm-replay` excludes
script-first from the warm pass in this mode. OpenAI continues to reject its
unsupported warm/honest options.

`CU_SF_REPAIR=blind` takes precedence, logging `segment_mode: "off:legacy"`.
Otherwise the segment flag enables `look` regardless of `CU_SF_LOOK`.
Ordinary flag-off prompts, tools, saved rows, caches and specialist routing
retain their existing behavior.

## Trying it locally

Run the no-model, synthetic-page checks:

```powershell
python -m pytest -q tests/test_segments.py tests/test_segments_harness.py tests/test_prompt_audit.py
```

These use fake provider responses and real headless Chrome/Chromium with routed
fixture pages; no public sites or model APIs are called. They cover delayed
content, same-URL wizards, wrong/missing evidence, malformed arguments, stale
checks, partial submissions with exactly one POST, queued-call refusal,
budget exhaustion, answer-key isolation and offline OpenAI transport.

Verification on this branch: `python -m pytest -q bench/test_harness.py tests`
reported **1,102 passed, 1 skipped** (15 Nov 2026). The starting tip4 suite was
992 passed, 1 skipped. The existing skip remains; these counts are regression
coverage, not an estimate of agent task accuracy.

Preview an eventual run's configuration without executing it:

```powershell
$env:CU_SF_SEGMENTS = "1"
python -m bench.probe --provider openai --model gpt-6-luna --effort medium --arms script_first --split dev3
Remove-Item Env:CU_SF_SEGMENTS
```

Live probes still need explicit approval and the existing spend ledgers/caps.
No new live accuracy measurement was made for this prototype.

## Results and next evaluation

Requested experiments log `segment_mode`, `segments`, `segment_cache` and
`segment_specialists`. Each segment records its receipt and any runtime verdict.
`script_steps` sums parsed actions across all segments; `model_calls` and tool
calls are separate. Token usage includes all returned provider responses and
tool time includes checks and snapshots. An issued call that throws may have
unknown token usage, as with the underlying provider adapter; zero reported
tokens is not proof of zero provider spend.

Compare flag-off and flag-on on the same development instances, model/effort
and starting state. First inspect completion failures, false accepts/rejects,
one-shot fraction, model calls and total time/cost per correctly finished task.
For causal attribution, separately evaluate observation, readiness checks and
continuation rather than crediting the whole change to one mechanism.

The model writes the expectations. They do not establish task relevance,
correct record selection or persisted backend state. Text checks are
top-document substring checks, not frame/shadow-aware extraction. This
prototype retains the existing restricted script grammar and runtime verifier;
it does not solve their full accuracy ceiling or add a visual fallback.

Use a fresh blinded test set for any later accuracy claim. Heldout3 task-level
examples were inspected during the preceding research, as already disclosed.
