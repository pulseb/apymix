"""Tests d'intégration pour POST /auth/register (inscription publique)."""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from apymix.auth.jwt import init_jwt_secret
from apymix.auth.models import User, UserAccount  # noqa: F401 — enregistre les tables
from apymix.auth.routes import router as auth_router
from apymix.db.session import get_db


@pytest_asyncio.fixture
async def client():
    init_jwt_secret("test-secret-for-register-tests")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()


async def test_register_creates_user_and_returns_tokens(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "newbie@test.dev", "password": "supersecret", "display_name": "Newbie"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_register_then_login(client):
    await client.post(
        "/auth/register",
        json={"email": "dup@test.dev", "password": "supersecret"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "dup@test.dev", "password": "supersecret"},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_register_duplicate_email_rejected(client):
    await client.post("/auth/register", json={"email": "dup@test.dev", "password": "supersecret"})
    resp = await client.post(
        "/auth/register",
        json={"email": "dup@test.dev", "password": "anothersecret"},
    )
    assert resp.status_code == 409


@pytest.mark.parametrize("password", ["", "short"])
async def test_register_weak_password_rejected(client, password):
    resp = await client.post(
        "/auth/register",
        json={"email": "weak@test.dev", "password": password},
    )
    assert resp.status_code == 422
