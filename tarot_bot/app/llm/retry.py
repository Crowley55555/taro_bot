"""Повтор запросов с экспоненциальной задержкой."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.config import CONFIG

T = TypeVar("T")
_log = logging.getLogger(__name__)


async def run_with_retry(
    op: Callable[[], Awaitable[T]],
    *,
    name: str,
) -> T:
    """Выполняет async-операцию с повтором при временных сбоях."""

    last_exc: Exception | None = None
    for attempt in range(1, CONFIG.llm_max_retries + 1):
        try:
            return await op()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            retriable = _is_retriable(exc)
            _log.warning("%s попытка %s/%s: %s", name, attempt, CONFIG.llm_max_retries, exc)
            if not retriable or attempt >= CONFIG.llm_max_retries:
                raise
            delay = CONFIG.llm_retry_backoff_base ** (attempt - 1)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _is_retriable(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    name = type(exc).__name__
    if name in {
        "ReadTimeout",
        "ConnectTimeout",
        "ConnectionError",
        "RemoteDisconnected",
        "ChunkedEncodingError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
        "TimeoutException",
    }:
        return True
    msg = str(exc).lower()
    return "timeout" in msg or "temporar" in msg or "429" in msg or "503" in msg or "502" in msg