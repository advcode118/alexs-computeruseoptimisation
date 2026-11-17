# Ledger summary

Source: `~/.cu-optimisation/openai-spend-alex15.json`; 131 charged task records
reconciled in ledger order to the three saved JSONLs, including token counts and
USD. No secrets copied. No repricing or ledger modification.

| Invocation | Charged rows | Recorded usage | Running total after |
|---|---:|---:|---:|
| smoke | 3 | $0.105299 | $0.155299 |
| default_rep1 | 88 | $3.023613 | $3.178912 |
| ultrafast_rep1 | 40 | $3.098815 | $6.277727 |

The separate **$0.050000 opening allowance** precedes the smoke.
Model usage is **$6.227727**; running total is
**$6.277727 / $9.00**, leaving **$2.722273**.

- Baselines + script_first, including both BU modes and failed MCP attempts:
  **$5.009993 / $5.00**, overshoot **$0.009993**.
- Cascade, including smoke: **$1.217734**
  (smoke $0.105299 + replicate 1 $1.112435).
- Opening allowance: **$0.050000**, kept separate from the arm sub-budgets.

The run caps check between tasks, allowing in-flight overshoot. Recorded costs
retain the aggregate-long-context accounting caveat in [ANALYSIS.md](ANALYSIS.md).
All paid runs remain stopped; unspent project balance is not authorization.
