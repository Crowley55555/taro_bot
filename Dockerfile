# Сборка образа бота (polling, без веб-сервера).
# Контекст сборки — корень репозитория (где лежат app/, run.py, requirements.txt).

FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates gosu \
    && rm -rf /var/lib/apt/lists/*

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

RUN useradd --create-home --uid 10001 --user-group appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /data \
    && chown appuser:appuser /data

# Запуск процесса бота — от appuser через entrypoint (после chown тома /data).
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "run.py"]
