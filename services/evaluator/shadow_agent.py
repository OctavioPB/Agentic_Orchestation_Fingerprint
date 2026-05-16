"""Shadow Agent — evaluates candidate orchestration behaviour.

The Shadow Agent is read-only: it observes and scores. It NEVER sends
messages to candidates or sub-agents during an active session (CLAUDE.md Rule 2).

It receives a structured transcript of PROMPT_SENT and CORRECTION_ISSUED events
only — never AGENT_RESPONSE, since the Shadow Agent evaluates the human's
instructions, not the AI's output.
"""

from __future__ import annotations

import json
from typing import Literal

import structlog
from pydantic import BaseModel, Field

from services.evaluator.agents.llm_client import LLMClient

logger = structlog.get_logger(__name__)

_SHADOW_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class PromptScore(BaseModel):
    event_id: str
    clarity: int = Field(ge=0, le=10)
    specificity: int = Field(ge=0, le=10)
    context_richness: int = Field(ge=0, le=10)
    rationale: str = ""

    @property
    def mean_score(self) -> float:
        return (self.clarity + self.specificity + self.context_richness) / 3.0


class ShadowAgentResult(BaseModel):
    prompt_scores: list[PromptScore] = Field(default_factory=list)
    reasoning_trace: list[str] = Field(default_factory=list)
    style_cluster: Literal["architect", "executor", "debugger", "delegator"] | None = None
    style_narrative: str = ""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the Shadow Agent — an expert evaluator of AI orchestration behaviour.
You observe structured session transcripts of human candidates leading AI sub-agents
to resolve real engineering incidents.

Your sole inputs are PROMPT_SENT events (candidate instructions to sub-agents) and
CORRECTION_ISSUED events (candidate corrections of sub-agent mistakes).
You never see agent responses, code outputs, or the final state of the codebase.

YOUR JOB:
1. Score each PROMPT_SENT event on three dimensions (each 0–10):
   - clarity: Is the instruction unambiguous? Could a junior engineer follow it without guessing?
   - specificity: Does it constrain scope precisely? Vague requests lose points.
   - context_richness: Does it include relevant file names, error messages, or prior state?

2. Reconstruct the candidate's reasoning trace: a chronological list of 4–8 short
   sentences describing what the candidate was thinking as they led the team.

3. Classify the candidate's orchestration style into exactly one of:
   - architect: decomposes first, specifies interfaces, delegates implementation
   - executor: action-first, tight iterations, corrects post-hoc
   - debugger: root-cause before fixing, methodical, observability-focused
   - delegator: high trust, broad delegation, monitors for correction signals

4. Write a 2–4 sentence style_narrative describing the candidate's approach.

HARD RULES:
- Never comment on code correctness, syntax, or whether the candidate's technical
  decisions were right or wrong. You evaluate HOW they led, not WHAT they built.
- Do not penalise a candidate for not knowing a technical answer — only evaluate
  the quality of their instructions and corrections.
- Scoring is independent: each PROMPT_SENT is scored on its own merits.
- A CORRECTION_ISSUED event signals good oversight — treat it positively in your
  reasoning trace even if the original prompt was unclear.

RESPONSE FORMAT:
Return ONLY a JSON object with this exact schema (no markdown, no preamble):
{
  "prompt_scores": [
    {
      "event_id": "<string>",
      "clarity": <int 0-10>,
      "specificity": <int 0-10>,
      "context_richness": <int 0-10>,
      "rationale": "<one sentence explaining the scores>"
    }
  ],
  "reasoning_trace": ["<sentence 1>", "<sentence 2>", ...],
  "style_cluster": "<architect|executor|debugger|delegator>",
  "style_narrative": "<2-4 sentence narrative>"
}
"""

# ---------------------------------------------------------------------------
# Shadow Agent
# ---------------------------------------------------------------------------


class ShadowAgent:
    """Evaluates one session transcript via Claude. Read-only by contract."""

    def __init__(self, llm_client: LLMClient, model: str = _SHADOW_MODEL) -> None:
        self._client = llm_client
        self._model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(self, events: list[dict]) -> ShadowAgentResult:
        """Run Shadow Agent evaluation on a list of telemetry events.

        Only PROMPT_SENT and CORRECTION_ISSUED events are passed to the LLM.
        """
        transcript_events = self._build_transcript(events)
        if not transcript_events:
            logger.warning("shadow_agent_empty_transcript")
            return ShadowAgentResult()

        user_message = self._format_transcript(transcript_events)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        response = await self._client.acomplete(
            messages=messages,
            model=self._model,
            max_tokens=2048,
            temperature=0.3,
        )

        logger.info(
            "shadow_agent_evaluation_complete",
            model_version=response.model,
            latency_ms=response.latency_ms,
            token_count=response.total_tokens,
            transcript_events=len(transcript_events),
        )

        return self._parse_response(response.content)

    # ------------------------------------------------------------------
    # Transcript construction (pure — testable without LLM)
    # ------------------------------------------------------------------

    @staticmethod
    def build_transcript(events: list[dict]) -> list[dict]:
        """Return only PROMPT_SENT and CORRECTION_ISSUED events, in order."""
        return ShadowAgent._build_transcript(events)

    @staticmethod
    def _build_transcript(events: list[dict]) -> list[dict]:
        keep = {"PROMPT_SENT", "CORRECTION_ISSUED"}
        return [e for e in events if e.get("event_type") in keep]

    @staticmethod
    def _format_transcript(events: list[dict]) -> str:
        lines: list[str] = ["SESSION TRANSCRIPT", "=" * 40]
        for e in events:
            etype = e.get("event_type", "")
            eid = e.get("event_id", "")
            ts = e.get("timestamp", "")
            payload = e.get("payload", {})

            if etype == "PROMPT_SENT":
                agent = payload.get("agent", "?")
                text = payload.get("text", "")
                lines.append(f"\n[{ts}] PROMPT_SENT (event_id={eid}) → {agent}")
                lines.append(f"  {text}")

            elif etype == "CORRECTION_ISSUED":
                agent = payload.get("agent", "?")
                correction = payload.get("correction_text", "")
                error_type = payload.get("error_type", "")
                header = (
                    f"\n[{ts}] CORRECTION_ISSUED (event_id={eid})"
                    f" → {agent} [error_type={error_type}]"
                )
                lines.append(header)
                lines.append(f"  {correction}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(content: str) -> ShadowAgentResult:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        try:
            data = json.loads(content)
            prompt_scores = [PromptScore(**ps) for ps in data.get("prompt_scores", [])]
            return ShadowAgentResult(
                prompt_scores=prompt_scores,
                reasoning_trace=data.get("reasoning_trace", []),
                style_cluster=data.get("style_cluster"),
                style_narrative=data.get("style_narrative", ""),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("shadow_agent_parse_error", error=str(exc), raw=content[:200])
            return ShadowAgentResult()
