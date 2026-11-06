import { armMeta, probes, progress } from "@/data/progress";

const highlight = "#4fd1a5";

export default function StatusBand() {
  const { status } = progress;
  const latest = probes.find((probe) => probe.id === status.probe)!;
  const maxSeconds = Math.max(...latest.results.map((result) => result.seconds ?? 0));
  const maxCost = Math.max(...latest.results.map((result) => result.cost ?? 0));
  const spend = status.spend;

  return (
    <section id="status" aria-labelledby="status-title" className="bg-night text-night-ink">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-16">
        <div>
          <p className="font-mono text-sm text-night-mute">Status on {progress.asOf}</p>
          <h1
            id="status-title"
            className="mt-4 font-display text-5xl leading-[0.95] font-bold tracking-[-0.035em] text-balance sm:text-7xl"
          >
            {status.headline}
            <span className="mt-2 block text-night-mute">{status.subhead}</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed">{status.body}</p>
          <p className="mt-5 inline-flex items-center gap-2 rounded-full border border-night-mute/40 px-3 py-1 text-sm">
            <span aria-hidden className="loop-pulse size-2 shrink-0 rounded-full" style={{ background: highlight }} />
            {status.next}
          </p>
        </div>

        <div className="self-end">
          <p className="font-display text-lg font-semibold">
            {latest.label} probe, {latest.model}
          </p>
          <div className="mt-4 space-y-5">
            {latest.results.map((result) => {
              const fill = result.arm === "script_first" ? highlight : "var(--color-night-ink)";

              return (
                <div key={result.arm}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-mono text-sm font-bold">{armMeta[result.arm].short}</span>
                    <span className="font-mono text-sm text-night-mute">
                      {result.successes}/{result.tasks} passed
                    </span>
                  </div>
                  <div className="mt-1.5 grid grid-cols-[3rem_minmax(0,1fr)_4.5rem] items-center gap-x-2 gap-y-1 text-xs text-night-mute">
                    <span>time</span>
                    <span className="h-2.5 rounded-full bg-white/10">
                      <span
                        className="block h-full rounded-full"
                        style={{ width: `${((result.seconds ?? 0) / maxSeconds) * 100}%`, background: fill }}
                      />
                    </span>
                    <span className="text-right font-mono text-sm text-night-ink">{result.seconds}s</span>
                    <span>cost</span>
                    <span className="h-2.5 rounded-full bg-white/10">
                      <span
                        className="block h-full rounded-full"
                        style={{ width: `${((result.cost ?? 0) / maxCost) * 100}%`, background: fill }}
                      />
                    </span>
                    <span className="text-right font-mono text-sm text-night-ink">${result.cost}</span>
                  </div>
                  {result.note ? <p className="mt-1 text-xs text-night-mute">{result.note}</p> : null}
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-xs text-night-mute">Wall time per success and cost, linear. Shorter is better.</p>

          <div className="mt-8 border-t border-white/15 pt-4">
            <div className="flex items-baseline justify-between text-sm">
              <span>Claude spend</span>
              <span className="font-mono">
                about ${spend.used} of ${spend.cap}
              </span>
            </div>
            <div className="relative mt-2 h-2.5 rounded-full bg-white/10">
              <span
                className="block h-full rounded-full bg-night-ink"
                style={{ width: `${(spend.used / spend.cap) * 100}%` }}
              />
              <span
                aria-hidden
                className="absolute -top-1 -bottom-1 w-0.5 bg-[#ff8a9a]"
                style={{ left: `${(spend.abortAt / spend.cap) * 100}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs text-night-mute">Scripts abort at ${spend.abortAt}, marked in red.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
