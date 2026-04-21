# Runtime image for ETR Study App API (Docker).
# Build: docker build -t study-app-api:local .
# See: docs/developer/0009-docker-image-and-container.html
#
# Process entrypoint is scripts/container_entrypoint.sh (same sequence as `make container-start` on host).

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# Dependencies: same pinned lockfile as local dev (`make install` / `pip install -r requirements.txt`).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini alembic.ini
COPY alembic/ alembic/
COPY app/ app/

COPY scripts/container_entrypoint.sh scripts/container_entrypoint.sh
RUN chmod +x scripts/container_entrypoint.sh && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/scripts/container_entrypoint.sh"]
