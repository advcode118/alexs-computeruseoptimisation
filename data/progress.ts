/**
 * All progress copy and every number on the site lives here. Edit this file to update the site.
 * Numbers come from the probe logs. Do not add a number that was not measured.
 */

export type ArmId = "playwright_mcp" | "diff_fast_act" | "macro_replay" | "script_first" | "stagehand";

export type ProbeId = "probe1" | "pr14" | "pr15" | "pr16" | "pr17";

export type ArmResult = {
  arm: ArmId;
  successes: number;
  tasks: number;
  /** Wall time per success in seconds, as logged. Absent when the probe did not report one. */
  seconds?: number;
  /** Cost in US dollars, as logged. Absent when the probe did not report one. */
  cost?: number;
  note?: string;
};

export type Probe = {
  id: ProbeId;
  label: string;
  model: string;
  summary: string;
  results: ArmResult[];
};

export type TimelineEntry = {
  id: string;
  label: string;
  title: string;
  body: string;
  figures: { value: string; label: string }[];
  stack?: { pr: string; text: string }[];
  tone?: "stop" | "now";
};

export type DemoLane = "model" | "tool" | "browser" | "check";

export type DemoStep = {
  lane: DemoLane;
  title: string;
  detail: string;
  counts?: "model" | "browser" | "repair";
  repeats?: boolean;
  branch?: "repair";
};

export type DemoArm = {
  id: "playwright_mcp" | "proxy" | "script_first" | "stagehand";
  name: string;
  arms: ArmId[];
  oneLine: string;
  steps: DemoStep[];
  takeaway: string;
};

export const armMeta: Record<ArmId, { name: string; short: string; color: string }> = {
  playwright_mcp: { name: "Plain Playwright MCP", short: "Playwright MCP", color: "var(--color-arm-mcp)" },
  diff_fast_act: { name: "Proxy: diff + fast act", short: "diff_fast_act", color: "var(--color-arm-proxy)" },
  macro_replay: { name: "Proxy: macro replay", short: "macro_replay", color: "var(--color-arm-replay)" },
  script_first: { name: "Script first", short: "script_first", color: "var(--color-arm-script)" },
  stagehand: { name: "Stagehand", short: "Stagehand", color: "var(--color-arm-stagehand)" },
};

export const probes: Probe[] = [
  {
    id: "probe1",
    label: "Probe 1",
    model: "No outer model on the proxy arms",
    summary: "No-model alone cannot do open tasks.",
    results: [
      { arm: "playwright_mcp", successes: 1, tasks: 3, seconds: 417.5, cost: 1.31 },
      { arm: "stagehand", successes: 1, tasks: 3, seconds: 33.5, cost: 0.1 },
      { arm: "diff_fast_act", successes: 0, tasks: 3 },
      { arm: "macro_replay", successes: 0, tasks: 3 },
    ],
  },
  {
    id: "pr14",
    label: "PR #14",
    model: "Outer Claude Sonnet 4.6",
    summary: "Outer Claude drives the proxy arms. Every proxy arm reaches 3/3, but plain Playwright MCP is still fastest.",
    results: [
      { arm: "playwright_mcp", successes: 3, tasks: 3, seconds: 9.5, cost: 0.29 },
      { arm: "diff_fast_act", successes: 3, tasks: 3, seconds: 16.7, cost: 0.27 },
      { arm: "macro_replay", successes: 3, tasks: 3, seconds: 25.5, cost: 0.55 },
      { arm: "stagehand", successes: 1, tasks: 3, note: "Scoring bug" },
    ],
  },
  {
    id: "pr15",
    label: "PR #15",
    model: "Outer Claude",
    summary: "Adaptive settle and macro caps. Plain Playwright MCP still wins. Design stop on proxy speed tuning.",
    results: [
      { arm: "playwright_mcp", successes: 3, tasks: 3, seconds: 14.7 },
      { arm: "macro_replay", successes: 3, tasks: 3, seconds: 19.5 },
      { arm: "diff_fast_act", successes: 3, tasks: 3, seconds: 29.9 },
      { arm: "stagehand", successes: 1, tasks: 3, seconds: 31.7 },
    ],
  },
  {
    id: "pr16",
    label: "PR #16",
    model: "Claude Sonnet 5.5",
    summary: "First script_first run. Cheapest per run, but only 1/3.",
    results: [
      { arm: "stagehand", successes: 2, tasks: 3, seconds: 2.5, cost: 0.053 },
      { arm: "playwright_mcp", successes: 3, tasks: 3, seconds: 3.8, cost: 0.15 },
      { arm: "script_first", successes: 1, tasks: 3, seconds: 4.1, cost: 0.031 },
    ],
  },
  {
    id: "pr17",
    label: "PR #17",
    model: "Claude Sonnet 5.5",
    summary: "One repair call and the Stagehand URL fix. script_first reaches 3/3.",
    results: [
      { arm: "playwright_mcp", successes: 3, tasks: 3, seconds: 3.06, cost: 0.167 },
      { arm: "script_first", successes: 3, tasks: 3, seconds: 4.56, cost: 0.042 },
      { arm: "stagehand", successes: 3, tasks: 3, seconds: 15.52, cost: 0.103, note: "Wikipedia alone ~40.9s" },
    ],
  },
];

export const progress = {
  project: "Computer-use optimisation",
  asOf: "6 November 2026",
  sourceFile: "data/progress.ts",
  goal: "A faster browser tool for computer use. An outer agent (Claude, Cursor) drives a browser. The main number is wall time per successful task, with success within about 2 points of the stronger baseline. Browser first. Desktop later, not started.",
  status: {
    headline: "script_first is 3/3 and the cheapest.",
    subhead: "It is not yet the fastest.",
    body: "In the latest probe (PR #17, Claude Sonnet 5.5, three tasks), plain Playwright MCP is 3.06s per success. script_first is 4.56s. The next PR targets fewer repair calls.",
    probe: "pr17" as ProbeId,
    next: "Next: one-shot rate PR, in progress. Fewer repair calls.",
    spend: { used: 16.35, cap: 50, abortAt: 40 },
  },
  tasks: ["Wikipedia search", "Python docs", "Hacker News top"],
  benchmark: {
    source: "LangChain, 3 Nov 2026, WebVoyager 100",
    rows: [
      { name: "Stagehand v4", pass: "90%", cost: "$1.98 total", time: "~17.4s median", steps: "~10 steps" },
      { name: "Playwright MCP", pass: "78%", cost: "$26.71", time: "~3x slower", steps: "~26 steps" },
    ],
  },
  timeline: [
    {
      id: "loop",
      label: "Before the speed layer",
      title: "A browser loop that owns each step",
      body: "Observe, decide, act, assert. No-model routing first, a cheap Nebius tier next, the Claude planner last. It raced Browser Use and cut model calls.",
      figures: [
        { value: "14", label: "live tasks passed on a cold open" },
        { value: "~3x", label: "faster per task, no task shortcuts" },
      ],
    },
    {
      id: "m0",
      label: "M0 measurement",
      title: "The outer model's thinking is the clock",
      body: "Claude Sonnet 4.6 over the API on Playwright MCP. One arXiv page (~130k tokens) was resent every step. Lesson: cut steps, not just snapshot size.",
      figures: [
        { value: "4/5", label: "succeeded" },
        { value: "36", label: "steps" },
        { value: "94.8s", label: "wall time" },
        { value: "87% / 13%", label: "model time vs tools" },
        { value: "3.2M / 3k", label: "input vs output tokens" },
        { value: "~$9", label: "cost of resending one arXiv page" },
      ],
    },
    {
      id: "stack",
      label: "Speed-layer PR stack",
      title: "Stacked PRs #7 to #17, none merged",
      body: "Each PR sits on the one before it.",
      stack: [
        { pr: "#7", text: "decide() and backend split" },
        { pr: "#8", text: "Bench harness fixes" },
        { pr: "#9", text: "Python MCP proxy over @playwright/mcp@0.0.84" },
        { pr: "#10", text: "fast_act and do_task_segment" },
        { pr: "#11", text: "Replay cache" },
        { pr: "#12", text: "Settle and compact diff" },
        { pr: "#13", text: "500ms settle, Stagehand arm, script spike" },
        { pr: "#14", text: "Outer Claude drives proxy arms, isolated browsers" },
        { pr: "#15", text: "Adaptive settle, macro caps" },
        { pr: "#16", text: "script_first arm" },
        { pr: "#17", text: "script_first repair and Stagehand URL fix" },
      ],
      figures: [
        { value: "~7,075", label: "tokens, full snapshot on the fixture" },
        { value: "23", label: "tokens, compact diff on the same fixture" },
      ],
    },
    {
      id: "probe1",
      label: "Probe 1",
      title: "No-model proxy arms cannot do open tasks",
      body: "Proxy arms with no outer model: neither finished a task.",
      figures: [
        { value: "1/3", label: "Playwright MCP, 417.5s, $1.31" },
        { value: "1/3", label: "Stagehand, 33.5s, $0.10" },
        { value: "0/3", label: "diff_fast_act" },
        { value: "0/3", label: "macro_replay" },
      ],
    },
    {
      id: "pr14",
      label: "Probe on PR #14",
      title: "Outer Claude makes every proxy arm pass",
      body: "Sonnet 4.6 drives the arms. Success is 3/3, but plain Playwright MCP is still the fastest per success.",
      figures: [
        { value: "9.5s", label: "Playwright MCP, 3/3, $0.29" },
        { value: "16.7s", label: "diff_fast_act, 3/3, $0.27" },
        { value: "25.5s", label: "macro_replay, 3/3, $0.55" },
        { value: "1/3", label: "Stagehand (scoring bug)" },
      ],
    },
    {
      id: "pr15",
      label: "Probe on PR #15",
      title: "Design stop on proxy speed tuning",
      body: "Adaptive settle and macro caps did not beat plain Playwright MCP. No more settle, macro, or replay PRs.",
      figures: [
        { value: "14.7s", label: "Playwright MCP, 3/3" },
        { value: "19.5s", label: "macro_replay, 3/3" },
        { value: "29.9s", label: "diff_fast_act, 3/3" },
        { value: "31.7s", label: "Stagehand, 1/3" },
      ],
      tone: "stop",
    },
    {
      id: "pr16",
      label: "Probe on PR #16",
      title: "The move to script_first",
      body: "One Claude call writes a short Playwright script for the whole task. Sonnet 5.5 from here on.",
      figures: [
        { value: "2.5s", label: "Stagehand, 2/3, $0.053" },
        { value: "3.8s", label: "Playwright MCP, 3/3, $0.150" },
        { value: "4.1s", label: "script_first, 1/3, $0.031" },
      ],
    },
    {
      id: "pr17",
      label: "Probe on PR #17",
      title: "One repair call: script_first reaches 3/3",
      body: "If the end-state check fails, Claude gets one repair call. The Stagehand URL fix lands too.",
      figures: [
        { value: "3.06s", label: "Playwright MCP, 3/3, $0.167" },
        { value: "4.56s", label: "script_first, 3/3, $0.042" },
        { value: "15.52s", label: "Stagehand, 3/3, $0.103" },
      ],
      tone: "now",
    },
    {
      id: "next",
      label: "Next",
      title: "Raise the one-shot rate",
      body: "In progress. Fewer repair calls, so script_first spends less time on its second pass.",
      figures: [],
    },
  ] satisfies TimelineEntry[],
  demos: [
    {
      id: "playwright_mcp",
      name: "Plain Playwright MCP",
      arms: ["playwright_mcp"],
      oneLine: "The outer model calls one browser tool, reads the whole page, then decides again.",
      steps: [
        { lane: "model", title: "Read the task", detail: "Outer Claude gets the task and the Playwright MCP tool list.", counts: "model" },
        { lane: "tool", title: "browser_navigate", detail: "Playwright MCP opens the start URL in Chrome.", counts: "browser" },
        { lane: "browser", title: "Full page snapshot", detail: "The whole accessibility tree goes back to the model. On the PR #12 fixture that was ~7,075 tokens." },
        { lane: "model", title: "Pick the next tool", detail: "Claude reads the snapshot and chooses one click or type.", counts: "model", repeats: true },
        { lane: "tool", title: "browser_type / browser_click", detail: "One action in Chrome.", counts: "browser", repeats: true },
        { lane: "browser", title: "Another full snapshot", detail: "The page is sent back again. In M0, one arXiv page (~130k tokens) resent every step cost about $9.", repeats: true },
        { lane: "model", title: "Answer and stop", detail: "Claude decides the task is done.", counts: "model" },
        { lane: "check", title: "End-state check", detail: "The harness checks the final page." },
      ],
      takeaway: "One outer model turn per page step. In M0 that was 36 steps over 5 tasks, with 87% of the time in the model.",
    },
    {
      id: "proxy",
      name: "Speed-layer proxy",
      arms: ["diff_fast_act", "macro_replay"],
      oneLine: "The same outer loop, with a proxy that settles the page and returns only what changed.",
      steps: [
        { lane: "model", title: "Read the task", detail: "Outer Claude gets the task and the proxy tools.", counts: "model" },
        { lane: "tool", title: "fast_act", detail: "The Python proxy over @playwright/mcp acts and waits for the page in one call.", counts: "browser" },
        { lane: "browser", title: "Settle", detail: "A 500ms settle (PR #13), then adaptive settle (PR #15)." },
        { lane: "tool", title: "Compact diff", detail: "Only the change goes back: 23 tokens on the PR #12 fixture, against ~7,075 for a full snapshot." },
        { lane: "model", title: "Pick the next action", detail: "Claude still reads and decides once per step.", counts: "model", repeats: true },
        { lane: "tool", title: "do_task_segment or replay", detail: "A macro runs several actions, or the replay cache runs learned actions with no model. Macros are capped (PR #15).", counts: "browser", repeats: true },
        { lane: "model", title: "Answer and stop", detail: "Claude decides the task is done.", counts: "model" },
        { lane: "check", title: "End-state check", detail: "The harness checks the final page." },
      ],
      takeaway: "Smaller replies did not remove outer model turns. Plain Playwright MCP stayed faster, so proxy speed tuning stopped after PR #15.",
    },
    {
      id: "script_first",
      name: "Script first",
      arms: ["script_first"],
      oneLine: "One Claude call writes the whole task as a short Playwright script. Chrome runs it.",
      steps: [
        { lane: "model", title: "Write the script", detail: "One Claude call writes a short Playwright script for the whole task.", counts: "model" },
        { lane: "tool", title: "Run it", detail: "The harness runs the script in Chrome.", counts: "browser" },
        { lane: "browser", title: "Every action, no model", detail: "Search, open, read. No outer model call between actions." },
        { lane: "check", title: "End-state check", detail: "The harness checks the final page." },
        { lane: "model", title: "One repair", detail: "Only if the check fails: Claude sees the failure and rewrites the script once.", counts: "repair", branch: "repair" },
        { lane: "tool", title: "Run the repaired script", detail: "Chrome runs the second script.", counts: "browser", branch: "repair" },
        { lane: "check", title: "Check again", detail: "Pass, or the run fails.", branch: "repair" },
      ],
      takeaway: "Cheapest arm per run. The repair pass is why it is not yet the fastest, which is what the next PR targets.",
    },
    {
      id: "stagehand",
      name: "Stagehand",
      arms: ["stagehand"],
      oneLine: "The outer agent gives plain-language steps. Stagehand turns each one into a browser action.",
      steps: [
        { lane: "model", title: "Read the task", detail: "The agent plans the task in plain-language steps.", counts: "model" },
        { lane: "tool", title: "Stagehand act", detail: "One plain-language step goes to Stagehand." },
        { lane: "tool", title: "Resolve the element", detail: "Stagehand uses its own model call to find the control.", counts: "model", repeats: true },
        { lane: "browser", title: "Act in Chrome", detail: "Stagehand clicks or types.", counts: "browser", repeats: true },
        { lane: "model", title: "Next step", detail: "The agent sends the next instruction, or stops.", counts: "model", repeats: true },
        { lane: "check", title: "End-state check", detail: "The harness checks the final page." },
      ],
      takeaway: "The comparison bar. On WebVoyager 100 (LangChain), Stagehand v4 took ~10 steps against ~26 for Playwright MCP.",
    },
  ] satisfies DemoArm[],
  loop: {
    title: "The browser loop",
    body: "The runtime owns the loop. Each cycle reads the page tree, picks the cheapest tier that can decide, acts on a numbered control, and asserts the result.",
    stages: [
      { id: "observe", title: "Observe", detail: "Read the page tree: url, title, control refs." },
      { id: "decide", title: "Decide", detail: "No-model routing first, a cheap Nebius tier next, the Claude planner last." },
      { id: "act", title: "Act", detail: "goto, click ref, fill ref, press, scroll." },
      { id: "assert", title: "Assert", detail: "url, title, or text. A failed assertion runs one more cycle." },
    ],
    tiers: [
      { name: "direct", detail: "No model. A unique link or button already named in the task is clicked." },
      { name: "fast", detail: "One Nebius call on the short control list. No screenshot." },
      { name: "planner", detail: "Claude, when the page has no unique target, and on one retry." },
    ],
  },
  pathway: {
    intro: "Computer use is slow because each step re-sees the screen with a large model and holds the pointer. The product is a runtime that owns the loop. A plugin is a surface inside that runtime, not a wrapper around someone else's screenshot agent.",
    sections: [
      {
        title: "Recommendation",
        paragraphs: [
          "Own the loop. One frontier model writes a batch of steps. The executor acts on a numbered control from the page tree. In the browser the person's pointer stays put.",
          "Tools-only is how that loop can start, and it does not change an agent that keeps taking screenshots. Sitting under an existing screenshot agent shortens capture and leaves the slow model in the path.",
        ],
      },
      {
        title: "First build",
        paragraphs: [
          "Browser attach to the user's real Chrome, an action language (goto, click ref, fill ref, press, scroll, assert, extract), a direct matcher on role and name, one planner that emits a batch, assertions between batches, a fixed task set, and telemetry (tier, latency, success).",
          "Wait, until a trace shows the planner naming obvious buttons: a small vision grounder, skill replay, and a Windows surface. A plugin marketplace waits until a second surface exists.",
        ],
      },
      {
        title: "Still open",
        paragraphs: [
          "The clock lengths on the sheet are a scale model, not a measurement on this machine. The surface switch is still open: browser if the pointer should stay put, Windows desktop if the pain is Cursor on this PC.",
        ],
      },
      {
        title: "Do not build first",
        paragraphs: [
          "A standalone policy for when to call an agent, or which model to call, before the runtime exists. Those are the router inside the first build.",
        ],
      },
    ],
  },
};
