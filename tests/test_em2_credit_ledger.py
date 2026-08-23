"""EM-2 regression tests: per-user persisted credit ledger.

Guards the audit gap: pipeline billing used a process-global USER_CREDITS=10
shared by every caller and lost on restart. Billing must now debit the
caller's persisted User.credits balance and write a CreditTransaction audit
row, atomically, per user.
"""
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_em2.db"

import contextlib

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core import auth as auth_mod
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models import CreditTransaction, User

STRONG_KEY = "em2-regression-key-" + "k" * 32


@pytest.fixture
def client_factory(monkeypatch, tmp_path):
    """Yields an async context manager producing {"client", "session"}.

    Sync fixture because pytest-asyncio 0.23.5 async fixtures are
    incompatible with this pytest version (see test_em1_auth_fail_closed.py).
    """
    monkeypatch.setattr(auth_mod, "SECRET_KEY", STRONG_KEY)
    from backend.app.api import pipeline as pipeline_api

    monkeypatch.setattr(pipeline_api, "_PREVIEW_ROOT", tmp_path)

    @contextlib.asynccontextmanager
    async def _make():
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        testing_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Pipeline background tasks use independent sessions, so retain the
        # production behaviour while binding them to this test database.
        monkeypatch.setattr(pipeline_api, "AsyncSessionLocal", testing_session)

        async def override_get_db():
            async with testing_session() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield {"client": ac, "session": testing_session}
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()

    return _make


async def _register_and_login(client: AsyncClient, email: str, username: str) -> dict:
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": "strongpass123"},
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/auth/login",
        data={"username": username, "password": "strongpass123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _set_credits(session_factory, username: str, credits: int) -> None:
    async with session_factory() as session:
        await session.execute(
            update(User).where(User.username == username).values(credits=credits)
        )
        await session.commit()


class TestPerUserCreditLedger:
    def test_global_user_credits_is_gone(self):
        """The process-global counter must not come back."""
        from backend.app.api import pipeline as pipeline_api

        assert not hasattr(pipeline_api, "USER_CREDITS"), (
            "USER_CREDITS global must stay removed; billing is per-user now"
        )

    @pytest.mark.asyncio
    async def test_credits_endpoint_reports_own_persisted_balance(self, client_factory):
        async with client_factory() as env:
            client = env["client"]
            headers = await _register_and_login(client, "bal@example.com", "baluser")
            r = await client.get("/api/pipeline/credits", headers=headers)
            assert r.status_code == 200
            # New users get the model default (1000), not a shared global 10
            assert r.json()["credits"] == 1000

    @pytest.mark.asyncio
    async def test_run_debits_balance_and_writes_audit_row(self, client_factory):
        async with client_factory() as env:
            client, session_factory = env["client"], env["session"]
            headers = await _register_and_login(client, "debit@example.com", "debituser")

            before = (await client.get("/api/pipeline/credits", headers=headers)).json()["credits"]
            r = await client.post(
                "/api/pipeline/run",
                json={"prompt": "build a todo app", "use_mock": True},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            after = (await client.get("/api/pipeline/credits", headers=headers)).json()["credits"]
            assert after == before - 1, "one run must debit exactly one credit"

            async with session_factory() as session:
                rows = (await session.execute(
                    select(CreditTransaction).where(CreditTransaction.transaction_type == "usage")
                )).scalars().all()
            assert len(rows) == 1, "each run must write exactly one usage transaction"
            assert rows[0].amount == -1
            assert "Pipeline run" in (rows[0].description or "")

    @pytest.mark.asyncio
    async def test_zero_balance_gets_402_and_no_job(self, client_factory):
        async with client_factory() as env:
            client, session_factory = env["client"], env["session"]
            headers = await _register_and_login(client, "poor@example.com", "pooruser")
            await _set_credits(session_factory, "pooruser", 0)

            r = await client.post(
                "/api/pipeline/run",
                json={"prompt": "build a todo app", "use_mock": True},
                headers=headers,
            )
            assert r.status_code == 402, r.text

            jobs = (await client.get("/api/pipeline/jobs", headers=headers)).json()
            assert jobs == [], "a refused run must not create a job"

    @pytest.mark.asyncio
    async def test_balances_are_independent_between_users(self, client_factory):
        async with client_factory() as env:
            client = env["client"]
            headers_a = await _register_and_login(client, "inda@example.com", "indauser")
            headers_b = await _register_and_login(client, "indb@example.com", "indbuser")

            bal_b_before = (await client.get("/api/pipeline/credits", headers=headers_b)).json()["credits"]
            r = await client.post(
                "/api/pipeline/run",
                json={"prompt": "build a todo app", "use_mock": True},
                headers=headers_a,
            )
            assert r.status_code == 200, r.text

            bal_a = (await client.get("/api/pipeline/credits", headers=headers_a)).json()["credits"]
            bal_b_after = (await client.get("/api/pipeline/credits", headers=headers_b)).json()["credits"]
            assert bal_a == 999
            assert bal_b_after == bal_b_before, "user B's balance must be untouched by user A's run"

    @pytest.mark.asyncio
    async def test_debit_is_atomic_with_transaction_row(self, client_factory):
        """Balance change and audit row must land in the same commit."""
        async with client_factory() as env:
            client, session_factory = env["client"], env["session"]
            headers = await _register_and_login(client, "atomic@example.com", "atomicuser")

            for i in range(3):
                r = await client.post(
                    "/api/pipeline/run",
                    json={"prompt": f"build app {i}", "use_mock": True},
                    headers=headers,
                )
                assert r.status_code == 200, r.text

            after = (await client.get("/api/pipeline/credits", headers=headers)).json()["credits"]
            assert after == 997

            async with session_factory() as session:
                rows = (await session.execute(
                    select(CreditTransaction).where(CreditTransaction.transaction_type == "usage")
                )).scalars().all()
            assert len(rows) == 3, "three runs must produce three audit rows"
            assert sum(r.amount for r in rows) == -3
