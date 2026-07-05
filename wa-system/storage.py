from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


def database_path() -> Path:
    path = Path(os.getenv("WA_DB_PATH", "data/wa-system.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                direction TEXT NOT NULL CHECK(direction IN ('incoming', 'outgoing')),
                phone TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                event_timestamp INTEGER,
                error TEXT,
                raw_json TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_phone_time
                ON messages(phone, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_status
                ON messages(status, updated_at DESC);
            """
        )


def message_exists(message_id: str) -> bool:
    with connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM messages WHERE message_id = ? LIMIT 1",
            (message_id,),
        ).fetchone()
    return row is not None


def save_message(
    *,
    message_id: str,
    direction: str,
    phone: str,
    body: str,
    status: str,
    event_timestamp: int | None = None,
    error: str | None = None,
    raw: dict[str, Any] | None = None,
) -> None:
    now = int(time.time())
    raw_json = json.dumps(raw, ensure_ascii=False, separators=(",", ":")) if raw else None
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO messages (
                message_id, direction, phone, body, status,
                event_timestamp, error, raw_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                status = excluded.status,
                event_timestamp = COALESCE(excluded.event_timestamp, messages.event_timestamp),
                error = excluded.error,
                raw_json = COALESCE(excluded.raw_json, messages.raw_json),
                updated_at = excluded.updated_at
            """,
            (
                message_id,
                direction,
                phone,
                body,
                status,
                event_timestamp,
                error,
                raw_json,
                now,
                now,
            ),
        )


def list_messages(limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 500))
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT message_id, direction, phone, body, status,
                   event_timestamp, error, created_at, updated_at
            FROM messages
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def status_summary() -> dict[str, int]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS total FROM messages GROUP BY status"
        ).fetchall()
    return {str(row["status"]): int(row["total"]) for row in rows}
