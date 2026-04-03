"""Сессия пользователя в context.user_data."""

from __future__ import annotations

from typing import Any

from app.config import CONFIG
from app.models.entities import DrawnCard, MessageHistory, ReadingMode, ReadingStyle
from app.utils.llm_response import is_valid_model_text, normalize_model_text
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
    KEY_FREE_DISCUSSION_HISTORY,
    KEY_FREE_CURRENT_QUESTION,
    KEY_FREE_CURRENT_SPREAD_SIZE,
    KEY_FREE_SESSION_ACTIVE,
    KEY_FREE_SESSION_HISTORY,
    KEY_FREE_SESSION_TOPIC,
    KEY_FREE_SESSION_TURN_COUNT,
    KEY_LAST_INTERPRETATION,
    KEY_SPREAD_ANCHOR_INTERPRETATION,
    KEY_LAST_QUESTION,
    KEY_MODEL,
    KEY_PENDING_REINTERPRET,
    KEY_PROVIDER,
    KEY_READING_MODE,
    KEY_READING_STYLE,
    KEY_SESSION_MODE,
    KEY_SPREAD_CATEGORY,
    KEY_STATE,
    SESSION_MODE_CLASSIC,
    SESSION_MODE_FREE,
    STATE_FOLLOWUP_MODE,
    STATE_IDLE,
)


def clear_pending_reinterpret(user_data: dict[str, Any]) -> None:
    """Сбрасывает флаг повторной интерпретации после смены ИИ."""

    user_data.pop(KEY_PENDING_REINTERPRET, None)


def reset_current_reading(user_data: dict[str, Any]) -> None:
    """Очищает активный расклад и диалог по нему; провайдер/модель/стиль/длина не трогает."""

    for k in (
        KEY_CURRENT_SPREAD_KEY,
        KEY_CURRENT_SPREAD_TITLE,
        KEY_CURRENT_SPREAD_DESCRIPTION,
        KEY_CURRENT_CARDS,
        KEY_LAST_QUESTION,
        KEY_LAST_INTERPRETATION,
        KEY_SPREAD_ANCHOR_INTERPRETATION,
        KEY_CURRENT_MESSAGES_HISTORY,
        KEY_CURRENT_REASONING_DETAILS,
        KEY_FOLLOWUP_COUNT,
        KEY_PENDING_REINTERPRET,
        KEY_SPREAD_CATEGORY,
        KEY_DISCUSSION_HISTORY,
    ):
        user_data.pop(k, None)
    user_data[KEY_FOLLOWUP_COUNT] = 0
    user_data[KEY_CURRENT_MESSAGES_HISTORY] = []


def clear_free_session(user_data: dict[str, Any]) -> None:
    """Сбрасывает режим «Свободный расклад»; настройки ИИ не трогает."""

    for k in (
        KEY_FREE_SESSION_ACTIVE,
        KEY_FREE_SESSION_TOPIC,
        KEY_FREE_SESSION_TURN_COUNT,
        KEY_FREE_SESSION_HISTORY,
        KEY_FREE_CURRENT_SPREAD_SIZE,
        KEY_FREE_CURRENT_CARDS,
        KEY_FREE_CURRENT_QUESTION,
        KEY_FREE_DISCUSSION_HISTORY,
    ):
        user_data.pop(k, None)
    user_data[KEY_SESSION_MODE] = SESSION_MODE_CLASSIC


def start_free_session(user_data: dict[str, Any], topic: str) -> None:
    """Начинает свободную сессию после ввода темы."""

    user_data[KEY_SESSION_MODE] = SESSION_MODE_FREE
    user_data[KEY_FREE_SESSION_ACTIVE] = True
    user_data[KEY_FREE_SESSION_TOPIC] = topic.strip()
    user_data[KEY_FREE_SESSION_TURN_COUNT] = 0
    user_data[KEY_FREE_SESSION_HISTORY] = []
    user_data.pop(KEY_FREE_CURRENT_SPREAD_SIZE, None)
    user_data[KEY_FREE_CURRENT_CARDS] = None
    user_data.pop(KEY_FREE_CURRENT_QUESTION, None)
    user_data[KEY_FREE_DISCUSSION_HISTORY] = []


def go_idle(user_data: dict[str, Any]) -> None:
    """Выход из сценария: idle + сброс pending reinterpret + полная очистка активного расклада."""

    user_data[KEY_STATE] = STATE_IDLE
    clear_pending_reinterpret(user_data)
    reset_current_reading(user_data)
    clear_free_session(user_data)


def restore_after_failed_reinterpret(user_data: dict[str, Any]) -> None:
    """Нормализует сессию после неудачной переинтерпретации (смена ИИ).

    Политика (вариант A): если до попытки оставалась валидная интерпретация прежнего
    расклада — возвращаем пользователя в follow-up с теми же картами и вопросом, чтобы
    не оставлять «зомби»-состояние idle + активный расклад. Иначе — go_idle: сбрасываем
    чтение, настройки провайдера/модели/режимов не трогаем.
    """

    prev = normalize_model_text(user_data.get(KEY_LAST_INTERPRETATION))
    if is_valid_model_text(prev):
        user_data[KEY_STATE] = STATE_FOLLOWUP_MODE
    else:
        go_idle(user_data)


def reset_for_new_spread(user_data: dict[str, Any]) -> None:
    """Сбрасывает поля текущего расклада и истории диалога, сохраняя настройки ИИ."""

    reset_current_reading(user_data)


def ensure_defaults(user_data: dict[str, Any]) -> None:
    """Гарантирует наличие ключей настроек и состояния."""

    user_data.setdefault(KEY_STATE, STATE_IDLE)
    user_data.setdefault(KEY_PROVIDER, CONFIG.default_llm_provider)
    user_data.setdefault(KEY_MODEL, _default_model_for(user_data.get(KEY_PROVIDER)))
    user_data.setdefault(KEY_READING_MODE, "medium")
    user_data.setdefault(KEY_READING_STYLE, "soft")
    user_data.setdefault(KEY_FOLLOWUP_COUNT, 0)
    user_data.setdefault(KEY_CURRENT_MESSAGES_HISTORY, [])
    user_data.setdefault(KEY_DISCUSSION_HISTORY, [])
    user_data.setdefault(KEY_SESSION_MODE, SESSION_MODE_CLASSIC)


def _default_model_for(provider: Any) -> str:
    p = str(provider or "").lower()
    if p == "openai":
        return CONFIG.default_openai_model
    if p == "gigachat":
        return CONFIG.default_gigachat_model
    if p == "yandex":
        return CONFIG.default_yandex_model
    return CONFIG.default_openrouter_model


def set_provider_and_model(user_data: dict[str, Any], provider: str, model: str | None) -> None:
    """Устанавливает провайдера и модель; при model=None подставляет дефолт."""

    user_data[KEY_PROVIDER] = provider
    if model:
        user_data[KEY_MODEL] = model
    else:
        user_data[KEY_MODEL] = _default_model_for(provider)


def serialize_cards(cards: list[DrawnCard]) -> list[dict[str, str]]:
    return [
        {"position_name": c.position_name, "card": c.card, "orientation": c.orientation}
        for c in cards
    ]


def deserialize_cards(raw: list[dict[str, Any]]) -> list[DrawnCard]:
    return [
        DrawnCard(
            position_name=str(x["position_name"]),
            card=str(x["card"]),
            orientation=str(x["orientation"]),  # type: ignore[arg-type]
        )
        for x in raw
    ]


def get_reading_mode(user_data: dict[str, Any]) -> ReadingMode:
    v = user_data.get(KEY_READING_MODE, "medium")
    if v in ("short", "medium", "deep"):
        return v  # type: ignore[return-value]
    return "medium"


def get_reading_style(user_data: dict[str, Any]) -> ReadingStyle:
    v = user_data.get(KEY_READING_STYLE, "soft")
    if v in ("soft", "psychological", "practical"):
        return v  # type: ignore[return-value]
    return "soft"


def get_message_history(user_data: dict[str, Any]) -> MessageHistory:
    h = user_data.get(KEY_CURRENT_MESSAGES_HISTORY)
    if isinstance(h, list):
        return h  # type: ignore[return-value]
    return []


def _trim_dialog_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Оставляет последние N сообщений; первая роль — user (не обрезаем пару посередине)."""

    max_m = max(2, CONFIG.max_dialog_messages)
    if len(messages) <= max_m:
        return messages
    trimmed = messages[-max_m:]
    while trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]
    return trimmed


def replace_message_history(user_data: dict[str, Any], messages: list[dict[str, str]]) -> None:
    """Заменяет историю диалога по текущему раскладу с усечением по лимиту."""

    user_data[KEY_CURRENT_MESSAGES_HISTORY] = _trim_dialog_messages(messages)


def get_discussion_history(user_data: dict[str, Any]) -> list[dict[str, str]]:
    h = user_data.get(KEY_DISCUSSION_HISTORY)
    if isinstance(h, list):
        return h  # type: ignore[return-value]
    return []


def append_discussion_turn(user_data: dict[str, Any], user_text: str, assistant_text: str) -> None:
    """Добавляет пару user/assistant в историю обсуждения классического расклада."""

    h = list(get_discussion_history(user_data))
    h.append({"role": "user", "content": user_text})
    h.append({"role": "assistant", "content": assistant_text})
    max_m = max(2, CONFIG.max_discussion_messages)
    if len(h) > max_m:
        h = h[-max_m:]
    user_data[KEY_DISCUSSION_HISTORY] = h


def get_free_discussion_history(user_data: dict[str, Any]) -> list[dict[str, str]]:
    h = user_data.get(KEY_FREE_DISCUSSION_HISTORY)
    if isinstance(h, list):
        return h  # type: ignore[return-value]
    return []


def append_free_discussion_turn(user_data: dict[str, Any], user_text: str, assistant_text: str) -> None:
    h = list(get_free_discussion_history(user_data))
    h.append({"role": "user", "content": user_text})
    h.append({"role": "assistant", "content": assistant_text})
    max_m = max(2, CONFIG.max_discussion_messages)
    if len(h) > max_m:
        h = h[-max_m:]
    user_data[KEY_FREE_DISCUSSION_HISTORY] = h


def append_history(user_data: dict[str, Any], role: str, content: str) -> None:
    h = get_message_history(user_data)
    h.append({"role": role, "content": content})
    user_data[KEY_CURRENT_MESSAGES_HISTORY] = _trim_dialog_messages(h)


def get_model_name(user_data: dict[str, Any]) -> str | None:
    """Возвращает имя модели или None, если нужно взять дефолт провайдера."""

    m = user_data.get(KEY_MODEL)
    if isinstance(m, str) and m.strip():
        return m.strip()
    return None


reset_user_session = reset_current_reading
