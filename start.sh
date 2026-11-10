#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
(cd frontend && npm ci && npm run build)
.venv/bin/python -m playwright install chromium firefox webkit
cd backend
exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
