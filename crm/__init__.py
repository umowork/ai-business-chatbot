"""
CRM Integration Package.

Supports Bitrix24 REST API and AmoCRM API v4.
"""

from crm.amocrm import AmoCRMProvider
from crm.base import BaseCRMProvider, CRMFactory, CRMResult
from crm.bitrix24 import Bitrix24Provider
from crm.mock import MockCRMProvider

__all__ = [
    "BaseCRMProvider",
    "Bitrix24Provider",
    "AmoCRMProvider",
    "MockCRMProvider",
    "CRMFactory",
    "CRMResult",
]
