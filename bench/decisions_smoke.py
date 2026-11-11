"""Live smoke for the Decisions API. Spends a little OpenAI money; never run by tests.

    OPENAI_API_KEY="$OPENAI_API_KEY" python -m bench.decisions_smoke --live

Sends a few canned script_first end states (no browser, no answer key),
prints each p(task_done), then p50 and p95 latency and the total cost.
Every priced call goes on the OpenAI ledger before the next one is sent.
Without --live, or without OPENAI_API_KEY, it refuses and sends nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys

from bench.decisions import DEFAULT_TIMEOUT_S, DecisionsClient, decisions_payload
from bench.openai_spend import OpenAISpendLedger

_ARTICLE_TEXT = (
    "Ada Lovelace. Augusta Ada King, Countess of Lovelace (née Byron; 10 December 1815 – "
    "27 November 1852) was an English mathematician and writer, chiefly known for her work on "
    "Charles Babbage's proposed mechanical general-purpose computer, the Analytical Engine. "
) * 20

# (label, fields). Each is an end state a held-out run could see. No markers.
CANNED = (
    (
        "right page, answer is its URL",
        dict(
            task_description="Open the Wikipedia article about Ada Lovelace and report its URL.",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
            live_url="https://en.wikipedia.org/wiki/Ada_Lovelace",
            title="Ada Lovelace - Wikipedia",
            h1="Ada Lovelace",
            answer="https://en.wikipedia.org/wiki/Ada_Lovelace",
            key_text="",
            runtime_reason="answer is not in the page text",
            page_text=_ARTICLE_TEXT,
        ),
    ),
    (
        "right page, nothing returned",
        dict(
            task_description="Go to the Wikipedia article about Ada Lovelace.",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
            live_url="https://en.wikipedia.org/wiki/Ada_Lovelace",
            title="Ada Lovelace - Wikipedia",
            h1="Ada Lovelace",
            answer="",
            key_text="",
            runtime_reason="the script returned no answer or key_text",
            page_text=_ARTICLE_TEXT,
        ),
    ),
    (
        "search results page",
        dict(
            task_description="Open the Wikipedia article about Ada Lovelace and report her birth year.",
            start_url="https://en.wikipedia.org/wiki/Main_Page",
            live_url="https://en.wikipedia.org/w/index.php?search=Ada+Lovelace",
            title="Search results for Ada Lovelace - Wikipedia",
            h1="Search results",
            answer="1815",
            key_text="",
            runtime_reason="answer is not in the page text",
            page_text="Search results. Ada Lovelace. English mathematician (1815-1852). Lovelace (disambiguation).",
        ),
    ),
    (
        "title with a different dash",
        dict(
            task_description="Open the Python docs page for the heapq module and report its title.",
            start_url="https://docs.python.org/3/",
            live_url="https://docs.python.org/3/library/heapq.html",
            title="heapq — Heap queue algorithm — Python 3 documentation",
            h1="heapq — Heap queue algorithm",
            answer="heapq - Heap queue algorithm",
            key_text="",
            runtime_reason="answer is not in the page text",
            page_text="heapq — Heap queue algorithm. Source code: Lib/heapq.py. This module provides an "
            "implementation of the heap queue algorithm, also known as the priority queue algorithm.",
        ),
    ),
    (
        "wrong article",
        dict(
            task_description="Open the arXiv abstract page for 'Attention Is All You Need' and report its title.",
            start_url="https://arxiv.org/",
            live_url="https://arxiv.org/list/cs.CL/recent",
            title="Computation and Language",
            h1="Computation and Language",
            answer="Computation and Language (cs.CL)",
            key_text="",
            runtime_reason="answer is not in the page text",
            page_text="Computation and Language. Authors and titles for recent submissions.",
        ),
    ),
)


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


async def _run(timeout_s: float, repeats: int) -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    ledger = OpenAISpendLedger.read()
    if not ledger.allows_project():
        print(f"OpenAI ledger is at ${ledger.running_total_usd:.2f}. Refusing.", file=sys.stderr)
        return 2
    client = DecisionsClient(api_key, timeout_s=timeout_s)
    latencies: list[float] = []
    spent = 0.0
    failures = 0
    for round_index in range(repeats):
        for label, fields in CANNED:
            opinion = await client.ask(decisions_payload(**fields))
            if opinion.unpriced:
                ledger.note_unpriced_call(opinion.unpriced)
                print(f"unpriced call, ledger aborted: {opinion.unpriced}", file=sys.stderr)
                return 2
            if opinion.usage:
                ledger.record_decisions(
                    run_id="decisions_smoke",
                    task_id=f"smoke:{round_index}:{label}",
                    input_tokens=opinion.usage["input_tokens"],
                    output_tokens=opinion.usage["output_tokens"],
                    cached_tokens=opinion.usage["cached_tokens"],
                    cache_write_30m_tokens=opinion.usage["cache_write_30m_tokens"],
                    cache_write_12h_tokens=opinion.usage["cache_write_12h_tokens"],
                )
                ledger.save()
                spent += opinion.usd
            latencies.append(opinion.elapsed_ms)
            if not opinion.ok:
                failures += 1
            shown = "-" if opinion.p("task_done") is None else f"{opinion.p('task_done'):.3f}"
            print(
                f"{label:32s} ok={opinion.ok} ms={opinion.elapsed_ms:7.1f} "
                f"p_task_done={shown} class={opinion.choice or '-'} {opinion.error}"
            )
    print(
        f"calls={len(latencies)} failures={failures} "
        f"p50_ms={statistics.median(latencies):.1f} p95_ms={_pct(latencies, 0.95):.1f} "
        f"usd={spent:.6f} ledger_total={ledger.running_total_usd:.6f}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Decisions API smoke. Needs --live and OPENAI_API_KEY.")
    parser.add_argument("--live", action="store_true", help="Required. Sends real, billed requests.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="Seconds per call.")
    parser.add_argument("--repeats", type=int, default=2, help="Rounds over the canned states (default 2).")
    args = parser.parse_args(argv)
    if not args.live:
        print("Refusing: pass --live to send billed Decisions requests.", file=sys.stderr)
        return 2
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("Refusing: OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2
    if not 1 <= args.repeats <= 10:
        print("Refusing: --repeats must be 1 to 10.", file=sys.stderr)
        return 2
    return asyncio.run(_run(args.timeout, args.repeats))


if __name__ == "__main__":
    raise SystemExit(main())
