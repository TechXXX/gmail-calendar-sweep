from __future__ import annotations

from pathlib import Path
import html

from .calendar_integration import CalendarActionLine, CalendarCreateResult, CalendarPreviewRow


def write_calendar_action_report(
    path: Path,
    result: CalendarCreateResult,
    calendar_name: str,
    source_csv: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(_action_row(line) for line in result.lines)
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Google Calendar Create Report</title>
  <style>
    body {{
      margin: 0;
      padding: 18px;
      background: #f3f6fa;
      color: #223042;
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    }}
    .panel {{
      background: #fff;
      border: 1px solid #d6dde8;
      margin-bottom: 16px;
      box-shadow: 0 8px 24px rgba(34, 48, 66, 0.08);
    }}
    .head {{
      padding: 14px 16px;
      border-bottom: 1px solid #d6dde8;
      background: #eef3f9;
      font-weight: 600;
    }}
    .sub {{
      padding: 12px 16px;
      color: #637287;
      border-bottom: 1px solid #d6dde8;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid #d6dde8;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
      white-space: pre-wrap;
    }}
    th {{ background: #f7f9fc; }}
  </style>
</head>
<body>
  <section class="panel">
    <div class="head">Google Calendar Create Summary</div>
    <div class="sub">Target Google Calendar: {html.escape(calendar_name)} | Source CSV: {html.escape(str(source_csv))} | Dry run: {str(result.dry_run).lower()}</div>
    <table>
      <thead>
        <tr>
          <th>Created</th>
          <th>Skipped Existing</th>
          <th>Skipped Ambiguous</th>
          <th>Skipped Duplicate</th>
          <th>Failed</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>{result.created}</td>
          <td>{result.skipped_existing}</td>
          <td>{result.skipped_ambiguous}</td>
          <td>{result.skipped_duplicate}</td>
          <td>{result.failed}</td>
        </tr>
      </tbody>
    </table>
  </section>
  <section class="panel">
    <div class="head">Per-row Actions</div>
    <table>
      <thead>
        <tr><th>HTML Row</th><th>Event Title</th><th>Outcome</th><th>Detail</th></tr>
      </thead>
      <tbody>
        {lines}
      </tbody>
    </table>
  </section>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _action_row(line: CalendarActionLine) -> str:
    detail = line.detail or ""
    return (
        "<tr>"
        f"<td>{line.html_row_number}</td>"
        f"<td>{html.escape(line.subject)}</td>"
        f"<td>{html.escape(line.outcome)}</td>"
        f"<td>{html.escape(detail)}</td>"
        "</tr>"
    )


def write_calendar_preview_report(
    path: Path,
    rows: tuple[CalendarPreviewRow, ...],
    calendar_name: str,
    source_csv: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body_rows = "".join(_preview_row(row) for row in rows)
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Google Calendar Preview Sheet</title>
  <style>
    :root {{
      --grid: #d6dde8;
      --head: #eef3f9;
      --subhead: #f7f9fc;
      --text: #223042;
      --muted: #637287;
      --sheet: #ffffff;
      --bg: #f3f6fa;
      --would-create: #e8f5f2;
      --skipped-existing: #eaf2ff;
      --skipped-ambiguous: #fff4df;
      --skipped-duplicate: #f8eaff;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; }}
    .wrap {{ padding: 18px; }}
    .sheet {{ background: var(--sheet); border: 1px solid var(--grid); box-shadow: 0 8px 24px rgba(34, 48, 66, 0.08); }}
    .sheet-head {{ padding: 16px 18px 10px; border-bottom: 1px solid var(--grid); background: linear-gradient(180deg, #fdfefe 0%, #f6f9fd 100%); }}
    h1 {{ margin: 0 0 8px; font-size: 1.1rem; font-weight: 600; }}
    .meta {{ margin: 0; color: var(--muted); font-size: 0.92rem; line-height: 1.5; }}
    .summary {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 8px; margin-top: 12px; }}
    .summary div {{ padding: 8px 10px; background: var(--subhead); border: 1px solid var(--grid); font-size: 0.9rem; }}
    .summary strong {{ display: block; margin-bottom: 2px; font-size: 0.74rem; letter-spacing: 0.03em; text-transform: uppercase; color: var(--muted); font-weight: 600; }}
    .table-wrap {{ overflow: auto; }}
    table {{ width: 100%; min-width: 1560px; border-collapse: collapse; table-layout: fixed; font-size: 13px; }}
    thead th {{ position: sticky; top: 0; z-index: 2; background: var(--head); border: 1px solid var(--grid); padding: 8px 10px; text-align: left; font-weight: 600; white-space: nowrap; }}
    tbody td {{ border: 1px solid var(--grid); padding: 8px 10px; vertical-align: top; word-break: break-word; white-space: pre-wrap; line-height: 1.35; }}
    tbody tr.outcome-would_create td {{ background: linear-gradient(90deg, var(--would-create) 0, var(--would-create) 6px, transparent 6px); }}
    tbody tr.outcome-skipped_existing td {{ background: linear-gradient(90deg, var(--skipped-existing) 0, var(--skipped-existing) 6px, transparent 6px); }}
    tbody tr.outcome-skipped_ambiguous td {{ background: linear-gradient(90deg, var(--skipped-ambiguous) 0, var(--skipped-ambiguous) 6px, transparent 6px); }}
    tbody tr.outcome-skipped_duplicate_confirmed_preferred td {{ background: linear-gradient(90deg, var(--skipped-duplicate) 0, var(--skipped-duplicate) 6px, transparent 6px); }}
    .tight {{ white-space: nowrap; }}
    .center {{ text-align: center; }}
    .small {{ color: var(--muted); font-size: 12px; }}
    col.index {{ width: 70px; }}
    col.category {{ width: 90px; }}
    col.outcome {{ width: 150px; }}
    col.source_subject {{ width: 320px; }}
    col.preview_title {{ width: 360px; }}
    col.timing {{ width: 260px; }}
    col.location {{ width: 320px; }}
    @media (max-width: 900px) {{
      .wrap {{ padding: 8px; }}
      .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="sheet">
      <div class="sheet-head">
        <h1>Google Calendar Preview Sheet</h1>
        <p class="meta">Target Google Calendar: {html.escape(calendar_name)}<br>Source CSV: {html.escape(str(source_csv))}</p>
        <div class="summary">
          <div><strong>Rows</strong>{len(rows)}</div>
          <div><strong>Would Create</strong>{sum(1 for row in rows if row.outcome == "would_create")}</div>
          <div><strong>Skipped Existing</strong>{sum(1 for row in rows if row.outcome == "skipped_existing")}</div>
          <div><strong>Skipped Ambiguous</strong>{sum(1 for row in rows if row.outcome == "skipped_ambiguous")}</div>
          <div><strong>Skipped Duplicate</strong>{sum(1 for row in rows if row.outcome == "skipped_duplicate_confirmed_preferred")}</div>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <colgroup>
            <col class="index">
            <col class="category">
            <col class="outcome">
            <col class="source_subject">
            <col class="preview_title">
            <col class="timing">
            <col class="location">
          </colgroup>
          <thead>
            <tr>
              <th>HTML Row</th>
              <th>Category</th>
              <th>Outcome</th>
              <th>Source Subject</th>
              <th>Preview Title</th>
              <th>Timing</th>
              <th>Location</th>
            </tr>
          </thead>
          <tbody>
            {body_rows or '<tr><td colspan="7">No preview rows available.</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _preview_row(row: CalendarPreviewRow) -> str:
    return (
        f'<tr class="outcome-{html.escape(row.outcome)}">'
        f'<td class="center tight">{row.html_row_number}</td>'
        f'<td class="tight">{html.escape(row.category)}</td>'
        f'<td class="tight">{html.escape(row.outcome)}</td>'
        f'<td>{html.escape(row.source_subject)}</td>'
        f'<td>{html.escape(row.preview_title)}</td>'
        f'<td class="small">{html.escape(row.timing)}</td>'
        f'<td>{html.escape(row.location)}</td>'
        "</tr>"
    )
