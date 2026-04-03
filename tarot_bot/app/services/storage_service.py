"""Хранение раскладов в SQLite."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import CONFIG
from app.models.entities import ReadingRecord


@dataclass(slots=True)
class StorageStats:
    """Статистика по сохранённым раскладам."""

    total_readings: int
    unique_users: int


def _configure_sqlite_connection(conn: sqlite3.Connection) -> None:
    """WAL и busy_timeout для устойчивости при последовательных записях."""

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")


class StorageService:
    """Сервис доступа к SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or CONFIG.sqlite_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._path,
            timeout=CONFIG.sqlite_connect_timeout_seconds,
        )
        _configure_sqlite_connection(conn)
        return conn

    def init_db(self) -> None:
        """Создаёт таблицу readings, если её ещё нет."""

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS free_session_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    created_at TEXT NOT NULL,
                    session_type TEXT NOT NULL,
                    session_topic TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    spread_size INTEGER NOT NULL,
                    cards_json TEXT NOT NULL,
                    question TEXT NOT NULL,
                    interpretation TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    reading_mode TEXT NOT NULL,
                    reading_style TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    created_at TEXT NOT NULL,
                    spread_key TEXT NOT NULL,
                    spread_title TEXT NOT NULL,
                    cards_json TEXT NOT NULL,
                    user_question TEXT NOT NULL,
                    interpretation TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    reading_mode TEXT NOT NULL,
                    reading_style TEXT NOT NULL,
                    reasoning_details TEXT
                )
                """
            )
            conn.commit()

    def save_free_session_step(
        self,
        *,
        user_id: int,
        username: str | None,
        session_topic: str,
        turn_number: int,
        spread_size: int,
        cards: list[dict[str, Any]],
        question: str,
        interpretation: str,
        provider: str,
        model: str,
        reading_mode: str,
        reading_style: str,
        session_type: str = "free_reading",
    ) -> int:
        """Сохраняет один шаг свободной сессии."""

        created = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cards_json = json.dumps(cards, ensure_ascii=False)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO free_session_steps (
                    user_id, username, created_at, session_type, session_topic,
                    turn_number, spread_size, cards_json, question, interpretation,
                    provider, model, reading_mode, reading_style
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    created,
                    session_type,
                    session_topic,
                    turn_number,
                    spread_size,
                    cards_json,
                    question,
                    interpretation,
                    provider,
                    model,
                    reading_mode,
                    reading_style,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def save_reading(
        self,
        *,
        user_id: int,
        username: str | None,
        spread_key: str,
        spread_title: str,
        cards: list[dict[str, Any]],
        user_question: str,
        interpretation: str,
        provider: str,
        model: str,
        reading_mode: str,
        reading_style: str,
        reasoning_details: Any | None = None,
    ) -> int:
        """Сохраняет расклад и возвращает id записи."""

        created = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cards_json = json.dumps(cards, ensure_ascii=False)
        reasoning_json: str | None
        if reasoning_details is None:
            reasoning_json = None
        else:
            reasoning_json = json.dumps(reasoning_details, ensure_ascii=False)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO readings (
                    user_id, username, created_at, spread_key, spread_title,
                    cards_json, user_question, interpretation, provider, model,
                    reading_mode, reading_style, reasoning_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    created,
                    spread_key,
                    spread_title,
                    cards_json,
                    user_question,
                    interpretation,
                    provider,
                    model,
                    reading_mode,
                    reading_style,
                    reasoning_json,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_user_readings(self, user_id: int, limit: int = 10) -> list[ReadingRecord]:
        """Последние расклады пользователя."""

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, user_id, username, created_at, spread_key, spread_title,
                       cards_json, user_question, interpretation, provider, model,
                       reading_mode, reading_style, reasoning_details
                FROM readings
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        out: list[ReadingRecord] = []
        for r in rows:
            out.append(
                ReadingRecord(
                    id=int(r["id"]),
                    user_id=int(r["user_id"]),
                    username=r["username"],
                    created_at=datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00")),
                    spread_key=str(r["spread_key"]),
                    spread_title=str(r["spread_title"]),
                    cards_json=str(r["cards_json"]),
                    user_question=str(r["user_question"]),
                    interpretation=str(r["interpretation"]),
                    provider=str(r["provider"]),
                    model=str(r["model"]),
                    reading_mode=str(r["reading_mode"]),
                    reading_style=str(r["reading_style"]),
                    reasoning_details=r["reasoning_details"],
                )
            )
        return out

    def count_stats(self) -> StorageStats:
        """Общее число записей и уникальных пользователей."""

        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
            uniq = conn.execute("SELECT COUNT(DISTINCT user_id) FROM readings").fetchone()[0]
        return StorageStats(total_readings=int(total), unique_users=int(uniq))
