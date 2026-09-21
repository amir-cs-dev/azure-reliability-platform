import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
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
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    delivered_at TEXT,
                    UNIQUE(incident_id, event),
                    FOREIGN KEY(incident_id)
                        REFERENCES incidents(id)
                )
            """)

            conn.execute("""
                INSERT OR IGNORE INTO monitor_state
                (id, consecutive_failures, incident_open)
                VALUES (1, 0, 0)
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            with conn:
                yield conn
        finally:
            conn.close()

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
        Atomically update monitoring state, incident history,
        and the notification queue.
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
                state,
                result,
                threshold,
            )

            timestamp = result["timestamp"]

            # Open a new incident and queue its notification.
            if event == "INCIDENT_OPENED":
                cursor = conn.execute("""
                    INSERT INTO incidents (opened_at)
                    VALUES (?)
                """, (timestamp,))

                incident_id = cursor.lastrowid

                payload = {
                    "event": "INCIDENT_OPENED",
                    "incident_id": incident_id,
                    "timestamp": timestamp,
                    "message": "Application health check failed",
                }

                conn.execute("""
                    INSERT INTO notifications
                    (incident_id, event, payload)
                    VALUES (?, ?, ?)
                """, (
                    incident_id,
                    event,
                    json.dumps(payload),
                ))

            # Recover the existing incident and queue recovery.
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

                recovered = datetime.fromisoformat(
                    timestamp
                )

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

                payload = {
                    "event": "RECOVERED",
                    "incident_id": incident["id"],
                    "timestamp": timestamp,
                    "duration_seconds": duration,
                    "message": "Application health restored",
                }

                conn.execute("""
                    INSERT INTO notifications
                    (incident_id, event, payload)
                    VALUES (?, ?, ?)
                """, (
                    incident["id"],
                    event,
                    json.dumps(payload),
                ))

            # Persist state within the same transaction.
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

    def pending_notifications(self):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT id, incident_id, event, payload,
                       status, attempts, last_error,
                       delivered_at
                FROM notifications
                WHERE status = 'pending'
                ORDER BY id
            """).fetchall()

        return [dict(row) for row in rows]

    def mark_delivered(self, notification_id):
        timestamp = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:
            cursor = conn.execute("""
                UPDATE notifications
                SET status = 'delivered',
                    delivered_at = ?,
                    last_error = NULL,
                    attempts = attempts + 1
                WHERE id = ?
                  AND status = 'pending'
            """, (
                timestamp,
                notification_id,
            ))

            return cursor.rowcount == 1

    def mark_failed(self, notification_id, error):
        with self.connect() as conn:
            cursor = conn.execute("""
                UPDATE notifications
                SET attempts = attempts + 1,
                    last_error = ?
                WHERE id = ?
                  AND status = 'pending'
            """, (
                str(error)[:500],
                notification_id,
            ))

            return cursor.rowcount == 1