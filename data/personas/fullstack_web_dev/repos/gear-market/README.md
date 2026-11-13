# gear-market

Marketplace with listings, offers and escrow-style checkout.

Stack: Next.js, TypeScript, Stripe.

## What is in here

- `app/api/checkout/route.ts`
- `prisma/schema.prisma`
- `src/components/ListingList.tsx`

## Notes

- Uses Next.js.
- Implemented in TypeScript.
- SQL tables with foreign keys, migrations and a few partial indexes sit underneath.
- Recent results are cached in memory so repeat requests return in milliseconds.
- See the case study for the business background.

## Run

```
npm ci
npm run dev
npm test
```
