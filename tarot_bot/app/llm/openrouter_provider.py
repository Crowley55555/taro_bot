"""Провайдер OpenRouter через requests (синхронный вызов в thread)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests

from app.config import CONFIG
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import ProviderRequestError
from app.models.entities import LLMCompletionResult

_log = logging.getLogger(__name__)

_ERR_SNIP_LEN = 200


def _safe_response_snippet(text: str, max_len: int = _ERR_SNIP_LEN) -> str:
    if not text:
        return ""
    one_line = text.replace("\r", " ").replace("\n", " ")
    if len(one_line) <= max_len:
        return one_line
    return one_line[:max_len] + "…"


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter: chat completions."""

    name = "openrouter"

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._url = "https://openrouter.ai/api/v1/chat/completions"

    def _post_sync(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        include_reasoning: bool,
    ) -> requests.Response:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if include_reasoning:
            body["reasoning"] = {"enabled": True}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        return requests.post(
            self._url,
            json=body,
            headers=headers,
            timeout=CONFIG.http_timeout_seconds,
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMCompletionResult:
        want_reasoning = CONFIG.openrouter_enable_reasoning

        def do_request(include_reasoning: bool) -> dict[str, Any]:
            resp = self._post_sync(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                include_reasoning=include_reasoning,
            )
            if resp.status_code >= 400:
                snip = _safe_response_snippet(resp.text)
                _log.warning(
                    "OpenRouter HTTP %s (reasoning=%s): %s",
                    resp.status_code,
                    include_reasoning,
                    snip,
                )
                raise ProviderRequestError(
                    f"OpenRouter временно недоступен (код {resp.status_code}).",
                    status_code=resp.status_code,
                )
            return resp.json()

        async def call(include_r: bool) -> dict[str, Any]:
            return await asyncio.to_thread(do_request, include_r)

        if want_reasoning:
            try:
                data = await call(True)
            except ProviderRequestError as exc:
                if exc.status_code in (400, 422):
                    _log.info("OpenRouter: повтор без reasoning после HTTP %s", exc.status_code)
                    data = await call(False)
                else:
                    raise
        else:
            data = await call(False)

        try:
            msg = data["choices"][0]["message"]
            raw_content = msg.get("content")
        except (KeyError, IndexError, TypeError) as exc:
            _log.warning("OpenRouter: неожиданная структура ответа")
            raise ProviderRequestError("Неожиданный ответ OpenRouter.") from exc

        if raw_content is None:
            return LLMCompletionResult(content="", raw_response=data, reasoning_details=None)

        if not isinstance(raw_content, str):
            raw_content = str(raw_content)

        reasoning = None
        if isinstance(msg, dict):
            reasoning = msg.get("reasoning_details") or msg.get("reasoning")

        return LLMCompletionResult(
            content=raw_content,
            raw_response=data,
            reasoning_details=reasoning,
        )
