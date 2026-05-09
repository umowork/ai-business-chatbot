"""
Tests for CRM package — providers, factory, mock mode.
"""

import pytest

from crm import (
    AmoCRMProvider,
    Bitrix24Provider,
    CRMFactory,
    CRMResult,
    MockCRMProvider,
)


class TestCRMResult:
    """Test CRMResult data class."""

    def test_crm_result_success(self):
        result = CRMResult(
            success=True,
            deal_id="DEAL_123",
            contact_id="CONTACT_456",
            message="Сделка создана",
        )
        assert result.success is True
        assert result.deal_id == "DEAL_123"
        assert result.contact_id == "CONTACT_456"

    def test_crm_result_failure(self):
        result = CRMResult(success=False, message="Ошибка API")
        assert result.success is False
        assert result.deal_id is None

    def test_crm_result_to_dict(self):
        result = CRMResult(success=True, deal_id="D1")
        d = result.to_dict()
        assert d["success"] is True
        assert d["deal_id"] == "D1"


class TestMockCRMProvider:
    """Test MockCRMProvider for development/testing."""

    @pytest.mark.asyncio
    async def test_create_deal(self, test_config):
        crm = MockCRMProvider(test_config)
        result = await crm.create_deal(
            name="Test Client",
            phone="+7 999 123-45-67",
            service="Консультация",
            budget="50000",
        )
        assert result.success is True
        assert result.deal_id is not None
        assert "MOCK_DEAL_" in result.deal_id

    @pytest.mark.asyncio
    async def test_create_contact(self, test_config):
        crm = MockCRMProvider(test_config)
        result = await crm.create_contact(
            name="Test Contact",
            phone="+7 999 888-77-66",
        )
        assert result.success is True
        assert result.contact_id is not None
        assert "MOCK_CONTACT_" in result.contact_id

    @pytest.mark.asyncio
    async def test_create_deal_without_phone(self, test_config):
        """Deal creation should work even without phone."""
        crm = MockCRMProvider(test_config)
        result = await crm.create_deal(name="No Phone Client")
        assert result.success is True
        assert result.deal_id is not None


class TestCRMFactory:
    """Test CRM Factory."""

    def test_factory_mock_mode(self, test_config):
        """MOCK_MODE should return MockCRMProvider."""
        crm = CRMFactory.get_crm(test_config)
        assert isinstance(crm, MockCRMProvider)

    def test_factory_explicit_mock(self, test_config):
        """Explicit 'mock' provider should return MockCRMProvider."""
        import os
        os.environ["MOCK_MODE"] = "false"
        os.environ["CRM_PROVIDER"] = "mock"

        fresh_config = test_config.__class__.from_env()
        object.__setattr__(fresh_config, "mock_mode", False)

        crm = CRMFactory.get_crm(fresh_config)
        assert isinstance(crm, MockCRMProvider)

    def test_factory_unknown_provider(self, test_config):
        """Unknown provider should fallback to MockCRMProvider."""
        import os
        os.environ["MOCK_MODE"] = "false"
        os.environ["CRM_PROVIDER"] = "nonexistent"

        fresh_config = test_config.__class__.from_env()
        object.__setattr__(fresh_config, "mock_mode", False)
        object.__setattr__(fresh_config, "crm_provider", "nonexistent")

        crm = CRMFactory.get_crm(fresh_config)
        assert isinstance(crm, MockCRMProvider)

    def test_factory_bitrix24(self, test_config):
        """Bitrix24 provider should be instantiated."""
        import os
        os.environ["MOCK_MODE"] = "false"
        os.environ["CRM_PROVIDER"] = "bitrix24"

        fresh_config = test_config.__class__.from_env()
        object.__setattr__(fresh_config, "mock_mode", False)
        object.__setattr__(fresh_config, "crm_provider", "bitrix24")

        crm = CRMFactory.get_crm(fresh_config)
        assert isinstance(crm, Bitrix24Provider)

    def test_factory_amocrm(self, test_config):
        """AmoCRM provider should be instantiated."""
        import os
        os.environ["MOCK_MODE"] = "false"
        os.environ["CRM_PROVIDER"] = "amocrm"

        fresh_config = test_config.__class__.from_env()
        object.__setattr__(fresh_config, "mock_mode", False)
        object.__setattr__(fresh_config, "crm_provider", "amocrm")

        crm = CRMFactory.get_crm(fresh_config)
        assert isinstance(crm, AmoCRMProvider)
