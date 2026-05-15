# ADR-002: Claude (Anthropic) for the Shadow Agent

**Status**: Accepted
**Date**: 2026-05-14

## Context

The Shadow Agent is the core evaluator in `orchid`. It receives the full session transcript of `PROMPT_SENT` and `CORRECTION_ISSUED` events — potentially 60+ minutes of interactions — and must:

1. Score each prompt on clarity (0–10), specificity (0–10), and context-richness (0–10).
2. Reconstruct the candidate's reasoning trace as a sequence of inferred decision points.
3. Classify the candidate's orchestration style into one of four clusters.
4. Generate a narrative report for hiring managers.

The two realistic LLM options were **Claude** (Anthropic) and **GPT-4o** (OpenAI). We already use GPT-4o for the three sub-agents (DELTA, NOVA, ECHO).

## Decision

Use **Claude (`claude-sonnet-4-6`)** for the Shadow Agent.

## Reasoning

### Context window
A 60-minute candidate session can produce 80–120 telemetry events. The structured transcript (event envelope + prompt text) averages ~250 tokens per event, yielding 20,000–30,000 input tokens per evaluation call. Claude's 200k-token context window handles this with headroom for the evaluation system prompt; GPT-4o's 128k window is sufficient but tighter.

### Structured output adherence
The Shadow Agent must return a strictly typed JSON object (`prompt_scores: list`, `reasoning_trace: list[str]`, `style_narrative: str`). In internal testing of evaluation prompts, Claude consistently returned parseable JSON without requiring `response_format: {"type": "json_object"}` workarounds. GPT-4o required the explicit `response_format` parameter and still produced occasional schema violations in long sessions.

### Instruction following in evaluation tasks
The Shadow Agent operates under a strict constraint: it must evaluate the candidate's **prompts only**, never their code outputs or task completion. Claude's instruction-following on "do not comment on X" constraints was more reliable in our prompt testing. GPT-4o showed a tendency to slip into commenting on code quality when the transcript included `CODE_EXECUTED` events.

### Provider separation
Using different providers for the evaluator (Anthropic) and the sub-agents (OpenAI) eliminates the risk of a single provider outage disabling the entire assessment. It also keeps cost attribution clean: sub-agent cost vs. evaluation cost are billed separately.

### Cost per session
At `claude-sonnet-4-6` pricing (input ~$3/MTok, output ~$15/MTok), a full Shadow Agent evaluation call (~25k input + ~2k output tokens) costs approximately $0.11. This fits within our $0.80 per-session budget target (Sprint 10).

## Consequences

**Enables:**
- Reliable evaluation of long sessions without context truncation.
- Provider diversity — Anthropic outage does not block sub-agent operation and vice versa.
- Clean cost attribution per provider.

**Forecloses:**
- Single-provider simplicity (one API key, one SDK).
- Using OpenAI Assistants API for stateful Shadow Agent observation (not feasible with Anthropic's stateless API anyway).

**Accepted trade-off:** Managing two LLM API keys is a minor operational overhead. The evaluation reliability improvement is non-negotiable for product integrity.
