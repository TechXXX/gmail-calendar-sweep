from __future__ import annotations

import os
import json
from pathlib import Path

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
DEFAULT_SCOPES = [GMAIL_READONLY_SCOPE]
TOKEN_JSON_ENV = "GMAIL_CANDIDATE_TOKEN_JSON"
CREDENTIALS_JSON_ENV = "GMAIL_CANDIDATE_CREDENTIALS_JSON"
NONINTERACTIVE_ENV = "GMAIL_CANDIDATE_NONINTERACTIVE"


def load_credentials(credentials_path: Path, token_path: Path, scopes: list[str] | tuple[str, ...] | None = None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    required_scopes = list(scopes or DEFAULT_SCOPES)
    creds = None
    token_payload = _load_json_payload(TOKEN_JSON_ENV)
    credentials_payload = _load_json_payload(CREDENTIALS_JSON_ENV)
    noninteractive = _is_noninteractive()

    if token_payload is None and token_path.exists():
        token_payload = json.loads(token_path.read_text(encoding="utf-8"))

    if token_payload is not None:
        granted_scopes = token_payload.get("scopes") or []
        if set(required_scopes).issubset(set(granted_scopes)):
            creds = Credentials.from_authorized_user_info(token_payload, required_scopes)

    if creds and creds.valid and creds.has_scopes(required_scopes):
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if creds and creds.expired and creds.refresh_token and creds.has_scopes(required_scopes):
        creds.refresh(Request())
    else:
        if noninteractive:
            raise RuntimeError(
                "Non-interactive auth could not load a valid authorized token with the required scopes. "
                f"Provide {TOKEN_JSON_ENV} or {token_path} containing an authorized user token for Gmail and Calendar."
            )
        if not credentials_path.exists():
            if credentials_payload is None:
                raise FileNotFoundError(
                    f"Missing OAuth client credentials at {credentials_path}. "
                    "Create a Desktop OAuth client in Google Cloud and place the JSON there, "
                    f"or provide {CREDENTIALS_JSON_ENV}."
                )
            flow = InstalledAppFlow.from_client_config(credentials_payload, required_scopes)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), required_scopes)
        creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _load_json_payload(env_name: str) -> dict | None:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return None
    return json.loads(raw)


def _is_noninteractive() -> bool:
    value = os.getenv(NONINTERACTIVE_ENV, "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("CI", "").strip().lower() in {"1", "true"}
