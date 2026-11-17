# External benchmark source snapshots

**WebWalkerQA provenance caveat:** [the paper, §3.1](https://arxiv.org/html/2501.07572v1#S3.SS1) says GPT-4o made the initial synthetic annotations, followed by crowd-sourced human quality control/filtering and possible rewriting/calibration; it is not exclusively human-written. No model calls were made by this project.

## STEP 3 procedure revision (before any heldout4 authoring)

The three-per-site cap now applies only to **accepted tasks**, across sources.
Every non-overlapping English reachable row remains in the ranked reserve: no
candidate site cap, quota truncation, or 2x margin truncation. Authoring walks
each stratum in rank order; only a site already holding three accepted tasks is
skipped as `site_cap`. Existing extdev decisions are frozen and seed accepted
site counts; new authoring walks the previously unreviewed ranks, not just ranks
after the last old decision. STEP 2 artifacts have `_step2` snapshots.
Seed 20261116, SHA-256 row ordering, site-to-set assignment and original quotas
are unchanged. Fill order is Mind2Web-Live, WebWalkerQA, WebVoyager,
AssistantBench, then Mind2Web; the latter has quota zero in both sets and is
fill-only. `bench.ext_sample.authoring_reserve` implements the accepted-only
walk with an append-only decision list. No heldout4 authoring has begun.

### Mind2Web train-only slim derivative

Source: https://huggingface.co/datasets/osunlp/Mind2Web (CC-BY-4.0), crowd-worker
task descriptions. Retrieved 2026-11-17 using `python -m bench.ext_fetch_mind2web`.
`mind2web_train_slim.jsonl` contains 1009 train rows and ONLY annotation_id,
confirmed_task, website, domain and subdomain. SHA-256:
`5ea636be202fa7eccf8f11b2ca9cf12eef55c590b3662122be37bd10be85aef9`.
The rows API was tried with one train row; its documented API has no column
projection and returned action/HTML cells, which were discarded, not saved.
Projected HTTP-range Parquet reads then fetched the five columns (plus required
Parquet footers), not the full 854MB HTML-bearing shards. The server's converted
train view reports `partial=true`; this derivative is explicitly that exposed
1009-row view, not a claim of additional unexposed data. Per-shard URLs, byte
counts, row counts and retrieval time are in `mind2web_train_provenance.json`.
No test split, contamination-protected ZIP, or full HTML-bearing JSON was fetched.
`mind2web_homepages.json` records the explicit website-name→homepage mapping;
each normalized task records this start_url assignment as a non-text edit.

Downloaded 2026-11-16; copied byte-for-byte from `~/ext`. These files are
redistributed for reproducibility, not authored or rewritten by this project.
Attribution and original licences remain with the dataset authors:

| Files | Source URL | Licence |
| --- | --- | --- |
| `mind2web-live_train_20240528.json`, `mind2web-live_test_20241024.json` | https://huggingface.co/datasets/iMeanAI/Mind2Web-Live | CC-BY-4.0 |
| `wv.jsonl`, `wv_ref.json` | https://github.com/MinorJerry/WebVoyager (data and reference answers) | Apache-2.0 |
| `ww_main.jsonl` | https://huggingface.co/datasets/callanwu/WebWalkerQA (main split) | Apache-2.0 |
| `ab_dev.jsonl` | https://huggingface.co/datasets/AssistantBench/AssistantBench (dev split) | Apache-2.0 |

Online-Mind2Web is gated on Hugging Face (requires login) and is **not used**.

## SHA-256

```text
c1abd710b99d6f810e2ce95cb6c43f31828dacd778c9e4d9dd4ddad2eaee6ac4  ab_dev.jsonl
abc2032302fed1ac801539ecc6003dd73ff0aafe824aaf9450e4e504a8ff83f2  mind2web-live_test_20241024.json
026adb028cc07f72e39af0952c8770fa630d59ea8ceffb4dc4fab5e01fd57b35  mind2web-live_train_20240528.json
69b19fd86c23f1a500244a3724e039aa7ca6a1223d03e11eb10e308d4f11c488  wv.jsonl
5473818408d8a19960c4f820c1e5721d218b87b547499d7281c2a0fc4267b0c4  wv_ref.json
cbe95d9de714ef52fe4a9ddf160dfab462407cb1ba526f1c31b4305ca32c34cb  ww_main.jsonl
```

## Sampling and normalization

Run `python -m bench.ext_sample` with Playwright and local Chromium installed.
No model client is imported or invoked. Output lives in
`docs/results/ext_sample_20261116/`. SEED is 20261116. Every task text is verbatim.
The pool contains every input task; `screening.jsonl` records every row considered,
including cheap exclusions after a stratum is full (no browser load for those).

Mind2Web IDs are filename plus original index (train and test index spaces differ);
start URL is the first evaluation URL and the complete evaluation list is retained.
WebWalkerQA has no native ID: IDs are `main:<zero-based row index>`. Its answer and
raw info (including source_website and golden_path) are retained. WebVoyager IDs
are native; reference entries are joined by website and numeric task ID, retaining
the raw answer entry and site notice. Missing references remain null, not invented.
AssistantBench uses native IDs, retains raw answer and gold_url, and records the
only non-text edit: setting start_url to the first gold_url's scheme/host root.

Domain normalization copies `tests/test_dev3.py::registrable`, including its
explicit multi-label suffix list (not a full Public Suffix List). Overlap includes
all catalog start hosts and end-marker hosts, not just a hand-listed split subset.
Sources are processed in the quota-table order: Mind2Web-Live, WebWalkerQA,
WebVoyager, AssistantBench. Rank is one-based within source, ordered by SHA-256.
Candidate files preserve source order and increasing within-source rank.

The earlier STEP 1 candidate cap/2x-target procedure is superseded by STEP 3
above. The pool does not itself register tasks. The overlap baseline excludes
the newly generated extdev/heldout4 catalog entries to avoid self-exclusion on
reruns; all pre-existing splits still participate. Authoring keys and decisions
are separate from the reserve and automated screening ledger.

Site evidence is cached at the first eligible start URL for that registrable site.
Later paths/subdomains reuse that evidence as required; reachability does not prove
the task's target content survives. A fresh default Playwright context is used per
site; local Chrome channel is preferred with Chromium fallback, headless, no UA,
viewport, proxy, TLS, or anti-bot overrides, following script_first's browser defaults
and the heldout3 verifiers. Navigation waits for DOMContentLoaded (30s maximum),
then 2s for rendering. No screenshots. Status, title, first 200 text characters,
text length, final URL, timestamp and errors are saved. Detailed failure classes
are nested under `reachability`; the automatic exclusion reason is `unreachable`.
Timeouts/TLS/other unclassified failures remain `unreachable`, not asserted to be
dead sites. An empty rendered body is a bot-block heuristic, not manual proof.
Reruns reuse the cache; use a different output directory for a new live screen.

## Final extdev authoring policy revision

The seed, ordering, source quotas and site assignment remain unchanged. Candidate
exclusions do not consume the three-accepted-task site cap. Duplicate exclusions
compare case/punctuation/whitespace-normalized task text after removing a trailing
site/domain/brand suffix (`in`/`on`), including the public Steam brand alias for
steampowered.com. They record the already-accepted task ID.

Factual multi-page tasks are retained as partial keys: one most-specific literal
fragment and its final page URL are graded; other fragments are audit-only.
All five former STEP-2 `multi_page_answer` decisions are superseded by appended
`revised` ledger lines, leaving the original 50 lines intact. Consumers use the
latest decision per source/id. The re-walk drops provisional above-cap Rovio
fills, not any original kept task, and stops at exactly 40 tasks. Only truly
computed answers and explicitly authorized `ungradeable_end_state` UI outcomes
remain `no_checkable_key`, counted separately. No upstream/incomplete state is
substituted for a grader-denied search URL or an unreadable submitted value.

The train homepage mapping preserves existing subdomains without adding an
invalid extra `www` for sports.yahoo, store.steampowered and us.megabus. This
non-text mapping correction changes no source text, ID, rank, or site assignment.
Raw and slim input files are unchanged. No paid model/API calls or live probe run.
