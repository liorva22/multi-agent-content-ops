# Multi-Agent Content Ops: pitch

## The pitch
Turning a product spec into a launch blog post takes a marketer a day and a reviewer another hour of fact-checking. This pipeline does it with four specialized agents: a researcher, a writer, a fact-checker, and a style polisher. When the fact-checker finds a claim the spec doesn't support, the pipeline rolls back and rewrites automatically, and every step's tokens, cost, latency, and output are logged for audit. In the demo runs, the fact-checker caught every invented statistic before publication, after 0, 1, and 2 rewrites.

## Problem and who it's for
Product marketing and DevRel teams who publish many feature announcements. The risk isn't bad prose; it's confident, wrong claims ("37% productivity boost") reaching customers. They need speed *and* an audit trail showing that each claim was checked.

## How it works
See the README diagram:
1. The **Researcher** turns the PRD into numbered facts with their sources.
2. The **Writer** drafts a post that cites fact IDs.
3. The **Fact-checker** combines an Opus review with a deterministic rule: every number in the draft must exist in the PRD or the facts. Each issue triggers a rollback: the draft is discarded and the writer gets the issues. After `max_write_attempts`, the run escalates to human review.
4. The **Style polisher** strips citations, adds a TL;DR, and enforces the style guide.
5. A **rubric** scores the final post.

Each transition writes one row to Postgres. The dashboard renders those rows as a timeline plus per-step metrics.

## Stack and design choices
- **Hand-rolled state machine instead of LangGraph.** Four nodes and one back-edge don't need a framework: ~60 readable lines, no dependency, and tests are a list comprehension over a log callback. *Trade-off:* parallel branches and resumable human approvals would need to be built. That's when I'd adopt LangGraph.
- **Deterministic number check inside the fact-checker.** It catches the highest-risk hallucination exactly and for free. *Trade-off:* it can't catch wrong *words* ("Spanish" vs "French"), which is the LLM's job.
- **Models matched to risk.** Opus where an error is costliest (fact-checking), Haiku for constrained edits. *Trade-off:* more models to evaluate and pin.
- **Postgres step log, no tracing vendor.** The full audit trail is queryable with SQL.

## What I'd do differently
- **Severity-graded fact-checks.** In the live run ($0.36), the real writer invented no numbers, but the Opus fact-checker rejected 7 of 8 drafts over framing ("first release", "No More Surprises") and sent 2 of 3 PRDs to a human. I'd have it grade severity and roll back only on unsupported facts. The mock writer's scripted number hallucinations tested a failure the real writer never showed.
- **Longer posts in mock mode.** The template writer produces about 210 words, so the rubric's 250-word minimum fails on all three PRDs. It's left visible as a working example of the rubric catching a real defect.
- **Claim-level verification**, not only numbers: extract every factual claim and require an entailing fact (NLI or an LLM).
- **Human-in-the-loop** approval before publishing, plus resumable runs. That's the point to bring in LangGraph checkpoints or a durable workflow engine.

## Interview talking points
- Why I chose not to use LangGraph, and the specific trigger that would change my mind.
- Rollback design: what state is kept (research), what's discarded (the draft), and how retries are bounded.
- Combining deterministic and LLM checks in one fact-checker.
- Honest mocks: scripted hallucinations to exercise failure paths, and no fake judge scores.
