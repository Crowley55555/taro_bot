"""Отправка интерпретации: длинный текст — несколько сообщений, клавиатура только на последнем."""

from __future__ import annotations

from collections import deque
from typing import Any

from app.utils.text import (
    MAX_MESSAGE_LEN,
    build_single_interpretation_html,
    split_text_for_telegram,
)

POST_READING_UX_HINT = (
    "\n\n—\n"
    "Вы можете написать уточняющий вопрос по этому раскладу или выбрать 1/3/5 карт для следующего шага."
)


def _interpretation_plain_chunks(plain_interpretation: str) -> list[str]:
    """Собирает plain-чанки; если после <pre>+escape длина > 4096 — дробит дальше."""

    def _fits_html(c: str) -> bool:
        return len(build_single_interpretation_html(c)) <= MAX_MESSAGE_LEN

    pending = deque(split_text_for_telegram(plain_interpretation))
    out: list[str] = []
    while pending:
        chunk = pending.popleft()
        if not chunk:
            continue
        if _fits_html(chunk):
            out.append(chunk)
            continue
        half = max(400, len(chunk) // 2)
        finer = split_text_for_telegram(chunk, max_plain_chars=half)
        if len(finer) <= 1:
            finer = [chunk[:half], chunk[half:]]
        for part in reversed(finer):
            if part:
                pending.appendleft(part)
    return out


async def send_interpretation_reply(
    message: Any,
    plain_interpretation: str,
    keyboard: Any,
    *,
    with_post_reading_hint: bool = True,
) -> None:
    """HTML в каждом чанке (<pre>); подсказка UX и клавиатура — только на последнем сообщении."""

    chunks = _interpretation_plain_chunks(plain_interpretation)
    if with_post_reading_hint and chunks:
        chunks[-1] = chunks[-1].rstrip() + POST_READING_UX_HINT
    elif with_post_reading_hint and not chunks:
        chunks = [POST_READING_UX_HINT.strip()]

    if not chunks:
        await message.reply_html(build_single_interpretation_html(""), reply_markup=keyboard)
        return

    last = len(chunks) - 1
    for i, chunk in enumerate(chunks):
        body = build_single_interpretation_html(chunk)
        await message.reply_html(body, reply_markup=keyboard if i == last else None)
