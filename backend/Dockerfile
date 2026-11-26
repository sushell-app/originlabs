FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system originlabs \
    && useradd --system --gid originlabs --create-home originlabs

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R originlabs:originlabs /app

USER originlabs

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
