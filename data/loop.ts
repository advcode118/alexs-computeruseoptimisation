export type Surface = "browser" | "windows";
export type SegKind = "model" | "act" | "settle";
export type Mark = "keep" | "later" | "cut";

export type Segment = { kind: SegKind; s: number; name: string };

export type Lane = {
  id: string;
  title: string;
  hands: string;
  segments: Segment[];
};

export type Stage = {
  title: string;
  body: string;
  model?: boolean;
  hatch?: boolean;
};

export type Route = {
  id: string;
  title: string;
  home: string;
  place?: string;
  stages: (surface: Surface) => Stage[];
  ceiling: string;
};

export type Way = {
  id: string;
  title: string;
  home: string;
  body: string;
  cost: string;
  fails: string;
};

export type Part = {
  id: string;
  group: "necessary" | "improves" | "hold";
  order: number;
  title: string;
  build: string;
  body?: string;
  browser?: string;
  windows?: string;
};

export const SCALE_PAD = 10;

export const GROUPS = [
  {
    id: "necessary" as const,
    title: "The system fails without these",
    lede: "Cut one and the runtime either cannot act, cannot tell a wrong click from a fast one, or sends the page off the machine raw.",
  },
  {
    id: "improves" as const,
    title: "These shorten the loop later",
    lede: "The first build is already faster without them. Add one when a trace shows the planner spending time on an obvious click.",
  },
  {
    id: "hold" as const,
    title: "Leave these out of the first build",
    lede: "Turn one on if you disagree. The note in this display says what that choice costs.",
  },
];

export const PARTS: Part[] = [
  {
    id: "session",
    group: "necessary",
    order: 1,
    title: "Session",
    build: "Attach to the real session, and show the warning.",
    browser:
      "Join the person's Chrome, logins included. The browser shows a debugging or extension warning. That warning is part of the product.",
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
    build: "Run a verb on the numbered control, and wait on the page's own events.",
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
    body: "Which tier ran, how long it took, whether the assertion passed. The clock on this page is a sketch of that record, waiting for your numbers.",
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
      "Windows, through the same verbs, once browser tasks are honest. This is what meets Cursor's desktop loop.",
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
    build: "Sit under someone else's agent and shorten the capture.",
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
    body: "Worth it once you know which guesses are cheap. In the first build the executor's waits already cover the slow part that is the page itself.",
  },
  {
    id: "shared",
    group: "hold",
    order: 34,
    title: "Shared skill packs",
    build: "Ship one customer's scripts to another.",
    body: "The pages look alike. The logins, the labels, and the blast radius do not. Keep skills on the machine that learned them until expiry works.",
  },
];

export const HOLES: { id: string; text: string }[] = [
  { id: "session", text: "Session is out. There is no browser and no desktop to act on." },
  { id: "tree", text: "The indexed tree is out. The planner is back to full screenshots." },
  { id: "language", text: "The action language is out. The planner and the executor have no shared verbs." },
  { id: "executor", text: "The executor is out. A plan would have nothing that can click." },
  { id: "assert", text: "Assertions are out. A wrong click will look like a fast success." },
  { id: "blast", text: "Blast radius is out. The fast path can pay, send, or delete, and can do it twice." },
  { id: "privacy", text: "The privacy filter is out. The model receives the raw tree, including whatever the page is showing." },
  { id: "planner", text: "The planner is out, and nothing else writes the steps." },
  { id: "human", text: "Human pause is out. A failed batch has nowhere to go but another model call." },
  { id: "trace", text: "The trace is out. You will feel the speed and have no record of which tier did the work." },
  { id: "tasks", text: "The task set is out. A drop in success will be invisible next to a shorter clock." },
];

export const CAUTIONS: { id: string; text: string }[] = [
  {
    id: "intercept",
    text: "Interception is in the build. It shortens capture. The model still sets the pace, and this path does not become the owned loop.",
  },
  { id: "marketplace", text: "A plugin marketplace is in the build, before a second surface exists." },
  { id: "verifier", text: "A verifier model is in the build. Assertions already answer most of those checks from the tree." },
  {
    id: "shared",
    text: "Shared skill packs are in the build. A script from another customer runs at full speed on this person's accounts.",
  },
];

export const ROUTES: Route[] = [
  {
    id: "own",
    title: "Own the loop",
    place: "Place to stand",
    home: "One plan, then the executor. This is the only place that removes the repeated model calls.",
    ceiling: "We take responsibility for whether the export happened. This is the only place to stand that removes the repeated model calls.",
    stages: (surface) => [
      { title: "Task", body: "The person asks for the export." },
      { title: "Planner", body: "One frontier model writes a batch of verbs from the tree.", model: true },
      {
        title: "Act",
        body:
          surface === "windows"
            ? "The executor invokes the control, or moves the pointer when it cannot."
            : "The executor uses the numbered control. The pointer stays put.",
      },
      { title: "Assert", body: "The file name, the URL, or the heading says it worked." },
      { title: "Person", body: "If the batch fails, or the action can pay or send, a person takes the step." },
    ],
  },
  {
    id: "tools",
    title: "Tools only",
    home: "Our verbs, their agent. If they refuse, the screenshot loop keeps its old length.",
    ceiling: "This speeds agents that call the verbs. It is also the first slice of owning the loop: ship the verbs, then put our planner on top of them.",
    stages: () => [
      { title: "Their agent", body: "Cursor, a browser agent, or another frontier model still decides.", model: true },
      { title: "Our verbs", body: "Observe, click 12, fill, assert. The same language as the owned loop." },
      {
        title: "If they refuse",
        body: "They keep taking screenshots, and their loop continues at the old length.",
        hatch: true,
      },
    ],
  },
  {
    id: "intercept",
    title: "Intercept",
    home: "A few hundred milliseconds a step. Their model still owns the clock.",
    ceiling: "A few hundred milliseconds a step. This does not grow into the owned loop, because the clock still belongs to their model.",
    stages: () => [
      { title: "Their agent", body: "Unchanged. It still wants a picture before each click.", model: true },
      { title: "Our socket", body: "We shorten the capture and can replay a path we have already seen." },
      {
        title: "Their model, again",
        body: "The long bars stay. We do not choose the model.",
        model: true,
        hatch: true,
      },
    ],
  },
];

export const WAYS: Way[] = [
  {
    id: "rules",
    title: "Rules, then a direct click",
    home: "When the role and the name are unique. No model.",
    body: "When the role and the name are unique, click that control. No model.",
    cost: "The match itself, tens of milliseconds, and no model bill.",
    fails: "Fails when the name is shared or missing. This way does not guess a neighbour.",
  },
  {
    id: "decider",
    title: "A lightweight decider, then a fast text model",
    home: "The decider only picks the tier. A text model reads the control list.",
    body: "A small decider only picks the tier. A fast text model then chooses from the control list. The decider does not click.",
    cost: "A small decision, then one short text call. No image.",
    fails: "Fails when the words cannot tell the controls apart. Icons and canvas are the usual miss.",
  },
  {
    id: "vision",
    title: "A fast vision model on a crop",
    home: "Only for icons and controls with no name.",
    body: "Only for an icon or a control with no name. The model sees a crop, not the whole screen.",
    cost: "One small vision call on that crop.",
    fails: "Fails when the crop misses the control, or the icon is ambiguous. Unnamed controls show up sooner on the Windows desktop than in the browser.",
  },
  {
    id: "batch",
    title: "One frontier model, then the batch",
    home: "One batch of verbs, then the executor until an assertion fails.",
    body: "One frontier model writes a batch of verbs from the tree. The executor runs that batch until an assertion fails, and then it stops.",
    cost: "One large model call for the batch. The clicks and the waits after that are the page, not another model.",
    fails: "Fails when the batch was wrong, the page moved, or the assertion does not hold. It does not click through a failed check.",
  },
  {
    id: "skill",
    title: "Skill replay",
    home: "After a traced success. Expires when the page changes.",
    body: "After a traced success, store the script and a fingerprint of the page. Replay it while the fingerprint matches. When the page changes, the skill expires.",
    cost: "A hit is no model call. A miss falls through to another way. A script past its expiry is a wrong click at full speed, so it does not run.",
    fails: "Fails when the fingerprint misses a real change, or matches too loosely. Expiry is the guard.",
  },
  {
    id: "plugin",
    title: "A plugin in Cursor or Claude",
    home: "A client of this runtime. Not the loop itself.",
    body: "Cursor or Claude can call this runtime. The plugin is a client. It is not the loop. Their agent may ask for a verb. The executor still owns the click.",
    cost: "Their model spends a call deciding to ask. The action is a verb on a numbered control, not another screenshot.",
    fails: "Fails when they skip the verbs and look at the screen again. The long bars stay, and this is no longer the owned loop.",
  },
];

export const TRUTHS = [
  "Pay, send, and delete wait for a person. A replay cannot submit the same form twice.",
  "Mail, balances, and message bodies are stripped from the tree before a model sees it, unless the task asked for that field.",
  "A skill stores a fingerprint of the page and expires when the page changes. A stale script is a wrong click at full speed.",
  "Extra tabs, popups, downloads, file pickers, and login walls are states the executor knows. They are where browser agents get lost.",
  "A person can pause, do the step, and have that correction saved.",
  "Chrome warns when we attach. The desktop shows the pointer when we cannot avoid it. Both stay visible.",
  "Every change re-runs the task set. A shorter clock counts when success holds.",
];

export const PROPOSAL = [
  "The ways on this page are open. This is one proposal for an order, not a decision that the others are out.",
  "Ship the browser verbs first, on the person's real Chrome. An agent they already use can call them the same week. Our planner uses those same verbs once the task set exists.",
  "Keep one frontier model in the loop. Add a smaller grounder when a trace shows the planner spending time on obvious clicks, and a vision crop when the control has no name.",
  "Start in the browser if the pointer should stay put. Use the switch on the clock if the pain you actually feel is Cursor on the desktop. The verbs stay. On Windows the pointer still moves for some controls, and unnamed icons still need a look.",
  "Store skills after you have traces worth replaying, with a fingerprint of the page, and expire them when that fingerprint changes.",
  "Leave interception as its own product. It never chooses the model, so the red bars stay red.",
];

export function lanesFor(surface: Surface): Lane[] {
  const owned: Lane =
    surface === "windows"
      ? {
          id: "owned",
          title: "Owning the loop",
          hands: "One plan, then UI Automation. The pointer moves when a control cannot be invoked. The short model bar is an unnamed icon.",
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
          id: "owned",
          title: "Owning the loop",
          hands: "One plan, then the node. In the browser the person's pointer stays put, in a background tab.",
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
      id: "cursor",
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
      id: "agents",
      title: "Operator, Claude in Chrome",
      hands: "The same loop inside a browser, along with the other screenshot-first frontier models. Operator's browser is elsewhere, so the person's mouse is free and the clock is not. Claude in Chrome drives a browser on this machine.",
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
      id: "browser-use",
      title: "Browser Use",
      hands: "The exception already shipping. The tree is in the prompt, so each call is shorter, and a large model still chooses every control.",
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

export function sum(segments: Segment[], kind?: SegKind) {
  return segments.reduce((total, seg) => total + (kind && seg.kind !== kind ? 0 : seg.s), 0);
}

export function scaleFor(lanes: Lane[]) {
  const max = Math.max(...lanes.map((lane) => sum(lane.segments)));
  return Math.ceil(max / SCALE_PAD) * SCALE_PAD;
}

export function kindLabel(kind: SegKind) {
  if (kind === "model") return "Model call";
  if (kind === "act") return "Acting on the control";
  return "Page settling";
}

export function partBody(part: Part, surface: Surface) {
  if (part.body) return part.body;
  return surface === "windows" ? part.windows ?? "" : part.browser ?? "";
}

export function defaultMark(part: Part): Mark {
  if (part.group === "necessary") return "keep";
  if (part.group === "improves") return "later";
  return "cut";
}

export function findings(marks: Record<string, Mark>) {
  const holes = HOLES.filter((hole) => marks[hole.id] !== "keep").map((hole) => hole.text);
  const cautions = CAUTIONS.filter((item) => marks[item.id] === "keep").map((item) => item.text);
  return [...holes, ...cautions];
}
