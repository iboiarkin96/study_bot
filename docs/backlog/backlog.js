(() => {
  const GROUP_PREVIEW_LIMIT = 10;
  const items = Array.from(document.querySelectorAll(".backlog-item"));
  if (!items.length) {
    return;
  }

  const groupLabel = {
    frontend: "Frontend",
    backend: "Backend",
    devops: "DevOps",
    docs: "Docs",
  };
  const allowedGroups = new Set(["frontend", "backend", "devops", "docs"]);
  const allowedTags = new Set(["bug", "feature", "research", "tech-debt"]);
  const priorityBaseHours = {
    P0: 28,
    P1: 18,
    P2: 11,
    P3: 7,
  };
  const groupComplexityMultiplier = {
    frontend: 1.0,
    backend: 1.2,
    devops: 1.3,
    docs: 0.8,
  };
  const llmAssistFactor = 0.78;
  const seniorFocusHoursPerDay = 5;
  const estimateScaleDivisor = 3;
  const SLA_BLOCKED_THRESHOLD_DAYS = 5;
  const FLOW_HEALTH_PERIOD_DAYS = 14;
  const ETA_PRESSURE_MAX_DAYS = 3;
  const DAY_MS = 24 * 60 * 60 * 1000;

  const state = {
    group: "all",
    priorities: new Set(),
    taskTypes: new Set(),
    risks: new Set(),
    confidences: new Set(),
    statuses: new Set(),
    search: "",
    quickPreset: "all",
    viewMode: "board",
  };
  const prioritySortRank = {
    P1: 2,
    P2: 3,
    P3: 4,
    P0: 5,
  };
  const statusSortRank = {
    todo: 0,
    "in-progress": 1,
    blocked: 2,
    done: 3,
    rejected: 4,
  };
  const statusPresentation = {
    todo: { label: "To do", className: "status-pill--todo" },
    "in-progress": { label: "In progress", className: "status-pill--in-progress" },
    done: { label: "Done", className: "status-pill--done" },
    blocked: { label: "Blocked", className: "status-pill--blocked" },
    rejected: { label: "Rejected", className: "status-pill--rejected" },
  };
  const reorderTopSections = () => {
    const main = document.querySelector("main.container");
    const intelligence = document.getElementById("backlog-intelligence");
    const groups = document.getElementById("backlog-blocks");
    const allTasks = document.getElementById("all-tasks-section");
    const cockpit = document.getElementById("backlog-cockpit");
    if (!main || !cockpit || !intelligence || !groups || !allTasks) {
      return;
    }
    main.insertBefore(cockpit, intelligence);
    main.insertBefore(intelligence, groups);
    main.insertBefore(groups, allTasks);
  };
  const taskListMount = document.getElementById("backlog-task-list");
  const setListLoadingState = (isLoading) => {
    if (!taskListMount) {
      return;
    }
    taskListMount.classList.toggle("is-loading", isLoading);
    if (isLoading && !taskListMount.querySelector(".backlog-skeleton")) {
      taskListMount.innerHTML = `
        <div class="backlog-skeleton" aria-hidden="true">
          <article class="backlog-skeleton-card"></article>
          <article class="backlog-skeleton-card"></article>
          <article class="backlog-skeleton-card"></article>
        </div>
      `;
    }
  };
  const ensureEmptyState = () => {
    if (!taskListMount) {
      return null;
    }
    let emptyState = document.getElementById("backlog-task-list-empty");
    if (!emptyState) {
      emptyState = document.createElement("p");
      emptyState.id = "backlog-task-list-empty";
      emptyState.className = "backlog-empty-state";
      emptyState.textContent = "No tasks matching current filter.";
      emptyState.hidden = true;
      taskListMount.insertAdjacentElement("beforebegin", emptyState);
    }
    return emptyState;
  };
  const ensureValidationMount = () => {
    const cockpit = document.getElementById("backlog-cockpit");
    if (!cockpit) {
      return null;
    }
    let mount = document.getElementById("backlog-validation-alert");
    if (!mount) {
      mount = document.createElement("section");
      mount.id = "backlog-validation-alert";
      mount.className = "backlog-validation-alert";
      mount.hidden = true;
      cockpit.appendChild(mount);
    }
    return mount;
  };
  const mountTaskList = () => {
    if (!taskListMount) {
      return;
    }
    setListLoadingState(false);
    taskListMount.innerHTML = "";
    items.forEach((item) => {
      taskListMount.appendChild(item);
    });
  };
  const renderIntelligencePanel = () => {
    const attentionMount = document.getElementById("backlog-attention-list");
    const bottlenecksMount = document.getElementById("backlog-bottlenecks-list");
    const reprioMount = document.getElementById("backlog-reprioritization-list");
    if (!attentionMount || !bottlenecksMount || !reprioMount) {
      return;
    }
    const visible = items.filter((item) => !item.hidden);
    const openP0 = visible.filter((item) => isOpenStatus(readStatus(item)) && (item.dataset.priority || "").trim() === "P0");
    const blocked = visible.filter((item) => readStatus(item) === "blocked");
    const inProgress = visible.filter((item) => readStatus(item) === "in-progress");
    const done = visible.filter((item) => readStatus(item) === "done");
    const byGroup = ["frontend", "backend", "devops", "docs"]
      .map((group) => ({
        group,
        open: visible.filter((item) => normalize(item.dataset.group) === group && isOpenStatus(readStatus(item))).length,
      }))
      .sort((a, b) => b.open - a.open)
      .slice(0, 3);

    const attentionItems = [
      `Open P0 now: ${openP0.length}`,
      `Blocked right now: ${blocked.length}`,
      `In progress load: ${inProgress.length}`,
    ];
    const bottleneckItems = byGroup.map((entry) => `${groupLabel[entry.group] || entry.group}: ${entry.open} open tasks`);
    const reprioItems = [
      blocked.length > 0
        ? `Escalate ${Math.min(blocked.length, 3)} blocked tasks to unblock sprint flow`
        : "No blockers detected; keep current sequencing",
      openP0.length > 0
        ? `Keep P0 focus lane strict (${openP0.length} active)`
        : "Consider pulling one high-value P1 into active execution",
      done.length < inProgress.length
        ? "Too many parallel tasks; reduce WIP and finish oldest in-progress first"
        : "Delivery flow is stable; maintain current WIP limits",
    ];

    const renderList = (mount, entries) => {
      mount.innerHTML = entries.map((entry) => `<li>${entry}</li>`).join("");
    };
    renderList(attentionMount, attentionItems);
    renderList(bottlenecksMount, bottleneckItems.length ? bottleneckItems : ["No strong bottlenecks in current scope"]);
    renderList(reprioMount, reprioItems);
  };

  const numberCards = () => {
    items.forEach((item, index) => {
      const heading = item.querySelector("h2");
      if (!heading) {
        return;
      }
      const existing = heading.querySelector(".backlog-order");
      if (existing) {
        existing.remove();
      }
      const marker = document.createElement("span");
      marker.className = "backlog-order";
      marker.textContent = `${index + 1}.`;
      heading.insertBefore(marker, heading.firstChild);
    });
  };

  const normalizeHeadingLayout = () => {
    items.forEach((item) => {
      const heading = item.querySelector("h2");
      if (!heading || heading.querySelector(".backlog-heading-main")) {
        return;
      }
      const orderMarker = heading.querySelector(".backlog-order");
      const statusPill = heading.querySelector(".status-pill");
      const nodes = Array.from(heading.childNodes);

      const main = document.createElement("span");
      main.className = "backlog-heading-main";

      if (orderMarker) {
        main.appendChild(orderMarker);
      }

      let firstContentAdded = false;
      nodes.forEach((node) => {
        if (node === orderMarker || node === statusPill) {
          return;
        }
        if (node.nodeType === Node.TEXT_NODE) {
          const text = node.textContent || "";
          const normalized = firstContentAdded ? text : text.trimStart();
          if (!normalized.trim()) {
            return;
          }
          node.textContent = normalized;
        }
        firstContentAdded = true;
        main.appendChild(node);
      });

      heading.innerHTML = "";
      heading.appendChild(main);
      if (statusPill) {
        heading.appendChild(statusPill);
      }
    });
  };


  const normalize = (value) => (value || "").trim().toLowerCase();
  const searchableTextFor = (item) => normalize(item.textContent || "");
  const parseIsoDate = (value) => {
    if (!value) {
      return null;
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };
  const daysSince = (date) => {
    if (!date) {
      return null;
    }
    const diff = Date.now() - date.getTime();
    return diff >= 0 ? Math.floor(diff / DAY_MS) : null;
  };

  const readStatus = (item) => {
    const value = normalize(item.dataset.status);
    if (value) {
      return value;
    }
    const pill = item.querySelector(".status-pill");
    if (!pill) {
      return "";
    }
    if (pill.classList.contains("status-pill--todo")) return "todo";
    if (pill.classList.contains("status-pill--in-progress")) return "in-progress";
    if (pill.classList.contains("status-pill--blocked")) return "blocked";
    if (pill.classList.contains("status-pill--done")) return "done";
    if (pill.classList.contains("status-pill--rejected")) return "rejected";
    return "";
  };

  const syncStatusPills = () => {
    items.forEach((item) => {
      const heading = item.querySelector("h2");
      if (!heading) {
        return;
      }
      const status = normalize(item.dataset.status);
      const presentation = statusPresentation[status] || { label: status || "To do", className: "status-pill--todo" };

      let pill = heading.querySelector(".status-pill");
      if (!pill) {
        pill = document.createElement("span");
        heading.appendChild(pill);
      }
      pill.className = "status-pill";
      pill.classList.add(presentation.className);
      pill.textContent = presentation.label;
      pill.setAttribute("aria-label", `Status: ${presentation.label}`);
    });
  };

  const itemNumber = (item) => {
    const match = (item.id || "").match(/item-(\d+)/i);
    return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
  };

  const readTags = (item) =>
    normalize(item.dataset.tags)
      .split(/\s+/)
      .filter(Boolean);

  const resolveRisk = (item) => {
    const explicit = normalize(item.dataset.risk);
    if (explicit === "high" || explicit === "medium" || explicit === "low") {
      return explicit;
    }
    const priority = (item.dataset.priority || "").trim();
    return priority === "P0" && isOpenStatus(readStatus(item)) ? "high" : "medium";
  };

  const resolveConfidence = (item) => {
    const explicit = normalize(item.dataset.confidence);
    if (explicit === "high" || explicit === "medium" || explicit === "low") {
      return explicit;
    }
    return "medium";
  };

  const readDtSectionText = (item, matcher) => {
    const dt = Array.from(item.querySelectorAll("dt")).find((node) => matcher.test(node.textContent || ""));
    const dd = dt?.nextElementSibling;
    return dd?.textContent?.replace(/\s+/g, " ").trim() || "";
  };

  const readDtPairByNumber = (item, number) => {
    const dt = Array.from(item.querySelectorAll("dt")).find((node) =>
      new RegExp(`^\\s*${number}\\)`).test((node.textContent || "").trim()),
    );
    const dd = dt?.nextElementSibling;
    return {
      title: dt?.textContent?.trim() || "",
      text: dd?.textContent?.replace(/\s+/g, " ").trim() || "",
      html: dt && dd ? `<dt>${dt.innerHTML}</dt><dd>${dd.innerHTML}</dd>` : "",
    };
  };

  const hasAnyTag = (item, expectedTags) => {
    const tags = readTags(item);
    return expectedTags.some((tag) => tags.includes(tag));
  };

  const priorityBucketRank = (item, status, priority) => {
    if (isOpenStatus(status) && priority === "P0") {
      return 0;
    }
    if (hasAnyTag(item, ["bug"])) {
      return 1;
    }
    return prioritySortRank[priority] ?? 6;
  };

  const sortItemsInPlace = () => {
    items.sort((a, b) => {
      const statusA = readStatus(a);
      const statusB = readStatus(b);
      const priorityA = (a.dataset.priority || "").trim();
      const priorityB = (b.dataset.priority || "").trim();

      const openRankA = isOpenStatus(statusA) ? 0 : 1;
      const openRankB = isOpenStatus(statusB) ? 0 : 1;
      if (openRankA !== openRankB) {
        return openRankA - openRankB;
      }

      const bucketA = priorityBucketRank(a, statusA, priorityA);
      const bucketB = priorityBucketRank(b, statusB, priorityB);
      if (bucketA !== bucketB) {
        return bucketA - bucketB;
      }

      const statusRankA = statusSortRank[statusA] ?? 99;
      const statusRankB = statusSortRank[statusB] ?? 99;
      if (statusRankA !== statusRankB) {
        return statusRankA - statusRankB;
      }

      return itemNumber(a) - itemNumber(b);
    });
  };

  const decorateCards = () => {
    items.forEach((item) => {
      const tags = normalize(item.dataset.tags)
        .split(/\s+/)
        .filter(Boolean);
      const summary = document.createElement("div");
      summary.className = "backlog-item-summary";
      const riskConfidenceRow = document.createElement("div");
      riskConfidenceRow.className = "backlog-item-risk-confidence";

      const group = normalize(item.dataset.group);
      if (group) {
        const groupBadge = document.createElement("span");
        groupBadge.className = "backlog-chip backlog-chip--group";
        groupBadge.textContent = groupLabel[group] || group;
        summary.appendChild(groupBadge);
      }

      tags.forEach((tag) => {
        const chip = document.createElement("span");
        chip.className = "backlog-chip";
        chip.textContent = tag;
        summary.appendChild(chip);
      });

      const risk = resolveRisk(item);
      const confidence = resolveConfidence(item);
      const riskChip = document.createElement("span");
      riskChip.className = `backlog-chip backlog-chip--risk backlog-chip--risk-${risk}`;
      riskChip.textContent = `Risk: ${risk}`;
      riskConfidenceRow.appendChild(riskChip);
      const confidenceChip = document.createElement("span");
      confidenceChip.className = "backlog-chip backlog-chip--confidence";
      confidenceChip.textContent = `Confidence: ${confidence}`;
      riskConfidenceRow.appendChild(confidenceChip);

      if (summary.childElementCount) {
        const h2 = item.querySelector("h2");
        h2?.insertAdjacentElement("afterend", summary);
        summary.insertAdjacentElement("afterend", riskConfidenceRow);
      }
    });
  };

  const renderTaskCardWorkspace = () => {
    items.forEach((item) => {
      const heading = item.querySelector("h2");
      const details = item.querySelector("dl");
      if (!heading || !details || item.querySelector(".backlog-task-meta")) {
        return;
      }

      const owner = item.dataset.owner || "Ivan Boyarkin";
      const createdAt = parseIsoDate(item.dataset.createdAt || "");
      const ageDays = Number.parseInt(item.dataset.ageDays || "", 10);
      const resolvedAge = Number.isFinite(ageDays) ? ageDays : (daysSince(createdAt) ?? 0);
      const priority = (item.dataset.priority || "P2").trim();
      const status = readStatus(item);
      const priorityTag = heading.querySelector(".priority-tag");
      if (priorityTag) {
        priorityTag.remove();
      }
      const { minHours, maxHours } = estimateForItem(item);
      const etaMin = Number.parseFloat(item.dataset.etaMinDays || "");
      const etaMax = Number.parseFloat(item.dataset.etaMaxDays || "");
      const etaDaysRaw = (item.dataset.etaDays || "").trim();
      const eta3hMin = roundToHalf(minHours / 3);
      const eta3hMax = roundToHalf(maxHours / 3);
      const etaLine = etaDaysRaw
        ? formatEtaRangeString(etaDaysRaw)
        : formatDayRange(
          Number.isFinite(etaMin) ? etaMin : eta3hMin,
          Number.isFinite(etaMax) ? etaMax : eta3hMax,
        );
      const etaUpdatedAt = item.dataset.estimateUpdatedAt || new Date().toISOString().slice(0, 10);
      const checkDone = Number.parseInt(item.dataset.checkDone || "", 10);
      const checkTotal = Number.parseInt(item.dataset.checkTotal || "", 10);
      const progressExplicit = Number.parseInt(item.dataset.progressPercent || "", 10);
      const progressPercent = Number.isFinite(progressExplicit)
        ? Math.max(0, Math.min(100, progressExplicit))
        : (Number.isFinite(checkDone) && Number.isFinite(checkTotal) && checkTotal > 0
          ? Math.round((checkDone / checkTotal) * 100)
          : null);

      const section4 = readDtPairByNumber(item, 4);
      const section5 = readDtPairByNumber(item, 5);
      const acceptance = section4.text || "Acceptance criteria not documented yet.";
      const dependencies = section5.text
        ? [section5.text]
        : item.dataset.dependencies
          ? item.dataset.dependencies.split("|").map((entry) => entry.trim()).filter(Boolean)
          : ["Dependencies are not explicitly listed."];
      const section4Html = section4.html || `<dt>4) Acceptance criteria</dt><dd>${acceptance}</dd>`;
      const section5Html = section5.html || `<dt>5) Dependencies</dt><dd>${dependencies.join("; ")}</dd>`;
      const fullDetailsHtml = `${details.innerHTML}${section4Html}${section5Html}`;

      const meta = document.createElement("div");
      meta.className = "backlog-task-meta";
      meta.innerHTML = `
        <span class="backlog-task-meta__item"><strong>Priority:</strong> ${priority}</span>
        <span class="backlog-task-meta__item"><strong>Owner:</strong> ${owner}</span>
        <span class="backlog-task-meta__item"><strong>Age:</strong> ${resolvedAge}d</span>
      `;
      heading.insertAdjacentElement("afterend", meta);

      const eta = document.createElement("div");
      eta.className = "backlog-task-eta";
      eta.innerHTML = `
        <span><strong>ETA:</strong> ${etaLine}</span>
        <span class="backlog-task-eta__meta">Recalculated: ${etaUpdatedAt}</span>
      `;
      const summaryRow = item.querySelector(".backlog-item-summary");
      if (summaryRow) {
        summaryRow.insertAdjacentElement("afterend", eta);
      } else {
        meta.insertAdjacentElement("afterend", eta);
      }

      if (progressPercent !== null) {
        const progress = document.createElement("div");
        progress.className = "backlog-task-progress";
        progress.innerHTML = `
          <div class="backlog-task-progress__head">
            <span>Progress</span>
            <strong>${progressPercent}%</strong>
          </div>
          <div class="backlog-task-progress__track"><span style="width:${progressPercent}%"></span></div>
        `;
        eta.insertAdjacentElement("afterend", progress);
      }

      const actions = document.createElement("div");
      actions.className = "backlog-task-actions";
      actions.innerHTML = `
        <button type="button" class="backlog-task-action-btn" data-task-action="toggle-details">Open details</button>
        <button type="button" class="backlog-task-action-btn" data-task-action="copy-link">Copy link</button>
      `;
      details.insertAdjacentElement("beforebegin", actions);

      const expanded = document.createElement("div");
      expanded.className = "backlog-task-expanded";
      expanded.hidden = true;
      expanded.innerHTML = `
        <section>
          <h4>Full task description</h4>
          <dl class="backlog-task-expanded-dl">${fullDetailsHtml}</dl>
        </section>
      `;
      details.insertAdjacentElement("beforebegin", expanded);
      details.hidden = true;
    });
  };

  const roundToHalf = (value) => Math.max(0.5, Math.round(value * 2) / 2);
  const formatDayRange = (minDays, maxDays) => {
    if (Math.abs(minDays - maxDays) < 0.001) {
      return `~${minDays} day${minDays === 1 ? "" : "s"}`;
    }
    return `~${minDays}-${maxDays} days`;
  };
  const formatEtaRangeString = (rawRange) => {
    const parts = rawRange.split("-").map((part) => Number.parseFloat(part.trim()));
    if (parts.length === 2 && Number.isFinite(parts[0]) && Number.isFinite(parts[1])) {
      return formatDayRange(parts[0], parts[1]);
    }
    const numeric = Number.parseFloat(rawRange);
    if (Number.isFinite(numeric)) {
      return formatDayRange(numeric, numeric);
    }
    return `${rawRange} days`;
  };

  const estimateForItem = (item) => {
    const priority = (item.dataset.priority || "P2").trim();
    const group = normalize(item.dataset.group) || "backend";
    const baseHours = priorityBaseHours[priority] || priorityBaseHours.P2;
    const complexity = groupComplexityMultiplier[group] || 1;
    const adjustedHours = (baseHours * complexity * llmAssistFactor) / estimateScaleDivisor;
    const days = adjustedHours / seniorFocusHoursPerDay;
    const minDays = roundToHalf(days * 0.8);
    const maxDays = roundToHalf(days * 1.35);
    const minHours = minDays * seniorFocusHoursPerDay;
    const maxHours = maxDays * seniorFocusHoursPerDay;
    return { minDays, maxDays, minHours, maxHours };
  };

  const recalibrateEstimateBlocks = () => {
    items.forEach((item) => {
      const estimateTitle = Array.from(item.querySelectorAll("dt")).find((dt) =>
        /Rough estimate/i.test(dt.textContent || ""),
      );
      if (!estimateTitle) {
        return;
      }
      estimateTitle.textContent = "Estimate (recalibrated for one senior + LLM)";

      const estimateBlock = estimateTitle.nextElementSibling;
      if (!estimateBlock) {
        return;
      }
      const cells = Array.from(estimateBlock.querySelectorAll(".time-cell"));
      if (!cells.length) {
        return;
      }
      const { minHours, maxHours } = estimateForItem(item);
      const hourByCell = [3, 2, 1];
      cells.forEach((cell, index) => {
        const strongLabel = cell.querySelector("strong")?.textContent || `${hourByCell[index] || 3} h/day`;
        const dayRate = hourByCell[index] || 3;
        const minDays = roundToHalf(minHours / dayRate);
        const maxDays = roundToHalf(maxHours / dayRate);
        cell.innerHTML = `<strong>${strongLabel}</strong> ${formatDayRange(minDays, maxDays)}`;
      });
    });
  };

  const isOpenStatus = (status) =>
    status === "todo" || status === "in-progress" || status === "blocked";

  const hasPriorityFilter = () => state.priorities.size > 0;
  const hasTaskTypeFilter = () => state.taskTypes.size > 0;
  const hasRiskFilter = () => state.risks.size > 0;
  const hasConfidenceFilter = () => state.confidences.size > 0;
  const hasStatusFilter = () => state.statuses.size > 0;
  const openStatuses = ["todo", "in-progress", "blocked"];
  const isExactStatusSet = (expected) =>
    state.statuses.size === expected.length &&
    expected.every((status) => state.statuses.has(status));
  const hasExactPriorities = (expected) =>
    state.priorities.size === expected.length &&
    expected.every((priority) => state.priorities.has(priority));

  const setQuickPresetButtons = (preset) => {
    document.querySelectorAll("[data-quick-preset]").forEach((button) => {
      const value = button.getAttribute("data-quick-preset") || "";
      button.classList.toggle("is-active", value === preset);
    });
  };

  const activatePriorityButtons = () => {
    const hasActivePriority = hasPriorityFilter();
    document.querySelectorAll("[data-filter-priority]").forEach((button) => {
      const value = button.getAttribute("data-filter-priority") || "all";
      if (value === "all") {
        button.classList.toggle("is-active", !hasActivePriority);
        return;
      }
      button.classList.toggle("is-active", state.priorities.has(value));
    });
  };

  const activateTaskTypeButtons = () => {
    const hasActiveTaskType = hasTaskTypeFilter();
    document.querySelectorAll("[data-filter-task-type]").forEach((button) => {
      const value = button.getAttribute("data-filter-task-type") || "all";
      if (value === "all") {
        button.classList.toggle("is-active", !hasActiveTaskType);
        return;
      }
      button.classList.toggle("is-active", state.taskTypes.has(value));
    });
  };

  const activateRiskButtons = () => {
    const hasActiveRisk = hasRiskFilter();
    document.querySelectorAll("[data-filter-risk]").forEach((button) => {
      const value = button.getAttribute("data-filter-risk") || "all";
      if (value === "all") {
        button.classList.toggle("is-active", !hasActiveRisk);
        return;
      }
      button.classList.toggle("is-active", state.risks.has(value));
    });
  };

  const activateConfidenceButtons = () => {
    const hasActiveConfidence = hasConfidenceFilter();
    document.querySelectorAll("[data-filter-confidence]").forEach((button) => {
      const value = button.getAttribute("data-filter-confidence") || "all";
      if (value === "all") {
        button.classList.toggle("is-active", !hasActiveConfidence);
        return;
      }
      button.classList.toggle("is-active", state.confidences.has(value));
    });
  };

  const activateStatusButtons = () => {
    const hasActiveStatus = hasStatusFilter();
    document.querySelectorAll("[data-filter-status]").forEach((button) => {
      const value = button.getAttribute("data-filter-status") || "all";
      if (value === "all") {
        button.classList.toggle("is-active", !hasActiveStatus);
        return;
      }
      button.classList.toggle("is-active", state.statuses.has(value));
    });
  };

  const matchesQuickPreset = (item, status, priority) => {
    switch (state.quickPreset) {
      case "my-focus":
        return isOpenStatus(status) && (priority === "P0" || priority === "P1");
      case "open":
        return isOpenStatus(status);
      case "blocked":
        return status === "blocked";
      case "high-risk":
        return priority === "P0" && hasAnyTag(item, ["bug", "tech-debt"]);
      default:
        return true;
    }
  };

  const syncQuickPresetFromDetailed = () => {
    const hasGroupFilter = state.group !== "all";
    if (!hasGroupFilter && !hasStatusFilter() && !hasPriorityFilter() && !hasTaskTypeFilter() && !hasRiskFilter() && !hasConfidenceFilter()) {
      state.quickPreset = "all";
    } else if (
      !hasGroupFilter &&
      isExactStatusSet(openStatuses) &&
      hasExactPriorities(["P0", "P1"]) &&
      !hasTaskTypeFilter() &&
      !hasRiskFilter() &&
      !hasConfidenceFilter()
    ) {
      state.quickPreset = "my-focus";
    } else if (
      !hasGroupFilter &&
      isExactStatusSet(openStatuses) &&
      !hasPriorityFilter() &&
      !hasTaskTypeFilter() &&
      !hasRiskFilter() &&
      !hasConfidenceFilter()
    ) {
      state.quickPreset = "open";
    } else if (
      !hasGroupFilter &&
      isExactStatusSet(["blocked"]) &&
      !hasPriorityFilter() &&
      !hasTaskTypeFilter() &&
      !hasRiskFilter() &&
      !hasConfidenceFilter()
    ) {
      state.quickPreset = "blocked";
    } else if (
      !hasGroupFilter &&
      !hasStatusFilter() &&
      hasExactPriorities(["P0"]) &&
      !hasRiskFilter() &&
      !hasConfidenceFilter() &&
      state.taskTypes.size === 2 &&
      state.taskTypes.has("bug") &&
      state.taskTypes.has("tech-debt")
    ) {
      state.quickPreset = "high-risk";
    } else {
      state.quickPreset = "custom";
    }
    setQuickPresetButtons(state.quickPreset);
  };

  const applyDetailedFromQuickPreset = (preset) => {
    state.group = "all";
    state.priorities.clear();
    state.taskTypes.clear();
    state.risks.clear();
    state.confidences.clear();
    state.statuses.clear();

    switch (preset) {
      case "my-focus":
        openStatuses.forEach((status) => state.statuses.add(status));
        state.priorities.add("P0");
        state.priorities.add("P1");
        break;
      case "open":
        openStatuses.forEach((status) => state.statuses.add(status));
        break;
      case "blocked":
        state.statuses.add("blocked");
        break;
      case "high-risk":
        state.priorities.add("P0");
        state.taskTypes.add("bug");
        state.taskTypes.add("tech-debt");
        break;
      default:
        break;
    }

    activateFilterButtons("[data-filter-group]", state.group);
    activatePriorityButtons();
    activateTaskTypeButtons();
    activateRiskButtons();
    activateConfidenceButtons();
    activateStatusButtons();
  };

  const matches = (item) => {
    const group = normalize(item.dataset.group);
    const priority = (item.dataset.priority || "").trim();
    const tags = readTags(item);
    const risk = resolveRisk(item);
    const confidence = resolveConfidence(item);
    const status = readStatus(item);
    const searchHaystack = searchableTextFor(item);
    const searchOk = !state.search || searchHaystack.includes(state.search);

    const groupOk = state.group === "all" || group === state.group;
    const priorityOk = !hasPriorityFilter() || state.priorities.has(priority);
    const taskTypeOk = !hasTaskTypeFilter() || tags.some((tag) => state.taskTypes.has(tag));
    const riskOk = !hasRiskFilter() || state.risks.has(risk);
    const confidenceOk = !hasConfidenceFilter() || state.confidences.has(confidence);
    const statusOk = !hasStatusFilter() || state.statuses.has(status);
    const quickPresetOk = matchesQuickPreset(item, status, priority);

    return groupOk && priorityOk && taskTypeOk && riskOk && confidenceOk && statusOk && quickPresetOk && searchOk;
  };

  const renderCockpitStats = () => {
    const mount = document.getElementById("backlog-cockpit-stats");
    if (!mount) {
      return;
    }
    const visible = items.filter((item) => !item.hidden);
    const totalCount = visible.length || 1;
    const openCount = visible.filter((item) => isOpenStatus(readStatus(item))).length;
    const inProgressCount = visible.filter((item) => readStatus(item) === "in-progress").length;
    const blockedCount = visible.filter((item) => readStatus(item) === "blocked").length;
    const doneCount = visible.filter((item) => readStatus(item) === "done").length;
    const donePercent = Math.round((doneCount / totalCount) * 100);

    const blockedDaysFor = (item) => {
      const explicit = Number.parseInt(item.dataset.blockedDays || "", 10);
      if (Number.isFinite(explicit)) {
        return explicit;
      }
      const blockedAt = parseIsoDate(item.dataset.blockedAt || "");
      return daysSince(blockedAt);
    };

    const doneDaysAgoFor = (item) => {
      const explicit = Number.parseInt(item.dataset.doneDaysAgo || "", 10);
      if (Number.isFinite(explicit)) {
        return explicit;
      }
      const doneAt = parseIsoDate(item.dataset.doneAt || "");
      return daysSince(doneAt);
    };

    const slaRiskItems = visible.filter((item) => {
      const status = readStatus(item);
      const priority = (item.dataset.priority || "").trim();
      const blockedDays = blockedDaysFor(item);
      return status === "blocked" && (priority === "P0" || priority === "P1") &&
        blockedDays !== null && blockedDays > SLA_BLOCKED_THRESHOLD_DAYS;
    });
    const blockedCriticalCount = visible.filter((item) => {
      const status = readStatus(item);
      const priority = (item.dataset.priority || "").trim();
      return status === "blocked" && (priority === "P0" || priority === "P1");
    }).length;

    const etaPressureCount = visible.filter((item) => {
      const status = readStatus(item);
      if (!isOpenStatus(status)) {
        return false;
      }
      const explicitEta = Number.parseFloat(item.dataset.etaMaxDays || "");
      if (Number.isFinite(explicitEta)) {
        return explicitEta <= ETA_PRESSURE_MAX_DAYS;
      }
      const { maxDays } = estimateForItem(item);
      return maxDays <= ETA_PRESSURE_MAX_DAYS;
    }).length;

    const recentDoneExplicit = visible.filter((item) => {
      const status = readStatus(item);
      const doneDaysAgo = doneDaysAgoFor(item);
      return status === "done" && doneDaysAgo !== null && doneDaysAgo <= FLOW_HEALTH_PERIOD_DAYS;
    }).length;
    const useFlowProxy = recentDoneExplicit === 0;
    const recentDoneCount = useFlowProxy ? doneCount : recentDoneExplicit;
    const flowRatePerWeek = Math.round((recentDoneCount / FLOW_HEALTH_PERIOD_DAYS) * 7 * 10) / 10;
    const completedWithActual = visible.filter((item) => {
      if (readStatus(item) !== "done") {
        return false;
      }
      const actualHours = Number.parseFloat(item.dataset.actualHours || "");
      return Number.isFinite(actualHours);
    });
    const avgActualHours = completedWithActual.length
      ? Math.round(
        (completedWithActual.reduce(
          (sum, item) => sum + Number.parseFloat(item.dataset.actualHours || "0"),
          0,
        ) / completedWithActual.length) * 10,
      ) / 10
      : null;
    const flowHealthState = flowRatePerWeek >= 2 ? "healthy" : flowRatePerWeek >= 1 ? "watch" : "risk";
    const slaState = slaRiskItems.length === 0 ? "healthy" : slaRiskItems.length <= 2 ? "watch" : "risk";
    const etaState = etaPressureCount === 0 ? "healthy" : etaPressureCount <= 3 ? "watch" : "risk";

    const percent = (value) => Math.round((value / totalCount) * 100);
    mount.innerHTML = `
      <article class="backlog-kpi">
        <span class="backlog-kpi__label">Visible tasks</span>
        <strong class="backlog-kpi__value">${visible.length}</strong>
        <span class="backlog-kpi__meta">Current filtered scope</span>
      </article>
      <article class="backlog-kpi">
        <span class="backlog-kpi__label">Open</span>
        <strong class="backlog-kpi__value">${openCount}</strong>
        <span class="backlog-kpi__meta">${percent(openCount)}% of visible</span>
      </article>
      <article class="backlog-kpi">
        <span class="backlog-kpi__label">In progress</span>
        <strong class="backlog-kpi__value">${inProgressCount}</strong>
        <span class="backlog-kpi__meta">${percent(inProgressCount)}% of visible</span>
      </article>
      <article class="backlog-kpi">
        <span class="backlog-kpi__label">Blocked</span>
        <strong class="backlog-kpi__value">${blockedCount}</strong>
        <span class="backlog-kpi__meta">${percent(blockedCount)}% of visible</span>
      </article>
      <article class="backlog-kpi">
        <span class="backlog-kpi__label">Done %</span>
        <strong class="backlog-kpi__value">${donePercent}%</strong>
        <span class="backlog-kpi__meta">${doneCount} completed tasks</span>
      </article>
      <article class="backlog-kpi backlog-kpi--${slaState}">
        <span class="backlog-kpi__label">SLA breach risk</span>
        <strong class="backlog-kpi__value">${slaRiskItems.length}</strong>
        <span class="backlog-kpi__meta">Blocked P0/P1 &gt; ${SLA_BLOCKED_THRESHOLD_DAYS}d (${blockedCriticalCount} critical blocked)</span>
      </article>
      <article class="backlog-kpi backlog-kpi--${etaState}">
        <span class="backlog-kpi__label">ETA pressure</span>
        <strong class="backlog-kpi__value">${etaPressureCount}</strong>
        <span class="backlog-kpi__meta">Open tasks with max ETA &le; ${ETA_PRESSURE_MAX_DAYS}d</span>
      </article>
      <article class="backlog-kpi backlog-kpi--${flowHealthState}">
        <span class="backlog-kpi__label">Flow health</span>
        <strong class="backlog-kpi__value">${flowRatePerWeek}/wk</strong>
        <span class="backlog-kpi__meta">${recentDoneCount} done / ${FLOW_HEALTH_PERIOD_DAYS}d${useFlowProxy ? " (snapshot proxy)" : ""}${avgActualHours !== null ? `; avg actual ${avgActualHours}h` : ""}</span>
      </article>
    `;
  };

  const applyViewMode = () => {
    document.body.setAttribute("data-backlog-view", state.viewMode);
  };

  const validateTaxonomy = () => {
    const issues = [];
    items.forEach((item) => {
      item.classList.remove("backlog-item--invalid-taxonomy");
      item.removeAttribute("data-validation-errors");

      const group = normalize(item.dataset.group);
      const tags = normalize(item.dataset.tags)
        .split(/\s+/)
        .filter(Boolean);
      const itemIssues = [];

      if (!allowedGroups.has(group)) {
        itemIssues.push(`invalid group "${group || "empty"}"`);
      }
      if (!tags.length) {
        itemIssues.push("missing tags");
      } else {
        const unknownTags = tags.filter((tag) => !allowedTags.has(tag));
        if (unknownTags.length) {
          itemIssues.push(`unknown tags: ${unknownTags.join(", ")}`);
        }
      }

      if (itemIssues.length) {
        const title = item.querySelector("h2")?.textContent?.replace(/\s+/g, " ").trim() || item.id;
        item.classList.add("backlog-item--invalid-taxonomy");
        item.setAttribute("data-validation-errors", itemIssues.join("; "));
        item.title = `Taxonomy issue: ${itemIssues.join("; ")}`;
        issues.push({ id: item.id, title, problems: itemIssues });
      } else {
        item.removeAttribute("title");
      }
    });

    const mount = ensureValidationMount();
    if (!mount) {
      return;
    }
    if (!issues.length) {
      mount.hidden = true;
      mount.innerHTML = "";
      return;
    }

    const preview = issues
      .slice(0, 5)
      .map(
        (issue) =>
          `<li><a href="#${issue.id}">${issue.title}</a> — ${issue.problems.join(", ")}</li>`,
      )
      .join("");
    const more = issues.length > 5 ? `<p>...and ${issues.length - 5} more.</p>` : "";
    mount.hidden = false;
    mount.innerHTML = `
      <h3>Taxonomy validation warnings</h3>
      <p>Some cards violate the backlog schema (<code>group</code> or <code>tags</code>). Fix them to keep filters reliable.</p>
      <ul>${preview}</ul>
      ${more}
    `;
  };

  const applyFilter = () => {
    if (taskListMount) {
      taskListMount.classList.add("backlog-task-list--transition");
      window.setTimeout(() => {
        taskListMount.classList.remove("backlog-task-list--transition");
      }, 220);
    }
    items.forEach((item) => {
      item.hidden = !matches(item);
    });
    const visibleCount = items.filter((item) => !item.hidden).length;
    const emptyState = ensureEmptyState();
    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
    renderGroupSections();
    renderCockpitStats();
    renderIntelligencePanel();
  };

  const activateFilterButtons = (selector, value) => {
    document.querySelectorAll(selector).forEach((button) => {
      const buttonValue =
        button.getAttribute("data-filter-group") ||
        button.getAttribute("data-filter-priority") ||
        button.getAttribute("data-filter-task-type") ||
        button.getAttribute("data-filter-risk") ||
        button.getAttribute("data-filter-confidence") ||
        button.getAttribute("data-filter-status") ||
        button.getAttribute("data-quick-preset") ||
        button.getAttribute("data-view-mode") ||
        "";
      button.classList.toggle("is-active", buttonValue === value);
    });
  };

  const wireButtons = () => {
    document.querySelectorAll("[data-filter-group]").forEach((button) => {
      button.addEventListener("click", () => {
        state.group = button.getAttribute("data-filter-group") || "all";
        activateFilterButtons("[data-filter-group]", state.group);
        syncQuickPresetFromDetailed();
        applyFilter();
      });
    });

    document.querySelectorAll("[data-filter-priority]").forEach((button) => {
      button.addEventListener("click", () => {
        const selectedPriority = button.getAttribute("data-filter-priority") || "all";
        if (selectedPriority === "all") {
          state.priorities.clear();
        } else if (state.priorities.has(selectedPriority)) {
          state.priorities.delete(selectedPriority);
        } else {
          state.priorities.add(selectedPriority);
        }
        activatePriorityButtons();
        syncQuickPresetFromDetailed();
        applyFilter();
      });
    });

    document.querySelectorAll("[data-filter-task-type]").forEach((button) => {
      button.addEventListener("click", () => {
        const selectedTaskType = button.getAttribute("data-filter-task-type") || "all";
        if (selectedTaskType === "all") {
          state.taskTypes.clear();
        } else if (state.taskTypes.has(selectedTaskType)) {
          state.taskTypes.delete(selectedTaskType);
        } else {
          state.taskTypes.add(selectedTaskType);
        }
        activateTaskTypeButtons();
        syncQuickPresetFromDetailed();
        applyFilter();
      });
    });

    document.querySelectorAll("[data-filter-risk]").forEach((button) => {
      button.addEventListener("click", () => {
        const selectedRisk = button.getAttribute("data-filter-risk") || "all";
        if (selectedRisk === "all") {
          state.risks.clear();
        } else if (state.risks.has(selectedRisk)) {
          state.risks.delete(selectedRisk);
        } else {
          state.risks.add(selectedRisk);
        }
        activateRiskButtons();
        syncQuickPresetFromDetailed();
        applyFilter();
      });
    });

    document.querySelectorAll("[data-filter-confidence]").forEach((button) => {
      button.addEventListener("click", () => {
        const selectedConfidence = button.getAttribute("data-filter-confidence") || "all";
        if (selectedConfidence === "all") {
          state.confidences.clear();
        } else if (state.confidences.has(selectedConfidence)) {
          state.confidences.delete(selectedConfidence);
        } else {
          state.confidences.add(selectedConfidence);
        }
        activateConfidenceButtons();
        syncQuickPresetFromDetailed();
        applyFilter();
      });
    });

    document.querySelectorAll("[data-filter-status]").forEach((button) => {
      button.addEventListener("click", () => {
        const selectedStatus = button.getAttribute("data-filter-status") || "all";
        if (selectedStatus === "all") {
          state.statuses.clear();
        } else if (state.statuses.has(selectedStatus)) {
          state.statuses.delete(selectedStatus);
        } else {
          state.statuses.add(selectedStatus);
        }
        activateStatusButtons();
        syncQuickPresetFromDetailed();
        applyFilter();
      });
    });

    document.querySelectorAll("[data-quick-preset]").forEach((button) => {
      button.addEventListener("click", () => {
        state.quickPreset = button.getAttribute("data-quick-preset") || "all";
        setQuickPresetButtons(state.quickPreset);
        applyDetailedFromQuickPreset(state.quickPreset);
        applyFilter();
      });
    });

    document.querySelectorAll("[data-view-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        state.viewMode = button.getAttribute("data-view-mode") || "board";
        activateFilterButtons("[data-view-mode]", state.viewMode);
        applyViewMode();
      });
    });

    const searchInput = document.getElementById("backlog-global-search");
    if (searchInput) {
      searchInput.addEventListener("input", () => {
        state.search = normalize(searchInput.value);
        applyFilter();
      });
    }

    const detailedFilters = document.getElementById("backlog-detailed-filters");
    if (detailedFilters && window.matchMedia("(max-width: 780px)").matches) {
      detailedFilters.open = false;
    }

    document.querySelectorAll(".backlog-task-action-btn").forEach((button) => {
      button.addEventListener("click", async () => {
        const action = button.getAttribute("data-task-action") || "";
        const card = button.closest(".backlog-item");
        if (!card) {
          return;
        }
        if (action === "toggle-details") {
          const expanded = card.querySelector(".backlog-task-expanded");
          if (!expanded) {
            return;
          }
          const isOpen = !expanded.hidden;
          expanded.hidden = isOpen;
          button.textContent = isOpen ? "Open details" : "Hide details";
          card.classList.toggle("is-expanded", !isOpen);
          return;
        }
        if (action === "copy-link") {
          const hash = `${window.location.origin}${window.location.pathname}#${card.id}`;
          try {
            await navigator.clipboard.writeText(hash);
            button.textContent = "Link copied";
            window.setTimeout(() => {
              button.textContent = "Copy link";
            }, 1200);
          } catch (error) {
            window.location.hash = card.id;
          }
        }
      });
    });

  };

  const renderGroupSections = () => {
    const mount = document.getElementById("backlog-group-sections");
    if (!mount) {
      return;
    }
    mount.innerHTML = "";

    const groups = ["frontend", "backend", "devops", "docs"];
    groups.forEach((group) => {
      const section = document.createElement("section");
      section.className = "backlog-group";

      const headerRow = document.createElement("div");
      headerRow.className = "backlog-group-header";
      const heading = document.createElement("h3");
      heading.textContent = groupLabel[group];
      const counter = document.createElement("span");
      counter.className = "backlog-group-count";
      headerRow.appendChild(heading);
      headerRow.appendChild(counter);
      section.appendChild(headerRow);

      const list = document.createElement("ul");
      list.className = "backlog-group-list";
      const groupItems = items.filter(
        (item) => normalize(item.dataset.group) === group && !item.hidden,
      );
      counter.textContent = `${groupItems.length}`;
      groupItems.forEach((item, index) => {
        const h2 = item.querySelector("h2");
        if (!h2) {
          return;
        }
        const li = document.createElement("li");
        if (index >= GROUP_PREVIEW_LIMIT) {
          li.hidden = true;
          li.classList.add("is-extra-item");
        }
        const a = document.createElement("a");
        a.href = `#${item.id}`;
        a.textContent = h2.textContent.replace(/\s+/g, " ").trim();
        li.appendChild(a);
        list.appendChild(li);
      });

      if (!list.childElementCount) {
        const li = document.createElement("li");
        li.textContent = "No tasks in this block for current filter.";
        list.appendChild(li);
      }
      section.appendChild(list);

      if (groupItems.length > GROUP_PREVIEW_LIMIT) {
        const toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "backlog-group-toggle";
        toggleBtn.textContent = `Show more (${groupItems.length - GROUP_PREVIEW_LIMIT})`;
        toggleBtn.setAttribute("aria-expanded", "false");
        toggleBtn.addEventListener("click", () => {
          const expanded = toggleBtn.getAttribute("aria-expanded") === "true";
          list.querySelectorAll(".is-extra-item").forEach((node) => {
            node.hidden = expanded;
          });
          toggleBtn.setAttribute("aria-expanded", expanded ? "false" : "true");
          toggleBtn.textContent = expanded
            ? `Show more (${groupItems.length - GROUP_PREVIEW_LIMIT})`
            : "Show less";
        });
        section.appendChild(toggleBtn);
      }

      mount.appendChild(section);
    });
  };

  sortItemsInPlace();
  setListLoadingState(true);
  window.requestAnimationFrame(() => {
    mountTaskList();
  });
  reorderTopSections();
  numberCards();
  syncStatusPills();
  normalizeHeadingLayout();
  decorateCards();
  recalibrateEstimateBlocks();
  renderTaskCardWorkspace();
  wireButtons();
  activatePriorityButtons();
  activateTaskTypeButtons();
  activateRiskButtons();
  activateConfidenceButtons();
  activateStatusButtons();
  setQuickPresetButtons(state.quickPreset);
  validateTaxonomy();
  applyViewMode();
  applyFilter();
})();
