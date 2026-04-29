"use strict";

/* ── ETR Study API — Home hero WebGL2 flowfield ────────────────────────────
   A fullscreen-quad fragment shader that paints a soft, animated curl-noise
   flowfield over the hero background. Mouse warps the field locally; scroll
   progress (0..1 across the hero) rotates and tightens it, so the scene
   morphs as the user reads down the page.

   Failure modes (any of these → no canvas, existing dotgrid/orbs remain):
     • prefers-reduced-motion: reduce
     • viewport narrower than ~720px (battery)
     • no WebGL2 context
     • avg FPS < 42 for 2s (teardown after first second of measurement)
*/

(function () {
  const TARGET_FPS_FLOOR = 42;
  const FPS_GUARD_MS = 2000;
  const MIN_VIEWPORT_PX = 720;

  // Public init — orchestrator (home-landing.js) calls this after intro is done.
  window.HomeWebgl = window.HomeWebgl || {};
  window.HomeWebgl.init = init;

  function init() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (window.innerWidth < MIN_VIEWPORT_PX) return;

    const canvas = document.querySelector("[data-home-webgl]");
    const host = document.querySelector(".home-hero");
    if (!canvas || !host) return;

    const gl = canvas.getContext("webgl2", {
      alpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      premultipliedAlpha: true,
      powerPreference: "high-performance",
    });
    if (!gl) return;

    const program = buildProgram(gl);
    if (!program) return;

    const loc = {
      uTime:      gl.getUniformLocation(program, "uTime"),
      uRes:       gl.getUniformLocation(program, "uRes"),
      uMouse:     gl.getUniformLocation(program, "uMouse"),
      uScroll:    gl.getUniformLocation(program, "uScroll"),
      uColorA:    gl.getUniformLocation(program, "uColorA"),
      uColorB:    gl.getUniformLocation(program, "uColorB"),
      uColorC:    gl.getUniformLocation(program, "uColorC"),
      uTheme:     gl.getUniformLocation(program, "uTheme"),
      uIntensity: gl.getUniformLocation(program, "uIntensity"),
    };

    // Fullscreen triangle (one tri covers the viewport, no VAO needed).
    const vbo = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(program, "aPos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    gl.useProgram(program);

    // ── State ────────────────────────────────────────────────────────────
    let dpr = clampDpr();
    let width = 0;
    let height = 0;
    let mouseX = 0.5;
    let mouseY = 0.5;
    let mouseTargetX = 0.5;
    let mouseTargetY = 0.5;
    let scroll = 0;
    let scrollTarget = 0;
    let intensity = 0;            // fade-in 0..1
    let intensityTarget = 1;
    let theme = readThemeFlag();  // 1.0 dark, 0.0 light
    let colors = readColors(theme);
    let running = false;
    let rafId = 0;
    let startTs = 0;
    let lastTs = 0;
    let disposed = false;

    // FPS guard
    let frames = 0;
    let measureStart = 0;
    let guardElapsed = 0;
    let guardActive = true;

    function clampDpr() {
      return Math.min(window.devicePixelRatio || 1, 1.5);
    }

    function readThemeFlag() {
      const root = document.documentElement;
      const attr = root.getAttribute("data-theme");
      if (attr === "dark") return 1;
      if (attr === "light") return 0;
      return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? 1 : 0;
    }

    function hexToRgb(hex) {
      const m = hex.replace("#", "");
      const v = m.length === 3
        ? m.split("").map((c) => parseInt(c + c, 16))
        : [parseInt(m.slice(0, 2), 16), parseInt(m.slice(2, 4), 16), parseInt(m.slice(4, 6), 16)];
      return [v[0] / 255, v[1] / 255, v[2] / 255];
    }

    function readCssVar(name, fallback) {
      const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      if (!v) return fallback;
      if (v.startsWith("#")) return hexToRgb(v);
      const m = v.match(/rgba?\(([^)]+)\)/);
      if (m) {
        const parts = m[1].split(",").map((s) => parseFloat(s.trim()));
        return [parts[0] / 255, parts[1] / 255, parts[2] / 255];
      }
      return fallback;
    }

    function readColors(themeFlag) {
      // "Sapphire" palette — restrained indigo family, decoupled from
      // --accent so brand blue stays exclusive to CTAs. Tuned for premium
      // restraint (Stripe / Linear ambient layer), not screensaver pop.
      //   A = deep indigo  (#3730a3) — base field tone
      //   B = mid  indigo  (#6366f1) — bands + soft mouse halo
      //   C = pale indigo  (#c7d2fe) — luminous highlights in deep field
      if (themeFlag > 0.5) {
        return {
          a: [0.216, 0.188, 0.639],   // #3730a3 indigo-800
          b: [0.388, 0.400, 0.945],   // #6366f1 indigo-500
          c: [0.780, 0.824, 0.996],   // #c7d2fe indigo-200
        };
      }
      return {
        // Light theme: deeper, slightly cooler indigos so the multiply
        // blend reads as a quiet tinted shadow over the white surface.
        a: [0.184, 0.169, 0.494],     // muted indigo-900
        b: [0.263, 0.220, 0.639],     // indigo-700
        c: [0.435, 0.408, 0.706],     // dusky periwinkle
      };
    }

    function resize() {
      const rect = host.getBoundingClientRect();
      width = Math.max(1, Math.ceil(rect.width));
      height = Math.max(1, Math.ceil(rect.height));
      dpr = clampDpr();
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      gl.viewport(0, 0, canvas.width, canvas.height);
    }

    function onPointerMove(event) {
      const rect = host.getBoundingClientRect();
      mouseTargetX = (event.clientX - rect.left) / Math.max(1, rect.width);
      mouseTargetY = 1 - (event.clientY - rect.top) / Math.max(1, rect.height);
    }

    function onPointerLeave() {
      mouseTargetX = 0.5;
      mouseTargetY = 0.5;
    }

    function readScrollProgress() {
      const rect = host.getBoundingClientRect();
      // 0 when hero fully in view at top, 1 when its bottom edge has passed
      // the top of the viewport.
      const total = rect.height;
      if (total <= 0) return 0;
      const traveled = Math.max(0, -rect.top);
      return Math.max(0, Math.min(1, traveled / total));
    }

    function tick(ts) {
      rafId = 0;
      if (disposed) return;
      if (!startTs) startTs = ts;
      const dt = lastTs ? Math.min(0.05, (ts - lastTs) / 1000) : 0.016;
      lastTs = ts;

      // Smooth mouse + scroll + intensity. Lower coefficients = the field
      // glides into position; restrained, not reactive.
      mouseX += (mouseTargetX - mouseX) * Math.min(1, dt * 3.2);
      mouseY += (mouseTargetY - mouseY) * Math.min(1, dt * 3.2);
      scrollTarget = readScrollProgress();
      scroll += (scrollTarget - scroll) * Math.min(1, dt * 3.0);
      intensity += (intensityTarget - intensity) * Math.min(1, dt * 2.0);

      gl.uniform1f(loc.uTime, (ts - startTs) / 1000);
      gl.uniform2f(loc.uRes, canvas.width, canvas.height);
      gl.uniform2f(loc.uMouse, mouseX, mouseY);
      gl.uniform1f(loc.uScroll, scroll);
      gl.uniform1f(loc.uIntensity, intensity);
      gl.uniform1f(loc.uTheme, theme);
      gl.uniform3f(loc.uColorA, colors.a[0], colors.a[1], colors.a[2]);
      gl.uniform3f(loc.uColorB, colors.b[0], colors.b[1], colors.b[2]);
      gl.uniform3f(loc.uColorC, colors.c[0], colors.c[1], colors.c[2]);

      gl.drawArrays(gl.TRIANGLES, 0, 3);

      // ── FPS guard ────────────────────────────────────────────────────
      if (guardActive) {
        frames++;
        if (!measureStart) measureStart = ts;
        guardElapsed = ts - measureStart;
        if (guardElapsed > 1000) {
          const fps = (frames * 1000) / guardElapsed;
          if (fps < TARGET_FPS_FLOOR && guardElapsed > FPS_GUARD_MS) {
            tearDown("fps-guard");
            return;
          }
          if (guardElapsed > FPS_GUARD_MS && fps >= TARGET_FPS_FLOOR) {
            guardActive = false; // passed: stop counting forever
          }
        }
      }

      if (running) rafId = window.requestAnimationFrame(tick);
    }

    function start() {
      if (running || disposed) return;
      running = true;
      lastTs = 0;
      if (!rafId) rafId = window.requestAnimationFrame(tick);
    }

    function stop() {
      running = false;
      if (rafId) {
        window.cancelAnimationFrame(rafId);
        rafId = 0;
      }
    }

    function tearDown(reason) {
      if (disposed) return;
      disposed = true;
      stop();
      try {
        const ext = gl.getExtension("WEBGL_lose_context");
        if (ext) ext.loseContext();
      } catch (_) { /* noop */ }
      window.removeEventListener("resize", onResize);
      host.removeEventListener("pointermove", onPointerMove);
      host.removeEventListener("pointerleave", onPointerLeave);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", onPageHide);
      themeObs.disconnect();
      canvas.remove();
      host.removeAttribute("data-webgl-active");
      // Reason is intentionally not surfaced to the user — fallback layers
      // (dotgrid, orbs, grid) remain visible because we never hid them at the
      // CSS level; we only dimmed via the host attribute we just removed.
      void reason;
    }

    function onResize() {
      resize();
    }

    function onVisibility() {
      if (document.hidden) stop();
      else start();
    }

    function onPageHide() {
      tearDown("pagehide");
    }

    // Theme observer — recolor on toggle without a re-init
    const themeObs = new MutationObserver(() => {
      theme = readThemeFlag();
      colors = readColors(theme);
    });
    themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    resize();
    window.addEventListener("resize", onResize, { passive: true });
    host.addEventListener("pointermove", onPointerMove, { passive: true });
    host.addEventListener("pointerleave", onPointerLeave, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", onPageHide);

    host.setAttribute("data-webgl-active", "");
    start();
  }

  /* ── GL helpers ─────────────────────────────────────────────────────── */

  function compile(gl, type, source) {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, source);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      // Surface to console only — silent on the page.
      // eslint-disable-next-line no-console
      console.warn("[home-webgl] shader compile failed:", gl.getShaderInfoLog(sh));
      gl.deleteShader(sh);
      return null;
    }
    return sh;
  }

  function buildProgram(gl) {
    const vs = compile(gl, gl.VERTEX_SHADER, VERT_SRC);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG_SRC);
    if (!vs || !fs) return null;
    const p = gl.createProgram();
    gl.attachShader(p, vs);
    gl.attachShader(p, fs);
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
      // eslint-disable-next-line no-console
      console.warn("[home-webgl] link failed:", gl.getProgramInfoLog(p));
      return null;
    }
    return p;
  }

  /* ── Shaders ────────────────────────────────────────────────────────── */

  const VERT_SRC = `#version 300 es
in vec2 aPos;
out vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

  // 2D simplex noise (Ashima-style, public domain) → fbm → curl-like
  // displacement. Renders a soft luminous flowfield with iridescent banding
  // and a localized mouse glow; vignette keeps it ambient.
  const FRAG_SRC = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform float uTime;
uniform vec2  uRes;
uniform vec2  uMouse;       // 0..1 in hero space, y-up
uniform float uScroll;      // 0..1 across hero scroll-out
uniform float uIntensity;   // 0..1 fade-in
uniform float uTheme;       // 1 dark, 0 light
uniform vec3  uColorA;
uniform vec3  uColorB;
uniform vec3  uColorC;

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec3 permute(vec3 x) { return mod289(((x * 34.0) + 1.0) * x); }

float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187,
                      0.366025403784439,
                     -0.577350269189626,
                      0.024390243902439);
  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod289(i);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                          + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0, x0),
                          dot(x12.xy, x12.xy),
                          dot(x12.zw, x12.zw)), 0.0);
  m = m * m; m = m * m;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
  vec3 g;
  g.x  = a0.x  * x0.x  + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

float fbm(vec2 p) {
  float a = 0.5;
  float v = 0.0;
  for (int i = 0; i < 5; i++) {
    v += a * snoise(p);
    p = mat2(1.6, 1.2, -1.2, 1.6) * p;
    a *= 0.5;
  }
  return v;
}

mat2 rot(float a) {
  float c = cos(a), s = sin(a);
  return mat2(c, -s, s, c);
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes.xy;
  vec2 p  = uv;
  // Aspect-corrected coords for noise (so rotation reads circular)
  vec2 q  = (gl_FragCoord.xy - 0.5 * uRes.xy) / min(uRes.x, uRes.y);

  // Mouse warp: subtle local pull — the field acknowledges the cursor
  // without chasing it. Aspect corrected.
  vec2 m  = (uMouse - 0.5) * vec2(uRes.x / uRes.y, 1.0);
  vec2 toM = m - q;
  float md = length(toM);
  vec2 warp = toM * exp(-md * 4.5) * 0.07;

  // Scroll: slow rotation + gentle zoom. Reads as the surface slowly
  // settling, not as a kinetic transition.
  float ang  = uScroll * 0.28;
  float zoom = 1.0 + uScroll * 0.18;
  vec2 nq = rot(ang) * q * zoom + warp;

  // Slowed time — a noble drift, ~2x slower than before.
  float t = uTime * 0.035;

  // Two-stage fbm: domain warp produces curl-like swirls without sampling
  // gradients — cheap, reads as fluid. Lower frequency = larger, calmer
  // shapes.
  vec2 d1 = vec2(fbm(nq * 1.1 + vec2(t, -t * 0.7)),
                 fbm(nq * 1.1 + vec2(-t * 0.6, t)));
  float n = fbm(nq * 1.25 + d1 * 1.0 + vec2(0.0, t * 0.5));

  // Wider, slower bands — fewer ridges per screen, no shimmering.
  float bands = 0.5 + 0.5 * sin(n * 6.2831853 * 0.85 + uTime * 0.16);

  // Color mix: A→B by bands, then bias toward C in deep field. Wider
  // smoothstep windows = softer transitions, less ridge contrast.
  vec3 col = mix(uColorA, uColorB, smoothstep(0.05, 0.95, bands));
  col = mix(col, uColorC, smoothstep(0.62, 1.10, n * 0.5 + 0.5));

  // Restrained mouse halo — barely a breath of light, not a flashlight.
  float glow = exp(-md * 6.0);
  col += uColorC * glow * 0.18;

  // Soft top-down vignette so the field never overpowers the H1 zone.
  float vignTop = smoothstep(0.0, 0.60, uv.y);
  float vignRad = smoothstep(0.92, 0.22, length(uv - vec2(0.5, 0.48)));
  float mask = vignTop * vignRad;

  // Lower alphas across the board — ambient mist, not a poster.
  float darkAlpha  = clamp(0.22 + 0.09 * bands, 0.0, 0.50) * mask;
  float lightAlpha = clamp(0.11 + 0.05 * bands, 0.0, 0.32) * mask;
  float alpha = mix(lightAlpha, darkAlpha, uTheme) * uIntensity;

  // Slight luminance compression for light theme so it stays readable
  col = mix(col * 0.78 + vec3(0.04), col, uTheme);

  // Premultiplied alpha
  fragColor = vec4(col * alpha, alpha);
}`;
})();
