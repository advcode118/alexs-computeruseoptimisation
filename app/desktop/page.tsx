import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Desktop — Computer-use optimisation",
  description:
    "Desktop computer use uses the same router. A unique name is clicked with no model. The pointer may move only when the tree has no name.",
};

const steps = [
  {
    mark: "Tree",
    tone: "text-paper",
    text: "Read the Windows UI Automation tree.",
  },
  {
    mark: "No model",
    tone: "text-lime",
    text: "Click a unique name with no model.",
  },
  {
    mark: "Fast model",
    tone: "text-amber",
    text: "Send an ambiguous list to a fast model.",
  },
  {
    mark: "Frontier",
    tone: "text-gap",
    text: "Call a frontier model only when the tree has no name, and that is when the pointer may move.",
  },
];

export default function DesktopPage() {
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
        <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">Desktop</p>
        <h1 className="mt-4 max-w-[12ch] font-serif text-6xl leading-[0.9] tracking-[-0.03em] sm:text-7xl">
          Same router.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          Desktop computer use uses the same router.
        </p>

        <ol className="mt-12 divide-y divide-line border-y border-line">
          {steps.map((step) => (
            <li key={step.mark} className="grid gap-3 py-8 sm:grid-cols-[9rem_minmax(0,1fr)] sm:items-baseline sm:gap-8">
              <p className={`font-mono text-[11px] tracking-[0.16em] uppercase ${step.tone}`}>{step.mark}</p>
              <p className="max-w-xl text-lg leading-relaxed">{step.text}</p>
            </li>
          ))}
        </ol>

        <section className="mt-16 max-w-2xl" aria-labelledby="plugin-title">
          <p className="font-mono text-[11px] tracking-[0.22em] text-muted uppercase">Plugin</p>
          <h2 id="plugin-title" className="mt-3 font-serif text-4xl leading-[1.05] tracking-[-0.03em]">
            A Cursor plugin can ask this runtime to do it.
          </h2>
          <p className="mt-6 text-lg leading-relaxed text-muted">
            A plugin cannot speed up a screenshot loop that stays in charge.
          </p>
        </section>
      </main>
    </>
  );
}
