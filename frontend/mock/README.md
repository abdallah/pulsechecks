# Design/UX sandbox mode

Runs the real frontend against a fake in-memory backend, with no cloud
project, no OAuth, and no backend deployment required. Built for pairing
with a designer on UX — one command, one URL, every screen reachable.

## Run it

```bash
cd frontend
npm install   # first time only
npm run dev:mock
```

Open **http://localhost:3000**, click **"Continue with demo data"** on the
login screen. That's it — no credentials, no `.env` setup beyond what's
already checked in (`.env.mock`).

## What you get

A backend implemented as a Vite dev-server middleware (`mock/server.js`),
serving realistic, deliberately varied fixture data (`mock/data.js`) so
every state the UI can be in is reachable without hunting for it:

- Two teams (admin on one, member on the other)
- Checks in every status: **up**, **late**, **pending** (never pinged),
  **paused**, plus one **late check with zero alert channels** (the amber
  "alerts disabled" warning) and one currently **suppressed** check
- All alert channel types (Mattermost, webhook, email, Telegram, a shared
  channel), and alert delivery history in every state — delivered,
  retrying, and dead-lettered/failed
- 35 pings on one check so "Load more" has something to do
- Audit log, maintenance windows (past/active/future), reports,
  API tokens, a pending member invitation

Everything is interactive and stateful for the session: pause a check,
create a channel, invite a member — it sticks until you restart the dev
server. Nothing is persisted to disk and nothing leaves your machine.

## How it works

`vite --mode mock` loads `.env.mock` (`VITE_MOCK=true`,
`VITE_API_URL=http://localhost:3000`) and `vite.config.js` conditionally
adds the mock middleware, so the frontend and fake API share one origin —
no CORS, no second process to manage. `LoginPage` shows a demo-login
button only when `VITE_MOCK=true`; it writes a fake token straight to
`localStorage` and skips real OAuth entirely. The mock server accepts any
`Authorization` header without checking it.

None of this ships in `npm run build` / `npm run build:aws` /
`npm run build:gcp` — the plugin only loads in `mode === 'mock'`, and the
demo button only renders when `VITE_MOCK === 'true'`, which is never set
in a real build.

## Editing the fixtures

Everything lives in `mock/data.js` as one plain object (`state`) grouped
by team ID. Add a check, change a status, add more pings — no schema,
just edit and refresh. `mock/server.js` is a small hand-rolled router
(no framework) implementing every endpoint `src/lib/api.js` calls.
