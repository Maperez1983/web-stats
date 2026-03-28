window.initMatchActionsChrome = function initMatchActionsChrome(options) {
  const {
    pageStatus,
    matchInfoCard,
    matchInfoEditBtn,
    matchInfoSaveBtn,
    matchInfoResetBtn,
    rivalToggleBtn,
    rivalDropdown,
    rivalOptions,
    quickHistoryModal,
    quickHistoryModalList,
    quickHistoryModalTitle,
    quickHistoryModalCloseBtn,
    quickHistoryState,
  } = options || {};

  let pageStatusTimer = null;

  const showPageStatus = (message, tone = 'info', timeout = 3600) => {
    if (!pageStatus) {
      return;
    }
    pageStatus.textContent = message;
    pageStatus.dataset.tone = tone;
    pageStatus.classList.add('is-visible');
    if (pageStatusTimer) {
      clearTimeout(pageStatusTimer);
      pageStatusTimer = null;
    }
    if (timeout > 0) {
      pageStatusTimer = setTimeout(() => {
        pageStatus.classList.remove('is-visible');
      }, timeout);
    }
  };

  const setMatchInfoEditing = (editing) => {
    if (!matchInfoCard) {
      return;
    }
    matchInfoCard.classList.toggle('is-editing', Boolean(editing));
    if (!editing && rivalDropdown) {
      rivalDropdown.classList.remove('is-open');
    }
  };

  const collectMatchInfoPayload = () => {
    if (!matchInfoCard) {
      return {};
    }
    return {
      opponent: matchInfoCard.querySelector('[data-field="opponent"] [data-input]')?.value?.trim() || '',
      location: matchInfoCard.querySelector('[data-field="location"] [data-input]')?.value?.trim() || '',
      datetime: matchInfoCard.querySelector('[data-field="datetime"] [data-input]')?.value?.trim() || '',
      round: matchInfoCard.querySelector('[data-field="round"] [data-input]')?.value?.trim() || '',
    };
  };

  const renderMatchInfoState = (matchInfoState) => {
    if (!matchInfoCard || !matchInfoState) {
      return;
    }
    Object.entries(matchInfoState).forEach(([key, value]) => {
      const row = matchInfoCard.querySelector(`[data-field="${key}"]`);
      if (!row) {
        return;
      }
      const input = row.querySelector('[data-input]');
      const display = row.querySelector('[data-display]');
      if (input) {
        input.value = value || '';
      }
      if (display) {
        display.textContent = value || '-';
      }
    });
  };

  const showQuickHistoryModal = (historyKey, title) => {
    const entries = quickHistoryState?.[historyKey] || [];
    if (!entries.length) {
      showPageStatus(`No hay registros de ${title.toLowerCase()} todavía.`, 'warning');
      return;
    }
    if (!quickHistoryModal || !quickHistoryModalList || !quickHistoryModalTitle) {
      showPageStatus(`No se pudo abrir el visor de ${title.toLowerCase()}.`, 'warning');
      return;
    }
    quickHistoryModalTitle.textContent = `${title} · ${entries.length}`;
    quickHistoryModalList.innerHTML = '';
    entries.forEach((entryText) => {
      const li = document.createElement('li');
      li.textContent = entryText;
      quickHistoryModalList.appendChild(li);
    });
    quickHistoryModal.classList.add('is-open');
    quickHistoryModal.setAttribute('aria-hidden', 'false');
  };

  const hideQuickHistoryModal = () => {
    if (!quickHistoryModal) {
      return;
    }
    quickHistoryModal.classList.remove('is-open');
    quickHistoryModal.setAttribute('aria-hidden', 'true');
  };

  if (quickHistoryModalCloseBtn) {
    quickHistoryModalCloseBtn.addEventListener('click', hideQuickHistoryModal);
  }
  if (quickHistoryModal) {
    quickHistoryModal.addEventListener('click', (event) => {
      if (event.target === quickHistoryModal) {
        hideQuickHistoryModal();
      }
    });
  }
  if (matchInfoEditBtn) {
    matchInfoEditBtn.addEventListener('click', () => {
      setMatchInfoEditing(!matchInfoCard?.classList.contains('is-editing'));
    });
  }
  if (rivalToggleBtn && rivalDropdown) {
    rivalToggleBtn.addEventListener('click', () => {
      rivalDropdown.classList.toggle('is-open');
    });
  }
  (rivalOptions || []).forEach((option) => {
    option.addEventListener('click', () => {
      const opponentInput = matchInfoCard?.querySelector('[data-field="opponent"] [data-input]');
      const locationInput = matchInfoCard?.querySelector('[data-field="location"] [data-input]');
      if (opponentInput) {
        opponentInput.value = option.dataset.rivalName || '';
      }
      if (locationInput && option.dataset.rivalLocation) {
        locationInput.value = option.dataset.rivalLocation;
      }
      if (rivalDropdown) {
        rivalDropdown.classList.remove('is-open');
      }
    });
  });
  document.addEventListener('click', (event) => {
    if (!matchInfoCard) {
      return;
    }
    if (rivalDropdown && !matchInfoCard.contains(event.target)) {
      rivalDropdown.classList.remove('is-open');
    }
  });

  return {
    showPageStatus,
    setMatchInfoEditing,
    collectMatchInfoPayload,
    renderMatchInfoState,
    showQuickHistoryModal,
    hideQuickHistoryModal,
  };
};
