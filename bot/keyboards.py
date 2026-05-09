"""
Telegram bot: inline keyboards.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def start_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for /start command."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Услуги", callback_data="services")
    builder.button(text="📞 Контакты", callback_data="contacts")
    builder.button(text="🆘 Помощь", callback_data="help")
    builder.adjust(2)
    return builder.as_markup()


def lead_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    """Admin keyboard for managing a lead."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять",
        callback_data=f"lead_accept_{lead_id}",
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"lead_reject_{lead_id}",
    )
    builder.button(
        text="📞 Позвонить",
        callback_data=f"lead_call_{lead_id}",
    )
    builder.adjust(2)
    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    """Admin panel keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📋 Лиды", callback_data="admin_leads")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="🔄 Обновить RAG", callback_data="admin_reindex_rag")
    builder.adjust(2)
    return builder.as_markup()
