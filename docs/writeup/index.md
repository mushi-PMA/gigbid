---
title: "The better retriever did not write better proposals"
---

# The better retriever did not write better proposals

*What we measured while building GigBid, a freelancer copilot that never sends anything without you.*

GigBid reads freelance job posts, decides which ones are worth a bid, and drafts a proposal in which every claim
about the freelancer points to a real item in their portfolio: a case study, a repository, a past proposal. A team of
LangGraph agents does the reading, risk checks, matching, pricing and writing, and nothing is submitted until the
freelancer approves it. The code, data and every result file are in the
[repository](https://github.com/mushi-PMA/gigbid), and the app runs at
[gigbid-9305.westus2.cloudapp.azure.com](https://gigbid-9305.westus2.cloudapp.azure.com).

We went in with a simple belief: proposals are only as good as the evidence behind them, so the retrieval step is
where quality is won. We spent most of our research time there. The most surprising thing our experiments showed is
that, measured where it matters, it barely mattered.

## The retrieval study did exactly what we hoped

Freelancer portfolios are hard to search. The same project is described three ways (a case study, a README, the
proposal that won the job), skills are implied rather than listed ("built the dashboard the ops team checks every
morning" is a Power BI skill), and code sits next to prose. We built our synthetic portfolios to be hard in exactly
these ways and labelled, for every dev job, which projects are real evidence for it.

Then we built nine retrieval variants as parts that combine: plain dense search (V0), query decomposition, hybrid BM25
plus dense search, a cross-encoder reranker, an outcome boost for evidence from proposals that won, project grouping,
contextual chunk lines, HyDE and a corrective loop. On 150 dev jobs the picture was clean. Hybrid search plus the
outcome boost (V2+V4) beat plain dense search on nDCG@10, 0.597 against 0.566. The ablation said both parts earn
their place: removing hybrid search cost 0.062, removing the outcome boost 0.021. HyDE on top was better still, 0.629
against 0.587 on the same 60 jobs, but it costs a model call per search, and on free model tiers a model call is the
scarce thing, so we shipped V2+V4.

Two of our own hypotheses failed along the way, and we report them as failed. We had predicted that decomposition,
hybrid search and reranking together would raise Recall@5 by ten points on jobs with four or more requirements; on
the 29 such jobs it fell by six (0.432 to 0.368). The reranker made every combination worse and timed out on the
two-core server. And "hybrid beats plain for every persona" was false: the shipped retrieval helps the web developer a
lot (nDCG@10 0.518 to 0.630) and hurts the AI engineer (0.610 to 0.584), worst of all on LLM-app jobs, where its
Recall@5 fell from 0.582 to 0.154.

Still, overall, better retrieval. So we expected better proposals.

## Then we sent the proposals to clients

We ran the same twelve fixed bid jobs through two pipelines that differ only in retrieval, V0 and the shipped V2+V4,
and sent every proposal to GigSim, our simulated marketplace, where each client has hidden preferences and decides
whether to reply.

Every one of V0's seven proposals got a reply. Seven of the shipped pipeline's eight did. A rubric judge scored them
3.57 and 3.63 out of 5. With seven and eight proposals, none of these differences is significant, and that is the
point: the retriever that clearly won its own benchmark produced proposals that clients could not tell apart.

The reason turned out to be in how a reply is earned, and we could read it because we wrote the simulator. A GigSim
client scores a letter on whether it names the job's skills, how much of the post's own wording it reuses, the price,
whether it opens with a generic greeting and whether it answers the screening questions. Nothing in that list asks
which project the letter cites. Both pipelines use the same Writer, which is told to open with the client's problem in their own terms and mention
specific details from the post, so both clear the bar.
Better evidence can only help a letter through those channels, and here it had none left to help through.

Better retrieval did change one thing, in the wrong direction. More evidence in the prompt led the Writer to make more
claims, and more claims means more that cannot be verified: the shipped pipeline averaged 1.00 unsupported claims per
proposal after claim verification, against 0.86 for V0. Claim verification itself worked as intended, cutting
unsupported claims in the shipped pipeline from 2.13 to 1.00 per proposal, but it starts from a higher pile.

GigSim is a simulator, and real clients may well notice which project you cite. But that is exactly the lesson. A
retrieval metric measures the step you can measure. Whether the step matters depends on what the final judge rewards,
and if you do not know that, a cleaner nDCG is a guess about value, not evidence of it.

## The same pattern, one level up

We saw the pattern again when we compared architectures. On the same nine jobs we ran one ReAct agent holding every
tool, a prebuilt `langgraph-supervisor` with three workers, and our hand-built graph with parallel analysis, a
verifier and a bounded critique loop. On the obvious score, the graph lost: it made the right bid-or-skip call on 4 of
9 jobs, against 5 for the single agent and 6 for the supervisor, at three times the tokens.

On the score that protects the freelancer, it won clearly: 0.5 unsupported claims per proposal against 2.0 and 6.0,
and no policy violation in its final text, where the supervisor let one through. A wrong "watch" costs a missed job. A
made-up claim sent to a client costs a reputation. Which architecture is better depends entirely on which of those you
count, which is the retrieval lesson again.

## Two of our own measurements lied

The part we least expected was that our own evaluation fooled us twice, and both times the number looked good.

We cache every model call by its prompt, so a rerun on free tiers costs nothing. After a crash we replayed the
held-out run from the cache, and it reported a p95 latency of about one second per proposal: a budget of 90 seconds,
"met". The real, live run had measured 334 seconds. A replayed call takes no time, so every rerun quietly reported a
fantasy. Each step now counts how many of its calls were replayed, latency is computed only over jobs whose calls all
ran live, and our held-out latency comes from the one fully live run. Three of our four budgets are missed, and we say
so.

The second lie looked like a weakness of one proposal strategy. In our A/B test of two writing strategies, almost
every job of the second strategy died before writing anything. The cause was not the strategy. Replays from the cache
reached our marketplace server far faster than live calls ever do, the server's own rate limiter (there to protect the
marketplace) refused them, and the pricing step failed. The limiter was doing its job; our test harness had made time
run faster than the world it was testing. The fix was one line in the harness. Finding it took tracing a "dead letter"
back through several layers.

Neither bug would have survived a reader asking "how was this number produced?" Both survived us for hours, because
the numbers were plausible and pointed the way we hoped.

## What we changed because of it

We keep claim verification on, because the unsupported-claim number is the one that measures harm. We stopped treating
retrieval metrics as the target and now look at retrieval only through the proposals it produces. Our main results
table puts the outcome a freelancer cares about, the reply rate, next to the retrieval numbers, so the two cannot be
read apart. And every latency in our report now says whether it was measured live.

The next experiments follow from the finding rather than from the leaderboard: give the Writer fewer, stronger pieces
of evidence instead of more, stop the critique loop when its only complaint after verification is length (on jobs with
thin evidence it currently spends the whole token budget and then hands the job to a human), and test retrieval
against clients who do look at which project you cite. The held-out results, the failure analysis and every number in
this post are in the [report](https://github.com/mushi-PMA/gigbid/blob/main/docs/report/main.pdf).
