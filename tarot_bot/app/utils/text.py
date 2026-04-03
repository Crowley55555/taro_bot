"""Форматирование текста для Telegram и отображение расклада."""

from __future__ import annotations

import html
import re
from typing import Final

from app.models.entities import DrawnCard

MAX_MESSAGE_LEN: Final[int] = 4096
# Запас под HTML-обёртку (<pre>) и сущности escape; не упираться в 4096.
INTERPRETATION_CHUNK_PLAIN_MAX: Final[int] = 3500


def escape_html(text: str) -> str:
    """Экранирует текст для parse_mode=HTML."""

    return html.escape(text, quote=True)


def build_single_interpretation_html(plain: str, *, max_len: int = MAX_MESSAGE_LEN) -> str:
    """Один HTML-блок интерпретации для одного сообщения Telegram (лимит max_len).

    Весь ответ (смысл, позиции, совет) остаётся в одном <pre>; при переполнении
    текст усечён и добавлена пометка — без второго сообщения и без разрыва клавиатуры.
    """

    plain = plain.strip()
    if not plain:
        return "<pre></pre>"

    note = "\n\n<i>Текст усечён — лимит одного сообщения Telegram (4096 символов).</i>"
    op, cl = "<pre>", "</pre>"

    def wrapped(inner: str) -> str:
        return f"{op}{escape_html(inner)}{cl}"

    full = wrapped(plain)
    if len(full) <= max_len:
        return full

    budget = max_len - len(note)
    lo, hi = 0, len(plain)
    best = wrapped("…")
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = plain[:mid].rstrip()
        if mid < len(plain):
            cand += "…"
        block = wrapped(cand)
        if len(block) <= budget:
            best = block + note
            lo = mid + 1
        else:
            hi = mid - 1

    if len(best) <= max_len:
        return best
    return "<pre>…</pre>"


def split_long_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Разбивает длинный текст на части, не превышающие лимит Telegram."""

    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        chunk = remaining[:limit]
        cut = chunk.rfind("\n\n")
        if cut < limit // 2:
            cut = chunk.rfind("\n")
        if cut < limit // 2:
            cut = limit
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    return parts


def split_text_for_telegram(
    text: str,
    *,
    max_plain_chars: int = INTERPRETATION_CHUNK_PLAIN_MAX,
) -> list[str]:
    """Делит plain-текст на чанки для отправки в Telegram с запасом под HTML.

    Границы (по убыванию приоритета): абзацы ``\\n\\n``, строки ``\\n``,
    конец предложения (``. `` / ``? `` / ``! ``), пробел; иначе жёсткий разрез.
    """

    text = strip_control_chars(text).strip()
    if not text:
        return []
    if len(text) <= max_plain_chars:
        return [text]

    parts: list[str] = []
    remaining = text
    min_first = min(120, max_plain_chars // 6)

    while remaining:
        if len(remaining) <= max_plain_chars:
            parts.append(remaining)
            break
        window = remaining[:max_plain_chars]
        cut = _split_window_at_natural_boundary(window, max_plain_chars, min_first)
        chunk = remaining[:cut]
        if not chunk.strip():
            chunk = remaining[:max_plain_chars]
            cut = len(chunk)
        parts.append(chunk)
        remaining = remaining[cut:]

    return parts


def _split_window_at_natural_boundary(window: str, max_chars: int, min_pos: int) -> int:
    """Индекс конца первого фрагмента (exclusive), не больше max_chars."""

    if len(window) <= max_chars:
        return len(window)
    w = window[:max_chars]
    lo = min(min_pos, max_chars // 4)

    pos = w.rfind("\n\n", lo)
    if pos != -1:
        return pos + 2

    pos = w.rfind("\n", lo)
    if pos != -1:
        return pos + 1

    pos = max(w.rfind(". ", lo), w.rfind("? ", lo), w.rfind("! ", lo))
    if pos != -1:
        return pos + 2

    pos = w.rfind(" ", lo)
    if pos != -1:
        return pos + 1

    return max_chars


def chunk_html_record_messages(
    header_html: str,
    record_blocks: list[str],
    *,
    limit: int = 3500,
    separator: str = "\n---\n",
) -> list[str]:
    """Собирает сообщения из целых HTML-блоков записей, не разрезая блок посередине."""

    if not record_blocks:
        return [header_html] if header_html.strip() else []

    chunks: list[str] = []
    buf = header_html.rstrip() + "\n\n" if header_html.strip() else ""
    first_block = True

    for block in record_blocks:
        sep = "" if first_block else separator
        first_block = False
        candidate = buf + sep + block

        if len(candidate) <= limit:
            buf = candidate
            continue

        if buf.strip():
            chunks.append(buf)
        if len(block) <= limit:
            buf = block
        else:
            plain = _html_block_to_plain_fallback(block, limit=limit - 100)
            chunks.append(plain)
            buf = ""

    if buf.strip():
        chunks.append(buf)

    return chunks if chunks else [header_html]


def _html_block_to_plain_fallback(block: str, *, limit: int) -> str:
    """Убирает простые HTML-теги и усечёт текст для отправки без parse_mode."""

    t = re.sub(r"<[^>]+>", "", block)
    t = html.unescape(t).strip()
    if len(t) > limit:
        t = t[: max(0, limit - 1)] + "…"
    return t


def format_cards_list(cards: list[DrawnCard]) -> str:
    """Краткий список карт с позициями и ориентациями (plain)."""

    lines: list[str] = []
    for i, c in enumerate(cards, start=1):
        lines.append(f"{i}. {c.position_name}: {c.card} — {c.orientation}")
    return "\n".join(lines)


def format_cards_list_html(cards: list[DrawnCard]) -> str:
    """Список карт для HTML-сообщения."""

    rows: list[str] = []
    for i, c in enumerate(cards, start=1):
        rows.append(
            f"{i}. <b>{escape_html(c.position_name)}</b>: "
            f"{escape_html(c.card)} — <i>{escape_html(c.orientation)}</i>"
        )
    return "\n".join(rows)


def short_spread_summary(title: str, description: str, cards_count: int) -> str:
    """Краткое описание расклада для меню."""

    return f"{title}\n{cards_count} карт(ы). {description}"


def strip_control_chars(text: str) -> str:
    """Удаляет управляющие символы, кроме переводов строк и табуляции."""

    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
