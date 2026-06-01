const truncate = (value, maxLength) => {
  if (!value) return "";
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
};

const apiBase = "/api";
const backendHelp =
  "Backend is unreachable. Start the API with `uvicorn src.web.api:app --reload --port 8000` from repo root.";

const hueByImportance = (importance) => {
  if (importance >= 0.8) return "bg-[linear-gradient(135deg,#68c8ff,#1976e8_72%)]";
  if (importance >= 0.7) return "bg-[linear-gradient(135deg,#9b94ff,#665bdb_72%)]";
  if (importance >= 0.6) return "bg-[linear-gradient(135deg,#44d1a5,#0b8e75_72%)]";
  if (importance >= 0.55) return "bg-[linear-gradient(135deg,#ffb34d,#f2682f_72%)]";
  return "bg-[linear-gradient(135deg,#ff8fb1,#e0597d_72%)]";
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
const actionsClass = "mt-3 flex flex-wrap gap-2 text-[0.75rem] font-semibold";
const actionBtnClass =
  "cursor-pointer rounded-md border border-[rgba(93,112,141,0.22)] bg-white px-2 py-[3px] text-[0.7rem] text-[#445b80] hover:bg-[#f2f6ff]";

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const formatPublished = (value) => {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(date);
};

const renderByline = (item) => {
  const bits = [formatPublished(item.published)];
  if (item.author) bits.push(`By ${item.author}`);
  return bits.join(" • ");
};

const sourceImportanceCache = {};
const sourceHueFor = (sourceId) => hueByImportance(sourceImportanceCache[sourceId] ?? 0.55);

const state = {
  mode: "discover",
  tag: "",
  window: "24h",
  hoursBack: 24,
};

const renderSourceLockup = (item) => {
  const sourceLabel = item.source_label || item.source || "Unknown";
  const initials = String(sourceLabel)
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] || "")
    .join("")
    .toUpperCase();
  return `
    <div class="${storySourceClass}">
      <span class="${sourceArtClass} ${sourceHueFor(item.source) || defaultHue}">${escapeHtml(initials)}</span>
      <span>${escapeHtml(sourceLabel)}</span>
    </div>
  `;
};

const renderActions = (item) => {
  if (!item.article_id) return "";
  return `
    <div class="${actionsClass}" data-actions="${item.article_id}">
      <button type="button" class="${actionBtnClass}" data-signal="like" data-article="${item.article_id}">▲ More like this</button>
      <button type="button" class="${actionBtnClass}" data-signal="hide" data-article="${item.article_id}">✕ Hide</button>
    </div>
  `;
};

const renderLeadStory = (item) => {
  const title = truncate(item.title || "Untitled", 190);
  const summary = truncate(item.summary || "No summary available", 280);
  const url = item.url || "";
  const tags = Array.isArray(item.tags) ? item.tags.slice(0, 3) : [];

  return `
    <article class="grid gap-5" data-article-id="${item.article_id || ""}">
      <a class="text-[clamp(2rem,3vw,3rem)] leading-[1.04] font-medium tracking-[-0.05em] text-[#113a63] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer" data-click="${item.article_id || ""}">
        ${escapeHtml(title)}
      </a>
      <div class="grid items-start gap-5 xl:grid-cols-[minmax(260px,0.95fr)_minmax(0,1.15fr)]">
        <div class="${leadArtClass} ${sourceHueFor(item.source) || defaultHue}">
          <span>${escapeHtml(item.source_label || item.source || "Story")}</span>
        </div>
        <div class="grid gap-4">
          ${renderSourceLockup(item)}
          <p class="m-0 text-[1.1rem] leading-[1.55] text-[#33445d]">${escapeHtml(summary)}</p>
          <p class="m-0 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
          ${tags.length ? `<div class="${tagRowClass}">${tags.map((t) => `<span class="${tagChipClass}">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
          ${renderActions(item)}
        </div>
      </div>
    </article>
  `;
};

const renderHeadlineRow = (item) => {
  const title = truncate(item.title || "Untitled", 145);
  const url = item.url || "";
  return `
    <article class="grid gap-2.5 border-t border-[rgba(78,104,135,0.16)] pt-2.5" data-article-id="${item.article_id || ""}">
      ${renderSourceLockup(item)}
      <a class="text-base leading-[1.35] text-[#2b3344] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer" data-click="${item.article_id || ""}">
        ${escapeHtml(title)}
      </a>
      <p class="m-0 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
      ${renderActions(item)}
    </article>
  `;
};

const renderRailStory = (item, index) => {
  const title = truncate(item.title || "Untitled", 108);
  const url = item.url || "";
  const topBorder = index === 0 ? "border-t-0 pt-0" : "border-t border-[rgba(78,104,135,0.16)] pt-[18px]";
  return `
    <article class="grid items-start gap-4 pb-[18px] ${topBorder} sm:grid-cols-[minmax(0,1fr)_102px]" data-article-id="${item.article_id || ""}">
      <div class="grid gap-3">
        ${renderSourceLockup(item)}
        <a class="text-[1.03rem] leading-[1.35] text-[#2b3344] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer" data-click="${item.article_id || ""}">
          ${escapeHtml(title)}
        </a>
        <p class="m-0 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
      </div>
      <div class="min-h-[102px] rounded-[20px] ${sourceHueFor(item.source) || defaultHue}"></div>
    </article>
  `;
};

const renderMoreStory = (item) => {
  const title = truncate(item.title || "Untitled", 150);
  const sourceLabel = item.source_label || item.source || "Unknown";
  const url = item.url || "";
  return `
    <article class="grid items-center gap-4 border-t border-[rgba(78,104,135,0.16)] py-5 sm:grid-cols-[minmax(0,1fr)_auto]" data-article-id="${item.article_id || ""}">
      <div>
        <p class="mb-2 text-[0.9rem] font-bold text-[#4a5871]">${escapeHtml(sourceLabel)}</p>
        <a class="text-[1.03rem] leading-[1.35] text-[#2b3344] no-underline" href="${escapeHtml(url)}" target="_blank" rel="noreferrer" data-click="${item.article_id || ""}">
          ${escapeHtml(title)}
        </a>
        <p class="m-0 mt-2 text-[0.97rem] leading-[1.5] text-[#637089]">${escapeHtml(renderByline(item))}</p>
        ${renderActions(item)}
      </div>
      <div class="text-[2rem] font-semibold tracking-[-0.06em] text-[#9bb2cf]">#${escapeHtml(item.rank || "")}</div>
    </article>
  `;
};

const renderHeadline = (mode, fellBack, tagLabel) => {
  if (mode === "for_you" && !fellBack) return "For you";
  if (tagLabel) return `${tagLabel} stories`;
  return "Top stories";
};

const renderNewsLayout = (results, { mode, fellBack, tagLabel }) => {
  if (!results.length) {
    return `
      <section class="${panelClass}">
        <div class="${panelInnerClass}">
          <div class="${panelHeaderClass}">
            <h2 class="m-0 text-[clamp(1.7rem,2vw,2.25rem)] font-medium tracking-[-0.04em]">${escapeHtml(renderHeadline(mode, fellBack, tagLabel))}</h2>
            <span class="text-[2rem] leading-none">›</span>
          </div>
          <div class="${dividerClass}"></div>
          <div class="${emptyStateClass}">No stories matched. Widen the window, change the topic, or hit Refresh again — the backend may still be filling its cache.</div>
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
          <h2 class="m-0 text-[clamp(1.7rem,2vw,2.25rem)] font-medium tracking-[-0.04em]">${escapeHtml(renderHeadline(mode, fellBack, tagLabel))}</h2>
          <span class="text-[2rem] leading-none">›</span>
        </div>
        ${fellBack ? `<p class="mt-1 mb-0 text-[0.85rem] text-[#7a8aa6]">Not enough signals yet — showing top stories. Like / hide a few articles to unlock For you.</p>` : ""}
        <div class="${dividerClass}"></div>
        ${renderLeadStory(lead)}
        <div class="mt-6 grid gap-[18px] xl:grid-cols-3">
          ${primaryRows.map(renderHeadlineRow).join("")}
        </div>
        ${moreRows.length ? `
              <div class="mt-7 rounded-full bg-[#eff2f7] px-6 py-[18px] text-center text-base font-bold text-[#45505f]">See more headlines & perspectives</div>
              <div class="mt-6 grid gap-0">
                ${moreRows.map(renderMoreStory).join("")}
              </div>
            ` : ""}
      </div>
    </section>
    <aside class="${panelClass}">
      <div class="${panelInnerClass}">
        <div class="${panelHeaderClass}">
          <h2 class="m-0 text-[clamp(1.45rem,1.7vw,1.9rem)] font-medium tracking-[-0.04em]">Live updates</h2>
          <span class="text-[2rem] leading-none">›</span>
        </div>
        <div class="${dividerClass}"></div>
        <div class="grid gap-0">
          ${railRows.length ? railRows.map(renderRailStory).join("") : `<div class="${emptyStateClass}">Not enough stories yet to fill the side rail.</div>`}
        </div>
      </div>
    </aside>
  `;
};

const renderTrending = (clusters) => {
  if (!clusters.length) {
    return `
      <section class="${panelClass}">
        <div class="${panelInnerClass}">
          <div class="${panelHeaderClass}">
            <h2 class="m-0 text-[clamp(1.7rem,2vw,2.25rem)] font-medium tracking-[-0.04em]">Trending across sources</h2>
          </div>
          <div class="${dividerClass}"></div>
          <div class="${emptyStateClass}">No multi-source trends detected in this window. Try a wider window.</div>
        </div>
      </section>
    `;
  }
  return `
    <section class="${panelClass}">
      <div class="${panelInnerClass}">
        <div class="${panelHeaderClass}">
          <h2 class="m-0 text-[clamp(1.7rem,2vw,2.25rem)] font-medium tracking-[-0.04em]">Trending across sources</h2>
        </div>
        <div class="${dividerClass}"></div>
        <div class="grid gap-6">
          ${clusters.map((c, i) => `
            <article class="grid gap-2">
              <div class="flex items-center justify-between gap-3">
                <h3 class="m-0 text-[1.15rem] font-semibold text-[#173a69]">${escapeHtml(c.representative ? c.representative.title : "Cluster #" + (i+1))}</h3>
                <span class="text-[0.75rem] font-bold text-[#7a8aa6]">${c.sources.length} sources • ${c.article_count} stories</span>
              </div>
              <ul class="m-0 grid gap-1.5 pl-0">
                ${c.members.map((m) => `
                  <li class="flex items-center justify-between gap-3 border-t border-[rgba(78,104,135,0.16)] pt-1.5">
                    <a href="${escapeHtml(m.url || "")}" target="_blank" rel="noreferrer" class="text-[0.97rem] text-[#2b3344] no-underline" data-click="${m.article_id || ""}">${escapeHtml(truncate(m.title, 130))}</a>
                    <span class="shrink-0 text-[0.78rem] font-semibold text-[#637089]">${escapeHtml(m.source_label)}</span>
                  </li>
                `).join("")}
              </ul>
            </article>
          `).join("")}
        </div>
      </div>
    </section>
  `;
};

const form = document.getElementById("news-form");
const button = document.getElementById("news-run-btn");
const trendingBtn = document.getElementById("news-trending-btn");
const errorBox = document.getElementById("news-error");
const sourceStatus = document.getElementById("news-source-status");
const resultsBox = document.getElementById("news-results");
const debugBox = document.getElementById("news-debug-json");
const resultCount = document.getElementById("news-result-count");
const sourcesList = document.getElementById("news-sources-list");
const sourcesPlaceholder = document.getElementById("news-sources-placeholder");
const sourcesCount = document.getElementById("news-sources-count");
const sourcesAll = document.getElementById("news-sources-all");
const sourcesNone = document.getElementById("news-sources-none");
const modeToggle = document.getElementById("news-mode-toggle");
const windowToggle = document.getElementById("news-window-toggle");
const tagsRow = document.getElementById("news-tags-row");
const tagsPlaceholder = document.getElementById("news-tags-placeholder");

const tagLabelCache = {};

const setActive = (container, attr, value) => {
  if (!container) return;
  container.querySelectorAll(`[data-${attr}]`).forEach((btn) => {
    btn.setAttribute("data-active", String(btn.getAttribute(`data-${attr}`) === value));
  });
};

const renderTagChip = (tag) => `
  <button type="button" data-tag="${escapeHtml(tag.id)}" title="${escapeHtml(tag.description || "")}" class="cursor-pointer rounded-full border border-[rgba(93,112,141,0.28)] bg-white px-2.5 py-1 text-[0.68rem] font-semibold text-[#35516f] transition data-[active=true]:border-[#1a73e8] data-[active=true]:bg-[#d8ecff] data-[active=true]:text-[#14679c]" data-active="false">${escapeHtml(tag.label)}</button>
`;

const loadTags = async () => {
  try {
    const response = await fetch(`${apiBase}/news/tags`);
    if (!response.ok) throw new Error("Failed to load tags");
    const data = await response.json();
    const tags = data.tags || [];
    for (const t of tags) tagLabelCache[t.id] = t.label;
    if (tagsPlaceholder) tagsPlaceholder.remove();
    if (tagsRow) tagsRow.insertAdjacentHTML("beforeend", tags.map(renderTagChip).join(""));
  } catch (err) {
    if (tagsPlaceholder) tagsPlaceholder.textContent = `Topics unavailable: ${err.message}`;
  }
};

const renderSourceCheckbox = (source) => {
  const checked = source.importance >= 0.6 ? "checked" : "";
  return `
    <label class="relative cursor-pointer">
      <input class="peer absolute opacity-0 pointer-events-none" type="checkbox" name="sources" value="${escapeHtml(source.id)}" ${checked} />
      <span class="inline-flex min-h-6 items-center rounded-lg border border-[rgba(93,112,141,0.28)] bg-[rgba(255,255,255,0.94)] px-2 text-[0.68rem] font-semibold text-[#35516f] transition peer-checked:border-[#d8ecff] peer-checked:bg-[#d8ecff] peer-checked:text-[#14679c]">${escapeHtml(source.label)}</span>
    </label>
  `;
};

const loadSources = async () => {
  try {
    const response = await fetch(`${apiBase}/news/sources`, { credentials: "include" });
    if (!response.ok) throw new Error("Failed to load sources");
    const data = await response.json();
    const sources = data.sources || [];
    sources.sort((a, b) => b.importance - a.importance || a.label.localeCompare(b.label));
    for (const s of sources) sourceImportanceCache[s.id] = s.importance;
    if (sourcesPlaceholder) sourcesPlaceholder.remove();
    if (sourcesList) {
      const legend = sourcesList.querySelector("legend");
      sourcesList.innerHTML = "";
      sourcesList.appendChild(legend);
      sourcesList.insertAdjacentHTML("beforeend", sources.map(renderSourceCheckbox).join(""));
    }
    if (sourcesCount) sourcesCount.textContent = `(${sources.length})`;
  } catch (err) {
    if (sourcesPlaceholder) sourcesPlaceholder.textContent = `Sources unavailable: ${err.message}`;
  }
};

const sendSignal = async (articleId, kind) => {
  if (!articleId) return;
  try {
    await fetch(`${apiBase}/news/signal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ article_id: Number(articleId), kind }),
    });
  } catch (err) {
    /* swallow */
  }
};

const wireResultActions = () => {
  if (!resultsBox) return;
  resultsBox.querySelectorAll("[data-click]").forEach((el) => {
    const articleId = el.getAttribute("data-click");
    if (!articleId) return;
    el.addEventListener("click", () => sendSignal(articleId, "click"));
  });
  resultsBox.querySelectorAll("[data-signal]").forEach((btn) => {
    const articleId = btn.getAttribute("data-article");
    const kind = btn.getAttribute("data-signal");
    btn.addEventListener("click", () => {
      sendSignal(articleId, kind);
      const card = btn.closest("[data-article-id]");
      if (kind === "hide" && card) card.style.display = "none";
      if (kind === "like") {
        btn.textContent = "✓ Thanks";
        btn.disabled = true;
      }
    });
  });
};

const collectSources = () => {
  const formData = new FormData(form);
  return formData.getAll("sources").map(String);
};

const refreshFeed = async () => {
  if (!form || !button || !errorBox || !sourceStatus || !resultsBox || !debugBox || !resultCount) return;
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
    const sources = collectSources();

    const body = {
      query,
      limit,
      hours_back: state.hoursBack,
      sources,
      mode: state.mode,
      tag: state.tag || null,
    };

    const response = await fetch(`${apiBase}/news`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if ([502, 503, 504].includes(response.status)) throw new Error(backendHelp);
      throw new Error(data?.detail?.message || "Request failed");
    }
    const results = data.results || [];
    const debug = data.debug || {};
    const modeUsed = data.mode || "discover";
    const fellBack = Boolean(debug.fell_back_to_discover);
    const tagLabel = state.tag ? tagLabelCache[state.tag] || state.tag : "";

    resultCount.textContent = `${results.length} ${results.length === 1 ? "Story" : "Stories"} • ${modeUsed === "for_you" ? "For you" : "Top"}`;
    sourceStatus.textContent = `${debug.total_candidates || 0} stories in cache • ${debug.total_ms || 0}ms`;
    resultsBox.innerHTML = renderNewsLayout(results, { mode: modeUsed, fellBack, tagLabel });
    debugBox.textContent = JSON.stringify(debug, null, 2);
    wireResultActions();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    errorBox.textContent = message.includes("Failed to fetch") || message.includes("NetworkError") ? backendHelp : message;
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
    button.textContent = "Refresh";
  }
};

const refreshTrending = async () => {
  if (!trendingBtn || !resultsBox || !resultCount || !errorBox) return;
  errorBox.textContent = "";
  resultsBox.innerHTML = "";
  resultCount.textContent = "Loading trends";
  trendingBtn.disabled = true;
  trendingBtn.textContent = "Loading...";
  try {
    const response = await fetch(`${apiBase}/news/trending?hours_back=${state.hoursBack}&min_sources=2&limit=10`, {
      credentials: "include",
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.detail?.message || "Trending failed");
    const clusters = data.clusters || [];
    resultCount.textContent = `${clusters.length} Trends`;
    resultsBox.innerHTML = renderTrending(clusters);
    if (sourceStatus) sourceStatus.textContent = `${clusters.length} multi-source clusters`;
    wireResultActions();
  } catch (error) {
    errorBox.textContent = error.message;
    resultCount.textContent = "Trending Failed";
  } finally {
    trendingBtn.disabled = false;
    trendingBtn.textContent = "Trending";
  }
};

if (sourcesAll) sourcesAll.addEventListener("click", () => {
  sourcesList?.querySelectorAll("input[type=checkbox]").forEach((cb) => { cb.checked = true; });
});
if (sourcesNone) sourcesNone.addEventListener("click", () => {
  sourcesList?.querySelectorAll("input[type=checkbox]").forEach((cb) => { cb.checked = false; });
});

if (modeToggle) {
  modeToggle.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-mode]");
    if (!btn) return;
    state.mode = btn.getAttribute("data-mode") || "discover";
    setActive(modeToggle, "mode", state.mode);
    refreshFeed();
  });
}

if (windowToggle) {
  windowToggle.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-window]");
    if (!btn) return;
    state.window = btn.getAttribute("data-window") || "24h";
    state.hoursBack = Number(btn.getAttribute("data-hours") || 24);
    setActive(windowToggle, "window", state.window);
    refreshFeed();
  });
}

if (tagsRow) {
  tagsRow.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-tag]");
    if (!btn) return;
    state.tag = btn.getAttribute("data-tag") || "";
    setActive(tagsRow, "tag", state.tag);
    refreshFeed();
  });
}

if (form && button) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    refreshFeed();
  });
}
if (trendingBtn) trendingBtn.addEventListener("click", refreshTrending);

(async () => {
  await Promise.all([loadSources(), loadTags()]);
  if (form) refreshFeed();
})();
