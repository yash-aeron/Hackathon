# Scoutly frontend

Next.js 16 (App Router) client for Scoutly. The full product docs — screens, architecture,
matching and verification logic, API reference and demo script — live in the
[root README](../README.md).

## Run

```bash
npm install
npm run dev      # http://localhost:3000
```

The backend must be running at `http://localhost:8000` (see the root README). Point the
client elsewhere with `NEXT_PUBLIC_API_URL` in `.env.local`; copy `.env.local.example` to
start.

## Routes

| Route | Purpose |
|---|---|
| `/` | Resume upload / paste, editable extracted profile, readiness checklist |
| `/matches` | Ranked opportunities with trust badges, "why this fits", calendar selection |
| `/kit/[id]` | Gap analysis, roadmap, resume bullets and cover note for one listing |

## Checks

```bash
npx tsc --noEmit
npm run lint
npm run build
```

## Layout

```
app/                 routes (/, /matches, /kit/[id])
components/          home, matches, kit and shared UI
lib/                 API client, profile store, types, design tokens
```

The API client lives in `lib/api.ts`; profile state is kept in `localStorage` so the
matches and kit screens always see the latest edits.
