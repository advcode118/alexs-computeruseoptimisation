"use client";

import { Component, createRef } from "react";
import {
  armMeta,
  type DemoArm,
  type DemoLane,
  type DemoStep,
  type Probe,
  type ProbeId,
} from "@/data/progress";

const lanes: { id: DemoLane; label: string }[] = [
  { id: "model", label: "Model" },
  { id: "tool", label: "Tool layer" },
  { id: "browser", label: "Chrome" },
  { id: "check", label: "Check" },
];

const laneColumn: Record<DemoLane, string> = {
  model: "md:col-start-1",
  tool: "md:col-start-2",
  browser: "md:col-start-3",
  check: "md:col-start-4",
};

type Props = {
  demos: DemoArm[];
  probes: Probe[];
  tasks: string[];
};

type State = {
  demoIndex: number;
  shown: number;
  playing: boolean;
  showRepair: boolean;
  probeId: ProbeId;
};

function probesFor(demo: DemoArm, probes: Probe[]) {
  return probes.filter((probe) => probe.results.some((result) => demo.arms.includes(result.arm)));
}

function latestProbe(demo: DemoArm, probes: Probe[]): ProbeId {
  const options = probesFor(demo, probes);
  return options[options.length - 1].id;
}

export default class RunDemo extends Component<Props, State> {
  private timer: ReturnType<typeof setInterval> | null = null;
  private reducedMotion = false;
  private list = createRef<HTMLOListElement>();

  constructor(props: Props) {
    super(props);
    this.state = {
      demoIndex: 0,
      shown: 1,
      playing: false,
      showRepair: true,
      probeId: latestProbe(props.demos[0], props.probes),
    };
  }

  componentDidMount() {
    this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  componentDidUpdate(_props: Props, previous: State) {
    if (this.state.shown > previous.shown && this.state.demoIndex === previous.demoIndex) {
      const latest = this.list.current?.lastElementChild;
      if (latest && latest.getBoundingClientRect().bottom > window.innerHeight) {
        latest.scrollIntoView({ block: "nearest", behavior: this.reducedMotion ? "auto" : "smooth" });
      }
    }
  }

  componentWillUnmount() {
    this.stopTimer();
  }

  steps(): DemoStep[] {
    const demo = this.props.demos[this.state.demoIndex];
    return demo.steps.filter((step) => this.state.showRepair || step.branch !== "repair");
  }

  stopTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  selectDemo(index: number) {
    this.stopTimer();
    this.setState({
      demoIndex: index,
      shown: 1,
      playing: false,
      probeId: latestProbe(this.props.demos[index], this.props.probes),
    });
  }

  step(delta: number) {
    const total = this.steps().length;
    this.setState((state) => ({ shown: Math.min(total, Math.max(1, state.shown + delta)) }));
  }

  reset() {
    this.stopTimer();
    this.setState({ shown: 1, playing: false });
  }

  togglePlay() {
    if (this.state.playing) {
      this.stopTimer();
      this.setState({ playing: false });
      return;
    }

    const total = this.steps().length;
    this.setState((state) => ({ playing: true, shown: state.shown >= total ? 1 : state.shown }));
    this.timer = setInterval(
      () => {
        const last = this.steps().length;
        if (this.state.shown >= last) {
          this.stopTimer();
          this.setState({ playing: false });
          return;
        }
        this.setState((state) => ({ shown: state.shown + 1 }));
      },
      this.reducedMotion ? 1600 : 1100,
    );
  }

  render() {
    const { demos, probes, tasks } = this.props;
    const { demoIndex, shown, playing, showRepair, probeId } = this.state;
    const demo = demos[demoIndex];
    const steps = this.steps();
    const visible = steps.slice(0, shown);
    const counts = {
      model: visible.filter((step) => step.counts === "model").length,
      browser: visible.filter((step) => step.counts === "browser").length,
      repair: visible.filter((step) => step.counts === "repair").length,
    };
    const probeOptions = probesFor(demo, probes);
    const probe = probeOptions.find((option) => option.id === probeId) ?? probeOptions[probeOptions.length - 1];
    const results = probe.results.filter((result) => demo.arms.includes(result.arm));
    const current = steps[shown - 1];
    const accent = armMeta[demo.arms[0]].color;

    return (
      <div className="border-y-2 border-ink bg-sheet">
        <div role="group" aria-label="Choose how the task runs" className="flex overflow-x-auto border-b border-rule">
          {demos.map((option, index) => {
            const active = index === demoIndex;

            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={active}
                onClick={() => this.selectDemo(index)}
                className={`flex shrink-0 items-center gap-2 border-b-4 px-4 py-3 text-left font-display text-lg font-semibold tracking-tight sm:px-6 ${
                  active ? "text-ink" : "border-transparent text-mute hover:text-ink"
                }`}
                style={active ? { borderColor: armMeta[option.arms[0]].color } : undefined}
              >
                <span aria-hidden className="size-2.5 rounded-full" style={{ background: armMeta[option.arms[0]].color }} />
                {option.name}
              </button>
            );
          })}
        </div>

        <div className="grid gap-8 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_17rem] lg:gap-10">
          <div className="min-w-0">
            <p className="max-w-2xl text-lg leading-snug">{demo.oneLine}</p>
            <p className="mt-1 text-sm text-mute">
              Probe tasks: {tasks.join(", ")}. The walk-through shows the shape of one task, not a timed trace.
            </p>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => this.togglePlay()}
                className="min-w-24 rounded-full bg-ink px-5 py-2 font-mono text-sm font-medium text-sheet hover:bg-night"
              >
                {playing ? "Pause" : "Play"}
              </button>
              <button
                type="button"
                onClick={() => this.step(-1)}
                disabled={shown <= 1}
                className="rounded-full border border-ink px-4 py-2 font-mono text-sm disabled:opacity-35"
              >
                Back
              </button>
              <button
                type="button"
                onClick={() => this.step(1)}
                disabled={shown >= steps.length}
                className="rounded-full border border-ink px-4 py-2 font-mono text-sm disabled:opacity-35"
              >
                Step
              </button>
              <button
                type="button"
                onClick={() => this.reset()}
                className="rounded-full px-3 py-2 font-mono text-sm text-mute underline-offset-4 hover:underline"
              >
                Reset
              </button>
              {demo.steps.some((step) => step.branch === "repair") ? (
                <label className="ml-auto flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={showRepair}
                    onChange={(event) => {
                      const next = event.target.checked;
                      this.setState((state) => ({
                        showRepair: next,
                        shown: Math.min(state.shown, demo.steps.filter((step) => next || step.branch !== "repair").length),
                      }));
                    }}
                    className="size-4 accent-[var(--color-arm-script)]"
                  />
                  The first check fails
                </label>
              ) : null}
            </div>

            {current ? (
              <div
                aria-live="polite"
                className="mt-5 min-h-[5.5rem] rounded-md border-l-[5px] bg-white px-4 py-3"
                style={{ borderColor: accent }}
              >
                <p className="font-mono text-xs text-mute">
                  Step {shown} of {steps.length} · {lanes.find((lane) => lane.id === current.lane)?.label}
                </p>
                <p className="mt-0.5 font-display text-lg leading-tight font-bold">{current.title}</p>
                <p className="mt-1 text-sm leading-snug text-mute">{current.detail}</p>
              </div>
            ) : null}

            <div className="mt-5 hidden grid-cols-4 gap-3 border-b border-rule pb-1.5 font-mono text-xs text-mute md:grid">
              {lanes.map((lane) => (
                <span key={lane.id}>{lane.label}</span>
              ))}
            </div>
            <ol ref={this.list} className="mt-2 grid gap-1.5 md:grid-cols-4 md:gap-x-3">
              {visible.map((step, index) => {
                const latest = index === visible.length - 1;

                return (
                  <li
                    key={`${demo.id}-${step.title}-${index}`}
                    className={`step-enter md:col-span-1 ${laneColumn[step.lane]} rounded-md border px-3 py-1.5 ${
                      latest ? "border-ink bg-white shadow-[0_2px_0_0_var(--color-ink)]" : "border-rule bg-white/60"
                    }`}
                    style={{ gridRow: index + 1, borderLeft: latest ? `5px solid ${accent}` : undefined }}
                  >
                    <p className="flex flex-wrap items-baseline gap-x-2 font-mono text-[11px] text-mute">
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <span className="md:hidden">{lanes.find((lane) => lane.id === step.lane)?.label}</span>
                      {step.repeats ? <span className="text-ink">repeats each page step</span> : null}
                      {step.branch === "repair" ? <span className="text-stop">only on a failed check</span> : null}
                    </p>
                    <p className="font-display text-[15px] leading-tight font-semibold">{step.title}</p>
                  </li>
                );
              })}
            </ol>
          </div>

          <aside className="min-w-0 border-t border-rule pt-6 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-8">
            <p className="font-display text-sm font-semibold">In this walk-through</p>
            <dl className="mt-3 grid grid-cols-3 gap-2 lg:grid-cols-1">
              {[
                { label: "Model calls", value: counts.model },
                { label: "Browser calls", value: counts.browser },
                { label: "Repairs", value: counts.repair },
              ].map((item) => (
                <div key={item.label} className="flex flex-col lg:flex-row lg:items-baseline lg:justify-between">
                  <dt className="text-sm text-mute">{item.label}</dt>
                  <dd className="font-mono text-3xl font-bold tabular-nums">{item.value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-xs text-mute">Steps marked as repeating run again for every page step.</p>

            <div className="mt-6 border-t border-rule pt-5">
              <label htmlFor="demo-probe" className="font-display text-sm font-semibold">
                Measured
              </label>
              <select
                id="demo-probe"
                value={probe.id}
                onChange={(event) => this.setState({ probeId: event.target.value as ProbeId })}
                className="mt-2 block w-full rounded-md border border-ink bg-white px-2 py-1.5 font-mono text-sm"
              >
                {probeOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-mute">{probe.model}</p>
              <ul className="mt-3 space-y-3">
                {results.map((result) => (
                  <li key={result.arm}>
                    <p className="font-mono text-xs text-mute">{armMeta[result.arm].short}</p>
                    <p className="font-mono text-sm">
                      <span className="text-xl font-bold">
                        {result.successes}/{result.tasks}
                      </span>
                      {result.seconds !== undefined ? ` · ${result.seconds}s per success` : ""}
                      {result.cost !== undefined ? ` · $${result.cost.toFixed(3).replace(/0$/, "")}` : ""}
                    </p>
                    {result.note ? <p className="text-xs text-mute">{result.note}</p> : null}
                  </li>
                ))}
              </ul>
            </div>

            <p className="mt-6 border-t border-rule pt-5 text-sm leading-snug">{demo.takeaway}</p>
          </aside>
        </div>
      </div>
    );
  }
}
