# studio-booking

Booking app with class schedule, passes and waitlists.

Stack: React, Node.js, PostgreSQL.

## What is in here

- `docker-compose.yml`
- `prisma/schema.prisma`
- `server/routes/bookings.ts`
- `src/components/BookingList.tsx`

## Notes

- Uses React.
- Uses Node.js.
- Checkout sessions and webhook handling cover payments, refunds and failed charges.
- Everything starts with a single compose command on any machine.
- Tests live next to the code they cover.

## Run

```
npm ci
npm run dev
npm test
```
