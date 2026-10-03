const discoverForm = document.getElementById("discover-form");
const discoverFormCompact = document.getElementById("discover-form-compact");
const discoverQuery = document.getElementById("discover-query");
const discoverQueryCompact = document.getElementById("discover-query-compact");
const discoverLimit = document.getElementById("discover-limit");
const discoverSourcesEl = document.getElementById("discover-sources");
const btnDiscover = document.getElementById("btn-discover");
const btnAnalyze = document.getElementById("btn-analyze");
const btnSelectAll = document.getElementById("btn-select-all");
const btnSelectNone = document.getElementById("btn-select-none");
const landing = document.getElementById("landing");
const resultsView = document.getElementById("results-view");
const serpResults = document.getElementById("serp-results");
const serpStats = document.getElementById("serp-stats");
const insightsSection = document.getElementById("insights-section");
const overlay = document.getElementById("overlay");
const overlayText = document.getElementById("overlay-text");
const errorSection = document.getElementById("error-section");
const errorText = document.getElementById("error-text");
const formHint = document.getElementById("form-hint");

let sourcePresets = [];
let isLoading = false;
let discoveredEntries = [];
let lastQuery = "";
let lastSearchMs = 0;
const MAX_ANALYZE_ENTRIES = 50;
/** id → original post URL from last live crawl (for analysis links) */
let postUrlById = {};

const DEFAULT_DISCOVER_SOURCES = [
  { id: "stackexchange", label: "Stack Exchange Q&A", defaultOn: true },
  { id: "hackernews", label: "Hacker News", defaultOn: true },
  { id: "playstore", label: "Google Play reviews", defaultOn: true },
  { id: "reddit", label: "Reddit (public JSON)", defaultOn: true },
];

const STAGE_CLASS = {
  "Expression Failure": "stage-expression",
  "Interpretation Failure": "stage-interpretation",
  "Evaluation Failure": "stage-evaluation",
  "Refinement Failure": "stage-refinement",
};

function setLoading(on, message = "Searching the web…") {
  isLoading = on;
  overlay.classList.toggle("hidden", !on);
  overlayText.textContent = message;
  btnDiscover.disabled = on;
  if (btnAnalyze) btnAnalyze.disabled = on || selectedCount() === 0;
  resultsView.querySelectorAll(".btn-search").forEach((b) => {
    b.disabled = on;
  });
}

function showApiError(message) {
  errorSection.classList.remove("hidden");
  errorText.textContent = message;
}

function hideApiError() {
  errorSection.classList.add("hidden");
}

function showFormHint(message) {
  formHint.textContent = message;
  formHint.classList.remove("hidden");
}

function hideFormHint() {
  formHint.classList.add("hidden");
  formHint.textContent = "";
}

function ensureDiscoverSourcesRendered() {
  if (discoverSourcesEl.querySelector('input[name="discover-source"]')) return;
  discoverSourcesEl.innerHTML = "<legend>Sources</legend>";
  for (const src of DEFAULT_DISCOVER_SOURCES) {
    const label = document.createElement("label");
    label.className = "source-check";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "discover-source";
    input.value = src.id;
    input.checked = src.defaultOn;
    label.appendChild(input);
    label.append(` ${src.label}`);
    discoverSourcesEl.appendChild(label);
  }
}

function selectedDiscoverSources() {
  return [...discoverSourcesEl.querySelectorAll('input[name="discover-source"]:checked')].map(
    (el) => el.value
  );
}

function activeQueryInput() {
  return document.body.classList.contains("mode-results")
    ? discoverQueryCompact
    : discoverQuery;
}

async function checkServerHealth() {
  const res = await fetch("api/health");
  if (!res.ok) {
    throw new Error(
      "Server not running or outdated. Run: py -3 -m src.web_app"
    );
  }
  const health = await res.json();
  if (!health.endpoints?.discover) {
    throw new Error("Restart the server: py -3 -m src.web_app");
  }
  return health;
}

function apiErrorMessage(res, body) {
  if (res.status === 404) {
    return "API not found — restart the server: py -3 -m src.web_app";
  }
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return res.statusText || "Request failed";
}

async function loadMeta() {
  await checkServerHealth();
  const res = await fetch("api/meta");
  if (!res.ok) throw new Error("Could not load app settings.");
  const meta = await res.json();
  sourcePresets = meta.source_presets || [];
  const el = document.getElementById("model-label");
  if (el && meta.model) {
    const fb = meta.llm_fallback ? ` → ${meta.llm_fallback}` : "";
    el.textContent = `${meta.provider}: ${meta.model}${fb}`;
  }
}

async function loadResearchFramework() {
  const res = await fetch("api/research-questions");
  if (!res.ok) return;
  const data = await res.json();
  renderResearchFramework(data.catalog, data.suggested_searches || []);
}

function renderResearchFramework(catalog, searches) {
  const container = document.getElementById("research-categories");
  if (!container || !catalog?.categories) return;

  container.innerHTML = catalog.categories
    .map(
      (cat) => `
      <details class="research-category">
        <summary>${escapeHtml(cat.title)} <span class="research-q-count">${(cat.questions || []).length} questions</span></summary>
        <ul>
          ${(cat.questions || [])
            .map(
              (q) =>
                `<li><strong>${escapeHtml(q.question)}</strong>${
                  q.insight_goal
                    ? `<span class="research-q-goal">${escapeHtml(q.insight_goal)}</span>`
                    : ""
                }</li>`
            )
            .join("")}
        </ul>
      </details>`
    )
    .join("");

  const chips = document.getElementById("suggested-chips");
  if (!chips) return;
  chips.innerHTML = searches
    .map(
      (q) =>
        `<button type="button" class="chip-btn" data-query="${escapeAttr(q)}">${escapeHtml(q)}</button>`
    )
    .join("");
  chips.querySelectorAll(".chip-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      discoverQuery.value = btn.dataset.query;
      discoverQueryCompact.value = btn.dataset.query;
      discoverFromWeb(btn.dataset.query);
    });
  });
}

function titleFromText(text) {
  const line = (text || "").split("\n")[0].trim();
  if (!line) return "Discussion snippet";
  return line.length > 100 ? `${line.slice(0, 97)}…` : line;
}

function snippetFromText(text) {
  const flat = (text || "").replace(/\s+/g, " ").trim();
  return flat.length > 260 ? `${flat.slice(0, 257)}…` : flat;
}

function displayUrl(url, source) {
  if (!url) return source || "Web";
  try {
    const u = new URL(url);
    return `${u.hostname}${u.pathname.length > 1 ? u.pathname : ""}`;
  } catch {
    return url;
  }
}

function selectedCount() {
  return serpResults.querySelectorAll('input[type="checkbox"]:checked').length;
}

function updateAnalyzeButton() {
  const n = selectedCount();
  btnAnalyze.disabled = isLoading || n === 0;
  btnAnalyze.textContent = n ? `Analyze selected (${n})` : "Analyze selected";
}

function showResultsView() {
  document.body.classList.remove("mode-landing");
  document.body.classList.add("mode-results");
  landing.classList.add("hidden");
  resultsView.classList.remove("hidden");
  if (discoverQueryCompact) discoverQueryCompact.value = lastQuery;
}

function serpItemHtml(entry, index, checked = true) {
  const title = titleFromText(entry.raw_text);
  const snippet = snippetFromText(entry.raw_text);
  const urlLine = displayUrl(entry.url, entry.source);
  const href = entry.url || "#";
  const linkAttrs = entry.url
    ? `href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer"`
    : 'href="#" aria-disabled="true"';
  const checkedAttr = checked ? "checked" : "";

  return `
    <article class="serp-item" data-index="${index}">
      <input type="checkbox" class="serp-check" id="serp-${index}" data-index="${index}" ${checkedAttr} aria-label="Include in analysis" />
      <div class="serp-body">
        <label for="serp-${index}" class="serp-select-hint">Include</label>
        <a class="serp-title" ${linkAttrs}>${escapeHtml(title)}</a>
        <div class="serp-url">${escapeHtml(urlLine)}</div>
        <p class="serp-snippet">${escapeHtml(snippet)}</p>
        <span class="serp-source">${escapeHtml(entry.source)}</span>
      </div>
    </article>`;
}

function bindSerpCheckboxes(root) {
  root.querySelectorAll(".serp-check").forEach((box) => {
    box.addEventListener("change", updateAnalyzeButton);
  });
}

function renderSerp(payload, metaLine) {
  discoveredEntries = payload.entries || [];
  serpResults.innerHTML = discoveredEntries
    .map((entry, index) => serpItemHtml(entry, index, true))
    .join("");
  bindSerpCheckboxes(serpResults);

  lastQuery = payload.query || lastQuery;
  if (metaLine) {
    serpStats.textContent = metaLine;
  } else {
    const seconds = (lastSearchMs / 1000).toFixed(2);
    serpStats.textContent = `About ${payload.count} results (${seconds} seconds) · live crawl · query: “${lastQuery}”`;
  }

  insightsSection.classList.add("hidden");
  updateAnalyzeButton();
  showResultsView();
}

function getSelectedEntries() {
  const selected = [];
  serpResults.querySelectorAll(".serp-check:checked").forEach((box) => {
    const idx = Number(box.dataset.index);
    if (discoveredEntries[idx]) selected.push(discoveredEntries[idx]);
  });
  return selected;
}

async function discoverFromWeb(queryOverride) {
  hideApiError();
  hideFormHint();
  insightsSection.classList.add("hidden");

  const query =
    queryOverride !== undefined && queryOverride !== null
      ? String(queryOverride).trim()
      : activeQueryInput().value.trim();
  if (query.length < 3) {
    showFormHint("Enter at least 3 characters to search.");
    return;
  }

  const sources = selectedDiscoverSources();
  if (!sources.length) {
    showFormHint("Select at least one source.");
    return;
  }

  discoverQuery.value = query;
  discoverQueryCompact.value = query;
  lastQuery = query;

  setLoading(true, "Searching public discussions…");
  const started = performance.now();

  try {
    const res = await fetch("api/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        limit: Number(discoverLimit.value),
        sources,
      }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(apiErrorMessage(res, body));

    lastSearchMs = performance.now() - started;
    renderSerp(body);

    const warn = (body.warnings || []).filter(Boolean);
    if (warn.length) {
      showFormHint(warn.join(" · "));
    } else {
      showFormHint(`Showing ${body.count} results relevant to Google Photos search & retrieval.`);
    }
  } catch (err) {
    showApiError(err.message);
  } finally {
    setLoading(false);
  }
}

async function runAnalysis() {
  hideApiError();
  let entries = getSelectedEntries().map(({ id, source, raw_text }) => ({
    id: id || undefined,
    source,
    raw_text,
  }));

  if (!entries.length) {
    showFormHint("Select at least one row to analyze.");
    return;
  }

  if (entries.length > MAX_ANALYZE_ENTRIES) {
    showFormHint(
      `Only the first ${MAX_ANALYZE_ENTRIES} selected rows can be analyzed per run (API limit).`
    );
    entries = entries.slice(0, MAX_ANALYZE_ENTRIES);
  } else {
    hideFormHint();
  }

  const batchNote =
    entries.length > 4
      ? ` (server runs ~${Math.ceil(entries.length / 4)} LLM batches; may take several minutes)`
      : "";
  setLoading(
    true,
    `Analyzing ${entries.length} item${entries.length === 1 ? "" : "s"}…${batchNote}`
  );
  refreshPostUrlMap();

  try {
    const res = await fetch("api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries, dry_run: false }),
    });
    let body;
    try {
      body = await res.json();
    } catch {
      body = {};
    }
    if (!res.ok) {
      throw new Error(apiErrorMessage(res, body) || "Analysis failed. Check OPENROUTER_API_KEY in .env.");
    }
    renderAnalysis(body);
    hideFormHint();
  } catch (err) {
    showApiError(err.message);
  } finally {
    setLoading(false);
    updateAnalyzeButton();
  }
}

function renderAnalysis(data) {
  insightsSection.classList.remove("hidden");
  document.getElementById("total-badge").textContent = `${data.total_analyzed} analyzed`;

  const researchEl = document.getElementById("research-insights");
  if (researchEl) {
    researchEl.innerHTML = (data.research_insights || [])
      .map(
        (item) => `
        <article class="research-answer">
          <p class="research-q">${escapeHtml(item.question)}</p>
          <p class="research-finding">${escapeHtml(item.finding)}</p>
          <p class="research-meta">Confidence: ${escapeHtml(item.confidence)}</p>
          <p class="research-meta research-posts">Posts: ${formatPostLinks(item.supporting_ids || [])}</p>
        </article>`
      )
      .join("");
  }

  const counts = data.summary_metrics.failure_stage_counts;
  document.getElementById("metrics").innerHTML = Object.entries(counts)
    .map(
      ([label, value]) => `
      <div class="metric-card">
        <div class="label">${escapeHtml(label)}</div>
        <div class="value">${value}</div>
      </div>`
    )
    .join("");

  renderRankList("clues-list", data.summary_metrics.top_remembered_clues, "clue");
  renderRankList("forgotten-list", data.summary_metrics.top_forgotten_metadata, "metadata");
  document.getElementById("insights").innerHTML = data.insights
    .map((item, index) => renderInsight(item, index))
    .join("");

  insightsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderRankList(id, items, key) {
  const rows = items || [];
  document.getElementById(id).innerHTML = rows.length
    ? rows
        .map(
          (row) =>
            `<li><span>${escapeHtml(row[key])}</span><strong>${row.count}</strong></li>`
        )
        .join("")
    : `<li class="rank-empty"><span>No tags in this batch</span></li>`;
}

function renderInsight(item, index) {
  const stageClass = STAGE_CLASS[item.failure_stage] || "stage-interpretation";
  return `
    <article class="insight-card">
      <div class="insight-head">
        <span class="insight-id">Result ${index + 1}</span>
        <span class="stage-pill ${stageClass}">${escapeHtml(item.failure_stage)}</span>
        <span class="photo-type">${escapeHtml(item.target_photo_type)}</span>
      </div>
      <p class="quote">"${escapeHtml(item.raw_text)}"</p>
      ${originalPostLink(item.id)}
      <p class="hint">${escapeHtml(item.source)} · ${escapeHtml(item.user_search_formulation)} · id: ${escapeHtml(item.id || "")}</p>
      <dl class="grid-meta">
        <div>
          <dt>Remembered clues</dt>
          <dd class="chips">${chips(item.remembered_clues)}</dd>
        </div>
        <div>
          <dt>Forgotten metadata</dt>
          <dd class="chips">${chips(item.forgotten_metadata)}</dd>
        </div>
      </dl>
      <p class="opportunity"><strong>Opportunity:</strong> ${escapeHtml(item.opportunity_area)}</p>
    </article>`;
}

function chips(arr) {
  return (arr || []).map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join("");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/'/g, "&#39;");
}

function refreshPostUrlMap() {
  postUrlById = {};
  for (const entry of discoveredEntries) {
    if (entry.id && entry.url) {
      postUrlById[entry.id] = entry.url;
    }
  }
}

function formatPostLinks(ids) {
  if (!ids || !ids.length) {
    return '<span class="post-link-missing">—</span>';
  }
  return ids
    .map((id) => {
      const url = postUrlById[id];
      if (url) {
        return `<a class="post-ref-link" href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer" title="${escapeAttr(url)}">${escapeHtml(id)}</a>`;
      }
      return `<span class="post-ref-id" title="No URL for this id">${escapeHtml(id)}</span>`;
    })
    .join("");
}

function originalPostLink(id) {
  const url = id ? postUrlById[id] : null;
  if (!url) return "";
  return `<p class="post-source-link-wrap"><a class="post-source-link" href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">Open original post</a> <span class="post-source-url">${escapeHtml(displayUrl(url, ""))}</span></p>`;
}

function goHome() {
  hideApiError();
  hideFormHint();
  insightsSection.classList.add("hidden");
  discoveredEntries = [];
  serpResults.innerHTML = "";
  document.body.classList.remove("mode-results");
  document.body.classList.add("mode-landing");
  landing.classList.remove("hidden");
  resultsView.classList.add("hidden");
  history.replaceState(null, "", "/");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function wireUi() {
  document.getElementById("btn-home")?.addEventListener("click", goHome);
}

discoverForm.addEventListener("submit", (e) => {
  e.preventDefault();
  discoverFromWeb();
});

discoverFormCompact.addEventListener("submit", (e) => {
  e.preventDefault();
  discoverFromWeb(discoverQueryCompact.value.trim());
});

btnAnalyze?.addEventListener("click", () => runAnalysis());
btnSelectAll.addEventListener("click", () => {
  serpResults.querySelectorAll(".serp-check").forEach((c) => {
    c.checked = true;
  });
  updateAnalyzeButton();
});
btnSelectNone.addEventListener("click", () => {
  serpResults.querySelectorAll(".serp-check").forEach((c) => {
    c.checked = false;
  });
  updateAnalyzeButton();
});

async function init() {
  wireUi();
  ensureDiscoverSourcesRendered();
  try {
    await loadMeta();
    await loadResearchFramework();
  } catch (e) {
    showApiError(`${e.message}`);
  }
}

init();
