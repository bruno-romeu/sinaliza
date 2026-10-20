#!/bin/bash
# spec-6-1: migrate-then-serve. Migration failure stops the container
# (non-zero exit) rather than starting an application against a stale schema.
set -e

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
