"""Style cluster classifier using K-Nearest Neighbours over benchmark centroids."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel

from services.evaluator.embeddings import cosine_similarity

logger = structlog.get_logger(__name__)

StyleCluster = Literal["architect", "executor", "debugger", "delegator"]

_K = 3  # neighbours for KNN vote


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class BenchmarkProfile(BaseModel):
    profile_id: str
    style_cluster: StyleCluster
    centroid: list[float]
    description: str = ""


# ---------------------------------------------------------------------------
# StyleClassifier
# ---------------------------------------------------------------------------


class StyleClassifier:
    def __init__(self, profiles: list[BenchmarkProfile]) -> None:
        if not profiles:
            raise ValueError("StyleClassifier requires at least one benchmark profile")
        self._profiles = profiles

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, session_centroid: list[float]) -> StyleCluster:
        """Return the most common cluster among the k nearest benchmark profiles."""
        scored = sorted(
            self._profiles,
            key=lambda p: cosine_similarity(session_centroid, p.centroid),
            reverse=True,
        )
        neighbours = scored[:_K]

        votes: dict[str, int] = {}
        for p in neighbours:
            votes[p.style_cluster] = votes.get(p.style_cluster, 0) + 1

        winner = max(votes, key=lambda c: votes[c])
        logger.info(
            "style_classified",
            result=winner,
            votes=votes,
            k=_K,
        )
        return winner  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_directory(cls, directory: str | Path) -> StyleClassifier:
        """Load all *.json benchmark profile files from a directory."""
        dir_path = Path(directory)
        profiles: list[BenchmarkProfile] = []
        for json_file in sorted(dir_path.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                profiles.append(BenchmarkProfile(**data))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "benchmark_profile_load_error",
                    file=str(json_file),
                    error=str(exc),
                )
        if not profiles:
            raise ValueError(f"No valid benchmark profiles found in {directory}")
        logger.info("benchmark_profiles_loaded", count=len(profiles), directory=str(dir_path))
        return cls(profiles)
