"""SQLAlchemy async engine and session factory.

Uses asyncpg driver. Connection URL is read from TENANT_DB_URL env var.
Call init_db() once at application startup to create all tables.
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

_DDL_CANDIDATES = """
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT        PRIMARY KEY,
    tenant_id    TEXT        NOT NULL,
    email        TEXT,
    name         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_DDL_API_KEYS = """
CREATE TABLE IF NOT EXISTS api_keys (
    key_id     TEXT PRIMARY KEY,
    tenant_id  TEXT NOT NULL,
    key_hash   TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_DDL_WEBHOOKS = """
CREATE TABLE IF NOT EXISTS webhooks (
    webhook_id TEXT        PRIMARY KEY,
    tenant_id  TEXT        NOT NULL,
    url        TEXT        NOT NULL,
    active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_DDL_FINGERPRINTS = """
CREATE TABLE IF NOT EXISTS fingerprints (
    session_id   TEXT        PRIMARY KEY,
    tenant_id    TEXT        NOT NULL,
    fingerprint  TEXT        NOT NULL,
    assembled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_ALL_DDL = [
    _DDL_SESSIONS,
    _DDL_CANDIDATES,
    _DDL_API_KEYS,
    _DDL_WEBHOOKS,
    _DDL_FINGERPRINTS,
]


async def init_db() -> None:
    """Create all tables if they don't exist. Idempotent — safe to call on every startup."""
    async with engine.begin() as conn:
        for ddl in _ALL_DDL:
            await conn.execute(text(ddl))
