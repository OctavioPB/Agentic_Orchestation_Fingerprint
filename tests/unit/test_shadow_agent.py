"""Unit tests for ShadowAgent — no LLM calls required."""

from __future__ import annotations

import asyncio
import json

import pytest

from services.evaluator.agents.llm_client import LLMClient, LLMResponse
from services.evaluator.shadow_agent import (
    PromptScore,
    ShadowAgent,
    ShadowAgentResult,
)

# ---------------------------------------------------------------------------
# Fake LLM client
# ---------------------------------------------------------------------------


class _FakeLLMClient(LLMClient):
    def __init__(self, response_json: dict | None = None, fail: bool = False) -> None:
        self._response = response_json or {}
        self._fail = fail
        self.calls: list[list[dict]] = []

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if self._fail:
            raise RuntimeError("fake LLM failure")
        return LLMResponse(
            content=json.dumps(self._response),
            model=model,
            latency_ms=10,
            prompt_tokens=50,
            completion_tokens=100,
        )


def _make_default_response(n_prompts: int = 2) -> dict:
    return {
        "prompt_scores": [
            {
                "event_id": f"evt_{i:03d}",
                "clarity": 8,
                "specificity": 7,
                "context_richness": 6,
                "rationale": "clear and scoped",
            }
            for i in range(n_prompts)
        ],
        "reasoning_trace": ["Candidate diagnosed the issue.", "Candidate delegated precisely."],
        "style_cluster": "architect",
        "style_narrative": "The candidate shows strong architectural instincts.",
    }


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


def _evt(event_type: str, event_id: str, agent: str = "DELTA", text: str = "fix this") -> dict:
    payload: dict = {}
    if event_type == "PROMPT_SENT":
        payload = {"agent": agent, "text": text}
    elif event_type == "CORRECTION_ISSUED":
        payload = {
            "agent": agent,
            "correction_text": text,
            "error_type": "hallucinated_column_name",
        }
    elif event_type == "AGENT_RESPONSE":
        payload = {"agent": agent, "text": "response", "latency_ms": 500}
    return {
        "event_id": event_id,
        "timestamp": "2026-05-10T09:00:00Z",
        "event_type": event_type,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# build_transcript (pure, no LLM)
# ---------------------------------------------------------------------------


class TestBuildTranscript:
    def test_filters_to_prompt_and_correction_only(self) -> None:
        events = [
            _evt("SCENARIO_STARTED", "e1"),
            _evt("PROMPT_SENT", "e2"),
            _evt("AGENT_RESPONSE", "e3"),
            _evt("CORRECTION_ISSUED", "e4"),
            _evt("CODE_EXECUTED", "e5"),
            _evt("SCENARIO_ENDED", "e6"),
        ]
        transcript = ShadowAgent.build_transcript(events)
        types = [e["event_type"] for e in transcript]
        assert types == ["PROMPT_SENT", "CORRECTION_ISSUED"]

    def test_preserves_order(self) -> None:
        events = [
            _evt("PROMPT_SENT", "e1"),
            _evt("AGENT_RESPONSE", "e2"),
            _evt("PROMPT_SENT", "e3"),
            _evt("CORRECTION_ISSUED", "e4"),
        ]
        transcript = ShadowAgent.build_transcript(events)
        ids = [e["event_id"] for e in transcript]
        assert ids == ["e1", "e3", "e4"]

    def test_empty_events(self) -> None:
        assert ShadowAgent.build_transcript([]) == []

    def test_no_embeddable_events_returns_empty(self) -> None:
        events = [_evt("AGENT_RESPONSE", "e1"), _evt("CODE_EXECUTED", "e2")]
        assert ShadowAgent.build_transcript(events) == []

    def test_chaos_injected_excluded(self) -> None:
        events = [_evt("CHAOS_INJECTED", "e1"), _evt("PROMPT_SENT", "e2")]
        transcript = ShadowAgent.build_transcript(events)
        assert len(transcript) == 1
        assert transcript[0]["event_type"] == "PROMPT_SENT"


# ---------------------------------------------------------------------------
# _format_transcript (pure)
# ---------------------------------------------------------------------------


class TestFormatTranscript:
    def test_prompt_sent_formatted(self) -> None:
        events = [_evt("PROMPT_SENT", "e1", text="Diagnose the pipeline")]
        text = ShadowAgent._format_transcript(events)  # noqa: SLF001
        assert "PROMPT_SENT" in text
        assert "Diagnose the pipeline" in text
        assert "e1" in text

    def test_correction_issued_formatted(self) -> None:
        events = [_evt("CORRECTION_ISSUED", "e2", text="That column name is wrong")]
        text = ShadowAgent._format_transcript(events)  # noqa: SLF001
        assert "CORRECTION_ISSUED" in text
        assert "That column name is wrong" in text

    def test_empty_transcript_shows_header(self) -> None:
        text = ShadowAgent._format_transcript([])  # noqa: SLF001
        assert "SESSION TRANSCRIPT" in text


# ---------------------------------------------------------------------------
# _parse_response (pure)
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_valid_json_parses_correctly(self) -> None:
        raw = json.dumps(_make_default_response(2))
        result = ShadowAgent._parse_response(raw)  # noqa: SLF001
        assert len(result.prompt_scores) == 2
        assert result.style_cluster == "architect"
        assert len(result.reasoning_trace) == 2
        assert "architectural" in result.style_narrative

    def test_markdown_code_block_stripped(self) -> None:
        raw = "```json\n" + json.dumps(_make_default_response()) + "\n```"
        result = ShadowAgent._parse_response(raw)  # noqa: SLF001
        assert len(result.prompt_scores) == 2

    def test_invalid_json_returns_empty_result(self) -> None:
        result = ShadowAgent._parse_response("not json at all {{{")  # noqa: SLF001
        assert result.prompt_scores == []
        assert result.reasoning_trace == []

    def test_partial_json_returns_empty_result(self) -> None:
        result = ShadowAgent._parse_response('{"broken":')  # noqa: SLF001
        assert result.style_cluster is None

    def test_all_four_clusters_accepted(self) -> None:
        for cluster in ("architect", "executor", "debugger", "delegator"):
            raw = json.dumps({**_make_default_response(), "style_cluster": cluster})
            result = ShadowAgent._parse_response(raw)  # noqa: SLF001
            assert result.style_cluster == cluster


# ---------------------------------------------------------------------------
# PromptScore
# ---------------------------------------------------------------------------


class TestPromptScore:
    def test_mean_score_computed(self) -> None:
        ps = PromptScore(event_id="e1", clarity=9, specificity=7, context_richness=8)
        assert ps.mean_score == pytest.approx(8.0)

    def test_all_zero_mean(self) -> None:
        ps = PromptScore(event_id="e1", clarity=0, specificity=0, context_richness=0)
        assert ps.mean_score == pytest.approx(0.0)

    def test_max_scores(self) -> None:
        ps = PromptScore(event_id="e1", clarity=10, specificity=10, context_richness=10)
        assert ps.mean_score == pytest.approx(10.0)

    def test_scores_validated_bounds(self) -> None:
        with pytest.raises(Exception):
            PromptScore(event_id="e1", clarity=11, specificity=5, context_richness=5)


# ---------------------------------------------------------------------------
# ShadowAgent.evaluate (with fake LLM)
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_calls_llm_once(self) -> None:
        client = _FakeLLMClient(_make_default_response())
        agent = ShadowAgent(llm_client=client)
        events = [_evt("PROMPT_SENT", "e1"), _evt("CORRECTION_ISSUED", "e2")]
        asyncio.run(agent.evaluate(events))
        assert len(client.calls) == 1

    def test_system_prompt_is_first_message(self) -> None:
        client = _FakeLLMClient(_make_default_response())
        agent = ShadowAgent(llm_client=client)
        events = [_evt("PROMPT_SENT", "e1")]
        asyncio.run(agent.evaluate(events))
        messages = client.calls[0]
        assert messages[0]["role"] == "system"
        assert "Shadow Agent" in messages[0]["content"]

    def test_only_transcript_events_sent_to_llm(self) -> None:
        client = _FakeLLMClient(_make_default_response())
        agent = ShadowAgent(llm_client=client)
        events = [
            _evt("SCENARIO_STARTED", "e1"),
            _evt("PROMPT_SENT", "e2", text="fix the broker"),
            _evt("AGENT_RESPONSE", "e3"),
            _evt("CORRECTION_ISSUED", "e4", text="wrong column"),
        ]
        asyncio.run(agent.evaluate(events))
        user_message = client.calls[0][-1]["content"]
        assert "fix the broker" in user_message
        assert "wrong column" in user_message
        assert "AGENT_RESPONSE" not in user_message

    def test_empty_events_returns_empty_result_without_llm(self) -> None:
        client = _FakeLLMClient()
        agent = ShadowAgent(llm_client=client)
        result = asyncio.run(agent.evaluate([]))
        assert client.calls == []
        assert isinstance(result, ShadowAgentResult)

    def test_no_transcript_events_skips_llm(self) -> None:
        client = _FakeLLMClient()
        agent = ShadowAgent(llm_client=client)
        events = [_evt("AGENT_RESPONSE", "e1"), _evt("CODE_EXECUTED", "e2")]
        result = asyncio.run(agent.evaluate(events))
        assert client.calls == []
        assert result.prompt_scores == []

    def test_returns_shadow_agent_result(self) -> None:
        client = _FakeLLMClient(_make_default_response())
        agent = ShadowAgent(llm_client=client)
        events = [_evt("PROMPT_SENT", "e1")]
        result = asyncio.run(agent.evaluate(events))
        assert isinstance(result, ShadowAgentResult)
        assert result.style_cluster == "architect"

    def test_real_session_transcript_sent_correctly(self) -> None:
        """Smoke test: session_001 events produce a non-empty transcript."""
        import json
        from pathlib import Path

        fixture = Path(__file__).parent.parent.parent / "data" / "synthetic" / "session_001.json"
        session = json.loads(fixture.read_text(encoding="utf-8"))
        events = session["events"]

        client = _FakeLLMClient(_make_default_response(n_prompts=5))
        agent = ShadowAgent(llm_client=client)
        result = asyncio.run(agent.evaluate(events))
        # session_001 has 5 PROMPT_SENT + 2 CORRECTION_ISSUED events
        assert len(result.prompt_scores) == 5
        assert result.style_cluster == "architect"
