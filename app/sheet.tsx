"use client";

import { useEffect, useId, useState } from "react";
import {
  GROUPS,
  PARTS,
  PROPOSAL,
  ROUTES,
  TRUTHS,
  WAYS,
  defaultMark,
  findings,
  kindLabel,
  lanesFor,
  partBody,
  scaleFor,
  sum,
  type Lane,
  type Mark,
  type Part,
  type Surface,
} from "@/data/loop";

const NAV = [
  { href: "#clock", label: "Clock" },
  { href: "#routes", label: "Routes" },
  { href: "#ways", label: "Ways" },
  { href: "#gaps", label: "Gaps" },
];

const STORAGE_KEY = "cuo-sheet-v1";

function freshMarks() {
  return Object.fromEntries(PARTS.map((part) => [part.id, defaultMark(part)])) as Record<string, Mark>;
}

function loadMarks() {
  const marks = freshMarks();
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "");
    for (const part of PARTS) {
      const value = saved.marks?.[part.id];
      if (value === "keep" || value === "later" || value === "cut") marks[part.id] = value;
    }
  } catch {
    /* a private window can refuse storage */
  }
  return marks;
}

function readOpen() {
  return new URLSearchParams(window.location.search).get("open");
}

export function Sheet() {
  const [surface, setSurface] = useState<Surface>("browser");
  const [marks, setMarks] = useState<Record<string, Mark>>(freshMarks);
  const [open, setOpen] = useState<string | null>(null);
  const titleId = useId();

  useEffect(() => {
    setMarks(loadMarks());
    setOpen(readOpen());
    const onPop = () => setOpen(readOpen());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    try {
      const previous = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          surface: previous.surface ?? "browser",
          filter: previous.filter ?? "all",
          notes: typeof previous.notes === "string" ? previous.notes : "",
          marks,
        }),
      );
    } catch {
      /* the sheet still works without storage */
    }
  }, [marks]);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDisplay();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function show(next: string) {
    const url = `/?open=${encodeURIComponent(next)}`;
    window.history.pushState({ open: next }, "", url);
    setOpen(next);
  }

  function closeDisplay() {
    window.history.pushState({ open: null }, "", "/");
    setOpen(null);
  }

  function setMark(id: string, mark: Mark) {
    setMarks((current) => ({ ...current, [id]: mark }));
  }

  const lanes = lanesFor(surface);

  return (
    <>
      <header className="sticky top-0 z-20 border-b border-line bg-ink/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <a href="#top" className="flex items-center gap-3">
            <span aria-hidden className="size-2.5 shrink-0 bg-amber" />
            <span className="font-mono text-[11px] tracking-[0.18em] uppercase">Computer-use optimisation</span>
          </a>
          <p className="font-mono text-[11px] tracking-[0.16em] whitespace-nowrap text-muted uppercase">
            28 October 2026
          </p>
        </div>
        <nav
          aria-label="On this page"
          className="mx-auto flex max-w-6xl gap-5 overflow-x-auto px-5 pb-3 font-mono text-[11px] tracking-[0.16em] uppercase sm:px-8"
        >
          {NAV.map((item) => (
            <a key={item.href} href={item.href} className="shrink-0 text-muted hover:text-paper">
              {item.label}
            </a>
          ))}
        </nav>
      </header>

      <main id="top" className="overflow-x-clip">
        <div className="mx-auto max-w-6xl px-5 pt-14 sm:px-8 sm:pt-20">
          <h1 className="max-w-[14ch] font-serif text-6xl leading-[0.9] tracking-[-0.03em] sm:text-7xl lg:text-8xl">
            The model looks again
            <br />
            <span className="italic">before it is willing to click.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted sm:text-xl">
            Cursor, Operator, Claude in Chrome, and the other frontier models share one loop. Picture, model,
            click, picture.
          </p>
        </div>

        <section className="mt-12 bg-amber text-amber-ink">
          <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-12">
            <p className="font-mono text-[11px] tracking-[0.22em] uppercase">The bottleneck</p>
            <h2 className="mt-4 max-w-[18ch] font-serif text-4xl leading-[1.02] tracking-[-0.03em] sm:text-6xl">
              Each step re-sees the screen and holds the pointer.
            </h2>
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-amber-muted">
              Owning the loop is the place to stand. How a step runs inside it is not settled. Click a bar, a
              route, or a way. The detail opens beside the page, and the lengths on the clock are a sketch.
            </p>
          </div>
        </section>

        <Clock lanes={lanes} surface={surface} onSurface={setSurface} onOpen={show} />
        <Routes onOpen={show} />
        <Ways onOpen={show} />
        <Gaps marks={marks} onOpen={show} />

        <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-8 font-mono text-[11px] tracking-[0.14em] text-muted uppercase sm:px-8">
          <p>Dark mode</p>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            <button type="button" className="hover:text-paper" onClick={() => show("truths")}>
              What has to stay true
            </button>
            <button type="button" className="hover:text-paper" onClick={() => show("proposal")}>
              One proposal for an order
            </button>
          </div>
        </footer>
      </main>

      {open ? (
        <div className="fixed inset-0 z-30">
          <button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-ink/70"
            onClick={closeDisplay}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            className="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col overflow-y-auto border-l border-line bg-ink outline-none"
          >
            <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-line bg-ink/95 px-5 py-4 backdrop-blur-md sm:px-8">
              <p className="font-mono text-[11px] tracking-[0.18em] text-amber uppercase">Where this comes from</p>
              <button
                type="button"
                onClick={closeDisplay}
                className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase hover:text-paper"
              >
                Close
              </button>
            </div>
            <div className="px-5 py-8 sm:px-8">
              <Display
                open={open}
                titleId={titleId}
                surface={surface}
                marks={marks}
                lanes={lanes}
                onOpen={show}
                onMark={setMark}
              />
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

function Clock({
  lanes,
  surface,
  onSurface,
  onOpen,
}: {
  lanes: Lane[];
  surface: Surface;
  onSurface: (surface: Surface) => void;
  onOpen: (id: string) => void;
}) {
  const scale = scaleFor(lanes);

  return (
    <section id="clock" aria-labelledby="clock-title" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
        <div>
          <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">The clock</p>
          <h2 id="clock-title" className="mt-3 font-serif text-5xl tracking-[-0.03em] sm:text-6xl">
            One invoice export.
          </h2>
        </div>
        <div className="font-mono text-[11px] tracking-[0.16em] uppercase">
          <p className="mb-2 text-muted">First build acts on</p>
          <div className="flex gap-4">
            {(
              [
                ["browser", "Browser"],
                ["windows", "Windows desktop"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={surface === value}
                onClick={() => onSurface(value)}
                className={
                  surface === value
                    ? "text-paper underline decoration-amber decoration-2 underline-offset-4"
                    : "text-muted hover:text-paper"
                }
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-6 max-w-2xl text-muted">
        Export last month’s invoices, from a logged-in billing page. Click a bar to see what it is. These
        lengths are a sketch, not a measurement on this machine.
      </p>

      <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2 font-mono text-[11px] tracking-[0.14em] uppercase">
        <li className="flex items-center gap-2">
          <span aria-hidden className="size-2.5 bg-gap" />
          Model call
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="size-2.5 bg-paper" />
          Acting
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="size-2.5 border border-paper" />
          Page settling
        </li>
      </ul>

      <div className="mt-8 overflow-x-auto">
        <div className="min-w-[40rem]">
          {lanes.map((lane) => {
            const total = sum(lane.segments);
            const owned = lane.id === "owned";
            let cursor = 0;
            return (
              <div
                key={lane.id}
                className={`grid items-center gap-x-6 gap-y-3 border-t border-line py-5 lg:grid-cols-[16rem_minmax(0,1fr)] ${
                  owned ? "shadow-[inset_3px_0_0_0_var(--color-lime)]" : ""
                }`}
              >
                <button type="button" onClick={() => onOpen(`lane:${lane.id}`)} className="text-left">
                  <p className="font-serif text-2xl tracking-[-0.02em]">{lane.title}</p>
                  <p className={`mt-1 font-mono text-sm tracking-[0.12em] ${owned ? "text-lime" : "text-amber"}`}>
                    {Math.round(total)}s
                  </p>
                </button>
                <div className="relative h-10 bg-[#191813]">
                  {lane.segments.map((seg, index) => {
                    const left = (cursor / scale) * 100;
                    const width = Math.max((seg.s / scale) * 100, 0.9);
                    cursor += seg.s;
                    const label = `${seg.name}, ${kindLabel(seg.kind)}, ${seg.s.toFixed(1)} seconds`;
                    return (
                      <button
                        key={`${lane.id}-${index}`}
                        type="button"
                        title={label}
                        aria-label={label}
                        onClick={() => onOpen(`seg:${lane.id}:${index}`)}
                        className={`absolute inset-y-0 overflow-hidden text-left font-mono text-[11px] tracking-[0.08em] uppercase ${
                          seg.kind === "model"
                            ? "bg-gap text-amber-ink"
                            : seg.kind === "act"
                              ? "bg-paper"
                              : "border border-paper/80"
                        }`}
                        style={{ left: `${left}%`, width: `${width}%` }}
                      >
                        {seg.kind === "model" && seg.s >= 4 ? <span className="px-1.5">{seg.name}</span> : null}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div className="grid border-t border-line lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-x-6">
            <div className="hidden lg:block" />
            <div className="relative h-6">
              {Array.from({ length: scale / 10 + 1 }, (_, index) => index * 10).map((tick) => (
                <span
                  key={tick}
                  className="absolute top-1 font-mono text-[11px] text-muted"
                  style={{
                    left: `${(tick / scale) * 100}%`,
                    transform: tick === 0 ? undefined : tick === scale ? "translateX(-100%)" : "translateX(-50%)",
                  }}
                >
                  {tick}s
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Routes({ onOpen }: { onOpen: (id: string) => void }) {
  return (
    <section id="routes" aria-labelledby="routes-title" className="mx-auto max-w-6xl px-5 pb-16 sm:px-8 sm:pb-24">
      <SectionHead kicker="Three places to stand" title="Same task, three owners of the clock." titleId="routes-title" />
      <ol>
        {ROUTES.map((route, index) => (
          <li key={route.id}>
            <Row
              index={index + 1}
              title={route.title}
              summary={route.home}
              live={Boolean(route.place)}
              mark={route.place}
              onClick={() => onOpen(`route:${route.id}`)}
            />
          </li>
        ))}
      </ol>
    </section>
  );
}

function Ways({ onOpen }: { onOpen: (id: string) => void }) {
  return (
    <section id="ways" aria-labelledby="ways-title" className="mx-auto max-w-6xl px-5 pb-16 sm:px-8 sm:pb-24">
      <SectionHead
        kicker="Shape 1"
        title="Ways to run the owned loop."
        titleId="ways-title"
        aside="None settled"
      />
      <ol>
        {WAYS.map((way, index) => (
          <li key={way.id}>
            <Row index={index + 1} title={way.title} summary={way.home} onClick={() => onOpen(`way:${way.id}`)} />
          </li>
        ))}
      </ol>
    </section>
  );
}

function Gaps({ marks, onOpen }: { marks: Record<string, Mark>; onOpen: (id: string) => void }) {
  const kept = PARTS.filter((part) => marks[part.id] === "keep").length;
  return (
    <section id="gaps" aria-labelledby="gaps-title" className="border-t-4 border-gap bg-[#191813]">
      <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
        <SectionHead kicker="Gaps" title="What the machine still needs." titleId="gaps-title" aside={`${kept} marked keep`} />
        <ol>
          {GROUPS.map((group, index) => {
            const count = PARTS.filter((part) => part.group === group.id).length;
            return (
              <li key={group.id}>
                <Row
                  index={index + 1}
                  title={group.title}
                  summary={`${count} parts`}
                  onClick={() => onOpen(`group:${group.id}`)}
                />
              </li>
            );
          })}
        </ol>
        <button
          type="button"
          onClick={() => onOpen("build")}
          className="mt-8 font-mono text-[11px] tracking-[0.16em] text-gap uppercase hover:text-paper"
        >
          The build you marked
        </button>
      </div>
    </section>
  );
}

function SectionHead({
  kicker,
  title,
  titleId,
  aside,
}: {
  kicker: string;
  title: string;
  titleId: string;
  aside?: string;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
      <div>
        <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">{kicker}</p>
        <h2 id={titleId} className="mt-3 max-w-[16ch] font-serif text-5xl tracking-[-0.03em] sm:text-6xl">
          {title}
        </h2>
      </div>
      {aside ? <p className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase">{aside}</p> : null}
    </div>
  );
}

function Row({
  index,
  title,
  summary,
  live,
  mark,
  onClick,
}: {
  index: number;
  title: string;
  summary: string;
  live?: boolean;
  mark?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`grid w-full grid-cols-[3.25rem_minmax(0,1fr)] items-baseline gap-x-4 gap-y-1 border-b border-line py-6 text-left lg:grid-cols-[4.5rem_minmax(0,1.15fr)_max-content_minmax(0,1fr)] lg:gap-x-8 ${
        live ? "shadow-[inset_3px_0_0_0_var(--color-lime)]" : ""
      }`}
    >
      <span className={`font-serif text-3xl italic ${live ? "text-lime" : "text-paper/35"}`}>
        {String(index).padStart(2, "0")}
      </span>
      <span className="min-w-0 font-serif text-2xl tracking-[-0.02em] lg:text-3xl">{title}</span>
      <span
        className={`col-start-2 font-mono text-[11px] tracking-[0.16em] uppercase lg:col-start-3 ${
          live ? "text-lime" : "text-muted"
        }`}
      >
        {mark ?? "Open"}
      </span>
      <span className="col-start-2 max-w-sm min-w-0 text-muted lg:col-start-4">{summary}</span>
    </button>
  );
}

function Display({
  open,
  titleId,
  surface,
  marks,
  lanes,
  onOpen,
  onMark,
}: {
  open: string;
  titleId: string;
  surface: Surface;
  marks: Record<string, Mark>;
  lanes: Lane[];
  onOpen: (id: string) => void;
  onMark: (id: string, mark: Mark) => void;
}) {
  const [type, a, b] = open.split(":");
  const lane = lanes.find((item) => item.id === a);
  const route = ROUTES.find((item) => item.id === a);
  const way = WAYS.find((item) => item.id === a);
  const group = GROUPS.find((item) => item.id === a);
  const part = PARTS.find((item) => item.id === (type === "part" ? a : ""));

  if (type === "lane" && lane) return <LaneDisplay lane={lane} titleId={titleId} />;
  if (type === "seg" && lane) {
    const seg = lane.segments[Number(b)];
    if (seg) return <SegmentDisplay lane={lane} index={Number(b)} titleId={titleId} onOpen={onOpen} />;
  }
  if (type === "route" && route) return <RouteDisplay routeId={route.id} surface={surface} titleId={titleId} />;
  if (type === "way" && way) return <WayDisplay wayId={way.id} titleId={titleId} />;
  if (type === "group" && group) return <GroupDisplay groupId={group.id} marks={marks} titleId={titleId} onOpen={onOpen} />;
  if (type === "part" && part) {
    return <PartDisplay part={part} surface={surface} mark={marks[part.id]} titleId={titleId} onMark={onMark} onOpen={onOpen} />;
  }
  if (type === "build") return <BuildDisplay marks={marks} titleId={titleId} onOpen={onOpen} />;
  if (type === "truths") return <ProseDisplay titleId={titleId} kicker="Still true" title="What has to stay true." items={TRUTHS} />;
  if (type === "proposal") {
    return <ProseDisplay titleId={titleId} kicker="Not settled" title="One proposal for an order." items={PROPOSAL} />;
  }
  return (
    <h2 id={titleId} className="font-serif text-4xl tracking-[-0.03em]">
      That item is not on this page.
    </h2>
  );
}

function LaneDisplay({ lane, titleId }: { lane: Lane; titleId: string }) {
  const total = sum(lane.segments);
  const model = sum(lane.segments, "model");
  return (
    <>
      <p className="font-mono text-[11px] tracking-[0.18em] text-muted uppercase">Lane</p>
      <h2 id={titleId} className="mt-3 font-serif text-5xl tracking-[-0.03em]">
        {lane.title}
      </h2>
      <p className="mt-4 font-mono text-sm tracking-[0.12em] text-amber uppercase">
        {Math.round(model)}s of {Math.round(total)}s is the model
      </p>
      <p className="mt-5 text-lg leading-relaxed text-muted">{lane.hands}</p>
      <p className="mt-4 text-muted">
        These lengths are a sketch, a scale model of one export, not a measurement on this machine.
        {lane.id === "owned"
          ? " This lane is one sketch of a single plan and then the clicks. It is not a timing of every way to run that plan."
          : ""}
      </p>
      <ol className="mt-8 border-t border-line">
        {lane.segments.map((seg, index) => (
          <li key={`${seg.name}-${index}`} className="grid grid-cols-[7rem_minmax(0,1fr)_4rem] gap-3 border-b border-line py-3">
            <span className="font-mono text-[11px] tracking-[0.14em] text-amber uppercase">{kindLabel(seg.kind)}</span>
            <span>{seg.name}</span>
            <span className="text-right font-mono text-sm text-muted">{seg.s.toFixed(1)}s</span>
          </li>
        ))}
      </ol>
    </>
  );
}

function SegmentDisplay({
  lane,
  index,
  titleId,
  onOpen,
}: {
  lane: Lane;
  index: number;
  titleId: string;
  onOpen: (id: string) => void;
}) {
  const seg = lane.segments[index];
  const total = sum(lane.segments);
  return (
    <>
      <p className="font-mono text-[11px] tracking-[0.18em] text-muted uppercase">{kindLabel(seg.kind)}</p>
      <h2 id={titleId} className="mt-3 font-serif text-5xl tracking-[-0.03em]">
        {seg.name}
      </h2>
      <p className="mt-4 font-mono text-sm tracking-[0.12em] text-amber uppercase">
        {seg.s.toFixed(1)}s inside {lane.title}
      </p>
      <p className="mt-5 text-lg leading-relaxed text-muted">
        This bar is {seg.s.toFixed(1)} seconds of the {Math.round(total)} second lane. It is{" "}
        {kindLabel(seg.kind).toLowerCase()}. The number is a sketch, not a timing taken on this machine.
      </p>
      <p className="mt-4 text-muted">{lane.hands}</p>
      <button
        type="button"
        onClick={() => onOpen(`lane:${lane.id}`)}
        className="mt-8 font-mono text-[11px] tracking-[0.16em] text-amber uppercase hover:text-paper"
      >
        Whole lane
      </button>
    </>
  );
}

function RouteDisplay({ routeId, surface, titleId }: { routeId: string; surface: Surface; titleId: string }) {
  const route = ROUTES.find((item) => item.id === routeId)!;
  return (
    <>
      <p className="font-mono text-[11px] tracking-[0.18em] text-muted uppercase">
        {route.place ?? "Route"}
      </p>
      <h2 id={titleId} className="mt-3 font-serif text-5xl tracking-[-0.03em]">
        {route.title}
      </h2>
      <ol className="mt-8">
        {route.stages(surface).map((stage) => (
          <li
            key={stage.title}
            className={`border-t border-line py-4 ${
              stage.hatch
                ? "bg-[repeating-linear-gradient(-45deg,transparent,transparent_5px,rgba(255,107,74,0.28)_5px,rgba(255,107,74,0.28)_6px)] px-3"
                : ""
            }`}
          >
            <p className={`font-mono text-[11px] tracking-[0.16em] uppercase ${stage.model ? "text-gap" : "text-amber"}`}>
              {stage.title}
            </p>
            <p className="mt-2 text-lg leading-snug">{stage.body}</p>
          </li>
        ))}
      </ol>
      <p className="mt-6 text-muted">{route.ceiling}</p>
    </>
  );
}

function WayDisplay({ wayId, titleId }: { wayId: string; titleId: string }) {
  const way = WAYS.find((item) => item.id === wayId)!;
  return (
    <>
      <p className="font-mono text-[11px] tracking-[0.18em] text-muted uppercase">One way to run it</p>
      <h2 id={titleId} className="mt-3 font-serif text-5xl tracking-[-0.03em]">
        {way.title}
      </h2>
      <p className="mt-5 text-lg leading-relaxed">{way.body}</p>
      <p className="mt-6 border-t border-line pt-4">
        <span className="font-mono text-[11px] tracking-[0.16em] text-amber uppercase">Cost</span>
        <span className="mt-2 block text-muted">{way.cost}</span>
      </p>
      <p className="mt-4 border-t border-line pt-4">
        <span className="font-mono text-[11px] tracking-[0.16em] text-gap uppercase">Fails</span>
        <span className="mt-2 block text-muted">{way.fails}</span>
      </p>
      <p className="mt-6 text-muted">None of the six ways is settled. The clock does not price this one.</p>
    </>
  );
}

function GroupDisplay({
  groupId,
  marks,
  titleId,
  onOpen,
}: {
  groupId: string;
  marks: Record<string, Mark>;
  titleId: string;
  onOpen: (id: string) => void;
}) {
  const group = GROUPS.find((item) => item.id === groupId)!;
  const parts = PARTS.filter((item) => item.group === group.id);
  return (
    <>
      <p className="font-mono text-[11px] tracking-[0.18em] text-muted uppercase">Gaps</p>
      <h2 id={titleId} className="mt-3 font-serif text-5xl tracking-[-0.03em]">
        {group.title}
      </h2>
      <p className="mt-5 text-lg leading-relaxed text-muted">{group.lede}</p>
      <ol className="mt-8 border-t border-line">
        {parts.map((item) => (
          <li key={item.id} className="border-b border-line">
            <button type="button" onClick={() => onOpen(`part:${item.id}`)} className="flex w-full items-baseline justify-between gap-4 py-4 text-left">
              <span className="font-serif text-2xl tracking-[-0.02em]">{item.title}</span>
              <span className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase">{marks[item.id]}</span>
            </button>
          </li>
        ))}
      </ol>
    </>
  );
}

function PartDisplay({
  part,
  surface,
  mark,
  titleId,
  onMark,
  onOpen,
}: {
  part: Part;
  surface: Surface;
  mark: Mark;
  titleId: string;
  onMark: (id: string, mark: Mark) => void;
  onOpen: (id: string) => void;
}) {
  return (
    <>
      <button
        type="button"
        onClick={() => onOpen(`group:${part.group}`)}
        className="font-mono text-[11px] tracking-[0.16em] text-amber uppercase hover:text-paper"
      >
        Back to the group
      </button>
      <h2 id={titleId} className="mt-4 font-serif text-5xl tracking-[-0.03em]">
        {part.title}
      </h2>
      <p className="mt-5 text-lg leading-relaxed">{partBody(part, surface)}</p>
      <p className="mt-4 text-muted">{part.build}</p>
      <div className="mt-8 flex gap-2" role="group" aria-label={part.title}>
        {(["keep", "later", "cut"] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={mark === value}
            onClick={() => onMark(part.id, value)}
            className={`min-w-20 border px-3 py-2 font-mono text-[11px] tracking-[0.16em] uppercase ${
              mark === value ? "border-paper bg-paper text-ink" : "border-line text-muted hover:text-paper"
            }`}
          >
            {value}
          </button>
        ))}
      </div>
    </>
  );
}

function BuildDisplay({
  marks,
  titleId,
  onOpen,
}: {
  marks: Record<string, Mark>;
  titleId: string;
  onOpen: (id: string) => void;
}) {
  const kept = PARTS.filter((part) => marks[part.id] === "keep").sort((a, b) => a.order - b.order);
  const notes = findings(marks);
  const differs = PARTS.some((part) => marks[part.id] !== defaultMark(part));
  return (
    <>
      <p className="font-mono text-[11px] tracking-[0.18em] text-muted uppercase">
        {differs ? "This differs from the proposal" : "This is the proposal"}
      </p>
      <h2 id={titleId} className="mt-3 font-serif text-5xl tracking-[-0.03em]">
        The build you marked.
      </h2>
      <p className="mt-5 text-muted">
        The default marks are a starting proposal, not a decision that one way has won. Cut a part the system
        needs and the gap shows here.
      </p>
      {notes.length ? (
        <ul className="mt-6 border-l-2 border-gap pl-4 text-gap">
          {notes.map((note) => (
            <li key={note} className="py-1">
              {note}
            </li>
          ))}
        </ul>
      ) : null}
      <ol className="mt-8 border-t border-line">
        {kept.length ? (
          kept.map((part, index) => (
            <li key={part.id} className="border-b border-line">
              <button type="button" onClick={() => onOpen(`part:${part.id}`)} className="grid w-full grid-cols-[2rem_minmax(0,1fr)] gap-3 py-4 text-left">
                <span className="font-mono text-sm text-amber">{String(index + 1).padStart(2, "0")}</span>
                <span>
                  <span className="block font-serif text-2xl tracking-[-0.02em]">{part.title}</span>
                  <span className="mt-1 block text-muted">{part.build}</span>
                </span>
              </button>
            </li>
          ))
        ) : (
          <li className="border-b border-line py-4 text-muted">Nothing is marked keep. The build is empty.</li>
        )}
      </ol>
    </>
  );
}

function ProseDisplay({
  titleId,
  kicker,
  title,
  items,
}: {
  titleId: string;
  kicker: string;
  title: string;
  items: string[];
}) {
  return (
    <>
      <p className="font-mono text-[11px] tracking-[0.18em] text-muted uppercase">{kicker}</p>
      <h2 id={titleId} className="mt-3 font-serif text-5xl tracking-[-0.03em]">
        {title}
      </h2>
      <div className="mt-6">
        {items.map((item) => (
          <p key={item} className="border-t border-line py-4 text-lg leading-relaxed text-muted">
            {item}
          </p>
        ))}
      </div>
    </>
  );
}
