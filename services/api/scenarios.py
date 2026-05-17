"""GET /scenarios — list available assessment scenarios from data/scenarios/."""
from __future__ import annotations

import json
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends

from services.api.auth import get_current_tenant
from services.api.models import ScenarioSummary
from services.api.rate_limiter import check_rate_limit

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_SCENARIOS_DIR = Path(__file__).parent.parent.parent / "data" / "scenarios"


@router.get("", response_model=list[ScenarioSummary])
async def list_scenarios(
    tenant_id: str = Depends(get_current_tenant),
) -> list[ScenarioSummary]:
    """Return all available scenarios. Every authenticated tenant sees the same catalogue."""
    check_rate_limit(tenant_id)
    results: list[ScenarioSummary] = []
    for meta_file in sorted(_SCENARIOS_DIR.glob("*/meta.json")):
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            results.append(
                ScenarioSummary(
                    scenario_id=data["scenario_id"],
                    name=data.get("name", data["scenario_id"]),
                    difficulty=data.get("difficulty", "medium"),
                    description=data.get("description", ""),
                    chaos_component=data.get("chaos_component"),
                )
            )
        except (KeyError, ValueError, OSError) as exc:
            logger.warning(
                "scenario_meta_parse_error",
                file=str(meta_file),
                error=str(exc),
            )
    return results
