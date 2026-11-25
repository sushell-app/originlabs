FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system originlabs \
    && useradd --system --gid originlabs --create-home originlabs

COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install .

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

RUN chown -R originlabs:originlabs /app
USER originlabs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
