"""Полная колода Таро: 78 карт в нормализованном русском виде."""

from __future__ import annotations

from typing import Final

_MAJORS: Final[tuple[str, ...]] = (
    "Шут",
    "Маг",
    "Верховная Жрица",
    "Императрица",
    "Император",
    "Иерофант",
    "Влюблённые",
    "Колесница",
    "Сила",
    "Отшельник",
    "Колесо Фортуны",
    "Справедливость",
    "Повешенный",
    "Смерть",
    "Умеренность",
    "Дьявол",
    "Башня",
    "Звезда",
    "Луна",
    "Солнце",
    "Суд",
    "Мир",
)

_RANKS: Final[tuple[str, ...]] = (
    "Туз",
    "Двойка",
    "Тройка",
    "Четвёрка",
    "Пятёрка",
    "Шестёрка",
    "Семёрка",
    "Восьмёрка",
    "Девятка",
    "Десятка",
    "Паж",
    "Рыцарь",
    "Королева",
    "Король",
)

_SUITS: Final[tuple[str, ...]] = ("Жезлов", "Кубков", "Мечей", "Пентаклей")


def _build_minors() -> list[str]:
    return [f"{rank} {suit}" for suit in _SUITS for rank in _RANKS]


TAROT_DECK: Final[list[str]] = list(_MAJORS) + _build_minors()


def assert_deck_size() -> None:
    """Проверка инварианта размера колоды (78)."""

    if len(TAROT_DECK) != 78:
        msg = f"Ожидалось 78 карт, получено {len(TAROT_DECK)}"
        raise RuntimeError(msg)


assert_deck_size()