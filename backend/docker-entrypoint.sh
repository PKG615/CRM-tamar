#!/bin/sh
set -e

# Only the API container migrates (RUN_MIGRATIONS=1), and the worker waits for the API
# to be healthy in docker-compose, so two containers never race to migrate.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
fi

exec "$@"
