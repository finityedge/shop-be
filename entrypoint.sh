#!/usr/bin/env bash
set -euo pipefail

DB_WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-60}"

# Prefer explicit DB_* vars; otherwise pg_isready reads DATABASE_URL directly.
if [ -n "${DB_HOST:-}" ]; then
  PG_TARGET=(-h "${DB_HOST}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}")
else
  PG_TARGET=(-d "${DATABASE_URL:?DATABASE_URL or DB_HOST must be set}")
fi

echo "==> Waiting for Postgres (timeout ${DB_WAIT_TIMEOUT}s)..."
waited=0
until pg_isready "${PG_TARGET[@]}" >/dev/null 2>&1; do
  if [ "${waited}" -ge "${DB_WAIT_TIMEOUT}" ]; then
    echo "!! Postgres not reachable after ${DB_WAIT_TIMEOUT}s; aborting." >&2
    exit 1
  fi
  sleep 1
  waited=$((waited + 1))
done
echo "==> Postgres is ready (waited ${waited}s)."

echo "==> Applying migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting: $*"
exec "$@"
