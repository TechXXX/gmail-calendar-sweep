from __future__ import annotations

import unittest
from datetime import date, datetime

from gmail_candidate_scan.calendar_integration import (
    CalendarEventDraft,
    CandidateRow,
    _draft_timing_label,
    build_identity_marker,
    create_event,
    event_exists,
    parse_identity_marker,
    prepare_calendar_draft,
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

    def test_prepare_calendar_draft_uses_exclusive_end_for_stays(self) -> None:
        candidate = Candidate(
            gmail_id="gmail-message-456",
            thread_id="thread-2",
            internal_datetime="2026-04-10T15:17:00+02:00",
            category="travel",
            confidence=6,
            sender="Airbnb",
            sender_email="automated@airbnb.com",
            subject="Bestätigt: Aufenthalt vom 13.–17. April – Quittung von Airbnb",
            matched_dates=("13 Apr", "17 Apr"),
            matched_times=("16:00",),
            reason_flags=("category:travel",),
            snippet="Check in Mon 13 Apr, check out Fri 17 Apr.",
        )

        draft = prepare_calendar_draft(CandidateRow(html_row_number=1, candidate=candidate))

        assert draft is not None
        self.assertEqual(draft.all_day_start, date(2026, 4, 13))
        self.assertEqual(draft.all_day_end, date(2026, 4, 18))
        self.assertEqual(_draft_timing_label(draft), "2026-04-13 to 2026-04-17 (all day)")

    def test_create_event_writes_exclusive_end_for_all_day_stays(self) -> None:
        service = _CalendarService()
        candidate = _candidate()
        draft = CalendarEventDraft(
            candidate=candidate,
            title="Stay in Oberndorf",
            notes=build_identity_marker(candidate.gmail_id),
            all_day_start=date(2026, 4, 13),
            all_day_end=date(2026, 4, 18),
        )

        create_event(service, "calendar-1", draft)

        kwargs = service.insert_call.last_kwargs
        assert kwargs is not None
        body = kwargs["body"]
        self.assertEqual(body["start"], {"date": "2026-04-13"})
        self.assertEqual(body["end"], {"date": "2026-04-18"})


if __name__ == "__main__":
    unittest.main()
