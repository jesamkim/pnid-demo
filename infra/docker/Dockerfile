# syntax=docker/dockerfile:1.7
#
# P&ID demo container — Vite frontend bundled into the same FastAPI process
# served by uvicorn. Two stages:
#   1) node:22-slim   -> npm ci + npm run build (frontend/dist)
#   2) python:3.11-slim -> pip install backend deps + copy dist
# CMD launches uvicorn on $PORT (default 8000) so the ALB target group
# can health-check /api/health.

# -------- Stage 1: build the React app -----------------------------------
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_BASE=""
RUN npm run build

# -------- Stage 2: backend runtime ---------------------------------------
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

# System deps for pypdfium2 + cairo (cairosvg).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libcairo2 \
      libpango-1.0-0 \
      libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps. requirements.txt is the demo's frozen list; if a
# prod requirements.lock is added later, switch this line.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt fastapi==0.128.0 uvicorn==0.40.0

# Backend source + agent entrypoint + samples + ground truth + cached extractions.
COPY backend/ ./backend/
COPY agent_main.py ./agent_main.py
COPY config/ ./config/
COPY data/samples/ ./data/samples/
COPY data/samples_real/ ./data/samples_real/
COPY data/ground_truth/ ./data/ground_truth/
COPY .claude/artifacts/extraction/ ./.claude/artifacts/extraction/

# Frontend bundle from stage 1.
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Static-mounted SPA + entrypoint stub.
COPY infra/docker/serve.py ./serve.py

# Drop privileges.
RUN useradd --create-home --uid 1001 app && chown -R app:app /app
USER app

EXPOSE 8000

# uvicorn with the SPA-aware FastAPI app. Single worker so the
# in-process AppState/SearchIndex (used for live-extraction indexing
# via /api/index_run) is shared across all requests — multi-worker
# would route /api/index_run and /api/query to different processes
# and leave the live extraction unsearchable.
CMD ["python", "-m", "uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
