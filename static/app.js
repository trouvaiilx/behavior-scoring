const healthBanner = document.getElementById("health-banner");
const form = document.getElementById("score-form");
const submitBtn = document.getElementById("submit-btn");
const errorBox = document.getElementById("error-box");
const resultPanel = document.getElementById("result-panel");
const resultContent = document.getElementById("result-content");
const historyTableBody = document.querySelector("#history-table tbody");

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.ollama.reachable && data.ollama.model_available_locally) {
      healthBanner.textContent = `Ollama connected — using model "${data.ollama.configured_model}"`;
      healthBanner.className = "health-banner ok";
    } else if (data.ollama.reachable) {
      healthBanner.textContent = `Ollama is reachable, but model "${data.ollama.configured_model}" was not found locally. Run: ollama pull ${data.ollama.configured_model}`;
      healthBanner.className = "health-banner error";
    } else {
      healthBanner.textContent = `Cannot reach Ollama at the configured URL. Is "ollama serve" running? (${data.ollama.error || ""})`;
      healthBanner.className = "health-banner error";
    }
  } catch (e) {
    healthBanner.textContent = "Cannot reach the backend API itself.";
    healthBanner.className = "health-banner error";
  }
}

function badgeClass(status) {
  if (status === "pass") return "badge pass";
  if (status === "fail") return "badge fail";
  return "badge review";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

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
        </div>
        <div class="dim-score">${d.score}</div>
      </div>`
    )
    .join("");

  const excluded = result.excluded_attributes_detected.length
    ? `<p><strong>Excluded attributes noticed (not used in scoring):</strong> ${result.excluded_attributes_detected.map(escapeHtml).join(", ")}</p>`
    : "";

  let prettyRaw = result.raw_model_output;
  try {
    prettyRaw = JSON.stringify(JSON.parse(result.raw_model_output), null, 2);
  } catch (e) {
    // leave as-is if it wasn't valid JSON
  }

  const summaryText = result.overall_summary ? escapeHtml(result.overall_summary) : "(no summary returned)";

  resultContent.innerHTML = `
    <div class="summary-box">
      <div class="summary-header">
        <span class="summary-badge">Overall Candidate Summary</span>
        <span class="summary-subtitle">Prompt → Parsing → DB → UI</span>
      </div>
      <p class="summary-text">${summaryText}</p>
    </div>

    <p>Composite score (weighted, red flag excluded from average):</p>
    <div class="composite">${result.composite_score} / 100</div>
    <p style="margin-top:16px"><span class="${badgeClass(result.red_flag.status)}">${result.red_flag.status}</span>
       Red Flag Screen — ${escapeHtml(result.red_flag.rationale)}</p>
    <h3>Dimension breakdown</h3>
    ${dims}
    ${excluded}
    <p class="dim-rationale">Rubric v${result.rubric_version} · model: ${escapeHtml(result.model_used)} · run id: ${result.id} · ${result.created_at || ""}</p>

    <details class="raw-output">
      <summary>Show raw model output (for auditing / debugging)</summary>
      <pre>${escapeHtml(prettyRaw)}</pre>
    </details>
  `;
}

function formatTime(isoStr) {
  if (!isoStr) return "";
  try {
    const date = new Date(isoStr);
    if (isNaN(date.getTime())) return isoStr;
    const yyyy = date.getUTCFullYear();
    const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(date.getUTCDate()).padStart(2, "0");
    const hh = String(date.getUTCHours()).padStart(2, "0");
    const min = String(date.getUTCMinutes()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
  } catch (e) {
    return isoStr;
  }
}

let historyCache = [];

async function loadHistory() {
  try {
    const res = await fetch("/api/scores");
    const rows = await res.json();
    historyCache = rows;
    historyTableBody.innerHTML = rows
      .map(
        (r) => {
          const summaryText = r.overall_summary || "(no summary)";
          const summarySnippet = summaryText.length > 40 ? summaryText.substring(0, 40) + "…" : summaryText;
          const modelText = r.model_used || "";
          const modelSnippet = modelText.length > 18 ? modelText.substring(0, 18) + "…" : modelText;
          const formattedTime = formatTime(r.created_at);
          return `
        <tr class="history-row" data-id="${r.id}">
          <td>${r.id}</td>
          <td class="history-label" title="${escapeHtml(r.candidate_label)}"><strong>${escapeHtml(r.candidate_label)}</strong></td>
          <td class="history-summary" title="${escapeHtml(summaryText)}">${escapeHtml(summarySnippet)}</td>
          <td>${r.composite_score}</td>
          <td><span class="${badgeClass(r.red_flag.status)}">${r.red_flag.status}</span></td>
          <td class="history-model" title="${escapeHtml(modelText)}">${escapeHtml(modelSnippet)}</td>
          <td class="history-time" title="${escapeHtml(r.created_at || "")}">${escapeHtml(formattedTime)}</td>
        </tr>`;
        }
      )
      .join("");

    document.querySelectorAll(".history-row").forEach((tr) => {
      tr.addEventListener("click", () => {
        const id = parseInt(tr.dataset.id, 10);
        const row = historyCache.find((r) => r.id === id);
        if (row) renderResult(row);
      });
    });
  } catch (e) {
    historyTableBody.innerHTML = `<tr><td colspan="7">Could not load history.</td></tr>`;
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.hidden = true;
  submitBtn.disabled = true;
  submitBtn.textContent = "Scoring… (this calls your local LLM, may take a bit)";

  const payload = {
    candidate_label: document.getElementById("candidate_label").value,
    cv_claims: document.getElementById("cv_claims").value,
    profile_about: document.getElementById("profile_about").value,
    posts_sample: document.getElementById("posts_sample").value,
    comments_sample: document.getElementById("comments_sample").value,
    network_notes: document.getElementById("network_notes").value,
  };

  try {
    const res = await fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Request failed with status ${res.status}`);
    }
    const result = await res.json();
    renderResult(result);
    loadHistory();
  } catch (err) {
    errorBox.hidden = false;
    errorBox.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Run Scoring";
  }
});

document.getElementById("refresh-history").addEventListener("click", loadHistory);

checkHealth();
loadHistory();
