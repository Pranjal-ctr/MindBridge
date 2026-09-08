# Kio Backend — FastAPI + Alembic
#
# Two stages: the builder compiles wheels (needs a toolchain), the runtime gets
# only the resulting virtualenv. Build tools never reach the shipped image.
#
# Build from the repo root so the backend/ path prefix below resolves:
#   docker build -f backend/Dockerfile -t kio-api ./backend

# ===================================================================
# Stage 1 — builder
# ===================================================================
FROM python:3.11.9-slim-bookworm AS builder

# Most of our tree ships manylinux wheels, but asyncpg/bcrypt fall back to a
# source build on some platforms. Provide a toolchain here only.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

# Self-contained venv so the runtime stage can copy one directory.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==24.2 \
    && pip install --no-cache-dir -r requirements.txt


# ===================================================================
# Stage 2 — runtime
# ===================================================================
FROM python:3.11.9-slim-bookworm AS runtime

# libpq is not needed (asyncpg speaks the wire protocol directly). curl is for
# the container healthcheck below.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Run unprivileged. Created before COPY so the chown lands in one layer.
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 kio
COPY --chown=kio:kio . /app

RUN chmod +x /app/docker-entrypoint.sh
USER kio

EXPOSE 8000

# Liveness only. Readiness (which includes the database) is /health/db and is
# left to the orchestrator, so a database blip doesn't kill the container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["serve"]
