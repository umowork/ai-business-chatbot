"""
Bitrix24 REST API integration.
Uses inbound webhooks (no OAuth refresh needed).
"""

import logging

from crm.base import BaseCRMProvider, CRMResult

logger = logging.getLogger(__name__)


class Bitrix24Provider(BaseCRMProvider):
    """Real Bitrix24 REST API integration via webhook."""

    def _get_client(self):
        """Lazy import of httpx."""
        import httpx
        return httpx.AsyncClient(timeout=30.0)

    async def create_contact(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> CRMResult:
        client = self._get_client()
        webhook = self.config.bitrix_webhook.rstrip("/")

        fields = {"NAME": name}
        if phone:
            fields["PHONE"] = [{"VALUE": phone, "VALUE_TYPE": "WORK"}]
        if email:
            fields["EMAIL"] = [{"VALUE": email, "VALUE_TYPE": "WORK"}]

        try:
            response = await client.post(
                f"{webhook}/crm.contact.add.json",
                json={"fields": fields, "params": {"REGISTER_SONET_EVENT": "Y"}},
            )
            data = response.json()
            if response.status_code == 200 and "result" in data:
                contact_id = str(data["result"])
                return CRMResult(
                    success=True,
                    contact_id=contact_id,
                    message=f"Контакт '{name}' создан в Bitrix24",
                )
            else:
                logger.error("Bitrix24 contact error: %s", data)
                return CRMResult(
                    success=False,
                    message=f"Ошибка Bitrix24: {data.get('error_description', 'Unknown error')}",
                )
        except Exception as e:
            logger.error("Bitrix24 request failed: %s", e)
            return CRMResult(success=False, message=f"Ошибка соединения: {str(e)}")
        finally:
            await client.aclose()

    async def create_deal(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        service: str | None = None,
        budget: str | None = None,
        comment: str | None = None,
    ) -> CRMResult:
        client = self._get_client()
        webhook = self.config.bitrix_webhook.rstrip("/")

        # First try to create/find contact
        contact_result = await self.create_contact(name, phone, email)
        contact_id = contact_result.contact_id if contact_result.success else None

        fields = {
            "TITLE": f"Заявка: {service or 'Консультация'} — {name}",
            "NAME": name,
        }
        if contact_id:
            fields["CONTACT_ID"] = contact_id
        if service:
            fields["COMMENTS"] = f"Услуга: {service}"
        if budget:
            fields["OPPORTUNITY"] = budget.replace(" ", "").replace("₽", "").strip()
        if comment:
            existing = fields.get("COMMENTS", "")
            fields["COMMENTS"] = f"{existing}\n{comment}" if existing else comment

        try:
            response = await client.post(
                f"{webhook}/crm.deal.add.json",
                json={"fields": fields, "params": {"REGISTER_SONET_EVENT": "Y"}},
            )
            data = response.json()
            if response.status_code == 200 and "result" in data:
                deal_id = str(data["result"])
                return CRMResult(
                    success=True,
                    deal_id=deal_id,
                    contact_id=contact_id,
                    message=f"Сделка '{name}' создана в Bitrix24 (ID: {deal_id})",
                )
            else:
                logger.error("Bitrix24 deal error: %s", data)
                return CRMResult(
                    success=False,
                    message=f"Ошибка Bitrix24: {data.get('error_description', 'Unknown error')}",
                )
        except Exception as e:
            logger.error("Bitrix24 request failed: %s", e)
            return CRMResult(success=False, message=f"Ошибка соединения: {str(e)}")
        finally:
            await client.aclose()
