from __future__ import annotations

import unittest
from datetime import datetime

from gmail_candidate_scan.calendar_integration import (
    CalendarEventDraft,
    build_identity_marker,
    create_event,
    event_exists,
    parse_identity_marker,
)
from gmail_candidate_scan.extraction import Candidate


class _EventsListCall:
    def __init__(self, response: dict):
        self.response = response
        self.last_kwargs: dict | None = None

    def list(self, **kwargs):
        self.last_kwargs = kwargs
        return self

    def execute(self):
        return self.response


class _EventsInsertCall:
    def __init__(self):
        self.last_kwargs: dict | None = None

    def insert(self, **kwargs):
        self.last_kwargs = kwargs
        return self

    def execute(self):
        return {"id": "evt-1"}


class _CalendarService:
    def __init__(self, list_response: dict | None = None):
        self.list_call = _EventsListCall(list_response or {})
        self.insert_call = _EventsInsertCall()

    def events(self):
        class _EventsProxy:
            def __init__(self, list_call, insert_call):
                self._list_call = list_call
                self._insert_call = insert_call

            def list(self, **kwargs):
                return self._list_call.list(**kwargs)

            def insert(self, **kwargs):
                return self._insert_call.insert(**kwargs)

        return _EventsProxy(self.list_call, self.insert_call)


def _candidate() -> Candidate:
    return Candidate(
        gmail_id="gmail-message-123",
        thread_id="thread-1",
        internal_datetime="2026-03-26T10:00:00+00:00",
        category="travel",
        confidence=6,
        sender="Airbnb",
        sender_email="host@example.com",
        subject="Stay in Bangkok",
        matched_dates=("1 Apr 2026",),
        matched_times=("10:00",),
        reason_flags=("category:travel",),
        snippet="Check-in details",
    )


class CalendarIdentityTests(unittest.TestCase):
    def test_identity_marker_round_trip(self) -> None:
        marker = build_identity_marker("gmail-message-123")
        self.assertEqual(marker, "gmail_candidate_id=gmail-message-123")
        self.assertEqual(parse_identity_marker(marker), "gmail-message-123")

    def test_event_exists_uses_private_extended_property_marker(self) -> None:
        service = _CalendarService({"items": [{"id": "evt-1"}]})

        exists = event_exists(service, "calendar-1", build_identity_marker("gmail-message-123"))

        self.assertTrue(exists)
        self.assertEqual(
            service.list_call.last_kwargs,
            {
                "calendarId": "calendar-1",
                "privateExtendedProperty": ["gmail_candidate_id=gmail-message-123"],
                "maxResults": 1,
                "singleEvents": False,
            },
        )

    def test_create_event_writes_marker_to_metadata_and_description(self) -> None:
        service = _CalendarService()
        candidate = _candidate()
        draft = CalendarEventDraft(
            candidate=candidate,
            title="Stay in Bangkok",
            notes="\n".join(
                [
                    build_identity_marker(candidate.gmail_id),
                    "category=travel",
                    "subject=Stay in Bangkok",
                ]
            ),
            start_at=datetime.fromisoformat("2026-04-01T10:00:00+00:00"),
            end_at=datetime.fromisoformat("2026-04-01T12:00:00+00:00"),
        )

        create_event(service, "calendar-1", draft)

        kwargs = service.insert_call.last_kwargs
        assert kwargs is not None
        body = kwargs["body"]
        self.assertEqual(kwargs["calendarId"], "calendar-1")
        self.assertEqual(body["extendedProperties"]["private"]["gmail_candidate_id"], candidate.gmail_id)
        self.assertIn(build_identity_marker(candidate.gmail_id), body["description"])


if __name__ == "__main__":
    unittest.main()
