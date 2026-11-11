/**
 * Every number on /stats lives here. Source of truth: docs/TEST_RESULTS.md and the raw JSONL under
 * docs/results/2026-11-10/ on branch docs/test-results-2026-11-10 (PR #41, commit 3e8bed0), plus the
 * 11 Nov held-out files docs/results/heldout_*_20261111.jsonl (PR #47, tip 9442722) and the plain-rule
 * and Decisions files docs/results/rules_*.jsonl and decisions_*.jsonl (PR #49, head 6b59b52).
 * OpenAI rows were re-computed from the JSONL. Claude Sonnet rows come from TEST_RESULTS.md (their
 * JSONL files are gitignored and not in the repo). Do not add a number that was not measured.
 */

export type StatsArm = "script_first" | "playwright_mcp" | "stagehand" | "browser_use";

export const armOrder: StatsArm[] = ["script_first", "playwright_mcp", "stagehand", "browser_use"];

export const arms: Record<StatsArm, { name: string; role: string; what: string }> = {
  script_first: {
    name: "script_first",
    role: "Our approach",
    what: "The model writes one Playwright script for the whole task. The harness runs it and grades the end state. A warm pass can replay a cached script with no (or fewer) model calls.",
  },
  playwright_mcp: {
    name: "Playwright MCP",
    role: "Baseline",
    what: "Many small tool calls through Playwright MCP, with a model call between steps.",
  },
  stagehand: {
    name: "Stagehand",
    role: "Local imitation",
    what: "A local imitation of Stagehand's tool surface on Playwright (bench/stagehand_local.py). It is not the Stagehand library. It was cut from the 50-task comparison until the real library is run.",
  },
  browser_use: {
    name: "browser-use",
    role: "Competitor",
    what: "browser-use 1.0 driving local Chrome.",
  },
};

export const tunedTasks = [
  { id: "wv_wikipedia_search", label: "Wikipedia", text: "Search Wikipedia for “Ada Lovelace” and confirm the article page." },
  { id: "wv_python_docs", label: "Python docs", text: "Find the Python docs page for the heapq module." },
  { id: "wv_hackernews_top", label: "Hacker News", text: "Go to Hacker News and give the title of the top story." },
];

export const heldOutTasks = [
  "ho_mdn_array_map",
  "ho_github_rust",
  "ho_arxiv_attention",
  "ho_wiki_eiffel_city",
  "ho_nodejs_fs_docs",
  "ho_httpbin_customer_form",
  "ho_pypi_requests",
  "ho_rust_book_borrowing",
  "ho_w3c_selectors_4",
  "ho_iana_status_451",
  "ho_rfc9110_get_section",
  "ho_schema_person",
  "ho_cppreference_vector",
  "ho_sqlite_vacuum",
  "ho_k8s_pod",
];

export type SonnetRow = {
  arm: StatsArm;
  pass: number;
  of: number;
  mean: number;
  median: number;
  note: string;
};

export type SonnetProbe = {
  id: string;
  title: string;
  tip: string;
  spendUsd: number;
  fair: boolean;
  summary: string;
  rows: SonnetRow[];
  warm: { pass: number; of: number; mean: number; median: number };
};

export const sonnetProbes: SonnetProbe[] = [
  {
    id: "pr27",
    title: "PR #27 re-probe",
    tip: "3409e8a — Grade script_first on the page body the script left.",
    spendUsd: 3.1459,
    fair: true,
    summary:
      "The best like-for-like Sonnet 5.5 result. script_first passed all 18 and was fastest on mean and median.",
    rows: [
      { arm: "script_first", pass: 18, of: 18, mean: 3.18, median: 2.98, note: "No failures. 17 one-shot scripts, one 2-step repair." },
      { arm: "playwright_mcp", pass: 17, of: 18, mean: 5.25, median: 4.03, note: "Failed Hacker News: answer is not the marked value." },
      { arm: "browser_use", pass: 17, of: 18, mean: 6.03, median: 4.95, note: "Failed Hacker News: answer is not the marked value." },
      { arm: "stagehand", pass: 16, of: 18, mean: 12.54, median: 6.69, note: "Failed Hacker News (not the marked value) and Eiffel city (missing text “Paris”)." },
    ],
    warm: { pass: 18, of: 18, mean: 1.81, median: 1.46 },
  },
  {
    id: "pr23",
    title: "PR #23 fair-grading re-probe",
    tip: "2e827a6 — Grade every arm by one fail-closed rule.",
    spendUsd: 2.9924,
    fair: true,
    summary: "First run on the shared fail-closed grader. browser-use passed all 18; script_first missed two.",
    rows: [
      { arm: "script_first", pass: 16, of: 18, mean: 3.52, median: 2.92, note: "Failed Eiffel city (missing “Paris”) and RFC 9110 GET section (model ended without completing)." },
      { arm: "browser_use", pass: 18, of: 18, mean: 5.41, median: 4.81, note: "No failures." },
      { arm: "playwright_mcp", pass: 17, of: 18, mean: 6.1, median: 3.77, note: "Failed Hacker News: empty answer." },
      { arm: "stagehand", pass: 16, of: 18, mean: 12.55, median: 7.23, note: "Failed Hacker News (empty answer) and Eiffel city (missing “Paris”)." },
    ],
    warm: { pass: 16, of: 18, mean: 1.48, median: 1.26 },
  },
  {
    id: "pr18",
    title: "PR #18 honest probe",
    tip: "Before the shared grader.",
    spendUsd: 3.2448,
    fair: false,
    summary:
      "Historical only. Hacker News was graded unevenly: three arms passed it with no deterministic check while browser-use failed it for the same reason.",
    rows: [
      { arm: "script_first", pass: 17, of: 18, mean: 2.85, median: 2.81, note: "Failed RFC 9110 GET section (model ended without completing). 17 one-shot, one 2-step repair." },
      { arm: "browser_use", pass: 17, of: 18, mean: 4.76, median: 4.39, note: "Failed Hacker News: no deterministic check, LLM judge not called." },
      { arm: "playwright_mcp", pass: 18, of: 18, mean: 5.71, median: 3.86, note: "No failures recorded." },
      { arm: "stagehand", pass: 17, of: 18, mean: 13.42, median: 5.75, note: "Failed Eiffel city (missing “Paris”)." },
    ],
    warm: { pass: 17, of: 18, mean: 1.8, median: 1.22 },
  },
];

export type Cell = { pass: boolean; s: number; usd: number };

/** Effort sweep: one Wikipedia task per cell. From probe_20261110_214520.jsonl. */
export const sweep: { model: "gpt-6-luna" | "gpt-6.1-sol"; effort: string; cells: Record<StatsArm, Cell> }[] = [
  { model: "gpt-6-luna", effort: "low", cells: { script_first: { pass: true, s: 3.02, usd: 0.00013 }, playwright_mcp: { pass: true, s: 9.93, usd: 0.000426 }, stagehand: { pass: false, s: 137.03, usd: 0.000659 }, browser_use: { pass: true, s: 10.9, usd: 0.000549 } } },
  { model: "gpt-6-luna", effort: "medium", cells: { script_first: { pass: true, s: 6.35, usd: 0.000129 }, playwright_mcp: { pass: true, s: 8.77, usd: 0.000927 }, stagehand: { pass: true, s: 75.54, usd: 0.000939 }, browser_use: { pass: true, s: 11.53, usd: 0.000615 } } },
  { model: "gpt-6-luna", effort: "high", cells: { script_first: { pass: true, s: 4.06, usd: 0.000166 }, playwright_mcp: { pass: true, s: 18.15, usd: 0.000822 }, stagehand: { pass: true, s: 50.92, usd: 0.00113 }, browser_use: { pass: true, s: 35.89, usd: 0.001349 } } },
  { model: "gpt-6-luna", effort: "xhigh", cells: { script_first: { pass: true, s: 4.36, usd: 0.000184 }, playwright_mcp: { pass: true, s: 8.54, usd: 0.000937 }, stagehand: { pass: true, s: 77.94, usd: 0.002056 }, browser_use: { pass: true, s: 14.11, usd: 0.000753 } } },
  { model: "gpt-6.1-sol", effort: "low", cells: { script_first: { pass: true, s: 3.44, usd: 0.00262 }, playwright_mcp: { pass: true, s: 12.01, usd: 0.01186 }, stagehand: { pass: true, s: 41.46, usd: 0.012407 }, browser_use: { pass: true, s: 11.59, usd: 0.015055 } } },
  { model: "gpt-6.1-sol", effort: "medium", cells: { script_first: { pass: true, s: 3.64, usd: 0.00253 }, playwright_mcp: { pass: true, s: 16.15, usd: 0.011946 }, stagehand: { pass: true, s: 74.26, usd: 0.015489 }, browser_use: { pass: true, s: 10.88, usd: 0.01202 } } },
  { model: "gpt-6.1-sol", effort: "high", cells: { script_first: { pass: true, s: 3.54, usd: 0.00263 }, playwright_mcp: { pass: true, s: 11.69, usd: 0.011946 }, stagehand: { pass: true, s: 45.31, usd: 0.014258 }, browser_use: { pass: true, s: 11.73, usd: 0.014218 } } },
  { model: "gpt-6.1-sol", effort: "xhigh", cells: { script_first: { pass: true, s: 3.8, usd: 0.00261 }, playwright_mcp: { pass: true, s: 12.09, usd: 0.01186 }, stagehand: { pass: true, s: 9.46, usd: 0.010249 }, browser_use: { pass: true, s: 9.66, usd: 0.011602 } } },
];

/** Per-arm sweep totals. Mean/median are per successful cell; usd sums all 8 cells. */
export const sweepTotals: Record<StatsArm, { pass: number; of: number; mean: number; median: number; usd: number }> = {
  script_first: { pass: 8, of: 8, mean: 4.03, median: 3.72, usd: 0.010999 },
  playwright_mcp: { pass: 8, of: 8, mean: 12.17, median: 11.85, usd: 0.050724 },
  stagehand: { pass: 7, of: 8, mean: 53.56, median: 50.92, usd: 0.057187 },
  browser_use: { pass: 8, of: 8, mean: 14.54, median: 11.56, usd: 0.056161 },
};

export type MediumRun = {
  model: string;
  file: string;
  runUsd: number;
  totals: Record<StatsArm, { pass: number; of: number; mean: number; median: number }>;
  tasks: { task: string; cells: Record<StatsArm, Cell & { answer: string }> }[];
};

export const mediumRuns: MediumRun[] = [
  {
    model: "gpt-6.1-sol",
    file: "probe_20261110_215922.jsonl",
    runUsd: 0.0961,
    totals: {
      script_first: { pass: 3, of: 3, mean: 3.4, median: 3.41 },
      playwright_mcp: { pass: 2, of: 3, mean: 9.46, median: 9.46 },
      stagehand: { pass: 2, of: 3, mean: 40.24, median: 40.24 },
      browser_use: { pass: 2, of: 3, mean: 17.68, median: 17.68 },
    },
    tasks: [
      {
        task: "Wikipedia",
        cells: {
          script_first: { pass: true, s: 3.29, usd: 0.00263, answer: "“Confirmed: on the Ada Lovelace article page on Wikipedia.”" },
          playwright_mcp: { pass: true, s: 11.94, usd: 0.005099, answer: "Sentence confirming the article" },
          stagehand: { pass: true, s: 73.62, usd: 0.015789, answer: "Sentence confirming the article" },
          browser_use: { pass: true, s: 12.77, usd: 0.010666, answer: "Sentence confirming the article" },
        },
      },
      {
        task: "Python docs",
        cells: {
          script_first: { pass: true, s: 3.41, usd: 0.002428, answer: "The heapq docs URL" },
          playwright_mcp: { pass: true, s: 6.97, usd: 0.00487, answer: "Empty (URL check passed)" },
          stagehand: { pass: true, s: 6.85, usd: 0.010559, answer: "Empty (URL check passed)" },
          browser_use: { pass: true, s: 22.58, usd: 0.018456, answer: "Found the heapq docs page" },
        },
      },
      {
        task: "Hacker News",
        cells: {
          script_first: { pass: true, s: 3.48, usd: 0.002542, answer: "“.name Grandfathered”" },
          playwright_mcp: { pass: false, s: 9.22, usd: 0.004039, answer: "Right title, wrapped in a sentence" },
          stagehand: { pass: false, s: 8.86, usd: 0.010952, answer: "Right title, wrapped in a sentence" },
          browser_use: { pass: false, s: 10.32, usd: 0.008069, answer: "Right title, in a sentence with markdown and a URL" },
        },
      },
    ],
  },
  {
    model: "gpt-6-luna",
    file: "probe_20261110_220242.jsonl",
    runUsd: 0.0079,
    totals: {
      script_first: { pass: 3, of: 3, mean: 4.53, median: 4.08 },
      playwright_mcp: { pass: 2, of: 3, mean: 10.23, median: 10.23 },
      stagehand: { pass: 2, of: 3, mean: 10.41, median: 10.41 },
      browser_use: { pass: 2, of: 3, mean: 16.59, median: 16.59 },
    },
    tasks: [
      {
        task: "Wikipedia",
        cells: {
          script_first: { pass: true, s: 3.79, usd: 0.000127, answer: "“Ada Lovelace - Wikipedia”" },
          playwright_mcp: { pass: true, s: 13.12, usd: 0.000331, answer: "Sentence confirming the article" },
          stagehand: { pass: true, s: 11.11, usd: 0.000742, answer: "Sentence confirming the article" },
          browser_use: { pass: true, s: 16.08, usd: 0.001077, answer: "JSON with url, title, heading" },
        },
      },
      {
        task: "Python docs",
        cells: {
          script_first: { pass: true, s: 5.71, usd: 0.000138, answer: "“heapq — Heap queue algorithm”" },
          playwright_mcp: { pass: true, s: 7.34, usd: 0.000432, answer: "Empty (URL check passed)" },
          stagehand: { pass: true, s: 9.71, usd: 0.000876, answer: "Sentence with the heapq URL" },
          browser_use: { pass: true, s: 17.1, usd: 0.000735, answer: "Found the heapq docs page" },
        },
      },
      {
        task: "Hacker News",
        cells: {
          script_first: { pass: true, s: 4.08, usd: 0.000126, answer: "“.name Grandfathered”" },
          playwright_mcp: { pass: false, s: 6.9, usd: 0.000271, answer: "Empty answer" },
          stagehand: { pass: false, s: 43.63, usd: 0.002661, answer: "Empty answer after 11 model calls" },
          browser_use: { pass: false, s: 5.38, usd: 0.000353, answer: "Right title, wrapped in a sentence" },
        },
      },
    ],
  },
];

export const ledgers = {
  claude: { used: 26.022488, cap: 50, abortAt: 40 },
  // 1.338349 after the 10 Nov runs, +1.695 for the 50-task held-out runs, +0.0727 and +0.112 for the Decisions rounds.
  openai: { used: 3.218456, cap: 20, perRun: 5, beforeHeldOut: 1.338349, heldOut: 1.695, experiments: 0.185 },
};

export const notExplored: { title: string; body: string; where?: string }[] = [
  {
    title: "A harder, fairer held-out set",
    body: "About 19 of the 50 held-out tasks have a final URL that can be guessed from the task text. There are no multi-step or single-page-app tasks yet. Replace some with tasks whose answer cannot be guessed.",
    where: "PR #45, PR #48",
  },
  {
    title: "Claude on the 50-task held-out set",
    body: "The held-out numbers are OpenAI only. A three-arm run on Claude Sonnet 5.5 uses the Claude API budget and has not been started.",
  },
  {
    title: "The real Stagehand library",
    body: "Every Stagehand row here comes from a local imitation of its tool surface. The library itself has not been run.",
  },
  {
    title: "Repeats for every arm and model",
    body: "script_first on Luna now has three repeats per setting. The held-out runs for Sol, Playwright MCP and browser-use are one run each, so they have no error bars. The same code swung by about five tasks between identical runs.",
  },
  {
    title: "Warm replay on OpenAI",
    body: "The cached-script replay that gave Sonnet a 1.46s median is refused on the OpenAI path. OpenAI numbers are cold only.",
  },
  {
    title: "The newer script_first speed-ups, alone",
    body: "Starting Chrome while the model writes (PR #30), caching the stable prompt (PR #29) and skipping a second page read (PR #40) are in the tip the held-out runs used. Their effect on its own has not been measured.",
    where: "PR #29, PR #30, PR #40",
  },
  {
    title: "Desktop computer use",
    body: "The desktop arm is written down so it cannot mix into script_first. It has no measured runs on this page.",
    where: "PR #31",
  },
];

// ---------------------------------------------------------------------------------------------
// 11 Nov 2026: held-out run, plain self-check rules, Decisions API experiment
// ---------------------------------------------------------------------------------------------

export type HeldOutArm = "script_first" | "playwright_mcp" | "browser_use";
export const heldOutArms: HeldOutArm[] = ["script_first", "playwright_mcp", "browser_use"];

export type HeldOutRow = { pass: number; of: number; median: number; medianPass: number; usd: number };

/** 50 held-out tasks, OpenAI medium effort, one run per task, no answer key in script_first's run. Median is over all 50 rows. */
export const heldOut: {
  model: "gpt-6-luna" | "gpt-6.1-sol";
  file: string;
  rows: Record<HeldOutArm, HeldOutRow>;
  /** Why script_first failed. Sums to its failure count. */
  scriptFirstFailures: { reason: string; n: number }[];
}[] = [
  {
    model: "gpt-6.1-sol",
    file: "heldout_sol_medium_20261111.jsonl",
    rows: {
      script_first: { pass: 37, of: 50, median: 4.15, medianPass: 3.74, usd: 0.241 },
      playwright_mcp: { pass: 38, of: 50, median: 13.79, medianPass: 13.63, usd: 0.501 },
      browser_use: { pass: 41, of: 50, median: 13.81, medianPass: 13.62, usd: 0.714 },
    },
    scriptFirstFailures: [
      { reason: "Ended on the wrong page", n: 4 },
      { reason: "Returned evidence not on the page", n: 4 },
      { reason: "Answer or claimed URL wrong", n: 3 },
      { reason: "Model ended without finishing", n: 1 },
      { reason: "Script error", n: 1 },
    ],
  },
  {
    model: "gpt-6-luna",
    file: "heldout_luna_medium_20261111.jsonl",
    rows: {
      script_first: { pass: 27, of: 50, median: 5.98, medianPass: 5.16, usd: 0.018 },
      playwright_mcp: { pass: 28, of: 50, median: 12.98, medianPass: 12.34, usd: 0.088 },
      browser_use: { pass: 40, of: 50, median: 20.33, medianPass: 18.73, usd: 0.059 },
    },
    scriptFirstFailures: [
      { reason: "Model ended without finishing", n: 10 },
      { reason: "Ended on the wrong page", n: 6 },
      { reason: "Answer or claimed URL wrong", n: 4 },
      { reason: "Returned evidence not on the page", n: 2 },
      { reason: "Script error", n: 1 },
    ],
  },
];

export type SelfCheckRun = { label: string; pass: number; median: number; usd: number };

/** script_first on Luna medium, the same 50 held-out tasks, one process per run. Median is over all 50 rows. */
export const selfCheckGroups: { id: string; title: string; note: string; runs: SelfCheckRun[] }[] = [
  {
    id: "before",
    title: "Before: the tip's string check",
    note: "Three runs of the same code (the Decisions check off or only watching).",
    runs: [
      { label: "Run 1", pass: 27, median: 5.98, usd: 0.0181 },
      { label: "Run 2", pass: 30, median: 4.48, usd: 0.0186 },
      { label: "Run 3", pass: 28, median: 5.87, usd: 0.0301 },
    ],
  },
  {
    id: "rules",
    title: "After: two plain rules (PR #50)",
    note: "No model call. The check accepts an answer that is the page's own URL, or that appears in the page title or main heading.",
    runs: [
      { label: "Run 1", pass: 31, median: 4.71, usd: 0.0153 },
      { label: "Run 2", pass: 36, median: 5.28, usd: 0.0148 },
      { label: "Run 3", pass: 31, median: 4.05, usd: 0.0155 },
    ],
  },
  {
    id: "decisions",
    title: "Plain rules + Decisions API check (PR #49)",
    note: "Asks OpenAI's Decisions API before a repair turn. Cost includes about $0.008 a run for the Decisions calls.",
    runs: [
      { label: "Run 1", pass: 29, median: 5.19, usd: 0.0238 },
      { label: "Run 2", pass: 35, median: 4.01, usd: 0.0217 },
      { label: "Run 3", pass: 37, median: 4.44, usd: 0.0208 },
    ],
  },
];

export const decisionsResult = {
  /** Plain rules: first self-check verdicts that passed because of a rule, across the three runs. */
  ruleFirstPasses: { urlRule: 15, titleRule: 5, gradedPass: 20 },
  /** First round, before the gate was narrowed. */
  firstRound: { overturns: 13, gradedPass: 9 },
  /** Three runs on top of the plain rules. */
  overturns: 9,
  overturnsGradedPass: 3,
  targetedRepairs: 14,
  targetedRepairsPassed: 1,
  calls: 149,
  medianMs: 299,
  maxMs: 911,
  barPct: 90,
};
