"""Тесты хелперов сессии (без Telegram)."""

from __future__ import annotations

from app.config import CONFIG

from app.services import session_service as ss
from app.states import (
    KEY_CURRENT_CARDS,
    KEY_FREE_SLIDING_MEMORY,
    KEY_PENDING_CARDS_BEFORE_DRAW,
    KEY_PENDING_MINI_SPREAD_SIZE,
    KEY_LAST_INTERPRETATION,
    KEY_LAST_QUESTION,
    KEY_MODEL,
    KEY_PENDING_REINTERPRET,
    KEY_PROVIDER,
    KEY_READING_MODE,
    KEY_READING_STYLE,
    KEY_STATE,
    STATE_FOLLOWUP_MODE,
    STATE_IDLE,
)


def test_clear_pending_reinterpret() -> None:
    ud: dict = {KEY_PENDING_REINTERPRET: True}
    ss.clear_pending_reinterpret(ud)
    assert KEY_PENDING_REINTERPRET not in ud


def test_reset_current_reading_preserves_provider_settings() -> None:
    ud: dict = {
        KEY_PROVIDER: "openai",
        KEY_MODEL: "gpt-4o-mini",
        KEY_READING_MODE: "deep",
        KEY_READING_STYLE: "practical",
        KEY_CURRENT_CARDS: [{"a": 1}],
        KEY_LAST_QUESTION: "q",
        KEY_LAST_INTERPRETATION: "interp",
        KEY_PENDING_REINTERPRET: True,
        KEY_PENDING_CARDS_BEFORE_DRAW: True,
        KEY_PENDING_MINI_SPREAD_SIZE: 3,
    }
    ss.reset_current_reading(ud)
    assert ud[KEY_PROVIDER] == "openai"
    assert ud[KEY_MODEL] == "gpt-4o-mini"
    assert ud[KEY_READING_MODE] == "deep"
    assert ud[KEY_READING_STYLE] == "practical"
    assert KEY_CURRENT_CARDS not in ud
    assert KEY_LAST_QUESTION not in ud
    assert KEY_PENDING_CARDS_BEFORE_DRAW not in ud
    assert KEY_PENDING_MINI_SPREAD_SIZE not in ud


def test_go_idle_clears_reading_and_pending() -> None:
    ud: dict = {
        KEY_STATE: STATE_FOLLOWUP_MODE,
        KEY_PENDING_REINTERPRET: True,
        KEY_CURRENT_CARDS: [],
        KEY_LAST_QUESTION: "x",
    }
    ss.go_idle(ud)
    assert ud[KEY_STATE] == STATE_IDLE
    assert KEY_PENDING_REINTERPRET not in ud
    assert KEY_LAST_QUESTION not in ud


def test_restore_after_failed_reinterpret_with_valid_prev() -> None:
    ud: dict = {
        KEY_STATE: STATE_IDLE,
        KEY_LAST_INTERPRETATION: "Старая валидная интерпретация",
        KEY_CURRENT_CARDS: [{"position_name": "p", "card": "Шут", "orientation": "Прямое"}],
    }
    ss.restore_after_failed_reinterpret(ud)
    assert ud[KEY_STATE] == STATE_FOLLOWUP_MODE
    assert ud[KEY_LAST_INTERPRETATION] == "Старая валидная интерпретация"


def test_append_free_sliding_pair_trims_to_limit() -> None:
    lim = max(2, CONFIG.free_session_memory_limit)
    ud: dict = {KEY_FREE_SLIDING_MEMORY: []}
    for i in range(lim + 4):
        ss.append_free_sliding_pair(ud, f"u{i}", f"a{i}")
    mem = ud[KEY_FREE_SLIDING_MEMORY]
    assert len(mem) == lim
    assert "u0" not in str(mem)
    assert f"u{lim + 3}" in mem[-2]["content"]


def test_restore_after_failed_reinterpret_without_valid_prev() -> None:
    ud: dict = {
        KEY_STATE: STATE_IDLE,
        KEY_LAST_INTERPRETATION: "",
        KEY_CURRENT_CARDS: [{"position_name": "p", "card": "Шут", "orientation": "Прямое"}],
    }
    ss.restore_after_failed_reinterpret(ud)
    assert ud[KEY_STATE] == STATE_IDLE
    assert KEY_CURRENT_CARDS not in ud
