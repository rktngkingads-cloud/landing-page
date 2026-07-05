from __future__ import annotations

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


def init_contact_store() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                phone TEXT PRIMARY KEY,
                opted_in INTEGER NOT NULL DEFAULT 0,
                consent_source TEXT,
                consent_note TEXT,
                consent_at INTEGER,
                opted_out_at INTEGER,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reply_counters (
                phone TEXT NOT NULL,
                day_key TEXT NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(phone, day_key)
            );
            """
        )


def set_opt_in(
    phone: str,
    *,
    source: str,
    note: str = "",
    consent_at: int | None = None,
) -> None:
    now = int(time.time())
    consent_time = consent_at or now
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO contacts (
                phone, opted_in, consent_source, consent_note,
                consent_at, opted_out_at, created_at, updated_at
            ) VALUES (?, 1, ?, ?, ?, NULL, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                opted_in = 1,
                consent_source = excluded.consent_source,
                consent_note = excluded.consent_note,
                consent_at = excluded.consent_at,
                opted_out_at = NULL,
                updated_at = excluded.updated_at
            """,
            (phone, source, note, consent_time, now, now),
        )


def set_opt_out(phone: str) -> None:
    now = int(time.time())
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO contacts (
                phone, opted_in, opted_out_at, created_at, updated_at
            ) VALUES (?, 0, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                opted_in = 0,
                opted_out_at = excluded.opted_out_at,
                updated_at = excluded.updated_at
            """,
            (phone, now, now, now),
        )


def is_opted_in(phone: str) -> bool:
    with connect() as connection:
        row = connection.execute(
            "SELECT opted_in FROM contacts WHERE phone = ?",
            (phone,),
        ).fetchone()
    return bool(row and row["opted_in"] == 1)


def get_contact(phone: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT phone, opted_in, consent_source, consent_note,
                   consent_at, opted_out_at, created_at, updated_at
            FROM contacts WHERE phone = ?
            """,
            (phone,),
        ).fetchone()
    return dict(row) if row else None


def list_contacts(limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 500))
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT phone, opted_in, consent_source, consent_note,
                   consent_at, opted_out_at, created_at, updated_at
            FROM contacts
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def replies_today(phone: str, day_key: str) -> int:
    with connect() as connection:
        row = connection.execute(
            "SELECT total FROM reply_counters WHERE phone = ? AND day_key = ?",
            (phone, day_key),
        ).fetchone()
    return int(row["total"]) if row else 0


def increment_reply_counter(phone: str, day_key: str) -> None:
    now = int(time.time())
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO reply_counters(phone, day_key, total, updated_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(phone, day_key) DO UPDATE SET
                total = reply_counters.total + 1,
                updated_at = excluded.updated_at
            """,
            (phone, day_key, now),
        )
