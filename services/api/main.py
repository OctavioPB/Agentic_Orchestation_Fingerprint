"""orchid API — FastAPI application entry point.

Exposes:
  REST  : /sessions  (see sessions.py router)
  WS    : /ws/session/{session_id}/agent/{agent_name}
"""
from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from services.api import state
from services.api.admin import router as admin_router
from services.api.candidates import router as candidates_router
from services.api.demo import router as demo_router
from services.api.scenarios import router as scenarios_router
from services.api.session_manager import SessionState
from services.api.sessions import router as sessions_router
from services.api.webhooks import router as webhooks_router
from services.evaluator.agents.llm_client import OpenAILLMClient
from services.evaluator.agents.sub_agent import SubAgent
from services.telemetry.models import (
    AgentName,
    AgentResponsePayload,
    PromptSentPayload,
    TelemetryEvent,
)

logger = structlog.get_logger(__name__)

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")


# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Initialize Kafka producer (best-effort — API works without Kafka)
    try:
        from services.telemetry.producer import TelemetryProducer

        state.producer = TelemetryProducer(bootstrap_servers=_KAFKA_BOOTSTRAP)
        logger.info("kafka_producer_ready", bootstrap=_KAFKA_BOOTSTRAP)
    except Exception as exc:
        logger.warning("kafka_producer_unavailable", error=str(exc))
        state.producer = None

    # Initialize DB schema (best-effort)
    try:
        from services.api.database import init_db

        await init_db()
        logger.info("db_schema_initialized")
    except Exception as exc:
        logger.warning("db_init_failed", error=str(exc))

    yield

    # Shutdown: cancel all timeout tasks, close Kafka producer
    for task in list(state.timeout_tasks.values()):
        task.cancel()
    if state.producer:
        state.producer.close()
    logger.info("orchid_api_stopped")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="orchid API", version="0.1.0", lifespan=lifespan)

_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(demo_router)
app.include_router(sessions_router)
app.include_router(candidates_router)
app.include_router(webhooks_router)
app.include_router(scenarios_router)
app.include_router(admin_router)


# ── WebSocket endpoint ─────────────────────────────────────────────────────────


@app.websocket("/ws/session/{session_id}/agent/{agent_name}")
async def agent_websocket(
    websocket: WebSocket,
    session_id: str,
    agent_name: str,
) -> None:
    """Real-time WebSocket channel between the sandbox and a sub-agent.

    Protocol (JSON):
      client → server : {"message": "<candidate instruction>"}
      server → client : {"agent": "DELTA", "response": "...", "latency_ms": N, "token_count": N}
      server → client : {"error": "<description>"}  on non-fatal errors
    """
    # Validate session
    record = state.session_manager.get(session_id)
    if record is None:
        await websocket.close(code=4404, reason="session not found")
        return
    if record.state != SessionState.ACTIVE:
        await websocket.close(
            code=4409, reason=f"session not active (state={record.state})"
        )
        return

    # Validate agent name
    try:
        agent_enum = AgentName(agent_name.upper())
    except ValueError:
        await websocket.close(code=4400, reason=f"unknown agent: {agent_name!r}")
        return

    await websocket.accept()
    logger.info("ws_connected", session_id=session_id, agent=agent_name)

    # Get or create SubAgent instance for this session × agent pair
    if session_id not in state.agent_sessions:
        state.agent_sessions[session_id] = {}
    if agent_name not in state.agent_sessions[session_id]:
        client = OpenAILLMClient(api_key=_OPENAI_API_KEY)
        state.agent_sessions[session_id][agent_name] = SubAgent(
            name=agent_enum, client=client
        )
    sub_agent = state.agent_sessions[session_id][agent_name]

    try:
        while True:
            raw = await websocket.receive_text()

            # Parse incoming message
            try:
                data = json.loads(raw)
                user_message: str = data.get("message", "")
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"error": "invalid JSON — expected {\"message\": \"...\"}"}),
                )
                continue

            if not user_message.strip():
                continue

            # Emit PROMPT_SENT to Kafka (best-effort)
            if state.producer:
                try:
                    prompt_event = TelemetryEvent.prompt_sent(
                        session_id,
                        PromptSentPayload(agent=agent_enum, text=user_message),
                    )
                    await state.producer.emit(prompt_event)
                except Exception as exc:
                    logger.warning("kafka_emit_failed", event="PROMPT_SENT", error=str(exc))

            # Call sub-agent
            try:
                response = await sub_agent.send(
                    session_id=session_id, user_message=user_message
                )
            except Exception as exc:
                logger.error("sub_agent_error", session_id=session_id, error=str(exc))
                await websocket.send_text(
                    json.dumps({"error": f"agent error: {exc}"}),
                )
                continue

            # Emit AGENT_RESPONSE to Kafka (best-effort)
            if state.producer:
                try:
                    resp_event = TelemetryEvent.agent_response(
                        session_id,
                        AgentResponsePayload(
                            agent=agent_enum,
                            text=response.content,
                            model=response.model,
                            latency_ms=response.latency_ms,
                            token_count=response.total_tokens,
                        ),
                    )
                    await state.producer.emit(resp_event)
                except Exception as exc:
                    logger.warning(
                        "kafka_emit_failed", event="AGENT_RESPONSE", error=str(exc)
                    )

            # Send response to client
            await websocket.send_text(
                json.dumps(
                    {
                        "agent": agent_enum.value,
                        "response": response.content,
                        "latency_ms": response.latency_ms,
                        "token_count": response.total_tokens,
                    }
                )
            )

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id, agent=agent_name)
