# Telegram-бот Таро с ИИ

Python 3.12+, `python-telegram-bot` (long polling), SQLite, несколько LLM-провайдеров (OpenRouter, OpenAI, GigaChat, YandexGPT).

## Структура репозитория

```
.
├── app/                 # код бота (handlers, services, llm, data)
├── tests/               # pytest
├── run.py               # точка входа
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile           # образ для продакшена
├── docker-compose.yml   # деплой с томом для SQLite
├── .env.example
└── README.md
```

## Установка (локально)

Клонируйте репозиторий и из **корня** проекта:

```bash
python -m venv .venv
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и задайте `TELEGRAM_BOT_TOKEN` и ключи нужных провайдеров.

### Тесты

```bash
pip install -r requirements-dev.txt
set PYTHONPATH=.          # Windows CMD
# export PYTHONPATH=.     # Linux/macOS
pytest
```

## Запуск локально

Из корня репозитория:

Windows:

```powershell
set PYTHONPATH=.
python run.py
```

Linux / macOS:

```bash
export PYTHONPATH=.
python run.py
```

## Поведение сессии

- **`/start` и `/cancel`** (и inline «Отмена») сбрасывают **классический** расклад. **Свободный расклад** при этом сохраняется в памяти процесса и в SQLite (история), пока вы явно не завершите контекст или не начнёте новый сценарий.
- **Настройки** (провайдер, модель, длина и стиль ответа, в т.ч. `normal_ai` и `predictor`) сохраняются в `user_data`.
- **Главное меню** сохраняет FSM свободной сессии в `free_fsm` для пункта «Продолжить текущий».

### Свободный расклад

Тема контекста → циклы «1 / 3 / 5 карт → вопрос → толкование» и обсуждение без новых карт. Краткосрочная память для промпта: последние **`FREE_SESSION_MEMORY_LIMIT`** сообщений (см. `.env`). Полный сброс: «Завершить контекст». Состояние также пишется в **`persisted_free_sessions`**.

### История

Классические расклады и свободные сессии **автоматически** сохраняются в SQLite; раздел «История» позволяет открыть запись и продолжить с того же места. Подробности — в справке бота и в `.env.example`.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `TELEGRAM_HTTP_TIMEOUT_SECONDS` | Таймаут HTTP к `api.telegram.org` |
| `SQLITE_PATH` | Путь к файлу БД (в Docker обычно `/data/tarot_bot.db`) |
| `SQLITE_CONNECT_TIMEOUT_SECONDS` | Ожидание блокировки SQLite |
| `FREE_SESSION_MEMORY_LIMIT` | Скользящее окно сообщений в свободном режиме |
| `MAX_DIALOG_MESSAGES` / `MAX_DISCUSSION_MESSAGES` | Усечение историй диалога |
| `HTTP_TIMEOUT_SECONDS` | Таймаут запросов к LLM |
| `OPENROUTER_ENABLE_REASONING` | Режим reasoning в OpenRouter |
| `ADMIN_USER_IDS` | Список id для `/stats` |

Полный список — в `.env.example`.

## Docker

### Сборка образа

Из корня репозитория:

```bash
docker build -t tarot-bot:latest .
```

### Запуск одной командой (том для БД)

```bash
docker run --rm --env-file .env -v "$(pwd)/data:/data" -e SQLITE_PATH=/data/tarot_bot.db tarot-bot:latest
```

Windows PowerShell:

```powershell
docker run --rm --env-file .env -v "${PWD}/data:/data" -e SQLITE_PATH=/data/tarot_bot.db tarot-bot:latest
```

Создайте каталог `./data` заранее или Docker создаст том на хосте при монтировании.

### Docker Compose (рекомендуется для деплоя)

1. Скопируйте `.env.example` → `.env`, заполните секреты.
2. Запуск в фоне с перезапуском и именованным томом для SQLite:

```bash
docker compose up -d --build
```

Остановка: `docker compose down` (том `tarot_data` с данными сохраняется).

Образ не слушает порты: используется **long polling** к Telegram. Пользователь в контейнере: `appuser` (uid 10001).

## Архитектура

- `app/bot.py` — `Application`, хендлеры, `concurrent_updates=False` для стабильного `user_data`.
- `app/handlers/` — команды и callback-и.
- `app/services/` — расклады, промпты, сессия, SQLite, автосохранение истории.
- `app/llm/` — провайдеры и фабрика.
- `app/data/` — колода и каталог раскладов.

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и меню |
| `/help` | Справка |
| `/settings` | Настройки ответа и ИИ |
| `/history` | История сохранённых раскладов и сессий |
| `/cancel` | Отмена сценария |
| `/stats` | Статистика БД (только `ADMIN_USER_IDS`) |

## Провайдеры LLM

| Ключ | Описание |
|------|----------|
| `openrouter` | OpenRouter |
| `openai` | OpenAI Chat Completions |
| `gigachat` | GigaChat |
| `yandex` | YandexGPT (OpenAI-compatible) |

## Типичные проблемы

- **TimedOut к Telegram** — сеть, VPN, файрвол; увеличьте `TELEGRAM_HTTP_TIMEOUT_SECONDS`; при прокси задайте `HTTPS_PROXY` / `HTTP_PROXY`.
- **NetworkError при polling** — нестабильный прокси; бот обычно сам переподключается.
- **OpenRouter 429 / таймаут** — лимиты бесплатных моделей; смените модель или ключ.
- **GigaChat SSL** — при отладке иногда `GIGACHAT_VERIFY_SSL=false` (не для продакшена).
