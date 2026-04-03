# Telegram-бот Таро с ИИ

Python 3.12+, `python-telegram-bot` (Application.builder), polling, SQLite, несколько LLM-провайдеров.

## Установка

```bash
cd tarot_bot
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и заполните `TELEGRAM_BOT_TOKEN` и ключи выбранных провайдеров.

### Тесты (опционально)

```bash
cd tarot_bot
pip install -r requirements-dev.txt
set PYTHONPATH=.
pytest
```

На Linux/macOS: `export PYTHONPATH=.` перед `pytest`.

## Запуск локально

```bash
cd tarot_bot
set PYTHONPATH=.
python run.py
```

На Linux/macOS:

```bash
cd tarot_bot
export PYTHONPATH=.
python run.py
```

## Поведение сессии

- **`/start` и `/cancel`** (и inline «Отмена» там, где ведёт в отмену) **полностью сбрасывают активный расклад**: карты, вопрос, интерпретацию, историю диалога по раскладу, флаги вроде ожидания переинтерпретации, а также режим **«Свободный расклад»** (тема и шаги контекста).
- **Настройки пользователя сохраняются**: провайдер ИИ, модель, длина ответа (reading mode), стиль ответа (reading style).
- **Главное меню** («Назад» в корень) также переводит в спокойное состояние без активного расклада — см. реализацию `go_idle` в коде.

### Свободный расклад

Отдельный сценарий из главного меню: задаёте **тему контекста**, затем повторяете цикл «1 / 3 / 5 карт → вопрос к шагу → ответ ИИ». Классический каталог раскладов и follow-up по ним не используются. Лимит шагов в одном контексте задаётся **`MAX_FREE_SESSION_TURNS`** (по умолчанию 20). Контекст сбрасывается при **«Завершить контекст»**, `/cancel`, `/start`, входе в **«Сделать расклад»** или полном выходе в главное меню. Каждый успешный шаг дополнительно пишется в SQLite (`free_session_steps`).

## История раскладов

- В SQLite попадают только расклады, сохранённые кнопкой **«Сохранить расклад»** после интерпретации.
- `/history` и пункт меню «История» показывают последние записи; длинный список режется **по целым записям**, без разреза HTML посередине тега.

## Важные переменные `.env`

| Переменная | Назначение |
|------------|------------|
| `OPENROUTER_ENABLE_REASONING` | `false` по умолчанию; при `true` в запрос OpenRouter добавляется reasoning; при 400/422 — один повтор без reasoning. |
| `MAX_DIALOG_MESSAGES` | Максимум сообщений в истории follow-up (после усечения), по умолчанию 8. |
| `MAX_FOLLOWUP_PER_READING` | Лимит уточняющих вопросов на один расклад. |
| `MAX_FREE_SESSION_TURNS` | Максимум шагов (циклов карт+вопрос+интерпретация) в одном контексте свободного расклада. |
| `SQLITE_PATH` | Путь к файлу базы. |
| `SQLITE_CONNECT_TIMEOUT_SECONDS` | Таймаут `sqlite3.connect` при ожидании блокировки. |
| `HTTP_TIMEOUT_SECONDS` | Таймаут HTTP/SDK для провайдеров. |
| `QUESTION_MIN_LEN` / `QUESTION_MAX_LEN` | Длина пользовательского вопроса. |

Полный список — в `.env.example`.

## Docker

Сборка из каталога `tarot_bot`:

```bash
cd tarot_bot
docker build -t tarot-bot .
```

Запуск с **сохранением SQLite на хосте** (Windows PowerShell, текущая папка — каталог с БД):

```powershell
docker run --rm --env-file .env -v "${PWD}:/data" -e SQLITE_PATH=/data/tarot_bot.db tarot-bot
```

На Linux/macOS удобно смонтировать каталог данных:

```bash
mkdir -p ./data
docker run --rm --env-file .env -v "$(pwd)/data:/data" -e SQLITE_PATH=/data/tarot_bot.db tarot-bot
```

Образ запускается не от root (`USER appuser`). При необходимости добавьте свой `HEALTHCHECK` в Dockerfile — в шаблоне оставлены только комментарии.

## Архитектура

- `app/bot.py` — сборка `Application`, регистрация хендлеров, последовательная обработка апдейтов (`concurrent_updates=False`) для stateful `user_data`.
- `app/handlers/` — команды и callback-и.
- `app/services/` — расклады, промпты, сессия, SQLite.
- `app/llm/` — провайдеры (OpenRouter, OpenAI, GigaChat, YandexGPT) и фабрика.
- `app/data/` — колода 78 карт и каталог раскладов.

Состояние FSM хранится в `context.user_data`.

## Команды

- `/start` — приветствие и меню (сброс активного расклада)
- `/help` — помощь
- `/settings` — настройки
- `/history` — последние сохранённые расклады
- `/cancel` — отмена сценария и сброс активного расклада
- `/stats` — статистика (только `ADMIN_USER_IDS`)

## Провайдеры

| Ключ | Описание |
|------|----------|
| `openrouter` | OpenRouter (HTTP `requests`) |
| `openai` | OpenAI Chat Completions |
| `gigachat` | GigaChat OAuth + REST или OpenAI-совместимый режим |
| `yandex` | YandexGPT через OpenAI-compatible API |

## Типичные ошибки

- **`telegram.error.TimedOut` / `ConnectTimeout` при запуске** — не доходят до `api.telegram.org`: VPN, корпоративный файрвол, блокировки. Проверьте в браузере или `curl https://api.telegram.org`. В `.env` увеличьте `TELEGRAM_HTTP_TIMEOUT_SECONDS` (например `60`). При прокси задайте переменные окружения `HTTPS_PROXY` / `HTTP_PROXY` (поддерживаются httpx).
- **Нет ответа ИИ** — проверьте ключи в `.env`, лимиты провайдера и сеть.
- **Пустой ответ модели** — состояние не должно ломаться; можно повторить вопрос или сменить ИИ.
- **GigaChat SSL** — при отладке можно выставить `GIGACHAT_VERIFY_SSL=false` (не рекомендуется в проде).
- **Yandex модель** — задаётся `DEFAULT_YANDEX_MODEL` и `YANDEX_CATALOG_ID`; итоговая строка модели `gpt://<catalog>/<model>`.
