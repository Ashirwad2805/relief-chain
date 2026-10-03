# ==============================================================================
# ReliefChain - single image: React/Vite frontend + FastAPI backend
# The backend serves the built frontend from /app/dist on port 8000.
# ==============================================================================

# ---------- Stage 1: build the frontend ----------
FROM node:20-alpine AS frontend-build
WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig*.json postcss.config.js tailwind.config.js ./
COPY public ./public
COPY src ./src

# URL the browser uses to reach the API (also used for the WebSocket).
# Must be reachable from the user's browser, not from inside the container.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------- Stage 2: backend runtime ----------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    BACKEND_PORT=8000 \
    FRONTEND_URL=http://localhost:8000 \
    DATABASE_URL=sqlite:////app/db/reliefchain.db \
    SIMULATION_SEED=42

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/data ./data
COPY backend/tests ./tests
COPY backend/conftest.py backend/verify_proof.py ./

# Built frontend (main.py looks for /app/dist/index.html)
COPY --from=frontend-build /build/dist ./dist

# Non-root user; /app/db holds the SQLite file (mount a volume here to persist)
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/db \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD sh -c "curl -f http://localhost:${PORT:-8000}/api/health || exit 1"

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
