"""Pipeline API — multi-agent generation. NVIDIA NIM exclusive (mock for smoke)."""
from __future__ import annotations
import os, uuid, json, asyncio, shutil, socket
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_

from backend.app.core.auth import get_current_active_user
from backend.app.core.database import AsyncSessionLocal, get_db
from backend.app.models import CreditTransaction, PipelineEvent, PipelineJob, User

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
_PREVIEW_ROOT = Path(os.getenv("PREVIEW_APPS_DIR", "preview_apps")).resolve()
_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)

class NIMInferenceError(Exception):
    pass

PIPELINE_RUN_COST = 1  # credits debited per pipeline run (EM-2: per-user ledger)

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
            yield "# Project Plan\n\n## Overview\nFull-stack app by EmergentSH.\n\n## Tech Stack\n- Next.js 14\n- FastAPI\n- SQLite\n"
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
                "      <h1 style={{color:'#76B900'}} className='backdrop-blur-md'>EmergentSH</h1>\n"
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
            if event["event"] == "agent_done":
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
            if p.is_file():
                rel = str(p.relative_to(project_dir))
                if rel not in artifacts:
                    artifacts.append(rel)
                    
        if status == "failed":
            await _update_job(job_id, artifacts=artifacts, phase="failed", status="failed", preview_url=None, message="Pipeline failed")
        else:
            await _update_job(job_id, artifacts=artifacts, phase="complete", status="complete", preview_url=f"/preview/{job_id}/", message=f"Build complete — {len(artifacts)} artifacts")
    except Exception as e:
        await _append_event(job_id, {"event": "pipeline_error", "role": "orchestrator", "data": {"error": str(e)}})
        await _update_job(job_id, status="failed", phase="failed", errors=[str(e)], message=f"Pipeline failed: {e}")
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
    while True:
        try:
            now = datetime.utcnow()
            async with AsyncSessionLocal() as db:
                ids = (await db.execute(select(PipelineJob.job_id).where(or_(PipelineJob.status == "queued", (PipelineJob.status == "running") & (PipelineJob.lease_expires_at < now))).order_by(PipelineJob.created_at).limit(4))).scalars().all()
            for job_id in ids:
                await _claim_and_run_job(job_id)
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
    background: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await _debit_credits(db, current_user, PIPELINE_RUN_COST, f"Pipeline run: {req.prompt[:80]}")
    
    job_id = uuid.uuid4().hex[:12]
    project_dir = _PREVIEW_ROOT / job_id
    project_dir.mkdir(parents=True, exist_ok=True)
    from backend.mobile_targets import detect_target
    job = PipelineJob(job_id=job_id, user_id=current_user.id, prompt=req.prompt, project_dir=str(project_dir), use_mock=req.use_mock, target=detect_target(req.prompt))
    db.add(job)
    await db.flush()
    background.add_task(_claim_and_run_job, job_id)
    return _status_response(job)

@router.get("/stream/{job_id}")
async def stream_job(job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    job = await db.get(PipelineJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    _job_owner(job, current_user)
        
    async def event_generator():
        last_event_id = 0
        while True:
            async with AsyncSessionLocal() as stream_db:
                events = (await stream_db.execute(select(PipelineEvent).where(PipelineEvent.job_id == job_id, PipelineEvent.id > last_event_id).order_by(PipelineEvent.id))).scalars().all()
                current_job = await stream_db.get(PipelineJob, job_id)
            for event in events:
                last_event_id = event.id
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
    project_dir = job.project_dir
    if not project_dir or not os.path.exists(project_dir):
        raise HTTPException(404, "Project directory not found")
        
    archive_path = shutil.make_archive(f"/tmp/{job_id}", "zip", project_dir)
    return FileResponse(archive_path, filename=f"{job_id}.zip")

@router.get("/credits")
async def get_credits(current_user: User = Depends(get_current_active_user)):
    """EM-2: report the caller's persisted balance, not a process global."""
    return {"credits": current_user.credits or 0}
