# Gmail Calendar Sweep

This repo now has two tracks:

- a local Python tool for broad Gmail discovery and CSV review
- the earlier Apps Script prototype, kept for reference and possible later automation

The Python tool is the current path. It scans Gmail through the Gmail API, looks for calendar-worthy candidates, writes a deterministic CSV/HTML review surface, and can create Google Calendar events through the Google Calendar API.

The repo now also includes a GitHub Pages-centered deployment path:

- GitHub Actions runs the existing Python pipeline on a daily schedule
- the workflow publishes a redacted static dashboard to `gh-pages`
- full CSV/HTML operator artifacts are uploaded as private workflow artifacts

## Local Python Tool

### What it does

- connects to Gmail with the read-only Gmail API
- requires an explicit Gmail query for discovery; there is no default scan window
- looks for likely travel, appointments, events, deadlines, and deliveries
- requires concrete scheduling evidence where possible to reduce false positives
- suppresses common noise sources such as newsletters, receipts, and generic promo mail
- writes stable CSV output to `/Users/kalter/Documents/CODEX/googlescript/output/candidates.csv`
- also writes an HTML review report to `/Users/kalter/Documents/CODEX/googlescript/output/candidates.html`
- also writes structured JSON output to `/Users/kalter/Documents/CODEX/googlescript/output/candidates.json`

### Setup

1. Create a Python virtual environment in `/Users/kalter/Documents/CODEX/googlescript`.
2. Install the package in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

3. In Google Cloud, enable both the Gmail API and the Google Calendar API, then create an OAuth Desktop App client.
4. Save the downloaded client JSON to `/Users/kalter/Documents/CODEX/googlescript/secrets/gmail_credentials.json`.
5. Run the scanner:

```bash
gmail-candidate-scan discover --query 'in:anywhere -in:chats newer_than:30d'
```

The first run opens a browser for consent and saves the token to `/Users/kalter/Documents/CODEX/googlescript/secrets/gmail_token.json`.

### Usage

```bash
gmail-candidate-scan \
  discover \
  --query 'in:anywhere -in:chats newer_than:30d' \
  --max-messages 3000 \
  --output /Users/kalter/Documents/CODEX/googlescript/output/candidates.csv \
  --report /Users/kalter/Documents/CODEX/googlescript/output/candidates.html \
  --json-report /Users/kalter/Documents/CODEX/googlescript/output/candidates.json
```

For backward compatibility, `gmail-candidate-scan --query ...` still runs discovery even without the explicit `discover` subcommand, but `--query` is now required.

### Create Google Calendar Events

Create events in Google Calendar from the current candidate CSV:

```bash
gmail-candidate-scan calendar-create --dry-run
gmail-candidate-scan calendar-create --limit 3
```

Behavior:

- reads from `/Users/kalter/Documents/CODEX/googlescript/output/candidates.csv` by default
- treats CSV order as the visible HTML sheet line item numbering, and uses those HTML row numbers when reporting actions
- enriches selected rows with the full Gmail message before generating Calendar titles and locations
- creates or reuses a dedicated Google Calendar named `Gmail Candidate Tests`
- embeds a stable Gmail message marker in Google Calendar event metadata and description to avoid duplicates on reruns
- skips ambiguous rows instead of guessing event times
- writes an HTML action report to `/Users/kalter/Documents/CODEX/googlescript/output/calendar_create.html`
- also writes structured JSON output to `/Users/kalter/Documents/CODEX/googlescript/output/calendar_create.json`
- will require one re-consent if your cached token was created before Calendar scopes were added

### Preview Google Calendar Events

```bash
gmail-candidate-scan calendar-preview
```

Behavior:

- reads from `/Users/kalter/Documents/CODEX/googlescript/output/candidates.csv` by default
- writes `/Users/kalter/Documents/CODEX/googlescript/output/calendar_preview.html`
- also writes `/Users/kalter/Documents/CODEX/googlescript/output/calendar_preview.json`

### Build the Static Pages Bundle

Build a publishable static site from the latest JSON outputs:

```bash
gmail-candidate-scan pages-build \
  --site-dir /Users/kalter/Documents/CODEX/googlescript/docs \
  --output-dir /Users/kalter/Documents/CODEX/googlescript/output/pages
```

This creates:

- `data/latest/` with the newest redacted discovery, preview, and create JSON
- `data/runs/<run_id>/` with timestamped historical snapshots
- `data/runs/index.json` for the run history index used by the dashboard

The published dashboard intentionally redacts sensitive content:

- no candidate-level subject, snippet, sender, timing, or location text
- no full Gmail body text
- only aggregate summary counts and category/outcome breakdowns are published

For local/operator use, full row-level review still lives in the private CSV/HTML outputs and workflow artifacts. Public GitHub Pages is intentionally summary-only.

### Non-Interactive Auth for CI

Interactive local OAuth is still the default for local development. For CI or GitHub Actions, set:

- `GMAIL_CANDIDATE_NONINTERACTIVE=1`
- `GMAIL_CANDIDATE_TOKEN_JSON` to an authorized user token JSON containing Gmail + Calendar scopes

In non-interactive mode the tool will:

- load the authorized token from the environment or token file
- refresh it when possible
- fail with a clear error instead of opening a browser if credentials are missing or under-scoped

### GitHub Pages Workflow

The repo includes `.github/workflows/publish_gmail_candidate_pages.yml`.

It:

- runs daily and also supports manual dispatch
- runs `discover`, `calendar-preview`, and `calendar-create`
- uploads the full `output/` directory as a private workflow artifact
- builds the redacted static dashboard from `docs/`
- updates the `gh-pages` branch with `latest/` and historical `runs/`

Expected repository configuration:

1. Add repository secret `GMAIL_CANDIDATE_TOKEN_JSON`.
2. Add repository variable `GMAIL_SCAN_QUERY` if you do not want the default `in:anywhere -in:chats newer_than:40d`.
3. Configure GitHub Pages to serve from the `gh-pages` branch root.

### CSV Columns

- `gmail_id`
- `thread_id`
- `internal_datetime`
- `category`
- `confidence`
- `sender`
- `sender_email`
- `subject`
- `matched_dates`
- `matched_times`
- `reason_flags`
- `snippet`

### Stability Notes

- Messages are fetched, normalized, and then sorted deterministically by Gmail internal timestamp and message ID before classification.
- CSV output is rewritten from scratch on each run for the same input set.
- JSON output is emitted alongside CSV/HTML so downstream automation and GitHub Pages can consume stable machine-readable data.
- The classifier is intentionally conservative: for most categories it requires explicit date or time evidence instead of generic keywords alone.

## Apps Script Prototype

The older Apps Script files are still here:

- `/Users/kalter/Documents/CODEX/googlescript/Code.js`
- `/Users/kalter/Documents/CODEX/googlescript/appsscript.json`

Those are useful as reference for category ideas and batching lessons, but they are not the primary implementation now. Once the discovery patterns are good enough, ongoing automation can still move back into Apps Script if that proves more convenient.
