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

  const init = async () => {
    const grid = document.getElementById('dash-grid');
    const settings = document.getElementById('dash-settings');
    const toggleSettingsBtn = document.getElementById('dash-toggle-settings');

    const roleSelect = document.getElementById('dash-role');
    const presetSelect = document.getElementById('dash-preset');
    const saveDefaultBtn = document.getElementById('dash-save-default');
    const defaultPill = document.getElementById('dash-default-pill');

    const scopeSelect = document.getElementById('dash-scope');
    const contextSelect = document.getElementById('dash-context');
    const matchWrap = document.getElementById('dash-match-wrap');
    const matchSelect = document.getElementById('dash-match');
    const playerWrap = document.getElementById('dash-player-wrap');
    const playerSelect = document.getElementById('dash-player');
    const runBtn = document.getElementById('dash-run');
    const output = document.getElementById('dash-output');
    const statusEl = document.getElementById('dash-status');

    const queryUrl = safeText(document.getElementById('dash-query-url')?.value);
    const csrf = document.querySelector('#dash-csrf input[name="csrfmiddlewaretoken"]')?.value || '';

    const setStatus = (text, isError = false) => {
      if (!statusEl) return;
      statusEl.textContent = safeText(text, '');
      statusEl.style.color = isError ? '#fecaca' : 'rgba(226,232,240,0.72)';
    };

    const showSettings = (show) => {
      const want = Boolean(show);
      if (settings) settings.hidden = !want;
      if (grid) grid.classList.toggle('show-settings', want);
      if (toggleSettingsBtn) toggleSettingsBtn.classList.toggle('primary', want);
    };

    const matchItems = Array.isArray(jsonFromScript('dash-match-items')) ? jsonFromScript('dash-match-items') : [];
    const playerItems = Array.isArray(jsonFromScript('dash-player-items')) ? jsonFromScript('dash-player-items') : [];

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

    const setScopeUi = () => {
      const scope = safeText(scopeSelect?.value, 'team');
      if (matchWrap) matchWrap.hidden = false;
      if (playerWrap) playerWrap.hidden = scope !== 'player';
    };
    setScopeUi();

    const sharedPresetsKey = 'kpi_explorer_presets:v1';
    const roleDefaultsKey = 'kpi_dashboard_role_defaults:v1';
    let presets = [];
    let roleDefaults = {};

    const normalizePresetName = (raw) => safeText(raw, '').replace(/\s+/g, ' ').trim().slice(0, 42);

    const loadPresets = async () => {
      presets = [];
      if (prefsClient) {
        const shared = await prefsClient.get(sharedPresetsKey);
        const items = Array.isArray(shared?.items) ? shared.items : (Array.isArray(shared) ? shared : []);
        presets = items
          .filter((x) => x && typeof x === 'object' && normalizePresetName(x.name))
          .map((x) => ({ name: normalizePresetName(x.name), metrics: Array.isArray(x.metrics) ? x.metrics.slice(0, 80) : [] }))
          .slice(0, 20);
      }
      if (!presets.length) {
        try {
          const local = JSON.parse(window.localStorage?.getItem('kpi_explorer:presets') || 'null');
          const items = Array.isArray(local?.items) ? local.items : [];
          presets = items
            .filter((x) => x && typeof x === 'object' && normalizePresetName(x.name))
            .map((x) => ({ name: normalizePresetName(x.name), metrics: Array.isArray(x.metrics) ? x.metrics.slice(0, 80) : [] }))
            .slice(0, 20);
        } catch (e) { /* ignore */ }
      }
      if (presetSelect) {
        presetSelect.innerHTML = presets.length
          ? presets.map((p) => `<option value="${escHtml(p.name)}">${escHtml(p.name)}</option>`).join('')
          : '<option value="">(Sin presets)</option>';
      }
    };

    const loadRoleDefaults = async () => {
      roleDefaults = {};
      if (!prefsClient) return;
      const v = await prefsClient.get(roleDefaultsKey);
      if (v && typeof v === 'object') roleDefaults = v;
    };

    const applyDefaultForRole = () => {
      const role = safeText(roleSelect?.value, 'coach');
      const defaultName = safeText(roleDefaults?.[role], '');
      const exists = presets.some((p) => p.name === defaultName);
      if (defaultPill) defaultPill.hidden = !Boolean(defaultName && exists);
      if (presetSelect && defaultName && exists) presetSelect.value = defaultName;
    };

    const saveDefaultForRole = async () => {
      if (!prefsClient) { setStatus('No se pudo guardar (sin workspace).', true); return; }
      const role = safeText(roleSelect?.value, 'coach');
      const name = safeText(presetSelect?.value, '');
      if (!name) { setStatus('Selecciona un preset.', true); return; }
      roleDefaults = { ...(roleDefaults && typeof roleDefaults === 'object' ? roleDefaults : {}), [role]: name };
      const ok = await prefsClient.set(roleDefaultsKey, roleDefaults);
      if (!ok) { setStatus('No se pudo guardar el default.', true); return; }
      applyDefaultForRole();
      setStatus('Default guardado.');
    };

    const currentState = () => ({
      scope: safeText(scopeSelect?.value, 'team'),
      context: safeText(contextSelect?.value, 'all'),
      match_id: Number(matchSelect?.value || 0) || 0,
      player_id: Number(playerSelect?.value || 0) || 0,
    });

    const ensureScopeOk = () => {
      const st = currentState();
      if (st.scope === 'match' && !st.match_id) { setStatus('Selecciona un partido.', true); return false; }
      if (st.scope === 'player' && !st.player_id) { setStatus('Selecciona un jugador.', true); return false; }
      return true;
    };

    const run = async () => {
      if (!queryUrl) return;
      if (!ensureScopeOk()) return;
      const presetName = safeText(presetSelect?.value, '');
      const preset = presets.find((p) => p.name === presetName);
      const metrics = Array.isArray(preset?.metrics) ? preset.metrics : [];
      if (!metrics.length) { setStatus('El preset no tiene KPIs.', true); return; }
      setStatus('Calculando…');
      try {
        const st = currentState();
        const resp = await fetch(queryUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ ...st, metrics }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        const rows = Array.isArray(data?.results) ? data.results : [];
        if (!output) return;
        output.innerHTML = rows.map((r) => {
          const label = safeText(r?.label, '—');
          const value = safeText(r?.value, '0');
          return `<article class="kpi"><div class="k">${escHtml(label)}</div><div class="v">${escHtml(value)}</div></article>`;
        }).join('') || '<div class="meta">—</div>';
        setStatus('Listo.');
      } catch (e) {
        if (output) output.innerHTML = '<div class="meta">—</div>';
        setStatus('No se pudo calcular.', true);
      }
    };

    await loadPresets();
    await loadRoleDefaults();
    applyDefaultForRole();

    // Dashboard "real": por defecto enseñamos los indicadores y ocultamos ajustes.
    // Si no hay presets, mostramos ajustes para guiar al staff.
    showSettings(!presets.length);
    toggleSettingsBtn?.addEventListener('click', () => {
      const next = settings ? Boolean(settings.hidden) : true;
      showSettings(next);
    });

    roleSelect?.addEventListener('change', applyDefaultForRole);
    saveDefaultBtn?.addEventListener('click', saveDefaultForRole);
    scopeSelect?.addEventListener('change', setScopeUi);
    runBtn?.addEventListener('click', run);

    try {
      if (presets.length) {
        run();
      } else {
        setStatus('Crea un preset en “KPIs avanzados”.', true);
      }
    } catch (e) { /* ignore */ }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { init().catch(() => {}); });
  } else {
    init().catch(() => {});
  }
})();
