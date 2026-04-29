/* Docs popup runtime helpers (toasts/prompts) */
(function () {
  function buildStickyTocPromoToast(onEnable, durationMs) {
    const existing = document.querySelector(".docs-inpage-toc-toast");
    if (existing) {
      existing.remove();
    }
    const toast = document.createElement("section");
    toast.className = "docs-inpage-toc-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    toast.innerHTML = `
      <div class="docs-inpage-toc-toast__title">Sticky TOC available</div>
      <p class="docs-inpage-toc-toast__text">
        We have a premium sticky "On this page" navigation for long docs.
      </p>
      <div class="docs-inpage-toc-toast__actions">
        <button type="button" class="docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--ghost" data-popup-dismiss>
          Hide
        </button>
        <button type="button" class="docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--primary" data-popup-enable>
          Enable sticky TOC
        </button>
      </div>
      <div class="docs-inpage-toc-toast__progress" aria-hidden="true"></div>
    `;
    document.body.appendChild(toast);

    let isClosed = false;
    let timerId = null;
    const close = () => {
      if (isClosed) {
        return;
      }
      isClosed = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
      toast.classList.add("docs-inpage-toc-toast--closing");
      window.setTimeout(() => {
        toast.remove();
      }, 180);
    };

    const dismissBtn = toast.querySelector("[data-popup-dismiss]");
    const enableBtn = toast.querySelector("[data-popup-enable]");
    dismissBtn?.addEventListener("click", close);
    enableBtn?.addEventListener("click", () => {
      if (typeof onEnable === "function") {
        onEnable();
      }
      close();
    });

    timerId = window.setTimeout(close, durationMs);
    return { close };
  }

  function buildContinueReadingToast(label, onContinue, onStartFromTop, durationMs) {
    const existing = document.querySelector(".docs-continue-reading--toast");
    if (existing) {
      existing.remove();
    }
    const prompt = document.createElement("aside");
    prompt.className = "docs-continue-reading--toast";
    prompt.setAttribute("aria-label", "Continue reading");

    const title = document.createElement("p");
    title.className = "docs-inpage-toc-toast__title";
    title.textContent = "Continue reading available";

    const text = document.createElement("p");
    text.className = "docs-inpage-toc-toast__text";
    text.textContent = label ? `Continue from § ${label}` : "Continue where you left off";

    const actions = document.createElement("div");
    actions.className = "docs-inpage-toc-toast__actions";

    const continueBtn = document.createElement("button");
    continueBtn.type = "button";
    continueBtn.className = "docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--primary";
    continueBtn.textContent = "Continue";

    const topBtn = document.createElement("button");
    topBtn.type = "button";
    topBtn.className = "docs-inpage-toc-toast__btn docs-inpage-toc-toast__btn--ghost";
    topBtn.textContent = "Start from top";

    const progress = document.createElement("div");
    progress.className = "docs-inpage-toc-toast__progress";
    progress.setAttribute("aria-hidden", "true");

    actions.appendChild(continueBtn);
    actions.appendChild(topBtn);
    prompt.appendChild(title);
    prompt.appendChild(text);
    prompt.appendChild(actions);
    prompt.appendChild(progress);
    document.body.appendChild(prompt);

    let timerId = null;
    let closed = false;
    const close = () => {
      if (closed) {
        return;
      }
      closed = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
      prompt.remove();
    };

    continueBtn.addEventListener("click", () => {
      if (typeof onContinue === "function") {
        onContinue();
      }
      close();
    });
    topBtn.addEventListener("click", () => {
      if (typeof onStartFromTop === "function") {
        onStartFromTop();
      }
      close();
    });
    timerId = window.setTimeout(close, durationMs);
    return { close };
  }

  window.DocsPopups = {
    showStickyTocPromoToast(options = {}) {
      const durationMs = Number(options.durationMs || 3000);
      return buildStickyTocPromoToast(options.onEnable, durationMs);
    },
    showContinueReadingToast(options = {}) {
      const durationMs = Number(options.durationMs || 3000);
      return buildContinueReadingToast(
        String(options.label || "").trim(),
        options.onContinue,
        options.onStartFromTop,
        durationMs,
      );
    },
  };
})();
