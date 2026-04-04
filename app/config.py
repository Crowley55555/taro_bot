"""Загрузка конфигурации из переменных окружения (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

load_dotenv()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _parse_admin_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return frozenset(ids)


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Настройки приложения, считанные из окружения."""

    telegram_bot_token: str
    # connect/read/write/pool для httpx → api.telegram.org (см. TELEGRAM_HTTP_TIMEOUT_SECONDS)
    telegram_http_timeout_seconds: float
    default_llm_provider: str
    default_openrouter_model: str
    default_openai_model: str
    default_gigachat_model: str
    default_yandex_model: str

    openrouter_api_key: str | None
    openrouter_enable_reasoning: bool
    openai_api_key: str | None

    gigachat_auth_key: str | None
    gigachat_client_id: str | None
    gigachat_scope: str
    gigachat_verify_ssl: bool
    gigachat_use_openai_compat: bool
    gigachat_base_url: str | None
    gigachat_oauth_url: str
    gigachat_api_url: str

    yandex_api_key: str | None
    yandex_catalog_id: str | None
    yandex_base_url: str

    sqlite_path: Path
    sqlite_connect_timeout_seconds: float
    debug: bool
    admin_user_ids: frozenset[int]

    http_timeout_seconds: float
    llm_max_retries: int
    llm_retry_backoff_base: float
    max_followup_per_reading: int
    max_dialog_messages: int
    question_min_len: int  # не используется для отсечения вопросов; оставлено для совместимости с .env
    question_max_len: int
    max_discussion_messages: int
    free_session_memory_limit: int


def load_config() -> AppConfig:
    """Собирает конфигурацию из переменных окружения."""

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    sqlite_raw = os.getenv("SQLITE_PATH", "./tarot_bot.db").strip() or "./tarot_bot.db"

    return AppConfig(
        telegram_bot_token=token,
        telegram_http_timeout_seconds=_env_float("TELEGRAM_HTTP_TIMEOUT_SECONDS", 30.0),
        default_llm_provider=os.getenv("DEFAULT_LLM_PROVIDER", "openrouter").strip()
        or "openrouter",
        default_openrouter_model=os.getenv(
            "DEFAULT_OPENROUTER_MODEL", "qwen/qwen3.6-plus:free"
        ).strip()
        or "qwen/qwen3.6-plus:free",
        default_openai_model=os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4o-mini").strip()
        or "gpt-4o-mini",
        default_gigachat_model=os.getenv("DEFAULT_GIGACHAT_MODEL", "GigaChat-2-Max").strip()
        or "GigaChat-2-Max",
        default_yandex_model=os.getenv("DEFAULT_YANDEX_MODEL", "yandexgpt/latest").strip()
        or "yandexgpt/latest",
        openrouter_api_key=_optional_key("OPENROUTER_API_KEY"),
        openrouter_enable_reasoning=_env_bool("OPENROUTER_ENABLE_REASONING", False),
        openai_api_key=_optional_key("OPENAI_API_KEY"),
        gigachat_auth_key=_optional_key("GIGACHAT_AUTH_KEY"),
        gigachat_client_id=_optional_key("GIGACHAT_CLIENT_ID"),
        gigachat_scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()
        or "GIGACHAT_API_PERS",
        gigachat_verify_ssl=_env_bool("GIGACHAT_VERIFY_SSL", True),
        gigachat_use_openai_compat=_env_bool("GIGACHAT_USE_OPENAI_COMPAT", False),
        gigachat_base_url=_optional_key("GIGACHAT_BASE_URL"),
        gigachat_oauth_url=os.getenv(
            "GIGACHAT_OAUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        ).strip()
        or "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        gigachat_api_url=os.getenv(
            "GIGACHAT_API_URL", "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        ).strip()
        or "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        yandex_api_key=_optional_key("YANDEX_API_KEY"),
        yandex_catalog_id=_optional_key("YANDEX_CATALOG_ID"),
        yandex_base_url=os.getenv(
            "YANDEX_BASE_URL", "https://llm.api.cloud.yandex.net/v1"
        ).strip()
        or "https://llm.api.cloud.yandex.net/v1",
        sqlite_path=Path(sqlite_raw).expanduser(),
        sqlite_connect_timeout_seconds=_env_float("SQLITE_CONNECT_TIMEOUT_SECONDS", 30.0),
        debug=_env_bool("DEBUG", False),
        admin_user_ids=_parse_admin_ids(os.getenv("ADMIN_USER_IDS")),
        http_timeout_seconds=_env_float("HTTP_TIMEOUT_SECONDS", 120.0),
        llm_max_retries=_env_int("LLM_MAX_RETRIES", 3),
        llm_retry_backoff_base=_env_float("LLM_RETRY_BACKOFF_BASE", 1.5),
        max_followup_per_reading=_env_int("MAX_FOLLOWUP_PER_READING", 5),
        max_dialog_messages=_env_int("MAX_DIALOG_MESSAGES", 8),
        question_min_len=_env_int("QUESTION_MIN_LEN", 30),
        question_max_len=_env_int("QUESTION_MAX_LEN", 1200),
        max_discussion_messages=_env_int("MAX_DISCUSSION_MESSAGES", 12),
        free_session_memory_limit=_env_int("FREE_SESSION_MEMORY_LIMIT", 35),
    )


def _optional_key(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    s = v.strip()
    return s or None


CONFIG: Final[AppConfig] = load_config()
