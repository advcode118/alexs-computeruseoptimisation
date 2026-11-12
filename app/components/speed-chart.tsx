import { armInfo, armOrder, measured, modelLabel, seconds, type ArmId } from "@/data/format";

type Run = (typeof measured.heldOut)[number];

const width = 720;
const height = 420;
const pad = { l: 58, r: 148, t: 28, b: 48 };

const nudge: Record<string, { dx: number; dy: number }> = {
  "gpt-6-luna:script_first": { dx: 12, dy: 4 },
  "gpt-6-luna:playwright_mcp": { dx: 12, dy: 16 },
  "gpt-6-luna:browser_use": { dx: 12, dy: 4 },
  "gpt-6.1-sol:script_first": { dx: 12, dy: -8 },
  "gpt-6.1-sol:playwright_mcp": { dx: 12, dy: 16 },
  "gpt-6.1-sol:browser_use": { dx: 12, dy: -10 },
};

export default function SpeedChart({ runs }: { runs: Run[] }) {
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const maxSeconds = 24;
  const xOf = (value: number) => pad.l + (value / maxSeconds) * plotW;
  const yOf = (passes: number) => pad.t + (1 - passes / 50) * plotH;
  const points = runs.flatMap((run) =>
    armOrder.map((arm) => {
      const row = run.arms[arm];
      return {
        key: `${run.model}:${arm}`,
        model: run.model,
        arm,
        pass: row.pass,
        median: row.all.medianS,
        x: xOf(row.all.medianS),
        y: yOf(row.pass),
      };
    }),
  );

  return (
    <figure className="overflow-hidden rounded-lg border border-rule bg-sheet">
      <figcaption className="px-4 pt-4 sm:px-5">
        <span className="block font-display text-lg font-bold">Pass count against median wall time</span>
        <span className="mt-1 block text-sm text-mute">
          Each point is one model and one arm on all 50 tasks. Further up passed more tasks. Further left has a lower median
          wall time. The median is every task, passes and misses together.
        </span>
      </figcaption>
      <div className="px-2 pb-2 sm:px-4">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-labelledby="speed-title speed-desc"
          className="h-auto w-full"
        >
          <title id="speed-title">Pass count against median wall time for both models</title>
          <desc id="speed-desc">
            {points
              .map(
                (point) =>
                  `${modelLabel(point.model)} ${armInfo[point.arm].name} passed ${point.pass} of 50 with a median of ${seconds(point.median)} on all tasks`,
              )
              .join(". ")}
            .
          </desc>
          {[0, 10, 20, 30, 40, 50].map((tick) => (
            <g key={tick}>
              <line
                x1={pad.l}
                x2={width - pad.r}
                y1={yOf(tick)}
                y2={yOf(tick)}
                stroke="var(--color-rule)"
                strokeWidth="1"
              />
              <text x={pad.l - 10} y={yOf(tick) + 4} textAnchor="end" fill="currentColor" fontSize="12" className="font-mono">
                {tick}
              </text>
            </g>
          ))}
          {[0, 6, 12, 18, 24].map((tick) => (
            <text
              key={tick}
              x={xOf(tick)}
              y={height - 16}
              textAnchor="middle"
              fill="currentColor"
              fontSize="12"
              className="font-mono"
            >
              {tick}s
            </text>
          ))}
          <text x={16} y={pad.t + plotH / 2} fill="currentColor" fontSize="12" transform={`rotate(-90 16 ${pad.t + plotH / 2})`} textAnchor="middle">
            Tasks passed
          </text>
          <text x={pad.l + plotW / 2} y={height - 2} fill="currentColor" fontSize="12" textAnchor="middle">
            Median seconds, all 50 tasks
          </text>
          {points.map((point) => {
            const shift = nudge[point.key] ?? { dx: 12, dy: 4 };
            const square = point.model === "gpt-6.1-sol";
            return (
              <g key={point.key}>
                {square ? (
                  <rect
                    x={point.x - 6}
                    y={point.y - 6}
                    width="12"
                    height="12"
                    fill={armInfo[point.arm].color}
                    stroke="var(--color-ink)"
                    strokeWidth="1"
                  >
                    <title>
                      {modelLabel(point.model)} {armInfo[point.arm].name}: {point.pass}/50, median {seconds(point.median)} on all tasks
                    </title>
                  </rect>
                ) : (
                  <circle cx={point.x} cy={point.y} r="6" fill={armInfo[point.arm].color} stroke="var(--color-ink)" strokeWidth="1">
                    <title>
                      {modelLabel(point.model)} {armInfo[point.arm].name}: {point.pass}/50, median {seconds(point.median)} on all tasks
                    </title>
                  </circle>
                )}
                <text x={point.x + shift.dx} y={point.y + shift.dy} fill="currentColor" fontSize="12" className="font-sans">
                  {point.model === "gpt-6-luna" ? "Luna" : "Sol"} {armInfo[point.arm as ArmId].name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-2 px-4 pb-4 text-sm sm:px-5" aria-label="Chart legend">
        {armOrder.map((arm) => (
          <li key={arm} className="flex items-center gap-2">
            <span aria-hidden className="inline-block size-3 rounded-sm" style={{ background: armInfo[arm].color }} />
            {armInfo[arm].name}
          </li>
        ))}
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block size-3 rounded-full border border-ink bg-ink" />
          Circle, gpt-6-luna
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block size-3 border border-ink bg-ink" />
          Square, gpt-6.1-sol
        </li>
      </ul>
    </figure>
  );
}
