#!/usr/bin/env bash
set -e

cd /app
export PYTHONPATH=/app

# Always use Poetry's in-project venv
VENV_PY="/app/.venv/bin/python"
VENV_UVICORN="/app/.venv/bin/uvicorn"

echo "entrypoint DATABASE_URL=${DATABASE_URL}"

# Wait for Postgres to accept connections
$VENV_PY - <<'PY'
import os, time, sys
import psycopg2

url = os.getenv("DATABASE_URL")
print("python DATABASE_URL =", url)
deadline = time.time() + 60
while True:
    try:
        psycopg2.connect(url).close()
        break
    except Exception as e:
        if time.time() > deadline:
            raise
        time.sleep(1)
PY

# Recreate schema + load dummy data on every startup
$VENV_PY application/db/declarative_mapping.py
$VENV_PY application/db/load_db_with_dummy_data.py

# Start the API
exec /app/.venv/bin/uvicorn application.main:app --host 0.0.0.0 --port 8000
