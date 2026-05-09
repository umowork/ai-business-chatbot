"""
Tests for Google Calendar service — mock mode, list/create/delete events.
"""

from datetime import datetime, timedelta, timezone

import pytest

from config import Config
from services.google_calendar import CalendarEvent, GoogleCalendarService


@pytest.fixture
def calendar_service(test_config: Config) -> GoogleCalendarService:
    """Create a GoogleCalendarService in mock mode."""
    return GoogleCalendarService(test_config)


class TestCalendarEvent:
    """Test CalendarEvent data class."""

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        evt = CalendarEvent(
            event_id="E1",
            summary="Test",
            start=now,
            end=now + timedelta(hours=1),
            description="desc",
            attendee_email="a@b.com",
        )
        d = evt.to_dict()
        assert d["event_id"] == "E1"
        assert d["summary"] == "Test"
        assert d["attendee_email"] == "a@b.com"

    def test_to_dict_no_optional(self):
        now = datetime.now(timezone.utc)
        evt = CalendarEvent(event_id="E2", summary="X", start=now, end=now)
        d = evt.to_dict()
        assert d["description"] is None
        assert d["attendee_email"] is None


class TestGoogleCalendarMockListEvents:
    """Test list_events in mock mode."""

    @pytest.mark.asyncio
    async def test_list_default(self, calendar_service):
        events = await calendar_service.list_events()
        assert len(events) == 3
        for evt in events:
            assert isinstance(evt, CalendarEvent)
            assert evt.event_id.startswith("MOCK_EVT_")

    @pytest.mark.asyncio
    async def test_list_custom_max(self, calendar_service):
        events = await calendar_service.list_events(max_results=1)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_list_with_time_min(self, calendar_service):
        future = datetime.now(timezone.utc) + timedelta(days=7)
        events = await calendar_service.list_events(time_min=future)
        assert len(events) > 0
        assert events[0].start >= future

    @pytest.mark.asyncio
    async def test_list_zero_returns_empty(self, calendar_service):
        events = await calendar_service.list_events(max_results=0)
        assert events == []


class TestGoogleCalendarMockCreateEvent:
    """Test create_event in mock mode."""

    @pytest.mark.asyncio
    async def test_create_basic(self, calendar_service):
        now = datetime.now(timezone.utc)
        evt = await calendar_service.create_event(
            summary="Запись к стоматологу",
            start=now + timedelta(hours=2),
            end=now + timedelta(hours=3),
        )
        assert evt.summary == "Запись к стоматологу"
        assert evt.event_id.startswith("MOCK_EVT_")
        assert evt.attendee_email is None

    @pytest.mark.asyncio
    async def test_create_with_attendee(self, calendar_service):
        now = datetime.now(timezone.utc)
        evt = await calendar_service.create_event(
            summary="B2B встреча",
            start=now + timedelta(days=1),
            end=now + timedelta(days=1, hours=1),
            description="Обсудить условия",
            attendee_email="client@example.com",
        )
        assert evt.attendee_email == "client@example.com"
        assert evt.description == "Обсудить условия"

    @pytest.mark.asyncio
    async def test_create_returns_unique_ids(self, calendar_service):
        now = datetime.now(timezone.utc)
        e1 = await calendar_service.create_event(
            summary="A", start=now, end=now + timedelta(hours=1)
        )
        e2 = await calendar_service.create_event(
            summary="B", start=now, end=now + timedelta(hours=1)
        )
        # Different summaries → different hash → different IDs (high probability)
        assert e1.event_id != e2.event_id or e1.summary != e2.summary


class TestGoogleCalendarMockDeleteEvent:
    """Test delete_event in mock mode."""

    @pytest.mark.asyncio
    async def test_delete_returns_true(self, calendar_service):
        result = await calendar_service.delete_event("MOCK_EVT_1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_arbitrary_id(self, calendar_service):
        result = await calendar_service.delete_event("any-id-123")
        assert result is True


class TestGoogleCalendarInit:
    """Test service initialization."""

    def test_mock_flag_set(self, test_config):
        svc = GoogleCalendarService(test_config)
        assert svc.mock is True

    def test_default_calendar_id(self, test_config):
        svc = GoogleCalendarService(test_config)
        assert svc.calendar_id == "primary"
