const SCALE_PAD = 10;

const GROUPS = [
  {
    id: "necessary",
    title: "The system fails without these",
    lede: "Cut one and the runtime either cannot act, cannot tell a wrong click from a fast one, or sends the page off the machine raw.",
  },
  {
    id: "improves",
    title: "These shorten the loop later",
    lede: "The first build is already faster without them. Add one when a trace shows the planner spending time on an obvious click.",
  },
  {
    id: "hold",
    title: "Leave these out of the first build",
    lede: "Turn one on if you disagree. The note at the bottom will say what that choice costs.",
  },
];

const COMPONENTS = [
  {
    id: "session",
    group: "necessary",
    order: 1,
    title: "Session",
    build: "Attach to the real session, and show the warning.",
    browser:
      "Join the person’s Chrome, logins included. The browser shows a debugging or extension warning. That warning is part of the product.",
    windows:
      "Join the Windows desktop through UI Automation. The pointer stays still when a control can be invoked, and moves when it cannot. The person sees it move.",
  },
  {
    id: "tree",
    group: "necessary",
    order: 2,
    title: "Indexed tree",
    build: "Number the controls once the page has settled.",
    browser:
      "Read the accessibility tree after the page settles. Number each control and resolve the number to a node on the machine. Screenshot a control only when it has no name.",
    windows:
      "Read the UI Automation tree and number the controls. Unnamed controls are more common here than in the browser, so a crop of the screen comes back sooner.",
  },
  {
    id: "language",
    group: "necessary",
    order: 3,
    title: "Action language",
    build: "Agree the verbs: goto, click, fill, press, scroll, extract, assert.",
    body: "The planner writes these verbs. The executor runs them. Another agent can call the same verbs before our planner exists. This is the bridge from tools to owning the loop.",
  },
  {
    id: "executor",
    group: "necessary",
    order: 4,
    title: "Executor",
    build: "Run a verb on the numbered control, and wait on the page’s own events.",
    body: "Waiting lives here: navigation, a settled tree, a file appearing. The model does not sit inside that wait.",
  },
  {
    id: "assert",
    group: "necessary",
    order: 5,
    title: "Assertions",
    build: "Decide success from the URL, the text, or the role.",
    body: "A file name, a heading, a URL. This is the check that keeps a fast path honest. A second model looking at the screen is a later luxury.",
  },
  {
    id: "blast",
    group: "necessary",
    order: 6,
    title: "Blast radius",
    build: "Hold pay, send, and delete, and refuse a second submit.",
    body: "Each verb has a blast radius. Pay, send, and delete do not run unattended. A replay may not submit the same form twice.",
  },
  {
    id: "privacy",
    group: "necessary",
    order: 7,
    title: "Privacy filter",
    build: "Strip mail, balances, and messages before a model sees the tree.",
    body: "Names, mail, balances, and message bodies come off the tree before it leaves the machine, unless the task asked for that field.",
  },
  {
    id: "planner",
    group: "necessary",
    order: 8,
    title: "Planner",
    build: "Ask one frontier model for a batch of verbs. Send the tree as text.",
    body: "One frontier model writes several steps, then stays quiet. It sees a screenshot only when the tree has no names. It is called again when a batch fails.",
  },
  {
    id: "human",
    group: "necessary",
    order: 9,
    title: "Human pause",
    build: "Let a person pause, finish the step, and save the correction.",
    body: "When a batch fails, a person can take the step. The correction is how the runtime learns a page the model missed.",
  },
  {
    id: "trace",
    group: "necessary",
    order: 10,
    title: "Trace",
    build: "Record the tier, the time, and the result of every step.",
    body: "Which tier ran, how long it took, whether the assertion passed. The clock at the top of this sheet is a sketch of that record, waiting for your numbers.",
  },
  {
    id: "tasks",
    group: "necessary",
    order: 11,
    title: "Task set",
    build: "Re-run a fixed set. Keep a change only if success holds.",
    body: "Tasks from real work: slow Cursor desktop sessions, slow Operator runs, slow Claude in Chrome runs. Speed counts when success holds on the same set.",
  },
  {
    id: "router",
    group: "improves",
    order: 20,
    title: "Router",
    build: "Skip the planner when one control matches the words of the task.",
    body: "A rules pass, tens of milliseconds. This is how a step falls from seconds to a click. Add it when the trace shows the planner naming obvious buttons.",
  },
  {
    id: "text",
    group: "improves",
    order: 21,
    title: "Text grounder",
    build: "Let a small text model choose among a handful of controls.",
    body: "For the steps with three plausible buttons and no unique name. A small model, the tree as text, no image.",
  },
  {
    id: "vision",
    group: "improves",
    order: 22,
    title: "Vision grounder",
    build: "Let a small vision model look at a crop, for icons and canvas.",
    body: "Icons, canvas, and controls with no name. The desktop will need this sooner than the browser. It sees a crop, not the whole screen.",
  },
  {
    id: "skills",
    group: "improves",
    order: 23,
    title: "Skills",
    build: "After a clean success, store a script and a fingerprint, and expire both when the page changes.",
    body: "A parameterized script for a site and an intent. Store a fingerprint of the page with it. When the fingerprint changes, the skill expires. A stale skill is a wrong click at full speed.",
  },
  {
    id: "second",
    group: "improves",
    order: 24,
    title: "Second surface",
    build: "Bring the other surface across on the same verbs.",
    browser:
      "Windows, through the same verbs, once browser tasks are honest. This is what meets Cursor’s desktop loop.",
    windows:
      "The browser, through the same verbs, once desktop tasks are honest. This is where the pointer can stay put.",
  },
  {
    id: "cost",
    group: "improves",
    order: 25,
    title: "Cost beside time",
    build: "Record dollars per task beside seconds.",
    body: "The choice of model is a bill as well as a clock. Put both numbers on the trace before you add another model.",
  },
  {
    id: "intercept",
    group: "hold",
    order: 30,
    title: "Interception",
    build: "Sit under someone else’s agent and shorten the capture.",
    body: "Prefetch the frame, return it faster, replay a path already seen. Their model stays in the loop. This is a different product, and it does not grow into the one above.",
  },
  {
    id: "marketplace",
    group: "hold",
    order: 31,
    title: "Plugin marketplace",
    build: "A registry of surfaces and models.",
    body: "Keep a narrow interface for a surface. A registry, a marketplace, and a third surface can wait until the second surface is real.",
  },
  {
    id: "verifier",
    group: "hold",
    order: 32,
    title: "Verifier model",
    build: "Ask another model whether the step worked.",
    body: "A model whose job is to look and judge. Assertions already read the tree. Add a model here only when the tree cannot answer.",
  },
  {
    id: "prefetch",
    group: "hold",
    order: 33,
    title: "Speculative screens",
    build: "Guess the next screen while the planner is still writing.",
    body: "Worth it once you know which guesses are cheap. In the first build the executor’s waits already cover the slow part that is the page itself.",
  },
  {
    id: "shared",
    group: "hold",
    order: 34,
    title: "Shared skill packs",
    build: "Ship one customer’s scripts to another.",
    body: "The pages look alike. The logins, the labels, and the blast radius do not. Keep skills on the machine that learned them until expiry works.",
  },
];

const HOLES = [
  {
    id: "session",
    text: "Session is out. There is no browser and no desktop to act on.",
  },
  {
    id: "tree",
    text: "The indexed tree is out. The planner is back to full screenshots.",
  },
  {
    id: "language",
    text: "The action language is out. The planner and the executor have no shared verbs.",
  },
  {
    id: "executor",
    text: "The executor is out. A plan would have nothing that can click.",
  },
  {
    id: "assert",
    text: "Assertions are out. A wrong click will look like a fast success.",
  },
  {
    id: "blast",
    text: "Blast radius is out. The fast path can pay, send, or delete, and can do it twice.",
  },
  {
    id: "privacy",
    text: "The privacy filter is out. The model receives the raw tree, including whatever the page is showing.",
  },
  {
    id: "planner",
    text: "The planner is out, and nothing else writes the steps.",
  },
  {
    id: "human",
    text: "Human pause is out. A failed batch has nowhere to go but another model call.",
  },
  {
    id: "trace",
    text: "The trace is out. You will feel the speed and have no record of which tier did the work.",
  },
  {
    id: "tasks",
    text: "The task set is out. A drop in success will be invisible next to a shorter clock.",
  },
];

const CAUTIONS = [
  {
    id: "intercept",
    text: "Interception is in the build. It shortens capture. The model still sets the pace, and this path does not become the owned loop.",
  },
  {
    id: "marketplace",
    text: "A plugin marketplace is in the build, before a second surface exists.",
  },
  {
    id: "verifier",
    text: "A verifier model is in the build. Assertions already answer most of those checks from the tree.",
  },
  {
    id: "shared",
    text: "Shared skill packs are in the build. A script from another customer runs at full speed on this person’s accounts.",
  },
];

function lanesFor(surface) {
  const owned =
    surface === "windows"
      ? {
          title: "Owning the loop",
          hands:
            "One plan, then UI Automation. The pointer moves when a control cannot be invoked. The short model bar is an unnamed icon.",
          segments: [
            { kind: "model", s: 5.5, name: "Plan" },
            { kind: "act", s: 0.4, name: "Window" },
            { kind: "act", s: 0.35, name: "Open" },
            { kind: "settle", s: 1.4, name: "Page" },
            { kind: "model", s: 1.8, name: "Icon" },
            { kind: "act", s: 0.3, name: "Month" },
            { kind: "act", s: 0.35, name: "Export" },
            { kind: "settle", s: 0.9, name: "File" },
          ],
        }
      : {
          title: "Owning the loop",
          hands:
            "One plan, then the node. In the browser the person’s pointer stays put, in a background tab.",
          segments: [
            { kind: "model", s: 5.5, name: "Plan" },
            { kind: "act", s: 0.25, name: "Open" },
            { kind: "settle", s: 1.3, name: "Page" },
            { kind: "act", s: 0.2, name: "Month" },
            { kind: "act", s: 0.3, name: "Export" },
            { kind: "settle", s: 0.8, name: "File" },
            { kind: "act", s: 0.15, name: "Check" },
          ],
        };

  return [
    {
      title: "Cursor on Windows",
      hands: "The Windows pointer is taken for the whole task.",
      segments: [
        { kind: "model", s: 6.4, name: "Desktop" },
        { kind: "act", s: 0.35, name: "Click" },
        { kind: "model", s: 5.6, name: "Browser" },
        { kind: "act", s: 0.3, name: "Click" },
        { kind: "model", s: 4.8, name: "Open" },
        { kind: "settle", s: 1.5, name: "Page" },
        { kind: "model", s: 6.2, name: "Read" },
        { kind: "act", s: 0.25, name: "Click" },
        { kind: "model", s: 5.4, name: "Invoices" },
        { kind: "act", s: 0.3, name: "Click" },
        { kind: "model", s: 4.9, name: "Month" },
        { kind: "act", s: 0.35, name: "Click" },
        { kind: "model", s: 5.8, name: "Download" },
        { kind: "settle", s: 1.1, name: "File" },
        { kind: "model", s: 4.4, name: "Confirm" },
        { kind: "act", s: 0.25, name: "Click" },
      ],
    },
    {
      title: "Operator, Claude in Chrome",
      hands:
        "The same loop inside a browser, along with the other screenshot-first frontier models. Operator’s browser is elsewhere, so the person’s mouse is free and the clock is not. Claude in Chrome drives a browser on this machine.",
      segments: [
        { kind: "model", s: 5.8, name: "Open" },
        { kind: "settle", s: 1.4, name: "Page" },
        { kind: "model", s: 6.1, name: "Read" },
        { kind: "act", s: 0.3, name: "Click" },
        { kind: "model", s: 5.2, name: "Invoices" },
        { kind: "act", s: 0.3, name: "Click" },
        { kind: "model", s: 4.7, name: "Month" },
        { kind: "act", s: 0.35, name: "Click" },
        { kind: "model", s: 6.4, name: "Download" },
        { kind: "settle", s: 1.0, name: "File" },
        { kind: "model", s: 4.3, name: "Confirm" },
        { kind: "act", s: 0.25, name: "Click" },
      ],
    },
    {
      title: "Browser Use",
      hands:
        "The exception already shipping. The tree is in the prompt, so each call is shorter, and a large model still chooses every control.",
      segments: [
        { kind: "model", s: 2.6, name: "Open" },
        { kind: "settle", s: 1.3, name: "Page" },
        { kind: "model", s: 2.4, name: "Read" },
        { kind: "act", s: 0.25, name: "Click" },
        { kind: "model", s: 2.2, name: "Invoices" },
        { kind: "act", s: 0.25, name: "Click" },
        { kind: "model", s: 2.1, name: "Month" },
        { kind: "act", s: 0.3, name: "Click" },
        { kind: "model", s: 2.5, name: "Download" },
        { kind: "settle", s: 0.9, name: "File" },
        { kind: "model", s: 2.0, name: "Confirm" },
      ],
    },
    owned,
  ];
}

const state = load();

function load() {
  const fresh = {
    surface: "browser",
    filter: "all",
    notes: "",
    marks: Object.fromEntries(COMPONENTS.map((c) => [c.id, defaultMark(c)])),
  };
  try {
    const raw = localStorage.getItem("cuo-sheet-v1");
    if (!raw) return fresh;
    const saved = JSON.parse(raw);
    const marks = { ...fresh.marks };
    for (const c of COMPONENTS) {
      if (["keep", "later", "cut"].includes(saved.marks?.[c.id])) {
        marks[c.id] = saved.marks[c.id];
      }
    }
    return {
      surface: saved.surface === "windows" ? "windows" : "browser",
      filter: ["all", "keep", "later", "cut"].includes(saved.filter) ? saved.filter : "all",
      notes: typeof saved.notes === "string" ? saved.notes : "",
      marks,
    };
  } catch {
    return fresh;
  }
}

function save() {
  try {
    localStorage.setItem(
      "cuo-sheet-v1",
      JSON.stringify({
        surface: state.surface,
        filter: state.filter,
        notes: state.notes,
        marks: state.marks,
      })
    );
  } catch {
    /* a private window can refuse storage; the sheet still works */
  }
}

function defaultMark(component) {
  if (component.group === "necessary") return "keep";
  if (component.group === "improves") return "later";
  return "cut";
}

function sum(segments, kind) {
  return segments.reduce((total, seg) => total + (kind && seg.kind !== kind ? 0 : seg.s), 0);
}

function scaleFor(lanes) {
  const max = Math.max(...lanes.map((lane) => sum(lane.segments)));
  return Math.ceil(max / SCALE_PAD) * SCALE_PAD;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function renderTrace() {
  const lanes = lanesFor(state.surface);
  const scale = scaleFor(lanes);
  const chart = document.getElementById("chart");
  const alt = document.getElementById("trace-text");
  chart.replaceChildren();
  const altLines = [];

  lanes.forEach((lane) => {
    const total = sum(lane.segments);
    const model = sum(lane.segments, "model");
    const row = el("div", "lane");
    const id = el("div", "lane-id");
    id.append(el("p", "lane-title", lane.title), el("p", "lane-total", `${Math.round(total)}s`));
    const track = el("div", "track");
    track.setAttribute("aria-hidden", "true");
    let cursor = 0;
    lane.segments.forEach((seg) => {
      const node = el("div", `seg ${seg.kind}`);
      node.style.left = `${(cursor / scale) * 100}%`;
      node.style.width = `${(seg.s / scale) * 100}%`;
      node.style.animationDelay = `${Math.min(cursor * 14, 420)}ms`;
      const label = `${seg.name}, ${seg.kind === "model" ? "model call" : seg.kind === "act" ? "action" : "page settling"}, ${seg.s.toFixed(1)}s`;
      node.title = label;
      if (seg.kind === "model" && seg.s >= 4) node.textContent = seg.name;
      track.append(node);
      cursor += seg.s;
    });
    const meta = el(
      "p",
      "lane-meta",
      `${Math.round(model)}s of ${Math.round(total)}s is the model. ${lane.hands}`
    );
    row.append(id, track, meta);
    chart.append(row);
    altLines.push(
      `${lane.title}: ${Math.round(total)} seconds, ${Math.round(model)} in model calls. ${lane.hands}`
    );
  });

  const axisRow = el("div", "lane axis-row");
  axisRow.append(el("div"));
  const axis = el("div", "axis");
  for (let t = 0; t <= scale; t += SCALE_PAD) {
    const tick = el("span", null, `${t}s`);
    tick.style.left = `${(t / scale) * 100}%`;
    axis.append(tick);
  }
  axisRow.append(axis);
  chart.append(axisRow);
  alt.textContent = altLines.join(" ");
  trimLabels(chart);
}

function trimLabels(root) {
  const probe = document.createElement("span");
  probe.style.cssText = "position:absolute;left:-9999px;top:0;white-space:nowrap;visibility:hidden;";
  document.body.append(probe);
  root.querySelectorAll(".seg").forEach((node) => {
    if (!node.textContent || node.clientWidth < 8) return;
    const style = getComputedStyle(node);
    probe.style.font = style.font;
    probe.textContent = node.textContent;
    const pad = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
    if (probe.getBoundingClientRect().width + pad > node.clientWidth - 4) node.textContent = "";
  });
  probe.remove();
}

function bodyFor(component) {
  if (component.body) return component.body;
  return state.surface === "windows" ? component.windows : component.browser;
}

function renderMachine() {
  const root = document.getElementById("machine");
  root.replaceChildren();
  for (const group of GROUPS) {
    const section = el("div", "group");
    section.dataset.group = group.id;
    section.append(el("h3", null, group.title), el("p", "lede", group.lede));
    for (const component of COMPONENTS.filter((item) => item.group === group.id)) {
      const part = el("article", "part");
      part.dataset.id = component.id;
      const main = el("div");
      main.append(el("h4", null, component.title), el("p", "part-body", bodyFor(component)));
      const marks = el("div", "marks segment");
      marks.setAttribute("role", "group");
      marks.setAttribute("aria-label", component.title);
      for (const [mark, label] of [
        ["keep", "Keep"],
        ["later", "Later"],
        ["cut", "Cut"],
      ]) {
        const button = el("button", null, label);
        button.type = "button";
        button.dataset.mark = mark;
        button.setAttribute("aria-pressed", String(state.marks[component.id] === mark));
        marks.append(button);
      }
      part.append(main, marks);
      section.append(part);
    }
    root.append(section);
  }
  applyFilter();
}

function applySurfaceCopy() {
  document.querySelectorAll("[data-for]").forEach((node) => {
    node.hidden = node.dataset.for !== state.surface;
  });
  document.querySelectorAll("[data-surface]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.surface === state.surface));
  });
  document.querySelectorAll(".part").forEach((part) => {
    const component = COMPONENTS.find((item) => item.id === part.dataset.id);
    const body = part.querySelector(".part-body");
    if (component && body) body.textContent = bodyFor(component);
  });
}

function applyFilter() {
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.filter === state.filter));
  });
  document.querySelectorAll(".part").forEach((part) => {
    part.hidden = state.filter !== "all" && state.marks[part.dataset.id] !== state.filter;
  });
  document.querySelectorAll(".group").forEach((group) => {
    group.hidden = !group.querySelector(".part:not([hidden])");
  });
}

function syncMarks() {
  document.querySelectorAll(".part").forEach((part) => {
    const current = state.marks[part.dataset.id];
    part.querySelectorAll("[data-mark]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.mark === current));
    });
  });
}

function findings() {
  const holes = HOLES.filter((hole) => state.marks[hole.id] !== "keep").map((hole) => hole.text);
  const cautions = CAUTIONS.filter((item) => state.marks[item.id] === "keep").map((item) => item.text);
  return { holes, cautions };
}

function decisionLines() {
  const kept = COMPONENTS.filter((c) => state.marks[c.id] === "keep");
  const later = COMPONENTS.filter((c) => state.marks[c.id] === "later");
  const cut = COMPONENTS.filter((c) => state.marks[c.id] === "cut");
  const surface =
    state.surface === "windows"
      ? "First surface is the Windows desktop."
      : "First surface is the browser.";
  const differs = COMPONENTS.some((c) => state.marks[c.id] !== defaultMark(c)) || state.surface !== "browser";
  const head = differs ? "This differs from the recommendation." : "This is the recommendation.";
  return {
    summary: `${head} ${surface} ${kept.length} in the build, ${later.length} waiting, ${cut.length} left out.`,
    kept,
    later,
    cut,
  };
}

function renderDecision() {
  const { summary, kept } = decisionLines();
  document.getElementById("summary").textContent = summary;
  const warnings = document.getElementById("warnings");
  const { holes, cautions } = findings();
  warnings.replaceChildren();
  for (const text of [...holes, ...cautions]) {
    warnings.append(el("li", null, text));
  }

  const build = document.getElementById("build");
  build.replaceChildren();
  const ordered = [...kept].sort((a, b) => a.order - b.order);
  if (!ordered.length) {
    const item = el("li");
    item.append(el("h3", null, "Nothing is marked keep"), el("p", null, "The build is empty."));
    build.append(item);
    return;
  }
  for (const component of ordered) {
    const item = el("li");
    item.append(el("h3", null, component.title), el("p", null, component.build));
    build.append(item);
  }
}

function decisionText() {
  const { summary, kept, later, cut } = decisionLines();
  const { holes, cautions } = findings();
  const lines = [
    "Computer use optimisation",
    summary,
    "",
    "In the build:",
    ...kept.sort((a, b) => a.order - b.order).map((c) => `- ${c.title}: ${c.build}`),
    "",
    "Waiting:",
    ...(later.length ? later.map((c) => `- ${c.title}`) : ["- none"]),
    "",
    "Left out:",
    ...(cut.length ? cut.map((c) => `- ${c.title}`) : ["- none"]),
  ];
  if (holes.length || cautions.length) {
    lines.push("", "Look at these:");
    for (const text of [...holes, ...cautions]) lines.push(`- ${text}`);
  }
  if (state.notes.trim()) {
    lines.push("", "Notes:", state.notes.trim());
  }
  return lines.join("\n");
}

function renderAll() {
  renderTrace();
  applySurfaceCopy();
  renderDecision();
  save();
}

document.getElementById("machine").addEventListener("click", (event) => {
  const button = event.target.closest("[data-mark]");
  if (!button) return;
  const part = button.closest(".part");
  state.marks[part.dataset.id] = button.dataset.mark;
  syncMarks();
  applyFilter();
  renderDecision();
  save();
});

document.querySelector(".toolbar").addEventListener("click", (event) => {
  const button = event.target.closest("[data-surface]");
  if (!button || button.dataset.surface === state.surface) return;
  state.surface = button.dataset.surface;
  renderAll();
});

document.getElementById("filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  applyFilter();
  save();
});

document.getElementById("notes").addEventListener("input", (event) => {
  state.notes = event.target.value;
  save();
});

document.getElementById("reset").addEventListener("click", () => {
  for (const component of COMPONENTS) state.marks[component.id] = defaultMark(component);
  state.filter = "all";
  syncMarks();
  applyFilter();
  renderDecision();
  save();
});

document.getElementById("copy").addEventListener("click", async () => {
  const button = document.getElementById("copy");
  const text = decisionText();
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch {
    button.textContent = "Copy failed";
  }
  window.setTimeout(() => {
    button.textContent = "Copy decision";
  }, 1600);
});

document.getElementById("notes").value = state.notes;
renderMachine();
renderAll();

let resizeTimer = 0;
window.addEventListener("resize", () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => renderTrace(), 120);
});
