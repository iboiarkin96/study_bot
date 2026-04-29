"use strict";

/**
 * Left navigation for multi-page docs under docs/internal/**.
 * Single source of truth: INTERNAL_SIDEBAR_NAV below — update when adding pages.
 *
 * Operation entries use labels shaped as `METHOD /path/...` (HTTP-first), not Python operationId names,
 * so navigation matches how integrators think about the API.
 *
 * HTML files under `internal/api/user/operations/` are named after the HTTP method and path template, e.g.
 * `post-api-v1-user.html`, `get-api-v1-user-system_uuid-system_user_id.html` — not after `operationId`.
 *
 * Sidebar labels for operations are short (action + method), not full paths — full URI belongs on the method page hero.
 *
 * Optional on a node with `children`: `expand: "after-api-hub"` — the `<details>` is open only
 * when the URL is the API hub page or under `internal/api/user/`, so the User subtree stays
 * collapsed until the reader opens API hub (or jumps to a User page). Other groups use
 * “active descendant” to decide `open`.
 */
(function () {
  const INTERNAL_SIDEBAR_COLLAPSED_STORAGE_KEY = "docs.internal.sidebar.collapsed";
  const INTERNAL_SIDEBAR_DRAWER_OPEN_STORAGE_KEY = "docs.internal.sidebar.drawer.open";
  const PHONE_MAX_WIDTH = 760;
  const DRAWER_MAX_WIDTH = 1024;
  const DRAWER_TOP_NAV_SECTIONS = [
    {
      title: "Project",
      kind: "internal",
      links: [
        { label: "Home", path: "index.html" },
        { label: "Internal docs", path: "internal/README.html" },
        { label: "QA checklists", path: "qa/README.html" },
        { label: "Assessments", path: "audit/README.html" },
        { label: "Backlog", path: "backlog/README.html" },
      ],
    },
    {
      title: "Code",
      kind: "public",
      links: [
        { label: "OpenAPI / Swagger UI", path: "openapi/index.html" },
        { label: "Python API (pdoc)", path: "pdoc/index.html" },
      ],
    },
  ];

  function readSidebarCollapsedPreference() {
    try {
      return window.localStorage.getItem(INTERNAL_SIDEBAR_COLLAPSED_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  }

  function persistSidebarCollapsedPreference(isCollapsed) {
    try {
      window.localStorage.setItem(INTERNAL_SIDEBAR_COLLAPSED_STORAGE_KEY, isCollapsed ? "1" : "0");
    } catch {
      // Ignore storage failures and keep interaction working.
    }
  }

  function readDrawerOpenPreference() {
    try {
      return window.sessionStorage.getItem(INTERNAL_SIDEBAR_DRAWER_OPEN_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  }

  function persistDrawerOpenPreference(isOpen) {
    try {
      window.sessionStorage.setItem(INTERNAL_SIDEBAR_DRAWER_OPEN_STORAGE_KEY, isOpen ? "1" : "0");
    } catch {
      // Ignore storage failures and keep interaction working.
    }
  }

  function ensureSidebarToggle(sidebar, sidebarHost, shell) {
    if (!sidebar || !sidebarHost || !shell) {
      return;
    }
    const title = sidebar.querySelector(".internal-layout__sidebar-title");
    if (title) {
      title.hidden = true;
    }

    let toggle = sidebar.querySelector("[data-internal-sidebar-toggle]");
    if (!toggle) {
      toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "internal-layout__sidebar-toggle";
      toggle.setAttribute("data-internal-sidebar-toggle", "1");
      if (title) {
        title.insertAdjacentElement("afterend", toggle);
      } else {
        sidebar.insertBefore(toggle, sidebarHost);
      }
    }

    toggle.setAttribute("aria-controls", sidebarHost.id);

    function applyCollapsedState(isCollapsed) {
      shell.classList.toggle("is-sidebar-collapsed", isCollapsed);
      sidebarHost.hidden = isCollapsed;
      toggle.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      toggle.textContent = isCollapsed ? "SHOW\nMENU" : "HIDE\nMENU";
    }

    let isCollapsed = readSidebarCollapsedPreference();
    applyCollapsedState(isCollapsed);
    shell.__internalSidebarApplyCollapsedState = applyCollapsedState;
    shell.__internalSidebarToggle = toggle;
    shell.__internalSidebarHost = sidebarHost;
    toggle.addEventListener("click", () => {
      isCollapsed = !isCollapsed;
      applyCollapsedState(isCollapsed);
      persistSidebarCollapsedPreference(isCollapsed);
    });
  }

  function buildDrawerTopSections(fromDir, currentPath) {
    const wrap = document.createElement("div");
    wrap.className = "internal-layout__drawer-sections";
    for (const section of DRAWER_TOP_NAV_SECTIONS) {
      const block = document.createElement("section");
      block.className = `internal-layout__drawer-section internal-layout__drawer-section--${section.kind}`;

      const title = document.createElement("p");
      title.className = "internal-layout__drawer-section-title";
      title.textContent = section.title;
      block.appendChild(title);

      const links = document.createElement("div");
      links.className = "internal-layout__drawer-section-links";
      for (const item of section.links) {
        const a = document.createElement("a");
        a.href = relHref(fromDir, item.path);
        a.textContent = item.label;
        if (pathMatchesSection(currentPath, item.path)) {
          a.classList.add("is-active");
          a.setAttribute("aria-current", "page");
        }
        links.appendChild(a);
      }
      block.appendChild(links);
      wrap.appendChild(block);
    }
    return wrap;
  }

  function ensureDrawerInteractions(sidebar, shell, fromDir, currentPath) {
    if (!sidebar || !shell) {
      return;
    }

    const drawerMedia = window.matchMedia(`(max-width: ${DRAWER_MAX_WIDTH}px)`);
    const phoneMedia = window.matchMedia(`(max-width: ${PHONE_MAX_WIDTH}px)`);
    let isOpen = false;
    const initialOpen = readDrawerOpenPreference();
    let lastLauncherFocus = null;

    let drawerRoot = document.getElementById("internal-docs-drawer");
    if (!drawerRoot) {
      drawerRoot = document.createElement("div");
      drawerRoot.id = "internal-docs-drawer";
      drawerRoot.className = "internal-layout__drawer";
      drawerRoot.setAttribute("role", "dialog");
      drawerRoot.setAttribute("aria-modal", "true");
      drawerRoot.setAttribute("aria-labelledby", "internal-docs-drawer-title");

      const backdrop = document.createElement("button");
      backdrop.type = "button";
      backdrop.className = "internal-layout__drawer-backdrop";
      backdrop.setAttribute("aria-label", "Close internal documentation menu");

      const panel = document.createElement("div");
      panel.className = "internal-layout__drawer-panel";

      const header = document.createElement("div");
      header.className = "internal-layout__drawer-header";

      const title = document.createElement("p");
      title.id = "internal-docs-drawer-title";
      title.className = "internal-layout__drawer-title";
      title.textContent = "Internal docs";

      const closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "internal-layout__drawer-close";
      closeBtn.textContent = "Close";

      const body = document.createElement("div");
      body.className = "internal-layout__drawer-body";

      header.appendChild(title);
      header.appendChild(closeBtn);
      panel.appendChild(header);
      panel.appendChild(body);
      drawerRoot.appendChild(backdrop);
      drawerRoot.appendChild(panel);
      document.body.appendChild(drawerRoot);

      backdrop.addEventListener("click", () => {
        closeDrawer(true);
      });
      closeBtn.addEventListener("click", () => {
        closeDrawer(true);
      });
    }

    const drawerBody = drawerRoot.querySelector(".internal-layout__drawer-body");

    if (!sidebar.id) {
      sidebar.id = "internal-sidebar-drawer";
    }

    function inDrawerMode() {
      return drawerMedia.matches;
    }

    function syncDrawerNavFromSource() {
      const sourceNav = sidebar.querySelector("nav");
      if (!sourceNav || !drawerBody) {
        return;
      }
      const navClone = sourceNav.cloneNode(true);
      drawerBody.replaceChildren(buildDrawerTopSections(fromDir, currentPath), navClone);
    }

    function applyDrawerState(nextOpen, shouldPersist) {
      const active = inDrawerMode();
      const open = active && nextOpen;
      isOpen = open;

      shell.classList.toggle("is-drawer-mode", active);
      document.body.classList.toggle("internal-sidebar-drawer-open", open);

      const applyCollapsedState = shell.__internalSidebarApplyCollapsedState;
      const collapseToggle = shell.__internalSidebarToggle;
      if (active) {
        if (typeof applyCollapsedState === "function") {
          applyCollapsedState(false);
        }
        if (collapseToggle) {
          collapseToggle.hidden = true;
        }
      } else {
        if (typeof applyCollapsedState === "function") {
          applyCollapsedState(readSidebarCollapsedPreference());
        }
        if (collapseToggle) {
          collapseToggle.hidden = false;
        }
      }

      if (open) {
        syncDrawerNavFromSource();
        drawerRoot.removeAttribute("hidden");
        drawerRoot.classList.add("is-open");
      } else {
        drawerRoot.classList.remove("is-open");
        drawerRoot.setAttribute("hidden", "");
      }

      if (shouldPersist && active) {
        if (phoneMedia.matches) {
          persistDrawerOpenPreference(false);
        } else {
          persistDrawerOpenPreference(open);
        }
      }

      document.dispatchEvent(
        new CustomEvent("internal-sidebar:drawer-state", {
          detail: {
            open,
            drawerMode: active,
            drawerId: drawerRoot.id,
          },
        }),
      );
    }

    function openDrawer(shouldPersist) {
      applyDrawerState(true, shouldPersist);
      const firstLink = drawerBody ? drawerBody.querySelector("a, button, summary") : null;
      if (firstLink && typeof firstLink.focus === "function") {
        firstLink.focus();
      }
    }

    function closeDrawer(shouldPersist) {
      applyDrawerState(false, shouldPersist);
      if (lastLauncherFocus && typeof lastLauncherFocus.focus === "function") {
        lastLauncherFocus.focus();
      }
    }

    function toggleDrawer() {
      if (!inDrawerMode()) {
        return;
      }
      if (isOpen) {
        closeDrawer(true);
      } else {
        openDrawer(true);
      }
    }

    function syncForViewport() {
      if (!inDrawerMode()) {
        closeDrawer(false);
        shell.classList.remove("is-drawer-mode");
        return;
      }
      if (phoneMedia.matches) {
        closeDrawer(false);
        return;
      }
      openDrawer(false);
      if (!initialOpen) {
        closeDrawer(false);
      }
    }

    if (drawerBody && !drawerBody.__internalDrawerNavBound) {
      drawerBody.__internalDrawerNavBound = true;
      drawerBody.addEventListener("click", (event) => {
        const target = event.target;
        const link = target && target.closest ? target.closest("a[href]") : null;
        if (!link || !inDrawerMode() || !isOpen) {
          return;
        }
        if (event.defaultPrevented) {
          return;
        }
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
        const href = link.getAttribute("href");
        if (!href || href.startsWith("#")) {
          return;
        }
        event.preventDefault();
        window.location.assign(link.href);
      });
    }

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isOpen) {
        closeDrawer(true);
      }
    });

    document.addEventListener("internal-sidebar:toggle-drawer", () => {
      lastLauncherFocus = document.activeElement;
      toggleDrawer();
    });

    drawerMedia.addEventListener("change", syncForViewport);
    phoneMedia.addEventListener("change", syncForViewport);
    syncForViewport();
  }

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
    // First "/docs/" is the repo docs root; lastIndexOf fails for .../docs/audit/docs/...
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
      "api",
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

  function normalizePath(p) {
    return normalizeParts(p.split("/")).join("/");
  }

  function pathIsActive(current, target) {
    const a = normalizePath(current);
    const b = normalizePath(target);
    return a === b;
  }

  function pathMatchesSection(currentPath, sectionPath) {
    if (pathIsActive(currentPath, sectionPath)) {
      return true;
    }
    if (sectionPath === "index.html") {
      return currentPath === "index.html";
    }
    if (sectionPath === "internal/README.html") {
      return currentPath.startsWith("internal/");
    }
    if (sectionPath === "audit/README.html") {
      return currentPath.startsWith("audit/");
    }
    if (sectionPath === "backlog/README.html") {
      return currentPath.startsWith("backlog/");
    }
    if (sectionPath === "qa/README.html") {
      return currentPath.startsWith("qa/");
    }
    if (sectionPath === "openapi/index.html") {
      return currentPath.startsWith("openapi/");
    }
    if (sectionPath === "pdoc/index.html") {
      return currentPath.startsWith("pdoc/");
    }
    return false;
  }

  function navHasActiveChild(node, currentPath) {
    if (node.path && pathIsActive(currentPath, node.path)) {
      return true;
    }
    if (!node.children) {
      return false;
    }
    for (let i = 0; i < node.children.length; i += 1) {
      if (navHasActiveChild(node.children[i], currentPath)) {
        return true;
      }
    }
    return false;
  }

  /** When to set `details.open` for a group (see file header). */
  function shouldOpenGroup(node, currentPath) {
    if (node.expand === "after-api-hub") {
      return (
        currentPath === "internal/api/README.html" ||
        currentPath.startsWith("internal/api/user/") ||
        currentPath.startsWith("internal/api/conspectus/")
      );
    }
    return navHasActiveChild(node, currentPath);
  }

  /**
   * Paths are relative to the docs/ root (e.g. internal/README.html).
   */
  const INTERNAL_SIDEBAR_NAV = [
    { label: "⌂ ETR Study API home", path: "index.html" },
    { label: "◉ Internal docs hub", path: "internal/README.html" },
    { label: "🧭 Methodology", path: "internal/analysis/methodology.html" },
    { label: "🏗 System design", path: "internal/analysis/system-design.html" },
    { label: "🌐 OpenAPI / Swagger UI", path: "openapi/index.html" },

    {
      separator: true,
    },

    {
      label: "ADRs",
      children: [
        { label: "Hub — ADR index", path: "adr/README.html" },
        {
          label: "Shared (cross-cutting)", children: [
            { label: "ADR template", path: "adr/0000-template.html" },
          ]
        },
        {
          label: "Process: how we record decisions",
          children: [
            { label: "ADR 0018 — lifecycle, ratification, badges", path: "adr/0018-adr-lifecycle-ratification-and-badges.html" },
          ],
        },
        {
          label: "Documentation and diagrams",
          children: [
            { label: "ADR 0027 — client-side docs search", path: "adr/0027-client-side-docs-search-index-and-ranking.html" },
            { label: "ADR 0025 — external vs internal API documentation", path: "adr/0025-external-and-internal-api-documentation.html" },
            { label: "ADR 0026 — internal service documentation (source of truth)", path: "adr/0026-internal-service-documentation-as-source-of-truth.html" },
            { label: "ADR 0024 — architecture and quality assessment documents", path: "adr/0024-architecture-and-quality-assessment-documents.html" },
            { label: "ADR 0001 — docs as code", path: "adr/0001-docs-as-code.html" },
            { label: "ADR 0013 — changelog and release notes", path: "adr/0013-changelog-and-release-notes.html" },
            { label: "ADR 0016 — Python docstrings and pdoc", path: "adr/0016-python-docstrings-google-style-and-pdoc.html" },
            { label: "ADR 0020 — C4, PlantUML, diagram conventions", path: "adr/0020-c4-plantuml-diagram-style-and-conventions.html" },
          ],
        },
        {
          label: "API contract and integrators",
          children: [
            { label: "ADR 0007 — OpenAPI governance and usability", path: "adr/0007-openapi-governance-and-usability-standard.html" },
            { label: "ADR 0003 — error contract governance", path: "adr/0003-error-contract-governance.html" },
            { label: "ADR 0004 — API versioning policy", path: "adr/0004-api-versioning-policy.html" },
            { label: "ADR 0006 — idempotency for write operations", path: "adr/0006-idempotency-write-operations.html" },
            { label: "ADR 0022 — embedded Swagger UI (superseded)", path: "adr/0022-embedded-swagger-ui-openapi-sandbox.html" },
          ],
        },
        {
          label: "Security, config, and supply chain",
          children: [
            { label: "ADR 0005 — API security defaults", path: "adr/0005-api-security-defaults.html" },
            { label: "ADR 0010 — env profiles and config governance", path: "adr/0010-env-profiles-and-config-governance.html" },
            { label: "ADR 0019 — pip-audit and dependency pinning", path: "adr/0019-python-dependency-security-pip-audit-and-pinning-policy.html" },
          ],
        },
        {
          label: "Testing and code health",
          children: [
            { label: "ADR 0002 — testing policy", path: "adr/0002-testing-policy.html" },
            { label: "ADR 0012 — testing strategy and load testing", path: "adr/0012-testing-strategy-and-load-testing.html" },
            { label: "ADR 0014 — dead code analysis and repository hygiene", path: "adr/0014-dead-code-analysis-and-repository-hygiene.html" },
          ],
        },
        {
          label: "Running, observing, and SLOs",
          children: [
            { label: "ADR 0009 — health, readiness, and observability", path: "adr/0009-health-readiness-and-observability.html" },
            { label: "ADR 0011 — SLO, SLA, and error budget", path: "adr/0011-slo-sla-error-budget.html" },
            { label: "ADR 0023 — structured logging and local Elasticsearch", path: "adr/0023-structured-logging-and-local-elasticsearch.html" },
          ],
        },
        {
          label: "Day-to-day workflow and Git",
          children: [
            { label: "ADR 0008 — Make command taxonomy and workflow entrypoints", path: "adr/0008-make-command-taxonomy-and-workflow-entrypoints.html" },
            { label: "ADR 0017 — branch naming and repository workflow", path: "adr/0017-branch-naming-and-repository-workflow.html" },
          ],
        },
        {
          label: "Containers and delivery",
          children: [
            { label: "ADR 0015 — container image", path: "adr/0015-container-image.html" },
            { label: "ADR 0021 — continuous delivery (GitHub Actions and GHCR)", path: "adr/0021-continuous-delivery-github-actions-and-ghcr.html" },
          ],
        },
      ]
    },

    {
      label: "RFCs",
      children: [
        { label: "Hub — RFC index", path: "rfc/README.html" },
        {
          label: "Shared (cross-cutting)", children: [
            { label: "RFC template", path: "rfc/0000-template.html" },
          ]
        },
        {
          label: "Docs search program",
          children: [
            { label: "RFC 0001 — docs search implementation", path: "rfc/0001-docs-search-implementation.html" },
            { label: "RFC 0002 — docs search KPI policy and SLO", path: "rfc/0002-docs-search-kpi-policy-and-slo.html" },
          ],
        },
      ],
    },


    {
      label: "How-to guides",
      children: [
        { label: "Hub — how-to index", path: "howto/README.html" },
        {
          label: "Onboarding and implementation",
          children: [
            { label: "Onboarding from zero to endpoint and docs", path: "howto/0001-onboarding-from-zero-to-endpoint-docs.html" },
            { label: "How to add POST /api/v1/contract", path: "howto/0004-how-to-add-post-contract.html" },
          ],
        },
        {
          label: "Documentation operations",
          children: [
            { label: "Internal service docs layout and how to add pages", path: "howto/0002-internal-service-docs-layout.html" },
            { label: "How to change docs frontend safely", path: "howto/0005-how-to-change-docs-frontend-safely.html" },
          ],
        },
        {
          label: "Workflow and commands",
          children: [{ label: "Make commands inventory", path: "howto/0003-make-commands-inventory.html" }],
        },
      ],
    },

    {
      label: "Runbooks",
      children: [
        { label: "Hub — runbooks index", path: "runbooks/README.html" },
        {
          label: "Shared (cross-cutting)", children: [
            { label: "Runbook template", path: "runbooks/0000-template.html" },
          ]
        },
        {
          label: "CI and local quality failures",
          children: [
            { label: "Tests failing", path: "runbooks/0001-tests-failing.html" },
            { label: "Pre-commit failing", path: "runbooks/0004-pre-commit-failing.html" },
            { label: "Quality check failing", path: "runbooks/0005-quality-check-failing.html" },
            { label: "OpenAPI contract test failing", path: "runbooks/0007-openapi-contract-test-failing.html" },
          ],
        },
        {
          label: "Data and migration failures",
          children: [{ label: "Migrations failing", path: "runbooks/0002-migrations-failing.html" }],
        },
        {
          label: "Security and API guardrails",
          children: [{ label: "API security failing", path: "runbooks/0006-api-security-failing.html" }],
        },
        {
          label: "Observability and reliability incidents",
          children: [
            { label: "Logging failing", path: "runbooks/0003-logging-failing.html" },
            { label: "Observability scrape failing", path: "runbooks/0008-observability-scrape-failing.html" },
            { label: "Error budget exhaustion", path: "runbooks/0009-error-budget-exhaustion.html" },
          ],
        },
        {
          label: "Docs frontend incidents",
          children: [{ label: "In-page TOC missing", path: "runbooks/0010-in-page-toc-missing.html" }],
        },
      ],
    },



    {
      label: "Audit",
      children: [
        { label: "Hub — assessments index", path: "audit/README.html" },
        {
          label: "Shared (cross-cutting)", children: [
            { label: "Assessment template", path: "audit/AUDIT_TEMPLATE.html" },
          ]
        },
        { label: "Assessment template", path: "audit/AUDIT_TEMPLATE.html" },
        {
          label: "DX",
          children: [
            { label: "DX 2026-04-14", path: "audit/docs/2026-04-14-documentation-experience-assessment.html" },
            { label: "DX 2026-04-18", path: "audit/docs/2026-04-18-documentation-experience-assessment.html" },
            { label: "UI/UX DX 2026-04-23", path: "audit/docs/2026-04-23-ui-ux-assessment.html" },
            { label: "UI/UX DX 2026-04-24", path: "audit/docs/2026-04-24-ui-ux-assessment.html" },
          ],
        },
        {
          label: "REST API",
          children: [
            { label: "REST API 2026-04-14", path: "audit/api/2026-04-14-rest-api-assessment.html" },
          ],
        },
      ],
    },

    {
      separator: true,
    },

    {
      label: "Managers portal",

      children: [
        { label: "Hub — managers index", path: "internal/manager/README.html" },
        { label: "⭐ Backlog", path: "backlog/README.html" },
        { label: "SDLC RACI matrix", path: "internal/manager/sdlc-raci-matrix.html" },
      ],
    },

    {
      label: "Developers portal",
      children: [
        { label: "Python API (pdoc)", path: "pdoc/index.html" },
        { label: "Hub — developer index", path: "developer/README.html" },
        {
          label: "Core architecture and contracts",
          children: [
            { label: "Requirements guide", path: "developer/0001-requirements.html" },
            { label: "Schemas and contracts", path: "developer/0002-schemas-and-contracts.html" },
            { label: "Business logic guide", path: "developer/0003-business-logic.html" },
            { label: "Error matrix by status", path: "developer/0005-error-matrix-by-status.html" },
          ],
        },
        {
          label: "Delivery workflow and operations",
          children: [
            { label: "Make commands and workflows", path: "developer/0010-make-commands-and-workflows.html" },
            { label: "Local development", path: "developer/0007-local-development.html" },
            { label: "Docker image and container", path: "developer/0009-docker-image-and-container.html" },
            { label: "API load testing", path: "developer/0006-api-load-testing.html" },
            { label: "Documentation pipeline", path: "developer/0008-docs-pipeline.html" },
          ],
        },
        {
          label: "How-to and onboarding",
          children: [
            { label: "How to add POST contract", path: "howto/0004-how-to-add-post-contract.html" },
            { label: "Onboarding from zero to endpoint and docs", path: "howto/0001-onboarding-from-zero-to-endpoint-docs.html" },
            { label: "Make commands inventory", path: "howto/0003-make-commands-inventory.html" },
          ],
        },
      ],
    },

    {
      label: "QA portal",
      children: [
        { label: "Hub — QA portal index", path: "qa/README.html" },
        {
          label: "QA checklists",
          children: [
            {
              label: "Documentation pages visual checklist",
              path: "qa/0001-documentation-pages-visual-checklist.html",
            },
          ],
        },
      ],
    },

    {
      separator: true,
    },

    {
      label: "API endpoints documentation",
      children: [
        { label: "Hub — internal HTTP API", path: "internal/api/README.html" },

        {
          label: "Shared (cross-cutting)",
          children: [
            { label: "Specification template", path: "internal/api/_shared/spec-template.html" },
            { label: "Definition of Done", path: "internal/api/_shared/spec-definition-of-done.html" },
            { label: "Idempotency", path: "internal/api/_shared/idempotency.html" },
            { label: "Error envelope", path: "internal/api/_shared/error-envelope.html" },
            { label: "Error catalog", path: "internal/api/_shared/error-catalog.html" },
            { label: "Authentication & authorization", path: "internal/api/_shared/auth.html" },
            { label: "Pagination", path: "internal/api/_shared/pagination.html" },
            { label: "Versioning", path: "internal/api/_shared/versioning.html" },
            { label: "Observability conventions", path: "internal/api/_shared/observability-conventions.html" },
            { label: "Field conventions", path: "internal/api/_shared/field-conventions.html" },
            { label: "OpenAPI authoring guide", path: "internal/api/_shared/openapi-authoring-guide.html" },
            { label: "Error matrix (auto-generated)", path: "internal/api/errors.html" },
          ],
        },
        {
          label: "User",
          expand: "after-api-hub",
          children: [
            { label: "Hub — business, contract & technical spec", path: "internal/api/user/index.html" },
            { label: "GET /user/", path: "internal/api/user/operations/get-api-v1-user-system_uuid-system_user_id.html" },
            { label: "POST /user", path: "internal/api/user/operations/post-api-v1-user.html" },
            { label: "PUT /user/", path: "internal/api/user/operations/put-api-v1-user-system_uuid-system_user_id.html" },
            { label: "PATCH /user/", path: "internal/api/user/operations/patch-api-v1-user-system_uuid-system_user_id.html" },
          ],
        },
        {
          label: "Conspectus",
          expand: "after-api-hub",
          children: [
            {
              labelHtml:
                'Hub — business, contract & technical spec',
              path: "internal/api/conspectus/index.html",
            },
            { label: "GET /conspectuses/due/", path: "internal/api/conspectus/operations/get-api-v1-conspectuses-due.html" },
            { label: "GET /schedule/summary/", path: "internal/api/conspectus/operations/get-api-v1-schedule-summary.html" },
            { label: "POST …/actions/review", path: "internal/api/conspectus/operations/post-api-v1-conspectuses-conspectus_uuid-actions-review.html" },
            { label: "POST /conspectuses", path: "internal/api/conspectus/operations/post-api-v1-conspectuses.html" },
            { label: "PATCH /conspectuses/{id}", path: "internal/api/conspectus/operations/patch-api-v1-conspectuses-conspectus_uuid.html" },
          ],
        },
        {
          label: "Error log",
          expand: "after-api-hub",
          children: [
            { label: "Hub — business, contract & technical spec", path: "internal/api/error-log/index.html" },
            { label: "GET /errors/", path: "internal/api/error-log/operations/get-api-v1-errors.html" },
            { label: "POST /errors", path: "internal/api/error-log/operations/post-api-v1-errors.html" },
          ],
        },
      ],
    },

    {
      label: "Docs frontend documentation",
      children: [
        {
          label: "Foundations",
          children: [
            { label: "Style guide", path: "internal/front/documentation-style-guide.html" },
            { label: "Maintenance process", path: "internal/front/documentation-process.html" },
            { label: "Frontend glossary", path: "internal/front/docs-frontend-glossary.html" },
            { label: "Quick entry by role", path: "internal/front/docs-frontend-fast-entry-by-role.html" },
          ],
        },
        {
          label: "Architecture",
          children: [
            { label: "Architecture map", path: "internal/front/docs-frontend-architecture-map.html" },
          ],
        },
        {
          label: "Screens",
          children: [
            { label: "Screen spec template", path: "internal/front/screens/docs-screen-template.html" },
            { label: "Engineering hub home", path: "internal/front/screens/docs-screen-home-landing.html" },
            { label: "Backlog cockpit", path: "internal/front/screens/docs-screen-backlog-cockpit.html" },
          ],
        },
        {
          label: "Components",
          children: [
            { label: "UI kit", path: "internal/front/docs-frontend-ui-kit.html" },
            { label: "Tooltips and inline hints", path: "internal/front/docs-frontend-tooltips.html" },
            { label: "Popup and overlay system", path: "internal/front/docs-frontend-popups-and-overlays.html" },
            { label: "Diagrams and lightbox", path: "internal/front/docs-frontend-diagrams-and-lightbox.html" },
            { label: "Resume reading and back-to-top", path: "internal/front/docs-frontend-resume-and-back-to-top.html" },
            { label: "Hotkeys", path: "internal/front/docs-frontend-hotkeys.html" },
          ],
        },
        {
          label: "Reference",
          children: [
            { label: "JavaScript modules", path: "internal/front/docs-frontend-js-modules-reference.html" },
            { label: "CSS architecture", path: "internal/front/docs-frontend-css-architecture.html" },
            { label: "Token gallery (auto-generated)", path: "internal/front/docs-frontend-token-gallery.html" },
          ],
        },
        {
          label: "Cross-cutting systems",
          children: [
            { label: "Navigation and theme contract", path: "internal/front/docs-frontend-menu-and-theme-controls.html" },
            { label: "Navigation, search, discovery", path: "internal/front/docs-frontend-navigation-search-and-discovery.html" },
            { label: "UI, motion, adaptivity", path: "internal/front/docs-frontend-ui-motion-and-adaptivity.html" },
            { label: "Feedback and editorial workflow", path: "internal/front/docs-frontend-feedback-and-editorial-workflow.html" },
          ],
        },
      ],
    },
  ];

  function renderTree(nodes, fromDir, currentPath) {
    const ul = document.createElement("ul");
    ul.className = "internal-sidebar__tree";
    for (let i = 0; i < nodes.length; i += 1) {
      const node = nodes[i];
      const li = document.createElement("li");
      if (node.separator) {
        li.className = "internal-sidebar__separator";
        li.setAttribute("role", "presentation");
        const hr = document.createElement("hr");
        hr.setAttribute("aria-hidden", "true");
        li.appendChild(hr);
      } else if (node.children && node.children.length) {
        const details = document.createElement("details");
        details.className = "internal-sidebar__group";
        if (shouldOpenGroup(node, currentPath)) {
          details.open = true;
        }
        const summary = document.createElement("summary");
        summary.className = "internal-sidebar__summary";
        summary.textContent = node.label;
        details.appendChild(summary);
        details.appendChild(renderTree(node.children, fromDir, currentPath));
        li.appendChild(details);
      } else {
        const a = document.createElement("a");
        a.href = relHref(fromDir, node.path);
        if (node.labelHtml) {
          a.innerHTML = node.labelHtml;
        } else {
          a.textContent = node.label;
        }
        if (pathIsActive(currentPath, node.path)) {
          a.classList.add("is-active");
          a.setAttribute("aria-current", "page");
        }
        li.appendChild(a);
      }
      ul.appendChild(li);
    }
    return ul;
  }

  function scrollToActiveSidebarItem(host) {
    if (!host) {
      return;
    }
    const activeLink = host.querySelector("a.is-active");
    if (!activeLink || typeof activeLink.scrollIntoView !== "function") {
      return;
    }
    // Keep the current page link near center for quicker orientation in long trees.
    activeLink.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
  }

  function mount() {
    const host = document.getElementById("internal-sidebar-mount");
    if (!host) {
      return;
    }
    const sidebar = host.closest(".internal-layout__sidebar");
    const shell = document.querySelector(".internal-layout__shell");
    const relPath = currentDocsRelPath();
    const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
    const nav = document.createElement("nav");
    nav.setAttribute("aria-label", "Internal documentation");
    nav.appendChild(renderTree(INTERNAL_SIDEBAR_NAV, fromDir, relPath));
    host.replaceChildren(nav);
    requestAnimationFrame(() => {
      scrollToActiveSidebarItem(host);
    });
    ensureSidebarToggle(sidebar, host, shell);
    ensureDrawerInteractions(sidebar, shell, fromDir, relPath);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
