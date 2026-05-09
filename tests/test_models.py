"""
Tests for database models and CRUD operations.
"""

import pytest


class TestDatabaseOperations:
    """Test database CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user(self, test_db):
        """Test creating a new user."""
        user = await test_db.get_or_create_user(
            telegram_id=11111,
            username="john",
            full_name="John Doe",
        )
        assert user.id is not None
        assert user.telegram_id == 11111
        assert user.username == "john"
        assert user.full_name == "John Doe"

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, test_db):
        """Test get_or_create returns existing user."""
        user1 = await test_db.get_or_create_user(
            telegram_id=11111, username="john", full_name="John Doe"
        )
        user2 = await test_db.get_or_create_user(
            telegram_id=11111, username="john_updated", full_name="John Doe"
        )
        assert user1.id == user2.id
        # Username should be updated
        assert user2.username == "john_updated"

    @pytest.mark.asyncio
    async def test_create_lead(self, test_db):
        """Test creating a lead."""
        user = await test_db.get_or_create_user(
            telegram_id=22222, username="jane", full_name="Jane Doe"
        )
        lead = await test_db.create_lead(
            user_id=user.id,
            name="Jane Doe",
            phone="+7 999 888-77-66",
            service="Консультация",
            budget="30000",
            status="new",
            category="sales",
        )
        assert lead.id is not None
        assert lead.name == "Jane Doe"
        assert lead.phone == "+7 999 888-77-66"
        assert lead.service == "Консультация"
        assert lead.status == "new"
        assert lead.category == "sales"

    @pytest.mark.asyncio
    async def test_add_dialog(self, test_db):
        """Test adding dialog entries."""
        user = await test_db.get_or_create_user(
            telegram_id=33333, username="dialogue", full_name="Dialogue Test"
        )
        d1 = await test_db.add_dialog(user_id=user.id, role="user", content="Привет")
        d2 = await test_db.add_dialog(
            user_id=user.id, role="assistant", content="Здравствуйте!"
        )
        assert d1.id is not None
        assert d2.id is not None
        assert d1.role == "user"
        assert d2.role == "assistant"

    @pytest.mark.asyncio
    async def test_get_dialog_history_ordered(self, test_db):
        """Test retrieving dialog history in chronological order."""
        user = await test_db.get_or_create_user(
            telegram_id=44444, username="history", full_name="History Test"
        )
        # Add messages
        await test_db.add_dialog(user_id=user.id, role="user", content="Первое")
        await test_db.add_dialog(user_id=user.id, role="assistant", content="Ответ 1")
        await test_db.add_dialog(user_id=user.id, role="user", content="Второе")

        history = await test_db.get_dialog_history_ordered(user.id, limit=10)
        assert len(history) == 3
        assert history[0].content == "Первое"
        assert history[1].content == "Ответ 1"
        assert history[2].content == "Второе"

    @pytest.mark.asyncio
    async def test_get_dialog_history_empty(self, test_db):
        """Test retrieving dialog history for user with no messages."""
        user = await test_db.get_or_create_user(
            telegram_id=55555, username="empty", full_name="Empty History"
        )
        history = await test_db.get_dialog_history_ordered(user.id)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_update_lead_crm(self, test_db):
        """Test updating a lead with CRM deal ID."""
        user = await test_db.get_or_create_user(
            telegram_id=66666, username="leadcrm", full_name="Lead CRM Test"
        )
        lead = await test_db.create_lead(
            user_id=user.id, name="CRM Test", phone="+7 111 222-33-44"
        )
        assert lead.status == "new"

        await test_db.update_lead_crm(lead.id, "CRM_DEAL_12345")
        updated = await test_db.get_lead_by_id(lead.id)
        assert updated is not None
        assert updated.crm_deal_id == "CRM_DEAL_12345"
        assert updated.status == "crm_created"

    @pytest.mark.asyncio
    async def test_clear_dialog_history(self, test_db):
        """Test clearing dialog history."""
        user = await test_db.get_or_create_user(
            telegram_id=77777, username="clear", full_name="Clear Test"
        )
        await test_db.add_dialog(user_id=user.id, role="user", content="Msg 1")
        await test_db.add_dialog(user_id=user.id, role="assistant", content="Response 1")

        count = await test_db.clear_dialog_history(user.id)
        assert count == 2

        history = await test_db.get_dialog_history_ordered(user.id)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, test_db):
        """Test getting basic statistics."""
        user = await test_db.get_or_create_user(
            telegram_id=88888, username="stats", full_name="Stats Test"
        )
        await test_db.add_dialog(user_id=user.id, role="user", content="Hi")
        await test_db.create_lead(user_id=user.id, name="Stats Lead")

        stats = await test_db.get_stats()
        assert stats["users"] >= 1
        assert stats["leads"] >= 1
        assert stats["dialog_messages"] >= 1

    @pytest.mark.asyncio
    async def test_get_leads_by_status(self, test_db):
        """Test filtering leads by status."""
        user = await test_db.get_or_create_user(
            telegram_id=99990, username="filter", full_name="Filter Test"
        )
        await test_db.create_lead(
            user_id=user.id, name="New Lead", status="new"
        )
        await test_db.create_lead(
            user_id=user.id, name="Qualified Lead", status="qualified"
        )

        new_leads = await test_db.get_leads_by_status("new")
        qualified = await test_db.get_leads_by_status("qualified")

        assert len(new_leads) >= 1
        assert len(qualified) >= 1
        assert new_leads[0].status == "new"

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, test_db):
        """Test getting user by ID."""
        user = await test_db.get_or_create_user(
            telegram_id=99991, username="getuser", full_name="Get User"
        )
        found = await test_db.get_user_by_id(user.id)
        assert found is not None
        assert found.telegram_id == 99991

        not_found = await test_db.get_user_by_id(99999)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_update_user_phone(self, test_db):
        """Test updating user phone number."""
        user = await test_db.get_or_create_user(
            telegram_id=99992, username="phoneuser", full_name="Phone User"
        )
        assert user.phone is None

        updated = await test_db.update_user_phone(user.id, "+7 999 123-45-67")
        assert updated is not None
        assert updated.phone == "+7 999 123-45-67"

        # Verify persistence
        fetched = await test_db.get_user_by_id(user.id)
        assert fetched is not None
        assert fetched.phone == "+7 999 123-45-67"
