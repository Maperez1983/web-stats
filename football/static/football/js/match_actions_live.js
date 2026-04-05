window.initMatchActionsLive = function initMatchActionsLive(options) {
  const {
    quickHistoryState,
    quickHistoryModal,
    quickHistoryModalList,
    quickHistoryModalTitle,
    subsHistoryCard,
    showQuickHistoryModal,
    hideQuickHistoryModal,
    historyList,
    liveEventStore,
    refreshLiveStatsHud,
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
  const emitSummaryChange = () => {
    if (typeof onSummaryChange !== 'function') return;
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
    if (statusCounters.amarilla) statusCounters.amarilla.textContent = quickStats.amarilla;
    if (persistentYellowEl) persistentYellowEl.textContent = quickStats.amarilla;
    if (statusCounters.roja) statusCounters.roja.textContent = quickStats.roja;
    if (persistentRedEl) persistentRedEl.textContent = quickStats.roja;
    if (statusCounters.subsUsed) statusCounters.subsUsed.textContent = quickStats.subs;
    if (persistentSubsUsedEl) persistentSubsUsedEl.textContent = quickStats.subs;
    if (statusCounters.subsLeft) statusCounters.subsLeft.textContent = Math.max(0, MAX_SUBSTITUTIONS - quickStats.subs);
    if (statusCounters.cornerFor) statusCounters.cornerFor.textContent = quickStats.corner_for;
    if (statusCounters.cornerAgainst) statusCounters.cornerAgainst.textContent = quickStats.corner_against;
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
    entries.slice(-3).forEach((text) => {
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
    quickStats[counterKey] += 1;
    const counterEl = quickCounters[counterKey];
    if (counterEl) counterEl.textContent = quickStats[counterKey];
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
    if (actionText.includes('amarilla') || resultText.includes('amarilla')) return 'amarilla';
    if (actionText.includes('roja') || resultText.includes('roja')) return 'roja';
    if (actionText.includes('saque de esquina a favor') || actionText.includes('corner a favor') || resultText.includes('a favor')) return 'corner_for';
    if (actionText.includes('saque de esquina en contra') || actionText.includes('corner en contra') || resultText.includes('en contra')) return 'corner_against';
    if (actionText.includes('sustituci') || actionText.includes('cambio') || resultText.includes('entrada') || resultText.includes('salida')) {
      return resultText.includes('salida') ? 'bajada' : 'subida';
    }
    return '';
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
      if (quickCounters.subs) quickCounters.subs.textContent = quickHistoryState.subs.length;
      quickStats.subs = quickHistoryState.subs.length;
      renderQuickHistoryPreview('subs');
      refreshStatusCounters();
    }
  } catch (err) {
    console.warn('No se pudo cargar historial inicial de sustituciones', err);
  }
  refreshStatusCounters();

  let clockInterval = null;
  let clockRunning = false;
  let currentHalf = 1;
  const formatClock = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };
  const getCurrentMatchMinute = () => Math.floor(elapsedRef.value / 60);
  const updateClockDisplay = () => {
    if (matchClockDisplay) matchClockDisplay.textContent = formatClock(elapsedRef.value);
    syncAutoFields();
    refreshLiveStatsHud();
    emitSummaryChange();
  };
  const pauseClock = () => {
    clockRunning = false;
    if (clockToggle) clockToggle.textContent = '►';
    clearInterval(clockInterval);
    clockInterval = null;
  };
  const resetClock = ({ keepHalf = false } = {}) => {
    pauseClock();
    elapsedRef.value = keepHalf && currentHalf === 2 ? 45 * 60 : 0;
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
        elapsedRef.value = 45 * 60;
        changeHalfBtn.textContent = '2ª Parte';
      } else {
        currentHalf = 1;
        elapsedRef.value = 0;
        changeHalfBtn.textContent = '1ª Parte';
      }
      updateClockDisplay();
    });
  }
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
    });
  });

  const appendHistoryEntry = ({ minute, player, action, zone, result, event_id }) => {
    if (!historyList) return false;
    if (event_id && historyList.querySelector(`[data-event-id="${event_id}"]`)) return false;
    const item = document.createElement('article');
    item.className = 'history-item';
    const numericMinute = Number(minute);
    const minuteLabel = Number.isFinite(numericMinute) ? `${numericMinute}'` : "Ahora'";
    item.innerHTML = `
      <span class="hist-minute">${minuteLabel}</span>
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
      Object.assign(matchInfoState, collectMatchInfoPayload());
      try {
        const response = await fetch(finalizeUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, Accept: 'application/json' },
          body: JSON.stringify({ match_info: matchInfoState }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          showPageStatus(data.error || 'No se pudo guardar el partido.', 'danger', 5200);
          return;
        }
        renderMatchInfoState(matchInfoState);
        if (matchInfoCard) matchInfoCard.classList.remove('is-editing');
        emitSummaryChange();
        showPageStatus(`Partido guardado. ${data.updated || 0} acciones consolidadas${data.deduplicated ? ` · ${data.deduplicated} duplicadas descartadas` : ''}.`, 'success', 4200);
      } catch (err) {
        console.error(err);
        showPageStatus('Error al guardar el partido.', 'danger', 5200);
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
    if (currentMatchId && !payload.get('match_id')) payload.set('match_id', currentMatchId);
    if (isTeamOnlyAction) payload.delete('player');
    try {
      actionSubmitInFlight = true;
      const response = await fetch(submitUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
        body: payload,
      });
      const data = await response.json();
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
      console.error(err);
      showPageStatus('Error al guardar la acción en el servidor.', 'danger', 5200);
    } finally {
      actionSubmitInFlight = false;
    }
  });

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
        if (!isTeamOnly && !player?.id) return;
        const minute = Math.floor(elapsedRef.value / 60);
        const formData = new FormData();
        if (!isTeamOnly && player?.id) formData.set('player', player.id);
        formData.set('action_type', config.eventType);
        formData.set('result', config.result || '');
        formData.set('minute', minute);
        formData.set('zone', config.zoneLabel || '');
        formData.set('tercio', '');
        formData.set('observation', '');
        if (currentMatchId) formData.set('match_id', currentMatchId);
        const response = await fetch(submitUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
          body: formData,
        });
        const data = await response.json();
        if (!response.ok) {
          showPageStatus(data.error || 'No se pudo registrar la acción rápida.', 'danger', 5200);
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
        incrementQuickCounter(config.dropKey);
        appendQuickHistory(config.dropKey, data.player?.name || 'Equipo', data.minute || minute, config.result);
        if (!isTeamOnly && player?.id) selectPlayer(player.id);
        emitSummaryChange();
        showPageStatus(`Acción rápida registrada${data.duplicate ? ' (duplicado detectado)' : ''}.`, data.duplicate ? 'warning' : 'success', 2600);
      } catch (err) {
        console.error(err);
        showPageStatus('Error al registrar la acción rápida.', 'danger', 5200);
      }
    });
    dropTarget.addEventListener('click', async () => {
      if (String(dropTarget.dataset.teamOnly || '').toLowerCase() !== 'true') return;
      const minute = Math.floor(elapsedRef.value / 60);
      const formData = new FormData();
      formData.set('action_type', dropTarget.dataset.eventType);
      formData.set('result', dropTarget.dataset.result || '');
      formData.set('minute', minute);
      formData.set('zone', dropTarget.dataset.zoneLabel || '');
      formData.set('tercio', '');
      formData.set('observation', '');
      if (currentMatchId) formData.set('match_id', currentMatchId);
      try {
        const response = await fetch(submitUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
          body: formData,
        });
        const data = await response.json();
        if (!response.ok) {
          showPageStatus(data.error || 'No se pudo registrar la acción rápida.', 'danger', 5200);
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
        incrementQuickCounter(dropTarget.dataset.dropKey);
        appendQuickHistory(dropTarget.dataset.dropKey, data.player?.name || 'Equipo', data.minute || minute, dropTarget.dataset.result);
        emitSummaryChange();
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
  };
};
