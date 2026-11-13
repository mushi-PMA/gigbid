# headless-shop

Custom storefront on the Shopify Storefront API.

Stack: Shopify, Next.js, GraphQL.

## What is in here

- `src/components/ProductList.tsx`
- `src/schema.ts`

## Notes

- Relies on Shopify.
- Next.js for the main logic.
- Styling is utility classes written directly in the markup.
- All code is typed end to end, with shared types between browser and server.
- Pull requests need a passing test run.

## Run

```
npm ci
npm run dev
npm test
```
