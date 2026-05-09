"""
CRM base classes and factory.
"""

import logging
from typing import Any

from config import Config

logger = logging.getLogger(__name__)


class CRMResult:
    """Typed result from CRM operations."""

    def __init__(
        self,
        success: bool,
        deal_id: str | None = None,
        contact_id: str | None = None,
        message: str = "",
        raw: dict[str, Any] | None = None,
    ):
        self.success = success
        self.deal_id = deal_id
        self.contact_id = contact_id
        self.message = message
        self.raw = raw or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "deal_id": self.deal_id,
            "contact_id": self.contact_id,
            "message": self.message,
        }


class BaseCRMProvider:
    """Abstract base for CRM providers."""

    def __init__(self, config: Config):
        self.config = config

    async def create_deal(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        service: str | None = None,
        budget: str | None = None,
        comment: str | None = None,
    ) -> CRMResult:
        raise NotImplementedError

    async def create_contact(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> CRMResult:
        raise NotImplementedError


class CRMFactory:
    """Factory to create CRM provider based on config."""

    @staticmethod
    def get_crm(config: Config) -> BaseCRMProvider:
        if config.mock_mode:
            logger.info("Using MockCRMProvider (MOCK_MODE=true)")
            from crm.mock import MockCRMProvider

            return MockCRMProvider(config)

        provider = config.crm_provider.lower()
        if provider == "bitrix24":
            logger.info("Using Bitrix24 CRM provider")
            from crm.bitrix24 import Bitrix24Provider

            return Bitrix24Provider(config)
        elif provider == "amocrm":
            logger.info("Using AmoCRM provider")
            from crm.amocrm import AmoCRMProvider

            return AmoCRMProvider(config)
        elif provider == "mock":
            logger.info("Using MockCRMProvider")
            from crm.mock import MockCRMProvider

            return MockCRMProvider(config)
        else:
            logger.warning("Unknown CRM provider '%s', using mock", provider)
            from crm.mock import MockCRMProvider

            return MockCRMProvider(config)
