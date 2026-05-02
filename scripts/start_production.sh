#!/usr/bin/env bash
# Uruchomienie produkcyjne: migracje, statyczne pliki, opcjonalny admin z ENV, potem Gunicorn+Uvicorn (ASGI / WebSockety).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-mysite.settings}"

echo "==> migrate"
python manage.py migrate --noinput

echo "==> collectstatic"
python manage.py collectstatic --noinput

echo "==> ensure_admin_user (pomija, jeśli brak ADMIN_PASSWORD)"
python manage.py ensure_admin_user

PORT="${PORT:-8000}"
BIND="${BIND:-0.0.0.0:${PORT}}"

echo "==> gunicorn (ASGI) on ${BIND}"
exec python -m gunicorn mysite.asgi:application -k uvicorn.workers.UvicornWorker --bind "${BIND}" --timeout 0 --graceful-timeout 30
