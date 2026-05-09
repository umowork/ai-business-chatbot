"""
Google Calendar integration for appointment booking.

Provides list_events and create_event with automatic mock mode fallback.
Uses google-api-python-client for real calls; returns synthetic data in mock mode.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """Simplified representation of a calendar event."""

    event_id: str
    summary: str
    start: datetime
    end: datetime
    description: str | None = None
    attendee_email: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "description": self.description,
            "attendee_email": self.attendee_email,
        }


class GoogleCalendarService:
    """Google Calendar API wrapper with mock mode support."""

    def __init__(self, config: Config):
        self.config = config
        self.mock = config.mock_mode
        self.calendar_id = "primary"
        self._service = None

    def _get_service(self):
        """Lazy-init the Google API client (real mode only)."""
        if self._service is not None:
            return self._service
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                self.config.google_calendar_credentials,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except Exception as exc:
            logger.error("Failed to init Google Calendar client: %s", exc)
            raise

    async def list_events(
        self,
        max_results: int = 10,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> list[CalendarEvent]:
        """Return upcoming calendar events."""
        if self.mock:
            return self._mock_list_events(max_results, time_min)

        service = self._get_service()
        now = time_min or datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "calendarId": self.calendar_id,
            "timeMin": now.isoformat() + "Z",
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_max:
            params["timeMax"] = time_max.isoformat() + "Z"

        events_result = service.events().list(**params).execute()
        events = events_result.get("items", [])
        return [self._parse_event(e) for e in events]

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str | None = None,
        attendee_email: str | None = None,
    ) -> CalendarEvent:
        """Create a new calendar event (appointment)."""
        if self.mock:
            return self._mock_create_event(summary, start, end, description, attendee_email)

        service = self._get_service()
        body: dict[str, Any] = {
            "summary": summary,
            "description": description or "",
            "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Moscow"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Moscow"},
        }
        if attendee_email:
            body["attendees"] = [{"email": attendee_email}]

        created = service.events().insert(calendarId=self.calendar_id, body=body).execute()
        return self._parse_event(created)

    async def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event by ID."""
        if self.mock:
            logger.info("[MOCK] Deleted event %s", event_id)
            return True

        service = self._get_service()
        service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
        return True

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_event(raw: dict[str, Any]) -> CalendarEvent:
        start_raw = raw["start"].get("dateTime", raw["start"].get("date"))
        end_raw = raw["end"].get("dateTime", raw["end"].get("date"))
        attendees = raw.get("attendees", [])
        return CalendarEvent(
            event_id=raw.get("id", ""),
            summary=raw.get("summary", "(no title)"),
            start=datetime.fromisoformat(start_raw.replace("Z", "+00:00")),
            end=datetime.fromisoformat(end_raw.replace("Z", "+00:00")),
            description=raw.get("description"),
            attendee_email=attendees[0]["email"] if attendees else None,
        )

    # ── mock helpers ─────────────────────────────────────────────────────

    def _mock_list_events(
        self, max_results: int, time_min: datetime | None
    ) -> list[CalendarEvent]:
        base = time_min or datetime.now(timezone.utc)
        events = []
        for i in range(min(max_results, 3)):
            start = base + timedelta(hours=i + 1)
            events.append(
                CalendarEvent(
                    event_id=f"MOCK_EVT_{i + 1}",
                    summary=f"[MOCK] Консультация #{i + 1}",
                    start=start,
                    end=start + timedelta(hours=1),
                    description="Тестовое событие (mock)",
                )
            )
        logger.info("[MOCK] Returning %d mock events", len(events))
        return events

    def _mock_create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str | None,
        attendee_email: str | None,
    ) -> CalendarEvent:
        event_id = f"MOCK_EVT_{abs(hash(summary + start.isoformat())) % 1_000_000}"
        logger.info("[MOCK] Created event '%s' (ID: %s)", summary, event_id)
        return CalendarEvent(
            event_id=event_id,
            summary=summary,
            start=start,
            end=end,
            description=description,
            attendee_email=attendee_email,
        )
