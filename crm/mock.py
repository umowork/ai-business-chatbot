"""
Mock CRM provider for development and testing.
"""

import asyncio

from crm.base import BaseCRMProvider, CRMResult


class MockCRMProvider(BaseCRMProvider):
    """Mock CRM for development and testing."""

    async def create_deal(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        service: str | None = None,
        budget: str | None = None,
        comment: str | None = None,
    ) -> CRMResult:
        await asyncio.sleep(0.2)
        deal_id = f"MOCK_DEAL_{abs(hash(name + str(phone))) % 1000000}"
        contact_id = f"MOCK_CONTACT_{abs(hash(name)) % 1000000}"
        return CRMResult(
            success=True,
            deal_id=deal_id,
            contact_id=contact_id,
            message=f"[MOCK] Сделка '{name}' создана (ID: {deal_id})",
        )

    async def create_contact(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> CRMResult:
        await asyncio.sleep(0.1)
        contact_id = f"MOCK_CONTACT_{abs(hash(name)) % 1000000}"
        return CRMResult(
            success=True,
            contact_id=contact_id,
            message=f"[MOCK] Контакт '{name}' создан (ID: {contact_id})",
        )
