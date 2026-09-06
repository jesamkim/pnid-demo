"""Container entry point for the P&ID demo.

Wraps `backend.api.main:app` and mounts the Vite-built SPA bundle so the
container serves both the React UI and the JSON/WebSocket API on the
same port (8000). The ALB target-group health check hits `/api/health`.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.main import app as api_app

DIST = Path(__file__).resolve().parent / "frontend" / "dist"

app: FastAPI = api_app

# Static assets (Vite bundles).
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(DIST / "index.html"))


@app.get("/{full_path:path}")
def spa_fallback(full_path: str) -> FileResponse:
    """SPA fallback — serves real dist files when present (favicon,
    public/* assets like agentcore-logo.png), otherwise returns the
    SPA shell so client-side routing works.
    """
    if full_path.startswith("api/") or full_path.startswith("assets/"):
        from fastapi import HTTPException
        raise HTTPException(404)
    # Try to serve real files from the dist root (Vite copies
    # frontend/public/* here at build time).
    candidate = DIST / full_path
    if candidate.is_file() and candidate.resolve().is_relative_to(DIST.resolve()):
        return FileResponse(str(candidate))
    return FileResponse(str(DIST / "index.html"))
