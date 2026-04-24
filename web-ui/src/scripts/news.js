const truncate = (value, maxLength) => {
  if (!value) {
    return "";
  }

  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
};

const sourceHue = {
  hackernews: "bg-[linear-gradient(135deg,#ffb34d,#f2682f_72%)]",
  lobsters: "bg-[linear-gradient(135deg,#ff8fb1,#e0597d_72%)]",
  "reddit-programming": "bg-[linear-gradient(135deg,#ff9866,#ee5b32_72%)]",
  "reddit-technology": "bg-[linear-gradient(135deg,#9b94ff,#665bdb_72%)]",
  techcrunch: "bg-[linear-gradient(135deg,#44d1a5,#0b8e75_72%)]",
  "openai-news": "bg-[linear-gradient(135deg,#68c8ff,#1976e8_72%)]",
  "anthropic-news": "bg-[linear-gradient(135deg,#ff8fb1,#e0597d_72%)]",
  "google-blog": "bg-[linear-gradient(135deg,#44d1a5,#0b8e75_72%)]",
  "google-developers": "bg-[linear-gradient(135deg,#ffb34d,#f2682f_72%)]",
  "google-research": "bg-[linear-gradient(135deg,#68c8ff,#1976e8_72%)]",
  "google-deepmind": "bg-[linear-gradient(135deg,#9b94ff,#665bdb_72%)]",
  "nvidia-blog": "bg-[linear-gradient(135deg,#44d1a5,#0b8e75_72%)]",
  "nvidia-news": "bg-[linear-gradient(135deg,#ffb34d,#f2682f_72%)]",
  "nvidia-generative-ai": "bg-[linear-gradient(135deg,#ff9866,#ee5b32_72%)]",
  "nvidia-developer": "bg-[linear-gradient(135deg,#68c8ff,#1976e8_72%)]",
  "huggingface-blog": "bg-[linear-gradient(135deg,#ff8fb1,#e0597d_72%)]",
  "microsoft-ai": "bg-[linear-gradient(135deg,#9b94ff,#665bdb_72%)]",
  x: "bg-[linear-gradient(135deg,#68c8ff,#1976e8_72%)]"
};

const defaultHue = "bg-[linear-gradient(135deg,#7692ff,#3e5daa_72%)]";
const panelClass =
  "rounded-[28px] border border-[rgba(17,56,102,0.08)] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(249,251,255,0.97))] shadow-[0_24px_60px_rgba(77,102,152,0.08)]";
const panelInnerClass = "p-6 sm:px-7 sm:py-[26px]";
const panelHeaderClass = "flex items-center justify-between gap-3 text-[#0b6899]";
const dividerClass = "my-[22px] mb-[26px] h-px bg-[rgba(64,94,128,0.16)]";
const emptyStateClass =
  "rounded-[14px] border-2 border-dashed border-line-soft bg-[rgba(255,255,255,0.55)] p-[18px] text-muted";
const storySourceClass =
  "inline-flex items-center gap-2.5 text-[0.98rem] font-bold text-[#334a67]";
const sourceArtClass =
  "inline-flex h-[30px] w-[30px] items-center justify-center rounded-lg text-[0.76rem] font-extrabold tracking-[0.05em] text-[rgba(255,255,255,0.95)]";
const leadArtClass =
  "flex min-h-[290px] items-end rounded-[24px] bg-[linear-gradient(145deg,rgba(255,255,255,0.1),transparent_35%),linear-gradient(180deg,rgba(13,28,56,0.06),rgba(13,28,56,0.34))] p-5 text-[1.6rem] leading-none font-semibold tracking-[-0.04em] text-[rgba(255,255,255,0.92)]";
const tagRowClass = "mt-3 flex flex-wrap gap-2";
const tagChipClass =
  "inline-flex items-center rounded-full border border-line bg-[rgba(180,76,47,0.08)] px-2 py-1 text-[0.78rem] font-bold";
const livePillClass =
  "inline-flex min-h-11 items-center rounded-2xl border border-[rgba(93,112,141,0.24)] bg-white px-[18px] font-semibold text-[#41556f]";
const livePillActiveClass = "border-[#d8ecff] bg-[#d8ecff] text-[#14679c]";

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
    <div class="${storySourceClass}">
      <span class="${sourceArtClass} ${sourceHue[sourceKey] || defaultHue}">${escapeHtml(initials)}</span>
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
    <article class="grid gap-5">
      <a class="text-[clamp(2rem,3vw,3rem)] leading-[1.04] font-medium tracking-[-0.05em] text-[#113a63] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
        ${escapeHtml(title)}
      </a>
      <div class="grid items-start gap-5 xl:grid-cols-[minmax(260px,0.95fr)_minmax(0,1.15fr)]">
        <div class="${leadArtClass} ${sourceHue[String(item.source || "")] || defaultHue}">
          <span>${escapeHtml(String(item.source_label || item.source || "Story"))}</span>
        </div>
        <div class="grid gap-4">
          ${renderSourceLockup(item)}
          <p class="m-0 text-[1.1rem] leading-[1.55] text-[#33445d]">${escapeHtml(summary)}</p>
          <p class="m-0 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
          ${
            tags.length
              ? `<div class="${tagRowClass}">${tags
                  .map((tag) => `<span class="${tagChipClass}">${escapeHtml(String(tag))}</span>`)
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
    <article class="grid gap-2.5 border-t border-[rgba(78,104,135,0.16)] pt-2.5">
      ${renderSourceLockup(item)}
      <a class="text-base leading-[1.35] text-[#2b3344] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
        ${escapeHtml(title)}
      </a>
      <p class="m-0 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
    </article>
  `;
};

const renderRailStory = (item, index) => {
  const title = truncate(String(item.title || "Untitled"), 108);
  const url = item.url ? String(item.url) : "";
  const sourceKey = String(item.source || "");
  const topBorder = index === 0 ? "border-t-0 pt-0" : "border-t border-[rgba(78,104,135,0.16)] pt-[18px]";

  return `
    <article class="grid items-start gap-4 pb-[18px] ${topBorder} sm:grid-cols-[minmax(0,1fr)_102px]">
      <div class="grid gap-3">
        ${renderSourceLockup(item)}
        <a class="text-[1.03rem] leading-[1.35] text-[#2b3344] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
          ${escapeHtml(title)}
        </a>
        <p class="m-0 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
      </div>
      <div class="min-h-[102px] rounded-[20px] ${sourceHue[sourceKey] || defaultHue}"></div>
    </article>
  `;
};

const renderMoreStory = (item) => {
  const title = truncate(String(item.title || "Untitled"), 150);
  const sourceLabel = String(item.source_label || item.source || "Unknown");
  const url = item.url ? String(item.url) : "";

  return `
    <article class="grid items-center gap-4 border-t border-[rgba(78,104,135,0.16)] py-5 sm:grid-cols-[minmax(0,1fr)_auto]">
      <div>
        <p class="mb-2 text-[0.9rem] font-bold text-[#4a5871]">${escapeHtml(sourceLabel)}</p>
        <a class="text-[1.03rem] leading-[1.35] text-[#2b3344] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">
          ${escapeHtml(title)}
        </a>
        <p class="m-0 mt-2 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
      </div>
      <div class="text-[2rem] font-semibold tracking-[-0.06em] text-[#9bb2cf]">#${escapeHtml(String(item.rank || ""))}</div>
    </article>
  `;
};

const renderNewsLayout = (results) => {
  if (!results.length) {
    return `
      <section class="${panelClass}">
        <div class="${panelInnerClass}">
          <div class="${panelHeaderClass}">
            <h2 class="m-0 text-[clamp(1.7rem,2vw,2.25rem)] font-medium tracking-[-0.04em]">Top stories</h2>
            <span class="text-[2rem] leading-none">›</span>
          </div>
          <div class="${dividerClass}"></div>
          <div class="${emptyStateClass}">No stories matched this topic and time window. Try broadening the query or expanding the recency window.</div>
        </div>
      </section>
    `;
  }

  const [lead, ...rest] = results;
  const primaryRows = rest.slice(0, 3);
  const railRows = rest.slice(3, 8);
  const moreRows = rest.slice(8);

  return `
    <section class="${panelClass}">
      <div class="${panelInnerClass}">
        <div class="${panelHeaderClass}">
          <h2 class="m-0 text-[clamp(1.7rem,2vw,2.25rem)] font-medium tracking-[-0.04em]">Top stories</h2>
          <span class="text-[2rem] leading-none">›</span>
        </div>
        <div class="${dividerClass}"></div>
        ${renderLeadStory(lead)}
        <div class="mt-6 grid gap-[18px] xl:grid-cols-3">
          ${primaryRows.map((item) => renderHeadlineRow(item)).join("")}
        </div>
        ${
          moreRows.length
            ? `
              <div class="mt-7 rounded-full bg-[#eff2f7] px-6 py-[18px] text-center text-base font-bold text-[#45505f]">See more headlines & perspectives</div>
              <div class="mt-6 grid gap-0">
                ${moreRows.map((item) => renderMoreStory(item)).join("")}
              </div>
            `
            : ""
        }
      </div>
    </section>
    <aside class="${panelClass}">
      <div class="${panelInnerClass}">
        <div class="${panelHeaderClass}">
          <h2 class="m-0 text-[clamp(1.45rem,1.7vw,1.9rem)] font-medium tracking-[-0.04em]">Live updates</h2>
          <span class="text-[2rem] leading-none">›</span>
        </div>
        <div class="mb-[18px] flex flex-wrap gap-2.5">
          <span class="${livePillClass} ${livePillActiveClass}">For you</span>
          <span class="${livePillClass}">Developers</span>
        </div>
        <div class="${dividerClass}"></div>
        <div class="grid gap-0">
          ${
            railRows.length
              ? railRows.map((item, index) => renderRailStory(item, index)).join("")
              : `<div class="${emptyStateClass}">Not enough stories yet to fill the side rail.</div>`
          }
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
        <section class="${panelClass}">
          <div class="${panelInnerClass}">
            <div class="${emptyStateClass}">The feed request did not complete. Check the error above and try again.</div>
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
