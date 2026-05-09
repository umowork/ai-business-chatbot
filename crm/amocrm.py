"""
AmoCRM API v4 integration (OAuth Bearer token).
"""

import logging
from typing import Any

from crm.base import BaseCRMProvider, CRMResult

logger = logging.getLogger(__name__)


class AmoCRMProvider(BaseCRMProvider):
    """Real AmoCRM API integration via OAuth token."""

    def _get_client(self):
        import httpx
        return httpx.AsyncClient(timeout=30.0)

    async def _api_request(
        self, client, method: str, endpoint: str, json_data: dict | None = None
    ) -> dict[str, Any]:
        """Make an authenticated request to AmoCRM API."""
        url = f"{self.config.amo_base_url.rstrip('/')}/api/v4/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.config.amo_token}",
            "Content-Type": "application/json",
        }

        if method.upper() == "GET":
            resp = await client.get(url, headers=headers)
        elif method.upper() == "POST":
            resp = await client.post(url, headers=headers, json=json_data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        data = resp.json()
        if resp.status_code in (200, 201):
            return data
        logger.error("AmoCRM API error %s: %s", resp.status_code, data)
        return {"_error": True, "_status": resp.status_code, "_detail": data}

    async def create_contact(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> CRMResult:
        client = self._get_client()
        try:
            custom_fields = []
            if phone:
                custom_fields.append({
                    "field_code": "PHONE",
                    "values": [{"value": phone}],
                })
            if email:
                custom_fields.append({
                    "field_code": "EMAIL",
                    "values": [{"value": email}],
                })

            payload = [{"name": name, "custom_fields_values": custom_fields}]
            data = await self._api_request(client, "POST", "contacts", json_data=payload)

            if data.get("_error"):
                return CRMResult(
                    success=False,
                    message=f"Ошибка AmoCRM: {data.get('_detail', 'Unknown')}",
                )

            embedded = data.get("_embedded", {})
            contacts = embedded.get("contacts", [])
            if contacts:
                contact_id = str(contacts[0]["id"])
                return CRMResult(
                    success=True,
                    contact_id=contact_id,
                    message=f"Контакт '{name}' создан в AmoCRM",
                )
            return CRMResult(success=False, message="Не удалось создать контакт")
        except Exception as e:
            logger.error("AmoCRM contact error: %s", e)
            return CRMResult(success=False, message=f"Ошибка: {str(e)}")
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
        try:
            # Create contact first
            contact_result = await self.create_contact(name, phone, email)
            contact_id = contact_result.contact_id if contact_result.success else None

            payload = [{
                "name": f"Заявка: {service or 'Консультация'} — {name}",
                "custom_fields_values": [
                    {
                        "field_code": "BUDGET",
                        "values": [{"value": budget or "Не указан"}],
                    }
                ],
                "_embedded": {
                    "contacts": [{"id": contact_id}] if contact_id else []
                },
            }]

            data = await self._api_request(client, "POST", "leads", json_data=payload)
            if data.get("_error"):
                return CRMResult(
                    success=False,
                    message=f"Ошибка AmoCRM: {data.get('_detail', 'Unknown')}",
                )

            embedded = data.get("_embedded", {})
            leads = embedded.get("leads", [])
            if leads:
                deal_id = str(leads[0]["id"])
                return CRMResult(
                    success=True,
                    deal_id=deal_id,
                    contact_id=contact_id,
                    message=f"Сделка '{name}' создана в AmoCRM (ID: {deal_id})",
                )
            return CRMResult(success=False, message="Не удалось создать сделку")
        except Exception as e:
            logger.error("AmoCRM deal error: %s", e)
            return CRMResult(success=False, message=f"Ошибка: {str(e)}")
        finally:
            await client.aclose()
