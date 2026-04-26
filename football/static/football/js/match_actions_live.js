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
    popupCloseButtons,
    convocationCards,
    playerInput,
    submitUrl,
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
    onSummaryChange,
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
  };
  const statusCounters = {
    amarilla: document.getElementById('status-yellow-count'),
    roja: document.getElementById('status-red-count'),
    subsUsed: document.getElementById('status-subs-used-count'),
    subsLeft: document.getElementById('status-subs-left-count'),
    cornerFor: document.getElementById('status-corner-for-count'),
    cornerAgainst: document.getElementById('status-corner-against-count'),
  };
  const MAX_SUBSTITUTIONS = 5;
  const quickStats = {
    amarilla: 0,
    roja: 0,
    subs: 0,
    corner_for: 0,
    corner_against: 0,
  };
  const undoLastActionBtn = document.getElementById('undo-last-action-btn');
  const offlineQueueBadge = document.getElementById('offline-queue-badge');
  const offlineQueueSyncBtn = document.getElementById('offline-queue-sync');
  const OFFLINE_ID_PREFIX = 'offline:';
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
  const recentActionsKey = 'webstats:live:recent_actions:v1';
  const safeParseJson = (raw, fallback) => {
    try {
      return JSON.parse(String(raw || ''));
    } catch (error) {
      return fallback;
    }
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
      if (article) {
        const text = article.querySelector('.hist-text')?.textContent || '';
        const parts = text.split('·').map((part) => part.trim());
        action = parts[0] || '';
        zone = parts[1] || '';
        result = parts[2] || '';
      }
      removeLiveEvent(oldId);
      registerLiveEvent({ id: newId, action, zone, result });
    } catch (error) {
      // ignore
    }
  };
  let flushOfflineInFlight = false;
  const flushOfflineQueue = async ({ limit = 20 } = {}) => {
    if (flushOfflineInFlight) return;
    if (!navigator.onLine) {
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
    emitSummaryChange();
  };

  const renderQuickHistoryPreview = (historyKey) => {
    const quickHistoryContainers = {
      amarilla: document.getElementById('yellow-history'),
      roja: document.getElementById('red-history'),
      subs: document.getElementById('sub-history'),
      corner_for: document.getElementById('corner-for-history'),
      corner_against: document.getElementById('corner-against-history'),
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
    if (actionText.includes('roja') || resultText.includes('roja')) return 'roja';
    if (actionText.includes('amarilla') || resultText.includes('amarilla')) return 'amarilla';
    if (actionText.includes('saque de esquina a favor') || actionText.includes('corner a favor') || resultText.includes('a favor')) return 'corner_for';
    if (actionText.includes('saque de esquina en contra') || actionText.includes('corner en contra') || resultText.includes('en contra')) return 'corner_against';
    if (actionText.includes('sustituci') || actionText.includes('cambio') || resultText.includes('entrada') || resultText.includes('salida')) {
      return resultText.includes('salida') ? 'bajada' : 'subida';
    }
    return '';
  };

  const bootstrapQuickHudFromExistingHistory = () => {
    if (!historyList) return;
    // El servidor renderiza el historial de acciones pendientes al cargar la página, pero los contadores
    // (amarillas/rojas/córners/cambios) se recalculan en cliente. Si no lo hacemos, la UI muestra 0 aunque
    // el historial tenga acciones.
    const resetKeys = ['amarilla', 'roja', 'corner_for', 'corner_against'];
    resetKeys.forEach((key) => {
      quickStats[key] = 0;
      quickHistoryState[key] = [];
    });

    const shouldBootstrapSubs = !(Array.isArray(quickHistoryState?.subs) && quickHistoryState.subs.length);
    if (shouldBootstrapSubs) {
      quickHistoryState.subs = [];
    }

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
        quickStats.amarilla += 1;
        pushHistoryRow('amarilla', normalizedPlayer, minuteLabel, result || action);
      } else if (derived === 'roja') {
        quickStats.roja += 1;
        pushHistoryRow('roja', normalizedPlayer, minuteLabel, result || action);
      } else if (derived === 'corner_for') {
        quickStats.corner_for += 1;
        pushHistoryRow('corner_for', normalizedPlayer, minuteLabel, result || action);
      } else if (derived === 'corner_against') {
        quickStats.corner_against += 1;
        pushHistoryRow('corner_against', normalizedPlayer, minuteLabel, result || action);
      } else if (shouldBootstrapSubs && (derived === 'subida' || derived === 'bajada')) {
        pushHistoryRow('subs', normalizedPlayer, minuteLabel, result || action || 'Sustitución');
      }
    });

    // Actualiza contadores y previews.
    if (quickCounters.amarilla) quickCounters.amarilla.textContent = String(quickStats.amarilla || 0);
    if (quickCounters.roja) quickCounters.roja.textContent = String(quickStats.roja || 0);
    if (quickCounters.corner_for) quickCounters.corner_for.textContent = String(quickStats.corner_for || 0);
    if (quickCounters.corner_against) quickCounters.corner_against.textContent = String(quickStats.corner_against || 0);
    renderQuickHistoryPreview('amarilla');
    renderQuickHistoryPreview('roja');
    renderQuickHistoryPreview('corner_for');
    renderQuickHistoryPreview('corner_against');
    if (shouldBootstrapSubs) renderQuickHistoryPreview('subs');
    refreshStatusCounters();
  };

  Object.entries({
    amarilla: document.getElementById('yellow-history'),
    roja: document.getElementById('red-history'),
    subs: document.getElementById('sub-history'),
    corner_for: document.getElementById('corner-for-history'),
    corner_against: document.getElementById('corner-against-history'),
  }).forEach(([historyKey, container]) => {
    if (!container) return;
    container.style.cursor = 'pointer';
    container.addEventListener('click', () => {
      const title =
        historyKey === 'amarilla' ? 'Amonestaciones (amarillas)'
          : historyKey === 'roja' ? 'Expulsiones (rojas)'
          : historyKey === 'corner_for' ? 'Córners a favor'
          : historyKey === 'corner_against' ? 'Córners en contra'
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
    clockToggle.addEventListener('click', (event) => {
      event.stopPropagation();
      if (clockRunning) pauseClock(); else startClock();
    });
  }
  if (clockResetBtn) {
    clockResetBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      resetClock();
    });
  }
  if (changeHalfBtn) {
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
  const showPopup = (x, y) => {
    const rect = interactiveSurface.getBoundingClientRect();
    const width = fieldPopup.offsetWidth;
    const height = fieldPopup.offsetHeight;
    const left = clamp(x - width / 2, 8, rect.width - width - 8);
    let top = y - height - 12;
    if (top < 8) top = clamp(y + 12, 8, rect.height - height - 8);
    fieldPopup.style.left = `${left}px`;
    fieldPopup.style.top = `${top}px`;
    fieldPopup.classList.add('is-visible');
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
  quickButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      quickButtons.forEach((other) => other.classList.remove('quake-action-active'));
      btn.classList.add('quake-action-active');
      actionInput.value = btn.dataset.action;
      pushRecentAction(btn.dataset.action);
      try {
        actionInput.dispatchEvent(new Event('input', { bubbles: true }));
      } catch (e) {}
    });
  });

  const appendHistoryEntry = ({ minute, player, action, zone, result, event_id, pending = false }) => {
    if (!historyList) return false;
    if (event_id && historyList.querySelector(`[data-event-id="${event_id}"]`)) return false;
    const item = document.createElement('article');
    item.className = 'history-item';
    if (pending) item.classList.add('is-offline-pending');
    if (player?.id) {
      item.dataset.playerId = String(player.id);
    }
    const numericMinute = Number(minute);
    const minuteLabel = Number.isFinite(numericMinute) ? `${numericMinute}'` : "Ahora'";
    item.innerHTML = `
      <span class="hist-minute">${minuteLabel}</span>
      ${pending ? `<span class="pending-pill">PENDIENTE</span>` : ''}
      <strong>#${player.number || '--'} ${(player.name || 'JUGADOR').toUpperCase()}</strong>
      <p class="hist-text">${action} · ${zone || '-'} · ${result || ''}</p>
      <button type="button" class="history-delete" aria-label="Eliminar acción">🗑</button>
    `;
    if (event_id) item.dataset.eventId = event_id;
    historyList.prepend(item);
    if (historyList.children.length > 24) historyList.removeChild(historyList.lastChild);
    registerLiveEvent({ id: event_id, action, zone, result });
    return true;
  };

  historyList.querySelectorAll('.history-item').forEach((item) => {
    const text = item.querySelector('.hist-text')?.textContent || '';
    const [action = '', zone = '', result = ''] = text.split('·').map((part) => part.trim());
    registerLiveEvent({ id: item.dataset.eventId || null, action, zone, result });
  });

  historyList.addEventListener('click', async (event) => {
    const button = event.target.closest('.history-delete');
    if (!button) return;
    const article = button.closest('[data-event-id]');
    const eventId = article?.dataset?.eventId;
    if (!eventId) return;
    if (isOfflineId(eventId)) {
      article.remove();
      removeLiveEvent(eventId);
      removeOfflineQueuedById(eventId);
      showPageStatus('Acción offline eliminada.', 'success', 2600);
      emitSummaryChange();
      return;
    }
    try {
      const response = await fetch(deleteUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken },
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
      emitSummaryChange();
    } catch (err) {
      console.error(err);
      showPageStatus('No se pudo eliminar la acción.', 'danger', 5200);
    }
  });

  const deleteHistoryArticle = async (article, successMessage = 'Última acción deshecha.') => {
    const eventId = article?.dataset?.eventId;
    if (!eventId) return false;
    if (isOfflineId(eventId)) {
      article.remove();
      removeLiveEvent(eventId);
      removeOfflineQueuedById(eventId);
      showPageStatus(successMessage, 'success', 2600);
      emitSummaryChange();
      return true;
    }
    try {
      const response = await fetch(deleteUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken },
        body: new URLSearchParams({ event_id: eventId, match_id: currentMatchId }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        showPageStatus(data.error || 'No se pudo eliminar la acción.', 'danger', 5200);
        return false;
      }
      article.remove();
      removeLiveEvent(eventId);
      emitSummaryChange();
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
      const latestArticle = historyList?.querySelector('[data-event-id]');
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
      button.disabled = true;
      Object.assign(matchInfoState, collectMatchInfoPayload());
      try {
        // No permitimos cerrar si hay acciones offline sin sincronizar: se perderían del resumen/KPI.
        const countOfflineActions = () =>
          readOfflineQueue().filter((item) => item && item.kind === 'action').length;
        const pendingOffline = countOfflineActions();
        if (pendingOffline > 0) {
          if (!navigator.onLine) {
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
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          showPageStatus(data.error || 'No se pudo guardar el partido.', 'danger', 5200);
          return;
        }
        try {
          const finalEl = document.getElementById('persistent-final');
          if (finalEl) {
            const current = parseInt(String(finalEl.textContent || '0'), 10);
            const next = (Number.isFinite(current) ? current : 0) + (parseInt(String(data.updated || 0), 10) || 0);
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
        showPageStatus(
          `Partido guardado. ${data.updated || 0} acciones consolidadas${data.deduplicated ? ` · ${data.deduplicated} duplicadas descartadas` : ''}.`,
          'success',
          5200
        );
      } catch (err) {
        console.error(err);
        showPageStatus('Error al guardar el partido.', 'danger', 5200);
      } finally {
        button.disabled = false;
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
  interactiveSurface.addEventListener('click', (event) => {
    if (fieldPopup.contains(event.target) || popupForm.contains(event.target)) return;
    const rect = interactiveSurface.getBoundingClientRect();
    const fieldX = event.clientX - rect.left;
    const fieldY = event.clientY - rect.top;
    if (fieldX < 0 || fieldX > rect.width || fieldY < 0 || fieldY > rect.height) return;
    highlight.style.left = `${fieldX}px`;
    highlight.style.top = `${fieldY}px`;
    highlight.classList.add('active');
    const zoneMatch = findClosestZone((fieldX / rect.width) * 100, (fieldY / rect.height) * 100);
    if (zoneMatch) {
      zoneInput.value = zoneMatch.label;
      syncAutoFields({ zone: zoneMatch.label });
      showZoneLabel(zoneMatch, fieldX, fieldY);
      showPopup(fieldX, fieldY);
    } else {
      zoneInput.value = '';
      syncAutoFields({ zone: '' });
      zoneLabel.style.display = 'none';
      hidePopup();
    }
  });
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
  popupForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (actionSubmitInFlight) return;
    const teamOnlyActions = ['saque de esquina a favor', 'saque de esquina en contra', 'corner a favor', 'corner en contra'];
    const currentAction = String(actionInput?.value || '').trim().toLowerCase();
    const isTeamOnlyAction = teamOnlyActions.includes(currentAction);
    if (!isTeamOnlyAction && !playerInput.value) {
      showPageStatus('Selecciona primero un jugador convocado.', 'warning', 3600);
      return;
    }
    syncAutoFields();
    const payload = new FormData(popupForm);
    // UID por envío para poder deduplicar reintentos de red sin bloquear acciones reales consecutivas.
    if (!payload.get('client_event_uid')) payload.set('client_event_uid', makeClientEventUid());
    if (currentMatchId && !payload.get('match_id')) payload.set('match_id', currentMatchId);
    if (isTeamOnlyAction) payload.delete('player');
    try {
      actionSubmitInFlight = true;
      if (!navigator.onLine) throw new Error('offline');
      const response = await fetch(submitUrl, {
	      method: 'POST',
	      credentials: 'same-origin',
	      headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
	      body: payload,
	    });
	    const data = await response.json().catch(() => ({}));
	    if (!response.ok) {
	      showPageStatus(data.error || 'No se pudo guardar la acción.', 'danger', 5200);
	      return;
	    }
      const inserted = appendHistoryEntry({
        minute: data.minute || 'Ahora',
        player: data.player,
        action: data.action,
        zone: data.zone,
        result: data.result,
        event_id: data.id,
      });
      if (!inserted) return;
      const derivedDropKey = classifyCounterDropKey({ action: data.action, result: data.result });
      if (derivedDropKey) {
        incrementQuickCounter(derivedDropKey);
        appendQuickHistory(derivedDropKey, data.player?.name || 'Jugador', data.minute || getCurrentMatchMinute(), data.result || data.action);
      }
      hidePopup();
      zoneLabel.style.display = 'none';
      quickButtons.forEach((btn) => btn.classList.remove('quake-action-active'));
      const lastPlayerId = playerInput.value;
      popupForm.reset();
      const csrfInput = popupForm.querySelector('input[name="csrfmiddlewaretoken"]');
      if (csrfInput) csrfInput.value = csrfToken;
      if (lastPlayerId) playerInput.value = lastPlayerId;
      syncAutoFields();
      emitSummaryChange();
      showPageStatus(`Acción registrada${data.duplicate ? ' (duplicado detectado)' : ''}.`, data.duplicate ? 'warning' : 'success', 2600);
    } catch (err) {
      if (!navigator.onLine || String(err?.message || '').toLowerCase().includes('offline')) {
        const offlineId = makeOfflineId();
        const fields = serializeFormData(payload);
        enqueueOfflineAction({ offlineId, fields });
        appendHistoryEntry({
          minute: payload.get('minute') || Math.floor(elapsedRef.value / 60),
          player: isTeamOnlyAction ? null : { id: playerInput.value, name: (playerInput.selectedOptions?.[0]?.textContent || 'Jugador'), number: '' },
          action: payload.get('action_type') || currentAction || 'Acción',
          zone: payload.get('zone') || zoneInput.value || '',
          result: payload.get('result') || '',
          event_id: offlineId,
          pending: true,
        });
        hidePopup();
        showPageStatus('Sin conexión: acción guardada en el dispositivo. Se sincronizará al volver la red.', 'warning', 5200);
        emitSummaryChange();
        updateOfflineQueueUi();
        return;
      }
      console.error(err);
      showPageStatus('Error al guardar la acción en el servidor.', 'danger', 5200);
    } finally {
      actionSubmitInFlight = false;
    }
  });

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
      if (!navigator.onLine) throw new Error('offline');
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
      });
      if (!inserted) return data;
      incrementQuickCounter(dropKey);
      appendQuickHistory(dropKey, data.player?.name || 'Equipo', data.minute || minute, result || data.result || data.action);
      if (!isTeamOnly && player?.id) selectPlayer(player.id);
      emitSummaryChange();
      return data;
    } catch (err) {
      if (!navigator.onLine || String(err?.message || '').toLowerCase().includes('offline')) {
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
    dropTarget.addEventListener('click', async () => {
      if (String(dropTarget.dataset.teamOnly || '').toLowerCase() !== 'true') return;
      try {
        const data = await postQuickDropAction({
          player: null,
          eventType: dropTarget.dataset.eventType,
          zoneLabel: dropTarget.dataset.zoneLabel,
          result: dropTarget.dataset.result || '',
          dropKey: dropTarget.dataset.dropKey,
          teamOnly: true,
        });
        if (!data) return;
        showPageStatus(`Acción rápida registrada${data.duplicate ? ' (duplicado detectado)' : ''}.`, data.duplicate ? 'warning' : 'success', 2600);
      } catch (err) {
        console.error(err);
        showPageStatus('Error al registrar la acción rápida.', 'danger', 5200);
      }
    });
  });

  return {
    clearRegisterHistoryUI,
    resetRegisterHudState,
    resetClock,
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
