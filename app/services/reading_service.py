"""Оркестрация вызовов LLM для расклада."""

from __future__ import annotations

import logging

from app.llm.exceptions import ConfigurationError, ProviderRequestError
from app.llm.factory import get_provider
from app.llm.retry import run_with_retry
from app.models.entities import DrawnCard, LLMCompletionResult, ReadingMode, ReadingStyle
from app.services.prompt_builder import (
    build_followup_messages,
    build_free_discussion_messages,
    build_free_session_messages,
    build_primary_reading_messages,
    build_reading_discussion_messages,
)
from app.utils.timing import log_duration
from app.utils.validators import detect_question_topic, sanitize_user_input_for_prompt

_log = logging.getLogger(__name__)


def _max_tokens_for_mode(mode: ReadingMode) -> int:
    if mode == "short":
        return 1200
    if mode == "deep":
        return 6000
    return 3500


async def run_primary_reading(
    *,
    provider_name: str,
    model_name: str | None,
    spread_title: str,
    spread_description: str,
    cards: list[DrawnCard],
    user_question: str,
    reading_mode: ReadingMode,
    reading_style: ReadingStyle,
) -> LLMCompletionResult:
    """Первичная интерпретация расклада."""

    q = sanitize_user_input_for_prompt(user_question)
    topic = detect_question_topic(q)
    messages = build_primary_reading_messages(
        spread_title=spread_title,
        spread_description=spread_description,
        cards=cards,
        user_question=q,
        topic=topic,
        reading_mode=reading_mode,
        reading_style=reading_style,
    )
    prov = get_provider(provider_name, model_name)

    async def _op() -> LLMCompletionResult:
        with log_duration(f"LLM primary {provider_name}", _log):
            return await prov.complete(
                messages,
                temperature=0.7,
                max_tokens=_max_tokens_for_mode(reading_mode),
            )

    try:
        return await run_with_retry(_op, name="primary")
    except ConfigurationError:
        raise
    except Exception as exc:
        _log.exception("Ошибка первичной интерпретации")
        raise ProviderRequestError("Не удалось получить ответ модели. Попробуйте позже.") from exc


async def run_followup_reading(
    *,
    provider_name: str,
    model_name: str | None,
    spread_title: str,
    spread_description: str,
    cards: list[DrawnCard],
    prior_messages: list[dict[str, str]],
    followup_question: str,
    reading_mode: ReadingMode,
    reading_style: ReadingStyle,
) -> LLMCompletionResult:
    """Уточнение по тому же раскладу."""

    q = sanitize_user_input_for_prompt(followup_question)
    topic = detect_question_topic(q)
    messages = build_followup_messages(
        spread_title=spread_title,
        spread_description=spread_description,
        cards=cards,
        prior_messages=prior_messages,
        followup_question=q,
        topic=topic,
        reading_mode=reading_mode,
        reading_style=reading_style,
    )
    prov = get_provider(provider_name, model_name)

    async def _op() -> LLMCompletionResult:
        with log_duration(f"LLM followup {provider_name}", _log):
            return await prov.complete(
                messages,
                temperature=0.65,
                max_tokens=_max_tokens_for_mode(reading_mode),
            )

    try:
        return await run_with_retry(_op, name="followup")
    except ConfigurationError:
        raise
    except Exception as exc:
        _log.exception("Ошибка уточнения")
        raise ProviderRequestError("Не удалось получить ответ модели. Попробуйте позже.") from exc


async def run_reading_discussion_reading(
    *,
    provider_name: str,
    model_name: str | None,
    spread_title: str,
    spread_description: str,
    cards: list[DrawnCard],
    original_question: str,
    last_interpretation: str,
    discussion_history: list[dict[str, str]],
    new_message: str,
    reading_mode: ReadingMode,
    reading_style: ReadingStyle,
) -> LLMCompletionResult:
    """Обсуждение текущего расклада без новых карт."""

    q = sanitize_user_input_for_prompt(new_message)
    topic = detect_question_topic(q)
    messages = build_reading_discussion_messages(
        spread_title=spread_title,
        spread_description=spread_description,
        cards=cards,
        original_question=sanitize_user_input_for_prompt(original_question),
        last_interpretation=sanitize_user_input_for_prompt(last_interpretation),
        discussion_history=discussion_history,
        new_message=q,
        topic=topic,
        reading_mode=reading_mode,
        reading_style=reading_style,
    )
    prov = get_provider(provider_name, model_name)

    async def _op() -> LLMCompletionResult:
        with log_duration(f"LLM discussion {provider_name}", _log):
            return await prov.complete(
                messages,
                temperature=0.65,
                max_tokens=_max_tokens_for_mode(reading_mode),
            )

    try:
        return await run_with_retry(_op, name="discussion")
    except ConfigurationError:
        raise
    except Exception as exc:
        _log.exception("Ошибка обсуждения расклада")
        raise ProviderRequestError("Не удалось получить ответ модели. Попробуйте позже.") from exc


async def run_free_discussion_reading(
    *,
    provider_name: str,
    model_name: str | None,
    session_topic: str,
    session_history: list[dict],
    current_cards: list[DrawnCard],
    last_step_interpretation: str,
    last_step_question: str,
    sliding_memory: list[dict[str, str]],
    new_message: str,
    reading_mode: ReadingMode,
    reading_style: ReadingStyle,
) -> LLMCompletionResult:
    """Обсуждение текущего шага свободной сессии без новых карт."""

    q = sanitize_user_input_for_prompt(new_message)
    topic = detect_question_topic(q)
    messages = build_free_discussion_messages(
        session_topic=sanitize_user_input_for_prompt(session_topic),
        session_history=session_history,
        sliding_memory=sliding_memory,
        current_cards=current_cards,
        last_step_interpretation=sanitize_user_input_for_prompt(last_step_interpretation),
        last_step_question=sanitize_user_input_for_prompt(last_step_question),
        new_message=q,
        topic=topic,
        reading_mode=reading_mode,
        reading_style=reading_style,
    )
    prov = get_provider(provider_name, model_name)

    async def _op() -> LLMCompletionResult:
        with log_duration(f"LLM free_discussion {provider_name}", _log):
            return await prov.complete(
                messages,
                temperature=0.65,
                max_tokens=_max_tokens_for_mode(reading_mode),
            )

    try:
        return await run_with_retry(_op, name="free_discussion")
    except ConfigurationError:
        raise
    except Exception as exc:
        _log.exception("Ошибка обсуждения в свободной сессии")
        raise ProviderRequestError("Не удалось получить ответ модели. Попробуйте позже.") from exc


async def run_free_session_reading(
    *,
    provider_name: str,
    model_name: str | None,
    session_topic: str,
    history: list[dict],
    sliding_memory: list[dict[str, str]],
    current_cards: list[DrawnCard],
    current_question: str,
    reading_mode: ReadingMode,
    reading_style: ReadingStyle,
) -> LLMCompletionResult:
    """Интерпретация шага свободной сессии."""

    q = sanitize_user_input_for_prompt(current_question)
    topic = detect_question_topic(q)
    messages = build_free_session_messages(
        session_topic=sanitize_user_input_for_prompt(session_topic),
        history=history,
        sliding_memory=sliding_memory,
        current_cards=current_cards,
        current_question=q,
        topic=topic,
        reading_mode=reading_mode,
        reading_style=reading_style,
    )
    prov = get_provider(provider_name, model_name)

    async def _op() -> LLMCompletionResult:
        with log_duration(f"LLM free_session {provider_name}", _log):
            return await prov.complete(
                messages,
                temperature=0.7,
                max_tokens=_max_tokens_for_mode(reading_mode),
            )

    try:
        return await run_with_retry(_op, name="free_session")
    except ConfigurationError:
        raise
    except Exception as exc:
        _log.exception("Ошибка свободной сессии")
        raise ProviderRequestError("Не удалось получить ответ модели. Попробуйте позже.") from exc