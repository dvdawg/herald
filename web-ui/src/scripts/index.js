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

const resultItemClass = "overflow-hidden rounded-none border-2 border-line bg-[#fffdf8]";
const resultRowClass = "grid grid-cols-1 sm:grid-cols-[88px_minmax(0,1fr)]";
const rankClass =
  "flex flex-row items-center justify-between gap-1 border-b-2 border-line bg-paper-panel-muted px-3 py-3.5 sm:flex-col sm:items-start sm:justify-between sm:border-r-2 sm:border-b-0";
const rankLabelClass =
  "text-[0.72rem] font-bold uppercase tracking-[0.08em] text-muted";
const rankValueClass = "text-[1.8rem] leading-none font-bold tracking-[-0.05em]";
const bodyClass = "px-4 pt-3.5 pb-4";
const metricsClass = "mb-2.5 flex flex-wrap gap-2";
const metricClass =
  "rounded-none border border-line bg-paper-panel-muted px-[9px] py-1 text-[0.8rem] leading-[1.2]";
const authorsClass = "mb-2.5 text-[0.92rem] leading-[1.45] text-muted";
const summaryClass = "m-0 leading-[1.55] text-[#2f2923]";
const linkClass =
  "mt-3 inline-block border-b-2 border-line font-bold no-underline";
const emptyStateClass =
  "rounded-none border-2 border-dashed border-line-soft bg-[#f3ede2] p-[18px] text-muted";

const renderResultCard = (item, index) => {
  const title = truncate(String(item.title || "Untitled"), 160);
  const authors = truncate(String((item.authors || []).join(", ") || "Unknown"), 140);
  const published = String(item.published || "Unknown");
  const score = Number(item.score || 0).toFixed(4);
  const summary = truncate(String(item.summary || "No abstract available"), 420);
  const rank = Number(item.rank || index + 1);
  const pdfUrl = item.pdf_url ? String(item.pdf_url) : "";

  return `
    <li class="${resultItemClass}">
      <article class="${resultRowClass}">
        <div class="${rankClass}">
          <span class="${rankLabelClass}">Rank</span>
          <span class="${rankValueClass}">${escapeHtml(String(rank))}</span>
        </div>
        <div class="${bodyClass}">
          <h3 class="mb-2.5 text-[1.05rem] leading-[1.3] font-semibold">${escapeHtml(title)}</h3>
          <div class="${metricsClass}">
            <span class="${metricClass}"><strong class="mr-1">Score</strong>${escapeHtml(score)}</span>
            <span class="${metricClass}"><strong class="mr-1">Published</strong>${escapeHtml(published)}</span>
          </div>
          <p class="${authorsClass}">${escapeHtml(authors)}</p>
          <p class="${summaryClass}">${escapeHtml(summary)}</p>
          ${
            pdfUrl
              ? `<a class="${linkClass}" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noreferrer">Open PDF</a>`
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
      const dateFrom = String(formData.get("date_from") || "").trim() || undefined;
      const dateTo = String(formData.get("date_to") || "").trim() || undefined;

      let weights;
      if (weightsRaw.length > 0) {
        weights = JSON.parse(weightsRaw);
      }

      const payload = {
        query,
        max_results: maxResults,
        top_k: topK,
        weights,
        date_from: dateFrom,
        date_to: dateTo,
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
        resultsBox.innerHTML = `<li class="${emptyStateClass}">No results matched this query.</li>`;
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
      resultsBox.innerHTML = `<li class="${emptyStateClass}">The request did not complete. Check the error above and try again.</li>`;
    } finally {
      button.disabled = false;
      button.textContent = "Run Search";
    }
  });
}
