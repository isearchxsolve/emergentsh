"""Pipeline API — multi-agent generation via configured live inference."""
from __future__ import annotations
import os, uuid, json, asyncio, socket, tempfile, zipfile, hashlib, io, shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, Response
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_

from backend.app.core.auth import get_current_active_user, get_owner_user
from backend.app.core.database import AsyncSessionLocal, get_db
from backend.app.models import CreditTransaction, PipelineEvent, PipelineJob, User, ManagedArtifact

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
_PREVIEW_ROOT = Path(os.getenv("PREVIEW_APPS_DIR", "preview_apps")).resolve()
_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)

class NIMInferenceError(Exception):
    pass

PIPELINE_RUN_COST = 1  # credits debited per pipeline run (EM-2: per-user ledger)
GIB = 1024 ** 3
# Static platform allocation: EmergentSH is capped at 1.5 GiB, leaving the
# remainder of the 10 GiB platform envelope for OiiOii and operating headroom.
MANAGED_ARTIFACT_QUOTA_BYTES = int(os.getenv("EMERGENT_ARTIFACT_QUOTA_BYTES", str(int(1.5 * GIB))))
PIPELINE_RESERVATION_BYTES = int(os.getenv("EMERGENT_PIPELINE_RESERVATION_BYTES", str(25 * 1024 * 1024)))
SINGLE_NODE_MODE = os.getenv("EMERGENT_SINGLE_NODE_MODE", "false").strip().lower() in {"true", "1", "yes", "on"}
WORKER_CONCURRENCY = 1 if SINGLE_NODE_MODE else max(1, int(os.getenv("PIPELINE_WORKER_CONCURRENCY", "2")))


def _deliverable_file(project_dir: Path, path: Path) -> bool:
    """Exclude interpreter/test caches from artifact inventories and exports."""
    relative = path.relative_to(project_dir)
    return path.is_file() and "__pycache__" not in relative.parts and path.suffix not in {".pyc", ".pyo"}

class PipelineRequest(BaseModel):
    prompt: str = Field(..., min_length=3)
    project_name: Optional[str] = None
    use_mock: bool = False

class PipelineStatusResponse(BaseModel):
    job_id: str
    status: str
    phase: str
    artifacts: List[str] = []
    preview_url: Optional[str] = None
    errors: List[str] = []
    message: str = ""
    target: str = "web"


def _status_response(job: PipelineJob) -> PipelineStatusResponse:
    return PipelineStatusResponse(
        job_id=job.job_id,
        status=job.status,
        phase=job.phase,
        artifacts=job.artifacts or [],
        preview_url=job.preview_url,
        errors=job.errors or [],
        message=job.message or "",
        target=job.target or "web",
    )

def _make_mock_client():
    """Smoke/mock NIM client. Branches route on the SYSTEM prompt role (not
    user-message keywords, which every later agent embeds and would misroute).
    Outputs satisfy each agent's validation contract: the designer yields
    valid JSON tokens and the frontend yields code that passes the EM-4
    structural design-token lint."""
    from unittest.mock import AsyncMock, MagicMock
    client = AsyncMock()
    async def fake_stream(messages, model=None, temperature=0.4, max_tokens=4096):
        system = ((messages[0].get("content") or "") if messages else "").lower()
        if "software architect" in system:
            yield "# Project Plan\n\n## Overview\nFull-stack app by NeonBuild.\n\n## Tech Stack\n- Next.js 14\n- FastAPI\n- SQLite\n"
        elif "ui/ux designer" in system:
            yield json.dumps({
                "colors": {"primary": "#76B900", "background": "#0A0A0B", "text": "#F5F5F7"},
                "typography": {"font_family": "Inter, system-ui, sans-serif"},
            })
        elif "frontend engineer" in system:
            request = ((messages[-1].get("content") or "") if messages else "").lower()
            if "flutter presentation" in request:
                yield "import 'package:flutter/material.dart';\nclass GeneratedApp extends StatelessWidget { const GeneratedApp({super.key}); @override Widget build(BuildContext context) => MaterialApp(home: Scaffold(body: Semantics(label: 'Home', child: const Text('Generated app')))); }\nvoid main()=>runApp(const GeneratedApp());\n"
            elif "expo router" in request:
                yield "import React from 'react';\nimport { SafeAreaView, Text, Pressable } from 'react-native';\nexport default function Home(){return <SafeAreaView accessibilityLabel='Home'><Text>Generated app</Text><Pressable accessibilityRole='button'><Text>Start</Text></Pressable></SafeAreaView>}\n"
            else:
              yield (
                "import React from 'react';\n"
                "export default function App() {\n"
                "  return (\n"
                "    <main style={{padding:'2rem',background:'#0A0A0B',color:'#F5F5F7'}} className='transition-colors'>\n"
                "      <h1 style={{color:'#76B900'}} className='backdrop-blur-md'>NeonBuild</h1>\n"
                "      <p className='transition-opacity hover:opacity-80'>Generated app</p>\n"
                "    </main>\n"
                "  );\n"
                "}\n"
              )
        elif "fastapi backend engineer" in system:
            yield "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health():\n    return {'status':'healthy'}\n"
        elif "devops and integration specialist" in system:
            yield "version: '3.8'\nservices:\n  app:\n    build: .\n    ports: ['8080:8080']\n"
        elif "qa engineer" in system:
            yield "def test_health():\n    assert True\n"
        elif "preview engineer" in system:
            yield "<!doctype html><html><head><style>body{background:#07110d;color:#fff;font-family:system-ui;padding:3rem}button{padding:1rem;background:#34d399;border:0;border-radius:1rem}</style></head><body><main><h1>Generated app</h1><p id='state'>Ready</p><button onclick=\"document.getElementById('state').textContent='Working'\">Start</button></main><script>document.documentElement.dataset.ready='true'</script></body></html>"
        elif "devops engineer" in system:
            yield "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
        else:
            yield "# artifact\n"
    client.chat_stream = fake_stream
    client.list_models = AsyncMock(return_value=[MagicMock(id="meta/llama-3.1-8b-instruct")])
    client.health_check = AsyncMock(return_value={"ready": True, "live": True})
    client.close = AsyncMock()
    return client

async def _update_job(job_id: str, **values: Any) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(PipelineJob).where(PipelineJob.job_id == job_id).values(**values))
        await db.commit()


async def _append_event(job_id: str, event: Dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        db.add(PipelineEvent(
            job_id=job_id,
            event_type=event["event"],
            role=event.get("role", "orchestrator"),
            data=event.get("data", {}),
        ))
        await db.commit()


def _archive_project(project_dir: Path) -> bytes:
    """Create a compact in-memory ZIP; generated app source is text-heavy."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in project_dir.rglob("*"):
            if _deliverable_file(project_dir, path):
                archive.write(path, path.relative_to(project_dir).as_posix())
    return output.getvalue()


async def _persist_project_archive(job_id: str, project_dir: Path) -> Optional[ManagedArtifact]:
    payload = _archive_project(project_dir)
    if not payload:
        return None
    sha256 = hashlib.sha256(payload).hexdigest()
    async with AsyncSessionLocal() as db:
        job = await db.get(PipelineJob, job_id)
        if not job:
            return None
        used = (await db.execute(select(ManagedArtifact.byte_size))).scalars().all()
        already = (await db.execute(select(ManagedArtifact).where(ManagedArtifact.sha256 == sha256))).scalar_one_or_none()
        if not already and sum(used) + len(payload) > MANAGED_ARTIFACT_QUOTA_BYTES:
            raise RuntimeError("Managed artifact quota reached; retention cleanup is required before another build can finalize.")
        artifact = already or ManagedArtifact(user_id=job.user_id, pipeline_job_id=job_id, name=f"{job_id}.zip", content_type="application/zip", sha256=sha256, byte_size=len(payload), payload=payload)
        if not already:
            db.add(artifact)
        job.preview_url = f"/api/pipeline/preview/{job_id}/index.html"
        job.project_dir = ""  # source is now retained in the managed archive, not a public disk tree.
        job.reserved_bytes = 0
        await db.commit(); await db.refresh(artifact)
    shutil.rmtree(project_dir, ignore_errors=True)
    return artifact


async def _run_job_stream(job_id: str, prompt: str, project_dir: Path, use_mock: bool) -> None:
    client = None
    artifacts: List[str] = []
    status = "running"
    await _update_job(job_id, status=status, phase="planning")
    try:
        from backend.agent_pipeline import AgentPipeline
        
        inference_strict = os.getenv("INFERENCE_STRICT_MODE", os.getenv("NIM_STRICT_MODE", "false")).lower() in ("true", "1")
        from backend.app.services.nim_client import configured_inference_provider, get_inference_client
        provider = configured_inference_provider()
        provider_configured = bool(os.getenv("OMNIROUTE_API_KEY")) if provider == "omniroute" else bool(os.getenv("NIM_API_KEY") or os.getenv("NVIDIA_API_KEY") or os.getenv("NGC_API_KEY"))
        if inference_strict:
            if not provider_configured:
                raise NIMInferenceError(f"{provider} credential is missing in strict mode.")
            client = get_inference_client()
            await _update_job(job_id, message=f"Running with live {provider}")
        else:
            if use_mock or not provider_configured:
                client = _make_mock_client()
                await _update_job(job_id, message="Running with mock inference")
            else:
                try:
                    client = get_inference_client()
                    await _update_job(job_id, message=f"Running with live {provider}")
                except Exception as e:
                    client = _make_mock_client()
                    await _update_job(job_id, message=f"Inference unavailable ({e}); mock")
                    
        pipeline = AgentPipeline(client)
        
        async for event in pipeline.stream_run(user_prompt=prompt, project_dir=str(project_dir)):
            await _append_event(job_id, event)
            if event["event"] == "agent_start":
                role = event.get("role", "agent")
                await _update_job(job_id, phase=role, message=f"{role.replace('_', ' ').title()} is working")
            elif event["event"] == "agent_retry":
                role = event.get("role", "agent")
                recovered = event.get("data", {}).get("recovered", False)
                message = (
                    f"{role.replace('_', ' ').title()} recovered with validated platform defaults"
                    if recovered else
                    f"{role.replace('_', ' ').title()} is repairing an incomplete result"
                )
                await _update_job(job_id, phase=role, message=message)
            elif event["event"] == "agent_done":
                artifacts = event["data"].get("artifacts", [])
                status = event["data"].get("status", "running")
                await _update_job(job_id, artifacts=artifacts, status=status)
            elif event["event"] == "agent_error":
                # A stage failure is terminal for the sequential pipeline.
                # Persist it immediately so a disconnected SSE client can
                # never observe a false successful completion later.
                status = "failed"
                error = event["data"].get("error", "Agent failed")
                await _update_job(
                    job_id,
                    artifacts=artifacts,
                    status="failed",
                    phase="failed",
                    errors=[error],
                    message=f"Pipeline failed: {error}",
                    preview_url=None,
                )
            elif event["event"] == "pipeline_complete":
                artifacts = event["data"].get("artifacts", artifacts)
                status = event["data"].get("status", status)
                errors = event["data"].get("errors", [])
                if status == "failed":
                    await _update_job(
                        job_id,
                        artifacts=artifacts,
                        status="failed",
                        phase="failed",
                        errors=errors,
                        message="Pipeline failed",
                        preview_url=None,
                    )
                
        for p in project_dir.rglob("*"):
            if _deliverable_file(project_dir, p):
                rel = p.relative_to(project_dir).as_posix()
                if rel not in artifacts:
                    artifacts.append(rel)
                    
        if status == "failed":
            await _update_job(job_id, artifacts=artifacts, phase="failed", status="failed", preview_url=None, message="Pipeline failed")
        else:
            artifact = await _persist_project_archive(job_id, project_dir)
            if artifact is None:
                raise RuntimeError("No project archive was produced")
            await _update_job(job_id, artifacts=artifacts, phase="complete", status="complete", preview_url=f"/api/pipeline/preview/{job_id}/index.html", message=f"Build complete — {len(artifacts)} artifacts; archived {artifact.byte_size} bytes")
    except Exception as e:
        await _append_event(job_id, {"event": "pipeline_error", "role": "orchestrator", "data": {"error": str(e)}})
        await _update_job(job_id, status="failed", phase="failed", errors=[str(e)], message=f"Pipeline failed: {e}", reserved_bytes=0)
    finally:
        if client is not None and hasattr(client, "close"):
            try:
                await client.close()
            except Exception:
                pass


async def _claim_and_run_job(job_id: str) -> bool:
    """Atomically lease a queued/expired job, then execute it once."""
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(PipelineJob).where(
                PipelineJob.job_id == job_id,
                or_(PipelineJob.status == "queued", (PipelineJob.status == "running") & (PipelineJob.lease_expires_at < now)),
            ).values(status="running", worker_id=worker_id, lease_expires_at=now + timedelta(hours=1), attempts=PipelineJob.attempts + 1)
        )
        await db.commit()
        if result.rowcount != 1:
            return False
        job = await db.get(PipelineJob, job_id)
        prompt, project_dir, use_mock = job.prompt, Path(job.project_dir), job.use_mock
    await _run_job_stream(job_id, prompt, project_dir, use_mock)
    return True


async def pipeline_worker_loop() -> None:
    """Replica-safe durable worker; atomic leases prevent duplicate execution."""
    interval = float(os.getenv("PIPELINE_WORKER_POLL_SECONDS", "1"))
    running: set[asyncio.Task] = set()
    while True:
        try:
            now = datetime.utcnow()
            async with AsyncSessionLocal() as db:
                ids = (await db.execute(select(PipelineJob.job_id).where(or_(PipelineJob.status == "queued", (PipelineJob.status == "running") & (PipelineJob.lease_expires_at < now))).order_by(PipelineJob.created_at).limit(WORKER_CONCURRENCY))).scalars().all()
            running = {task for task in running if not task.done()}
            for job_id in ids[:max(0, WORKER_CONCURRENCY - len(running))]:
                task = asyncio.create_task(_claim_and_run_job(job_id))
                running.add(task)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Durable rows remain queued/leased for another polling iteration.
            pass
        await asyncio.sleep(interval)
def _job_owner(job: PipelineJob, user: User) -> None:
    """EM-1: jobs are owned; a non-superuser may only touch their own jobs."""
    owner_id = job.user_id
    if owner_id is not None and owner_id != user.id and not user.is_superuser:
        raise HTTPException(404, "Job not found")


async def _debit_credits(db: AsyncSession, user: User, amount: int, description: str) -> None:
    """EM-2: debit the caller's persisted ledger and record the transaction.

    Raises 402 when the balance cannot cover the cost. The caller's request
    session commits both the balance change and the audit row atomically.
    """
    result = await db.execute(
        update(User)
        .where(User.id == user.id, User.credits >= amount)
        .values(credits=User.credits - amount)
    )
    if result.rowcount != 1:
        balance = user.credits or 0
        raise HTTPException(402, f"Insufficient credits: balance {balance}, cost {amount}.")
    db.add(CreditTransaction(
        user_id=user.id,
        amount=-amount,
        transaction_type="usage",
        description=description,
    ))
    await db.flush()


@router.post("/run", response_model=PipelineStatusResponse)
async def start_pipeline(
    req: PipelineRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    used = (await db.execute(select(ManagedArtifact.byte_size))).scalars().all()
    reserved = (await db.execute(select(PipelineJob.reserved_bytes).where(PipelineJob.status.in_(["queued", "running"])))).scalars().all()
    if sum(used) + sum(reserved) + PIPELINE_RESERVATION_BYTES > MANAGED_ARTIFACT_QUOTA_BYTES:
        raise HTTPException(507, "Managed storage is at its service allocation; retry after retention cleanup.")
    await _debit_credits(db, current_user, PIPELINE_RUN_COST, f"Pipeline run: {req.prompt[:80]}")
    
    job_id = uuid.uuid4().hex[:12]
    project_dir = _PREVIEW_ROOT / job_id
    project_dir.mkdir(parents=True, exist_ok=True)
    from backend.mobile_targets import detect_target
    job = PipelineJob(job_id=job_id, user_id=current_user.id, prompt=req.prompt, project_dir=str(project_dir), use_mock=req.use_mock, target=detect_target(req.prompt), reserved_bytes=PIPELINE_RESERVATION_BYTES)
    db.add(job)
    await db.flush()
    return _status_response(job)

@router.get("/stream/{job_id}")
async def stream_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    last_event_id: int = Header(0, alias="Last-Event-ID"),
):
    job = await db.get(PipelineJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    _job_owner(job, current_user)
        
    async def event_generator():
        cursor = max(0, last_event_id)
        while True:
            async with AsyncSessionLocal() as stream_db:
                events = (await stream_db.execute(select(PipelineEvent).where(PipelineEvent.job_id == job_id, PipelineEvent.id > cursor).order_by(PipelineEvent.id))).scalars().all()
                current_job = await stream_db.get(PipelineJob, job_id)
            for event in events:
                cursor = event.id
                yield f"id: {event.id}\ndata: {json.dumps({'event': event.event_type, 'role': event.role, 'data': event.data})}\n\n"
            if current_job and current_job.status in {"complete", "failed"}:
                break
            await asyncio.sleep(0.25)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/status/{job_id}", response_model=PipelineStatusResponse)
async def pipeline_status(job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    job = await db.get(PipelineJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    _job_owner(job, current_user)
    return _status_response(job)

@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    query = select(PipelineJob)
    if not current_user.is_superuser:
        query = query.where(PipelineJob.user_id == current_user.id)
    jobs = (await db.execute(query.order_by(PipelineJob.created_at.desc()))).scalars().all()
    return [{"job_id": j.job_id, "status": j.status, "phase": j.phase, "preview_url": j.preview_url, "prompt": j.prompt[:120]} for j in jobs]

@router.get("/export/{job_id}")
async def export_job(job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    job = await db.get(PipelineJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    _job_owner(job, current_user)
    artifact = (await db.execute(select(ManagedArtifact).where(ManagedArtifact.pipeline_job_id == job_id))).scalar_one_or_none()
    if artifact:
        return Response(artifact.payload, media_type=artifact.content_type, headers={"Content-Disposition": f'attachment; filename="{artifact.name}"'})
    project_dir = job.project_dir
    if not project_dir or not os.path.exists(project_dir): raise HTTPException(404, "Project archive not found")
        
    project_path = Path(project_dir).resolve()
    archive_path = Path(tempfile.gettempdir()) / f"neonbuild-{job_id}-{uuid.uuid4().hex}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in project_path.rglob("*"):
            if _deliverable_file(project_path, path):
                archive.write(path, path.relative_to(project_path).as_posix())
    return FileResponse(
        archive_path,
        filename=f"{job_id}.zip",
        background=BackgroundTask(archive_path.unlink, missing_ok=True),
    )


@router.get("/preview/{job_id}/{member_path:path}")
async def preview_member(job_id: str, member_path: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    job = await db.get(PipelineJob, job_id)
    if not job: raise HTTPException(404, "Job not found")
    _job_owner(job, current_user)
    normalized = member_path.strip("/") or "index.html"
    if ".." in Path(normalized).parts: raise HTTPException(400, "Invalid preview path")
    artifact = (await db.execute(select(ManagedArtifact).where(ManagedArtifact.pipeline_job_id == job_id))).scalar_one_or_none()
    if not artifact: raise HTTPException(404, "Preview is not archived yet")
    try:
        with zipfile.ZipFile(io.BytesIO(artifact.payload)) as archive:
            data = archive.read(normalized)
    except KeyError: raise HTTPException(404, "Preview file not found")
    content_type = "text/html; charset=utf-8" if normalized.endswith(".html") else "text/plain; charset=utf-8"
    return Response(data, media_type=content_type, headers={"Cache-Control": "private, no-store"})


@router.get("/admin/history")
async def admin_history(db: AsyncSession = Depends(get_db), _: User = Depends(get_owner_user)):
    jobs = (await db.execute(select(PipelineJob).order_by(PipelineJob.created_at.desc()))).scalars().all()
    archives = (await db.execute(select(ManagedArtifact))).scalars().all()
    return {"jobs": [{"job_id": j.job_id, "user_id": j.user_id, "status": j.status, "prompt": j.prompt, "artifacts": j.artifacts, "preview_url": j.preview_url, "created_at": j.created_at} for j in jobs], "managed_storage_bytes": sum(a.byte_size for a in archives), "managed_storage_cap_bytes": MANAGED_ARTIFACT_QUOTA_BYTES}

@router.get("/credits")
async def get_credits(current_user: User = Depends(get_current_active_user)):
    """EM-2: report the caller's persisted balance, not a process global."""
    return {"credits": current_user.credits or 0}
