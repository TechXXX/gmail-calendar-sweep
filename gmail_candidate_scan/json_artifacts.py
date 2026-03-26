from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from .calendar_integration import CalendarCreateResult, CalendarPreviewRow
from .extraction import Candidate


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat()


def current_run_id() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def write_discover_json(
    path: Path,
    candidates: list[Candidate],
    scanned_message_count: int,
    query: str,
    run_id: str,
    generated_at: str,
    artifacts: dict[str, str],
) -> None:
    category_counts = Counter(candidate.category for candidate in candidates)
    confidence_counts = Counter(candidate.confidence for candidate in candidates)
    payload = {
        "run_id": run_id,
        "generated_at": generated_at,
        "query": query,
        "summary": {
            "candidate_count": len(candidates),
            "scanned_message_count": scanned_message_count,
            "top_category": _top_category_label(category_counts),
            "highest_confidence": max(confidence_counts) if confidence_counts else 0,
        },
        "artifacts": artifacts,
        "candidates": [
            {
                **asdict(candidate),
                "row_number": index,
            }
            for index, candidate in enumerate(candidates, start=1)
        ],
    }
    _write_json(path, payload)


def write_calendar_preview_json(
    path: Path,
    rows: tuple[CalendarPreviewRow, ...],
    calendar_name: str,
    source_csv: Path,
    run_id: str,
    generated_at: str,
    query: str,
    artifacts: dict[str, str],
) -> None:
    outcome_counts = Counter(row.outcome for row in rows)
    payload = {
        "run_id": run_id,
        "generated_at": generated_at,
        "query": query,
        "calendar_name": calendar_name,
        "summary": {
            "row_count": len(rows),
            "would_create": outcome_counts.get("would_create", 0),
            "skipped_existing": outcome_counts.get("skipped_existing", 0),
            "skipped_ambiguous": outcome_counts.get("skipped_ambiguous", 0),
            "skipped_duplicate": outcome_counts.get("skipped_duplicate_confirmed_preferred", 0),
        },
        "source_csv": str(source_csv),
        "artifacts": artifacts,
        "rows": [asdict(row) for row in rows],
    }
    _write_json(path, payload)


def write_calendar_create_json(
    path: Path,
    result: CalendarCreateResult,
    calendar_name: str,
    source_csv: Path,
    run_id: str,
    generated_at: str,
    query: str,
    artifacts: dict[str, str],
) -> None:
    payload = {
        "run_id": run_id,
        "generated_at": generated_at,
        "query": query,
        "calendar_name": calendar_name,
        "summary": {
            "created": result.created,
            "skipped_existing": result.skipped_existing,
            "skipped_ambiguous": result.skipped_ambiguous,
            "skipped_duplicate": result.skipped_duplicate,
            "failed": result.failed,
            "dry_run": result.dry_run,
        },
        "source_csv": str(source_csv),
        "artifacts": artifacts,
        "lines": [asdict(line) for line in result.lines],
    }
    _write_json(path, payload)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _top_category_label(counts: Counter[str]) -> str:
    if not counts:
        return "n/a"
    category, count = counts.most_common(1)[0]
    return f"{category} ({count})"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
