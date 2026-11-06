import { armMeta, ownerLabel, probes, progress } from "@/data/progress";

const highlight = "var(--color-yours-bright)";

export default function StatusBand() {
  const { status, pitch } = progress;
  const latest = probes.find((probe) => probe.id === status.probe)!;
  const maxSeconds = Math.max(...latest.results.map((result) => result.seconds ?? 0));
  const maxCost = Math.max(...latest.results.map((result) => result.cost ?? 0));

  return (
    <section id="pitch" aria-labelledby="pitch-title" className="overflow-hidden bg-night text-night-ink">
      <div className="hero-out mx-auto grid max-w-6xl gap-12 px-5 pt-16 pb-20 sm:px-8 sm:pt-24 sm:pb-28 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] lg:gap-16">
        <div>
          <p className="flex items-center gap-2 font-mono text-sm" style={{ color: highlight }}>
            <span aria-hidden className="size-2 rounded-full" style={{ background: highlight }} />
            {pitch.kicker}
          </p>
          <h1
            id="pitch-title"
            className="mt-5 font-display text-5xl leading-[0.95] font-bold tracking-[-0.035em] text-balance sm:text-7xl"
          >
            {pitch.headline}
          </h1>
          <p className="mt-6 max-w-xl text-xl leading-relaxed text-night-mute">{pitch.line}</p>

          <dl className="mt-10 grid gap-6 border-t border-white/15 pt-6 sm:grid-cols-3 sm:gap-8">
            {pitch.proof.map((item) => (
              <div key={item.label} className="flex flex-col">
                <dt className="order-2 text-sm">{item.label}</dt>
                <dd className="order-1 font-mono text-4xl font-bold tracking-tight tabular-nums" style={{ color: highlight }}>
                  {item.value}
                </dd>
                <dd className="order-3 mt-1 text-sm leading-snug text-night-mute">{item.compare}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="self-end">
          <p className="font-display text-lg font-semibold">
            Latest probe: {latest.label}, {latest.model}
          </p>
          <p className="mt-1 flex flex-wrap gap-x-4 text-sm text-night-mute">
            <span className="flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-full" style={{ background: highlight }} />
              script_first (Alex's tool)
            </span>
            <span className="flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-full bg-white/35" />
              Baselines and others
            </span>
          </p>
          <div className="mt-5 space-y-5">
            {latest.results.map((result) => {
              const yours = armMeta[result.arm].owner === "yours";
              const fill = yours ? highlight : "rgba(223, 230, 245, 0.35)";

              return (
                <div
                  key={result.arm}
                  className={yours ? "-mx-3 rounded-lg px-3 py-2 ring-2 ring-[var(--color-yours-bright)]" : ""}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="flex items-center gap-2 font-mono text-sm font-bold">
                      <span style={yours ? { color: highlight } : undefined}>{armMeta[result.arm].short}</span>
                      <span className="font-sans text-xs font-normal text-night-mute">
                        {ownerLabel[armMeta[result.arm].owner]}
                      </span>
                    </span>
                    <span className="font-mono text-sm text-night-mute">{result.successes}/{result.tasks}</span>
                  </div>
                  <div className="mt-1.5 grid grid-cols-[3rem_minmax(0,1fr)_4.5rem] items-center gap-x-2 gap-y-1 text-xs text-night-mute">
                    <span>time</span>
                    <span className="h-2.5 rounded-full bg-white/10">
                      <span
                        className="grow-x block h-full rounded-full"
                        style={{ width: `${((result.seconds ?? 0) / maxSeconds) * 100}%`, background: fill }}
                      />
                    </span>
                    <span className="text-right font-mono text-sm text-night-ink">{result.seconds}s</span>
                    <span>cost</span>
                    <span className="h-2.5 rounded-full bg-white/10">
                      <span
                        className="grow-x block h-full rounded-full"
                        style={{ width: `${((result.cost ?? 0) / maxCost) * 100}%`, background: fill }}
                      />
                    </span>
                    <span className="text-right font-mono text-sm text-night-ink">${result.cost}</span>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-6 inline-flex items-center gap-2 rounded-full border border-night-mute/40 px-3 py-1 text-sm">
            <span aria-hidden className="loop-pulse size-2 shrink-0 rounded-full" style={{ background: highlight }} />
            {status.next}
          </p>
        </div>
      </div>
    </section>
  );
}
