# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; npm ci
COPY frontend/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.56.0-noble
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY experiments /app/experiments
COPY --from=frontend /ui/dist /app/frontend/dist
RUN groupadd -g 10001 aurora && useradd -u 10001 -g aurora -m aurora && mkdir -p /app/data && chown -R aurora:aurora /app/data
USER aurora
ENV DATA_DIR=/app/data PYTHONUNBUFFERED=1
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
