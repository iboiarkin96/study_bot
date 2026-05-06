"use strict";

/**
 * Long-page reading aids for internal docs:
 *  - "Resume reading" banner at top: if the reader scrolled past 25% of the page on a
 *    previous visit (within the last 14 days), offer a one-click jump to that position.
 *  - "Back to top" floating button: appears after scrolling 600 px; smooth-scrolls home.
 *
 * Storage:
 *  - sessionStorage `docs.resume.seen.<path>` — "1" when the resume banner has been
 *    actioned/dismissed in this tab, so we do not nag.
 *  - localStorage  `docs.resume.<path>`       — last scrollY (number) and timestamp (ms).
 *
 * Scope: any page that loads this script. The `internal-layout` container is preferred,
 * but the script gracefully no-ops when not present.
 */
(function () {
  const PATH_KEY = location.pathname.replace(/[^A-Za-z0-9_/-]/g, "_");
  const RESUME_KEY = "docs.resume." + PATH_KEY;
  const SEEN_KEY = "docs.resume.seen." + PATH_KEY;
  const TTL_MS = 14 * 24 * 60 * 60 * 1000;
  const MIN_SCROLL_FRACTION = 0.25;
  const BACK_TO_TOP_THRESHOLD = 600;
  const SAVE_THROTTLE_MS = 750;

  function safeReadJson(key) {
    try {
      const raw = window.localStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      return parsed;
    } catch {
      return null;
    }
  }

  function safeWriteJson(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore quota / disabled storage */
    }
  }

  function safeReadSession(key) {
    try {
      return window.sessionStorage.getItem(key);
    } catch {
      return null;
    }
  }

  function safeWriteSession(key, value) {
    try {
      window.sessionStorage.setItem(key, value);
    } catch {
      /* ignore */
    }
  }

  function pageHeight() {
    return Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight,
      document.body.offsetHeight,
      document.documentElement.offsetHeight,
    );
  }

  function viewportHeight() {
    return window.innerHeight || document.documentElement.clientHeight || 0;
  }

  function scrollableExtent() {
    return Math.max(0, pageHeight() - viewportHeight());
  }

  function buildBackToTop() {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "docs-resume-top";
    btn.setAttribute("aria-label", "Back to top of page");
    btn.setAttribute("title", "Back to top");
    btn.innerHTML =
      '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">' +
      '<path d="M7 11V3M7 3L3 7M7 3L11 7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' +
      "</svg><span>Top</span>";
    btn.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    document.body.appendChild(btn);

    function syncVisibility() {
      const show = window.scrollY > BACK_TO_TOP_THRESHOLD;
      btn.classList.toggle("is-visible", show);
    }
    syncVisibility();
    window.addEventListener("scroll", syncVisibility, { passive: true });
  }

  function buildResumeBanner(savedY) {
    const banner = document.createElement("div");
    banner.className = "docs-resume-banner";
    banner.setAttribute("role", "status");
    banner.innerHTML =
      '<div class="docs-resume-banner__text">' +
      "<strong>Continue reading?</strong> You stopped here last time on this page." +
      "</div>" +
      '<div class="docs-resume-banner__actions">' +
      '<button type="button" class="docs-resume-banner__btn docs-resume-banner__btn--primary" data-resume-go>Jump to last position</button>' +
      '<button type="button" class="docs-resume-banner__btn" data-resume-dismiss>Dismiss</button>' +
      "</div>";

    function dismiss() {
      safeWriteSession(SEEN_KEY, "1");
      banner.classList.add("is-leaving");
      window.setTimeout(() => banner.remove(), 200);
    }

    banner.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest("[data-resume-go]")) {
        window.scrollTo({ top: savedY, behavior: "smooth" });
        dismiss();
      } else if (target.closest("[data-resume-dismiss]")) {
        dismiss();
      }
    });

    document.body.appendChild(banner);
  }

  function maybeOfferResume() {
    if (safeReadSession(SEEN_KEY) === "1") return;
    const saved = safeReadJson(RESUME_KEY);
    if (!saved || typeof saved.y !== "number" || typeof saved.t !== "number") return;
    if (Date.now() - saved.t > TTL_MS) return;
    const extent = scrollableExtent();
    if (extent <= 0) return;
    if (saved.y / extent < MIN_SCROLL_FRACTION) return;
    if (saved.y > extent - 40) return;
    buildResumeBanner(saved.y);
  }

  function startScrollPersistence() {
    let lastSaved = 0;
    let pending = null;
    function persist() {
      pending = null;
      const y = window.scrollY;
      if (y < 200) return;
      lastSaved = Date.now();
      safeWriteJson(RESUME_KEY, { y, t: lastSaved });
    }
    window.addEventListener(
      "scroll",
      () => {
        if (pending !== null) return;
        const sinceLast = Date.now() - lastSaved;
        const wait = Math.max(SAVE_THROTTLE_MS - sinceLast, 100);
        pending = window.setTimeout(persist, wait);
      },
      { passive: true },
    );
    window.addEventListener("beforeunload", persist);
  }

  function init() {
    if (!document.body) return;
    // The standalone ↑ Top button has been retired in favour of the rocket
    // FAB built by docs-nav.js (initBackToTopButton). buildBackToTop is kept
    // in this file as dead code so the resume banner + scroll persistence
    // logic below stays untouched; remove the function later if cleaning up.
    void buildBackToTop;
    maybeOfferResume();
    startScrollPersistence();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
