(() => {
  const WINDOWS_SCRIPT_ID = "match-stats-windows";
  const STORAGE = {
    tab: "webstats:match_stats:tab",
    auto: "webstats:match_stats:auto_refresh_30s",
    window: "webstats:match_stats:window",
  };

  function getWindows() {
    const el = document.getElementById(WINDOWS_SCRIPT_ID);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (_) {
      return null;
    }
  }

  function setBodyTab(tab) {
    if (!tab) return;
    document.body.dataset.msTab = tab;
    try {
      localStorage.setItem(STORAGE.tab, tab);
    } catch (_) {}
  }

  function initTabs() {
    const buttons = Array.from(document.querySelectorAll("[data-ms-tab]"));
    if (!buttons.length) return;

    let initial = "resumen";
    try {
      initial = localStorage.getItem(STORAGE.tab) || initial;
    } catch (_) {}
    if (!["resumen", "timeline", "jugadores"].includes(initial)) initial = "resumen";
    setBodyTab(initial);

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        setBodyTab(btn.dataset.msTab || "resumen");
      });
    });
  }

  function debounce(fn, waitMs) {
    let timer = null;
    return (...args) => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => fn(...args), waitMs);
    };
  }

  function initFilters() {
    const eventFilter = document.getElementById("ms-event-filter");
    const events = Array.from(document.querySelectorAll("#ms-events .ms-event"));
    if (eventFilter && events.length) {
      const apply = debounce(() => {
        const q = (eventFilter.value || "").trim().toLowerCase();
        events.forEach((li) => {
          if (!q) {
            li.hidden = false;
            return;
          }
          const hay = (li.dataset.msSearch || "").toLowerCase();
          li.hidden = !hay.includes(q);
        });
      }, 60);
      eventFilter.addEventListener("input", apply);
    }

    const playerFilter = document.getElementById("ms-player-filter");
    const players = Array.from(document.querySelectorAll("#ms-player-grid .player-card"));
    if (playerFilter && players.length) {
      const apply = debounce(() => {
        const q = (playerFilter.value || "").trim().toLowerCase();
        players.forEach((card) => {
          if (!q) {
            card.hidden = false;
            return;
          }
          const hay = (card.dataset.msPlayerSearch || "").toLowerCase();
          card.hidden = !hay.includes(q);
        });
      }, 60);
      playerFilter.addEventListener("input", apply);
    }
  }

  function renderChips(container, items, labelKey) {
    if (!container) return;
    container.textContent = "";
    if (!Array.isArray(items) || !items.length) {
      const span = document.createElement("span");
      span.className = "ms-chip";
      span.textContent = "—";
      container.appendChild(span);
      return;
    }
    items.forEach((item) => {
      const label = (item && item[labelKey]) || "";
      const count = (item && item.count) || 0;
      if (!label) return;
      const chip = document.createElement("span");
      chip.className = "ms-chip";
      const strong = document.createElement("strong");
      strong.textContent = String(count);
      chip.appendChild(strong);
      chip.appendChild(document.createTextNode(" " + label));
      container.appendChild(chip);
    });
  }

  function initWindows() {
    const windows = getWindows();
    const chips = Array.from(document.querySelectorAll("[data-ms-window]"));
    const totalEl = document.getElementById("ms-total-actions");
    const typesEl = document.getElementById("ms-top-types");
    const resultsEl = document.getElementById("ms-top-results");
    if (!windows || !chips.length || !totalEl) return;

    function applyWindow(key) {
      const data = windows[key] || windows.all;
      if (!data) return;
      totalEl.textContent = String(data.total_events ?? 0);
      renderChips(typesEl, data.top_event_types || [], "event");
      renderChips(resultsEl, data.top_results || [], "result");
      chips.forEach((c) => c.classList.toggle("is-active", c.dataset.msWindow === key));
      try {
        localStorage.setItem(STORAGE.window, key);
      } catch (_) {}
    }

    // disable missing windows
    chips.forEach((c) => {
      const key = c.dataset.msWindow;
      if (key && !windows[key]) {
        if (key !== "all") {
          c.style.opacity = "0.55";
          c.style.pointerEvents = "none";
          c.title = "No disponible en este partido";
        }
      }
    });

    let initial = "all";
    try {
      initial = localStorage.getItem(STORAGE.window) || initial;
    } catch (_) {}
    if (!windows[initial]) initial = "all";
    applyWindow(initial);

    chips.forEach((c) => {
      c.addEventListener("click", () => {
        const key = c.dataset.msWindow || "all";
        applyWindow(key);
      });
    });
  }

  function initRefresh() {
    const refreshBtn = document.getElementById("ms-refresh");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => location.reload());
    }

    const auto = document.getElementById("ms-auto-refresh");
    if (!auto) return;

    let enabled = false;
    try {
      enabled = localStorage.getItem(STORAGE.auto) === "1";
    } catch (_) {}
    auto.checked = enabled;

    let timer = null;
    const start = () => {
      stop();
      timer = setInterval(() => location.reload(), 30_000);
    };
    const stop = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };

    if (enabled) start();
    auto.addEventListener("change", () => {
      const on = !!auto.checked;
      try {
        localStorage.setItem(STORAGE.auto, on ? "1" : "0");
      } catch (_) {}
      if (on) start();
      else stop();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    // Default tab for responsive layout.
    if (!document.body.dataset.msTab) {
      document.body.dataset.msTab = "resumen";
    }
    initTabs();
    initFilters();
    initWindows();
    initRefresh();
  });
})();

