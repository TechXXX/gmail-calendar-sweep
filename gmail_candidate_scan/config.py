from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "candidates.csv"
DEFAULT_TOKEN_PATH = PROJECT_ROOT / "secrets" / "gmail_token.json"
DEFAULT_CREDENTIALS_PATH = PROJECT_ROOT / "secrets" / "gmail_credentials.json"
DEFAULT_MAX_MESSAGES = 2000
DEFAULT_PAGE_SIZE = 100


def _compile_many(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


@dataclass(frozen=True)
class CategoryRule:
    name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class ScanRules:
    categories: tuple[CategoryRule, ...] = (
        CategoryRule(
            "travel",
            (
                "flight",
                "boarding",
                "check-in",
                "itinerary",
                "hotel",
                "reservation",
                "trip",
                "departs",
                "arrives",
                "rental car",
                "train",
            ),
        ),
        CategoryRule(
            "appointment",
            (
                "appointment",
                "consultation",
                "scheduled",
                "booking confirmed",
                "meeting",
                "doctor",
                "dentist",
                "clinic",
                "interview",
            ),
        ),
        CategoryRule(
            "event",
            (
                "ticket",
                "event",
                "concert",
                "conference",
                "festival",
                "workshop",
                "meetup",
                "admission",
                "doors open",
            ),
        ),
        CategoryRule(
            "deadline",
            (
                "deadline",
                "due date",
                "payment due",
                "renewal",
                "expires",
                "submit by",
                "respond by",
                "last day",
            ),
        ),
        CategoryRule(
            "delivery",
            (
                "delivery",
                "arriving",
                "pickup",
                "pick up",
                "drop-off",
                "courier",
                "shipment",
                "out for delivery",
                "delivery window",
            ),
        ),
    )
    positive_senders: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: tuple(
            _compile_many(
                [
                    r"airlines?",
                    r"booking\.com",
                    r"airbnb",
                    r"hotel",
                    r"expedia",
                    r"rail",
                    r"doctor",
                    r"clinic",
                    r"hospital",
                    r"eventbrite",
                    r"ticketmaster",
                    r"dhl",
                    r"ups",
                    r"fedex",
                ]
            )
        )
    )
    negative_senders: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: tuple(
            _compile_many(
                [
                    r"substack",
                    r"newsletter",
                    r"linkedin",
                    r"glassdoor",
                    r"mailchimp",
                    r"paypal",
                    r"stripe",
                    r"google-maps-platform",
                    r"notifications@vercel\.com",
                ]
            )
        )
    )
    negative_subjects: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: tuple(
            _compile_many(
                [
                    r"\binvoice\b",
                    r"\breceipt\b",
                    r"\be-?receipt\b",
                    r"\bpayment\b",
                    r"\bnewsletter\b",
                    r"\bdigest\b",
                    r"\bweekly update\b",
                    r"\bnews round(?:up)?\b",
                    r"\border confirmation\b",
                    r"\bmigrate to\b",
                    r"\bswift package manager\b",
                    r"\bios sdk",
                    r"\bapi(?:s)?\b",
                    r"\bbestätigung\b",
                    r"\bconfirmation\b",
                    r"\bterms and conditions\b",
                    r"\breward programme\b",
                    r"\breward program\b",
                    r"\bnew login\b",
                    r"\bnew sign-?in\b",
                    r"\blogin attempt\b",
                    r"\bsecurity alert\b",
                    r"\bhealthy lawn\b",
                    r"\blawn plans?\b",
                    r"\bfirst application\b",
                    r"\baccount-gegevens zijn bijgewerkt\b",
                    r"\baccount.?information.*updated\b",
                    r"\bmust still be confirmed\b",
                    r"\bwacht op bevestiging\b",
                    r"\breisgegevens nodig\b",
                    r"\byou have a message from\b",
                    r"\bvalora tu estancia\b",
                    r"\bmuss noch bestätigt werden\b",
                ]
            )
        )
    )
    negative_body: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: tuple(
            _compile_many(
                [
                    r"\bread more\b",
                    r"\bview in browser\b",
                    r"\bprivacy policy\b",
                    r"\bterms of service\b",
                    r"\bunsubscribe\b",
                    r"\bnewsletter\b",
                    r"\breader-supported\b",
                    r"\bmanage preferences\b",
                    r"\bswift package manager\b",
                    r"\bcocoapods\b",
                    r"\bios sdk",
                    r"\bdeveloper(?:s)?\b",
                    r"\bgoogle maps platform customer\b",
                    r"\bdevelopment and release processes\b",
                    r"\bmigrate to\b",
                    r"\berfolgreich übermittelt\b",
                    r"\bsubmitted successfully\b",
                    r"\bovermittelt\b",
                    r"\bzusammenfassung ihrer übermittelten daten\b",
                    r"\bconfirmation of submission\b",
                    r"\bform(?:ular)? .* erfolgreich\b",
                    r"\bterms and conditions\b",
                    r"\breward programme\b",
                    r"\breward program\b",
                    r"\bnew login(?: attempt)?\b",
                    r"\bnew sign-?in\b",
                    r"\bdid you just log in\b",
                    r"\bmake sure it'?s really you\b",
                    r"\bnew location, device or browser\b",
                    r"\bsecurity alert\b",
                    r"\blocation .* time thursday\b",
                    r"\bhealthy lawn\b",
                    r"\blawn plan\b",
                    r"\bbeautiful lawns start here\b",
                    r"\bpromotional offer\b",
                    r"\bfirst application\b",
                    r"\bapple account.?informatie is bijgewerkt\b",
                    r"\bapple account.*updated\b",
                    r"\bde volgende wijzigingen aan je apple account\b",
                    r"\bbooking is nog niet .* bevestigd\b",
                    r"\bboeking wacht op bevestiging\b",
                    r"\bnoch nicht von der fluggesellschaft bestätigt\b",
                    r"\bmuss noch bestätigt werden\b",
                    r"\bneeds your travel information\b",
                    r"\breisinformatie nodig\b",
                    r"\bje touroperator heeft je reisinformatie nodig\b",
                    r"\bwhat was your experience\b",
                    r"\bqué tal fue tu experiencia\b",
                    r"\brate your stay\b",
                    r"\bvalora tu estancia\b",
                    r"\bproperty'?s message: salinetas hola\b",
                ]
            )
        )
    )
    date_patterns: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:mon|monday|tue|tuesday|wed|wednesday|thu|thursday|fri|friday|sat|saturday|sun|sunday),?\s+"
            r"(\d{1,2})\s+"
            r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
            r"\s+(\d{4})\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(\d{1,2})\s+"
            r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
            r"\s+(\d{4})\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b"
            r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
            r"\s+(\d{1,2}),?\s+(\d{4})\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b"),
    )
    time_patterns: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b"),
        re.compile(r"\b([1-9]|1[0-2])(?::([0-5]\d))?\s?(am|pm)\b", re.IGNORECASE),
    )
    future_signals: tuple[str, ...] = (
        "today",
        "tomorrow",
        "scheduled for",
        "starts at",
        "boarding",
        "check-in",
        "appointment on",
        "pickup at",
        "delivery window",
        "arrives on",
        "due on",
    )


RULES = ScanRules()
