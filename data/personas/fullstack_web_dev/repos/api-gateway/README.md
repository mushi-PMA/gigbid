# api-gateway

GraphQL layer over several REST back ends.

Stack: GraphQL, Node.js, TypeScript.

## What is in here

- `Dockerfile`
- `server/routes/accounts.ts`
- `src/schema.ts`

## Notes

- Built with GraphQL.
- Stack: Node.js.
- Documented HTTP endpoints serve the front end.
- The service ships as one image that runs the same on a laptop and in the cloud.
- Tests live next to the code they cover.

## Run

```
npm ci
npm run dev
npm test
```
