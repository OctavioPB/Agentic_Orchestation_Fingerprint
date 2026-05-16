"""All five orchestration scoring functions for Sprint 7.

Per CLAUDE.md Rule 4: efficiency_ratio is always computed relative to the
AI-solo baseline for the same scenario — never a static constant.

Score contract: all functions return a float in [0.0, 1.0].
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_BASELINES_DIR = Path(__file__).parent.parent.parent / "data" / "scenarios" / "agents" / "baseline"

# Error-type severity weights for trust_calibration (higher = more credit for catching it)
_ERROR_SEVERITY: dict[str, float] = {
    "hallucinated_column_name": 1.0,
    "hallucinated_table_name": 1.0,
    "hallucinated_value": 0.9,
    "scope_overreach": 0.8,
    "unauthorized_scope_expansion": 0.8,
    "wrong_api": 0.7,
    "over_engineered": 0.5,
    "clarification_flood": 0.4,
}
_DEFAULT_SEVERITY = 0.6

# Assumed scenario median recovery time (seconds) used when no external data is available
_MEDIAN_RECOVERY_SEC = 600.0

# Maximum correction-to-detect time we consider "fast" (anything beyond → score 0)
_MAX_VELOCITY_SEC = 600.0


# ---------------------------------------------------------------------------
# 1. efficiency_ratio
# ---------------------------------------------------------------------------


def efficiency_ratio(
    events: list[dict],
    scenario_id: str,
    baselines_dir: Path = _BASELINES_DIR,
) -> float:
    """Return candidate_speed / ai_solo_speed, clamped to [0, 1].

    A score of 1.0 means the candidate matched or beat the AI solo run.
    Requires a baseline JSON file at baselines_dir/<scenario_id_slug>.json.
    """
    baseline_sec = _load_baseline_duration(scenario_id, baselines_dir)
    if baseline_sec is None:
        logger.warning("efficiency_ratio_no_baseline", scenario_id=scenario_id)
        return 0.5  # neutral fallback

    started, ended = _session_time_bounds(events)
    if started is None or ended is None:
        logger.warning("efficiency_ratio_missing_timestamps")
        return 0.5

    candidate_sec = (ended - started).total_seconds()
    if candidate_sec <= 0:
        return 1.0

    score = min(1.0, baseline_sec / candidate_sec)
    logger.info(
        "score_efficiency_ratio",
        baseline_sec=baseline_sec,
        candidate_sec=candidate_sec,
        score=round(score, 4),
    )
    return round(score, 4)


# ---------------------------------------------------------------------------
# 2. trust_calibration
# ---------------------------------------------------------------------------


def trust_calibration(events: list[dict]) -> float:
    """Return weighted correction rate, normalised to [0, 1].

    Each CORRECTION_ISSUED contributes its error_type severity weight.
    The denominator is total AGENT_RESPONSE events (opportunities to correct).
    Score = 0 means blind trust (no corrections despite errors);
    Score = 1 means the candidate caught every high-severity mistake.
    """
    agent_responses = sum(1 for e in events if e.get("event_type") == "AGENT_RESPONSE")
    corrections = [e for e in events if e.get("event_type") == "CORRECTION_ISSUED"]

    if agent_responses == 0:
        return 0.0

    weighted_sum = sum(
        _ERROR_SEVERITY.get(
            c.get("payload", {}).get("error_type", ""), _DEFAULT_SEVERITY
        )
        for c in corrections
    )

    # Normalise: full score = every response corrected with max-weight errors
    # We cap at 1.0 — catching more than 100% is still 1.0
    score = min(1.0, weighted_sum / agent_responses)
    logger.info(
        "score_trust_calibration",
        corrections=len(corrections),
        agent_responses=agent_responses,
        weighted_sum=round(weighted_sum, 4),
        score=round(score, 4),
    )
    return round(score, 4)


# ---------------------------------------------------------------------------
# 3. correction_velocity
# ---------------------------------------------------------------------------


def correction_velocity(events: list[dict]) -> float:
    """Return normalised speed of detecting and correcting agent hallucinations.

    For each CORRECTION_ISSUED that references an AGENT_RESPONSE via
    `original_event_id`, the detection latency is:
        latency = ts(CORRECTION_ISSUED) - ts(original AGENT_RESPONSE)

    Score = 1 - (median_latency / MAX_VELOCITY_SEC), clamped to [0, 1].
    Fast correction → score near 1; very slow correction → score near 0.
    """
    event_by_id: dict[str, dict] = {e.get("event_id", ""): e for e in events}
    latencies: list[float] = []

    for event in events:
        if event.get("event_type") != "CORRECTION_ISSUED":
            continue
        orig_id = event.get("payload", {}).get("original_event_id")
        if not orig_id or orig_id not in event_by_id:
            continue
        original = event_by_id[orig_id]
        try:
            t_original = _parse_ts(original.get("timestamp", ""))
            t_correction = _parse_ts(event.get("timestamp", ""))
            latency = (t_correction - t_original).total_seconds()
            if latency >= 0:
                latencies.append(latency)
        except (ValueError, TypeError):
            continue

    if not latencies:
        return 0.5  # no corrections to measure

    median_latency = statistics.median(latencies)
    score = max(0.0, 1.0 - (median_latency / _MAX_VELOCITY_SEC))
    logger.info(
        "score_correction_velocity",
        n_corrections=len(latencies),
        median_latency_sec=round(median_latency, 1),
        score=round(score, 4),
    )
    return round(score, 4)


# ---------------------------------------------------------------------------
# 4. decomposition_score
# ---------------------------------------------------------------------------


def decomposition_score(prompt_scores: list[Any]) -> float:
    """Return mean Shadow Agent prompt quality score, normalised to [0, 1].

    Accepts a list of PromptScore objects (or dicts with 'clarity',
    'specificity', 'context_richness' keys). Each dimension is 0–10.
    """
    if not prompt_scores:
        return 0.0

    means: list[float] = []
    for ps in prompt_scores:
        if hasattr(ps, "mean_score"):
            means.append(ps.mean_score)
        else:
            c = ps.get("clarity", 0)
            s = ps.get("specificity", 0)
            r = ps.get("context_richness", 0)
            means.append((c + s + r) / 3.0)

    score = min(1.0, statistics.mean(means) / 10.0)
    logger.info("score_decomposition", n_prompts=len(means), score=round(score, 4))
    return round(score, 4)


# ---------------------------------------------------------------------------
# 5. chaos_resilience
# ---------------------------------------------------------------------------


def chaos_resilience(
    events: list[dict],
    median_recovery_sec: float = _MEDIAN_RECOVERY_SEC,
) -> float:
    """Return chaos resilience score in [0, 1].

    Measures how quickly and deliberately the candidate responded after
    CHAOS_INJECTED. Two components:
        - first_response_speed: how quickly the first PROMPT_SENT arrived
          after CHAOS_INJECTED (faster = better)
        - recovery_thoroughness: 1.0 if a recovery-oriented PROMPT_SENT or
          CODE_EXECUTED appeared within median_recovery_sec, else proportional

    Final score = mean of the two components.
    """
    chaos_ts = _chaos_injection_ts(events)
    if chaos_ts is None:
        logger.warning("chaos_resilience_no_chaos_event")
        return 0.5

    post_chaos = [
        e for e in events
        if e.get("event_type") in {"PROMPT_SENT", "CODE_EXECUTED"}
        and _parse_ts_safe(e.get("timestamp", "")) is not None
        and (_parse_ts_safe(e.get("timestamp", "")) - chaos_ts).total_seconds() > 0  # type: ignore[operator]
    ]

    if not post_chaos:
        return 0.0

    first_post = min(
        post_chaos,
        key=lambda e: (_parse_ts_safe(e.get("timestamp", "")) - chaos_ts).total_seconds(),  # type: ignore[operator]
    )
    first_latency = (_parse_ts_safe(first_post.get("timestamp", "")) - chaos_ts).total_seconds()  # type: ignore[operator]

    # First response speed: normalised against the median baseline
    first_response_speed = max(0.0, 1.0 - (first_latency / median_recovery_sec))

    # Recovery thoroughness: did a recovery action arrive before deadline?
    deadline_events = [
        e for e in post_chaos
        if (  # type: ignore[operator]
            _parse_ts_safe(e.get("timestamp", "")) - chaos_ts
        ).total_seconds() <= median_recovery_sec
    ]
    recovery_thoroughness = min(1.0, len(deadline_events) / 3.0)  # ≥3 actions = full score

    score = (first_response_speed + recovery_thoroughness) / 2.0
    logger.info(
        "score_chaos_resilience",
        first_latency_sec=round(first_latency, 1),
        first_response_speed=round(first_response_speed, 4),
        recovery_thoroughness=round(recovery_thoroughness, 4),
        score=round(score, 4),
    )
    return round(score, 4)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _load_baseline_duration(scenario_id: str, baselines_dir: Path) -> float | None:
    """Look up AI-solo baseline duration for the given scenario."""
    slug = scenario_id.replace("scenario_", "").replace("_v1", "").replace("_", "_")
    candidates = [
        baselines_dir / f"{scenario_id}.json",
        baselines_dir / f"{slug}_ai_solo.json",
        *baselines_dir.glob(f"*{slug}*.json"),
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return float(data["total_duration_sec"])
            except (KeyError, ValueError, OSError):
                continue
    return None


def _session_time_bounds(
    events: list[dict],
) -> tuple[datetime | None, datetime | None]:
    started = next(
        (
            _parse_ts_safe(e.get("timestamp", ""))
            for e in events
            if e.get("event_type") == "SCENARIO_STARTED"
        ),
        None,
    )
    ended = next(
        (
            _parse_ts_safe(e.get("timestamp", ""))
            for e in events
            if e.get("event_type") == "SCENARIO_ENDED"
        ),
        None,
    )
    return started, ended


def _chaos_injection_ts(events: list[dict]) -> datetime | None:
    for e in events:
        if e.get("event_type") == "CHAOS_INJECTED":
            injected_at = e.get("payload", {}).get("injected_at") or e.get("timestamp", "")
            return _parse_ts_safe(injected_at)
    return None


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _parse_ts_safe(ts: str) -> datetime | None:
    try:
        return _parse_ts(ts)
    except (ValueError, AttributeError):
        return None
