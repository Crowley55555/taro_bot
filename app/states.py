"""Состояния FSM (хранятся в context.user_data["state"])."""

from __future__ import annotations

from typing import Final, Literal

UserState = Literal[
    "idle",
    "choosing_category",
    "choosing_spread",
    "waiting_question",
    "followup_mode",
    "choosing_provider",
    "choosing_model",
    "changing_settings",
    "free_session_launch",
    "free_session_choose",
    "free_session_waiting_question",
]

STATE_IDLE: Final[UserState] = "idle"
STATE_CHOOSING_CATEGORY: Final[UserState] = "choosing_category"
STATE_CHOOSING_SPREAD: Final[UserState] = "choosing_spread"
STATE_WAITING_QUESTION: Final[UserState] = "waiting_question"
STATE_FOLLOWUP_MODE: Final[UserState] = "followup_mode"
STATE_CHOOSING_PROVIDER: Final[UserState] = "choosing_provider"
STATE_CHOOSING_MODEL: Final[UserState] = "choosing_model"
STATE_CHANGING_SETTINGS: Final[UserState] = "changing_settings"
STATE_FREE_SESSION_LAUNCH: Final[UserState] = "free_session_launch"
STATE_FREE_SESSION_CHOOSE: Final[UserState] = "free_session_choose"
STATE_FREE_SESSION_WAITING_QUESTION: Final[UserState] = "free_session_waiting_question"

KEY_STATE: Final = "state"
KEY_PROVIDER: Final = "provider"
KEY_MODEL: Final = "model"
KEY_READING_MODE: Final = "reading_mode"
KEY_READING_STYLE: Final = "reading_style"
KEY_CURRENT_SPREAD_KEY: Final = "current_spread_key"
KEY_CURRENT_SPREAD_TITLE: Final = "current_spread_title"
KEY_CURRENT_SPREAD_DESCRIPTION: Final = "current_spread_description"
KEY_CURRENT_CARDS: Final = "current_cards"
KEY_LAST_QUESTION: Final = "last_question"
KEY_LAST_INTERPRETATION: Final = "last_interpretation"
KEY_SPREAD_ANCHOR_INTERPRETATION: Final = "spread_anchor_interpretation"
KEY_CURRENT_MESSAGES_HISTORY: Final = "current_messages_history"
KEY_CURRENT_REASONING_DETAILS: Final = "current_reasoning_details"
KEY_FOLLOWUP_COUNT: Final = "followup_count"
KEY_DISCUSSION_HISTORY: Final = "discussion_history"
KEY_FREE_DISCUSSION_HISTORY: Final = "free_discussion_history"
KEY_PENDING_REINTERPRET: Final = "pending_reinterpret"
KEY_SPREAD_CATEGORY: Final = "spread_category"

KEY_SESSION_MODE: Final = "session_mode"
KEY_FREE_SESSION_ACTIVE: Final = "free_session_active"
KEY_FREE_SESSION_TOPIC: Final = "free_session_topic"
KEY_FREE_SESSION_TURN_COUNT: Final = "free_session_turn_count"
KEY_FREE_SESSION_HISTORY: Final = "free_session_history"
KEY_FREE_CURRENT_SPREAD_SIZE: Final = "free_current_spread_size"
KEY_FREE_CURRENT_CARDS: Final = "free_current_cards"
KEY_FREE_CURRENT_QUESTION: Final = "free_current_question"
KEY_FREE_FSM: Final = "free_fsm"
KEY_FREE_SLIDING_MEMORY: Final = "free_sliding_memory"
KEY_PERSIST_CLASSIC_ID: Final = "persist_classic_id"
KEY_PERSIST_FREE_ID: Final = "persist_free_id"

# Вопрос к раскладу до вытягивания карт (каталог, mini pr:* , free fr:*)
KEY_PENDING_CARDS_BEFORE_DRAW: Final = "pending_cards_before_draw"
KEY_PENDING_MINI_SPREAD_SIZE: Final = "pending_mini_spread_size"
KEY_FREE_PENDING_STEP_SIZE: Final = "free_pending_step_size"

SESSION_MODE_CLASSIC: Final = "classic"
SESSION_MODE_FREE: Final = "free"
