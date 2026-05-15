"""ScenarioEngine — provisions and tears down assessment sessions via the API.

All orchestration logic lives here. Airflow DAGs are thin wrappers that call
``asyncio.run(engine.provision(...))`` and ``asyncio.run(engine.teardown(...))``.
"""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

_DEFAULT_SCENARIOS_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "scenarios" / "v1" / "configs"
)
_DEFAULT_API_BASE_URL = os.getenv("ORCHID_API_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChaosConfig(BaseModel):
    type: str
    trigger_at_sec: int
    target: str
    params: dict[str, Any] = Field(default_factory=dict)


class ScenarioConfig(BaseModel):
    scenario_id: str
    name: str
    version: str
    description: str
    chaos_config: ChaosConfig
    sandbox_image: str = "orchid-sandbox:latest"
    scenario_env: dict[str, str] = Field(default_factory=dict)
    expected_resolution_steps: int
    ai_solo_baseline_path: str
    max_duration_sec: int
    workspace_dir: str
    violations_count: int


class ProvisionResult(BaseModel):
    session_id: str
    scenario_id: str
    state: str
    started_at: datetime
    config: ScenarioConfig


class TeardownResult(BaseModel):
    session_id: str
    state: str
    ended_at: datetime
    duration_sec: float
    archived_log_path: str | None = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ScenarioEngine:
    """Provisions and tears down orchid assessment sessions.

    Accepts an optional ``http_client`` so tests can inject an
    ``httpx.AsyncClient`` backed by ``ASGITransport`` without running a server.
    """

    def __init__(
        self,
        api_base_url: str = _DEFAULT_API_BASE_URL,
        scenarios_dir: Path | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._scenarios_dir = scenarios_dir or _DEFAULT_SCENARIOS_DIR
        self._http_client = http_client

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def load_config(self, scenario_id: str) -> ScenarioConfig:
        """Load and validate the scenario config JSON for *scenario_id*."""
        path = self._scenarios_dir / f"{scenario_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"No config found for scenario '{scenario_id}' at {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ScenarioConfig.model_validate(raw)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_duration(self, started_at: datetime, ended_at: datetime) -> float:
        """Return elapsed seconds between two UTC-aware datetimes."""
        return (ended_at - started_at).total_seconds()

    # ------------------------------------------------------------------
    # Provision
    # ------------------------------------------------------------------

    async def provision(
        self,
        scenario_id: str,
        candidate_id: str,
        tenant_id: str = "default",
    ) -> ProvisionResult:
        """Create and activate a session for *scenario_id*.

        Makes a POST /sessions call to the orchid API. On success returns a
        ``ProvisionResult`` containing the full ``ScenarioConfig``.
        """
        config = self.load_config(scenario_id)
        payload = {
            "candidate_id": candidate_id,
            "scenario_id": scenario_id,
            "tenant_id": tenant_id,
        }

        log = logger.bind(scenario_id=scenario_id, candidate_id=candidate_id)
        log.info("provisioning_session")

        async with self._client_ctx() as client:
            t0 = time.monotonic()
            response = await client.post(
                f"{self._api_base_url}/sessions",
                json=payload,
                timeout=30.0,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

        response.raise_for_status()
        data = response.json()

        log.info(
            "session_provisioned",
            session_id=data["session_id"],
            state=data["state"],
            latency_ms=latency_ms,
        )

        return ProvisionResult(
            session_id=data["session_id"],
            scenario_id=scenario_id,
            state=data["state"],
            started_at=datetime.fromisoformat(data["started_at"]),
            config=config,
        )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def teardown(
        self,
        session_id: str,
        archive_dir: Path | None = None,
    ) -> TeardownResult:
        """Complete a session and optionally archive its log.

        Makes a DELETE /sessions/{session_id} call to the orchid API.
        """
        log = logger.bind(session_id=session_id)
        log.info("tearing_down_session")

        async with self._client_ctx() as client:
            t0 = time.monotonic()
            response = await client.delete(
                f"{self._api_base_url}/sessions/{session_id}",
                timeout=30.0,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

        response.raise_for_status()
        data = response.json()

        ended_at = datetime.now(UTC)
        started_at_raw = data.get("started_at")
        if started_at_raw:
            started_at = datetime.fromisoformat(started_at_raw)
            duration_sec = self._compute_duration(started_at, ended_at)
        else:
            duration_sec = 0.0

        archived_log_path: str | None = None
        if archive_dir is not None:
            archive_dir.mkdir(parents=True, exist_ok=True)
            log_file = archive_dir / f"{session_id}.json"
            log_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            archived_log_path = str(log_file)

        log.info(
            "session_torn_down",
            state=data.get("state"),
            duration_sec=duration_sec,
            latency_ms=latency_ms,
        )

        return TeardownResult(
            session_id=session_id,
            state=data.get("state", "COMPLETED"),
            ended_at=ended_at,
            duration_sec=duration_sec,
            archived_log_path=archived_log_path,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _client_ctx(self) -> httpx.AsyncClient:
        """Return the injected client if present, else create a new one."""
        if self._http_client is not None:
            return _NullAsyncContextManager(self._http_client)
        return httpx.AsyncClient()


class _NullAsyncContextManager:
    """Wraps an existing ``httpx.AsyncClient`` as an async context manager
    without closing it on exit — the owner manages the lifecycle."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *_: object) -> None:
        pass
