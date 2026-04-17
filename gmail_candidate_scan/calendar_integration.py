from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import re
import unicodedata

from .extraction import Candidate
from .gmail_client import MessageRecord


CALENDAR_NAME = "Email-Derived Events"
IDENTITY_PREFIX = "gmail_candidate_id="
IDENTITY_FIELD = "gmail_candidate_id"

MONTHS = {
    "jan": 1,
    "january": 1,
    "januar": 1,
    "feb": 2,
    "february": 2,
    "februar": 2,
    "mar": 3,
    "march": 3,
    "märz": 3,
    "maerz": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mai": 5,
    "jun": 6,
    "june": 6,
    "juni": 6,
    "jul": 7,
    "july": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    "dez": 12,
    "dezember": 12,
}


@dataclass(frozen=True)
class CalendarEventDraft:
    candidate: Candidate
    title: str
    notes: str
    location: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day_start: date | None = None
    all_day_end: date | None = None

    @property
    def identity(self) -> str:
        return build_identity_marker(self.candidate.gmail_id)

    @property
    def is_all_day(self) -> bool:
        return self.all_day_start is not None


@dataclass(frozen=True)
class CalendarCreateResult:
    created: int
    skipped_existing: int
    skipped_ambiguous: int
    skipped_duplicate: int
    failed: int
    dry_run: bool
    lines: tuple["CalendarActionLine", ...]


@dataclass(frozen=True)
class CalendarPreviewRow:
    html_row_number: int
    source_subject: str
    preview_title: str
    outcome: str
    timing: str
    location: str
    category: str


@dataclass(frozen=True)
class CandidateRow:
    html_row_number: int
    candidate: Candidate
    message_record: MessageRecord | None = None


@dataclass(frozen=True)
class CalendarActionLine:
    html_row_number: int
    subject: str
    outcome: str
    detail: str | None = None

    def render(self) -> str:
        line = f"HTML row {self.html_row_number}: {self.subject} -> {self.outcome}"
        if self.detail:
            return f"{line} ({self.detail})"
        return line


def load_candidates(path: Path) -> list[CandidateRow]:
    from .cli import read_candidates_from_csv

    return [
        CandidateRow(html_row_number=index, candidate=candidate)
        for index, candidate in enumerate(read_candidates_from_csv(path), start=1)
    ]


def limit_candidates(candidates: list[CandidateRow], limit: int | None) -> list[CandidateRow]:
    if limit is None:
        return candidates
    return candidates[:limit]


def enrich_candidate_rows(
    candidate_rows: list[CandidateRow],
    message_records: list[MessageRecord],
) -> list[CandidateRow]:
    message_by_id = {record.gmail_id: record for record in message_records}
    return [
        CandidateRow(
            html_row_number=row.html_row_number,
            candidate=row.candidate,
            message_record=message_by_id.get(row.candidate.gmail_id),
        )
        for row in candidate_rows
    ]


def prepare_calendar_draft(candidate_row: CandidateRow) -> CalendarEventDraft | None:
    candidate = candidate_row.candidate
    message_body_text = candidate_row.message_record.body_text if candidate_row.message_record else ""
    details = _extract_airbnb_details(candidate, message_body_text)
    flight_details = _extract_flight_details(candidate, message_body_text)
    title = _build_title(candidate, details, flight_details)
    notes = _build_notes(candidate, details, flight_details)

    stay_range = _extract_stay_range(candidate)
    if stay_range is not None:
        return CalendarEventDraft(
            candidate=candidate,
            title=title,
            notes=notes,
            location=details.full_address if details else None,
            all_day_start=stay_range[0],
            all_day_end=stay_range[1],
        )

    timed_range = _extract_timed_event(candidate)
    if timed_range is None and flight_details and flight_details.start_at and flight_details.end_at:
        timed_range = (flight_details.start_at, flight_details.end_at)

    if timed_range is not None:
        return CalendarEventDraft(
            candidate=candidate,
            title=title,
            notes=notes,
            location=(details.full_address if details else None) or (flight_details.carrier_label if flight_details else None),
            start_at=timed_range[0],
            end_at=timed_range[1],
        )

    return None


def create_calendar_events(
    candidates: list[CandidateRow],
    calendar_service,
    calendar_name: str = CALENDAR_NAME,
    dry_run: bool = False,
) -> CalendarCreateResult:
    created = 0
    skipped_existing = 0
    skipped_ambiguous = 0
    skipped_duplicate = 0
    failed = 0
    lines: list[CalendarActionLine] = []

    if not dry_run:
        ensured_calendar_id = ensure_calendar_exists(calendar_service, calendar_name)
        primary_calendar_id = find_primary_calendar_id(calendar_service)
    else:
        ensured_calendar_id = None
        primary_calendar_id = None

    contexts = _build_calendar_contexts(candidates)

    for context in contexts:
        candidate_row = context.row
        candidate = candidate_row.candidate
        draft = context.draft

        if context.duplicate_outcome is not None:
            skipped_duplicate += 1
            lines.append(
                CalendarActionLine(
                    html_row_number=candidate_row.html_row_number,
                    subject=context.preview_title,
                    outcome=context.duplicate_outcome,
                )
            )
            continue

        if draft is None:
            skipped_ambiguous += 1
            lines.append(
                CalendarActionLine(
                    html_row_number=candidate_row.html_row_number,
                    subject=context.preview_title,
                    outcome="skipped_ambiguous",
                )
            )
            continue

        if dry_run:
            lines.append(
                CalendarActionLine(
                    html_row_number=candidate_row.html_row_number,
                    subject=draft.title,
                    outcome="would_create",
                    detail=_draft_label(draft),
                )
            )
            created += 1
            continue

        if primary_calendar_id and native_gmail_event_exists(calendar_service, primary_calendar_id, draft):
            skipped_existing += 1
            lines.append(
                CalendarActionLine(
                    html_row_number=candidate_row.html_row_number,
                    subject=draft.title,
                    outcome="skipped_existing",
                    detail="native_gmail_event",
                )
            )
            continue

        if event_exists(calendar_service, ensured_calendar_id, draft.identity):
            skipped_existing += 1
            lines.append(
                CalendarActionLine(
                    html_row_number=candidate_row.html_row_number,
                    subject=draft.title,
                    outcome="skipped_existing",
                )
            )
            continue

        try:
            create_event(calendar_service, ensured_calendar_id, draft)
            created += 1
            lines.append(
                CalendarActionLine(
                    html_row_number=candidate_row.html_row_number,
                    subject=draft.title,
                    outcome="created",
                    detail=_draft_label(draft),
                )
            )
        except Exception as exc:
            failed += 1
            lines.append(
                CalendarActionLine(
                    html_row_number=candidate_row.html_row_number,
                    subject=draft.title,
                    outcome="failed",
                    detail=str(exc) or "unknown error",
                )
            )

    return CalendarCreateResult(
        created=created,
        skipped_existing=skipped_existing,
        skipped_ambiguous=skipped_ambiguous,
        skipped_duplicate=skipped_duplicate,
        failed=failed,
        dry_run=dry_run,
        lines=tuple(lines),
    )


def preview_calendar_events(
    candidates: list[CandidateRow],
    calendar_service,
    calendar_name: str = CALENDAR_NAME,
) -> tuple[CalendarPreviewRow, ...]:
    rows: list[CalendarPreviewRow] = []
    calendar_id = find_calendar_id(calendar_service, calendar_name)
    primary_calendar_id = find_primary_calendar_id(calendar_service)

    for context in _build_calendar_contexts(candidates):
        candidate_row = context.row
        candidate = candidate_row.candidate
        draft = context.draft

        if context.duplicate_outcome is not None:
            timing = ""
            location = ""
            if context.flight_details:
                timing_parts = [part for part in (context.flight_details.time_label, context.flight_details.service_label) if part]
                timing = "\n".join(timing_parts)
                location = context.flight_details.carrier_label or ""
            rows.append(
                CalendarPreviewRow(
                    html_row_number=candidate_row.html_row_number,
                    source_subject=candidate.subject,
                    preview_title=context.preview_title,
                    outcome=context.duplicate_outcome,
                    timing=timing,
                    location=location,
                    category=candidate.category,
                )
            )
            continue

        if draft is None:
            timing = ""
            location = ""
            if context.flight_details:
                timing_parts = [part for part in (context.flight_details.time_label, context.flight_details.service_label) if part]
                timing = "\n".join(timing_parts)
                location = context.flight_details.carrier_label or ""
            rows.append(
                CalendarPreviewRow(
                    html_row_number=candidate_row.html_row_number,
                    source_subject=candidate.subject,
                    preview_title=context.preview_title,
                    outcome="skipped_ambiguous",
                    timing=timing,
                    location=location,
                    category=candidate.category,
                )
            )
            continue

        outcome = "would_create"
        if primary_calendar_id and native_gmail_event_exists(calendar_service, primary_calendar_id, draft):
            outcome = "skipped_existing"
        elif calendar_id and event_exists(calendar_service, calendar_id, draft.identity):
            outcome = "skipped_existing"

        rows.append(
            CalendarPreviewRow(
                html_row_number=candidate_row.html_row_number,
                source_subject=candidate.subject,
                preview_title=draft.title,
                outcome=outcome,
                timing=_draft_timing_label(draft),
                location=draft.location or "",
                category=candidate.category,
            )
        )

    return tuple(rows)


def _build_calendar_contexts(candidates: list[CandidateRow]) -> list[CandidateCalendarContext]:
    contexts: list[CandidateCalendarContext] = []
    for candidate_row in candidates:
        candidate = candidate_row.candidate
        message_body_text = candidate_row.message_record.body_text if candidate_row.message_record else ""
        details = _extract_airbnb_details(candidate, message_body_text)
        flight_details = _extract_flight_details(candidate, message_body_text)
        draft = prepare_calendar_draft(candidate_row)
        contexts.append(
            CandidateCalendarContext(
                row=candidate_row,
                details=details,
                flight_details=flight_details,
                draft=draft,
            )
        )
    return _mark_duplicate_flights(contexts)


def _mark_duplicate_flights(contexts: list[CandidateCalendarContext]) -> list[CandidateCalendarContext]:
    grouped: dict[str, list[CandidateCalendarContext]] = {}
    for context in contexts:
        key = context.flight_details.duplicate_key if context.flight_details else None
        if key is None:
            continue
        grouped.setdefault(key, []).append(context)

    if not grouped:
        return contexts

    duplicates: dict[int, str] = {}
    for group in grouped.values():
        if len(group) < 2:
            continue
        scored_group = [(_duplicate_preference_score(item.row.candidate), item) for item in group]
        if max(score for score, _ in scored_group) < 20:
            continue
        winner = max(scored_group, key=lambda pair: (pair[0], -pair[1].row.html_row_number))[1]
        for context in group:
            if context is winner:
                continue
            duplicates[id(context)] = "skipped_duplicate_confirmed_preferred"

    output: list[CandidateCalendarContext] = []
    for context in contexts:
        if id(context) in duplicates:
            output.append(
                CandidateCalendarContext(
                    row=context.row,
                    details=context.details,
                    flight_details=context.flight_details,
                    draft=None,
                    duplicate_outcome=duplicates[id(context)],
                )
            )
            continue
        output.append(context)
    return output


def _duplicate_preference_score(candidate: Candidate) -> int:
    subject = candidate.subject.lower()
    score = 0
    if "bestätigt" in subject or "bestatigt" in subject or "confirmed" in subject:
        score += 20
    if "buchungsinformationen" in subject or "booking information" in subject:
        score += 5
    if "checken sie" in subject or "check in" in subject or "check-in" in subject:
        score -= 5
    return score


def build_calendar_service(creds):
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def find_calendar_id(calendar_service, calendar_name: str) -> str | None:
    page_token = None
    while True:
        response = calendar_service.calendarList().list(pageToken=page_token).execute()
        for item in response.get("items", []):
            if item.get("summary") == calendar_name:
                return item["id"]
        page_token = response.get("nextPageToken")
        if not page_token:
            return None


def find_primary_calendar_id(calendar_service) -> str | None:
    page_token = None
    while True:
        response = calendar_service.calendarList().list(pageToken=page_token).execute()
        for item in response.get("items", []):
            if item.get("primary"):
                return item["id"]
        page_token = response.get("nextPageToken")
        if not page_token:
            return None


def ensure_calendar_exists(calendar_service, calendar_name: str) -> str:
    existing_id = find_calendar_id(calendar_service, calendar_name)
    if existing_id:
        return existing_id
    created = calendar_service.calendars().insert(body={"summary": calendar_name}).execute()
    return created["id"]


def event_exists(calendar_service, calendar_id: str, identity: str) -> bool:
    gmail_id = parse_identity_marker(identity)
    response = calendar_service.events().list(
        calendarId=calendar_id,
        privateExtendedProperty=[f"{IDENTITY_FIELD}={gmail_id}"],
        maxResults=1,
        singleEvents=False,
    ).execute()
    return bool(response.get("items"))


def native_gmail_event_exists(calendar_service, calendar_id: str, draft: CalendarEventDraft) -> bool:
    if not draft.is_all_day or draft.candidate.category != "travel":
        return False

    response = calendar_service.events().list(
        calendarId=calendar_id,
        timeMin=datetime.combine(draft.all_day_start, time.min).astimezone().isoformat(),
        timeMax=datetime.combine(draft.all_day_end, time.min).astimezone().isoformat(),
        singleEvents=True,
        maxResults=50,
    ).execute()
    for event in response.get("items", []):
        if _is_native_gmail_duplicate_event(draft, event):
            return True
    return False


def create_event(calendar_service, calendar_id: str, draft: CalendarEventDraft) -> None:
    body = {
        "summary": draft.title,
        "description": draft.notes,
        "extendedProperties": {
            "private": {
                IDENTITY_FIELD: draft.candidate.gmail_id,
            }
        },
    }
    if draft.location:
        body["location"] = draft.location

    if draft.is_all_day:
        body["start"] = {"date": draft.all_day_start.isoformat()}
        body["end"] = {"date": draft.all_day_end.isoformat()}
    else:
        timezone_name = _local_timezone_name()
        body["start"] = {
            "dateTime": draft.start_at.isoformat(),
            "timeZone": timezone_name,
        }
        body["end"] = {
            "dateTime": draft.end_at.isoformat(),
            "timeZone": timezone_name,
        }

    calendar_service.events().insert(calendarId=calendar_id, body=body).execute()


def build_identity_marker(gmail_id: str) -> str:
    return f"{IDENTITY_PREFIX}{gmail_id}"


def parse_identity_marker(identity: str) -> str:
    return identity.removeprefix(IDENTITY_PREFIX)


def _local_timezone_name() -> str:
    local_dt = datetime.now().astimezone()
    tzinfo = local_dt.tzinfo
    zone_name = getattr(tzinfo, "key", None)
    if zone_name:
        return zone_name
    return local_dt.tzname() or "UTC"



def _build_title(
    candidate: Candidate,
    details: "AirbnbDetails | None",
    flight_details: "FlightDetails | None",
) -> str:
    subject = " ".join(candidate.subject.split())
    if details and "aufenthalt" in subject.lower():
        prefix = subject.replace("Bestätigt:", "").replace("Quittung von Airbnb", "")
        prefix = re.sub(r"\s*[–-]\s*$", "", prefix).strip()
        return " - ".join(part for part in (prefix, details.city_country, details.listing_title) if part)
    if flight_details and flight_details.route_label:
        prefix = _flight_title_prefix(subject, flight_details.route_label)
        carrier = flight_details.carrier_label
        return " - ".join(part for part in (prefix, flight_details.route_label, carrier) if part)
    if candidate.category == "travel" and "aufenthalt" in subject.lower():
        return subject.replace("Bestätigt:", "").strip()
    return subject


def _build_notes(
    candidate: Candidate,
    details: "AirbnbDetails | None",
    flight_details: "FlightDetails | None",
) -> str:
    parts = [
        build_identity_marker(candidate.gmail_id),
        f"category={candidate.category}",
        f"sender={candidate.sender}",
        f"subject={candidate.subject}",
    ]
    if candidate.matched_dates:
        parts.append(f"matched_dates={' | '.join(candidate.matched_dates)}")
    if candidate.matched_times:
        parts.append(f"matched_times={' | '.join(candidate.matched_times)}")
    if candidate.reason_flags:
        parts.append(f"reason_flags={' | '.join(candidate.reason_flags)}")
    if details:
        if details.listing_title:
            parts.append(f"listing_title={details.listing_title}")
        if details.city_country:
            parts.append(f"city_country={details.city_country}")
        if details.full_address:
            parts.append(f"address={details.full_address}")
    if flight_details:
        if flight_details.route_label:
            parts.append(f"flight_route={flight_details.route_label}")
        if flight_details.time_label:
            parts.append(f"flight_time={flight_details.time_label}")
        if flight_details.service_label:
            parts.append(f"flight_service={flight_details.service_label}")
        if flight_details.carrier_label:
            parts.append(f"flight_carrier={flight_details.carrier_label}")
    if candidate.snippet:
        parts.append(f"snippet={candidate.snippet}")
    return "\n".join(parts)


def _build_preview_title(
    candidate: Candidate,
    details: "AirbnbDetails | None",
    flight_details: "FlightDetails | None",
) -> str:
    return _build_title(candidate, details, flight_details)


@dataclass(frozen=True)
class AirbnbDetails:
    listing_title: str | None
    city_country: str | None
    full_address: str | None


@dataclass(frozen=True)
class FlightDetails:
    route_label: str | None
    time_label: str | None
    service_label: str | None
    carrier_label: str | None
    start_at: datetime | None = None
    end_at: datetime | None = None

    @property
    def duplicate_key(self) -> str | None:
        if not self.route_label or not self.start_at or not self.end_at:
            return None
        carrier = self.carrier_label or ""
        return "|".join(
            (
                self.route_label,
                self.start_at.isoformat(),
                self.end_at.isoformat(),
                carrier,
            )
        )


@dataclass(frozen=True)
class CandidateCalendarContext:
    row: CandidateRow
    details: "AirbnbDetails | None"
    flight_details: "FlightDetails | None"
    draft: CalendarEventDraft | None
    duplicate_outcome: str | None = None

    @property
    def preview_title(self) -> str:
        if self.draft is not None:
            return self.draft.title
        return _build_preview_title(self.row.candidate, self.details, self.flight_details)


def _extract_airbnb_details(candidate: Candidate, message_body_text: str) -> AirbnbDetails | None:
    if "airbnb" not in candidate.sender_email.lower():
        return None
    if not message_body_text.strip():
        return None

    listing_title = _extract_airbnb_listing_title(message_body_text)
    full_address = _extract_airbnb_address(message_body_text)
    city_country = _city_country_from_address(full_address) if full_address else None

    if not listing_title and not city_country and not full_address:
        return None
    return AirbnbDetails(
        listing_title=listing_title,
        city_country=city_country,
        full_address=full_address,
    )


def _extract_flight_details(candidate: Candidate, message_body_text: str) -> FlightDetails | None:
    sender_email = candidate.sender_email.lower()
    if not any(domain in sender_email for domain in ("booking.com", "gotogate", "lufthansa.com", "tripadvisor.com", "outlook.com")):
        return None

    if not message_body_text.strip():
        return None

    route_label = _extract_booking_route_label(message_body_text)
    time_label = _extract_booking_time_label(message_body_text)
    service_label = _extract_booking_service_label(message_body_text)
    carrier_label = _extract_booking_carrier_label(message_body_text)
    timed_range = _extract_booking_timed_range(message_body_text, candidate.internal_datetime)

    if not any((route_label, time_label, service_label, carrier_label, timed_range)):
        return None
    return FlightDetails(
        route_label=route_label,
        time_label=time_label,
        service_label=service_label,
        carrier_label=carrier_label,
        start_at=timed_range[0] if timed_range else None,
        end_at=timed_range[1] if timed_range else None,
    )


def _extract_booking_route_label(text: str) -> str | None:
    match = re.search(
        r'aria-label="Von\s+([^"]+?\([A-Z]{3}\)\s+nach\s+[^"]+?\([A-Z]{3}\))"',
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return _clean_inline_text(match.group(1))


def _extract_booking_time_label(text: str) -> str | None:
    match = re.search(
        r'([A-Z][a-z]{1,2}\.,\s*\d{1,2}\.\s*[A-Za-zäöüÄÖÜ]+\.?\s*).*?(\d{1,2}:\d{2}).*?([A-Z][a-z]{1,2}\.,\s*\d{1,2}\.\s*[A-Za-zäöüÄÖÜ]+\.?\s*).*?(\d{1,2}:\d{2})',
        text,
        re.DOTALL,
    )
    if not match:
        return None
    start_day = _clean_inline_text(match.group(1))
    start_time = match.group(2)
    end_day = _clean_inline_text(match.group(3))
    end_time = match.group(4)
    return f"{start_day} · {start_time} - {end_day} · {end_time}"


def _extract_booking_service_label(text: str) -> str | None:
    match = re.search(
        r'(Direkt|1\s*Stopp|2\s*Stopps?)\s*</span>.*?aria-label="([^"]+)".*?Economy',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    directness = _clean_inline_text(match.group(1))
    duration = _clean_inline_text(match.group(2))
    return f"{directness} · {duration} · Economy"


def _extract_booking_carrier_label(text: str) -> str | None:
    match = re.search(
        r'>(Bangkok Airways|Lufthansa|Thai Airways International|VietJet|VietJet Air|Tripadvisor)[<].{0,200}?aria-label="([^"]+)"',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    carrier = _clean_inline_text(match.group(1))
    flight_number = _clean_inline_text(match.group(2)).replace(" ", "")
    return f"{carrier} · {flight_number}"


def _extract_booking_timed_range(text: str, internal_datetime: str) -> tuple[datetime, datetime] | None:
    json_range = _extract_booking_json_timed_range(text)
    if json_range is not None:
        return json_range

    label = _extract_booking_time_label(text)
    if not label:
        return None

    match = re.fullmatch(
        r"(.+?)\s+·\s+(\d{1,2}:\d{2})\s+-\s+(.+?)\s+·\s+(\d{1,2}:\d{2})",
        label,
    )
    if not match:
        return None

    start_date = _parse_day_month_label(match.group(1), internal_datetime)
    end_date = _parse_day_month_label(match.group(3), internal_datetime)
    start_time = _parse_time_token(match.group(2))
    end_time = _parse_time_token(match.group(4))
    if not start_date or not end_date or not start_time or not end_time:
        return None

    start_at = datetime.combine(start_date, start_time)
    end_at = datetime.combine(end_date, end_time)
    if end_at <= start_at:
        return None
    return start_at, end_at


def _extract_booking_json_timed_range(text: str) -> tuple[datetime, datetime] | None:
    departure_match = re.search(r'"departureTime"\s*:\s*"([^"]+)"', text)
    arrival_match = re.search(r'"arrivalTime"\s*:\s*"([^"]+)"', text)
    if not departure_match or not arrival_match:
        return None
    try:
        start_at = datetime.fromisoformat(departure_match.group(1))
        end_at = datetime.fromisoformat(arrival_match.group(1))
    except ValueError:
        return None
    if end_at <= start_at:
        return None
    return start_at, end_at


def _flight_title_prefix(subject: str, route_label: str) -> str:
    destination = _flight_destination_from_route(route_label)
    if destination:
        return f"Flug nach {destination}"
    match = re.search(r"flug nach\s+(.+)$", subject, re.IGNORECASE)
    if match:
        suffix = _clean_inline_text(match.group(1))
        suffix = re.sub(r"\s+ein$", "", suffix, flags=re.IGNORECASE)
        suffix = re.sub(r"\s+ist bestätigt$", "", suffix, flags=re.IGNORECASE)
        return f"Flug nach {suffix}"
    return subject


def _flight_destination_from_route(route_label: str) -> str | None:
    match = re.search(r"nach\s+(.+?)\s+\([A-Z]{3}\)$", route_label, re.IGNORECASE)
    if not match:
        return None
    return _clean_inline_text(match.group(1))


def _extract_airbnb_listing_title(text: str) -> str | None:
    cleaned = _clean_body_text(text)
    match = re.search(
        r"https?://[^\s]*airbnb\.[^\s]*/rooms/[^\s]+\s+(.+?)\s+(?:Gesamte Unterkunft|Zimmer|Wohnung|Apartment|Appartement|Privatzimmer)",
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return _normalize_listing_title(match.group(1))


def _extract_airbnb_address(text: str) -> str | None:
    cleaned = _clean_body_text(text)
    match = re.search(r"\bADRESSE\b\s+(.+?)\s+Wegbeschreibung anzeigen", cleaned, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    address = _clean_inline_text(match.group(1))
    return address or None


def _city_country_from_address(address: str) -> str | None:
    parts = [part.strip() for part in address.split(",")]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return None

    country = parts[-1]
    locality = None
    for part in reversed(parts[:-1]):
        if re.fullmatch(r"[\d\- ]+", part):
            continue
        locality = _simplify_locality(part)
        break
    if not locality:
        return country
    return f"{locality}, {country}"


def _simplify_locality(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"^(chang wat|tinh|provincia|province)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _clean_body_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = _clean_inline_text(raw_line)
        if not line:
            continue
        if line == "%opentrack%":
            continue
        lines.append(line)
    return "\n".join(lines)


def _clean_inline_text(value: str) -> str:
    cleaned = "".join(char for char in value if unicodedata.category(char) != "Cf")
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _normalize_listing_title(value: str) -> str | None:
    cleaned = _clean_inline_text(value)
    cleaned = re.sub(r"https?://\S+", "", cleaned).strip()
    if not cleaned:
        return None

    letters = [char for char in cleaned if char.isalpha()]
    if letters and all(char.upper() == char for char in letters):
        cleaned = _smart_titlecase(cleaned.lower())
    return cleaned


def _smart_titlecase(value: str) -> str:
    parts = re.split(r"(\s+)", value)
    return "".join(_titlecase_token(part) if not part.isspace() else part for part in parts)


def _titlecase_token(token: str) -> str:
    separators = "-,./"
    for separator in separators:
        if separator in token:
            return separator.join(_titlecase_token(piece) for piece in token.split(separator))
    if not token:
        return token
    if token.isdigit():
        return token
    return token[:1].upper() + token[1:]




def _extract_stay_range(candidate: Candidate) -> tuple[date, date] | None:
    subject = candidate.subject
    internal_dt = datetime.fromisoformat(candidate.internal_datetime)
    match = re.search(
        r"aufenthalt vom\s+(\d{1,2})\.\s*[–-]\s*(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)",
        subject,
        re.IGNORECASE,
    )
    if match:
        start_day = int(match.group(1))
        end_day = int(match.group(2))
        month = _month_number(match.group(3))
        if month is None:
            return None
        year = internal_dt.year
        start_date = date(year, month, start_day)
        # Google Calendar all-day end dates are exclusive, so add one day.
        end_date = date(year, month, end_day) + timedelta(days=1)
        return start_date, end_date

    cross_month = re.search(
        r"aufenthalt vom\s+(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\.?\s*[–-]\s*(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)",
        subject,
        re.IGNORECASE,
    )
    if cross_month:
        start_day = int(cross_month.group(1))
        start_month = _month_number(cross_month.group(2))
        end_day = int(cross_month.group(3))
        end_month = _month_number(cross_month.group(4))
        if start_month is None or end_month is None:
            return None
        year = internal_dt.year
        start_date = date(year, start_month, start_day)
        end_year = year + 1 if end_month < start_month else year
        # Google Calendar all-day end dates are exclusive, so add one day.
        end_date = date(end_year, end_month, end_day) + timedelta(days=1)
        return start_date, end_date

    return None


def _extract_timed_event(candidate: Candidate) -> tuple[datetime, datetime] | None:
    parsed_dates = [_parse_date_token(token, candidate.internal_datetime) for token in candidate.matched_dates]
    parsed_dates = [item for item in parsed_dates if item is not None]
    parsed_times = [_parse_time_token(token) for token in candidate.matched_times]
    parsed_times = [item for item in parsed_times if item is not None]

    if len(parsed_dates) == 1 and len(parsed_times) >= 1:
        start_at = datetime.combine(parsed_dates[0], parsed_times[0])
        end_time = parsed_times[1] if len(parsed_times) > 1 else _default_end_time(parsed_times[0])
        end_at = datetime.combine(parsed_dates[0], end_time)
        if end_at <= start_at:
            end_at = start_at + timedelta(hours=2)
        return start_at, end_at

    if len(parsed_dates) >= 2 and len(parsed_times) >= 2:
        start_at = datetime.combine(parsed_dates[0], parsed_times[0])
        end_at = datetime.combine(parsed_dates[1], parsed_times[1])
        if end_at > start_at:
            return start_at, end_at

    return None


def _parse_date_token(value: str, internal_datetime: str) -> date | None:
    token = value.strip().lower()
    base_year = datetime.fromisoformat(internal_datetime).year

    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", token)
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year = int(slash_match.group(3))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None

    dotted_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", token)
    if dotted_match:
        day = int(dotted_match.group(1))
        month = int(dotted_match.group(2))
        year = int(dotted_match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    text_match = re.search(r"(\d{1,2})\s+([a-zäöü]+)\s+(\d{4})", token)
    if text_match:
        day = int(text_match.group(1))
        month = _month_number(text_match.group(2))
        year = int(text_match.group(3))
        if month is not None:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    month_first_match = re.search(r"([a-zäöü]+)\s+(\d{1,2}),?\s+(\d{4})", token)
    if month_first_match:
        month = _month_number(month_first_match.group(1))
        day = int(month_first_match.group(2))
        year = int(month_first_match.group(3))
        if month is not None:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    day_month_only = re.search(r"(?:mon|tue|wed|thu|fri|sat|sun),?\s*(\d{1,2})\s+([a-zäöü]+)", token)
    if day_month_only:
        day = int(day_month_only.group(1))
        month = _month_number(day_month_only.group(2))
        if month is not None:
            try:
                return date(base_year, month, day)
            except ValueError:
                return None

    return None


def _parse_day_month_label(value: str, internal_datetime: str) -> date | None:
    token = _clean_inline_text(value).lower().rstrip(".")
    base_year = datetime.fromisoformat(internal_datetime).year
    match = re.search(r"(\d{1,2})\.\s*([a-zäöü]+)", token)
    if not match:
        return None
    day = int(match.group(1))
    month = _month_number(match.group(2))
    if month is None:
        return None
    try:
        return date(base_year, month, day)
    except ValueError:
        return None


def _parse_time_token(value: str) -> time | None:
    token = value.strip().lower()
    direct = re.fullmatch(r"(\d{1,2}):(\d{2})", token)
    if direct:
        return time(int(direct.group(1)), int(direct.group(2)))
    am_pm = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(am|pm)", token)
    if am_pm:
        hour = int(am_pm.group(1))
        minute = int(am_pm.group(2))
        suffix = am_pm.group(3)
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        return time(hour, minute)
    return None


def _month_number(raw: str) -> int | None:
    cleaned = raw.strip().lower().rstrip(".")
    return MONTHS.get(cleaned)


def _default_end_time(start_time: time) -> time:
    start_dt = datetime.combine(date(2000, 1, 1), start_time) + timedelta(hours=2)
    return start_dt.time()


def _is_native_gmail_duplicate_event(draft: CalendarEventDraft, event: dict) -> bool:
    if event.get("eventType") != "fromGmail":
        return False

    start_date = event.get("start", {}).get("date")
    end_date = event.get("end", {}).get("date")
    if start_date != draft.all_day_start.isoformat():
        return False
    if end_date != draft.all_day_end.isoformat():
        return False

    draft_text = " ".join(part for part in (draft.title, draft.location or "") if part)
    event_text = " ".join(
        part
        for part in (
            event.get("summary", ""),
            event.get("location", ""),
            event.get("description", ""),
        )
        if part
    )

    draft_postcodes = _postal_code_tokens(draft_text)
    event_postcodes = _postal_code_tokens(event_text)
    if draft_postcodes and event_postcodes and draft_postcodes.intersection(event_postcodes):
        return True

    shared_tokens = _significant_tokens(draft_text).intersection(_significant_tokens(event_text))
    return len(shared_tokens) >= 2


def _postal_code_tokens(value: str) -> set[str]:
    return {match.group(0) for match in re.finditer(r"\b\d{4,5}\b", value)}


def _significant_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    stopwords = {
        "the",
        "and",
        "for",
        "from",
        "gmail",
        "event",
        "email",
        "created",
        "received",
        "stay",
        "at",
        "von",
        "by",
        "vom",
        "aufenthalt",
        "germany",
    }
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]{4,}", normalized)
        if token not in stopwords
    }
    return tokens


def _draft_label(draft: CalendarEventDraft) -> str:
    if draft.is_all_day:
        return f"all_day:{draft.all_day_start}->{_inclusive_all_day_end(draft)}"
    return f"timed:{draft.start_at.isoformat()}->{draft.end_at.isoformat()}"


def _draft_timing_label(draft: CalendarEventDraft) -> str:
    if draft.is_all_day:
        return f"{draft.all_day_start.isoformat()} to {_inclusive_all_day_end(draft).isoformat()} (all day)"
    return f"{draft.start_at.isoformat()} to {draft.end_at.isoformat()}"


def _inclusive_all_day_end(draft: CalendarEventDraft) -> date:
    return draft.all_day_end - timedelta(days=1)
