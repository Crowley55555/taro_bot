"""Валидация вопросов и мягкая классификация темы."""

from __future__ import annotations

import re
from typing import Final

from app.config import CONFIG
from app.models.entities import QuestionTopic

_LOVE_WORDS: Final[tuple[str, ...]] = (
    "любовь", "любов", "любим", "партнёр", "партнер", "отношени", "брак", "свидани",
    "секс", "интим", "ревност", "измен", "бывш", "встреч", "чувств",
)
_CAREER_WORDS: Final[tuple[str, ...]] = (
    "работ", "карьер", "начальник", "коллег", "офис", "проект", "увольн", "резюме",
    "интервью", "должност", "професси", "стаж", "курсы",
)
_MONEY_WORDS: Final[tuple[str, ...]] = (
    "деньг", "финанс", "долг", "кредит", "зарплат", "покупка", "прибыл", "убыт",
    "инвест", "бюджет", "расход", "доход",
)
_DECISION_WORDS: Final[tuple[str, ...]] = (
    "решени", "выбор", "вариант", "оставаться", "уходить", "согласиться", "отказаться",
)
_SELF_WORDS: Final[tuple[str, ...]] = (
    "я ", "сам", "себя", "самооцен", "тревог", "страх", "границ", "здоровье",
    "психолог", "терапия", "выгоран", "смысл",
)

# При равном score выбираем тему с меньшим индексом (детерминированный tie-break).
_TOPIC_PRIORITY: Final[tuple[QuestionTopic, ...]] = (
    "love",
    "career",
    "money",
    "decision",
    "self",
    "general",
)


def validate_question_length(text: str) -> tuple[bool, str | None]:
    """Проверяет длину вопроса по настройкам CONFIG."""

    t = text.strip()
    if not t:
        return False, "Вопрос не может быть пустым."
    if len(t) < CONFIG.question_min_len:
        return False, "Вопрос слишком короткий. Расскажите чуть подробнее."
    if len(t) > CONFIG.question_max_len:
        return False, "Вопрос слишком длинный. Сократите текст."
    return True, None


def sanitize_user_input_for_prompt(text: str) -> str:
    """Очищает пользовательский ввод для подстановки в промпт."""

    t = text.strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)
    return t[: CONFIG.question_max_len]


def detect_question_topic(text: str) -> QuestionTopic:
    """Грубая эвристическая классификация темы вопроса."""

    low = text.lower()

    def score(words: tuple[str, ...]) -> int:
        return sum(1 for w in words if w in low)

    scores: dict[QuestionTopic, int] = {
        "love": score(_LOVE_WORDS),
        "career": score(_CAREER_WORDS),
        "money": score(_MONEY_WORDS),
        "decision": score(_DECISION_WORDS),
        "self": score(_SELF_WORDS),
    }

    ranked = sorted(
        _TOPIC_PRIORITY[:-1],
        key=lambda t: (-scores[t], _TOPIC_PRIORITY.index(t)),
    )
    best_topic = ranked[0]
    best_score = scores[best_topic]
    if best_score == 0:
        return "general"
    return best_topic
