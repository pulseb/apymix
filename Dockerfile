# ============================================================
# Stage 1 — Build deps + bytecode
# ============================================================
FROM python:3.14-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

# Manifest + source
COPY pyproject.toml ./
COPY apymix/ apymix/
COPY alembic.ini ./
COPY alembic/ alembic/

# Install (editable excluded — on package directement)
RUN uv sync --no-cache --no-dev

# Précompilation du bytecode (accélère les imports au démarrage)
RUN python -m compileall -q -j 0 /app/.venv/lib

# ============================================================
# Stage 2 — Image runtime (léger)
# ============================================================
FROM python:3.14-slim

# --- Outils système (curl pour healthcheck) ---
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# --- Utilisateur non-root (uid 1000, requis par la plupart des hébergeurs) ---
RUN useradd -m -u 1000 user
USER user

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# --- Dépendances précompilées depuis le builder ---
COPY --chown=user --from=builder /app/.venv /app/.venv

# --- Code source + alembic ---
COPY --chown=user apymix/ apymix/
COPY --chown=user alembic.ini ./alembic.ini
COPY --chown=user alembic/ alembic/
COPY --chown=user pyproject.toml ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD curl -fsS http://localhost:8000/-/health || exit 1

CMD ["python", "-m", "uvicorn", "apymix.app:app", "--host", "0.0.0.0", "--port", "8000"]
