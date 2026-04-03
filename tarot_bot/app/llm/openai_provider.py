"""Провайдер OpenAI через официальный SDK (async)."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import CONFIG
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import ProviderRequestError
from app.models.entities import LLMCompletionResult

_log = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI chat completions."""

    name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, timeout=CONFIG.http_timeout_seconds)

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMCompletionResult:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise ProviderRequestError(f"OpenAI: {exc}") from exc

        choice = resp.choices[0].message
        content = choice.content or ""
        raw = resp.model_dump() if hasattr(resp, "model_dump") else {}
        return LLMCompletionResult(content=str(content), raw_response=raw, reasoning_details=None)