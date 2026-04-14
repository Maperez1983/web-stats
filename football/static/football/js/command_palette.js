(() => {
  const STATIC_ITEMS_EL = document.getElementById('cmdk-static-items');
  const CMDK_EL = document.getElementById('cmdk');
  const LIST_EL = document.getElementById('cmdk-list');
  const INPUT_EL = document.getElementById('cmdk-input');

  if (!STATIC_ITEMS_EL || !CMDK_EL || !LIST_EL || !INPUT_EL) return;

  const RECENTS_KEY = 'webstats:cmdk:recents:v1';
  const FAVS_KEY = 'webstats:cmdk:favs:v1';
  const SERVER_SEARCH_MIN = 2;

  const safeParse = (raw, fallback) => {
    try {
      const parsed = JSON.parse(String(raw || ''));
      return parsed === undefined || parsed === null ? fallback : parsed;
    } catch {
      return fallback;
    }
  };

  const normalizeUrl = (url) => {
    const value = String(url || '').trim();
    if (!value) return '';
    try {
      const u = new URL(value, window.location.origin);
      return u.pathname + u.search + u.hash;
    } catch {
      return value;
    }
  };

  const loadStaticItems = () => {
    const raw = STATIC_ITEMS_EL.textContent || '[]';
    const items = safeParse(raw, []);
    return Array.isArray(items)
      ? items
          .map((it) => ({
            label: String((it && it.label) || '').trim(),
            url: normalizeUrl((it && it.url) || ''),
            keywords: String((it && it.keywords) || '').toLowerCase(),
          }))
          .filter((it) => it.label && it.url)
      : [];
  };

  const loadFavs = () => {
    const items = safeParse(localStorage.getItem(FAVS_KEY), []);
    const urls = Array.isArray(items) ? items.map(normalizeUrl).filter(Boolean) : [];
    return Array.from(new Set(urls)).slice(0, 30);
  };

  const saveFavs = (urls) => {
    localStorage.setItem(FAVS_KEY, JSON.stringify(urls.slice(0, 30)));
  };

  const loadRecents = () => {
    const items = safeParse(localStorage.getItem(RECENTS_KEY), []);
    if (!Array.isArray(items)) return [];
    return items
      .map((it) => ({
        label: String((it && it.label) || '').trim(),
        url: normalizeUrl((it && it.url) || ''),
        ts: Number((it && it.ts) || 0),
      }))
      .filter((it) => it.label && it.url && it.ts)
      .sort((a, b) => b.ts - a.ts)
      .slice(0, 12);
  };

  const saveRecents = (items) => {
    localStorage.setItem(RECENTS_KEY, JSON.stringify(items.slice(0, 20)));
  };

  const shouldRecordRecent = () => {
    const path = window.location.pathname || '';
    if (!path) return false;
    if (path.startsWith('/static/')) return false;
    if (path.startsWith('/media/')) return false;
    if (path.startsWith('/login')) return false;
    if (path.startsWith('/logout')) return false;
    if (path.includes('/pdf')) return false;
    if (path.endsWith('.pdf')) return false;
    if (document.title && String(document.title).toLowerCase().includes('pdf')) return false;
    return true;
  };

  const recordRecent = () => {
    if (!shouldRecordRecent()) return;
    const label = (document.title || '').replace(/\s+/g, ' ').trim().slice(0, 90) || 'Página';
    const url = normalizeUrl(window.location.href);
    const now = Date.now();
    const existing = loadRecents().filter((it) => it.url !== url);
    existing.unshift({ label, url, ts: now });
    saveRecents(existing);
  };

  const state = {
    open: false,
    query: '',
    selectedIndex: 0,
    items: loadStaticItems(),
    serverQuery: '',
    serverGroups: [],
    serverStatus: 'idle', // idle | loading | ok | error
    serverReqId: 0,
  };

  const isFav = (url) => loadFavs().includes(normalizeUrl(url));

  const toggleFav = (url) => {
    const norm = normalizeUrl(url);
    if (!norm) return;
    const favs = loadFavs();
    const idx = favs.indexOf(norm);
    if (idx >= 0) favs.splice(idx, 1);
    else favs.unshift(norm);
    saveFavs(favs);
  };

  const scoreItem = (item, tokens) => {
    const hay = `${item.label} ${item.keywords}`.toLowerCase();
    let score = 0;
    for (const t of tokens) {
      const i = hay.indexOf(t);
      if (i < 0) return -1;
      score += i === 0 ? 40 : Math.max(1, 20 - i);
      if (item.label.toLowerCase().startsWith(t)) score += 25;
    }
    return score;
  };

  const resolveActiveTeamId = () => {
    try {
      const params = new URLSearchParams(String(window.location.search || ''));
      const raw = String(params.get('team') || '').trim();
      if (/^\d+$/.test(raw)) return raw;
    } catch {}
    return '';
  };

  const buildServerSearchUrl = (query) => {
    const params = new URLSearchParams();
    params.set('q', String(query || '').trim());
    const teamId = resolveActiveTeamId();
    if (teamId) params.set('team', teamId);
    return `/api/search/?${params.toString()}`;
  };

  const serverCache = new Map(); // q -> groups

  const fetchServerResults = async (query) => {
    const q = String(query || '').trim();
    if (q.length < SERVER_SEARCH_MIN) {
      state.serverQuery = '';
      state.serverGroups = [];
      state.serverStatus = 'idle';
      return;
    }
    if (serverCache.has(q)) {
      state.serverQuery = q;
      state.serverGroups = serverCache.get(q) || [];
      state.serverStatus = 'ok';
      return;
    }
    state.serverStatus = 'loading';
    state.serverQuery = q;
    const reqId = (state.serverReqId || 0) + 1;
    state.serverReqId = reqId;
    try {
      const resp = await fetch(buildServerSearchUrl(q), { credentials: 'same-origin' });
      const data = await resp.json();
      if (state.serverReqId !== reqId) return; // stale
      if (!resp.ok || !data || data.ok !== true) throw new Error(String((data && data.error) || 'search failed'));
      const groups = Array.isArray(data.groups) ? data.groups : [];
      serverCache.set(q, groups);
      try {
        while (serverCache.size > 30) {
          const firstKey = serverCache.keys().next().value;
          if (!firstKey) break;
          serverCache.delete(firstKey);
        }
      } catch {}
      state.serverGroups = groups;
      state.serverStatus = 'ok';
    } catch (e) {
      if (state.serverReqId !== reqId) return;
      state.serverGroups = [];
      state.serverStatus = 'error';
    }
  };

  const debounce = (fn, ms) => {
    let t = 0;
    return (...args) => {
      if (t) window.clearTimeout(t);
      t = window.setTimeout(() => fn(...args), ms);
    };
  };

  const debouncedFetch = debounce((q) => {
    fetchServerResults(q).then(() => render());
  }, 160);

  const buildResults = () => {
    const q = String(state.query || '').toLowerCase().trim();
    const tokens = q ? q.split(/\s+/).filter(Boolean).slice(0, 6) : [];
    const staticItems = state.items;
    const recents = loadRecents();
    const favUrls = loadFavs();

    const byUrl = new Map();
    for (const it of staticItems) byUrl.set(normalizeUrl(it.url), it);

    const favItems = favUrls
      .map((url) => byUrl.get(normalizeUrl(url)))
      .filter(Boolean)
      .map((it) => ({ ...it, section: 'Favoritos' }));

    const recentItems = recents.map((it) => ({
      label: it.label,
      url: it.url,
      keywords: 'reciente recent',
      section: 'Recientes',
      subtitle: it.url,
    }));

    const serverItems = [];
    if (q && state.serverQuery && state.serverQuery.toLowerCase() === q && Array.isArray(state.serverGroups)) {
      state.serverGroups.forEach((g) => {
        const label = String((g && g.label) || '').trim() || 'Resultados';
        const items = Array.isArray(g && g.items) ? g.items : [];
        items.forEach((it) => {
          const url = normalizeUrl((it && it.url) || '');
          const title = String((it && it.label) || '').trim();
          if (!url || !title) return;
          const meta = String((it && it.meta) || '').trim();
          const type = String((it && it.type) || '').trim();
          serverItems.push({
            label: title,
            url,
            keywords: `${type} ${meta}`.toLowerCase(),
            section: label,
            subtitle: meta || url,
          });
        });
      });
    }

    const base = q
      ? [...serverItems, ...staticItems.map((it) => ({ ...it, section: 'Ir a' }))]
      : [...favItems, ...recentItems, ...staticItems.map((it) => ({ ...it, section: 'Ir a' }))];

    const seen = new Set();
    const filtered = [];
    for (const it of base) {
      const key = normalizeUrl(it.url);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      const s = tokens.length ? scoreItem(it, tokens) : 10;
      if (tokens.length && s < 0) continue;
      filtered.push({ ...it, _score: s });
    }
    if (tokens.length) filtered.sort((a, b) => b._score - a._score);
    return filtered.slice(0, 18);
  };

  const render = () => {
    const results = buildResults();
    if (state.selectedIndex >= results.length) state.selectedIndex = Math.max(0, results.length - 1);
    if (state.selectedIndex < 0) state.selectedIndex = 0;

    let html = '';
    let currentSection = '';
    if (state.query && String(state.query || '').trim().length >= SERVER_SEARCH_MIN && state.serverStatus === 'loading') {
      html += `<div class="cmdk-section">Buscando…</div>`;
    }
    results.forEach((it, idx) => {
      if (it.section && it.section !== currentSection) {
        currentSection = it.section;
        html += `<div class="cmdk-section">${escapeHtml(currentSection)}</div>`;
      }
      const selected = idx === state.selectedIndex;
      const fav = isFav(it.url);
      const subtitle = it.subtitle || it.keywords || it.url;
      html += `
        <div class="cmdk-item" role="option" aria-selected="${selected ? 'true' : 'false'}" data-cmdk-index="${idx}" data-cmdk-url="${escapeAttr(it.url)}">
          <div class="cmdk-main">
            <div class="cmdk-title">${escapeHtml(it.label)}</div>
            <div class="cmdk-sub">${escapeHtml(String(subtitle || '').slice(0, 80))}</div>
          </div>
          <button type="button" class="cmdk-star ${fav ? 'is-fav' : ''}" data-cmdk-fav="${escapeAttr(it.url)}" title="${fav ? 'Quitar favorito' : 'Añadir favorito'}">★</button>
        </div>
      `;
    });

    LIST_EL.innerHTML = html || `<div class="cmdk-section">Sin resultados</div>`;

    // Scroll selected into view.
    const sel = LIST_EL.querySelector(`.cmdk-item[data-cmdk-index="${state.selectedIndex}"]`);
    if (sel && typeof sel.scrollIntoView === 'function') sel.scrollIntoView({ block: 'nearest' });
  };

  const open = () => {
    if (state.open) return;
    state.open = true;
    CMDK_EL.hidden = false;
    CMDK_EL.setAttribute('aria-hidden', 'false');
    state.query = '';
    state.selectedIndex = 0;
    INPUT_EL.value = '';
    render();
    setTimeout(() => INPUT_EL.focus(), 0);
  };

  const close = () => {
    if (!state.open) return;
    state.open = false;
    CMDK_EL.hidden = true;
    CMDK_EL.setAttribute('aria-hidden', 'true');
  };

  const go = (url) => {
    const target = normalizeUrl(url);
    if (!target) return;
    close();
    window.location.href = target;
  };

  const escapeHtml = (value) =>
    String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');

  const escapeAttr = (value) => escapeHtml(value).replace(/`/g, '&#96;');

  document.addEventListener('keydown', (ev) => {
    const k = String(ev.key || '').toLowerCase();
    const isK = k === 'k';
    if ((ev.ctrlKey || ev.metaKey) && isK) {
      ev.preventDefault();
      state.open ? close() : open();
      return;
    }
    if (!state.open) return;
    if (k === 'escape') {
      ev.preventDefault();
      close();
      return;
    }
    if (k === 'arrowdown') {
      ev.preventDefault();
      state.selectedIndex += 1;
      render();
      return;
    }
    if (k === 'arrowup') {
      ev.preventDefault();
      state.selectedIndex -= 1;
      render();
      return;
    }
    if (k === 'enter') {
      ev.preventDefault();
      const results = buildResults();
      const it = results[state.selectedIndex];
      if (it && it.url) go(it.url);
      return;
    }
  });

  document.querySelectorAll('[data-command-palette]').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      open();
      // Close "Menú" dropdown if click came from inside it.
      try {
        const details = btn.closest('details');
        if (details) details.removeAttribute('open');
      } catch {}
    });
  });

  CMDK_EL.querySelectorAll('[data-cmdk-close]').forEach((el) => el.addEventListener('click', close));

  INPUT_EL.addEventListener('input', () => {
    state.query = INPUT_EL.value || '';
    state.selectedIndex = 0;
    debouncedFetch(state.query);
    render();
  });

  LIST_EL.addEventListener('click', (ev) => {
    const target = ev.target;
    if (!(target instanceof HTMLElement)) return;
    const favUrl = target.getAttribute('data-cmdk-fav');
    if (favUrl) {
      ev.preventDefault();
      ev.stopPropagation();
      toggleFav(favUrl);
      render();
      return;
    }
    const item = target.closest('.cmdk-item');
    if (!item) return;
    const url = item.getAttribute('data-cmdk-url');
    if (url) go(url);
  });

  // Registra la página actual como reciente (sin tocar backend).
  try {
    recordRecent();
  } catch {}
})();
