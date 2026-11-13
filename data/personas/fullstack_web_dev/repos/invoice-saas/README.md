# invoice-saas

Invoice builder with recurring billing and reminders.

Stack: Next.js, Node.js, PostgreSQL.

## What is in here

- `.github/workflows/ci.yml`
- `app/api/checkout/route.ts`
- `prisma/schema.prisma`

## Notes

- Relies on Next.js.
- Node.js for the main logic.
- Card payments go through a hosted payment provider, and webhooks confirm every charge.
- All code is typed end to end, with shared types between browser and server.
- Sample data is synthetic.

## Run

```
npm ci
npm run dev
npm test
```
