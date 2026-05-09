"""
Tests for Telegram bot handlers.
Uses a mock bot instance to test handler logic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Patch aiogram Bot before importing handlers
with patch("aiogram.Bot") as MockBot:
    MockBot.return_value = AsyncMock()
    from bot.handlers import BotApp, DialogStates

from config import Config
from models.base import Database


@pytest.fixture
def mock_bot_app(test_config: Config, test_db: Database):
    """Create a BotApp with mocked aiogram bot."""
    with patch("bot.handlers.Bot") as MockBot:
        MockBot.return_value = AsyncMock()
        app = BotApp(test_config, test_db)

    # Mock the bot and dispatcher
    app.bot = AsyncMock()
    app.dp = MagicMock()
    app.storage = MagicMock()

    return app


class TestBotAppHelpers:
    """Test BotApp internal helper methods."""

    def test_is_admin(self, test_config):
        with patch("bot.handlers.Bot") as MockBot:
            MockBot.return_value = AsyncMock()
            app = BotApp(test_config, MagicMock())
        assert app._is_admin(12345) is True
        assert app._is_admin(67890) is True
        assert app._is_admin(99999) is False

    def test_wants_human(self, test_config):
        with patch("bot.handlers.Bot") as MockBot:
            MockBot.return_value = AsyncMock()
            app = BotApp(test_config, MagicMock())
        assert app._wants_human("Соедините с человеком") is True
        assert app._wants_human("Позовите оператора") is True
        assert app._wants_human("Привет, как дела?") is False
        assert app._wants_human("") is False
        assert app._wants_human("хочу поговорить с менеджером") is True

    def test_has_phone(self, test_config):
        with patch("bot.handlers.Bot") as MockBot:
            MockBot.return_value = AsyncMock()
            app = BotApp(test_config, MagicMock())
        assert app._has_phone("+7 999 123-45-67") is True
        assert app._has_phone("Мой номер 8(999)1234567") is True
        assert app._has_phone("Привет, как дела?") is False
        assert app._has_phone("") is False

    def test_extract_phone(self, test_config):
        app = BotApp(test_config, MagicMock())
        phone = app._extract_phone("Мой номер +7 999 123-45-67, позвоните")
        assert phone == "+7 999 123-45-67"

        phone2 = app._extract_phone("Привет, меня зовут Иван")
        assert phone2 is None

    def test_build_system_prompt(self, test_config):
        app = BotApp(test_config, MagicMock())
        prompt = app._build_system_prompt()
        assert test_config.business_name in prompt
        assert "AI-ассистент" in prompt
        assert "русском" in prompt

    def test_build_system_prompt_with_user_info(self, test_config):
        app = BotApp(test_config, MagicMock())
        prompt = app._build_system_prompt(
            user_info={"full_name": "Иван", "phone": "+7 999 123-45-67"}
        )
        assert "Иван" in prompt
        assert "+7 999 123-45-67" in prompt

    def test_create_context_message(self, test_config, test_db):
        """Test formatting of dialog history for LLM context."""

        app = BotApp(test_config, test_db)

        # Create mock dialog objects
        class MockDialog:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        history = [
            MockDialog("user", "Привет"),
            MockDialog("assistant", "Здравствуйте!"),
            MockDialog("user", "Есть вопрос"),
        ]

        context = app._create_context_message(history)
        assert len(context) == 3
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Привет"
        assert context[1]["role"] == "assistant"
        assert context[1]["content"] == "Здравствуйте!"


class TestBotStates:
    """Test FSM state definitions."""

    def test_dialog_states_exist(self):
        assert DialogStates.chatting is not None
        assert DialogStates.awaiting_phone is not None
        assert DialogStates.awaiting_feedback is not None
        assert DialogStates.chatting.state == "DialogStates:chatting"
