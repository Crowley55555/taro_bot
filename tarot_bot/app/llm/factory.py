"""Фабрика LLM-провайдеров."""

from __future__ import annotations

from typing import Final

from app.config import CONFIG
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import ConfigurationError
from app.llm.gigachat_provider import GigaChatProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.openrouter_provider import OpenRouterProvider
from app.llm.yandex_provider import YandexGPTProvider

_PROVIDER_ALIASES: Final[dict[str, str]] = {
    "openrouter": "openrouter",
    "or": "openrouter",
    "openai": "openai",
    "gigachat": "gigachat",
    "giga": "gigachat",
    "yandex": "yandex",
    "yandexgpt": "yandex",
}


def get_provider(provider_name: str, model_name: str | None = None) -> BaseLLMProvider:
    """Возвращает экземпляр провайдера; проверяет наличие ключей."""

    key = _PROVIDER_ALIASES.get(provider_name.strip().lower(), provider_name.strip().lower())

    if key == "openrouter":
        if not CONFIG.openrouter_api_key:
            raise ConfigurationError("Не задан OPENROUTER_API_KEY в .env")
        model = model_name or CONFIG.default_openrouter_model
        return OpenRouterProvider(api_key=CONFIG.openrouter_api_key, model=model)

    if key == "openai":
        if not CONFIG.openai_api_key:
            raise ConfigurationError("Не задан OPENAI_API_KEY в .env")
        model = model_name or CONFIG.default_openai_model
        return OpenAIProvider(api_key=CONFIG.openai_api_key, model=model)

    if key == "gigachat":
        model = model_name or CONFIG.default_gigachat_model
        return GigaChatProvider(
            client_id=CONFIG.gigachat_client_id or "",
            auth_key=CONFIG.gigachat_auth_key or "",
            scope=CONFIG.gigachat_scope,
            model=model,
            oauth_url=CONFIG.gigachat_oauth_url,
            api_url=CONFIG.gigachat_api_url,
            verify_ssl=CONFIG.gigachat_verify_ssl,
            use_openai_compat=CONFIG.gigachat_use_openai_compat,
            openai_base_url=CONFIG.gigachat_base_url,
        )

    if key == "yandex":
        if not CONFIG.yandex_api_key or not CONFIG.yandex_catalog_id:
            raise ConfigurationError("Задайте YANDEX_API_KEY и YANDEX_CATALOG_ID в .env")
        model = model_name or CONFIG.default_yandex_model
        return YandexGPTProvider(
            api_key=CONFIG.yandex_api_key,
            catalog_id=CONFIG.yandex_catalog_id,
            base_url=CONFIG.yandex_base_url,
            model=model,
        )

    raise ConfigurationError(f"Неизвестный провайдер: {provider_name}")