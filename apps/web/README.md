# GigBid web

The browser app for GigBid. React, Vite, TypeScript (strict) and React Router. The API client is generated from the FastAPI OpenAPI schema.

## Run it

```bash
cd apps/web
npm install
npm run dev        # http://localhost:5173, proxies /api to http://localhost:8000
```

Start the API first (FastAPI on port 8000). To call an API on another host, set `VITE_API_URL` (for example `VITE_API_URL=http://localhost:8000 npm run dev`). By default the app uses relative `/api` URLs.

## Build

```bash
npm run build      # type check (tsc) then vite build into dist/
npm run preview
```

## Typed API client

```bash
npm run gen:api    # openapi-typescript ../api/openapi.json -o src/lib/api/schema.d.ts
```

Run it again whenever `apps/api/openapi.json` changes. `src/lib/api/schema.d.ts` is generated, do not edit it by hand. `src/lib/api/client.ts` creates the openapi-fetch client (cookie session, plus an in-memory Bearer token as a fallback), and `src/lib/api/endpoints.ts` has one small function per endpoint. The OpenAPI schema types some responses as plain objects, so their shapes are written in `src/lib/types.ts`.

## Tests

```bash
npx playwright install chromium   # once
npx playwright test               # starts npm run dev by itself
npx playwright show-report        # open the HTML report (playwright-report/)
```

The specs in `tests/e2e/` mock every `/api/` call with `page.route`, so they need no backend and no model. Fixtures are in `tests/e2e/fixtures.ts`.

## Docker

From the repository root:

```bash
docker build -f infra/docker/web.Dockerfile -t gigbid-web .
```

nginx serves `dist/`, falls back to `index.html` for app routes and proxies `/api/` to `http://api:8000` with buffering off, so the live run stream works.

## Screens

| Route | Screen |
| --- | --- |
| `/sign-in` | Sign in or create an account |
| `/onboarding` | Persona, rates, filters, budget, connected accounts, portfolio upload |
| `/` | Job inbox |
| `/jobs/:jobId` | Job detail |
| `/approvals` | All pending approvals |
| `/studio/:threadId` | Proposal studio |
| `/pipeline` | Pipeline board |
| `/messages`, `/messages/:threadId` | Client messages and reply approval |
| `/runs/:threadId` | Live agent run viewer |
| `/analytics` | Analytics |
| `/settings` | Settings, accounts, memory |

Pending approvals are always read from the API, so a page refresh never loses one.
