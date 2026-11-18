import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Measured runs — Computer-use optimisation",
  description:
    "Paired live run against browser-use (18 Nov 2026), older timed router runs, and which clock figures are sketches.",
};

// Paired live run, 18 Nov 2026: docs/results/paired_run_20261118 (summary.json, raw rows).
const paired = [
  { arm: "Script, then our interactive stage", ours: true, passed: "4/18", calls: "4.3 / 6", wall: "21.7s / 32.9s", usd: "$0.041", perPass: "97.7s · $0.185" },
  { arm: "Script, then browser-use (benchmark)", ours: false, passed: "12/18", calls: "8.9 / 24", wall: "41.1s / 85.4s", usd: "$0.067", perPass: "61.7s · $0.101" },
  { arm: "browser-use alone, ultrafast", ours: false, passed: "11/18", calls: "9.7 / 17", wall: "57.8s / 141.7s", usd: "$0.072", perPass: "94.5s · $0.117" },
];

const sketches = [
  { time: "36s", what: "Screenshot every step, in a browser" },
  { time: "48s", what: "Cursor on Windows, same sketch" },
  { time: "17s", what: "A Browser Use-style tree agent" },
];

export default function RunsPage() {
  return (
    <>
      <header className="sticky top-0 z-20 border-b border-line bg-ink/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <a href="/" className="flex items-center gap-3">
            <span aria-hidden className="size-2.5 shrink-0 bg-amber" />
            <span className="font-mono text-[11px] tracking-[0.18em] uppercase">
              Computer-use optimisation
            </span>
          </a>
          <a
            href="/"
            className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase hover:text-paper"
          >
            Clock
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-20">
        <section aria-labelledby="paired-title">
          <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">Measured · 18 Nov 2026</p>
          <h1 id="paired-title" className="mt-4 max-w-[20ch] font-serif text-5xl leading-[0.95] tracking-[-0.03em] sm:text-6xl">
            Faster per task, but not yet good enough.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
            Our own interactive recovery is the fastest and cheapest arm per task, but it passes 4 of 18 tasks
            against 11 for browser-use alone, so per successful task it is slower and more expensive. 18 fresh,
            pre-registered external tasks, gpt-6.1-sol at medium effort, one run per arm, graded with scorer v2.
            One run cannot separate differences of a task or two.
          </p>
          <div className="mt-10 overflow-x-auto border-y border-line">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="font-mono text-[11px] tracking-[0.14em] text-muted uppercase">
                <tr>
                  <th className="py-4 pr-4 font-normal">Arm</th>
                  <th className="py-4 pr-4 font-normal">Passed</th>
                  <th className="py-4 pr-4 font-normal">Calls mean / p90</th>
                  <th className="py-4 pr-4 font-normal">Wall mean / p90</th>
                  <th className="py-4 pr-4 font-normal">$ / task</th>
                  <th className="py-4 font-normal">Per pass</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {paired.map((row) => (
                  <tr key={row.arm}>
                    <td className={`py-4 pr-4 ${row.ours ? "text-amber" : ""}`}>{row.arm}</td>
                    <td className="py-4 pr-4 font-mono">{row.passed}</td>
                    <td className="py-4 pr-4 font-mono text-muted">{row.calls}</td>
                    <td className="py-4 pr-4 font-mono text-muted">{row.wall}</td>
                    <td className="py-4 pr-4 font-mono text-muted">{row.usd}</td>
                    <td className="py-4 font-mono text-muted">{row.perPass}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-6 max-w-2xl text-muted">
            Our interactive stage ran on 14 tasks and recovered 1; browser-use as the recovery stage ran on 15 and
            recovered 10. browser-use is the benchmark, not our product fallback: the next step is making our own
            stage recover tasks.
          </p>
        </section>

        <p className="mt-20 font-mono text-[11px] tracking-[0.22em] text-muted uppercase">Older · router runs</p>
        <h2 className="mt-4 max-w-[16ch] font-serif text-5xl leading-[0.9] tracking-[-0.03em] sm:text-6xl">
          Seven runs on this router.
        </h2>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          Wall-clock time includes launching Chrome. The bars on the clock page were not remeasured.
        </p>

        <ol className="mt-12 divide-y divide-line border-y border-line">
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">4.47s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Packing list</h2>
              <p className="mt-2 max-w-xl text-muted">
                Add milk on the local packing page. Tiers: planner, then fast. The assertion passed.
                The following cycle stopped because the model reply content was null.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">13.64s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">example.com</h2>
              <p className="mt-2 max-w-xl text-muted">
                Open the page and confirm the heading. Tiers: planner, fast, planner. The fast check
                missed. One retry confirmed the title.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">3.81s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Biography section</h2>
              <p className="mt-2 max-w-xl text-muted">
                Open the Biography section on the Ada Lovelace article and confirm the title. Tiers:
                planner, direct, planner. The direct check missed. One retry confirmed the title.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">2.30s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Wikiquote search</h2>
              <p className="mt-2 max-w-xl text-muted">
                Search for quincunx and confirm the title. Tiers: planner, then direct. The search box
                was filled and Search was clicked. No retry.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">2.55s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Charles Babbage</h2>
              <p className="mt-2 max-w-xl text-muted">
                Follow the Charles Babbage link on the Ada Lovelace article and confirm the title.
                Tiers: planner, then direct. No retry.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">3.26s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Demo form</h2>
              <p className="mt-2 max-w-xl text-muted">
                Fill a name, an email, and a short message on the local text-box demo, then submit.
                Tiers: planner. One of one cycles used a model. No retry.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">2.45s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Python docs</h2>
              <p className="mt-2 max-w-xl text-muted">
                Search for heapq, open the module, then open Priority Queue Implementation Notes.
                Tiers: planner, direct, direct. One of three cycles used a model. No retry.
              </p>
            </div>
          </li>
        </ol>
        <p className="mt-8 max-w-2xl text-muted">
          Browser Use still asks a model for every control. These runs were not raced against it.
        </p>

        <section className="mt-16" aria-labelledby="sketches-title">
          <p className="font-mono text-[11px] tracking-[0.22em] text-muted uppercase">Not a measurement</p>
          <h2 id="sketches-title" className="mt-3 font-serif text-4xl tracking-[-0.03em]">
            The older figures are sketches.
          </h2>
          <ul className="mt-8 divide-y divide-line border-y border-line">
            {sketches.map((item) => (
              <li key={item.time} className="grid grid-cols-[5rem_minmax(0,1fr)] items-baseline gap-6 py-5">
                <span className="font-mono text-sm tracking-[0.14em] text-amber">{item.time}</span>
                <span className="text-muted">{item.what}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}
