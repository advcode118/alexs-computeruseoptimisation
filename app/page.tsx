import PitchSteps from "@/app/components/pitch-steps";
import RunDemo from "@/app/components/run-demo";
import SpeedChart from "@/app/components/speed-chart";
import StatusBand from "@/app/components/status-band";
import { armInfo, armOrder, dollars, measured, seconds } from "@/data/format";
import { progress } from "@/data/progress";

const sections = [
  { href: "#pitch", label: "Pitch" },
  { href: "#works", label: "How it works" },
  { href: "#how", label: "Walk-through" },
  { href: "#compare", label: "Comparison" },
  { href: "#next", label: "Next" },
];

function SectionHead({ id, number, title, lede }: { id: string; number: string; title: string; lede: string }) {
  return (
    <div className="grid gap-3 sm:grid-cols-[4rem_minmax(0,1fr)] sm:gap-6">
      <span className="font-mono text-sm font-bold text-mute">{number}</span>
      <div>
        <h2 id={id} className="font-display text-4xl leading-[1.02] font-bold tracking-[-0.03em] text-balance sm:text-5xl">
          {title}
        </h2>
        <p className="mt-3 max-w-2xl text-lg leading-relaxed text-mute">{lede}</p>
      </div>
    </div>
  );
}

function RepoLinks({ className }: { className: string }) {
  return (
    <ul aria-label="Source code" className={className}>
      {progress.links.map((link) => (
        <li key={link.href}>
          <a
            href={link.href}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-full border border-ink px-3 py-1 font-semibold text-ink hover:bg-ink hover:text-sheet"
          >
            {link.label}
            <span aria-hidden>↗</span>
          </a>
        </li>
      ))}
    </ul>
  );
}

export default function HomePage() {
  const off = measured.rules.offPasses;
  const on = measured.rules.onPasses;
  const luna = measured.heldOut.find((run) => run.model === "gpt-6-luna")!;
  const sol = measured.heldOut.find((run) => run.model === "gpt-6.1-sol")!;

  return (
    <>
      <span aria-hidden className="scroll-progress fixed top-0 left-0 z-30 h-[3px] w-full bg-[var(--color-yours)]" />
      <a
        href="#pitch"
        className="sr-only z-50 rounded-md bg-ink px-4 py-2 text-sheet focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to the pitch
      </a>
      <header className="sticky top-0 z-20 border-b border-rule bg-paper/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-1 px-5 py-3 sm:px-8">
          <a href="#top" className="flex items-center gap-2.5 font-display text-lg font-bold tracking-tight">
            <span aria-hidden className="grid size-6 place-items-center rounded-full bg-ink">
              <span className="size-2 rounded-full bg-[var(--color-yours-bright)]" />
            </span>
            {progress.project}
          </a>
          <nav aria-label="On this page" className="-mx-3 flex max-w-full gap-1 overflow-x-auto text-sm">
            {sections.map((section) => (
              <a
                key={section.href}
                href={section.href}
                className="shrink-0 rounded-full px-3 py-1.5 text-mute hover:bg-sheet hover:text-ink"
              >
                {section.label}
              </a>
            ))}
          </nav>
          <div className="flex shrink-0 items-center gap-2 text-sm">
            <a href="/stats" className="rounded-full bg-ink px-3 py-1 font-semibold text-sheet hover:bg-[var(--color-yours)]">
              Stats
            </a>
            <RepoLinks className="flex shrink-0 gap-2" />
          </div>
        </div>
      </header>

      <main id="top">
        <StatusBand />
        <PitchSteps />

        <section aria-labelledby="how" className="py-16 sm:py-24">
          <div className="reveal mx-auto max-w-6xl px-5 sm:px-8">
            <SectionHead
              id="how"
              number="01"
              title="Compare it, step by step"
              lede="Press Play or Step. Pink is script_first. The picture is the mechanism, and the numbers live on the stats page."
            />
          </div>
          <div className="reveal mx-auto mt-10 max-w-6xl sm:px-8">
            <RunDemo demos={progress.demos} />
          </div>
        </section>

        <section aria-labelledby="compare" className="border-y border-rule bg-sheet/70 py-16 sm:py-24">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <div className="reveal">
              <SectionHead
                id="compare"
                number="02"
                title="The same 50 tasks, both models"
                lede="OpenAI, medium effort, one cold run. Three arms. script_first never saw an answer key. Median and p90 below are two different populations: every task, and graded passes only."
              />
            </div>
            <div className="reveal mt-10">
              <SpeedChart runs={measured.heldOut} />
            </div>
            <div className="reveal mt-8 overflow-x-auto">
              <table className="w-full min-w-[44rem] text-left text-sm">
                <caption className="pb-3 text-left font-display text-lg font-bold">
                  Held-out comparison. p90 is nearest-rank.
                </caption>
                <thead className="border-b-2 border-ink font-display">
                  <tr>
                    <th scope="col" className="py-2 pr-4">Model</th>
                    <th scope="col" className="py-2 pr-4">Arm</th>
                    <th scope="col" className="py-2 pr-4">Passed</th>
                    <th scope="col" className="py-2 pr-4">Median, all 50</th>
                    <th scope="col" className="py-2 pr-4">p90, all 50</th>
                    <th scope="col" className="py-2 pr-4">Median, passes</th>
                    <th scope="col" className="py-2 pr-4">p90, passes</th>
                    <th scope="col" className="py-2">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {measured.heldOut.flatMap((run) =>
                    armOrder.map((arm) => {
                      const row = run.arms[arm];
                      return (
                        <tr key={`${run.model}-${arm}`} className={arm === "script_first" ? "bg-[var(--color-yours-soft)]" : ""}>
                          <th scope="row" className="py-2 pr-4 font-mono font-medium">
                            {run.model}
                          </th>
                          <td className="py-2 pr-4">
                            <span className="inline-flex items-center gap-2">
                              <span aria-hidden className="size-2.5 rounded-sm" style={{ background: armInfo[arm].color }} />
                              {armInfo[arm].name}
                            </span>
                          </td>
                          <td className="py-2 pr-4 font-mono tabular-nums">
                            {row.pass}/{row.of}
                          </td>
                          <td className="py-2 pr-4 font-mono tabular-nums">{seconds(row.all.medianS)}</td>
                          <td className="py-2 pr-4 font-mono tabular-nums">{seconds(row.all.p90S)}</td>
                          <td className="py-2 pr-4 font-mono tabular-nums">{seconds(row.successes.medianS)}</td>
                          <td className="py-2 pr-4 font-mono tabular-nums">{seconds(row.successes.p90S)}</td>
                          <td className="py-2 font-mono tabular-nums">{dollars(row.usd)}</td>
                        </tr>
                      );
                    }),
                  )}
                </tbody>
              </table>
            </div>
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-mute">
              script_first is the quickest arm on both models, and the cheapest. browser-use passes more tasks on both models:
              {luna.arms.browser_use.pass} against {luna.arms.script_first.pass} on gpt-6-luna, {sol.arms.browser_use.pass} against{" "}
              {sol.arms.script_first.pass} on gpt-6.1-sol. Playwright MCP passes {luna.arms.playwright_mcp.pass} on Luna and{" "}
              {sol.arms.playwright_mcp.pass} on Sol.
            </p>
          </div>
        </section>

        <section aria-labelledby="next" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
          <div className="reveal">
            <SectionHead
              id="next"
              number="03"
              title="Reliability is the open gap"
              lede="The plain URL, title and heading rules are a later code variant. Decisions stays off."
            />
          </div>
          <div className="reveal mt-10 grid gap-6 lg:grid-cols-2">
            <article className="rounded-lg border border-rule bg-sheet p-5">
              <h3 className="font-display text-2xl font-bold">Plain rules, Decisions off</h3>
              <p className="mt-2 text-mute">
                gpt-6-luna, script_first only, three separate runs of the same later code. Passes {off.join(", ")} out of 50.
                Mean {measured.rules.offMean.toFixed(1)}. Together {measured.rules.offGraded}, {((off.reduce((sum, n) => sum + n, 0) / 150) * 100).toFixed(1)}%.
              </p>
            </article>
            <article className="rounded-lg border border-rule bg-sheet p-5">
              <h3 className="font-display text-2xl font-bold">Decisions on</h3>
              <p className="mt-2 text-mute">
                The same later code with the Decisions gate. Passes {on.join(", ")} out of 50. Mean {measured.rules.onMean.toFixed(1)}.
                {measured.rules.decisions.overturnsGradedPass} of {measured.rules.decisions.overturns} overturns passed the grade,
                under the {measured.rules.decisions.precisionBar * 100}% bar. {measured.rules.decisions.targetedRepairsPassed} of{" "}
                {measured.rules.decisions.targetedRepairs} targeted repairs passed. The gate stays off.
              </p>
            </article>
          </div>
          <p className="reveal mt-6 max-w-3xl text-sm leading-relaxed text-mute">
            Those six runs are a different build from the three-arm table above. Read them on their own. The stats page has the
            timings, the sources, and every task.
          </p>
        </section>

        <footer className="border-t border-rule">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 font-mono text-xs text-mute sm:px-8">
            <p>As of {progress.asOf}. Figures are recomputed from the saved rows.</p>
            <RepoLinks className="flex gap-2 font-sans text-sm" />
            <p>
              <a href="/stats" className="underline underline-offset-4">
                Stats and sources
              </a>
            </p>
          </div>
        </footer>
      </main>
    </>
  );
}
