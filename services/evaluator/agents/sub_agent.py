"""Sub-agent: loads a versioned persona system prompt and wraps the LLM client."""
from __future__ import annotations

from pathlib import Path

import structlog

from services.evaluator.agents.llm_client import LLMClient, LLMResponse
from services.telemetry.models import AgentName

_SYSTEM_PROMPT_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "scenarios" / "agents" / "v1"
)
_SUB_AGENT_MODEL = "gpt-4o"
_MAX_TOKENS = 1024

logger = structlog.get_logger(__name__)


class SubAgent:
    """A persona-injected LLM agent that maintains per-session conversation history."""

    def __init__(self, name: AgentName, client: LLMClient) -> None:
        self._name = name
        self._client = client
        self._system_prompt = self._load_system_prompt(name)
        self._history: list[dict[str, str]] = []

    # ── Public interface ───────────────────────────────────────────────────────

    def build_messages(self, user_message: str) -> list[dict[str, str]]:
        """Return the full message list for the next LLM call without mutating history.

        Useful for unit testing prompt construction without making LLM calls.
        """
        return (
            [{"role": "system", "content": self._system_prompt}]
            + list(self._history)
            + [{"role": "user", "content": user_message}]
        )

    async def send(self, session_id: str, user_message: str) -> LLMResponse:
        """Send a message, append the exchange to history, and return the LLM response."""
        self._history.append({"role": "user", "content": user_message})
        messages = [
            {"role": "system", "content": self._system_prompt}
        ] + self._history
        response = await self._client.acomplete(
            messages=messages,
            model=_SUB_AGENT_MODEL,
            max_tokens=_MAX_TOKENS,
        )
        self._history.append({"role": "assistant", "content": response.content})
        logger.info(
            "sub_agent_response",
            session_id=session_id,
            agent=self._name.value,
            latency_ms=response.latency_ms,
            token_count=response.total_tokens,
            model_version=response.model,
        )
        return response

    @property
    def name(self) -> AgentName:
        return self._name

    # ── Private ────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_system_prompt(name: AgentName) -> str:
        path = _SYSTEM_PROMPT_DIR / f"{name.value.lower()}_system.md"
        return path.read_text(encoding="utf-8")
