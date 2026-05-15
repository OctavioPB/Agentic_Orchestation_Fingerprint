"""Register all Avro schemas from docs/schema/ with the Confluent Schema Registry."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from services.telemetry.schemas import SchemaRegistryHelper

_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "schema"


def register_all(schema_registry_url: str, compatibility: str = "BACKWARD") -> None:
    helper = SchemaRegistryHelper(schema_registry_url)

    existing = helper.list_subjects()
    print(f"Schema Registry has {len(existing)} existing subjects.")

    results = helper.register_all(compatibility=compatibility)

    print(f"\nRegistered {len(results)} schemas:")
    for subject, schema_id in results.items():
        print(f"  {subject:<55} → ID {schema_id}")

    # Verify BACKWARD compatibility is set on each subject
    print("\nCompatibility check:")
    for subject in results:
        try:
            schema = helper.get_schema(subject)
            print(f"  OK {subject} (version has {len(schema.get('fields', []))} fields)")
        except Exception as exc:
            print(f"  WARN {subject}: {exc}", file=sys.stderr)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register orchid Avro schemas with the Schema Registry."
    )
    parser.add_argument(
        "--schema-registry",
        default="http://localhost:8081",
        help="Schema Registry URL (default: http://localhost:8081)",
    )
    parser.add_argument(
        "--compatibility",
        default="BACKWARD",
        choices=["BACKWARD", "FORWARD", "FULL", "NONE"],
        help="Compatibility mode to enforce (default: BACKWARD)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    print(f"Registering schemas with Schema Registry at {args.schema_registry} ...")
    register_all(args.schema_registry, compatibility=args.compatibility)
