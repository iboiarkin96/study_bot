"use strict";

function normalizeParts(parts) {
  const out = [];
  for (const part of parts) {
    if (!part || part === ".") {
      continue;
    }
    if (part === "..") {
      if (out.length > 0) {
        out.pop();
      }
      continue;
    }
    out.push(part);
  }
  return out;
}

function relHref(fromDir, targetRelPath) {
  const fromParts = normalizeParts(fromDir.split("/"));
  const targetParts = normalizeParts(targetRelPath.split("/"));

  let i = 0;
  while (i < fromParts.length && i < targetParts.length && fromParts[i] === targetParts[i]) {
    i += 1;
  }

  const up = new Array(fromParts.length - i).fill("..");
  const down = targetParts.slice(i);
  const joined = [...up, ...down].join("/");
  return joined || ".";
}

function currentDocsRelPath() {
  const path = window.location.pathname.replace(/\\/g, "/");
  const marker = "/docs/";
  const idx = path.lastIndexOf(marker);
  if (idx >= 0) {
    return path.slice(idx + marker.length);
  }
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) {
    return "index.html";
  }
  const docsRootFirstSegments = new Set([
    "index.html",
    "adr",
    "api",
    "assets",
    "audit",
    "backlog",
    "developer",
    "howto",
    "internal",
    "openapi",
    "rfc",
    "runbooks",
  ]);
  if (docsRootFirstSegments.has(parts[0])) {
    return parts.join("/");
  }
  if (parts.length >= 2) {
    return parts.slice(1).join("/");
  }
  return parts[0] || "index.html";
}

function activeTarget(relPath) {
  if (relPath === "index.html" || relPath.endsWith("/index.html")) {
    return "index.html";
  }
  if (relPath.startsWith("adr/")) {
    return "adr/README.html";
  }
  if (relPath.startsWith("developer/")) {
    return "internal/developers.html";
  }
  if (relPath.startsWith("backlog/")) {
    return "backlog/README.html";
  }
  if (relPath.startsWith("runbooks/")) {
    return "runbooks/README.html";
  }
  if (relPath.startsWith("rfc/")) {
    return "rfc/README.html";
  }
  if (relPath.startsWith("audit/")) {
    return "audit/README.html";
  }
  if (relPath === "internal/system-design.html") {
    return "internal/system-design.html";
  }
  if (relPath.startsWith("internal/")) {
    return "internal/README.html";
  }
  if (relPath.startsWith("howto/")) {
    return "howto/README.html";
  }
  if (relPath.startsWith("api/")) {
    return "api/index.html";
  }
  if (relPath === "openapi-explorer.html" || relPath === "openapi/openapi-explorer.html") {
    return "openapi/openapi-explorer.html";
  }
  if (relPath === "internal/developers.html") {
    return "internal/developers.html";
  }
  return "index.html";
}

const DOCS_SEARCH_INDEX_PATH = "assets/search-index.json";
const DOCS_SEARCH_MAX_RESULTS = 10;
const DOCS_SEARCH_DEBOUNCE_MS = 120;
const DOCS_SEARCH_MAX_PREFIX_EXPANSIONS = 24;
const DOCS_SEARCH_SUCCESS_WINDOW_MS = 60_000;
const DOCS_FEEDBACK_REPOSITORY = "iboiarkin96/study_bot";
const DOCS_FEEDBACK_TEMPLATE = "docs_feedback.yml";
const DOCS_FEEDBACK_LABELS = ["docs-feedback"];
let docsSearchIndexPromise = null;
let docsSearchSessionId = null;
let docsSearchQuerySeq = 0;

function docsSearchTelemetryConfig() {
  const meta = document.querySelector('meta[name="docs-search-telemetry-endpoint"]');
  const endpointFromMeta = meta ? String(meta.getAttribute("content") || "").trim() : "";
  if (endpointFromMeta) {
    return { endpoint: endpointFromMeta };
  }
  const host = window.location.hostname;
  const isLocalHost = host === "127.0.0.1" || host === "localhost";
  if (isLocalHost) {
    return { endpoint: `${window.location.protocol}//${host}:8000/internal/telemetry/docs-search` };
  }
  return { endpoint: "" };
}

function getDocsSearchSessionId() {
  if (!docsSearchSessionId) {
    docsSearchSessionId = `s_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  }
  return docsSearchSessionId;
}

function makeDocsSearchQueryId() {
  docsSearchQuerySeq += 1;
  return `q_${Date.now()}_${docsSearchQuerySeq}`;
}

function emitDocsSearchTelemetry(eventName, payload) {
  const body = {
    event: eventName,
    emitted_at_ms: Date.now(),
    page_path: window.location.pathname,
    ...payload,
  };

  document.dispatchEvent(
    new CustomEvent("docs-search-telemetry", {
      detail: body,
    })
  );

  const { endpoint } = docsSearchTelemetryConfig();
  if (!endpoint) {
    return;
  }

  const serialized = JSON.stringify(body);
  fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: serialized,
    credentials: "same-origin",
    keepalive: true,
  }).catch(() => { });
}

function docsSearchIndexUrl(fromDir) {
  return relHref(fromDir, DOCS_SEARCH_INDEX_PATH);
}

function normalizeSearchText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s/_-]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenizeSearchText(value) {
  const normalized = normalizeSearchText(value);
  if (!normalized) {
    return [];
  }
  return normalized.match(/[a-z0-9]+/g) || [];
}

async function loadDocsSearchIndex(fromDir) {
  if (!docsSearchIndexPromise) {
    docsSearchIndexPromise = fetch(docsSearchIndexUrl(fromDir), {
      credentials: "same-origin",
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`search-index load failed: ${response.status}`);
        }
        return response.json();
      })
      .then((indexData) => {
        if (!indexData || typeof indexData !== "object") {
          return null;
        }
        if (!Array.isArray(indexData.docs) || typeof indexData.postings !== "object") {
          return null;
        }
        const docs = indexData.docs.map((doc) => ({
          id: Number(doc.id),
          title: String(doc.title || ""),
          url: String(doc.url || ""),
          section: String(doc.section || ""),
          preview: String(doc.preview || ""),
          contentLen: Number(doc.content_len || 1),
          titleNorm: normalizeSearchText(doc.title || ""),
          urlNorm: normalizeSearchText(doc.url || ""),
          sectionNorm: normalizeSearchText(doc.section || ""),
        }));
        const vocabulary = Object.keys(indexData.postings);
        const avgContentLen =
          Number(indexData?.meta?.avg_content_len) > 0 ? Number(indexData.meta.avg_content_len) : 1;
        return {
          docs,
          postings: indexData.postings,
          docFreq: indexData.doc_freq || {},
          docCount: docs.length,
          avgContentLen,
          vocabulary,
        };
      })
      .catch((error) => {
        docsSearchIndexPromise = null;
        throw error;
      });
  }
  return docsSearchIndexPromise;
}

function expandTokenCandidates(token, vocabulary, isLastToken) {
  if (!token) {
    return [];
  }
  if (!isLastToken || token.length < 3) {
    return [token];
  }
  const expanded = [token];
  for (const candidate of vocabulary) {
    if (candidate !== token && candidate.startsWith(token)) {
      expanded.push(candidate);
      if (expanded.length >= DOCS_SEARCH_MAX_PREFIX_EXPANSIONS) {
        break;
      }
    }
  }
  return expanded;
}

function idf(docCount, docFreq) {
  return Math.log(1 + (docCount + 1) / (docFreq + 0.5));
}

function tf(tfValue) {
  return Math.log(1 + tfValue);
}

function runDocsSearch(indexData, query) {
  if (!indexData || !Array.isArray(indexData.docs) || indexData.docs.length === 0) {
    return [];
  }
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) {
    return [];
  }
  const queryTokens = tokenizeSearchText(normalizedQuery);
  if (queryTokens.length === 0) {
    return [];
  }

  const candidates = new Map();
  queryTokens.forEach((token, tokenIndex) => {
    const tokenVariants = expandTokenCandidates(
      token,
      indexData.vocabulary,
      tokenIndex === queryTokens.length - 1
    );
    tokenVariants.forEach((variant) => {
      const postings = indexData.postings[variant];
      if (!Array.isArray(postings)) {
        return;
      }
      const tokenIdf = idf(indexData.docCount, Number(indexData.docFreq[variant] || 0));
      postings.forEach((posting) => {
        const [docId, tfTitle, tfUrl, tfSection, tfContent] = posting;
        const fieldScore =
          8.0 * tf(tfTitle || 0) +
          4.0 * tf(tfUrl || 0) +
          2.0 * tf(tfSection || 0) +
          1.4 * tf(tfContent || 0);
        if (fieldScore <= 0) {
          return;
        }
        const prev = candidates.get(docId) || 0;
        candidates.set(docId, prev + tokenIdf * fieldScore);
      });
    });
  });

  const scored = [];
  candidates.forEach((baseScore, docId) => {
    const entry = indexData.docs[docId];
    if (!entry) {
      return;
    }
    let score = baseScore;

    const allTokensInTitle = queryTokens.every((token) => entry.titleNorm.includes(token));
    const allTokensInUrl = queryTokens.every((token) => entry.urlNorm.includes(token));
    if (allTokensInTitle) {
      score += 9;
    }
    if (allTokensInUrl) {
      score += 4;
    }
    if (entry.titleNorm.includes(normalizedQuery)) {
      score += 12;
    }
    if (entry.urlNorm.includes(normalizedQuery)) {
      score += 6;
    }
    if (entry.titleNorm.startsWith(normalizedQuery)) {
      score += 5;
    }
    if (entry.sectionNorm === normalizedQuery) {
      score += 3;
    }

    const lenRatio = entry.contentLen / Math.max(indexData.avgContentLen, 1);
    const lengthNorm = 1 / (1 + 0.08 * Math.max(0, lenRatio - 1));
    score *= lengthNorm;

    if (score > 0) {
      scored.push({ entry, score, docId });
    }
  });

  scored.sort((a, b) => {
    if (b.score !== a.score) {
      return b.score - a.score;
    }
    if (a.docId !== b.docId) {
      return a.docId - b.docId;
    }
    return a.entry.title.localeCompare(b.entry.title);
  });
  return scored.slice(0, DOCS_SEARCH_MAX_RESULTS).map((item) => item.entry);
}

function buildSearchResultHref(fromDir, targetUrl) {
  const rel = String(targetUrl || "").replace(/^\/+/, "");
  if (!rel) {
    return "#";
  }
  return relHref(fromDir, rel);
}

function renderDocsSearchResults(list, results, fromDir, selectedIndex, listId) {
  list.replaceChildren();
  if (!results || results.length === 0) {
    const empty = document.createElement("li");
    empty.className = "docs-search__empty";
    empty.setAttribute("role", "status");
    empty.textContent = "No matches";
    list.appendChild(empty);
    return;
  }

  results.forEach((item, index) => {
    const li = document.createElement("li");
    li.setAttribute("role", "presentation");
    const link = document.createElement("a");
    const optionId = `${listId}-option-${index}`;
    link.id = optionId;
    link.className = "docs-search__result-link";
    link.setAttribute("role", "option");
    link.setAttribute("aria-selected", index === selectedIndex ? "true" : "false");
    if (index === selectedIndex) {
      link.classList.add("docs-search__result-link--active");
    }
    link.href = buildSearchResultHref(fromDir, item.url);

    const title = document.createElement("span");
    title.className = "docs-search__result-title";
    title.textContent = item.title || item.url;

    const meta = document.createElement("span");
    meta.className = "docs-search__result-meta";
    const section = item.section ? `${item.section} - ` : "";
    meta.textContent = `${section}${item.url}`;

    const preview = document.createElement("span");
    preview.className = "docs-search__result-preview";
    preview.textContent = item.preview || "";

    link.appendChild(title);
    link.appendChild(meta);
    if (item.preview) {
      link.appendChild(preview);
    }
    li.appendChild(link);
    list.appendChild(li);
  });
}

function mountDocsSearch(nav, fromDir) {
  const searchUid = `docs-search-${Math.random().toString(36).slice(2, 9)}`;
  const inputId = `${searchUid}-input`;
  const resultsId = `${searchUid}-results`;
  const wrap = document.createElement("div");
  wrap.className = "docs-search";

  const label = document.createElement("label");
  label.className = "docs-search__label";
  label.setAttribute("for", inputId);
  label.textContent = "Search docs";

  const input = document.createElement("input");
  input.id = inputId;
  input.className = "docs-search__input";
  input.type = "search";
  input.placeholder = "Type to search all docs...";
  input.setAttribute("autocomplete", "off");
  input.setAttribute("spellcheck", "false");
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", resultsId);
  input.setAttribute("aria-expanded", "false");

  const results = document.createElement("ul");
  results.id = resultsId;
  results.className = "docs-search__results";
  results.setAttribute("role", "listbox");
  results.hidden = true;

  wrap.appendChild(label);
  wrap.appendChild(input);
  wrap.appendChild(results);
  nav.appendChild(wrap);

  let debounceId = null;
  let activeResults = [];
  let selectedIndex = -1;
  let activeQueryCtx = null;
  let firstQueryTs = null;
  let successTracked = false;

  function hideResults() {
    results.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    results.replaceChildren();
    activeResults = [];
    selectedIndex = -1;
  }

  function resetSearchSession() {
    activeQueryCtx = null;
    firstQueryTs = null;
    successTracked = false;
  }

  function showStatus(message, isError) {
    results.hidden = false;
    input.setAttribute("aria-expanded", "true");
    input.removeAttribute("aria-activedescendant");
    const item = document.createElement("li");
    item.className = isError ? "docs-search__status docs-search__status--error" : "docs-search__status";
    item.setAttribute("role", "status");
    item.textContent = message;
    results.replaceChildren(item);
  }

  async function searchNow(query) {
    const normalized = normalizeSearchText(query);
    if (!normalized) {
      hideResults();
      resetSearchSession();
      return;
    }
    const sessionId = getDocsSearchSessionId();
    const queryId = makeDocsSearchQueryId();
    const searchStartedAt = performance.now();
    showStatus("Searching...", false);
    try {
      const indexData = await loadDocsSearchIndex(fromDir);
      activeResults = runDocsSearch(indexData, query);
      selectedIndex = activeResults.length > 0 ? 0 : -1;
      results.hidden = false;
      input.setAttribute("aria-expanded", "true");
      if (selectedIndex >= 0) {
        input.setAttribute("aria-activedescendant", `${resultsId}-option-${selectedIndex}`);
      } else {
        input.removeAttribute("aria-activedescendant");
      }
      renderDocsSearchResults(results, activeResults, fromDir, selectedIndex, resultsId);

      const now = Date.now();
      if (!firstQueryTs) {
        firstQueryTs = now;
      }
      const topResults = activeResults.map((item, index) => ({ rank: index + 1, url: item.url }));
      activeQueryCtx = {
        queryId,
        sessionId,
        queryStartedAt: now,
        resultCount: activeResults.length,
      };
      emitDocsSearchTelemetry("search_query", {
        session_id: sessionId,
        query_id: queryId,
        query_text: normalized,
        query_len: normalized.length,
        tokens_count: tokenizeSearchText(normalized).length,
        results_count: activeResults.length,
        latency_ms: Math.max(0, Math.round(performance.now() - searchStartedAt)),
        top_results: topResults,
      });
    } catch (error) {
      const fileProtocol = window.location.protocol === "file:";
      const message = fileProtocol
        ? "Could not load search index. Open docs over HTTP(S), not file://."
        : "Could not load search index.";
      showStatus(message, true);
      emitDocsSearchTelemetry("search_query_error", {
        session_id: sessionId,
        query_id: queryId,
        query_text: normalized,
        query_len: normalized.length,
        error: "index_load_failed",
      });
    }
  }

  function trackSearchClick(hit, rank, source) {
    if (!hit || !hit.url) {
      return;
    }

    const now = Date.now();
    const sessionId = getDocsSearchSessionId();
    const queryCtx = activeQueryCtx;
    emitDocsSearchTelemetry("search_result_click", {
      session_id: sessionId,
      query_id: queryCtx ? queryCtx.queryId : null,
      result_rank: rank,
      result_url: hit.url,
      results_count: queryCtx ? queryCtx.resultCount : activeResults.length,
      source,
    });

    if (
      queryCtx &&
      !successTracked &&
      firstQueryTs &&
      now - queryCtx.queryStartedAt <= DOCS_SEARCH_SUCCESS_WINDOW_MS
    ) {
      successTracked = true;
      emitDocsSearchTelemetry("search_success", {
        session_id: sessionId,
        query_id: queryCtx.queryId,
        result_rank: rank,
        result_url: hit.url,
        time_to_success_ms: Math.max(0, now - firstQueryTs),
        time_to_click_ms: Math.max(0, now - queryCtx.queryStartedAt),
      });
    }
  }

  input.addEventListener("focus", () => {
    loadDocsSearchIndex(fromDir).catch(() => { });
  });

  input.addEventListener("input", () => {
    if (debounceId) {
      clearTimeout(debounceId);
    }
    debounceId = window.setTimeout(() => {
      searchNow(input.value);
    }, DOCS_SEARCH_DEBOUNCE_MS);
  });

  input.addEventListener("keydown", (event) => {
    if (results.hidden || activeResults.length === 0) {
      if (event.key === "Escape") {
        hideResults();
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      selectedIndex = (selectedIndex + 1) % activeResults.length;
      input.setAttribute("aria-activedescendant", `${resultsId}-option-${selectedIndex}`);
      renderDocsSearchResults(results, activeResults, fromDir, selectedIndex, resultsId);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      selectedIndex = (selectedIndex - 1 + activeResults.length) % activeResults.length;
      input.setAttribute("aria-activedescendant", `${resultsId}-option-${selectedIndex}`);
      renderDocsSearchResults(results, activeResults, fromDir, selectedIndex, resultsId);
      return;
    }
    if (event.key === "Enter" && selectedIndex >= 0) {
      event.preventDefault();
      const hit = activeResults[selectedIndex];
      if (hit && hit.url) {
        trackSearchClick(hit, selectedIndex + 1, "keyboard_enter");
        window.location.assign(buildSearchResultHref(fromDir, hit.url));
      }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      hideResults();
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    const link = target && target.closest ? target.closest(".docs-search__result-link") : null;
    if (link && wrap.contains(link)) {
      const links = [...results.querySelectorAll(".docs-search__result-link")];
      const hitIndex = links.indexOf(link);
      if (hitIndex >= 0 && hitIndex < activeResults.length) {
        trackSearchClick(activeResults[hitIndex], hitIndex + 1, "mouse_click");
      }
      return;
    }
    if (!wrap.contains(event.target)) {
      hideResults();
    }
  });
}

function appendTopNavLinks(container, items, fromDir, active) {
  for (const item of items) {
    const link = document.createElement("a");
    link.textContent = item.label;
    link.href = relHref(fromDir, item.target);
    if (item.className) {
      link.className = item.className;
    }
    if (item.target === active) {
      link.classList.add("is-active");
      link.setAttribute("aria-current", "page");
    }
    container.appendChild(link);
  }
}

function renderTopNav() {
  const host = document.getElementById("docs-top-nav");
  if (!host) {
    return;
  }

  const relPath = currentDocsRelPath();
  const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
  const active = activeTarget(relPath);
  const internalItems = [
    { label: "Home", target: "index.html" },
    { label: "Internal docs", target: "internal/README.html" },
    { label: "API assessment reports", target: "audit/README.html" },
    { label: "⭐Backlog", target: "backlog/README.html", className: "top-nav__link--backlog" },
  ];
  const publicItems = [
    { label: "OpenAPI explorer", target: "openapi/openapi-explorer.html" },
    { label: "Pdoc API docs", target: "api/index.html" },
  ];

  const nav = document.createElement("nav");
  nav.className = "top-nav";
  nav.setAttribute("aria-label", "Documentation navigation");

  const groups = document.createElement("div");
  groups.className = "top-nav__groups";

  const internalSection = document.createElement("section");
  internalSection.className = "top-nav__group top-nav__group--internal";
  internalSection.setAttribute("aria-labelledby", "top-nav-internal-label");

  const internalHead = document.createElement("div");
  internalHead.className = "top-nav__group-head";
  internalHead.id = "top-nav-internal-label";

  const internalTitle = document.createElement("span");
  internalTitle.className = "top-nav__group-title";
  internalTitle.textContent = "Internal";

  const internalHint = document.createElement("span");
  internalHint.className = "top-nav__group-hint";
  internalHint.textContent = "Team, architecture, and operations";

  internalHead.appendChild(internalTitle);
  internalHead.appendChild(internalHint);

  const internalLinks = document.createElement("div");
  internalLinks.className = "top-nav__links";
  internalLinks.id = "top-nav-internal-links";
  appendTopNavLinks(internalLinks, internalItems, fromDir, active);

  internalSection.appendChild(internalHead);
  internalSection.appendChild(internalLinks);

  const split = document.createElement("div");
  split.className = "top-nav__split";
  split.setAttribute("aria-hidden", "true");

  const publicSection = document.createElement("section");
  publicSection.className = "top-nav__group top-nav__group--public";
  publicSection.setAttribute("aria-labelledby", "top-nav-public-label");

  const publicHead = document.createElement("div");
  publicHead.className = "top-nav__group-head";
  publicHead.id = "top-nav-public-label";

  const publicTitle = document.createElement("span");
  publicTitle.className = "top-nav__group-title";
  publicTitle.textContent = "Code";

  const publicHint = document.createElement("span");
  publicHint.className = "top-nav__group-hint";
  publicHint.textContent = "Development documentation";

  publicHead.appendChild(publicTitle);
  publicHead.appendChild(publicHint);

  const publicLinks = document.createElement("div");
  publicLinks.className = "top-nav__links";
  appendTopNavLinks(publicLinks, publicItems, fromDir, active);

  publicSection.appendChild(publicHead);
  publicSection.appendChild(publicLinks);

  groups.appendChild(internalSection);
  groups.appendChild(split);
  groups.appendChild(publicSection);
  nav.appendChild(groups);
  mountDocsSearch(nav, fromDir);

  /* Keep `#docs-top-nav` in the DOM — `initAutoInPageToc` and formatters anchor off this host. */
  host.replaceChildren(nav);
}

/** ADR: single `data-adr-weight` on <main> (−1…7) → current status + linear status log. */

const ADR_STEPS = [
  { w: 0, axis: "Decision", label: "Proposed" },
  { w: 1, axis: "Decision", label: "Accepted" },
  { w: 2, axis: "Decision", label: "Superseded" },
  { w: 3, axis: "Documentation", label: "Draft" },
  { w: 4, axis: "Documentation", label: "Ready" },
  { w: 5, axis: "Implementation", label: "Not started" },
  { w: 6, axis: "Implementation", label: "In progress" },
  { w: 7, axis: "Implementation", label: "Done" },
];

function parseAdrWeightValue(raw) {
  const n = parseInt(String(raw ?? "-1").trim(), 10);
  if (Number.isNaN(n)) {
    return -1;
  }
  if (n < -1) {
    return -1;
  }
  if (n > 7) {
    return 7;
  }
  return n;
}

function adrCurrentWeight(main) {
  return parseAdrWeightValue(main.getAttribute("data-adr-weight"));
}

function stepKind(stepWeight, globalMax) {
  if (globalMax < 0) {
    return "todo";
  }
  if (stepWeight < globalMax) {
    return "done";
  }
  if (stepWeight === globalMax) {
    // Terminal step: show green (same as passed), not yellow "in progress"
    if (stepWeight === 7) {
      return "done";
    }
    return "current";
  }
  return "todo";
}

/** Current status banner: emoji + label + CSS tone (draft / ongoing / declined / done). */
function adrCurrentStatusPresentation(globalMax) {
  const rows = [
    [-1, { emoji: "📝", label: "Draft", tone: "draft" }],
    [0, { emoji: "⏳", label: "In progress", tone: "ongoing" }],
    [1, { emoji: "⏳", label: "In progress", tone: "ongoing" }],
    [2, { emoji: "🚫", label: "Declined", tone: "declined" }],
    [3, { emoji: "⏳", label: "In progress", tone: "ongoing" }],
    [4, { emoji: "⏳", label: "In progress", tone: "ongoing" }],
    [5, { emoji: "⏳", label: "In progress", tone: "ongoing" }],
    [6, { emoji: "⏳", label: "In progress", tone: "ongoing" }],
    [7, { emoji: "⭐", label: "Done", tone: "done" }],
  ];
  const map = new Map(rows);
  const hit = map.get(globalMax);
  if (hit) {
    return hit;
  }
  return {
    emoji: "❔",
    label: `Weight ${globalMax}`,
    tone: "ongoing",
  };
}

function renderAdrCurrentStatus(nav, globalMax) {
  const box = document.createElement("div");
  box.className = "adr-current-status";
  box.setAttribute("role", "status");

  const pres = adrCurrentStatusPresentation(globalMax);
  box.classList.add(`adr-current-status--${pres.tone}`);

  const label = document.createElement("span");
  label.className = "adr-current-status__label";
  label.textContent = "Current status:";

  const value = document.createElement("strong");
  value.className = "adr-current-status__value";
  value.textContent = `${pres.emoji} ${pres.label}`;

  box.appendChild(label);
  box.appendChild(document.createTextNode(" "));
  box.appendChild(value);
  nav.insertAdjacentElement("afterend", box);
  return box;
}

function renderAdrStatusLogAfter(anchor, globalMax) {
  const wrap = document.createElement("div");
  wrap.className = "adr-status-log";
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", "Status log");

  const title = document.createElement("span");
  title.className = "adr-status-log__title";
  title.textContent = "Status log";
  wrap.appendChild(title);

  const row = document.createElement("div");
  row.className = "adr-status-log__row";

  for (const step of ADR_STEPS) {
    const sp = document.createElement("span");
    const kind = stepKind(step.w, globalMax);
    sp.className = `adr-step adr-step--${kind}`;
    sp.textContent = `${step.axis}: ${step.label}`;
    if (globalMax >= 0 && step.w === globalMax) {
      sp.setAttribute("aria-current", "step");
    }
    row.appendChild(sp);
  }

  wrap.appendChild(row);
  anchor.insertAdjacentElement("afterend", wrap);
}

function mainHasAdrWeight(main) {
  return main.hasAttribute("data-adr-weight");
}

function renderAdr(main) {
  if (!mainHasAdrWeight(main)) {
    return;
  }

  const nav = main.querySelector("nav.top-nav");
  if (!nav) {
    return;
  }

  const globalMax = adrCurrentWeight(main);

  const anchor = renderAdrCurrentStatus(nav, globalMax);
  renderAdrStatusLogAfter(anchor, globalMax);
}

/**
 * Inject shared audit score legend from `assets/audit-score-legend-fragment.html` into
 * `<div class="audit-score-legend-include" data-legend-id="optional-suffix"></div>`.
 * One source of truth for markup; styles remain in docs.css (ADR 0024).
 */
function auditScoreLegendFragmentUrl() {
  const relPath = currentDocsRelPath();
  const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
  return relHref(fromDir, "assets/audit-score-legend-fragment.html");
}

function stripLeadingHtmlComment(text) {
  return text.replace(/^\s*<!--[\s\S]*?-->\s*/, "").trimStart();
}

function applyLegendIdSuffix(aside, suffix) {
  const h3 = aside.querySelector(".audit-score-legend-title");
  if (!h3) {
    return;
  }
  if (suffix) {
    const id = `audit-score-legend-title-${suffix}`;
    h3.id = id;
    aside.setAttribute("aria-labelledby", id);
  }
}

async function injectAuditScoreLegends() {
  const hosts = document.querySelectorAll(".audit-score-legend-include");
  if (hosts.length === 0) {
    return;
  }

  const url = auditScoreLegendFragmentUrl();
  let htmlText;
  try {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) {
      throw new Error(`${res.status}`);
    }
    htmlText = await res.text();
  } catch (e) {
    for (const host of hosts) {
      const err = document.createElement("p");
      err.className = "audit-score-legend-error";
      err.setAttribute("role", "alert");
      err.textContent =
        "Could not load the score legend. Open this site over HTTP(S) or see ADR 0024 for the scale.";
      host.replaceWith(err);
    }
    return;
  }

  const cleaned = stripLeadingHtmlComment(htmlText);
  const parsed = new DOMParser().parseFromString(cleaned, "text/html");
  const templateAside = parsed.querySelector("aside.audit-score-legend");
  if (!templateAside) {
    return;
  }

  for (const host of hosts) {
    const suffix = (host.getAttribute("data-legend-id") || "").trim();
    const aside = document.importNode(templateAside, true);
    applyLegendIdSuffix(aside, suffix);
    host.replaceWith(aside);
  }
}

function slugifyForTocId(text) {
  let s = String(text || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
  return s || "section";
}

function ensureUniqueDomId(base, used) {
  let id = base;
  let n = 2;
  while (used.has(id)) {
    id = `${base}-${n}`;
    n += 1;
  }
  used.add(id);
  return id;
}

/**
 * Assign stable `id`s for in-page anchors on headings. `p.lead` is not listed in the TOC; add `id` on a lead manually if
 * you need a shareable `#fragment`.
 */
function ensureTocAnchorIds(article) {
  const used = new Set();
  for (const el of article.querySelectorAll("[id]")) {
    if (el.id) {
      used.add(el.id);
    }
  }

  for (const el of article.querySelectorAll("h2, h3")) {
    if (el.closest(".docs-inpage-toc")) {
      continue;
    }
    if (el.closest("figure.sys-diagram, .sys-diagram")) {
      continue;
    }
    if (!el.id) {
      const base = slugifyForTocId(el.textContent);
      el.id = ensureUniqueDomId(base, used);
    }
  }
}

function collectTocEntries(article) {
  const candidates = [];
  for (const el of article.querySelectorAll("h2, h3")) {
    if (el.closest(".docs-inpage-toc")) {
      continue;
    }
    if (el.closest("figure.sys-diagram, .sys-diagram")) {
      continue;
    }
    if (!el.id) {
      continue;
    }
    const level = el.tagName === "H3" ? 3 : 2;
    candidates.push({ el, level });
  }

  return candidates.map(({ el, level }) => ({
    id: el.id,
    label: el.textContent.trim().replace(/\s+/g, " "),
    level,
  }));
}

function normalizeTocTitleText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

/**
 * Remove legacy in-article manual "Contents" blocks so the page keeps a single navigation sidebar.
 * Legacy blocks are usually `<nav><h2 id="toc">Contents</h2>...</nav>` near the top of article content.
 */
function removeLegacyManualContents(article) {
  const navs = [...article.querySelectorAll("nav")];
  for (const nav of navs) {
    const heading = nav.querySelector("h1, h2, h3, h4, h5, h6");
    if (!heading) {
      continue;
    }
    const normalized = normalizeTocTitleText(heading.textContent);
    if (heading.id === "toc" || normalized === "contents") {
      nav.remove();
      return;
    }
  }

  const standaloneHeading = article.querySelector("h2#toc, h3#toc");
  if (!standaloneHeading) {
    return;
  }
  const list = standaloneHeading.nextElementSibling;
  standaloneHeading.remove();
  if (list && (list.tagName === "OL" || list.tagName === "UL")) {
    list.remove();
  }
}

function docsFeedbackIssueUrl() {
  const pagePath = currentDocsRelPath();
  const pageUrl = window.location.href;
  const title = `[Docs feedback] ${pagePath}`;
  const body = [
    "## Page",
    pagePath,
    "",
    "## URL",
    pageUrl,
    "",
    "## Feedback",
    "<!-- What is unclear, missing, or incorrect? -->",
  ].join("\n");

  const query = new URLSearchParams({
    template: DOCS_FEEDBACK_TEMPLATE,
    title,
    labels: DOCS_FEEDBACK_LABELS.join(","),
    body,
  });
  return `https://github.com/${DOCS_FEEDBACK_REPOSITORY}/issues/new?${query.toString()}`;
}

function injectDocsFeedbackCard() {
  const main = document.querySelector("main.container");
  if (!main) {
    return;
  }
  if (main.querySelector(".docs-feedback-card")) {
    return;
  }

  const mount = main.querySelector('.docs-inpage-toc-mount[data-inpage-toc="auto"]');
  if (!mount) {
    return;
  }

  const section = document.createElement("section");
  section.className = "card docs-feedback-card";
  section.setAttribute("aria-label", "Documentation feedback");

  const heading = document.createElement("h2");
  heading.textContent = "Page feedback";

  const text = document.createElement("p");
  text.textContent =
    "Found something unclear or outdated? Open a prefilled GitHub issue for this page.";

  const link = document.createElement("a");
  link.href = docsFeedbackIssueUrl();
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Report feedback on GitHub";

  section.appendChild(heading);
  section.appendChild(text);
  section.appendChild(link);
  mount.insertAdjacentElement("beforebegin", section);
}

/**
 * Wrap content after `#docs-top-nav` in a grid with a sticky “On this page” TOC built from `h2`/`h3` (not `p.lead`).
 * If mount is missing, create it as the last child of `<main>` automatically.
 * Very long outlines scroll inside the sidebar (see `.docs-inpage-toc nav` in docs.css).
 */
function initAutoInPageToc() {
  const main = document.querySelector("main.container");
  if (!main) {
    return;
  }

  let mount = main.querySelector('.docs-inpage-toc-mount[data-inpage-toc="auto"]');
  if (!mount) {
    mount = document.createElement("div");
    mount.className = "docs-inpage-toc-mount";
    mount.setAttribute("data-inpage-toc", "auto");
    main.appendChild(mount);
  }

  if (mount.closest("main") !== main) {
    return;
  }
  const nav = main.querySelector("#docs-top-nav");
  if (!nav) {
    mount.remove();
    return;
  }

  main.classList.add("docs-page-layout");

  const article = document.createElement("article");
  article.className = "docs-page-layout__article";

  let node = nav.nextSibling;
  while (node && node !== mount) {
    const next = node.nextSibling;
    if (node.nodeType === Node.ELEMENT_NODE) {
      article.appendChild(node);
    } else if (node.nodeType === Node.TEXT_NODE) {
      const t = node.textContent;
      if (t && t.trim()) {
        article.appendChild(node);
      } else {
        node.remove();
      }
    }
    node = next;
  }

  removeLegacyManualContents(article);
  ensureTocAnchorIds(article);
  const entries = collectTocEntries(article);

  const inner = document.createElement("div");
  inner.className = "docs-page-layout__inner";
  inner.appendChild(article);

  /* No h2/h3 → no aside; a single grid child would otherwise sit in the narrow first track only. */
  if (entries.length === 0) {
    inner.classList.add("docs-page-layout__inner--single");
  }

  if (entries.length > 0) {
    const aside = document.createElement("aside");
    aside.className = "docs-inpage-toc";
    aside.setAttribute("aria-labelledby", "inpage-toc-heading");

    const title = document.createElement("p");
    title.id = "inpage-toc-heading";
    title.className = "docs-inpage-toc__title";
    title.textContent = "On this page";

    const navEl = document.createElement("nav");
    navEl.setAttribute("aria-labelledby", "inpage-toc-heading");
    const ul = document.createElement("ul");

    for (const e of entries) {
      const li = document.createElement("li");
      if (e.level === 3) {
        li.className = "docs-inpage-toc__item--nested";
      }
      const a = document.createElement("a");
      a.className = "docs-inpage-toc__link";
      a.href = `#${e.id}`;
      a.textContent = e.label;
      li.appendChild(a);
      ul.appendChild(li);
    }

    navEl.appendChild(ul);
    aside.appendChild(title);
    aside.appendChild(navEl);
    inner.appendChild(aside);
  }

  mount.replaceWith(inner);
}

/**
 * Highlight the “On this page” TOC link that matches the section currently at the top of the viewport.
 * Expects `.docs-inpage-toc nav a[href^="#"]` and matching `id` on in-page targets.
 */
function initInPageTocScrollSpy() {
  const toc = document.querySelector(".docs-inpage-toc");
  if (!toc) {
    return;
  }
  const links = [...toc.querySelectorAll('nav a[href^="#"]')];
  if (links.length === 0) {
    return;
  }

  const targets = links
    .map((a) => {
      const id = a.getAttribute("href").slice(1);
      if (!id) {
        return null;
      }
      const el = document.getElementById(id);
      return el ? { a, el } : null;
    })
    .filter(Boolean);

  if (targets.length === 0) {
    return;
  }

  /** Sections whose top edge has crossed this line (from viewport top) become candidates; last match wins. */
  const ACTIVATION_LINE_PX = 96;

  function updateActive() {
    const scrollBottom = window.scrollY + window.innerHeight;
    const docBottom = document.documentElement.scrollHeight;
    const nearBottom = scrollBottom >= docBottom - 8;

    let activeIndex = 0;
    if (nearBottom) {
      activeIndex = targets.length - 1;
    } else {
      for (let i = 0; i < targets.length; i++) {
        const top = targets[i].el.getBoundingClientRect().top;
        if (top <= ACTIVATION_LINE_PX) {
          activeIndex = i;
        }
      }
    }

    for (let i = 0; i < targets.length; i++) {
      const on = i === activeIndex;
      targets[i].a.classList.toggle("docs-inpage-toc__link--active", on);
      if (on) {
        targets[i].a.setAttribute("aria-current", "location");
      } else {
        targets[i].a.removeAttribute("aria-current");
      }
    }
  }

  let ticking = false;
  function onScrollOrResize() {
    if (!ticking) {
      requestAnimationFrame(() => {
        updateActive();
        ticking = false;
      });
      ticking = true;
    }
  }

  window.addEventListener("scroll", onScrollOrResize, { passive: true });
  window.addEventListener("resize", onScrollOrResize, { passive: true });
  updateActive();
}

document.addEventListener("DOMContentLoaded", () => {
  renderTopNav();
  const main = document.querySelector("main.container");
  if (main) {
    renderAdr(main);
  }
  injectAuditScoreLegends();
  injectDocsFeedbackCard();
  initAutoInPageToc();
  initInPageTocScrollSpy();
});
