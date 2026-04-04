"""Тесты безопасного chunking HTML по записям истории."""

from __future__ import annotations

from app.utils.text import (
    INTERPRETATION_CHUNK_PLAIN_MAX,
    build_single_interpretation_html,
    chunk_html_record_messages,
    escape_html,
    split_text_for_telegram,
)


def test_chunk_keeps_record_blocks_intact() -> None:
    blocks = [
        f"<b>{escape_html('A')}</b>\n<i>Вопрос:</i> {escape_html('q1')}\n",
        f"<b>{escape_html('B')}</b>\n<i>Вопрос:</i> {escape_html('q2')}\n",
    ]
    chunks = chunk_html_record_messages("<b>H</b>\n\n", blocks, limit=500)
    assert len(chunks) >= 1
    for ch in chunks:
        assert "<b>" in ch
        assert ch.count("<b>") == ch.count("</b>")


def test_chunk_splits_when_buffer_exceeds_limit() -> None:
    big = "<b>x</b>\n" * 200
    blocks = [big, big]
    chunks = chunk_html_record_messages("", blocks, limit=80)
    assert len(chunks) >= 2


def test_build_single_interpretation_under_cap() -> None:
    h = build_single_interpretation_html("Короткий ответ.\n\nСовет: дышать.")
    assert len(h) <= 4096
    assert "<pre>" in h


def test_build_single_interpretation_truncates_long() -> None:
    h = build_single_interpretation_html("Z" * 20000)
    assert len(h) <= 4096
    assert "усечён" in h or "…" in h


def test_split_text_for_telegram_single_short() -> None:
    assert split_text_for_telegram("Короткий ответ.") == ["Короткий ответ."]


def test_split_text_for_telegram_respects_max_and_splits() -> None:
    big = "\n\n".join([f"Блок {i}.\n" + ("строка " * 120) for i in range(40)]).strip()
    parts = split_text_for_telegram(big, max_plain_chars=800)
    assert len(parts) >= 2
    assert all(len(p) <= 800 for p in parts)
    assert "".join(parts) == big


def test_split_text_for_telegram_default_limit() -> None:
    assert INTERPRETATION_CHUNK_PLAIN_MAX <= 3800


def test_oversized_single_block_uses_plain_fallback() -> None:
    huge = "<b>" + "x" * 5000 + "</b>"
    chunks = chunk_html_record_messages("", [huge], limit=100)
    assert len(chunks) >= 1
    assert any("<" not in c for c in chunks)
