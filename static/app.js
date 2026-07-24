/* ===================================================================
   app.js — Behavior Scoring Frontend
   Handles all tabs: Score, History, Analytics, Compare, Batch
   =================================================================== */

// ---- DOM References ----
const healthBanner = document.getElementById("health-banner");
const form = document.getElementById("score-form");
const submitBtn = document.getElementById("submit-btn");
const errorBox = document.getElementById("error-box");
const resultPanel = document.getElementById("result-panel");
const resultContent = document.getElementById("result-content");
const historyTableBody = document.querySelector("#history-table tbody");
const historyStats = document.getElementById("history-stats");

// ---- Tab Navigation ----
const tabBtns = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");

tabBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabBtns.forEach((b) => b.classList.remove("active"));
    tabContents.forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");

    if (btn.dataset.tab === "tab-history") loadHistory();
    if (btn.dataset.tab === "tab-analytics") loadAnalytics();
  });
});

// ---- Health Check ----
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.ollama.reachable && data.ollama.model_available_locally) {
      healthBanner.textContent = `Connected — model "${data.ollama.configured_model}"`;
      healthBanner.className = "health-banner ok";
    } else if (data.ollama.reachable) {
      healthBanner.textContent = `Ollama up, but model "${data.ollama.configured_model}" not found. Run: ollama pull ${data.ollama.configured_model}`;
      healthBanner.className = "health-banner error";
    } else {
      healthBanner.textContent = `Cannot reach Ollama. Is "ollama serve" running?`;
      healthBanner.className = "health-banner error";
    }
  } catch {
    healthBanner.textContent = "Cannot reach the backend API.";
    healthBanner.className = "health-banner error";
  }
}

// ---- Utilities ----
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function badgeHtml(status, type = "flag") {
  const cls = status || "pending";
  return `<span class="badge ${cls}">${cls}</span>`;
}

function formatTime(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  } catch {
    return isoStr;
  }
}

function truncate(str, len = 40) {
  if (!str) return "";
  return str.length > len ? str.substring(0, len) + "…" : str;
}

// ---- Score Form ----
let inFlightScoreRequest = null;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.hidden = true;

  const payload = {
    candidate_label: document.getElementById("candidate_label").value.trim(),
    job_role: document.getElementById("job_role").value.trim(),
    cv_claims: document.getElementById("cv_claims").value,
    profile_about: document.getElementById("profile_about").value,
    posts_sample: document.getElementById("posts_sample").value,
    comments_sample: document.getElementById("comments_sample").value,
    network_notes: document.getElementById("network_notes").value,
  };

  if (!payload.candidate_label) {
    errorBox.hidden = false;
    errorBox.textContent = "Candidate label is required.";
    return;
  }

  const hasAnyText = [payload.cv_claims, payload.profile_about, payload.posts_sample, payload.comments_sample, payload.network_notes].some(
    (v) => v && v.trim().length > 0
  );
  if (!hasAnyText) {
    errorBox.hidden = false;
    errorBox.textContent = "Fill in at least one text field before scoring.";
    return;
  }

  if (inFlightScoreRequest) inFlightScoreRequest.abort();
  const controller = new AbortController();
  inFlightScoreRequest = controller;

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Scoring… (calling local LLM)`;

  try {
    const res = await fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Request failed with status ${res.status}`);
    }
    const result = await res.json();
    renderResult(result);
    loadHistory();
  } catch (err) {
    if (err.name === "AbortError") return;
    errorBox.hidden = false;
    errorBox.textContent = err.message;
  } finally {
    if (inFlightScoreRequest === controller) {
      inFlightScoreRequest = null;
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Run Scoring`;
    }
  }
});

// ---- Render Score Result ----
function renderResult(result) {
  resultPanel.hidden = false;
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  const dims = result.dimension_scores
    .map(
      (d) => `
      <div class="dim-row">
        <div style="flex:1">
          <div><strong>${escapeHtml(d.label)}</strong></div>
          <div class="dim-rationale">${escapeHtml(d.rationale)}</div>
          <div class="dim-bar-track"><div class="dim-bar-fill" style="width:${d.score}%"></div></div>
        </div>
        <div class="dim-score">${d.score}</div>
      </div>`
    )
    .join("");

  const excluded = result.excluded_attributes_detected.length
    ? `<p style="margin-top:12px"><strong>Excluded attributes noticed:</strong> ${result.excluded_attributes_detected.map(escapeHtml).join(", ")}</p>`
    : "";

  let prettyRaw = result.raw_model_output;
  try { prettyRaw = JSON.stringify(JSON.parse(result.raw_model_output), null, 2); } catch {}

  const summaryText = result.overall_summary ? escapeHtml(result.overall_summary) : "(no summary returned)";
  const jobRoleLine = result.job_role ? `<span class="meta-text" style="margin-left:8px">Role: ${escapeHtml(result.job_role)}</span>` : "";
  const hrStatus = result.human_review ? result.human_review.status : "pending";

  resultContent.innerHTML = `
    <div class="summary-box">
      <div class="summary-header">
        <span class="summary-badge">Overall Candidate Summary</span>
        ${jobRoleLine}
      </div>
      <p class="summary-text">${summaryText}</p>
    </div>

    <p class="muted-text">Composite score (weighted, red flag excluded):</p>
    <div class="composite">${result.composite_score} / 100</div>

    <p style="margin-top:16px">
      ${badgeHtml(result.red_flag.status)} Red Flag — ${escapeHtml(result.red_flag.rationale)}
    </p>
    <p style="margin-top:8px">
      Human Review: ${badgeHtml(hrStatus)}
    </p>

    <h3 style="margin-top:20px; font-size:14px; font-weight:700;">Dimension Breakdown</h3>
    ${dims}
    ${excluded}

    <p class="meta-text" style="margin-top:16px">
      Rubric v${result.rubric_version} · hash: ${result.rubric_hash || "n/a"}
      · model: ${escapeHtml(result.model_used)} · run #${result.id || "—"}
      · ${result.created_at || ""}
    </p>

    <details class="raw-output">
      <summary>Show raw model output</summary>
      <pre>${escapeHtml(prettyRaw)}</pre>
    </details>
  `;
}

// ---- History (with filters) ----
let historyCache = [];

function getFilterParams() {
  const params = new URLSearchParams();
  const search = document.getElementById("filter-search").value.trim();
  const rfStatus = document.getElementById("filter-red-flag").value;
  const hrStatus = document.getElementById("filter-human-review").value;
  const minScore = document.getElementById("filter-min-score").value;
  const maxScore = document.getElementById("filter-max-score").value;
  const sortBy = document.getElementById("filter-sort-by").value;
  const sortOrder = document.getElementById("filter-sort-order").value;

  params.set("limit", "50");
  params.set("offset", "0");
  if (search) params.set("search", search);
  if (rfStatus) params.set("red_flag_status", rfStatus);
  if (hrStatus) params.set("human_review_status", hrStatus);
  if (minScore) params.set("min_score", minScore);
  if (maxScore) params.set("max_score", maxScore);
  params.set("sort_by", sortBy);
  params.set("sort_order", sortOrder);
  return params;
}

async function loadHistory() {
  try {
    const params = getFilterParams();
    const res = await fetch(`/api/scores?${params.toString()}`);
    const data = await res.json();
    const rows = Array.isArray(data) ? data : data.results || [];
    const total = data.total || rows.length;
    historyCache = rows;

    historyStats.textContent = `Showing ${rows.length} of ${total} result${total !== 1 ? "s" : ""}`;

    historyTableBody.innerHTML = rows
      .map((r) => {
        const hrStatus = r.human_review ? r.human_review.status : "pending";
        return `
        <tr data-id="${r.id}">
          <td>${r.id}</td>
          <td class="cell-truncate" title="${escapeHtml(r.candidate_label)}"><strong>${escapeHtml(truncate(r.candidate_label, 16))}</strong></td>
          <td class="cell-truncate" title="${escapeHtml(r.job_role || "")}">${escapeHtml(truncate(r.job_role || "—", 14))}</td>
          <td class="cell-truncate" title="${escapeHtml(r.overall_summary || "")}">${escapeHtml(truncate(r.overall_summary || "—", 30))}</td>
          <td><strong>${r.composite_score}</strong></td>
          <td>${badgeHtml(r.red_flag.status)}</td>
          <td>${badgeHtml(hrStatus)}</td>
          <td class="meta-text">${formatTime(r.created_at)}</td>
          <td>
            <div class="actions-cell">
              <button class="btn btn-ghost btn-xs action-view" data-id="${r.id}" title="View details">👁</button>
              <button class="btn btn-review-status btn-xs action-review" data-id="${r.id}" title="Human review">✎</button>
              <button class="btn btn-danger btn-xs action-delete" data-id="${r.id}" title="Delete">✕</button>
            </div>
          </td>
        </tr>`;
      })
      .join("");

    // Attach action handlers
    document.querySelectorAll(".action-view").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openDetailModal(parseInt(btn.dataset.id, 10));
      });
    });

    document.querySelectorAll(".action-review").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openReviewModal(parseInt(btn.dataset.id, 10));
      });
    });

    document.querySelectorAll(".action-delete").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id, 10);
        if (!confirm(`Delete score run #${id}? This cannot be undone.`)) return;
        try {
          const res = await fetch(`/api/scores/${id}`, { method: "DELETE" });
          if (!res.ok) throw new Error("Failed to delete");
          loadHistory();
        } catch (err) {
          alert("Error deleting: " + err.message);
        }
      });
    });

    // Row click opens detail (skip if any action button was clicked)
    historyTableBody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest(".actions-cell")) return;
        openDetailModal(parseInt(tr.dataset.id, 10));
      });
      tr.style.cursor = "pointer";
    });
  } catch {
    historyTableBody.innerHTML = `<tr><td colspan="9" class="muted-text">Could not load history.</td></tr>`;
  }
}

// ---- Filter Actions ----
document.getElementById("apply-filters-btn").addEventListener("click", loadHistory);
document.getElementById("clear-filters-btn").addEventListener("click", () => {
  document.getElementById("filter-search").value = "";
  document.getElementById("filter-red-flag").value = "";
  document.getElementById("filter-human-review").value = "";
  document.getElementById("filter-min-score").value = "";
  document.getElementById("filter-max-score").value = "";
  document.getElementById("filter-sort-by").value = "id";
  document.getElementById("filter-sort-order").value = "desc";
  loadHistory();
});
document.getElementById("refresh-history").addEventListener("click", loadHistory);

// Enter key in search triggers filter
document.getElementById("filter-search").addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadHistory();
});

// ---- Export ----
document.getElementById("export-csv-btn").addEventListener("click", () => {
  const params = getFilterParams();
  params.set("format", "csv");
  params.delete("limit");
  params.delete("offset");
  window.open(`/api/scores/export?${params.toString()}`, "_blank");
});

document.getElementById("export-json-btn").addEventListener("click", () => {
  const params = getFilterParams();
  params.set("format", "json");
  params.delete("limit");
  params.delete("offset");
  window.open(`/api/scores/export?${params.toString()}`, "_blank");
});

// ---- Modal Helpers ----
const detailModal = document.getElementById("detail-modal");
const detailModalBody = document.getElementById("detail-modal-body");
const detailModalTitle = document.getElementById("detail-modal-title");
const reviewModal = document.getElementById("review-modal");
const reviewModalLabel = document.getElementById("review-modal-label");

function closeAllModals() {
  detailModal.hidden = true;
  reviewModal.hidden = true;
}

// ESC key closes any open modal
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeAllModals();
});

// ---- Detail Modal ----
document.getElementById("detail-modal-close").addEventListener("click", closeAllModals);
detailModal.addEventListener("click", (e) => {
  if (e.target === detailModal) closeAllModals();
});

async function openDetailModal(id) {
  closeAllModals();
  detailModal.hidden = false;
  detailModalTitle.textContent = `Score #${id}`;
  detailModalBody.innerHTML = `<p class="muted-text">Loading…</p>`;

  try {
    const res = await fetch(`/api/scores/${id}`);
    if (!res.ok) throw new Error("Not found");
    const data = await res.json();

    const dims = data.dimension_scores
      .map(
        (d) => `
        <div class="dim-row">
          <div style="flex:1">
            <div><strong>${escapeHtml(d.label)}</strong></div>
            <div class="dim-rationale">${escapeHtml(d.rationale)}</div>
            <div class="dim-bar-track"><div class="dim-bar-fill" style="width:${d.score}%"></div></div>
          </div>
          <div class="dim-score">${d.score}</div>
        </div>`
      )
      .join("");

    const excluded = (data.excluded_attributes_detected || []).length
      ? `<p><strong>Excluded attributes:</strong> ${data.excluded_attributes_detected.map(escapeHtml).join(", ")}</p>`
      : "";

    const hrStatus = data.human_review ? data.human_review.status : "pending";
    const hrNotes = data.human_review && data.human_review.notes ? escapeHtml(data.human_review.notes) : "(none)";
    const hrTime = data.human_review && data.human_review.reviewed_at ? formatTime(data.human_review.reviewed_at) : "—";

    let prettyRaw = data.raw_model_output || "";
    try { prettyRaw = JSON.stringify(JSON.parse(prettyRaw), null, 2); } catch {}

    detailModalBody.innerHTML = `
      <div class="summary-box">
        <div class="summary-header">
          <span class="summary-badge">Summary</span>
          ${data.job_role ? `<span class="meta-text">Role: ${escapeHtml(data.job_role)}</span>` : ""}
        </div>
        <p class="summary-text">${escapeHtml(data.overall_summary || "(none)")}</p>
      </div>

      <p class="muted-text">Composite Score:</p>
      <div class="composite">${data.composite_score} / 100</div>

      <p style="margin-top:12px">${badgeHtml(data.red_flag.status)} Red Flag — ${escapeHtml(data.red_flag.rationale)}</p>

      <div style="margin-top:12px; padding:10px; background:var(--glass); border-radius:var(--radius-xs); border:1px solid var(--glass-border);">
        <p><strong>Human Review:</strong> ${badgeHtml(hrStatus)}</p>
        <p class="meta-text">Notes: ${hrNotes}</p>
        <p class="meta-text">Reviewed at: ${hrTime}</p>
      </div>

      <h3 style="margin-top:16px; font-size:13px; font-weight:700;">Dimensions</h3>
      ${dims}
      ${excluded}

      <p class="meta-text" style="margin-top:14px">
        Rubric v${data.rubric_version} · hash: ${data.rubric_hash || "n/a"}
        · model: ${escapeHtml(data.model_used)} · ${formatTime(data.created_at)}
      </p>

      <details class="raw-output">
        <summary>Raw model output</summary>
        <pre>${escapeHtml(prettyRaw)}</pre>
      </details>
    `;
  } catch {
    detailModalBody.innerHTML = `<p class="muted-text">Could not load score detail.</p>`;
  }
}

// ---- Human Review Modal ----
let reviewTargetId = null;

document.getElementById("review-modal-close").addEventListener("click", closeAllModals);
document.getElementById("review-cancel-btn").addEventListener("click", closeAllModals);
reviewModal.addEventListener("click", (e) => {
  if (e.target === reviewModal) closeAllModals();
});

function openReviewModal(id) {
  closeAllModals();
  reviewTargetId = id;
  const row = historyCache.find((r) => r.id === id);
  const currentStatus = row && row.human_review ? row.human_review.status : "pending";
  const currentNotes = row && row.human_review ? row.human_review.notes : "";

  reviewModalLabel.textContent = `Score #${id} — ${row ? row.candidate_label : ""}`;
  document.getElementById("review-status").value = currentStatus;
  document.getElementById("review-notes").value = currentNotes;
  reviewModal.hidden = false;
}

document.getElementById("review-save-btn").addEventListener("click", async () => {
  if (!reviewTargetId) return;
  const status = document.getElementById("review-status").value;
  const notes = document.getElementById("review-notes").value;

  try {
    const res = await fetch(`/api/scores/${reviewTargetId}/review`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, notes }),
    });
    if (!res.ok) throw new Error("Failed to update review");
    reviewModal.hidden = true;
    loadHistory();
  } catch (err) {
    alert("Error saving review: " + err.message);
  }
});

// ---- Analytics ----
async function loadAnalytics() {
  const container = document.getElementById("analytics-content");
  container.innerHTML = `<p class="muted-text">Loading analytics…</p>`;

  try {
    const res = await fetch("/api/scores/analytics");
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();

    const stats = data.composite_score_stats;
    const rf = data.red_flag_breakdown;
    const hr = data.human_review_breakdown;
    const buckets = data.score_buckets;
    const excludedAttrs = data.excluded_attributes_counts || {};

    // Find max bucket for bar scaling
    const bucketValues = Object.values(buckets);
    const maxBucket = Math.max(...bucketValues, 1);

    const bucketLabels = {
      "0_to_20": "0–20",
      "21_to_40": "21–40",
      "41_to_60": "41–60",
      "61_to_80": "61–80",
      "81_to_100": "81–100",
    };

    const barsHtml = Object.entries(buckets)
      .map(([k, v]) => {
        const pct = (v / maxBucket) * 100;
        return `
        <div class="bar-col">
          <div class="bar-count">${v}</div>
          <div class="bar-fill" style="height:${Math.max(pct, 3)}%"></div>
          <div class="bar-label">${bucketLabels[k] || k}</div>
        </div>`;
      })
      .join("");

    const rfItems = Object.entries(rf)
      .map(([k, v]) => `<div class="breakdown-item"><div class="breakdown-count" style="color:var(--${k})">${v}</div><div class="breakdown-label">${k}</div></div>`)
      .join("");

    const hrItems = Object.entries(hr)
      .map(([k, v]) => `<div class="breakdown-item"><div class="breakdown-count" style="color:var(--${k})">${v}</div><div class="breakdown-label">${k}</div></div>`)
      .join("");

    const excludedHtml = Object.keys(excludedAttrs).length
      ? Object.entries(excludedAttrs)
          .map(([attr, count]) => `<div class="breakdown-item"><div class="breakdown-count" style="color:var(--review)">${count}</div><div class="breakdown-label">${escapeHtml(truncate(attr, 20))}</div></div>`)
          .join("")
      : `<p class="muted-text">No excluded attributes detected across any runs.</p>`;

    container.innerHTML = `
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-value">${data.total_candidates}</div><div class="stat-label">Total Scored</div></div>
        <div class="stat-card"><div class="stat-value">${stats.avg}</div><div class="stat-label">Avg Score</div></div>
        <div class="stat-card"><div class="stat-value">${stats.median}</div><div class="stat-label">Median</div></div>
        <div class="stat-card"><div class="stat-value">${stats.min}</div><div class="stat-label">Min</div></div>
        <div class="stat-card"><div class="stat-value">${stats.max}</div><div class="stat-label">Max</div></div>
      </div>

      <div class="chart-section">
        <h3>Score Distribution</h3>
        <div class="bar-chart">${barsHtml}</div>
      </div>

      <div class="chart-section">
        <h3>Red Flag Breakdown</h3>
        <div class="breakdown-grid">${rfItems}</div>
      </div>

      <div class="chart-section">
        <h3>Human Review Status</h3>
        <div class="breakdown-grid">${hrItems}</div>
      </div>

      <div class="chart-section">
        <h3>Excluded Attributes Detected</h3>
        <div class="breakdown-grid">${excludedHtml}</div>
      </div>
    `;
  } catch {
    container.innerHTML = `<p class="muted-text">Failed to load analytics.</p>`;
  }
}

document.getElementById("refresh-analytics-btn").addEventListener("click", loadAnalytics);

// ---- Compare ----
document.getElementById("compare-btn").addEventListener("click", async () => {
  const idsStr = document.getElementById("compare-ids").value.trim();
  const container = document.getElementById("compare-content");

  if (!idsStr) {
    container.innerHTML = `<p class="muted-text">Enter comma-separated score IDs to compare.</p>`;
    return;
  }

  container.innerHTML = `<p class="muted-text">Loading comparison…</p>`;

  try {
    const res = await fetch(`/api/scores/compare?ids=${encodeURIComponent(idsStr)}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Comparison failed");
    }
    const data = await res.json();

    const cards = data.candidates
      .map((c) => {
        const dimsHtml = c.dimension_scores
          .map(
            (d) => `
            <div class="compare-dim-item">
              <div class="compare-dim-score">${d.score}</div>
              <div class="compare-dim-label">${escapeHtml(truncate(d.label, 18))}</div>
            </div>`
          )
          .join("");

        const hrStatus = c.human_review ? c.human_review.status : "pending";
        const isHighest = c.candidate_label === data.highest_scoring_candidate;
        const isLowest = c.candidate_label === data.lowest_scoring_candidate;
        let indicator = "";
        if (isHighest) indicator = `<span class="badge approved" style="margin-left:8px">Highest</span>`;
        if (isLowest) indicator = `<span class="badge rejected" style="margin-left:8px">Lowest</span>`;

        return `
        <div class="compare-card">
          <div class="compare-card-header">
            <div>
              <div class="compare-card-title">${escapeHtml(c.candidate_label)} ${indicator}</div>
              <div class="meta-text">${c.job_role ? escapeHtml(c.job_role) : "No role specified"} · ${badgeHtml(c.red_flag.status)} · Review: ${badgeHtml(hrStatus)}</div>
            </div>
            <div class="compare-card-score">${c.composite_score}</div>
          </div>
          <div class="compare-dims">${dimsHtml}</div>
        </div>`;
      })
      .join("");

    const avgHtml = Object.entries(data.dimension_averages)
      .map(([k, v]) => `<span><strong>${escapeHtml(k)}:</strong> ${v}</span>`)
      .join(" · ");

    const rfSummary = Object.entries(data.red_flags_summary)
      .map(([k, v]) => `<span>${k}: <strong>${v}</strong></span>`)
      .join(" · ");

    container.innerHTML = `
      <div class="compare-grid">${cards}</div>
      <div class="compare-summary-row">
        <h3>Dimension Averages</h3>
        <div class="compare-meta">${avgHtml}</div>
      </div>
      <div class="compare-summary-row" style="margin-top:8px">
        <h3>Red Flags Summary</h3>
        <div class="compare-meta">${rfSummary}</div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<p class="muted-text">${escapeHtml(err.message)}</p>`;
  }
});

// ---- Batch Scoring ----
document.getElementById("batch-submit-btn").addEventListener("click", async () => {
  const jsonInput = document.getElementById("batch-json").value.trim();
  const statusArea = document.getElementById("batch-status");
  const submitBatchBtn = document.getElementById("batch-submit-btn");

  if (!jsonInput) {
    statusArea.innerHTML = `<p class="muted-text">Enter a JSON array of candidate profiles.</p>`;
    return;
  }

  let profiles;
  try {
    profiles = JSON.parse(jsonInput);
    if (!Array.isArray(profiles) || profiles.length === 0) throw new Error("Must be a non-empty array");
  } catch (err) {
    statusArea.innerHTML = `<div class="error-box">Invalid JSON: ${escapeHtml(err.message)}</div>`;
    return;
  }

  submitBatchBtn.disabled = true;
  submitBatchBtn.textContent = "Submitting…";
  statusArea.innerHTML = `<p class="muted-text">Submitting batch…</p>`;

  try {
    const res = await fetch("/api/scores/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profiles }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Batch submission failed");
    }
    const data = await res.json();
    const batchId = data.batch_id;

    statusArea.innerHTML = `
      <div class="batch-progress">
        <p>Batch <strong>${batchId}</strong> submitted (${data.total_items} profiles). Polling for results…</p>
        <div class="progress-bar-track"><div class="progress-bar-fill" id="batch-progress-fill" style="width:0%"></div></div>
      </div>
      <div class="batch-results-list" id="batch-results-list"></div>
    `;

    // Poll
    pollBatch(batchId, data.total_items);
  } catch (err) {
    statusArea.innerHTML = `<div class="error-box">${escapeHtml(err.message)}</div>`;
  } finally {
    submitBatchBtn.disabled = false;
    submitBatchBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Submit Batch`;
  }
});

async function pollBatch(batchId, totalItems) {
  const progressFill = document.getElementById("batch-progress-fill");
  const resultsList = document.getElementById("batch-results-list");
  let attempts = 0;
  const maxAttempts = 120; // 10 min max polling

  const poll = async () => {
    if (attempts >= maxAttempts) {
      resultsList.innerHTML += `<div class="batch-item"><span class="muted-text">Polling timed out. Check batch status manually.</span></div>`;
      return;
    }
    attempts++;

    try {
      const res = await fetch(`/api/scores/batch/${batchId}`);
      if (!res.ok) return;
      const data = await res.json();

      const completed = data.completed_items + data.failed_items;
      const pct = totalItems > 0 ? (completed / totalItems) * 100 : 0;
      if (progressFill) progressFill.style.width = `${pct}%`;

      resultsList.innerHTML = data.results
        .map((r) => {
          const statusBadge = r.status === "completed" ? badgeHtml("pass") : badgeHtml("fail");
          const score = r.score_result ? r.score_result.composite_score : "—";
          return `<div class="batch-item">
            <span><strong>${escapeHtml(r.candidate_label)}</strong></span>
            <span>${statusBadge} Score: ${score} ${r.error ? `<span class="muted-text">${escapeHtml(truncate(r.error, 40))}</span>` : ""}</span>
          </div>`;
        })
        .join("");

      if (data.status === "completed" || data.status === "failed") {
        resultsList.innerHTML += `<div class="batch-item" style="border-color:var(--accent);"><span><strong>Batch ${data.status}.</strong> ${data.completed_items} succeeded, ${data.failed_items} failed.</span></div>`;
        return;
      }

      setTimeout(poll, 5000);
    } catch {
      setTimeout(poll, 5000);
    }
  };

  setTimeout(poll, 3000);
}

// ---- Init ----
checkHealth();
loadHistory();
