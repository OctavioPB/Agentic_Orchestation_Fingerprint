"""Unit tests for the session state machine — no I/O, no mocks required."""
from __future__ import annotations

import pytest

from services.api.session_manager import (
    InvalidTransitionError,
    SessionManager,
    SessionState,
)


@pytest.fixture()
def manager() -> SessionManager:
    return SessionManager()


# ── Creation ───────────────────────────────────────────────────────────────────


class TestSessionCreation:
    def test_initial_state_is_created(self, manager: SessionManager) -> None:
        record = manager.create(candidate_id="c1", scenario_id="s1")
        assert record.state == SessionState.CREATED

    def test_create_assigns_prefixed_session_id(self, manager: SessionManager) -> None:
        record = manager.create(candidate_id="c1", scenario_id="s1")
        assert record.session_id.startswith("sess_")

    def test_custom_session_id_is_used(self, manager: SessionManager) -> None:
        record = manager.create(
            candidate_id="c1", scenario_id="s1", session_id="sess_custom"
        )
        assert record.session_id == "sess_custom"

    def test_get_returns_same_record(self, manager: SessionManager) -> None:
        record = manager.create(candidate_id="c1", scenario_id="s1")
        assert manager.get(record.session_id) is record

    def test_get_nonexistent_returns_none(self, manager: SessionManager) -> None:
        assert manager.get("sess_does_not_exist") is None

    def test_ended_at_is_none_after_creation(self, manager: SessionManager) -> None:
        record = manager.create(candidate_id="c1", scenario_id="s1")
        assert record.ended_at is None


# ── Valid transitions ──────────────────────────────────────────────────────────


class TestValidTransitions:
    def test_created_to_active(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        result = manager.transition(r.session_id, SessionState.ACTIVE)
        assert result.state == SessionState.ACTIVE

    def test_active_to_chaos(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        result = manager.transition(r.session_id, SessionState.CHAOS)
        assert result.state == SessionState.CHAOS

    def test_active_to_completed(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        result = manager.transition(r.session_id, SessionState.COMPLETED)
        assert result.state == SessionState.COMPLETED

    def test_chaos_to_resolving(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        manager.transition(r.session_id, SessionState.CHAOS)
        result = manager.transition(r.session_id, SessionState.RESOLVING)
        assert result.state == SessionState.RESOLVING

    def test_chaos_to_completed(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        manager.transition(r.session_id, SessionState.CHAOS)
        result = manager.transition(r.session_id, SessionState.COMPLETED)
        assert result.state == SessionState.COMPLETED

    def test_resolving_to_completed(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        manager.transition(r.session_id, SessionState.CHAOS)
        manager.transition(r.session_id, SessionState.RESOLVING)
        result = manager.transition(r.session_id, SessionState.COMPLETED)
        assert result.state == SessionState.COMPLETED


# ── Invalid transitions ────────────────────────────────────────────────────────


class TestInvalidTransitions:
    def test_created_to_chaos_raises(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        with pytest.raises(InvalidTransitionError):
            manager.transition(r.session_id, SessionState.CHAOS)

    def test_created_to_completed_raises(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        with pytest.raises(InvalidTransitionError):
            manager.transition(r.session_id, SessionState.COMPLETED)

    def test_created_to_resolving_raises(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        with pytest.raises(InvalidTransitionError):
            manager.transition(r.session_id, SessionState.RESOLVING)

    def test_completed_to_active_raises(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        manager.transition(r.session_id, SessionState.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            manager.transition(r.session_id, SessionState.ACTIVE)

    def test_completed_to_chaos_raises(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        manager.transition(r.session_id, SessionState.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            manager.transition(r.session_id, SessionState.CHAOS)

    def test_unknown_session_raises_key_error(self, manager: SessionManager) -> None:
        with pytest.raises(KeyError):
            manager.transition("sess_phantom", SessionState.ACTIVE)


# ── Completion semantics ───────────────────────────────────────────────────────


class TestCompletionSemantics:
    def test_ended_at_set_on_completion(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        manager.transition(r.session_id, SessionState.COMPLETED)
        assert r.ended_at is not None

    def test_ended_at_still_none_while_active(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        assert r.ended_at is None

    def test_ended_at_still_none_while_in_chaos(self, manager: SessionManager) -> None:
        r = manager.create(candidate_id="c1", scenario_id="s1")
        manager.transition(r.session_id, SessionState.ACTIVE)
        manager.transition(r.session_id, SessionState.CHAOS)
        assert r.ended_at is None


# ── Isolation between sessions ─────────────────────────────────────────────────


class TestSessionIsolation:
    def test_two_sessions_are_independent(self, manager: SessionManager) -> None:
        r1 = manager.create(candidate_id="c1", scenario_id="s1")
        r2 = manager.create(candidate_id="c2", scenario_id="s1")
        manager.transition(r1.session_id, SessionState.ACTIVE)
        assert r2.state == SessionState.CREATED

    def test_all_sessions_returns_both(self, manager: SessionManager) -> None:
        manager.create(candidate_id="c1", scenario_id="s1")
        manager.create(candidate_id="c2", scenario_id="s1")
        assert len(manager.all_sessions()) == 2
