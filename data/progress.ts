import type { ArmId } from "@/data/format";

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
  id: ArmId;
  name: string;
  arms: ArmId[];
  oneLine: string;
  steps: DemoStep[];
  takeaway: string;
};

export const armMeta: Record<ArmId, { name: string; short: string; color: string }> = {
  script_first: { name: "script_first", short: "script_first", color: "var(--color-yours)" },
  playwright_mcp: { name: "Playwright MCP", short: "Playwright MCP", color: "var(--color-arm-mcp)" },
  browser_use: { name: "browser-use", short: "browser-use", color: "var(--color-stop)" },
};

export const progress = {
  project: "Our approach",
  links: [{ label: "GitHub", href: "https://github.com/advcode118/alexs-computeruseoptimisation" }],
  asOf: "11 November 2026",
  sourceFile: "data/measured.json",
  pitch: {
    kicker: "script_first, our approach",
    headline: "One model call writes the whole browser task.",
    line: "Chrome runs the script. No model between clicks. If the check fails, the model gets one repair.",
    proof: [
      { value: "1", label: "model call writes the script", compare: "Chrome runs every action in between" },
      { value: "50", label: "held-out tasks", compare: "The same set for both models and all three arms" },
      { value: "2", label: "models, cold, medium", compare: "gpt-6-luna and gpt-6.1-sol, one run each" },
    ],
    steps: [
      {
        title: "The model writes the script",
        body: "One call. The model writes a short Playwright script for the whole task.",
        tag: "1 model call",
      },
      {
        title: "Chrome runs it",
        body: "The harness runs the script in Chrome. Search, open, read. No model call between actions.",
        tag: "0 model calls",
      },
      {
        title: "Check, repair once",
        body: "The harness checks the final page. A failed check sends the failure back, and the model rewrites the script once.",
        tag: "At most 1 repair",
      },
    ],
    stepsNote: "The walk-through is an illustration of that shape. Wall time, passes and call counts from the saved runs are on the stats page.",
  },
  demos: [
    {
      id: "script_first",
      name: "script_first",
      arms: ["script_first"],
      oneLine: "One model call writes the whole task as a short Playwright script. Chrome runs it.",
      steps: [
        { lane: "model", title: "Write the script", detail: "One model call writes a short Playwright script for the whole task.", counts: "model" },
        { lane: "tool", title: "Run it", detail: "The harness runs the script in Chrome.", counts: "browser" },
        { lane: "browser", title: "Every action, no model", detail: "Search, open, read. No model call between actions." },
        { lane: "check", title: "End-state check", detail: "The harness checks the final page against the live URL, title and text." },
        {
          lane: "model",
          title: "One repair",
          detail: "When the check fails, the model sees the failure and rewrites the script once.",
          counts: "repair",
          branch: "repair",
        },
        { lane: "tool", title: "Run the repaired script", detail: "Chrome runs the second script.", counts: "browser", branch: "repair" },
        { lane: "check", title: "Check again", detail: "Pass, or the run fails.", branch: "repair" },
      ],
      takeaway: "Our approach. The measured runs on the stats page are cold: each task starts without a cached script.",
    },
    {
      id: "playwright_mcp",
      name: "Plain Playwright MCP",
      arms: ["playwright_mcp"],
      oneLine: "The model calls one browser tool, reads the page, then decides again.",
      steps: [
        { lane: "model", title: "Read the task", detail: "The model gets the task and the Playwright MCP tool list.", counts: "model" },
        { lane: "tool", title: "Open the page", detail: "Playwright MCP opens the start URL in Chrome.", counts: "browser" },
        { lane: "browser", title: "Page snapshot", detail: "The page comes back to the model." },
        { lane: "model", title: "Pick the next tool", detail: "The model reads the snapshot and chooses one click or type.", counts: "model", repeats: true },
        { lane: "tool", title: "One action", detail: "One click or type in Chrome.", counts: "browser", repeats: true },
        { lane: "browser", title: "Another snapshot", detail: "The page is sent back again.", repeats: true },
        { lane: "model", title: "Answer and stop", detail: "The model decides the task is done.", counts: "model" },
        { lane: "check", title: "End-state check", detail: "The harness grades the final page with the same rule as the other arms." },
      ],
      takeaway: "A model turn between page steps. The stats page has the step and model-call counts from the saved rows.",
    },
    {
      id: "browser_use",
      name: "browser-use",
      arms: ["browser_use"],
      oneLine: "browser-use 1.0 drives local Chrome, with the model in the loop between actions.",
      steps: [
        { lane: "model", title: "Read the task", detail: "browser-use gets the task and plans the next action.", counts: "model" },
        { lane: "tool", title: "Act in Chrome", detail: "One action runs in local Chrome.", counts: "browser" },
        { lane: "browser", title: "Page comes back", detail: "The new page is the input for the next decision.", repeats: true },
        { lane: "model", title: "Next action", detail: "The model chooses another action, or stops.", counts: "model", repeats: true },
        { lane: "check", title: "End-state check", detail: "The harness grades the final page with the same rule as the other arms." },
      ],
      takeaway: "Illustrated shape of the competitor arm. The pass counts and wall times are the saved rows, on the stats page.",
    },
  ] satisfies DemoArm[],
};
