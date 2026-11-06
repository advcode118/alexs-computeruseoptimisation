# Computer-use optimisation

A dark-mode progress page for this work: the current bottleneck, what to do next, the four tracks, and what is still missing.

All of the copy is hardcoded in [`data/progress.ts`](data/progress.ts). Edit that file to update the page.

## Run locally

Node.js 20 or newer.

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

To check the production build:

```bash
npm run build
npm start
```

## Deploy on Vercel

This is a standard Next.js App Router app. It has no environment variables and no custom output directory.

If Vercel asks for settings:

| Setting | Value |
| --- | --- |
| Framework preset | Next.js |
| Root directory | repository root |
| Install command | `npm install` |
| Build command | `npm run build` |
| Output directory | leave empty (Next.js default) |

### CLI

The git remote for this repo is Origin (Cursor), not GitHub, GitLab, or Bitbucket. Vercel’s Git import will not see it. Deploy from a checkout with the Vercel CLI, signed into Tom’s Vercel account:

```bash
npx vercel login
npx vercel
npx vercel --prod
```

`npx vercel` links the directory and deploys a preview. `npx vercel --prod` deploys production.

### What still blocks a deploy

- **Tom’s Vercel account.** The app is ready to build. A deploy has to be started by someone who can sign in to that account (CLI above), or via a Vercel Git integration on this GitHub repo once linked.

## Computer-use loop (from Cursor Origin)

The Python agent stack lives beside this site (synced from Origin tip through PR #17 / script-first repair):

- `loop/` — local observe/decide/act loop + MCP server
- `bench/` — competitive probe harness (playwright_mcp, script_first, stagehand, …)
- `proxy/`, `backends/`, `core/`, `tests/`

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m loop demo
# or: ANTHROPIC_API_KEY=… python -m bench.probe --execute --arms playwright_mcp,script_first,stagehand
```

Cursor Origin remains the day-to-day forge for open stack PRs; this GitHub repo mirrors the progress site plus the current tip tree for visibility and Vercel.
