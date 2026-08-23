"""Emergent.sh Clone API — NVIDIA NIM exclusive."""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.core.database import init_db, close_db
from backend.app.core.auth import validate_secret_key
from backend.app.api import projects, auth, credits, pipeline as pipeline_api

@asynccontextmanager
async def lifespan(app: FastAPI):
    # EM-1 fail-closed boot: refuse to serve on a forgeable JWT signing key.
    validate_secret_key()
    await init_db()
    yield
    await close_db()

app = FastAPI(title="Emergent.sh Clone API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(pipeline_api.router, prefix="/api")
_preview = Path(os.getenv("PREVIEW_APPS_DIR", "preview_apps")).resolve()
_preview.mkdir(parents=True, exist_ok=True)
app.mount("/preview", StaticFiles(directory=str(_preview), html=True), name="preview")

@app.get("/")
async def root():
    return {"name": "Emergent.sh Clone API", "version": "1.0.0", "inference": "NVIDIA NIM exclusive", "docs": "/docs", "pipeline": "/api/pipeline/run"}

@app.get("/health")
async def health():
    return {"status": "healthy", "nim_configured": bool(os.getenv("NIM_API_KEY") or os.getenv("NVIDIA_API_KEY"))}
