import LoopPathway from "@/app/components/loop-pathway";
import PitchSteps from "@/app/components/pitch-steps";
import ProbeCharts from "@/app/components/probe-charts";
import RunDemo from "@/app/components/run-demo";
import StatusBand from "@/app/components/status-band";
import { armMeta, probes, progress, type TimelineEntry } from "@/data/progress";

const sections = [
  { href: "#pitch", label: "Pitch" },
  { href: "#works", label: "How it works" },
  { href: "#how", label: "Compare" },
  { href: "#charts", label: "Results" },
  { href: "#history", label: "History" },
  { href: "#loop", label: "Background" },
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
      <span aria-hidden className="absolute top-2 bottom-2 left-[7px] w-0.5 bg-rule" />
      <span aria-hidden className="rail-fill absolute top-2 bottom-2 left-[7px] w-0.5 bg-ink" />
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

function RepoLinks({ className }: { className: string }) {
  return (
    <ul aria-label="Source code" className={className}>
      {progress.links.map((link) => (
        <li key={link.label}>
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
  const spend = progress.status.spend;

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
          <RepoLinks className="flex shrink-0 gap-2 text-sm" />
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
              lede="Press Play or Step. See where each arm calls a model. Pink is script_first."
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

        <section aria-labelledby="charts" className="border-y border-rule bg-sheet/70 py-16 sm:py-24">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <div className="reveal">
              <SectionHead
                id="charts"
                number="02"
                title="Results, probe by probe"
                lede={`Scored on wall time per successful task. Three tasks per probe: ${progress.tasks.join(", ")}.`}
              />
            </div>
            <div className="reveal mt-10">
              <ProbeCharts probes={probes} />
            </div>
            <ProbeTable />

            <div className="reveal mt-14 grid gap-10 border-t-2 border-ink pt-8 lg:grid-cols-2 lg:gap-16">
              <div>
                <h3 className="font-display text-xl font-bold">The bar to beat</h3>
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
              <div>
                <h3 className="font-display text-xl font-bold">Claude spend</h3>
                <p className="mt-1 font-mono text-2xl font-bold">
                  about ${spend.used} <span className="text-base font-normal text-mute">of ${spend.cap}</span>
                </p>
                <div className="relative mt-3 h-3 rounded-full bg-rule/60">
                  <span
                    className="grow-x block h-full rounded-full bg-ink"
                    style={{ width: `${(spend.used / spend.cap) * 100}%` }}
                  />
                  <span
                    aria-hidden
                    className="absolute -top-1 -bottom-1 w-0.5 bg-stop"
                    style={{ left: `${(spend.abortAt / spend.cap) * 100}%` }}
                  />
                </div>
                <p className="mt-2 text-sm text-mute">Scripts abort at ${spend.abortAt}.</p>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="history" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
          <div className="reveal">
            <SectionHead
              id="history"
              number="03"
              title="How it got here"
              lede="A browser loop, one measurement, a stack of speed-layer PRs, then one script per task."
            />
          </div>
          <Timeline />
        </section>

        <section aria-labelledby="loop" className="border-t border-rule bg-sheet/70 py-16 sm:py-24">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <div className="reveal">
              <SectionHead id="loop" number="04" title="Background: the loop and the pathway" lede={progress.loop.body} />
            </div>
            <div className="reveal">
              <LoopPathway />
            </div>
          </div>
        </section>

        <footer className="border-t border-rule">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 font-mono text-xs text-mute sm:px-8">
            <p>As of {progress.asOf}. Numbers are from the probe logs.</p>
            <RepoLinks className="flex gap-2 font-sans text-sm" />
            <p>Edit {progress.sourceFile}</p>
          </div>
        </footer>
      </main>
    </>
  );
}
