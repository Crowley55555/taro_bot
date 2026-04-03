"""Inline-клавиатуры."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Сделать расклад", callback_data="m:spread")],
            [InlineKeyboardButton("Свободный расклад", callback_data="m:free")],
            [InlineKeyboardButton("Выбрать ИИ", callback_data="m:ai")],
            [InlineKeyboardButton("Настройки", callback_data="m:set")],
            [InlineKeyboardButton("История", callback_data="m:hist")],
            [InlineKeyboardButton("Помощь", callback_data="m:help")],
        ]
    )


def back_cancel_row(back_data: str = "m:main", cancel_data: str = "x:cancel") -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton("Назад", callback_data=back_data),
        InlineKeyboardButton("Отмена", callback_data=cancel_data),
    ]


def back_cancel_keyboard(back_data: str = "m:main", cancel_data: str = "x:cancel") -> InlineKeyboardMarkup:
    """Одна строка «Назад» + «Отмена» как полноценный reply_markup."""

    return InlineKeyboardMarkup([back_cancel_row(back_data, cancel_data)])


def categories_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Быстрые", callback_data="c:quick")],
        [InlineKeyboardButton("Универсальные", callback_data="c:universal")],
        [InlineKeyboardButton("Любовь и отношения", callback_data="c:love")],
        [InlineKeyboardButton("Карьера и деньги", callback_data="c:career")],
        [InlineKeyboardButton("Глубокие", callback_data="c:deep")],
        back_cancel_row("m:main"),
    ]
    return InlineKeyboardMarkup(rows)


def spread_list_keyboard(keys: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """keys: (spread_key, title)"""

    rows: list[list[InlineKeyboardButton]] = []
    for sk, title in keys:
        rows.append([InlineKeyboardButton(title[:64], callback_data=f"s:{sk}")])
    rows.append(back_cancel_row("m:spread_cat", "m:main"))
    return InlineKeyboardMarkup(rows)


def spread_confirm_keyboard(spread_key: str, category_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Подтвердить расклад", callback_data=f"sc:{spread_key}")],
            back_cancel_row(f"bc:{category_key}", "m:main"),
        ]
    )


def free_session_actions_keyboard(completed_turns: int, max_turns: int) -> InlineKeyboardMarkup:
    """Действия в свободной сессии; после лимита шагов — только новый контекст и главное меню."""

    if completed_turns >= max_turns:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Новый свободный расклад", callback_data="m:free")],
                [InlineKeyboardButton("Главное меню", callback_data="m:main")],
            ]
        )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1 карта", callback_data="fr:1"),
                InlineKeyboardButton("3 карты", callback_data="fr:3"),
                InlineKeyboardButton("5 карт", callback_data="fr:5"),
            ],
            [InlineKeyboardButton("Завершить контекст", callback_data="fr:end")],
            [InlineKeyboardButton("Главное меню", callback_data="m:main")],
        ]
    )


def after_reading_keyboard() -> InlineKeyboardMarkup:
    """После толкования: текст = обсуждение; 1/3/5 — новый шаг с новыми картами."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1 карта", callback_data="pr:1"),
                InlineKeyboardButton("3 карты", callback_data="pr:3"),
                InlineKeyboardButton("5 карт", callback_data="pr:5"),
            ],
            [
                InlineKeyboardButton("Новый расклад", callback_data="f:new"),
                InlineKeyboardButton("Сменить ИИ", callback_data="f:chg_ai"),
            ],
            [InlineKeyboardButton("Главное меню", callback_data="m:main")],
        ]
    )


def providers_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("OpenRouter", callback_data="p:openrouter")],
            [InlineKeyboardButton("OpenAI", callback_data="p:openai")],
            [InlineKeyboardButton("GigaChat", callback_data="p:gigachat")],
            [InlineKeyboardButton("YandexGPT", callback_data="p:yandex")],
            back_cancel_row("m:main"),
        ]
    )


def model_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Модель по умолчанию (.env)", callback_data="md:def")],
            [InlineKeyboardButton("Ввести модель вручную", callback_data="md:manual")],
            back_cancel_row("m:ai"),
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Длина ответа", callback_data="st:mode")],
            [InlineKeyboardButton("Стиль ответа", callback_data="st:style")],
            [InlineKeyboardButton("Провайдер и модель", callback_data="m:ai")],
            back_cancel_row("m:main"),
        ]
    )


def reading_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Кратко", callback_data="rm:short")],
            [InlineKeyboardButton("Подробно", callback_data="rm:medium")],
            [InlineKeyboardButton("Глубоко", callback_data="rm:deep")],
            back_cancel_row("m:set"),
        ]
    )


def reading_style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Мягкий", callback_data="rs:soft")],
            [InlineKeyboardButton("Психологический", callback_data="rs:psychological")],
            [InlineKeyboardButton("Практический", callback_data="rs:practical")],
            back_cancel_row("m:set"),
        ]
    )