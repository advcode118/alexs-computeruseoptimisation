import type { Metadata } from "next";
import type { ReactNode } from "react";
import { EffortLines, Legend, SonnetGroups, SpeedCostScatter, armColor } from "./charts";
import {
  armOrder,
  arms,
  decisionsResult,
  heldOut,
  heldOutArms,
  heldOutTasks,
  ledgers,
  mediumRuns,
  notExplored,
  selfCheckGroups,
  sonnetProbes,
  sweep,
  sweepTotals,
  tunedTasks,
  type Cell,
  type HeldOutArm,
  type StatsArm,
} from "@/data/stats";

export const metadata: Metadata = {
  title: "Stats: what we've tested — script_first",
  description:
    "Every live probe so far: the 50-task held-out run with no answer key, the self-check fixes and the Decisions API experiment, plus script_first against Playwright MCP, Stagehand and browser-use on Claude Sonnet 5.5 and OpenAI gpt-6.1-sol / gpt-6-luna, how grading works, and what has not been tested yet.",
};

const toc = [
  { href: "#board", label: "Leaderboard" },
  { href: "#arms", label: "What we test" },
  { href: "#grading", label: "Grading" },
  { href: "#heldout", label: "Held-out, 50 tasks" },
  { href: "#selfcheck", label: "Self-check & Decisions" },
  { href: "#sonnet", label: "Sonnet 5.5" },
  { href: "#sweep", label: "Effort sweep" },
  { href: "#medium", label: "OpenAI 3-task" },
  { href: "#spend", label: "Spend" },
  { href: "#unexplored", label: "Not tested yet" },
  { href: "#caveats", label: "Caveats" },
];

const sec = (n: number) => `${n.toFixed(2)}s`;
const usd = (n: number) => `$${n.toFixed(6)}`;
const yoursText = "text-[var(--color-yours-ink)]";

function ArmName({ arm, withRole = false }: { arm: StatsArm; withRole?: boolean }) {
  const yours = arm === "script_first";
  return (
    <span className={yours ? `font-semibold ${yoursText}` : "font-semibold"}>
      {arms[arm].name}
      {withRole ? <span className="block text-sm font-normal text-mute">{arms[arm].role}</span> : null}
    </span>
  );
}

function Verdict({ pass }: { pass: boolean }) {
  return pass ? (
    <span className="inline-flex items-center gap-1 font-sans font-semibold text-[var(--color-pass)]">
      <span aria-hidden>✓</span> Pass
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded bg-[var(--color-fail-soft)] px-1.5 font-sans font-semibold text-[var(--color-fail)]">
      <span aria-hidden>✗</span> Fail
    </span>
  );
}

function SectionHead({ id, number, title, children }: { id: string; number: string; title: string; children?: ReactNode }) {
  return (
    <div className="grid gap-2 sm:grid-cols-[4rem_minmax(0,1fr)] sm:gap-6">
      <span aria-hidden className="font-mono text-sm font-bold text-mute">
        {number}
      </span>
      <div>
        <h2 id={id} className="font-display text-3xl leading-[1.05] font-bold tracking-[-0.03em] text-balance sm:text-5xl">
          {title}
        </h2>
        {children ? <div className="mt-3 max-w-3xl text-lg leading-relaxed text-mute">{children}</div> : null}
      </div>
    </div>
  );
}

function ChartCard({ title, note, shapes = false, children }: { title: string; note: string; shapes?: boolean; children: ReactNode }) {
  return (
    <figure className="rounded-lg border border-rule bg-sheet p-4 sm:p-5">
      <figcaption>
        <span className="block font-display text-lg font-bold">{title}</span>
        <span className="block text-sm text-mute">{note}</span>
      </figcaption>
      <div className="mt-3">
        <Legend shapes={shapes} />
      </div>
      <div className="mt-3 overflow-hidden rounded-md">{children}</div>
    </figure>
  );
}

function Leaderboard() {
  const best = sonnetProbes[0];
  const heldCell = (arm: StatsArm, model: string) => {
    const run = heldOut.find((r) => r.model === model);
    const inRun = (heldOutArms as StatsArm[]).includes(arm);
    const row = run && inRun ? run.rows[arm as HeldOutArm] : null;
    return row ? `${row.pass}/${row.of} · ${sec(row.median)}` : "not run";
  };
  const medMed = (arm: StatsArm) => {
    const p = mediumRuns.reduce((n, r) => n + r.totals[arm].pass, 0);
    const o = mediumRuns.reduce((n, r) => n + r.totals[arm].of, 0);
    return `${p}/${o}`;
  };
  const max = Math.max(...best.rows.map((r) => r.median));
  return (
    <TableWrap label="Leaderboard across all tests">
      <table className="w-full min-w-[72rem] text-sm">
        <caption className="px-3 pt-3 text-left font-display text-lg font-bold">
          Leaderboard. Sorted by Sonnet median time, fastest first.
        </caption>
        <thead className="border-b-2 border-ink">
          <tr>
            <th scope="col" className={th}>Arm</th>
            <th scope="col" className={`${th} text-right`}>Held-out 50, Sol: passed · median</th>
            <th scope="col" className={`${th} text-right`}>Held-out 50, Luna: passed · median</th>
            <th scope="col" className={`${th} text-right`}>Sonnet 18 tasks passed (upper bound)</th>
            <th scope="col" className={th}>Sonnet median time per success</th>
            <th scope="col" className={`${th} text-right`}>OpenAI sweep median</th>
            <th scope="col" className={`${th} text-right`}>OpenAI sweep cost</th>
            <th scope="col" className={`${th} text-right`}>OpenAI 3-task, both models</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {[...best.rows].sort((a, b) => a.median - b.median).map((r) => (
            <tr key={r.arm} className={r.arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}>
              <th scope="row" className={`${td} text-left`}>
                <span className="flex items-center gap-2">
                  <span aria-hidden className="inline-block size-3 rounded-sm" style={{ background: armColor[r.arm] }} />
                  <ArmName arm={r.arm} withRole />
                </span>
              </th>
              <td className={`${td} text-right font-mono tabular-nums`}>{heldCell(r.arm, "gpt-6.1-sol")}</td>
              <td className={`${td} text-right font-mono tabular-nums`}>{heldCell(r.arm, "gpt-6-luna")}</td>
              <td className={`${td} text-right font-mono tabular-nums`}>{r.pass}/{r.of}</td>
              <td className={td}>
                <span className="flex items-center gap-3">
                  <span aria-hidden className="h-2.5 w-40 rounded-full bg-rule/60">
                    <span className="block h-full rounded-full" style={{ width: `${(r.median / max) * 100}%`, background: armColor[r.arm] }} />
                  </span>
                  <span className="font-mono tabular-nums">{sec(r.median)}</span>
                </span>
              </td>
              <td className={`${td} text-right font-mono tabular-nums`}>{sec(sweepTotals[r.arm].median)}</td>
              <td className={`${td} text-right font-mono tabular-nums`}>${sweepTotals[r.arm].usd.toFixed(4)}</td>
              <td className={`${td} text-right font-mono tabular-nums`}>{medMed(r.arm)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

/** Scrollable table wrapper: keyboard-focusable so it can be scrolled without a mouse. */
function TableWrap({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="region" aria-label={label} tabIndex={0} className="mt-6 overflow-x-auto rounded-lg border border-rule bg-sheet">
      {children}
    </div>
  );
}

const th = "px-3 py-2.5 text-left align-bottom font-display font-semibold";
const td = "px-3 py-2.5 align-top";

/** Horizontal bars. Each row carries its name and value as text, so the bar itself is decorative. */
function Bars({
  title,
  note,
  max,
  rows,
}: {
  title: string;
  note: string;
  max: number;
  rows: { key: string; label: ReactNode; value: number; text: string; yours?: boolean }[];
}) {
  return (
    <figure className="rounded-lg border border-rule bg-sheet p-4 sm:p-6">
      <figcaption>
        <span className="block font-display text-lg font-bold">{title}</span>
        <span className="block text-sm text-mute">{note}</span>
      </figcaption>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => (
          <li key={row.key} className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)_auto] items-center gap-3 text-sm sm:grid-cols-[11rem_minmax(0,1fr)_6.5rem]">
            <span className={row.yours ? `font-semibold ${yoursText}` : "font-semibold"}>{row.label}</span>
            <span aria-hidden className="h-3 rounded-full bg-rule/50">
              <span
                className={`block h-full rounded-full ${row.yours ? "bg-[var(--color-yours)]" : "bg-[var(--color-arm-mcp)]"}`}
                style={{ width: `${Math.max(1.5, (row.value / max) * 100)}%` }}
              />
            </span>
            <span className="text-right font-mono font-bold tabular-nums">{row.text}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

function CellText({ cell }: { cell: Cell }) {
  return (
    <>
      <Verdict pass={cell.pass} />
      <span className="mt-0.5 block font-mono text-sm tabular-nums">{sec(cell.s)}</span>
      <span className="block font-mono text-xs text-mute tabular-nums">{usd(cell.usd)}</span>
    </>
  );
}

export default function StatsPage() {
  const best = sonnetProbes[0];
  const sweepRunUsd = 0.1751;

  return (
    <div className="aa min-h-screen bg-paper text-ink">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-ink px-4 py-2 text-sheet focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-20 border-b border-rule bg-paper/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-8">
          <a href="/" className="flex items-center gap-2.5 font-display text-lg font-bold tracking-tight">
            <span aria-hidden className="grid size-6 place-items-center rounded-full bg-ink">
              <span className="size-2 rounded-full bg-[var(--color-yours-bright)]" />
            </span>
            Our approach
          </a>
          <nav aria-label="Site">
            <ul className="flex gap-1 text-sm">
              <li>
                <a href="/" className="block rounded-full px-3 py-2 text-mute hover:bg-sheet hover:text-ink">
                  Overview
                </a>
              </li>
              <li>
                <a href="/stats" aria-current="page" className="block rounded-full bg-ink px-3 py-2 font-semibold text-sheet">
                  Stats
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      <main id="main">
        {/* Hero */}
        <section aria-labelledby="title" className="mx-auto max-w-6xl px-4 pt-12 pb-10 sm:px-8 sm:pt-20">
          <p className="font-mono text-sm font-bold tracking-wide text-mute uppercase">Stats · runs up to 11 November 2026</p>
          <h1 id="title" className="mt-3 max-w-4xl font-display text-4xl leading-[1.02] font-bold tracking-[-0.035em] text-balance sm:text-6xl">
            What we&apos;ve tested, and what we haven&apos;t.
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-mute sm:text-xl">
            The goal is to make browser computer use faster than Stagehand, Playwright MCP and browser-use without giving up
            success rate. <strong className={`font-semibold ${yoursText}`}>script_first</strong> is our approach. Every
            number below comes from a saved run file or probe log. Nothing is estimated unless it says so. The headline is
            the 50-task held-out run, where script_first has no answer key.
          </p>

          <dl className="mt-10 grid gap-4 sm:grid-cols-3">
            <div className="flex flex-col-reverse rounded-lg border border-rule bg-sheet p-5">
              <dt className="mt-1 text-sm text-mute">
                Tasks script_first passed out of 50 held-out tasks (gpt-6.1-sol, no answer key). browser-use passed 41, Playwright MCP 38.
              </dt>
              <dd className={`font-mono text-4xl font-bold tracking-tight tabular-nums ${yoursText}`}>37/50</dd>
            </div>
            <div className="flex flex-col-reverse rounded-lg border border-rule bg-sheet p-5">
              <dt className="mt-1 text-sm text-mute">
                Median time per task on those 50. browser-use and Playwright MCP: 13.8s. On gpt-6-luna: 5.98s against 12.98s and 20.33s.
              </dt>
              <dd className={`font-mono text-4xl font-bold tracking-tight tabular-nums ${yoursText}`}>4.15s</dd>
            </div>
            <div className="flex flex-col-reverse rounded-lg border border-rule bg-sheet p-5">
              <dt className="mt-1 text-sm text-mute">
                Cost of the 50 tasks on gpt-6.1-sol. browser-use: $0.71. Playwright MCP: $0.50.
              </dt>
              <dd className={`font-mono text-4xl font-bold tracking-tight tabular-nums ${yoursText}`}>$0.24</dd>
            </div>
          </dl>
          <p className="mt-5 max-w-3xl text-mute">
            The honest part: script_first is the fastest and cheapest, but it is <strong>not yet the most accurate</strong>. On
            gpt-6-luna it passed 27 of 50 on its first run and 31, 36 and 31 after the plain self-check rules, against 40 for
            browser-use. The earlier 18/18 on Claude Sonnet 5.5 had the answer key in the loop, so it is an upper bound.
          </p>

          <nav aria-label="On this page" className="mt-10 border-t border-rule pt-4">
            <h2 className="sr-only">On this page</h2>
            <ul className="flex flex-wrap gap-2 text-sm">
              {toc.map((item) => (
                <li key={item.href}>
                  <a href={item.href} className="block rounded-full border border-rule bg-sheet px-3 py-2 hover:border-ink">
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </section>

        <section aria-labelledby="board" className="mx-auto max-w-6xl px-4 pb-14 sm:px-8">
          <h2 id="board" className="font-display text-2xl font-bold sm:text-3xl">Leaderboard</h2>
          <p className="mt-1 max-w-3xl text-mute">
            Every test on one table. The two held-out columns are 50 tasks with no answer key. Sonnet figures are the PR #27 probe
            (18 tasks, measured with the answer key in script_first&apos;s loop, so an upper bound). OpenAI figures also include one
            Wikipedia task across 8 effort cells, and two 3-task medium runs. The sets differ, so read each column on its own.
          </p>
          <Leaderboard />
        </section>

        {/* 01 Arms and tasks */}
        <section aria-labelledby="arms" className="border-t border-rule bg-sheet/70 py-14 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="arms" number="01" title="What we're testing">
              Four ways to run the same browser task (&ldquo;arms&rdquo;), on the same tasks, the same model and the same grader.
            </SectionHead>

            <ul className="mt-10 grid gap-4 sm:grid-cols-2">
              {armOrder.map((arm) => {
                const yours = arm === "script_first";
                return (
                  <li
                    key={arm}
                    className={`rounded-lg border p-5 ${yours ? "border-2 border-[var(--color-yours)] bg-[var(--color-yours-soft)]" : "border-rule bg-paper"}`}
                  >
                    <h3 className="font-display text-xl font-bold">
                      <ArmName arm={arm} />
                    </h3>
                    <p className="text-sm font-semibold text-mute">{arms[arm].role}</p>
                    <p className="mt-2 leading-relaxed">{arms[arm].what}</p>
                  </li>
                );
              })}
            </ul>

            <h3 className="mt-14 font-display text-2xl font-bold">The task sets</h3>
            <ol className="mt-4 grid gap-4 lg:grid-cols-3">
              <li className="rounded-lg border border-rule bg-paper p-5">
                <p className="font-mono text-3xl font-bold">3 tasks</p>
                <p className="mt-1 font-semibold">Probe set: the tasks the arms were tuned on</p>
                <ul className="mt-3 space-y-2 text-sm leading-relaxed">
                  {tunedTasks.map((t) => (
                    <li key={t.id}>
                      <span className="font-semibold">{t.label}.</span> {t.text}
                    </li>
                  ))}
                </ul>
              </li>
              <li className="rounded-lg border border-rule bg-paper p-5">
                <p className="font-mono text-3xl font-bold">18 tasks</p>
                <p className="mt-1 font-semibold">Honest set: the 3 tuned tasks plus 15 held out</p>
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer font-semibold underline underline-offset-4">Show the 15 held-out tasks</summary>
                  <ul className="mt-2 grid grid-cols-1 gap-1 font-mono text-xs">
                    {heldOutTasks.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                </details>
                <p className="mt-3 text-sm text-mute">All Claude Sonnet 5.5 results use this set.</p>
              </li>
              <li className="rounded-lg border border-rule bg-paper p-5">
                <p className="font-mono text-3xl font-bold">50 tasks</p>
                <p className="mt-1 font-semibold">Held-out score set the dev set may not tune on</p>
                <p className="mt-3 text-sm">
                  <span className="rounded bg-[var(--color-yours)] px-1.5 py-0.5 font-semibold text-white">Probed 11 Nov</span>
                </p>
                <p className="mt-3 text-sm text-mute">
                  gpt-6.1-sol and gpt-6-luna at medium effort, one run per task, no answer key. Results in section 03. Set built in PR #33 and
                  PR #34.
                </p>
              </li>
            </ol>
          </div>
        </section>

        {/* 02 Grading */}
        <section aria-labelledby="grading" className="mx-auto max-w-6xl px-4 py-14 sm:px-8 sm:py-20">
          <SectionHead id="grading" number="02" title="How a run is graded">
            One grading function for every arm. Grading changes may only stay the same or get stricter, and always apply to all
            four arms.
          </SectionHead>
          <ol className="mt-10 grid gap-4 md:grid-cols-2">
            {[
              ["Same page, same check", "After each run the final page is read once and the same check is used for every arm (for example, the URL must contain Ada_Lovelace or heapq)."],
              ["Unknown is a fail", "An UNKNOWN verdict counts as a fail for every arm. Nothing passes by default."],
              ["Hacker News is exact match", "The answer must be the top title itself. Case and spacing fold, but a sentence around the right headline fails."],
              ["script_first must pass its own check", "Its run must end on PASS, and the evidence it returns (URL, title, key text, values) must be on the live page."],
            ].map(([title, body], i) => (
              <li key={title} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-3 rounded-lg border border-rule bg-sheet p-5">
                <span aria-hidden className="grid size-8 place-items-center rounded-full bg-ink font-mono text-sm font-bold text-sheet">
                  {i + 1}
                </span>
                <div>
                  <h3 className="font-display text-lg font-bold">{title}</h3>
                  <p className="mt-1 leading-relaxed text-mute">{body}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-6 max-w-3xl text-mute">
            Timing is wall-clock seconds, averaged over <strong className="text-ink">successful</strong> tasks only. Cost is the
            dollar figure priced on each run row.
          </p>
        </section>

        {/* 03 Sonnet */}
        {/* 03 Held-out */}
        <section aria-labelledby="heldout" className="mx-auto max-w-6xl px-4 py-14 sm:px-8 sm:py-20">
          <SectionHead id="heldout" number="03" title="Held-out: 50 tasks, no answer key">
            The newest and fairest test. Fifty tasks the script was not tuned on, one run per task, OpenAI at medium effort.
            script_first no longer sees the task&apos;s answer markers while it runs, and every arm is graded the same way.
            These numbers are <strong>not comparable</strong> to the 18-task Sonnet results below.
          </SectionHead>

          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            {heldOut.map((run) => (
              <Bars
                key={run.model}
                title={`Median time per task, ${run.model}`}
                note="Lower is faster. All 50 tasks, passes and misses."
                max={22}
                rows={heldOutArms.map((arm) => ({
                  key: arm,
                  label: arms[arm].name,
                  value: run.rows[arm].median,
                  text: sec(run.rows[arm].median),
                  yours: arm === "script_first",
                }))}
              />
            ))}
          </div>

          {heldOut.map((run) => {
            const sf = run.rows.script_first;
            return (
              <article key={run.model} aria-labelledby={`ho-${run.model}`} className="mt-12">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h3 id={`ho-${run.model}`} className="font-display text-2xl font-bold">
                    {run.model}, medium effort
                  </h3>
                  <p className="font-mono text-sm text-mute">{run.file}</p>
                </div>
                <TableWrap label={`${run.model} held-out results`}>
                  <table className="w-full min-w-[40rem] text-sm">
                    <caption className="sr-only">Held-out results for {run.model}, 50 tasks per arm.</caption>
                    <thead className="border-b-2 border-ink">
                      <tr>
                        <th scope="col" className={th}>Arm</th>
                        <th scope="col" className={`${th} text-right`}>Passed</th>
                        <th scope="col" className={`${th} text-right`}>Median, all 50</th>
                        <th scope="col" className={`${th} text-right`}>Median, passes only</th>
                        <th scope="col" className={`${th} text-right`}>Cost, 50 tasks</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-rule">
                      {heldOutArms.map((arm) => {
                        const r = run.rows[arm];
                        return (
                          <tr key={arm} className={arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}>
                            <th scope="row" className={`${td} text-left`}>
                              <ArmName arm={arm} />
                            </th>
                            <td className={`${td} text-right font-mono tabular-nums`}>{r.pass}/{r.of}</td>
                            <td className={`${td} text-right font-mono tabular-nums`}>{sec(r.median)}</td>
                            <td className={`${td} text-right font-mono tabular-nums`}>{sec(r.medianPass)}</td>
                            <td className={`${td} text-right font-mono tabular-nums`}>${r.usd.toFixed(3)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </TableWrap>
                <p className="mt-4 text-sm text-mute">
                  Why script_first missed {sf.of - sf.pass} of 50:
                </p>
                <ul className="mt-2 flex flex-wrap gap-2 text-sm">
                  {run.scriptFirstFailures.map((f) => (
                    <li key={f.reason} className="rounded-full border border-rule bg-sheet px-3 py-1.5">
                      {f.reason} <span className="font-mono font-bold tabular-nums">{f.n}</span>
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}

          <div className="mt-12 rounded-lg border border-rule bg-sheet p-5 sm:p-6">
            <h3 className="font-display text-xl font-bold">Reading it</h3>
            <ul className="mt-3 grid max-w-4xl gap-3 leading-relaxed">
              <li>
                <strong className={yoursText}>script_first is the fastest and cheapest arm on both models.</strong> On Sol it takes
                a 4.15s median against 13.8s for browser-use and Playwright MCP, and costs $0.24 against $0.71 and $0.50.
              </li>
              <li>
                <strong>It still passes fewer tasks.</strong> On Sol, 37 against 41 for browser-use and 38 for Playwright MCP. On Luna,
                27 against 40 and 28. Faster is not yet better.
              </li>
              <li>
                <strong>Many of the Luna misses are its own check being too strict.</strong> All 10 &ldquo;Model ended without
                finishing&rdquo; runs had already landed on a URL that satisfied the task&apos;s URL check. The self-check rejected the
                run and the model did not send a second script. The next section is about that.
              </li>
              <li>
                <strong>Playwright MCP on Luna loses mostly on answer format:</strong> 15 of its 22 misses are an empty or wrong
                answer, not a wrong page.
              </li>
            </ul>
          </div>
        </section>

        {/* 04 Self-check and Decisions */}
        <section aria-labelledby="selfcheck" className="border-y border-rule bg-sheet/70 py-14 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="selfcheck" number="04" title="A smarter self-check, and the Decisions API">
              script_first checks its own run before it stops, using only what the run can see. Two plain rules fixed some false
              rejects with no model call. We also tried OpenAI&apos;s Decisions API as a second opinion. It did not earn a place.
            </SectionHead>

            <div className="mt-10">
              <Bars
                title="Tasks passed, script_first on Luna, three runs each"
                note="Out of 50. The same 50 held-out tasks and the same model every time."
                max={50}
                rows={selfCheckGroups.flatMap((g) =>
                  g.runs.map((run, i) => ({
                    key: `${g.id}-${i}`,
                    label: `${g.id === "before" ? "Before" : g.id === "rules" ? "Plain rules" : "+ Decisions"} · ${run.label}`,
                    value: run.pass,
                    text: `${run.pass}/50`,
                    yours: g.id === "rules",
                  })),
                )}
              />
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-3">
              {selfCheckGroups.map((g) => {
                const mean = g.runs.reduce((n, r) => n + r.pass, 0) / g.runs.length;
                const lo = Math.min(...g.runs.map((r) => r.pass));
                const hi = Math.max(...g.runs.map((r) => r.pass));
                return (
                  <div key={g.id} className="rounded-lg border border-rule bg-sheet p-5">
                    <h3 className="font-display text-lg font-bold">{g.title}</h3>
                    <p className="mt-1 text-sm text-mute">{g.note}</p>
                    <p className="mt-3 font-mono text-3xl font-bold tabular-nums">
                      {mean.toFixed(1)} <span className="text-base font-normal text-mute">mean, range {lo} to {hi}</span>
                    </p>
                    <ul className="mt-3 space-y-1 font-mono text-sm tabular-nums text-mute">
                      {g.runs.map((r) => (
                        <li key={r.label}>
                          {r.label}: {r.pass}/50, {sec(r.median)} median, ${r.usd.toFixed(4)}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>

            <div className="mt-8 grid gap-6 md:grid-cols-2">
              <div className="rounded-lg border border-rule bg-sheet p-5 sm:p-6">
                <h3 className="font-display text-xl font-bold">Plain rules: kept</h3>
                <ul className="mt-3 space-y-2 leading-relaxed">
                  <li>
                    Mean passes went from 28.3 to 32.7. The two ranges (27 to 30, then 31 to 36) do not overlap.
                  </li>
                  <li>
                    {decisionsResult.ruleFirstPasses.gradedPass} first self-check verdicts passed because of a rule (
                    {decisionsResult.ruleFirstPasses.urlRule} from the URL rule, {decisionsResult.ruleFirstPasses.titleRule} from the
                    title or heading rule). All {decisionsResult.ruleFirstPasses.gradedPass} passed the grade.
                  </li>
                  <li>The rules do not apply while the browser is still on the start page.</li>
                </ul>
              </div>
              <div className="rounded-lg border border-rule bg-sheet p-5 sm:p-6">
                <h3 className="font-display text-xl font-bold">Decisions API: not kept</h3>
                <ul className="mt-3 space-y-2 leading-relaxed">
                  <li>
                    Bar set before the runs: at least {decisionsResult.barPct}% of overturned verdicts must pass the grade. Result:{" "}
                    <strong>
                      {decisionsResult.overturnsGradedPass} of {decisionsResult.overturns}
                    </strong>{" "}
                    ({Math.round((decisionsResult.overturnsGradedPass / decisionsResult.overturns) * 100)}%). In the first round it
                    was {decisionsResult.firstRound.gradedPass} of {decisionsResult.firstRound.overturns}.
                  </li>
                  <li>
                    The &ldquo;stay on this page and return the value&rdquo; repair worked {decisionsResult.targetedRepairsPassed} time in{" "}
                    {decisionsResult.targetedRepairs}.
                  </li>
                  <li>
                    The check on averaged 33.7 passes against 32.7 with it off. That is inside the run-to-run noise.
                  </li>
                  <li>
                    Speed was not the problem: {decisionsResult.calls} calls, no timeouts, a median of {decisionsResult.medianMs} ms
                    per task that used one and {decisionsResult.maxMs} ms at worst. It judges whether the page is right, not whether the
                    returned answer is.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="sonnet" className="border-y border-rule bg-sheet/70 py-14 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="sonnet" number="05" title="Claude Sonnet 5.5 on 18 tasks">
              Three probes of the 18-task honest set, each about $3. Only script_first gets a warm replay (re-running its cached
              script). PR #27 is the fairest comparison between arms, but <strong>script_first&apos;s own stop and repair check used
              the task&apos;s answer markers in all three probes</strong>, which no real user has. Read its numbers here as an upper
              bound. The held-out run above removes the key.
            </SectionHead>

            <div className="mt-10 grid gap-6 lg:grid-cols-2">
              <Bars
                title="Median time per success, PR #27"
                note="Lower is faster. 18 tasks, one cold run each."
                max={7}
                rows={[
                  { key: "warm", label: "script_first, warm", value: best.warm.median, text: sec(best.warm.median), yours: true },
                  ...best.rows.map((r) => ({
                    key: r.arm,
                    label: arms[r.arm].name,
                    value: r.median,
                    text: sec(r.median),
                    yours: r.arm === "script_first",
                  })),
                ]}
              />
              <Bars
                title="Tasks passed, PR #27"
                note="Out of 18. Higher is better."
                max={18}
                rows={best.rows.map((r) => ({
                  key: r.arm,
                  label: arms[r.arm].name,
                  value: r.pass,
                  text: `${r.pass}/${r.of}`,
                  yours: r.arm === "script_first",
                }))}
              />
            </div>

            <div className="mt-6">
              <ChartCard title="Median time per success across the three probes" note="Lower is faster. 18 tasks per probe. PR #18 used uneven grading.">
                <SonnetGroups />
              </ChartCard>
            </div>

            {sonnetProbes.map((probe) => (
              <article key={probe.id} aria-labelledby={`${probe.id}-h`} className="mt-12">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h3 id={`${probe.id}-h`} className="font-display text-2xl font-bold">
                    {probe.title}
                  </h3>
                  {probe.fair ? (
                    <span className="rounded bg-ink px-1.5 py-0.5 text-xs font-semibold text-sheet">Shared fail-closed grader</span>
                  ) : (
                    <span className="rounded bg-[var(--color-fail-soft)] px-1.5 py-0.5 text-xs font-semibold text-[var(--color-fail)]">
                      Historical: uneven grading
                    </span>
                  )}
                </div>
                <p className="mt-1 font-mono text-xs text-mute">
                  {probe.tip} Spend ${probe.spendUsd.toFixed(4)}.
                </p>
                <p className="mt-2 max-w-3xl">{probe.summary}</p>
                <TableWrap label={`${probe.title} results table`}>
                  <table className="w-full min-w-[40rem] text-sm">
                    <caption className="sr-only">
                      {probe.title}: success, mean and median wall time per success, and failures, for each arm.
                    </caption>
                    <thead className="border-b-2 border-ink">
                      <tr>
                        <th scope="col" className={th}>Arm</th>
                        <th scope="col" className={`${th} text-right`}>Passed</th>
                        <th scope="col" className={`${th} text-right`}>Mean</th>
                        <th scope="col" className={`${th} text-right`}>Median</th>
                        <th scope="col" className={th}>What failed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-rule">
                      {probe.rows.map((r) => (
                        <tr key={r.arm} className={r.arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}>
                          <th scope="row" className={`${td} text-left`}>
                            <ArmName arm={r.arm} />
                          </th>
                          <td className={`${td} text-right font-mono tabular-nums`}>{r.pass}/{r.of}</td>
                          <td className={`${td} text-right font-mono tabular-nums`}>{sec(r.mean)}</td>
                          <td className={`${td} text-right font-mono tabular-nums`}>{sec(r.median)}</td>
                          <td className={`${td} text-mute`}>{r.note}</td>
                        </tr>
                      ))}
                      <tr className="bg-[var(--color-yours-soft)]">
                        <th scope="row" className={`${td} text-left`}>
                          <span className={`font-semibold ${yoursText}`}>script_first, warm replay</span>
                        </th>
                        <td className={`${td} text-right font-mono tabular-nums`}>{probe.warm.pass}/{probe.warm.of}</td>
                        <td className={`${td} text-right font-mono tabular-nums`}>{sec(probe.warm.mean)}</td>
                        <td className={`${td} text-right font-mono tabular-nums`}>{sec(probe.warm.median)}</td>
                        <td className={`${td} text-mute`}>Re-runs the cached script.</td>
                      </tr>
                    </tbody>
                  </table>
                </TableWrap>
              </article>
            ))}
          </div>
        </section>

        {/* 04 Sweep */}
        <section aria-labelledby="sweep" className="mx-auto max-w-6xl px-4 py-14 sm:px-8 sm:py-20">
          <SectionHead id="sweep" number="06" title="OpenAI effort sweep: does thinking harder help?">
            One task (Wikipedia: find the Ada Lovelace article) at four reasoning-effort levels on two OpenAI models:{" "}
            <strong className="text-ink">gpt-6-luna</strong> (the small, cheap one) and{" "}
            <strong className="text-ink">gpt-6.1-sol</strong> (the larger one). 8 cells × 4 arms = 32 runs, ${sweepRunUsd} in
            total.
          </SectionHead>

          <div className="mt-10">
            <ChartCard title="Speed against cost" note="Each point is one of the 32 runs. Both axes are logarithmic. The bottom left is best." shapes>
              <SpeedCostScatter />
            </ChartCard>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            {(["gpt-6-luna", "gpt-6.1-sol"] as const).map((m) => (
              <ChartCard key={m} title={`Time by effort, ${m}`} note="Wikipedia task. Log scale. A cross is a failed run.">
                <EffortLines model={m} />
              </ChartCard>
            ))}
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Bars
              title="Median time per success, all 8 cells"
              note="Lower is faster. Stagehand's one failure (137.03s) is left out."
              max={55}
              rows={armOrder.map((arm) => ({
                key: arm,
                label: arms[arm].name,
                value: sweepTotals[arm].median,
                text: sec(sweepTotals[arm].median),
                yours: arm === "script_first",
              }))}
            />
            <Bars
              title="Total cost, all 8 cells"
              note="Lower is cheaper. Includes the failed Stagehand cell."
              max={0.06}
              rows={armOrder.map((arm) => ({
                key: arm,
                label: arms[arm].name,
                value: sweepTotals[arm].usd,
                text: `$${sweepTotals[arm].usd.toFixed(4)}`,
                yours: arm === "script_first",
              }))}
            />
          </div>

          <ul className="mt-8 grid max-w-4xl gap-3 leading-relaxed">
            <li>
              <strong>Effort level made no clear difference to script_first.</strong> It stayed between 3.02s and 6.35s and was one
              model call, one script, every time (8/8, zero repairs).
            </li>
            <li>
              <strong>Sol cost about 17× as much as Luna</strong> for the same script_first work ($0.010390 vs $0.000609 over four
              cells), with no gain in success or speed.
            </li>
            <li>
              <strong>The only failure:</strong> Stagehand on Luna / low stopped on Wikipedia&apos;s main page with an empty answer
              after 7 model calls and 137.03s.
            </li>
          </ul>

          <TableWrap label="Effort sweep, every cell">
            <table className="w-full min-w-[46rem] text-sm">
              <caption className="px-3 pt-3 text-left font-display text-lg font-bold">
                Every cell: result, wall time, cost
              </caption>
              <thead className="border-b-2 border-ink">
                <tr>
                  <th scope="col" className={th}>Model / effort</th>
                  {armOrder.map((arm) => (
                    <th key={arm} scope="col" className={th}>
                      <ArmName arm={arm} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {sweep.map((row) => (
                  <tr key={`${row.model}-${row.effort}`}>
                    <th scope="row" className={`${td} text-left font-mono font-medium whitespace-nowrap`}>
                      {row.model.replace("gpt-6.1-", "").replace("gpt-6-", "")} / {row.effort}
                    </th>
                    {armOrder.map((arm) => (
                      <td key={arm} className={`${td} ${arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}`}>
                        <CellText cell={row.cells[arm]} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-ink">
                <tr>
                  <th scope="row" className={`${td} text-left`}>All 8 cells</th>
                  {armOrder.map((arm) => (
                    <td key={arm} className={`${td} font-mono text-sm tabular-nums ${arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}`}>
                      <span className="block font-bold">
                        {sweepTotals[arm].pass}/{sweepTotals[arm].of}
                      </span>
                      mean {sec(sweepTotals[arm].mean)}
                    </td>
                  ))}
                </tr>
              </tfoot>
            </table>
          </TableWrap>
        </section>

        {/* 05 Medium */}
        <section aria-labelledby="medium" className="border-y border-rule bg-sheet/70 py-14 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="medium" number="07" title="OpenAI at medium effort, all 3 tuned tasks">
              Two separate runs, one per model, on Wikipedia, Python docs and Hacker News. script_first passed 3/3 on both, each in
              a single script. Every other arm passed 2/3: they all missed Hacker News.
            </SectionHead>

            {mediumRuns.map((run) => (
              <article key={run.model} aria-labelledby={`${run.model}-h`} className="mt-12">
                <h3 id={`${run.model}-h`} className="font-display text-2xl font-bold">
                  {run.model}, medium
                </h3>
                <p className="mt-1 font-mono text-xs text-mute">
                  {run.file} · 12 runs · ${run.runUsd}
                </p>

                <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                  {armOrder.map((arm) => (
                    <div
                      key={arm}
                      className={`flex flex-col-reverse rounded-lg border p-4 ${arm === "script_first" ? "border-2 border-[var(--color-yours)] bg-[var(--color-yours-soft)]" : "border-rule bg-paper"}`}
                    >
                      <dt className="text-sm">
                        <ArmName arm={arm} />
                        <span className="block text-mute">median {sec(run.totals[arm].median)}</span>
                      </dt>
                      <dd className="font-mono text-2xl font-bold tabular-nums">
                        {run.totals[arm].pass}/{run.totals[arm].of}
                      </dd>
                    </div>
                  ))}
                </dl>

                <TableWrap label={`${run.model} medium, per task`}>
                  <table className="w-full min-w-[52rem] text-sm">
                    <caption className="sr-only">{run.model} at medium effort: result, time, cost and returned answer for each task and arm.</caption>
                    <thead className="border-b-2 border-ink">
                      <tr>
                        <th scope="col" className={th}>Task</th>
                        {armOrder.map((arm) => (
                          <th key={arm} scope="col" className={th}>
                            <ArmName arm={arm} />
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-rule">
                      {run.tasks.map((t) => (
                        <tr key={t.task}>
                          <th scope="row" className={`${td} text-left font-semibold`}>{t.task}</th>
                          {armOrder.map((arm) => (
                            <td key={arm} className={`${td} ${arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}`}>
                              <CellText cell={t.cells[arm]} />
                              <span className="mt-1 block text-xs leading-snug text-mute">{t.cells[arm].answer}</span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
              </article>
            ))}

            <aside aria-labelledby="hn-h" className="mt-12 rounded-lg border-l-4 border-ink bg-paper p-5 sm:p-6">
              <h3 id="hn-h" className="font-display text-xl font-bold">
                Why the others failed Hacker News
              </h3>
              <p className="mt-2 max-w-3xl leading-relaxed">
                The live top title was <span className="font-mono">.name Grandfathered</span>. script_first returned exactly that on
                both models.
              </p>
              <ul className="mt-3 max-w-3xl list-disc space-y-2 pl-5 leading-relaxed">
                <li>
                  <strong>On Sol, a format failure.</strong> Playwright MCP, Stagehand and browser-use all found the right title
                  but wrapped it in a sentence, so the exact-match check failed.
                </li>
                <li>
                  <strong>On Luna, real failures.</strong> Playwright MCP and Stagehand returned nothing. browser-use again wrapped
                  the right title in a sentence.
                </li>
              </ul>
              <p className="mt-3 max-w-3xl text-mute">
                So script_first&apos;s success lead here is partly answer format. Its speed lead is real on every task, including the
                ones the other arms passed.
              </p>
            </aside>
          </div>
        </section>

        {/* 06 Spend */}
        <section aria-labelledby="spend" className="mx-auto max-w-6xl px-4 py-14 sm:px-8 sm:py-20">
          <SectionHead id="spend" number="08" title="What it has cost so far">
            Claude and OpenAI keep separate ledgers with hard caps. The OpenAI runs did not touch the Claude ledger.
          </SectionHead>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {[
              {
                name: "Claude ledger",
                used: ledgers.claude.used,
                cap: ledgers.claude.cap,
                mark: ledgers.claude.abortAt,
                text: `Scripts abort at $${ledgers.claude.abortAt}. Each 18-task Sonnet probe cost about $3.`,
              },
              {
                name: "OpenAI ledger",
                used: ledgers.openai.used,
                cap: ledgers.openai.cap,
                text: `$${ledgers.openai.beforeHeldOut.toFixed(2)} before the held-out runs, about $${ledgers.openai.heldOut.toFixed(2)} for the 50-task held-out runs on both models, and about $${ledgers.openai.experiments.toFixed(2)} for the self-check and Decisions experiments. $${ledgers.openai.perRun} cap per run.`,
              },
            ].map((l) => (
              <div key={l.name} className="rounded-lg border border-rule bg-sheet p-5">
                <h3 className="font-display text-lg font-bold">{l.name}</h3>
                <p className="mt-1 font-mono text-3xl font-bold tabular-nums">
                  ${l.used.toFixed(2)} <span className="text-base font-normal text-mute">of ${l.cap} cap</span>
                </p>
                <div
                  role="meter"
                  aria-label={`${l.name} spend`}
                  aria-valuemin={0}
                  aria-valuemax={l.cap}
                  aria-valuenow={Number(l.used.toFixed(2))}
                  aria-valuetext={`$${l.used.toFixed(2)} of $${l.cap}`}
                  className="relative mt-3 h-3 rounded-full bg-rule/60"
                >
                  <span className="block h-full rounded-full bg-ink" style={{ width: `${(l.used / l.cap) * 100}%` }} />
                  {l.mark ? (
                    <span aria-hidden className="absolute -top-1 -bottom-1 w-0.5 bg-stop" style={{ left: `${(l.mark / l.cap) * 100}%` }} />
                  ) : null}
                </div>
                <p className="mt-3 text-sm text-mute">{l.text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 09 Not explored */}
        <section aria-labelledby="unexplored" className="bg-night py-14 text-night-ink sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <div className="grid gap-2 sm:grid-cols-[4rem_minmax(0,1fr)] sm:gap-6">
              <span aria-hidden className="font-mono text-sm font-bold text-night-mute">
                09
              </span>
              <div>
                <h2 id="unexplored" className="font-display text-3xl leading-[1.05] font-bold tracking-[-0.03em] sm:text-5xl">
                  What we haven&apos;t tested yet
                </h2>
                <p className="mt-3 max-w-3xl text-lg leading-relaxed text-night-mute">
                  The results above are a start, not a verdict. These are the gaps, none of which have been run.
                </p>
              </div>
            </div>
            <ul className="mt-10 grid gap-4 md:grid-cols-2">
              {notExplored.map((item) => (
                <li key={item.title} className="rounded-lg border border-dashed border-night-mute/60 p-5">
                  <h3 className="font-display text-xl font-bold text-white">{item.title}</h3>
                  <p className="mt-2 leading-relaxed text-night-ink">{item.body}</p>
                  {item.where ? <p className="mt-2 font-mono text-sm text-night-mute">{item.where}</p> : null}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* 10 Caveats */}
        <section aria-labelledby="caveats" className="mx-auto max-w-6xl px-4 py-14 sm:px-8 sm:py-20">
          <SectionHead id="caveats" number="10" title="Read these before quoting a number" />
          <ul className="mt-8 grid max-w-4xl gap-4 leading-relaxed">
            <li>
              <strong>The 18/18 and 2.98s headline had the answer key in the loop.</strong> Up to PR #42, script_first&apos;s own
              stop and repair check used the task&apos;s answer markers. No real user has those. Every Sonnet figure for script_first
              is an upper bound. The held-out run removes the key.
            </li>
            <li>
              <strong>Held-out is one run per task per arm, and the same code swings.</strong> script_first on Luna scored 27, 30 and
              28 before the rules and 31, 36 and 31 after. A gap smaller than about five tasks is not a result.
            </li>
            <li>
              <strong>Some held-out tasks are easy.</strong> About 19 of the 50 have a final URL that can be guessed from the task
              text, there are no multi-step or single-page-app tasks, and the arms do not all share the same timeouts and browser yet.
            </li>
            <li>
              <strong>Before and after runs were measured on live sites on the same day.</strong> Some of the gain may be site
              drift. The 20 first verdicts that passed because of a plain rule all passed the grade, which is the firmer evidence.
            </li>
            <li>
              <strong>Stagehand here is a local imitation</strong> of its tool surface, not the library. It is left out of the
              50-task comparison.
            </li>
            <li>
              <strong>3 tasks is not 18.</strong> The OpenAI runs are one Wikipedia task per effort level plus two 3-task runs on
              tuned tasks. They are not a like-for-like match with the Sonnet 18-task results.
            </li>
            <li>
              <strong>Mostly one run per cell.</strong> Only script_first on Luna has repeats (three per setting). There are no
              confidence intervals, and no warm replay on OpenAI.
            </li>
            <li>
              <strong>Stagehand timing swings a lot:</strong> 9.46s to 137.03s within the sweep. Treat a single cell as one sample.
            </li>
            <li>
              <strong>Hacker News exact match is strict on purpose.</strong> Several &ldquo;failures&rdquo; had the right title inside a
              sentence.
            </li>
            <li>
              <strong>PR #18 used uneven grading</strong> and is shown for history only. PR #23 and PR #27 use the shared grader.
            </li>
            <li>
              <strong>Sonnet per-row data is not in the repo.</strong> Those three tables come from the write-up and its probe
              logs. The OpenAI tables were re-checked against the committed JSONL files.
            </li>
          </ul>
        </section>
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-sm text-mute sm:px-8">
          <p>
            Source: <span className="font-mono">docs/TEST_RESULTS.md</span> and{" "}
            <span className="font-mono">docs/results/2026-11-10/*.jsonl</span> on{" "}
            <a
              className="font-semibold text-ink underline underline-offset-4"
              href="https://github.com/advcode118/alexs-computeruseoptimisation/pull/41"
            >
              PR #41
            </a>
            . OpenAI runs measured on tip <span className="font-mono">b33989a</span>, 10 November 2026. The 50-task held-out
            rows are on{" "}
            <a
              className="font-semibold text-ink underline underline-offset-4"
              href="https://github.com/advcode118/alexs-computeruseoptimisation/pull/47"
            >
              PR #47
            </a>{" "}
            (tip <span className="font-mono">9442722</span>). The plain-rule and Decisions rows are on{" "}
            <a
              className="font-semibold text-ink underline underline-offset-4"
              href="https://github.com/advcode118/alexs-computeruseoptimisation/pull/49"
            >
              PR #49
            </a>{" "}
            and{" "}
            <a
              className="font-semibold text-ink underline underline-offset-4"
              href="https://github.com/advcode118/alexs-computeruseoptimisation/pull/50"
            >
              PR #50
            </a>
            , 11 November 2026.
          </p>
          <p>
            <a className="font-semibold text-ink underline underline-offset-4" href="/">
              Back to the overview
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
