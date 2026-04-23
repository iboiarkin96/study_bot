(() => {
  const GROUP_PREVIEW_LIMIT = 10;
  const items = Array.from(document.querySelectorAll(".backlog-item"));
  if (!items.length) {
    return;
  }

  const groupLabel = {
    bug: "Bug",
    frontend: "Frontend",
    backend: "Backend",
    devops: "DevOps",
    docs: "Docs",
    "tech-debt": "Tech debt",
  };
  const priorityBaseHours = {
    P0: 28,
    P1: 18,
    P2: 11,
    P3: 7,
  };
  const groupComplexityMultiplier = {
    bug: 1.1,
    frontend: 1.0,
    backend: 1.2,
    devops: 1.3,
    docs: 0.8,
    "tech-debt": 1.35,
  };
  const llmAssistFactor = 0.78;
  const seniorFocusHoursPerDay = 5;
  const estimateScaleDivisor = 3;

  const state = {
    group: "all",
    priority: "all",
    view: "all",
  };
  const reorderTopSections = () => {
    const main = document.querySelector("main.container");
    const quick = document.getElementById("quick-views-section");
    const overview = document.getElementById("overview-section");
    const groups = document.getElementById("backlog-blocks");
    const allTasks = document.getElementById("all-tasks-section");
    if (!main || !quick || !overview || !groups || !allTasks) {
      return;
    }
    main.insertBefore(quick, overview);
    main.insertBefore(overview, groups);
    main.insertBefore(groups, allTasks);
  };
  const taskListMount = document.getElementById("backlog-task-list");
  const ensureEmptyState = () => {
    if (!taskListMount) {
      return null;
    }
    let emptyState = document.getElementById("backlog-task-list-empty");
    if (!emptyState) {
      emptyState = document.createElement("p");
      emptyState.id = "backlog-task-list-empty";
      emptyState.className = "backlog-empty-state";
      emptyState.textContent = "По указанным фильтрам задач не найдено.";
      emptyState.hidden = true;
      taskListMount.insertAdjacentElement("beforebegin", emptyState);
    }
    return emptyState;
  };
  const mountTaskList = () => {
    if (!taskListMount) {
      return;
    }
    items.forEach((item) => {
      taskListMount.appendChild(item);
    });
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


  const normalize = (value) => (value || "").trim().toLowerCase();

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

  const decorateCards = () => {
    items.forEach((item) => {
      const tags = normalize(item.dataset.tags)
        .split(/\s+/)
        .filter(Boolean);
      const summary = document.createElement("div");
      summary.className = "backlog-item-summary";

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

      if (summary.childElementCount) {
        const h2 = item.querySelector("h2");
        h2?.insertAdjacentElement("afterend", summary);
      }
    });
  };

  const roundToHalf = (value) => Math.max(0.5, Math.round(value * 2) / 2);

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
        cell.innerHTML = `<strong>${strongLabel}</strong> ~${minDays}-${maxDays} days`;
      });
    });
  };

  const isOpenStatus = (status) =>
    status === "todo" || status === "in-progress" || status === "blocked";

  const matches = (item) => {
    const group = normalize(item.dataset.group);
    const priority = (item.dataset.priority || "").trim();
    const status = readStatus(item);

    const groupOk = state.group === "all" || group === state.group;
    const priorityOk = state.priority === "all" || priority === state.priority;
    const viewOk =
      state.view === "all" ||
      (state.view === "open" && isOpenStatus(status)) ||
      (state.view === "done" && status === "done");

    return groupOk && priorityOk && viewOk;
  };

  const applyFilter = () => {
    items.forEach((item) => {
      item.hidden = !matches(item);
    });
    const visibleCount = items.filter((item) => !item.hidden).length;
    const emptyState = ensureEmptyState();
    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
    renderGroupSections();
  };

  const activateFilterButtons = (selector, value) => {
    document.querySelectorAll(selector).forEach((button) => {
      const buttonValue =
        button.getAttribute("data-filter-group") ||
        button.getAttribute("data-filter-priority") ||
        button.getAttribute("data-filter-view") ||
        "";
      button.classList.toggle("is-active", buttonValue === value);
    });
  };

  const wireButtons = () => {
    document.querySelectorAll("[data-filter-group]").forEach((button) => {
      button.addEventListener("click", () => {
        state.group = button.getAttribute("data-filter-group") || "all";
        activateFilterButtons("[data-filter-group]", state.group);
        applyFilter();
      });
    });

    document.querySelectorAll("[data-filter-priority]").forEach((button) => {
      button.addEventListener("click", () => {
        state.priority = button.getAttribute("data-filter-priority") || "all";
        activateFilterButtons("[data-filter-priority]", state.priority);
        applyFilter();
      });
    });

    document.querySelectorAll("[data-filter-view]").forEach((button) => {
      button.addEventListener("click", () => {
        state.view = button.getAttribute("data-filter-view") || "all";
        activateFilterButtons("[data-filter-view]", state.view);
        applyFilter();
      });
    });
  };

  const renderGroupSections = () => {
    const mount = document.getElementById("backlog-group-sections");
    if (!mount) {
      return;
    }
    mount.innerHTML = "";

    const groups = ["bug", "frontend", "backend", "devops", "docs", "tech-debt"];
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

  mountTaskList();
  reorderTopSections();
  numberCards();
  decorateCards();
  recalibrateEstimateBlocks();
  wireButtons();
  applyFilter();
})();
