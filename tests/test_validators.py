"""Тесты мягкой валидации сообщений."""

from __future__ import annotations

import pytest

from app.utils.validators import UserMessageContext, is_trivial_filler, validate_user_message


@pytest.mark.parametrize(
    "text",
    [
        "что дальше",
        "итог",
        "по чувствам",
        "если написать ей",
        "про работу",
        "когда",
        "стоит ли",
        "а если подождать",
        "про него",
        "я не знаю что делать",
    ],
)
def test_short_followups_not_trivial(text: str) -> None:
    assert is_trivial_filler(text) is False
    ok, err = validate_user_message(text, context=UserMessageContext.FOLLOWUP_DISCUSSION)
    assert ok is True
    assert err is None


@pytest.mark.parametrize(
    "text",
    ["ну", "ага", "...", "ок", "да", "?!", "   ...   "],
)
def test_trivial_fillers_rejected_softly(text: str) -> None:
    assert is_trivial_filler(text) is True
    ok, err = validate_user_message(text, context=UserMessageContext.FOLLOWUP_DISCUSSION)
    assert ok is False
    assert err
    assert "слишком коротк" not in (err or "").lower()
    assert "ошибка" not in (err or "").lower()


def test_empty_soft_followup() -> None:
    ok, err = validate_user_message("   ", context=UserMessageContext.FOLLOWUP_DISCUSSION)
    assert ok is False
    assert err
    assert "уточн" in err.lower() or "могу" in err.lower() or "если хотите" in err.lower()
    assert "1 / 3 / 5" in err


def test_primary_short_question_ok() -> None:
    ok, err = validate_user_message("по работе", context=UserMessageContext.PRIMARY_FIRST_QUESTION)
    assert ok is True
    assert err is None


def test_free_topic_short_ok() -> None:
    ok, err = validate_user_message("отношения", context=UserMessageContext.FREE_TOPIC_LAUNCH)
    assert ok is True
    assert err is None
