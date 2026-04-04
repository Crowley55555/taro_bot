"""Тесты таблиц истории (без Telegram)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.services.storage_service import StorageService


def _tmp_db() -> Path:
    fd, raw = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Path(raw)


def test_persisted_classic_upsert_and_list() -> None:
    path = _tmp_db()
    try:
        s = StorageService(path)
        s.init_db()
        uid = 42
        i1 = s.upsert_classic_reading(
            user_id=uid,
            username="u",
            record_id=None,
            display_label="Test label",
            spread_key="k",
            spread_title="Title",
            spread_description="desc",
            cards=[{"position_name": "1", "card": "Fool", "orientation": "Upright"}],
            user_question="q?",
            last_interpretation="interp",
            anchor_interpretation="interp",
            discussion_history=[],
            followup_messages=[{"role": "user", "content": "q"}],
            followup_count=0,
            provider="openrouter",
            model="m",
            reading_mode="medium",
            reading_style="soft",
            reasoning_details=None,
            client_state="followup_mode",
        )
        assert i1 > 0
        i2 = s.upsert_classic_reading(
            user_id=uid,
            username="u",
            record_id=i1,
            display_label="Test label",
            spread_key="k",
            spread_title="Title",
            spread_description="desc",
            cards=[{"position_name": "1", "card": "Fool", "orientation": "Upright"}],
            user_question="q?",
            last_interpretation="interp2",
            anchor_interpretation="interp2",
            discussion_history=[{"role": "user", "content": "x"}],
            followup_messages=[],
            followup_count=1,
            provider="openrouter",
            model="m",
            reading_mode="medium",
            reading_style="soft",
            reasoning_details=None,
            client_state="followup_mode",
        )
        assert i2 == i1
        rows = s.list_user_history_merged(uid, limit=10, offset=0)
        assert len(rows) == 1
        assert rows[0].kind == "classic"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_free_insert_update() -> None:
    path = _tmp_db()
    try:
        s = StorageService(path)
        s.init_db()
        uid = 7
        jid = s.insert_free_session(
            user_id=uid,
            username=None,
            topic="Topic",
            display_label="Topic",
            session_json={"v": 1, "topic": "Topic", "state": "free_session_choose"},
        )
        ok = s.update_free_session(
            record_id=jid,
            user_id=uid,
            username=None,
            topic="Topic",
            display_label="Topic updated",
            session_json={"v": 1, "topic": "Topic", "state": "free_session_waiting_question"},
        )
        assert ok
        row = s.get_free_persisted(jid, uid)
        assert row is not None
        assert "updated" in row["display_label"]
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
