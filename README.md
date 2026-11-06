# Computer-use optimisation

A progress page for this work: the current status, the history from the browser loop to script_first, step-through demos of how each arm runs a task, probe charts, and the loop and pathway.
Browser loop, separate from this page: `python -m loop demo` ([loop/README.md](loop/README.md)).

All of the copy and every probe number is hardcoded in [`data/progress.ts`](data/progress.ts). Edit that file to update the page.

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

- **Tom’s Vercel account.** The app is ready to build, and it is not linked to a Vercel project. A deploy has to be started by someone who can sign in to that account.
- **The remote is Origin, not GitHub.** There is no GitHub remote, so a Vercel Git integration (deploy on push) cannot be connected. Use the CLI above, or mirror the repo to GitHub, GitLab, or Bitbucket first.
