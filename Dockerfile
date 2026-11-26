# Stage 1: Build React + TypeScript + Tailwind frontend
FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src
RUN npm run build

# Stage 2: Unified Python 3.12 runtime serving FastAPI API + built SPA frontend
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ORIGINLABS_STATIC_DIR=/app/static

WORKDIR /app

RUN groupadd --system originlabs \
    && useradd --system --gid originlabs --create-home originlabs

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY --from=frontend-build /frontend/dist /app/static

RUN pip install --upgrade pip \
    && pip install . \
    && chown -R originlabs:originlabs /app

USER originlabs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/meta')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
