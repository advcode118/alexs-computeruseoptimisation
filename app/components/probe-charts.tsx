"use client";

import { Component } from "react";
import { armMeta, ownerLabel, type ArmId, type ArmResult, type Probe } from "@/data/progress";

type Metric = "seconds" | "success" | "cost";
type Grouping = "probe" | "arm";

type Props = {
  probes: Probe[];
};

type State = {
  metric: Metric;
  grouping: Grouping;
};

const metrics: { id: Metric; label: string; scale: string }[] = [
  { id: "seconds", label: "Wall time per success", scale: "Log scale, 1s to 500s. Shorter is better." },
  { id: "success", label: "Success", scale: "Tasks passed out of 3. Longer is better." },
  { id: "cost", label: "Cost", scale: "Log scale, $0.01 to $2, as logged. Shorter is better." },
];

const armOrder: ArmId[] = ["playwright_mcp", "script_first", "stagehand", "diff_fast_act", "macro_replay"];

function width(metric: Metric, result: ArmResult): number | null {
  if (metric === "success") {
    return (result.successes / result.tasks) * 100;
  }
  if (metric === "seconds") {
    if (result.seconds === undefined) return null;
    return Math.max(2, (Math.log10(result.seconds) / Math.log10(500)) * 100);
  }
  if (result.cost === undefined) return null;
  return Math.max(2, (Math.log10(result.cost / 0.01) / Math.log10(200)) * 100);
}

function valueText(metric: Metric, result: ArmResult): string {
  if (metric === "success") return `${result.successes}/${result.tasks}`;
  if (metric === "seconds") {
    if (result.seconds !== undefined) return `${result.seconds}s`;
    return result.successes === 0 ? "no success" : "not logged";
  }
  if (result.cost !== undefined) return `$${result.cost.toFixed(3).replace(/0$/, "")}`;
  return "not logged";
}

const ticks: Record<Exclude<Metric, "success">, { at: number; label: string }[]> = {
  seconds: [1, 10, 100].map((value) => ({ at: (Math.log10(value) / Math.log10(500)) * 100, label: `${value}s` })),
  cost: [0.01, 0.1, 1].map((value) => ({
    at: (Math.log10(value / 0.01) / Math.log10(200)) * 100,
    label: `$${value}`,
  })),
};

export default class ProbeCharts extends Component<Props, State> {
  state: State = { metric: "seconds", grouping: "probe" };

  groups() {
    const { probes } = this.props;

    if (this.state.grouping === "probe") {
      return probes.map((probe) => ({
        key: probe.id,
        title: probe.label,
        caption: probe.model,
        rows: [...probe.results]
          .sort((a, b) => armOrder.indexOf(a.arm) - armOrder.indexOf(b.arm))
          .map((result) => ({ key: result.arm, label: armMeta[result.arm].short, color: armMeta[result.arm].color, result })),
      }));
    }

    return armOrder.map((arm) => ({
      key: arm,
      title: armMeta[arm].name,
      caption: ownerLabel[armMeta[arm].owner],
      rows: probes.flatMap((probe) => {
        const result = probe.results.find((item) => item.arm === arm);
        return result ? [{ key: probe.id, label: probe.label, color: armMeta[arm].color, result }] : [];
      }),
    }));
  }

  render() {
    const { metric, grouping } = this.state;
    const active = metrics.find((item) => item.id === metric)!;

    return (
      <div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div role="group" aria-label="Measure" className="flex flex-wrap gap-2">
            {metrics.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={metric === item.id}
                onClick={() => this.setState({ metric: item.id })}
                className={`rounded-full border px-4 py-2 text-sm font-semibold ${
                  metric === item.id ? "border-ink bg-ink text-sheet" : "border-rule bg-sheet text-ink hover:border-ink"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div role="group" aria-label="Group by" className="flex items-center gap-1 rounded-full border border-rule bg-sheet p-1">
            {(["probe", "arm"] as Grouping[]).map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={grouping === option}
                onClick={() => this.setState({ grouping: option })}
                className={`rounded-full px-3 py-1 font-mono text-xs ${
                  grouping === option ? "bg-night text-night-ink" : "text-mute hover:text-ink"
                }`}
              >
                By {option}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-3 text-sm text-mute">{active.scale}</p>

        <div className="mt-6 grid gap-x-10 gap-y-8 md:grid-cols-2">
          {this.groups().map((group) => (
            <figure key={group.key} className="min-w-0">
              <figcaption className="flex items-baseline justify-between gap-3 border-b-2 border-ink pb-1.5">
                <span
                  className={`font-display text-xl font-semibold tracking-tight ${
                    group.key === "script_first" ? "text-[var(--color-yours)]" : ""
                  }`}
                >
                  {group.title}
                </span>
                <span className="truncate font-mono text-xs text-mute">{group.caption}</span>
              </figcaption>
              <div className="relative mt-2">
                {metric !== "success"
                  ? ticks[metric].map((tick) => (
                      <span
                        key={tick.label}
                        aria-hidden
                        className="absolute top-0 bottom-0 border-l border-dashed border-rule"
                        style={{ left: `calc(9.5rem + (100% - 9.5rem - 6.5rem) * ${tick.at / 100})` }}
                      />
                    ))
                  : null}
                <ul className="relative">
                  {group.rows.map((row) => {
                    const bar = width(metric, row.result);
                    const measured = bar !== null;

                    return (
                      <li key={row.key} className="grid grid-cols-[9.5rem_minmax(0,1fr)_6.5rem] items-center py-1.5">
                        <span className="min-w-0 pr-2 font-mono text-xs">
                          <span
                            className={`block truncate ${
                              armMeta[row.result.arm].owner === "yours" ? "font-bold text-[var(--color-yours)]" : "text-mute"
                            }`}
                          >
                            {armMeta[row.result.arm].owner === "yours" && grouping === "probe" ? "Yours: " : ""}
                            {row.label}
                          </span>
                          {row.result.note ? (
                            <span className="block truncate font-sans text-[11px] text-mute">{row.result.note}</span>
                          ) : null}
                        </span>
                        <span className="h-5 rounded-sm bg-rule/40">
                          {measured ? (
                            <span
                              className="bar-grow block h-full rounded-sm"
                              style={{ width: `${bar}%`, background: row.color }}
                            />
                          ) : null}
                        </span>
                        <span
                          className={`pl-2 text-right font-mono tabular-nums ${
                            measured ? "text-sm font-bold" : "text-xs text-mute"
                          }`}
                        >
                          {valueText(metric, row.result)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                {metric !== "success" ? (
                  <div aria-hidden className="relative mr-[6.5rem] ml-[9.5rem] h-4 font-mono text-[10px] text-mute">
                    {ticks[metric].map((tick) => (
                      <span key={tick.label} className="absolute -translate-x-1/2" style={{ left: `${tick.at}%` }}>
                        {tick.label}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </figure>
          ))}
        </div>
      </div>
    );
  }
}
