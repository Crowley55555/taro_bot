"""Нормализация и валидация текста ответа LLM перед обновлением сессии."""

from __future__ import annotations


def normalize_model_text(raw: object) -> str:
    """Приводит ответ модели к строке, strip; литералы none/None — пустая строка."""

    if raw is None:
        return ""
    if isinstance(raw, str):
        s = raw.strip()
    else:
        s = str(raw).strip()
    if s.lower() == "none":
        return ""
    return s


def is_valid_model_text(s: str) -> bool:
    """True, если ответ можно считать содержательным для пользователя и истории."""

    return bool(s and s.strip())
