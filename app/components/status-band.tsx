import { armOrder, dollars, measured, seconds, type ArmId } from "@/data/format";
import { progress } from "@/data/progress";

const highlight = "var(--color-yours-bright)";

const nightFill: Record<ArmId, string> = {
  script_first: highlight,
  playwright_mcp: "rgba(223, 230, 245, 0.55)",
  browser_use: "#f0b45a",
};

export default function StatusBand() {
  const { pitch } = progress;
  const maxSeconds = Math.max(
    ...measured.heldOut.flatMap((run) => armOrder.map((arm) => run.arms[arm].all.medianS)),
  );
  const maxCost = Math.max(...measured.heldOut.flatMap((run) => armOrder.map((arm) => run.arms[arm].usd)));

  return (
    <section id="pitch" aria-labelledby="pitch-title" className="overflow-hidden bg-night text-night-ink">
      <div className="hero-out mx-auto grid max-w-6xl gap-12 px-5 pt-16 pb-20 sm:px-8 sm:pt-24 sm:pb-28 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-16">
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
          <p className="font-display text-lg font-semibold">50 held-out tasks, one cold run each</p>
          <p className="mt-1 text-sm text-night-mute">
            OpenAI medium. Median wall time of all 50 tasks. script_first had no answer key in its runtime.
          </p>
          <div className="mt-5 space-y-6">
            {measured.heldOut.map((run) => (
              <div key={run.model}>
                <p className="font-mono text-sm font-bold" style={{ color: highlight }}>
                  {run.model}
                </p>
                <div className="mt-2 space-y-3">
                  {armOrder.map((arm) => {
                    const row = run.arms[arm];
                    const fill = nightFill[arm];
                    return (
                      <div key={arm}>
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="font-mono text-sm font-bold">{arm === "script_first" ? "script_first" : arm === "playwright_mcp" ? "Playwright MCP" : "browser-use"}</span>
                          <span className="font-mono text-sm text-night-mute">
                            {row.pass}/{row.of}
                          </span>
                        </div>
                        <div className="mt-1 grid grid-cols-[3rem_minmax(0,1fr)_4.75rem] items-center gap-x-2 text-xs text-night-mute">
                          <span>time</span>
                          <span className="h-2 rounded-full bg-white/10">
                            <span
                              className="block h-full rounded-full"
                              style={{ width: `${(row.all.medianS / maxSeconds) * 100}%`, background: fill }}
                            />
                          </span>
                          <span className="text-right font-mono text-sm text-night-ink">{seconds(row.all.medianS)}</span>
                          <span>cost</span>
                          <span className="h-2 rounded-full bg-white/10">
                            <span
                              className="block h-full rounded-full"
                              style={{ width: `${(row.usd / maxCost) * 100}%`, background: fill }}
                            />
                          </span>
                          <span className="text-right font-mono text-sm text-night-ink">{dollars(row.usd)}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-6 text-sm text-night-mute">
            <a href="/stats" className="font-semibold text-night-ink underline decoration-white/30 underline-offset-4">
              Full tables, both latency populations, and the per-task rows
            </a>
          </p>
        </div>
      </div>
    </section>
  );
}
