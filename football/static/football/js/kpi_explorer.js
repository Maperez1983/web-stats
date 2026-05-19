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
    const presetNameInput = document.getElementById('kpi-preset-name');
    const presetSaveBtn = document.getElementById('kpi-preset-save');
    const presetList = document.getElementById('kpi-preset-list');

    const derivedWrap = document.getElementById('kpi-derived');
    const eventTypesWrap = document.getElementById('kpi-event-types');
    const resultsWrap = document.getElementById('kpi-results');
    const zonesWrap = document.getElementById('kpi-zones');
    const terciosWrap = document.getElementById('kpi-tercios');
    const selectedWrap = document.getElementById('kpi-selected');
    const outputWrap = document.getElementById('kpi-output');

    const optionsUrl = safeText(document.getElementById('kpi-options-url')?.value);
    const queryUrl = safeText(document.getElementById('kpi-query-url')?.value);
    const sourcesUrl = safeText(document.getElementById('kpi-sources-url')?.value);
    const pdfUrl = safeText(document.getElementById('kpi-pdf-url')?.value);
    const csrf = document.querySelector('#kpi-csrf input[name="csrfmiddlewaretoken"]')?.value || '';

    const prefsClient = (() => {
      const cfg = window.WEBSTATS_WORKSPACE_PREFS || null;
      const getUrl = cfg && typeof cfg.getUrl === 'string' ? cfg.getUrl : '';
      const setUrl = cfg && typeof cfg.setUrl === 'string' ? cfg.setUrl : '';
      if (!getUrl || !setUrl) return null;
      const readCsrf = () => (document.cookie || '')
        .split(';')
        .map((s) => s.trim())
        .find((s) => s.startsWith('csrftoken='))
        ?.split('=')[1] || '';
      const get = async (key) => {
        const k = String(key || '').trim();
        if (!k) return null;
        const url = new URL(getUrl, window.location.origin);
        url.searchParams.set('key', k);
        const resp = await fetch(url.toString(), { method: 'GET', credentials: 'same-origin', headers: { Accept: 'application/json' } });
        const data = await resp.json().catch(() => null);
        if (!resp.ok || !data || data.ok === false) return null;
        return data.value ?? null;
      };
      const set = async (key, value) => {
        const k = String(key || '').trim();
        if (!k) return false;
        const resp = await fetch(setUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': readCsrf(), Accept: 'application/json' },
          body: JSON.stringify({ key: k, value }),
        });
        const data = await resp.json().catch(() => null);
        return Boolean(resp.ok && data && data.ok !== false);
      };
      return { get, set };
    })();

    const sourcesModal = document.getElementById('kpi-sources-modal');
    const sourcesClose = document.getElementById('kpi-sources-close');
    const sourcesTitle = document.getElementById('kpi-sources-title');
    const sourcesSubtitle = document.getElementById('kpi-sources-subtitle');
    const sourcesList = document.getElementById('kpi-sources-list');

    const matchItems = Array.isArray(jsonFromScript('kpi-match-items')) ? jsonFromScript('kpi-match-items') : [];
    const playerItems = Array.isArray(jsonFromScript('kpi-player-items')) ? jsonFromScript('kpi-player-items') : [];
    const derivedMetrics = Array.isArray(jsonFromScript('kpi-derived-metrics')) ? jsonFromScript('kpi-derived-metrics') : [];
    const derivedByKey = new Map((derivedMetrics || []).map((m) => [safeText(m?.key), m]).filter((x) => x[0]));

    const storageKey = 'kpi_explorer:selected';
    const stored = (() => {
      try { return JSON.parse(window.localStorage?.getItem(storageKey) || 'null'); } catch (e) { return null; }
    })();
    let selected = Array.isArray(stored) ? stored : [];

    const presetsStorageKey = 'kpi_explorer:presets';
    const sharedPresetsKey = 'kpi_explorer_presets:v1';
    const normalizePresetName = (raw) => safeText(raw, '').replace(/\s+/g, ' ').trim().slice(0, 42);
    const readLocalPresets = () => {
      try {
        const parsed = JSON.parse(window.localStorage?.getItem(presetsStorageKey) || 'null');
        if (!parsed || typeof parsed !== 'object') return [];
        const items = Array.isArray(parsed?.items) ? parsed.items : [];
        return items
          .filter((x) => x && typeof x === 'object' && normalizePresetName(x.name))
          .map((x) => ({ name: normalizePresetName(x.name), metrics: Array.isArray(x.metrics) ? x.metrics.slice(0, 80) : [] }))
          .slice(0, 20);
      } catch (e) {
        return [];
      }
    };
    const writeLocalPresets = (items) => {
      try {
        window.localStorage?.setItem(presetsStorageKey, JSON.stringify({ v: 1, items: (items || []).slice(0, 20) }));
      } catch (e) { /* ignore */ }
    };
    let sharedPresets = [];

    const DEFAULT_PRESETS = [
      {
        name: 'Resumen equipo',
        metrics: [
          { kind: 'derived', key: 'total_actions' },
          { kind: 'derived', key: 'success_rate' },
          { kind: 'derived', key: 'goals' },
          { kind: 'derived', key: 'assists' },
          { kind: 'derived', key: 'passes_accuracy' },
          { kind: 'derived', key: 'shots_accuracy' },
          { kind: 'derived', key: 'duel_rate' },
          { kind: 'derived', key: 'yellow_cards' },
        ],
      },
      {
        name: 'Ataque',
        metrics: [
          { kind: 'derived', key: 'goals' },
          { kind: 'derived', key: 'assists' },
          { kind: 'derived', key: 'shot_attempts' },
          { kind: 'derived', key: 'shots_on_target' },
          { kind: 'derived', key: 'shots_accuracy' },
          { kind: 'derived', key: 'pass_attempts' },
          { kind: 'derived', key: 'passes_completed' },
          { kind: 'derived', key: 'passes_accuracy' },
          { kind: 'derived', key: 'key_passes_completed' },
        ],
      },
      {
        name: 'Defensa',
        metrics: [
          { kind: 'derived', key: 'duels_total' },
          { kind: 'derived', key: 'duel_rate' },
          { kind: 'derived', key: 'aerial_duels_total' },
          { kind: 'derived', key: 'aerial_duel_rate' },
          { kind: 'derived', key: 'yellow_cards' },
          { kind: 'derived', key: 'red_cards' },
          { kind: 'derived', key: 'success_rate' },
          { kind: 'derived', key: 'total_actions' },
        ],
      },
      {
        name: 'Portero',
        metrics: [
          { kind: 'derived', key: 'goalkeeper_saves' },
          { kind: 'derived', key: 'shots_on_target' },
          { kind: 'derived', key: 'goals' },
        ],
      },
    ];

    const seedDefaultPresetsIfMissing = async () => {
      const local = readLocalPresets();
      if (local.length) return false;
      const items = DEFAULT_PRESETS
        .map((p) => ({ name: normalizePresetName(p.name), metrics: Array.isArray(p.metrics) ? p.metrics.slice(0, 80) : [] }))
        .filter((p) => p.name && p.metrics.length)
        .slice(0, 20);
      if (!items.length) return false;
      sharedPresets = items;
      renderPresets();
      writeLocalPresets(sharedPresets);
      if (prefsClient) {
        try { await prefsClient.set(sharedPresetsKey, { v: 1, items: sharedPresets }); } catch (e) { /* ignore */ }
      }
      return true;
    };

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

    const renderPresets = () => {
      if (!presetList) return;
      const items = Array.isArray(sharedPresets) ? sharedPresets : [];
      if (!items.length) {
        presetList.innerHTML = '<div class="meta">No hay presets guardados todavía.</div>';
        return;
      }
      presetList.innerHTML = items.map((p) => {
        const name = normalizePresetName(p?.name) || 'Preset';
        const metrics = Array.isArray(p?.metrics) ? p.metrics : [];
        const payload = { name, metrics };
        return `
          <div class="row">
            <div style="display:flex; flex-direction:column; gap:0.1rem; min-width:0;">
              <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escHtml(name)}</strong>
              <small>${escHtml(String(metrics.length))} KPIs</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-preset-load='${escHtml(JSON.stringify(payload))}'>Cargar</button>
              <button type="button" class="button danger" data-preset-del="${escHtml(name)}">Borrar</button>
            </div>
          </div>
        `;
      }).join('');

      Array.from(presetList.querySelectorAll('[data-preset-load]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const raw = btn.getAttribute('data-preset-load') || '';
          try {
            const payload = JSON.parse(raw);
            const metrics = Array.isArray(payload?.metrics) ? payload.metrics : [];
            selected = metrics.slice(0, 80);
            persistSelected();
            renderSelected();
            setStatus(`Preset cargado: ${safeText(payload?.name, '')}.`);
          } catch (e) { /* ignore */ }
        });
      });
      Array.from(presetList.querySelectorAll('[data-preset-del]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const name = normalizePresetName(btn.getAttribute('data-preset-del') || '');
          if (!name) return;
          sharedPresets = (Array.isArray(sharedPresets) ? sharedPresets : []).filter((p) => normalizePresetName(p?.name) !== name);
          renderPresets();
          writeLocalPresets(sharedPresets);
          if (prefsClient) prefsClient.set(sharedPresetsKey, { v: 1, items: sharedPresets }).catch(() => {});
          setStatus('Preset borrado.');
        });
      });
    };

    const loadPresets = async () => {
      sharedPresets = readLocalPresets();
      renderPresets();
      if (!prefsClient) return;
      try {
        const shared = await prefsClient.get(sharedPresetsKey);
        const items = Array.isArray(shared?.items) ? shared.items : (Array.isArray(shared) ? shared : []);
        if (items && items.length) {
          sharedPresets = items
            .filter((x) => x && typeof x === 'object' && normalizePresetName(x.name))
            .map((x) => ({ name: normalizePresetName(x.name), metrics: Array.isArray(x.metrics) ? x.metrics.slice(0, 80) : [] }))
            .slice(0, 20);
          writeLocalPresets(sharedPresets);
          renderPresets();
        }
      } catch (e) { /* ignore */ }
    };

    const savePreset = async () => {
      const name = normalizePresetName(presetNameInput?.value || '');
      if (!name) { setStatus('Pon un nombre al preset.', true); return; }
      if (!selected.length) { setStatus('No hay KPIs seleccionados para guardar.', true); return; }
      const existing = (Array.isArray(sharedPresets) ? sharedPresets : []).filter((p) => normalizePresetName(p?.name) !== name);
      sharedPresets = [{ name, metrics: selected.slice(0, 80) }, ...existing].slice(0, 20);
      renderPresets();
      writeLocalPresets(sharedPresets);
      if (prefsClient) {
        const ok = await prefsClient.set(sharedPresetsKey, { v: 1, items: sharedPresets });
        if (!ok) setStatus('Preset guardado local, pero no se pudo sincronizar al workspace.', true);
        else setStatus('Preset guardado.');
      } else {
        setStatus('Preset guardado (local).');
      }
      try { if (presetNameInput) presetNameInput.value = ''; } catch (e) { /* ignore */ }
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

    const applyPreset = (preset) => {
      const p = safeText(preset).toLowerCase();
      const keys = {
        summary: [
          'total_actions', 'success_rate',
          'duels_total', 'duel_rate',
          'aerial_duels_total', 'aerial_duel_rate',
          'pass_attempts', 'passes_accuracy',
          'shot_attempts', 'shots_accuracy',
          'goals', 'assists',
          'yellow_cards', 'red_cards',
        ],
        attack: [
          'shot_attempts', 'shots_on_target', 'shots_accuracy',
          'goals', 'assists',
          'key_passes_completed',
          'pass_attempts', 'passes_accuracy',
        ],
        defense: [
          'duels_total', 'duels_won', 'duel_rate',
          'aerial_duels_total', 'aerial_duels_won', 'aerial_duel_rate',
          'yellow_cards', 'red_cards',
        ],
        gk: ['goalkeeper_saves', 'shot_attempts', 'shots_on_target', 'shots_accuracy'],
      }[p] || [];
      if (!keys.length) return;
      const next = [];
      keys.forEach((key) => {
        const m = derivedByKey.get(key);
        if (m) next.push({ ...m, kind: 'derived' });
      });
      if (!next.length) return;
      selected = next.slice(0, 80);
      persistSelected();
      renderSelected();
      setStatus(`Preset aplicado: ${p}.`);
    };

    // Presets UI
    Array.from(document.querySelectorAll('[data-kpi-preset]')).forEach((btn) => {
      btn.addEventListener('click', () => applyPreset(btn.getAttribute('data-kpi-preset') || ''));
    });

    // Deep-link: preselección por query string (?scope=player&player_id=...&match_id=...&context=...&preset=summary)
    (() => {
      let params = null;
      try { params = new URLSearchParams(window.location.search || ''); } catch (e) { params = null; }
      if (!params) return;
      const qsScope = safeText(params.get('scope') || '');
      const qsContext = safeText(params.get('context') || '');
      const qsMatch = Number(params.get('match_id') || 0) || 0;
      const qsPlayer = Number(params.get('player_id') || 0) || 0;
      const qsPreset = safeText(params.get('preset') || '');

      if (contextSelect && qsContext) {
        const opt = Array.from(contextSelect.options || []).find((o) => safeText(o.value) === qsContext);
        if (opt) contextSelect.value = qsContext;
      }
      if (scopeSelect && (qsScope || qsPlayer || qsMatch)) {
        const inferred = qsPlayer ? 'player' : (qsMatch ? 'match' : qsScope);
        if (inferred) {
          const opt = Array.from(scopeSelect.options || []).find((o) => safeText(o.value) === inferred);
          if (opt) scopeSelect.value = inferred;
        }
      }
      // Render dependent UI now (listener puede no estar aún).
      try { setScopeUi(); } catch (e) { /* ignore */ }
      if (matchSelect && qsMatch) {
        // options are populated later from JSON; set after population.
        matchSelect.dataset.preselect = String(qsMatch);
      }
      if (playerSelect && qsPlayer) {
        playerSelect.dataset.preselect = String(qsPlayer);
      }
      if (qsPreset) applyPreset(qsPreset);
    })();

    const applyPreselects = () => {
      try {
        if (matchSelect?.dataset?.preselect) {
          const id = safeText(matchSelect.dataset.preselect);
          const opt = Array.from(matchSelect.options || []).find((o) => safeText(o.value) === id);
          if (opt) matchSelect.value = id;
          delete matchSelect.dataset.preselect;
        }
      } catch (e) { /* ignore */ }
      try {
        if (playerSelect?.dataset?.preselect) {
          const id = safeText(playerSelect.dataset.preselect);
          const opt = Array.from(playerSelect.options || []).find((o) => safeText(o.value) === id);
          if (opt) playerSelect.value = id;
          delete playerSelect.dataset.preselect;
        }
      } catch (e) { /* ignore */ }
    };

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

    // Ensure preselects are applied once options are rendered the first time.
    try { applyPreselects(); } catch (e) { /* ignore */ }

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
          const metric = { kind: safeText(r?.kind), key: safeText(r?.key), label };
          return `<article class="kpi" data-metric='${escHtml(JSON.stringify(metric))}' title="Ver acciones"><div class="k">${escHtml(label)}</div><div class="v">${escHtml(value)}</div></article>`;
        }).join('') || '<div class="meta">—</div>';
        setStatus('Listo.');
      } catch (e) {
        outputWrap.innerHTML = '<div class="meta">—</div>';
        setStatus('No se pudo calcular.', true);
      }
    };

    const closeSources = () => {
      if (!sourcesModal) return;
      sourcesModal.hidden = true;
    };

    const openSources = async (metric) => {
      if (!sourcesUrl || !sourcesModal || !sourcesList) return;
      if (!ensureMatchRequired()) return;
      const st = currentState();
      const metricKind = safeText(metric?.kind);
      const metricKeyVal = safeText(metric?.key);
      if (!metricKind || !metricKeyVal) return;

      sourcesSubtitle && (sourcesSubtitle.textContent = `${metricKind}`);
      sourcesTitle && (sourcesTitle.textContent = safeText(metric?.label, metricKeyVal));
      sourcesList.innerHTML = '<div class="meta">Cargando…</div>';
      sourcesModal.hidden = false;

      try {
        const resp = await fetch(sourcesUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ ...st, metric: { kind: metricKind, key: metricKeyVal } }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        const events = Array.isArray(data?.events) ? data.events : [];
        if (!events.length) {
          sourcesList.innerHTML = '<div class="meta">No hay acciones para este KPI.</div>';
          return;
        }
        sourcesList.innerHTML = events.map((ev) => {
          const minute = (ev?.minute === null || ev?.minute === undefined) ? '—' : String(ev.minute);
          const player = safeText(ev?.player, 'EQUIPO');
          const etype = safeText(ev?.event_type, '—');
          const res = safeText(ev?.result, '—');
          const zone = safeText(ev?.zone, '');
          const obs = safeText(ev?.observation, '');
          return `
            <div class="row">
              <div style="display:flex; flex-direction:column; gap:0.15rem; min-width:0;">
                <strong>${escHtml(`${minute}' · ${player}`)}</strong>
                <small>${escHtml([etype, res, zone].filter(Boolean).join(' · '))}</small>
                ${obs ? `<small style="opacity:0.95;">${escHtml(obs)}</small>` : ''}
              </div>
            </div>
          `;
        }).join('');
      } catch (e) {
        sourcesList.innerHTML = '<div class="meta">No se pudieron cargar las acciones.</div>';
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
    presetSaveBtn?.addEventListener('click', savePreset);
    presetNameInput?.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        savePreset();
      }
    });

    sourcesClose?.addEventListener('click', closeSources);
    sourcesModal?.addEventListener('click', (ev) => {
      if (ev?.target === sourcesModal) closeSources();
    });
    document.addEventListener('keydown', (ev) => {
      if (ev?.key === 'Escape') closeSources();
    });

    outputWrap?.addEventListener('click', (ev) => {
      const target = ev?.target;
      const kpi = target?.closest ? target.closest('[data-metric]') : null;
      const raw = safeText(kpi?.getAttribute?.('data-metric') || '');
      if (!raw) return;
      try {
        const metric = JSON.parse(raw);
        openSources(metric);
      } catch (e) { /* ignore */ }
    });

    renderSelected();
    renderAllOptions();
    loadPresets().then(seedDefaultPresetsIfMissing).catch(() => {});
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
