"""LLM client abstraction: one interface, two provider implementations."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient(ABC):
    """Abstract base for all LLM provider clients.

    Concrete implementations must never be called directly in business logic —
    always inject an LLMClient instance through the constructor.
    """

    @abstractmethod
    async def acomplete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse: ...


class OpenAILLMClient(LLMClient):
    """Async OpenAI chat completion client (used for DELTA, NOVA, ECHO sub-agents)."""

    def __init__(self, api_key: str) -> None:
        import openai  # lazy — not required in test environments

        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        t0 = time.monotonic()
        resp = await self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]  # SDK accepts list[dict]
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        result = LLMResponse(
            content=content,
            model=resp.model,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
        logger.info(
            "llm_call_completed",
            provider="openai",
            model=resp.model,
            latency_ms=latency_ms,
            token_count=result.total_tokens,
        )
        return result


class AnthropicLLMClient(LLMClient):
    """Async Anthropic Messages client (used for the Shadow Agent in Sprint 7)."""

    def __init__(self, api_key: str) -> None:
        import anthropic  # lazy — not required in test environments

        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        system = next(
            (m["content"] for m in messages if m["role"] == "system"), ""
        )
        non_system = [m for m in messages if m["role"] != "system"]
        t0 = time.monotonic()
        resp = await self._client.messages.create(
            model=model,
            system=system,
            messages=non_system,  # type: ignore[arg-type]  # SDK accepts list[dict]
            max_tokens=max_tokens,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        content = resp.content[0].text if resp.content else ""
        result = LLMResponse(
            content=content,
            model=resp.model,
            latency_ms=latency_ms,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )
        logger.info(
            "llm_call_completed",
            provider="anthropic",
            model=resp.model,
            latency_ms=latency_ms,
            token_count=result.total_tokens,
        )
        return result
