# heldout4 verification — UNSEALED

No paid model calls or benchmark-arm runs were made. Authoring and verification
use plain HTTP and local Playwright. This is not an all-pass seal: the first
full run passes only 101 keys, and the required minimum is 120 surviving tasks.
No final drops or final task-module seal have been declared yet.

## Base and grader

Heldout4 checkpoints were moved off the merged `devin/ext-heldout4` branch onto
`devin/1794909426-heldout4-seal`, initially based on integration commit
`11a8b23`. The grader and its existing pin/contract tests came from that base;
no files were copied from the old PR #88 branch. After the main-merge update,
`origin/main` was fetched at `abdf56b048e93b14e2b7074ba848eefda41fc660`.
Both bases' grader bytes match the required SHA-256:

`7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`

The first run's input `bench/tasks_heldout4.py` SHA-256 is:

`277c47d484c3a179c48c656f15ae1790dfc5e38b9500a19752979cc8b0d3d006`

This is a run-input hash, **not a final seal**. Each run metadata record also
contains hashes of its verifier and append-only authoring ledger.

## Full run 1 — 2026-11-17

Command: `python -m bench.verify_heldout4` using the local screening virtualenv.
It ran all 130 tasks on the integration-based topic branch before the subsequent
instruction to move the topic branch onto main.

```text
Key checks: 101/130 PASS
Reproducers: 14/19 PASS; 111 none; statuses={'PASS': 14, 'FAIL': 2, 'NONE': 111, 'ERROR': 3}
Negatives: 259/259 correctly FAIL; 130/130 tasks covered
Full/partial: 124/6
```

Reproducer pass rate: **73.6842% (14/19)**, including failures/errors in the
denominator; zero were classified blocked by grader. One task's key setup raised
before a wrong-answer control could run; its independent real wrong-host
control still ran. An unread/UNKNOWN observation never counts as a successful
negative. Negative-control results do not rescue a failing positive key.

Evidence (this run only, never merged with another run):

- `results/ext_sample_20261116/verification_heldout4_20261117T100724469791Z.jsonl`
- `results/ext_sample_20261116/verification_heldout4_20261117T100724469791Z.summary.json`
- `results/ext_sample_20261116/verification_heldout4_full_1.log`
- `results/ext_sample_20261116/verification_heldout4_20261117T100724469791Z_artifacts/`

The JSONL contains a run header followed by live observations and outcomes.
Read physical newline-delimited records (iterate the file), not Python's
Unicode `str.splitlines()`: native page text can contain Unicode line separators
inside otherwise valid JSON strings.

## Outstanding key issues

Twenty failures report `answer part is not in the page text`. Eighteen are
factual questions whose authored parts are supported on multiple URLs, while
the verifier reads only the final rendered page and visible child frames.
Examples include the two Fall Guys power-ups, ACL conference/tutorial chairs,
the two POMS award years and the two NIME instrument papers. The fixed grader
still requires **every** answer part on that single observation. We have not
silently pooled other pages into its final-page text or removed requested facts.
Alternative combined-index pages have not been exhaustively investigated.

The other cases include a search marker missing a search-recognizable path,
legacy marker/parts alignment, stateful form readback/setup and downloaded PDF
text. These need key-format or verifier corrections, with an append-only record
for each correction, before the permitted second full run. Straightforward
corrections to those cases alone cannot yield 120 survivors under the currently
authored single-final-page keys.

The five nonpassing reproducers were Resy pizza, Parking.com, SoundCloud Nirvana,
Trainline preferences and JetBlue careers. UI timing, state and selector causes
are not all diagnosed; they are not represented as successes or automatically
labelled flaky sites. The Under Armour direct key and independent reproducer
disagree on the persisted-message selector, also not yet diagnosed.

## Authored inventory before drops

130 tasks; at most three per registrable site (61 sites when counting start and
key hosts). All descriptions retain source wording except recorded edits.
Interactive/filter/form/multi-step/multi-page tasks remain represented.

| Source | Count |
| --- | ---: |
| Mind2Web-Live | 69 |
| WebWalkerQA | 50 |
| WebVoyager | 8 |
| AssistantBench | 3 |
| Mind2Web train | 0 |

The WebVoyager and AssistantBench quota shortfalls were filled in the fixed
source/rank order, with 14 additional Mind2Web-Live tasks. Mind2Web train remains
fill-only and was not needed before the 130-task target.

Kinds: value 69; nav 29; filter 20; search 5; form 4; spa 2; multisite 1.
Full/partial: 124/6. Script/none: 19/111.

| Effective exclusion reason | Count |
| --- | ---: |
| `site_cap` | 325 |
| `site_gone_or_content_gone` | 76 |
| `captcha_or_bot_block` | 29 |
| `volatile_lt_1day` | 26 |
| `login` | 16 |
| `no_checkable_key` | 12 |
| `payment` | 3 |
| `duplicate_task` | 3 |

`no_checkable_key` subreasons: computed **12**; ungradeable end state **0**.
Original ledger lines remain intact, including the committed 120-task prefix.

| Grader flag | Count |
| --- | ---: |
| `compound_answer` | 63 |
| `url_only_answer` | 51 |
| `length_cap` | 37 |
| `nonfinal_or_nontext_evidence` | 30 |
| `non_unique_answer` | 6 |
| `search_results_url` | 4 |
| `form_value_evidence` | 4 |
| `download_end_state` | 2 |
| `artifact_output` | 1 |
| `cart_quantity` | 1 |
| `link_attribute_evidence` | 1 |
| `pdf_evidence` | 1 |

Flags are retained authoring/audit metadata, not automatic failures or passes
under the fixed grader. The verifier reads real rendered bodies/visible frames,
and, for tasks explicitly requiring it, visible link targets and selected-control
values. It does not insert expected answers into observation text. Stateful
keys prepare real anonymous UI sessions; reproducers use separate fresh contexts.

One manual judgement: the Resy/X sharing task was excluded for the authenticated
account required to publish a post. Its anonymous X intent stayed blank even
after a separate readiness trial; that blank-render cause is **unverified**, not
presented as an observed login wall. No account creation or post was submitted.

## Remaining work

Resolve the multi-page/120-survivor conflict without silently weakening keys;
apply and record permitted corrections; perform the remaining full run; declare
and record drops; record the final module SHA; run the full offline suite on the
main-based branch; then commit and push that new branch only.

The full offline suite has not yet been run for this unfinished seal.
`docs/HELDOUT4_PLAN.md` is intentionally left to the lead.
