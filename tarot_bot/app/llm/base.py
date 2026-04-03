"""Базовый интерфейс провайдера LLM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from app.models.entities import LLMCompletionResult


class BaseLLMProvider(ABC):
    """Абстрактный провайдер чат-модели."""

    name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMCompletionResult:
        """Выполняет запрос к модели и возвращает текст ответа."""