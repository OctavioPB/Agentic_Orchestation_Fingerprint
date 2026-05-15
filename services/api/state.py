"""Module-level singletons shared across FastAPI routes and WebSocket handlers.

Imported by both sessions.py and main.py to avoid circular imports.
All mutations happen inside async route handlers (single-threaded event loop).
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from services.api.session_manager import SessionManager

if TYPE_CHECKING:
    from services.evaluator.agents.sub_agent import SubAgent
    from services.telemetry.producer import TelemetryProducer

session_manager: SessionManager = SessionManager()

# session_id → agent_name (str) → SubAgent instance (one per session × agent pair)
agent_sessions: dict[str, dict[str, SubAgent]] = {}

# session_id → running asyncio timeout Task
timeout_tasks: dict[str, asyncio.Task[None]] = {}

# Kafka producer — initialized in lifespan, None if Kafka unavailable
producer: TelemetryProducer | None = None
