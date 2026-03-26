from __future__ import annotations

from datetime import datetime
import hashlib
import json
import shutil
from pathlib import Path


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
    previous_hashes = set((previous_latest or {}).get("candidate_hashes", []))
    candidate_hashes: list[str] = []
    category_counts: dict[str, int] = {}
    new_category_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    for row in payload.get("candidates", []):
        candidate_hash = _candidate_hash(row)
        candidate_hashes.append(candidate_hash)
        category = row["category"]
        confidence = str(row["confidence"])
        category_counts[category] = category_counts.get(category, 0) + 1
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
        if candidate_hash not in previous_hashes:
            new_category_counts[category] = new_category_counts.get(category, 0) + 1
    new_candidates = sum(new_category_counts.values())
    return {
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "query": payload["query"],
        "summary": {
            **payload["summary"],
            "new_candidates": new_candidates,
            "category_counts": category_counts,
            "new_category_counts": new_category_counts,
            "confidence_counts": confidence_counts,
        },
        "candidate_hashes": candidate_hashes,
    }


def _public_preview_payload(payload: dict) -> dict:
    outcome_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in payload.get("rows", []):
        outcome = row["outcome"]
        category = row["category"]
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "query": payload.get("query", ""),
        "calendar_name": payload["calendar_name"],
        "summary": {
            **payload["summary"],
            "outcome_counts": outcome_counts,
            "category_counts": category_counts,
        },
    }


def _public_create_payload(payload: dict) -> dict:
    outcome_counts: dict[str, int] = {}
    for line in payload.get("lines", []):
        outcome = line["outcome"]
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    return {
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "query": payload.get("query", ""),
        "calendar_name": payload["calendar_name"],
        "summary": {
            **payload["summary"],
            "outcome_counts": outcome_counts,
        },
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


def _candidate_hash(row: dict) -> str:
    return hashlib.sha256(_candidate_key(row).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return _load_json(path)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
