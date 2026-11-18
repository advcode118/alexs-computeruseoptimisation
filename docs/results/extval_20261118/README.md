# extval: pre-registered 18-task validation set (18 Nov 2026)

Authorised by Alex. Built without any model API call: plain HTTP GETs and a
local headless Playwright browser only. Keys follow docs/GRADER.md, "Scorer v2".

## Selection procedure (committed before any authoring)

**Pool.** `docs/results/ext_sample_20261116/candidates_extdev.jsonl`. It is
exactly the rows of `pool.jsonl` whose site has
`bench.ext_sample.assigned_set(site) == "extdev"`, that passed the 16 Nov
screen (English, start page reachable without captcha or bot block, site not
used by a pre-extdev catalog task). Heldout4-assigned sites are never used.
Each row keeps its existing `rank`: the order of
`digest(f"{SEED}:{source}:{source_id}")` within its source, SEED 20261116.

**Automatic exclusions** (recorded, no judgement):

* `catalog_task`: the row is one of the 40 extdev tasks (same source and
  source_id), or its `bench.ext_sample.task_fingerprint` equals the fingerprint
  of any task in `bench.tasks.get_all_tasks()` or of any row in
  `candidates_heldout4.jsonl` / `candidates_heldout4_step2.jsonl`.
* `duplicate_task`: its fingerprint equals that of an extval task already accepted.
* `site_cap`: its site already holds 2 accepted extval tasks (accepted tasks
  only; extdev tasks do not count toward this cap).

**Walk order.** The extdev procedure, scaled to 18. Quotas are the extdev
quotas (16/16/5/3 of 40) scaled to 18 by largest remainder:
Mind2Web-Live 7, WebWalkerQA 7, WebVoyager 2, AssistantBench 2, Mind2Web 0.

1. Quota pass: for each source in the order Mind2Web-Live, WebWalkerQA,
   WebVoyager, AssistantBench, walk its rows in rank order and decide each one
   until that source has its quota of accepted tasks or runs out of rows.
2. Fill pass: if fewer than 18 are accepted, walk the rows not yet decided in
   the order Mind2Web-Live, WebWalkerQA, WebVoyager, AssistantBench, Mind2Web
   (fill-only, last), each in rank order, until 18 are accepted.
3. Stop at 18 accepted. The set is then frozen: no substitutions.

**Manual decision.** A row is accepted only if all hold:

* Read-only. Rejected as `not_read_only` if the task needs logging in, signing
  up, buying, paying, booking, adding to a cart or basket, sending, posting,
  submitting a form, following, voting or deleting (anything an approval gate
  would stop).
* Its answer or end state can be verified today from public pages and is not
  expected to change before the live run. Rejected as `volatile` (live prices,
  stock, availability, "latest", "today", live scores, rolling calendars),
  `site_gone_or_content_gone`, `captcha_or_bot_block` (re-checked today), or
  `unverifiable` (the answer cannot be confirmed from the site's public pages).
* A v2 key can be written that rests on quoted page facts. Rejected as
  `no_checkable_key` when the answer must be computed across pages or the end
  state leaves no URL or page-text trace.

A description may be edited only to fix staleness (for example a date that no
longer exists); the original text and the reason are recorded in the task's
`text_edits` and in the decision row. Keys never appear in the description.

**Ledger.** Every decision, automatic or manual, is appended to
`authoring_decisions.jsonl` in walk order: source, source_id, site, rank, pass,
disposition (`accepted` / `rejected`), reason, note, and for accepted rows the
task id. Lines are never rewritten.

**Keys.** `bench/tasks_extval.py` holds the tasks and their `key_v2`. Every key
cites the page fact it rests on (URL, fetch date, quoted text) in
[KEYS.md](KEYS.md).
