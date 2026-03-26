# Gmail Calendar Sweep

Deterministic Gmail-to-Google-Calendar automation with:

- a public summary dashboard on GitHub Pages
- a scheduled GitHub Actions backend
- a local Python CLI for development, debugging, and first-time OAuth setup

Live dashboard:

- [techxxx.github.io/gmail-calendar-sweep](https://techxxx.github.io/gmail-calendar-sweep/)

Repository:

- [TechXXX/gmail-calendar-sweep](https://github.com/TechXXX/gmail-calendar-sweep)

## How It Works

The product has three layers:

- GitHub Actions runs the actual Gmail scan and Google Calendar write flow on a schedule
- GitHub Pages publishes a redacted public summary of the latest and historical runs
- the Python package remains the execution engine for discovery, preview, create, and dedupe

Current pipeline:

```bash
gmail-candidate-scan discover --query '...'
gmail-candidate-scan calendar-preview
gmail-candidate-scan calendar-create
gmail-candidate-scan pages-build
```

The system is deterministic:

- Gmail discovery is rule-based, not AI-driven
- parsing and extraction live in `gmail_candidate_scan/`
- Google Calendar duplicate prevention uses the Gmail message ID stored in Calendar metadata and description

## Public vs Private Data

Public GitHub Pages is intentionally summary-only.

Publicly exposed:

- total candidate counts
- category counts
- preview/create outcome counts
- run timestamps
- the configured Gmail query string

Not publicly exposed:

- Gmail credentials or OAuth tokens
- raw email bodies
- candidate-level subjects or snippets
- sender emails
- per-row preview/create details
- full CSV or HTML operator reports

Private operator outputs stay in GitHub Actions artifacts and local files under `output/`.

## Hosted Automation

The repository includes `.github/workflows/publish_gmail_candidate_pages.yml`.

It:

- runs on a daily schedule
- also supports manual workflow dispatch
- runs discovery, preview, create, and Pages build
- uploads full `output/` artifacts privately in GitHub Actions
- can optionally email a private weekly ZIP candidate summary on Mondays (Europe/Berlin)
- publishes the redacted dashboard to `gh-pages`

Required GitHub configuration:

- repository secret: `GMAIL_CANDIDATE_TOKEN_JSON`
- optional repository variable: `GMAIL_SCAN_QUERY`
- optional repository variable: `GMAIL_WEEKLY_SUMMARY_QUERY`
- GitHub Pages source: `gh-pages` branch, `/ (root)`

Optional email delivery secrets:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `OPERATOR_EMAIL_TO`
- `OPERATOR_EMAIL_FROM` (optional, defaults to `SMTP_USERNAME`)

Email delivery behavior:

- if the SMTP secrets are present, the workflow sends a ZIP attachment on Mondays in the `Europe/Berlin` timezone
- the ZIP includes `weekly_candidates.html`, `weekly_candidates.csv`, and `weekly_candidates.json`
- the weekly summary is generated from a separate seven-day discovery query and does not change the daily preview/create run
- this is more convenient than downloading artifacts manually, but it moves private candidate data into your email inbox

## Local Development

The Python CLI is still the source of truth for the product behavior. Local usage matters for:

- first-time OAuth consent
- debugging parser/extraction logic
- backfills and one-off scans
- validating behavior before changing the scheduled workflow

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

In Google Cloud:

1. Enable Gmail API and Google Calendar API.
2. Create an OAuth Desktop App client.
3. Save the client JSON to `/Users/kalter/Documents/CODEX/googlescript/secrets/gmail_credentials.json`.

The first interactive run will save the authorized token to:

- `/Users/kalter/Documents/CODEX/googlescript/secrets/gmail_token.json`

### Common Commands

Discovery:

```bash
gmail-candidate-scan \
  discover \
  --query 'in:anywhere -in:chats newer_than:40d'
```

Preview Calendar writes:

```bash
gmail-candidate-scan calendar-preview
```

Create Calendar events:

```bash
gmail-candidate-scan calendar-create
```

Build the static Pages bundle locally:

```bash
gmail-candidate-scan pages-build \
  --site-dir /Users/kalter/Documents/CODEX/googlescript/docs \
  --output-dir /Users/kalter/Documents/CODEX/googlescript/output/pages
```

### Local Outputs

Discovery writes:

- `output/candidates.csv`
- `output/candidates.html`
- `output/candidates.json`

Preview writes:

- `output/calendar_preview.html`
- `output/calendar_preview.json`

Create writes:

- `output/calendar_create.html`
- `output/calendar_create.json`

Pages build writes:

- `output/pages/data/latest/`
- `output/pages/data/runs/<run_id>/`
- `output/pages/data/runs/index.json`

## CI Auth

Local development uses interactive OAuth by default.

CI and GitHub Actions use non-interactive auth:

- `GMAIL_CANDIDATE_NONINTERACTIVE=1`
- `GMAIL_CANDIDATE_TOKEN_JSON=<authorized token json>`

In non-interactive mode the tool:

- loads the authorized token from env or token file
- refreshes it when possible
- fails instead of opening a browser if the token is missing or under-scoped

## Implementation Notes

The current implementation is all deterministic heuristics plus Google APIs.

Key modules:

- `gmail_candidate_scan/extraction.py`
- `gmail_candidate_scan/calendar_integration.py`
- `gmail_candidate_scan/cli.py`

Behavioral notes:

- discovery output is sorted deterministically by Gmail internal timestamp and Gmail message ID
- Google Calendar dedupe is based on Gmail message ID
- the classifier is intentionally conservative and requires timing evidence for many categories

## Apps Script

The older Apps Script prototype is still in the repo:

- `Code.js`
- `appsscript.json`

It is reference material only. The active implementation is the Python package plus GitHub Actions and GitHub Pages.
