"""Автосохранение раскладов в SQLite и восстановление из раздела «История»."""

from __future__ import annotations

import json
from typing import Any

from app.services import session_service as ss
from app.services.storage_service import StorageService
from app.states import (
    KEY_CURRENT_CARDS,
    KEY_CURRENT_MESSAGES_HISTORY,
    KEY_CURRENT_REASONING_DETAILS,
    KEY_CURRENT_SPREAD_DESCRIPTION,
    KEY_CURRENT_SPREAD_KEY,
    KEY_CURRENT_SPREAD_TITLE,
    KEY_DISCUSSION_HISTORY,
    KEY_FOLLOWUP_COUNT,
    KEY_FREE_CURRENT_CARDS,
    KEY_FREE_CURRENT_SPREAD_SIZE,
    KEY_FREE_PENDING_STEP_SIZE,
    KEY_FREE_DISCUSSION_HISTORY,
    KEY_FREE_FSM,
    KEY_FREE_SESSION_ACTIVE,
    KEY_FREE_SESSION_HISTORY,
    KEY_FREE_SESSION_TOPIC,
    KEY_FREE_SESSION_TURN_COUNT,
    KEY_FREE_SLIDING_MEMORY,
    KEY_LAST_INTERPRETATION,
    KEY_LAST_QUESTION,
    KEY_MODEL,
    KEY_PERSIST_CLASSIC_ID,
    KEY_PERSIST_FREE_ID,
    KEY_PROVIDER,
    KEY_READING_MODE,
    KEY_READING_STYLE,
    KEY_SESSION_MODE,
    KEY_SPREAD_ANCHOR_INTERPRETATION,
    KEY_SPREAD_CATEGORY,
    KEY_STATE,
    SESSION_MODE_CLASSIC,
    SESSION_MODE_FREE,
    STATE_FOLLOWUP_MODE,
    STATE_FREE_SESSION_CHOOSE,
    STATE_FREE_SESSION_LAUNCH,
    STATE_WAITING_QUESTION,
)
from app.utils.llm_response import is_valid_model_text, normalize_model_text


def _label_classic(title: str, question: str, max_len: int = 72) -> str:
    t = (title or "Расклад").strip()
    q = (question or "").strip().replace("\n", " ")
    if q:
        combined = f"{t} — {q}"
    else:
        combined = t
    if len(combined) <= max_len:
        return combined
    return combined[: max_len - 1] + "…"


def _label_free(topic: str, max_len: int = 72) -> str:
    s = (topic or "Свободный расклад").strip().replace("\n", " ")
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def save_classic_snapshot(
    storage: StorageService,
    user_data: dict[str, Any],
    *,
    user_id: int,
    username: str | None,
) -> None:
    cards = user_data.get(KEY_CURRENT_CARDS)
    if not isinstance(cards, list) or not cards:
        return
    interp = normalize_model_text(user_data.get(KEY_LAST_INTERPRETATION))
    if not is_valid_model_text(interp):
        return

    disc = ss.get_discussion_history(user_data)
    fu = ss.get_message_history(user_data)
    anchor = normalize_model_text(user_data.get(KEY_SPREAD_ANCHOR_INTERPRETATION)) or interp

    label = _label_classic(
        str(user_data.get(KEY_CURRENT_SPREAD_TITLE) or ""),
        str(user_data.get(KEY_LAST_QUESTION) or ""),
    )

    rid = user_data.get(KEY_PERSIST_CLASSIC_ID)
    record_id = int(rid) if rid is not None else None

    st = str(user_data.get(KEY_STATE) or STATE_FOLLOWUP_MODE)
    if st not in (STATE_FOLLOWUP_MODE, STATE_WAITING_QUESTION):
        st = STATE_FOLLOWUP_MODE

    new_id = storage.upsert_classic_reading(
        user_id=user_id,
        username=username,
        record_id=record_id,
        display_label=label,
        spread_key=str(user_data.get(KEY_CURRENT_SPREAD_KEY) or ""),
        spread_title=str(user_data.get(KEY_CURRENT_SPREAD_TITLE) or ""),
        spread_description=str(user_data.get(KEY_CURRENT_SPREAD_DESCRIPTION) or ""),
        cards=cards,
        user_question=str(user_data.get(KEY_LAST_QUESTION) or ""),
        last_interpretation=interp,
        anchor_interpretation=anchor,
        discussion_history=disc,
        followup_messages=fu,
        followup_count=int(user_data.get(KEY_FOLLOWUP_COUNT) or 0),
        provider=str(user_data.get(KEY_PROVIDER) or ""),
        model=str(user_data.get(KEY_MODEL) or ""),
        reading_mode=str(user_data.get(KEY_READING_MODE) or "medium"),
        reading_style=str(user_data.get(KEY_READING_STYLE) or "soft"),
        reasoning_details=user_data.get(KEY_CURRENT_REASONING_DETAILS),
        client_state=st,
    )
    user_data[KEY_PERSIST_CLASSIC_ID] = new_id


def _free_state_to_json(user_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "topic": str(user_data.get(KEY_FREE_SESSION_TOPIC) or ""),
        "turn_count": int(user_data.get(KEY_FREE_SESSION_TURN_COUNT) or 0),
        "history": user_data.get(KEY_FREE_SESSION_HISTORY) or [],
        "free_current_cards": user_data.get(KEY_FREE_CURRENT_CARDS),
        "free_current_spread_size": user_data.get(KEY_FREE_CURRENT_SPREAD_SIZE),
        "free_pending_step_size": user_data.get(KEY_FREE_PENDING_STEP_SIZE),
        "free_discussion_history": user_data.get(KEY_FREE_DISCUSSION_HISTORY) or [],
        "free_sliding_memory": user_data.get(KEY_FREE_SLIDING_MEMORY) or [],
        "free_fsm": user_data.get(KEY_FREE_FSM),
        "state": str(user_data.get(KEY_STATE) or STATE_FREE_SESSION_CHOOSE),
        "provider": str(user_data.get(KEY_PROVIDER) or ""),
        "model": str(user_data.get(KEY_MODEL) or ""),
        "reading_mode": str(user_data.get(KEY_READING_MODE) or "medium"),
        "reading_style": str(user_data.get(KEY_READING_STYLE) or "soft"),
    }


def register_free_session_row(
    storage: StorageService,
    user_data: dict[str, Any],
    *,
    user_id: int,
    username: str | None,
    topic: str,
) -> None:
    """После start_free_session: создаёт строку persisted_free и задаёт KEY_PERSIST_FREE_ID."""

    blob = _free_state_to_json(user_data)
    label = _label_free(topic)
    new_id = storage.insert_free_session(
        user_id=user_id,
        username=username,
        topic=topic.strip(),
        display_label=label,
        session_json=blob,
    )
    user_data[KEY_PERSIST_FREE_ID] = new_id


def persist_free_if_active(
    storage: StorageService,
    user_data: dict[str, Any],
    *,
    user_id: int,
    username: str | None,
) -> None:
    """Сохранить свободную сессию перед go_idle / сменой экрана (пока state ещё не idle)."""

    if user_data.get(KEY_FREE_SESSION_ACTIVE) and user_data.get(KEY_PERSIST_FREE_ID):
        save_free_snapshot(storage, user_data, user_id=user_id, username=username)


def save_free_snapshot(
    storage: StorageService,
    user_data: dict[str, Any],
    *,
    user_id: int,
    username: str | None,
) -> None:
    if not user_data.get(KEY_FREE_SESSION_ACTIVE):
        return
    rid = user_data.get(KEY_PERSIST_FREE_ID)
    if rid is None:
        return
    topic = str(user_data.get(KEY_FREE_SESSION_TOPIC) or "")
    label = _label_free(topic)
    blob = _free_state_to_json(user_data)
    storage.update_free_session(
        record_id=int(rid),
        user_id=user_id,
        username=username,
        topic=topic,
        display_label=label,
        session_json=blob,
    )


def restore_classic_from_persisted(user_data: dict[str, Any], row: dict[str, Any]) -> None:
    ss.clear_free_session(user_data)
    user_data[KEY_PERSIST_CLASSIC_ID] = int(row["id"])
    user_data[KEY_CURRENT_SPREAD_KEY] = str(row["spread_key"])
    user_data[KEY_CURRENT_SPREAD_TITLE] = str(row["spread_title"])
    user_data[KEY_CURRENT_SPREAD_DESCRIPTION] = str(row["spread_description"] or "")
    user_data[KEY_CURRENT_CARDS] = json.loads(row["cards_json"])
    user_data[KEY_LAST_QUESTION] = str(row["user_question"])
    user_data[KEY_LAST_INTERPRETATION] = str(row["last_interpretation"])
    user_data[KEY_SPREAD_ANCHOR_INTERPRETATION] = str(row["anchor_interpretation"])
    user_data[KEY_DISCUSSION_HISTORY] = json.loads(row["discussion_history_json"] or "[]")
    user_data[KEY_CURRENT_MESSAGES_HISTORY] = json.loads(row["followup_messages_json"] or "[]")
    user_data[KEY_FOLLOWUP_COUNT] = int(row["followup_count"] or 0)
    user_data[KEY_PROVIDER] = str(row["provider"])
    user_data[KEY_MODEL] = str(row["model"])
    user_data[KEY_READING_MODE] = str(row["reading_mode"])
    user_data[KEY_READING_STYLE] = str(row["reading_style"])
    rd = row.get("reasoning_details")
    if rd:
        try:
            user_data[KEY_CURRENT_REASONING_DETAILS] = (
                json.loads(rd) if isinstance(rd, str) else rd
            )
        except json.JSONDecodeError:
            user_data[KEY_CURRENT_REASONING_DETAILS] = None
    else:
        user_data.pop(KEY_CURRENT_REASONING_DETAILS, None)
    user_data.pop(KEY_SPREAD_CATEGORY, None)
    user_data[KEY_SESSION_MODE] = SESSION_MODE_CLASSIC
    st = str(row.get("client_state") or STATE_FOLLOWUP_MODE)
    if st == "classic_mini_waiting_question":
        st = STATE_WAITING_QUESTION
    if st not in (STATE_FOLLOWUP_MODE, STATE_WAITING_QUESTION):
        st = STATE_FOLLOWUP_MODE
    user_data[KEY_STATE] = st


def restore_free_from_persisted_row(
    user_data: dict[str, Any],
    row: dict[str, Any],
) -> None:
    ss.reset_current_reading(user_data)
    ss.clear_free_session(user_data)

    blob = json.loads(row["session_json"])
    user_data[KEY_PERSIST_FREE_ID] = int(row["id"])
    user_data[KEY_SESSION_MODE] = SESSION_MODE_FREE
    user_data[KEY_FREE_SESSION_ACTIVE] = True
    user_data[KEY_FREE_SESSION_TOPIC] = str(blob.get("topic") or row.get("topic") or "")
    user_data[KEY_FREE_SESSION_TURN_COUNT] = int(blob.get("turn_count") or 0)
    user_data[KEY_FREE_SESSION_HISTORY] = blob.get("history") or []
    user_data[KEY_FREE_CURRENT_CARDS] = blob.get("free_current_cards")
    user_data[KEY_FREE_CURRENT_SPREAD_SIZE] = blob.get("free_current_spread_size")
    pss = blob.get("free_pending_step_size")
    if pss is not None:
        user_data[KEY_FREE_PENDING_STEP_SIZE] = pss
    else:
        user_data.pop(KEY_FREE_PENDING_STEP_SIZE, None)
    user_data[KEY_FREE_DISCUSSION_HISTORY] = blob.get("free_discussion_history") or []
    user_data[KEY_FREE_SLIDING_MEMORY] = blob.get("free_sliding_memory") or []
    fsm = blob.get("free_fsm")
    if fsm is not None:
        user_data[KEY_FREE_FSM] = fsm
    else:
        user_data.pop(KEY_FREE_FSM, None)

    st = str(blob.get("state") or STATE_FREE_SESSION_CHOOSE)
    if st == STATE_FREE_SESSION_LAUNCH:
        st = STATE_FREE_SESSION_CHOOSE
    user_data[KEY_STATE] = st

    user_data[KEY_PROVIDER] = str(blob.get("provider") or user_data.get(KEY_PROVIDER) or "")
    user_data[KEY_MODEL] = str(blob.get("model") or user_data.get(KEY_MODEL) or "")
    user_data[KEY_READING_MODE] = str(blob.get("reading_mode") or "medium")
    user_data[KEY_READING_STYLE] = str(blob.get("reading_style") or "soft")


def migrate_legacy_reading_to_persisted(
    storage: StorageService,
    legacy: dict[str, Any],
    *,
    user_id: int,
    username: str | None,
) -> int:
    """Переносит запись из readings в persisted_classic и удаляет legacy."""

    cards = json.loads(str(legacy["cards_json"]))
    reason_raw = legacy.get("reasoning_details")
    reason: Any | None
    if reason_raw:
        try:
            reason = json.loads(reason_raw) if isinstance(reason_raw, str) else reason_raw
        except json.JSONDecodeError:
            reason = None
    else:
        reason = None

    label = _label_classic(str(legacy["spread_title"]), str(legacy["user_question"]))
    new_id = storage.upsert_classic_reading(
        user_id=user_id,
        username=username,
        record_id=None,
        display_label=label,
        spread_key=str(legacy["spread_key"]),
        spread_title=str(legacy["spread_title"]),
        spread_description="",
        cards=cards,
        user_question=str(legacy["user_question"]),
        last_interpretation=str(legacy["interpretation"]),
        anchor_interpretation=str(legacy["interpretation"]),
        discussion_history=[],
        followup_messages=[],
        followup_count=0,
        provider=str(legacy["provider"]),
        model=str(legacy["model"]),
        reading_mode=str(legacy["reading_mode"]),
        reading_style=str(legacy["reading_style"]),
        reasoning_details=reason,
        client_state=STATE_FOLLOWUP_MODE,
    )
    storage.delete_legacy_reading(int(legacy["id"]), user_id)
    return new_id
