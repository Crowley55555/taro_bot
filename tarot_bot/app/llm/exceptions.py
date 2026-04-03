"""Исключения слоя LLM."""

from __future__ import annotations


class LLMError(Exception):
    """Базовая ошибка LLM."""


class ConfigurationError(LLMError):
    """Отсутствуют ключи или некорректная конфигурация провайдера."""


class ProviderRequestError(LLMError):
    """Ошибка запроса к внешнему API."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code