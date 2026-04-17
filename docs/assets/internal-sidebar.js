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

  function normalizePath(p) {
    return normalizeParts(p.split("/")).join("/");
  }

  function pathIsActive(current, target) {
    const a = normalizePath(current);
    const b = normalizePath(target);
    return a === b;
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
        currentPath === "internal/api/README.html" || currentPath.startsWith("internal/api/user/")
      );
    }
    return navHasActiveChild(node, currentPath);
  }

  /**
   * Paths are relative to the docs/ root (e.g. internal/README.html).
   */
  const INTERNAL_SIDEBAR_NAV = [
    { label: "Welcome", path: "internal/README.html" },
    { label: "Methodology", path: "internal/methodology.html" },
    { label: "System design", path: "internal/system-design.html" },
    { label: "Developers Docs", path: "internal/developers.html" },
    {
      label: "Kafka (just example)",
      children: [
        { label: "Overview", path: "kafka/README.html" },
        { label: "Topics", path: "kafka/topics.html" },
        { label: "Producers", path: "kafka/producers.html" },
        { label: "Consumers", path: "kafka/consumers.html" },
        { label: "Connectors", path: "kafka/connectors.html" },
        { label: "Tools", path: "kafka/tools.html" },
      ],
    },
    {
      label: "API documentation",
      children: [
        { label: "Errors", path: "internal/api/errors.html" },
        {
          label: "User",
          expand: "after-api-hub",
          children: [
            { label: "Hub — business, contract & technical spec", path: "internal/api/user/index.html" },
            { label: "Create — POST", path: "internal/api/user/operations/post-api-v1-user.html" },
            { label: "Read — GET", path: "internal/api/user/operations/get-api-v1-user-system_uuid-system_user_id.html" },
            { label: "Replace — PUT", path: "internal/api/user/operations/put-api-v1-user-system_uuid-system_user_id.html" },
            { label: "Partial update — PATCH", path: "internal/api/user/operations/patch-api-v1-user-system_uuid-system_user_id.html" },
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
        a.textContent = node.label;
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
    const relPath = currentDocsRelPath();
    const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
    const nav = document.createElement("nav");
    nav.setAttribute("aria-label", "Internal documentation");
    nav.appendChild(renderTree(INTERNAL_SIDEBAR_NAV, fromDir, relPath));
    host.replaceChildren(nav);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
