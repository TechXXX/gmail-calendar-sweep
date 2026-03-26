from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gmail_candidate_scan.pages_builder import _candidate_hash, build_pages_site


class PagesBuilderTests(unittest.TestCase):
    def test_build_pages_site_redacts_and_marks_new_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            site_dir = root / "site"
            site_dir.mkdir()
            (site_dir / "index.html").write_text("<!doctype html><title>site</title>", encoding="utf-8")

            output_dir = root / "published"
            (output_dir / "data" / "latest").mkdir(parents=True)
            previous_candidate_row = {
                "gmail_id": "same-id",
                "category": "travel",
                "matched_dates": ["1 Apr 2026"],
                "matched_times": ["10:00"],
            }
            previous_discover = {
                "run_id": "20260325_090000",
                "generated_at": "2026-03-25T09:00:00+00:00",
                "query": "old",
                "summary": {"candidate_count": 1, "scanned_message_count": 3, "top_category": "travel (1)", "highest_confidence": 5, "new_candidates": 1},
                "candidate_hashes": [_candidate_hash(previous_candidate_row)],
            }
            (output_dir / "data" / "latest" / "discover.json").write_text(
                json.dumps(previous_discover),
                encoding="utf-8",
            )

            discover_payload = {
                "run_id": "20260326_101500",
                "generated_at": "2026-03-26T10:15:00+00:00",
                "query": "in:anywhere -in:chats newer_than:40d",
                "summary": {
                    "candidate_count": 2,
                    "scanned_message_count": 10,
                    "top_category": "travel (2)",
                    "highest_confidence": 6,
                },
                "candidates": [
                    {
                        "gmail_id": "same-id",
                        "thread_id": "thread-1",
                        "internal_datetime": "2026-03-26T09:00:00+00:00",
                        "category": "travel",
                        "confidence": 6,
                        "sender": "Airbnb",
                        "sender_email": "host@example.com",
                        "subject": "Trip to Bangkok 12345",
                        "matched_dates": ["1 Apr 2026"],
                        "matched_times": ["10:00"],
                        "reason_flags": ["category:travel"],
                        "snippet": "Check-in details 12345",
                        "row_number": 1,
                    },
                    {
                        "gmail_id": "new-id",
                        "thread_id": "thread-2",
                        "internal_datetime": "2026-03-26T09:30:00+00:00",
                        "category": "event",
                        "confidence": 4,
                        "sender": "Tickets",
                        "sender_email": "notify@tickets.test",
                        "subject": "Concert invite jane@example.com",
                        "matched_dates": ["2 Apr 2026"],
                        "matched_times": [],
                        "reason_flags": ["category:event"],
                        "snippet": "Call +49 555 123456 for entry.",
                        "row_number": 2,
                    },
                ],
            }
            preview_payload = {
                "run_id": "20260326_101500",
                "generated_at": "2026-03-26T10:16:00+00:00",
                "query": "in:anywhere -in:chats newer_than:40d",
                "calendar_name": "Gmail Candidate Tests",
                "summary": {
                    "row_count": 2,
                    "would_create": 1,
                    "skipped_existing": 1,
                    "skipped_ambiguous": 0,
                    "skipped_duplicate": 0,
                },
                "rows": [
                    {
                        "html_row_number": 1,
                        "source_subject": "Trip to Bangkok 12345",
                        "preview_title": "Stay in Bangkok 9999",
                        "outcome": "would_create",
                        "timing": "1 Apr 2026",
                        "location": "Private address",
                        "category": "travel",
                    }
                ],
            }
            create_payload = {
                "run_id": "20260326_101500",
                "generated_at": "2026-03-26T10:17:00+00:00",
                "query": "in:anywhere -in:chats newer_than:40d",
                "calendar_name": "Gmail Candidate Tests",
                "summary": {
                    "created": 1,
                    "skipped_existing": 1,
                    "skipped_ambiguous": 0,
                    "skipped_duplicate": 0,
                    "failed": 0,
                    "dry_run": False,
                },
                "lines": [
                    {
                        "html_row_number": 1,
                        "subject": "Stay in Bangkok 9999",
                        "outcome": "created",
                        "detail": "Room 4567",
                    }
                ],
            }

            discover_path = root / "discover.json"
            preview_path = root / "preview.json"
            create_path = root / "create.json"
            discover_path.write_text(json.dumps(discover_payload), encoding="utf-8")
            preview_path.write_text(json.dumps(preview_payload), encoding="utf-8")
            create_path.write_text(json.dumps(create_payload), encoding="utf-8")

            summary = build_pages_site(discover_path, preview_path, create_path, site_dir, output_dir)

            self.assertEqual(summary["run_id"], "20260326_101500")
            latest_discover = json.loads((output_dir / "data" / "latest" / "discover.json").read_text(encoding="utf-8"))
            latest_preview = json.loads((output_dir / "data" / "latest" / "preview.json").read_text(encoding="utf-8"))
            latest_create = json.loads((output_dir / "data" / "latest" / "create.json").read_text(encoding="utf-8"))
            history = json.loads((output_dir / "data" / "runs" / "index.json").read_text(encoding="utf-8"))

            self.assertEqual(latest_discover["summary"]["new_candidates"], 1)
            self.assertEqual(latest_discover["summary"]["category_counts"]["travel"], 1)
            self.assertEqual(latest_discover["summary"]["category_counts"]["event"], 1)
            self.assertEqual(latest_discover["summary"]["new_category_counts"]["event"], 1)
            self.assertNotIn("candidates", latest_discover)
            self.assertEqual(latest_preview["summary"]["outcome_counts"]["would_create"], 1)
            self.assertEqual(latest_create["summary"]["outcome_counts"]["created"], 1)
            self.assertEqual(history["latest_run_id"], "20260326_101500")
            self.assertEqual(history["runs"][0]["candidate_count"], 2)


if __name__ == "__main__":
    unittest.main()
