const truncate = (value, maxLength) => {
  if (!value) {
    return "";
  }

  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
};

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const renderResultCard = (item, index) => {
  const title = truncate(String(item.title || "Untitled"), 160);
  const authors = truncate(String((item.authors || []).join(", ") || "Unknown"), 140);
  const published = String(item.published || "Unknown");
  const score = Number(item.score || 0).toFixed(4);
  const summary = truncate(String(item.summary || "No abstract available"), 420);
  const rank = Number(item.rank || index + 1);
  const pdfUrl = item.pdf_url ? String(item.pdf_url) : "";

  return `
    <li class="result-item">
      <article class="result-item__row">
        <div class="result-rank">
          <span class="result-rank__label">Rank</span>
          <span class="result-rank__value">${escapeHtml(String(rank))}</span>
        </div>
        <div class="result-body">
          <h3>${escapeHtml(title)}</h3>
          <div class="result-metrics">
            <span class="result-metric"><strong>Score</strong>${escapeHtml(score)}</span>
            <span class="result-metric"><strong>Published</strong>${escapeHtml(published)}</span>
          </div>
          <p class="result-authors">${escapeHtml(authors)}</p>
          <p class="result-summary">${escapeHtml(summary)}</p>
          ${
            pdfUrl
              ? `<a class="result-link" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noreferrer">Open PDF</a>`
              : ""
          }
        </div>
      </article>
    </li>
  `;
};

const form = document.getElementById("run-form");
const button = document.getElementById("run-btn");
const errorBox = document.getElementById("error");
const resultsBox = document.getElementById("results");
const debugBox = document.getElementById("debug-json");
const resultCount = document.getElementById("result-count");
const apiBase = "/api";
const backendHelp =
  "Backend is unreachable. Start the API with `uvicorn src.web.api:app --reload --port 8000` from repo root, or set HERALD_API_TARGET in web-ui.";

if (form && button && errorBox && resultsBox && debugBox && resultCount) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.textContent = "";
    resultsBox.innerHTML = "";
    debugBox.textContent = "{}";
    resultCount.textContent = "Running";
    button.disabled = true;
    button.textContent = "Running...";

    try {
      const formData = new FormData(form);
      const query = String(formData.get("query") || "");
      const maxResults = Number(formData.get("max_results") || 20);
      const topK = Number(formData.get("top_k") || 10);
      const weightsRaw = String(formData.get("weights") || "").trim();

      let weights;
      if (weightsRaw.length > 0) {
        weights = JSON.parse(weightsRaw);
      }

      const payload = {
        query,
        max_results: maxResults,
        top_k: topK,
        weights
      };

      const response = await fetch(`${apiBase}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 502 || response.status === 503 || response.status === 504) {
          throw new Error(backendHelp);
        }
        throw new Error(data?.detail?.message || "Request failed");
      }

      const results = data.results || [];
      resultCount.textContent = `${results.length} ${results.length === 1 ? "Paper" : "Papers"}`;

      if (results.length === 0) {
        resultsBox.innerHTML = `<li class="empty-state">No results matched this query.</li>`;
      } else {
        resultsBox.innerHTML = results.map((item, index) => renderResultCard(item, index)).join("");
      }

      debugBox.textContent = JSON.stringify(data.debug || {}, null, 2);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errorBox.textContent =
        message.includes("Failed to fetch") || message.includes("NetworkError")
          ? backendHelp
          : message;
      resultCount.textContent = "Run Failed";
      resultsBox.innerHTML = `<li class="empty-state">The request did not complete. Check the error above and try again.</li>`;
    } finally {
      button.disabled = false;
      button.textContent = "Run Search";
    }
  });
}
