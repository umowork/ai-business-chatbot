"""
Configuration for AI Business Chatbot.
Uses pydantic-settings for type-safe env management.
"""

import os
from dataclasses import dataclass, field


def _parse_int_list(raw: str) -> list[int]:
    """Parse comma-separated integers from env string."""
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    # --- Telegram ---
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    admin_ids: list[int] = field(
        default_factory=lambda: _parse_int_list(os.getenv("ADMIN_IDS", ""))
    )

    # --- CRM ---
    crm_provider: str = field(default_factory=lambda: os.getenv("CRM_PROVIDER", "mock"))
    bitrix_webhook: str = field(default_factory=lambda: os.getenv("BITRIX_WEBHOOK", ""))
    amo_token: str = field(default_factory=lambda: os.getenv("AMO_TOKEN", ""))
    amo_base_url: str = field(default_factory=lambda: os.getenv("AMO_BASE_URL", "https://your-subdomain.amocrm.ru"))

    # --- Google Calendar ---
    google_calendar_credentials: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")
    )

    # --- Database ---
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db"))

    # --- Redis / Celery ---
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # --- LLM ---
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", ""))
    gigachat_credentials: str = field(default_factory=lambda: os.getenv("GIGACHAT_CREDENTIALS", ""))
    gigachat_model: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_MODEL", "GigaChat-20-1.5-h2o")
    )
    yandex_api_key: str = field(default_factory=lambda: os.getenv("YANDEX_API_KEY", ""))
    yandex_folder_id: str = field(default_factory=lambda: os.getenv("YANDEX_FOLDER_ID", ""))
    yandex_model: str = field(default_factory=lambda: os.getenv("YANDEX_MODEL", "yandexgpt-lite"))

    # --- RAG ---
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "openai")
    )
    documents_dir: str = field(default_factory=lambda: os.getenv("DOCUMENTS_DIR", "./documents"))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "500")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "50")))
    top_k: int = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "3")))

    # --- Mode ---
    mock_mode: bool = field(
        default_factory=lambda: os.getenv("MOCK_MODE", "false").lower() in ("1", "true", "yes")
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
    )

    # --- Business config ---
    business_name: str = field(default_factory=lambda: os.getenv("BUSINESS_NAME", "Компания"))
    business_tonality: str = field(
        default_factory=lambda: os.getenv("BUSINESS_TONALITY", "Дружелюбный, профессиональный")
    )

    # --- Web API ---
    api_key: str = field(default_factory=lambda: os.getenv("API_KEY", ""))

    @classmethod
    def from_env(cls) -> "Config":
        return cls()
