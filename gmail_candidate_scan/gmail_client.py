from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Iterable

@dataclass(frozen=True)
class MessageRecord:
    gmail_id: str
    thread_id: str
    internal_ts: int
    internal_datetime: str
    label_ids: tuple[str, ...]
    from_header: str
    from_email: str
    subject: str
    snippet: str
    body_text: str


def build_gmail_service(creds):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_message_ids(service, query: str, page_size: int, max_messages: int | None) -> list[str]:
    ids: list[str] = []
    page_token: str | None = None

    while True:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                includeSpamTrash=False,
                maxResults=page_size,
                pageToken=page_token,
            )
            .execute()
        )
        ids.extend(item["id"] for item in response.get("messages", []))

        if max_messages is not None and len(ids) >= max_messages:
            return ids[:max_messages]

        page_token = response.get("nextPageToken")
        if not page_token:
            return ids


def fetch_messages(service, message_ids: Iterable[str]) -> list[MessageRecord]:
    records: list[MessageRecord] = []

    for message_id in message_ids:
        payload = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        records.append(_to_record(payload))

    records.sort(key=lambda record: (record.internal_ts, record.gmail_id))
    return records


def _to_record(payload: dict) -> MessageRecord:
    headers = {header["name"].lower(): header["value"] for header in payload["payload"].get("headers", [])}
    from_header = headers.get("from", "")
    _, from_email = parseaddr(from_header)
    internal_ts = int(payload["internalDate"])
    internal_dt = datetime.fromtimestamp(internal_ts / 1000, tz=timezone.utc).isoformat()

    return MessageRecord(
        gmail_id=payload["id"],
        thread_id=payload["threadId"],
        internal_ts=internal_ts,
        internal_datetime=internal_dt,
        label_ids=tuple(sorted(payload.get("labelIds", []))),
        from_header=from_header,
        from_email=from_email.lower(),
        subject=headers.get("subject", ""),
        snippet=payload.get("snippet", ""),
        body_text=_extract_body_text(payload["payload"]),
    )


def _extract_body_text(payload: dict) -> str:
    parts = payload.get("parts", [])
    if parts:
        text_chunks: list[str] = []
        for part in parts:
            text_chunks.extend(_walk_part(part))
        return "\n".join(chunk for chunk in text_chunks if chunk).strip()
    body_data = payload.get("body", {}).get("data")
    return _decode_body(body_data)


def _walk_part(part: dict) -> list[str]:
    mime_type = part.get("mimeType", "")
    nested_parts = part.get("parts", [])
    if nested_parts:
        chunks: list[str] = []
        for nested in nested_parts:
            chunks.extend(_walk_part(nested))
        return chunks
    if mime_type not in {"text/plain", "text/html"}:
        return []
    body = _decode_body(part.get("body", {}).get("data"))
    if mime_type == "text/html":
        body = _strip_html(body)
    return [body]


def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    output: list[str] = []
    in_tag = False
    for char in text:
        if char == "<":
            in_tag = True
            continue
        if char == ">":
            in_tag = False
            continue
        if not in_tag:
            output.append(char)
    return "".join(output)
