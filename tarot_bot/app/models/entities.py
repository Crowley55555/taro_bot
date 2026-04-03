"""Сущности данных: расклад, карта, запись истории."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass(slots=True)
class DrawnCard:
    """Одна позиция расклада с картой и ориентацией."""

    position_name: str
    card: str
    orientation: Literal["Прямое", "Перевёрнутое"]


ReadingMode = Literal["short", "medium", "deep"]
ReadingStyle = Literal["soft", "psychological", "practical"]
QuestionTopic = Literal["love", "career", "money", "decision", "self", "general"]


@dataclass(slots=True)
class ReadingRecord:
    """Запись сохранённого расклада в SQLite."""

    id: int | None
    user_id: int
    username: str | None
    created_at: datetime
    spread_key: str
    spread_title: str
    cards_json: str
    user_question: str
    interpretation: str
    provider: str
    model: str
    reading_mode: str
    reading_style: str
    reasoning_details: str | None = None


@dataclass(slots=True)
class LLMCompletionResult:
    """Результат вызова LLM."""

    content: str
    raw_response: dict[str, Any] | None = None
    reasoning_details: Any | None = None


@dataclass(slots=True)
class ChatMessage:
    """Сообщение для LLM API."""

    role: Literal["system", "user", "assistant"]
    content: str


MessageHistory = list[dict[str, str]]


def cards_to_payload(cards: list[DrawnCard]) -> list[dict[str, str]]:
    return [
        {"position_name": c.position_name, "card": c.card, "orientation": c.orientation}
        for c in cards
    ]


@dataclass
class SpreadDefinition:
    """Описание расклада из каталога."""

    key: str
    title: str
    category: str
    short_description: str
    cards_count: int
    positions: list[str]
    suggested_questions: list[str]
    is_deep: bool
    allow_followup: bool = True