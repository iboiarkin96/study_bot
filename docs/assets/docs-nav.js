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
    return "developer/README.html";
  }
  if (relPath.startsWith("backlog/")) {
    return "backlog/README.html";
  }
  if (relPath.startsWith("runbooks/")) {
    return "runbooks/README.html";
  }
  if (relPath.startsWith("api/")) {
    return "api/index.html";
  }
  if (relPath === "openapi-explorer.html") {
    return "openapi-explorer.html";
  }
  if (relPath === "engineering-practices.html") {
    return "engineering-practices.html";
  }
  return "system-analysis.html";
}

function renderTopNav() {
  const host = document.getElementById("docs-top-nav");
  if (!host) {
    return;
  }

  const relPath = currentDocsRelPath();
  const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
  const active = activeTarget(relPath);
  const items = [
    { label: "Home", target: "index.html" },
    { label: "System Analysis", target: "system-analysis.html" },
    { label: "Engineering Practices", target: "engineering-practices.html" },
    { label: "Developer Docs", target: "developer/README.html" },
    { label: "Backlog", target: "backlog/README.html" },
    { label: "ADR", target: "adr/README.html" },
    { label: "Runbooks", target: "runbooks/README.html" },
    { label: "API (Python)", target: "api/index.html" },
    { label: "OpenAPI (test)", target: "openapi-explorer.html" },
  ];

  const nav = document.createElement("nav");
  nav.className = "top-nav";
  nav.setAttribute("aria-label", "Documentation navigation");

  for (const item of items) {
    const link = document.createElement("a");
    link.textContent = item.label;
    link.href = relHref(fromDir, item.target);
    if (item.target === active) {
      link.className = "is-active";
      link.setAttribute("aria-current", "page");
    }
    nav.appendChild(link);
  }

  host.replaceWith(nav);
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

document.addEventListener("DOMContentLoaded", () => {
  renderTopNav();
  const main = document.querySelector("main.container");
  if (main) {
    renderAdr(main);
  }
});
