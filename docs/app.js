const emptyRow = (colspan = 1, message = "No data published yet.") =>
  `<tr><td colspan="${colspan}" class="empty">${message}</td></tr>`;

const formatDateTime = (value) => {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

const pill = (label, extraClass = "") =>
  `<span class="pill ${extraClass}">${label.replaceAll("_", " ")}</span>`;

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

function renderSummaryCards(index) {
  const runs = index.runs || [];
  const latest = runs[0];
  const cards = [
    { label: "Published Runs", value: runs.length || 0 },
    { label: "Latest Candidates", value: latest?.candidate_count ?? "n/a" },
    { label: "Latest Created", value: latest?.created ?? "n/a" },
    { label: "Latest New Rows", value: latest?.new_candidates ?? "n/a" },
  ];
  document.querySelector("#summary-cards").innerHTML = cards
    .map((card) => `<article class="card"><div class="card-label">${card.label}</div><div class="card-value">${card.value}</div></article>`)
    .join("");
}

function renderLatest(discover, preview, create) {
  document.querySelector("#latest-title").textContent = `Run ${discover.run_id}`;
  document.querySelector("#latest-meta").textContent =
    `Generated ${formatDateTime(discover.generated_at)} | Query: ${discover.query}`;

  const stats = [
    { label: "Candidates", value: discover.summary.candidate_count },
    { label: "New Candidates", value: discover.summary.new_candidates },
    { label: "Would Create", value: preview.summary.would_create },
    { label: "Created", value: create.summary.created },
    { label: "Skipped Existing", value: create.summary.skipped_existing },
  ];
  document.querySelector("#latest-stats").innerHTML = stats
    .map((stat) => `<article class="stat"><div class="stat-label">${stat.label}</div><div class="stat-value">${stat.value}</div></article>`)
    .join("");

  const discoverRows = discover.candidates || [];
  document.querySelector("#discover-rows").innerHTML = discoverRows.length
    ? discoverRows
        .map(
          (row) => `
            <tr>
              <td>${row.row_number}<br>${row.is_new ? pill("new", "new") : ""}</td>
              <td>${pill(row.category)}</td>
              <td>${row.subject}</td>
              <td>${row.snippet || "n/a"}</td>
              <td>${(row.matched_dates || []).join("<br>") || "n/a"}</td>
              <td>${(row.matched_times || []).join("<br>") || "n/a"}</td>
              <td>${row.sender_domain || "n/a"}</td>
            </tr>
          `,
        )
        .join("")
    : emptyRow(7);

  const previewRows = preview.rows || [];
  document.querySelector("#preview-rows").innerHTML = previewRows.length
    ? previewRows
        .map(
          (row) => `
            <tr>
              <td>${row.html_row_number}</td>
              <td>${pill(row.outcome, row.outcome)}</td>
              <td>${row.preview_title}</td>
              <td>${row.timing || "n/a"}</td>
            </tr>
          `,
        )
        .join("")
    : emptyRow(4);

  const createRows = create.lines || [];
  document.querySelector("#create-rows").innerHTML = createRows.length
    ? createRows
        .map(
          (row) => `
            <tr>
              <td>${row.html_row_number}</td>
              <td>${pill(row.outcome, row.outcome)}</td>
              <td>${row.subject}</td>
              <td>${row.detail || "n/a"}</td>
            </tr>
          `,
        )
        .join("")
    : emptyRow(4);
}

function renderHistory(index) {
  const rows = index.runs || [];
  document.querySelector("#history-rows").innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <tr>
              <td>${row.run_id}</td>
              <td>${formatDateTime(row.generated_at)}</td>
              <td>${row.query}</td>
              <td>${row.candidate_count}</td>
              <td>${row.new_candidates}</td>
              <td>${row.would_create}</td>
              <td>${row.created}</td>
              <td>${row.failed}</td>
            </tr>
          `,
        )
        .join("")
    : emptyRow(8);
}

async function main() {
  try {
    const [index, discover, preview, create] = await Promise.all([
      loadJson("./data/runs/index.json"),
      loadJson("./data/latest/discover.json"),
      loadJson("./data/latest/preview.json"),
      loadJson("./data/latest/create.json"),
    ]);
    renderSummaryCards(index);
    renderLatest(discover, preview, create);
    renderHistory(index);
  } catch (error) {
    document.querySelector("#summary-cards").innerHTML =
      `<article class="card"><div class="card-label">Status</div><div class="card-value">No data</div></article>`;
    document.querySelector("#latest-title").textContent = "No published runs";
    document.querySelector("#latest-meta").textContent = error.message;
    document.querySelector("#latest-stats").innerHTML = "";
    document.querySelector("#discover-rows").innerHTML = emptyRow(7, "Publish a run to populate the dashboard.");
    document.querySelector("#preview-rows").innerHTML = emptyRow(4, "Publish a run to populate the dashboard.");
    document.querySelector("#create-rows").innerHTML = emptyRow(4, "Publish a run to populate the dashboard.");
    document.querySelector("#history-rows").innerHTML = emptyRow(8, "Publish a run to populate the dashboard.");
  }
}

main();
