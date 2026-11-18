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
`authoring_decisions.jsonl` in walk order: source, source_id, site, rank, phase,
(`quota` / `fill`), disposition (`accepted` / `rejected`), reason, note, and for
accepted rows the task id and final URL. Lines are never rewritten.

**Keys.** `bench/tasks_extval.py` holds the tasks and their `key_v2`. Every key
cites the page fact it rests on (URL, fetch date, quoted text) in
[KEYS.md](KEYS.md).

## Frozen set (18 Nov 2026)

The walk stopped at 18 accepted after 194 decided rows (195 ledger lines: one
appended correction of a wrong note, same decision). No substitutions, no
description edits (`text_edits` is empty for all 18).

| Task | Deliverable | Site | Source |
|---|---|---|---|
| `extval_nav_real_madrid_ucl_schedule` | page | espn.com | Mind2Web-Live |
| `extval_nav_nfl_super_bowl_2015_scoreboard` | page | espn.com | Mind2Web-Live |
| `extval_nav_spothero_love_field` | page | spothero.com | Mind2Web-Live |
| `extval_filter_spothero_wheelchair_times_square` | page | spothero.com | Mind2Web-Live |
| `extval_nav_darienlake_gift_shops` | page | sixflags.com | Mind2Web-Live |
| `extval_value_icse_2002_gil_tutorial` | answer | icse-conferences.org | WebWalkerQA |
| `extval_value_roviocon_theme_series` | answer | rovio.com | WebWalkerQA |
| `extval_value_icse_2002_deadlines` | answer | icse-conferences.org | WebWalkerQA |
| `extval_value_rovio_burger_king_ar_end` | answer | rovio.com | WebWalkerQA |
| `extval_value_junkworld_launch_update` | answer | ironhidegames.com | WebWalkerQA |
| `extval_value_kingdom_rush_prize_comic` | answer | ironhidegames.com | WebWalkerQA |
| `extval_value_apec_photo_2021_country` | answer | apec.org | WebWalkerQA |
| `extval_value_cambridge_present_perfect` | both | cambridge.org | WebVoyager |
| `extval_value_cambridge_feel_giddy_synonyms` | answer | cambridge.org | WebVoyager |
| `extval_value_hf_cc_by_sa_most_liked` | answer | huggingface.co | WebVoyager |
| `extval_filter_amazon_womens_hiking_boots` | page | amazon.com | WebVoyager |
| `extval_value_hf_trainer_parameters` | answer | huggingface.co | WebVoyager |
| `extval_filter_amazon_gaming_desktop` | page | amazon.com | WebVoyager |

Totals: 7 page, 10 answer, 1 both. By pass: Mind2Web-Live 5 (quota 7, its
rows ran out), WebWalkerQA 7, WebVoyager 2 in the quota pass and 4 in the fill
pass, AssistantBench 0 (all 3 rows need arithmetic).

**Rejected: 176.** Automatic: 62 `site_cap`, 38 `catalog_task` (extdev tasks
and fingerprint matches, including heldout4 candidates). Manual: 35 `volatile`
(live prices, availability, rankings, rolling calendars, past 2024 dates), 22
`not_read_only` (cart, booking, buying, following, sign-up, voting), 10
`no_checkable_key` (computed answers; filters that leave no URL trace; dollar
filters that the GB region rewrites), 7 `site_gone_or_content_gone`, 1
`captcha_or_bot_block`, 1 `catalog_task` by hand (WebWalkerQA main:358 asks the
same question with the same answer as `extdev_value_apec_ministers_chair`).

**Canonical hash.** The canonical JSON is the list of the 18 tasks in
`EXTVAL_TASK_IDS` order, each reduced to `id`, `description`, `start_url`,
`key_v2`, serialised with
`json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
and hashed as UTF-8 (`tests/test_extval.py::canonical_sha256`).

Canonical SHA-256: `e17277c858da7f446b321431fd48379b2b8cbd989e396655c58dc12f03ed0a03`

**Notes for the run.**

* All 18 sites are extdev-assigned, so every extval site also hosts extdev
  tasks (this is what the procedure allows; heldout4 sites are untouched).
  Tasks differ from every extdev task; `extval_value_kingdom_rush_prize_comic`
  shares one fact (the GDC prize) with `extdev_value_ironhide_arcade_gdc`.
* Pages were read from a GB-resolved machine: SpotHero shows a "not available
  in country code GB" modal (Continue Anyway), Airbnb redirects to airbnb.co.uk,
  Steam shows VAT prices. Run from the same region or recheck these.
* Amazon facet ids (`rh=p_n_g-...`) and ESPN fixtures can change; recheck the
  two Amazon tasks and `extval_nav_real_madrid_ucl_schedule` on run day.
* `extval_value_hf_cc_by_sa_most_liked` rests on a ranking (748 likes vs 453
  for the second on 18 Nov 2026).
* Excluded from the sampler's site-overlap list and from the extdev
  disjointness test by the `extval_` prefix (`bench/ext_sample.existing_sites`,
  `tests/test_extdev.py`), so neither the extdev pool nor its tests change.
