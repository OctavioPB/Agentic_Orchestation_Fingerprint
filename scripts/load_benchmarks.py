"""Load benchmark profiles into Qdrant.

Usage:
    python scripts/load_benchmarks.py [--profiles-dir PATH] [--dry-run]

Reads every *.json file from the benchmark profiles directory, constructs
EmbeddingPoints from the stored centroids, and upserts them into Qdrant under
the collection 'orchid_embeddings'.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluator.embedding_etl import EmbeddingPoint  # type: ignore[attr-defined]
from services.evaluator.qdrant_store import QdrantStore
from services.evaluator.style_classifier import BenchmarkProfile

_DEFAULT_DIR = Path(__file__).parent.parent / "data" / "benchmarks" / "senior_engineer_profiles"


def _make_point_id(profile_id: str) -> int:
    import hashlib

    digest = hashlib.sha256(profile_id.encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big") & 0x7FFF_FFFF_FFFF_FFFF


async def _run(profiles_dir: Path, dry_run: bool) -> None:
    store = QdrantStore(
        host=os.environ.get("QDRANT_HOST", "localhost"),
        port=int(os.environ.get("QDRANT_PORT", 6333)),
        api_key=os.environ.get("QDRANT_API_KEY"),
    )

    if not dry_run:
        await store.create_collection_if_not_exists()

    profiles: list[BenchmarkProfile] = []
    for json_file in sorted(profiles_dir.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        profiles.append(BenchmarkProfile(**data))

    print(f"Loaded {len(profiles)} benchmark profiles from {profiles_dir}")

    points: list[EmbeddingPoint] = []
    for p in profiles:
        points.append(
            EmbeddingPoint(
                point_id=_make_point_id(p.profile_id),
                session_id="__benchmark__",
                event_id=p.profile_id,
                event_type="BENCHMARK_PROFILE",
                text=p.description,
                embedding=p.centroid,
                timestamp="",
            )
        )

    if dry_run:
        print(f"[dry-run] Would upsert {len(points)} benchmark points into Qdrant.")
        return

    upserted = await store.upsert(points)
    print(f"Upserted {upserted} benchmark points into Qdrant.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load benchmark profiles into Qdrant")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=_DEFAULT_DIR,
        help="Directory containing *.json benchmark profile files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be upserted without writing to Qdrant",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.profiles_dir, args.dry_run))


if __name__ == "__main__":
    main()
