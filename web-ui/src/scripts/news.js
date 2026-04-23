const truncate = (value, maxLength) => {
  if (!value) {
    return "";
  }

  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
};

const sourceHue = {
  hackernews: "source-art--amber",
  lobsters: "source-art--rose",
  "reddit-programming": "source-art--orange",
  "reddit-technology": "source-art--violet",
  techcrunch: "source-art--mint",
  "openai-news": "source-art--sky",
  "anthropic-news": "source-art--rose",
  "google-blog": "source-art--mint",
  "google-developers": "source-art--amber",
  "google-research": "source-art--sky",
  "google-deepmind": "source-art--violet",
  "nvidia-blog": "source-art--mint",
  "nvidia-news": "source-art--amber",
  "nvidia-generative-ai": "source-art--orange",
  "nvidia-developer": "source-art--sky",
  "huggingface-blog": "source-art--rose",
  "microsoft-ai": "source-art--violet",
  x: "source-art--sky"
};

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const formatPublished = (value) => {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(date);
};

const renderByline = (item) => {
  const bits = [formatPublished(item.published)];
  if (item.author) {
    bits.push(`By ${String(item.author)}`);
  }
  return bits.join(" • ");
};

const renderSourceLockup = (item) => {
  const sourceKey = String(item.source || "");
  const sourceLabel = String(item.source_label || item.source || "Unknown");
  const initials = sourceLabel
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] || "")
    .join("")
    .toUpperCase();

  return `
    <div class="story-source">
      <span class="source-art ${sourceHue[sourceKey] || "source-art--default"}">${escapeHtml(initials)}</span>
      <span>${escapeHtml(sourceLabel)}</span>
    </div>
  `;
};

const renderLeadStory = (item) => {
  const title = truncate(String(item.title || "Untitled"), 190);
  const summary = truncate(String(item.summary || "No summary available"), 280);
  const url = item.url ? String(item.url) : "";
  const tags = Array.isArray(item.tags) ? item.tags.slice(0, 3) : [];

  return `
    <article class="lead-story">
      <a class="lead-story__headline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
        ${escapeHtml(title)}
      </a>
      <div class="lead-story__grid">
        <div class="lead-story__art ${sourceHue[String(item.source || "")] || "source-art--default"}">
          <span>${escapeHtml(String(item.source_label || item.source || "Story"))}</span>
        </div>
        <div class="lead-story__body">
          ${renderSourceLockup(item)}
          <p class="lead-story__summary">${escapeHtml(summary)}</p>
          <p class="lead-story__meta">${escapeHtml(renderByline(item))}</p>
          ${
            tags.length
              ? `<div class="tag-row">${tags
                  .map((tag) => `<span class="tag-chip">${escapeHtml(String(tag))}</span>`)
                  .join("")}</div>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
};

const renderHeadlineRow = (item) => {
  const title = truncate(String(item.title || "Untitled"), 145);
  const url = item.url ? String(item.url) : "";

  return `
    <article class="headline-row">
      ${renderSourceLockup(item)}
      <a class="headline-row__link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
        ${escapeHtml(title)}
      </a>
      <p class="headline-row__meta">${escapeHtml(renderByline(item))}</p>
    </article>
  `;
};

const renderRailStory = (item) => {
  const title = truncate(String(item.title || "Untitled"), 108);
  const url = item.url ? String(item.url) : "";
  const sourceKey = String(item.source || "");

  return `
    <article class="rail-story">
      <div class="rail-story__body">
        ${renderSourceLockup(item)}
        <a class="rail-story__link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
          ${escapeHtml(title)}
        </a>
        <p class="rail-story__meta">${escapeHtml(renderByline(item))}</p>
      </div>
      <div class="rail-story__art ${sourceHue[sourceKey] || "source-art--default"}"></div>
    </article>
  `;
};

const renderMoreStory = (item) => {
  const title = truncate(String(item.title || "Untitled"), 150);
  const sourceLabel = String(item.source_label || item.source || "Unknown");
  const url = item.url ? String(item.url) : "";

  return `
    <article class="more-story">
      <div>
        <p class="more-story__source">${escapeHtml(sourceLabel)}</p>
        <a class="more-story__link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
          ${escapeHtml(title)}
        </a>
        <p class="more-story__meta">${escapeHtml(renderByline(item))}</p>
      </div>
      <div class="more-story__score">#${escapeHtml(String(item.rank || ""))}</div>
    </article>
  `;
};

const renderNewsLayout = (results) => {
  if (!results.length) {
    return `
      <section class="panel news-cluster news-cluster--primary">
        <div class="panel-inner">
          <div class="news-cluster__header">
            <h2>Top stories</h2>
            <span class="news-cluster__arrow">›</span>
          </div>
          <div class="news-cluster__divider"></div>
          <div class="empty-state">No stories matched this topic and time window. Try broadening the query or expanding the recency window.</div>
        </div>
      </section>
    `;
  }

  const [lead, ...rest] = results;
  const primaryRows = rest.slice(0, 3);
  const railRows = rest.slice(3, 8);
  const moreRows = rest.slice(8);

  return `
    <section class="panel news-cluster news-cluster--primary">
      <div class="panel-inner">
        <div class="news-cluster__header">
          <h2>Top stories</h2>
          <span class="news-cluster__arrow">›</span>
        </div>
        <div class="news-cluster__divider"></div>
        ${renderLeadStory(lead)}
        <div class="headline-stack">
          ${primaryRows.map((item) => renderHeadlineRow(item)).join("")}
        </div>
        ${
          moreRows.length
            ? `
              <div class="news-cluster__cta">See more headlines & perspectives</div>
              <div class="more-grid">
                ${moreRows.map((item) => renderMoreStory(item)).join("")}
              </div>
            `
            : ""
        }
      </div>
    </section>
    <aside class="panel news-cluster news-cluster--rail">
      <div class="panel-inner">
        <div class="news-cluster__header">
          <h2>Live updates</h2>
          <span class="news-cluster__arrow">›</span>
        </div>
        <div class="news-cluster__pill-row">
          <span class="news-cluster__pill news-cluster__pill--active">For you</span>
          <span class="news-cluster__pill">Developers</span>
        </div>
        <div class="news-cluster__divider"></div>
        <div class="rail-stack">
          ${railRows.length ? railRows.map((item) => renderRailStory(item)).join("") : '<div class="empty-state">Not enough stories yet to fill the side rail.</div>'}
        </div>
      </div>
    </aside>
  `;
};

const form = document.getElementById("news-form");
const button = document.getElementById("news-run-btn");
const errorBox = document.getElementById("news-error");
const sourceStatus = document.getElementById("news-source-status");
const resultsBox = document.getElementById("news-results");
const debugBox = document.getElementById("news-debug-json");
const resultCount = document.getElementById("news-result-count");
const apiBase = "/api";
const backendHelp =
  "Backend is unreachable. Start the API with `uvicorn src.web.api:app --reload --port 8000` from repo root, or set HERALD_API_TARGET in web-ui.";

if (form && button && errorBox && sourceStatus && resultsBox && debugBox && resultCount) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.textContent = "";
    sourceStatus.textContent = "";
    resultsBox.innerHTML = "";
    debugBox.textContent = "{}";
    resultCount.textContent = "Refreshing";
    button.disabled = true;
    button.textContent = "Refreshing...";

    try {
      const formData = new FormData(form);
      const query = String(formData.get("query") || "").trim();
      const limit = Number(formData.get("limit") || 20);
      const hoursBack = Number(formData.get("hours_back") || 72);
      const sources = formData.getAll("sources").map((value) => String(value));

      const payload = {
        query,
        limit,
        hours_back: hoursBack,
        sources
      };

      const response = await fetch(`${apiBase}/news`, {
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
      const debug = data.debug || {};
      const unavailable = Array.isArray(debug.unavailable_sources) ? debug.unavailable_sources : [];

      resultCount.textContent = `${results.length} ${results.length === 1 ? "Story" : "Stories"}`;
      sourceStatus.textContent = unavailable.length
        ? `Unavailable: ${unavailable.join(", ")}`
        : "All selected sources responded.";

      resultsBox.innerHTML = renderNewsLayout(results);

      debugBox.textContent = JSON.stringify(debug, null, 2);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errorBox.textContent =
        message.includes("Failed to fetch") || message.includes("NetworkError")
          ? backendHelp
          : message;
      resultCount.textContent = "Refresh Failed";
      resultsBox.innerHTML = `
        <section class="panel news-cluster news-cluster--primary">
          <div class="panel-inner">
            <div class="empty-state">The feed request did not complete. Check the error above and try again.</div>
          </div>
        </section>
      `;
    } finally {
      button.disabled = false;
      button.textContent = "Refresh Feed";
    }
  });

  form.requestSubmit();
}
