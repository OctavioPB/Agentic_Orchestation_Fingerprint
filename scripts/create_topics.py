"""Create all orchid Kafka topics. Idempotent — safe to run multiple times."""
from __future__ import annotations

import argparse
import sys

from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.error import KafkaException

from services.telemetry.topics import ALL_ORCHID_TOPICS

_NUM_PARTITIONS = 3
_REPLICATION_FACTOR = 1


def create_topics(bootstrap_servers: str, dry_run: bool = False) -> int:
    """Create all orchid topics. Returns the number of topics actually created."""
    client = AdminClient({"bootstrap.servers": bootstrap_servers})

    new_topics = [
        NewTopic(
            topic,
            num_partitions=_NUM_PARTITIONS,
            replication_factor=_REPLICATION_FACTOR,
        )
        for topic in ALL_ORCHID_TOPICS
    ]

    if dry_run:
        print(f"[dry-run] Would create {len(new_topics)} topics:")
        for t in new_topics:
            print(f"  {t.topic}")
        return 0

    futures = client.create_topics(new_topics)
    created = 0
    for topic, future in futures.items():
        try:
            future.result()
            print(f"  created : {topic}")
            created += 1
        except KafkaException as exc:
            already = "already exists" in str(exc).lower() or exc.args[0].code() == 36
            if already:  # TOPIC_ALREADY_EXISTS (code 36)
                print(f"  exists  : {topic}")
            else:
                print(f"  ERROR   : {topic} — {exc}", file=sys.stderr)
                raise

    print(f"\n{created}/{len(new_topics)} topics created.")
    return created


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create all orchid Kafka topics.")
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:29092",
        help="Kafka bootstrap servers (default: localhost:29092)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without actually creating",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    print(f"Connecting to Kafka at {args.bootstrap_servers} ...")
    create_topics(args.bootstrap_servers, dry_run=args.dry_run)
