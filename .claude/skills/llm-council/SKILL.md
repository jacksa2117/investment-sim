---
name: llm-council
description: >-
  Convene an "LLM Council" (Andrej Karpathy's method) to answer a hard,
  open-ended, or high-stakes question through structured deliberation instead
  of a single answer. Runs three stages — parallel first opinions from several
  council members, anonymized peer review and ranking, and a Chairman synthesis
  into one final answer. Use when the user asks to "convene the council", "ask
  the LLM council", wants multiple perspectives / a debate / a devil's advocate,
  or faces a strategic decision (pivots, positioning, hiring, architecture,
  investment calls). Do NOT use for simple factual lookups, arithmetic, or pure
  execution tasks where a single answer suffices.
---

# LLM Council

An implementation of Andrej Karpathy's [LLM Council](https://github.com/karpathy/llm-council)
pattern as a Claude Code skill. Instead of answering a hard question yourself,
you convene a *council* of independent members, have them critique each other
anonymously, and then synthesize a single, better-calibrated answer.

The original project routes the same question to several different model
providers via OpenRouter. Inside Claude Code there is one model, so the council
is formed from **independent subagents given distinct personas and no shared
context** — each reasons in isolation, exactly as separate council members would.

## When to convene the council

Convene it for questions where *deliberation adds value*:

- Strategic / judgment calls with no single right answer (product pivots,
  positioning, hiring, build-vs-buy, architectural direction, investment theses).
- Questions where you want the blind spots surfaced, not just an answer.
- Anything the user explicitly frames as "ask the council", "get several
  opinions", "play devil's advocate", "debate this".

Do **not** convene it for factual lookups, arithmetic, straightforward coding
tasks, or anything with an unambiguous answer — the overhead just adds latency.
Answer those directly.

## The three stages

### Stage 0 — Frame the question

Restate the user's question in a single, neutral sentence. Strip out any
leading framing that presupposes an answer ("isn't it obvious we should…").
Gather only the context the council genuinely needs (repo facts, constraints,
prior decisions) and write it down once so every member sees the *same* brief.

### Stage 1 — First opinions (parallel, independent)

Spawn the council members **in parallel** using the `Agent` tool — one call per
member, all in a single message so they run concurrently. Each member gets:

1. The neutral question and the shared context brief.
2. Its persona (see the roster below).
3. An instruction to answer independently and NOT to hedge toward a middle
   ground — give its sharpest honest take.

Default roster (5 members — adjust to the question, keep them genuinely
distinct):

| Member            | Mandate |
| ----------------- | ------- |
| **Contrarian**    | Argue the strongest case *against* the obvious answer. Name the failure modes. |
| **First-Principles** | Ignore convention. Re-derive the answer from the underlying constraints. Question whether the question itself is framed right. |
| **Expansionist**  | Surface the opportunities and second-order upside everyone else is missing. |
| **Outsider**      | Answer with fresh eyes and minimal domain baggage; flag what "everyone knows" that may be wrong. |
| **Executor**      | Ignore theory. What is the concrete Monday-morning action, and what breaks in practice? |

Collect each member's response verbatim. If you show the user intermediate
output, present these as a labelled tab-style list so they can inspect each
opinion individually.

### Stage 2 — Anonymized peer review

Now have the members judge each other's work. **Anonymize first**: relabel the
Stage 1 responses as "Response A, B, C…" with the persona names stripped, so no
member can play favorites.

Spawn a review pass (parallel again is fine) where each reviewer receives all
anonymized responses and must:

- Rank them from best to worst on **accuracy and insight** (not verbosity).
- Give a one-line justification per ranking.
- Explicitly call out any claim it believes is *wrong*.

Aggregate the rankings (e.g. mean rank per response) to see which opinions the
council collectively trusts most, and which claims drew disagreement.

### Stage 3 — Chairman synthesis

Acting as **Chairman**, produce the single final answer. The Chairman does not
just pick the top-ranked response — it integrates. Deliver:

1. **Verdict** — the recommended answer / decision, stated plainly up front.
2. **Consensus** — what the council agreed on.
3. **Live disagreement** — where members genuinely diverged, and why it matters.
4. **Blind spots** — risks or options only one member caught.
5. **One next action** — the single most concrete thing to do next.

Keep the synthesis tight. The point of the council is a *sharper* answer, not a
longer one.

## Running it

By default, run all three stages and return only the Stage 3 synthesis, briefly
noting how the council split. If the user wants to see the deliberation, show
the Stage 1 opinions and Stage 2 rankings as well.

Practical notes:
- Spawn Stage 1 members in one message (parallel) for speed.
- Give each subagent *only* the shared brief — never let one member see
  another's answer before Stage 2, or you lose independence.
- Scale the roster to the question: a small call might use 3 members, a big
  strategic one all 5 (or more). More than ~6 rarely helps.
- If the question is actually simple, say so and answer directly instead of
  convening — that judgment is part of the skill.

## Attribution

Pattern by Andrej Karpathy — <https://github.com/karpathy/llm-council>. This is
an independent Claude Code adaptation of that idea, not affiliated with the
original author.
