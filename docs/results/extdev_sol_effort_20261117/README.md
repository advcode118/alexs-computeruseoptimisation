# Sol effort and 6.1 vs 6.2 — 17 November 2026

**AI-made hand labels; indicative only, not human ground truth or a general
accuracy claim.** Follow-up to [draft PR #103](https://github.com/advcode118/alexs-computeruseoptimisation/pull/103).
Same fixed 12/40 extdev tasks, **browser_use only**, **one cold run per setting**.
Two new runs (24 task attempts); the 12 GPT-6.2 Sol medium rows and their labels
are reused unchanged from #103, not rerun or charged again.

## Results

| Model | Effort | AI correct / accuracy | AI partial | Frozen grader pass | Mean wall (s) | Median wall (s) | P90 wall (s) | USD/task | Run USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gpt-6.2-sol | low | 4/12 (33.3%) | 8/12 | 1/12 | 24.131 | 25.030 | 44.862 | $0.069505 | $0.834056 |
| gpt-6.2-sol | medium, reused #103 | 5/12 (41.7%) | 7/12 | 1/12 | 29.324 | 21.277 | 57.589 | $0.083444 | $1.001328 |
| gpt-6.1-sol | medium | 8/12 (66.7%) | 4/12 | 2/12 | 35.355 | 30.845 | 68.387 | $0.083571 | $1.002848 |

- **Effort:** 6.2 low has 17.7% lower mean wall time and 16.7% lower cost than
  6.2 medium here, but its median is higher. Its strict AI-correct count is one
  lower, entirely due to the ICSE date ambiguity below. Low is the cheapest
  and fastest by mean/p90 **of these tested settings**, not proven globally fastest.
- **Version:** 6.2 medium has 17.1% lower mean time than 6.1 medium and three
  fewer AI-correct answers: Booking's saved
  four-star evidence, APEC's saved target article and Steam's daily-player table.
  This run does not show an accuracy improvement from 6.2.
- **Uncertainty:** one replicate, small previously inspected subset, sequential
  live-site runs, variable networking/caching and one unblinded AI labeller.
  These differences are descriptive, not statistically established model rankings.

All time statistics include every task attempt, not only successes. They use
version-2 `wall_ms`, excluding separate browser-launch and post-run grade reads.
P90 is R7 linear interpolation. USD/task is total recorded USD divided by 12;
costs are the existing token-ledger estimates, not provider invoices. **All
36 rows use aggregate-token pricing**, not per-request pricing. The 6.1 Airbnb
task totals 357,123 input tokens, crossing the 272k threshold on the aggregate;
the existing harness conservatively applies long-context rates to that whole
task ($0.337064), although no individual request may have crossed it. Thus the
near-equal medium run totals do not establish invoice-level cost parity.
No accounting code or old charges were changed for this comparison. Exact
numbers are in [metrics.json](metrics.json); individual times, costs, steps,
grader results and label reasons are in [hand_labels.csv](hand_labels.csv).
Saved answers and final page evidence are in the JSONLs in [raw_manifest.json](raw_manifest.json).

## Task set and execution

The subset is exactly #103's preregistered `probe_tasks("extdev")[::3][:12]`,
indices `0,3,6,9,12,15,18,21,24,27,30,33`; [tasks.json](tasks.json) is identical.

```text
extdev_filter_greatamerica_thrill
extdev_filter_booking_times_square
extdev_filter_airbnb_europe_mansions
extdev_value_icse_2002_chairs
extdev_value_apec_peru_arrivals
extdev_value_hf_first_user_message
extdev_nav_nets_schedule
extdev_filter_amazon_puppy_food
extdev_nav_steam_daily_players
extdev_value_pirate_treasures
extdev_value_ironhide_arcade_gdc
extdev_value_cambridge_gestalt
```

Run order: #103's 6.2 medium, then this follow-up's 6.2 low, then 6.1 medium.
Each setting has one replicate of each task. No retries, warm replay, fallback,
web search, extra model-ID probes or paid labelling calls. All 24 new tasks
finished, none skipped for budget or infrastructure. Default browser-use mode
(not `ultrafast`), browser-use 1.0.6, local headless Chromium, max 30 steps, same
prompts and frozen grader. Package versions and the pre-edit #103 source commit
are saved in [environment.json](environment.json); this PR's wrapper/effort-list
edits were present for both new runs.

### Exact commands

Working directory: repository root. This VM used Python 3.12.16 in `.venv`.
The exec environment bound `OPENAI_API_KEY` to `secret:org:OPENAI_API_KEY`;
the key was not printed or written to disk. The declared optional dependency
was absent in the snapshot and installed with:

```sh
.venv/bin/python -m pip install -e '.[browser_use]'
```

Each paid shell sourced nvm and the venv and ran one of these exact commands:

```sh
source ~/.nvm/nvm.sh
source .venv/bin/activate
CU_BU_MODE= PYTHONPATH=. python docs/results/extdev_gpt62_20261117/run.py gpt-6.2-sol --effort low --output-root docs/results/extdev_sol_effort_20261117 --spend-baseline 8.583958 --spend-limit 3 --run-cap 1.25 --headroom 0.5 > docs/results/extdev_sol_effort_20261117/gpt-6.2-sol-low.log 2>&1
CU_BU_MODE= PYTHONPATH=. python docs/results/extdev_gpt62_20261117/run.py gpt-6.1-sol --effort medium --output-root docs/results/extdev_sol_effort_20261117 --spend-baseline 8.583958 --spend-limit 3 --run-cap 1.25 --headroom 0.5 > docs/results/extdev_sol_effort_20261117/gpt-6.1-sol-medium.log 2>&1
```

The reused medium invocation was
`PYTHONPATH=. python docs/results/extdev_gpt62_20261117/run.py gpt-6.2-sol`
on #103's version of the wrapper; full original commands and accounting are in
[its README](../extdev_gpt62_20261117/README.md).

The extended #103 wrapper still calls `execute_openai_probe` with
`arms=("browser_use",), split="extdev", sweep=False, one_task=False,
headless=True, warm_replay=False, honest=False`, the same fixed selector, and
the explicitly requested model/effort. It now accepts output/budget arguments,
requires a non-stale non-aborted ledger, and refuses an existing destination.
New destination names include effort. Do not rerun paid commands without new
approval, a fresh destination and a current approved ledger/budget baseline.

Only `gpt-6.2-sol` low effort was additionally enabled; Astra's effort list,
default model/medium effort, prices and default sweep cells are unchanged. Official
[Sol model documentation](https://developers.openai.com/api/docs/models/gpt-6.2-sol)
and [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
were read before the run; the low run completed using that requested effort.
Both Sol versions use the existing Standard input/cached-input/30m-write/
12h-write/output rates of **$2 / $0.1 / $2.5 / $5 / $10 per million tokens**,
with existing long-context rules. No Fast/Ultrafast billing tier was requested.

## Hand-label method and sensitivity

Same evidence-supported rubric as [#103](../extdev_gpt62_20261117/README.md)
and [#97](../extdev_hand_labels_20261117/README.md): AI reads the task,
returned answer, final URL and saved page text, labels `correct`, `partial`,
`wrong` or `infra`, and writes a reason. Only `correct` enters accuracy;
partial includes plausible but not fully source-supported compound answers.
Frozen-grader outcomes are visible alongside, so labelling is not blinded.
No second labeller or separate live/human spot-check. Saved text is capped,
and earlier pages cited by an answer may be absent from the final snapshot.
Labels are manually AI-authored in [labels_input.txt](labels_input.txt);
the build script joins them offline and copies #103's medium labels unchanged.

**ICSE date sensitivity:** 6.2 low returns May 19–24, supported by its saved
ICSE history page. The committee page saved by both medium runs instead says
May 19–25. Chairs and Orlando match throughout. Following #103's conservative
treatment of the date conflict, low is `partial`, not a fully correct answer.
Accepting the history page's date makes low **5/12 (41.7%)**, tying 6.2 medium;
this alone changes the low-versus-medium strict accuracy comparison. It does
not alter the latency/cost figures. Do not interpret that one-task gap as an
established effort-related accuracy loss.

All settings remain partial on Airbnb's missing Mansions restriction,
multi-page Pirate opening/prize evidence, Ironhide's compound historical
claims and Cambridge's final Cloudflare page. Frozen passes remain separate:
only Nets for each 6.2 setting, Nets and APEC for 6.1 medium.

## Budget reconciliation

| Item | USD |
|---|---:|
| Opening recorded total from #103 | $8.583958 |
| New 6.2 Sol low run | $0.834056 |
| New 6.1 Sol medium run | $1.002848 |
| **New total, below the $3 approval** | **$1.836904** |
| **Final recorded ledger total** | **$10.420862** |
| Approved project cap, raised from $19 | $22.000000 |

This VM had no `~/.cu-optimisation/openai-spend-20261117.json`. Before the first
call it was restored from #103's committed `ledger_summary.json`: all 32 listed
task records were preserved, the older $2.942581 seed was carried forward as an
aggregate, and the existing $1 interrupted-call reserve was retained, not
resolved or removed. Thus `recorded_extra_usd` is $3.942581, **not new spend**.
No new unpriced reserve or other charge was added. Provider reconciliation of
the old $1 reserve remains outstanding as in #103.

Opening/final snapshots are [opening_ledger.json](opening_ledger.json) and
[final_ledger.json](final_ledger.json); snapshot hashes, totals and preservation
checks are in [ledger_summary.json](ledger_summary.json). Cap $22 is persisted
locally. The two run ceilings were each $1.25, further limited to remaining
new-spend allowance minus $0.50 headroom. These are the harness's between-task
checks, not provider hard limits; neither ceiling was reached. No calls were
made after these two runs. Keep the final ledger for future authorized work.

## Offline reproduction and checks

```sh
source .venv/bin/activate
python docs/results/extdev_sol_effort_20261117/build_labels.py
pytest -q tests/test_openai_provider.py tests/test_browser_use_arm.py docs/results/extdev_gpt62_20261117/test_report.py docs/results/extdev_sol_effort_20261117/test_run.py
git diff --check
```

The offline join asserts identical task order, full label coverage, no skips,
one attempt/task/setting, model/effort, cold browser_use and default mode.
Ledger checks verify 24 new task records, all opening records/reserves unchanged,
new spend below $3 and the exact final total. Budget/destination tests stub out
the probe and verify pre-call refusal paths and the reduced remaining allowance.
Focused checks: **58 passed**.
Frozen grader SHA256 unchanged:
`7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`.
No full suite, frontend build or separate visual test was run for this benchmark.
