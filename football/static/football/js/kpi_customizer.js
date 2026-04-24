(() => {
  const safeJsonParse = (raw) => {
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (err) {
      return null;
    }
  };

  const applyVisibility = (container, visibilityByKey) => {
    if (!container) return;
    const elements = Array.from(container.querySelectorAll("[data-kpi-key]"));
    elements.forEach((el) => {
      const key = String(el.dataset.kpiKey || "").trim();
      if (!key) return;
      const visible = visibilityByKey[key] !== false;
      el.hidden = !visible;
    });
  };

  const collectKpis = (container) => {
    const elements = Array.from(container.querySelectorAll("[data-kpi-key]"));
    const map = new Map();
    elements.forEach((el) => {
      const key = String(el.dataset.kpiKey || "").trim();
      if (!key) return;
      const label =
        String(el.dataset.kpiLabel || "").trim() ||
        (el.querySelector(".kpi-ring-label")?.textContent || "").trim() ||
        (el.querySelector(".ring-label")?.textContent || "").trim() ||
        (el.querySelector(".label")?.textContent || "").trim() ||
        key;
      if (!map.has(key)) {
        map.set(key, { key, label, elements: [] });
      }
      map.get(key).elements.push(el);
    });
    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label, "es"));
  };

  const ensureCustomizer = (detailsEl) => {
    const prefKey = String(detailsEl.dataset.kpiPrefKey || "").trim();
    if (!prefKey) return;
    const container = detailsEl.closest("[data-kpi-container]") || document;
    const storageKey = `kpi_visibility:${prefKey}`;
    const stored = safeJsonParse(window.localStorage?.getItem(storageKey));
    const visibilityByKey = stored && typeof stored === "object" ? stored : {};

    // Apply current visibility before building UI.
    applyVisibility(container, visibilityByKey);

    const kpis = collectKpis(container).filter((item) => item.key && item.label);
    const body = detailsEl.querySelector(".kpi-customizer-body");
    if (!body) return;

    body.innerHTML = "";
    const hint = document.createElement("div");
    hint.style.fontSize = "0.85rem";
    hint.style.color = "rgba(71, 85, 105, 0.96)";
    hint.style.margin = "0.35rem 0 0.65rem";
    hint.textContent = "Selecciona qué KPIs quieres ver en esta pantalla (se guarda en este dispositivo).";
    body.appendChild(hint);

    const list = document.createElement("div");
    list.style.display = "grid";
    list.style.gridTemplateColumns = "repeat(auto-fit, minmax(220px, 1fr))";
    list.style.gap = "0.55rem 1rem";
    body.appendChild(list);

    const persist = () => {
      try {
        window.localStorage?.setItem(storageKey, JSON.stringify(visibilityByKey));
      } catch (err) {
        // ignore
      }
    };

    const onToggle = (key, checked) => {
      visibilityByKey[key] = Boolean(checked);
      applyVisibility(container, visibilityByKey);
      persist();
    };

    kpis.forEach((item) => {
      const row = document.createElement("label");
      row.style.display = "flex";
      row.style.alignItems = "center";
      row.style.gap = "0.5rem";
      row.style.userSelect = "none";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = visibilityByKey[item.key] !== false;
      checkbox.addEventListener("change", () => onToggle(item.key, checkbox.checked));

      const text = document.createElement("span");
      text.textContent = item.label;

      row.appendChild(checkbox);
      row.appendChild(text);
      list.appendChild(row);
    });
  };

  const init = () => {
    const customizers = Array.from(document.querySelectorAll("details.kpi-customizer[data-kpi-pref-key]"));
    customizers.forEach((detailsEl) => ensureCustomizer(detailsEl));
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

