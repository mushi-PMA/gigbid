# ADR 0002: MCP for every capability; the marketplace port lives in one MCP server

Status: accepted

**Context.** Agents must never call GigSim, Upwork, a database or a file directly, and the graph must not know
whether it talks to GigSim or live Upwork.

**Decision.** Three servers built with the official MCP Python SDK (portfolio, marketplace, workspace). The
marketplace server owns the port and its two adapters, switched by config; the agent side uses one thin
`MarketplacePort` over MCP tools. Each agent gets an allowlist of tool names.

**Consequences.** Idempotency, dry runs, approval tokens, rate limiting and the audit log are enforced in one place
for both marketplaces. The Upwork tool names are mapped in config because they can change.
