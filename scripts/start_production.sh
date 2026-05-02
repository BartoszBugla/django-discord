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

echo "==> purge_read_notifications (stare przeczytane in-app)"
python manage.py purge_read_notifications

PORT="${PORT:-8000}"
BIND="${BIND:-0.0.0.0:${PORT}}"

# Render (i inne reverse proxy): poprawne IP klienta / nagłówki X-Forwarded-* dla Uvicorn workera.
FORWARDED="${FORWARDED_ALLOW_IPS:-*}"

if [[ "${USE_DAPHNE:-0}" == "1" ]]; then
  echo "==> daphne (ASGI) on ${BIND} — osobna implementacja WS (Twisted), często najmniej problemów na PaaS"
  exec daphne -b "${BIND%:*}" -p "${BIND##*:}" mysite.asgi:application
fi

echo "==> gunicorn + UvicornWorker (ASGI) on ${BIND} — wymaga pakietu websockets (patrz requirements.txt)"
exec python -m gunicorn mysite.asgi:application -k uvicorn.workers.UvicornWorker --bind "${BIND}" --timeout 0 --graceful-timeout 30 --forwarded-allow-ips "${FORWARDED}"
