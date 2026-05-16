"""Unit tests for StyleClassifier and BenchmarkProfile."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from services.evaluator.embeddings import synthesize_centroid
from services.evaluator.style_classifier import BenchmarkProfile, StyleClassifier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(profile_id: str, cluster: str, dims: int = 8) -> BenchmarkProfile:
    return BenchmarkProfile(
        profile_id=profile_id,
        style_cluster=cluster,  # type: ignore[arg-type]
        centroid=synthesize_centroid(profile_id, cluster, dims=dims),
        description=f"Synthetic {cluster} profile",
    )


def _make_classifier(*cluster_ids: tuple[str, str], dims: int = 8) -> StyleClassifier:
    profiles = [_profile(pid, cluster, dims) for pid, cluster in cluster_ids]
    return StyleClassifier(profiles)


# ---------------------------------------------------------------------------
# BenchmarkProfile
# ---------------------------------------------------------------------------


class TestBenchmarkProfile:
    def test_valid_clusters_accepted(self) -> None:
        for cluster in ("architect", "executor", "debugger", "delegator"):
            p = BenchmarkProfile(
                profile_id="test",
                style_cluster=cluster,  # type: ignore[arg-type]
                centroid=[0.0],
            )
            assert p.style_cluster == cluster

    def test_description_defaults_to_empty(self) -> None:
        p = BenchmarkProfile(
            profile_id="x", style_cluster="architect", centroid=[1.0]  # type: ignore[arg-type]
        )
        assert p.description == ""

    def test_json_roundtrip(self) -> None:
        p = _profile("arch_01", "architect")
        restored = BenchmarkProfile(**json.loads(p.model_dump_json()))
        assert restored.profile_id == p.profile_id
        assert restored.style_cluster == p.style_cluster
        assert len(restored.centroid) == len(p.centroid)


# ---------------------------------------------------------------------------
# StyleClassifier construction
# ---------------------------------------------------------------------------


class TestStyleClassifierConstruction:
    def test_empty_profiles_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            StyleClassifier([])

    def test_single_profile_works(self) -> None:
        clf = _make_classifier(("p1", "architect"))
        assert clf.classify(synthesize_centroid("p1", "architect", dims=8)) == "architect"


# ---------------------------------------------------------------------------
# KNN classification
# ---------------------------------------------------------------------------


class TestKNNClassification:
    def test_exact_match_returns_correct_cluster(self) -> None:
        clf = _make_classifier(
            ("a1", "architect"),
            ("e1", "executor"),
            ("d1", "debugger"),
        )
        # A centroid identical to architect_001 should classify as architect
        centroid = synthesize_centroid("a1", "architect", dims=8)
        assert clf.classify(centroid) == "architect"

    def test_majority_vote_breaks_tie(self) -> None:
        """3 architect profiles vs 1 executor → architect wins k=3."""
        clf = _make_classifier(
            ("arch_a", "architect"),
            ("arch_b", "architect"),
            ("arch_c", "architect"),
            ("exec_a", "executor"),
        )
        # Use arch_a's centroid — all three arch profiles should be nearest
        centroid = synthesize_centroid("arch_a", "architect", dims=8)
        result = clf.classify(centroid)
        assert result == "architect"

    def test_returns_valid_cluster_string(self) -> None:
        clf = _make_classifier(
            ("d1", "debugger"),
            ("d2", "delegator"),
            ("e1", "executor"),
        )
        centroid = [0.1] * 8
        result = clf.classify(centroid)
        assert result in ("architect", "executor", "debugger", "delegator")

    def test_classify_with_realistic_dims(self) -> None:
        """Smoke test with 1536-dim centroids — should not error."""
        clf = _make_classifier(
            ("x1", "architect"),
            ("x2", "executor"),
            ("x3", "debugger"),
            dims=1536,
        )
        centroid = synthesize_centroid("x1", "architect", dims=1536)
        result = clf.classify(centroid)
        assert result in ("architect", "executor", "debugger", "delegator")


# ---------------------------------------------------------------------------
# from_directory
# ---------------------------------------------------------------------------


class TestFromDirectory:
    def _write_profile(self, dir_path: Path, profile_id: str, cluster: str) -> None:
        p = _profile(profile_id, cluster)
        (dir_path / f"{profile_id}.json").write_text(
            p.model_dump_json(), encoding="utf-8"
        )

    def test_loads_all_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for pid, cluster in [("a1", "architect"), ("e1", "executor"), ("d1", "debugger")]:
                self._write_profile(d, pid, cluster)
            clf = StyleClassifier.from_directory(d)
            # Should not raise; we can classify with the loaded profiles
            centroid = synthesize_centroid("a1", "architect", dims=8)
            assert clf.classify(centroid) in ("architect", "executor", "debugger", "delegator")

    def test_empty_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError, match="No valid benchmark profiles"):
                StyleClassifier.from_directory(tmp)

    def test_invalid_json_skipped_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            # valid profile
            self._write_profile(d, "good", "executor")
            # corrupt file
            (d / "bad.json").write_text("{invalid json", encoding="utf-8")
            clf = StyleClassifier.from_directory(d)
            centroid = synthesize_centroid("good", "executor", dims=8)
            assert clf.classify(centroid) in ("architect", "executor", "debugger", "delegator")

    def test_loads_real_benchmark_profiles(self) -> None:
        """Verify the 10 profiles in data/benchmarks/ parse correctly."""
        profiles_dir = (
            Path(__file__).parent.parent.parent
            / "data"
            / "benchmarks"
            / "senior_engineer_profiles"
        )
        if not profiles_dir.exists():
            pytest.skip("Benchmark profiles directory not found")
        clf = StyleClassifier.from_directory(profiles_dir)
        # 10 profiles expected
        assert len(clf._profiles) == 10  # noqa: SLF001

    def test_real_profiles_cover_all_four_clusters(self) -> None:
        profiles_dir = (
            Path(__file__).parent.parent.parent
            / "data"
            / "benchmarks"
            / "senior_engineer_profiles"
        )
        if not profiles_dir.exists():
            pytest.skip("Benchmark profiles directory not found")
        clf = StyleClassifier.from_directory(profiles_dir)
        clusters = {p.style_cluster for p in clf._profiles}  # noqa: SLF001
        assert clusters == {"architect", "executor", "debugger", "delegator"}
