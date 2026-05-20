"""Creates dirty_warehouse.db with intentional data quality violations for the assessment."""
import os
import sqlite3

DB_PATH = "dirty_warehouse.db"


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            email       TEXT,          -- Violation: should be NOT NULL per data contract
            signup_date TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id    INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(customer_id),
            amount      REAL NOT NULL,
            status      TEXT NOT NULL
        );

        -- Violation: no PRIMARY KEY constraint → allows duplicate event_id values
        CREATE TABLE IF NOT EXISTS raw_events (
            event_id   TEXT,
            source     TEXT NOT NULL,
            payload    TEXT,
            created_at TEXT NOT NULL
        );

        -- Violation: inconsistent column naming (snake_case mixed with PascalCase)
        CREATE TABLE IF NOT EXISTS products (
            product_id  INTEGER PRIMARY KEY,
            ProductName TEXT NOT NULL,
            unit_Price  REAL
        );
    """)


def seed_dirty_data(conn: sqlite3.Connection) -> None:
    # Violation 1: NULL stored in NOT NULL column (email)
    conn.execute("INSERT INTO customers VALUES (1, 'alice@example.com', '2024-01-15')")
    conn.execute("INSERT INTO customers VALUES (2, NULL, '2024-02-20')")
    conn.execute("INSERT INTO customers VALUES (3, 'charlie@example.com', '2024-03-10')")

    # Violation 2: FK violation — customer_id 999 does not exist in customers
    conn.execute("INSERT INTO orders VALUES (101, 1,   250.00,            'completed')")
    conn.execute("INSERT INTO orders VALUES (102, 999, 75.50,             'pending')")
    conn.execute("INSERT INTO orders VALUES (103, 2,   120.00,            'completed')")

    # Violation 3: Wrong data type stored in REAL column (string where numeric expected)
    conn.execute("INSERT INTO orders VALUES (104, 3, 'REFUND_PENDING', 'refunded')")

    # Violations 4, 5, 6: FK null — orders with no customer association
    conn.execute("INSERT INTO orders VALUES (105, NULL, 45.00,  'pending')")
    conn.execute("INSERT INTO orders VALUES (106, NULL, 89.99,  'completed')")
    conn.execute("INSERT INTO orders VALUES (107, NULL, 210.50, 'pending')")

    # Violation 7: Duplicate event_id in raw_events (no PK to prevent this)
    payload = '{"event_type": "PROMPT_SENT", "session_id": "sess_abc"}'
    conn.execute(
        "INSERT INTO raw_events VALUES (?, ?, ?, ?)",
        ("evt_001", "kafka_consumer", payload, "2024-04-01T10:00:00Z"),
    )
    conn.execute(
        "INSERT INTO raw_events VALUES (?, ?, ?, ?)",
        ("evt_001", "kafka_consumer_retry", payload, "2024-04-01T10:00:01Z"),
    )

    # Violation 8: Malformed JSON in payload column
    conn.execute(
        "INSERT INTO raw_events VALUES"
        " ('evt_002', 'kafka_consumer', '{broken json: missing quotes}', '2024-04-01T10:01:00Z')"
    )

    conn.execute("INSERT INTO products VALUES (1, 'Widget Alpha', 9.99)")
    conn.execute("INSERT INTO products VALUES (2, 'Widget Beta',  14.99)")


def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    create_schema(conn)
    seed_dirty_data(conn)
    conn.commit()
    conn.close()
    print(f"Created {DB_PATH} with 8 intentional data quality violations.")


if __name__ == "__main__":
    main()
