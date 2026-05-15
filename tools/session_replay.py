"""CLI tool: replay a synthetic session fixture into Kafka for dev/test purposes.

Usage:
    python tools/session_replay.py --fixture data/synthetic/session_001.json
    python tools/session_replay.py --fixture data/synthetic/session_002.json --delay-ms 50
    python tools/session_replay.py --fixture data/synthetic/session_001.json --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from services.telemetry.models import TelemetryEvent
from services.telemetry.producer import TelemetryProducer


def _load_fixture(fixture_path: Path) -> tuple[str, list[dict]]:
    """Load a synthetic session fixture. Returns (session_id, events)."""
    data = json.loads(fixture_path.read_text())
    return data["session_id"], data["events"]


async def replay(
    fixture_path: Path,
    bootstrap_servers: str,
    delay_ms: int,
    dry_run: bool,
) -> None:
    session_id, events = _load_fixture(fixture_path)

    print(f"Session  : {session_id}")
    print(f"Fixture  : {fixture_path}")
    print(f"Events   : {len(events)}")
    print(f"Servers  : {bootstrap_servers}")
    print(f"Delay    : {delay_ms} ms between events")
    print(f"Mode     : {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 60)

    if dry_run:
        for i, evt in enumerate(events, 1):
            print(f"  [{i:02d}/{len(events)}] {evt['event_type']:<25} event_id={evt['event_id']}")
        print("\nDry run complete — no events produced.")
        return

    producer = TelemetryProducer(bootstrap_servers=bootstrap_servers)
    produced = 0
    failed = 0

    for i, raw_event in enumerate(events, 1):
        try:
            event = TelemetryEvent.model_validate(raw_event)
            await producer.emit(event)
            print(f"  [{i:02d}/{len(events)}] {event.event_type:<25} ✓")
            produced += 1
        except Exception as exc:
            print(f"  [{i:02d}/{len(events)}] {raw_event.get('event_type', '?'):<25} ✗ {exc}")
            failed += 1

        if delay_ms > 0 and i < len(events):
            await asyncio.sleep(delay_ms / 1000)

    # Wait for all in-flight deliveries
    t0 = time.monotonic()
    producer.flush(timeout=15.0)
    flush_ms = int((time.monotonic() - t0) * 1000)

    print("-" * 60)
    print(f"Produced : {produced}/{len(events)} events")
    if failed:
        print(f"Failed   : {failed} events")
    print(f"Flush    : {flush_ms} ms")
    producer.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a synthetic session fixture into Kafka.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        required=True,
        help="Path to a session fixture JSON file (e.g. data/synthetic/session_001.json)",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:29092",
        help="Kafka bootstrap servers. Use localhost:29092 when running outside Docker.",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=100,
        help="Milliseconds to wait between producing each event (simulates real pacing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List events that would be produced without actually connecting to Kafka.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if not args.fixture.exists():
        raise SystemExit(f"Fixture not found: {args.fixture}")
    asyncio.run(
        replay(
            fixture_path=args.fixture,
            bootstrap_servers=args.bootstrap_servers,
            delay_ms=args.delay_ms,
            dry_run=args.dry_run,
        )
    )
