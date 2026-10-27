/**
 * All progress copy lives here. Edit this file to update the site.
 */

export type TrackStatus = "in_progress" | "not_started";

export type ProgressTrack = {
  index: string;
  title: string;
  status: TrackStatus;
  statusLabel: string;
  summary: string;
};

export type MissingItem = {
  title: string;
  detail: string;
};

export const progress = {
  project: "Computer-use optimisation",
  asOf: "27 October 2026",
  sourceFile: "data/progress.ts",
  headline: "Stuck on\nagent calls.",
  dek: "Two levers: when an agent must be called, and which agent is called.",
  next: {
    id: "next",
    kicker: "What to do next",
    aside: "Before tracks 2 and 3",
    title: "Get a baseline before changing the call policy.",
    body: "There is no log of current agent calls, and no computer-use agent code in this repo. Changing when an agent is called, or which agent is called, would be a guess.",
    steps: [
      {
        label: "Score",
        text: "Use wait time and cost. That stands until Tom says otherwise.",
      },
      {
        label: "Land the code",
        text: "Put the computer-use agent in this repo. Call-policy work cannot start without it.",
      },
      {
        label: "Then log",
        text: "Log each call before changing when an agent runs, or which agent runs.",
      },
    ],
  },
  bottleneck: {
    id: "bottleneck",
    kicker: "Current bottleneck",
    title: "Agent calls",
    body: "The work is limited by agent calls. Both levers are still untouched.",
    levers: [
      {
        index: "01",
        title: "When an agent must be called",
        detail: "The condition that justifies a call. Not started.",
      },
      {
        index: "02",
        title: "Which agent is called",
        detail: "The choice of agent once a call is justified. Not started.",
      },
    ],
  },
  tracks: {
    id: "tracks",
    kicker: "Tracks",
    title: "Four tracks",
    items: [
      {
        index: "01",
        title: "Progress site",
        status: "in_progress",
        statusLabel: "In progress",
        summary: "This site. The bottleneck, the tracks, and what is still missing, in one place.",
      },
      {
        index: "02",
        title: "When to call an agent",
        status: "not_started",
        statusLabel: "Not started",
        summary: "Decide when an agent must be called.",
      },
      {
        index: "03",
        title: "Which agent to call",
        status: "not_started",
        statusLabel: "Not started",
        summary: "Decide which agent is called.",
      },
      {
        index: "04",
        title: "Measurement",
        status: "not_started",
        statusLabel: "Not started",
        summary: "Log calls so we can tell if the other two changes help.",
      },
    ] satisfies ProgressTrack[],
  },
  missing: {
    id: "missing",
    kicker: "What's missing",
    title: "What's missing",
    items: [
      {
        title: "No baseline of current agent calls",
        detail: "Nothing is logged, so there is no before to compare against.",
      },
      {
        title: "No success number chosen yet",
        detail: "Default until Tom says otherwise: wait time and cost.",
      },
      {
        title: "No computer-use agent code in the repo yet",
        detail: "The call-policy work cannot start from code.",
      },
      {
        title: "Vercel deploy still needs Tom's Vercel account",
        detail: "The app can be deployed. It is not linked to a Vercel project.",
      },
      {
        title: "The git remote is Origin, not GitHub",
        detail: "The remote is Origin (Cursor). There is no GitHub remote.",
      },
    ] satisfies MissingItem[],
  },
};
