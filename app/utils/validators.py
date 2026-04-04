"""Валидация пользовательских сообщений и мягкая классификация темы."""

from __future__ import annotations

import re
from enum import Enum
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

_TOPIC_PRIORITY: Final[tuple[QuestionTopic, ...]] = (
    "love",
    "career",
    "money",
    "decision",
    "self",
    "general",
)

# Сообщение из одних знаков препинания / пробелов (короткое «…», «?!» и т.п.)
_PUNCT_OR_SPACE_ONLY: Final[re.Pattern[str]] = re.compile(r"^[\s.,!?;…\-–—:]+$")

# Односложные реплики без содержательного запроса (не путать с «что дальше», «итог», «по работе»).
_TRIVIAL_TOKENS: Final[frozenset[str]] = frozenset({
    ".", "..", "...", "?", "!", "??", "?!", "!?", "…", "-", "—",
    "ок", "окей", "оки", "ага", "угу", "uu", "uuu",
    "ну", "да", "нет", "мм", "хм", "хмм",
    "ещё", "еще", "ладно", "хорошо", "понятно", "ясно",
    "ok", "okay", "yes", "no", "yep", "nope",
    "спс", "thx", "thanks",
})


class UserMessageContext(str, Enum):
    """Где используется сообщение — влияет на мягкие ответы при слабом вводе."""

    PRIMARY_FIRST_QUESTION = "primary_first_question"
    FOLLOWUP_DISCUSSION = "followup_discussion"
    FREE_TOPIC_LAUNCH = "free_topic_launch"
    FREE_STEP_QUESTION = "free_step_question"
    FREE_DISCUSSION = "free_discussion"


def is_trivial_filler(text: str) -> bool:
    """
    Очень короткие или пустые по смыслу реплики («ну», «ага», «...»), без запроса к раскладу.
    Пустую строку не считает filler — её обрабатывает validate_user_message.
    """

    t = text.strip()
    if not t:
        return False
    if len(t) <= 48 and _PUNCT_OR_SPACE_ONLY.fullmatch(t):
        return True
    core = t.strip(" \t").strip(".!?…").strip()
    if not core:
        return True  # только знаки препинания
    low = core.lower()
    if low in _TRIVIAL_TOKENS:
        return True
    return False


def _pick_variant(key: str, pool: tuple[str, ...]) -> str:
    if not pool:
        return ""
    i = sum(ord(c) for c in key) % len(pool)
    return pool[i]


# Подсказки после мягкого уточнения (контекст «карты уже есть / сессия идёт»).
_HINT_CLASSIC = (
    "\n\nВы можете уточнить текущий расклад текстом или выбрать 1 / 3 / 5 карт "
    "для следующего шага — кнопки под сообщением."
)
_HINT_FREE = (
    "\n\nМожно написать уточнение текстом или выбрать 1 / 3 / 5 карт для следующего шага."
)
_HINT_FREE_TOPIC = (
    "\n\nЕсли хотите начать свободный расклад, опишите тему одной фразой или вернитесь в меню."
)

_CLARIFY_WITH_CARDS: Final[tuple[str, ...]] = (
    "Могу уточнить этот расклад. Что именно вам сейчас важно понять: чувства, развитие ситуации, итог или совет?",
    "Я могу продолжить толкование этого расклада. Уточните, пожалуйста, что именно вас интересует.",
    "Если хотите, могу посмотреть этот же расклад с акцентом на чувства, действия человека, "
    "развитие ситуации или практический совет — напишите, что ближе.",
)

_CLARIFY_FREE_TOPIC: Final[tuple[str, ...]] = (
    "Я могу вести свободную сессию по одной теме. Напишите, что вы хотите рассмотреть "
    "(например отношения, работу, выбор) — одной-двумя фразами.",
    "Чтобы начать, опишите тему контекста: что вас сейчас больше всего волнует или что хотите "
    "исследовать в картах.",
    "Могу помочь с толкованием в свободной форме. Выберите расклад кнопками ниже или напишите тему "
    "чуть конкретнее.",
)

_CLARIFY_NO_ACTIVE: Final[tuple[str, ...]] = (
    "Я могу помочь с толкованием расклада. Выберите расклад кнопками ниже или напишите, какая тема "
    "вас интересует.",
    "Если хотите начать, выберите 1 / 3 / 5 карт или напишите вопрос в свободной форме.",
)


def _too_long_message() -> str:
    return (
        "Сообщение получилось очень длинным — сократите, пожалуйста, "
        f"до {CONFIG.question_max_len} символов."
    )


def _empty_or_weak_message(ctx: UserMessageContext) -> str:
    """Мягкий ответ при пустом вводе или «пустой» реплике (без фразы «слишком короткий»)."""

    if ctx == UserMessageContext.FREE_TOPIC_LAUNCH:
        base = _pick_variant("__empty__", _CLARIFY_FREE_TOPIC)
        return base + _HINT_FREE_TOPIC

    if ctx in (
        UserMessageContext.PRIMARY_FIRST_QUESTION,
        UserMessageContext.FOLLOWUP_DISCUSSION,
    ):
        base = _pick_variant("__empty__", _CLARIFY_WITH_CARDS)
        return base + _HINT_CLASSIC

    if ctx in (UserMessageContext.FREE_STEP_QUESTION, UserMessageContext.FREE_DISCUSSION):
        base = _pick_variant("__empty__", _CLARIFY_WITH_CARDS)
        return base + _HINT_FREE

    base = _pick_variant("__empty__", _CLARIFY_NO_ACTIVE)
    return base


def validate_user_message(
    text: str,
    *,
    context: UserMessageContext,
) -> tuple[bool, str | None]:
    """
    Мягкая проверка: без минимальной длины по символам.
    Возвращает (успех, None) или (False, текст подсказки — не «ошибка валидации»).
    """

    t = text.strip()
    if not t:
        return False, _empty_or_weak_message(context)

    if len(t) > CONFIG.question_max_len:
        return False, _too_long_message()

    if is_trivial_filler(t):
        return False, _empty_or_weak_message(context)

    return True, None


def validate_question_length(text: str) -> tuple[bool, str | None]:
    """Совместимость: то же, что первый вопрос к раскладу после вытягивания карт."""

    return validate_user_message(text, context=UserMessageContext.PRIMARY_FIRST_QUESTION)


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
