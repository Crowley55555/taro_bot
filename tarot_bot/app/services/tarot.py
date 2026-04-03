"""Генерация расклада: случайные карты без повторов."""

from __future__ import annotations

import random
from typing import Literal

from app.data.spreads import SPREADS
from app.data.tarot_deck import TAROT_DECK
from app.models.entities import DrawnCard


def draw_spread(spread_key: str) -> list[DrawnCard]:
    """Вытягивает карты для расклада: уникальные карты, случайная ориентация."""

    spec = SPREADS[spread_key]
    n = spec["cards_count"]
    positions: list[str] = list(spec["positions"])
    if len(positions) != n:
        msg = f"Несовпадение числа позиций и cards_count для {spread_key}"
        raise ValueError(msg)

    chosen = random.sample(TAROT_DECK, k=n)
    orientations: tuple[Literal["Прямое", "Перевёрнутое"], ...] = ("Прямое", "Перевёрнутое")

    result: list[DrawnCard] = []
    for pos, card in zip(positions, chosen, strict=True):
        ori = random.choice(orientations)
        result.append(DrawnCard(position_name=pos, card=card, orientation=ori))
    return result


def draw_free_spread(size: int) -> list[DrawnCard]:
    """Случайные карты без каталога раскладов (1 / 3 / 5 карт)."""

    if size not in (1, 3, 5):
        msg = f"Размер свободного расклада должен быть 1, 3 или 5, получено {size}"
        raise ValueError(msg)
    chosen = random.sample(TAROT_DECK, k=size)
    orientations: tuple[Literal["Прямое", "Перевёрнутое"], ...] = ("Прямое", "Перевёрнутое")
    return [
        DrawnCard(
            position_name=f"Карта {i}",
            card=card,
            orientation=random.choice(orientations),
        )
        for i, card in enumerate(chosen, start=1)
    ]