"""Session state machine — pure Python, zero I/O. Safe to unit-test without mocks."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

logger = logging.getLogger(__name__)


class SessionState(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    CHAOS = "CHAOS"
    RESOLVING = "RESOLVING"
    COMPLETED = "COMPLETED"


_VALID_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.CREATED: frozenset({SessionState.ACTIVE}),
    SessionState.ACTIVE: frozenset({SessionState.CHAOS, SessionState.COMPLETED}),
    SessionState.CHAOS: frozenset({SessionState.RESOLVING, SessionState.COMPLETED}),
    SessionState.RESOLVING: frozenset({SessionState.COMPLETED}),
    SessionState.COMPLETED: frozenset(),
}


class InvalidTransitionError(Exception):
    """Raised when a requested state transition is not allowed by the session machine."""


@dataclass
class SessionRecord:
    session_id: str
    candidate_id: str
    scenario_id: str
    tenant_id: str = "default"
    state: SessionState = SessionState.CREATED
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None


class SessionManager:
    """In-memory session registry and state machine.

    Intentionally free of database, Kafka, or any I/O dependency so that it can
    be unit-tested without mocks. Persistence is handled by SessionRepository.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def create(
        self,
        candidate_id: str,
        scenario_id: str,
        tenant_id: str = "default",
        session_id: str | None = None,
    ) -> SessionRecord:
        sid = session_id or f"sess_{uuid.uuid4().hex[:16]}"
        record = SessionRecord(
            session_id=sid,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
            tenant_id=tenant_id,
        )
        self._sessions[sid] = record
        logger.info("session_created session_id=%s", sid)
        return record

    def transition(self, session_id: str, new_state: SessionState) -> SessionRecord:
        """Apply a state transition. Raises InvalidTransitionError if not allowed."""
        record = self._require(session_id)
        allowed = _VALID_TRANSITIONS[record.state]
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition {record.state!r} → {new_state!r} "
                f"for session {session_id!r}"
            )
        record.state = new_state
        if new_state == SessionState.COMPLETED:
            record.ended_at = datetime.now(UTC)
        logger.info(
            "session_transitioned session_id=%s state=%s", session_id, new_state
        )
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def all_sessions(self) -> list[SessionRecord]:
        return list(self._sessions.values())

    def _require(self, session_id: str) -> SessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(f"Session {session_id!r} not found")
        return record
