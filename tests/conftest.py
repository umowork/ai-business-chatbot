"""
Pytest configuration and shared fixtures.
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

# Ensure the project root is on sys.path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..")
)

from typing import TYPE_CHECKING

from config import Config
from models.base import Database

if TYPE_CHECKING:
    from models.base import Dialog, Lead, User


# ── Test Configuration ──────────────────────────────────────────────────


@pytest.fixture(scope="session")
def test_config() -> Config:
    """Create a test configuration with mock mode enabled."""
    os.environ.setdefault("MOCK_MODE", "true")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("BOT_TOKEN", "test:token")
    os.environ.setdefault("ADMIN_IDS", "12345,67890")
    os.environ.setdefault("CRM_PROVIDER", "mock")
    os.environ.setdefault("LLM_PROVIDER", "openai")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
    os.environ.setdefault("DOCUMENTS_DIR", "/tmp/test_documents")
    return Config.from_env()


# ── In-Memory Database ──────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def test_db(test_config: Config) -> AsyncGenerator[Database, None]:
    """Create a fresh in-memory database for each test."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    yield db
    await db.engine.dispose()


# ── LLM Mock Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_llm_response():
    """Return a mock LLM response."""
    from services.llm import LLMResponse

    return LLMResponse(
        content="Это тестовый ответ от AI-ассистента.",
        model="test-model",
        provider="test",
        latency_ms=100,
        cost_usd=0.0,
        input_tokens=10,
        output_tokens=20,
    )


# ── Test Data Factories ─────────────────────────────────────────────────


async def create_test_user(db: Database, telegram_id: int = 99999) -> User:
    """Create a test user."""

    # Use db method
    return await db.get_or_create_user(
        telegram_id=telegram_id,
        username="test_user",
        full_name="Test User",
    )


async def create_test_lead(db: Database, user_id: int, **overrides) -> Lead:
    """Create a test lead."""

    data = {
        "name": "Test Lead",
        "phone": "+7 999 123-45-67",
        "service": "Консультация",
        "budget": "50000",
        "status": "qualified",
        "category": "sales",
    }
    data.update(overrides)
    return await db.create_lead(user_id=user_id, **data)


async def create_test_dialog(
    db: Database, user_id: int, role: str = "user", content: str = "Тестовое сообщение"
) -> Dialog:
    """Create a test dialog entry."""

    return await db.add_dialog(user_id=user_id, role=role, content=content)
