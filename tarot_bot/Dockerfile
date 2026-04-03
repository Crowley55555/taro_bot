FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# SQLite: смонтируйте том на каталог с SQLITE_PATH (см. README).
# HEALTHCHECK при желании добавьте сами (curl/wget к health-endpoint бота здесь нет).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["python", "run.py"]
