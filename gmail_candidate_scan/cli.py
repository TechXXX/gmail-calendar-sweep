from __future__ import annotations

import argparse
import csv
from datetime import datetime
import shutil
from pathlib import Path
import sys

from .auth import CALENDAR_SCOPE, GMAIL_READONLY_SCOPE, load_credentials
from .calendar_integration import (
    CALENDAR_NAME,
    build_calendar_service,
    create_calendar_events,
    enrich_candidate_rows,
    limit_candidates,
    load_candidates,
    preview_calendar_events,
)
from .calendar_report import write_calendar_action_report, write_calendar_preview_report
from .config import (
    DEFAULT_CREDENTIALS_PATH,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_PAGE_SIZE,
    PROJECT_ROOT,
    DEFAULT_TOKEN_PATH,
)
from .extraction import Candidate, discover_candidates
from .gmail_client import build_gmail_service, fetch_messages, list_message_ids
from .json_artifacts import (
    current_run_id,
    current_timestamp,
    write_calendar_create_json,
    write_calendar_preview_json,
    write_discover_json,
)
from .pages_builder import build_pages_site
from .report import write_diff_html_report, write_html_report


DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_PATH.with_suffix(".html")
DEFAULT_RUNS_DIR = DEFAULT_OUTPUT_PATH.parent / "runs"
DEFAULT_CALENDAR_REPORT_PATH = DEFAULT_OUTPUT_PATH.parent / "calendar_create.html"
DEFAULT_CALENDAR_PREVIEW_PATH = DEFAULT_OUTPUT_PATH.parent / "calendar_preview.html"
DEFAULT_DISCOVER_JSON_PATH = DEFAULT_OUTPUT_PATH.with_suffix(".json")
DEFAULT_CALENDAR_CREATE_JSON_PATH = DEFAULT_OUTPUT_PATH.parent / "calendar_create.json"
DEFAULT_CALENDAR_PREVIEW_JSON_PATH = DEFAULT_OUTPUT_PATH.parent / "calendar_preview.json"
DEFAULT_PAGES_OUTPUT_DIR = DEFAULT_OUTPUT_PATH.parent / "pages"
DEFAULT_SITE_DIR = PROJECT_ROOT / "docs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan Gmail for calendar-worthy email candidates, preview Google Calendar drafts, or create Google Calendar events from the current CSV."
    )
    subparsers = parser.add_subparsers(dest="command")

    discover = subparsers.add_parser("discover", help="Scan Gmail and write candidate CSV/HTML outputs.")
    discover.add_argument("--query", required=True, help="Gmail search query to scan.")
    discover.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="CSV output path.",
    )
    discover.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="HTML review report path.",
    )
    discover.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS_PATH,
        help="Path to Google OAuth desktop client JSON.",
    )
    discover.add_argument(
        "--token",
        type=Path,
        default=DEFAULT_TOKEN_PATH,
        help="Path to cached Google API OAuth token JSON.",
    )
    discover.add_argument(
        "--max-messages",
        type=int,
        default=DEFAULT_MAX_MESSAGES,
        help="Maximum number of Gmail messages to inspect.",
    )
    discover.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Gmail API page size for message discovery.",
    )
    discover.add_argument(
        "--json-report",
        type=Path,
        default=DEFAULT_DISCOVER_JSON_PATH,
        help="JSON output path for structured discovery results.",
    )
    discover.add_argument(
        "--run-id",
        default=None,
        help="Optional shared run identifier for multi-stage automation.",
    )

    calendar_create = subparsers.add_parser(
        "calendar-create",
        help="Create Google Calendar events from the current candidate CSV.",
    )
    calendar_create.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="CSV input path to convert into calendar events.",
    )
    calendar_create.add_argument(
        "--calendar-name",
        default=CALENDAR_NAME,
        help="Target Google Calendar name.",
    )
    calendar_create.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which events would be created without writing to Google Calendar.",
    )
    calendar_create.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of candidate rows processed from the CSV.",
    )
    calendar_create.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_CALENDAR_REPORT_PATH,
        help="HTML action report path.",
    )
    calendar_create.add_argument(
        "--json-report",
        type=Path,
        default=DEFAULT_CALENDAR_CREATE_JSON_PATH,
        help="JSON output path for structured calendar create results.",
    )
    calendar_create.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS_PATH,
        help="Path to Google OAuth desktop client JSON for Gmail enrichment and Calendar access.",
    )
    calendar_create.add_argument(
        "--token",
        type=Path,
        default=DEFAULT_TOKEN_PATH,
        help="Path to cached Google API OAuth token JSON for Gmail enrichment and Calendar access.",
    )
    calendar_create.add_argument(
        "--run-id",
        default=None,
        help="Optional shared run identifier for multi-stage automation.",
    )
    calendar_create.add_argument(
        "--query",
        default="",
        help="Source Gmail query metadata for JSON output.",
    )

    calendar_preview = subparsers.add_parser(
        "calendar-preview",
        help="Build an HTML preview sheet showing how Google Calendar entries would look from the current candidate CSV.",
    )
    calendar_preview.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="CSV input path to preview.",
    )
    calendar_preview.add_argument(
        "--calendar-name",
        default=CALENDAR_NAME,
        help="Target Google Calendar name for duplicate checks.",
    )
    calendar_preview.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of candidate rows processed from the CSV.",
    )
    calendar_preview.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_CALENDAR_PREVIEW_PATH,
        help="HTML preview report path.",
    )
    calendar_preview.add_argument(
        "--json-report",
        type=Path,
        default=DEFAULT_CALENDAR_PREVIEW_JSON_PATH,
        help="JSON output path for structured calendar preview results.",
    )
    calendar_preview.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS_PATH,
        help="Path to Google OAuth desktop client JSON for Gmail enrichment and Calendar access.",
    )
    calendar_preview.add_argument(
        "--token",
        type=Path,
        default=DEFAULT_TOKEN_PATH,
        help="Path to cached Google API OAuth token JSON for Gmail enrichment and Calendar access.",
    )
    calendar_preview.add_argument(
        "--run-id",
        default=None,
        help="Optional shared run identifier for multi-stage automation.",
    )
    calendar_preview.add_argument(
        "--query",
        default="",
        help="Source Gmail query metadata for JSON output.",
    )

    pages_build = subparsers.add_parser(
        "pages-build",
        help="Assemble a static GitHub Pages site from the latest JSON outputs.",
    )
    pages_build.add_argument(
        "--discover-json",
        type=Path,
        default=DEFAULT_DISCOVER_JSON_PATH,
        help="Structured discovery JSON path.",
    )
    pages_build.add_argument(
        "--preview-json",
        type=Path,
        default=DEFAULT_CALENDAR_PREVIEW_JSON_PATH,
        help="Structured calendar preview JSON path.",
    )
    pages_build.add_argument(
        "--create-json",
        type=Path,
        default=DEFAULT_CALENDAR_CREATE_JSON_PATH,
        help="Structured calendar create JSON path.",
    )
    pages_build.add_argument(
        "--site-dir",
        type=Path,
        default=DEFAULT_SITE_DIR,
        help="Static site source directory.",
    )
    pages_build.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_PAGES_OUTPUT_DIR,
        help="Target directory for the generated Pages site.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    argv = sys.argv[1:]
    if not argv:
        parser.print_help(sys.stderr)
        raise SystemExit(2)
    if argv[0] not in {"discover", "calendar-create", "calendar-preview", "pages-build"}:
        argv = ["discover", *argv]
    args = parser.parse_args(argv)

    if args.command == "calendar-create":
        run_calendar_create(args)
        return
    if args.command == "calendar-preview":
        run_calendar_preview(args)
        return
    if args.command == "pages-build":
        run_pages_build(args)
        return
    run_discover(args)


def run_discover(args) -> None:
    run_id = args.run_id or current_run_id()
    generated_at = current_timestamp()
    creds = load_credentials(args.credentials, args.token, scopes=[GMAIL_READONLY_SCOPE])
    service = build_gmail_service(creds)

    message_ids = list_message_ids(
        service,
        query=args.query,
        page_size=args.page_size,
        max_messages=args.max_messages,
    )
    messages = fetch_messages(service, message_ids)
    candidates = discover_candidates(messages)

    previous_csv_path, previous_report_path = snapshot_previous_outputs(
        args.output, args.report, DEFAULT_RUNS_DIR
    )
    write_csv(args.output, candidates)
    write_html_report(args.report, candidates, len(messages), args.query)
    write_discover_json(
        path=args.json_report,
        candidates=candidates,
        scanned_message_count=len(messages),
        query=args.query,
        run_id=run_id,
        generated_at=generated_at,
        artifacts={
            "csv": str(args.output),
            "html": str(args.report),
        },
    )
    run_csv_path, run_report_path = snapshot_current_outputs(
        args.output, args.report, DEFAULT_RUNS_DIR
    )
    diff_path = None
    if previous_csv_path:
        previous_candidates = read_candidates_from_csv(previous_csv_path)
        diff_path = run_report_path.with_name(run_report_path.stem + "_diff.html")
        write_diff_html_report(diff_path, previous_candidates, candidates)
    print(
        f"Wrote {len(candidates)} candidates from {len(messages)} messages to {args.output} and {args.report}"
    )
    print(f"Wrote structured discovery JSON to {args.json_report}")
    if previous_csv_path:
        print(f"Archived previous run to {previous_csv_path} and {previous_report_path}")
        print(f"Archived current run to {run_csv_path} and {run_report_path}")
        if diff_path:
            print(f"Wrote diff summary to {diff_path}")


def run_calendar_create(args) -> None:
    run_id = args.run_id or current_run_id()
    generated_at = current_timestamp()
    creds = load_credentials(
        args.credentials,
        args.token,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_SCOPE],
    )
    candidates = load_enriched_candidate_rows(args.input, args.limit, creds)
    previous_report_path = snapshot_single_output(args.report, DEFAULT_RUNS_DIR)
    try:
        result = create_calendar_events(
            candidates=candidates,
            calendar_service=build_calendar_service(creds),
            calendar_name=args.calendar_name,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Google Calendar create failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    write_calendar_action_report(
        path=args.report,
        result=result,
        calendar_name=args.calendar_name,
        source_csv=args.input,
    )
    write_calendar_create_json(
        path=args.json_report,
        result=result,
        calendar_name=args.calendar_name,
        source_csv=args.input,
        run_id=run_id,
        generated_at=generated_at,
        query=args.query,
        artifacts={
            "csv": str(args.input),
            "html": str(args.report),
        },
    )
    current_report_path = snapshot_single_output(args.report, DEFAULT_RUNS_DIR, suffix="calendar_create")

    print(
        f"Calendar create summary: created={result.created} skipped_existing={result.skipped_existing} "
        f"skipped_ambiguous={result.skipped_ambiguous} skipped_duplicate={result.skipped_duplicate} "
        f"failed={result.failed} dry_run={str(result.dry_run).lower()}"
    )
    for line in result.lines:
        print(line.render())
    if previous_report_path:
        print(f"Archived previous calendar report to {previous_report_path}")
    print(f"Archived current calendar report to {current_report_path}")
    print(f"Wrote structured calendar create JSON to {args.json_report}")


def run_calendar_preview(args) -> None:
    run_id = args.run_id or current_run_id()
    generated_at = current_timestamp()
    creds = load_credentials(
        args.credentials,
        args.token,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_SCOPE],
    )
    candidates = load_enriched_candidate_rows(args.input, args.limit, creds)
    try:
        rows = preview_calendar_events(
            candidates=candidates,
            calendar_service=build_calendar_service(creds),
            calendar_name=args.calendar_name,
        )
    except Exception as exc:
        print(f"Google Calendar preview failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    previous_report_path = snapshot_single_output(args.report, DEFAULT_RUNS_DIR)
    write_calendar_preview_report(
        path=args.report,
        rows=rows,
        calendar_name=args.calendar_name,
        source_csv=args.input,
    )
    write_calendar_preview_json(
        path=args.json_report,
        rows=rows,
        calendar_name=args.calendar_name,
        source_csv=args.input,
        run_id=run_id,
        generated_at=generated_at,
        query=args.query,
        artifacts={
            "csv": str(args.input),
            "html": str(args.report),
        },
    )
    current_report_path = snapshot_single_output(args.report, DEFAULT_RUNS_DIR, suffix="calendar_preview")

    print(f"Wrote {len(rows)} calendar preview rows to {args.report}")
    if previous_report_path:
        print(f"Archived previous calendar preview report to {previous_report_path}")
    print(f"Archived current calendar preview report to {current_report_path}")
    print(f"Wrote structured calendar preview JSON to {args.json_report}")


def run_pages_build(args) -> None:
    summary = build_pages_site(
        discover_json_path=args.discover_json,
        preview_json_path=args.preview_json,
        create_json_path=args.create_json,
        site_dir=args.site_dir,
        output_dir=args.output_dir,
    )
    print(
        f"Built Pages site for run {summary['run_id']} at {args.output_dir} "
        f"(candidates={summary['candidate_count']} created={summary['created']})"
    )


def write_csv(path: Path, candidates) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "gmail_id",
                "thread_id",
                "internal_datetime",
                "category",
                "confidence",
                "sender",
                "sender_email",
                "subject",
                "matched_dates",
                "matched_times",
                "reason_flags",
                "snippet",
            ],
        )
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "gmail_id": candidate.gmail_id,
                    "thread_id": candidate.thread_id,
                    "internal_datetime": candidate.internal_datetime,
                    "category": candidate.category,
                    "confidence": candidate.confidence,
                    "sender": candidate.sender,
                    "sender_email": candidate.sender_email,
                    "subject": candidate.subject,
                    "matched_dates": " | ".join(candidate.matched_dates),
                    "matched_times": " | ".join(candidate.matched_times),
                    "reason_flags": " | ".join(candidate.reason_flags),
                    "snippet": candidate.snippet,
                }
            )


def snapshot_previous_outputs(output_path: Path, report_path: Path, runs_dir: Path) -> tuple[Path | None, Path | None]:
    if not output_path.exists() and not report_path.exists():
        return None, None

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    run_dir = runs_dir / f"{stamp}_previous"
    run_dir.mkdir(parents=True, exist_ok=True)

    archived_csv = None
    archived_report = None
    if output_path.exists():
        archived_csv = run_dir / output_path.name
        shutil.copy2(output_path, archived_csv)
    if report_path.exists():
        archived_report = run_dir / report_path.name
        shutil.copy2(report_path, archived_report)
    return archived_csv, archived_report


def snapshot_current_outputs(output_path: Path, report_path: Path, runs_dir: Path) -> tuple[Path, Path]:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    run_dir = runs_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    archived_csv = run_dir / output_path.name
    archived_report = run_dir / report_path.name
    shutil.copy2(output_path, archived_csv)
    shutil.copy2(report_path, archived_report)
    return archived_csv, archived_report


def snapshot_single_output(path: Path, runs_dir: Path, suffix: str = "previous") -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    run_dir = runs_dir / f"{stamp}_{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    archived = run_dir / path.name
    shutil.copy2(path, archived)
    return archived


def read_candidates_from_csv(path: Path) -> list[Candidate]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        candidates = []
        for row in reader:
            candidates.append(
                Candidate(
                    gmail_id=row["gmail_id"],
                    thread_id=row["thread_id"],
                    internal_datetime=row["internal_datetime"],
                    category=row["category"],
                    confidence=int(row["confidence"]),
                    sender=row["sender"],
                    sender_email=row["sender_email"],
                    subject=row["subject"],
                    matched_dates=_split_pipe_field(row["matched_dates"]),
                    matched_times=_split_pipe_field(row["matched_times"]),
                    reason_flags=_split_pipe_field(row["reason_flags"]),
                    snippet=row["snippet"],
                )
            )
    return candidates


def load_enriched_candidate_rows(input_path: Path, limit: int | None, creds):
    candidates = limit_candidates(load_candidates(input_path), limit)
    if candidates:
        try:
            service = build_gmail_service(creds)
            message_records = fetch_messages(service, [row.candidate.gmail_id for row in candidates])
            candidates = enrich_candidate_rows(candidates, message_records)
        except Exception as exc:
            print(f"Calendar enrichment warning: {exc}", file=sys.stderr)
    return candidates


def _split_pipe_field(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    return tuple(part.strip() for part in value.split("|"))


if __name__ == "__main__":
    main()
