"""Простые таймеры для логирования."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

import logging

_log = logging.getLogger(__name__)


@contextmanager
def log_duration(name: str, logger: logging.Logger | None = None) -> Generator[None, None, None]:
    """Логирует длительность блока в миллисекундах."""

    lg = logger or _log
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        lg.info("%s завершено за %.1f мс", name, ms)