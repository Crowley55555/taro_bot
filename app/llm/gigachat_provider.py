"""Провайдер GigaChat: OAuth + REST или OpenAI-совместимый режим."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from typing import Any

import requests
from openai import AsyncOpenAI

from app.config import CONFIG
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import ConfigurationError, ProviderRequestError
from app.models.entities import LLMCompletionResult

_log = logging.getLogger(__name__)


def _safe_response_snippet(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    one_line = text.replace("\r", " ").replace("\n", " ")
    if len(one_line) <= max_len:
        return one_line
    return one_line[:max_len] + "…"


class GigaChatProvider(BaseLLMProvider):
    """GigaChat с кэшем access token в памяти."""

    name = "gigachat"

    def __init__(
        self,
        *,
        client_id: str,
        auth_key: str,
        scope: str,
        model: str,
        oauth_url: str,
        api_url: str,
        verify_ssl: bool,
        use_openai_compat: bool,
        openai_base_url: str | None,
    ) -> None:
        if not client_id or not auth_key:
            raise ConfigurationError("GigaChat: задайте GIGACHAT_CLIENT_ID и GIGACHAT_AUTH_KEY")
        self._client_id = client_id
        self._auth_key = auth_key
        self._scope = scope
        self._model = model
        self._oauth_url = oauth_url
        self._api_url = api_url
        self._verify = verify_ssl
        self._use_openai_compat = use_openai_compat
        self._openai_base_url = (openai_base_url or "").strip() or None

        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMCompletionResult:
        if self._use_openai_compat and self._openai_base_url:
            return await self._complete_openai_compat(messages, temperature, max_tokens)
        return await self._complete_rest(messages, temperature, max_tokens)

    def _ensure_token_sync(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token

        basic = base64.b64encode(f"{self._client_id}:{self._auth_key}".encode()).decode()
        headers = {
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
            "RqUID": str(uuid.uuid4()),
        }
        data = {"scope": self._scope, "grant_type": "client_credentials"}
        resp = requests.post(
            self._oauth_url,
            data=data,
            headers=headers,
            timeout=CONFIG.http_timeout_seconds,
            verify=self._verify,
        )
        if resp.status_code >= 400:
            snip = _safe_response_snippet(resp.text)
            _log.warning("GigaChat OAuth HTTP %s: %s", resp.status_code, snip)
            raise ProviderRequestError(
                f"GigaChat временно недоступен (код {resp.status_code}).",
                status_code=resp.status_code,
            )
        payload = resp.json()
        token = str(payload.get("access_token", "")).strip()
        if not token:
            _log.warning("GigaChat OAuth: нет access_token в ответе")
            raise ProviderRequestError("Не удалось авторизоваться в GigaChat.")
        expires_in = int(payload.get("expires_in", 1200))
        self._token = token
        self._token_expires_at = time.time() + max(60, expires_in)
        return token

    async def _complete_rest(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> LLMCompletionResult:
        def _call() -> dict[str, Any]:
            token = self._ensure_token_sync()
            body = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            resp = requests.post(
                self._api_url,
                json=body,
                headers=headers,
                timeout=CONFIG.http_timeout_seconds,
                verify=self._verify,
            )
            if resp.status_code >= 400:
                snip = _safe_response_snippet(resp.text)
                _log.warning("GigaChat HTTP %s: %s", resp.status_code, snip)
                raise ProviderRequestError(
                    f"GigaChat временно недоступен (код {resp.status_code}).",
                    status_code=resp.status_code,
                )
            return resp.json()

        data = await asyncio.to_thread(_call)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            _log.warning("GigaChat: неожиданная структура ответа")
            raise ProviderRequestError("Неожиданный ответ GigaChat.") from exc
        return LLMCompletionResult(content=str(content), raw_response=data, reasoning_details=None)

    async def _complete_openai_compat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> LLMCompletionResult:
        base = self._openai_base_url
        if not base:
            raise ConfigurationError("GIGACHAT_BASE_URL не задан для OpenAI-совместимого режима")

        token = await asyncio.to_thread(self._ensure_token_sync)

        client = AsyncOpenAI(
            api_key=token,
            base_url=base.rstrip("/"),
            timeout=CONFIG.http_timeout_seconds,
        )
        try:
            resp = await client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            _log.warning("GigaChat (OpenAI compat): %s", exc)
            raise ProviderRequestError("GigaChat временно недоступен.") from exc

        choice = resp.choices[0].message
        content = choice.content or ""
        raw = resp.model_dump() if hasattr(resp, "model_dump") else {}
        return LLMCompletionResult(content=str(content), raw_response=raw, reasoning_details=None)