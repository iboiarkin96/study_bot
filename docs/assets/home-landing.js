"use strict";

(function () {
  const FIRST_VISIT_KEY = "docs.home.first-visit.v1";
  const mediaReduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const canAnimate = !mediaReduced.matches;
  const INTRO_DURATION_MS = 2400;

  function isFirstVisit() {
    try {
      return window.localStorage.getItem(FIRST_VISIT_KEY) !== "1";
    } catch {
      return false;
    }
  }

  function persistFirstVisitSeen() {
    try {
      window.localStorage.setItem(FIRST_VISIT_KEY, "1");
    } catch {
      // Ignore storage failures.
    }
  }

  function markFirstVisitClass() {
    if (isFirstVisit() && canAnimate) {
      document.body.classList.add("home-first-visit");
    }
  }

  function bindFirstVisitIntro() {
    const intro = document.querySelector("[data-home-intro]");
    const skip = document.querySelector("[data-home-intro-skip]");
    if (!intro || !canAnimate || !isFirstVisit()) {
      persistFirstVisitSeen();
      return;
    }

    document.body.classList.add("home-intro-lock");
    intro.classList.add("is-active");
    intro.setAttribute("aria-hidden", "false");

    let closed = false;
    function closeIntro() {
      if (closed) {
        return;
      }
      closed = true;
      persistFirstVisitSeen();
      intro.classList.add("is-exit");
      window.setTimeout(() => {
        intro.classList.remove("is-active", "is-exit");
        intro.setAttribute("aria-hidden", "true");
        document.body.classList.remove("home-intro-lock");
      }, 420);
    }

    window.setTimeout(closeIntro, INTRO_DURATION_MS);
    if (skip) {
      skip.addEventListener("click", closeIntro);
    }
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeIntro();
      }
    });
  }

  function bindRevealOnScroll() {
    const revealNodes = Array.from(document.querySelectorAll("[data-home-reveal]"));
    if (!revealNodes.length) {
      return;
    }
    if (!canAnimate || !("IntersectionObserver" in window)) {
      revealNodes.forEach((node) => node.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.15 },
    );
    revealNodes.forEach((node) => observer.observe(node));
  }

  function bindHeroParallax() {
    const host = document.querySelector("[data-home-parallax-host]");
    const layers = Array.from(document.querySelectorAll("[data-home-parallax-layer]"));
    if (!host || !layers.length || !canAnimate) {
      return;
    }
    let rafId = 0;
    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;

    function tick() {
      currentX += (targetX - currentX) * 0.12;
      currentY += (targetY - currentY) * 0.12;
      layers.forEach((layer) => {
        const depth = Number(layer.getAttribute("data-home-parallax-layer")) || 0;
        const x = currentX * depth;
        const y = currentY * depth;
        layer.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      });
      if (Math.abs(targetX - currentX) > 0.08 || Math.abs(targetY - currentY) > 0.08) {
        rafId = window.requestAnimationFrame(tick);
      } else {
        rafId = 0;
      }
    }

    host.addEventListener("pointermove", (event) => {
      const rect = host.getBoundingClientRect();
      const relX = (event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5;
      const relY = (event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5;
      targetX = relX * 32;
      targetY = relY * 24;
      if (!rafId) {
        rafId = window.requestAnimationFrame(tick);
      }
    });

    host.addEventListener("pointerleave", () => {
      targetX = 0;
      targetY = 0;
      if (!rafId) {
        rafId = window.requestAnimationFrame(tick);
      }
    });
  }

  function bindScrollProgress() {
    const bar = document.querySelector("[data-home-scroll-progress]");
    if (!bar || !canAnimate) {
      return;
    }
    let rafId = 0;
    function draw() {
      rafId = 0;
      const doc = document.documentElement;
      const maxScroll = Math.max(doc.scrollHeight - window.innerHeight, 1);
      const p = Math.min(Math.max(window.scrollY / maxScroll, 0), 1);
      bar.style.transform = `scaleX(${p.toFixed(4)})`;
    }
    function schedule() {
      if (!rafId) {
        rafId = window.requestAnimationFrame(draw);
      }
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    schedule();
  }

  function bindMagneticCta() {
    const elements = Array.from(document.querySelectorAll("[data-home-magnetic]"));
    if (!elements.length || !canAnimate) {
      return;
    }
    elements.forEach((el) => {
      let rafId = 0;
      let tx = 0;
      let ty = 0;
      let cx = 0;
      let cy = 0;

      function paint() {
        cx += (tx - cx) * 0.16;
        cy += (ty - cy) * 0.16;
        el.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0)`;
        if (Math.abs(tx - cx) > 0.1 || Math.abs(ty - cy) > 0.1) {
          rafId = window.requestAnimationFrame(paint);
        } else {
          rafId = 0;
        }
      }

      el.addEventListener("pointermove", (event) => {
        const rect = el.getBoundingClientRect();
        const dx = event.clientX - (rect.left + rect.width / 2);
        const dy = event.clientY - (rect.top + rect.height / 2);
        tx = Math.max(Math.min(dx * 0.16, 9), -9);
        ty = Math.max(Math.min(dy * 0.16, 7), -7);
        if (!rafId) {
          rafId = window.requestAnimationFrame(paint);
        }
      });

      el.addEventListener("pointerleave", () => {
        tx = 0;
        ty = 0;
        if (!rafId) {
          rafId = window.requestAnimationFrame(paint);
        }
      });
    });
  }

  function init() {
    markFirstVisitClass();
    bindFirstVisitIntro();
    bindRevealOnScroll();
    bindHeroParallax();
    bindScrollProgress();
    bindMagneticCta();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
