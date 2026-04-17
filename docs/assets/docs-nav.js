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
  const ghPages = path.match(/^\/[^/]+\/(.*)$/);
  if (ghPages) {
    const rel = ghPages[1];
    return rel && rel.length > 0 ? rel : "index.html";
  }
  const parts = path.split("/").filter(Boolean);
  const last = parts[parts.length - 1];
  if (!last) {
    return "index.html";
  }
  return last;
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
    { label: "How-to guides", target: "howto/README.html" },
    { label: "ADR", target: "adr/README.html" },
    { label: "Runbooks", target: "runbooks/README.html" },
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

/**
 * Wrap content after `#docs-top-nav` in a grid with a sticky “On this page” TOC built from `h2`/`h3` (not `p.lead`).
 * Add a mount as the last child of `<main>`: `<div class="docs-inpage-toc-mount" data-inpage-toc="auto"></div>`.
 * Very long outlines scroll inside the sidebar (see `.docs-inpage-toc nav` in docs.css).
 */
function initAutoInPageToc() {
  const mount = document.querySelector('.docs-inpage-toc-mount[data-inpage-toc="auto"]');
  if (!mount) {
    return;
  }
  const main = mount.closest("main");
  if (!main) {
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
  initAutoInPageToc();
  initInPageTocScrollSpy();
});
