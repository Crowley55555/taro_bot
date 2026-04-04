"""Тесты нормализации и валидации ответа модели."""

from __future__ import annotations

import pytest

from app.utils.llm_response import is_valid_model_text, normalize_model_text


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, ""),
        ("", ""),
        ("  \n\t  ", ""),
        ("  hello  ", "hello"),
        ("None", ""),
        ("none", ""),
        ("NONE", ""),
        (123, "123"),
    ],
)
def test_normalize_model_text(raw: object, expected: str) -> None:
    assert normalize_model_text(raw) == expected


@pytest.mark.parametrize(
    "s,ok",
    [
        ("", False),
        ("   ", False),
        ("x", True),
        (" ответ ", True),
    ],
)
def test_is_valid_model_text(s: str, ok: bool) -> None:
    assert is_valid_model_text(s) is ok
