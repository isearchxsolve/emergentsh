"""NeonBuild application-generation API."""
from __future__ import annotations
import os, asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.core.database import init_db, close_db
from backend.app.core.auth import validate_secret_key, get_password_hash
from backend.app.models import User
from backend.app.core.database import AsyncSessionLocal
from sqlalchemy import select
from backend.app.api import projects, auth, credits, pipeline as pipeline_api

@asynccontextmanager
async def lifespan(app: FastAPI):
    # EM-1 fail-closed boot: refuse to serve on a forgeable JWT signing key.
    validate_secret_key()
    await init_db()
    # Closed SaaS bootstrap. The owner is the only account allowed to receive
    # administrator privileges; customers are created through /api/auth/admin.
    owner_email = os.getenv("OWNER_EMAIL", "").strip().lower()
    owner_password = os.getenv("OWNER_INITIAL_PASSWORD", "")
    if owner_email and owner_password:
        async with AsyncSessionLocal() as db:
            owner = (await db.execute(select(User).where(User.email == owner_email))).scalar_one_or_none()
            if owner is None:
                db.add(User(email=owner_email, username=os.getenv("OWNER_USERNAME", "owner"), full_name=os.getenv("OWNER_NAME", "Service Owner"), hashed_password=get_password_hash(owner_password), is_superuser=True))
            else:
                owner.is_superuser = True
            await db.commit()
    worker = asyncio.create_task(pipeline_api.pipeline_worker_loop())
    yield
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    await close_db()

app = FastAPI(title="NeonBuild API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(pipeline_api.router, prefix="/api")
# Preview content is served only through the owner-scoped pipeline endpoint.

@app.get("/")
async def root():
    return {"name": "NeonBuild API", "version": "1.0.0", "inference": os.getenv("INFERENCE_PROVIDER", "auto"), "docs": "/docs", "pipeline": "/api/pipeline/run"}

@app.get("/health")
async def health():
    provider = os.getenv("INFERENCE_PROVIDER", "auto").lower()
    omni = bool(os.getenv("OMNIROUTE_API_KEY"))
    nim = bool(os.getenv("NIM_API_KEY") or os.getenv("NVIDIA_API_KEY") or os.getenv("NGC_API_KEY"))
    selected = ("omniroute" if omni else "nim") if provider == "auto" else provider
    return {"status": "healthy", "inference_provider": selected, "inference_configured": omni if selected == "omniroute" else nim}
