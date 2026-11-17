# GPT-6.2 extdev browser_use comparison — 17 November 2026

**Indicative AI-made labels only, not human ground truth or a general accuracy
claim.** One cold run per model on a fixed, identical **12/40 extdev** task subset.
Both runs use **browser_use only**, default mode, **medium** reasoning effort,
browser-use 1.0.6, local headless Chromium, no web search and the existing 30-step
limit. No task retries, warm replay or model fallback. The grader was not changed.

## Results

| Model | Attempts | AI hand correct | AI partial | Frozen grader pass | Mean wall (s) | Median wall (s) | P90 wall (s) | Run cost (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gpt-6.2-astra | 12 | 6/12 (50.0%) | 6/12 | 1/12 (8.3%) | 30.496 | 29.357 | 45.473 | $3.373590 |
| gpt-6.2-sol | 12 | 5/12 (41.7%) | 7/12 | 1/12 (8.3%) | 29.324 | 21.277 | 57.589 | $1.001328 |

Times use recorded version-2 single-timer `wall_ms`, all 12 attempts including
failures; browser launch and post-run grade reads are separate and excluded.
P90 is linearly interpolated (R7). Unrounded values: [metrics.json](metrics.json).
Per-task timing, steps, answer and page evidence are in the raw JSONLs linked by
[raw_manifest.json](raw_manifest.json); labels and grader verdicts are side by
side in [hand_labels.csv](hand_labels.csv).

Do not infer that Astra is more accurate from a one-task difference. Six Astra
and seven Sol answers are partial or evidence-limited, not counted correct.
Both models have zero `wrong` labels under this rubric, which does **not** mean
100% success. Both frozen-grader passes are Nets schedule navigation. Sol's
Steam end state is By Current Players, not the requested By Daily Players;
Astra reaches the daily table. Astra's ICSE date ends on May 24, whereas the
saved site says May 25; Sol returns the latter and saves the chairs page.

## Budget and fixed task selection

Before paid benchmarking, the control's [ledger_summary.json](../extdev_control_20261117/ledger_summary.json)
was read. Its browser_use default cost was $1.641794 / 22 tasks. Astra Standard
token rates are 4x the old Sol rates; GPT-6.2 Sol's rates are equal. Extrapolated
two-model 40-task browser_use cost: `1.641794 / 22 * 40 * (4 + 1)` = **$14.925400**,
so both full runs would not fit $7.50. Twelve paired tasks project to **$4.477620**
before probes and incidental spend, fitting the remaining budget after the
arm-change interruption described below. This is a token-volume projection,
not a guarantee; actual models differ in steps and tokens.

The final subset was fixed **before the first paid browser_use attempt**:
`probe_tasks("extdev")[::3][:12]`, zero-based indices
`0,3,6,9,12,15,18,21,24,27,30,33`. Exact IDs are in [tasks.json](tasks.json).
It was not selected from either model's browser_use outcomes. Some tasks had
already appeared in the stopped cascade, so this is not a fresh/blind claim set.
The same 12 tasks were completed for both models, one replicate each, Astra first.
No accuracy extrapolation to the other 28 tasks is warranted.

### Ledger reconciliation

Ledger: `~/.cu-optimisation/openai-spend-20261117.json`.

| Item | USD |
|---|---:|
| Provided snapshot total | $2.927650 |
| Explicit seed adjustment requested by user | $0.014931 |
| Ledger before this task's calls | **$2.942581** |
| Exact-ID probes, both models | $0.000390 |
| Completed stopped-cascade rows (Astra) | $0.266069 |
| Conservative reserve for interrupted cascade call(s), usage unavailable | $1.000000 |
| Astra browser_use | $3.373590 |
| Sol browser_use | $1.001328 |
| **New accounted spend, including reserve** | **$5.641377** |
| **Ledger after all calls** | **$8.583958** |

New measured/recorded usage alone is **$4.641377**; the extra $1 is a reserve,
not an invented token charge. The interrupted request has not been reconciled
against provider billing. No further API calls were made to label/report.
All dollar amounts are token-ledger estimates, not invoices.

The snapshot was loaded from the supplied local attachment; its SHA256 and every
new ledger task are in [ledger_summary.json](ledger_summary.json). Existing task
charges were preserved; the requested seed adjustment was added to
`recorded_extra_usd` (from $0.050000 to $0.064931 before the interruption reserve).
Project cap is **$19**, persisted in the ledger, which `OpenAISpendLedger.read`
uses when no environment override is supplied. No project-cap code change was
needed. Per-run enforcement remains enabled: the wrapper sets
`min($4.50, $7.00 - new_accounted_spend_so_far)`, leaving room below the $7.50
soft stop / $8 hard task budget. Actual caps were $4.50 for Astra and $2.359951
for Sol; neither was reached and no selected task was budget-skipped. These are
between-task checks, as in the existing harness, not provider hard limits.

## Arm-change interruption and environment failures

The original instruction allowed the product cascade. A 20-task cascade subset
was started after projecting approximately $10.11 for both full cascade runs.
When the new **browser_use only** instruction arrived, it was immediately killed.
Six completed cascade rows cost **$0.266069**. No more non-browser_use benchmark
calls were made after the change. The in-flight task's usage was not saved;
the ledger's standard $1 unpriced-call reserve was added and retained. Its
abort flag was then explicitly cleared to resume the newly authorized arm,
without removing the reserve. Thus non-browser_use benchmark accounting is
**$1.266069 including reserve**, plus the separate **$0.000390** required ID probes.
The interrupted cascade is preserved in `gpt-6.2-astra/` and excluded from the
results table; its original task manifest is `stopped-cascade-tasks.json`.
There were no completed standalone browser_use results to retain at that point.

The first browser_use invocation produced 12 infrastructure skips at zero cost:
`browser-use==1.0.6 is not installed`. The requested `.venv` and nvm environment
were active; the optional dependency was genuinely absent. Installed the
repository's declared extra with `python -m pip install -e '.[browser_use]'`,
then ran the two paid comparisons. The zero-cost file
`gpt-6.2-astra-browser_use/probe_20261117_184129.jsonl` is retained but excluded.
The earlier cascade may also have lacked its optional browser_use fallback;
its outputs are not a valid cascade comparison and are reported only for spend.

Both models encountered Cambridge security verification at the final snapshot;
their plausible dictionary answers are labelled partial, not source-verified.
Other multi-page answers likewise remain partial when the final saved evidence
does not verify all facts. No UI was separately visually checked.

## Commands and model verification

Working directory: repository root. All Python commands used `.venv` and
`source ~/.nvm/nvm.sh`. The exec tool bound `OPENAI_API_KEY` to the provisioned
secret; no key was printed or written to disk.

Exact-ID probes used POST `https://api.openai.com/v1/responses`, one request per
model, with the following payload (the model substituted literally):

```json
{"model":"gpt-6.2-astra","input":"Reply with OK.","reasoning":{"effort":"medium"},"max_output_tokens":32,"store":false}
```

Both returned `status=completed` under the exact requested ID. Astra used 10
input / 6 output tokens ($0.000320); Sol 10 / 5 ($0.000070). Full requests and
responses are `gpt-6.2-{astra,sol}-probe.json`. Probe usage was normalized with
`bench.openai_client.normalize_usage` and recorded with
`OpenAISpendLedger.record_task(run_id="gpt62-id-probe", task_id="reply_OK", ...)`.

Published rates checked before use:
[Astra](https://developers.openai.com/api/docs/models/gpt-6.2-astra),
[Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol).
USD per million input/cached-input/30m-write/12h-write/output tokens:
Astra **8 / 0.4 / 10 / 20 / 40**, Sol **2 / 0.1 / 2.5 / 5 / 10**.
The existing >272k long-context multipliers still apply. Only medium effort
was added for the new IDs; other efforts were not probed or enabled. Production
default model and sweep cells are unchanged.

Paid browser_use invocations:

```sh
source ~/.nvm/nvm.sh
source .venv/bin/activate
PYTHONPATH=. python docs/results/extdev_gpt62_20261117/run.py gpt-6.2-astra >> docs/results/extdev_gpt62_20261117/astra-browser_use.log 2>&1
PYTHONPATH=. python docs/results/extdev_gpt62_20261117/run.py gpt-6.2-sol > docs/results/extdev_gpt62_20261117/sol-browser_use.log 2>&1
```

`run.py` calls the existing `execute_openai_probe` with
`arms=("browser_use",), split="extdev", sweep=False, effort="medium",
one_task=False, headless=True, warm_replay=False, honest=False` and supplies the
fixed task subset through its task selector. It writes normal probe JSONLs and
uses the existing ledger and per-run enforcement. Do not re-run these paid
commands without a new explicit approval; rerunning also requires a fresh
output directory to preserve this experiment.

## AI hand-label method and offline reproduction

Same method/rubric as merged PR #97's
[extdev hand labels](../extdev_hand_labels_20261117/README.md): an AI agent reads
each task description, returned answer, final URL and saved page text, writing
`correct`, `partial`, `wrong` or `infra` with a short reason. Frozen grader
verdicts are visible alongside; this is **not blinded**, and there is no second
labeller. Partial includes evidence that cannot confirm a required part; a
plausible unsupported answer is not counted correct. Saved page text is capped,
so these labels measure evidence-supported success, not exhaustive live truth.
Actions are accepted from saved URL/page state, not independently re-executed.
These are **AI-made, indicative labels only**. Do not directly compare their
strict percentages to earlier labels that may have accepted more unsupported
multi-page answers. The answer keys were not changed or used during live runs.

Grader SHA256:
`7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`.

```sh
python docs/results/extdev_gpt62_20261117/build_labels.py
pytest -q tests/test_openai_provider.py tests/test_browser_use_arm.py
pytest -q docs/results/extdev_gpt62_20261117/test_report.py
```

Checks: **44 passed in 0.63s** (provider/browser_use), **3 passed in 0.04s**
(report empty/normal/error cases); `git diff --check` clean. No full suite,
build, separate visual verification, push or PR was performed.
