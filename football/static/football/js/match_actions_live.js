window.initMatchActionsLive = function initMatchActionsLive(options) {
  const {
    quickHistoryState,
    matchHalfMinutes,
    quickHistoryModal,
    quickHistoryModalList,
    quickHistoryModalTitle,
    subsHistoryCard,
    showQuickHistoryModal,
    hideQuickHistoryModal,
    historyList,
    liveEventStore,
    refreshLiveStatsHud,
    persistentClockEl,
    persistentYellowEl,
    persistentRedEl,
    persistentSubsUsedEl,
    showPageStatus,
    elapsedRef,
    setPopupEditMode,
    popupEditToggle,
    actionInput,
    observationInput,
    matchClockDisplay,
    clockToggle,
    clockResetBtn,
    changeHalfBtn,
    liveStatsHud,
    liveStatsToggle,
    fieldZoneDefs,
    fieldPopup,
    popupForm,
    zoneLabel,
    zoneInput,
    highlight,
    interactiveSurface,
    quickButtons,
    quickButtonsContainer,
    popupCloseButtons,
    convocationCards,
    playerInput,
    submitUrl,
    updateUrl,
    eventsUrl,
    keepaliveUrl,
    reachabilityUrl: reachabilityUrlFromOptions,
    csrfToken,
    currentMatchId,
    deleteUrl,
    resetRegisterUrl,
    finalizeUrl,
    matchFinalizeBtn,
    matchInfoState,
    collectMatchInfoPayload,
    renderMatchInfoState,
    matchInfoCard,
    syncAutoFields,
    selectPlayer,
    resetClockExternal,
    registerLiveEvent,
    removeLiveEvent,
    onFieldTap,
    onSummaryChange,
    analysisVideoClipUrlTemplate,
    lastVideoClipBtn,
  } = options || {};

  const matchFinalizeButtons = (() => {
    if (!matchFinalizeBtn) return [];
    if (Array.isArray(matchFinalizeBtn)) return matchFinalizeBtn.filter(Boolean);
    // NodeList / HTMLCollection
    if (typeof matchFinalizeBtn.length === 'number' && typeof matchFinalizeBtn.item === 'function') {
      return Array.from(matchFinalizeBtn).filter(Boolean);
    }
    return [matchFinalizeBtn].filter(Boolean);
  })();

  const periodInput = (() => {
    try {
      return popupForm?.querySelector?.('input[name="period"]') || null;
    } catch (e) {
      return null;
    }
  })();

  // Safari (y iOS) puede restaurar la página desde bfcache con el estado DOM "congelado"
  // (por ejemplo: botones deshabilitados tras un submit). Forzamos un estado coherente.
  const forceEnableFinalizeButtons = () => {
    matchFinalizeButtons.forEach((btn) => {
      if (!btn) return;
      btn.disabled = false;
      btn.removeAttribute('aria-busy');
      try {
        delete btn.dataset.prevDisabled;
      } catch (err) {
        // Safari: `delete dataset.*` puede fallar en strict mode, usa removeAttribute.
        try {
          btn.removeAttribute('data-prev-disabled');
        } catch (e) {}
      }
    });
  };
  forceEnableFinalizeButtons();
  window.addEventListener('pageshow', (event) => {
    if (event && event.persisted) {
      forceEnableFinalizeButtons();
    }
  });

  const computeSubstitutionsCount = () => {
    const rows = quickHistoryState?.subs || [];
    let entries = 0;
    let exits = 0;
    let other = 0;
    rows.forEach((row) => {
      const text = String(row || '').toLowerCase();
      if (text.includes('entrada')) entries += 1;
      else if (text.includes('salida')) exits += 1;
      else other += 1;
    });
    return Math.max(entries + other, exits);
  };

  const quickCounters = {
    amarilla: document.getElementById('yellow-count'),
    roja: document.getElementById('red-count'),
    subs: document.getElementById('sub-count'),
    corner_for: document.getElementById('corner-for-count'),
    corner_against: document.getElementById('corner-against-count'),
    goal: document.getElementById('goal-count'),
    assist: document.getElementById('assist-count'),
  };
  const statusCounters = {
    amarilla: document.getElementById('status-yellow-count'),
    roja: document.getElementById('status-red-count'),
    subsUsed: document.getElementById('status-subs-used-count'),
    subsLeft: document.getElementById('status-subs-left-count'),
    cornerFor: document.getElementById('status-corner-for-count'),
    cornerAgainst: document.getElementById('status-corner-against-count'),
    goal: document.getElementById('status-goal-count'),
    assist: document.getElementById('status-assist-count'),
  };
  const MAX_SUBSTITUTIONS = 5;
  const quickStats = {
    amarilla: 0,
    roja: 0,
    subs: 0,
    corner_for: 0,
    corner_against: 0,
    goal: 0,
    assist: 0,
  };
  const undoLastActionBtn = document.getElementById('undo-last-action-btn');
  const offlineQueueBadge = document.getElementById('offline-queue-badge');
  const offlineQueueSyncBtn = document.getElementById('offline-queue-sync');
  const OFFLINE_ID_PREFIX = 'offline:';
  const redoStack = [];
  const offlineQueueKey = (() => {
    const mid = String(currentMatchId || '').trim() || 'unknown';
    return `webstats:live:queue:v1:${mid}`;
  })();
  const canUseStorage = (() => {
    try {
      const probeKey = '__live_queue_probe__';
      window.localStorage.setItem(probeKey, '1');
      window.localStorage.removeItem(probeKey);
      return true;
    } catch (error) {
      return false;
    }
  })();
  const liveStateKey = (() => {
    const mid = String(currentMatchId || '').trim();
    return mid ? `webstats:live:state:v1:${mid}` : '';
  })();
  const lastClipKey = (() => {
    const mid = String(currentMatchId || '').trim();
    return mid ? `webstats:live:last_clip:v1:${mid}` : '';
  })();
  const lastVideoTimeKey = (() => {
    const mid = String(currentMatchId || '').trim();
    return mid ? `webstats:live:last_video_time:v1:${mid}` : '';
  })();
  const recentActionsKey = 'webstats:live:recent_actions:v1';
  const proAutoSendStorageKey = 'webstats:match_actions:pro_autosend:v1';
  const safeParseJson = (raw, fallback) => {
    try {
      return JSON.parse(String(raw || ''));
    } catch (error) {
      return fallback;
    }
  };

  // `navigator.onLine` no es fiable en iOS/WKWebView. Si reporta offline, verificamos contra servidor.
  // Importante: endpoint público para no confundir "sesión caducada" con "offline".
  const reachabilityUrl = String(reachabilityUrlFromOptions || '/api/build/').trim() || '/api/build/';
  const isServerReachable = async () => {
    try {
      const opts = { method: 'GET', credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } };
      if (typeof AbortController !== 'undefined') {
        const ctrl = new AbortController();
        const timer = window.setTimeout(() => { try { ctrl.abort(); } catch (e) {} }, 2500);
        try {
          const resp = await fetch(reachabilityUrl, { ...opts, signal: ctrl.signal });
          return !!(resp && resp.ok);
        } catch (e) {
          return false;
        } finally {
          try { window.clearTimeout(timer); } catch (e) {}
        }
      }
      const resp = await fetch(reachabilityUrl, opts);
      return !!(resp && resp.ok);
    } catch (e) {
      return false;
    }
  };
  const ensureOnline = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator && navigator.onLine === false) {
        return await isServerReachable();
      }
    } catch (e) {}
    return true;
  };

  const buildClipUrl = (clipId) => {
    const id = Number(clipId) || 0;
    if (!id || !analysisVideoClipUrlTemplate) return '';
    const tpl = String(analysisVideoClipUrlTemplate || '').trim();
    // reverse('analysis-video-clip-view', 0) => ".../clip/0/"
    if (tpl.includes('/0/')) return tpl.replace('/0/', `/${id}/`);
    return tpl.replace(/\/\d+\/?$/, `/${id}/`);
  };

  const setLastClipUi = ({ clipId, label = '' } = {}) => {
    if (!lastVideoClipBtn) return;
    const url = buildClipUrl(clipId);
    if (!url) {
      lastVideoClipBtn.hidden = true;
      return;
    }
    lastVideoClipBtn.hidden = false;
    lastVideoClipBtn.setAttribute('href', url);
    lastVideoClipBtn.setAttribute('target', '_blank');
    lastVideoClipBtn.setAttribute('rel', 'noopener');
    const clean = String(label || '').trim();
    if (clean) lastVideoClipBtn.setAttribute('title', clean);
  };

  const persistLastClip = ({ clipId, label = '' } = {}) => {
    if (!canUseStorage || !lastClipKey) return;
    const id = Number(clipId) || 0;
    if (!id) return;
    try {
      window.localStorage.setItem(lastClipKey, JSON.stringify({ clip_id: id, label: String(label || '').slice(0, 220), at: Date.now() }));
    } catch (e) {}
  };

  const persistLastVideoTime = ({ timeMs = 0, videoId = 0, elapsedMs = 0, kickoffVideoMs = 0 } = {}) => {
    if (!canUseStorage || !lastVideoTimeKey) return;
    const t = Number(timeMs) || 0;
    if (!t) return;
    try {
      window.localStorage.setItem(
        lastVideoTimeKey,
        JSON.stringify({
          time_ms: t,
          video_id: Number(videoId) || 0,
          elapsed_ms: Number(elapsedMs) || 0,
          kickoff_video_ms: Number(kickoffVideoMs) || 0,
          at: Date.now(),
        })
      );
    } catch (e) {}
  };

  const restoreLastClip = () => {
    if (!canUseStorage || !lastClipKey) return;
    try {
      const raw = window.localStorage.getItem(lastClipKey) || '';
      const parsed = safeParseJson(raw, null);
      if (!parsed || typeof parsed !== 'object') return;
      const id = Number(parsed.clip_id) || 0;
      const label = String(parsed.label || '').trim();
      if (!id) return;
      setLastClipUi({ clipId: id, label });
    } catch (e) {}
  };
  const readOfflineQueue = () => {
    if (!canUseStorage) return [];
    try {
      const raw = window.localStorage.getItem(offlineQueueKey) || '';
      const list = safeParseJson(raw, []);
      return Array.isArray(list) ? list : [];
    } catch (error) {
      return [];
    }
  };
  const writeOfflineQueue = (list) => {
    if (!canUseStorage) return;
    try {
      window.localStorage.setItem(offlineQueueKey, JSON.stringify(Array.isArray(list) ? list : []));
    } catch (error) {
      // ignore quota errors
    }
  };
  const readLiveState = () => {
    if (!canUseStorage || !liveStateKey) return null;
    try {
      const raw = window.localStorage.getItem(liveStateKey) || '';
      const parsed = safeParseJson(raw, null);
      return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (error) {
      return null;
    }
  };
  const writeLiveState = (value) => {
    if (!canUseStorage || !liveStateKey) return;
    try {
      window.localStorage.setItem(liveStateKey, JSON.stringify(value && typeof value === 'object' ? value : {}));
    } catch (error) {
      // ignore quota errors
    }
  };
  const pushRecentAction = (label) => {
    if (!canUseStorage) return;
    const clean = String(label || '').trim();
    if (!clean) return;
    const normalize = (value) => {
      const raw = String(value || '').trim().toLowerCase();
      try {
        return raw.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      } catch (e) {
        return raw;
      }
    };
    const key = normalize(clean);
    if (!key) return;
    try {
      const raw = window.localStorage.getItem(recentActionsKey) || '[]';
      const parsed = safeParseJson(raw, []);
      const existing = Array.isArray(parsed) ? parsed.map((item) => String(item || '').trim()).filter(Boolean) : [];
      const next = [clean, ...existing.filter((item) => normalize(item) !== key)].slice(0, 12);
      window.localStorage.setItem(recentActionsKey, JSON.stringify(next));
    } catch (error) {
      // ignore
    }
  };
  const updateOfflineQueueUi = () => {
    const list = readOfflineQueue();
    const count = list.length;
    if (offlineQueueBadge) {
      offlineQueueBadge.hidden = count <= 0;
      offlineQueueBadge.textContent = count > 0 ? `Offline: ${count}` : '';
    }
    if (offlineQueueSyncBtn) {
      offlineQueueSyncBtn.hidden = count <= 0;
    }
  };
  restoreLastClip();
  const makeOfflineId = () => `${OFFLINE_ID_PREFIX}${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const isOfflineId = (value) => String(value || '').startsWith(OFFLINE_ID_PREFIX);
  const makeClientEventUid = () => {
    try {
      const cryptoObj = window.crypto || window.msCrypto;
      if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
        return cryptoObj.randomUUID();
      }
    } catch (error) {
      // ignore
    }
    return `evt:${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  };
  const isProModeEnabled = () => document.body.classList.contains('pro-mode');
  const isProAutoSendEnabled = () => {
    if (!canUseStorage) return false;
    try {
      return String(window.localStorage.getItem(proAutoSendStorageKey) || '') === '1';
    } catch (error) {
      return false;
    }
  };
  const eventIdInput = popupForm?.querySelector('input[name="event_id"]') || null;
  const setEditingEventId = (value) => {
    if (!eventIdInput) return;
    eventIdInput.value = value ? String(value) : '';
  };
  const getEditingEventId = () => {
    const raw = String(eventIdInput?.value || '').trim();
    const parsed = parseInt(raw, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  };
  const serializeFormData = (formData) => {
    const out = {};
    try {
      formData.forEach((value, key) => {
        if (value instanceof File) return;
        if (String(key) === 'csrfmiddlewaretoken') return;
        out[String(key)] = String(value);
      });
    } catch (error) {
      // ignore
    }
    return out;
  };
  const enqueueOfflineAction = ({ offlineId, fields }) => {
    const list = readOfflineQueue();
    list.push({
      v: 1,
      kind: 'action',
      offline_id: String(offlineId || ''),
      created_at: new Date().toISOString(),
      fields: fields && typeof fields === 'object' ? fields : {},
    });
    writeOfflineQueue(list);
    updateOfflineQueueUi();
  };
  const removeOfflineQueuedById = (offlineId) => {
    const id = String(offlineId || '');
    if (!id) return;
    const next = readOfflineQueue().filter((item) => String(item?.offline_id || '') !== id);
    writeOfflineQueue(next);
    updateOfflineQueueUi();
  };
  const replaceOfflineHistoryId = ({ offlineId, serverId }) => {
    const oldId = String(offlineId || '');
    const newId = String(serverId || '');
    if (!oldId || !newId) return;
    const article = historyList?.querySelector(`[data-event-id="${CSS.escape(oldId)}"]`);
    if (article) {
      article.dataset.eventId = newId;
      article.classList.remove('is-offline-pending');
      article.querySelector('.pending-pill')?.remove();
    }
    try {
      let action = '';
      let zone = '';
      let result = '';
      let minute = null;
      if (article) {
        const minuteText = article.querySelector('.hist-minute')?.textContent || '';
        const minuteParsed = parseInt(String(minuteText || '').replace(/[^\d]/g, ''), 10);
        if (Number.isFinite(minuteParsed)) minute = minuteParsed;
        const text = article.querySelector('.hist-text')?.textContent || '';
        const parts = text.split('·').map((part) => part.trim());
        action = parts[0] || '';
        zone = parts[1] || '';
        result = parts[2] || '';
      }
      removeLiveEvent(oldId);
      registerLiveEvent({ id: newId, action, zone, result, minute });
    } catch (error) {
      // ignore
    }
  };
  let flushOfflineInFlight = false;
  const flushOfflineQueue = async ({ limit = 20 } = {}) => {
    if (flushOfflineInFlight) return;
    if (!(await ensureOnline())) {
      updateOfflineQueueUi();
      return;
    }
    const list = readOfflineQueue();
    if (!list.length) {
      updateOfflineQueueUi();
      return;
    }
    flushOfflineInFlight = true;
    try {
      let processed = 0;
      for (const item of list.slice(0, limit)) {
        if (!item || item.kind !== 'action') continue;
        const fields = item.fields && typeof item.fields === 'object' ? item.fields : {};
        const offlineId = String(item.offline_id || '');
        if (!offlineId) continue;
        const formData = new FormData();
        Object.entries(fields).forEach(([key, value]) => {
          if (value == null) return;
          formData.set(String(key), String(value));
        });
        // Siempre fuerza match_id en el envío.
        if (currentMatchId) formData.set('match_id', currentMatchId);
        try {
          const response = await fetch(submitUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
            body: formData,
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok) {
            // Si la sesión caducó, paramos: no queremos perder cola.
            if (response.status === 401 || response.status === 403) {
              showPageStatus('Sesión caducada. Inicia sesión y pulsa “Sincronizar”.', 'warning', 7000);
              break;
            }
            showPageStatus(data.error || 'No se pudo sincronizar una acción offline.', 'danger', 5200);
            break;
          }
          // Actualiza el placeholder en historial y el store.
          if (data?.id) replaceOfflineHistoryId({ offlineId, serverId: data.id });
          removeOfflineQueuedById(offlineId);
          processed += 1;
        } catch (error) {
          // Problema de red: paramos y dejamos cola intacta.
          break;
        }
      }
      if (processed) showPageStatus(`Sincronizadas: ${processed}.`, 'success', 2600);
    } finally {
      flushOfflineInFlight = false;
      updateOfflineQueueUi();
    }
  };
  updateOfflineQueueUi();
  offlineQueueSyncBtn?.addEventListener('click', () => flushOfflineQueue());
  window.addEventListener('online', () => flushOfflineQueue({ limit: 50 }));
  try { window.setInterval(() => flushOfflineQueue({ limit: 10 }), 15_000); } catch (error) { /* ignore */ }
  const emitSummaryChange = () => {
    if (typeof onSummaryChange !== 'function') return;
    try {
      const pendingEl = document.getElementById('persistent-pending');
      if (pendingEl && historyList) {
        const count = historyList.querySelectorAll('[data-event-id]').length;
        pendingEl.textContent = String(count);
      }
    } catch (error) {
      // ignore
    }
    onSummaryChange({
      actions: liveEventStore.size,
      yellow: quickStats.amarilla,
      red: quickStats.roja,
      subs: quickStats.subs,
      cornerFor: quickStats.corner_for,
      cornerAgainst: quickStats.corner_against,
      goals: quickStats.goal,
      assists: quickStats.assist,
      elapsedSeconds: elapsedRef.value,
      matchInfo: { ...matchInfoState },
    });
  };

  const clearRegisterHistoryUI = () => {
    if (!historyList) return;
    historyList.innerHTML = '';
    const emptyItem = document.createElement('article');
    emptyItem.className = 'history-item';
    emptyItem.innerHTML = `
      <span class="hist-minute">—</span>
      <strong>Sin acciones todavía</strong>
      <p class="hist-text">Comienza el registro para ver cómo se llenan aquí.</p>
    `;
    historyList.appendChild(emptyItem);
  };

  const refreshStatusCounters = () => {
    quickStats.subs = computeSubstitutionsCount();
    if (statusCounters.amarilla) statusCounters.amarilla.textContent = quickStats.amarilla;
    if (persistentYellowEl) persistentYellowEl.textContent = quickStats.amarilla;
    if (statusCounters.roja) statusCounters.roja.textContent = quickStats.roja;
    if (persistentRedEl) persistentRedEl.textContent = quickStats.roja;
    if (statusCounters.subsUsed) statusCounters.subsUsed.textContent = quickStats.subs;
    if (persistentSubsUsedEl) persistentSubsUsedEl.textContent = quickStats.subs;
    if (statusCounters.subsLeft) statusCounters.subsLeft.textContent = Math.max(0, MAX_SUBSTITUTIONS - quickStats.subs);
    if (statusCounters.cornerFor) statusCounters.cornerFor.textContent = quickStats.corner_for;
    if (statusCounters.cornerAgainst) statusCounters.cornerAgainst.textContent = quickStats.corner_against;
    if (quickCounters.subs) quickCounters.subs.textContent = String(quickStats.subs);
    if (statusCounters.goal) statusCounters.goal.textContent = String(quickStats.goal || 0);
    if (statusCounters.assist) statusCounters.assist.textContent = String(quickStats.assist || 0);
    if (quickCounters.goal) quickCounters.goal.textContent = String(quickStats.goal || 0);
    if (quickCounters.assist) quickCounters.assist.textContent = String(quickStats.assist || 0);
    emitSummaryChange();
  };

  const renderQuickHistoryPreview = (historyKey) => {
    const quickHistoryContainers = {
      amarilla: document.getElementById('yellow-history'),
      roja: document.getElementById('red-history'),
      subs: document.getElementById('sub-history'),
      corner_for: document.getElementById('corner-for-history'),
      corner_against: document.getElementById('corner-against-history'),
      goal: document.getElementById('goal-history'),
      assist: document.getElementById('assist-history'),
    };
    const container = quickHistoryContainers[historyKey];
    if (!container) return;
    container.innerHTML = '';
    const entries = quickHistoryState[historyKey] || [];
    const parseHistoryEntry = (text) => {
      const raw = String(text || '').trim();
      if (!raw) return null;
      const parts = raw.split('·').map((part) => part.trim()).filter(Boolean);
      if (parts.length < 2) return null;
      const name = parts[0] || '';
      const minutePart = parts[1] || '';
      const minute = parseInt(minutePart.replace(/[^\d]/g, ''), 10);
      const label = parts.slice(2).join(' · ').trim();
      if (!Number.isFinite(minute)) return null;
      return { name, minute, label: label || '' };
    };
    const groupSubstitutionEntries = (rows) => {
      const parsed = rows.map(parseHistoryEntry).filter(Boolean);
      if (!parsed.length) return rows;
      const groups = new Map();
      parsed.forEach((item) => {
        const key = String(item.minute);
        const existing = groups.get(key) || { minute: item.minute, inName: '', outName: '' };
        const label = String(item.label || '').toLowerCase();
        if (label.includes('salida')) existing.outName = existing.outName || item.name;
        else if (label.includes('entrada')) existing.inName = existing.inName || item.name;
        groups.set(key, existing);
      });
      const grouped = Array.from(groups.values())
        .sort((a, b) => a.minute - b.minute)
        .map((g) => {
          if (g.inName && g.outName) return `${g.minute}' · SALE ${g.outName} · ENTRA ${g.inName}`.toUpperCase();
          if (g.outName) return `${g.minute}' · SALE ${g.outName}`.toUpperCase();
          if (g.inName) return `${g.minute}' · ENTRA ${g.inName}`.toUpperCase();
          return `${g.minute}' · SUSTITUCIÓN`.toUpperCase();
        });
      return grouped.length ? grouped : rows;
    };
    const displayEntries = historyKey === 'subs' ? groupSubstitutionEntries(entries) : entries;
    displayEntries.slice(-3).forEach((text) => {
      const entry = document.createElement('span');
      entry.textContent = text;
      container.appendChild(entry);
    });
    container.classList.toggle('is-clickable', entries.length > 0);
    container.dataset.totalEntries = String(entries.length);
    if (historyKey === 'subs') {
      const meta = document.getElementById('sub-history-meta');
      if (meta) {
        meta.textContent = entries.length ? `Pulsa para ver ${entries.length} cambios` : 'Pulsa para ver todos los cambios';
      }
    }
  };

  const resetRegisterHudState = () => {
    liveEventStore.clear();
    refreshLiveStatsHud();
    quickStats.amarilla = 0;
    quickStats.roja = 0;
    quickStats.subs = 0;
    quickStats.corner_for = 0;
    quickStats.corner_against = 0;
    quickStats.goal = 0;
    quickStats.assist = 0;
    Object.keys(quickHistoryState).forEach((key) => {
      quickHistoryState[key] = [];
      renderQuickHistoryPreview(key);
    });
    Object.entries(quickCounters).forEach(([key, el]) => {
      if (el) el.textContent = String(quickStats[key] || 0);
    });
    refreshStatusCounters();
  };

  const incrementQuickCounter = (dropKey) => {
    const counterKey =
      dropKey === 'amarilla'
        ? 'amarilla'
        : dropKey === 'roja'
        ? 'roja'
        : dropKey === 'corner_for'
        ? 'corner_for'
        : dropKey === 'corner_against'
        ? 'corner_against'
        : dropKey === 'goal'
        ? 'goal'
        : dropKey === 'assist'
        ? 'assist'
        : 'subs';
    if (counterKey !== 'subs') {
      quickStats[counterKey] += 1;
      const counterEl = quickCounters[counterKey];
      if (counterEl) counterEl.textContent = quickStats[counterKey];
    }
    refreshStatusCounters();
  };

  const appendQuickHistory = (dropKey, playerName, minute, label) => {
    const historyKey = dropKey === 'subida' || dropKey === 'bajada' ? 'subs' : dropKey;
    if (!historyKey || typeof historyKey !== 'string') return;
    const entryText = `${playerName} · ${minute}' · ${label || ''}`.trim().toUpperCase();
    if (!quickHistoryState[historyKey]) quickHistoryState[historyKey] = [];
    quickHistoryState[historyKey].push(entryText);
    renderQuickHistoryPreview(historyKey);
  };

  const classifyCounterDropKey = ({ action = '', result = '' }) => {
    const actionText = String(action || '').toLowerCase();
    const resultText = String(result || '').toLowerCase();
    if (actionText.includes('asist') || resultText.includes('asist')) return 'assist';
    if (actionText.includes('gol') || resultText.includes('gol')) return 'goal';
    if (actionText.includes('roja') || resultText.includes('roja')) return 'roja';
    if (actionText.includes('amarilla') || resultText.includes('amarilla')) return 'amarilla';
    const isCorner = actionText.includes('corner') || actionText.includes('córner') || actionText.includes('esquina');
    if (isCorner) {
      if (actionText.includes('en contra') || resultText.includes('en contra') || actionText.includes('contra') || resultText.includes('contra')) return 'corner_against';
      if (actionText.includes('a favor') || resultText.includes('a favor') || actionText.includes('favor') || resultText.includes('favor')) return 'corner_for';
    }
    if (actionText.includes('sustituci') || actionText.includes('cambio') || resultText.includes('entrada') || resultText.includes('salida')) {
      return resultText.includes('salida') ? 'bajada' : 'subida';
    }
    return '';
  };

	  const bootstrapQuickHudFromExistingHistory = () => {
	    if (!historyList) return;
	    // Sincroniza estado interno (quickStats/quickHistory) con el historial visible.
	    // Importante: esto debe ser idempotente para que editar/borrar acciones mantenga contadores correctos.
	    const resetKeys = ['amarilla', 'roja', 'corner_for', 'corner_against', 'goal', 'assist', 'subs'];
	    resetKeys.forEach((key) => { quickHistoryState[key] = []; });
	    const counts = {
	      amarilla: 0,
	      roja: 0,
	      corner_for: 0,
	      corner_against: 0,
	      goal: 0,
	      assist: 0,
	    };

	    const safeText = (value) => String(value ?? '').trim();
	    const pushHistoryRow = (historyKey, playerName, minute, label) => {
	      if (!historyKey) return;
      const minuteNum = parseInt(String(minute ?? '').replace(/[^\d]/g, ''), 10);
      const minuteLabel = Number.isFinite(minuteNum) ? minuteNum : Math.floor(elapsedRef.value / 60);
      const nameLabel = safeText(playerName).toUpperCase() || 'JUGADOR';
      const entryText = `${nameLabel} · ${minuteLabel}' · ${safeText(label).toUpperCase()}`.trim();
      if (!quickHistoryState[historyKey]) quickHistoryState[historyKey] = [];
      quickHistoryState[historyKey].push(entryText);
    };

    historyList.querySelectorAll('.history-item[data-event-id]').forEach((item) => {
      const text = item.querySelector('.hist-text')?.textContent || '';
      const [action = '', zone = '', result = ''] = text.split('·').map((part) => part.trim());
      const derived = classifyCounterDropKey({ action, result });
      if (!derived) return;
      const minuteLabel = item.querySelector('.hist-minute')?.textContent || '';
      const playerLabel = item.querySelector('strong')?.textContent || '';
	      const normalizedPlayer = safeText(playerLabel).replace(/^#\S+\s+/, '').trim() || playerLabel || 'Jugador';

	      if (derived === 'amarilla') {
	        counts.amarilla += 1;
	        pushHistoryRow('amarilla', normalizedPlayer, minuteLabel, result || action);
	      } else if (derived === 'roja') {
	        counts.roja += 1;
	        pushHistoryRow('roja', normalizedPlayer, minuteLabel, result || action);
	      } else if (derived === 'corner_for') {
	        counts.corner_for += 1;
	        pushHistoryRow('corner_for', normalizedPlayer, minuteLabel, result || action);
	      } else if (derived === 'corner_against') {
	        counts.corner_against += 1;
	        pushHistoryRow('corner_against', normalizedPlayer, minuteLabel, result || action);
	      } else if (derived === 'goal') {
	        counts.goal += 1;
	        pushHistoryRow('goal', normalizedPlayer, minuteLabel, result || action || 'Gol');
	      } else if (derived === 'assist') {
	        counts.assist += 1;
	        pushHistoryRow('assist', normalizedPlayer, minuteLabel, result || action || 'Asistencia');
	      } else if (derived === 'subida' || derived === 'bajada') {
	        pushHistoryRow('subs', normalizedPlayer, minuteLabel, result || action || 'Sustitución');
	      }
	    });

	    // Aplica contadores recalculados.
	    quickStats.amarilla = counts.amarilla;
	    quickStats.roja = counts.roja;
	    quickStats.corner_for = counts.corner_for;
	    quickStats.corner_against = counts.corner_against;
	    quickStats.goal = counts.goal;
	    quickStats.assist = counts.assist;
	    Object.entries({
	      amarilla: quickStats.amarilla,
	      roja: quickStats.roja,
	      corner_for: quickStats.corner_for,
	      corner_against: quickStats.corner_against,
	      goal: quickStats.goal,
	      assist: quickStats.assist,
	    }).forEach(([key, value]) => {
	      const el = quickCounters[key];
	      if (el) el.textContent = String(value || 0);
	    });

	    // Actualiza previews/modales y contadores "status".
	    renderQuickHistoryPreview('amarilla');
	    renderQuickHistoryPreview('roja');
	    renderQuickHistoryPreview('corner_for');
	    renderQuickHistoryPreview('corner_against');
	    renderQuickHistoryPreview('goal');
	    renderQuickHistoryPreview('assist');
	    renderQuickHistoryPreview('subs');
	    refreshStatusCounters();
	  };

  Object.entries({
    amarilla: document.getElementById('yellow-history'),
    roja: document.getElementById('red-history'),
    subs: document.getElementById('sub-history'),
    corner_for: document.getElementById('corner-for-history'),
    corner_against: document.getElementById('corner-against-history'),
    goal: document.getElementById('goal-history'),
    assist: document.getElementById('assist-history'),
  }).forEach(([historyKey, container]) => {
    if (!container) return;
    container.style.cursor = 'pointer';
    container.addEventListener('click', () => {
      const title =
        historyKey === 'amarilla' ? 'Amonestaciones (amarillas)'
          : historyKey === 'roja' ? 'Expulsiones (rojas)'
          : historyKey === 'corner_for' ? 'Córners a favor'
          : historyKey === 'corner_against' ? 'Córners en contra'
          : historyKey === 'goal' ? 'Goles'
          : historyKey === 'assist' ? 'Asistencias'
          : 'Sustituciones';
      showQuickHistoryModal(historyKey, title);
    });
  });

  if (subsHistoryCard) {
    const openSubsHistory = (event) => {
      if (event?.target?.closest('.quick-drop')) return;
      showQuickHistoryModal('subs', 'Sustituciones');
    };
    subsHistoryCard.addEventListener('click', openSubsHistory);
    subsHistoryCard.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openSubsHistory(event);
      }
    });
  }

  try {
    const initialSubHistory = JSON.parse(document.getElementById('substitution-history-data')?.textContent || '[]');
    if (Array.isArray(initialSubHistory) && initialSubHistory.length) {
      quickHistoryState.subs = initialSubHistory.map((value) => String(value || '').trim()).filter(Boolean);
      quickStats.subs = computeSubstitutionsCount();
      if (quickCounters.subs) quickCounters.subs.textContent = String(quickStats.subs);
      renderQuickHistoryPreview('subs');
      refreshStatusCounters();
    }
  } catch (err) {
    console.warn('No se pudo cargar historial inicial de sustituciones', err);
  }
  bootstrapQuickHudFromExistingHistory();
  refreshStatusCounters();

  let clockInterval = null;
  let clockRunning = false;
  let currentHalf = 1;
  let wakeLockSentinel = null;
  let wakeLockEnabled = false;
  const halfSeconds = (() => {
    const value = Number(matchHalfMinutes);
    if (!Number.isFinite(value) || value <= 0) return 45 * 60;
    return Math.round(value * 60);
  })();
  const formatClock = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };
  const getCurrentMatchMinute = () => Math.floor(elapsedRef.value / 60);
  let lastPersistedAt = 0;
  const persistClockState = () => {
    if (!liveStateKey) return;
    const now = Date.now();
    // Evita escribir en localStorage cada segundo.
    if (now - lastPersistedAt < 5000) return;
    lastPersistedAt = now;
    writeLiveState({
      v: 1,
      saved_at: now,
      elapsed: Number(elapsedRef.value) || 0,
      half: currentHalf,
      running: Boolean(clockRunning),
      offline_queue: (() => {
        try {
          return readOfflineQueue().length;
        } catch (e) {
          return 0;
        }
      })(),
    });
  };
  const restoreClockState = () => {
    const state = readLiveState();
    if (!state || state.v !== 1) return;
    const savedAt = Number(state.saved_at) || 0;
    // Si es muy antiguo, ignora (nuevo partido / dispositivo).
    if (savedAt && Date.now() - savedAt > 8 * 60 * 60 * 1000) return;
    const elapsed = Number(state.elapsed);
    if (Number.isFinite(elapsed) && elapsed >= 0) {
      elapsedRef.value = Math.round(elapsed);
    }
    const half = Number(state.half);
    if (half === 2) {
      currentHalf = 2;
      if (changeHalfBtn) changeHalfBtn.textContent = '2ª Parte';
    } else {
      currentHalf = 1;
      if (changeHalfBtn) changeHalfBtn.textContent = '1ª Parte';
    }
  };
  const requestWakeLock = async () => {
    if (!wakeLockEnabled) return;
    if (!navigator.wakeLock || typeof navigator.wakeLock.request !== 'function') return;
    try {
      if (wakeLockSentinel) return;
      wakeLockSentinel = await navigator.wakeLock.request('screen');
      wakeLockSentinel.addEventListener('release', () => {
        wakeLockSentinel = null;
      });
    } catch (error) {
      // No disponible / permiso denegado: ignora.
      wakeLockSentinel = null;
    }
  };
  const releaseWakeLock = async () => {
    try {
      await wakeLockSentinel?.release?.();
    } catch (error) {
      // ignore
    } finally {
      wakeLockSentinel = null;
    }
  };
  const updateClockDisplay = () => {
    if (matchClockDisplay) matchClockDisplay.textContent = formatClock(elapsedRef.value);
    if (persistentClockEl) persistentClockEl.textContent = formatClock(elapsedRef.value);
    if (periodInput) periodInput.value = String(Number(currentHalf) || 1);
    syncAutoFields();
    refreshLiveStatsHud();
    emitSummaryChange();
    persistClockState();
  };
  const pauseClock = () => {
    clockRunning = false;
    if (clockToggle) clockToggle.textContent = '►';
    clearInterval(clockInterval);
    clockInterval = null;
    wakeLockEnabled = false;
    void releaseWakeLock();
    persistClockState();
  };
  const resetClock = ({ keepHalf = false } = {}) => {
    pauseClock();
    elapsedRef.value = keepHalf && currentHalf === 2 ? halfSeconds : 0;
    if (!keepHalf) {
      currentHalf = 1;
      if (changeHalfBtn) changeHalfBtn.textContent = '1ª Parte';
    }
    updateClockDisplay();
  };
  const startClock = () => {
    if (clockRunning) return;
    clockRunning = true;
    if (clockToggle) clockToggle.textContent = '||';
    wakeLockEnabled = true;
    void requestWakeLock();
    clockInterval = setInterval(() => {
      elapsedRef.value += 1;
      updateClockDisplay();
    }, 1000);
  };

  if (clockToggle) {
    if (clockToggle.dataset.boundClock !== '1') {
      clockToggle.addEventListener('click', (event) => {
        event.stopPropagation();
        if (clockRunning) pauseClock(); else startClock();
      });
      clockToggle.dataset.boundClock = '1';
    }
  }
  if (clockResetBtn) {
    if (clockResetBtn.dataset.boundClock !== '1') {
      clockResetBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        resetClock();
      });
      clockResetBtn.dataset.boundClock = '1';
    }
  }
  if (changeHalfBtn) {
    if (changeHalfBtn.dataset.boundClock !== '1') {
      changeHalfBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        pauseClock();
        if (currentHalf === 1) {
          currentHalf = 2;
          elapsedRef.value = halfSeconds;
          changeHalfBtn.textContent = '2ª Parte';
        } else {
          currentHalf = 1;
          elapsedRef.value = 0;
          changeHalfBtn.textContent = '1ª Parte';
        }
        updateClockDisplay();
      });
      changeHalfBtn.dataset.boundClock = '1';
    }
  }
  // Restaura cronómetro si el iPad recarga (suspensión/auto-lock).
  try {
    restoreClockState();
  } catch (error) {
    // ignore
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      void requestWakeLock();
      persistClockState();
    } else {
      persistClockState();
    }
  });
  window.addEventListener('pagehide', () => {
    persistClockState();
  });
  updateClockDisplay();
  setPopupEditMode(false);
  if (liveStatsHud && liveStatsToggle) {
    liveStatsHud.classList.add('is-collapsed');
    liveStatsToggle.textContent = 'Mostrar';
    liveStatsToggle.addEventListener('click', () => {
      const collapsed = liveStatsHud.classList.contains('is-collapsed');
      liveStatsHud.classList.toggle('is-collapsed', !collapsed);
      liveStatsToggle.textContent = collapsed ? 'Ocultar' : 'Mostrar';
    });
  }

  const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
  const isPointInsideZone = (zone, xPercent, yPercent) => (
    xPercent >= zone.left_pct &&
    xPercent <= zone.left_pct + zone.width_pct &&
    yPercent >= zone.top_pct &&
    yPercent <= zone.top_pct + zone.height_pct
  );
  const findClosestZone = (xPercent, yPercent) => {
    const directMatch = fieldZoneDefs.find((zone) => isPointInsideZone(zone, xPercent, yPercent));
    if (directMatch) return directMatch;
    let closest = null;
    let closestDist = Infinity;
    fieldZoneDefs.forEach((zone) => {
      const centerX = zone.left_pct + zone.width_pct / 2;
      const centerY = zone.top_pct + zone.height_pct / 2;
      const dist = (xPercent - centerX) ** 2 + (yPercent - centerY) ** 2;
      if (dist < closestDist) {
        closestDist = dist;
        closest = zone;
      }
    });
    return closest;
  };
  const showPopup = (x, y, { preserveEditing = false } = {}) => {
    // Abriendo el popup desde el campo => modo creación, no edición (salvo que se indique lo contrario).
    if (!preserveEditing) setEditingEventId('');
    const rect = interactiveSurface.getBoundingClientRect();
    const width = fieldPopup.offsetWidth;
    const height = fieldPopup.offsetHeight;
    const left = clamp(x - width / 2, 8, rect.width - width - 8);
    let top = y - height - 12;
    if (top < 8) top = clamp(y + 12, 8, rect.height - height - 8);
    fieldPopup.style.left = `${left}px`;
    fieldPopup.style.top = `${top}px`;
    fieldPopup.classList.add('is-visible');
    // UX iPad: no bloquear el flujo obligando a elegir "Resultado" cada vez.
    ensureResultSelected(String(actionInput?.value || '').trim());
    syncAutoFields();
  };
  const hidePopup = () => {
    fieldPopup.classList.remove('is-visible');
    setPopupEditMode(false);
  };
  popupCloseButtons.forEach((btn) => btn.addEventListener('click', hidePopup));
  if (popupEditToggle) {
    popupEditToggle.addEventListener('click', () => {
      setPopupEditMode(true, { focusField: true });
    });
  }
  fieldPopup.addEventListener('click', (event) => event.stopPropagation());
  const resultSelect = popupForm?.querySelector?.('select[name="result"]') || null;
  const teamOnlyInput = popupForm?.querySelector?.('input[name="team_only"]') || null;
  const ensureResultSelected = (actionLabel = '') => {
    if (!resultSelect) return '';
    const current = String(resultSelect.value || '').trim();
    if (current) return current;
    const options = Array.from(resultSelect.options || [])
      .map((opt) => String(opt.value || '').trim())
      .filter(Boolean);
    if (!options.length) return '';
    const key = String(actionLabel || '').trim().toLowerCase();
    const isShot = key.includes('disparo') || key.includes('tiro') || key.includes('remate') || key.includes('chut') || key.includes('shot');
    const preferredShot = options.find((v) => String(v).toLowerCase() === 'a puerta');
    const preferred = (isShot && preferredShot) ? preferredShot : options[0];
    try {
      resultSelect.value = preferred;
      resultSelect.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) {}
    return preferred;
  };
  const setResultValue = (value) => {
    const v = String(value || '').trim();
    if (!resultSelect || !v) return false;
    try {
      const exists = Array.from(resultSelect.options || []).some((opt) => String(opt.value || '') === v);
      if (!exists) {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        resultSelect.appendChild(opt);
      }
    } catch (e) {}
    resultSelect.value = v;
    try {
      resultSelect.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) {}
    return true;
  };
  const normalizeButtonsList = (value) => {
    if (!value) return [];
    if (Array.isArray(value)) return value.filter(Boolean);
    if (typeof value.length === 'number') return Array.from(value).filter(Boolean);
    return [];
  };
  const getQuickButtons = () => {
    if (quickButtonsContainer && quickButtonsContainer.querySelectorAll) {
      return Array.from(quickButtonsContainer.querySelectorAll('.quick-action')).filter(Boolean);
    }
    return normalizeButtonsList(quickButtons);
  };
  const applyQuickButton = (btn) => {
    if (!btn) return;
    const all = getQuickButtons();
    try {
      all.forEach((other) => other.classList.remove('quake-action-active'));
    } catch (e) {}
    try {
      btn.classList.add('quake-action-active');
    } catch (e) {}
    const action = String(
      btn.dataset.action
        || btn.dataset.eventType
        || btn.dataset.actionType
        || btn.getAttribute?.('data-action')
        || btn.getAttribute?.('data-event-type')
        || btn.getAttribute?.('data-action-type')
        || btn.textContent
        || ''
    ).trim();
    if (actionInput && action) actionInput.value = action;
    if (action) pushRecentAction(action);
    try {
      if (teamOnlyInput) teamOnlyInput.value = btn.dataset.teamOnly === '1' ? '1' : '0';
    } catch (e) {}
    try {
      if (btn.dataset.result) setResultValue(btn.dataset.result);
    } catch (e) {}
    try {
      // Si el atajo no define resultado, usa default para permitir auto-enviar.
      ensureResultSelected(action);
    } catch (e) {}
    try {
      actionInput?.dispatchEvent?.(new Event('input', { bubbles: true }));
    } catch (e) {}
    try {
      schedulePopupAutoSend('quick_action');
    } catch (e) {}
  };

  let popupAutoSendTimer = null;
  const schedulePopupAutoSend = (source) => {
    if (!isProAutoSendEnabled()) return;
    if (!fieldPopup?.classList?.contains('is-visible')) return;
    // Evita auto-enviar mientras el usuario está corrigiendo una acción existente.
    try {
      const editingId = getEditingEventId && typeof getEditingEventId === 'function' ? getEditingEventId() : null;
      if (editingId) return;
    } catch (e) {}
    if (popupAutoSendTimer) window.clearTimeout(popupAutoSendTimer);
    popupAutoSendTimer = window.setTimeout(() => {
      popupAutoSendTimer = null;
      if (actionSubmitInFlight) return;
      const currentAction = String(actionInput?.value || '').trim();
      if (!currentAction) return;
      const isTeamOnlyAction = isTeamOnlyActionValue(currentAction);
      if (!isTeamOnlyAction && !String(playerInput?.value || '').trim()) return;
      ensureResultSelected(currentAction);
      if (!String(resultSelect?.value || '').trim()) return;
      // En popup (modo iPad), la zona viene del tap en el campo. Sin zona, preferimos no auto-enviar.
      if (!String(zoneInput?.value || '').trim()) return;
      try {
        syncAutoFields();
      } catch (e) {}
      const payload = new FormData(popupForm);
      void submitPopupAction(payload, { isTeamOnlyAction, source: 'pro_autosend' });
    }, 60);
  };

  // Delegación: soporta re-render de atajos sin reiniciar la página.
  const initialButtons = getQuickButtons();
  initialButtons.forEach((btn) => btn.addEventListener('click', () => applyQuickButton(btn)));
  if (quickButtonsContainer && quickButtonsContainer.addEventListener) {
    let lastQuickTapAt = 0;
    const handleQuickTap = (event) => {
      const target = event?.target;
      const btn = target && target.closest ? target.closest('.quick-action') : null;
      if (!btn) return;
      // Evita doble ejecución cuando iOS dispara touchend/pointerup + click.
      const now = Date.now();
      if (now - lastQuickTapAt < 360 && (event?.type === 'click')) return;
      lastQuickTapAt = now;
      try { event.preventDefault(); } catch (e) {}
      try { event.stopPropagation?.(); } catch (e) {}
      applyQuickButton(btn);
    };
    quickButtonsContainer.addEventListener('click', handleQuickTap);
    // iOS/WKWebView: a veces el `click` no llega o llega tarde; `pointerup/touchend` es más fiable.
    quickButtonsContainer.addEventListener('pointerup', handleQuickTap);
    quickButtonsContainer.addEventListener('touchend', handleQuickTap, { passive: false });
  }

  // Auto-enviar desde popup: cuando ya están todos los campos, guarda y vuelve al campo.
  try {
    if (playerInput) {
      playerInput.addEventListener('change', () => schedulePopupAutoSend('player'));
      playerInput.addEventListener('input', () => schedulePopupAutoSend('player'));
    }
    if (actionInput) {
      actionInput.addEventListener('input', () => schedulePopupAutoSend('action'));
      actionInput.addEventListener('change', () => schedulePopupAutoSend('action'));
    }
    if (resultSelect) {
      resultSelect.addEventListener('change', () => schedulePopupAutoSend('result'));
    }
    if (zoneInput) {
      zoneInput.addEventListener('input', () => schedulePopupAutoSend('zone'));
      zoneInput.addEventListener('change', () => schedulePopupAutoSend('zone'));
    }
  } catch (e) {}

  // Hotkeys: rehace lookup dinámico (por si se reconfiguran atajos).
  window.addEventListener('keydown', (event) => {
    if (!event || event.defaultPrevented) return;
    const key = String(event.key || '').trim();
    if (!'123456789'.includes(key)) return;
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)) return;
    const btn = getQuickButtons().find((candidate) => String(candidate?.dataset?.hotkey || '').trim() === key);
    if (!btn) return;
    event.preventDefault();
    applyQuickButton(btn);
  });

  const appendHistoryEntry = ({ minute, player, action, zone, result, event_id, pending = false, video_link = null, system = '' }) => {
    if (!historyList) return false;
    if (event_id && historyList.querySelector(`[data-event-id="${event_id}"]`)) return false;
    const item = document.createElement('article');
    item.className = 'history-item';
    if (pending) item.classList.add('is-offline-pending');
    const sys = String(system || '').trim() || (pending ? 'offline' : 'touch-field');
    if (sys) item.dataset.system = sys;
    if (player?.id) {
      item.dataset.playerId = String(player.id);
    }
    const vlink = (video_link && typeof video_link === 'object') ? video_link : null;
    const vTimeMs = vlink ? (Number(vlink.time_ms) || 0) : 0;
    const vElapsedMs = vlink ? (Number(vlink.elapsed_ms) || 0) : 0;
    const vKickoffMs = vlink ? (Number(vlink.kickoff_video_ms) || 0) : 0;
    const vVideoId = vlink ? (Number(vlink.video_id) || 0) : 0;
    const vClipId = vlink ? (Number(vlink.clip_id) || 0) : 0;
    const numericMinute = Number(minute);
    const minuteLabel = Number.isFinite(numericMinute) ? `${numericMinute}'` : "Ahora'";
    const playerNumber = player?.number || '--';
    const playerName = String(player?.name || 'EQUIPO').toUpperCase();
    item.innerHTML = `
      <span class="hist-minute">${minuteLabel}</span>
      ${pending ? `<span class="pending-pill">PENDIENTE</span>` : (sys === 'touch-field-final' ? `<span class="pending-pill" style="background: rgba(47,125,50,0.16); border-color: rgba(47,125,50,0.35); color: rgba(226,255,232,0.92);">GUARDADA</span>` : '')}
      <strong>#${playerNumber} ${playerName}</strong>
      <p class="hist-text">${action} · ${zone || '-'} · ${result || ''}</p>
      <div class="history-actions">
        ${vTimeMs ? `<button type="button" class="history-replay" aria-label="Replay vídeo" data-vtime="${vTimeMs}" data-velapsed="${vElapsedMs}" data-vkickoff="${vKickoffMs}" data-vid="${vVideoId}" data-vclip="${vClipId}">🎬</button>` : ''}
        ${(sys === 'touch-field-final') ? '' : '<button type="button" class="history-delete" aria-label="Eliminar acción">🗑</button>'}
      </div>
    `;
    if (event_id) item.dataset.eventId = event_id;
    if (vTimeMs) {
      item.dataset.videoTimeMs = String(vTimeMs);
      item.dataset.videoElapsedMs = String(vElapsedMs || 0);
      item.dataset.videoKickoffMs = String(vKickoffMs || 0);
      item.dataset.videoId = String(vVideoId || 0);
      item.dataset.videoClipId = String(vClipId || 0);
    }
    historyList.prepend(item);
    if (historyList.children.length > 24) historyList.removeChild(historyList.lastChild);
    registerLiveEvent({ id: event_id, action, zone, result, minute: numericMinute });
    return true;
  };

  historyList.querySelectorAll('.history-item').forEach((item) => {
    const minuteText = item.querySelector('.hist-minute')?.textContent || '';
    const minute = parseInt(String(minuteText || '').replace(/[^\d]/g, ''), 10);
    const text = item.querySelector('.hist-text')?.textContent || '';
    const [action = '', zone = '', result = ''] = text.split('·').map((part) => part.trim());
    const sys = String(item.dataset.system || '').trim();
    registerLiveEvent({
      id: item.dataset.eventId || null,
      action,
      zone,
      result,
      minute: Number.isFinite(minute) ? minute : null,
    });
    // Si el item viene renderizado como "guardado", aseguramos que el botón de delete no actúe.
    try {
      if (sys === 'touch-field-final') {
        item.querySelectorAll('.history-delete').forEach((btn) => btn.remove());
      }
    } catch (e) {}
  });

  const closestSafe = (node, selector) => {
    try {
      if (!node) return null;
      if (node.closest) return node.closest(selector);
      const parent = node.parentElement || node.parentNode;
      if (parent && parent.closest) return parent.closest(selector);
      return null;
    } catch (e) {
      return null;
    }
  };

  historyList.addEventListener('click', async (event) => {
    const replayBtn = closestSafe(event.target, '.history-replay');
    if (replayBtn) {
      event.preventDefault();
      const timeMs = Number(replayBtn.getAttribute('data-vtime')) || 0;
      const elapsedMs = Number(replayBtn.getAttribute('data-velapsed')) || 0;
      const kickoffMs = Number(replayBtn.getAttribute('data-vkickoff')) || 0;
      const videoId = Number(replayBtn.getAttribute('data-vid')) || 0;
      const clipId = Number(replayBtn.getAttribute('data-vclip')) || 0;
      try {
        document.dispatchEvent(new CustomEvent('webstats:match-video:seek', { detail: { time_ms: timeMs, elapsed_ms: elapsedMs, kickoff_video_ms: kickoffMs, video_id: videoId, clip_id: clipId } }));
      } catch (e) {}
      return;
    }
    const button = closestSafe(event.target, '.history-delete');
    if (!button) return;
    const article = button.closest('[data-event-id]');
    const eventId = article?.dataset?.eventId;
    if (!eventId) return;
	    if (isOfflineId(eventId)) {
	      article.remove();
	      removeLiveEvent(eventId);
	      removeOfflineQueuedById(eventId);
	      showPageStatus('Acción offline eliminada.', 'success', 2600);
	      try { bootstrapQuickHudFromExistingHistory(); } catch (e) { emitSummaryChange(); }
	      return;
	    }
		    try {
		      const response = await fetch(deleteUrl, {
		        method: 'POST',
		        credentials: 'same-origin',
	        headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
	        body: new URLSearchParams({ event_id: eventId, match_id: currentMatchId }),
	      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        showPageStatus(data.error || 'No se pudo eliminar la acción.', 'danger', 5200);
        return;
	      }
	      article.remove();
	      removeLiveEvent(eventId);
	      showPageStatus('Acción eliminada del registro en vivo.', 'success', 2600);
	      try { bootstrapQuickHudFromExistingHistory(); } catch (e) { emitSummaryChange(); }
	    } catch (err) {
	      console.error(err);
	      showPageStatus('No se pudo eliminar la acción.', 'danger', 5200);
	    }
	  });

  const deleteHistoryArticle = async (article, successMessage = 'Última acción deshecha.') => {
    const eventId = article?.dataset?.eventId;
    if (!eventId) return false;
    const parsedForRedo = parseHistoryArticle(article);
	    if (isOfflineId(eventId)) {
	      article.remove();
	      removeLiveEvent(eventId);
	      removeOfflineQueuedById(eventId);
      if (parsedForRedo) {
        redoStack.push(parsedForRedo);
        if (redoStack.length > 12) redoStack.shift();
        updateRedoUi();
	      }
	      showPageStatus(successMessage, 'success', 2600);
	      try { bootstrapQuickHudFromExistingHistory(); } catch (e) { emitSummaryChange(); }
	      return true;
	    }
		    try {
		      const response = await fetch(deleteUrl, {
		        method: 'POST',
	        credentials: 'same-origin',
	        headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
	        body: new URLSearchParams({ event_id: eventId, match_id: currentMatchId }),
	      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        showPageStatus(data.error || 'No se pudo eliminar la acción.', 'danger', 5200);
        return false;
      }
      article.remove();
      removeLiveEvent(eventId);
	      if (parsedForRedo) {
	        redoStack.push(parsedForRedo);
	        if (redoStack.length > 12) redoStack.shift();
	        updateRedoUi();
	      }
	      try { bootstrapQuickHudFromExistingHistory(); } catch (e) { emitSummaryChange(); }
	      showPageStatus(successMessage, 'success', 2400);
	      return true;
	    } catch (err) {
	      console.error(err);
	      showPageStatus('No se pudo deshacer la acción.', 'danger', 5200);
      return false;
    }
  };

  if (undoLastActionBtn) {
    undoLastActionBtn.addEventListener('click', async () => {
      const items = Array.from(historyList?.querySelectorAll?.('[data-event-id]') || []);
      const latestArticle = items.find((el) => {
        const sys = String(el?.dataset?.system || '').trim();
        // Solo deshacer pendientes (server) u offline locales.
        return sys !== 'touch-field-final';
      });
      if (!latestArticle) {
        showPageStatus('No hay acciones pendientes para deshacer.', 'warning', 2600);
        return;
      }
      await deleteHistoryArticle(latestArticle);
    });
  }

  const matchResetBtn = document.getElementById('match-reset-btn');
  if (matchResetBtn) {
    matchResetBtn.addEventListener('click', async () => {
      const confirmed = confirm('¿Reiniciar solo las acciones pendientes del registro en vivo de este partido?');
      if (!confirmed) return;
      try {
        const response = await fetch(resetRegisterUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
          body: new URLSearchParams({ match_id: currentMatchId }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          showPageStatus(data.error || 'No se pudo reiniciar el registro.', 'danger', 5200);
          return;
        }
        clearRegisterHistoryUI();
        resetRegisterHudState();
        resetClockExternal ? resetClockExternal() : resetClock();
        emitSummaryChange();
        showPageStatus('Registro en vivo reiniciado. Las acciones finalizadas se mantienen.', 'warning', 4200);
      } catch (err) {
        console.error(err);
        showPageStatus('Error al reiniciar el registro.', 'danger', 5200);
      }
    });
  }

  const bindFinalizeHandler = (button) => {
    if (!button) return;
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      const setFinalizeInFlight = (inFlight) => {
        matchFinalizeButtons.forEach((btn) => {
          if (!btn) return;
          if (inFlight) {
            btn.dataset.prevDisabled = btn.disabled ? '1' : '0';
            btn.disabled = true;
            btn.setAttribute('aria-busy', 'true');
          } else {
            const prev = btn.dataset.prevDisabled;
            if (prev === '1') btn.disabled = true;
            else btn.disabled = false;
            delete btn.dataset.prevDisabled;
            btn.removeAttribute('aria-busy');
          }
        });
      };
      setFinalizeInFlight(true);
      try {
        try {
          showPageStatus('Guardando partido…', 'info', 1800);
        } catch (err) {
          // ignore
        }
        try {
          Object.assign(matchInfoState, collectMatchInfoPayload());
        } catch (err) {
          console.error(err);
          showPageStatus('No se pudo leer el formulario del partido. Recarga la página y prueba de nuevo.', 'danger', 6200);
          return;
        }
        // No permitimos cerrar si hay acciones offline sin sincronizar: se perderían del resumen/KPI.
        const countOfflineActions = () =>
          readOfflineQueue().filter((item) => item && item.kind === 'action').length;
        const pendingOffline = countOfflineActions();
        if (pendingOffline > 0) {
          if (!(await ensureOnline())) {
            showPageStatus(
              `Tienes ${pendingOffline} acciones offline pendientes. Conéctate y pulsa “Sincronizar” antes de guardar el partido.`,
              'warning',
              7000
            );
            return;
          }
          await flushOfflineQueue({ limit: 500 });
          const stillPending = countOfflineActions();
          if (stillPending > 0) {
            showPageStatus(
              `Aún quedan ${stillPending} acciones offline pendientes. Pulsa “Sincronizar” y vuelve a guardar.`,
              'warning',
              7000
            );
            return;
          }
        }

        const response = await fetch(finalizeUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, Accept: 'application/json' },
          body: JSON.stringify({ match_id: currentMatchId, match_info: matchInfoState }),
        });
        const rawText = await response.text().catch(() => '');
        const data = safeParseJson(rawText, {});
        if (!response.ok) {
          showPageStatus(data.error || 'No se pudo guardar el partido.', 'danger', 5200);
          return;
        }
        const updatedCount = (() => {
          const parsed = parseInt(String(data.updated ?? 0), 10);
          return Number.isFinite(parsed) ? parsed : 0;
        })();
        const dedupCount = (() => {
          const parsed = parseInt(String(data.deduplicated ?? 0), 10);
          return Number.isFinite(parsed) ? parsed : 0;
        })();
        try {
          const finalEl = document.getElementById('persistent-final');
          if (finalEl) {
            const current = parseInt(String(finalEl.textContent || '0'), 10);
            const next = (Number.isFinite(current) ? current : 0) + (updatedCount || 0);
            finalEl.textContent = String(next);
          }
        } catch (error) {
          // ignore
        }
        try {
          if (Object.prototype.hasOwnProperty.call(data, 'score_for')) {
            matchInfoState.score_for = String(data.score_for ?? '').trim();
          }
          if (Object.prototype.hasOwnProperty.call(data, 'score_against')) {
            matchInfoState.score_against = String(data.score_against ?? '').trim();
          }
        } catch (error) {
          // ignore
        }
        renderMatchInfoState(matchInfoState);
        if (matchInfoCard) matchInfoCard.classList.remove('is-editing');
        emitSummaryChange();
        // UX: al guardar, el staff espera que se "reinicie" el registro en vivo.
        // Consolidamos en servidor y limpiamos el HUD/panel de pendientes sin tocar los datos ya guardados.
        clearRegisterHistoryUI();
        resetRegisterHudState();
        resetClockExternal ? resetClockExternal() : resetClock();
        emitSummaryChange();
        try {
          document.querySelector('[data-stage-tab="close"]')?.click();
        } catch (err) { /* ignore */ }
        const message = updatedCount
          ? `Partido guardado. ${updatedCount} acciones consolidadas${dedupCount ? ` · ${dedupCount} duplicadas descartadas` : ''}.`
          : 'Partido guardado. No había acciones nuevas para consolidar.';
        showPageStatus(message, 'success', 5200);
        // Reinicio total: tras guardar un partido, volvemos a prepartido para arrancar limpio
        // (nuevo match / nueva convocatoria / nuevo 11). Evita quedarse "atrapado" en el match ya cerrado en iPad.
        try {
          window.setTimeout(() => {
            const base = String(window.location.pathname || '/registro-acciones/').trim() || '/registro-acciones/';
            window.location.href = `${base}?stage=pre`;
          }, 650);
        } catch (e) {}
      } catch (err) {
        console.error(err);
        showPageStatus('Error al guardar el partido.', 'danger', 5200);
      } finally {
        setFinalizeInFlight(false);
      }
    });
  };
  matchFinalizeButtons.forEach(bindFinalizeHandler);

  const showZoneLabel = (zoneMatch, x, y) => {
    if (!zoneMatch) {
      zoneLabel.style.display = 'none';
      return;
    }
    zoneLabel.textContent = zoneMatch.label;
    zoneLabel.style.left = `${x}px`;
    zoneLabel.style.top = `${Math.max(16, y - 10)}px`;
    zoneLabel.style.display = 'block';
  };
  let lastZoneLabel = '';
  let lastTapAt = 0;
  let lastTapPoint = null;
  let swipeStart = null;
  // iOS/Safari a veces no dispara `click` de forma fiable en divs con overlays.
  // Unificamos el gesto como "tap" y lo escuchamos por `pointerup` + fallback `touchend`/`click`.
  let lastPhysicalTapAt = 0;
  const handleSurfaceTap = (clientX, clientY, event) => {
    if (!interactiveSurface) return;
    if (fieldPopup.contains(event?.target) || popupForm.contains(event?.target)) return;
    const rect = interactiveSurface.getBoundingClientRect();
    const fieldX = clientX - rect.left;
    const fieldY = clientY - rect.top;
    if (fieldX < 0 || fieldX > rect.width || fieldY < 0 || fieldY > rect.height) return;
    highlight.style.left = `${fieldX}px`;
    highlight.style.top = `${fieldY}px`;
    highlight.classList.add('active');
    const xPct = (fieldX / rect.width) * 100;
    const yPct = (fieldY / rect.height) * 100;
    const zoneMatch = findClosestZone(xPct, yPct);
    if (zoneMatch) {
      lastZoneLabel = String(zoneMatch.label || '').trim();
      // Doble toque: repetir última acción en esta zona (Modo PRO).
      try {
        const now = Date.now();
        const withinMs = now - (lastTapAt || 0) <= 320;
        const withinPx = (() => {
          if (!lastTapPoint) return false;
          const dx = (fieldX - lastTapPoint.x);
          const dy = (fieldY - lastTapPoint.y);
          return (dx * dx + dy * dy) <= (18 * 18);
        })();
        lastTapAt = now;
        lastTapPoint = { x: fieldX, y: fieldY };
        if (withinMs && withinPx && isProModeEnabled()) {
          void repeatLastAtLastZone();
          return;
        }
      } catch (e) { /* ignore */ }
      zoneInput.value = zoneMatch.label;
      syncAutoFields({ zone: zoneMatch.label });
      try {
        if (typeof onFieldTap === 'function') {
          onFieldTap({ x_pct: xPct, y_pct: yPct, zone: zoneMatch.label });
        }
      } catch (e) {}
      showZoneLabel(zoneMatch, fieldX, fieldY);
      if (isProAutoSendEnabled()) {
        const currentAction = String(actionInput?.value || '').trim();
        if (!currentAction) {
          showPopup(fieldX, fieldY);
          showPageStatus('Selecciona una acción (botón “Acción”).', 'warning', 2400);
          return;
        }
        const isTeamOnlyAction = isTeamOnlyActionValue(currentAction);
        if (!isTeamOnlyAction && !playerInput.value) {
          showPopup(fieldX, fieldY);
          showPageStatus('Selecciona un jugador.', 'warning', 2400);
          return;
        }
        ensureResultSelected(currentAction);
        const payload = new FormData(popupForm);
        void submitPopupAction(payload, { isTeamOnlyAction, source: 'pro_autosend' });
        return;
      }
      showPopup(fieldX, fieldY);
    } else {
      zoneInput.value = '';
      syncAutoFields({ zone: '' });
      zoneLabel.style.display = 'none';
      hidePopup();
    }
  };

  interactiveSurface.addEventListener('pointerup', (event) => {
    if (!event || !event.isPrimary) return;
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    lastPhysicalTapAt = Date.now();
    handleSurfaceTap(event.clientX, event.clientY, event);
  });
  interactiveSurface.addEventListener('touchend', (event) => {
    // Fallback para iOS antiguos sin Pointer Events.
    const touch = event?.changedTouches?.[0];
    if (!touch) return;
    lastPhysicalTapAt = Date.now();
    handleSurfaceTap(touch.clientX, touch.clientY, event);
  }, { passive: true });
  interactiveSurface.addEventListener('click', (event) => {
    // Evita el "ghost click" tras touchend/pointerup.
    if (Date.now() - (lastPhysicalTapAt || 0) < 450) return;
    handleSurfaceTap(event.clientX, event.clientY, event);
  });

  // Gestos pro: swipe izq = deshacer, swipe der = rehacer.
  interactiveSurface.addEventListener('pointerdown', (event) => {
    if (!isProModeEnabled()) return;
    if (!event.isPrimary) return;
    if (fieldPopup.contains(event.target) || popupForm.contains(event.target)) return;
    swipeStart = { x: event.clientX, y: event.clientY, t: Date.now() };
  });
  interactiveSurface.addEventListener('pointerup', (event) => {
    if (!swipeStart) return;
    const start = swipeStart;
    swipeStart = null;
    if (!isProModeEnabled()) return;
    const dt = Date.now() - (start.t || 0);
    if (dt > 650) return;
    const dx = (event.clientX - start.x);
    const dy = (event.clientY - start.y);
    if (Math.abs(dx) < 70) return;
    if (Math.abs(dy) > 45) return;
    try {
      if (dx < 0) document.getElementById('undo-last-action-btn')?.click?.();
      else redoLastUndo();
    } catch (e) { /* ignore */ }
  });
  interactiveSurface.addEventListener('pointercancel', () => { swipeStart = null; });
  fieldPopup.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hidePopup();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideQuickHistoryModal();
    if ((event.key || '').toLowerCase() === 's' && !event.metaKey && !event.ctrlKey) {
      const tag = (event.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      event.preventDefault();
      if (liveStatsHud && liveStatsToggle) {
        const collapsed = liveStatsHud.classList.contains('is-collapsed');
        liveStatsHud.classList.toggle('is-collapsed', !collapsed);
        liveStatsToggle.textContent = collapsed ? 'Ocultar' : 'Mostrar';
      }
    }
  });

  let actionSubmitInFlight = false;
  const teamOnlyActions = ['saque de esquina a favor', 'saque de esquina en contra', 'corner a favor', 'corner en contra'];
  const isTeamOnlyActionValue = (actionValue) =>
    teamOnlyActions.includes(String(actionValue || '').trim().toLowerCase());
  // `resultSelect` ya está resuelto arriba (para atajos). Reutilizarlo evita errores de redeclaración.
  const resetPopupForm = ({ preserveFields = false } = {}) => {
    if (!popupForm) return;
    const preserved = {
      player: String(playerInput?.value || ''),
      action: String(actionInput?.value || ''),
      result: String(resultSelect?.value || ''),
    };
    popupForm.reset();
    const csrfInput = popupForm.querySelector('input[name="csrfmiddlewaretoken"]');
    if (csrfInput) csrfInput.value = csrfToken;
    if (preserveFields) {
      if (playerInput && preserved.player) playerInput.value = preserved.player;
      if (actionInput && preserved.action) actionInput.value = preserved.action;
      if (resultSelect && preserved.result) resultSelect.value = preserved.result;
    } else {
      if (playerInput && preserved.player) playerInput.value = preserved.player;
    }
    syncAutoFields();
  };

  const submitPopupAction = async (payload, { isTeamOnlyAction = false, source = 'popup' } = {}) => {
    if (!payload || actionSubmitInFlight) return null;
    try {
      actionSubmitInFlight = true;
      // UID por envío para poder deduplicar reintentos de red sin bloquear acciones reales consecutivas.
      if (!payload.get('client_event_uid')) payload.set('client_event_uid', makeClientEventUid());
      if (currentMatchId && !payload.get('match_id')) payload.set('match_id', currentMatchId);
      // iOS/Safari: en algunos casos el valor de inputs hidden puede no reflejarse a tiempo en el POST.
      // Forzamos minuto/parte desde el estado real del cronómetro antes de enviar.
      try {
        payload.set('minute', String(getCurrentMatchMinute()));
      } catch (e) {}
      try {
        payload.set('period', String(Number(currentHalf) === 2 ? 2 : 1));
      } catch (e) {}
      if (isTeamOnlyAction) payload.delete('player');

      const editingId = getEditingEventId();
      const isEdit = Boolean(editingId && updateUrl);
      if (!(await ensureOnline())) throw new Error('offline');
      const response = await fetch(isEdit ? updateUrl : submitUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
        body: payload,
      });
      const ctype = String(response?.headers?.get?.('content-type') || '');
      const isJson = ctype.includes('application/json');
      let data = {};
      if (isJson) {
        data = await response.json().catch(() => ({}));
      } else {
        const raw = await response.text().catch(() => '');
        data = { error: raw ? raw.slice(0, 180) : '' };
      }
      if (!response.ok) {
        const msg = String(data?.error || '').trim();
        showPageStatus(msg || `No se pudo guardar la acción (HTTP ${response.status}).`, 'danger', 5200);
        return null;
      }
      if (!isJson) {
        const msg = String(data?.error || '').trim();
        showPageStatus(
          msg || 'No se pudo guardar la acción (respuesta no JSON).',
          'danger',
          5200
        );
        return null;
      }
      if (isEdit) {
        const article = historyList?.querySelector(`[data-event-id="${CSS.escape(String(data.id))}"]`);
        if (article) {
          if (data?.player?.id) article.dataset.playerId = String(data.player.id);
          else delete article.dataset.playerId;
          const minuteEl = article.querySelector('.hist-minute');
          if (minuteEl) {
            const numericMinute = Number(data.minute);
            minuteEl.textContent = Number.isFinite(numericMinute) ? `${numericMinute}'` : "Ahora'";
          }
          const strong = article.querySelector('strong');
          if (strong) {
            const num = data.player?.number || '--';
            const nm = String(data.player?.name || 'EQUIPO').toUpperCase();
            strong.textContent = `#${num} ${nm}`;
          }
          const textEl = article.querySelector('.hist-text');
          if (textEl) textEl.textContent = `${data.action} · ${data.zone || '-'} · ${data.result || ''}`;
        }
        try {
          removeLiveEvent(String(data.id));
          registerLiveEvent({ id: String(data.id), action: data.action, zone: data.zone, result: data.result, minute: data.minute });
        } catch (e) {}
        try {
          // Recalcula contadores desde el historial para no dejar estados inconsistentes tras editar.
          bootstrapQuickHudFromExistingHistory();
        } catch (e) {}
        setEditingEventId('');
        hidePopup();
        zoneLabel.style.display = 'none';
        emitSummaryChange();
        showPageStatus('Acción actualizada.', 'success', 1800);
        return data;
      }

      const inserted = appendHistoryEntry({
        minute: data.minute || 'Ahora',
        player: data.player,
        action: data.action,
        zone: data.zone,
        result: data.result,
        event_id: data.id,
        video_link: data.video_link || null,
      });
      if (!inserted) return data;

      const derivedDropKey = classifyCounterDropKey({ action: data.action, result: data.result });
      if (derivedDropKey) {
        incrementQuickCounter(derivedDropKey);
        appendQuickHistory(
          derivedDropKey,
          data.player?.name || (isTeamOnlyAction ? 'Equipo' : 'Jugador'),
          data.minute || getCurrentMatchMinute(),
          data.result || data.action
        );
      }

      // UX: en Modo PRO, evita limpiar acción/resultado para ir más rápido.
      const preserveFields = isProModeEnabled();
      hidePopup();
      zoneLabel.style.display = 'none';
      quickButtons.forEach((btn) => btn.classList.remove('quake-action-active'));
      resetPopupForm({ preserveFields });
      emitSummaryChange();
      try {
        const clipId = data?.video_clip_id || data?.video_link?.clip_id;
        if (clipId) {
          const label = `${data.minute || getCurrentMatchMinute()}' · ${data.action || ''}`.trim();
          setLastClipUi({ clipId, label });
          persistLastClip({ clipId, label });
        }
        const timeMs = data?.video_link?.time_ms;
        const videoId = data?.video_link?.video_id;
        const elapsedMs = data?.video_link?.elapsed_ms;
        const kickoffVideoMs = data?.video_link?.kickoff_video_ms;
        if (timeMs) persistLastVideoTime({ timeMs, videoId, elapsedMs, kickoffVideoMs });
      } catch (e) {}
      try {
        document.dispatchEvent(new CustomEvent('webstats:match-actions:recorded', { detail: { id: data.id, action: data.action, result: data.result, zone: data.zone, video_link: data.video_link || null } }));
      } catch (e) {}
      showPageStatus(
        `${source === 'pro_autosend' ? 'Auto-enviar:' : ''} Acción registrada${data.duplicate ? ' (duplicado detectado)' : ''}.`.trim(),
        data.duplicate ? 'warning' : 'success',
        2000
      );
      return data;
    } catch (err) {
      if (!(await ensureOnline()) || String(err?.message || '').toLowerCase().includes('offline')) {
        const offlineId = makeOfflineId();
        const fields = serializeFormData(payload);
        enqueueOfflineAction({ offlineId, fields });
        const offlineAction = payload.get('action_type') || String(actionInput?.value || '').trim() || 'Acción';
        const offlineResult = payload.get('result') || '';
        const offlineZone = payload.get('zone') || zoneInput.value || '';
        appendHistoryEntry({
          minute: payload.get('minute') || Math.floor(elapsedRef.value / 60),
          player: isTeamOnlyAction
            ? null
            : { id: playerInput.value, name: (playerInput.selectedOptions?.[0]?.textContent || 'Jugador'), number: '' },
          action: offlineAction,
          zone: offlineZone,
          result: offlineResult,
          event_id: offlineId,
          pending: true,
        });
        // Mantén el HUD inferior (acciones/posesión/ritmo) coherente incluso sin conexión.
        try {
          if (typeof registerLiveEvent === 'function') {
            const minuteRaw = payload.get('minute') || Math.floor(elapsedRef.value / 60);
            registerLiveEvent({ id: offlineId, action: offlineAction, zone: offlineZone, result: offlineResult, minute: minuteRaw });
          }
        } catch (e) {}
        // Mantén el panel superior coherente incluso sin conexión (popup normal, no quick-drop).
        try {
          const derivedDropKey = classifyCounterDropKey({ action: offlineAction, result: offlineResult });
          if (derivedDropKey) {
            incrementQuickCounter(derivedDropKey);
            appendQuickHistory(
              derivedDropKey,
              isTeamOnlyAction ? 'Equipo' : (playerInput.selectedOptions?.[0]?.textContent || 'Jugador'),
              payload.get('minute') || Math.floor(elapsedRef.value / 60),
              offlineResult || offlineAction
            );
          }
        } catch (e) {}
        hidePopup();
        emitSummaryChange();
        updateOfflineQueueUi();
        showPageStatus('Sin conexión: acción guardada en el dispositivo. Se sincronizará al volver la red.', 'warning', 5200);
        return { offline: true, id: offlineId };
      }
      console.error(err);
      showPageStatus('Error al guardar la acción en el servidor.', 'danger', 5200);
      return null;
    } finally {
      actionSubmitInFlight = false;
    }
  };

  popupForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (actionSubmitInFlight) return;
    const currentAction = String(actionInput?.value || '').trim();
    const isTeamOnlyAction = isTeamOnlyActionValue(currentAction);
    if (!isTeamOnlyAction && !playerInput.value) {
      showPageStatus('Selecciona primero un jugador convocado.', 'warning', 3600);
      return;
    }
    ensureResultSelected(currentAction);
    syncAutoFields();
    const payload = new FormData(popupForm);
    await submitPopupAction(payload, { isTeamOnlyAction, source: 'popup' });
  });
  // Señal para que el HTML fallback (ES5) sepa que el submit ya está interceptado.
  // Evita que, por caching/orden de scripts, se quede activado el fallback y genere dobles envíos.
  try {
    if (popupForm && popupForm.dataset) popupForm.dataset.liveBound = '1';
  } catch (e) {}

  function parseHistoryArticle(article) {
    if (!article) return null;
    const eventId = String(article.dataset.eventId || '').trim();
    const minuteText = article.querySelector('.hist-minute')?.textContent || '';
    const minute = parseInt(String(minuteText || '').replace(/[^\d]/g, ''), 10);
    const text = article.querySelector('.hist-text')?.textContent || '';
    const parts = text.split('·').map((p) => p.trim());
    const action = parts[0] || '';
    const zone = parts[1] || '';
    const result = parts[2] || '';
    const playerId = String(article.dataset.playerId || '').trim();
    return {
      eventId,
      playerId: playerId || '',
      action,
      zone: zone === '-' ? '' : zone,
      result,
      minute: Number.isFinite(minute) ? minute : Math.floor(elapsedRef.value / 60),
    };
  }

  const updateRedoUi = () => {
    const btn = document.getElementById('pro-redo');
    if (!btn) return;
    btn.disabled = redoStack.length <= 0;
    btn.textContent = redoStack.length > 0 ? `Rehacer (${redoStack.length})` : 'Rehacer';
  };
  updateRedoUi();

  const editLastAction = () => {
    const latestArticle = historyList?.querySelector('[data-event-id]');
    if (!latestArticle) {
      showPageStatus('No hay acciones para editar.', 'warning', 2200);
      return false;
    }
    const parsed = parseHistoryArticle(latestArticle);
    if (!parsed?.eventId) {
      showPageStatus('No se pudo abrir la edición.', 'warning', 2200);
      return false;
    }
    if (isOfflineId(parsed.eventId)) {
      showPageStatus('Esta acción está offline. Sincroniza antes de editar.', 'warning', 3600);
      return false;
    }
    if (!updateUrl) {
      showPageStatus('Edición no disponible en este entorno.', 'warning', 2600);
      return false;
    }
    // Carga campos en el popup y marca event_id para que el submit vaya a updateUrl.
    setEditingEventId(parsed.eventId);
    if (playerInput && parsed.playerId) playerInput.value = parsed.playerId;
    if (actionInput) actionInput.value = parsed.action || '';
    if (zoneInput) zoneInput.value = parsed.zone || '';
    if (resultSelect) resultSelect.value = parsed.result || '';
    try {
      const minuteHidden = popupForm.querySelector('input[name="minute"]');
      if (minuteHidden) minuteHidden.value = String(parsed.minute ?? Math.floor(elapsedRef.value / 60));
    } catch (e) {}
    syncAutoFields();
    // Abre popup centrado.
    const rect = interactiveSurface.getBoundingClientRect();
    showPopup(rect.width * 0.5, rect.height * 0.5, { preserveEditing: true });
    try {
      showPageStatus('Editando última acción. Pulsa Guardar para actualizar.', 'info', 2000);
    } catch (e) {}
    return true;
  };

  const redoLastUndo = async () => {
    if (!redoStack.length) {
      showPageStatus('No hay nada que rehacer.', 'warning', 2200);
      updateRedoUi();
      return false;
    }
    const item = redoStack.pop();
    updateRedoUi();
    if (!item) return false;
    // Rehacer crea una nueva acción (mismo contenido). No reutiliza event_id.
    setEditingEventId('');
    if (playerInput && item.playerId) playerInput.value = item.playerId;
    if (actionInput) actionInput.value = item.action || '';
    if (zoneInput) zoneInput.value = item.zone || '';
    if (resultSelect) resultSelect.value = item.result || '';
    try {
      const minuteHidden = popupForm.querySelector('input[name="minute"]');
      if (minuteHidden) minuteHidden.value = String(item.minute ?? Math.floor(elapsedRef.value / 60));
    } catch (e) {}
    syncAutoFields();
    const payload = new FormData(popupForm);
    const isTeamOnlyAction = isTeamOnlyActionValue(String(actionInput?.value || '').trim());
    const data = await submitPopupAction(payload, { isTeamOnlyAction, source: 'redo' });
    return Boolean(data);
  };

  const repeatLastAtLastZone = async () => {
    if (!lastZoneLabel) {
      showPageStatus('Primero toca una zona del campo.', 'warning', 2200);
      return false;
    }
    const currentAction = String(actionInput?.value || '').trim();
    if (!currentAction) {
      showPageStatus('Selecciona una acción.', 'warning', 2200);
      return false;
    }
    const isTeamOnlyAction = isTeamOnlyActionValue(currentAction);
    if (!isTeamOnlyAction && !playerInput.value) {
      showPageStatus('Selecciona un jugador.', 'warning', 2200);
      return false;
    }
    ensureResultSelected(currentAction);
    zoneInput.value = lastZoneLabel;
    syncAutoFields({ zone: lastZoneLabel });
    const payload = new FormData(popupForm);
    const data = await submitPopupAction(payload, { isTeamOnlyAction, source: 'repeat' });
    return Boolean(data);
  };

  // Mantén la sesión viva en iPad (evita saltos a login en mitad del partido).
  const pingKeepalive = async () => {
    if (!keepaliveUrl) return;
    try {
      await fetch(keepaliveUrl, { method: 'GET', credentials: 'same-origin', headers: { Accept: 'application/json' } });
    } catch (e) {
      // ignore: si falla, el usuario verá el 401/403 al guardar y podrá recargar.
    }
  };
  if (keepaliveUrl) {
    try { window.setInterval(() => void pingKeepalive(), 90_000); } catch (e) {}
    // Primer ping a los pocos segundos para detectar sesión caducada pronto.
    try { window.setTimeout(() => void pingKeepalive(), 6_000); } catch (e) {}
  }

  // Sync básico multi-dispositivo: trae eventos nuevos creados desde otro iPad/PC.
  const parseServerEventId = (value) => {
    const n = parseInt(String(value || '').replace(/[^\d]/g, ''), 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  };
  let maxServerEventId = 0;
  try {
    historyList?.querySelectorAll('[data-event-id]').forEach((item) => {
      const idValue = String(item.dataset.eventId || '');
      const n = parseServerEventId(idValue);
      if (n && n > maxServerEventId) maxServerEventId = n;
    });
  } catch (e) {}

  let pollInFlight = false;
  const pollRemoteEvents = async () => {
    if (!eventsUrl || pollInFlight) return;
    if (document.visibilityState !== 'visible') return;
    if (!(await ensureOnline())) return;
    pollInFlight = true;
    try {
      const url = new URL(eventsUrl, window.location.origin);
      if (currentMatchId) url.searchParams.set('match_id', String(currentMatchId));
      if (maxServerEventId) url.searchParams.set('since_id', String(maxServerEventId));
      url.searchParams.set('limit', '80');
      const response = await fetch(url.toString(), { method: 'GET', credentials: 'same-origin', headers: { Accept: 'application/json' } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data?.ok) return;
      const events = Array.isArray(data.events) ? data.events : [];
      if (!events.length) return;
      events.forEach((ev) => {
        const evId = parseServerEventId(ev?.id);
        if (evId && evId > maxServerEventId) maxServerEventId = evId;
        const inserted = appendHistoryEntry({
          minute: ev.minute || 'Ahora',
          player: ev.player,
          action: ev.action,
          zone: ev.zone,
          result: ev.result,
          event_id: String(ev.id || ''),
          video_link: ev.video_link || null,
        });
        if (!inserted) return;
        const derivedDropKey = classifyCounterDropKey({ action: ev.action, result: ev.result });
        if (derivedDropKey) {
          incrementQuickCounter(derivedDropKey);
          appendQuickHistory(derivedDropKey, ev.player?.name || 'Equipo', ev.minute || getCurrentMatchMinute(), ev.result || ev.action);
        }
        try {
          document.dispatchEvent(new CustomEvent('webstats:match-actions:recorded', { detail: { id: ev.id, action: ev.action, result: ev.result, zone: ev.zone } }));
        } catch (e) {}
      });
      emitSummaryChange();
    } catch (e) {
      // ignore
    } finally {
      pollInFlight = false;
    }
  };
  if (eventsUrl) {
    try { window.setInterval(() => void pollRemoteEvents(), 3_500); } catch (e) {}
    window.addEventListener('online', () => void pollRemoteEvents());
  }

  const postQuickDropAction = async ({ player = null, eventType, zoneLabel, result, dropKey, teamOnly = false, minuteOverride = null }) => {
    const isTeamOnly = Boolean(teamOnly);
    if (!eventType) {
      showPageStatus('Acción rápida inválida.', 'warning', 3200);
      return null;
    }
    if (!isTeamOnly && !player?.id) {
      showPageStatus('Selecciona un jugador convocado.', 'warning', 3600);
      return null;
    }
    const minute = Number.isFinite(minuteOverride) ? minuteOverride : Math.floor(elapsedRef.value / 60);
    const formData = new FormData();
    if (!isTeamOnly && player?.id) formData.set('player', player.id);
    formData.set('action_type', eventType);
    formData.set('result', result || '');
    formData.set('minute', minute);
    formData.set('zone', zoneLabel || '');
    formData.set('tercio', '');
    formData.set('observation', '');
    // UID por envío para deduplicar reintentos de red sin bloquear acciones reales consecutivas.
    formData.set('client_event_uid', makeClientEventUid());
    if (currentMatchId) formData.set('match_id', currentMatchId);
    try {
      if (!(await ensureOnline())) throw new Error('offline');
      const response = await fetch(submitUrl, {
	      method: 'POST',
	      credentials: 'same-origin',
	      headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
	      body: formData,
	    });
	    const data = await response.json().catch(() => ({}));
	    if (!response.ok) {
	      showPageStatus(data.error || 'No se pudo registrar la acción rápida.', 'danger', 5200);
	      return null;
	    }
      const inserted = appendHistoryEntry({
        minute: data.minute || 'Ahora',
        player: data.player,
        action: data.action,
        zone: data.zone,
        result: data.result,
        event_id: data.id,
        video_link: data.video_link || null,
      });
      if (!inserted) return data;
      incrementQuickCounter(dropKey);
      appendQuickHistory(dropKey, data.player?.name || 'Equipo', data.minute || minute, result || data.result || data.action);
      if (!isTeamOnly && player?.id) selectPlayer(player.id);
      emitSummaryChange();
      try {
        document.dispatchEvent(new CustomEvent('webstats:match-actions:recorded', { detail: { id: data.id, action: data.action, result: data.result, zone: data.zone, video_link: data.video_link || null } }));
      } catch (e) {}
      return data;
    } catch (err) {
      if (!(await ensureOnline()) || String(err?.message || '').toLowerCase().includes('offline')) {
        const offlineId = makeOfflineId();
        const fields = serializeFormData(formData);
        enqueueOfflineAction({ offlineId, fields });
        appendHistoryEntry({
          minute: minute,
          player: isTeamOnly ? null : { id: player?.id, name: player?.name || 'Jugador', number: player?.number || '' },
          action: eventType,
          zone: zoneLabel || '',
          result: result || '',
          event_id: offlineId,
          pending: true,
        });
        // Mantén el HUD inferior (acciones/posesión/ritmo) coherente incluso sin conexión.
        try {
          if (typeof registerLiveEvent === 'function') {
            registerLiveEvent({ id: offlineId, action: eventType, zone: zoneLabel || '', result: result || '', minute });
          }
        } catch (e) {}
        incrementQuickCounter(dropKey);
        appendQuickHistory(dropKey, player?.name || 'Equipo', minute, result || eventType);
        emitSummaryChange();
        showPageStatus('Sin conexión: acción guardada en el dispositivo. Se sincronizará al volver la red.', 'warning', 5200);
        updateOfflineQueueUi();
        return { offline: true, id: offlineId };
      }
      console.error(err);
      showPageStatus('Error al registrar la acción rápida.', 'danger', 5200);
      return null;
    }
  };

  const quickDropTargets = document.querySelectorAll('.quick-drop');
  quickDropTargets.forEach((dropTarget) => {
    let lastQuickDropTapAt = 0;
    const buildSelectedPlayerPayload = () => {
      const pid = String(playerInput?.value || '').trim();
      if (!pid) return null;
      let card = null;
      try {
        card = document.querySelector(`.convocation-card.selected[data-player-id="${CSS.escape(pid)}"]`);
      } catch (e) {
        card = null;
      }
      if (!card) {
        try {
          // Fallback: busca por id aunque la tarjeta no esté marcada como selected.
          card = Array.from(convocationCards || []).find((c) => String(c?.dataset?.playerId || '') === pid) || null;
        } catch (e) {
          card = null;
        }
      }
      return {
        id: pid,
        name: String(card?.dataset?.playerName || '').trim() || 'Jugador',
        number: String(card?.dataset?.playerNumber || '').trim() || '--',
        photo: String(card?.dataset?.playerPhoto || '').trim(),
        position: String(card?.dataset?.playerPosition || '').trim(),
      };
    };
    const handleQuickDropTap = async (event) => {
      const now = Date.now();
      // Evita doble disparo (touchend/pointerup + click).
      if (event?.type === 'click' && now - lastQuickDropTapAt < 360) return;
      lastQuickDropTapAt = now;
      try { event?.preventDefault?.(); } catch (e) {}
      try { event?.stopPropagation?.(); } catch (e) {}

      const config = {
        eventType: dropTarget.dataset.eventType,
        zoneLabel: dropTarget.dataset.zoneLabel,
        result: dropTarget.dataset.result,
        dropKey: dropTarget.dataset.dropKey,
        teamOnly: dropTarget.dataset.teamOnly || '',
      };
      const isTeamOnly = String(config.teamOnly || '').toLowerCase() === 'true';
      try {
        const data = await postQuickDropAction({
          player: isTeamOnly ? null : buildSelectedPlayerPayload(),
          eventType: config.eventType,
          zoneLabel: config.zoneLabel,
          result: config.result || '',
          dropKey: config.dropKey,
          teamOnly: isTeamOnly,
        });
        if (!data) {
          if (!isTeamOnly) {
            showPageStatus('Selecciona un jugador para usar este atajo.', 'warning', 2600);
          }
          return;
        }
        showPageStatus(`Acción rápida registrada${data.duplicate ? ' (duplicado detectado)' : ''}.`, data.duplicate ? 'warning' : 'success', 2200);
      } catch (err) {
        console.error(err);
        showPageStatus('Error al registrar la acción rápida.', 'danger', 5200);
      }
    };
    dropTarget.addEventListener('dragover', (event) => {
      event.preventDefault();
      dropTarget.classList.add('is-drag-over');
    });
    dropTarget.addEventListener('dragleave', () => {
      dropTarget.classList.remove('is-drag-over');
    });
    dropTarget.addEventListener('drop', async (event) => {
      event.preventDefault();
      dropTarget.classList.remove('is-drag-over');
      const payload = event.dataTransfer?.getData('text/plain');
      if (!payload) return;
      try {
        const player = JSON.parse(payload);
        const config = {
          eventType: dropTarget.dataset.eventType,
          zoneLabel: dropTarget.dataset.zoneLabel,
          result: dropTarget.dataset.result,
          dropKey: dropTarget.dataset.dropKey,
          teamOnly: dropTarget.dataset.teamOnly || '',
        };
        const isTeamOnly = String(config.teamOnly || '').toLowerCase() === 'true';
        const data = await postQuickDropAction({
          player,
          eventType: config.eventType,
          zoneLabel: config.zoneLabel,
          result: config.result,
          dropKey: config.dropKey,
          teamOnly: isTeamOnly,
        });
        if (!data) return;
        showPageStatus(`Acción rápida registrada${data.duplicate ? ' (duplicado detectado)' : ''}.`, data.duplicate ? 'warning' : 'success', 2600);
      } catch (err) {
        console.error(err);
        showPageStatus('Error al registrar la acción rápida.', 'danger', 5200);
      }
    });
    // iPad/WKWebView: `click` puede fallar o llegar tarde; `pointerup/touchend` es más fiable.
    dropTarget.addEventListener('pointerup', handleQuickDropTap);
    dropTarget.addEventListener('touchend', handleQuickDropTap, { passive: false });
    dropTarget.addEventListener('click', handleQuickDropTap);
  });

  return {
    clearRegisterHistoryUI,
    resetRegisterHudState,
    resetClock,
    getCurrentHalf: () => Number(currentHalf) || 1,
    getElapsedSeconds: () => Number(elapsedRef.value) || 0,
    editLastAction,
    redoLastUndo,
    repeatLastAtLastZone,
    registerQuickDropAction: postQuickDropAction,
    registerSubstitutionPair: async ({ outPlayer = null, inPlayer = null, minute = null } = {}) => {
      if (!outPlayer?.id || !inPlayer?.id) return false;
      const safeMinute = Number.isFinite(minute) ? minute : Math.floor(elapsedRef.value / 60);
      const exitData = await postQuickDropAction({
        player: outPlayer,
        eventType: 'Sustitución',
        zoneLabel: 'Sustitución Saliente',
        result: 'Salida',
        dropKey: 'bajada',
        teamOnly: false,
        minuteOverride: safeMinute,
      });
      if (!exitData) return false;
      const entryData = await postQuickDropAction({
        player: inPlayer,
        eventType: 'Sustitución',
        zoneLabel: 'Sustitución Entrante',
        result: 'Entrada',
        dropKey: 'subida',
        teamOnly: false,
        minuteOverride: safeMinute,
      });
      return Boolean(entryData);
    },
  };
};
