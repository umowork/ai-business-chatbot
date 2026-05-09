"""
Telegram bot: message and callback handlers.
Integrates with all real services: LLM, CRM, RAG, Classifier.
"""

import logging
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)

from bot.keyboards import admin_keyboard, lead_keyboard, start_keyboard
from config import Config
from crm import CRMFactory
from models.base import Database
from services.classifier import QueryClassifier
from services.llm import LLMFactory
from services.rag import RAGEngine

logger = logging.getLogger(__name__)


# ── FSM States ──────────────────────────────────────────────────────────


class DialogStates(StatesGroup):
    chatting = State()
    awaiting_phone = State()
    awaiting_feedback = State()


# ── Bot Application ─────────────────────────────────────────────────────


class BotApp:
    """Telegram bot application with all handlers."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db

        # Services (lazy init)
        self._llm = None
        self._crm = None
        self._classifier = None
        self._rag = None

        # Bot setup
        self.storage = MemoryStorage()
        self.bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher(storage=self.storage)

        # Register handlers
        self._register_handlers()

    @property
    def llm(self):
        if self._llm is None:
            self._llm = LLMFactory.get_provider(self.config)
        return self._llm

    @property
    def crm(self):
        if self._crm is None:
            self._crm = CRMFactory.get_crm(self.config)
        return self._crm

    @property
    def classifier(self):
        if self._classifier is None:
            self._classifier = QueryClassifier(self.config)
        return self._classifier

    @property
    def rag(self):
        if self._rag is None:
            self._rag = RAGEngine(self.config)
        return self._rag

    # ── System Prompt ────────────────────────────────────────────────

    def _build_system_prompt(self, user_info: dict[str, Any] | None = None) -> str:
        """Build the system prompt for the AI assistant."""
        prompt = (
            f"Ты AI-ассистент компании «{self.config.business_name}». "
            f"Тон общения: {self.config.business_tonality}.\n\n"
            f"Твои задачи:\n"
            f"1. Отвечать на вопросы клиентов вежливо и профессионально.\n"
            f"2. Если клиент хочет купить услугу — собери контактные данные (имя, телефон).\n"
            f"3. Не выдумывай информацию — если не знаешь, предложи передать вопрос менеджеру.\n"
            f"4. Отвечай на русском языке.\n\n"
            f"Важно: Если клиент явно просит передать вопрос человеку или сообщает "
            f"о сложной проблеме — предложи передать запрос менеджеру."
        )
        if user_info:
            prompt += (
                f"\n\nИнформация о клиенте:\n"
                f"Имя: {user_info.get('full_name', 'Неизвестно')}\n"
            )
            if user_info.get("phone"):
                prompt += f"Телефон: {user_info['phone']}\n"
        return prompt

    # ── Handler Registration ─────────────────────────────────────────

    def _register_handlers(self):
        """Register all message and callback handlers."""
        # Message handlers
        self.dp.message(CommandStart())(self.cmd_start)
        self.dp.message(Command("help"))(self.cmd_help)
        self.dp.message(Command("stats"))(self.cmd_stats)
        self.dp.message(Command("leads"))(self.cmd_leads)
        self.dp.message(Command("admin"))(self.cmd_admin)
        self.dp.message(Command("clear"))(self.cmd_clear)
        self.dp.message(DialogStates.chatting)(self.process_message)
        self.dp.message(DialogStates.awaiting_phone)(self.process_phone)
        self.dp.message(DialogStates.awaiting_feedback)(self.process_feedback)

        # Callback handlers
        self.dp.callback_query(F.data == "services")(self.cb_services)
        self.dp.callback_query(F.data == "contacts")(self.cb_contacts)
        self.dp.callback_query(F.data == "help")(self.cb_show_help)
        self.dp.callback_query(F.data == "admin_stats")(self.cb_admin_stats)
        self.dp.callback_query(F.data == "admin_leads")(self.cb_admin_leads)
        self.dp.callback_query(F.data == "admin_users")(self.cb_admin_users)
        self.dp.callback_query(F.data == "admin_reindex_rag")(self.cb_admin_reindex_rag)
        self.dp.callback_query(F.data.startswith("lead_accept_"))(self.cb_lead_action)
        self.dp.callback_query(F.data.startswith("lead_reject_"))(self.cb_lead_action)
        self.dp.callback_query(F.data.startswith("lead_call_"))(self.cb_lead_action)
        self.dp.callback_query(F.data == "talk_to_human")(self.cb_talk_to_human)

    # ── Utility ──────────────────────────────────────────────────────

    def _is_admin(self, user_id: int) -> bool:
        return user_id in self.config.admin_ids

    async def _get_or_create_user(self, message: Message):
        return await self.db.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name or "Пользователь",
        )

    def _create_context_message(
        self, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """Format dialog history for LLM context."""
        return [
            {"role": "assistant" if d.role == "assistant" else "user", "content": d.content}
            for d in history
        ][-10:]  # Last 10 messages for context

    async def _notify_admins(self, text: str, keyboard: InlineKeyboardMarkup | None = None):
        """Send notification to all admin users."""
        for admin_id in self.config.admin_ids:
            try:
                await self.bot.send_message(
                    admin_id, text, reply_markup=keyboard
                )
            except Exception as e:
                logger.warning("Failed to notify admin %s: %s", admin_id, e)

    # ── Message Handlers ─────────────────────────────────────────────

    async def cmd_start(self, message: Message, state: FSMContext):
        """Handle /start command."""
        await state.clear()
        user = await self._get_or_create_user(message)

        greeting = (
            f"👋 <b>Здравствуйте, {user.full_name}!</b>\n\n"
            f"Я AI-ассистент компании «{self.config.business_name}». "
            f"Я могу:\n"
            f"• Ответить на вопросы о наших услугах 📋\n"
            f"• Помочь с выбором и записью ✅\n"
            f"• Передать ваш вопрос менеджеру 👨‍💼\n\n"
            f"Чем я могу вам помочь?"
        )

        await state.set_state(DialogStates.chatting)
        await message.answer(greeting, reply_markup=start_keyboard())

    async def cmd_help(self, message: Message):
        """Handle /help command."""
        help_text = (
            "ℹ️ <b>Помощь</b>\n\n"
            "Команды:\n"
            "/start — начать диалог\n"
            "/help — эта справка\n"
            "/clear — очистить историю диалога\n"
            "/admin — панель администратора (только для админов)\n"
            "/stats — статистика (только для админов)\n"
            "/leads — список лидов (только для админов)\n\n"
            "Просто напишите ваш вопрос, и я постараюсь помочь! 😊"
        )
        await message.answer(help_text)

    async def cmd_clear(self, message: Message, state: FSMContext):
        """Clear dialog history."""
        await state.clear()
        await state.set_state(DialogStates.chatting)
        await message.answer("🧹 История диалога очищена. Чем могу помочь?")

    async def cmd_stats(self, message: Message):
        """Show statistics (admin only)."""
        if not self._is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для этой команды.")
            return

        try:
            stats = await self.db.get_stats()
            text = (
                "📊 <b>Статистика</b>\n\n"
                f"👤 Пользователей: <b>{stats['users']}</b>\n"
                f"📋 Лидов: <b>{stats['leads']}</b>\n"
                f"💬 Сообщений в диалогах: <b>{stats['dialog_messages']}</b>\n"
            )
            await message.answer(text)
        except Exception as e:
            logger.error("Stats error: %s", e)
            await message.answer("❌ Ошибка получения статистики.")

    async def cmd_leads(self, message: Message):
        """Show recent leads (admin only)."""
        if not self._is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для этой команды.")
            return

        try:
            leads = await self.db.get_all_leads(limit=10)
            if not leads:
                await message.answer("📋 Лидов пока нет.")
                return

            text_lines = ["📋 <b>Последние лиды</b>\n"]
            for lead in leads:
                text_lines.append(
                    f"#{lead.id} | {lead.name or '—'} | {lead.phone or '—'} | "
                    f"{lead.service or '—'} | {lead.status}"
                )
            await message.answer("\n".join(text_lines))
        except Exception as e:
            logger.error("Leads error: %s", e)
            await message.answer("❌ Ошибка получения лидов.")

    async def cmd_admin(self, message: Message):
        """Show admin panel."""
        if not self._is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для этой команды.")
            return
        await message.answer(
            "🔧 <b>Панель администратора</b>",
            reply_markup=admin_keyboard(),
        )

    async def process_message(self, message: Message, state: FSMContext):
        """Process a chat message from the user."""
        user = await self._get_or_create_user(message)
        user_text = message.text or ""

        if not user_text.strip():
            await message.answer("Пожалуйста, напишите ваш вопрос.")
            return

        # Save user message
        await self.db.add_dialog(user.id, "user", user_text)

        # Check if user wants to talk to a human
        if self._wants_human(user_text):
            await self._transfer_to_human(message, user)
            return

        # Classify the query
        classification = await self.classifier.classify(user_text)
        logger.info(
            "Query classified as %s (confidence: %.2f)",
            classification.category.value,
            classification.confidence,
        )

        # Get dialog history for context
        history = await self.db.get_dialog_history_ordered(user.id, limit=10)
        llm_history = self._create_context_message(history[:-1])  # Exclude current message

        # Build system prompt
        user_info = {
            "full_name": user.full_name,
            "phone": user.phone,
        }
        system_prompt = self._build_system_prompt(user_info)

        # Try RAG-enhanced response
        try:
            response_text = await self.rag.answer_with_context(
                query=user_text,
                llm_provider=self.llm,
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.warning("RAG error, falling back to direct LLM: %s", e)
            response = await self.llm.chat_with_history(
                system_prompt=system_prompt,
                user_message=user_text,
                history=llm_history,
            )
            response_text = response.content

        # Save assistant response
        await self.db.add_dialog(user.id, "assistant", response_text)

        # Handle lead qualification from classification
        if classification.is_sales():
            extracted = classification.extracted_data
            if extracted.get("phone") or self._has_phone(user_text):
                phone = extracted.get("phone") or self._extract_phone(user_text)

                # Create lead
                lead = await self.db.create_lead(
                    user_id=user.id,
                    name=extracted.get("service") or user.full_name,
                    phone=phone,
                    service=extracted.get("service"),
                    budget=extracted.get("budget"),
                    urgency=extracted.get("urgency"),
                    category="sales",
                    status="qualified",
                )

                # Create CRM deal
                crm_result = await self.crm.create_deal(
                    name=user.full_name,
                    phone=phone,
                    service=extracted.get("service"),
                    budget=extracted.get("budget"),
                )
                if crm_result.success:
                    await self.db.update_lead_crm(lead.id, crm_result.deal_id)
                    response_text += (
                        "\n\n✅ Ваш запрос передан менеджеру! "
                        "Мы свяжемся с вами в ближайшее время."
                    )

                    # Notify admins
                    admin_msg = (
                        f"🔔 <b>Новый лид!</b>\n\n"
                        f"👤 {user.full_name}\n"
                        f"📞 {phone}\n"
                        f"📋 {extracted.get('service', '—')}\n"
                        f"💰 {extracted.get('budget', '—')}\n"
                        f"🆔 CRM: {crm_result.deal_id}"
                    )
                    await self._notify_admins(
                        admin_msg,
                        keyboard=lead_keyboard(lead.id),
                    )

        await message.answer(response_text, reply_markup=start_keyboard())

    async def process_phone(self, message: Message, state: FSMContext):
        """Process phone number input."""
        phone = message.text.strip()
        # Basic phone validation
        import re

        phone_pattern = re.compile(r"^[\d\s\+\-\(\)]{7,20}$")
        if not phone_pattern.match(phone):
            await message.answer(
                "Пожалуйста, укажите корректный номер телефона "
                "(например: +7 999 123-45-67)"
            )
            return

        user = await self._get_or_create_user(message)
        await self.db.update_user_phone(user.id, phone)

        data = await state.get_data()
        service = data.get("pending_service", "Консультация")

        # Create lead
        lead = await self.db.create_lead(
            user_id=user.id,
            name=user.full_name,
            phone=phone,
            service=service,
            status="qualified",
            category="sales",
        )

        # CRM
        crm_result = await self.crm.create_deal(
            name=user.full_name,
            phone=phone,
            service=service,
        )
        if crm_result.success:
            await self.db.update_lead_crm(lead.id, crm_result.deal_id)

        await state.set_state(DialogStates.chatting)
        await message.answer(
            "✅ Спасибо! Ваш запрос принят. Менеджер свяжется с вами в ближайшее время.\n\n"
            "Если у вас есть ещё вопросы, я готов помочь! 😊"
        )

        # Notify admins
        admin_msg = (
            f"🔔 <b>Новый лид (через запрос телефона)</b>\n\n"
            f"👤 {user.full_name}\n"
            f"📞 {phone}\n"
            f"📋 {service}\n"
        )
        if crm_result.success:
            admin_msg += f"🆔 CRM: {crm_result.deal_id}"
        await self._notify_admins(admin_msg, keyboard=lead_keyboard(lead.id))

    async def process_feedback(self, message: Message, state: FSMContext):
        """Process user feedback."""
        feedback_text = message.text or ""
        user = await self._get_or_create_user(message)

        await self.db.add_dialog(user.id, "user", f"[ОТЗЫВ] {feedback_text}")
        await state.set_state(DialogStates.chatting)

        await message.answer(
            "💬 Спасибо за ваш отзыв! Мы обязательно учтём его.\n"
            "Чем я могу помочь вам сейчас?"
        )

        # Notify admins about feedback
        admin_msg = (
            f"💬 <b>Отзыв от пользователя</b>\n\n"
            f"👤 {user.full_name} (@{user.username or '—'})\n"
            f"📝 {feedback_text[:500]}"
        )
        await self._notify_admins(admin_msg)

    # ── Callback Handlers ────────────────────────────────────────────

    async def cb_services(self, callback: CallbackQuery):
        """Show services information."""
        text = (
            "📋 <b>Наши услуги</b>\n\n"
            "Я могу помочь с:\n"
            "• Консультацией по услугам\n"
            "• Записью на приём\n"
            "• Подбором подходящего решения\n"
            "• Расчётом стоимости\n\n"
            "Напишите, что вас интересует, и я подробно расскажу! 😊"
        )
        await callback.message.answer(text)
        await callback.answer()

    async def cb_contacts(self, callback: CallbackQuery):
        """Show contact information."""
        text = (
            "📞 <b>Контакты</b>\n\n"
            f"Компания: {self.config.business_name}\n"
            "Телефон: уточните у менеджера\n"
            "Email: через менеджера\n\n"
            "Напишите ваш вопрос, и я помогу или передам его менеджеру! 😊"
        )
        await callback.message.answer(text)
        await callback.answer()

    async def cb_show_help(self, callback: CallbackQuery):
        """Show help information."""
        await self.cmd_help(callback.message)  # type: ignore
        await callback.answer()

    async def cb_admin_stats(self, callback: CallbackQuery):
        """Admin stats callback."""
        await self.cmd_stats(callback.message)  # type: ignore
        await callback.answer()

    async def cb_admin_leads(self, callback: CallbackQuery):
        """Admin leads callback."""
        await self.cmd_leads(callback.message)  # type: ignore
        await callback.answer()

    async def cb_admin_users(self, callback: CallbackQuery):
        """Admin users callback."""
        try:
            users = await self.db.get_all_users()
            text = "👥 <b>Пользователи</b>\n\n"
            for u in users[:10]:
                text += f"• {u.full_name} (@{u.username or '—'}) — {u.phone or 'нет телефона'}\n"
            await callback.message.answer(text)
        except Exception as e:
            await callback.message.answer(f"❌ Ошибка: {e}")
        await callback.answer()

    async def cb_admin_reindex_rag(self, callback: CallbackQuery):
        """Re-index RAG documents."""
        await callback.message.answer("🔄 Переиндексация документов RAG...")
        try:
            await self.rag.initialize(force_reload=True)
            await callback.message.answer("✅ Переиндексация завершена!")
        except Exception as e:
            await callback.message.answer(f"❌ Ошибка переиндексации: {e}")
        await callback.answer()

    async def cb_lead_action(self, callback: CallbackQuery):
        """Handle lead action from admin keyboard."""
        data = callback.data
        parts = data.split("_")
        if len(parts) < 3:
            await callback.answer("Неверный формат данных")
            return

        action = parts[1]  # accept, reject, call
        lead_id = int(parts[2])

        try:
            lead = await self.db.get_lead_by_id(lead_id)
            if not lead:
                await callback.message.answer(f"❌ Лид #{lead_id} не найден.")
                await callback.answer()
                return

            if action == "accept":
                await callback.message.edit_text(
                    f"{callback.message.html_text}\n\n✅ Лид #{lead_id} принят в работу."
                )
            elif action == "reject":
                await callback.message.edit_text(
                    f"{callback.message.html_text}\n\n❌ Лид #{lead_id} отклонён."
                )
            elif action == "call":
                await callback.message.answer(
                    f"📞 Номер для звонка: {lead.phone or 'не указан'}"
                )
        except Exception as e:
            logger.error("Lead action error: %s", e)
            await callback.message.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    async def cb_talk_to_human(self, callback: CallbackQuery):
        """Handle request to talk to a human."""
        user = callback.from_user
        await callback.message.answer(
            "Соединяю с менеджером... Пожалуйста, ожидайте! ⏳"
        )

        admin_msg = (
            f"🆘 <b>Запрос на перевод человеку</b>\n\n"
            f"👤 {user.full_name} (@{user.username or '—'})\n"
            f"🆔 TG ID: {user.id}\n\n"
            f"Перейдите в диалог с пользователем, чтобы ответить."
        )
        await self._notify_admins(admin_msg)
        await callback.answer()

    # ── Helper Methods ───────────────────────────────────────────────

    def _wants_human(self, text: str) -> bool:
        """Check if user explicitly wants to talk to a human."""
        keywords = [
            "человек", "оператор", "менеджер", "живой", "живого",
            "соедините", "переключите", "переведите", "свяжите с",
            "реальный", "не бот", "позовите", "администратор",
            "human", "operator", "agent",
        ]
        text_lower = text.lower().strip()
        return any(kw in text_lower for kw in keywords)

    def _has_phone(self, text: str) -> bool:
        """Check if text contains a phone number."""
        import re

        phone_pattern = re.compile(r"(?:\+?7|8)\s?\(?\d{3}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}")
        return bool(phone_pattern.search(text))

    def _extract_phone(self, text: str) -> str | None:
        """Extract phone number from text."""
        import re

        phone_pattern = re.compile(r"(?:\+?7|8)\s?\(?\d{3}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}")
        match = phone_pattern.search(text)
        return match.group(0) if match else None
