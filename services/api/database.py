"""SQLAlchemy async engine and session factory.

Uses asyncpg driver. Connection URL is read from TENANT_DB_URL env var.
Call init_db() once at application startup to create the sessions table.
"""
from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DATABASE_URL = os.getenv(
    "TENANT_DB_URL",
    "postgresql+asyncpg://orchid:orchid@localhost:5432/orchid",
)

engine = create_async_engine(_DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

_DDL_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT        PRIMARY KEY,
    candidate_id TEXT        NOT NULL,
    scenario_id  TEXT        NOT NULL,
    tenant_id    TEXT        NOT NULL DEFAULT 'default',
    state        TEXT        NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL,
    ended_at     TIMESTAMPTZ
);
"""


async def init_db() -> None:
    """Create tables if they don't exist. Idempotent — safe to call on every startup."""
    async with engine.begin() as conn:
        await conn.execute(text(_DDL_SESSIONS))
