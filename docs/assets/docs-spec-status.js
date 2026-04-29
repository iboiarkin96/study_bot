"use strict";

/**
 * Spec lifecycle status card.
 *
 * Single source of truth: `data-spec-status` attribute on `<body>`.
 * Allowed values: draft · in-review · approved · implemented · deprecated.
 *
 * For every element with the `data-spec-status-mount` attribute the script:
 *   - applies the matching tone class on the element (`spec-status-pill` +
 *     `spec-status-pill--<status>`),
 *   - injects an emoji glyph and a Mixed-case label into the element,
 *   - inserts a `<details class="spec-status-help">` panel right after the pill
 *     so the reader always has an explanation of how to change the status.
 *
 * No CSS-only `::before` / `::after` content tricks: the visible label lives in
 * real DOM text, so it is selectable, screen-reader-accessible, and survives
 * "save page as text".
 */
(function () {
  /**
   * Lifecycle stages, in chronological order. Each entry contains:
   *   - status:    the canonical attribute value used on `<body>`,
   *   - emoji:     glyph shown on the pill,
   *   - label:     human-readable (Mixed-case) text,
   *   - tone:      CSS tone suffix (matches `spec-status-pill--<tone>`),
   *   - blurb:     one-sentence "what it means" for the help panel.
   */
  const STAGES = [
    { status: "draft",       emoji: "📝", label: "Draft",       tone: "draft",       blurb: "Authoring in progress. Not yet implementable." },
    { status: "in-review",   emoji: "👀", label: "In review",   tone: "in-review",   blurb: "Submitted for peer review. Wording can change; contract surface is frozen." },
    { status: "approved",    emoji: "✅", label: "Approved",    tone: "approved",    blurb: "Reviewers signed off. Implementation may start." },
    { status: "implemented", emoji: "⭐", label: "Implemented", tone: "implemented", blurb: "Live in production. Additive changes only without a new ADR." },
    { status: "deprecated",  emoji: "🚫", label: "Deprecated",  tone: "deprecated",  blurb: "Sunset announced. New clients should not adopt." },
  ];

  /**
   * Auxiliary state used only on the spec-template page itself; surfaces a
   * neutral "Template" pill so the metadata strip is never empty there.
   */
  const TEMPLATE_STAGE = {
    status: "template",
    emoji: "📐",
    label: "Template",
    tone: "draft",
    blurb: "Authoring scaffold; copy this page to start a real operation spec.",
  };

  const STAGE_BY_STATUS = new Map(STAGES.map((s) => [s.status, s]));
  STAGE_BY_STATUS.set(TEMPLATE_STAGE.status, TEMPLATE_STAGE);

  function findStage(rawStatus) {
    const key = String(rawStatus || "").trim().toLowerCase();
    return STAGE_BY_STATUS.get(key) || null;
  }

  /** Build the pill body: <span emoji /><span label />. */
  function buildPillContent(stage) {
    const fragment = document.createDocumentFragment();
    const emoji = document.createElement("span");
    emoji.className = "spec-status-pill__emoji";
    emoji.setAttribute("aria-hidden", "true");
    emoji.textContent = stage.emoji;
    const label = document.createElement("span");
    label.className = "spec-status-pill__label";
    label.textContent = stage.label;
    fragment.appendChild(emoji);
    fragment.appendChild(label);
    return fragment;
  }

  /** Construct one row of the lifecycle table inside the help panel. */
  function buildLifecycleRow(stage, currentStatus) {
    const tr = document.createElement("tr");
    if (stage.status === currentStatus) {
      tr.classList.add("spec-status-help__row--current");
    }
    const cellPill = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `spec-status-pill spec-status-pill--${stage.tone}`;
    pill.appendChild(buildPillContent(stage));
    cellPill.appendChild(pill);

    const cellValue = document.createElement("td");
    const code = document.createElement("code");
    code.textContent = stage.status;
    cellValue.appendChild(code);

    const cellBlurb = document.createElement("td");
    cellBlurb.textContent = stage.blurb;

    tr.appendChild(cellPill);
    tr.appendChild(cellValue);
    tr.appendChild(cellBlurb);
    return tr;
  }

  /** Build the always-available help panel rendered after the pill. */
  function buildHelp(currentStatus) {
    const details = document.createElement("details");
    details.className = "spec-status-help";

    const summary = document.createElement("summary");
    summary.className = "spec-status-help__summary";
    summary.setAttribute("aria-label", "How to change the spec status");
    const summaryEmoji = document.createElement("span");
    summaryEmoji.className = "spec-status-help__summary-icon";
    summaryEmoji.setAttribute("aria-hidden", "true");
    summaryEmoji.textContent = "💡";
    const summaryText = document.createElement("span");
    summaryText.className = "spec-status-help__summary-text";
    summaryText.textContent = "How to change";
    summary.appendChild(summaryEmoji);
    summary.appendChild(summaryText);

    const panel = document.createElement("div");
    panel.className = "spec-status-help__panel";

    const intro = document.createElement("p");
    intro.className = "spec-status-help__intro";
    intro.innerHTML =
      'Set <code>data-spec-status</code> on <code>&lt;body&gt;</code> to one of the values below. ' +
      'The pill above and the lint check follow the attribute — no badge text to keep in sync.';
    panel.appendChild(intro);

    const table = document.createElement("table");
    table.className = "spec-status-help__table";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th scope=\"col\">Stage</th><th scope=\"col\">Attribute value</th><th scope=\"col\">When to use</th></tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const stage of STAGES) {
      tbody.appendChild(buildLifecycleRow(stage, currentStatus));
    }
    table.appendChild(tbody);
    panel.appendChild(table);

    const example = document.createElement("p");
    example.className = "spec-status-help__example small";
    example.innerHTML =
      'Example: <code>&lt;body data-spec-status="approved"&gt;</code> renders the “Approved” pill.';
    panel.appendChild(example);

    details.appendChild(summary);
    details.appendChild(panel);

    bindOutsideClose(details, summary);
    return details;
  }

  /** Close the help on Escape and outside-click — same UX as the ADR status log. */
  function bindOutsideClose(details, summary) {
    const closeOnOutside = (event) => {
      if (!details.open) return;
      const target = event.target;
      if (target instanceof Node && details.contains(target)) return;
      details.open = false;
    };
    const closeOnEscape = (event) => {
      if (event.key !== "Escape" || !details.open) return;
      details.open = false;
      summary.focus();
    };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
  }

  function hydrate() {
    const body = document.body;
    if (!body) return;
    const stage = findStage(body.getAttribute("data-spec-status"));
    if (!stage) return;
    const mounts = document.querySelectorAll("[data-spec-status-mount]");
    if (mounts.length === 0) return;
    for (const el of mounts) {
      el.classList.add("spec-status-pill", `spec-status-pill--${stage.tone}`);
      el.setAttribute("role", "status");
      el.setAttribute("aria-label", `Spec status: ${stage.label}`);
      el.replaceChildren(buildPillContent(stage));
      const help = buildHelp(stage.status);
      el.insertAdjacentElement("afterend", help);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hydrate);
  } else {
    hydrate();
  }
})();
