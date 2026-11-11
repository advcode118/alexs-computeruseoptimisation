import { armOrder, arms, sonnetProbes, sweep, type StatsArm } from "@/data/stats";

/** Palette validated for dark mode (lightness band, CVD separation, contrast). Identity is also carried by shape, legend and labels. */
export const armColor: Record<StatsArm, string> = {
  script_first: "#f0508a",
  playwright_mcp: "#2c98c4",
  stagehand: "#c0841c",
  browser_use: "#9080e8",
};

const AXIS = "#9aa8c4";
const GRID = "#243049";
const SURFACE = "#111a2e";

const logPos = (v: number, min: number, max: number, a: number, b: number) =>
  a + ((Math.log10(v) - Math.log10(min)) / (Math.log10(max) - Math.log10(min))) * (b - a);

export function Legend({ shapes = false }: { shapes?: boolean }) {
  return (
    <ul aria-label="Legend" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
      {armOrder.map((arm) => (
        <li key={arm} className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-1 w-4 rounded-full" style={{ background: armColor[arm] }} />
          <span className={arm === "script_first" ? "font-semibold text-ink" : "text-mute"}>{arms[arm].name}</span>
        </li>
      ))}
      {shapes ? (
        <>
          <li className="flex items-center gap-2 text-mute">
            <svg aria-hidden width="12" height="12" viewBox="-6 -6 12 12"><circle r="5" fill="#9aa8c4" /></svg> gpt-6-luna
          </li>
          <li className="flex items-center gap-2 text-mute">
            <svg aria-hidden width="12" height="12" viewBox="-6 -6 12 12"><path d="M0-6 6 0 0 6-6 0Z" fill="#9aa8c4" /></svg> gpt-6.1-sol
          </li>
          <li className="flex items-center gap-2 text-mute">
            <svg aria-hidden width="12" height="12" viewBox="-6 -6 12 12"><path d="M-5-5 5 5M5-5-5 5" stroke="#ff8a8a" strokeWidth="2.5" /></svg> failed
          </li>
        </>
      ) : null}
    </ul>
  );
}

function ChartShell({ title, desc, children, min = 560 }: { title: string; desc: string; children: React.ReactNode; min?: number }) {
  return (
    <div role="region" aria-label={`${title} (scrolls sideways on small screens)`} tabIndex={0} className="overflow-x-auto">
      <svg role="img" aria-label={`${title}. ${desc}`} viewBox="0 0 640 380" style={{ minWidth: min }} className="block h-auto w-full">
        <rect width="640" height="380" fill={SURFACE} />
        {children}
      </svg>
    </div>
  );
}

/** Speed vs cost, one point per OpenAI sweep run. Both axes logarithmic. */
export function SpeedCostScatter() {
  const L = 64, R = 20, T = 16, B = 52;
  const x0 = L, x1 = 640 - R, y0 = 380 - B, y1 = T;
  const X = (s: number) => logPos(s, 2, 200, x0, x1);
  const Y = (c: number) => logPos(c, 0.0001, 0.02, y0, y1);
  const xt = [2, 5, 10, 20, 50, 100, 200];
  const yt = [0.0001, 0.001, 0.01];
  return (
    <ChartShell
      title="Speed against cost, effort sweep"
      desc="Each point is one run on the Wikipedia task. script_first sits at the fast, cheap corner for both models; every other arm is slower and costs several times more."
    >
      {yt.map((t) => (
        <g key={t}>
          <line x1={x0} x2={x1} y1={Y(t)} y2={Y(t)} stroke={GRID} />
          <text x={x0 - 8} y={Y(t) + 4} textAnchor="end" fontSize="12" fill={AXIS}>{`$${t}`}</text>
        </g>
      ))}
      {xt.map((t) => (
        <g key={t}>
          <line x1={X(t)} x2={X(t)} y1={y1} y2={y0} stroke={GRID} />
          <text x={X(t)} y={y0 + 18} textAnchor="middle" fontSize="12" fill={AXIS}>{`${t}s`}</text>
        </g>
      ))}
      <text x={(x0 + x1) / 2} y={372} textAnchor="middle" fontSize="12" fill={AXIS}>Wall time per run (log scale), faster is left</text>
      <text transform="rotate(-90)" x={-(y0 + y1) / 2} y={14} textAnchor="middle" fontSize="12" fill={AXIS}>Cost per run (log scale), cheaper is lower</text>
      <text x={X(2.3)} y={Y(0.00055) } fontSize="12" fontWeight="700" fill="#f0508a">script_first on Luna</text>
      <text x={X(2.3)} y={Y(0.0057)} fontSize="12" fontWeight="700" fill="#f0508a">script_first on Sol</text>
      {sweep.flatMap((row) =>
        armOrder.map((arm) => {
          const c = row.cells[arm];
          const cx = X(c.s), cy = Y(c.usd);
          const sol = row.model === "gpt-6.1-sol";
          const label = `${arms[arm].name}, ${row.model}, ${row.effort}: ${c.pass ? "passed" : "failed"}, ${c.s.toFixed(2)}s, $${c.usd.toFixed(6)}`;
          return (
            <g key={`${row.model}-${row.effort}-${arm}`} transform={`translate(${cx} ${cy})`}>
              <title>{label}</title>
              {!c.pass ? (
                <path d="M-6-6 6 6M6-6-6 6" stroke="#ff8a8a" strokeWidth="3" />
              ) : sol ? (
                <path d="M0-7 7 0 0 7-7 0Z" fill={armColor[arm]} stroke={SURFACE} strokeWidth="2" />
              ) : (
                <circle r="6" fill={armColor[arm]} stroke={SURFACE} strokeWidth="2" />
              )}
              <circle r="12" fill="transparent" />
            </g>
          );
        }),
      )}
    </ChartShell>
  );
}

/** Wall time by effort, one panel per model. Log y. */
export function EffortLines({ model }: { model: "gpt-6-luna" | "gpt-6.1-sol" }) {
  const rows = sweep.filter((r) => r.model === model);
  const L = 56, R = 24, T = 16, B = 44;
  const x0 = L, x1 = 640 - R, y0 = 380 - B, y1 = T;
  const X = (i: number) => x0 + 40 + (i * (x1 - x0 - 80)) / 3;
  const Y = (s: number) => logPos(s, 2, 200, y0, y1);
  const yt = [2, 5, 10, 20, 50, 100, 200];
  return (
    <ChartShell
      title={`Wall time by effort, ${model}`}
      desc="script_first stays near 3 to 6 seconds at every effort level. The other arms are slower, and Stagehand varies the most."
    >
      {yt.map((t) => (
        <g key={t}>
          <line x1={x0} x2={x1} y1={Y(t)} y2={Y(t)} stroke={GRID} />
          <text x={x0 - 8} y={Y(t) + 4} textAnchor="end" fontSize="12" fill={AXIS}>{`${t}s`}</text>
        </g>
      ))}
      {rows.map((r, i) => (
        <text key={r.effort} x={X(i)} y={y0 + 22} textAnchor="middle" fontSize="12" fill={AXIS}>{r.effort}</text>
      ))}
      <text x={(x0 + x1) / 2} y={372} textAnchor="middle" fontSize="12" fill={AXIS}>Reasoning effort</text>
      {armOrder.map((arm) => (
        <g key={arm}>
          <polyline
            fill="none"
            stroke={armColor[arm]}
            strokeWidth={arm === "script_first" ? 3 : 2}
            points={rows.map((r, i) => `${X(i)},${Y(r.cells[arm].s)}`).join(" ")}
          />
          {rows.map((r, i) => {
            const c = r.cells[arm];
            return (
              <g key={r.effort} transform={`translate(${X(i)} ${Y(c.s)})`}>
                <title>{`${arms[arm].name}, ${model}, ${r.effort}: ${c.pass ? "passed" : "failed"}, ${c.s.toFixed(2)}s`}</title>
                {c.pass ? <circle r="5" fill={armColor[arm]} stroke={SURFACE} strokeWidth="2" /> : <path d="M-6-6 6 6M6-6-6 6" stroke="#ff8a8a" strokeWidth="3" />}
                <circle r="12" fill="transparent" />
              </g>
            );
          })}
        </g>
      ))}
      <text x={X(0)} y={Y(rows[0].cells.script_first.s) + 22} fontSize="12" fontWeight="700" fill="#f0508a">script_first</text>
    </ChartShell>
  );
}

/** Median wall time on the 18-task set, grouped by probe. */
export function SonnetGroups() {
  const probes = [...sonnetProbes].reverse(); // PR #18, #23, #27
  const L = 48, R = 16, T = 24, B = 56;
  const x0 = L, x1 = 640 - R, y0 = 380 - B, y1 = T;
  const max = 8;
  const Y = (v: number) => y0 - (v / max) * (y0 - y1);
  const groupW = (x1 - x0) / probes.length;
  const barW = 28, gap = 4;
  return (
    <ChartShell
      title="Median time per success, three Sonnet probes"
      desc="script_first has the lowest median in all three probes. PR #18 used uneven grading and is shown for history."
    >
      {[0, 2, 4, 6, 8].map((t) => (
        <g key={t}>
          <line x1={x0} x2={x1} y1={Y(t)} y2={Y(t)} stroke={GRID} />
          <text x={x0 - 8} y={Y(t) + 4} textAnchor="end" fontSize="12" fill={AXIS}>{`${t}s`}</text>
        </g>
      ))}
      {probes.map((p, gi) => {
        const total = armOrder.length * barW + (armOrder.length - 1) * gap;
        const gx = x0 + gi * groupW + (groupW - total) / 2;
        return (
          <g key={p.id}>
            {armOrder.map((arm, ai) => {
              const row = p.rows.find((r) => r.arm === arm)!;
              const h = y0 - Y(row.median);
              const x = gx + ai * (barW + gap);
              return (
                <g key={arm}>
                  <title>{`${p.title}, ${arms[arm].name}: ${row.pass}/${row.of}, median ${row.median.toFixed(2)}s`}</title>
                  <path d={`M${x} ${y0}V${y0 - h + 4}a4 4 0 0 1 4-4h${barW - 8}a4 4 0 0 1 4 4V${y0}Z`} fill={armColor[arm]} />
                  {arm === "script_first" ? (
                    <text x={x + barW / 2} y={y0 - h - 6} textAnchor="middle" fontSize="12" fontWeight="700" fill="#ff8db3">{row.median.toFixed(2)}</text>
                  ) : null}
                </g>
              );
            })}
            <text x={x0 + gi * groupW + groupW / 2} y={y0 + 20} textAnchor="middle" fontSize="12" fill={AXIS}>
              {p.title.split(" ").slice(0, 2).join(" ")}
              {p.fair ? "" : " (history)"}
            </text>
          </g>
        );
      })}
      <line x1={x0} x2={x1} y1={y0} y2={y0} stroke={AXIS} />
    </ChartShell>
  );
}

/** Pass/fail matrix for the two 3-task medium runs: shape and text, not just colour. */
export function ChartLegendBlock({ shapes = false }: { shapes?: boolean }) {
  return <Legend shapes={shapes} />;
}
