"""EM-1 regression tests: SECRET_KEY fail-closed boot + pipeline route auth.

Guards two audit gaps:
  1. The app must refuse to boot when SECRET_KEY is missing, a known-insecure
     default, or shorter than 32 chars (forgeable JWT signatures).
  2. Every /api/pipeline/* route must require a valid Bearer token and jobs
     must be owned: user B cannot read/export/stream user A's jobs.
"""
import os

# The app DB engine is built at import time from DATABASE_URL. The ambient
# shell may carry a stale postgres:// URL from other projects, so pin a
# local sqlite URL BEFORE importing any backend.app module.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_em1.db"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core import auth as auth_mod
from backend.app.core.auth import validate_secret_key
from backend.app.core.database import Base, get_db
from backend.app import main as main_mod
from backend.app.main import app

STRONG_KEY = "em1-regression-key-" + "k" * 32  # >= 32 chars, not in INSECURE set


# ---------------------------------------------------------------------------
# validate_secret_key unit tests
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """passlib was incompatible with bcrypt>=4.1 (register was broken at
    runtime); auth now uses bcrypt directly. Guard the round trip."""

    def test_hash_and_verify_round_trip(self):
        from backend.app.core.auth import get_password_hash, verify_password

        h = get_password_hash("strongpass123")
        assert h.startswith("$2")
        assert verify_password("strongpass123", h)
        assert not verify_password("wrongpass", h)

    def test_long_password_truncated_not_crashed(self):
        from backend.app.core.auth import get_password_hash, verify_password

        long_pw = "p" * 200  # > bcrypt's 72-byte cap
        h = get_password_hash(long_pw)
        assert verify_password(long_pw, h)

    def test_verify_garbage_hash_returns_false(self):
        from backend.app.core.auth import verify_password

        assert verify_password("anything", "not-a-bcrypt-hash") is False


class TestValidateSecretKey:
    def test_missing_key_refused(self):
        with pytest.raises(RuntimeError, match="not set"):
            validate_secret_key(secret="")

    def test_known_insecure_default_refused(self):
        with pytest.raises(RuntimeError, match="known-insecure"):
            validate_secret_key(secret="your-secret-key-change-in-production")

    def test_every_known_default_is_refused(self):
        for bad in auth_mod.INSECURE_SECRET_KEYS:
            with pytest.raises(RuntimeError):
                validate_secret_key(secret=bad)

    def test_short_key_refused(self):
        with pytest.raises(RuntimeError, match="too short"):
            validate_secret_key(secret="a" * (auth_mod.MIN_SECRET_KEY_LENGTH - 1))

    def test_strong_key_accepted(self):
        assert validate_secret_key(secret=STRONG_KEY) == STRONG_KEY

    def test_module_level_default_is_refused(self, monkeypatch):
        """The shipped default SECRET_KEY must never pass validation."""
        monkeypatch.setattr(auth_mod, "SECRET_KEY", "your-secret-key-change-in-production")
        with pytest.raises(RuntimeError):
            validate_secret_key()


# ---------------------------------------------------------------------------
# Boot-time (lifespan) enforcement
# ---------------------------------------------------------------------------

class TestBootFailClosed:
    @pytest.mark.asyncio
    async def test_boot_refuses_insecure_secret(self, monkeypatch):
        monkeypatch.setattr(auth_mod, "SECRET_KEY", "your-secret-key-change-in-production")
        with pytest.raises(RuntimeError, match="known-insecure"):
            async with app.router.lifespan_context(app):
                pass  # pragma: no cover — lifespan must raise before yield

    @pytest.mark.asyncio
    async def test_boot_refuses_short_secret(self, monkeypatch):
        monkeypatch.setattr(auth_mod, "SECRET_KEY", "short-key")
        with pytest.raises(RuntimeError, match="too short"):
            async with app.router.lifespan_context(app):
                pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_boot_accepts_strong_secret(self, monkeypatch):
        monkeypatch.setattr(auth_mod, "SECRET_KEY", STRONG_KEY)

        async def _noop_db():
            return None

        monkeypatch.setattr(main_mod, "init_db", _noop_db)
        monkeypatch.setattr(main_mod, "close_db", _noop_db)
        async with app.router.lifespan_context(app):
            pass  # must not raise


# ---------------------------------------------------------------------------
# Route auth + job ownership
# ---------------------------------------------------------------------------

import contextlib


@pytest.fixture
def client_factory(monkeypatch, tmp_path):
    """Sync fixture: pytest-asyncio 0.23.5 async fixtures are incompatible
    with this pytest version, so tests do `async with client_factory() as c:`.
    """
    monkeypatch.setattr(auth_mod, "SECRET_KEY", STRONG_KEY)
    # Keep background-job artifacts out of the repo preview_apps/ dir
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

        # Background pipeline workers open their own application session.
        # Point that factory at this isolated test database as well.
        monkeypatch.setattr(pipeline_api, "AsyncSessionLocal", testing_session)

        async def override_get_db():
            # Mirror the real get_db: commit after the request so rows
            # written by one route are visible to the next.
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
            yield ac
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


class TestPipelineRouteAuth:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/pipeline/run"),
            ("GET", "/api/pipeline/jobs"),
            ("GET", "/api/pipeline/credits"),
            ("GET", "/api/pipeline/status/doesnotexist"),
            ("GET", "/api/pipeline/stream/doesnotexist"),
            ("GET", "/api/pipeline/export/doesnotexist"),
        ],
    )
    async def test_every_pipeline_route_rejects_anonymous(self, client_factory, method, path):
        async with client_factory() as client:
            kwargs = {"json": {"prompt": "build a todo app"}} if method == "POST" else {}
            r = await client.request(method, path, **kwargs)
            assert r.status_code == 401, f"{path} must require auth, got {r.status_code}"

    @pytest.mark.asyncio
    async def test_run_with_valid_token_accepted_and_owned(self, client_factory):
        async with client_factory() as client:
            headers = await _register_and_login(client, "owner@example.com", "owneruser")
            r = await client.post(
                "/api/pipeline/run",
                json={"prompt": "build a todo app", "use_mock": True},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            job_id = r.json()["job_id"]
            assert job_id

            # The job is durable state, rather than a process-local dict.
            r = await client.get(f"/api/pipeline/status/{job_id}", headers=headers)
            assert r.status_code == 200, r.text

    @pytest.mark.asyncio
    async def test_job_isolation_between_users(self, client_factory):
        async with client_factory() as client:
            headers_a = await _register_and_login(client, "alice@example.com", "aliceuser")
            headers_b = await _register_and_login(client, "bob@example.com", "bobuser")

            r = await client.post(
                "/api/pipeline/run",
                json={"prompt": "build a todo app", "use_mock": True},
                headers=headers_a,
            )
            assert r.status_code == 200, r.text
            job_id = r.json()["job_id"]

            # Owner can read their job
            r = await client.get(f"/api/pipeline/status/{job_id}", headers=headers_a)
            assert r.status_code == 200

            # Another user must not (404, not 403, to avoid existence leaks)
            r = await client.get(f"/api/pipeline/status/{job_id}", headers=headers_b)
            assert r.status_code == 404
            r = await client.get(f"/api/pipeline/export/{job_id}", headers=headers_b)
            assert r.status_code == 404

            # Job list is scoped to the owner
            r = await client.get("/api/pipeline/jobs", headers=headers_b)
            assert r.status_code == 200
            assert all(j["job_id"] != job_id for j in r.json())

    @pytest.mark.asyncio
    async def test_credits_with_valid_token(self, client_factory):
        async with client_factory() as client:
            headers = await _register_and_login(client, "credits@example.com", "creditsuser")
            r = await client.get("/api/pipeline/credits", headers=headers)
            assert r.status_code == 200
            assert "credits" in r.json()

    @pytest.mark.asyncio
    async def test_forged_token_rejected(self, client_factory):
        """A token signed with the OLD insecure default key must be rejected."""
        from jose import jwt

        forged = jwt.encode(
            {"sub": "attacker"},
            "your-secret-key-change-in-production",
            algorithm="HS256",
        )
        async with client_factory() as client:
            r = await client.get(
                "/api/pipeline/jobs",
                headers={"Authorization": f"Bearer {forged}"},
            )
            assert r.status_code == 401
