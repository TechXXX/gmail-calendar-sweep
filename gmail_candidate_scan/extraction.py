from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import RULES, CategoryRule
from .gmail_client import MessageRecord


@dataclass(frozen=True)
class Candidate:
    gmail_id: str
    thread_id: str
    internal_datetime: str
    category: str
    confidence: int
    sender: str
    sender_email: str
    subject: str
    matched_dates: tuple[str, ...]
    matched_times: tuple[str, ...]
    reason_flags: tuple[str, ...]
    snippet: str


def discover_candidates(messages: Iterable[MessageRecord]) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen_keys: set[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = set()

    for message in messages:
        candidate = classify_message(message)
        if not candidate:
            continue
        key = (
            candidate.gmail_id,
            candidate.category,
            candidate.matched_dates,
            candidate.matched_times,
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        candidates.append(candidate)

    candidates.sort(key=lambda item: (item.internal_datetime, item.gmail_id, item.category))
    return candidates


def classify_message(message: MessageRecord) -> Candidate | None:
    haystack = _compact_text(" ".join((message.subject, message.snippet, message.body_text)))
    sender_haystack = f"{message.from_header} {message.from_email}".lower()
    reason_flags: list[str] = []

    if _looks_like_forwarded_duplicate(message, haystack):
        return None
    if any(pattern.search(sender_haystack) for pattern in RULES.negative_senders):
        return None
    if any(pattern.search(message.subject) for pattern in RULES.negative_subjects):
        return None
    if any(pattern.search(haystack) for pattern in RULES.negative_body):
        return None
    if "list-unsubscribe" in haystack:
        return None

    category, category_flags = _match_category(haystack)
    if not category:
        return None
    reason_flags.extend(category_flags)

    matched_dates = tuple(dict.fromkeys(_match_patterns(haystack, RULES.date_patterns)))
    matched_times = tuple(dict.fromkeys(_match_patterns(haystack, RULES.time_patterns)))

    explicit_schedule = bool(matched_dates)
    timing_signal = explicit_schedule or bool(matched_times)
    future_signal = any(signal in haystack for signal in RULES.future_signals)
    if explicit_schedule:
        reason_flags.append("explicit_date")
    if matched_times:
        reason_flags.append("explicit_time")
    if future_signal:
        reason_flags.append("future_signal")

    positive_sender = any(pattern.search(sender_haystack) for pattern in RULES.positive_senders)
    if positive_sender:
        reason_flags.append("strong_sender")

    confidence = 0
    confidence += 2
    confidence += 2 if explicit_schedule else 0
    confidence += 1 if matched_times else 0
    confidence += 1 if future_signal else 0
    confidence += 1 if positive_sender else 0

    # Conservative filter: broad discovery, but still require concrete scheduling evidence.
    if not timing_signal and category != "deadline":
        return None
    if category == "deadline" and not (explicit_schedule or future_signal):
        return None
    if category == "delivery" and not (explicit_schedule or "delivery window" in haystack or "out for delivery" in haystack):
        return None
    if category in {"travel", "appointment", "event"} and not (explicit_schedule or matched_times):
        return None

    return Candidate(
        gmail_id=message.gmail_id,
        thread_id=message.thread_id,
        internal_datetime=message.internal_datetime,
        category=category,
        confidence=confidence,
        sender=message.from_header,
        sender_email=message.from_email,
        subject=message.subject,
        matched_dates=matched_dates,
        matched_times=matched_times,
        reason_flags=tuple(reason_flags),
        snippet=message.snippet.strip(),
    )


def _looks_like_forwarded_duplicate(message: MessageRecord, haystack: str) -> bool:
    subject = message.subject.strip().lower()
    if not (subject.startswith("fw:") or subject.startswith("fwd:")):
        return False
    forwarded_markers = (
        "from:",
        "sent:",
        "to:",
        "subject:",
    )
    return all(marker in haystack for marker in forwarded_markers)


def _match_category(haystack: str) -> tuple[str | None, list[str]]:
    best_category: str | None = None
    best_hits = 0
    best_flags: list[str] = []

    for category in RULES.categories:
        hits = _count_keyword_hits(haystack, category)
        if hits > best_hits:
            best_hits = hits
            best_category = category.name
            best_flags = [f"category:{category.name}", f"keyword_hits:{hits}"]

    return best_category, best_flags


def _count_keyword_hits(haystack: str, category: CategoryRule) -> int:
    return sum(1 for keyword in category.keywords if keyword in haystack)


def _match_patterns(text: str, patterns) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        for found in pattern.finditer(text):
            matches.append(found.group(0))
    return matches


def _compact_text(text: str) -> str:
    return " ".join(text.lower().split())
