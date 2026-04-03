"""Настройка стандартного логирования приложения."""

from __future__ import annotations

import logging
import sys
from typing import Final

from app.config import CONFIG


def setup_logging() -> None:
    """Инициализирует корневой логгер: уровень, формат, вывод в stderr."""

    level = logging.DEBUG if CONFIG.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    logging.getLogger("telegram.ext").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Возвращает именованный логгер."""

    return logging.getLogger(name)


_APP_LOGGER: Final = get_logger("tarot_bot.app")