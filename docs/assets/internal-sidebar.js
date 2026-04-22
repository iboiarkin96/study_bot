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
        { label: "Assessments", path: "audit/README.html" },
        { label: "Backlog", path: "backlog/README.html" },
      ],
    },
    {
      title: "Code",
      kind: "public",
      links: [
        { label: "OpenAPI explorer", path: "openapi/openapi-explorer.html" },
        { label: "Pdoc API docs", path: "api/index.html" },
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
    if (!title) {
      return;
    }
    const expandedTitleText = "Internal docs";
    const collapsedTitleText = "DOCS";
    title.textContent = expandedTitleText;

    let toggle = sidebar.querySelector("[data-internal-sidebar-toggle]");
    if (!toggle) {
      toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "internal-layout__sidebar-toggle";
      toggle.setAttribute("data-internal-sidebar-toggle", "1");
      title.insertAdjacentElement("afterend", toggle);
    }

    toggle.setAttribute("aria-controls", sidebarHost.id);

    function applyCollapsedState(isCollapsed) {
      shell.classList.toggle("is-sidebar-collapsed", isCollapsed);
      sidebarHost.hidden = isCollapsed;
      toggle.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      toggle.textContent = isCollapsed ? "SHOW\nMENU" : "Hide menu";
      title.textContent = isCollapsed ? collapsedTitleText : expandedTitleText;
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
    if (sectionPath === "openapi/openapi-explorer.html") {
      return currentPath === "openapi/openapi-explorer.html" || currentPath === "openapi-explorer.html";
    }
    if (sectionPath === "api/index.html") {
      return currentPath.startsWith("api/");
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
    // { label: "Documentation home", path: "index.html" },
    { label: "Welcome to internal docs!", path: "internal/README.html" },
    { label: "Employee portal", path: "internal/portal/index.html" },
    { label: "Methodology", path: "internal/methodology.html" },
    { label: "System design", path: "internal/system-design.html" },
    { label: "Developers Docs", path: "internal/developers.html" },
    { label: "Documentation style guide", path: "internal/documentation-style-guide.html" },
    { label: "How-to guides", path: "howto/README.html" },
    { label: "ADR", path: "adr/README.html" },
    { label: "RFC", path: "rfc/README.html" },
    { label: "OpenAPI explorer", path: "openapi/openapi-explorer.html" },
    { label: "Runbooks", path: "runbooks/README.html" },
    // { label: "Backlog", path: "backlog/README.html" },
    // { label: "Architecture & quality assessments", path: "audit/README.html" },
    {
      label: "API documentation",
      children: [
        { label: "Errors", path: "internal/api/errors.html" },
        {
          label: "User",
          expand: "after-api-hub",
          children: [
            { label: "Hub — business, contract & technical spec", path: "internal/api/user/index.html" },
            { label: "POST /user", path: "internal/api/user/operations/post-api-v1-user.html" },
            { label: "GET /user/", path: "internal/api/user/operations/get-api-v1-user-system_uuid-system_user_id.html" },
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
                'Hub — entity, <span class="docs-tooltip docs-tooltip--etr">ETR</span> mapping &amp; methods',
              path: "internal/api/conspectus/index.html",
            },
            { label: "POST /conspectuses", path: "internal/api/conspectus/operations/post-api-v1-conspectuses.html" },
            { label: "PATCH /conspectuses/{id}", path: "internal/api/conspectus/operations/patch-api-v1-conspectuses-conspectus_uuid.html" },
            { label: "POST …/actions/review", path: "internal/api/conspectus/operations/post-api-v1-conspectuses-conspectus_uuid-actions-review.html" },
            { label: "GET /conspectuses/due/", path: "internal/api/conspectus/operations/get-api-v1-conspectuses-due.html" },
            { label: "GET /schedule/summary/", path: "internal/api/conspectus/operations/get-api-v1-schedule-summary.html" },
          ],
        },
        {
          label: "Error log",
          expand: "after-api-hub",
          children: [
            { label: "Hub — FR-4 & methods", path: "internal/api/error-log/index.html" },
            { label: "GET /errors/", path: "internal/api/error-log/operations/get-api-v1-errors.html" },
            { label: "POST /errors", path: "internal/api/error-log/operations/post-api-v1-errors.html" },
          ],
        },
      ],
    },
    {
      label: "Docs documentation",
      children: [{
        label: "#1 Docs frontend navigation and theme controls",
        path: "internal/docs-documentation-frontend-tz-menu-and-theme.html"
      },

      ]
    },
  ];

  function renderTree(nodes, fromDir, currentPath) {
    const ul = document.createElement("ul");
    ul.className = "internal-sidebar__tree";
    for (let i = 0; i < nodes.length; i += 1) {
      const node = nodes[i];
      const li = document.createElement("li");
      if (node.children && node.children.length) {
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
    ensureSidebarToggle(sidebar, host, shell);
    ensureDrawerInteractions(sidebar, shell, fromDir, relPath);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
