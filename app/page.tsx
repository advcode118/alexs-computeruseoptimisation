import LoopPathway from "@/app/components/loop-pathway";
import ProbeCharts from "@/app/components/probe-charts";
import RunDemo from "@/app/components/run-demo";
import StatusBand from "@/app/components/status-band";
import { armMeta, probes, progress, type TimelineEntry } from "@/data/progress";

const sections = [
  { href: "#status", label: "Status" },
  { href: "#history", label: "History" },
  { href: "#how", label: "How it runs" },
  { href: "#charts", label: "Charts" },
  { href: "#loop", label: "Loop and pathway" },
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

function Timeline() {
  return (
    <ol className="relative mt-12 sm:ml-[5.5rem]">
      <span aria-hidden className="absolute top-2 bottom-2 left-[7px] w-0.5 bg-ink/80" />
      {progress.timeline.map((entry: TimelineEntry) => {
        const dot =
          entry.tone === "stop"
            ? "bg-stop"
            : entry.tone === "now"
              ? "bg-[var(--color-arm-script)]"
              : entry.id === "next"
                ? "border-2 border-ink bg-paper"
                : "bg-ink";

        return (
          <li key={entry.id} className="reveal relative pb-14 pl-10 last:pb-0">
            <span aria-hidden className={`absolute top-1.5 left-0 size-4 rounded-full ring-4 ring-paper ${dot}`} />
            <p className={`font-mono text-sm ${entry.tone === "stop" ? "font-bold text-stop" : "text-mute"}`}>
              {entry.label}
            </p>
            <h3 className="mt-1 font-display text-2xl leading-tight font-bold tracking-tight sm:text-3xl">{entry.title}</h3>
            <p className="mt-2 max-w-3xl leading-relaxed text-mute">{entry.body}</p>
            {entry.stack ? (
              <ol className="mt-4 grid max-w-3xl gap-x-6 sm:grid-cols-2">
                {entry.stack.map((item) => (
                  <li key={item.pr} className="grid grid-cols-[2.75rem_minmax(0,1fr)] border-b border-rule py-1.5 text-sm">
                    <span className="font-mono font-bold">{item.pr}</span>
                    <span>{item.text}</span>
                  </li>
                ))}
              </ol>
            ) : null}
            {entry.figures.length ? (
              <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
                {entry.figures.map((figure) => (
                  <div
                    key={figure.label}
                    className={`flex min-w-[8rem] flex-col-reverse ${
                      figure.yours ? "-mx-2 rounded-md bg-[var(--color-yours-soft)] px-2 py-1" : ""
                    }`}
                  >
                    <dt className={`text-sm ${figure.yours ? "font-semibold text-[var(--color-yours)]" : "text-mute"}`}>
                      {figure.yours ? "Yours: " : ""}
                      {figure.label}
                    </dt>
                    <dd
                      className={`font-mono text-2xl font-bold tracking-tight tabular-nums ${
                        figure.yours ? "text-[var(--color-yours)]" : ""
                      }`}
                    >
                      {figure.value}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function ProbeTable() {
  return (
    <details className="mt-10 border-t border-rule pt-4">
      <summary className="cursor-pointer font-display font-semibold">The same numbers as a table</summary>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="border-b-2 border-ink font-display">
            <tr>
              <th className="py-2 pr-4">Probe</th>
              <th className="py-2 pr-4">Arm</th>
              <th className="py-2 pr-4">Success</th>
              <th className="py-2 pr-4">Wall time per success</th>
              <th className="py-2 pr-4">Cost</th>
              <th className="py-2">Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule font-mono">
            {probes.flatMap((probe) =>
              probe.results.map((result) => (
                <tr key={`${probe.id}-${result.arm}`}>
                  <td className="py-2 pr-4">{probe.label}</td>
                  <td className="py-2 pr-4">{armMeta[result.arm].short}</td>
                  <td className="py-2 pr-4">
                    {result.successes}/{result.tasks}
                  </td>
                  <td className="py-2 pr-4">{result.seconds !== undefined ? `${result.seconds}s` : "—"}</td>
                  <td className="py-2 pr-4">{result.cost !== undefined ? `$${result.cost}` : "—"}</td>
                  <td className="py-2 font-sans text-mute">{result.note ?? ""}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export default function HomePage() {
  return (
    <>
      <a
        href="#status"
        className="sr-only z-50 rounded-md bg-ink px-4 py-2 text-sheet focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to the status
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
        </div>
        <div className="border-t border-rule/70">
          <ul
            aria-label="Colour key"
            className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-1 px-5 py-1.5 text-xs sm:px-8"
          >
            <li className="flex items-center gap-2 font-bold text-[var(--color-yours)]">
              <span aria-hidden className="h-2.5 w-6 rounded-full bg-[var(--color-yours)]" />
              Yours (script_first)
            </li>
            <li className="flex items-center gap-2 text-mute">
              <span aria-hidden className="flex gap-0.5">
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-arm-mcp)]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-arm-stagehand)]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-arm-proxy)]" />
              </span>
              Baselines &amp; others: Playwright MCP, Stagehand, parked proxy
            </li>
          </ul>
        </div>
      </header>

      <main id="top">
        <StatusBand />

        <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
          <div className="grid gap-6 border-b border-rule pb-10 lg:grid-cols-2 lg:gap-16">
            <p className="text-lg leading-relaxed">{progress.goal}</p>
            <div>
              <p className="font-display text-base font-semibold">The bar to beat</p>
              <p className="text-sm text-mute">{progress.benchmark.source}</p>
              <dl className="mt-3 divide-y divide-rule border-y border-rule">
                {progress.benchmark.rows.map((row) => (
                  <div key={row.name} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 py-2.5">
                    <dt className="font-semibold">{row.name}</dt>
                    <dd className="font-mono text-sm">
                      {row.pass} pass, {row.cost}
                    </dd>
                    <dd className="col-span-2 font-mono text-xs text-mute">
                      {row.time}, {row.steps}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </div>

        <section aria-labelledby="history" className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-20">
          <SectionHead
            id="history"
            number="01"
            title="How it got here"
            lede="From a loop that owns each step, through one measurement and a stack of speed-layer PRs, to one script per task."
          />
          <Timeline />
        </section>

        <section aria-labelledby="how" className="border-t border-rule py-14 sm:py-20">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <SectionHead
              id="how"
              number="02"
              title="How a task runs, arm by arm"
              lede="Pick an arm, then press Play or Step. Watch where the model calls happen. The numbers beside it are that arm's probe results."
            />
          </div>
          <div className="reveal mx-auto mt-10 max-w-6xl sm:px-8">
            <RunDemo
              demos={[
                ...progress.demos.filter((demo) => demo.id === "script_first"),
                ...progress.demos.filter((demo) => demo.id !== "script_first"),
              ]}
              probes={probes}
              tasks={progress.tasks}
            />
          </div>
        </section>

        <section aria-labelledby="charts" className="border-t border-rule bg-sheet/60 py-14 sm:py-20">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <SectionHead
              id="charts"
              number="03"
              title="Every probe, every arm"
              lede={`Three tasks per probe: ${progress.tasks.join(", ")}. Switch the measure, or group by arm to follow one arm across probes.`}
            />
            <div className="reveal mt-10">
              <ProbeCharts probes={probes} />
            </div>
            <ProbeTable />
          </div>
        </section>

        <section aria-labelledby="loop" className="border-t border-rule py-14 sm:py-20">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <SectionHead id="loop" number="04" title="The loop and the pathway" lede={progress.loop.body} />
            <LoopPathway />
          </div>
        </section>

        <footer className="border-t border-rule">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 font-mono text-xs text-mute sm:px-8">
            <p>As of {progress.asOf}. Numbers are from the probe logs.</p>
            <p>Edit {progress.sourceFile}</p>
          </div>
        </footer>
      </main>
    </>
  );
}
