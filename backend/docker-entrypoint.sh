#!/usr/bin/env sh
set -eu

if [ "${ORIGINLABS_AUTO_MIGRATE:-false}" = "true" ]; then
    alembic upgrade head
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

PORT_TO_BIND="${PORT:-${SERVER_PORT:-8000}}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT_TO_BIND}"
