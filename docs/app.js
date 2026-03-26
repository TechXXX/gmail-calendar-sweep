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
    `Generated ${formatDateTime(discover.generated_at)} | Public dashboard shows summary-only data`;

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

  const categoryCounts = discover.summary.category_counts || {};
  const newCategoryCounts = discover.summary.new_category_counts || {};
  const discoverRows = Object.keys(categoryCounts).sort();
  document.querySelector("#discover-rows").innerHTML = discoverRows.length
    ? discoverRows
        .map(
          (category) => `
            <tr>
              <td>${pill(category)}</td>
              <td>${categoryCounts[category]}</td>
              <td>${newCategoryCounts[category] || 0}</td>
            </tr>
          `,
        )
        .join("")
    : emptyRow(3);

  const previewRows = Object.entries(preview.summary.outcome_counts || {});
  document.querySelector("#preview-rows").innerHTML = previewRows.length
    ? previewRows
        .map(
          ([outcome, count]) => `
            <tr>
              <td>${pill(outcome, outcome)}</td>
              <td>${count}</td>
            </tr>
          `,
        )
        .join("")
    : emptyRow(2);

  const createRows = Object.entries(create.summary.outcome_counts || {});
  document.querySelector("#create-rows").innerHTML = createRows.length
    ? createRows
        .map(
          ([outcome, count]) => `
            <tr>
              <td>${pill(outcome, outcome)}</td>
              <td>${count}</td>
            </tr>
          `,
        )
        .join("")
    : emptyRow(2);
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
    document.querySelector("#discover-rows").innerHTML = emptyRow(3, "Publish a run to populate the dashboard.");
    document.querySelector("#preview-rows").innerHTML = emptyRow(2, "Publish a run to populate the dashboard.");
    document.querySelector("#create-rows").innerHTML = emptyRow(2, "Publish a run to populate the dashboard.");
    document.querySelector("#history-rows").innerHTML = emptyRow(8, "Publish a run to populate the dashboard.");
  }
}

main();
