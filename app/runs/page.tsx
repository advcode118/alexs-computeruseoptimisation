import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Measured runs — Computer-use optimisation",
  description:
    "Two timed router runs. The 36s, 48s, and 17s figures on the clock are sketches.",
};

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
        <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">Measured</p>
        <h1 className="mt-4 max-w-[16ch] font-serif text-6xl leading-[0.9] tracking-[-0.03em] sm:text-7xl">
          Two runs on this router.
        </h1>
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
        </ol>

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
