# LLM Council skill

A Claude Code skill implementing Andrej Karpathy's
[LLM Council](https://github.com/karpathy/llm-council) pattern: answer a hard
question by convening a council of independent members, having them critique
each other anonymously, and synthesizing a single Chairman answer.

## What it does

Three stages, faithful to the original:

1. **First opinions** — several council members (spawned as independent
   subagents with distinct personas) answer the same neutral question in
   isolation.
2. **Anonymized peer review** — members rank each other's answers with
   identities stripped, so no one plays favorites.
3. **Chairman synthesis** — one integrated final answer: verdict, consensus,
   live disagreement, blind spots, and a single next action.

Karpathy's original routes the question to different providers (GPT, Gemini,
Claude, Grok) via OpenRouter. Inside Claude Code there's one model, so the
council is formed from independent subagents given distinct mandates and no
shared context.

## Usage

The skill triggers automatically when you ask to "convene the council", "ask the
LLM council", want multiple perspectives / a debate / a devil's advocate, or
face a strategic decision. Or invoke it explicitly:

```
/llm-council should we rewrite the runner in async?
```

Use it for judgment calls, not factual lookups or arithmetic.

## Install elsewhere

This lives in the repo at `.claude/skills/llm-council/`. To use it globally,
copy the folder to `~/.claude/skills/llm-council/`.

## Attribution

Pattern by Andrej Karpathy — https://github.com/karpathy/llm-council. Independent
adaptation, not affiliated with the original author.
