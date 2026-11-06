import { progress } from "@/data/progress";

export default function PitchSteps() {
  const { pitch } = progress;

  return (
    <section aria-labelledby="works" className="border-b border-rule">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:gap-16">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <p className="font-mono text-sm font-bold text-[var(--color-yours)]">How it works</p>
          <h2 id="works" className="mt-3 font-display text-4xl leading-[1.02] font-bold tracking-[-0.03em] text-balance sm:text-5xl">
            Write once, run, check.
          </h2>
          <p className="mt-4 max-w-md text-lg leading-relaxed text-mute">
            Other arms ask a model at every page step. script_first asks once for the whole task.
          </p>
          <p className="mt-4 text-sm text-mute">{pitch.stepsNote}</p>
        </div>

        <ol className="space-y-6 lg:space-y-[28vh] lg:py-[8vh]">
          {pitch.steps.map((step, index) => (
            <li key={step.title} className="spotlight grid grid-cols-[3.5rem_minmax(0,1fr)] gap-4 sm:grid-cols-[5rem_minmax(0,1fr)]">
              <span className="font-display text-5xl leading-none font-bold text-[var(--color-yours)] sm:text-7xl">
                {index + 1}
              </span>
              <div className="border-t-2 border-ink pt-3">
                <h3 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">{step.title}</h3>
                <p className="mt-2 max-w-lg text-lg leading-relaxed text-mute">{step.body}</p>
                <p className="mt-3 inline-block rounded-full bg-[var(--color-yours-soft)] px-3 py-1 font-mono text-sm font-bold text-[var(--color-yours)]">
                  {step.tag}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
