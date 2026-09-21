import sqlite3
from datetime import datetime
from pathlib import Path

from monitor.state import evaluate


class IncidentStore:
    def __init__(self, db_path="data/incidents.sqlite3"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitor_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    incident_open INTEGER NOT NULL DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opened_at TEXT NOT NULL,
                    recovered_at TEXT,
                    duration_seconds REAL
                )
            """)

            conn.execute("""
                INSERT OR IGNORE INTO monitor_state
                (id, consecutive_failures, incident_open)
                VALUES (1, 0, 0)
            """)

    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def load_state(self):
        with self.connect() as conn:
            row = conn.execute("""
                SELECT consecutive_failures, incident_open
                FROM monitor_state
                WHERE id = 1
            """).fetchone()

        return {
            "consecutive_failures": row["consecutive_failures"],
            "incident_open": bool(row["incident_open"]),
        }

    def record(self, result, threshold=2):
        """
        Atomically update monitoring state and incident history.
        """
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT consecutive_failures, incident_open
                FROM monitor_state
                WHERE id = 1
            """).fetchone()

            state = {
                "consecutive_failures": row["consecutive_failures"],
                "incident_open": bool(row["incident_open"]),
            }

            new_state, event = evaluate(
                state, result, threshold
            )

            timestamp = result["timestamp"]

            if event == "INCIDENT_OPENED":
                conn.execute("""
                    INSERT INTO incidents (opened_at)
                    VALUES (?)
                """, (timestamp,))

            elif event == "RECOVERED":
                incident = conn.execute("""
                    SELECT id, opened_at
                    FROM incidents
                    WHERE recovered_at IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                """).fetchone()

                if incident is None:
                    raise RuntimeError(
                        "Recovery detected without an open incident"
                    )

                opened = datetime.fromisoformat(
                    incident["opened_at"]
                )
                recovered = datetime.fromisoformat(timestamp)

                duration = max(
                    0.0,
                    round(
                        (recovered - opened).total_seconds(),
                        3,
                    ),
                )

                conn.execute("""
                    UPDATE incidents
                    SET recovered_at = ?,
                        duration_seconds = ?
                    WHERE id = ?
                """, (
                    timestamp,
                    duration,
                    incident["id"],
                ))

            conn.execute("""
                UPDATE monitor_state
                SET consecutive_failures = ?,
                    incident_open = ?
                WHERE id = 1
            """, (
                new_state["consecutive_failures"],
                int(new_state["incident_open"]),
            ))

        return new_state, event

    def list_incidents(self):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT id, opened_at, recovered_at,
                       duration_seconds
                FROM incidents
                ORDER BY id
            """).fetchall()

        return [dict(row) for row in rows]