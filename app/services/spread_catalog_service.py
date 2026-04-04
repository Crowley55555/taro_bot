"""Доступ к каталогу раскладов и категориям."""

from __future__ import annotations

from typing import Final

from app.data.spreads import SPREADS
from app.models.entities import SpreadDefinition

_CATEGORY_LABELS: Final[dict[str, str]] = {
    "quick": "Быстрые",
    "universal": "Универсальные",
    "love": "Любовь и отношения",
    "career": "Карьера и деньги",
    "deep": "Глубокие",
}

_CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "quick",
    "universal",
    "love",
    "career",
    "deep",
)


def list_categories() -> list[tuple[str, str]]:
    """Возвращает пары (key, title) в порядке меню."""

    return [(k, _CATEGORY_LABELS[k]) for k in _CATEGORY_ORDER]


def spreads_for_category(category_key: str) -> list[SpreadDefinition]:
    """Все расклады выбранной категории."""

    items: list[SpreadDefinition] = []
    for data in SPREADS.values():
        if data["category"] == category_key:
            items.append(_to_definition(data))
    items.sort(key=lambda s: s.title)
    return items


def get_spread(spread_key: str) -> SpreadDefinition:
    """Возвращает описание расклада по ключу."""

    if spread_key not in SPREADS:
        msg = f"Неизвестный расклад: {spread_key}"
        raise KeyError(msg)
    return _to_definition(SPREADS[spread_key])


def _to_definition(data: dict) -> SpreadDefinition:
    return SpreadDefinition(
        key=data["key"],
        title=data["title"],
        category=data["category"],
        short_description=data["short_description"],
        cards_count=int(data["cards_count"]),
        positions=list(data["positions"]),
        suggested_questions=list(data["suggested_questions"]),
        is_deep=bool(data["is_deep"]),
        allow_followup=bool(data.get("allow_followup", True)),
    )