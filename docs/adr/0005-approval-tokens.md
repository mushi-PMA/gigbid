# ADR 0005: Approval tokens bind the human's decision to the exact payload

Status: accepted

**Context.** Approvals happen in the UI, but the write happens later in the worker, possibly after a crash.

**Decision.** When the human approves, the API mints a signed token over the user, action, target and a hash of the
exact payload. The marketplace server refuses any write without a matching token. Idempotency keys are derived from
the thread and the payload hash.

**Consequences.** A model, a bug or a later edit cannot send content the human did not approve, and a resumed or
retried submit cannot spend Connects twice.
