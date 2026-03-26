from __future__ import annotations

from collections import Counter
from datetime import datetime
import html
from pathlib import Path


def write_html_report(path: Path, candidates, scanned_message_count: int, query: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    category_counts = Counter(candidate.category for candidate in candidates)
    confidence_counts = Counter(candidate.confidence for candidate in candidates)

    summary = [
        ("Candidates", str(len(candidates))),
        ("Messages Scanned", str(scanned_message_count)),
        ("Top Category", _top_category_label(category_counts)),
        ("Highest Confidence", str(max(confidence_counts) if confidence_counts else 0)),
    ]
    table_rows = "".join(_candidate_row(index + 1, candidate) for index, candidate in enumerate(candidates))

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gmail Candidate Sheet</title>
  <style>
    :root {{
      --grid: #d6dde8;
      --head: #eef3f9;
      --subhead: #f7f9fc;
      --text: #223042;
      --muted: #637287;
      --sheet: #ffffff;
      --bg: #f3f6fa;
      --travel: #e8f5f2;
      --appointment: #eaf2ff;
      --event: #f3ecff;
      --deadline: #fff4df;
      --delivery: #ffe8ee;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    }}
    .wrap {{
      padding: 18px;
    }}
    .sheet {{
      background: var(--sheet);
      border: 1px solid var(--grid);
      box-shadow: 0 8px 24px rgba(34, 48, 66, 0.08);
    }}
    .sheet-head {{
      padding: 16px 18px 10px;
      border-bottom: 1px solid var(--grid);
      background: linear-gradient(180deg, #fdfefe 0%, #f6f9fd 100%);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 1.1rem;
      font-weight: 600;
    }}
    .meta {{
      margin: 0;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }}
    .summary div {{
      padding: 8px 10px;
      background: var(--subhead);
      border: 1px solid var(--grid);
      font-size: 0.9rem;
    }}
    .summary strong {{
      display: block;
      margin-bottom: 2px;
      font-size: 0.74rem;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 600;
    }}
    .table-wrap {{
      overflow: auto;
    }}
    table {{
      width: 100%;
      min-width: 1720px;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 13px;
    }}
    thead th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: var(--head);
      border: 1px solid var(--grid);
      padding: 8px 10px;
      text-align: left;
      font-weight: 600;
      white-space: nowrap;
    }}
    tbody td {{
      border: 1px solid var(--grid);
      padding: 8px 10px;
      vertical-align: top;
      word-break: break-word;
      white-space: pre-wrap;
      line-height: 1.35;
    }}
    tbody tr:nth-child(even) {{
      background: #fbfcfe;
    }}
    tbody tr.category-travel td {{
      background: linear-gradient(90deg, var(--travel) 0, var(--travel) 6px, transparent 6px);
    }}
    tbody tr.category-appointment td {{
      background: linear-gradient(90deg, var(--appointment) 0, var(--appointment) 6px, transparent 6px);
    }}
    tbody tr.category-event td {{
      background: linear-gradient(90deg, var(--event) 0, var(--event) 6px, transparent 6px);
    }}
    tbody tr.category-deadline td {{
      background: linear-gradient(90deg, var(--deadline) 0, var(--deadline) 6px, transparent 6px);
    }}
    tbody tr.category-delivery td {{
      background: linear-gradient(90deg, var(--delivery) 0, var(--delivery) 6px, transparent 6px);
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .center {{
      text-align: center;
    }}
    .tight {{
      white-space: nowrap;
    }}
    .small {{
      color: var(--muted);
      font-size: 12px;
    }}
    col.index {{ width: 56px; }}
    col.internal_datetime {{ width: 148px; }}
    col.category {{ width: 96px; }}
    col.confidence {{ width: 88px; }}
    col.sender {{ width: 220px; }}
    col.sender_email {{ width: 210px; }}
    col.subject {{ width: 340px; }}
    col.matched_dates {{ width: 170px; }}
    col.matched_times {{ width: 170px; }}
    col.reason_flags {{ width: 280px; }}
    col.snippet {{ width: 500px; }}
    col.gmail_id {{ width: 150px; }}
    col.thread_id {{ width: 150px; }}
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
        <h1>Gmail Candidate Sheet</h1>
        <p class="meta">Generated {html.escape(generated_at)}<br>Query: {html.escape(query)}</p>
        <div class="summary">
          {''.join(_summary_cell(label, value) for label, value in summary)}
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <colgroup>
            <col class="index">
            <col class="internal_datetime">
            <col class="category">
            <col class="confidence">
            <col class="sender">
            <col class="sender_email">
            <col class="subject">
            <col class="matched_dates">
            <col class="matched_times">
            <col class="reason_flags">
            <col class="snippet">
            <col class="gmail_id">
            <col class="thread_id">
          </colgroup>
          <thead>
            <tr>
              <th>#</th>
              <th>Internal Datetime</th>
              <th>Category</th>
              <th>Confidence</th>
              <th>Sender</th>
              <th>Sender Email</th>
              <th>Subject</th>
              <th>Matched Dates</th>
              <th>Matched Times</th>
              <th>Reason Flags</th>
              <th>Snippet</th>
              <th>Gmail ID</th>
              <th>Thread ID</th>
            </tr>
          </thead>
          <tbody>
            {table_rows or '<tr><td colspan="13">No candidates matched the current rules.</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def write_diff_html_report(path: Path, previous_candidates, current_candidates) -> None:
    previous_map = {_candidate_key(candidate): candidate for candidate in previous_candidates}
    current_map = {_candidate_key(candidate): candidate for candidate in current_candidates}

    removed = [previous_map[key] for key in previous_map.keys() - current_map.keys()]
    added = [current_map[key] for key in current_map.keys() - previous_map.keys()]
    removed.sort(key=lambda item: (item.internal_datetime, item.gmail_id))
    added.sort(key=lambda item: (item.internal_datetime, item.gmail_id))

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gmail Candidate Diff</title>
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
    .empty {{ padding: 14px 16px; color: #637287; }}
  </style>
</head>
<body>
  <section class="panel">
    <div class="head">Run Diff Summary</div>
    <div class="sub">Added: {len(added)} | Removed: {len(removed)} | Unchanged: {len(previous_map.keys() & current_map.keys())}</div>
  </section>
  {_diff_table("Removed Candidates", removed)}
  {_diff_table("Added Candidates", added)}
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _summary_cell(label: str, value: str) -> str:
    return f"<div><strong>{html.escape(label)}</strong>{html.escape(value)}</div>"


def _top_category_label(category_counts: Counter[str]) -> str:
    if not category_counts:
        return "None"
    category, count = category_counts.most_common(1)[0]
    return f"{category} ({count})"


def _candidate_row(index: int, candidate) -> str:
    return (
        f'<tr class="category-{html.escape(candidate.category)}">'
        f'<td class="center tight">{index}</td>'
        f'<td class="tight">{html.escape(_pretty_datetime(candidate.internal_datetime))}</td>'
        f'<td class="tight">{html.escape(candidate.category)}</td>'
        f'<td class="center tight">{candidate.confidence}</td>'
        f'<td>{html.escape(candidate.sender)}</td>'
        f'<td class="small">{html.escape(candidate.sender_email)}</td>'
        f'<td>{html.escape(candidate.subject)}</td>'
        f'<td>{html.escape(_fallback_join(candidate.matched_dates))}</td>'
        f'<td>{html.escape(_fallback_join(candidate.matched_times))}</td>'
        f'<td>{html.escape(_fallback_join(candidate.reason_flags))}</td>'
        f'<td>{html.escape(candidate.snippet)}</td>'
        f'<td class="mono">{html.escape(candidate.gmail_id)}</td>'
        f'<td class="mono">{html.escape(candidate.thread_id)}</td>'
        "</tr>"
    )


def _fallback_join(values) -> str:
    return " | ".join(values) if values else ""


def _pretty_datetime(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def _candidate_key(candidate) -> tuple[str, str, str]:
    return (candidate.gmail_id, candidate.category, candidate.subject)


def _diff_table(title: str, candidates) -> str:
    if not candidates:
        return f'<section class="panel"><div class="head">{html.escape(title)}</div><div class="empty">None</div></section>'
    rows = "".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{html.escape(_pretty_datetime(candidate.internal_datetime))}</td>"
        f"<td>{html.escape(candidate.category)}</td>"
        f"<td>{html.escape(candidate.subject)}</td>"
        f"<td>{html.escape(candidate.sender)}</td>"
        f"<td>{html.escape(_fallback_join(candidate.matched_dates))}</td>"
        f"<td>{html.escape(_fallback_join(candidate.matched_times))}</td>"
        f"<td>{html.escape(candidate.snippet)}</td>"
        "</tr>"
        for index, candidate in enumerate(candidates, start=1)
    )
    return (
        f'<section class="panel"><div class="head">{html.escape(title)}</div>'
        "<table>"
        "<thead><tr><th>#</th><th>Internal Datetime</th><th>Category</th><th>Subject</th><th>Sender</th><th>Matched Dates</th><th>Matched Times</th><th>Snippet</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></section>"
    )
