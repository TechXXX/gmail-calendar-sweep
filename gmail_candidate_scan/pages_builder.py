from __future__ import annotations

from datetime import datetime
import json
import re
import shutil
from pathlib import Path

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
DIGIT_RUN_RE = re.compile(r"\b\d{4,}\b")
WHITESPACE_RE = re.compile(r"\s+")


def build_pages_site(
    discover_json_path: Path,
    preview_json_path: Path,
    create_json_path: Path,
    site_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    discover_payload = _load_json(discover_json_path)
    preview_payload = _load_json(preview_json_path)
    create_payload = _load_json(create_json_path)
    run_id = str(discover_payload["run_id"])

    output_dir.mkdir(parents=True, exist_ok=True)
    _copy_static_site(site_dir, output_dir)

    data_dir = output_dir / "data"
    latest_dir = data_dir / "latest"
    runs_dir = data_dir / "runs"
    run_dir = runs_dir / run_id
    latest_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    previous_latest = _load_optional_json(latest_dir / "discover.json")
    public_discover = _public_discover_payload(discover_payload, previous_latest)
    public_preview = _public_preview_payload(preview_payload)
    public_create = _public_create_payload(create_payload)

    _write_json(run_dir / "discover.json", public_discover)
    _write_json(run_dir / "preview.json", public_preview)
    _write_json(run_dir / "create.json", public_create)

    _write_json(latest_dir / "discover.json", public_discover)
    _write_json(latest_dir / "preview.json", public_preview)
    _write_json(latest_dir / "create.json", public_create)

    run_summary = _build_run_summary(public_discover, public_preview, public_create)
    runs_index_path = runs_dir / "index.json"
    runs_index = _load_optional_json(runs_index_path) or {"generated_at": "", "latest_run_id": "", "runs": []}
    runs = [entry for entry in runs_index.get("runs", []) if entry.get("run_id") != run_id]
    runs.append(run_summary)
    runs.sort(key=lambda item: item["generated_at"], reverse=True)
    runs_index = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "latest_run_id": run_id,
        "runs": runs,
    }
    _write_json(runs_index_path, runs_index)
    return run_summary


def _copy_static_site(site_dir: Path, output_dir: Path) -> None:
    for source in site_dir.iterdir():
        if source.name == "data":
            continue
        target = output_dir / source.name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)


def _public_discover_payload(payload: dict, previous_latest: dict | None) -> dict:
    previous_keys = {
        candidate["key"]
        for candidate in (previous_latest or {}).get("candidates", [])
    }
    candidates = []
    for row in payload.get("candidates", []):
        key = _candidate_key(row)
        candidates.append(
            {
                "row_number": row["row_number"],
                "key": key,
                "is_new": key not in previous_keys,
                "internal_datetime": row["internal_datetime"],
                "category": row["category"],
                "confidence": row["confidence"],
                "subject": _sanitize_text(row["subject"], limit=120),
                "snippet": _sanitize_text(row["snippet"], limit=160),
                "matched_dates": list(row.get("matched_dates", [])),
                "matched_times": list(row.get("matched_times", [])),
                "reason_flags": list(row.get("reason_flags", [])),
                "sender_domain": _sender_domain(row.get("sender_email", "")),
            }
        )
    new_candidates = sum(1 for item in candidates if item["is_new"])
    return {
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "query": payload["query"],
        "summary": {
            **payload["summary"],
            "new_candidates": new_candidates,
        },
        "candidates": candidates,
    }


def _public_preview_payload(payload: dict) -> dict:
    rows = []
    for row in payload.get("rows", []):
        rows.append(
            {
                "html_row_number": row["html_row_number"],
                "source_subject": _sanitize_text(row["source_subject"], limit=100),
                "preview_title": _sanitize_text(row["preview_title"], limit=110),
                "outcome": row["outcome"],
                "timing": _sanitize_text(row["timing"], limit=120),
                "location": "",
                "category": row["category"],
            }
        )
    return {
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "query": payload.get("query", ""),
        "calendar_name": payload["calendar_name"],
        "summary": payload["summary"],
        "rows": rows,
    }


def _public_create_payload(payload: dict) -> dict:
    lines = []
    for line in payload.get("lines", []):
        lines.append(
            {
                "html_row_number": line["html_row_number"],
                "subject": _sanitize_text(line["subject"], limit=110),
                "outcome": line["outcome"],
                "detail": _sanitize_text(line.get("detail") or "", limit=120),
            }
        )
    return {
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "query": payload.get("query", ""),
        "calendar_name": payload["calendar_name"],
        "summary": payload["summary"],
        "lines": lines,
    }


def _build_run_summary(discover_payload: dict, preview_payload: dict, create_payload: dict) -> dict:
    discover_summary = discover_payload["summary"]
    preview_summary = preview_payload["summary"]
    create_summary = create_payload["summary"]
    return {
        "run_id": discover_payload["run_id"],
        "generated_at": discover_payload["generated_at"],
        "query": discover_payload["query"],
        "candidate_count": discover_summary["candidate_count"],
        "new_candidates": discover_summary["new_candidates"],
        "scanned_message_count": discover_summary["scanned_message_count"],
        "would_create": preview_summary["would_create"],
        "skipped_existing_preview": preview_summary["skipped_existing"],
        "skipped_ambiguous_preview": preview_summary["skipped_ambiguous"],
        "created": create_summary["created"],
        "skipped_existing_create": create_summary["skipped_existing"],
        "skipped_ambiguous_create": create_summary["skipped_ambiguous"],
        "skipped_duplicate_create": create_summary["skipped_duplicate"],
        "failed": create_summary["failed"],
        "dry_run": create_summary["dry_run"],
        "paths": {
            "discover": f"./{discover_payload['run_id']}/discover.json",
            "preview": f"./{discover_payload['run_id']}/preview.json",
            "create": f"./{discover_payload['run_id']}/create.json",
        },
    }


def _candidate_key(row: dict) -> str:
    matched_dates = "|".join(row.get("matched_dates", []))
    matched_times = "|".join(row.get("matched_times", []))
    return f"{row['gmail_id']}::{row['category']}::{matched_dates}::{matched_times}"


def _sender_domain(value: str) -> str:
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[-1].lower()


def _sanitize_text(value: str, limit: int) -> str:
    text = WHITESPACE_RE.sub(" ", value or "").strip()
    text = EMAIL_RE.sub("[email]", text)
    text = URL_RE.sub("[link]", text)
    text = PHONE_RE.sub("[phone]", text)
    text = DIGIT_RUN_RE.sub("[id]", text)
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return _load_json(path)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
