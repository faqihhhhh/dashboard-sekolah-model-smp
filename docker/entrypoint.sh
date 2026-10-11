#!/usr/bin/env bash
# Menjalankan migrasi database lalu menjalankan perintah utama (Gunicorn).
set -euo pipefail

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
