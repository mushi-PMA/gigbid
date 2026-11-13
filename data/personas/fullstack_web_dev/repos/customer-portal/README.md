# customer-portal

Customer portal with single sign-on and claims forms.

Stack: React, Node.js, PostgreSQL.

## What is in here

- `.github/workflows/ci.yml`
- `Dockerfile`
- `server/routes/claims.ts`

## Notes

- Uses React.
- Implemented in Node.js.
- A JSON API that both web and mobile clients call, with documented endpoints.
- A pipeline checks and deploys each commit.
- Config is read from environment variables.

## Run

```
npm ci
npm run dev
npm test
```
