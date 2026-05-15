"""Unit tests for SubAgent — no LLM calls, no network I/O."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from services.evaluator.agents.llm_client import LLMClient, LLMResponse
from services.evaluator.agents.sub_agent import _SYSTEM_PROMPT_DIR, SubAgent
from services.telemetry.models import AgentName

# ── Test double ────────────────────────────────────────────────────────────────


class _FakeLLMClient(LLMClient):
    """In-process stub that returns a deterministic response without network I/O."""

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(
            content="fake response",
            model=model,
            latency_ms=10,
            prompt_tokens=20,
            completion_tokens=5,
        )


_FAKE_CLIENT = _FakeLLMClient()


# ── System prompt files ────────────────────────────────────────────────────────


class TestSystemPromptFiles:
    def test_delta_prompt_file_exists(self) -> None:
        assert (_SYSTEM_PROMPT_DIR / "delta_system.md").exists()

    def test_nova_prompt_file_exists(self) -> None:
        assert (_SYSTEM_PROMPT_DIR / "nova_system.md").exists()

    def test_echo_prompt_file_exists(self) -> None:
        assert (_SYSTEM_PROMPT_DIR / "echo_system.md").exists()

    def test_each_agent_has_distinct_prompt(self) -> None:
        prompts = {
            name: (
                Path(_SYSTEM_PROMPT_DIR) / f"{name.value.lower()}_system.md"
            ).read_text()
            for name in AgentName
        }
        assert len(set(prompts.values())) == len(AgentName), (
            "All three agent prompts must be distinct"
        )

    def test_prompts_are_substantive(self) -> None:
        for name in AgentName:
            path = _SYSTEM_PROMPT_DIR / f"{name.value.lower()}_system.md"
            assert len(path.read_text().strip()) > 100, (
                f"{name.value} prompt is too short — must be a real system prompt"
            )


# ── build_messages ─────────────────────────────────────────────────────────────


class TestBuildMessages:
    def test_first_message_role_is_system(self) -> None:
        agent = SubAgent(name=AgentName.DELTA, client=_FAKE_CLIENT)
        messages = agent.build_messages("analyze this")
        assert messages[0]["role"] == "system"

    def test_last_message_is_user_input(self) -> None:
        agent = SubAgent(name=AgentName.DELTA, client=_FAKE_CLIENT)
        messages = agent.build_messages("analyze this")
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "analyze this"

    def test_system_prompt_content_is_non_empty(self) -> None:
        agent = SubAgent(name=AgentName.DELTA, client=_FAKE_CLIENT)
        messages = agent.build_messages("x")
        assert len(messages[0]["content"]) > 0

    def test_build_messages_does_not_mutate_history(self) -> None:
        agent = SubAgent(name=AgentName.NOVA, client=_FAKE_CLIENT)
        before = len(agent._history)
        agent.build_messages("test message")
        assert len(agent._history) == before

    def test_history_appears_between_system_and_user(self) -> None:
        agent = SubAgent(name=AgentName.ECHO, client=_FAKE_CLIENT)
        # Manually plant history to test ordering
        agent._history = [
            {"role": "user", "content": "prior question"},
            {"role": "assistant", "content": "prior answer"},
        ]
        messages = agent.build_messages("new question")
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "prior question"
        assert messages[2]["content"] == "prior answer"
        assert messages[-1]["content"] == "new question"


# ── send (async, uses FakeLLMClient) ──────────────────────────────────────────


class TestSend:
    def test_send_appends_user_and_assistant_to_history(self) -> None:
        agent = SubAgent(name=AgentName.ECHO, client=_FAKE_CLIENT)
        assert len(agent._history) == 0
        asyncio.run(agent.send(session_id="sess_test", user_message="first"))
        assert len(agent._history) == 2  # user + assistant

    def test_send_returns_fake_content(self) -> None:
        agent = SubAgent(name=AgentName.DELTA, client=_FAKE_CLIENT)
        response = asyncio.run(
            agent.send(session_id="sess_test", user_message="query")
        )
        assert response.content == "fake response"
        assert response.latency_ms == 10
        assert response.total_tokens == 25  # prompt(20) + completion(5)

    def test_history_accumulates_across_multiple_sends(self) -> None:
        agent = SubAgent(name=AgentName.NOVA, client=_FAKE_CLIENT)
        asyncio.run(agent.send(session_id="sess_test", user_message="first"))
        asyncio.run(agent.send(session_id="sess_test", user_message="second"))
        assert len(agent._history) == 4  # 2 exchanges × (user + assistant)

    def test_send_preserves_history_in_subsequent_build_messages(self) -> None:
        agent = SubAgent(name=AgentName.DELTA, client=_FAKE_CLIENT)
        asyncio.run(agent.send(session_id="sess_test", user_message="first"))
        messages = agent.build_messages("second")
        # system + user1 + assistant1 + user2 = 4
        assert len(messages) == 4


# ── name property ──────────────────────────────────────────────────────────────


class TestProperties:
    @pytest.mark.parametrize("name", list(AgentName))
    def test_name_property_matches_constructor(self, name: AgentName) -> None:
        agent = SubAgent(name=name, client=_FAKE_CLIENT)
        assert agent.name == name
