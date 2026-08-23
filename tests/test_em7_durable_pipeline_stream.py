"""Regression coverage for durable, multi-client pipeline event streaming."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api import pipeline
from backend.app.models import Base, PipelineEvent, PipelineJob, User


@pytest.mark.asyncio
async def test_pipeline_events_are_durable_and_replayable_by_each_consumer(monkeypatch):
    """Two independent DB sessions must see the same ordered event history.

    This guards against a return to a process-local, destructive queue where
    one SSE connection consumes events that another browser or API replica
    should also receive.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(pipeline, "AsyncSessionLocal", sessions)

    async with sessions() as db:
        db.add(User(id="stream-user", email="stream@example.com", username="stream", hashed_password="hash"))
        db.add(PipelineJob(job_id="stream-job", user_id="stream-user", prompt="build app", project_dir="/tmp/stream-job"))
        await db.commit()

    await pipeline._append_event("stream-job", {"event": "agent_start", "role": "planner", "data": {}})
    await pipeline._append_event("stream-job", {"event": "agent_done", "role": "planner", "data": {"artifacts": ["PLAN.md"]}})

    async def read_from_new_consumer():
        async with sessions() as db:
            return (await db.execute(
                select(PipelineEvent).where(PipelineEvent.job_id == "stream-job").order_by(PipelineEvent.id)
            )).scalars().all()

    consumer_a, consumer_b = await read_from_new_consumer(), await read_from_new_consumer()
    assert [event.event_type for event in consumer_a] == ["agent_start", "agent_done"]
    assert [event.id for event in consumer_a] == [event.id for event in consumer_b]
    await engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_job_lease_allows_only_one_replica(monkeypatch, tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(pipeline, "AsyncSessionLocal", sessions)
    calls = []

    async def fake_run(job_id, prompt, project_dir, use_mock):
        calls.append((job_id, prompt, use_mock))

    monkeypatch.setattr(pipeline, "_run_job_stream", fake_run)
    async with sessions() as db:
        db.add(User(id="worker-user", email="worker@example.com", username="worker", hashed_password="hash"))
        db.add(PipelineJob(job_id="leased-job", user_id="worker-user", prompt="mobile app", project_dir=str(tmp_path), use_mock=True))
        await db.commit()

    first = await pipeline._claim_and_run_job("leased-job")
    second = await pipeline._claim_and_run_job("leased-job")
    assert first is True
    assert second is False
    assert calls == [("leased-job", "mobile app", True)]
    async with sessions() as db:
        job = await db.get(PipelineJob, "leased-job")
        assert job.attempts == 1
        assert job.worker_id
    await engine.dispose()
