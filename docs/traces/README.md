# Public traces

Six runs from the live site (reviewer account, persona AI/ML engineer), exported from the Phoenix trace store on 15 Nov 2026. Each JSON file holds every span of one trace in start order: `run.*` is the graph run, `node.*` an agent step, `tool.*` an MCP tool call, `rag.*` a retrieval, `llm.*` a model call with its model, tokens, cost and latency. The live traces are also in Phoenix at `/phoenix/` (read-only login on the submission). Seconds for `llm.*` rows cover the whole call, including any wait for a free-tier rate-limit lane or a retry, which is why one call can take far longer than the others.

## One job from analysis to a draft waiting for approval

Job gs-0654 ("Need help: Random Python Works"). Risk Assessor, Analyst and Fit Matcher run in parallel; the Fit Matcher searches the portfolio once per requirement; Pricing, Writer, claim Verifier, Critic and Compliance Guard follow; the graph pauses at `prepare_approval`. The Critic approved on the first pass and all five claims were supported by cited evidence.

[approved-proposal-draft.json](approved-proposal-draft.json) · trace `641f2474ddbb7ef0f7a03082944d9e8b` · status `awaiting_approval` · 35 spans · 9 model calls · 15,919 tokens · $0.0040 · 60.6 s

| Span | Agent or node | Model | Tokens | Seconds |
|---|---|---|---|---|
| `node.scout` | scout |  |  | 0.0 |
| `node.analyst` | analyst |  |  | 0.4 |
| `node.risk_assessor` | risk_assessor |  |  | 0.6 |
| `tool.get_client_history` | risk_assessor |  |  | 0.2 |
| `node.fit_matcher` | fit_matcher |  |  | 1.5 |
| `llm.analyst` | analyst | gpt-oss-120b | 1330 | 0.4 |
| `llm.rag_helper` | rag_helper | gpt-oss-120b | 330 | 0.4 |
| `tool.search_evidence` | fit_matcher |  |  | 0.6 |
| `tool.search_evidence` | fit_matcher |  |  | 0.6 |
| `tool.search_evidence` | fit_matcher |  |  | 0.6 |
| `tool.search_evidence` | fit_matcher |  |  | 0.6 |
| `tool.search_evidence` | fit_matcher |  |  | 0.6 |
| `llm.risk_assessor` | risk_assessor | gpt-oss-120b | 989 | 0.3 |
| `llm.fit_matcher` | fit_matcher | gpt-oss-120b | 2589 | 0.5 |
| `node.decide` | decide |  |  | 0.0 |
| `node.pricing` | pricing |  |  | 1.2 |
| `tool.get_market_pricing` | pricing |  |  | 0.6 |
| `tool.get_connects_balance` | pricing |  |  | 0.1 |
| `llm.pricing` | pricing | gpt-oss-120b | 890 | 0.4 |
| `node.writer` | writer |  |  | 0.8 |
| `tool.search_evidence` | writer |  |  | 0.1 |
| `tool.search_evidence` | writer |  |  | 0.1 |
| `tool.search_evidence` | writer |  |  | 0.1 |
| `llm.writer` | writer | gpt-oss-120b | 3378 | 0.5 |
| `node.verifier` | verifier |  |  | 0.8 |
| `rag.verify_claims` |  |  |  | 0.8 |
| `llm.verifier` | verifier | gpt-oss-120b | 4023 | 0.8 |
| `node.critic` | critic |  |  | 55.7 |
| `llm.critic` | critic | gpt-oss-120b | 1225 | 55.7 |
| `node.compliance` | compliance |  |  | 0.5 |
| `llm.compliance` | compliance | gpt-oss-120b | 1165 | 0.4 |
| `node.prepare_approval` | prepare_approval |  |  | 0.1 |
| `tool.create_proposal_draft` | submitter |  |  | 0.1 |
| `node.approval` | approval |  |  | 0.0 |

## The same job after the freelancer approved it

A separate run: the worker resumes the paused thread from the checkpointer with the approval token, and `submit` sends the proposal once with an idempotency key. Status `submitted`.

[approved-proposal-submit.json](approved-proposal-submit.json) · trace `02d4cd5e5d9d91a2cdb5a65eb5859a67` · status `submitted` · 5 spans · 0 model calls · 0 tokens · $0.0000 · 0.2 s

| Span | Agent or node | Model | Tokens | Seconds |
|---|---|---|---|---|
| `node.approval` | approval |  |  | 0.0 |
| `node.submit` | submit |  |  | 0.1 |
| `tool.create_proposal_draft` | submitter |  |  | 0.1 |
| `tool.submit_proposal` | submitter |  |  | 0.1 |

## The Critic sends a draft back twice

Job gs-0649 (roofing image processing). Writer, Verifier and Critic run three times (the limit is two revisions), then Compliance checks the last draft and it waits for the freelancer with the Critic's remaining issues shown on top.

[critic-loop.json](critic-loop.json) · trace `bcbb41549a9c42044bc6a2507b6ed5aa` · status `awaiting_approval` · 54 spans · 21 model calls · 56,936 tokens · $0.0125 · 178.8 s

| Span | Agent or node | Model | Tokens | Seconds |
|---|---|---|---|---|
| `node.scout` | scout |  |  | 0.0 |
| `node.analyst` | analyst |  |  | 0.7 |
| `node.risk_assessor` | risk_assessor |  |  | 0.3 |
| `tool.get_client_history` | risk_assessor |  |  | 0.1 |
| `node.fit_matcher` | fit_matcher |  |  | 58.0 |
| `llm.risk_assessor` | risk_assessor | gpt-oss-120b | 995 | 0.2 |
| `llm.analyst` | analyst | gpt-oss-120b | 1262 | 0.7 |
| `llm.rag_helper` | rag_helper | gpt-oss-120b | 376 | 56.5 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `llm.fit_matcher` | fit_matcher | gpt-oss-120b | 2686 | 1.2 |
| `node.decide` | decide |  |  | 0.0 |
| `node.pricing` | pricing |  |  | 0.4 |
| `tool.get_market_pricing` | pricing |  |  | 0.1 |
| `tool.get_connects_balance` | pricing |  |  | 0.1 |
| `llm.pricing` | pricing | gpt-oss-120b | 885 | 0.3 |
| `node.writer` | writer |  |  | 0.8 |
| `tool.search_evidence` | writer |  |  | 0.1 |
| `tool.search_evidence` | writer |  |  | 0.2 |
| `llm.writer` | writer | gpt-oss-120b | 3497 | 0.6 |
| `node.verifier` | verifier |  |  | 57.5 |
| `rag.verify_claims` |  |  |  | 57.5 |
| `llm.verifier` | verifier | gpt-oss-120b | 4093 | 0.5 |
| `llm.verifier` | verifier | gpt-oss-120b | 3651 | 0.3 |
| `llm.verifier` | verifier | gpt-oss-120b | 3961 | 56.7 |
| `node.critic` | critic |  |  | 0.4 |
| `llm.critic` | critic | gpt-oss-120b | 1160 | 0.4 |
| `node.writer` | writer |  |  | 0.4 |
| `llm.writer` | writer | gpt-oss-120b | 3591 | 0.4 |
| `node.verifier` | verifier |  |  | 1.6 |
| `rag.verify_claims` |  |  |  | 1.6 |
| `llm.verifier` | verifier | gpt-oss-120b | 4378 | 0.6 |
| `llm.verifier` | verifier | gpt-oss-120b | 3888 | 0.5 |
| `llm.verifier` | verifier | gpt-oss-120b | 4050 | 0.6 |
| `node.critic` | critic |  |  | 0.4 |
| `llm.critic` | critic | gpt-oss-120b | 1049 | 0.4 |
| `node.writer` | writer |  |  | 0.6 |
| `llm.writer` | writer | gpt-oss-120b | 3605 | 0.5 |
| `node.verifier` | verifier |  |  | 57.6 |
| `rag.verify_claims` |  |  |  | 57.6 |
| `llm.verifier` | verifier | gpt-oss-120b | 4142 | 56.7 |
| `llm.verifier` | verifier | gpt-oss-120b | 3737 | 0.5 |
| `llm.verifier` | verifier | gpt-oss-120b | 3811 | 0.4 |
| `node.critic` | critic |  |  | 0.5 |
| `llm.critic` | critic | gpt-oss-120b | 1000 | 0.5 |
| `node.compliance` | compliance |  |  | 0.4 |
| `llm.compliance` | compliance | gpt-oss-120b | 1119 | 0.3 |
| `node.prepare_approval` | prepare_approval |  |  | 0.1 |
| `tool.create_proposal_draft` | submitter |  |  | 0.1 |
| `node.approval` | approval |  |  | 0.0 |

## A scam caught and skipped

Job gs-0252 ("Urgent machine learning work, easy money"). The Risk Assessor flags it ("Send a photo of your ID and your bank details"), a scam rule from the policy pack agrees, and `decide` skips it. No Writer call, no tokens spent on a proposal.

[scam-skipped.json](scam-skipped.json) · trace `b5874f3840e1922ec333bb64fe6ea0ff` · status `skipped` · 14 spans · 4 model calls · 4,494 tokens · $0.0013 · 59.1 s

| Span | Agent or node | Model | Tokens | Seconds |
|---|---|---|---|---|
| `node.scout` | scout |  |  | 0.0 |
| `node.analyst` | analyst |  |  | 0.5 |
| `node.risk_assessor` | risk_assessor |  |  | 0.4 |
| `tool.get_client_history` | risk_assessor |  |  | 0.1 |
| `node.fit_matcher` | fit_matcher |  |  | 59.0 |
| `llm.rag_helper` | rag_helper | gpt-oss-120b | 411 | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.2 |
| `tool.search_evidence` | fit_matcher |  |  | 0.2 |
| `tool.search_evidence` | fit_matcher |  |  | 0.2 |
| `llm.risk_assessor` | risk_assessor | gpt-oss-120b | 1075 | 0.3 |
| `llm.analyst` | analyst | gpt-oss-120b | 1054 | 0.4 |
| `llm.fit_matcher` | fit_matcher | gpt-oss-120b | 1954 | 58.5 |
| `node.decide` | decide |  |  | 0.0 |

## An injected instruction ignored

Job gs-0746 (OpenTelemetry, Node.js and Kafka POC). The post contains instructions aimed at automated tools. It is treated as data, flagged, and the job is skipped for safety ("the post contains instructions aimed at automated tools; skipped for safety").

[injection-skipped.json](injection-skipped.json) · trace `b6e9bc11e285b9ffd5b9881dec2445fc` · status `skipped` · 16 spans · 4 model calls · 5,696 tokens · $0.0015 · 1.5 s

| Span | Agent or node | Model | Tokens | Seconds |
|---|---|---|---|---|
| `node.scout` | scout |  |  | 0.0 |
| `node.analyst` | analyst |  |  | 1.4 |
| `node.risk_assessor` | risk_assessor |  |  | 0.4 |
| `tool.get_client_history` | risk_assessor |  |  | 0.1 |
| `node.fit_matcher` | fit_matcher |  |  | 1.1 |
| `llm.risk_assessor` | risk_assessor | gpt-oss-120b | 1176 | 0.3 |
| `llm.rag_helper` | rag_helper | gpt-oss-120b | 538 | 0.4 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `tool.search_evidence` | fit_matcher |  |  | 0.3 |
| `llm.fit_matcher` | fit_matcher | gpt-oss-120b | 2584 | 0.4 |
| `llm.analyst` | analyst | openai/gpt-oss-120b | 1398 | 1.4 |
| `node.decide` | decide |  |  | 0.0 |

## A client reply handled

Conversation th-ai_m-029. The client asks to move to WhatsApp and pay outside the platform. The Client Liaison classifies it as a scam signal, drafts a polite reply that keeps everything on the platform, checks it, and pauses at `reply_approval` for the freelancer.

[client-reply.json](client-reply.json) · trace `cd726e8a25ba2f6c97a0271fc36f8462` · status `running` · 10 spans · 3 model calls · 2,212 tokens · $0.0005 · 677.8 s

| Span | Agent or node | Model | Tokens | Seconds |
|---|---|---|---|---|
| `node.load_messages` | load_messages |  |  | 0.1 |
| `tool.list_messages` | client_liaison |  |  | 0.1 |
| `node.classify_intent` | classify_intent |  |  | 338.4 |
| `llm.intent` | intent | openai/gpt-oss-20b | 600 | 43.0 |
| `node.draft_reply` | draft_reply |  |  | 133.2 |
| `llm.client_liaison` | client_liaison | openai/gpt-oss-120b | 689 | 0.9 |
| `node.check_reply` | check_reply |  |  | 8.0 |
| `llm.compliance` | compliance | openai/gpt-oss-20b | 923 | 8.0 |
| `node.reply_approval` | reply_approval |  |  | 0.0 |
