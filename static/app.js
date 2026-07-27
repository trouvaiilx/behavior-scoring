/* ===================================================================
   app.js — Behavior Scoring Frontend
   Handles all tabs: Analyze, History, Analytics, Compare, Batch
   =================================================================== */

// ================================================================
// DOM REFERENCES
// ================================================================
const healthBanner  = document.getElementById("health-banner");
const healthText    = document.getElementById("health-text");
const form          = document.getElementById("score-form");
const submitBtn     = document.getElementById("submit-btn");
const errorBox      = document.getElementById("error-box");
const errorText     = document.getElementById("error-text");
const resultPanel   = document.getElementById("result-panel");
const resultContent = document.getElementById("result-content");
const historyTbody  = document.getElementById("history-tbody");
const historyStats  = document.getElementById("history-stats");

// ================================================================
// TOAST NOTIFICATION SYSTEM
// ================================================================
const toastContainer = document.getElementById("toast-container");

function showToast(message, type = "info", duration = 4000) {
  const icons = {
    success: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
    error:   `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    info:    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  };

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", "status");
  toast.innerHTML = `
    ${icons[type] || icons.info}
    <span>${escapeHtml(message)}</span>
    <button class="toast-close" aria-label="Dismiss notification">×</button>
  `;

  const dismiss = () => {
    toast.classList.add("toast-exit");
    setTimeout(() => toast.remove(), 280);
  };

  toast.querySelector(".toast-close").addEventListener("click", dismiss);
  toastContainer.appendChild(toast);
  setTimeout(dismiss, duration);
}

// ================================================================
// TAB NAVIGATION
// ================================================================
const tabBtns     = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");

tabBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabBtns.forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
    tabContents.forEach((c) => c.classList.remove("active"));

    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    const target = document.getElementById(btn.dataset.tab);
    target.classList.add("active");

    if (btn.dataset.tab === "tab-history")   loadHistory();
    if (btn.dataset.tab === "tab-analytics") loadAnalytics();
  });
});

// ================================================================
// HEALTH CHECK
// ================================================================
async function checkHealth() {
  try {
    const res  = await fetch("/api/health");
    const data = await res.json();

    if (data.ollama.reachable && data.ollama.model_available_locally) {
      healthText.textContent = `Connected — ${data.ollama.configured_model}`;
      healthBanner.className = "health-banner ok";
    } else if (data.ollama.reachable) {
      healthText.textContent = `Model "${data.ollama.configured_model}" not found. Run: ollama pull ${data.ollama.configured_model}`;
      healthBanner.className = "health-banner error";
    } else {
      healthText.textContent = `Ollama unreachable. Run: ollama serve`;
      healthBanner.className = "health-banner error";
    }
  } catch {
    healthText.textContent = "Cannot reach the backend API.";
    healthBanner.className = "health-banner error";
  }
}

// ================================================================
// UTILITIES
// ================================================================
function escapeHtml(str) {
  if (!str) return "";
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

function badgeHtml(status) {
  const cls = status || "pending";
  return `<span class="badge ${cls}">${cls}</span>`;
}

/**
 * Format ISO timestamp.
 * Recent (<24h): relative — "2 hours ago".
 * Older: absolute — "2026-07-25 14:30".
 */
function formatTime(isoStr) {
  if (!isoStr) return "";
  try {
    const d   = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1)   return "just now";
    if (diffMin < 60)  return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24)    return `${diffH}h ago`;

    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  } catch {
    return isoStr;
  }
}

function truncate(str, len = 40) {
  if (!str) return "";
  return str.length > len ? str.substring(0, len) + "…" : str;
}

/** Returns CSS class for score tier */
function scoreClass(score) {
  const n = parseFloat(score);
  if (n >= 70) return "score-high";
  if (n >= 40) return "score-mid";
  return "score-low";
}

/** Animate a number from start → end over duration ms */
function animateNumber(el, start, end, duration = 900) {
  const startTime = performance.now();
  const range = end - start;
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);

  const tick = (now) => {
    const elapsed = now - startTime;
    const t = Math.min(elapsed / duration, 1);
    el.textContent = Math.round(start + range * easeOut(t));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// ================================================================
// DELETE CONFIRMATION MODAL
// ================================================================
let confirmCallback = null;
const confirmModal      = document.getElementById("confirm-modal");
const confirmModalTitle = document.getElementById("confirm-modal-title");
const confirmModalDesc  = document.getElementById("confirm-modal-desc");
const confirmCancelBtn  = document.getElementById("confirm-cancel-btn");
const confirmDeleteBtn  = document.getElementById("confirm-delete-btn");

function showConfirm(title, description, onConfirm) {
  confirmModalTitle.textContent = title;
  confirmModalDesc.textContent  = description;
  confirmCallback = onConfirm;
  confirmModal.hidden = false;
}

function closeConfirm() {
  confirmModal.hidden = true;
  confirmCallback = null;
}

confirmCancelBtn.addEventListener("click", closeConfirm);
confirmModal.addEventListener("click", (e) => { if (e.target === confirmModal) closeConfirm(); });
confirmDeleteBtn.addEventListener("click", () => {
  if (confirmCallback) confirmCallback();
  closeConfirm();
});

// ================================================================
// SCORE FORM
// ================================================================
let inFlightScoreRequest = null;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();

  const payload = {
    candidate_label: document.getElementById("candidate_label").value.trim(),
    job_role:        document.getElementById("job_role").value.trim(),
    cv_claims:       document.getElementById("cv_claims").value,
    profile_about:   document.getElementById("profile_about").value,
    posts_sample:    document.getElementById("posts_sample").value,
    comments_sample: document.getElementById("comments_sample").value,
    network_notes:   document.getElementById("network_notes").value,
  };

  if (!payload.candidate_label) {
    showError("Candidate label is required before analysis can begin.");
    return;
  }

  const hasText = [payload.cv_claims, payload.profile_about, payload.posts_sample,
                   payload.comments_sample, payload.network_notes]
    .some((v) => v && v.trim().length > 0);

  if (!hasText) {
    showError("Fill in at least one profile text field so there's content to analyze.");
    return;
  }

  if (inFlightScoreRequest) inFlightScoreRequest.abort();
  const controller = new AbortController();
  inFlightScoreRequest = controller;

  setSubmitLoading(true);

  try {
    const res = await fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Request failed (${res.status})`);
    }

    const result = await res.json();
    renderResult(result);
    showToast(`Analysis complete — score: ${result.composite_score}/100`, "success");

    // Reload history cache silently
    loadHistory();

  } catch (err) {
    if (err.name === "AbortError") return;
    showError(err.message);
    showToast("Analysis failed. See the error message below.", "error");
  } finally {
    if (inFlightScoreRequest === controller) {
      inFlightScoreRequest = null;
      setSubmitLoading(false);
    }
  }
});

function setSubmitLoading(loading) {
  submitBtn.disabled = loading;
  if (loading) {
    submitBtn.innerHTML = `
      <svg class="spin" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
      </svg>
      Analyzing… (local LLM running)`;
  } else {
    submitBtn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      Analyze Candidate`;
  }
}

function showError(msg) {
  errorText.textContent = msg;
  errorBox.hidden = false;
}

function hideError() {
  errorBox.hidden = true;
}

// ================================================================
// RENDER SCORE RESULT
// ================================================================
function renderResult(result) {
  resultPanel.hidden = false;
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  const hrStatus = result.human_review ? result.human_review.status : "pending";

  // Build dimension rows with staggered animation delay
  const dims = result.dimension_scores.map((d, i) => `
    <div class="dim-row" style="animation-delay: ${i * 60}ms">
      <div style="flex:1; min-width:0;">
        <div class="dim-name">${escapeHtml(d.label)}</div>
        <div class="dim-rationale">${escapeHtml(d.rationale)}</div>
        <div class="dim-bar-track">
          <div class="dim-bar-fill" data-width="${d.score}"></div>
        </div>
      </div>
      <div class="dim-score">${d.score}</div>
    </div>`).join("");

  const excluded = result.excluded_attributes_detected.length
    ? `<p style="margin-top:10px; font-size:var(--text-xs); color:var(--review);">
        ⚠ Excluded attributes flagged: ${result.excluded_attributes_detected.map(escapeHtml).join(", ")}
       </p>`
    : "";

  let prettyRaw = result.raw_model_output;
  try { prettyRaw = JSON.stringify(JSON.parse(result.raw_model_output), null, 2); } catch {}

  const summaryText = result.overall_summary ? escapeHtml(result.overall_summary) : "(no summary returned)";
  const jobRole     = result.job_role ? `<span class="meta-text" style="font-size:var(--text-xs)">Role: ${escapeHtml(result.job_role)}</span>` : "";

  resultContent.innerHTML = `
    <!-- Hero: gauge + meta -->
    <div class="result-hero">
      <div class="gauge-wrapper" aria-label="Composite score: ${result.composite_score} out of 100">
        <svg class="gauge-svg" viewBox="0 0 120 120" aria-hidden="true">
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stop-color="#6366f1"/>
              <stop offset="100%" stop-color="#a5b4fc"/>
            </linearGradient>
          </defs>
          <circle class="gauge-track" cx="60" cy="60" r="54"/>
          <circle class="gauge-fill" cx="60" cy="60" r="54" data-score="${result.composite_score}"/>
        </svg>
        <div class="gauge-label">
          <span class="gauge-score" id="gauge-score-num">0</span>
          <span class="gauge-unit">/ 100</span>
        </div>
      </div>
      <div class="result-meta">
        <div class="result-meta-title">${escapeHtml(result.candidate_label)}</div>
        ${jobRole}
        <div class="result-meta-flags">
          <span>${badgeHtml(result.red_flag.status)}</span>
          <span class="meta-text">${escapeHtml(result.red_flag.rationale)}</span>
        </div>
        <div class="result-meta-flags">
          <span class="meta-text">Human Review:</span>
          ${badgeHtml(hrStatus)}
        </div>
      </div>
    </div>

    <!-- Summary -->
    <div class="summary-box">
      <div class="summary-header">
        <span class="summary-badge">Overall Summary</span>
        <span class="meta-text">Rubric v${result.rubric_version} · Run #${result.id || "—"}</span>
      </div>
      <p class="summary-text">${summaryText}</p>
    </div>

    <!-- Dimensions -->
    <div class="section-title" style="margin-top: var(--space-3);">Dimension Breakdown</div>
    <div class="dim-list">${dims}</div>
    ${excluded}

    <p class="meta-text" style="margin-top: var(--space-2);">
      Rubric hash: ${result.rubric_hash || "n/a"} · Model: ${escapeHtml(result.model_used)} · ${result.created_at || ""}
    </p>

    <details class="raw-output">
      <summary>View raw model output</summary>
      <pre>${escapeHtml(prettyRaw)}</pre>
    </details>
  `;

  // Animate gauge arc
  const gaugeFill  = resultContent.querySelector(".gauge-fill");
  const gaugeNum   = resultContent.querySelector("#gauge-score-num");
  const score      = parseFloat(result.composite_score) || 0;
  const circumference = 2 * Math.PI * 54; // r=54 → ~339.3

  requestAnimationFrame(() => {
    setTimeout(() => {
      const dashArray = (score / 100) * circumference;
      gaugeFill.style.strokeDasharray = `${dashArray} ${circumference}`;
      animateNumber(gaugeNum, 0, score, 900);
    }, 80);
  });

  // Animate dimension bars with stagger
  resultContent.querySelectorAll(".dim-bar-fill").forEach((bar, i) => {
    setTimeout(() => {
      bar.style.width = bar.dataset.width + "%";
    }, 200 + i * 60);
  });
}

// ================================================================
// HISTORY (with filters)
// ================================================================
let historyCache = [];

function getFilterParams() {
  const params = new URLSearchParams();
  const search   = document.getElementById("filter-search").value.trim();
  const rfStatus = document.getElementById("filter-red-flag").value;
  const hrStatus = document.getElementById("filter-human-review").value;
  const sortBy   = document.getElementById("filter-sort-by").value;
  const sortOrder= document.getElementById("filter-sort-order").value;

  params.set("limit", "50");
  params.set("offset", "0");
  if (search)   params.set("search", search);
  if (rfStatus) params.set("red_flag_status", rfStatus);
  if (hrStatus) params.set("human_review_status", hrStatus);
  params.set("sort_by", sortBy);
  params.set("sort_order", sortOrder);
  return params;
}

function renderSkeletonRows(count = 5) {
  return Array.from({ length: count }, () => `
    <tr class="skeleton-row">
      ${Array.from({ length: 9 }, () => `<td><span class="skeleton skeleton-cell"></span></td>`).join("")}
    </tr>`).join("");
}

async function loadHistory() {
  historyTbody.innerHTML = renderSkeletonRows(5);

  try {
    const params = getFilterParams();
    const res    = await fetch(`/api/scores?${params.toString()}`);
    const data   = await res.json();
    const rows   = Array.isArray(data) ? data : data.results || [];
    const total  = data.total || rows.length;
    historyCache = rows;

    historyStats.textContent = `Showing ${rows.length} of ${total} result${total !== 1 ? "s" : ""}`;

    if (rows.length === 0) {
      historyTbody.innerHTML = `
        <tr>
          <td colspan="9" style="padding:0; border:none;">
            <div class="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M3 3l18 18"/><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"/><path d="M17 5V3"/><path d="M13 5H9"/></svg>
              <h3>No scoring runs yet</h3>
              <p>Analyze your first candidate using the Analyze tab. Results will appear here.</p>
            </div>
          </td>
        </tr>`;
      return;
    }

    historyTbody.innerHTML = rows.map((r) => {
      const hrStatus = r.human_review ? r.human_review.status : "pending";
      const cls = scoreClass(r.composite_score);
      return `
      <tr data-id="${r.id}">
        <td class="meta-text">${r.id}</td>
        <td class="cell-truncate" title="${escapeHtml(r.candidate_label)}"><strong>${escapeHtml(truncate(r.candidate_label, 16))}</strong></td>
        <td class="cell-truncate" title="${escapeHtml(r.job_role || "")}">${escapeHtml(truncate(r.job_role || "—", 14))}</td>
        <td class="cell-truncate" title="${escapeHtml(r.overall_summary || "")}">${escapeHtml(truncate(r.overall_summary || "—", 30))}</td>
        <td><span class="${cls}">${r.composite_score}</span></td>
        <td>${badgeHtml(r.red_flag.status)}</td>
        <td>${badgeHtml(hrStatus)}</td>
        <td class="meta-text" title="${r.created_at || ""}">${formatTime(r.created_at)}</td>
        <td>
          <div class="actions-cell">
            <button class="btn btn-ghost btn-xs action-view" data-id="${r.id}" title="View full details" aria-label="View details for run ${r.id}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
            </button>
            <button class="btn btn-review-status btn-xs action-review" data-id="${r.id}" title="Set human review decision" aria-label="Review run ${r.id}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
            </button>
            <button class="btn btn-danger btn-xs action-delete" data-id="${r.id}" title="Delete this run" aria-label="Delete run ${r.id}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </div>
        </td>
      </tr>`;
    }).join("");

    attachHistoryHandlers();

  } catch {
    historyTbody.innerHTML = `<tr><td colspan="9" class="muted-text" style="padding:16px;">Could not load history. Is the backend running?</td></tr>`;
  }
}

function attachHistoryHandlers() {
  // View
  historyTbody.querySelectorAll(".action-view").forEach((btn) =>
    btn.addEventListener("click", (e) => { e.stopPropagation(); openDetailModal(+btn.dataset.id); })
  );

  // Review
  historyTbody.querySelectorAll(".action-review").forEach((btn) =>
    btn.addEventListener("click", (e) => { e.stopPropagation(); openReviewModal(+btn.dataset.id); })
  );

  // Delete — styled modal instead of confirm()
  historyTbody.querySelectorAll(".action-delete").forEach((btn) =>
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = +btn.dataset.id;
      showConfirm(
        `Delete score run #${id}?`,
        `This will permanently remove run #${id} and all its associated data. This action cannot be undone.`,
        async () => {
          try {
            const res = await fetch(`/api/scores/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error("Delete failed");
            showToast(`Run #${id} deleted.`, "info");
            loadHistory();
          } catch (err) {
            showToast("Could not delete run: " + err.message, "error");
          }
        }
      );
    })
  );

  // Row click → detail
  historyTbody.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.style.cursor = "pointer";
    tr.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      openDetailModal(+tr.dataset.id);
    });
  });
}

// ================================================================
// FILTER ACTIONS
// ================================================================
document.getElementById("apply-filters-btn").addEventListener("click", loadHistory);
document.getElementById("refresh-history").addEventListener("click", () => { loadHistory(); showToast("History refreshed.", "info", 2000); });
document.getElementById("filter-search").addEventListener("keydown", (e) => { if (e.key === "Enter") loadHistory(); });

document.getElementById("clear-filters-btn").addEventListener("click", () => {
  document.getElementById("filter-search").value = "";
  document.getElementById("filter-red-flag").value = "";
  document.getElementById("filter-human-review").value = "";
  document.getElementById("filter-sort-by").value = "id";
  document.getElementById("filter-sort-order").value = "desc";
  loadHistory();
});

// ================================================================
// EXPORT
// ================================================================
document.getElementById("export-csv-btn").addEventListener("click", () => {
  const params = getFilterParams();
  params.set("format", "csv"); params.delete("limit"); params.delete("offset");
  window.open(`/api/scores/export?${params}`, "_blank");
});

document.getElementById("export-json-btn").addEventListener("click", () => {
  const params = getFilterParams();
  params.set("format", "json"); params.delete("limit"); params.delete("offset");
  window.open(`/api/scores/export?${params}`, "_blank");
});

// ================================================================
// MODALS — shared close
// ================================================================
const detailModal      = document.getElementById("detail-modal");
const detailModalBody  = document.getElementById("detail-modal-body");
const detailModalTitle = document.getElementById("detail-modal-title");
const reviewModal      = document.getElementById("review-modal");
const reviewModalLabel = document.getElementById("review-modal-label");

function closeAllModals() {
  detailModal.hidden  = true;
  reviewModal.hidden  = true;
  // confirmModal is managed separately
}

document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeAllModals(); closeConfirm(); } });

// ================================================================
// DETAIL MODAL
// ================================================================
document.getElementById("detail-modal-close").addEventListener("click", closeAllModals);
detailModal.addEventListener("click", (e) => { if (e.target === detailModal) closeAllModals(); });

async function openDetailModal(id) {
  closeAllModals();
  detailModal.hidden = false;
  detailModalTitle.textContent = `Score Run #${id}`;
  detailModalBody.innerHTML = renderSkeletonRows(3);

  try {
    const res = await fetch(`/api/scores/${id}`);
    if (!res.ok) throw new Error("Not found");
    const data = await res.json();

    const dims = data.dimension_scores.map((d, i) => `
      <div class="dim-row" style="animation-delay:${i * 50}ms">
        <div style="flex:1; min-width:0;">
          <div class="dim-name">${escapeHtml(d.label)}</div>
          <div class="dim-rationale">${escapeHtml(d.rationale)}</div>
          <div class="dim-bar-track">
            <div class="dim-bar-fill" data-width="${d.score}"></div>
          </div>
        </div>
        <div class="dim-score">${d.score}</div>
      </div>`).join("");

    const excluded = (data.excluded_attributes_detected || []).length
      ? `<p style="font-size:var(--text-xs); color:var(--review); margin-top:8px;">⚠ Excluded attributes flagged: ${data.excluded_attributes_detected.map(escapeHtml).join(", ")}</p>`
      : "";

    const hrStatus = data.human_review ? data.human_review.status : "pending";
    const hrNotes  = data.human_review?.notes ? escapeHtml(data.human_review.notes) : "(none)";
    const hrTime   = data.human_review?.reviewed_at ? formatTime(data.human_review.reviewed_at) : "—";

    let prettyRaw = data.raw_model_output || "";
    try { prettyRaw = JSON.stringify(JSON.parse(prettyRaw), null, 2); } catch {}

    const score = parseFloat(data.composite_score) || 0;
    const cls   = scoreClass(score);

    detailModalBody.innerHTML = `
      <div class="summary-box">
        <div class="summary-header">
          <span class="summary-badge">Summary</span>
          ${data.job_role ? `<span class="meta-text">Role: ${escapeHtml(data.job_role)}</span>` : ""}
        </div>
        <p class="summary-text">${escapeHtml(data.overall_summary || "(none)")}</p>
      </div>

      <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
        <div>
          <div class="meta-text" style="margin-bottom:3px;">Composite Score</div>
          <div style="font-size: var(--text-3xl); font-weight:800; letter-spacing:-0.04em;" class="${cls}">${data.composite_score}</div>
        </div>
        <div style="flex:1; min-width:160px;">
          <div style="margin-bottom:6px;">${badgeHtml(data.red_flag.status)} <span class="meta-text">${escapeHtml(data.red_flag.rationale)}</span></div>
          <div class="meta-text" style="padding:8px; background:var(--glass); border-radius:var(--radius-xs); border:1px solid var(--glass-border);">
            <strong>Human Review:</strong> ${badgeHtml(hrStatus)}<br>
            Notes: ${hrNotes}<br>
            Reviewed: ${hrTime}
          </div>
        </div>
      </div>

      <div class="section-title">Dimensions</div>
      <div class="dim-list">${dims}</div>
      ${excluded}

      <p class="meta-text">Rubric v${data.rubric_version} · hash: ${data.rubric_hash || "n/a"} · ${escapeHtml(data.model_used)} · ${formatTime(data.created_at)}</p>

      <details class="raw-output">
        <summary>View raw model output</summary>
        <pre>${escapeHtml(prettyRaw)}</pre>
      </details>
    `;

    // Animate bars
    detailModalBody.querySelectorAll(".dim-bar-fill").forEach((bar, i) => {
      setTimeout(() => { bar.style.width = bar.dataset.width + "%"; }, 150 + i * 50);
    });

  } catch {
    detailModalBody.innerHTML = `<p class="muted-text">Could not load score detail.</p>`;
  }
}

// ================================================================
// HUMAN REVIEW MODAL
// ================================================================
let reviewTargetId = null;

document.getElementById("review-modal-close").addEventListener("click", closeAllModals);
document.getElementById("review-cancel-btn").addEventListener("click", closeAllModals);
reviewModal.addEventListener("click", (e) => { if (e.target === reviewModal) closeAllModals(); });

function openReviewModal(id) {
  closeAllModals();
  reviewTargetId = id;
  const row = historyCache.find((r) => r.id === id);
  const currentStatus = row?.human_review?.status || "pending";
  const currentNotes  = row?.human_review?.notes  || "";

  reviewModalLabel.textContent = `Score run #${id} — ${row ? row.candidate_label : ""}`;
  document.getElementById("review-status").value = currentStatus;
  document.getElementById("review-notes").value  = currentNotes;
  reviewModal.hidden = false;
}

document.getElementById("review-save-btn").addEventListener("click", async () => {
  if (!reviewTargetId) return;
  const status = document.getElementById("review-status").value;
  const notes  = document.getElementById("review-notes").value;

  const saveBtn = document.getElementById("review-save-btn");
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving…";

  try {
    const res = await fetch(`/api/scores/${reviewTargetId}/review`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, notes }),
    });
    if (!res.ok) throw new Error("Failed to save review");

    reviewModal.hidden = true;
    showToast(`Review saved: ${status}`, "success");
    loadHistory();

  } catch (err) {
    showToast("Could not save review: " + err.message, "error");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save Review";
  }
});

// ================================================================
// ANALYTICS
// ================================================================
async function loadAnalytics() {
  const container = document.getElementById("analytics-content");
  container.innerHTML = `<p class="muted-text">Loading analytics…</p>`;

  try {
    const res = await fetch("/api/scores/analytics");
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();

    const stats  = data.composite_score_stats;
    const rf     = data.red_flag_breakdown;
    const hr     = data.human_review_breakdown;
    const buckets= data.score_buckets;
    const excludedAttrs = data.excluded_attributes_counts || {};

    const bucketValues = Object.values(buckets);
    const maxBucket    = Math.max(...bucketValues, 1);

    const bucketLabels = { "0_to_20":"0–20", "21_to_40":"21–40", "41_to_60":"41–60", "61_to_80":"61–80", "81_to_100":"81–100" };

    const barsHtml = Object.entries(buckets).map(([k, v]) => {
      const pct = (v / maxBucket) * 100;
      return `
      <div class="bar-col">
        <div class="bar-count">${v}</div>
        <div class="bar-fill" data-height="${Math.max(pct, 3)}" style="height:3%"></div>
        <div class="bar-label">${bucketLabels[k] || k}</div>
      </div>`;
    }).join("");

    const rfItems = Object.entries(rf)
      .map(([k, v]) => `<div class="breakdown-item"><div class="breakdown-count" style="color:var(--${k})">${v}</div><div class="breakdown-label">${k}</div></div>`)
      .join("");

    const hrItems = Object.entries(hr)
      .map(([k, v]) => `<div class="breakdown-item"><div class="breakdown-count" style="color:var(--${k})">${v}</div><div class="breakdown-label">${k}</div></div>`)
      .join("");

    const excludedHtml = Object.keys(excludedAttrs).length
      ? Object.entries(excludedAttrs)
          .map(([a, c]) => `<div class="breakdown-item"><div class="breakdown-count" style="color:var(--review)">${c}</div><div class="breakdown-label">${escapeHtml(truncate(a, 20))}</div></div>`)
          .join("")
      : `<p class="muted-text">No excluded attributes detected across any runs.</p>`;

    container.innerHTML = `
      <div class="stats-grid">
        <div class="stat-card" style="animation-delay:0ms"><div class="stat-value">${data.total_candidates}</div><div class="stat-label">Total Scored</div></div>
        <div class="stat-card" style="animation-delay:60ms"><div class="stat-value">${stats.avg}</div><div class="stat-label">Avg Score</div></div>
        <div class="stat-card" style="animation-delay:120ms"><div class="stat-value">${stats.median}</div><div class="stat-label">Median</div></div>
        <div class="stat-card" style="animation-delay:180ms"><div class="stat-value">${stats.min}</div><div class="stat-label">Min</div></div>
        <div class="stat-card" style="animation-delay:240ms"><div class="stat-value">${stats.max}</div><div class="stat-label">Max</div></div>
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

    // Animate bars after paint
    requestAnimationFrame(() => {
      container.querySelectorAll(".bar-fill[data-height]").forEach((el, i) => {
        setTimeout(() => { el.style.height = el.dataset.height + "%"; }, i * 80);
      });
    });

  } catch {
    container.innerHTML = `<p class="muted-text">Failed to load analytics. Is the backend running?</p>`;
  }
}

document.getElementById("refresh-analytics-btn").addEventListener("click", () => { loadAnalytics(); showToast("Analytics refreshed.", "info", 2000); });

// ================================================================
// COMPARE
// ================================================================
document.getElementById("compare-btn").addEventListener("click", async () => {
  const idsStr    = document.getElementById("compare-ids").value.trim();
  const container = document.getElementById("compare-content");

  if (!idsStr) {
    container.innerHTML = `<p class="muted-text">Enter comma-separated score IDs to compare (e.g. 1, 2, 5).</p>`;
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

    const count = data.candidates.length;
    const gridCls = count === 2 ? "compare-grid-2" : count === 3 ? "compare-grid-3" : "";

    const cards = data.candidates.map((c) => {
      const dimsHtml = c.dimension_scores.map((d) => `
        <div class="compare-dim-item">
          <div class="compare-dim-score">${d.score}</div>
          <div class="compare-dim-label">${escapeHtml(truncate(d.label, 18))}</div>
        </div>`).join("");

      const hrStatus  = c.human_review ? c.human_review.status : "pending";
      const isHighest = c.candidate_label === data.highest_scoring_candidate;
      const isLowest  = c.candidate_label === data.lowest_scoring_candidate;
      const cardCls   = isHighest ? "is-highest" : isLowest ? "is-lowest" : "";
      const indicator = isHighest
        ? `<span class="badge approved" style="margin-left:6px">Highest</span>`
        : isLowest ? `<span class="badge rejected" style="margin-left:6px">Lowest</span>` : "";

      return `
      <div class="compare-card ${cardCls}">
        <div class="compare-card-header">
          <div>
            <div class="compare-card-title">${escapeHtml(c.candidate_label)} ${indicator}</div>
            <div class="meta-text">${c.job_role ? escapeHtml(c.job_role) : "No role"} · ${badgeHtml(c.red_flag.status)} · Review: ${badgeHtml(hrStatus)}</div>
          </div>
          <div class="compare-card-score ${scoreClass(c.composite_score)}">${c.composite_score}</div>
        </div>
        <div class="compare-dims">${dimsHtml}</div>
      </div>`;
    }).join("");

    const avgHtml = Object.entries(data.dimension_averages)
      .map(([k, v]) => `<span><strong>${escapeHtml(k)}:</strong> ${v}</span>`).join(" · ");
    const rfSummary = Object.entries(data.red_flags_summary)
      .map(([k, v]) => `<span>${k}: <strong>${v}</strong></span>`).join(" · ");

    container.innerHTML = `
      <div class="compare-grid ${gridCls}">${cards}</div>
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

// ================================================================
// BATCH SCORING
// ================================================================
document.getElementById("batch-submit-btn").addEventListener("click", async () => {
  const jsonInput      = document.getElementById("batch-json").value.trim();
  const statusArea     = document.getElementById("batch-status");
  const batchSubmitBtn = document.getElementById("batch-submit-btn");

  if (!jsonInput) {
    statusArea.innerHTML = `<p class="muted-text">Paste a JSON array of candidate profiles above, then click Start Batch Analysis.</p>`;
    return;
  }

  let profiles;
  try {
    profiles = JSON.parse(jsonInput);
    if (!Array.isArray(profiles) || profiles.length === 0) throw new Error("Must be a non-empty JSON array");
    if (profiles.length > 20) throw new Error("Maximum 20 profiles per batch");
  } catch (err) {
    statusArea.innerHTML = `<div class="error-box"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> <span>Invalid JSON: ${escapeHtml(err.message)}</span></div>`;
    return;
  }

  batchSubmitBtn.disabled = true;
  batchSubmitBtn.innerHTML = `<svg class="spin" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Submitting…`;
  statusArea.innerHTML = `<p class="muted-text">Submitting ${profiles.length} profiles…</p>`;

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

    showToast(`Batch ${data.batch_id} submitted — ${data.total_items} profiles queued.`, "info");

    statusArea.innerHTML = `
      <div class="batch-progress">
        <p>Batch <strong>${data.batch_id}</strong> — ${data.total_items} profiles. Polling for results…</p>
        <div class="progress-bar-track"><div class="progress-bar-fill" id="batch-progress-fill" style="width:0%"></div></div>
      </div>
      <div class="batch-results-list" id="batch-results-list"></div>
    `;

    pollBatch(data.batch_id, data.total_items);

  } catch (err) {
    statusArea.innerHTML = `<div class="error-box"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> <span>${escapeHtml(err.message)}</span></div>`;
    showToast("Batch submission failed: " + err.message, "error");
  } finally {
    batchSubmitBtn.disabled = false;
    batchSubmitBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Start Batch Analysis`;
  }
});

async function pollBatch(batchId, totalItems) {
  const progressFill = document.getElementById("batch-progress-fill");
  const resultsList  = document.getElementById("batch-results-list");
  let attempts = 0;
  const maxAttempts = 120;

  const poll = async () => {
    if (attempts >= maxAttempts) {
      resultsList.innerHTML += `<div class="batch-item"><span class="muted-text">Polling timed out after 10 minutes. Check back manually.</span></div>`;
      return;
    }
    attempts++;

    try {
      const res = await fetch(`/api/scores/batch/${batchId}`);
      if (!res.ok) { setTimeout(poll, 5000); return; }
      const data = await res.json();

      const completed = data.completed_items + data.failed_items;
      const pct = totalItems > 0 ? (completed / totalItems) * 100 : 0;
      if (progressFill) progressFill.style.width = `${pct}%`;

      resultsList.innerHTML = data.results.map((r) => {
        const cls   = r.status === "completed" ? "score-high" : "score-low";
        const score = r.score_result ? r.score_result.composite_score : "—";
        return `<div class="batch-item">
          <span><strong>${escapeHtml(r.candidate_label)}</strong></span>
          <span class="${cls}">${r.status === "completed" ? "✓" : "✗"} Score: ${score} ${r.error ? `<span class="muted-text">${escapeHtml(truncate(r.error, 40))}</span>` : ""}</span>
        </div>`;
      }).join("");

      if (data.status === "completed" || data.status === "failed") {
        resultsList.innerHTML += `<div class="batch-item" style="border-color:var(--accent);">
          <span><strong>Batch ${data.status}.</strong> ${data.completed_items} succeeded, ${data.failed_items} failed.</span>
        </div>`;
        showToast(`Batch complete — ${data.completed_items}/${totalItems} succeeded.`,
          data.failed_items === 0 ? "success" : "info");
        loadHistory();
        return;
      }

      setTimeout(poll, 5000);

    } catch {
      setTimeout(poll, 5000);
    }
  };

  setTimeout(poll, 3000);
}

// ================================================================
// INIT
// ================================================================
checkHealth();
loadHistory();
