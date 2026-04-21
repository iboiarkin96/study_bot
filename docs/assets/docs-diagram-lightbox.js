"use strict";

/**
 * Full-screen lightbox for PlantUML diagram images (PNG or SVG).
 * Binds to img.diagram--uml anywhere in the page.
 * Supports wheel zoom, +/- / Reset buttons, and drag-to-pan when zoomed.
 */
(function () {
  var MIN_SCALE = 1;
  var MAX_SCALE = 6;
  var WHEEL_FACTOR = 0.002;
  var BTN_FACTOR = 1.25;

  function createLightbox() {
    var root = document.createElement("div");
    root.id = "docs-diagram-lightbox";
    root.className = "docs-diagram-lightbox";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", "Expanded diagram");
    root.hidden = true;

    var backdrop = document.createElement("button");
    backdrop.type = "button";
    backdrop.className = "docs-diagram-lightbox__backdrop";
    backdrop.setAttribute("aria-label", "Close");

    var panel = document.createElement("div");
    panel.className = "docs-diagram-lightbox__panel";

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "docs-diagram-lightbox__close";
    closeBtn.setAttribute("aria-label", "Close");
    closeBtn.textContent = "×";

    var toolbar = document.createElement("div");
    toolbar.className = "docs-diagram-lightbox__toolbar";
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", "Diagram zoom");

    function makeToolBtn(label, text, title) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "docs-diagram-lightbox__tool-btn";
      b.setAttribute("aria-label", label);
      b.title = title || label;
      b.textContent = text;
      return b;
    }

    var zoomInBtn = makeToolBtn("Zoom in", "+", "Zoom in (or wheel up)");
    var zoomOutBtn = makeToolBtn("Zoom out", "−", "Zoom out (or wheel down)");
    var resetBtn = makeToolBtn("Reset zoom and pan", "Reset", "Fit to window");

    var hint = document.createElement("span");
    hint.className = "docs-diagram-lightbox__hint";
    hint.textContent = "Wheel · +/− keys · drag when zoomed";

    toolbar.appendChild(zoomOutBtn);
    toolbar.appendChild(zoomInBtn);
    toolbar.appendChild(resetBtn);
    toolbar.appendChild(hint);

    var viewport = document.createElement("div");
    viewport.className = "docs-diagram-lightbox__viewport";

    var stage = document.createElement("div");
    stage.className = "docs-diagram-lightbox__stage";

    var img = document.createElement("img");
    img.className = "docs-diagram-lightbox__img";
    img.alt = "";
    img.draggable = false;

    stage.appendChild(img);
    viewport.appendChild(stage);

    panel.appendChild(closeBtn);
    panel.appendChild(toolbar);
    panel.appendChild(viewport);
    root.appendChild(backdrop);
    root.appendChild(panel);
    document.body.appendChild(root);

    return {
      root: root,
      backdrop: backdrop,
      closeBtn: closeBtn,
      panel: panel,
      viewport: viewport,
      stage: stage,
      img: img,
      zoomInBtn: zoomInBtn,
      zoomOutBtn: zoomOutBtn,
      resetBtn: resetBtn,
    };
  }

  var ui = createLightbox();
  var lastFocus = null;

  var scale = 1;
  var tx = 0;
  var ty = 0;

  var panning = false;
  var panStartX = 0;
  var panStartY = 0;
  var panOrigTx = 0;
  var panOrigTy = 0;

  function clampScale(s) {
    if (s < MIN_SCALE) return MIN_SCALE;
    if (s > MAX_SCALE) return MAX_SCALE;
    return s;
  }

  function applyTransform() {
    ui.stage.style.transform =
      "translate(" + tx + "px, " + ty + "px) scale(" + scale + ")";
  }

  function resetView() {
    scale = 1;
    tx = 0;
    ty = 0;
    applyTransform();
    ui.viewport.classList.remove("is-panning");
  }

  function open(src, alt) {
    lastFocus = document.activeElement;
    ui.img.src = src;
    ui.img.alt = alt || "";
    resetView();
    ui.root.hidden = false;
    document.body.classList.add("docs-diagram-lightbox-open");
    ui.closeBtn.focus();
  }

  function close() {
    ui.root.hidden = true;
    ui.img.removeAttribute("src");
    ui.img.alt = "";
    resetView();
    document.body.classList.remove("docs-diagram-lightbox-open");
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
  }

  function zoomAtFactor(factor) {
    scale = clampScale(scale * factor);
    if (scale <= MIN_SCALE + 1e-6) {
      tx = 0;
      ty = 0;
    }
    applyTransform();
  }

  ui.zoomInBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    zoomAtFactor(BTN_FACTOR);
  });
  ui.zoomOutBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    zoomAtFactor(1 / BTN_FACTOR);
  });
  ui.resetBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    resetView();
  });

  ui.panel.addEventListener(
    "wheel",
    function (ev) {
      ev.preventDefault();
      var delta = ev.deltaY;
      var next = scale * (1 - delta * WHEEL_FACTOR);
      scale = clampScale(next);
      if (scale <= MIN_SCALE + 1e-6) {
        tx = 0;
        ty = 0;
      }
      applyTransform();
    },
    { passive: false }
  );

  ui.viewport.addEventListener("mousedown", function (ev) {
    if (ev.button !== 0) return;
    if (scale <= MIN_SCALE + 1e-6) return;
    ev.preventDefault();
    panning = true;
    panStartX = ev.clientX;
    panStartY = ev.clientY;
    panOrigTx = tx;
    panOrigTy = ty;
    ui.viewport.classList.add("is-panning");
  });

  window.addEventListener("mousemove", function (ev) {
    if (!panning) return;
    tx = panOrigTx + (ev.clientX - panStartX);
    ty = panOrigTy + (ev.clientY - panStartY);
    applyTransform();
  });

  window.addEventListener("mouseup", function () {
    if (panning) {
      panning = false;
      ui.viewport.classList.remove("is-panning");
    }
  });

  ui.viewport.addEventListener("touchstart", function (ev) {
    if (ev.touches.length === 1 && scale > MIN_SCALE + 1e-6) {
      var t = ev.touches[0];
      panning = true;
      panStartX = t.clientX;
      panStartY = t.clientY;
      panOrigTx = tx;
      panOrigTy = ty;
      ui.viewport.classList.add("is-panning");
    }
  }, { passive: true });

  ui.viewport.addEventListener("touchmove", function (ev) {
    if (!panning || ev.touches.length !== 1) return;
    var t = ev.touches[0];
    tx = panOrigTx + (t.clientX - panStartX);
    ty = panOrigTy + (t.clientY - panStartY);
    applyTransform();
    ev.preventDefault();
  }, { passive: false });

  ui.viewport.addEventListener("touchend", function () {
    panning = false;
    ui.viewport.classList.remove("is-panning");
  });

  ui.viewport.addEventListener("touchcancel", function () {
    panning = false;
    ui.viewport.classList.remove("is-panning");
  });

  document.addEventListener("keydown", function (ev) {
    if (ui.root.hidden) return;
    if (ev.key === "Escape") {
      ev.preventDefault();
      close();
      return;
    }
    if (ev.key === "+" || ev.key === "=") {
      ev.preventDefault();
      zoomAtFactor(BTN_FACTOR);
    }
    if (ev.key === "-" || ev.key === "_") {
      ev.preventDefault();
      zoomAtFactor(1 / BTN_FACTOR);
    }
    if (ev.key === "0" && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      resetView();
    }
  });

  ui.backdrop.addEventListener("click", close);
  ui.closeBtn.addEventListener("click", close);

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("img.diagram--uml").forEach(function (diagramImg) {
      if (diagramImg.closest(".diagram-uml-wrap")) {
        return;
      }
      var wrap = document.createElement("div");
      wrap.className = "diagram-uml-wrap";
      diagramImg.parentNode.insertBefore(wrap, diagramImg);
      wrap.appendChild(diagramImg);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "diagram-expand-btn";
      btn.setAttribute("aria-label", "Expand diagram");
      btn.textContent = "Expand";
      btn.addEventListener("click", function () {
        open(diagramImg.currentSrc || diagramImg.src, diagramImg.alt);
      });
      wrap.appendChild(btn);
    });
  });
})();
