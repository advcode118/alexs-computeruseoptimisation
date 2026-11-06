import { progress } from "@/data/progress";

const points = [
  { x: 160, y: 46 },
  { x: 274, y: 160 },
  { x: 160, y: 274 },
  { x: 46, y: 160 },
];

const arcs = [
  "M 196 52 A 114 114 0 0 1 268 124",
  "M 268 196 A 114 114 0 0 1 196 268",
  "M 124 268 A 114 114 0 0 1 52 196",
  "M 52 124 A 114 114 0 0 1 124 52",
];

function LoopDiagram() {
  return (
    <svg viewBox="0 0 320 320" role="img" aria-labelledby="loop-svg-title" className="mx-auto w-full max-w-sm">
      <title id="loop-svg-title">Observe, decide, act, assert, then observe again.</title>
      <defs>
        <marker id="loop-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--color-ink)" />
        </marker>
      </defs>
      <circle cx="160" cy="160" r="114" fill="none" stroke="var(--color-rule)" strokeWidth="18" />
      {arcs.map((d) => (
        <path key={d} d={d} fill="none" stroke="var(--color-ink)" strokeWidth="2.5" markerEnd="url(#loop-arrow)" />
      ))}
      {progress.loop.stages.map((stage, index) => {
        const point = points[index];
        const decide = stage.id === "decide";

        return (
          <g key={stage.id}>
            <circle
              cx={point.x}
              cy={point.y}
              r="38"
              fill={decide ? "var(--color-night)" : "var(--color-sheet)"}
              stroke="var(--color-ink)"
              strokeWidth="2.5"
            />
            <text
              x={point.x}
              y={point.y + 5}
              textAnchor="middle"
              fontSize="15"
              fontWeight="700"
              className="font-display"
              fill={decide ? "var(--color-night-ink)" : "var(--color-ink)"}
            >
              {stage.title}
            </text>
          </g>
        );
      })}
      <text x="160" y="154" textAnchor="middle" fontSize="12" fill="var(--color-mute)" className="font-mono">
        cheapest tier
      </text>
      <text x="160" y="172" textAnchor="middle" fontSize="12" fill="var(--color-mute)" className="font-mono">
        that can decide
      </text>
    </svg>
  );
}

export default function LoopPathway() {
  const { loop, pathway } = progress;

  return (
    <>
      <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-center lg:gap-16">
        <LoopDiagram />
        <div>
          <ol className="divide-y divide-rule border-y border-rule">
            {loop.stages.map((stage, index) => (
              <li key={stage.id} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-3 py-3">
                <span className="font-mono text-sm text-mute">{index + 1}</span>
                <div>
                  <p className="font-display text-lg font-bold">{stage.title}</p>
                  <p className="text-mute">{stage.detail}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-6 font-display font-semibold">Decide, cheapest first</p>
          <ul className="mt-2 grid gap-2 sm:grid-cols-3">
            {loop.tiers.map((tier, index) => (
              <li key={tier.name} className="border-t-4 pt-2" style={{ borderColor: `rgba(19, 34, 74, ${0.3 + index * 0.35})` }}>
                <p className="font-mono text-sm font-bold">{tier.name}</p>
                <p className="text-sm leading-snug text-mute">{tier.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <article aria-labelledby="pathway-title" className="mt-16 border-t-2 border-ink pt-8">
        <h3 id="pathway-title" className="font-display text-3xl font-bold tracking-tight">
          Pathway
        </h3>
        <p className="mt-3 max-w-3xl text-xl leading-relaxed">{pathway.intro}</p>
        <div className="mt-8 grid gap-x-12 gap-y-8 md:grid-cols-2">
          {pathway.sections.map((section) => (
            <section key={section.title}>
              <h4 className="font-display text-xl font-bold">{section.title}</h4>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph} className="mt-2 leading-relaxed text-mute">
                  {paragraph}
                </p>
              ))}
            </section>
          ))}
        </div>
      </article>
    </>
  );
}
