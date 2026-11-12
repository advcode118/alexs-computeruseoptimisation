import type { Metadata } from "next";
import type { ReactNode } from "react";
import SpeedChart from "@/app/components/speed-chart";
import { armInfo, armOrder, dollars, measured, oneDecimal, seconds, share, taskRuns, type ArmId } from "@/data/format";
import { progress } from "@/data/progress";

export const metadata: Metadata = {
  title: "Stats: 50 held-out tasks — script_first",
  description:
    "Fair comparison of script_first, Playwright MCP and browser-use on 50 held-out tasks for gpt-6-luna and gpt-6.1-sol, plus the later plain-rule runs with Decisions off and on.",
};

const toc = [
  { href: "#comparison", label: "50 tasks" },
  { href: "#tasks", label: "Per task" },
  { href: "#rules", label: "Plain rules" },
  { href: "#decisions", label: "Decisions" },
  { href: "#next", label: "Next" },
  { href: "#ledgers", label: "Ledgers" },
  { href: "#sources", label: "Sources" },
];

const th = "px-3 py-2.5 text-left align-bottom font-display font-semibold";
const td = "px-3 py-2.5 align-top";

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

function count(value: number | null): string {
  return value === null ? "—" : String(value);
}

function fileUrl(commit: string, path: string): string {
  return `${measured.sources.repo}/blob/${commit}/${path}`;
}

export default function StatsPage() {
  const { rules, sources, ledgers } = measured;
  const decisions = rules.decisions;
  const luna = measured.heldOut.find((run) => run.model === "gpt-6-luna")!;
  const sol = measured.heldOut.find((run) => run.model === "gpt-6.1-sol")!;
  const ruleSpread = Math.max(...rules.offPasses) - Math.min(...rules.offPasses);

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
        <section aria-labelledby="title" className="mx-auto max-w-6xl px-4 pt-12 pb-10 sm:px-8 sm:pt-20">
          <p className="font-mono text-sm font-bold tracking-wide text-mute uppercase">Stats · {progress.asOf}</p>
          <h1 id="title" className="mt-3 max-w-4xl font-display text-4xl leading-[1.02] font-bold tracking-[-0.035em] text-balance sm:text-6xl">
            Fifty tasks, two models, three arms.
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-mute sm:text-xl">
            OpenAI medium, cold, one run per model and arm. script_first&apos;s runtime had no answer key and no task markers.
            Stagehand is outside this comparison. Every figure is recomputed from the saved rows.
          </p>
          <dl className="mt-10 grid gap-4 sm:grid-cols-3">
            <div className="flex flex-col-reverse rounded-lg border border-rule bg-sheet p-5">
              <dt className="mt-1 text-sm text-mute">
                gpt-6-luna script_first. Playwright MCP {luna.arms.playwright_mcp.pass}. browser-use {luna.arms.browser_use.pass}.
              </dt>
              <dd className="font-mono text-4xl font-bold tracking-tight text-[var(--color-yours-ink)] tabular-nums">
                {luna.arms.script_first.pass}/{luna.arms.script_first.of}
              </dd>
            </div>
            <div className="flex flex-col-reverse rounded-lg border border-rule bg-sheet p-5">
              <dt className="mt-1 text-sm text-mute">
                gpt-6.1-sol script_first. Playwright MCP {sol.arms.playwright_mcp.pass}. browser-use {sol.arms.browser_use.pass}.
              </dt>
              <dd className="font-mono text-4xl font-bold tracking-tight text-[var(--color-yours-ink)] tabular-nums">
                {sol.arms.script_first.pass}/{sol.arms.script_first.of}
              </dd>
            </div>
            <div className="flex flex-col-reverse rounded-lg border border-rule bg-sheet p-5">
              <dt className="mt-1 text-sm text-mute">script_first median wall time on all 50 tasks, Luna then Sol.</dt>
              <dd className="font-mono text-3xl font-bold tracking-tight text-[var(--color-yours-ink)] tabular-nums sm:text-4xl">
                {seconds(luna.arms.script_first.all.medianS)}
                <span className="text-mute"> / </span>
                {seconds(sol.arms.script_first.all.medianS)}
              </dd>
            </div>
          </dl>
          <nav aria-label="On this page" className="mt-10 flex gap-2 overflow-x-auto border-t border-rule pt-4 text-sm">
            {toc.map((item) => (
              <a key={item.href} href={item.href} className="shrink-0 rounded-full px-3 py-1.5 text-mute hover:bg-sheet hover:text-ink">
                {item.label}
              </a>
            ))}
          </nav>
        </section>

        <section aria-labelledby="comparison" className="mx-auto max-w-6xl px-4 py-12 sm:px-8">
          <SectionHead id="comparison" number="01" title="The fair comparison">
            {measured.populationNote} Seconds on the page are those values rounded to two decimals. Cost is the sum of the row
            usd fields, to four decimals.
          </SectionHead>
          <div className="mt-8">
            <SpeedChart runs={measured.heldOut} />
          </div>
          <div className="mt-8 overflow-x-auto rounded-lg border border-rule">
            <table className="w-full min-w-[52rem] text-sm">
              <caption className="px-3 pt-3 text-left font-display text-lg font-bold">Both models, all three arms</caption>
              <thead className="border-b-2 border-ink">
                <tr>
                  <th scope="col" className={th}>Model</th>
                  <th scope="col" className={th}>Arm</th>
                  <th scope="col" className={th}>Passed</th>
                  <th scope="col" className={th}>Median, all 50</th>
                  <th scope="col" className={th}>p90, all 50</th>
                  <th scope="col" className={th}>Median, passes</th>
                  <th scope="col" className={th}>p90, passes</th>
                  <th scope="col" className={th}>Cost</th>
                  <th scope="col" className={th}>Model calls</th>
                  <th scope="col" className={th}>Harness steps</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {measured.heldOut.flatMap((run) =>
                  armOrder.map((arm) => {
                    const row = run.arms[arm];
                    return (
                      <tr key={`${run.model}-${arm}`} className={arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}>
                        <th scope="row" className={`${td} font-mono font-medium`}>
                          {run.model}
                        </th>
                        <td className={td}>{armInfo[arm].name}</td>
                        <td className={`${td} font-mono tabular-nums`}>
                          {row.pass}/{row.of}
                        </td>
                        <td className={`${td} font-mono tabular-nums`}>{seconds(row.all.medianS)}</td>
                        <td className={`${td} font-mono tabular-nums`}>{seconds(row.all.p90S)}</td>
                        <td className={`${td} font-mono tabular-nums`}>{seconds(row.successes.medianS)}</td>
                        <td className={`${td} font-mono tabular-nums`}>{seconds(row.successes.p90S)}</td>
                        <td className={`${td} font-mono tabular-nums`}>{dollars(row.usd)}</td>
                        <td className={`${td} font-mono tabular-nums`}>{count(row.modelCallsSum)}</td>
                        <td className={`${td} font-mono tabular-nums`}>{count(row.stepsSum)}</td>
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-3 max-w-3xl text-sm text-mute">
            Model calls and harness steps are sums over the 50 rows. browser-use rows have no model-call field, so that cell is
            a dash. script_first script lines sum to {luna.arms.script_first.scriptStepsSum} on gpt-6-luna and{" "}
            {sol.arms.script_first.scriptStepsSum} on gpt-6.1-sol.
          </p>
          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            {measured.heldOut.map((run) => (
              <article key={run.model} className="rounded-lg border border-rule bg-sheet p-4">
                <h3 className="font-display text-xl font-bold">{run.model} misses</h3>
                <ul className="mt-3 space-y-3 text-sm">
                  {armOrder.map((arm) => (
                    <li key={arm}>
                      <p className="font-semibold">{armInfo[arm].name}</p>
                      <p className="text-mute">
                        {run.arms[arm].failureBuckets.map((bucket) => `${bucket.reason} ${bucket.n}`).join(" · ")}
                      </p>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="tasks" className="border-t border-rule bg-sheet/40 py-12">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="tasks" number="02" title="Every task">
              Wall time is that task&apos;s own seconds. Harness steps, model calls and script lines are the fields on the row.
              A dash means the log has no such field.
            </SectionHead>
            <div className="mt-8 space-y-4">
              {taskRuns.map((run) => (
                <details key={run.model} open className="rounded-lg border border-rule bg-sheet">
                  <summary className="cursor-pointer px-4 py-3 font-display text-lg font-bold">{run.model}, 50 tasks</summary>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[64rem] text-sm">
                      <caption className="sr-only">{run.model} per-task results</caption>
                      <thead className="border-y border-rule">
                        <tr>
                          <th scope="col" className={th}>Task</th>
                          {armOrder.map((arm) => (
                            <th key={arm} scope="col" className={th}>
                              {armInfo[arm].name}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-rule">
                        {run.tasks.map((task) => (
                          <tr key={task.id}>
                            <th scope="row" className={`${td} max-w-xs text-left`}>
                              <span className="block font-mono text-xs text-mute">{task.id}</span>
                              <span className="mt-1 block font-sans font-medium">{task.description}</span>
                            </th>
                            {armOrder.map((arm) => {
                              const cell = task.arms[arm as ArmId];
                              return (
                                <td key={arm} className={td}>
                                  <span className={cell.pass ? "font-semibold text-[var(--color-pass)]" : "font-semibold text-[var(--color-fail)]"}>
                                    {cell.pass ? "Pass" : "Fail"}
                                  </span>
                                  <span className="mt-1 block font-mono text-xs tabular-nums">
                                    {seconds(cell.wallS)} · steps {count(cell.steps)} · calls {count(cell.modelCalls)}
                                    {arm === "script_first" ? ` · script ${count(cell.scriptSteps)}` : ""}
                                  </span>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section aria-labelledby="rules" className="mx-auto max-w-6xl px-4 py-12 sm:px-8">
          <SectionHead id="rules" number="03" title="Plain rules, three repeats">
            {rules.codeNote} gpt-6-luna, script_first, medium, cold. The check accepts an answer that is the live page URL, or
            that appears in the page title or h1. Decisions is off in this table.
          </SectionHead>
          <div className="mt-8 overflow-x-auto rounded-lg border border-rule">
            <table className="w-full min-w-[40rem] text-sm">
              <caption className="px-3 pt-3 text-left font-display text-lg font-bold">
                Decisions off. Mean {oneDecimal(rules.offMean)} from {rules.offPasses.join(", ")}. {rules.offGraded},{" "}
                {share(rules.offPasses.reduce((sum, n) => sum + n, 0), 150)}.
              </caption>
              <thead className="border-b-2 border-ink">
                <tr>
                  <th scope="col" className={th}>Run</th>
                  <th scope="col" className={th}>Passed</th>
                  <th scope="col" className={th}>Median, all 50</th>
                  <th scope="col" className={th}>p90, all 50</th>
                  <th scope="col" className={th}>Median, passes</th>
                  <th scope="col" className={th}>Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {rules.off.map((run) => (
                  <tr key={run.file}>
                    <th scope="row" className={`${td} font-mono`}>
                      {run.run}
                    </th>
                    <td className={`${td} font-mono tabular-nums`}>
                      {run.pass}/{run.of}
                    </td>
                    <td className={`${td} font-mono tabular-nums`}>{seconds(run.all.medianS)}</td>
                    <td className={`${td} font-mono tabular-nums`}>{seconds(run.all.p90S)}</td>
                    <td className={`${td} font-mono tabular-nums`}>{seconds(run.successes.medianS)}</td>
                    <td className={`${td} font-mono tabular-nums`}>{dollars(run.usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-4 max-w-3xl space-y-1 text-sm text-mute">
            {Object.entries(rules.ruleFirstPasses).map(([reason, countOf]) => (
              <li key={reason}>
                <span className="font-mono text-ink">{countOf}</span> first verdicts: {reason}
              </li>
            ))}
            <li>All {rules.ruleFirstGradedPass} of those first verdicts passed the grade. Counted across the six runs, off and on.</li>
          </ul>
        </section>

        <section aria-labelledby="decisions" className="border-t border-rule py-12">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="decisions" number="04" title="Decisions gate, same later code">
              Three more Luna script_first runs with the gate on. Mean {oneDecimal(rules.onMean)} from {rules.onPasses.join(", ")}.{" "}
              {rules.onGraded}, {share(rules.onPasses.reduce((sum, n) => sum + n, 0), 150)}. The off runs spread from 31 to 36, so
              this mean sits inside that spread.
            </SectionHead>
            <div className="mt-8 overflow-x-auto rounded-lg border border-rule">
              <table className="w-full min-w-[40rem] text-sm">
                <caption className="px-3 pt-3 text-left font-display text-lg font-bold">Decisions on</caption>
                <thead className="border-b-2 border-ink">
                  <tr>
                    <th scope="col" className={th}>Run</th>
                    <th scope="col" className={th}>Passed</th>
                    <th scope="col" className={th}>Median, all 50</th>
                    <th scope="col" className={th}>p90, all 50</th>
                    <th scope="col" className={th}>Median, passes</th>
                    <th scope="col" className={th}>Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {rules.on.map((run) => (
                    <tr key={run.file}>
                      <th scope="row" className={`${td} font-mono`}>
                        {run.run}
                      </th>
                      <td className={`${td} font-mono tabular-nums`}>
                        {run.pass}/{run.of}
                      </td>
                      <td className={`${td} font-mono tabular-nums`}>{seconds(run.all.medianS)}</td>
                      <td className={`${td} font-mono tabular-nums`}>{seconds(run.all.p90S)}</td>
                      <td className={`${td} font-mono tabular-nums`}>{seconds(run.successes.medianS)}</td>
                      <td className={`${td} font-mono tabular-nums`}>{dollars(run.usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-rule bg-sheet p-4">
                <dt className="text-sm text-mute">Overturns that passed the grade</dt>
                <dd className="mt-1 font-mono text-2xl font-bold tabular-nums">
                  {decisions.overturnsGradedPass}/{decisions.overturns}
                </dd>
                <dd className="mt-1 text-sm text-mute">The bar set in advance was {decisions.precisionBar * 100}%.</dd>
              </div>
              <div className="rounded-lg border border-rule bg-sheet p-4">
                <dt className="text-sm text-mute">Targeted repairs that passed</dt>
                <dd className="mt-1 font-mono text-2xl font-bold tabular-nums">
                  {decisions.targetedRepairsPassed}/{decisions.targetedRepairs}
                </dd>
                <dd className="mt-1 text-sm text-mute">A repair where the blocked reason was answer needed.</dd>
              </div>
              <div className="rounded-lg border border-rule bg-sheet p-4">
                <dt className="text-sm text-mute">Decisions calls</dt>
                <dd className="mt-1 font-mono text-2xl font-bold tabular-nums">{decisions.calls}</dd>
                <dd className="mt-1 text-sm text-mute">{decisions.errors} errors on the logged error field.</dd>
              </div>
              <div className="rounded-lg border border-rule bg-sheet p-4">
                <dt className="text-sm text-mute">Call time</dt>
                <dd className="mt-1 font-mono text-2xl font-bold tabular-nums">{oneDecimal(decisions.perTaskMsMedian)} ms</dd>
                <dd className="mt-1 text-sm text-mute">
                  Median per task of in-run plus after-clock calls summed, over {decisions.tasksWithCalls} tasks. Max{" "}
                  {oneDecimal(decisions.perTaskMsMax)} ms. Tasks with a single call: {decisions.singleCallTasks}, median{" "}
                  {oneDecimal(decisions.singleCallMsMedian)} ms.
                </dd>
              </div>
            </dl>
            <p className="mt-6 max-w-3xl text-lg text-mute">The gate stays off.</p>
          </div>
        </section>

        <section aria-labelledby="next" className="border-t border-rule py-12">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="next" number="05" title="What to measure next">
              Pass count is the gap. browser-use leads both models. The three-arm table is a single run, so it has no repeat
              spread. The plain-rule repeats exist for Luna script_first only.
            </SectionHead>
            <ul className="mt-8 grid gap-4 sm:grid-cols-2">
              <li className="rounded-lg border border-rule bg-sheet p-4">
                <h3 className="font-display text-lg font-bold">Raise script_first&apos;s pass count</h3>
                <p className="mt-2 text-sm text-mute">
                  On Luna the largest script_first miss group is the model ending before the task is finished (10). On Sol the
                  largest is evidence that is not on the page (4), tied with ending on the wrong page (4).
                </p>
              </li>
              <li className="rounded-lg border border-rule bg-sheet p-4">
                <h3 className="font-display text-lg font-bold">Repeat the other arms</h3>
                <p className="mt-2 text-sm text-mute">
                  Sol, Playwright MCP and browser-use each have one saved run on this set. The Luna script_first plain-rule
                  passes already span {ruleSpread} tasks across the three repeats.
                </p>
              </li>
              <li className="rounded-lg border border-rule bg-sheet p-4">
                <h3 className="font-display text-lg font-bold">Keep the answer key out of the runtime</h3>
                <p className="mt-2 text-sm text-mute">
                  The plain rules use the live URL, the title and the h1. They do not read the task&apos;s answer markers.
                </p>
              </li>
              <li className="rounded-lg border border-rule bg-sheet p-4">
                <h3 className="font-display text-lg font-bold">Leave Decisions off</h3>
                <p className="mt-2 text-sm text-mute">
                  {decisions.overturnsGradedPass} of {decisions.overturns} overturns passed the grade. The 90% bar was missed.
                </p>
              </li>
            </ul>
          </div>
        </section>

        <section aria-labelledby="ledgers" className="border-t border-rule py-12">
          <div className="mx-auto max-w-6xl px-4 sm:px-8">
            <SectionHead id="ledgers" number="06" title="Recorded ledgers">
              Dated figures from the 11 Nov write-up. This page did not open the live ledger files.
            </SectionHead>
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <article className="rounded-lg border border-rule bg-sheet p-5">
                <h3 className="font-display text-xl font-bold">OpenAI</h3>
                <p className="mt-2 font-mono text-3xl font-bold tabular-nums">
                  ${ledgers.openai.used} <span className="text-base font-normal text-mute">of ${ledgers.openai.cap}</span>
                </p>
                <p className="mt-3 text-sm text-mute">{ledgers.openai.note}</p>
              </article>
              <article className="rounded-lg border border-rule bg-sheet p-5">
                <h3 className="font-display text-xl font-bold">Claude</h3>
                <p className="mt-2 font-mono text-3xl font-bold tabular-nums">
                  ${ledgers.claude.used} <span className="text-base font-normal text-mute">of ${ledgers.claude.cap}</span>
                </p>
                <p className="mt-3 text-sm text-mute">
                  The code aborts a run at ${ledgers.claude.abortAt}. {ledgers.claude.note}
                </p>
              </article>
            </div>
          </div>
        </section>

        <section aria-labelledby="sources" className="border-t border-rule py-12">
          <div className="mx-auto max-w-6xl px-4 pb-8 sm:px-8">
            <SectionHead id="sources" number="07" title="Sources">
              Held-out rows at commit {sources.heldOutCommit.slice(0, 7)}. Plain-rule rows at commit{" "}
              {sources.decisionsCommit.slice(0, 7)}. The held-out files match byte for byte on both commits.
            </SectionHead>
            <ul className="mt-8 space-y-2 text-sm">
              <li>
                <a className="underline underline-offset-4" href={sources.heldOutCommitUrl}>
                  Held-out commit
                </a>
              </li>
              <li>
                <a className="underline underline-offset-4" href={sources.decisionsCommitUrl}>
                  Plain-rule and Decisions commit
                </a>
              </li>
              <li>
                <a className="underline underline-offset-4" href={sources.heldOutWriteUp}>
                  Write-up section 7b
                </a>
              </li>
              <li>
                <a className="underline underline-offset-4" href={sources.decisionsWriteUp}>
                  Write-up section 7d
                </a>
              </li>
              {measured.heldOut.map((run) => (
                <li key={run.file}>
                  <a className="underline underline-offset-4" href={fileUrl(sources.heldOutCommit, run.file)}>
                    {run.file}
                  </a>
                </li>
              ))}
              {[...rules.off, ...rules.on].map((run) => (
                <li key={run.file}>
                  <a className="underline underline-offset-4" href={fileUrl(sources.decisionsCommit, run.file)}>
                    {run.file}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
}
