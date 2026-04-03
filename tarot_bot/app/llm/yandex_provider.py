"""Провайдер YandexGPT через OpenAI-совместимый клиент."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import CONFIG
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import ConfigurationError, ProviderRequestError
from app.models.entities import LLMCompletionResult

_log = logging.getLogger(__name__)


class YandexGPTProvider(BaseLLMProvider):
    """Yandex Cloud Foundation Models (OpenAI-compatible)."""

    name = "yandex"

    def __init__(
        self,
        *,
        api_key: str,
        catalog_id: str,
        base_url: str,
        model: str,
    ) -> None:
        if not api_key or not catalog_id:
            raise ConfigurationError("Yandex: задайте YANDEX_API_KEY и YANDEX_CATALOG_ID")
        self._catalog_id = catalog_id
        full_model = model.strip()
        if not full_model.startswith("gpt://"):
            full_model = f"gpt://{catalog_id}/{full_model.lstrip('/')}"
        self._model = full_model
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=CONFIG.http_timeout_seconds,
            default_headers={"x-folder-id": catalog_id},
        )

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
            raise ProviderRequestError(f"YandexGPT: {exc}") from exc

        choice = resp.choices[0].message
        content = choice.content or ""
        raw = resp.model_dump() if hasattr(resp, "model_dump") else {}
        return LLMCompletionResult(content=str(content), raw_response=raw, reasoning_details=None)