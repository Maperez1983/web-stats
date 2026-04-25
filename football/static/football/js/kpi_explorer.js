(function () {
  const safeText = (value, fallback = '') => String(value ?? '').trim() || fallback;
  const escHtml = (value) => safeText(value, '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

  const jsonFromScript = (id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent || 'null'); } catch (e) { return null; }
  };

  const setStatus = (text, isError = false) => {
    const el = document.getElementById('kpi-status');
    if (!el) return;
    el.textContent = safeText(text, '');
    el.style.color = isError ? '#fecaca' : 'rgba(226,232,240,0.72)';
  };

  const downloadBlob = (blob, filename) => {
    try {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'export.pdf';
      document.body.appendChild(a);
      a.click();
      window.setTimeout(() => {
        try { URL.revokeObjectURL(url); } catch (e) { /* ignore */ }
        try { a.remove(); } catch (e) { /* ignore */ }
      }, 500);
    } catch (e) { /* ignore */ }
  };

  const downloadResponseBlob = async (resp, fallbackName) => {
    const blob = await resp.blob();
    let name = fallbackName || 'export.bin';
    try {
      const cd = resp.headers.get('content-disposition') || '';
      const m = /filename=\"([^\"]+)\"/i.exec(cd);
      if (m && m[1]) name = m[1];
    } catch (e) { /* ignore */ }
    downloadBlob(blob, name);
  };

  const postJsonDownload = async ({ url, payload, csrf, fallbackName }) => {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      credentials: 'same-origin',
      body: JSON.stringify(payload || {}),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err?.error || 'error');
    }
    await downloadResponseBlob(resp, fallbackName);
  };

  const init = () => {
    const scopeSelect = document.getElementById('kpi-scope');
    const contextSelect = document.getElementById('kpi-context');
    const matchWrap = document.getElementById('kpi-match-wrap');
    const matchSelect = document.getElementById('kpi-match');
    const playerWrap = document.getElementById('kpi-player-wrap');
    const playerSelect = document.getElementById('kpi-player');
    const loadBtn = document.getElementById('kpi-load');
    const runBtn = document.getElementById('kpi-run');
    const pdfBtn = document.getElementById('kpi-pdf');
    const clearBtn = document.getElementById('kpi-clear');
    const searchInput = document.getElementById('kpi-search');

    const derivedWrap = document.getElementById('kpi-derived');
    const eventTypesWrap = document.getElementById('kpi-event-types');
    const resultsWrap = document.getElementById('kpi-results');
    const zonesWrap = document.getElementById('kpi-zones');
    const terciosWrap = document.getElementById('kpi-tercios');
    const selectedWrap = document.getElementById('kpi-selected');
    const outputWrap = document.getElementById('kpi-output');

    const optionsUrl = safeText(document.getElementById('kpi-options-url')?.value);
    const queryUrl = safeText(document.getElementById('kpi-query-url')?.value);
    const pdfUrl = safeText(document.getElementById('kpi-pdf-url')?.value);
    const csrf = document.querySelector('#kpi-csrf input[name="csrfmiddlewaretoken"]')?.value || '';

    const matchItems = Array.isArray(jsonFromScript('kpi-match-items')) ? jsonFromScript('kpi-match-items') : [];
    const playerItems = Array.isArray(jsonFromScript('kpi-player-items')) ? jsonFromScript('kpi-player-items') : [];
    const derivedMetrics = Array.isArray(jsonFromScript('kpi-derived-metrics')) ? jsonFromScript('kpi-derived-metrics') : [];

    const storageKey = 'kpi_explorer:selected';
    const stored = (() => {
      try { return JSON.parse(window.localStorage?.getItem(storageKey) || 'null'); } catch (e) { return null; }
    })();
    let selected = Array.isArray(stored) ? stored : [];

    const normalize = (s) => safeText(s, '').toLowerCase();

    const setScopeUi = () => {
      const scope = safeText(scopeSelect?.value, 'team');
      if (matchWrap) matchWrap.hidden = false;
      if (playerWrap) playerWrap.hidden = scope !== 'player';
      // En match scope, el partido es obligatorio (lo marcamos via placeholder).
      if (matchSelect) matchSelect.dataset.required = scope === 'match' ? '1' : '0';
    };

    const fillSelect = (el, items, { includeEmpty = true, emptyLabel = '—' } = {}) => {
      if (!el) return;
      const opts = [];
      if (includeEmpty) opts.push(`<option value="0">${escHtml(emptyLabel)}</option>`);
      for (const it of (items || [])) {
        const id = Number(it?.id) || 0;
        const label = safeText(it?.label, String(id));
        if (!id) continue;
        opts.push(`<option value="${id}">${escHtml(label)}</option>`);
      }
      el.innerHTML = opts.join('');
    };

    fillSelect(matchSelect, matchItems, { includeEmpty: true, emptyLabel: 'Todos (últimos 60)' });
    fillSelect(playerSelect, playerItems, { includeEmpty: true, emptyLabel: '—' });
    setScopeUi();

    const persistSelected = () => {
      try { window.localStorage?.setItem(storageKey, JSON.stringify(selected.slice(0, 80))); } catch (e) { /* ignore */ }
    };

    const metricKey = (m) => `${safeText(m?.kind)}|${safeText(m?.key || m?.value)}`;
    const hasMetric = (m) => selected.some((x) => metricKey(x) === metricKey(m));
    const addMetric = (m) => {
      if (!m || !safeText(m.kind)) return;
      if (hasMetric(m)) return;
      selected = [...selected, m].slice(0, 80);
      persistSelected();
      renderSelected();
    };
    const removeMetric = (key) => {
      selected = selected.filter((x) => metricKey(x) !== key);
      persistSelected();
      renderSelected();
    };
    const moveMetric = (key, dir) => {
      const idx = selected.findIndex((x) => metricKey(x) === key);
      if (idx < 0) return;
      const next = idx + dir;
      if (next < 0 || next >= selected.length) return;
      const copy = selected.slice();
      const tmp = copy[idx];
      copy[idx] = copy[next];
      copy[next] = tmp;
      selected = copy;
      persistSelected();
      renderSelected();
    };

    const renderSelected = () => {
      if (!selectedWrap) return;
      if (!selected.length) {
        selectedWrap.innerHTML = '<div class="meta">No hay KPIs seleccionados.</div>';
        return;
      }
      selectedWrap.innerHTML = selected.map((m) => {
        const key = metricKey(m);
        const label = safeText(m?.label, safeText(m?.key || m?.value, key));
        return `
          <div class="row">
            <div style="display:flex; flex-direction:column; gap:0.1rem; min-width:0;">
              <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escHtml(label)}</strong>
              <small>${escHtml(safeText(m?.kind, ''))}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button ghost" data-move-up="${escHtml(key)}">↑</button>
              <button type="button" class="button ghost" data-move-down="${escHtml(key)}">↓</button>
              <button type="button" class="button danger" data-remove="${escHtml(key)}">Quitar</button>
            </div>
          </div>
        `;
      }).join('');

      Array.from(selectedWrap.querySelectorAll('[data-remove]')).forEach((btn) => {
        btn.addEventListener('click', () => removeMetric(safeText(btn.getAttribute('data-remove'))));
      });
      Array.from(selectedWrap.querySelectorAll('[data-move-up]')).forEach((btn) => {
        btn.addEventListener('click', () => moveMetric(safeText(btn.getAttribute('data-move-up')), -1));
      });
      Array.from(selectedWrap.querySelectorAll('[data-move-down]')).forEach((btn) => {
        btn.addEventListener('click', () => moveMetric(safeText(btn.getAttribute('data-move-down')), +1));
      });
    };

    const currentState = () => ({
      scope: safeText(scopeSelect?.value, 'team'),
      context: safeText(contextSelect?.value, 'all'),
      match_id: Number(matchSelect?.value || 0) || 0,
      player_id: Number(playerSelect?.value || 0) || 0,
    });

    const ensureMatchRequired = () => {
      const st = currentState();
      if (st.scope === 'match' && !st.match_id) {
        setStatus('Selecciona un partido.', true);
        return false;
      }
      if (st.scope === 'player' && !st.player_id) {
        setStatus('Selecciona un jugador.', true);
        return false;
      }
      return true;
    };

    const filterList = (items, q, getLabel) => {
      const qq = normalize(q);
      if (!qq) return items;
      return (items || []).filter((it) => normalize(getLabel(it)).includes(qq));
    };

    const renderOptionsList = (wrap, items, builder) => {
      if (!wrap) return;
      if (!items.length) {
        wrap.innerHTML = '<div class="meta">—</div>';
        return;
      }
      wrap.innerHTML = items.slice(0, 80).map(builder).join('');
      Array.from(wrap.querySelectorAll('[data-add]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const raw = btn.getAttribute('data-add') || '';
          try {
            const m = JSON.parse(raw);
            addMetric(m);
          } catch (e) { /* ignore */ }
        });
      });
    };

    let lastDimensions = { event_types: [], results: [], zones: [], tercios: [] };

    const renderAllOptions = () => {
      const q = safeText(searchInput?.value, '');
      const derived = filterList(derivedMetrics, q, (x) => x?.label || x?.key);
      const evTypes = filterList(lastDimensions.event_types || [], q, (x) => x?.value);
      const res = filterList(lastDimensions.results || [], q, (x) => x?.value);
      const zones = filterList(lastDimensions.zones || [], q, (x) => x?.value);
      const tercios = filterList(lastDimensions.tercios || [], q, (x) => x?.value);

      renderOptionsList(derivedWrap, derived, (d) => {
        const metric = { kind: 'derived', key: safeText(d?.key), label: safeText(d?.label), format: safeText(d?.format) };
        return `<div class="row"><div style="min-width:0;"><strong>${escHtml(metric.label)}</strong><small>${escHtml(metric.key)}</small></div><button type="button" class="button" data-add='${escHtml(JSON.stringify(metric))}'>Añadir</button></div>`;
      });
      renderOptionsList(eventTypesWrap, evTypes, (d) => {
        const metric = { kind: 'event_type', value: safeText(d?.value), label: `Acción: ${safeText(d?.value)}` };
        return `<div class="row"><div style="min-width:0;"><strong style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(metric.label)}</strong><small>${escHtml(d?.count)} · ocurrencias</small></div><button type="button" class="button" data-add='${escHtml(JSON.stringify(metric))}'>Añadir</button></div>`;
      });
      renderOptionsList(resultsWrap, res, (d) => {
        const metric = { kind: 'result', value: safeText(d?.value), label: `Resultado: ${safeText(d?.value)}` };
        return `<div class="row"><div style="min-width:0;"><strong style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(metric.label)}</strong><small>${escHtml(d?.count)} · ocurrencias</small></div><button type="button" class="button" data-add='${escHtml(JSON.stringify(metric))}'>Añadir</button></div>`;
      });
      renderOptionsList(zonesWrap, zones, (d) => {
        const metric = { kind: 'zone', value: safeText(d?.value), label: `Zona: ${safeText(d?.value)}` };
        return `<div class="row"><div style="min-width:0;"><strong style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(metric.label)}</strong><small>${escHtml(d?.count)} · ocurrencias</small></div><button type="button" class="button" data-add='${escHtml(JSON.stringify(metric))}'>Añadir</button></div>`;
      });
      renderOptionsList(terciosWrap, tercios, (d) => {
        const metric = { kind: 'tercio', value: safeText(d?.value), label: `Tercio: ${safeText(d?.value)}` };
        return `<div class="row"><div style="min-width:0;"><strong style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(metric.label)}</strong><small>${escHtml(d?.count)} · ocurrencias</small></div><button type="button" class="button" data-add='${escHtml(JSON.stringify(metric))}'>Añadir</button></div>`;
      });
    };

    const loadOptions = async () => {
      if (!optionsUrl) return;
      if (!ensureMatchRequired()) return;
      const st = currentState();
      setStatus('Cargando acciones…');
      try {
        const url = new URL(optionsUrl, window.location.origin);
        url.searchParams.set('scope', st.scope);
        url.searchParams.set('context', st.context);
        if (st.match_id) url.searchParams.set('match_id', String(st.match_id));
        if (st.player_id) url.searchParams.set('player_id', String(st.player_id));
        const resp = await fetch(url.toString(), { credentials: 'same-origin' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        lastDimensions = data?.dimensions || {};
        renderAllOptions();
        setStatus('Acciones cargadas.');
      } catch (e) {
        lastDimensions = { event_types: [], results: [], zones: [], tercios: [] };
        renderAllOptions();
        setStatus('No se pudieron cargar acciones.', true);
      }
    };

    const runQuery = async () => {
      if (!queryUrl) return;
      if (!ensureMatchRequired()) return;
      const st = currentState();
      if (!selected.length) { setStatus('Añade al menos 1 KPI.', true); return; }
      setStatus('Calculando…');
      try {
        const resp = await fetch(queryUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ ...st, metrics: selected }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        const rows = Array.isArray(data?.results) ? data.results : [];
        outputWrap.innerHTML = rows.map((r) => {
          const label = safeText(r?.label, '—');
          const value = safeText(r?.value, '0');
          return `<article class="kpi"><div class="k">${escHtml(label)}</div><div class="v">${escHtml(value)}</div></article>`;
        }).join('') || '<div class="meta">—</div>';
        setStatus('Listo.');
      } catch (e) {
        outputWrap.innerHTML = '<div class="meta">—</div>';
        setStatus('No se pudo calcular.', true);
      }
    };

    const exportPdf = async () => {
      if (!pdfUrl) return;
      if (!ensureMatchRequired()) return;
      const st = currentState();
      if (!selected.length) { setStatus('Añade al menos 1 KPI.', true); return; }
      try {
        setStatus('Generando PDF…');
        await postJsonDownload({
          url: pdfUrl,
          csrf,
          payload: { ...st, title: 'KPIs avanzados', metrics: selected },
          fallbackName: 'kpis.pdf',
        });
        setStatus('PDF descargado.');
      } catch (e) {
        setStatus('No se pudo generar PDF.', true);
      }
    };

    const clearAll = () => {
      selected = [];
      persistSelected();
      renderSelected();
      outputWrap.innerHTML = '<div class="meta">—</div>';
      setStatus('Limpio.');
    };

    scopeSelect?.addEventListener('change', () => { setScopeUi(); });
    loadBtn?.addEventListener('click', loadOptions);
    runBtn?.addEventListener('click', runQuery);
    pdfBtn?.addEventListener('click', exportPdf);
    clearBtn?.addEventListener('click', clearAll);
    searchInput?.addEventListener('input', renderAllOptions);

    renderSelected();
    renderAllOptions();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

