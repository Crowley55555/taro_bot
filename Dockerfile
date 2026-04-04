# Сборка образа бота (polling, без веб-сервера).
# Контекст сборки — корень репозитория (где лежат app/, run.py, requirements.txt).

FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

# SQLite: смонтируйте том на каталог с SQLITE_PATH (см. README и docker-compose.yml).
CMD ["python", "run.py"]
