"""API tests for AI Business Chatbot — all endpoints, auth, validation."""

import os

import pytest

os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("CRM_PROVIDER", "mock")

pytestmark = pytest.mark.asyncio

HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture(autouse=True)
def _setup(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    os.environ["MOCK_MODE"] = "true"
    os.environ["API_KEY"] = "test-key"


@pytest.fixture
async def client(_setup):
    from httpx import ASGITransport, AsyncClient

    from config import Config
    from models.base import Database

    config = Config()
    db = Database(config.database_url)
    await db.create_tables()

    from api.web import WebAPI

    api = WebAPI(config, db)
    transport = ASGITransport(app=api.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await db.engine.dispose()


# ── Health ─────────────────────────────────────────────────────────


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert "services" in data


# ── Auth errors ────────────────────────────────────────────────────


async def test_chat_no_auth(client):
    r = await client.post(
        "/chat",
        json={"message": "Hello", "user_id": "u1"},
    )
    assert r.status_code == 401


async def test_chat_wrong_key(client):
    r = await client.post(
        "/chat",
        json={"message": "Hello", "user_id": "u1"},
        headers={"X-API-Key": "wrong"},
    )
    assert r.status_code == 401


async def test_stats_no_auth(client):
    r = await client.get("/stats")
    assert r.status_code == 401


async def test_leads_no_auth(client):
    r = await client.get("/leads")
    assert r.status_code == 401


async def test_reindex_no_auth(client):
    r = await client.post("/reindex")
    assert r.status_code == 401


# ── Chat ───────────────────────────────────────────────────────────


async def test_chat_success(client):
    r = await client.post(
        "/chat",
        json={"message": "Привет, какие услуги?", "user_id": "user1"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    assert len(data["reply"]) > 0


async def test_chat_with_history(client):
    r = await client.post(
        "/chat",
        json={
            "message": "Расскажите подробнее",
            "user_id": "user1",
            "history": [
                {"role": "user", "content": "Какие услуги?"},
                {"role": "assistant", "content": "Мы предоставляем ИИ-решения."},
            ],
        },
        headers=HEADERS,
    )
    assert r.status_code == 200
    assert "reply" in r.json()


async def test_chat_empty_message(client):
    r = await client.post(
        "/chat",
        json={"message": "", "user_id": "user1"},
        headers=HEADERS,
    )
    assert r.status_code == 422


# ── Stats ──────────────────────────────────────────────────────────


async def test_stats(client):
    r = await client.get("/stats", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "users" in data
    assert "leads" in data
    assert "dialog_messages" in data


# ── Leads ──────────────────────────────────────────────────────────


async def test_leads_empty(client):
    r = await client.get("/leads", headers=HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_leads_with_limit(client):
    r = await client.get("/leads?limit=5", headers=HEADERS)
    assert r.status_code == 200


async def test_leads_with_status_filter(client):
    r = await client.get("/leads?status=new", headers=HEADERS)
    assert r.status_code == 200


# ── Reindex ────────────────────────────────────────────────────────


async def test_reindex(client):
    r = await client.post("/reindex", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
