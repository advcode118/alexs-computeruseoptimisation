import { progress, type TrackStatus } from "@/data/progress";

const sections = [
  { href: "#next", label: "Next" },
  { href: "#bottleneck", label: "Bottleneck" },
  { href: "#tracks", label: "Tracks" },
  { href: "#missing", label: "Missing" },
];

function StatusMark({ status, label }: { status: TrackStatus; label: string }) {
  const live = status === "in_progress";

  return (
    <span
      className={`inline-flex items-center gap-2 font-mono text-[11px] tracking-[0.18em] whitespace-nowrap uppercase ${
        live ? "text-lime" : "text-muted"
      }`}
    >
      <span
        aria-hidden
        className={`size-2 shrink-0 rounded-full ${live ? "bg-lime" : "border border-current"}`}
      />
      {label}
    </span>
  );
}

export default function HomePage() {
  const headline = progress.headline.split("\n");

  return (
    <>
      <header className="sticky top-0 z-20 border-b border-line bg-ink/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-4 sm:px-8">
          <a href="#top" className="flex items-center gap-3">
            <span aria-hidden className="size-2.5 shrink-0 bg-amber" />
            <span className="font-mono text-[11px] tracking-[0.18em] uppercase">
              {progress.project}
            </span>
          </a>
          <p className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase">
            {progress.asOf}
          </p>
        </div>
        <nav
          aria-label="On this page"
          className="mx-auto flex max-w-6xl gap-5 overflow-x-auto px-5 pb-3 font-mono text-[11px] tracking-[0.16em] uppercase sm:px-8"
        >
          {sections.map((section) => (
            <a
              key={section.href}
              href={section.href}
              className="shrink-0 text-muted hover:text-paper"
            >
              {section.label}
            </a>
          ))}
        </nav>
      </header>

      <main id="top">
        <div className="mx-auto max-w-6xl px-5 pt-14 sm:px-8 sm:pt-20">
          <h1 className="max-w-[14ch] font-serif text-6xl leading-[0.9] tracking-[-0.03em] sm:text-7xl lg:text-8xl">
            {headline.map((line, index) => (
              <span key={line} className={index === headline.length - 1 ? "italic" : undefined}>
                {index > 0 ? <br /> : null}
                {line}
              </span>
            ))}
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-balance text-muted sm:text-xl">
            {progress.dek}
          </p>
        </div>

        <section
          id={progress.next.id}
          aria-labelledby="next-title"
          className="mt-12 bg-amber bg-[linear-gradient(165deg,#ffc44d_0%,#f0a202_48%,#e09400_100%)] text-amber-ink"
        >
          <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <p className="font-mono text-[11px] tracking-[0.22em] uppercase">
                {progress.next.kicker}
              </p>
              <p className="font-mono text-[11px] tracking-[0.18em] text-amber-muted uppercase">
                {progress.next.aside}
              </p>
            </div>
            <h2
              id="next-title"
              className="mt-4 max-w-[16ch] font-serif text-4xl leading-[1.02] tracking-[-0.03em] text-balance sm:text-6xl"
            >
              {progress.next.title}
            </h2>
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-amber-muted">
              {progress.next.body}
            </p>
            <ol className="mt-10 grid gap-8 sm:grid-cols-3">
              {progress.next.steps.map((step, index) => (
                <li key={step.label} className="border-t border-amber-ink/20 pt-4">
                  <p className="font-mono text-[11px] tracking-[0.18em] uppercase">
                    {String(index + 1).padStart(2, "0")} {step.label}
                  </p>
                  <p className="mt-3 text-base leading-snug">{step.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section
          id={progress.bottleneck.id}
          aria-labelledby="bottleneck-title"
          className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24"
        >
          <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">
            {progress.bottleneck.kicker}
          </p>
          <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:items-end lg:gap-16">
            <h2
              id="bottleneck-title"
              className="font-serif text-5xl leading-none tracking-[-0.03em] sm:text-6xl"
            >
              {progress.bottleneck.title}
            </h2>
            <p className="max-w-xl text-lg leading-relaxed text-muted">{progress.bottleneck.body}</p>
          </div>
          <ol className="mt-12 divide-y divide-line border-y border-line">
            {progress.bottleneck.levers.map((lever) => (
              <li
                key={lever.index}
                className="grid gap-3 py-7 sm:grid-cols-[4.5rem_minmax(0,1fr)] sm:gap-8"
              >
                <span className="font-mono text-sm tracking-[0.14em] text-amber">{lever.index}</span>
                <div>
                  <h3 className="font-serif text-3xl tracking-[-0.02em] sm:text-4xl">{lever.title}</h3>
                  <p className="mt-2 text-muted">{lever.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section
          id={progress.tracks.id}
          aria-labelledby="tracks-title"
          className="mx-auto max-w-6xl px-5 pb-16 sm:px-8 sm:pb-24"
        >
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
            <div>
              <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">
                {progress.tracks.kicker}
              </p>
              <h2
                id="tracks-title"
                className="mt-3 font-serif text-5xl tracking-[-0.03em] sm:text-6xl"
              >
                {progress.tracks.title}
              </h2>
            </div>
            <p className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase">
              {progress.tracks.items.length} tracks
            </p>
          </div>
          <ol>
            {progress.tracks.items.map((track) => {
              const live = track.status === "in_progress";

              return (
                <li
                  key={track.index}
                  className={`grid grid-cols-[3.25rem_minmax(0,1fr)] items-baseline gap-x-4 gap-y-1 border-b border-line py-6 lg:grid-cols-[4.5rem_minmax(0,1.15fr)_max-content_minmax(0,1fr)] lg:gap-x-8 ${
                    live ? "shadow-[inset_3px_0_0_0_var(--color-lime)]" : ""
                  }`}
                >
                  <span
                    className={`font-serif text-3xl italic ${live ? "text-lime" : "text-paper/35"}`}
                  >
                    {track.index}
                  </span>
                  <h3 className="min-w-0 font-serif text-2xl tracking-[-0.02em] lg:text-3xl">
                    {track.title}
                  </h3>
                  <div className="col-start-2 lg:col-start-3">
                    <StatusMark status={track.status} label={track.statusLabel} />
                  </div>
                  <p className="col-start-2 max-w-sm min-w-0 text-muted lg:col-start-4">{track.summary}</p>
                </li>
              );
            })}
          </ol>
        </section>

        <section
          id={progress.missing.id}
          aria-labelledby="missing-title"
          className="border-t-4 border-gap bg-[#191813]"
        >
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="font-mono text-[11px] tracking-[0.22em] text-gap uppercase">
                  {progress.missing.kicker}
                </p>
                <h2
                  id="missing-title"
                  className="mt-3 font-serif text-5xl tracking-[-0.03em] sm:text-6xl"
                >
                  {progress.missing.title}
                </h2>
              </div>
              <p className="font-mono text-[11px] tracking-[0.16em] text-gap uppercase">
                {progress.missing.items.length} open
              </p>
            </div>
            <ol className="mt-10">
              {progress.missing.items.map((item, index) => (
                <li
                  key={item.title}
                  className="grid grid-cols-[3.25rem_minmax(0,1fr)] items-baseline gap-x-4 gap-y-2 border-b border-line py-7 lg:grid-cols-[4.5rem_minmax(0,1fr)_minmax(0,0.9fr)] lg:gap-x-8"
                >
                  <span className="font-mono text-sm tracking-[0.14em] text-gap">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3 className="min-w-0 font-serif text-2xl leading-tight tracking-[-0.02em] lg:text-3xl">
                    {item.title}
                  </h3>
                  <p className="col-start-2 min-w-0 leading-relaxed text-muted lg:col-start-3">
                    {item.detail}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 font-mono text-[11px] tracking-[0.14em] text-muted uppercase sm:px-8">
          <p>Dark mode only</p>
          <p>Edit {progress.sourceFile}</p>
        </footer>
      </main>
    </>
  );
}
