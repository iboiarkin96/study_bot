"use strict";

/**
 * Internal docs UI helpers (portal grouping, page editors, profile maintained list).
 * People data is generated into docs/assets/docs-portal-data.js from each profile page
 * (data-* on <body>) by scripts/collect_docs_portal_data.py — run make docs-fix.
 */
(function () {
  window.__DOCS_INTERNAL_META__ = {
    site: {
      github: {
        owner: "iboiarkin96",
        repo: "study_bot",
        defaultBranch: "main",
        docsPathPrefix: "docs/",
      },
    },
  };

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
      "meta",
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

  function docsRootPrefixFromPage() {
    const relPath = currentDocsRelPath();
    const dir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
    const fromParts = normalizeParts(dir.split("/"));
    const up = new Array(fromParts.length).fill("..");
    const joined = [...up].join("/");
    return joined ? `${joined}/` : "";
  }

  function getPortalPeople() {
    const d = window.__DOCS_PORTAL_DATA__;
    return d && Array.isArray(d.people) ? d.people : [];
  }

  function personById(id) {
    const list = getPortalPeople();
    for (let i = 0; i < list.length; i += 1) {
      if (list[i].personId === id) {
        return list[i];
      }
    }
    return null;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Comma-separated person ids on <body data-maintainer-ids="a,b"> */
  function parseMaintainerIds() {
    const raw = document.body.getAttribute("data-maintainer-ids") || "";
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function renderPageMeta() {
    const mount = document.getElementById("docs-page-meta-mount");
    if (!mount) {
      return;
    }
    const ids = parseMaintainerIds();
    if (ids.length === 0) {
      return;
    }

    const relPath = currentDocsRelPath();
    const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";

    const knownEditors = ids
      .map((pid) => personById(pid))
      .filter(Boolean);
    const stacked = knownEditors
      .slice(0, 3)
      .map((p) => {
        const profileHref = relHref(fromDir, `internal/portal/people/${p.slug}/index.html`);
        const photoHref = `${docsRootPrefixFromPage()}${p.photo}`;
        return `<a class="docs-page-meta__stack-item" href="${profileHref}" aria-label="${escapeHtml(p.displayName)}">
  <img class="docs-page-meta__stack-avatar" src="${photoHref}" width="24" height="24" alt="" />
</a>`;
      })
      .join("");
    const extra = knownEditors.length > 3 ? `<span class="docs-page-meta__stack-extra">+${knownEditors.length - 3}</span>` : "";
    const stackHtml =
      knownEditors.length > 0
        ? `<div class="docs-page-meta__stack" aria-label="Editors overview">${stacked}${extra}</div>`
        : "";

    const editorsHtml = ids
      .map((pid) => {
        const p = personById(pid);
        if (p) {
          const profileHref = relHref(fromDir, `internal/portal/people/${p.slug}/index.html`);
          const photoHref = `${docsRootPrefixFromPage()}${p.photo}`;
          const name = p.displayName;
          return `<li class="docs-page-meta__editor">
  <a class="docs-page-meta__avatar-link" href="${profileHref}">
    <img class="docs-page-meta__avatar" src="${photoHref}" width="40" height="40" alt="" />
  </a>
  <a class="docs-page-meta__editor-name-link" href="${profileHref}">${escapeHtml(name)}</a>
</li>`;
        }
        return `<li class="docs-page-meta__editor" role="status">Unknown person id <code>${escapeHtml(pid)}</code> — add a profile under <code>docs/internal/portal/people/</code> with this <code>data-person-id</code> and run <code>make docs-fix</code>.</li>`;
      })
      .join("");

    mount.innerHTML = `<section class="docs-page-meta docs-page-meta--premium" aria-labelledby="docs-page-meta-title">
  <button type="button" class="docs-page-meta__title docs-page-meta__toggle" id="docs-page-meta-title" aria-expanded="false" aria-controls="docs-page-meta-list">Page editors</button>
  ${stackHtml}
  <ul class="docs-page-meta__editors" id="docs-page-meta-list" hidden>${editorsHtml}</ul>
</section>`;
    const toggle = mount.querySelector(".docs-page-meta__toggle");
    const list = mount.querySelector("#docs-page-meta-list");
    if (toggle && list) {
      toggle.addEventListener("click", () => {
        const isOpen = !list.hidden;
        list.hidden = isOpen;
        toggle.setAttribute("aria-expanded", isOpen ? "false" : "true");
      });
    }
    mount.hidden = false;
  }

  const PORTAL_GROUP_ORDER = ["pm", "backend", "devops"];

  const PORTAL_GROUP_TITLES = {
    pm: "PM",
    backend: "Backend",
    devops: "DevOps",
  };

  function titleForGroupKey(k) {
    if (Object.prototype.hasOwnProperty.call(PORTAL_GROUP_TITLES, k)) {
      return PORTAL_GROUP_TITLES[k];
    }
    return String(k)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (ch) => ch.toUpperCase());
  }

  function collectGroupKeysPresent(people) {
    const set = new Set();
    for (let i = 0; i < people.length; i += 1) {
      const g = people[i].groups;
      if (!Array.isArray(g)) {
        continue;
      }
      for (let j = 0; j < g.length; j += 1) {
        set.add(g[j]);
      }
    }
    return set;
  }

  function orderedPortalGroupEntries(presentKeys) {
    const out = [];
    let idx = 0;
    for (idx = 0; idx < PORTAL_GROUP_ORDER.length; idx += 1) {
      const k = PORTAL_GROUP_ORDER[idx];
      if (presentKeys.has(k)) {
        out.push({ key: k, title: titleForGroupKey(k) });
      }
    }
    const rest = [...presentKeys]
      .filter((k) => PORTAL_GROUP_ORDER.indexOf(k) === -1)
      .sort();
    for (idx = 0; idx < rest.length; idx += 1) {
      const k = rest[idx];
      out.push({ key: k, title: titleForGroupKey(k) });
    }
    return out;
  }

  function portalGroupDomId(key) {
    return String(key).replace(/[^a-zA-Z0-9_-]/g, "_");
  }

  /** Items per page for Maintained pages on profile */
  const MAINTAINED_PAGE_SIZE = 10;
  const SKELETON_MIN_VISIBLE_MS = 600;

  let maintainedPagerState = null;

  function maintainedListItemsHtml(slice, fromDir) {
    return slice
      .map((pg) => {
        const href = relHref(fromDir, pg.path);
        return `<li><a href="${escapeHtml(href)}">${escapeHtml(pg.title)}</a> <span class="portal-profile__path">(<code>${escapeHtml(pg.path)}</code>)</span></li>`;
      })
      .join("");
  }

  function maintainedPagerNavHtml(pageIndex, totalPages) {
    if (totalPages <= 1) {
      return "";
    }
    const prevDisabled = pageIndex <= 0;
    const nextDisabled = pageIndex >= totalPages - 1;
    return `<nav class="portal-maintained-pager__nav" aria-label="Maintained pages pagination">
  <button type="button" class="portal-maintained-pager__btn" data-maintained-act="prev"${prevDisabled ? " disabled" : ""
      }>Previous</button>
  <span class="portal-maintained-pager__status">Page ${pageIndex + 1} of ${totalPages}</span>
  <button type="button" class="portal-maintained-pager__btn" data-maintained-act="next"${nextDisabled ? " disabled" : ""
      }>Next</button>
</nav>`;
  }

  function paintMaintainedPager(mount) {
    const state = maintainedPagerState;
    if (!state || !mount) {
      return;
    }
    const { pages, fromDir, pageSize } = state;
    const total = pages.length;
    if (total === 0) {
      mount.innerHTML = `<p class="portal-people-group__empty">No pages list you yet. Set <code>data-maintainer-ids=&quot;${escapeHtml(
        state.personId,
      )}&quot;</code> on a doc page <code>&lt;body&gt;</code> and run <code>make docs-fix</code>.</p>`;
      mount.onclick = null;
      return;
    }
    const totalPages = Math.ceil(total / pageSize);
    let idx = state.pageIndex;
    if (idx >= totalPages) {
      idx = totalPages - 1;
    }
    if (idx < 0) {
      idx = 0;
    }
    state.pageIndex = idx;
    const start = idx * pageSize;
    const slice = pages.slice(start, start + pageSize);
    const items = maintainedListItemsHtml(slice, fromDir);
    const nav = maintainedPagerNavHtml(idx, totalPages);
    mount.innerHTML = `<ul class="portal-profile-maintained__list">${items}</ul>${nav}`;
    mount.onclick = function (e) {
      const btn = e.target.closest("[data-maintained-act]");
      if (!btn || btn.disabled || !maintainedPagerState) {
        return;
      }
      const act = btn.getAttribute("data-maintained-act");
      const st = maintainedPagerState;
      const tp = Math.ceil(st.pages.length / st.pageSize);
      if (act === "prev" && st.pageIndex > 0) {
        st.pageIndex -= 1;
      } else if (act === "next" && st.pageIndex < tp - 1) {
        st.pageIndex += 1;
      }
      paintMaintainedPager(mount);
    };
  }

  function renderProfileMaintainedMount() {
    const mount = document.getElementById("portal-maintained-mount");
    if (!mount) {
      return;
    }
    const personId = document.body.getAttribute("data-person-id");
    if (!personId) {
      return;
    }
    mount.innerHTML = `<ul class="portal-skeleton-list" aria-hidden="true"><li></li><li></li><li></li></ul>`;
    const d = window.__DOCS_PORTAL_DATA__ || {};
    const pages = (d.maintainerPages && d.maintainerPages[personId]) || [];
    const relPath = currentDocsRelPath();
    const fromDir = relPath.includes("/") ? relPath.slice(0, relPath.lastIndexOf("/")) : "";
    maintainedPagerState = {
      personId,
      pages,
      fromDir,
      pageIndex: 0,
      pageSize: MAINTAINED_PAGE_SIZE,
    };
    window.setTimeout(() => {
      paintMaintainedPager(mount);
    }, SKELETON_MIN_VISIBLE_MS);
  }

  function renderPersonCard(p, fromDir) {
    const profileHref = relHref(fromDir, `internal/portal/people/${p.slug}/index.html`);
    const photoHref = `${docsRootPrefixFromPage()}${p.photo}`;
    const name = escapeHtml(p.displayName);
    const groupsRaw = Array.isArray(p.groups) ? p.groups : [];
    const groups = groupsRaw.map((g) => escapeHtml(titleForGroupKey(g))).join(" · ");
    const groupsHtml = groups ? `<span class="portal-people__meta">${groups}</span>` : "";
    return `<li class="portal-people__item card">
  <a class="portal-people__link" href="${profileHref}">
    <span class="portal-people__avatar-link">
      <img class="portal-people__avatar" src="${photoHref}" width="56" height="56" alt="" />
    </span>
    <span class="portal-people__text">
      <span class="portal-people__name">${name}</span>
      ${groupsHtml}
    </span>
  </a>
</li>`;
  }

  function renderPortalPeople() {
    const mount = document.getElementById("portal-people-mount");
    if (!mount) {
      return;
    }
    mount.innerHTML = `<div class="portal-skeleton-grid" aria-hidden="true"><span></span><span></span><span></span></div>`;
    const fromDir = "internal/portal";
    const people = getPortalPeople();

    const presentKeys = collectGroupKeysPresent(people);
    const groupEntries = orderedPortalGroupEntries(presentKeys);

    if (groupEntries.length === 0) {
      mount.innerHTML = `<p class="portal-people-group__empty">No profiles with <code>data-groups</code> under <code>docs/internal/portal/people/</code> yet. Run <code>make docs-fix</code> after editing profiles.</p>`;
      return;
    }

    const blocks = groupEntries
      .map((g) => {
        const gid = portalGroupDomId(g.key);
        const inGroup = people
          .filter((p) => Array.isArray(p.groups) && p.groups.includes(g.key))
          .slice()
          .sort((a, b) => String(a.displayName || "").localeCompare(String(b.displayName || "")));
        const listItems = inGroup.map((p) => renderPersonCard(p, fromDir)).join("");
        const count = inGroup.length;
        const countBadge = `<span class="portal-people-group__count" aria-label="${escapeHtml(g.title)} people count">${count}</span>`;
        const body = listItems
          ? `<ul class="portal-people__list">${listItems}</ul>`
          : `<p class="portal-people-group__empty">No people listed yet.</p>`;
        return `<section class="portal-people-group" aria-labelledby="portal-group-${gid}">
  <h3 class="portal-people-group__title" id="portal-group-${gid}">${escapeHtml(g.title)} ${countBadge}</h3>
  ${body}
</section>`;
      })
      .join("");

    window.setTimeout(() => {
      mount.innerHTML = blocks;
    }, SKELETON_MIN_VISIBLE_MS);
  }

  function initDocsInternalMeta() {
    renderProfileMaintainedMount();
    renderPageMeta();
    renderPortalPeople();
  }

  window.initDocsInternalMeta = initDocsInternalMeta;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDocsInternalMeta);
  } else {
    initDocsInternalMeta();
  }
})();
