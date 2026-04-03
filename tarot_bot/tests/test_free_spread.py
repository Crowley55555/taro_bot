"""Тесты свободного расклада (без Telegram и LLM)."""

from __future__ import annotations

import pytest

from app.services.prompt_builder import _format_free_history_for_prompt
from app.services.tarot import draw_free_spread


@pytest.mark.parametrize("size", [1, 3, 5])
def test_draw_free_spread_length_unique_positions(size: int) -> None:
    cards = draw_free_spread(size)
    assert len(cards) == size
    names = [c.card for c in cards]
    assert len(names) == len(set(names))
    for i, c in enumerate(cards, start=1):
        assert c.position_name == f"Карта {i}"


def test_draw_free_spread_rejects_invalid_size() -> None:
    with pytest.raises(ValueError):
        draw_free_spread(2)


def test_free_history_splits_old_and_recent() -> None:
    history = [
        {
            "turn": i,
            "spread_size": 3,
            "question": f"вопрос шага {i}",
            "cards": [{"position_name": "Карта 1", "card": "Шут", "orientation": "Прямое"}],
            "interpretation": f"интерпретация {i}",
        }
        for i in range(1, 8)
    ]
    compact, recent = _format_free_history_for_prompt(history)
    assert "Шаг 1" in compact
    assert "Шаг 2" in compact
    assert "Шаг 7" in recent
    assert "Шаг 3" not in compact
