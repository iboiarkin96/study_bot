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
  // Use the first "/docs/" as the repo docs root. lastIndexOf breaks paths that also
  // contain ".../audit/docs/..." (file:// and static hosts), yielding only the file name.
  const idx = path.indexOf(marker);
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
    "pdoc",
    "assets",
    "audit",
    "backlog",
    "developer",
    "howto",
    "internal",
    "openapi",
    "qa",
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
    return "developer/README.html";
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
  if (relPath.startsWith("qa/")) {
    return "qa/README.html";
  }
  if (relPath.startsWith("audit/")) {
    return "audit/README.html";
  }
  if (relPath === "internal/analysis/system-design.html") {
    return "internal/analysis/system-design.html";
  }
  if (relPath === "internal/analysis/methodology.html") {
    return "internal/analysis/methodology.html";
  }
  if (relPath.startsWith("internal/")) {
    return "internal/README.html";
  }
  if (relPath.startsWith("howto/")) {
    return "howto/README.html";
  }
  if (relPath.startsWith("pdoc/")) {
    return "pdoc/index.html";
  }
  if (relPath.startsWith("openapi/")) {
    return "openapi/index.html";
  }
  return "index.html";
}

const DOCS_SEARCH_INDEX_PATH = "assets/search-index.json";
const DOCS_SEARCH_MAX_RESULTS = 10;
const DOCS_SEARCH_DEBOUNCE_MS = 120;
const DOCS_SEARCH_MAX_PREFIX_EXPANSIONS = 24;
const DOCS_SEARCH_SUCCESS_WINDOW_MS = 60_000;
const DOCS_FEEDBACK_REPOSITORY = "iboiarkin96/study_bot";
const DOCS_FEEDBACK_TEMPLATE = "docs_feedback.md";
const DOCS_FEEDBACK_LABELS = ["docs-feedback"];
const DOCS_FEEDBACK_CARD_ENABLED = true;

/** Page toolbar + quick-actions modal: desktop only (matches internal top-nav “phone” breakpoint). */
const DOCS_PAGE_ACTIONS_MIN_WIDTH = 761;
const desktopDocsPageActionsMq = window.matchMedia(`(min-width: ${DOCS_PAGE_ACTIONS_MIN_WIDTH}px)`);
let docsQuickActionsRuntime = null;
const DOCS_THEME_STORAGE_KEY = "docs-theme-preference";
const DOCS_READING_MODE_STORAGE_KEY = "docs-reading-mode-enabled";
const DOCS_HOTKEY_HINT_DISMISSED_KEY = "docs-hotkey-hint-dismissed-v1";
const DOCS_CONTINUE_READING_STORAGE_KEY = "docs-reading-progress-v1";
const DOCS_CONTINUE_READING_TTL_MS = 14 * 24 * 60 * 60 * 1000;
const DOCS_NAV_LINK_REGISTRY = {
  home: {
    target: "index.html",
    icon: "⌂",
    navLabel: "Home",
    footerLabel: "Documentation home",
    searchLabel: "Go to Documentation home",
    activePrefixes: [],
  },
  openapi: {
    target: "openapi/index.html",
    icon: "◎",
    navLabel: "API Explorer",
    searchLabel: "Go to OpenAPI / Swagger UI",
    activePrefixes: ["openapi"],
  },
  backlog: {
    target: "backlog/README.html",
    icon: "▣",
    navLabel: "Backlog",
    activePrefixes: ["backlog"],
  },
  pdoc: {
    target: "pdoc/index.html",
    icon: "◧",
    navLabel: "Python Docs",
    searchLabel: "Go to Python API (pdoc)",
    activePrefixes: ["pdoc"],
  },
  internal: {
    target: "internal/README.html",
    icon: "◉",
    navLabel: "Internal docs",
    searchLabel: "Go to Internal README",
    activePrefixes: ["internal"],
  },
  runbooks: {
    target: "runbooks/README.html",
    searchLabel: "Go to Runbooks",
    activePrefixes: ["runbooks"],
  },
};
const DOCS_TOP_NAV_KEYS = ["home", "internal", "openapi", "backlog", "pdoc"];
const DOCS_SEARCH_EMPTY_QUICK_LINK_KEYS = ["internal", "pdoc", "openapi", "runbooks"];
const DOCS_FOOTER_LINK_KEYS = ["home"];
function getDocsToastStackHost() {
  if (window.DocsPopups && typeof window.DocsPopups.getStackHost === "function") {
    return window.DocsPopups.getStackHost();
  }
  let host = document.getElementById("docs-toast-stack");
  if (!host) {
    host = document.createElement("div");
    host.id = "docs-toast-stack";
    host.className = "docs-toast-stack";
    host.setAttribute("role", "region");
    host.setAttribute("aria-label", "Notifications");
    document.body.appendChild(host);
  }
  return host;
}

function enqueueDocsPromoToast(options) {
  const config = options || {};
  const toast = document.createElement("section");
  toast.className = `docs-inpage-toc-toast ${config.className || ""}`.trim();
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  toast.innerHTML = `
    <div class="docs-inpage-toc-toast__title">${String(config.title || "")}</div>
    <p class="docs-inpage-toc-toast__text">
      ${String(config.text || "")}
    </p>
    <div class="docs-inpage-toc-toast__actions">
      <button type="button" class="docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--ghost" data-docs-promo-dismiss>
        ${String(config.dismissLabel || "Hide")}
      </button>
      <button type="button" class="docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--primary" data-docs-promo-primary>
        ${String(config.primaryLabel || "Open")}
      </button>
    </div>
    <div class="docs-inpage-toc-toast__progress" aria-hidden="true"></div>
  `;
  getDocsToastStackHost().appendChild(toast);
  const dismissBtn = toast.querySelector("[data-docs-promo-dismiss]");
  const primaryBtn = toast.querySelector("[data-docs-promo-primary]");
  let isClosed = false;
  let timerId = null;
  const closeToast = () => {
    if (isClosed) {
      return;
    }
    isClosed = true;
    if (timerId !== null) {
      window.clearTimeout(timerId);
    }
    toast.classList.add("docs-inpage-toc-toast--closing");
    window.setTimeout(() => {
      toast.remove();
    }, 180);
  };
  dismissBtn?.addEventListener("click", () => {
    if (config.storageKey) {
      try { localStorage.setItem(config.storageKey, "1"); } catch (e) { }
    }
    closeToast();
  });
  primaryBtn?.addEventListener("click", () => {
    if (config.storageKey) {
      try { localStorage.setItem(config.storageKey, "1"); } catch (e) { }
    }
    if (typeof config.onPrimary === "function") {
      config.onPrimary();
    }
    closeToast();
  });
  timerId = window.setTimeout(() => {
    closeToast();
  }, Number(config.durationMs) > 0 ? Number(config.durationMs) : 3000);
  return { close: closeToast };
}

function docsNavEntry(key) {
  return DOCS_NAV_LINK_REGISTRY[key] || null;
}

function docsTopNavItems() {
  return DOCS_TOP_NAV_KEYS.map((key) => {
    const entry = docsNavEntry(key);
    return {
      icon: entry.icon || "•",
      label: entry.navLabel || entry.searchLabel || entry.footerLabel || key,
      target: entry.target,
      activePrefixes: Array.isArray(entry.activePrefixes) ? entry.activePrefixes : [],
    };
  });
}

function docsQuickLinks(fromDir) {
  return DOCS_SEARCH_EMPTY_QUICK_LINK_KEYS.map((key) => {
    const entry = docsNavEntry(key);
    return {
      label: entry.searchLabel || entry.navLabel || entry.footerLabel || key,
      href: buildSearchResultHref(fromDir, entry.target),
    };
  });
}

function docsFooterLinks() {
  return DOCS_FOOTER_LINK_KEYS.map((key) => {
    const entry = docsNavEntry(key);
    return {
      href: entry.target,
      label: entry.footerLabel || entry.navLabel || entry.searchLabel || key,
    };
  });
}

function docsPalettePrimaryHotkeyLabel() {
  const platform = String(navigator.platform || "").toLowerCase();
  return platform.includes("mac") ? "⌘K / ⌘⇧P" : "Ctrl+K / Ctrl+Shift+P";
}

function docsPaletteMetaEnterLabel() {
  const platform = String(navigator.platform || "").toLowerCase();
  return platform.includes("mac") ? "⌘↵" : "Ctrl↵";
}

function emitDocsPaletteTelemetry(eventName, payload = {}) {
  const detail = {
    event: eventName,
    emitted_at_ms: Date.now(),
    page_path: window.location.pathname,
    ...payload,
  };
  document.dispatchEvent(
    new CustomEvent("docs-palette-telemetry", {
      detail,
    }),
  );
}

function isDocsReadingModeEnabled() {
  try {
    return window.localStorage.getItem(DOCS_READING_MODE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function setDocsReadingModeEnabled(enabled) {
  try {
    if (enabled) {
      window.localStorage.setItem(DOCS_READING_MODE_STORAGE_KEY, "1");
    } else {
      window.localStorage.removeItem(DOCS_READING_MODE_STORAGE_KEY);
    }
  } catch {
    // Ignore storage failures.
  }
}

function syncDocsReadingModeControls(enabled) {
  for (const btn of document.querySelectorAll("[data-docs-reading-mode-toggle]")) {
    btn.setAttribute("aria-pressed", enabled ? "true" : "false");
    btn.classList.toggle("docs-page-actions__button--active", enabled);
    btn.textContent = enabled ? "Reading mode: on" : "Reading mode: off";
  }
}

function applyDocsReadingMode(enabled, source = "unknown") {
  const body = document.body;
  if (!body) {
    return;
  }
  body.classList.toggle("docs-reading-mode", !!enabled);
  syncDocsReadingModeControls(!!enabled);
  emitDocsPaletteTelemetry("reading_mode_toggle", {
    enabled: !!enabled,
    source,
  });
}

function toggleDocsReadingMode(source = "unknown") {
  const enabled = !document.body.classList.contains("docs-reading-mode");
  setDocsReadingModeEnabled(enabled);
  applyDocsReadingMode(enabled, source);
}

function isTypingElement(target) {
  return (
    target instanceof HTMLElement &&
    (target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable)
  );
}

function isReadingModeHotkeyEvent(event) {
  const key = String(event.key || "").toLowerCase();
  const code = String(event.code || "");
  if (event.metaKey || event.ctrlKey || event.altKey) {
    return false;
  }
  // Primary gesture is Shift+F, but we also accept plain F to be resilient
  // across local file:// contexts and keyboard-layout quirks.
  return code === "KeyF" || key === "f" || key === "а";
}

/**
 * Minimal vertical flashlight (beam up): soft glow ellipse + reflector + grip + end cap.
 * Beam uses `.top-nav__theme-flashlight-beam` for “lit” styling in docs-site-nav.css.
 */
const DOCS_THEME_FLASHLIGHT_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
  <ellipse class="top-nav__theme-flashlight-beam" cx="12" cy="4.35" rx="5" ry="1.9" fill="currentColor" />
  <path fill="currentColor" d="M7.65 10.85c0-1.45 1.18-2.62 2.62-2.62h3.46c1.45 0 2.62 1.18 2.62 2.62v0.42c0 .38-.31.7-.7.7H8.35c-.38 0-.7-.31-.7-.7v-.42z" />
  <path fill="currentColor" opacity="0.9" d="M8.2 11.85h7.6v1.05c0 .34-.28.62-.62.62H8.82c-.34 0-.62-.28-.62-.62v-1.05z" />
  <rect x="9.1" y="13.35" width="5.8" height="8.35" rx="1.35" fill="currentColor" />
  <rect x="9.85" y="21.2" width="4.3" height="1.7" rx="0.5" fill="currentColor" opacity="0.88" />
</svg>`;

/** Bump when the shared ADR/RFC lifecycle help copy in `injectDocsLifecycleHelp` changes. */
const DOCS_LIFECYCLE_HELP_SNIPPET_VERSION = "2";

function docsPageDir() {
  const rel = currentDocsRelPath();
  const i = rel.lastIndexOf("/");
  return i >= 0 ? rel.slice(0, i) : "";
}

function docsLifecycleHelpHref(targetRelPath) {
  return relHref(docsPageDir(), targetRelPath);
}

/**
 * Fills `<details class="adr-weight-help|rfc-weight-help" data-docs-lifecycle="…">` from a single source
 * so policy wording and links stay consistent across ADR/RFC pages (see DOCS_LIFECYCLE_HELP_SNIPPET_VERSION).
 */
function injectDocsLifecycleHelp() {
  const v = DOCS_LIFECYCLE_HELP_SNIPPET_VERSION;
  for (const el of document.querySelectorAll("details[data-docs-lifecycle]")) {
    const kind = el.getAttribute("data-docs-lifecycle");
    el.setAttribute("data-docs-lifecycle-version", v);
    if (kind === "adr-short") {
      // Short ADR helper is now shown inside "Status log" callout.
      el.remove();
    } else if (kind === "rfc-short") {
      const h18 = docsLifecycleHelpHref("adr/0018-adr-lifecycle-ratification-and-badges.html");
      el.innerHTML = `<summary>RFC status on this page</summary>
      <p class="small">
        Set <code>data-rfc-weight</code> on <code>&lt;main&gt;</code> to a value from −1 to 7 (same scale as ADRs;
        see <a href="${h18}">ADR 0018</a>). Change it when this document\u2019s milestone changes.
      </p>`;
    } else if (kind === "adr-template") {
      const h18 = docsLifecycleHelpHref("adr/0018-adr-lifecycle-ratification-and-badges.html");
      el.innerHTML = `<summary>How to set status (author reference)</summary>
      <p class="small">
        On <code>&lt;main&gt;</code>, set <code>data-adr-weight</code> to the <strong>current</strong> milestone (−1 … 7).
        The page shows <strong>Current status</strong> and a collapsible <strong>Status log</strong> (expand to see all
        steps) from that value. Policy:
        <a href="${h18}">ADR 0018</a>.
      </p>
      <table>
        <caption>Milestone scale (single order 0 → 7)</caption>
        <thead>
          <tr>
            <th>Value</th>
            <th>Meaning (current milestone)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>-1</code></td>
            <td>Status not set (or unknown)</td>
          </tr>
          <tr>
            <td><code>0</code></td>
            <td><strong>Decision</strong> — Proposed</td>
          </tr>
          <tr>
            <td><code>1</code></td>
            <td><strong>Decision</strong> — Accepted</td>
          </tr>
          <tr>
            <td><code>2</code></td>
            <td><strong>Decision</strong> — Superseded</td>
          </tr>
          <tr>
            <td><code>3</code></td>
            <td><strong>Documentation</strong> — Draft</td>
          </tr>
          <tr>
            <td><code>4</code></td>
            <td><strong>Documentation</strong> — Ready</td>
          </tr>
          <tr>
            <td><code>5</code></td>
            <td><strong>Implementation</strong> — Not started</td>
          </tr>
          <tr>
            <td><code>6</code></td>
            <td><strong>Implementation</strong> — In progress</td>
          </tr>
          <tr>
            <td><code>7</code></td>
            <td><strong>Implementation</strong> — Done</td>
          </tr>
        </tbody>
      </table>
      <p class="small">
        Example: <code>data-adr-weight="4"</code> gives <strong>Current status</strong> Documentation · Ready. Values
        outside the range are clamped in <code>docs/assets/docs-nav.js</code>.
      </p>`;
    }
  }
}

function getStoredDocsTheme() {
  try {
    return window.localStorage.getItem(DOCS_THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function setStoredDocsTheme(mode) {
  try {
    if (mode === "system" || mode === null) {
      window.localStorage.removeItem(DOCS_THEME_STORAGE_KEY);
    } else {
      window.localStorage.setItem(DOCS_THEME_STORAGE_KEY, mode);
    }
  } catch {
    // Ignore storage failures; theme toggle still updates the live document.
  }
}

function applyDocsThemeFromMode(mode) {
  const root = document.documentElement;
  if (mode === "dark") {
    root.setAttribute("data-theme", "dark");
  } else if (mode === "light") {
    root.setAttribute("data-theme", "light");
  } else {
    root.removeAttribute("data-theme");
  }
}

function getEffectiveDocsThemeMode() {
  const s = getStoredDocsTheme();
  if (s === "dark" || s === "light") {
    return s;
  }
  return "system";
}

function cycleDocsTheme() {
  const order = ["system", "light", "dark"];
  const cur = getEffectiveDocsThemeMode();
  const i = order.indexOf(cur);
  const next = order[(i + 1) % order.length];
  setStoredDocsTheme(next === "system" ? null : next);
  applyDocsThemeFromMode(next);
  syncDocsThemeToggleLabel();
  showDocsThemePillowToast(next);
}

function showDocsThemePillowToast(mode) {
  const labels = {
    system: "Automatic theme — follows your system",
    light: "Light theme",
    dark: "Dark theme",
  };
  const text = labels[mode] || labels.system;
  let host = document.getElementById("docs-theme-toast-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "docs-theme-toast-host";
    host.className = "docs-theme-toast-host";
    document.body.appendChild(host);
  }
  host.replaceChildren();
  const el = document.createElement("div");
  el.className = "docs-theme-toast docs-theme-toast--pillow";
  el.setAttribute("role", "status");
  el.setAttribute("aria-live", "polite");
  el.textContent = text;
  host.appendChild(el);
  requestAnimationFrame(() => {
    el.classList.add("docs-theme-toast--visible");
  });
  window.clearTimeout(host.__docsThemeToastTimer);
  host.__docsThemeToastTimer = window.setTimeout(() => {
    el.classList.remove("docs-theme-toast--visible");
    el.classList.add("docs-theme-toast--leaving");
    window.setTimeout(() => {
      el.remove();
    }, 320);
  }, 2600);
}

function syncDocsThemeToggleLabel() {
  const btn = document.querySelector("[data-docs-theme-toggle]");
  if (!btn) {
    return;
  }
  const mode = getEffectiveDocsThemeMode();
  const lit = mode === "dark";
  btn.classList.toggle("top-nav__theme-btn--lit", lit);
  btn.setAttribute("data-theme-mode", mode);
  const modeWords = {
    system: "Automatic (follows system)",
    light: "Light",
    dark: "Dark",
  };
  btn.setAttribute(
    "title",
    "Cycle documentation color theme: automatic → light → dark",
  );
  btn.setAttribute(
    "aria-label",
    `Color theme: ${modeWords[mode] || modeWords.system}. Activate to cycle: automatic, light, dark.`,
  );
}
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

function docsSearchResultKind(url) {
  const safeUrl = String(url || "").toLowerCase();
  if (!safeUrl) {
    return "Docs";
  }
  if (safeUrl.startsWith("pdoc/")) {
    return "Python API";
  }
  if (safeUrl.startsWith("openapi/")) {
    return "OpenAPI";
  }
  if (safeUrl.startsWith("adr/")) {
    return "ADR";
  }
  if (safeUrl.startsWith("runbooks/")) {
    return "Runbook";
  }
  if (safeUrl.startsWith("howto/")) {
    return "How-to";
  }
  if (safeUrl.startsWith("internal/")) {
    return "Internal";
  }
  if (safeUrl.startsWith("audit/")) {
    return "Audit";
  }
  return "Docs";
}

function escapeRegex(text) {
  return String(text || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function appendSearchHighlightedText(target, text, queryText) {
  const raw = String(text || "");
  const tokens = tokenizeSearchText(queryText).filter((t) => t.length >= 2);
  if (!raw || tokens.length === 0) {
    target.textContent = raw;
    return;
  }
  const pattern = tokens.map((token) => escapeRegex(token)).join("|");
  if (!pattern) {
    target.textContent = raw;
    return;
  }
  const regex = new RegExp(`(${pattern})`, "ig");
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(raw)) !== null) {
    if (match.index > lastIndex) {
      target.appendChild(document.createTextNode(raw.slice(lastIndex, match.index)));
    }
    const mark = document.createElement("mark");
    mark.className = "docs-search__match";
    mark.textContent = match[0];
    target.appendChild(mark);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < raw.length) {
    target.appendChild(document.createTextNode(raw.slice(lastIndex)));
  }
}

function levenshteinDistance(a, b) {
  const aa = String(a || "");
  const bb = String(b || "");
  if (aa === bb) {
    return 0;
  }
  if (!aa) {
    return bb.length;
  }
  if (!bb) {
    return aa.length;
  }
  const prev = new Array(bb.length + 1);
  const curr = new Array(bb.length + 1);
  for (let j = 0; j <= bb.length; j++) {
    prev[j] = j;
  }
  for (let i = 1; i <= aa.length; i++) {
    curr[0] = i;
    for (let j = 1; j <= bb.length; j++) {
      const cost = aa[i - 1] === bb[j - 1] ? 0 : 1;
      curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
    }
    for (let j = 0; j <= bb.length; j++) {
      prev[j] = curr[j];
    }
  }
  return prev[bb.length];
}

function suggestDocsSearchQuery(rawQuery, indexData) {
  const query = normalizeSearchText(rawQuery);
  const tokens = tokenizeSearchText(query);
  if (!query || tokens.length === 0 || !indexData || !Array.isArray(indexData.vocabulary)) {
    return "";
  }
  const fixed = tokens.map((token) => {
    if (indexData.vocabulary.includes(token)) {
      return token;
    }
    const first = token[0] || "";
    const candidates = indexData.vocabulary.filter((v) =>
      Math.abs(v.length - token.length) <= 2 && (!first || v[0] === first),
    );
    let best = "";
    let bestScore = Number.POSITIVE_INFINITY;
    for (const c of candidates.slice(0, 120)) {
      const d = levenshteinDistance(token, c);
      if (d < bestScore) {
        bestScore = d;
        best = c;
      }
    }
    return bestScore <= 2 ? best : token;
  });
  const suggestion = fixed.join(" ");
  return suggestion !== query ? suggestion : "";
}

function docsSearchRelatedQueries(queryText) {
  const q = normalizeSearchText(queryText);
  const base = ["openapi", "runbook", "adr", "howto", "internal", "qa checklist"];
  if (!q) {
    return base.slice(0, 4);
  }
  const out = [];
  for (const item of base) {
    if (!item.includes(q) && !q.includes(item)) {
      out.push(item);
    }
    if (out.length >= 3) {
      break;
    }
  }
  return out;
}

function renderDocsSearchResults(list, results, fromDir, selectedIndex, listId, queryText = "", options = {}) {
  list.replaceChildren();
  if (!results || results.length === 0) {
    const empty = document.createElement("li");
    empty.className = "docs-search__empty";
    empty.setAttribute("role", "status");
    const safeQuery = String(queryText || "").trim();

    const title = document.createElement("p");
    title.className = "docs-search__empty-title";
    title.textContent = safeQuery ? `No matches for "${safeQuery}"` : "No matches";
    empty.appendChild(title);

    const didYouMean = options.didYouMean || "";
    if (didYouMean) {
      const did = document.createElement("p");
      did.className = "docs-search__didyoumean";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "docs-search__didyoumean-action";
      btn.setAttribute("data-search-action", "didyoumean");
      btn.setAttribute("data-search-query", didYouMean);
      btn.textContent = didYouMean;
      did.appendChild(document.createTextNode("Did you mean: "));
      did.appendChild(btn);
      did.appendChild(document.createTextNode("?"));
      empty.appendChild(did);
    }

    const tips = document.createElement("ul");
    tips.className = "docs-search__empty-tips";
    ["Check spelling", "Try shorter query", "Use related terms (openapi, runbook, qa)"].forEach((tipText) => {
      const tip = document.createElement("li");
      tip.textContent = tipText;
      tips.appendChild(tip);
    });

    const actions = document.createElement("div");
    actions.className = "docs-search__empty-actions";

    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "docs-search__empty-action docs-search__empty-action--clear";
    clearBtn.setAttribute("data-search-action", "clear");
    clearBtn.textContent = "Clear query";

    const quickLinks = docsQuickLinks(fromDir);
    actions.appendChild(clearBtn);
    quickLinks.forEach((item) => {
      const link = document.createElement("a");
      link.className = "docs-search__empty-action";
      link.href = item.href;
      link.textContent = item.label;
      actions.appendChild(link);
    });

    empty.appendChild(tips);
    const related = docsSearchRelatedQueries(safeQuery);
    if (related.length > 0) {
      const relatedWrap = document.createElement("p");
      relatedWrap.className = "docs-search__related-queries";
      relatedWrap.appendChild(document.createTextNode("Try related queries: "));
      related.forEach((term, idx) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "docs-search__related-query";
        btn.setAttribute("data-search-action", "related");
        btn.setAttribute("data-search-query", term);
        btn.textContent = term;
        relatedWrap.appendChild(btn);
        if (idx < related.length - 1) {
          relatedWrap.appendChild(document.createTextNode(" "));
        }
      });
      empty.appendChild(relatedWrap);
    }
    empty.appendChild(actions);
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
    appendSearchHighlightedText(title, item.title || item.url, queryText);

    const kind = document.createElement("span");
    kind.className = "docs-search__result-kind";
    kind.textContent = docsSearchResultKind(item.url);

    const meta = document.createElement("span");
    meta.className = "docs-search__result-meta";
    const section = item.section ? `${item.section} - ` : "";
    meta.textContent = `${section}${item.url}`;

    const topRow = document.createElement("span");
    topRow.className = "docs-search__result-top";
    topRow.appendChild(title);
    topRow.appendChild(kind);

    const preview = document.createElement("span");
    preview.className = "docs-search__result-preview";
    appendSearchHighlightedText(preview, item.preview || "", queryText);

    link.appendChild(topRow);
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
  let activeIndexData = null;

  function hideResults() {
    results.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    results.replaceChildren();
    activeResults = [];
    selectedIndex = -1;
    activeIndexData = null;
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

  function applyKindFilter(items) {
    return Array.isArray(items) ? items : [];
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
      activeIndexData = indexData;
      const rawResults = runDocsSearch(indexData, query);
      activeResults = applyKindFilter(rawResults);
      selectedIndex = activeResults.length > 0 ? 0 : -1;
      results.hidden = false;
      input.setAttribute("aria-expanded", "true");
      if (selectedIndex >= 0) {
        input.setAttribute("aria-activedescendant", `${resultsId}-option-${selectedIndex}`);
      } else {
        input.removeAttribute("aria-activedescendant");
      }
      const didYouMean = activeResults.length === 0 ? suggestDocsSearchQuery(query, indexData) : "";
      renderDocsSearchResults(results, activeResults, fromDir, selectedIndex, resultsId, query, { didYouMean });

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
      const didYouMean = activeResults.length === 0 ? suggestDocsSearchQuery(input.value, activeIndexData) : "";
      renderDocsSearchResults(results, activeResults, fromDir, selectedIndex, resultsId, input.value, { didYouMean });
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      selectedIndex = (selectedIndex - 1 + activeResults.length) % activeResults.length;
      input.setAttribute("aria-activedescendant", `${resultsId}-option-${selectedIndex}`);
      const didYouMean = activeResults.length === 0 ? suggestDocsSearchQuery(input.value, activeIndexData) : "";
      renderDocsSearchResults(results, activeResults, fromDir, selectedIndex, resultsId, input.value, { didYouMean });
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
    const clearAction =
      target && target.closest ? target.closest('.docs-search__empty-action[data-search-action="clear"]') : null;
    if (clearAction && wrap.contains(clearAction)) {
      event.preventDefault();
      input.value = "";
      hideResults();
      resetSearchSession();
      input.focus();
      return;
    }
    const queryAction =
      target && target.closest
        ? target.closest('[data-search-action="didyoumean"], [data-search-action="related"]')
        : null;
    if (queryAction && wrap.contains(queryAction)) {
      event.preventDefault();
      const query = String(queryAction.getAttribute("data-search-query") || "").trim();
      if (query) {
        input.value = query;
        searchNow(query);
        input.focus();
      }
      return;
    }
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

function isTopNavItemActive(item, relPath, activeTargetPath) {
  if (item.target === activeTargetPath) {
    return true;
  }
  if (item.activePrefixes && item.activePrefixes.length > 0) {
    return item.activePrefixes.some((prefix) => relPath === prefix || relPath.startsWith(`${prefix}/`));
  }
  return false;
}

function appendTopNavLinks(container, items, fromDir, active, relPath) {
  for (const item of items) {
    const link = document.createElement("a");
    if (item.icon) {
      const icon = document.createElement("span");
      icon.className = "top-nav__link-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = item.icon;
      link.appendChild(icon);
      const label = document.createElement("span");
      label.className = "top-nav__link-label";
      label.textContent = item.label;
      link.appendChild(label);
    } else {
      link.textContent = item.label;
    }
    link.href = relHref(fromDir, item.target);
    if (item.className) {
      link.className = item.className;
    }
    if (isTopNavItemActive(item, relPath, active)) {
      link.classList.add("is-active");
      link.setAttribute("aria-current", "page");
    }
    container.appendChild(link);
  }
}

/** Hub HTML file for a path prefix (directory trail), or null if there is no index page. */
function docsHubHrefForPrefix(prefix) {
  const hubs = {
    adr: "adr/README.html",
    pdoc: "pdoc/index.html",
    openapi: "openapi/index.html",
    audit: "audit/README.html",
    "audit/docs": "audit/docs/README.html",
    "audit/api": "audit/api/README.html",
    backlog: "backlog/README.html",
    developer: "developer/README.html",
    howto: "howto/README.html",
    internal: "internal/README.html",
    "internal/portal": "internal/README.html#team-onboarding",
    "internal/portal/people": "internal/README.html#team-onboarding",
    "internal/api": "internal/api/README.html",
    "internal/api/user": "internal/api/user/index.html",
    "internal/api/conspectus": "internal/api/conspectus/index.html",
    "internal/api/error-log": "internal/api/error-log/index.html",
    qa: "qa/README.html",
    rfc: "rfc/README.html",
    runbooks: "runbooks/README.html",
  };
  return hubs[prefix] || null;
}

/** Human-readable label for a directory prefix (path segments joined by "/"). */
function docsBreadcrumbLabelForPrefix(prefix) {
  const labels = {
    adr: "ADRs",
    pdoc: "Python API (pdoc)",
    openapi: "OpenAPI",
    audit: "Assessments",
    "audit/docs": "DX assessments",
    "audit/api": "API assessments",
    backlog: "Backlog",
    developer: "Developer guides",
    howto: "How-to guides",
    internal: "Internal docs",
    "internal/portal": "Portal",
    "internal/portal/people": "People",
    "internal/api": "Internal API",
    "internal/api/user": "User",
    "internal/api/conspectus": "Conspectus",
    "internal/api/error-log": "Error log",
    "internal/api/user/operations": "Operations",
    qa: "QA portal",
    rfc: "RFCs",
    runbooks: "Runbooks",
    assets: "Assets",
  };
  if (labels[prefix]) {
    return labels[prefix];
  }
  const last = prefix.includes("/") ? prefix.slice(prefix.lastIndexOf("/") + 1) : prefix;
  if (!last) {
    return prefix;
  }
  return last.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function docsBreadcrumbCurrentLabel(fileName) {
  const t = document.title.trim();
  if (t) {
    const first = t.split(/\s[—–-]\s/)[0].trim();
    if (first) {
      return first;
    }
  }
  const stem = fileName.replace(/\.html?$/i, "");
  return stem.replace(/-/g, " ");
}

/**
 * @returns {{ label: string, href?: string, current?: boolean }[]}
 */
function buildDocsBreadcrumbItems(relPath) {
  const normalized = relPath.replace(/\\/g, "/");
  if (normalized === "index.html") {
    return [{ label: "Documentation", current: true }];
  }

  const parts = normalized.split("/");
  const fileName = parts.pop() || "";
  const dirParts = parts;
  const fullPath = normalized;

  const crumbs = [{ label: "Documentation", href: "index.html" }];

  let prefix = "";
  for (let i = 0; i < dirParts.length; i++) {
    prefix = i === 0 ? dirParts[0] : `${prefix}/${dirParts[i]}`;
    const hub = docsHubHrefForPrefix(prefix);
    const hubIsThisPage =
      hub &&
      hub === fullPath &&
      (fileName === "README.html" || fileName === "index.html");
    if (hubIsThisPage) {
      crumbs.push({ label: docsBreadcrumbLabelForPrefix(prefix), current: true });
      return crumbs;
    }
    crumbs.push({
      label: docsBreadcrumbLabelForPrefix(prefix),
      href: hub || undefined,
    });
  }

  crumbs.push({
    label: docsBreadcrumbCurrentLabel(fileName),
    current: true,
  });

  /* e.g. .../cursor/index.html — folder crumb "Cursor" + current "Cursor" from <title> */
  if (crumbs.length >= 2) {
    const cur = crumbs[crumbs.length - 1];
    const prev = crumbs[crumbs.length - 2];
    if (
      cur.current &&
      prev.href === undefined &&
      prev.label.trim().toLowerCase() === cur.label.trim().toLowerCase()
    ) {
      crumbs.splice(crumbs.length - 2, 1);
    }
  }
  return crumbs;
}

function renderDocsBreadcrumbNav(fromDir, relPath) {
  const items = buildDocsBreadcrumbItems(relPath);
  const el = document.createElement("nav");
  el.className = "docs-breadcrumbs";
  el.setAttribute("aria-label", "Breadcrumb");
  const ol = document.createElement("ol");
  ol.className = "docs-breadcrumbs__list";
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "docs-breadcrumbs__item";
    if (item.current) {
      const span = document.createElement("span");
      span.className = "docs-breadcrumbs__current";
      span.textContent = item.label;
      span.setAttribute("aria-current", "page");
      li.appendChild(span);
    } else if (item.href) {
      const a = document.createElement("a");
      a.href = relHref(fromDir, item.href);
      a.textContent = item.label;
      li.appendChild(a);
    } else {
      const span = document.createElement("span");
      span.className = "docs-breadcrumbs__text";
      span.textContent = item.label;
      li.appendChild(span);
    }
    ol.appendChild(li);
  }
  el.appendChild(ol);
  return el;
}

function ensureInternalDrawerMenuAriaSync() {
  if (window.__docsInternalDrawerMenuAriaSyncInstalled) {
    return;
  }
  window.__docsInternalDrawerMenuAriaSyncInstalled = true;
  document.addEventListener("internal-sidebar:drawer-state", (event) => {
    const detail = event && event.detail ? event.detail : {};
    const expanded = !!(detail && detail.open && detail.drawerMode);
    const drawerId = detail && detail.drawerId ? String(detail.drawerId) : "";
    for (const btn of document.querySelectorAll("[data-internal-drawer-menu]")) {
      if (drawerId) {
        btn.setAttribute("aria-controls", drawerId);
      }
      btn.setAttribute("aria-expanded", expanded ? "true" : "false");
      btn.setAttribute(
        "aria-label",
        expanded ? "Close documentation menu" : "Open documentation menu",
      );
    }
  });
}

function mountInternalDrawerMenuButton() {
  ensureInternalDrawerMenuAriaSync();
  const main = document.querySelector("main.container");
  if (!main) {
    return null;
  }
  let row = main.querySelector("[data-internal-drawer-menu-row]");
  if (!row) {
    /*
     * Anchor to the first main heading in this page context.
     * We keep this resilient because some pages are transformed after initial render.
     */
    const h1 = main.querySelector("h1");
    if (!h1) {
      return null;
    }
    row = document.createElement("div");
    row.className = "internal-layout__page-title-row";
    row.setAttribute("data-internal-drawer-menu-row", "1");
    const parent = h1.parentElement;
    if (parent) {
      parent.insertBefore(row, h1);
    } else {
      h1.insertAdjacentElement("beforebegin", row);
    }
    row.appendChild(h1);
  }

  let menuBtn = row.querySelector("[data-internal-drawer-menu]");
  if (!menuBtn) {
    menuBtn = document.createElement("button");
    menuBtn.type = "button";
    menuBtn.className = "internal-layout__page-menu-btn";
    menuBtn.setAttribute("data-internal-drawer-menu", "1");
    menuBtn.setAttribute("aria-label", "Open documentation menu");
    menuBtn.setAttribute("aria-controls", "internal-sidebar-drawer");
    menuBtn.setAttribute("aria-expanded", "false");
    menuBtn.textContent = "Menu";

    menuBtn.addEventListener("click", () => {
      document.dispatchEvent(
        new CustomEvent("internal-sidebar:toggle-drawer", {
          detail: { source: "page-title" },
        }),
      );
    });
    row.insertBefore(menuBtn, row.firstChild);
  }

  return row;
}

function syncInternalThemeTogglePlacement() {
  const hasChrome =
    document.body.classList.contains("internal-layout") && document.getElementById("internal-sidebar-mount");
  if (!hasChrome) {
    return;
  }
  const btn = document.querySelector("[data-docs-theme-toggle]");
  if (!btn) {
    return;
  }
  const row = mountInternalDrawerMenuButton();
  if (!row) {
    return;
  }
  if (btn.parentElement !== row) {
    row.appendChild(btn);
  }
}

function syncDocsThemeToggleWithHeading() {
  const main = document.querySelector("main.container");
  if (!main) {
    return;
  }
  const btn = document.querySelector("[data-docs-theme-toggle]");
  const themeBar = document.querySelector(".top-nav .top-nav__theme-bar");
  if (!btn || !themeBar) {
    return;
  }

  let h1 = null;
  for (const child of main.children) {
    if (child.tagName === "H1") {
      h1 = child;
      break;
    }
  }
  if (!h1) {
    return;
  }

  let row = main.querySelector("[data-docs-page-title-row]");
  if (!row) {
    row = document.createElement("div");
    row.className = "docs-page-title-row";
    row.setAttribute("data-docs-page-title-row", "1");
    h1.insertAdjacentElement("beforebegin", row);
    row.appendChild(h1);
  }

  if (btn.parentElement !== row) {
    row.appendChild(btn);
  }
}

function injectDocsPopupsRuntime() {
  if (window.DocsPopups) {
    return;
  }
  if (document.querySelector('script[data-docs-popups-runtime="1"]')) {
    return;
  }
  const script = document.createElement("script");
  script.defer = true;
  script.src = relHref(docsPageDir(), "assets/docs-popups.js");
  script.setAttribute("data-docs-popups-runtime", "1");
  document.head.appendChild(script);
}

function ensureInternalLayoutForInternalSections() {
  const relPath = currentDocsRelPath();
  const internalPrefixes = [
    "adr/",
    "rfc/",
    "runbooks/",
    "howto/",
    "developer/",
    "audit/",
    "backlog/",
    "qa/",
    "internal/",
  ];
  const shouldApply = internalPrefixes.some((prefix) => relPath.startsWith(prefix));
  if (!shouldApply) {
    return;
  }

  const body = document.body;
  const main = document.querySelector("main.container");
  if (!body || !main) {
    return;
  }

  const hasSidebarMount = !!document.getElementById("internal-sidebar-mount");
  if (!hasSidebarMount) {
    const shell = document.createElement("div");
    shell.className = "internal-layout__shell";

    const sidebar = document.createElement("aside");
    sidebar.className = "internal-layout__sidebar";

    const mount = document.createElement("div");
    mount.id = "internal-sidebar-mount";

    sidebar.appendChild(mount);

    const mainWrap = document.createElement("div");
    mainWrap.className = "internal-layout__main";

    main.insertAdjacentElement("beforebegin", shell);
    mainWrap.appendChild(main);
    shell.appendChild(sidebar);
    shell.appendChild(mainWrap);
  }

  body.classList.add("internal-layout");

  if (!document.querySelector('script[src$="assets/internal-sidebar.js"]')) {
    const script = document.createElement("script");
    script.defer = true;
    script.src = relHref(docsPageDir(), "assets/internal-sidebar.js");
    document.head.appendChild(script);
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
  const primaryItems = docsTopNavItems();

  const isInternalLayoutChrome =
    document.body.classList.contains("internal-layout") && document.getElementById("internal-sidebar-mount");

  const nav = document.createElement("nav");
  nav.className = "top-nav";
  if (isInternalLayoutChrome) {
    nav.classList.add("top-nav--internal-page");
  }
  nav.setAttribute("aria-label", "Documentation navigation");

  // ── Flat app bar: wordmark · links · actions ────────────────────────────
  const bar = document.createElement("div");
  bar.className = "top-nav__bar";

  // Wordmark (left anchor — always links to home)
  const wordmark = document.createElement("a");
  wordmark.className = "top-nav__wordmark";
  wordmark.href = relHref(fromDir, "index.html");
  wordmark.textContent = "ETR Study API";
  bar.appendChild(wordmark);

  // Nav links (center): flat top-level quick entry
  const linksEl = document.createElement("div");
  linksEl.className = "top-nav__links";
  appendTopNavLinks(linksEl, primaryItems, fromDir, active, relPath);
  bar.appendChild(linksEl);

  // Actions (right): search widget + theme toggle
  const actionsEl = document.createElement("div");
  actionsEl.className = "top-nav__actions";

  // Keep .top-nav__theme-bar wrapper — syncDocsThemeToggleWithHeading queries it
  const themeBtn = document.createElement("button");
  themeBtn.type = "button";
  themeBtn.className = "top-nav__theme-btn top-nav__theme-btn--flashlight";
  themeBtn.setAttribute("data-docs-theme-toggle", "1");
  themeBtn.innerHTML = `<span class="top-nav__theme-btn__icon">${DOCS_THEME_FLASHLIGHT_SVG}</span>`;
  themeBtn.addEventListener("click", () => {
    cycleDocsTheme();
  });
  const themeBar = document.createElement("div");
  themeBar.className = "top-nav__theme-bar";
  themeBar.appendChild(themeBtn);
  actionsEl.appendChild(themeBar);

  bar.appendChild(actionsEl);
  nav.appendChild(bar);

  // Mount search (appends .docs-search to nav), then move it into actionsEl before the theme bar
  mountDocsSearch(nav, fromDir);
  const searchWidget = nav.querySelector(".docs-search");
  if (searchWidget) {
    actionsEl.insertBefore(searchWidget, themeBar);
  }

  const breadcrumbNav = renderDocsBreadcrumbNav(fromDir, relPath);

  /* Keep `#docs-top-nav` in the DOM — `initAutoInPageToc` and formatters anchor off this host. */
  host.replaceChildren(breadcrumbNav, nav);

  if (isInternalLayoutChrome) {
    mountInternalDrawerMenuButton();
    syncInternalThemeTogglePlacement();
  } else {
    syncDocsThemeToggleWithHeading();
  }
}

/**
 * ADR / RFC lifecycle: one weight on `<main>` (−1…7) → current status + linear status log.
 * ADRs use `data-adr-weight`; RFCs use `data-rfc-weight` (same steps as ADR 0018).
 */

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
  return box;
}

function renderAdrStatusLogAfter(anchor, globalMax) {
  const details = document.createElement("details");
  details.className = "adr-status-log";

  const summary = document.createElement("summary");
  summary.className = "adr-status-log__summary";
  summary.textContent = "Status log";

  const callout = document.createElement("p");
  callout.className = "adr-status-log__callout";
  callout.innerHTML = `💡 Set <code>data-adr-weight</code> on <code>&lt;main&gt;</code> to a value from −1 to 7. See
    <a href="${docsLifecycleHelpHref("adr/0018-adr-lifecycle-ratification-and-badges.html")}">ADR 0018</a> for
    milestone meanings, and the
    <a href="${docsLifecycleHelpHref("adr/0000-template.html")}">ADR template</a> for the full milestone table.`;

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

  const panel = document.createElement("div");
  panel.className = "adr-status-log__panel";
  panel.appendChild(callout);
  panel.appendChild(row);

  const updatePanelPlacement = () => {
    details.classList.remove("adr-status-log--align-right");
    if (!details.open) {
      return;
    }
    const rect = panel.getBoundingClientRect();
    if (rect.right > window.innerWidth - 12) {
      details.classList.add("adr-status-log--align-right");
    }
  };

  const closeOnOutsideClick = (event) => {
    if (!details.open) {
      return;
    }
    const target = event.target;
    if (target instanceof Node && details.contains(target)) {
      return;
    }
    details.open = false;
  };
  const closeOnEscape = (event) => {
    if (event.key !== "Escape" || !details.open) {
      return;
    }
    details.open = false;
    summary.focus();
  };
  details.addEventListener("toggle", updatePanelPlacement);
  window.addEventListener("resize", updatePanelPlacement);
  document.addEventListener("pointerdown", closeOnOutsideClick);
  document.addEventListener("keydown", closeOnEscape);

  details.appendChild(summary);
  details.appendChild(panel);
  anchor.appendChild(details);
}

function renderLifecycleStatusBlocks(main) {
  const nav = main.querySelector("nav.top-nav");
  if (!nav) {
    return;
  }
  const attr = main.hasAttribute("data-adr-weight")
    ? "data-adr-weight"
    : main.hasAttribute("data-rfc-weight")
      ? "data-rfc-weight"
      : null;
  if (!attr) {
    return;
  }

  const globalMax = parseAdrWeightValue(main.getAttribute(attr));

  const row = document.createElement("div");
  row.className = "adr-status-row";
  row.appendChild(renderAdrCurrentStatus(nav, globalMax));
  renderAdrStatusLogAfter(row, globalMax);
  nav.insertAdjacentElement("afterend", row);
}

/**
 * Markup fallback when `fetch()` cannot load `audit-score-legend-fragment.html` (e.g. `file://` pages).
 * Keep in sync with the `<aside class="audit-score-legend">` in that file.
 */
const AUDIT_SCORE_LEGEND_ASIDE_FALLBACK = `<aside class="audit-score-legend" role="note" aria-labelledby="audit-score-legend-title">
<h3 class="audit-score-legend-title" id="audit-score-legend-title">Score scale (1–10)</h3>
<p class="audit-score-legend-intro">
  Indicative maturity versus the reference practices in <em>this</em> document only. Not comparable across unrelated
  assessments unless recalibrated. Does not rate individuals.
</p>
<ul class="audit-score-legend-bands">
  <li>
    <span class="audit-score-swatch score-excellent" aria-hidden="true"></span>
    <span><strong>9–10 — Excellent.</strong> Strong fit for the stated scope (e.g. PET / small-team service where that
      framing applies).</span>
  </li>
  <li>
    <span class="audit-score-swatch score-good" aria-hidden="true"></span>
    <span><strong>7–8 — Good.</strong> Solid, with clear room to improve.</span>
  </li>
  <li>
    <span class="audit-score-swatch score-needs-attention" aria-hidden="true"></span>
    <span><strong>1–6 — Needs attention.</strong> Missing, partial, narrow applicability, or below the reference bar for
      this row.</span>
  </li>
</ul>
</aside>`;

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
    htmlText = `<!DOCTYPE html><html><body>${AUDIT_SCORE_LEGEND_ASIDE_FALLBACK}</body></html>`;
  }

  const cleaned = stripLeadingHtmlComment(htmlText);
  const parsed = new DOMParser().parseFromString(cleaned, "text/html");
  const templateAside = parsed.querySelector("aside.audit-score-legend");
  if (!templateAside) {
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

function docsFeedbackIssueUrl(extraFeedback = "", feedbackType = "Other") {
  const pagePath = currentDocsRelPath();
  const pageUrl = /^https?:/i.test(window.location.href) ? window.location.href : pagePath;
  const title = `[Docs feedback] ${pagePath}`;
  const feedbackText = (extraFeedback || "").trim();
  const body = [
    "## Page",
    pagePath,
    "",
    "## URL",
    pageUrl,
    "",
    "## Feedback type",
    feedbackType || "Other",
    "",
    "## What should be improved",
    feedbackText || "<!-- Describe the issue and expected fix -->",
    "",
    "## Additional context",
    "<!-- Optional: screenshots, references, related pages -->",
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
  if (!DOCS_FEEDBACK_CARD_ENABLED) {
    return;
  }
  const main = document.querySelector("main.container");
  if (!main) {
    return;
  }
  if (main.dataset.docsFeedbackMounted === "1") {
    return;
  }

  function feedbackHintLabelSpan(text, tooltip) {
    const span = document.createElement("span");
    span.tabIndex = 0;
    span.setAttribute("data-tooltip", tooltip);
    span.textContent = text;
    return span;
  }

  const modal = document.createElement("section");
  modal.className = "docs-feedback-modal";
  modal.hidden = true;
  modal.setAttribute("aria-hidden", "true");

  const modalPanel = document.createElement("div");
  modalPanel.className = "docs-feedback-modal__panel";
  modalPanel.setAttribute("role", "dialog");
  modalPanel.setAttribute("aria-modal", "true");
  modalPanel.setAttribute("aria-label", "Page feedback form");

  const modalCloseBtn = document.createElement("button");
  modalCloseBtn.type = "button";
  modalCloseBtn.className = "docs-feedback-modal__close";
  modalCloseBtn.setAttribute("data-feedback-close", "true");
  modalCloseBtn.setAttribute("aria-label", "Close feedback form");
  modalCloseBtn.textContent = "Close";

  const contentHost = modalPanel;
  let lastFocusTarget = null;

  const heading = document.createElement("h2");
  heading.textContent = "Report issue";

  const text = document.createElement("p");
  text.textContent =
    "Found something unclear or outdated? Open a prefilled GitHub issue for this page.";

  const form = document.createElement("form");
  form.className = "docs-feedback-card__form";

  const inputLabel = document.createElement("label");
  inputLabel.className = "docs-feedback-card__label";
  inputLabel.setAttribute("for", "docs-feedback-input");
  inputLabel.appendChild(
    feedbackHintLabelSpan(
      "What should be improved?",
      "Describe the problem on this page (unclear step, wrong command, broken link). At least 10 characters; text is copied and included in the GitHub issue body.",
    ),
  );

  const typeLabel = document.createElement("label");
  typeLabel.className = "docs-feedback-card__label";
  typeLabel.setAttribute("for", "docs-feedback-type");
  typeLabel.appendChild(
    feedbackHintLabelSpan(
      "Feedback type",
      "Pick a category for triage; it is passed into the prefilled issue so maintainers can route faster.",
    ),
  );

  const typeSelect = document.createElement("select");
  typeSelect.id = "docs-feedback-type";
  typeSelect.className = "docs-feedback-card__select";
  ["Incorrect or outdated content", "Missing explanation", "Broken link or navigation", "Accessibility issue", "Other"].forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = item;
    typeSelect.appendChild(option);
  });
  typeSelect.value = "Other";

  const textarea = document.createElement("textarea");
  textarea.id = "docs-feedback-input";
  textarea.className = "docs-feedback-card__textarea";
  textarea.rows = 4;
  textarea.minLength = 10;
  textarea.placeholder = "Example: This section needs a quick example for mobile setup.";
  textarea.required = true;

  const status = document.createElement("p");
  status.className = "docs-feedback-card__status";
  status.setAttribute("aria-live", "polite");
  status.textContent = "Your feedback text will be prefilled in GitHub issue.";

  const toast = document.createElement("div");
  toast.className = "docs-feedback-card__toast";
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");

  const actions = document.createElement("div");
  actions.className = "docs-feedback-card__actions";

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.className = "docs-page-actions__button";
  submitBtn.innerHTML = '<span class="docs-feedback-card__btn-text">Report issue</span><span class="docs-feedback-card__btn-spinner" aria-hidden="true"></span>';

  function closeModal() {
    if (modal.hidden) {
      return;
    }
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("docs-feedback-modal-open");
    if (lastFocusTarget && typeof lastFocusTarget.focus === "function") {
      lastFocusTarget.focus();
    }
  }

  function openModal(triggerEl) {
    if (!modal.hidden) {
      closeModal();
      return;
    }
    lastFocusTarget = triggerEl || document.activeElement;
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("docs-feedback-modal-open");
    window.setTimeout(() => {
      if (document.body.contains(textarea)) {
        textarea.focus();
      }
    }, 0);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = textarea.value.trim();
    if (message.length < 10) {
      status.className = "docs-feedback-card__status docs-feedback-card__status--error";
      status.textContent = "Please enter at least 10 characters so we can understand the issue.";
      textarea.focus();
      return;
    }
    status.className = "docs-feedback-card__status docs-feedback-card__status--success";
    status.textContent = "Preparing GitHub issue...";
    submitBtn.disabled = true;
    submitBtn.classList.add("docs-feedback-card__btn--loading");
    const targetUrl = docsFeedbackIssueUrl(message, typeSelect.value);
    try {
      await navigator.clipboard.writeText(message);
      status.textContent = "Text copied as backup.";
    } catch (_error) {
      // Clipboard may be unavailable for file:// pages; keep submit flow working.
    }
    toast.textContent = "Opening GitHub with prefilled feedback...";
    toast.classList.add("docs-feedback-card__toast--visible");
    textarea.value = "";
    window.setTimeout(() => {
      window.location.href = targetUrl;
    }, 160);
    window.setTimeout(() => {
      if (!document.body.contains(status) || !document.body.contains(toast)) {
        return;
      }
      status.textContent = "Thanks! You can submit another feedback item anytime.";
      toast.classList.remove("docs-feedback-card__toast--visible");
      submitBtn.disabled = false;
      submitBtn.classList.remove("docs-feedback-card__btn--loading");
      closeModal();
    }, 900);
  });

  modalCloseBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    closeModal();
  });
  modal.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const closeTrigger = target.closest("[data-feedback-close]");
    if (closeTrigger) {
      event.preventDefault();
      closeModal();
      return;
    }
    /*
     * Close on backdrop: `target === modal` breaks when flex layout or subpixels
     * map the hit target differently; rely on panel boundary instead.
     */
    if (!modalPanel.contains(target)) {
      closeModal();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal();
    }
  });

  actions.appendChild(submitBtn);
  form.appendChild(typeLabel);
  form.appendChild(typeSelect);
  form.appendChild(inputLabel);
  form.appendChild(textarea);
  form.appendChild(status);
  form.appendChild(actions);

  contentHost.appendChild(heading);
  contentHost.appendChild(text);
  contentHost.appendChild(toast);
  contentHost.appendChild(form);

  modalPanel.appendChild(modalCloseBtn);
  modal.appendChild(modalPanel);
  document.body.appendChild(modal);

  const REPORT_BUG_FAB_HTML =
    '<svg class="docs-report-bug-fab__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path class="bug-antenna bug-antenna--l" d="M9 7 Q8 4 6 3"/>' +
    '<path class="bug-antenna bug-antenna--r" d="M15 7 Q16 4 18 3"/>' +
    '<g class="bug-body">' +
    '<ellipse cx="12" cy="14" rx="4.6" ry="5.6"/>' +
    '<line x1="12" y1="9" x2="12" y2="19.5"/>' +
    '<path d="M7.5 12 L4.5 11"/>' +
    '<path d="M7.5 14.5 L4 14.5"/>' +
    '<path d="M7.5 17 L4.5 18.5"/>' +
    '<path d="M16.5 12 L19.5 11"/>' +
    '<path d="M16.5 14.5 L20 14.5"/>' +
    '<path d="M16.5 17 L19.5 18.5"/>' +
    '</g>' +
    '</svg>' +
    '<span class="docs-report-bug-fab__label">Found a bug? Report issue</span>';

  function upgradeReportBugFab(fab) {
    if (!fab || fab.dataset.fabUpgraded === "1") {
      return;
    }
    fab.type = "button";
    if (!fab.hasAttribute("aria-label")) {
      fab.setAttribute("aria-label", "Found a bug? Report issue");
    }
    if (!fab.hasAttribute("data-tooltip")) {
      fab.setAttribute("data-tooltip", "Report issue");
    }
    fab.innerHTML = REPORT_BUG_FAB_HTML;
    fab.dataset.fabUpgraded = "1";
  }

  let floatingReportButtons = Array.from(document.querySelectorAll(".docs-report-bug-fab"));
  if (floatingReportButtons.length === 0) {
    const fab = document.createElement("button");
    fab.className = "docs-report-bug-fab";
    fab.setAttribute("data-feedback-open", "true");
    upgradeReportBugFab(fab);
    document.body.appendChild(fab);
    floatingReportButtons = [fab];
  } else {
    /*
     * Reparent every existing FAB to <body>: ancestors inside the main
     * column may create containing blocks (transform/filter/contain) that
     * trap `position: fixed`, anchoring the FAB to the column edge instead
     * of the viewport. Drop duplicates: keep the first, remove the rest.
     */
    const primary = floatingReportButtons[0];
    upgradeReportBugFab(primary);
    if (primary.parentElement !== document.body) {
      document.body.appendChild(primary);
    }
    for (let i = 1; i < floatingReportButtons.length; i += 1) {
      floatingReportButtons[i].remove();
    }
    floatingReportButtons = [primary];
  }

  const triggers = Array.from(document.querySelectorAll("[data-feedback-open]"));
  triggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      openModal(trigger);
    });
  });

  floatingReportButtons.forEach((button) => {
    button.classList.add("docs-report-bug-fab--visible");
  });
  main.dataset.docsFeedbackMounted = "1";
}

/**
 * Normalize Page history across docs:
 * 1) keep it as the final section of main content,
 * 2) wrap content into a collapsible details block,
 * 3) enforce consistent styling hooks.
 */
function normalizeDocsPageHistory() {
  const main = document.querySelector("main.container");
  if (!main) {
    return;
  }
  const section =
    main.querySelector("section#page-history") ||
    main.querySelector("section#5-page-history");
  if (!section) {
    return;
  }

  section.classList.add("card", "docs-page-history-fold");
  const existingDetails = section.querySelector(":scope > details");
  if (existingDetails) {
    existingDetails.classList.add("docs-collapse", "docs-page-history-fold__details");
    let summary = existingDetails.querySelector(":scope > summary");
    if (!summary) {
      summary = document.createElement("summary");
      summary.textContent = "Page history";
      existingDetails.insertAdjacentElement("afterbegin", summary);
    }
    const heading = section.querySelector(":scope > h2");
    if (heading) {
      const label = heading.textContent ? heading.textContent.trim() : "";
      if (label) {
        summary.textContent = label;
      }
      heading.remove();
    }
  } else {
    const heading = section.querySelector(":scope > h2");
    const summaryLabel = heading && heading.textContent ? heading.textContent.trim() : "Page history";
    const details = document.createElement("details");
    details.className = "docs-collapse docs-page-history-fold__details";
    const summary = document.createElement("summary");
    summary.textContent = summaryLabel || "Page history";
    const body = document.createElement("div");
    body.className = "docs-collapse__body docs-page-history-fold__body";

    const children = Array.from(section.childNodes);
    children.forEach((node) => {
      if (heading && node === heading) {
        return;
      }
      body.appendChild(node);
    });
    details.appendChild(summary);
    details.appendChild(body);
    section.replaceChildren(details);
  }

  if (section.parentElement === main && section !== main.lastElementChild) {
    main.appendChild(section);
  }
}

/**
 * Wrap content after `#docs-top-nav` in a grid with a sticky “On this page” TOC built from `h2`/`h3` (not `p.lead`).
 * If mount is missing, create it as the last child of `<main>` automatically.
 * Very long outlines scroll inside the sidebar (see `.docs-inpage-toc nav` in docs.css).
 * The aside is hidden on viewports `max-width: 900px` in docs.css (desktop/tablet-only chrome).
 */
function initAutoInPageToc() {
  const main = document.querySelector("main.container");
  if (!main) {
    return;
  }
  if (main.getAttribute("data-inpage-toc") === "off") {
    return;
  }
  const relPath = currentDocsRelPath();
  const isDocsHomePage = relPath === "index.html";
  /** Same treatment as docs home: no sticky-TOC promo toast; no default collapsed rail. */
  const isInternalReadmeHub = relPath === "internal/README.html";
  const isTocPromoExcludedHub = isDocsHomePage || isInternalReadmeHub;

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

    const head = document.createElement("div");
    head.className = "docs-inpage-toc__head";

    const title = document.createElement("p");
    title.id = "inpage-toc-heading";
    title.className = "docs-inpage-toc__title";
    title.textContent = "On this page";

    const navEl = document.createElement("nav");
    const navId = `docs-inpage-toc-nav-${Math.random().toString(36).slice(2, 8)}`;
    navEl.id = navId;
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

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "docs-inpage-toc__toggle";
    toggle.setAttribute("aria-controls", navId);
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Hide On this page");
    toggle.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M7.5 2L3.5 6L7.5 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    let isCollapsed = false;
    function applyCollapsedState(nextCollapsed) {
      isCollapsed = !!nextCollapsed;
      aside.classList.toggle("docs-inpage-toc--collapsed", isCollapsed);
      inner.classList.toggle("docs-page-layout__inner--toc-collapsed", isCollapsed);
      toggle.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      toggle.setAttribute("aria-label", isCollapsed ? "Show On this page" : "Hide On this page");
      toggle.innerHTML = isCollapsed
        ? '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M4.5 2L8.5 6L4.5 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        : '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M7.5 2L3.5 6L7.5 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }
    function showStickyTocPromoToast() {
      enqueueDocsPromoToast({
        title: "Sticky TOC available",
        text: 'We have a premium sticky "On this page" navigation for long docs.',
        dismissLabel: "Hide",
        primaryLabel: "Enable sticky TOC",
        onPrimary: () => {
          applyCollapsedState(false);
        },
        durationMs: 3000,
      });
    }
    /**
     * Collapse/expand action for in-page TOC.
     * UX rule: the whole "On this page" header is clickable (not only chevron).
     */
    function toggleCollapsedState() {
      applyCollapsedState(!isCollapsed);
    }
    toggle.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleCollapsedState();
    });
    head.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleCollapsedState();
    });
    /*
     * Fallback: when collapsed, any click on the rail re-opens TOC.
     * This protects against tiny hit areas and overlay edge-cases.
     */
    aside.addEventListener("click", (event) => {
      if (!isCollapsed) {
        return;
      }
      const target = event.target;
      if (target && target.closest && target.closest("a[href]")) {
        return;
      }
      applyCollapsedState(false);
    });

    navEl.appendChild(ul);
    head.appendChild(title);
    head.appendChild(toggle);
    aside.appendChild(head);
    aside.appendChild(navEl);
    inner.appendChild(aside);
    /* Hub pages (docs home, internal README hub) skip sticky TOC promo and default collapse. */
    if (!isTocPromoExcludedHub) {
      /*
       * Keep default collapsed rail only on wide desktop where promo is shown.
       * On compact desktop/tablet, keep TOC expanded so it is usable immediately.
       */
      applyCollapsedState(window.matchMedia("(min-width: 1025px)").matches);
    }
    if (!isTocPromoExcludedHub && window.matchMedia("(min-width: 1025px)").matches) {
      showStickyTocPromoToast();
    }
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

/** Scroll-to-top control with two-tier morph:
    Compact (sleeping rocket) appears once the user has scrolled past the
    first viewport — small icon-only pill, muted, click is a no-op (nudge
    only). A fueling ring around the icon fills as the reader approaches
    the footer. Within `armedThresholdPx` of the bottom, the pill morphs
    open: label fades in, color brightens to accent, flame/smoke wake up,
    and the click finally launches the rocket. The user has to literally
    reach the end of the page to fire the rocket. */
function initBackToTopButton() {
  const root = document.documentElement;
  const armedThresholdPx = 320;       // distance-to-footer that arms the rocket
  const compactAfterPx = 600;         // wake the compact pill once we scroll past this
  const minScrollExtra = 100;
  let isLaunching = false;
  // When the rocket finishes its flight, the smooth-scroll-to-top is often
  // still mid-page — so a naive updateVisibility() would re-arm the compact
  // pill (with its progress-ring "phantom circle") at the bottom-right
  // before the page reaches top. Suppress visibility entirely until either
  // the user actually scrolls or a small settle timeout elapses; the next
  // user-initiated scroll then shows the FAB normally.
  let suppressUntilUserScroll = false;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "docs-back-to-top";
  btn.setAttribute("aria-label", "Scroll to footer to launch the rocket");
  btn.setAttribute("title", "Scroll to footer to launch the rocket");
  btn.setAttribute("aria-hidden", "true");
  btn.tabIndex = -1;
  btn.innerHTML = `
    <span class="docs-back-to-top__progress-ring" aria-hidden="true"></span>
    <span class="docs-back-to-top__rocket-wrap" aria-hidden="true">
      <svg class="docs-back-to-top__rocket" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3c3.4 1.9 5.5 5.5 5.5 9.3v1.1L12 19l-5.5-5.6v-1.1C6.5 8.5 8.6 4.9 12 3z"/>
        <path d="M12 8.2a1.6 1.6 0 1 1 0 3.2 1.6 1.6 0 0 1 0-3.2z"/>
        <path d="M9.3 16.6l-1.8 3.1M14.7 16.6l1.8 3.1"/>
        <path d="M10.8 19.3h2.4"/>
      </svg>
      <span class="docs-back-to-top__ember docs-back-to-top__ember--1"></span>
      <span class="docs-back-to-top__ember docs-back-to-top__ember--2"></span>
      <span class="docs-back-to-top__ember docs-back-to-top__ember--3"></span>
      <span class="docs-back-to-top__ember docs-back-to-top__ember--4"></span>
      <span class="docs-back-to-top__ember docs-back-to-top__ember--5"></span>
      <span class="docs-back-to-top__trail"></span>
      <span class="docs-back-to-top__flame"></span>
      <span class="docs-back-to-top__speed-line docs-back-to-top__speed-line--a"></span>
      <span class="docs-back-to-top__speed-line docs-back-to-top__speed-line--b"></span>
      <span class="docs-back-to-top__smoke docs-back-to-top__smoke--left"></span>
      <span class="docs-back-to-top__smoke docs-back-to-top__smoke--mid"></span>
      <span class="docs-back-to-top__smoke docs-back-to-top__smoke--right"></span>
    </span>
    <span class="docs-back-to-top__label">Go to top!</span>`;

  function pageIsScrollable() {
    return root.scrollHeight > window.innerHeight + minScrollExtra;
  }

  function isNearBottom() {
    return window.scrollY + window.innerHeight >= root.scrollHeight - armedThresholdPx;
  }

  function isPastFirstScreen() {
    return window.scrollY > compactAfterPx;
  }

  function updateProgress() {
    // 0..100, linear from compact-wake threshold to armed threshold.
    const armedAt = root.scrollHeight - window.innerHeight - armedThresholdPx;
    const range = armedAt - compactAfterPx;
    if (range <= 0) {
      btn.style.setProperty("--rocket-progress", "100");
      return;
    }
    const p = Math.max(0, Math.min(1, (window.scrollY - compactAfterPx) / range));
    btn.style.setProperty("--rocket-progress", (p * 100).toFixed(1));
  }

  function updateVisibility() {
    if (isLaunching) {
      // Rocket has flown — pill shows as collapsed/empty until cleanup.
      btn.classList.add("docs-back-to-top--visible");
      btn.classList.remove("docs-back-to-top--armed");
      btn.setAttribute("aria-hidden", "false");
      btn.tabIndex = -1;
      return;
    }
    if (suppressUntilUserScroll) {
      // Hold the FAB hidden after a launch so the compact pill / progress-
      // ring doesn't pop in while smooth-scroll-to-top is still mid-flight.
      btn.classList.remove("docs-back-to-top--visible");
      btn.classList.remove("docs-back-to-top--armed");
      btn.setAttribute("aria-hidden", "true");
      btn.tabIndex = -1;
      updateProgress();
      return;
    }
    const scrollable = pageIsScrollable();
    const visible = scrollable && (isPastFirstScreen() || isNearBottom());
    const armed = scrollable && isNearBottom();
    btn.classList.toggle("docs-back-to-top--visible", visible);
    btn.classList.toggle("docs-back-to-top--armed", armed);
    btn.setAttribute("aria-hidden", visible ? "false" : "true");
    // Only focusable when armed — otherwise tabbing onto a no-op button is
    // a footgun for keyboard users.
    btn.tabIndex = armed ? 0 : -1;
    if (armed) {
      btn.setAttribute("aria-label", "Launch rocket and scroll to top");
      btn.setAttribute("title", "Launch rocket — back to top");
    } else {
      btn.setAttribute("aria-label", "Scroll to footer to launch the rocket");
      btn.setAttribute("title", "Scroll to footer to launch the rocket");
    }
    updateProgress();
  }

  /* ── JS rAF rocket flight ──────────────────────────────────────────────
     Replaces CSS offset-path animation. Full premium implementation:
       • G2-continuous loop via 4 cubic Bézier circle segments (kappa)
       • C2-smooth velocity profile: smootherstep + Gaussian apex + exit-bias
       • Per-frame tangent rotation + curvature banking + speed stretch
       • Canvas2D particle trail: hot core (lighter) + smoke (source-over)   */
  /* ── Premium WebGL2 rocket launch (Canvas2D fallback) ────────────────
     Architecture:
       • CPU-side deterministic physics (fixed-seed RNG, fixed timestep)
       • Shared particle pool used by either renderer
       • WebGL2: instanced quads, procedural domain-warped FBM smoke
         shader, premultiplied-alpha smoke pass + additive hot pass
       • Canvas2D: radial-gradient fallback when WebGL2 unavailable     */
  function launchRocketAnimation(wrap, onDone) {
    // ── Tunables (TZ §6: parameterized) ─────────────────────────────────
    const DURATION = 2600;            // ms total flight time
    const PRE_MS = 800;              // фаза нагнетания перед стартом, мс (TZ §3)
    const POST_SMOKE_MS = 0;          // дым убирается в момент старта → буфер не нужен
    const FIXED_STEP = 1 / 60;        // deterministic sim step, seconds
    const SMOKE_LAG_MS = 140;         // визуальное запаздывание дыма за соплом
    const SMOKE_SETTLE_ACC = 50;      // px/s² — мягкое оседание дыма вниз
    const SMOKE_DRAG = 0.93;          // коэффициент сохранения скорости за 1/60 сек
    const SMOKE_SPREAD = 1.0;         // нормированный множитель радиальной дисперсии
    const SMOKE_LIFETIME = 3.0;       // сек — базовое время жизни клубов
    const EMIT_SMOKE_IN_FLIGHT = false; // эмиссия в полёте — выкл. (TZ §3)
    // Deterministic particle RNG: fixed seed for identical visuals every launch.
    let rngState = 0x51f15eed >>> 0;
    function rand() {
      rngState = (rngState + 0x6d2b79f5) | 0;
      let t = Math.imul(rngState ^ (rngState >>> 15), 1 | rngState);
      t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }

    // ── Trajectory ──────────────────────────────────────────────────────
    const vw = window.innerWidth, vh = window.innerHeight;
    const s = Math.max(0.45, Math.min(vh / 900, (vw - 60) / 480, 1.4));
    const R = 110 * s;
    const kc = R * 0.5522847498; // Bézier kappa for circle approximation
    // Loop entry/exit at (lx, ly); center at (lx+R, ly)
    const lx = -260 * s, ly = -560 * s;
    const cx = lx + R, cy = ly;

    // Seven cubic Bézier segments [p0, cp1, cp2, p1] in local px offset from start
    const segs = [
      // Approach: gentle arc from launch pad up toward loop entry
      [[0, 0], [-40 * s, -120 * s], [-120 * s, -260 * s], [-180 * s, -360 * s]],
      [[-180 * s, -360 * s], [-240 * s, -460 * s], [lx, ly + kc], [lx, ly]],
      // Loop (4 segments, G2-continuous circle): left→top→right→bottom→left
      [[cx - R, cy], [cx - R, cy - kc], [cx - kc, cy - R], [cx, cy - R]],
      [[cx, cy - R], [cx + kc, cy - R], [cx + R, cy - kc], [cx + R, cy]],
      [[cx + R, cy], [cx + R, cy + kc], [cx + kc, cy + R], [cx, cy + R]],
      [[cx, cy + R], [cx - kc, cy + R], [cx - R, cy + kc], [cx - R, cy]],
      // Exit: upward off-screen
      [[lx, ly], [lx, ly - kc], [-220 * s, -780 * s], [-160 * s, -900 * s]],
    ];

    // ── Arc-length table (uniform-speed reparameterization) ─────────────
    function bpt(seg, t) {
      const [p0, c1, c2, p1] = seg;
      const mt = 1 - t, mt2 = mt * mt, mt3 = mt2 * mt, t2 = t * t, t3 = t2 * t;
      return [
        mt3 * p0[0] + 3 * mt2 * t * c1[0] + 3 * mt * t2 * c2[0] + t3 * p1[0],
        mt3 * p0[1] + 3 * mt2 * t * c1[1] + 3 * mt * t2 * c2[1] + t3 * p1[1],
      ];
    }
    function btan(seg, t) {
      const [p0, c1, c2, p1] = seg;
      const mt = 1 - t, mt2 = mt * mt, t2 = t * t;
      return [
        3 * (mt2 * (c1[0] - p0[0]) + 2 * mt * t * (c2[0] - c1[0]) + t2 * (p1[0] - c2[0])),
        3 * (mt2 * (c1[1] - p0[1]) + 2 * mt * t * (c2[1] - c1[1]) + t2 * (p1[1] - c2[1])),
      ];
    }
    function bcurv(seg, t) {
      const tan = btan(seg, t);
      const [p0, c1, c2, p1] = seg; const mt = 1 - t;
      const d2x = 6 * (mt * (c2[0] - 2 * c1[0] + p0[0]) + t * (p1[0] - 2 * c2[0] + c1[0]));
      const d2y = 6 * (mt * (c2[1] - 2 * c1[1] + p0[1]) + t * (p1[1] - 2 * c2[1] + c1[1]));
      const cr = tan[0] * d2y - tan[1] * d2x;
      const ln = Math.hypot(tan[0], tan[1]);
      return ln < 1e-8 ? 0 : cr / (ln * ln * ln);
    }

    const NSAMP = 100; // samples per segment for arc table
    const arcTbl = []; // {si, t, len}
    let totalArc = 0;
    for (let si = 0; si < segs.length; si++) {
      let prev = bpt(segs[si], 0);
      for (let i = 1; i <= NSAMP; i++) {
        const t = i / NSAMP;
        const cur = bpt(segs[si], t);
        const dx = cur[0] - prev[0], dy = cur[1] - prev[1];
        totalArc += Math.sqrt(dx * dx + dy * dy);
        arcTbl.push({ si, t, len: totalArc });
        prev = cur;
      }
    }
    function arcLookup(u) {
      const tgt = u * totalArc;
      let lo = 0, hi = arcTbl.length - 1;
      while (lo < hi) { const m = (lo + hi) >> 1; if (arcTbl[m].len < tgt) lo = m + 1; else hi = m; }
      if (lo === 0) return { si: arcTbl[0].si, t: arcTbl[0].t };
      const a = arcTbl[lo - 1], b = arcTbl[lo];
      const f = (b.len - a.len) > 1e-10 ? (tgt - a.len) / (b.len - a.len) : 0;
      return { si: b.si, t: a.t + f * (b.t - a.t) };
    }

    // ── Velocity profile (C2-smooth) ────────────────────────────────────
    // smootherstep base + Gaussian apex slow-down + exit bias
    function smootherstep(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
    const APEX_T = 0.54, APEX_S = 0.072, APEX_A = 0.42, EXIT_B = 0.20;
    function velProfile(t) {
      let u = smootherstep(t);
      const dt = t - APEX_T;
      u *= 1 - APEX_A * Math.exp(-(dt * dt) / (2 * APEX_S * APEX_S));
      if (t > 0.74) { const e = (t - 0.74) / 0.26; u += EXIT_B * e * e; }
      return Math.max(0, Math.min(1, u));
    }
    // Numerical derivative for speed factor
    function velSpeed(t) {
      const h = 0.008;
      return (velProfile(Math.min(1, t + h)) - velProfile(Math.max(0, t - h))) / (2 * h);
    }

    function rocketStateAt(flightT) {
      const u = velProfile(flightT);
      const { si, t: bt } = arcLookup(u);
      const seg = segs[si];
      const pos = bpt(seg, bt);
      const tan = btan(seg, bt);
      const tl = Math.hypot(tan[0], tan[1]);
      const tx = tl > 1e-8 ? tan[0] / tl : 0;
      const ty = tl > 1e-8 ? tan[1] / tl : -1;
      const angle = Math.atan2(tx, -ty);
      const curv = bcurv(seg, bt);
      const bank = Math.max(-0.38, Math.min(0.38, curv * R * 0.22));
      const spd = velSpeed(flightT);
      const sy2 = 1 + Math.min(0.22, spd * 0.14);
      const sx2 = 1 - Math.min(0.06, spd * 0.04);
      const vib = 0.009 * Math.sin(flightT * Math.PI * 12);
      const fAng = angle + bank + vib;
      const rocketCX = startX + pos[0];
      const rocketCY = startY + pos[1];
      const noz = nozzlePos(rocketCX, rocketCY, fAng);
      return { pos, tx, ty, spd, sx2, sy2, fAng, noz };
    }

    // ── Стартовая позиция ракеты в viewport ─────────────────────────────
    const wr = wrap.getBoundingClientRect();
    const startX = wr.left + wr.width * 0.5;
    const startY = wr.top + wr.height * 0.5;

    // Позиция сопла ракеты в viewport-координатах. SVG смотрит вверх,
    // сопло — нижний конец. CSS rotate(ang) поворот по часовой при y-вниз:
    // bottomEnd при rotate(ang) = (cx - sin(ang)*L, cy + cos(ang)*L).
    const NOZZLE_LEN = 14;
    function nozzlePos(cx2, cy2, ang) {
      return {
        x: cx2 - Math.sin(ang) * NOZZLE_LEN,
        y: cy2 + Math.cos(ang) * NOZZLE_LEN,
      };
    }

    // ── Canvas + WebGL2 detection ──────────────────────────────────────
    // Cap DPR at 2: на 3x retina лишний пиксель не виден из-за блюра дыма,
    // зато fragment shader экономит до 2.25x работы.
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cvs = document.createElement("canvas");
    cvs.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:9998;";
    cvs.width = Math.max(1, Math.round(vw * dpr));
    cvs.height = Math.max(1, Math.round(vh * dpr));
    cvs.style.width = vw + "px";
    cvs.style.height = vh + "px";
    document.body.appendChild(cvs);

    let gl = null;
    try {
      gl = cvs.getContext("webgl2", {
        alpha: true,
        premultipliedAlpha: true,
        antialias: false,
        depth: false,
        preserveDrawingBuffer: false,
      });
    } catch (e) { /* unsupported → fallback */ }

    const useGL = !!gl;
    // WebGL → плотные клубы из ~2400 instanced-quad'ов с шейдерным fbm.
    // Canvas2D fallback → меньше частиц, мягкие радиальные градиенты.
    const NPARTS = useGL ? 2400 : 800;

    // ── Particle pool (CPU, shared) ────────────────────────────────────
    const P = new Array(NPARTS);
    for (let i = 0; i < NPARTS; i++) {
      P[i] = { x: 0, y: 0, vx: 0, vy: 0, life: 0, maxL: 1, size: 0, hot: 0, seed: (i + 1) * 0.61803398875 };
    }
    let ph = 0;

    // ── Эмиссия частиц ────────────────────────────────────────────────
    // dense=true → фаза нагнетания (широкий клубящийся столб).
    // dense=false → эмиссия в полёте (только при EMIT_SMOKE_IN_FLIGHT).
    function emit(noz, exhX, exhY, spd, dense) {
      if (dense) {
        // Плотный кипящий пар у пускового стола: широкие реалистичные клубы.
        const baseCnt = (useGL ? 18 : 8) + ((rand() * (useGL ? 9 : 6)) | 0);
        const cnt = Math.max(4, Math.round(baseCnt * (0.7 + spd * 0.2)));
        const baseR = (useGL ? 70 : 50) * s * SMOKE_SPREAD;  // широкая «лужа»
        for (let i = 0; i < cnt; i++) {
          const p = P[ph++ % NPARTS];
          // Сплющенный диск вокруг сопла: дым стелется, а не пыхает точкой.
          const ang = rand() * Math.PI * 2;
          const rr = Math.sqrt(rand());                       // равномерно по площади
          p.x = noz.x + Math.cos(ang) * rr * baseR;
          p.y = noz.y + Math.sin(ang) * rr * baseR * 0.36 + 4 * s;
          // Более широкий веер направлений → меньше «луча», больше клубов.
          const swayAng = ang + (rand() - 0.5) * 0.72;
          const outSpd = (40 + rand() * 80) * (0.7 + spd * 0.3);
          p.vx = Math.cos(swayAng) * outSpd * SMOKE_SPREAD + (rand() - 0.5) * 26 * SMOKE_SPREAD;
          p.vy = (5 + rand() * 28) * (0.7 + spd * 0.3);       // строго ≥ 0 — дым никогда не вверх
          p.maxL = SMOKE_LIFETIME * (0.85 + rand() * 0.55);
          // Больше клубов разного калибра: малые «кудри» + крупные облака.
          p.size = (useGL ? 36 : 14) * s + rand() * (useGL ? 50 : 28) * s;
          p.life = 1;
          p.hot = 0;
        }
        return;
      }
      if (!EMIT_SMOKE_IN_FLIGHT) return;
      const perpX = -exhY, perpY = exhX;
      const cnt = Math.max(6, Math.round(8 + spd * 7));
      for (let i = 0; i < cnt; i++) {
        const p = P[ph++ % NPARTS];
        const hot = rand() < 0.28 ? 1 : 0;
        if (hot) {
          const spread = (rand() - 0.5) * 0.42;
          const spd2 = (160 + rand() * 180) * spd;
          p.x = noz.x + (rand() - 0.5) * 3;
          p.y = noz.y + (rand() - 0.5) * 3;
          p.vx = (exhX + perpX * spread) * spd2;
          p.vy = (exhY + perpY * spread) * spd2;
          p.maxL = 0.18 + rand() * 0.22;
          p.size = (2 + rand() * 4) * s;
        } else {
          const spread = (rand() - 0.5) * SMOKE_SPREAD * 0.18;
          const spd2 = (90 + rand() * 100) * spd;
          const ang = rand() * Math.PI * 2;
          const burstR = 1 + rand() * 3;
          p.x = noz.x + Math.cos(ang) * burstR;
          p.y = noz.y + Math.sin(ang) * burstR;
          p.vx = (exhX + perpX * spread) * spd2;
          p.vy = Math.max(0, (exhY + perpY * spread) * spd2);
          p.maxL = SMOKE_LIFETIME * 0.7 + rand() * 0.5;
          p.size = (6 + rand() * 10) * s;
        }
        p.life = 1;
        p.hot = hot;
      }
    }

    // ── Physics step ───────────────────────────────────────────────────
    // lockSmokeY=true означает «ракета взлетела». По требованию пользователя
    // дым в этот момент полностью убирается из кадра — никакого облака во
    // время полёта (TZ §4 переопределён). Hot-particles продолжают жить,
    // если когда-нибудь включат EMIT_SMOKE_IN_FLIGHT.
    function physicsStep(dt, lockSmokeY) {
      if (lockSmokeY) {
        for (let i = 0; i < NPARTS; i++) {
          const p = P[i];
          if (!p.hot && p.life > 0) p.life = 0;
        }
      }
      const dragStep = Math.pow(SMOKE_DRAG, dt * 60);
      const ceilingY = startY - 2 * s;
      for (let i = 0; i < NPARTS; i++) {
        const p = P[i]; if (p.life <= 0) continue;
        p.life -= dt / p.maxL;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        if (!p.hot) {
          // В lockSmokeY дым уже мёртв — сюда попадаем только в PRE-фазе.
          if (p.vy < 0) p.vy = 0;
          p.vy += SMOKE_SETTLE_ACC * dt;
          const t = 1 - p.life;
          // Двухчастотная турбулентность: высокая (мелкие кудри) + низкая
          // (крупные клубы) → визуально читаемые puff'ы вместо ровного облака.
          const swirl = Math.sin(t * 7.3 + p.seed * 6.7)
            + 0.62 * Math.sin(t * 3.1 + p.seed * 4.2)
            + 0.34 * Math.sin(t * 1.5 + p.seed * 2.3);
          p.vx += swirl * 26 * SMOKE_SPREAD * dt;
          p.vx *= dragStep;
          p.vy *= dragStep;
          if (p.vy > 95) p.vy = 95;
          if (p.y < ceilingY) { p.y = ceilingY; if (p.vy < 0) p.vy = 0; }
        } else {
          const hd = Math.pow(0.94, dt * 60);
          p.vx *= hd; p.vy *= hd;
        }
      }
    }

    // ── Renderer (WebGL2 OR Canvas2D) ──────────────────────────────────
    // Once a canvas has a webgl2 context, getContext("2d") on it returns
    // null per spec — so we commit to a path based on probe result.
    function noop() { }
    let renderFrame = noop;
    let disposeRenderer = noop;
    if (useGL) {
      const gx = setupWebGLRenderer();
      if (gx) {
        renderFrame = gx.render;
        disposeRenderer = gx.dispose;
      } else {
        // Shader compile/link failed despite WebGL2 support — extremely
        // rare. Continue with no-op renderer so rocket still completes.
        // eslint-disable-next-line no-console
        console.warn("[rocket] WebGL2 shader setup failed; smoke disabled");
      }
    } else {
      const cx2 = setupCanvas2DRenderer();
      renderFrame = cx2.render;
      disposeRenderer = cx2.dispose;
    }

    // ───────────────────────────────────────────────────────────────────
    // WebGL2 renderer: ~1800 instanced quads, procedural domain-warped fbm
    // smoke shader, two passes: smoke (premul. over) + hot (additive).
    // ───────────────────────────────────────────────────────────────────
    function setupWebGLRenderer() {
      const VS = "#version 300 es\n"
        + "layout(location=0) in vec2 aCorner;\n"
        + "layout(location=1) in vec4 aPSA;\n"           // x, y, size, age
        + "layout(location=2) in vec2 aSK;\n"            // seed, kind
        + "uniform vec2 uRes;\n"
        + "out vec2 vUv;\n"
        + "out float vAge;\n"
        + "out float vSeed;\n"
        + "out float vKind;\n"
        + "void main() {\n"
        + "  vec2 worldPos = aPSA.xy + aCorner * aPSA.z;\n"
        + "  vec2 ndc = (worldPos / uRes) * 2.0 - 1.0;\n"
        + "  ndc.y = -ndc.y;\n"
        + "  gl_Position = vec4(ndc, 0.0, 1.0);\n"
        + "  vUv = aCorner;\n"
        + "  vAge = aPSA.w;\n"
        + "  vSeed = aSK.x;\n"
        + "  vKind = aSK.y;\n"
        + "}\n";

      const FS = "#version 300 es\n"
        + "precision highp float;\n"
        + "in vec2 vUv;\n"
        + "in float vAge;\n"
        + "in float vSeed;\n"
        + "in float vKind;\n"
        + "uniform float uPass;\n"                       // 0=smoke, 1=hot
        + "out vec4 fragColor;\n"
        + "float hash21(vec2 p, float s) {\n"
        + "  p = fract(p * vec2(123.34, 456.21) + s * 17.71);\n"
        + "  p += dot(p, p + 45.32);\n"
        + "  return fract(p.x * p.y);\n"
        + "}\n"
        + "float vnoise(vec2 p, float s) {\n"
        + "  vec2 i = floor(p);\n"
        + "  vec2 f = fract(p);\n"
        + "  vec2 u = f * f * (3.0 - 2.0 * f);\n"
        + "  return mix(\n"
        + "    mix(hash21(i, s), hash21(i + vec2(1.0,0.0), s), u.x),\n"
        + "    mix(hash21(i + vec2(0.0,1.0), s), hash21(i + vec2(1.0,1.0), s), u.x),\n"
        + "    u.y);\n"
        + "}\n"
        + "float fbm(vec2 p, float s) {\n"
        + "  float v = 0.0; float a = 0.5;\n"
        + "  for (int i = 0; i < 4; i++) {\n"
        + "    v += a * vnoise(p, s);\n"
        + "    p *= 2.07; a *= 0.5;\n"
        + "  }\n"
        + "  return v;\n"
        + "}\n"
        // Domain warp = fbm of a position perturbed by another fbm —
        // даёт «curl-like» закрутки, как у настоящего стартового дыма.
        + "float warp(vec2 p, float s) {\n"
        + "  vec2 q = vec2(fbm(p, s), fbm(p + vec2(5.2, 1.3), s + 0.31));\n"
        + "  return fbm(p + 1.4 * q, s + 0.71);\n"
        + "}\n"
        + "void main() {\n"
        + "  if (abs(vKind - uPass) > 0.5) discard;\n"
        + "  float r = length(vUv);\n"
        + "  if (r > 1.0) discard;\n"
        + "  float life = 1.0 - vAge;\n"
        // Внутренняя структура клуба: domain-warped fbm — крупные «cauliflower»
        // bulbs с тёмными прожилками; чем больше масштаб, тем виднее clumps.
        + "  vec2 nuv = vUv * 2.85 + vec2(vSeed * 12.34, vAge * 20.1);\n"
        + "  float n = warp(nuv, vSeed * 0.7);\n"
        + "  n = 0.55 + n * 0.62;\n"
        // Soft falloff: плотный центр, туманные края.
        + "  float core = smoothstep(0.0, 0.45, 1.0 - r);\n"
        + "  float halo = smoothstep(0.0, 1.0, 1.0 - r);\n"
        + "  float density = mix(halo * 0.6, core, 0.62) * n;\n"
        + "  if (vKind > 0.5) {\n"
        // Hot core — аддитивный огненный свет.
        + "    vec3 col = mix(vec3(1.0, 0.55, 0.05), vec3(1.0, 0.92, 0.5), life * 0.7);\n"
        + "    float a = density * (life * life) * 0.95;\n"
        + "    fragColor = vec4(col * a, a);\n"
        + "  } else {\n"
        // Smoke — единая светло-серая палитра для всех тем. Лёгкая
        // лавандовая подкладка сохраняет согласие с docs-портал темой.
        // На светлой теме контраст обеспечивает альфа (1.6) + чуть более
        // тёмный outer-rim; на тёмной теме это читается как обычный
        // светлый дым. Альфа без буста.
        + "    vec3 cInner = vec3(0.88, 0.87, 0.91);\n"
        + "    vec3 cMid   = vec3(0.78, 0.77, 0.82);\n"
        + "    vec3 cOuter = vec3(0.68, 0.66, 0.72);\n"
        + "    float t = clamp(density * 1.35, 0.0, 1.0);\n"
        + "    vec3 col = mix(cOuter, mix(cMid, cInner, smoothstep(0.45, 1.0, t)), smoothstep(0.0, 0.7, t));\n"
        + "    col *= mix(1.0, 0.9, vAge * 0.5);\n"
        + "    float clump = 0.72 + 0.5 * sin(vSeed * 8.7 + vAge * 9.5);\n"
        + "    float a = density * (life * life * 1.6 * clump);\n"
        + "    fragColor = vec4(col * a, a);\n"
        + "  }\n"
        + "}\n";

      function compile(type, src) {
        const sh = gl.createShader(type);
        gl.shaderSource(sh, src);
        gl.compileShader(sh);
        if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
          // eslint-disable-next-line no-console
          console.warn("[rocket] shader compile failed:", gl.getShaderInfoLog(sh));
          gl.deleteShader(sh);
          return null;
        }
        return sh;
      }
      const vs = compile(gl.VERTEX_SHADER, VS);
      const fs = compile(gl.FRAGMENT_SHADER, FS);
      if (!vs || !fs) return null;
      const prog = gl.createProgram();
      gl.attachShader(prog, vs);
      gl.attachShader(prog, fs);
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        // eslint-disable-next-line no-console
        console.warn("[rocket] program link failed:", gl.getProgramInfoLog(prog));
        return null;
      }
      gl.deleteShader(vs); gl.deleteShader(fs);

      const uRes = gl.getUniformLocation(prog, "uRes");
      const uPass = gl.getUniformLocation(prog, "uPass");

      // Quad corners ((-1,-1) .. (1,1)) reused for every instance.
      const cornerBuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, cornerBuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

      // Per-instance attribute buffers: (x,y,size,age) and (seed,kind).
      const psaArr = new Float32Array(NPARTS * 4);
      const skArr = new Float32Array(NPARTS * 2);
      const psaBuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, psaBuf);
      gl.bufferData(gl.ARRAY_BUFFER, psaArr.byteLength, gl.DYNAMIC_DRAW);
      const skBuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, skBuf);
      gl.bufferData(gl.ARRAY_BUFFER, skArr.byteLength, gl.DYNAMIC_DRAW);

      const vao = gl.createVertexArray();
      gl.bindVertexArray(vao);
      gl.bindBuffer(gl.ARRAY_BUFFER, cornerBuf);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.vertexAttribDivisor(0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, psaBuf);
      gl.enableVertexAttribArray(1);
      gl.vertexAttribPointer(1, 4, gl.FLOAT, false, 0, 0);
      gl.vertexAttribDivisor(1, 1);
      gl.bindBuffer(gl.ARRAY_BUFFER, skBuf);
      gl.enableVertexAttribArray(2);
      gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 0, 0);
      gl.vertexAttribDivisor(2, 1);
      gl.bindVertexArray(null);

      function ensureCanvasSize() {
        const w = Math.max(1, Math.round(window.innerWidth * dpr));
        const h = Math.max(1, Math.round(window.innerHeight * dpr));
        if (cvs.width !== w || cvs.height !== h) {
          cvs.width = w; cvs.height = h;
          cvs.style.width = window.innerWidth + "px";
          cvs.style.height = window.innerHeight + "px";
        }
      }

      function render() {
        // Pack live particles into instance buffers (compact, no holes).
        let live = 0;
        for (let i = 0; i < NPARTS; i++) {
          const p = P[i]; if (p.life <= 0) continue;
          const age = 1 - p.life;
          const r = p.size * (0.95 + age * 1.95);
          const j = live * 4;
          psaArr[j] = p.x * dpr;
          psaArr[j + 1] = p.y * dpr;
          psaArr[j + 2] = r * dpr;
          psaArr[j + 3] = age;
          const k = live * 2;
          skArr[k] = p.seed;
          skArr[k + 1] = p.hot;
          live++;
        }

        ensureCanvasSize();
        gl.viewport(0, 0, cvs.width, cvs.height);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.enable(gl.BLEND);
        gl.useProgram(prog);
        gl.uniform2f(uRes, cvs.width, cvs.height);
        if (live === 0) return;

        gl.bindBuffer(gl.ARRAY_BUFFER, psaBuf);
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, psaArr.subarray(0, live * 4));
        gl.bindBuffer(gl.ARRAY_BUFFER, skBuf);
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, skArr.subarray(0, live * 2));
        gl.bindVertexArray(vao);

        // Pass 1: smoke (premultiplied "over")
        gl.uniform1f(uPass, 0.0);
        gl.blendFuncSeparate(gl.ONE, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, live);

        // Pass 2: hot core (additive bloom)
        gl.uniform1f(uPass, 1.0);
        gl.blendFunc(gl.ONE, gl.ONE);
        gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, live);

        gl.bindVertexArray(null);
      }

      function dispose() {
        try {
          gl.deleteBuffer(cornerBuf);
          gl.deleteBuffer(psaBuf);
          gl.deleteBuffer(skBuf);
          gl.deleteVertexArray(vao);
          gl.deleteProgram(prog);
        } catch (e) { /* best-effort */ }
      }
      return { render, dispose };
    }

    // ───────────────────────────────────────────────────────────────────
    // Canvas2D fallback: радиальные градиенты, без шейдеров.
    // ───────────────────────────────────────────────────────────────────
    function setupCanvas2DRenderer() {
      // Fallback works in CSS pixels — отдаём resolution backing store 1:1.
      cvs.width = window.innerWidth;
      cvs.height = window.innerHeight;
      cvs.style.width = window.innerWidth + "px";
      cvs.style.height = window.innerHeight + "px";
      const ctx = cvs.getContext("2d");

      function ensureSize() {
        if (cvs.width !== window.innerWidth || cvs.height !== window.innerHeight) {
          cvs.width = window.innerWidth;
          cvs.height = window.innerHeight;
        }
      }

      function render() {
        ensureSize();
        ctx.clearRect(0, 0, cvs.width, cvs.height);
        ctx.globalCompositeOperation = "lighter";
        for (let i = 0; i < NPARTS; i++) {
          const p = P[i]; if (p.life <= 0 || !p.hot) continue;
          const a = Math.max(0, p.life);
          const r = p.size * (0.35 + a * 0.65);
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
          g.addColorStop(0, "rgba(255,225,110," + (a * 0.95).toFixed(3) + ")");
          g.addColorStop(0.38, "rgba(255,130,20," + (a * 0.58).toFixed(3) + ")");
          g.addColorStop(1, "rgba(160,30,0,0)");
          ctx.fillStyle = g;
          ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
        }
        ctx.globalCompositeOperation = "source-over";
        for (let i = 0; i < NPARTS; i++) {
          const p = P[i]; if (p.life <= 0 || p.hot) continue;
          const age = 1 - p.life;
          const clump = 0.85 + 0.45 * Math.sin(p.seed * 8.7 + age * 10.5);
          const a = Math.max(0, p.life * p.life * 0.62 * clump);
          const r = p.size * (0.95 + age * 2.4);
          const g = ctx.createRadialGradient(p.x, p.y, r * 0.02, p.x, p.y, r);
          // Единая светло-серая палитра вне зависимости от темы.
          g.addColorStop(0, "rgba(224,222,232," + (a * 0.95).toFixed(3) + ")");
          g.addColorStop(0.28, "rgba(199,196,209," + (a * 0.78).toFixed(3) + ")");
          g.addColorStop(0.6, "rgba(173,168,184," + (a * 0.4).toFixed(3) + ")");
          g.addColorStop(1, "rgba(153,148,167,0)");
          ctx.fillStyle = g;
          ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
        }
      }
      return { render, dispose: noop };
    }

    // ── Animation loop ─────────────────────────────────────────────────
    let startTs = 0, simTs = 0, simAccumulator = 0, rafId = 0, disposed = false;

    function frame(ts) {
      if (disposed) return;
      if (!startTs) startTs = ts;
      const elapsed = ts - startTs;
      simAccumulator += Math.max(0, elapsed - simTs);

      // Детерминированный fixed-step: эмиссия и физика не зависят от FPS.
      while (simAccumulator >= FIXED_STEP * 1000) {
        simTs += FIXED_STEP * 1000;
        simAccumulator -= FIXED_STEP * 1000;
        if (simTs < PRE_MS) {
          const preT = simTs / PRE_MS;
          const noz = nozzlePos(startX, startY, 0);
          emit(noz, 0, 1, 0.8 + preT * 2.5, true);
        } else if (EMIT_SMOKE_IN_FLIGHT) {
          const simFlightT = Math.min(1, (simTs - PRE_MS) / DURATION);
          const lagFlightT = Math.max(0, simFlightT - (SMOKE_LAG_MS / DURATION));
          const smokeState = rocketStateAt(lagFlightT);
          emit(smokeState.noz, -smokeState.tx, -smokeState.ty, 0.55 + smokeState.spd * 1.6, false);
        }
        physicsStep(FIXED_STEP, simTs >= PRE_MS);
      }

      renderFrame();

      // ── Фаза 1: до старта только дым ────────────────────────────────
      if (elapsed < PRE_MS) {
        rafId = window.requestAnimationFrame(frame);
        return;
      }

      // ── Фаза 2: полёт ракеты по фиксированной траектории ────────────
      const flightT = Math.min(1, (elapsed - PRE_MS) / DURATION);
      const rocketState = rocketStateAt(flightT);
      wrap.style.transform =
        "translate(" + rocketState.pos[0].toFixed(2) + "px," + rocketState.pos[1].toFixed(2) + "px)" +
        " rotate(" + rocketState.fAng.toFixed(4) + "rad)" +
        " scaleX(" + rocketState.sx2.toFixed(4) + ") scaleY(" + rocketState.sy2.toFixed(4) + ")";

      if (flightT > 0.84) {
        const ft = (flightT - 0.84) / 0.16;
        wrap.style.opacity = (1 - ft * ft).toFixed(4);
      }

      if (flightT < 1 || elapsed < PRE_MS + DURATION + POST_SMOKE_MS) {
        rafId = window.requestAnimationFrame(frame);
      } else {
        cleanup(); onDone();
      }
    }

    function cleanup() {
      if (disposed) return;
      disposed = true;
      if (rafId) { window.cancelAnimationFrame(rafId); rafId = 0; }
      try { disposeRenderer(); } catch (e) { /* best-effort */ }
      cvs.remove();
      wrap.style.transform = "";
      wrap.style.opacity = "";
    }

    rafId = window.requestAnimationFrame(frame);
    return cleanup;
  }

  const wrap = btn.querySelector(".docs-back-to-top__rocket-wrap");

  btn.addEventListener("click", () => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (isLaunching) {
      return;
    }
    // Gate: only the armed (full-pill) state launches. In compact mode we
    // give a small shake — feedback that the button registered the click
    // but the rocket isn't ready until the user reaches the footer.
    if (!btn.classList.contains("docs-back-to-top--armed")) {
      btn.classList.remove("docs-back-to-top--nudge");
      // Force reflow so the animation re-triggers on rapid repeat clicks.
      void btn.offsetWidth;
      btn.classList.add("docs-back-to-top--nudge");
      window.setTimeout(() => btn.classList.remove("docs-back-to-top--nudge"), 620);
      return;
    }
    if (!reduceMotion) {
      isLaunching = true;
      btn.classList.add("docs-back-to-top--launching");
      // After the rocket exits the viewport we need to drop the --launching
      // class so the FAB returns to its scroll-based icon state. But the
      // base CSS doesn't transition background-color/box-shadow, so the
      // pill snaps from transparent back to solid instantly — and if the
      // page just smooth-scrolled to top, the FAB is also fading opacity
      // 1→0 at the same moment, so the user sees an empty solid pill (a
      // "phantom circle" where the rocket was) briefly flash before the
      // fade completes. Hold --launching through the fade-out window when
      // the FAB is becoming hidden, and drop it immediately when the FAB
      // stays visible (so the icon snaps back to its compact/armed look).
      const finishLaunch = () => {
        isLaunching = false;
        // Block the compact pill / progress-ring from popping in while
        // smooth-scroll-to-top is still mid-page. The flag is cleared on
        // the next user-initiated scroll (see scroll listener below); a
        // safety timeout also clears it in case scroll never resumes.
        suppressUntilUserScroll = true;
        postLaunchSettled = false;
        updateVisibility();
        // FAB is now hidden — keep --launching so the pill stays
        // transparent through the opacity fade-out, then drop it once the
        // FAB is invisible so the styles are clean for the next show.
        window.setTimeout(
          () => btn.classList.remove("docs-back-to-top--launching"),
          320,
        );
        // Safety net: release suppression after a long settle window in
        // case the user never scrolls (e.g. very short page). On a normal
        // long page the user's first wheel/touch tick clears it sooner.
        window.setTimeout(() => {
          if (!suppressUntilUserScroll) return;
          suppressUntilUserScroll = false;
          updateVisibility();
        }, 4000);
      };
      const cancelFlight = launchRocketAnimation(wrap, finishLaunch);
      // Safety net: force-complete if rAF stalls (e.g. backgrounded tab).
      // Timeout = PRE_MS(2000) + DURATION(2600) + POST_SMOKE_MS(0) + 400 slack = 5000
      window.setTimeout(() => {
        if (!isLaunching) return;
        cancelFlight();
        finishLaunch();
      }, 5000);
      // Скролл откладываем до конца нагнетания — ракета должна улететь, а не
      // исчезнуть со страницей до взлёта. Кнопка fixed, поэтому ракета всегда
      // видна независимо от позиции скролла, но задержка делает переход плавнее.
      window.setTimeout(
        () => window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }),
        reduceMotion ? 0 : 2000,
      );
    }
    if (reduceMotion) {
      window.scrollTo({ top: 0, behavior: "auto" });
    }
  });

  // While suppressUntilUserScroll is set, watch for two stages:
  //   1) the smooth-scroll-to-top reaching window.scrollY === 0, and
  //   2) a fresh scroll movement away from that resting point.
  // Step 2 is what we treat as the user "starting to scroll", which is
  // the moment the FAB is allowed to come back according to scroll
  // dynamics. Plain scroll events without the settle stage are the
  // smooth-scroll-to-top ticks themselves and must NOT clear the flag.
  let postLaunchSettled = false;
  window.addEventListener(
    "scroll",
    () => {
      if (suppressUntilUserScroll) {
        if (!postLaunchSettled) {
          if (window.scrollY <= 0) postLaunchSettled = true;
        } else if (window.scrollY > 0) {
          suppressUntilUserScroll = false;
          postLaunchSettled = false;
        }
      }
      updateVisibility();
    },
    { passive: true },
  );
  window.addEventListener("resize", updateVisibility, { passive: true });

  document.body.appendChild(btn);
  updateVisibility();
}

/** Thin top progress indicator for long docs pages. */
function initDocsReadingProgressBar() {
  if (!document.getElementById("docs-top-nav")) {
    return;
  }
  if (document.querySelector(".docs-reading-progress")) {
    return;
  }

  const root = document.documentElement;
  const bar = document.createElement("div");
  bar.className = "docs-reading-progress is-hidden";
  bar.setAttribute("role", "progressbar");
  bar.setAttribute("aria-label", "Page reading progress");
  bar.setAttribute("aria-valuemin", "0");
  bar.setAttribute("aria-valuemax", "100");
  bar.setAttribute("aria-valuenow", "0");

  const fill = document.createElement("span");
  fill.className = "docs-reading-progress__fill";
  fill.setAttribute("aria-hidden", "true");
  bar.appendChild(fill);
  document.body.appendChild(bar);

  let ticking = false;
  function update() {
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    if (maxScroll <= 8) {
      bar.classList.add("is-hidden");
      fill.style.transform = "scaleX(0)";
      bar.setAttribute("aria-valuenow", "0");
      return;
    }

    bar.classList.remove("is-hidden");
    const scrollTop = Math.max(0, window.scrollY || root.scrollTop || 0);
    const ratio = Math.min(1, Math.max(0, scrollTop / maxScroll));
    fill.style.transform = `scaleX(${ratio})`;
    bar.setAttribute("aria-valuenow", String(Math.round(ratio * 100)));
  }

  function scheduleUpdate() {
    if (ticking) {
      return;
    }
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      update();
    });
  }

  window.addEventListener("scroll", scheduleUpdate, { passive: true });
  window.addEventListener("resize", scheduleUpdate, { passive: true });
  scheduleUpdate();
}

/**
 * Scales footer atmosphere (docs.css body::before / body::after) by scroll: subtler at the top of
 * the document, full strength near the bottom. Sets `--docs-footer-scroll-strength` on `<html>`.
 * CSS default is 1 when this script does not run.
 */
function initDocsFooterAtmosphereScroll() {
  const root = document.documentElement;
  const minStrength = 0.18;

  function computeStrength() {
    const scrollable = root.scrollHeight - window.innerHeight;
    if (scrollable <= 4) {
      return 1;
    }
    const t = Math.min(1, Math.max(0, window.scrollY / scrollable));
    return minStrength + (1 - minStrength) * t;
  }

  let ticking = false;
  function apply() {
    root.style.setProperty("--docs-footer-scroll-strength", computeStrength().toFixed(4));
    ticking = false;
  }

  function onScrollOrResize() {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(apply);
    }
  }

  window.addEventListener("scroll", onScrollOrResize, { passive: true });
  window.addEventListener("resize", onScrollOrResize, { passive: true });
  apply();
}

/** Keeps FAB and rocket above the footer by updating --docs-footer-visible-h on <body>. */
function initFabFooterAwareness() {
  const footer = document.getElementById("docs-site-footer");
  if (!footer) {
    return;
  }

  function update() {
    const rect = footer.getBoundingClientRect();
    const vh = window.innerHeight;
    const visible = Math.max(0, Math.min(footer.offsetHeight, vh - rect.top));
    document.body.style.setProperty("--docs-footer-visible-h", visible > 0 ? visible + "px" : "0px");
  }

  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update, { passive: true });
  update();
}

/** Site-wide footer on hand-written docs pages (presence of `#docs-top-nav`). */
function initDocsSiteFooter() {
  if (document.getElementById("docs-site-footer")) {
    return;
  }
  if (!document.getElementById("docs-top-nav")) {
    return;
  }

  const relPath = currentDocsRelPath();
  const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";

  const footer = document.createElement("footer");
  footer.id = "docs-site-footer";
  footer.className = "docs-site-footer";
  footer.setAttribute("role", "contentinfo");

  const inner = document.createElement("div");
  inner.className = "container docs-site-footer__inner";

  // ── Multi-column navigation ──────────────────────────────────────────────
  const cols = document.createElement("nav");
  cols.className = "docs-site-footer__cols";
  cols.setAttribute("aria-label", "Footer navigation");

  const groups = [
    {
      label: "Docs",
      links: [
        { href: "index.html", text: "Documentation home" },
        { href: "internal/README.html", text: "Internal docs" },
        { href: "internal/analysis/system-design.html", text: "System design" },
        { href: "internal/analysis/methodology.html", text: "Methodology" },
      ],
    },
    {
      label: "API",
      links: [
        { href: "internal/api/README.html", text: "Internal HTTP API" },
        { href: "openapi/index.html", text: "OpenAPI / Swagger UI" },
        { href: "internal/api/errors.html", text: "Error matrix" },
        { href: "pdoc/index.html", text: "Python API (pdoc)" },
      ],
    },
    {
      label: "Guides",
      links: [
        { href: "howto/0001-onboarding-from-zero-to-endpoint-docs.html", text: "Onboarding" },
        { href: "howto/README.html", text: "How-to guides" },
        { href: "runbooks/README.html", text: "Runbooks" },
        { href: "developer/README.html", text: "Developer docs" },
      ],
    },
    {
      label: "Governance",
      links: [
        { href: "adr/README.html", text: "ADRs" },
        { href: "rfc/README.html", text: "RFCs" },
        { href: "backlog/README.html", text: "Backlog" },
        { href: `https://github.com/${DOCS_FEEDBACK_REPOSITORY}`, text: "GitHub", external: true },
      ],
    },
  ];

  groups.forEach((group) => {
    const col = document.createElement("div");
    col.className = "docs-site-footer__col";

    const label = document.createElement("p");
    label.className = "docs-site-footer__col-label";
    label.textContent = group.label;
    col.appendChild(label);

    const ul = document.createElement("ul");
    ul.className = "docs-site-footer__col-links";

    group.links.forEach((link) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = link.external ? link.href : relHref(fromDir, link.href);
      a.textContent = link.text;
      if (link.external) {
        a.target = "_blank";
        a.rel = "noopener noreferrer";
      }
      li.appendChild(a);
      ul.appendChild(li);
    });

    col.appendChild(ul);
    cols.appendChild(col);
  });

  // ── Bottom bar ───────────────────────────────────────────────────────────
  const bottom = document.createElement("div");
  bottom.className = "docs-site-footer__bottom";

  const copy = document.createElement("span");
  copy.className = "docs-site-footer__copy";
  copy.textContent = `© ${new Date().getFullYear()} ETR Study API`;

  const tech = document.createElement("span");
  tech.className = "docs-site-footer__tech";
  tech.textContent = "Static HTML · docs/ · No build step";

  bottom.appendChild(copy);
  bottom.appendChild(tech);

  inner.appendChild(cols);
  inner.appendChild(bottom);
  footer.appendChild(inner);
  document.body.appendChild(footer);
}

function buildDocsPageActions(fromDir, relPath) {
  const homeHref = relHref(fromDir, "index.html");
  const internalHref = relHref(fromDir, "internal/README.html");
  const qaHref = relHref(fromDir, "qa/README.html");
  const auditHref = relHref(fromDir, "audit/README.html");
  const backlogHref = relHref(fromDir, "backlog/README.html");
  const runbooksHref = relHref(fromDir, "runbooks/README.html");
  const howtoHref = relHref(fromDir, "howto/README.html");
  const pdocHref = relHref(fromDir, "pdoc/index.html");
  const openApiHref = relHref(fromDir, "openapi/index.html");
  return [
    {
      label: "Edit page",
      hint: "Open GitHub editor for this file",
      href: `https://github.com/${DOCS_FEEDBACK_REPOSITORY}/edit/main/docs/${relPath}`,
      group: "Page",
      keywords: ["edit", "github", "source"],
      external: true,
    },
    {
      label: "Report issue",
      hint: "Open prefilled docs feedback issue",
      href: docsFeedbackIssueUrl(),
      group: "Page",
      keywords: ["feedback", "bug", "issue"],
      external: true,
    },
    {
      label: "Copy page link",
      hint: "Copy current URL to clipboard",
      group: "Page",
      keywords: ["copy", "url", "link", "share"],
      action: () => {
        if (navigator && navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
          return navigator.clipboard.writeText(window.location.href);
        }
        return Promise.reject(new Error("Clipboard unavailable"));
      },
    },
    {
      label: "Toggle color theme",
      hint: "Cycle automatic, light, dark theme",
      group: "Commands",
      keywords: ["theme", "dark", "light", "appearance"],
      action: () => {
        cycleDocsTheme();
      },
    },
    {
      label: "Toggle reading mode",
      hint: "Focus content and hide navigation chrome",
      group: "Commands",
      keywords: ["reading", "focus", "mode", "distraction"],
      action: () => {
        toggleDocsReadingMode("palette");
      },
    },
    {
      label: "Go to documentation home",
      hint: "Main docs landing page",
      href: homeHref,
      group: "Go to page",
      keywords: ["home", "index", "landing"],
    },
    {
      label: "Go to internal docs",
      hint: "Internal project documentation hub",
      href: internalHref,
      group: "Go to page",
      keywords: ["internal", "hub"],
    },
    {
      label: "Go to QA checklists",
      hint: "Testing and visual checks",
      href: qaHref,
      group: "Go to page",
      keywords: ["qa", "checklist", "testing"],
    },
    {
      label: "Go to assessments",
      hint: "Quality and DX assessments",
      href: auditHref,
      group: "Go to page",
      keywords: ["assessment", "audit", "dx"],
    },
    {
      label: "Go to backlog",
      hint: "Priorities and roadmap",
      href: backlogHref,
      group: "Go to page",
      keywords: ["backlog", "roadmap", "priority"],
    },
    {
      label: "Go to runbooks",
      hint: "Operational troubleshooting docs",
      href: runbooksHref,
      group: "Go to page",
      keywords: ["runbook", "ops", "incident"],
    },
    {
      label: "Go to how-to guides",
      hint: "Step-by-step implementation guides",
      href: howtoHref,
      group: "Go to page",
      keywords: ["howto", "guide", "tutorial"],
    },
    {
      label: "Go to Python API (pdoc)",
      hint: "Generated API reference pages",
      href: pdocHref,
      group: "Go to page",
      keywords: ["api", "reference", "pdoc"],
    },
    {
      label: "Go to OpenAPI / Swagger UI",
      hint: "Static Swagger UI against openapi-baseline.json in docs/openapi/",
      href: openApiHref,
      group: "Go to page",
      keywords: ["openapi", "swagger", "contract"],
    },
  ];
}

function buildDocsSectionActions() {
  const main = document.querySelector("main.container");
  if (!main) {
    return [];
  }
  ensureTocAnchorIds(main);
  const sectionNodes = [
    ...main.querySelectorAll(
      ".docs-page-layout__article h2[id], .docs-page-layout__article h3[id], section.card h2[id], section.card h3[id]",
    ),
  ];
  const seen = new Set();
  const actions = [];
  for (const node of sectionNodes) {
    if (!node.id || seen.has(node.id) || node.closest(".docs-inpage-toc")) {
      continue;
    }
    seen.add(node.id);
    const rawLabel = (node.textContent || "").trim().replace(/\s+/g, " ");
    if (!rawLabel) {
      continue;
    }
    const isNested = node.tagName === "H3";
    actions.push({
      label: isNested ? `Jump to ${rawLabel}` : `Jump to section: ${rawLabel}`,
      hint: isNested ? "Subsection in current page" : "Section in current page",
      href: `#${node.id}`,
      group: "Jump to section",
      keywords: ["jump", "section", "toc", rawLabel.toLowerCase()],
    });
    if (actions.length >= 18) {
      break;
    }
  }
  return actions;
}

function injectDocsPageActions() {
  if (!desktopDocsPageActionsMq.matches) {
    return;
  }
  const main = document.querySelector("main.container");
  const navHost = document.getElementById("docs-top-nav");
  if (!main || !navHost || main.querySelector(".docs-page-actions")) {
    return;
  }
  const relPath = currentDocsRelPath();
  const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
  const wrap = document.createElement("div");
  wrap.className = "docs-page-actions";
  wrap.setAttribute("role", "toolbar");
  wrap.setAttribute("aria-label", "Page actions");

  const hint = document.createElement("span");
  hint.className = "docs-page-actions__hint";
  hint.textContent = `Quick actions (${docsPalettePrimaryHotkeyLabel()})`;
  wrap.appendChild(hint);

  const launcher = document.createElement("button");
  launcher.type = "button";
  launcher.className = "docs-page-actions__button";
  launcher.setAttribute("data-docs-quick-actions-open", "1");
  launcher.setAttribute("aria-haspopup", "dialog");
  launcher.setAttribute("aria-controls", "docs-quick-actions");
  launcher.setAttribute("aria-expanded", "false");
  launcher.textContent = `Open (${docsPalettePrimaryHotkeyLabel()})`;
  launcher.setAttribute("aria-label", "Open quick actions");
  wrap.appendChild(launcher);

  const focusBtn = document.createElement("button");
  focusBtn.type = "button";
  focusBtn.className = "docs-page-actions__button";
  focusBtn.setAttribute("data-docs-reading-mode-toggle", "1");
  focusBtn.setAttribute("aria-pressed", "false");
  focusBtn.addEventListener("click", () => {
    toggleDocsReadingMode("toolbar_button");
  });
  wrap.appendChild(focusBtn);

  for (const item of buildDocsPageActions(fromDir, relPath)) {
    const a = document.createElement("a");
    a.className = "docs-page-actions__link";
    a.textContent = item.label;
    a.href = item.href;
    if (item.href.startsWith("http")) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    wrap.appendChild(a);
  }
  syncDocsReadingModeControls(document.body.classList.contains("docs-reading-mode"));
  navHost.insertAdjacentElement("afterend", wrap);
}

function removeDocsPageActionsToolbar() {
  for (const el of document.querySelectorAll(".docs-page-actions")) {
    el.remove();
  }
}

function destroyDocsQuickActionsUi() {
  const panel = document.getElementById("docs-quick-actions");
  if (panel) {
    panel.hidden = true;
    panel.remove();
  }
  docsQuickActionsRuntime = null;
}

function installDocsQuickActionsUi() {
  if (docsQuickActionsRuntime) {
    return;
  }
  if (document.getElementById("docs-quick-actions")) {
    return;
  }
  const relPath = currentDocsRelPath();
  const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";

  const panel = document.createElement("div");
  panel.id = "docs-quick-actions";
  panel.className = "docs-quick-actions";
  panel.hidden = true;
  panel.innerHTML = `<div class="docs-quick-actions__backdrop" data-qa-close="1"></div>
<div class="docs-quick-actions__panel" role="dialog" aria-modal="true" aria-labelledby="docs-quick-actions-title">
  <div class="docs-quick-actions__head">
    <p class="docs-quick-actions__title" id="docs-quick-actions-title">Command Palette</p>
    <p class="docs-quick-actions__kbd-hint" aria-hidden="true"></p>
  </div>
  <input class="docs-quick-actions__filter" type="search" autocomplete="off" spellcheck="false" placeholder="Type a command, page, or section..." aria-label="Filter quick actions" />
  <ul class="docs-quick-actions__list"></ul>
</div>`;
  const filterInput = panel.querySelector(".docs-quick-actions__filter");
  const list = panel.querySelector(".docs-quick-actions__list");
  const kbdHint = panel.querySelector(".docs-quick-actions__kbd-hint");
  if (kbdHint) {
    kbdHint.textContent = `${docsPalettePrimaryHotkeyLabel()} • Enter execute • ↑/↓ navigate • Esc close`;
  }
  let activeActions = [];
  let filteredActions = [];
  let activeIndex = -1;
  let lastFocusedElement = null;
  document.body.appendChild(panel);

  function actionKey(item) {
    return [item.group || "", item.label || "", item.href || "", typeof item.action === "function" ? "fn" : "href"].join("|");
  }

  function paletteGlyphForItem(item) {
    const label = String(item.label || "").toLowerCase();
    const hint = String(item.hint || "").toLowerCase();
    const text = `${label} ${hint}`;
    if (text.includes("theme")) {
      return "☼";
    }
    if (text.includes("reading")) {
      return "◧";
    }
    if (text.includes("copy") || text.includes("link")) {
      return "⧉";
    }
    if (text.includes("report") || text.includes("issue") || text.includes("feedback")) {
      return "⚑";
    }
    if (text.includes("openapi") || text.includes("api")) {
      return "⌘";
    }
    if (text.includes("runbook")) {
      return "✚";
    }
    const group = String(item.group || "").toLowerCase();
    if (group.includes("commands")) {
      return "✦";
    }
    if (group.includes("jump")) {
      return "↳";
    }
    if (group.includes("page")) {
      return "◦";
    }
    return "•";
  }

  function palettePillForItem(item) {
    const group = String(item.group || "").toLowerCase();
    if (group.includes("commands")) {
      return "Command";
    }
    if (group.includes("jump")) {
      return "Section";
    }
    if (group.includes("page")) {
      return "Page";
    }
    return "Action";
  }

  function paletteKeycapsForItem(item) {
    if (typeof item.action === "function") {
      return ["↵"];
    }
    return ["↵", docsPaletteMetaEnterLabel()];
  }

  function appendHighlightedText(target, text, query) {
    const raw = String(text || "");
    const q = String(query || "").trim().toLowerCase();
    if (!q) {
      target.textContent = raw;
      return;
    }
    const lower = raw.toLowerCase();
    const idx = lower.indexOf(q);
    if (idx < 0) {
      target.textContent = raw;
      return;
    }
    const before = raw.slice(0, idx);
    const match = raw.slice(idx, idx + q.length);
    const after = raw.slice(idx + q.length);
    if (before) {
      target.appendChild(document.createTextNode(before));
    }
    const mark = document.createElement("mark");
    mark.className = "docs-quick-actions__match";
    mark.textContent = match;
    target.appendChild(mark);
    if (after) {
      target.appendChild(document.createTextNode(after));
    }
  }

  function visibleItems() {
    return [...list.querySelectorAll("a, button")].filter(
      (el) => el.closest("li") && !el.closest("li").hidden,
    );
  }

  function filterActions(query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) {
      return activeActions.slice();
    }
    return activeActions.filter((item) => {
      const hay = [
        item.label || "",
        item.hint || "",
        item.group || "",
        ...(Array.isArray(item.keywords) ? item.keywords : []),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }

  function renderActions(items, query = "") {
    list.replaceChildren();
    if (!items || items.length === 0) {
      const empty = document.createElement("li");
      empty.className = "docs-quick-actions__empty";
      empty.textContent = "No commands found. Try 'theme', 'runbook', or 'jump'.";
      list.appendChild(empty);
      activeIndex = -1;
      return;
    }

    let lastGroup = "";
    for (const item of items) {
      if (item.group && item.group !== lastGroup) {
        const sep = document.createElement("li");
        sep.className = "docs-quick-actions__group";
        sep.textContent = item.group;
        list.appendChild(sep);
        lastGroup = item.group;
      }

      const li = document.createElement("li");
      let actionEl;
      if (typeof item.action === "function") {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.addEventListener("click", () => {
          Promise.resolve(item.action())
            .then(() => {
              closePanel();
            })
            .catch(() => {
              closePanel();
            });
        });
        actionEl = btn;
      } else {
        const a = document.createElement("a");
        a.href = item.href || "#";
        if (item.external) {
          a.target = "_blank";
          a.rel = "noopener noreferrer";
        }
        a.addEventListener("click", () => {
          closePanel();
        });
        actionEl = a;
      }

      const row = document.createElement("span");
      row.className = "docs-quick-actions__item-row";
      const meta = document.createElement("span");
      meta.className = "docs-quick-actions__item-meta";
      const glyph = document.createElement("span");
      glyph.className = "docs-quick-actions__item-glyph";
      glyph.setAttribute("aria-hidden", "true");
      glyph.textContent = paletteGlyphForItem(item);
      const pill = document.createElement("span");
      pill.className = "docs-quick-actions__item-pill";
      pill.textContent = palettePillForItem(item);
      meta.appendChild(glyph);
      meta.appendChild(pill);

      const label = document.createElement("span");
      label.className = "docs-quick-actions__item-label";
      appendHighlightedText(label, item.label, query);
      row.appendChild(label);
      row.appendChild(meta);
      actionEl.appendChild(row);

      if (item.hint) {
        const hint = document.createElement("span");
        hint.className = "docs-quick-actions__item-hint";
        appendHighlightedText(hint, item.hint, query);
        actionEl.appendChild(hint);
      }

      const keycaps = document.createElement("span");
      keycaps.className = "docs-quick-actions__item-keycaps";
      for (const keycapLabel of paletteKeycapsForItem(item)) {
        const keycap = document.createElement("kbd");
        keycap.className = "docs-quick-actions__item-keycap";
        keycap.textContent = keycapLabel;
        keycaps.appendChild(keycap);
      }
      actionEl.appendChild(keycaps);

      actionEl.setAttribute("data-action-key", actionKey(item));
      li.appendChild(actionEl);
      list.appendChild(li);
    }
  }

  function setActiveIndex(nextIndex, opts = { focus: false }) {
    const items = visibleItems();
    if (items.length === 0) {
      activeIndex = -1;
      return;
    }
    const bounded = Math.max(0, Math.min(items.length - 1, nextIndex));
    activeIndex = bounded;
    items.forEach((itemEl, index) => {
      const isActive = index === bounded;
      itemEl.classList.toggle("docs-quick-actions__item--active", isActive);
      itemEl.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    if (opts.focus) {
      items[bounded].focus();
    }
  }

  function moveActive(delta, opts = { focus: false }) {
    const items = visibleItems();
    if (items.length === 0) {
      activeIndex = -1;
      return;
    }
    const base = activeIndex >= 0 ? activeIndex : delta > 0 ? -1 : 0;
    const next = (base + delta + items.length) % items.length;
    setActiveIndex(next, opts);
  }

  function activateActiveItem(options = { newTab: false, source: "keyboard" }) {
    const items = visibleItems();
    if (items.length === 0) {
      return false;
    }
    const idx = activeIndex >= 0 ? activeIndex : 0;
    const target = items[idx];
    if (!target) {
      return false;
    }
    const selected = filteredActions[idx] || null;
    if (options.newTab && target.tagName === "A") {
      window.open(target.href, "_blank", "noopener");
      if (selected) {
        emitDocsPaletteTelemetry("palette_execute", {
          source: options.source,
          label: selected.label,
          group: selected.group || "",
          kind: selected.action ? "command" : "link",
          new_tab: true,
        });
      }
      closePanel("execute");
      return true;
    }
    target.click();
    if (selected) {
      emitDocsPaletteTelemetry("palette_execute", {
        source: options.source,
        label: selected.label,
        group: selected.group || "",
        kind: selected.action ? "command" : "link",
        new_tab: false,
      });
    }
    return true;
  }

  function applyFilter(query) {
    const q = String(query || "").trim().toLowerCase();
    const prevIndex = activeIndex;
    const prevAction = prevIndex >= 0 ? filteredActions[prevIndex] : null;
    const prevKey = prevAction ? actionKey(prevAction) : "";
    filteredActions = filterActions(q);
    renderActions(filteredActions, q);
    if (filteredActions.length > 0 && prevKey) {
      const stickyIndex = filteredActions.findIndex((item) => actionKey(item) === prevKey);
      if (stickyIndex >= 0) {
        setActiveIndex(stickyIndex, { focus: false });
      } else {
        setActiveIndex(0, { focus: false });
      }
    } else if (filteredActions.length > 0) {
      setActiveIndex(0, { focus: false });
    } else {
      activeIndex = -1;
    }
    emitDocsPaletteTelemetry("palette_filter", {
      query_len: q.length,
      results_count: filteredActions.length,
    });
  }

  function refreshActionSet() {
    const pageActions = buildDocsPageActions(fromDir, relPath);
    const sectionActions = buildDocsSectionActions();
    activeActions = [...pageActions, ...sectionActions];
    filteredActions = activeActions.slice();
  }

  function closePanel(source = "manual") {
    panel.hidden = true;
    filterInput.value = "";
    applyFilter("");
    activeIndex = -1;
    const launcherBtn = document.querySelector("[data-docs-quick-actions-open]");
    if (launcherBtn) {
      launcherBtn.setAttribute("aria-expanded", "false");
    }
    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
      lastFocusedElement.focus();
    }
    lastFocusedElement = null;
    emitDocsPaletteTelemetry("palette_close", { source });
  }

  function showPaletteHintToast() {
    enqueueDocsPromoToast({
      title: "Command Palette available",
      text: "Hey! We have a premium Command Palette for quick navigation and actions.",
      dismissLabel: "Hide",
      primaryLabel: "Open Command Palette",
      onPrimary: () => {
        openPanel();
      },
      durationMs: 3000,
      className: "docs-palette-hint-toast",
    });
  }

  function openPanel() {
    lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    refreshActionSet();
    panel.hidden = false;
    filterInput.value = "";
    applyFilter("");
    filterInput.focus();
    filterInput.select();
    const launcherBtn = document.querySelector("[data-docs-quick-actions-open]");
    if (launcherBtn) {
      launcherBtn.setAttribute("aria-expanded", "true");
    }
    try {
      window.localStorage.setItem(DOCS_HOTKEY_HINT_DISMISSED_KEY, "1");
    } catch {
      // Ignore storage failures for private mode.
    }
    emitDocsPaletteTelemetry("palette_open", { source: "hotkey_or_button" });
    showPaletteHintToast();
  }

  docsQuickActionsRuntime = { panel, openPanel, closePanel };

  const launcherBtn = document.querySelector("[data-docs-quick-actions-open]");
  if (launcherBtn) {
    launcherBtn.addEventListener("click", () => {
      openPanel();
    });
  }

  panel.addEventListener("click", (event) => {
    const target = event.target;
    const closeHit =
      target instanceof Element && target.closest ? target.closest("[data-qa-close]") : null;
    if (closeHit && closeHit.getAttribute("data-qa-close") === "1") {
      closePanel();
    }
  });
  panel.addEventListener("keydown", (event) => {
    if (event.key !== "Tab" || panel.hidden) {
      return;
    }
    const focusables = [...panel.querySelectorAll(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter((el) => el instanceof HTMLElement && !el.hasAttribute("hidden"));
    if (focusables.length === 0) {
      event.preventDefault();
      filterInput.focus();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (event.shiftKey) {
      if (active === first || !panel.contains(active)) {
        event.preventDefault();
        last.focus();
      }
      return;
    }
    if (active === last || !panel.contains(active)) {
      event.preventDefault();
      first.focus();
    }
  });
  filterInput.addEventListener("input", () => {
    applyFilter(filterInput.value);
  });
  filterInput.addEventListener("keydown", (event) => {
    const items = visibleItems();
    if (event.key === "Escape") {
      event.preventDefault();
      closePanel();
      return;
    }
    if (items.length === 0) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveActive(1, { focus: true });
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveActive(-1, { focus: true });
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const openInNewTab = event.metaKey || event.ctrlKey;
      activateActiveItem({ newTab: openInNewTab, source: "filter_enter" });
    }
  });
  list.addEventListener("keydown", (event) => {
    const items = visibleItems();
    if (items.length === 0) {
      return;
    }
    const currentIndex = items.findIndex((el) => el === document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (currentIndex >= 0) {
        setActiveIndex(currentIndex, { focus: false });
      }
      moveActive(1, { focus: true });
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (currentIndex <= 0) {
        filterInput.focus();
      } else {
        setActiveIndex(currentIndex - 1, { focus: true });
      }
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (currentIndex >= 0) {
        setActiveIndex(currentIndex, { focus: false });
      }
      const openInNewTab = event.metaKey || event.ctrlKey;
      activateActiveItem({ newTab: openInNewTab, source: "list_enter" });
    }
  });
}

function injectDocsHotkeyHint() {
  if (!desktopDocsPageActionsMq.matches) {
    return;
  }
  if (document.querySelector(".docs-palette-hint-toast")) {
    return;
  }
  const hasTopNav = !!document.getElementById("docs-top-nav");
  if (!hasTopNav) {
    return;
  }
  try {
    if (localStorage.getItem("docs-palette-hint-dismissed") === "1") {
      return;
    }
  } catch (e) { }
  enqueueDocsPromoToast({
    title: "Command Palette available",
    text: `Hey! We have a premium Command Palette. Press <kbd>${docsPalettePrimaryHotkeyLabel()}</kbd> or open it now.`,
    dismissLabel: "Hide",
    primaryLabel: "Open Command Palette",
    storageKey: "docs-palette-hint-dismissed",
    onPrimary: () => {
      if (docsQuickActionsRuntime && typeof docsQuickActionsRuntime.openPanel === "function") {
        docsQuickActionsRuntime.openPanel();
        return;
      }
      const launcherBtn = document.querySelector("[data-docs-quick-actions-open]");
      if (launcherBtn && typeof launcherBtn.click === "function") {
        launcherBtn.click();
      }
    },
    durationMs: 3000,
    className: "docs-palette-hint-toast",
  });
}

function injectDocsSkipToContentLink() {
  if (document.querySelector(".docs-skip-link")) {
    return;
  }
  const main = document.querySelector("main.container");
  if (!main) {
    return;
  }
  if (!main.id) {
    main.id = "docs-main-content";
  }
  const link = document.createElement("a");
  link.className = "docs-skip-link";
  link.href = `#${main.id}`;
  link.textContent = "Skip to content";
  link.addEventListener("click", () => {
    main.setAttribute("tabindex", "-1");
    main.focus({ preventScroll: true });
  });
  document.body.insertAdjacentElement("afterbegin", link);
}

function readDocsContinueProgressMap() {
  try {
    const raw = window.localStorage.getItem(DOCS_CONTINUE_READING_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function isDocsContinueProgressExpired(entry, nowMs = Date.now()) {
  if (!entry || typeof entry !== "object") {
    return true;
  }
  const updatedAt = Number(entry.updated_at_ms || 0);
  if (!Number.isFinite(updatedAt) || updatedAt <= 0) {
    return true;
  }
  return nowMs - updatedAt > DOCS_CONTINUE_READING_TTL_MS;
}

function pruneExpiredDocsContinueProgress() {
  const mapValue = readDocsContinueProgressMap();
  let changed = false;
  const nowMs = Date.now();
  for (const key of Object.keys(mapValue)) {
    if (isDocsContinueProgressExpired(mapValue[key], nowMs)) {
      delete mapValue[key];
      changed = true;
    }
  }
  if (changed) {
    writeDocsContinueProgressMap(mapValue);
  }
}

function writeDocsContinueProgressMap(mapValue) {
  try {
    window.localStorage.setItem(DOCS_CONTINUE_READING_STORAGE_KEY, JSON.stringify(mapValue));
  } catch {
    // Ignore storage failures.
  }
}

function setDocsContinueProgressForPath(path, progress) {
  pruneExpiredDocsContinueProgress();
  const mapValue = readDocsContinueProgressMap();
  mapValue[path] = progress;
  writeDocsContinueProgressMap(mapValue);
}

function getDocsContinueProgressForPath(path) {
  pruneExpiredDocsContinueProgress();
  const mapValue = readDocsContinueProgressMap();
  const item = mapValue[path];
  if (!item || typeof item !== "object") {
    return null;
  }
  if (isDocsContinueProgressExpired(item)) {
    delete mapValue[path];
    writeDocsContinueProgressMap(mapValue);
    return null;
  }
  return item;
}

function removeDocsContinueProgressForPath(path) {
  const mapValue = readDocsContinueProgressMap();
  if (!(path in mapValue)) {
    return;
  }
  delete mapValue[path];
  writeDocsContinueProgressMap(mapValue);
}

function currentContinueAnchorSnapshot() {
  const headings = [
    ...document.querySelectorAll(
      ".docs-page-layout__article h2[id], .docs-page-layout__article h3[id], section.card h2[id], section.card h3[id]",
    ),
  ];
  const activationLine = 130;
  let active = null;
  for (const heading of headings) {
    const top = heading.getBoundingClientRect().top;
    if (top <= activationLine) {
      active = heading;
    }
  }
  if (!active) {
    active = headings[0] || null;
  }
  if (!active || !active.id) {
    return null;
  }
  const label = String(active.textContent || "").trim().replace(/\s+/g, " ");
  return {
    anchor: `#${active.id}`,
    label,
  };
}

function initDocsContinueReadingPrompt() {
  if (!document.getElementById("docs-top-nav")) {
    return;
  }
  const relPath = currentDocsRelPath();

  let saveTimer = null;
  function saveProgress() {
    const root = document.documentElement;
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    if (maxScroll < 260) {
      removeDocsContinueProgressForPath(relPath);
      return;
    }
    const y = Math.max(0, Math.round(window.scrollY || 0));
    if (y < 120) {
      removeDocsContinueProgressForPath(relPath);
      return;
    }
    const snapshot = currentContinueAnchorSnapshot();
    setDocsContinueProgressForPath(relPath, {
      y,
      anchor: snapshot ? snapshot.anchor : "",
      label: snapshot ? snapshot.label : "",
      updated_at_ms: Date.now(),
    });
  }

  function scheduleSaveProgress() {
    if (saveTimer) {
      return;
    }
    saveTimer = window.setTimeout(() => {
      saveTimer = null;
      saveProgress();
    }, 420);
  }

  window.addEventListener("scroll", scheduleSaveProgress, { passive: true });
  window.addEventListener("beforeunload", saveProgress);

  const saved = getDocsContinueProgressForPath(relPath);
  if (!saved) {
    return;
  }
  const savedY = Number(saved.y || 0);
  const currentY = Math.max(0, window.scrollY || 0);
  const distanceToSaved = Math.abs(savedY - currentY);
  // Skip prompt only when user is already near saved location.
  if (savedY < 220 || distanceToSaved < 140) {
    return;
  }

  const label = String(saved.label || "").trim();
  const continueAction = () => {
    if (saved.anchor) {
      window.location.hash = saved.anchor;
      if (savedY > 0) {
        window.setTimeout(() => {
          window.scrollTo({ top: savedY, behavior: "smooth" });
        }, 20);
      }
    } else if (savedY > 0) {
      window.scrollTo({ top: savedY, behavior: "smooth" });
    }
  };
  const startFromTopAction = () => {
    removeDocsContinueProgressForPath(relPath);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  let closePrompt = null;
  if (window.DocsPopups && typeof window.DocsPopups.showContinueReadingToast === "function") {
    const instance = window.DocsPopups.showContinueReadingToast({
      label,
      durationMs: 3000,
      onContinue: continueAction,
      onStartFromTop: startFromTopAction,
    });
    closePrompt = () => {
      if (instance && typeof instance.close === "function") {
        instance.close();
      }
    };
  } else {
    const prompt = document.createElement("aside");
    prompt.className = "docs-continue-reading--toast";
    prompt.setAttribute("aria-label", "Continue reading");
    const title = document.createElement("p");
    title.className = "docs-inpage-toc-toast__title";
    title.textContent = "Continue reading available";
    const text = document.createElement("p");
    text.className = "docs-inpage-toc-toast__text";
    text.textContent = label ? `Continue from § ${label}` : "Continue where you left off";
    const actions = document.createElement("div");
    actions.className = "docs-inpage-toc-toast__actions";
    const continueBtn = document.createElement("button");
    continueBtn.type = "button";
    continueBtn.className = "docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--primary";
    continueBtn.textContent = "Continue";
    const topBtn = document.createElement("button");
    topBtn.type = "button";
    topBtn.className = "docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--ghost";
    topBtn.textContent = "Start from top";
    const progress = document.createElement("div");
    progress.className = "docs-inpage-toc-toast__progress";
    progress.setAttribute("aria-hidden", "true");
    actions.appendChild(continueBtn);
    actions.appendChild(topBtn);
    prompt.appendChild(title);
    prompt.appendChild(text);
    prompt.appendChild(actions);
    prompt.appendChild(progress);
    document.body.appendChild(prompt);
    let autoDismissTimer = window.setTimeout(() => {
      prompt.remove();
    }, 3000);
    closePrompt = () => {
      if (autoDismissTimer) {
        window.clearTimeout(autoDismissTimer);
        autoDismissTimer = null;
      }
      prompt.remove();
    };
    continueBtn.addEventListener("click", () => {
      continueAction();
      closePrompt();
    });
    topBtn.addEventListener("click", () => {
      startFromTopAction();
      closePrompt();
    });
  }

  const dismissOnIntent = () => {
    if ((window.scrollY || 0) > 120) {
      if (typeof closePrompt === "function") {
        closePrompt();
      }
      window.removeEventListener("scroll", dismissOnIntent);
    }
  };
  window.addEventListener("scroll", dismissOnIntent, { passive: true });
}

function handleDocsQuickActionsGlobalKeydown(event) {
  const isTypingTarget = isTypingElement(event.target);
  const key = String(event.key).toLowerCase();
  const code = String(event.code || "");
  const isPrimaryK = (event.metaKey || event.ctrlKey) && (key === "k" || code === "KeyK");
  const isPrimaryShiftK =
    (event.metaKey || event.ctrlKey) && event.shiftKey && (key === "k" || code === "KeyK");
  const isPrimaryShiftP =
    (event.metaKey || event.ctrlKey) && event.shiftKey && (key === "p" || code === "KeyP");
  const isShiftPOnly = !event.metaKey && !event.ctrlKey && !event.altKey && event.shiftKey && (key === "p" || code === "KeyP");
  const isSlash = !event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey && (key === "/" || code === "Slash");
  const isQuickActionHotkey = isPrimaryK || isPrimaryShiftK || isPrimaryShiftP || isShiftPOnly || isSlash;

  if (isTypingTarget && (isSlash || isShiftPOnly)) {
    return;
  }

  if (isQuickActionHotkey && (!docsQuickActionsRuntime || !docsQuickActionsRuntime.panel.isConnected)) {
    try {
      installDocsQuickActionsUi();
    } catch {
      return;
    }
  }

  const rt = docsQuickActionsRuntime;
  if (!rt || !rt.panel.isConnected) {
    return;
  }
  const { panel, openPanel, closePanel } = rt;

  if (isQuickActionHotkey) {
    event.preventDefault();
    if (panel.hidden) {
      openPanel();
    } else {
      closePanel();
    }
    return;
  }
  if (event.key === "Escape" && !panel.hidden) {
    closePanel();
  }
}

function syncDocsPageActionsForViewport() {
  if (desktopDocsPageActionsMq.matches) {
    injectDocsPageActions();
    installDocsQuickActionsUi();
  } else {
    removeDocsPageActionsToolbar();
    destroyDocsQuickActionsUi();
  }
}

// ── Level 3: Interactive premium patterns ─────────────────────────────────────
// Copy-to-clipboard on <pre>, § anchor links on h2/h3, breadcrumbs, sticky
// top-bar with backdrop blur, and smooth section highlight on hash navigation.

function level3WriteToClipboard(text, onSuccess, onError) {
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    navigator.clipboard.writeText(text).then(onSuccess, () =>
      level3ClipboardFallback(text, onSuccess, onError),
    );
  } else {
    level3ClipboardFallback(text, onSuccess, onError);
  }
}

function level3ClipboardFallback(text, onSuccess, onError) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (ok) {
      onSuccess();
    } else {
      onError && onError();
    }
  } catch {
    onError && onError();
  }
}

function level3SectionFlash(el) {
  if (!el) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const target = el.closest(".card, section") || el;
  target.classList.remove("docs-section-flash");
  void target.offsetWidth; // force reflow to restart animation
  target.classList.add("docs-section-flash");
  target.addEventListener(
    "animationend",
    () => target.classList.remove("docs-section-flash"),
    { once: true },
  );
}

function initLevel3CopyButtons() {
  document.querySelectorAll("pre").forEach((pre) => {
    if (pre.querySelector(".docs-copy-btn")) return;
    if (getComputedStyle(pre).position === "static") {
      pre.style.position = "relative";
    }

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "docs-copy-btn";
    btn.setAttribute("aria-label", "Copy code");
    btn.textContent = "Copy";

    btn.addEventListener("click", () => {
      const code = pre.querySelector("code") || pre;
      level3WriteToClipboard(
        code.textContent,
        () => {
          btn.textContent = "✓ Copied";
          btn.classList.add("is-copied");
          clearTimeout(btn._l3t);
          btn._l3t = setTimeout(() => {
            btn.textContent = "Copy";
            btn.classList.remove("is-copied");
          }, 2000);
        },
        () => { },
      );
    });

    pre.appendChild(btn);
  });
}

function initLevel3AnchorLinks() {
  document.querySelectorAll("h2[id], h3[id]").forEach((h) => {
    if (h.querySelector(".docs-anchor")) return;

    const anchor = document.createElement("a");
    anchor.className = "docs-anchor";
    anchor.href = "#" + h.id;
    anchor.setAttribute("aria-label", "Copy link to this section");
    anchor.title = "Copy link";
    anchor.textContent = "§";

    anchor.addEventListener("click", (e) => {
      e.preventDefault();
      const url = window.location.href.split("#")[0] + "#" + h.id;
      level3WriteToClipboard(url, () => { }, () => { });
      if (history.pushState) {
        history.pushState(null, "", "#" + h.id);
      } else {
        window.location.hash = h.id;
      }
      level3SectionFlash(h);
    });

    h.appendChild(anchor);
  });
}

function initLevel3SectionHighlight() {
  function onHashChange() {
    const id = window.location.hash.slice(1);
    if (!id) return;
    const target = document.getElementById(id);
    if (target) level3SectionFlash(target);
  }
  window.addEventListener("hashchange", onHashChange);
  if (window.location.hash) {
    window.setTimeout(onHashChange, 120);
  }
}

/**
 * Re-apply initial hash navigation after docs layout transforms.
 * This keeps direct URL anchors (e.g. file:///.../page.html#overview) stable
 * even when init code wraps/moves content for sticky TOC.
 */
function restoreInitialHashPosition() {
  const rawHash = window.location.hash;
  if (!rawHash || rawHash === "#") {
    return;
  }
  let id = rawHash.slice(1);
  try {
    id = decodeURIComponent(id);
  } catch {
    // Keep raw hash segment if decode fails.
  }
  const target = document.getElementById(id);
  if (!target) {
    return;
  }
  window.requestAnimationFrame(() => {
    target.scrollIntoView({ block: "start", inline: "nearest" });
  });
}

function initLevel3Breadcrumbs() {
  const main = document.querySelector("main.container");
  if (!main || main.querySelector(".docs-breadcrumbs")) return;

  const relPath = currentDocsRelPath();
  if (!relPath || relPath === "index.html") return;

  const segments = relPath.split("/").filter(Boolean);
  if (segments.length === 0) return;

  const fromDir = segments.length > 1 ? segments.slice(0, -1).join("/") : "";

  const LABELS = {
    adr: "ADR",
    developer: "Developer",
    howto: "How-to",
    runbooks: "Runbooks",
    qa: "QA",
    rfc: "RFC",
    internal: "Internal",
    analysis: "Analysis",
    api: "API",
    front: "Frontend",
    manager: "Manager",
    portal: "Portal",
    audit: "Audit",
    openapi: "API Explorer",
    pdoc: "Python Docs",
    backlog: "Backlog",
    "error-log": "Error Log",
    user: "User",
    conspectus: "Conspectus",
    screens: "Screens",
  };

  function segLabel(seg) {
    return LABELS[seg] || seg.charAt(0).toUpperCase() + seg.slice(1).replace(/-/g, " ");
  }

  const crumbs = [];
  crumbs.push({ label: "Docs", href: relHref(fromDir, "index.html") });

  const lastName = segments[segments.length - 1];
  const isReadme = lastName === "README.html";
  const dirSegs = segments.slice(0, -1); // everything before the filename

  dirSegs.forEach((seg, i) => {
    const isCurrent = isReadme && i === dirSegs.length - 1;
    const segPath = segments.slice(0, i + 1).join("/") + "/README.html";
    crumbs.push({
      label: segLabel(seg),
      href: isCurrent ? null : relHref(fromDir, segPath),
      current: isCurrent,
    });
  });

  if (!isReadme) {
    const h1 = main.querySelector("h1");
    let label;
    if (h1) {
      label = h1.textContent.trim();
    } else {
      const base = lastName.replace(/\.html$/, "").replace(/^\d{4}-/, "").replace(/-/g, " ");
      label = base.charAt(0).toUpperCase() + base.slice(1);
    }
    crumbs.push({ label, href: null, current: true });
  }

  if (crumbs.length <= 1) return;

  const nav = document.createElement("nav");
  nav.className = "docs-breadcrumbs";
  nav.setAttribute("aria-label", "Breadcrumb");

  const ol = document.createElement("ol");
  ol.className = "docs-breadcrumbs__list";

  crumbs.forEach((crumb) => {
    const li = document.createElement("li");
    li.className = "docs-breadcrumbs__item";

    if (crumb.href) {
      const a = document.createElement("a");
      a.className = "docs-breadcrumbs__link";
      a.href = crumb.href;
      a.textContent = crumb.label;
      li.appendChild(a);
    } else {
      const span = document.createElement("span");
      span.className = "docs-breadcrumbs__current";
      if (crumb.current) span.setAttribute("aria-current", "page");
      span.textContent = crumb.label;
      li.appendChild(span);
    }

    ol.appendChild(li);
  });

  nav.appendChild(ol);

  const h1 = main.querySelector("h1");
  if (h1) {
    main.insertBefore(nav, h1);
  } else {
    main.insertBefore(nav, main.firstChild);
  }
}

function initLevel3StickyTopBar() {
  const wrapper = document.getElementById("docs-top-nav");
  if (!wrapper) return;

  const topNav = wrapper.querySelector(".top-nav");
  if (!topNav || typeof IntersectionObserver === "undefined") return;

  const sentinel = document.createElement("div");
  sentinel.className = "docs-sticky-sentinel";
  sentinel.setAttribute("aria-hidden", "true");
  wrapper.parentNode.insertBefore(sentinel, wrapper);

  new IntersectionObserver(
    ([entry]) => topNav.classList.toggle("is-scrolled", !entry.isIntersecting),
    { threshold: 0 },
  ).observe(sentinel);
}

document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.add("docs-density-ultra-compact");
  injectDocsPopupsRuntime();
  ensureInternalLayoutForInternalSections();
  injectDocsSkipToContentLink();
  document.addEventListener(
    "keydown",
    (event) => {
      if (isReadingModeHotkeyEvent(event) && !isTypingElement(event.target)) {
        event.preventDefault();
        event.stopPropagation();
        toggleDocsReadingMode("global_hotkey");
      }
    },
    true,
  );
  document.addEventListener("keydown", handleDocsQuickActionsGlobalKeydown);
  applyDocsReadingMode(isDocsReadingModeEnabled(), "initial_load");
  injectDocsLifecycleHelp();
  renderTopNav();
  applyDocsThemeFromMode(getEffectiveDocsThemeMode());
  syncDocsThemeToggleLabel();
  const main = document.querySelector("main.container");
  if (main) {
    renderLifecycleStatusBlocks(main);
  }
  injectAuditScoreLegends();
  injectDocsFeedbackCard();
  try {
    syncDocsPageActionsForViewport();
  } catch {
    // Keep the rest of docs chrome available even if palette init fails.
  }
  if (typeof desktopDocsPageActionsMq.addEventListener === "function") {
    desktopDocsPageActionsMq.addEventListener("change", syncDocsPageActionsForViewport);
  } else if (typeof desktopDocsPageActionsMq.addListener === "function") {
    desktopDocsPageActionsMq.addListener(syncDocsPageActionsForViewport);
  }
  initAutoInPageToc();
  restoreInitialHashPosition();
  syncInternalThemeTogglePlacement();
  window.setTimeout(syncInternalThemeTogglePlacement, 0);
  initInPageTocScrollSpy();
  initBackToTopButton();
  initDocsReadingProgressBar();
  initDocsFooterAtmosphereScroll();
  initDocsSiteFooter();
  initFabFooterAwareness();
  initDocsContinueReadingPrompt();
  try {
    injectDocsHotkeyHint();
  } catch {
    // Non-critical helper; ignore failures.
  }
  try {
    normalizeDocsPageHistory();
  } catch {
    // Keep docs usable if page-history normalization fails.
  }
  // Level 3 — interactive premium patterns
  initLevel3CopyButtons();
  initLevel3AnchorLinks();
  initLevel3Breadcrumbs();
  initLevel3StickyTopBar();
  initLevel3SectionHighlight();
});
