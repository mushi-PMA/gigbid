# ADR 0001: Hand-written LangGraph StateGraph for the bid flow

Status: accepted

**Context.** The brief requires parallel analysis, a bounded critique loop, human approval that survives restarts,
and budgets. A prebuilt supervisor or a single ReAct agent decides the control flow with a model at run time.

**Decision.** A hand-written `StateGraph` with fixed edges: `Send` fan-out to Analyst, Risk Assessor and Fit Matcher,
a deterministic decision node, conditional edges for the Critic loop and Compliance block, and `interrupt()` before
any write. The prebuilt supervisor and a single ReAct agent are kept as baselines (R&D question C).

**Consequences.** Control flow is testable without models (`tests/integration`), the approval gate cannot be skipped
by a model, and budgets are enforced in routing. The cost is more code than a prebuilt agent.
