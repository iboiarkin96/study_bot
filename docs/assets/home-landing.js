"use strict";

(function () {
  const mediaReduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const canAnimate = !mediaReduced.matches;
  const INTRO_DURATION_MS = 3000;
  const WORDMARK_TEXT = "ETR // API";

  // Track intro state on the module so modules registered AFTER dispatch can
  // still see it (e.g. reduced-motion path dispatches synchronously inside init).
  let introIsDone = false;
  function markIntroDone() {
    if (introIsDone) return;
    introIsDone = true;
    window.dispatchEvent(new CustomEvent("home:intro-done"));
  }
  function whenIntroDone(fn) {
    if (introIsDone) { fn(); return; }
    window.addEventListener("home:intro-done", () => fn(), { once: true });
  }

  function markFirstVisitClass() {
    if (canAnimate) {
      document.body.classList.add("home-first-visit");
    }
  }

  /* ── Boot-sequence intro ────────────────────────────────────────────────
     Three concurrent effects:
       1. Glyph rain canvas (matrix-style background)
       2. Boot log streaming top-left
       3. Wordmark scramble-resolve in center, with lock-flash + scan beam
  */

  const GLYPH_POOL = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ0123456789ABCDEFGHIJKLMNOP{}<>+=*#%@&?!/_-";

  function startGlyphRain(intro) {
    const canvas = intro.querySelector("[data-home-intro-rain]");
    if (!canvas) return { stop: () => {}, burst: () => {} };
    const ctx = canvas.getContext("2d");
    if (!ctx) return { stop: () => {}, burst: () => {} };

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;
    let columns = [];
    let burst = 0; // 0..1, decays each frame; bumped on wordmark char lock
    const FONT_SIZE = 16;
    const COLUMN_W = FONT_SIZE * 1.1;

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const colCount = Math.ceil(width / COLUMN_W);
      columns = new Array(colCount).fill(0).map(() => ({
        y: -Math.random() * height,
        speed: 1.5 + Math.random() * 3,
        active: Math.random() < 0.55,
      }));
    }

    let stopped = false;
    function draw() {
      if (stopped) return;
      // Background fade — slightly stronger during burst so heads pop more
      const fadeAlpha = 0.18 - burst * 0.06;
      ctx.fillStyle = `rgba(4, 8, 18, ${fadeAlpha.toFixed(3)})`;
      ctx.fillRect(0, 0, width, height);
      ctx.font = `${FONT_SIZE}px ui-monospace, monospace`;
      ctx.textBaseline = "top";

      const headAlpha = Math.min(1, 0.92 + burst * 0.3);
      const trailAlpha = Math.min(1, 0.55 + burst * 0.45);
      const headColor = `rgba(${Math.round(232 + burst * 20)}, 236, 255, ${headAlpha.toFixed(3)})`;
      const trailColor = `rgba(165, 180, 252, ${trailAlpha.toFixed(3)})`;

      for (let i = 0; i < columns.length; i++) {
        const col = columns[i];
        // During a burst, briefly wake some inactive columns
        const isActive = col.active || (burst > 0.45 && Math.random() < burst * 0.25);
        if (!isActive) continue;
        const x = i * COLUMN_W;
        const ch = GLYPH_POOL[Math.floor(Math.random() * GLYPH_POOL.length)];
        ctx.fillStyle = headColor;
        ctx.fillText(ch, x, col.y);
        ctx.fillStyle = trailColor;
        const ch2 = GLYPH_POOL[Math.floor(Math.random() * GLYPH_POOL.length)];
        ctx.fillText(ch2, x, col.y - FONT_SIZE * 1.2);
        col.y += col.speed * (1 + burst * 0.8);
        if (col.y > height + 40) {
          col.y = -Math.random() * 200;
          col.speed = 1.5 + Math.random() * 3;
          col.active = Math.random() < 0.65;
        }
      }
      // Decay burst exponentially (~250ms half-life at 60fps)
      burst *= 0.92;
      if (burst < 0.005) burst = 0;
      window.requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener("resize", resize);
    window.requestAnimationFrame(draw);
    return {
      stop: () => { stopped = true; window.removeEventListener("resize", resize); },
      burst: (amount) => { burst = Math.min(1, burst + (amount || 0.6)); },
    };
  }

  function startWordmarkScramble(intro, finalText, onLocked, rain) {
    const row = intro.querySelector("[data-home-intro-glyphs]");
    const wordmark = intro.querySelector("[data-home-intro-wordmark]");
    const progressFill = intro.querySelector("[data-home-intro-progress]");
    const progressPct = intro.querySelector("[data-home-intro-progress-pct]");
    if (!row || !wordmark) {
      onLocked();
      return;
    }
    row.textContent = "";
    const chars = Array.from(finalText);
    const spans = chars.map((ch) => {
      const span = document.createElement("span");
      if (ch === " ") {
        span.className = "ig-char ig-space";
        span.textContent = "\u00a0";
        span.dataset.fixed = "1";
      } else if (ch === "/") {
        span.className = "ig-char ig-slash";
        span.textContent = "/";
        span.dataset.fixed = "1";
      } else {
        span.className = "ig-char ig-char--scrambling";
        span.textContent = GLYPH_POOL[Math.floor(Math.random() * GLYPH_POOL.length)];
      }
      row.appendChild(span);
      return span;
    });

    const SCRAMBLE_DURATION = 720;
    const STAGGER = 90;
    const INITIAL_DELAY = 600;
    const start = performance.now();
    const scrambleSpans = spans.filter((s) => s.dataset.fixed !== "1");
    const totalScrambleSpans = scrambleSpans.length;
    let lockedCount = 0;
    let lastPct = -1;

    function updateProgress() {
      const pct = Math.round((lockedCount / Math.max(1, totalScrambleSpans)) * 100);
      if (pct === lastPct) return;
      lastPct = pct;
      if (progressFill) progressFill.style.width = pct + "%";
      if (progressPct) progressPct.textContent = String(pct);
    }
    updateProgress();

    let lastTick = 0;
    function frame(now) {
      const t = now - start - INITIAL_DELAY;
      let allLocked = true;
      // Roll random glyphs every ~50ms
      const shouldRoll = now - lastTick > 50;
      if (shouldRoll) lastTick = now;

      spans.forEach((span, i) => {
        if (span.dataset.fixed === "1") return;
        if (span.dataset.locked === "1") return;
        const localStart = i * STAGGER;
        const localEnd = localStart + SCRAMBLE_DURATION;
        // Always keep the row width stable: every unlocked char keeps rolling
        // random glyphs from t=0, locks at its own (start+duration) point.
        if (t >= localEnd) {
          span.textContent = chars[i];
          span.classList.remove("ig-char--scrambling");
          span.classList.add("ig-char--locked");
          span.dataset.locked = "1";
          lockedCount++;
          updateProgress();
          if (rain && typeof rain.burst === "function") rain.burst(0.55);
          window.setTimeout(() => span.classList.remove("ig-char--locked"), 420);
          return;
        }
        if (shouldRoll) {
          span.textContent = GLYPH_POOL[Math.floor(Math.random() * GLYPH_POOL.length)];
        }
        allLocked = false;
      });

      if (allLocked) {
        wordmark.classList.add("is-locked");
        intro.classList.add("is-locked");
        if (rain && typeof rain.burst === "function") rain.burst(1);
        onLocked();
      } else {
        window.requestAnimationFrame(frame);
      }
    }
    window.requestAnimationFrame(frame);
  }

  function runBootSequence(intro, onDone) {
    const status = intro.querySelector("[data-home-intro-status]");
    const setStatus = (text) => { if (status) status.textContent = text; };

    const rain = startGlyphRain(intro);

    window.setTimeout(() => setStatus("decoding wordmark"), 600);
    window.setTimeout(() => setStatus("locking glyphs"), 1100);

    startWordmarkScramble(intro, WORDMARK_TEXT, () => {
      setStatus("ready");
      window.setTimeout(() => {
        if (typeof onDone === "function") onDone(rain.stop);
      }, 320);
    }, rain);
  }

  function runShutterExit(intro) {
    const DURATION = 720;
    const bg = window.getComputedStyle(intro).backgroundColor;

    const overlay = document.createElement("div");
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:130;pointer-events:none;" +
      "background:" + bg + ";" +
      "clip-path:circle(150% at 50% 46%);";

    document.body.appendChild(overlay);
    overlay.getBoundingClientRect();

    intro.style.transition = "none";
    intro.classList.remove("is-active");
    intro.setAttribute("aria-hidden", "true");
    document.body.classList.remove("home-intro-lock");

    overlay.style.transition = "clip-path " + DURATION + "ms cubic-bezier(0.87, 0, 0.13, 1)";
    overlay.style.clipPath = "circle(0% at 50% 46%)";

    // Fire decrypt at shutter start so the H1 is already mid-scramble
    // by the time the iris fully clears.
    markIntroDone();

    window.setTimeout(() => {
      overlay.remove();
      intro.style.transition = "";
    }, DURATION + 40);
  }

  function bindFirstVisitIntro() {
    const intro = document.querySelector("[data-home-intro]");
    const skip = document.querySelector("[data-home-intro-skip]");
    if (!intro || !canAnimate) {
      if (intro) intro.remove();
      markIntroDone();
      return;
    }

    document.body.classList.add("home-intro-lock");
    intro.classList.add("is-active");
    intro.setAttribute("aria-hidden", "false");

    let closed = false;
    let stopRain = null;
    function closeIntro() {
      if (closed) return;
      closed = true;
      if (typeof stopRain === "function") stopRain();
      runShutterExit(intro);
    }

    const closeAt = performance.now() + INTRO_DURATION_MS;
    runBootSequence(intro, (rainStopper) => {
      stopRain = rainStopper;
      const remaining = Math.max(0, closeAt - performance.now());
      window.setTimeout(closeIntro, remaining);
    });

    // Hard upper bound — close even if scramble doesn't lock for some reason
    window.setTimeout(closeIntro, INTRO_DURATION_MS + 600);

    if (skip) skip.addEventListener("click", closeIntro);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeIntro();
    });
  }

  /* ── H1 glyph-scramble decrypt ─────────────────────────────────────────── */

  const SCRAMBLE_CHARS = "█▓▒░ABCDEFGHIJKLMNOPQRSTUVWXYZ#@%&*+=<>/_";

  function decryptElement(el, finalText, opts) {
    const total = (opts && opts.duration) || 700;
    const stagger = (opts && opts.stagger) || 28;
    el.textContent = "";
    el.setAttribute("aria-label", finalText);
    const chars = Array.from(finalText);
    const spans = chars.map((ch) => {
      const span = document.createElement("span");
      span.className = "home-decrypt-char home-decrypt-char--scrambling";
      span.textContent = ch === " " ? "\u00a0" : SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
      el.appendChild(span);
      return span;
    });

    const start = performance.now();
    function frame(now) {
      const t = now - start;
      let allDone = true;
      spans.forEach((span, i) => {
        if (span.dataset.done === "1") return;
        const localStart = i * stagger;
        const localEnd = localStart + total;
        if (t < localStart) {
          allDone = false;
          return;
        }
        if (t >= localEnd) {
          span.textContent = chars[i] === " " ? "\u00a0" : chars[i];
          span.classList.remove("home-decrypt-char--scrambling");
          span.dataset.done = "1";
          return;
        }
        span.textContent = SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
        allDone = false;
      });
      if (!allDone) window.requestAnimationFrame(frame);
    }
    window.requestAnimationFrame(frame);
  }

  function bindHeroDecrypt() {
    const lines = Array.from(document.querySelectorAll("[data-home-decrypt]"));
    if (!lines.length) return;
    if (!canAnimate || !document.body.classList.contains("home-first-visit")) return;

    function run() {
      lines.forEach((el, idx) => {
        const finalText = el.getAttribute("data-home-decrypt") || el.textContent;
        window.setTimeout(() => decryptElement(el, finalText, { duration: 580, stagger: 32 }), idx * 140);
      });
    }
    whenIntroDone(run);
  }

  /* ── Variable-font weight on scroll ────────────────────────────────────── */

  function bindVariableWeight() {
    const el = document.querySelector("[data-home-variable-weight]");
    if (!el || !canAnimate) return;
    let rafId = 0;
    function update() {
      rafId = 0;
      const rect = el.getBoundingClientRect();
      const viewport = window.innerHeight || 1;
      const offset = Math.max(0, Math.min(1, 1 - rect.top / viewport));
      const wght = Math.round(500 + offset * 260);
      el.style.setProperty("--home-h1-wght", String(wght));
    }
    function schedule() {
      if (!rafId) rafId = window.requestAnimationFrame(update);
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    update();
  }

  /* ── Live self-typing terminal ─────────────────────────────────────────── */

  const TERMINAL_SCRIPT = [
    { cls: "home-terminal__t-mute", text: "$ " },
    { cls: "home-terminal__t-cmd",  text: "curl" },
    { text: " " },
    { cls: "home-terminal__t-url",  text: "https://api.etr.study/v1/conspectuses/due" },
    { text: " \\\n     " },
    { cls: "home-terminal__t-flag", text: "-H" },
    { text: " " },
    { cls: "home-terminal__t-str",  text: "\"Authorization: Bearer " },
    { cls: "home-terminal__t-var",  text: "$ETR_TOKEN" },
    { cls: "home-terminal__t-str",  text: "\"" },
    { text: "\n" },
    { cls: "home-terminal__t-mute", text: "→ " },
    { cls: "home-terminal__t-ok",   text: "200 OK" },
    { cls: "home-terminal__t-mute", text: " · " },
    { cls: "home-terminal__t-num",  text: "14" },
    { cls: "home-terminal__t-mute", text: " items · " },
    { cls: "home-terminal__t-lat",  text: "38ms" },
    { text: "\n" },
    { cls: "home-terminal__t-mute", text: "  " },
    { cls: "home-terminal__t-ok",   text: "schedule_summary" },
    { cls: "home-terminal__t-mute", text: " · next review in " },
    { cls: "home-terminal__t-num",  text: "12m" },
  ];

  function renderTerminalStatic(target) {
    target.textContent = "";
    TERMINAL_SCRIPT.forEach((seg) => {
      const span = document.createElement("span");
      if (seg.cls) span.className = seg.cls;
      span.textContent = seg.text;
      target.appendChild(span);
    });
  }

  function bindLiveTerminal() {
    const target = document.querySelector("[data-home-terminal-target]");
    if (!target) return;
    if (!canAnimate) {
      renderTerminalStatic(target);
      return;
    }

    const segments = TERMINAL_SCRIPT;
    target.textContent = "";
    const caret = document.createElement("span");
    caret.className = "home-terminal__caret";
    caret.setAttribute("aria-hidden", "true");
    target.appendChild(caret);

    let segIdx = 0;
    let charIdx = 0;
    let activeSpan = null;
    let started = false;
    let introDone = false;
    let visible = false;

    function nextSegment() {
      if (segIdx >= segments.length) return;
      const seg = segments[segIdx];
      activeSpan = document.createElement("span");
      if (seg.cls) activeSpan.className = seg.cls;
      target.insertBefore(activeSpan, caret);
      charIdx = 0;
      typeChar();
    }

    function typeChar() {
      const seg = segments[segIdx];
      if (!seg) return;
      const ch = seg.text[charIdx];
      if (ch === undefined) {
        segIdx++;
        if (segIdx < segments.length) {
          const delay = seg.text.endsWith("\n") ? 90 : 22;
          window.setTimeout(nextSegment, delay);
        }
        return;
      }
      activeSpan.appendChild(document.createTextNode(ch));
      charIdx++;
      const isWhitespace = /\s/.test(ch);
      const base = isWhitespace ? 18 : 24;
      const jitter = Math.random() * 28;
      window.setTimeout(typeChar, base + jitter);
    }

    function maybeStart() {
      if (started) return;
      if (!introDone || !visible) return;
      started = true;
      // Brief pause after intro closes so the user catches the page settling
      // before the terminal starts typing.
      window.setTimeout(nextSegment, 420);
    }

    whenIntroDone(() => {
      introDone = true;
      maybeStart();
    });

    if ("IntersectionObserver" in window) {
      const obs = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            visible = true;
            obs.disconnect();
            maybeStart();
          }
        });
      }, { threshold: 0.35 });
      obs.observe(target);
    } else {
      visible = true;
      maybeStart();
    }
  }

  /* ── Cursor-reactive dot grid ──────────────────────────────────────────── */

  function bindDotGrid() {
    const canvas = document.querySelector("[data-home-dotgrid]");
    if (!canvas || !canAnimate) {
      if (canvas) canvas.remove();
      return;
    }
    const host = canvas.parentElement && canvas.parentElement.parentElement;
    if (!host) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const SPACING = 26;
    const DOT_RADIUS = 1.1;
    const REACT_RADIUS = 140;
    const REACT_RADIUS_SQ = REACT_RADIUS * REACT_RADIUS;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;
    let mouseX = -9999;
    let mouseY = -9999;
    let targetX = -9999;
    let targetY = -9999;
    let rafId = 0;
    let dotColor = "rgba(150, 165, 220, 0.45)";
    let dotColorHot = "rgba(129, 140, 248, 0.95)";

    function readColors() {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark"
        || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
            && document.documentElement.getAttribute("data-theme") !== "light");
      // Restrained indigo family — same as the WebGL field + intro chrome.
      // The hot-spot is indigo-400 (#818cf8), not a punchy accent — feels
      // like a ripple of light, not a laser pointer.
      dotColor = isDark ? "rgba(165, 180, 252, 0.28)" : "rgba(67, 56, 202, 0.28)";
      dotColorHot = isDark ? "rgba(129, 140, 248, 1)" : "rgba(67, 56, 202, 1)";
    }

    function resize() {
      const rect = host.getBoundingClientRect();
      width = Math.ceil(rect.width);
      height = Math.ceil(rect.height);
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, width * dpr);
      canvas.height = Math.max(1, height * dpr);
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function draw() {
      rafId = 0;
      mouseX += (targetX - mouseX) * 0.18;
      mouseY += (targetY - mouseY) * 0.18;
      ctx.clearRect(0, 0, width, height);

      const cols = Math.ceil(width / SPACING) + 1;
      const rows = Math.ceil(height / SPACING) + 1;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const x = c * SPACING + (SPACING / 2);
          const y = r * SPACING + (SPACING / 2);
          const dx = x - mouseX;
          const dy = y - mouseY;
          const distSq = dx * dx + dy * dy;
          if (distSq < REACT_RADIUS_SQ) {
            const t = 1 - distSq / REACT_RADIUS_SQ;
            const radius = DOT_RADIUS + t * 2.6;
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fillStyle = dotColorHot;
            ctx.globalAlpha = 0.4 + t * 0.6;
            ctx.fill();
          } else {
            ctx.beginPath();
            ctx.arc(x, y, DOT_RADIUS, 0, Math.PI * 2);
            ctx.fillStyle = dotColor;
            ctx.globalAlpha = 1;
            ctx.fill();
          }
        }
      }
      ctx.globalAlpha = 1;

      const stillMoving = Math.abs(targetX - mouseX) > 0.4 || Math.abs(targetY - mouseY) > 0.4;
      if (stillMoving) schedule();
    }

    function schedule() {
      if (!rafId) rafId = window.requestAnimationFrame(draw);
    }

    function onMove(event) {
      const rect = host.getBoundingClientRect();
      targetX = event.clientX - rect.left;
      targetY = event.clientY - rect.top;
      schedule();
    }

    function onLeave() {
      targetX = -9999;
      targetY = -9999;
      schedule();
    }

    readColors();
    resize();
    draw();
    window.addEventListener("resize", () => { resize(); schedule(); });
    host.addEventListener("pointermove", onMove);
    host.addEventListener("pointerleave", onLeave);

    // Re-read colors if theme toggles
    const themeObserver = new MutationObserver(() => { readColors(); schedule(); });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  }

  /* ── Number tickers (count-up on reveal) ───────────────────────────────── */

  function bindTickers() {
    const wrap = document.querySelector("[data-home-tickers]");
    if (!wrap) return;
    const nums = Array.from(wrap.querySelectorAll("[data-home-ticker-target]"));
    if (!nums.length) return;

    function runCountUp(el) {
      const target = Number(el.getAttribute("data-home-ticker-target")) || 0;
      const suffix = el.getAttribute("data-home-ticker-suffix") || "";
      if (!canAnimate) {
        el.textContent = String(target) + suffix;
        return;
      }
      const duration = 900;
      const start = performance.now();
      function frame(now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = String(Math.round(target * eased)) + (t === 1 ? suffix : "");
        if (t < 1) window.requestAnimationFrame(frame);
        else el.textContent = String(target) + suffix;
      }
      window.requestAnimationFrame(frame);
    }

    if ("IntersectionObserver" in window) {
      const obs = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          nums.forEach((n, i) => window.setTimeout(() => runCountUp(n), i * 80));
          obs.disconnect();
        });
      }, { threshold: 0.5 });
      obs.observe(wrap);
    } else {
      nums.forEach(runCountUp);
    }
  }

  /* ── Section tint shift ────────────────────────────────────────────────── */

  function bindSectionTints() {
    const sections = Array.from(document.querySelectorAll("[data-section-tint]"));
    if (!sections.length || !("IntersectionObserver" in window)) return;
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.classList.add("is-tinted");
      });
    }, { rootMargin: "0px 0px -25% 0px", threshold: 0.1 });
    sections.forEach((s) => obs.observe(s));
  }

  /* ── View Transitions API (cross-page nav) ────────────────────────────── */

  function bindViewTransitions() {
    if (!("startViewTransition" in document)) return;
    const links = Array.from(document.querySelectorAll("a[data-home-vt]"));
    links.forEach((link) => {
      link.addEventListener("click", (event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (event.button !== 0) return;
        const href = link.getAttribute("href");
        if (!href || href.startsWith("#") || /^https?:/.test(href)) return;
        event.preventDefault();
        document.startViewTransition(() => {
          window.location.href = href;
        });
      });
    });
  }

  /* ── Existing modules (kept) ───────────────────────────────────────────── */

  function bindRevealOnScroll() {
    const revealNodes = Array.from(document.querySelectorAll("[data-home-reveal]"));
    if (!revealNodes.length) return;
    if (!canAnimate || !("IntersectionObserver" in window)) {
      revealNodes.forEach((node) => {
        node.classList.add("is-visible");
        node.querySelectorAll(".home-card").forEach((card) => card.classList.add("is-visible"));
      });
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const cards = Array.from(entry.target.querySelectorAll(".home-card"));
          if (cards.length > 0) {
            entry.target.style.transition = "none";
            entry.target.style.opacity = "1";
            entry.target.style.transform = "none";
            entry.target.classList.add("is-visible");
            window.requestAnimationFrame(() => {
              entry.target.style.transition = "";
              entry.target.style.opacity = "";
              entry.target.style.transform = "";
            });
            cards.forEach((card, i) => {
              const delay = i * 65;
              card.style.transitionDelay = delay + "ms";
              window.requestAnimationFrame(() =>
                window.requestAnimationFrame(() => card.classList.add("is-visible"))
              );
              window.setTimeout(() => { card.style.transitionDelay = ""; }, 480 + delay + 80);
            });
          } else {
            entry.target.classList.add("is-visible");
          }
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
    if (!host || !layers.length || !canAnimate) return;
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
      if (!rafId) rafId = window.requestAnimationFrame(tick);
    });

    host.addEventListener("pointerleave", () => {
      targetX = 0;
      targetY = 0;
      if (!rafId) rafId = window.requestAnimationFrame(tick);
    });
  }

  function bindScrollProgress() {
    const bar = document.querySelector("[data-home-scroll-progress]");
    if (!bar || !canAnimate) return;
    let rafId = 0;
    function draw() {
      rafId = 0;
      const doc = document.documentElement;
      const maxScroll = Math.max(doc.scrollHeight - window.innerHeight, 1);
      const p = Math.min(Math.max(window.scrollY / maxScroll, 0), 1);
      bar.style.transform = `scaleX(${p.toFixed(4)})`;
    }
    function schedule() {
      if (!rafId) rafId = window.requestAnimationFrame(draw);
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    schedule();
  }

  function bindMagneticCta() {
    const elements = Array.from(document.querySelectorAll("[data-home-magnetic]"));
    if (!elements.length || !canAnimate) return;
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
        if (!rafId) rafId = window.requestAnimationFrame(paint);
      });

      el.addEventListener("pointerleave", () => {
        tx = 0;
        ty = 0;
        if (!rafId) rafId = window.requestAnimationFrame(paint);
      });
    });
  }

  function bindWebglHero() {
    // The WebGL module ships its own feature detection (reduced-motion,
    // viewport width, WebGL2 context, FPS guard). We just wait for the intro
    // to finish so we don't compete with the boot canvas for the GPU.
    if (!window.HomeWebgl || typeof window.HomeWebgl.init !== "function") return;
    whenIntroDone(() => {
      try { window.HomeWebgl.init(); } catch (_) { /* fallback layers stay */ }
    });
  }

  function init() {
    markFirstVisitClass();
    bindFirstVisitIntro();
    bindHeroDecrypt();
    bindVariableWeight();
    bindLiveTerminal();
    bindDotGrid();
    bindWebglHero();
    bindTickers();
    bindSectionTints();
    bindViewTransitions();
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
