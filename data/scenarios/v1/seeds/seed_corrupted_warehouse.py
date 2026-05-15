"""Reference seed script for Scenario v1: The Corrupted Warehouse.

Creates dirty_warehouse.db with all 8 intentional data quality violations.
This script is the canonical definition — the sandbox version at
services/sandbox/workspace/seed_db.py mirrors it exactly.

Run from the scenario seeds directory:
    python3 seed_corrupted_warehouse.py [path/to/dirty_warehouse.db]
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dirty_warehouse.db")

# ---------------------------------------------------------------------------
# Violation catalogue (8 total)
# ---------------------------------------------------------------------------
# Table: customers
#   V1 — customers.email is NOT NULL in the schema but NULL is stored (row 2).
#         The missing constraint (no CHECK, no trigger) silently allows it.
#
# Table: orders
#   V2 — orders.customer_id = 999 references a customer that does not exist.
#         FK enforcement is OFF, so SQLite accepts the orphaned row.
#   V3 — orders.amount = 'REFUND_PENDING' (TEXT stored in a REAL column).
#         SQLite's dynamic typing permits this; numeric operations will fail.
#   V4 — orders.customer_id = NULL (row 105) — order has no customer.
#   V5 — orders.customer_id = NULL (row 106) — order has no customer.
#   V6 — orders.customer_id = NULL (row 107) — order has no customer.
#
# Table: raw_events
#   V7 — raw_events.event_id has no PRIMARY KEY constraint, so duplicate IDs
#         are silently stored (evt_001 appears twice).
#   V8 — raw_events.payload contains malformed JSON that cannot be deserialized.
# ---------------------------------------------------------------------------


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            email       TEXT NOT NULL,
            signup_date TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id    INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(customer_id),
            amount      REAL NOT NULL,
            status      TEXT NOT NULL
        );

        -- V7: no PRIMARY KEY → duplicate event_id values are permitted
        CREATE TABLE IF NOT EXISTS raw_events (
            event_id   TEXT,
            source     TEXT NOT NULL,
            payload    TEXT,
            created_at TEXT NOT NULL
        );

        -- Bonus defect (not counted as a numbered violation): inconsistent
        -- column naming — PascalCase mixed with snake_case in the same table.
        CREATE TABLE IF NOT EXISTS products (
            product_id  INTEGER PRIMARY KEY,
            ProductName TEXT NOT NULL,
            unit_Price  REAL
        );
    """)


def seed_dirty_data(conn: sqlite3.Connection) -> None:
    # V1: NULL in NOT NULL column
    conn.execute("INSERT INTO customers VALUES (1, 'alice@example.com', '2024-01-15')")
    conn.execute("INSERT INTO customers VALUES (2, NULL, '2024-02-20')")
    conn.execute("INSERT INTO customers VALUES (3, 'charlie@example.com', '2024-03-10')")

    # V2: FK referential integrity — customer 999 does not exist
    conn.execute("INSERT INTO orders VALUES (101, 1,   250.00,            'completed')")
    conn.execute("INSERT INTO orders VALUES (102, 999, 75.50,             'pending')")
    conn.execute("INSERT INTO orders VALUES (103, 2,   120.00,            'completed')")

    # V3: Wrong data type (TEXT in REAL column)
    conn.execute("INSERT INTO orders VALUES (104, 3, 'REFUND_PENDING', 'refunded')")

    # V4, V5, V6: FK null — orders with no customer association
    conn.execute("INSERT INTO orders VALUES (105, NULL, 45.00,  'pending')")
    conn.execute("INSERT INTO orders VALUES (106, NULL, 89.99,  'completed')")
    conn.execute("INSERT INTO orders VALUES (107, NULL, 210.50, 'pending')")

    # V7: Duplicate event_id (no PK to prevent this)
    payload = '{"event_type": "PROMPT_SENT", "session_id": "sess_abc"}'
    conn.execute(
        "INSERT INTO raw_events VALUES (?, ?, ?, ?)",
        ("evt_001", "kafka_consumer", payload, "2024-04-01T10:00:00Z"),
    )
    conn.execute(
        "INSERT INTO raw_events VALUES (?, ?, ?, ?)",
        ("evt_001", "kafka_consumer_retry", payload, "2024-04-01T10:00:01Z"),
    )

    # V8: Malformed JSON payload
    conn.execute(
        "INSERT INTO raw_events VALUES"
        " ('evt_002', 'kafka_consumer', '{broken json: missing quotes}', '2024-04-01T10:01:00Z')"
    )

    conn.execute("INSERT INTO products VALUES (1, 'Widget Alpha', 9.99)")
    conn.execute("INSERT INTO products VALUES (2, 'Widget Beta',  14.99)")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    create_schema(conn)
    seed_dirty_data(conn)
    conn.commit()
    conn.close()
    print(f"Created {DB_PATH} with 8 intentional data quality violations.")


if __name__ == "__main__":
    main()
