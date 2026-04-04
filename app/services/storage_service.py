"""Хранение раскладов в SQLite."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import CONFIG
from app.models.entities import HistoryListItem, ReadingRecord


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


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        """Создаёт таблицы, если их ещё нет."""

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS persisted_classic_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    updated_at TEXT NOT NULL,
                    display_label TEXT NOT NULL,
                    spread_key TEXT NOT NULL,
                    spread_title TEXT NOT NULL,
                    spread_description TEXT NOT NULL DEFAULT '',
                    cards_json TEXT NOT NULL,
                    user_question TEXT NOT NULL,
                    last_interpretation TEXT NOT NULL,
                    anchor_interpretation TEXT NOT NULL,
                    discussion_history_json TEXT NOT NULL,
                    followup_messages_json TEXT NOT NULL,
                    followup_count INTEGER NOT NULL DEFAULT 0,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    reading_mode TEXT NOT NULL,
                    reading_style TEXT NOT NULL,
                    reasoning_details TEXT,
                    client_state TEXT NOT NULL DEFAULT 'followup_mode'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS persisted_free_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    updated_at TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    display_label TEXT NOT NULL,
                    session_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_persist_classic_user ON persisted_classic_readings(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_persist_free_user ON persisted_free_sessions(user_id)"
            )
            self._migrate_schema(conn)
            conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Добавляет столбцы в существующие БД."""

        try:
            rows = conn.execute("PRAGMA table_info(persisted_classic_readings)").fetchall()
            names = {str(r[1]) for r in rows}
            if names and "client_state" not in names:
                conn.execute(
                    "ALTER TABLE persisted_classic_readings ADD COLUMN client_state TEXT NOT NULL DEFAULT 'followup_mode'"
                )
        except sqlite3.OperationalError:
            pass

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
        """Сохраняет один шаг свободной сессии (опциональный журнал)."""

        created = _now_iso()
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
        """Совместимость: явное сохранение в legacy-таблицу readings."""

        created = _now_iso()
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

    def upsert_classic_reading(
        self,
        *,
        user_id: int,
        username: str | None,
        record_id: int | None,
        display_label: str,
        spread_key: str,
        spread_title: str,
        spread_description: str,
        cards: list[dict[str, Any]],
        user_question: str,
        last_interpretation: str,
        anchor_interpretation: str,
        discussion_history: list[dict[str, str]],
        followup_messages: list[dict[str, str]],
        followup_count: int,
        provider: str,
        model: str,
        reading_mode: str,
        reading_style: str,
        reasoning_details: Any | None,
        client_state: str,
    ) -> int:
        """Создаёт или обновляет запись классического расклада; возвращает id."""

        ts = _now_iso()
        cards_json = json.dumps(cards, ensure_ascii=False)
        disc_json = json.dumps(discussion_history, ensure_ascii=False)
        fu_json = json.dumps(followup_messages, ensure_ascii=False)
        reason: str | None
        if reasoning_details is None:
            reason = None
        else:
            reason = json.dumps(reasoning_details, ensure_ascii=False)

        with self._connect() as conn:
            if record_id is not None:
                conn.execute(
                    """
                    UPDATE persisted_classic_readings SET
                        username = ?,
                        updated_at = ?,
                        display_label = ?,
                        spread_key = ?,
                        spread_title = ?,
                        spread_description = ?,
                        cards_json = ?,
                        user_question = ?,
                        last_interpretation = ?,
                        anchor_interpretation = ?,
                        discussion_history_json = ?,
                        followup_messages_json = ?,
                        followup_count = ?,
                        provider = ?,
                        model = ?,
                        reading_mode = ?,
                        reading_style = ?,
                        reasoning_details = ?,
                        client_state = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        username,
                        ts,
                        display_label,
                        spread_key,
                        spread_title,
                        spread_description,
                        cards_json,
                        user_question,
                        last_interpretation,
                        anchor_interpretation,
                        disc_json,
                        fu_json,
                        followup_count,
                        provider,
                        model,
                        reading_mode,
                        reading_style,
                        reason,
                        client_state,
                        record_id,
                        user_id,
                    ),
                )
                conn.commit()
                return int(record_id)

            cur = conn.execute(
                """
                INSERT INTO persisted_classic_readings (
                    user_id, username, updated_at, display_label,
                    spread_key, spread_title, spread_description,
                    cards_json, user_question, last_interpretation, anchor_interpretation,
                    discussion_history_json, followup_messages_json, followup_count,
                    provider, model, reading_mode, reading_style, reasoning_details, client_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    ts,
                    display_label,
                    spread_key,
                    spread_title,
                    spread_description,
                    cards_json,
                    user_question,
                    last_interpretation,
                    anchor_interpretation,
                    disc_json,
                    fu_json,
                    followup_count,
                    provider,
                    model,
                    reading_mode,
                    reading_style,
                    reason,
                    client_state,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_classic_persisted(self, record_id: int, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM persisted_classic_readings
                WHERE id = ? AND user_id = ?
                """,
                (record_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def delete_classic_persisted(self, record_id: int, user_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM persisted_classic_readings WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def insert_free_session(
        self,
        *,
        user_id: int,
        username: str | None,
        topic: str,
        display_label: str,
        session_json: dict[str, Any],
    ) -> int:
        ts = _now_iso()
        blob = json.dumps(session_json, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO persisted_free_sessions (
                    user_id, username, updated_at, topic, display_label, session_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, ts, topic, display_label, blob),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update_free_session(
        self,
        *,
        record_id: int,
        user_id: int,
        username: str | None,
        topic: str,
        display_label: str,
        session_json: dict[str, Any],
    ) -> bool:
        ts = _now_iso()
        blob = json.dumps(session_json, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE persisted_free_sessions SET
                    username = ?,
                    updated_at = ?,
                    topic = ?,
                    display_label = ?,
                    session_json = ?
                WHERE id = ? AND user_id = ?
                """,
                (username, ts, topic, display_label, blob, record_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_free_persisted(self, record_id: int, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM persisted_free_sessions WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def delete_free_persisted(self, record_id: int, user_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM persisted_free_sessions WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_legacy_reading(self, record_id: int, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM readings WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def delete_legacy_reading(self, record_id: int, user_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM readings WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def list_user_history_merged(
        self,
        user_id: int,
        *,
        limit: int = 12,
        offset: int = 0,
    ) -> list[HistoryListItem]:
        """Объединённый список: классика, свободные сессии, старые записи readings."""

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT 'classic' AS kind, id, display_label AS lbl, updated_at AS ts
                    FROM persisted_classic_readings WHERE user_id = ?
                    UNION ALL
                    SELECT 'free', id, display_label, updated_at
                    FROM persisted_free_sessions WHERE user_id = ?
                    UNION ALL
                    SELECT 'legacy', id,
                        spread_title || ' — ' || substr(user_question, 1, 48)
                        || CASE WHEN length(user_question) > 48 THEN '…' ELSE '' END,
                        created_at
                    FROM readings WHERE user_id = ?
                ) ORDER BY ts DESC LIMIT ? OFFSET ?
                """,
                (user_id, user_id, user_id, limit, offset),
            ).fetchall()

        out: list[HistoryListItem] = []
        for r in rows:
            ts_raw = str(r["ts"])
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now(UTC)
            out.append(
                HistoryListItem(
                    kind=r["kind"],  # type: ignore[arg-type]
                    record_id=int(r["id"]),
                    label=str(r["lbl"])[:200],
                    updated_at=dt,
                )
            )
        return out

    def count_history_rows_for_user(self, user_id: int) -> int:
        with self._connect() as conn:
            n1 = conn.execute(
                "SELECT COUNT(*) FROM persisted_classic_readings WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            n2 = conn.execute(
                "SELECT COUNT(*) FROM persisted_free_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            n3 = conn.execute(
                "SELECT COUNT(*) FROM readings WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
        return int(n1) + int(n2) + int(n3)

    def list_user_readings(self, user_id: int, limit: int = 10) -> list[ReadingRecord]:
        """Последние расклады из legacy-таблицы readings (совместимость)."""

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
        """Общее число записей во всех таблицах истории и уникальных пользователей."""

        with self._connect() as conn:
            total = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM readings)
                  + (SELECT COUNT(*) FROM persisted_classic_readings)
                  + (SELECT COUNT(*) FROM persisted_free_sessions)
                """
            ).fetchone()[0]
            uniq = conn.execute(
                """
                SELECT COUNT(DISTINCT uid) FROM (
                    SELECT user_id AS uid FROM readings
                    UNION SELECT user_id FROM persisted_classic_readings
                    UNION SELECT user_id FROM persisted_free_sessions
                )
                """
            ).fetchone()[0]
        return StorageStats(total_readings=int(total), unique_users=int(uniq))
