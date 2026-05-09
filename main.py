"""
AI Business Chatbot — Main Entry Point.

Provides both Telegram bot (aiogram) and Web API (FastAPI) interfaces.
Usage:
    python main.py                    # Telegram bot
    python main.py --api              # Web API
    python main.py --all              # Both (requires uvicorn)
"""
from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

from logging_config import configure_logging, get_logger

if TYPE_CHECKING:
    from config import Config
    from models.base import Database


# Lazy imports — heavy libraries imported only when needed


def load_config() -> Config:
    """Load configuration from environment."""
    from config import Config

    return Config.from_env()


async def init_database(config) -> Database:
    """Initialize database and create tables."""
    from models.base import Database

    db = Database(config.database_url)
    await db.create_tables()
    get_logger(__name__).info("Database initialized")
    return db


async def run_telegram_bot(config, db) -> None:
    """Run the Telegram bot."""
    from bot.handlers import BotApp

    bot_app = BotApp(config, db)
    bot = bot_app.bot
    dp = bot_app.dp

    logger = get_logger(__name__)
    logger.info("Telegram bot starting polling...")

    # Initialize RAG in background
    try:
        await bot_app.rag.initialize()
    except Exception as e:
        logger.warning("RAG init skipped (non-fatal): %s", e)

    await dp.start_polling(bot)


def run_web_api(config, db) -> None:
    """Run the FastAPI web API via uvicorn."""
    from api.web import WebAPI

    web_api = WebAPI(config, db)
    app = web_api.app

    logger = get_logger(__name__)
    logger.info("Web API starting on 0.0.0.0:%d", 8000)

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


async def run_all(config, db) -> None:
    """Run both Telegram bot and Web API concurrently."""
    import threading

    import uvicorn

    from api.web import WebAPI

    # Start FastAPI in a thread
    web_api = WebAPI(config, db)
    app = web_api.app

    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

    api_thread = threading.Thread(target=run_fastapi, daemon=True)
    api_thread.start()

    logger = get_logger(__name__)
    logger.info("Both interfaces started (telegram+web) on port %d", 8000)

    # Run Telegram bot in main thread
    await run_telegram_bot(config, db)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="AI Business Chatbot — Telegram bot + Web API"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run only the FastAPI web API",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run both Telegram bot and Web API",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Load env from .env file if present
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    # Configuration and logging
    config = load_config()
    configure_logging(debug=args.debug or config.debug)
    logger = get_logger(__name__)

    logger.info(
        "Starting AI Business Chatbot",
        version="1.0.0",
        mock_mode=config.mock_mode,
        llm_provider=config.llm_provider,
        crm_provider=config.crm_provider,
    )

    # Initialize database
    db = asyncio.run(init_database(config))

    if args.api:
        run_web_api(config, db)
    elif args.all:
        asyncio.run(run_all(config, db))
    else:
        asyncio.run(run_telegram_bot(config, db))


if __name__ == "__main__":
    main()
