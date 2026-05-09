/* Extracted from templates/football/match_actions.html to shrink HTML payload. */
(function () {
  const boot = (window.matchActionsBoot || {});
      const getInitials = (value) => {
        const raw = String(value || '').trim();
        if (!raw) return '?';
        const words = raw.split(/\s+/).filter(Boolean);
        if (!words.length) return '?';
        if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
        return (words[0][0] + words[1][0]).toUpperCase();
      };
  const playerAvatarFallback = String((boot.playerAvatarFallback || ''));
	      const fieldZoneDefs = JSON.parse(
	        document.getElementById('field-zone-defs')?.textContent || '[]',
	      );
      const touchField = document.getElementById('touch-field');
      const fieldSurface = document.getElementById('field-surface');
      const interactiveSurface = fieldSurface || touchField;
      const fieldPopup = document.getElementById('field-popup');
      // Guardrail: si faltan elementos base, no podemos inicializar el registro táctil.
      // En ese caso, dejamos una pista visible en UI para poder diagnosticar desde iPad.
      const pageStatusEl = document.getElementById('match-page-status');
      const bootError = (msg) => {
        try {
          if (!pageStatusEl) return;
          pageStatusEl.textContent = String(msg || 'Error inicializando el registro.');
          pageStatusEl.style.display = 'block';
          pageStatusEl.style.background = 'rgba(239,68,68,0.22)';
          pageStatusEl.style.border = '1px solid rgba(239,68,68,0.28)';
          pageStatusEl.style.color = '#fecaca';
          pageStatusEl.style.padding = '0.55rem 0.75rem';
          pageStatusEl.style.borderRadius = '14px';
        } catch (e) {}
      };
      if (!interactiveSurface) {
        bootError('No se encontró el campo (#field-surface).');
        return;
      }
      if (!fieldPopup) {
        bootError('No se encontró el popup (#field-popup).');
        return;
      }
      const quickHistoryModal = document.getElementById('quick-history-modal');
      const quickHistoryModalList = document.getElementById('quick-history-list');
	      const quickHistoryModalTitle = document.getElementById('quick-history-title');
	      const quickHistoryModalCloseBtn = document.getElementById('quick-history-close');
	      const subsHistoryCard = document.getElementById('subs-history-card');
	      const proModeToggleBtn = document.getElementById('pro-mode-toggle');
	      const proSidebarToggleBtn = document.getElementById('pro-sidebar-toggle');
	      const proQuickPanel = document.getElementById('pro-quick-panel');
	      const proQuickMeta = document.getElementById('pro-quick-meta');
	      const proOnfieldChips = document.getElementById('pro-onfield-chips');
	      const proBenchChips = document.getElementById('pro-bench-chips');
	      const proOpenActionPickerBtn = document.getElementById('pro-open-action-picker');
	      const proAutoSendToggleBtn = document.getElementById('pro-autosend-toggle');
	      const proRepeatLastBtn = document.getElementById('pro-repeat-last');
	      const proPresetBtns = [
	        document.getElementById('pro-preset-1'),
	        document.getElementById('pro-preset-2'),
	        document.getElementById('pro-preset-3'),
	        document.getElementById('pro-preset-4'),
	        document.getElementById('pro-preset-5'),
	        document.getElementById('pro-preset-6'),
	      ].filter(Boolean);
	      const proActionFavoritesEl = document.getElementById('pro-action-favorites');
	      const proEditLastBtn = document.getElementById('pro-edit-last');
	      const proRedoBtn = document.getElementById('pro-redo');
	      const proClearPlayerBtn = document.getElementById('pro-clear-player');
	      const proUndoBtn = document.getElementById('pro-undo');
	      const popupForm = document.getElementById('field-popup-form');
	      if (!popupForm) {
	        bootError('No se encontró el formulario (#field-popup-form).');
	        return;
	      }
      const matchInfoCard = document.getElementById('match-info-card');
      const matchInfoEditBtn = document.getElementById('match-info-edit-btn');
      const matchInfoSaveBtn = document.getElementById('match-info-save-btn');
	      const matchInfoResetBtn = document.getElementById('match-info-reset-btn');

		      // --- Modo Partido PRO ---
		      const proModeStorageKey = 'webstats:match_actions:pro_mode:v1';
		      const proAutoSendStorageKey = 'webstats:match_actions:pro_autosend:v1';
		      const wantsProByDefault = () => {
		        try {
		          const isTouch = ('ontouchstart' in window) || (Number(navigator.maxTouchPoints || 0) > 0);
		          if (!isTouch) return false;
		          const params = new URLSearchParams(window.location.search || '');
		          const live = String(params.get('live') || '').trim().toLowerCase();
		          const stage = String(params.get('stage') || '').trim().toLowerCase();
		          if (live === '1' || live === 'true' || live === 'on' || stage === 'live') return true;
		          const platform = String(navigator.platform || '');
		          const isIpad = /iPad/i.test(platform) || (platform === 'MacIntel' && Number(navigator.maxTouchPoints || 0) > 1 && Math.max(window.innerWidth || 0, window.innerHeight || 0) >= 900);
		          return isIpad;
		        } catch (e) {
		          return false;
		        }
		      };
		      const loadProMode = () => {
		        try {
		          const url = new URL(window.location.href);
		          const qp = url.searchParams.get('pro');
		          if (qp === '1' || qp === 'true' || qp === 'on') return true;
		          if (qp === '0' || qp === 'false' || qp === 'off') return false;
		        } catch (e) {}
		        try {
		          const raw = localStorage.getItem(proModeStorageKey);
		          if (raw === null || raw === undefined || raw === '') return wantsProByDefault();
		          return String(raw) === '1';
		        } catch (e) {
		          return wantsProByDefault();
		        }
		      };
	      const setProMode = (enabled, { persist = true } = {}) => {
	        const on = Boolean(enabled);
	        document.body.classList.toggle('pro-mode', on);
	        if (proQuickPanel) proQuickPanel.hidden = !on;
	        if (proSidebarToggleBtn) proSidebarToggleBtn.hidden = !on;
	        if (!on) document.body.classList.remove('pro-sidebar-open');
	        if (proModeToggleBtn) {
	          proModeToggleBtn.textContent = on ? 'Modo PRO: ON' : 'Modo PRO';
	          proModeToggleBtn.style.borderColor = on ? 'rgba(244, 180, 0, 0.48)' : '';
	          proModeToggleBtn.style.background = on ? 'rgba(244, 180, 0, 0.12)' : '';
	          proModeToggleBtn.style.color = on ? 'rgba(255, 242, 199, 0.98)' : '';
	        }
	        if (persist) {
	          try { localStorage.setItem(proModeStorageKey, on ? '1' : '0'); } catch (e) {}
	        }
	      };
	      const getProAutoSend = () => {
	        try {
	          const raw = localStorage.getItem(proAutoSendStorageKey);
	          if (raw === null || raw === undefined || raw === '') return false;
	          return String(raw) === '1';
	        } catch (e) {
	          return false;
	        }
	      };
	      const setProAutoSendUi = (enabled) => {
	        if (!proAutoSendToggleBtn) return;
	        const on = Boolean(enabled);
	        proAutoSendToggleBtn.textContent = on ? 'Auto-enviar: ON' : 'Auto-enviar: OFF';
	        proAutoSendToggleBtn.classList.toggle('is-selected', on);
	        proAutoSendToggleBtn.style.borderColor = on ? 'rgba(34, 211, 238, 0.55)' : '';
	        proAutoSendToggleBtn.style.background = on ? 'rgba(34, 211, 238, 0.12)' : '';
	        proAutoSendToggleBtn.style.color = on ? 'rgba(224, 242, 254, 0.95)' : '';
	      };
	      const setProAutoSend = (enabled, { persist = true } = {}) => {
	        const on = Boolean(enabled);
	        if (persist) {
	          try { localStorage.setItem(proAutoSendStorageKey, on ? '1' : '0'); } catch (e) {}
	        }
	        setProAutoSendUi(on);
	      };
	      const toggleProSidebar = () => {
	        const on = document.body.classList.toggle('pro-sidebar-open');
	        if (proSidebarToggleBtn) {
	          proSidebarToggleBtn.textContent = on ? 'Ocultar' : 'Convocados';
	        }
	      };
	      // Aplica estado inicial cuanto antes (para no "reflow" visual).
	      setProMode(loadProMode(), { persist: false });
	      setProAutoSend(getProAutoSend(), { persist: false });
	      if (proModeToggleBtn) {
	        proModeToggleBtn.addEventListener('click', () => {
	          const next = !document.body.classList.contains('pro-mode');
	          setProMode(next);
	        });
	      }
	      if (proSidebarToggleBtn) {
	        proSidebarToggleBtn.addEventListener('click', toggleProSidebar);
	      }
	      if (proAutoSendToggleBtn) {
	        proAutoSendToggleBtn.addEventListener('click', () => {
	          setProAutoSend(!getProAutoSend());
	          try {
	            showPageStatus(getProAutoSend() ? 'Auto-enviar activado.' : 'Auto-enviar desactivado.', 'info', 1600);
	          } catch (e) {}
	        });
	      }
	      const matchFinalizeBtn = [
	        document.getElementById('match-finalize-btn'),
	        document.getElementById('match-finalize-btn-top'),
	      ].filter(Boolean);
      const rivalToggleBtn = matchInfoCard?.querySelector('.rival-toggle') || null;
      const rivalDropdown = matchInfoCard?.querySelector('[data-rival-dropdown]') || null;
      const rivalOptions = matchInfoCard?.querySelectorAll('.rival-option') || [];
      const actionInput = popupForm.querySelector('input[name="action_type"]');
      const zoneInput = popupForm.querySelector('input[name="zone"]');
      const minuteInput = popupForm.querySelector('input[name="minute"]');
      const minuteDisplay = popupForm.querySelector('[data-minute-display]');
      const tercioInput = popupForm.querySelector('input[name="tercio"]');
      const tercioDisplay = popupForm.querySelector('[data-tercio-display]');
      const observationInput = popupForm.querySelector('textarea[name="observation"]');
      const resultSelect = popupForm.querySelector('select[name="result"]');
      const proResultButtons = Array.from(document.querySelectorAll('.pro-result-btn[data-pro-result]') || []);
      const autoPlayerRow = document.getElementById('auto-player-row');
      const autoPlayerChips = document.getElementById('auto-player-chips');
      const autoPlayerToggleBtn = document.getElementById('auto-player-toggle');
      const popupEditToggle = document.getElementById('popup-edit-toggle');
      const setPopupEditMode = (enabled, { focusField = false } = {}) => {
        const isEdit = Boolean(enabled);
        if (popupEditToggle) {
          popupEditToggle.dataset.mode = isEdit ? 'edit' : 'ipad';
          popupEditToggle.textContent = isEdit ? 'Modo edición' : 'Modo iPad';
        }
        if (actionInput) {
          actionInput.readOnly = !isEdit;
          actionInput.inputMode = isEdit ? 'text' : 'none';
        }
        if (observationInput) {
          observationInput.readOnly = false;
        }
        if (isEdit && focusField && actionInput) {
          try {
            actionInput.focus();
          } catch (err) {
            // ignore
          }
        }
      };
      if (popupEditToggle) {
        popupEditToggle.addEventListener('click', () => {
          setPopupEditMode(popupEditToggle.dataset.mode !== 'edit', { focusField: true });
        });
      }
      setPopupEditMode(false);
      // Resultado: si ya venimos con acción preseleccionada, ajusta opciones (Disparo => A puerta/Fuera).
      try { syncResultOptionsForAction(actionInput?.value || ''); } catch (e) {}
      const setResultValue = (value, { silent = false } = {}) => {
        const v = String(value || '').trim();
        if (!resultSelect) return false;
        if (!v) return false;
        // Asegura que el select tenga esa opción (por si no está en el catálogo actual).
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
        // Actualiza chips.
        try {
          proResultButtons.forEach((btn) => {
            btn.classList.toggle('is-selected', String(btn.dataset.proResult || '') === v);
          });
        } catch (e) {}
        if (!silent) {
          try { resultSelect.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
        }
        return true;
      };
      if (proResultButtons.length) {
        proResultButtons.forEach((btn) => {
          btn.addEventListener('click', () => {
            setResultValue(btn.dataset.proResult || '');
          });
        });
      }
      const playerInput = document.getElementById('selected-player');
      const quickButtonsContainer = popupForm.querySelector('.popup-quick-actions');
      const quickButtons = popupForm.querySelectorAll('.quick-action');
      const popupCloseButtons = popupForm.querySelectorAll('.close-popup');
      const convocationCards = document.querySelectorAll('.convocation-card');
      const historyList = document.getElementById('history-list');
      const actionCatalog = (() => {
        try {
          const raw = document.getElementById('match-action-catalog')?.textContent || '[]';
          const parsed = JSON.parse(raw);
          return Array.isArray(parsed) ? parsed.filter(Boolean).map((item) => String(item).trim()).filter(Boolean) : [];
        } catch (e) {
          return [];
        }
      })();
      const actionPickerOverlay = document.getElementById('action-picker');
      const actionPickerOpenBtn = document.getElementById('action-picker-open');
      const actionPickerCloseBtn = document.getElementById('action-picker-close');
      const actionPickerSearch = document.getElementById('action-picker-search');
      const actionPickerCount = document.getElementById('action-picker-count');
      const actionPickerFavorites = document.getElementById('action-picker-favorites');
      const actionPickerList = document.getElementById('action-picker-list');
      const normalizeActionKey = (value) => {
        const raw = String(value || '').trim().toLowerCase();
        try {
          return raw.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        } catch (e) {
          return raw;
        }
      };
      const recentActionsKey = 'webstats:live:recent_actions:v1';
      const readRecentActions = () => {
        try {
          const raw = window.localStorage?.getItem(recentActionsKey) || '[]';
          const parsed = JSON.parse(raw);
          return Array.isArray(parsed) ? parsed.map((item) => String(item || '').trim()).filter(Boolean) : [];
        } catch (e) {
          return [];
        }
      };
      const writeRecentActions = (items) => {
        try {
          window.localStorage?.setItem(recentActionsKey, JSON.stringify(Array.isArray(items) ? items : []));
        } catch (e) {}
      };
      const pushRecentAction = (label) => {
        const clean = String(label || '').trim();
        if (!clean) return;
        const key = normalizeActionKey(clean);
        if (!key) return;
        const existing = readRecentActions();
        const next = [clean, ...existing.filter((item) => normalizeActionKey(item) !== key)].slice(0, 12);
        writeRecentActions(next);
      };
      const baseResultOptions = (() => {
        const out = [];
        try {
          (resultSelect?.querySelectorAll('option') || []).forEach((opt) => {
            const value = String(opt.value || '').trim();
            if (!value) return;
            out.push(value);
          });
        } catch (e) {}
        return out.length ? out : ['Ganado', 'Perdido'];
      })();
      const shotResultOptions = ['A puerta', 'Fuera'];
      const isShotAction = (actionLabel) => {
        const key = normalizeActionKey(actionLabel);
        if (!key) return false;
        return (
          key.includes('disparo')
          || key.includes('tiro')
          || key.includes('remate')
          || key.includes('chut')
          || key.includes('shot')
        );
      };
      const setResultOptions = (options, { keepValue = true } = {}) => {
        if (!resultSelect) return;
        const previous = String(resultSelect.value || '').trim();
        const nextValue = keepValue ? previous : '';
        resultSelect.innerHTML = '';
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Selecciona resultado';
        resultSelect.appendChild(placeholder);
        (options || []).forEach((value) => {
          const opt = document.createElement('option');
          opt.value = value;
          opt.textContent = value;
          resultSelect.appendChild(opt);
        });
        if (nextValue && Array.from(resultSelect.options).some((opt) => String(opt.value) === nextValue)) {
          resultSelect.value = nextValue;
        } else {
          resultSelect.value = '';
        }
      };
      const syncResultOptionsForAction = (actionLabel) => {
        if (!resultSelect) return;
        const useShot = isShotAction(actionLabel);
        const active = Array.from(resultSelect.options).map((opt) => String(opt.value || '').trim()).filter(Boolean);
        const target = useShot ? shotResultOptions : baseResultOptions;
        const normalizedActive = active.join('|');
        const normalizedTarget = target.join('|');
        if (normalizedActive !== normalizedTarget) {
          setResultOptions(target, { keepValue: true });
        }
      };
      const parseHistoryActionType = (raw) => {
        const text = String(raw || '').trim();
        if (!text) return '';
        const [action = ''] = text.split('·').map((part) => part.trim());
        return action;
      };
      const buildMatchActionCounts = () => {
        const counts = new Map();
        try {
          historyList?.querySelectorAll('.history-item .hist-text')?.forEach((el) => {
            const actionType = parseHistoryActionType(el.textContent || '');
            const key = normalizeActionKey(actionType);
            if (!key) return;
            counts.set(key, (counts.get(key) || 0) + 1);
          });
        } catch (e) {}
        return counts;
      };
      const renderActionPickerButtons = (container, items, { showCounts = false, counts = null } = {}) => {
        if (!container) return;
        container.innerHTML = '';
        if (!items.length) {
          const empty = document.createElement('div');
          empty.className = 'pre-lineup-empty';
          empty.textContent = 'Sin datos todavía.';
          container.appendChild(empty);
          return;
        }
        items.forEach((label) => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'action-picker-item';
          btn.dataset.action = label;
          btn.textContent = label;
          if (showCounts && counts) {
            const key = normalizeActionKey(label);
            const value = counts.get(key) || 0;
            const small = document.createElement('small');
            small.textContent = value ? `${value}x` : '—';
            btn.appendChild(small);
          }
          btn.addEventListener('click', () => {
            try { quickButtons.forEach((other) => other.classList.remove('quake-action-active')); } catch (e) {}
            if (actionInput) actionInput.value = label;
            pushRecentAction(label);
            syncResultOptionsForAction(label);
            closeActionPicker();
          });
          container.appendChild(btn);
        });
      };
      const computeFavorites = () => {
        const counts = buildMatchActionCounts();
        const scored = actionCatalog
          .map((label, idx) => ({
            label,
            idx,
            score: counts.get(normalizeActionKey(label)) || 0,
          }))
          .filter((row) => row.label);
        scored.sort((a, b) => (b.score - a.score) || (a.idx - b.idx));
        const favorites = scored.filter((row) => row.score > 0).slice(0, 12).map((row) => row.label);
        const seen = new Set(favorites.map((label) => normalizeActionKey(label)));
        const recents = readRecentActions();
        recents.forEach((label) => {
          if (favorites.length >= 12) return;
          const key = normalizeActionKey(label);
          if (!key || seen.has(key)) return;
          if (!actionCatalog.some((item) => normalizeActionKey(item) === key)) return;
          seen.add(key);
          favorites.push(label);
        });
        return { favorites, counts };
      };
      const loadFallbackFavorites = () => {
        const defaults = Array.from(quickButtons).map((btn) => String(btn.dataset.action || '').trim()).filter(Boolean);
        const seen = new Set();
        const out = [];
        defaults.forEach((label) => {
          const key = normalizeActionKey(label);
          if (!key || seen.has(key)) return;
          seen.add(key);
          out.push(label);
        });
        readRecentActions().forEach((label) => {
          if (out.length >= 12) return;
          const key = normalizeActionKey(label);
          if (!key || seen.has(key)) return;
          seen.add(key);
          out.push(label);
        });
        actionCatalog.forEach((label) => {
          if (out.length >= 12) return;
          const key = normalizeActionKey(label);
          if (!key || seen.has(key)) return;
          seen.add(key);
          out.push(label);
        });
        return out.slice(0, 12);
      };
      const normalizeQuickConfigItems = (items) => {
        const raw = Array.isArray(items) ? items : [];
        const out = [];
        raw.forEach((it) => {
          if (typeof it === 'string') {
            const action = String(it || '').trim();
            if (!action) return;
            out.push({ label: action, action, result: '', hotkey: '' });
            return;
          }
          if (!it || typeof it !== 'object') return;
          const action = String(it.action || it.event_type || '').trim();
          if (!action) return;
          out.push({
            label: String(it.label || action).trim() || action,
            action,
            result: String(it.result || '').trim(),
            hotkey: String(it.hotkey || '').trim().slice(0, 1),
          });
        });
        return out.slice(0, 30);
      };

      const renderProActionFavorites = () => {
        if (!proActionFavoritesEl) return;
        if (!document.body.classList.contains('pro-mode')) {
          proActionFavoritesEl.innerHTML = '';
          return;
        }
        const quick = normalizeQuickConfigItems(matchdayQuickActions);
        const list = (quick.length ? quick.map((row) => row.action) : []).slice(0, 6);
        const fallback = !list.length ? (computeFavorites().favorites.length ? computeFavorites().favorites : loadFallbackFavorites()) : [];
        const labels = (list.length ? list : fallback).slice(0, 6);
        proActionFavoritesEl.innerHTML = '';
        if (!labels.length) return;
        labels.forEach((label) => {
          const quickHit = quick.find((row) => String(row.action || '').trim() === String(label || '').trim()) || null;
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'pro-chip';
          btn.textContent = quickHit ? (quickHit.label || label) : label;
          btn.title = 'Seleccionar acción';
          btn.addEventListener('click', () => {
            const action = quickHit ? (quickHit.action || '') : label;
            const result = quickHit ? (quickHit.result || '') : '';
            if (actionInput) actionInput.value = action;
            try { syncResultOptionsForAction(action); } catch (e) {}
            try { pushRecentAction(action); } catch (e) {}
            try { if (result) setResultValue(result); } catch (e) {}
            try { actionInput?.dispatchEvent?.(new Event('input', { bubbles: true })); } catch (e) {}
          });
          proActionFavoritesEl.appendChild(btn);
        });
      };
      const filterCatalog = (query) => {
        const q = normalizeActionKey(query);
        if (!q) return actionCatalog.slice(0, 60);
        const results = [];
        for (const label of actionCatalog) {
          const key = normalizeActionKey(label);
          if (key.includes(q)) results.push(label);
          if (results.length >= 80) break;
        }
        return results;
      };
      const syncActionPickerCount = (shown, total) => {
        if (!actionPickerCount) return;
        if (!total) actionPickerCount.textContent = '0';
        else actionPickerCount.textContent = `${shown}/${total}`;
      };
      const openActionPicker = () => {
        if (!actionPickerOverlay) return;
        actionPickerOverlay.classList.add('is-open');
        actionPickerOverlay.setAttribute('aria-hidden', 'false');
        const { favorites, counts } = computeFavorites();
        renderActionPickerButtons(actionPickerFavorites, favorites.length ? favorites : loadFallbackFavorites(), { showCounts: true, counts });
        const list = filterCatalog(actionPickerSearch?.value || '');
        renderActionPickerButtons(actionPickerList, list, { showCounts: false });
        syncActionPickerCount(list.length, actionCatalog.length);
        try {
          actionPickerSearch?.focus();
          actionPickerSearch?.select?.();
        } catch (e) {}
      };
      const closeActionPicker = () => {
        if (!actionPickerOverlay) return;
        actionPickerOverlay.classList.remove('is-open');
        actionPickerOverlay.setAttribute('aria-hidden', 'true');
      };
	      if (actionPickerOpenBtn) {
	        actionPickerOpenBtn.addEventListener('click', () => openActionPicker());
	      }
	      if (proOpenActionPickerBtn) {
	        proOpenActionPickerBtn.addEventListener('click', () => openActionPicker());
	      }
	      if (actionInput) {
	        const persistActionPick = () => {
	          try {
	            writeProState({
	              action: String(actionInput.value || '').trim(),
	              player_id: String(selectedPlayerId || '').trim(),
	              result: String(resultSelect?.value || '').trim(),
	            });
	          } catch (e) {}
	        };
	        actionInput.addEventListener('click', (event) => {
	          if (!actionInput.readOnly) return;
	          event.preventDefault();
	          openActionPicker();
	        });
	        actionInput.addEventListener('input', () => { syncResultOptionsForAction(actionInput.value); persistActionPick(); });
	        actionInput.addEventListener('change', () => { syncResultOptionsForAction(actionInput.value); persistActionPick(); });
	      }
      if (resultSelect) {
        resultSelect.addEventListener('change', () => {
          try {
            writeProState({
              action: String(actionInput?.value || '').trim(),
              player_id: String(selectedPlayerId || '').trim(),
              result: String(resultSelect.value || '').trim(),
            });
          } catch (e) {}
        });
      }
      // Favoritos rápidos (Modo PRO).
      try { renderProActionFavorites(); } catch (e) {}
      document.addEventListener('webstats:match-actions:recorded', () => {
        try { renderProActionFavorites(); } catch (e) {}
      });
      document.addEventListener('webstats:match-actions:lineup-changed', () => {
        try { renderProActionFavorites(); } catch (e) {}
      });
      if (actionPickerCloseBtn) {
        actionPickerCloseBtn.addEventListener('click', () => closeActionPicker());
      }
      if (actionPickerOverlay) {
        actionPickerOverlay.addEventListener('click', (event) => {
          if (event.target === actionPickerOverlay) closeActionPicker();
        });
      }
      document.addEventListener('keydown', (event) => {
        const isOpen = actionPickerOverlay?.classList.contains('is-open');
        if (event.key === 'Escape' && isOpen) closeActionPicker();
        const activeTag = String(document.activeElement?.tagName || '').toLowerCase();
        const isTyping = ['input', 'textarea', 'select'].includes(activeTag);
        const wantsOpen = (
          (event.key === 'k' && (event.metaKey || event.ctrlKey))
          || event.key === '/'
        );
        if (!isOpen && wantsOpen && !isTyping) {
          event.preventDefault();
          openActionPicker();
        }
      });
      (() => {
        if (!actionPickerSearch) return;
        let t = null;
        const run = () => {
          const list = filterCatalog(actionPickerSearch.value || '');
          renderActionPickerButtons(actionPickerList, list, { showCounts: false });
          syncActionPickerCount(list.length, actionCatalog.length);
        };
        actionPickerSearch.addEventListener('input', () => {
          if (t) window.clearTimeout(t);
          t = window.setTimeout(run, 120);
        });
        actionPickerSearch.addEventListener('keydown', (event) => {
          if (event.key !== 'Enter') return;
          const first = actionPickerList?.querySelector('.action-picker-item');
          if (first) {
            event.preventDefault();
            first.click();
          }
        });
      })();
      const lineupInput = document.getElementById('initial-lineup-data');
      const startersLimit = (() => {
        const value = Number((boot.startersLimit || 11));
        return Number.isFinite(value) && value > 0 ? value : 11;
      })();
      const lineupSections = {
        starters: {
          wrapper: document.querySelector('#sidebar-initial-lineup')?.closest('.lineup-slot') || null,
          element: document.getElementById('sidebar-initial-lineup'),
          countEl: document.getElementById('lineup-starters-count'),
          limit: startersLimit,
          placeholder: `Arrastra hasta ${startersLimit} jugadores desde la convocatoria.`,
        },
        bench: {
          wrapper: document.querySelector('#sidebar-bench-lineup')?.closest('.lineup-slot') || null,
          element: document.getElementById('sidebar-bench-lineup'),
          countEl: document.getElementById('lineup-bench-count'),
          placeholder: 'Arrastra suplentes aquí.',
        },
      };
      const lineupStatusMsg = document.getElementById('lineup-status-msg');
      const preLineupCountEl = document.getElementById('pre-lineup-count');
      const preLineupChipsEl = document.getElementById('pre-lineup-chips');
      const lineupAutoPickBtn = document.getElementById('lineup-auto-pick-btn');
      const lineupFillBenchBtn = document.getElementById('lineup-fill-bench-btn');
      const lineupClearBtn = document.getElementById('lineup-clear-btn');
      const matchClockDisplay = document.getElementById('match-clock-display');
      const clockToggle = document.getElementById('field-clock-toggle');
      const clockResetBtn = document.getElementById('field-clock-reset');
      const changeHalfBtn = document.getElementById('change-half-btn');
      const elapsedRef = { value: 0 };
      const highlight = document.createElement('span');
      const zoneLabel = document.createElement('span');
      const csrfInput = popupForm.querySelector('input[name="csrfmiddlewaretoken"]');
      const csrfToken = csrfInput?.value || '';
      const submitUrl = popupForm.dataset.submitUrl;
      const updateUrl = popupForm.dataset.updateUrl;
      const initialMatchDbIdEl = document.getElementById('match-db-id');
      const pageStatus = document.getElementById('match-page-status');
      const currentMatchId = String(initialMatchDbIdEl?.textContent || '').trim();
	      const matchInfoState = {
	        opponent: matchInfoCard?.querySelector('[data-field="opponent"] [data-input]')?.value || '',
	        location: matchInfoCard?.querySelector('[data-field="location"] [data-input]')?.value || '',
	        datetime: matchInfoCard?.querySelector('[data-field="datetime"] [data-input]')?.value || '',
	        round: matchInfoCard?.querySelector('[data-field="round"] [data-input]')?.value || '',
	        context: matchInfoCard?.querySelector('[data-field="context"] [data-input]')?.value || 'league',
	        tournament_name: matchInfoCard?.querySelector('[data-field="tournament_name"] [data-input]')?.value || '',
	        tournament_stage: matchInfoCard?.querySelector('[data-field="tournament_stage"] [data-input]')?.value || '',
	        score_for: matchInfoCard?.querySelector('[data-field="score_for"] [data-input]')?.value || '',
	        score_against: matchInfoCard?.querySelector('[data-field="score_against"] [data-input]')?.value || '',
	      };
      
  const urls = (boot.urls || {});
  const deleteUrl = String(urls.deleteUrl || "");
  const matchInfoSaveUrl = String(urls.matchInfoSaveUrl || "");
  const finalizeUrl = String(urls.finalizeUrl || "");
  const resetRegisterUrl = String(urls.resetRegisterUrl || "");
  const eventsUrl = String(urls.eventsUrl || "");
  const keepaliveUrl = String(urls.keepaliveUrl || "");
  const matchdayQuickButtonsApiUrl = String(urls.matchdayQuickButtonsApiUrl || "");
  const matchVideoLinksApiUrl = String(urls.matchVideoLinksApiUrl || "");
  const matchVideoMarkerApiUrl = String(urls.matchVideoMarkerApiUrl || "");
  const analysisVideoStudioUrlTemplate = String(urls.analysisVideoStudioUrlTemplate || "");
  const analysisVideoClipUrlTemplate = String(urls.analysisVideoClipUrlTemplate || "");
  const lineupSaveUrl = String(urls.lineupSaveUrl || "");
  const lineupGetUrl = String(urls.lineupGetUrl || "");
  const workspacePrefGetUrl = String(urls.workspacePrefGetUrl || "");
  const workspacePrefSetUrl = String(urls.workspacePrefSetUrl || "");

const urlWithMatchId = (baseUrl) => {
        if (!currentMatchId) return baseUrl;
        const joiner = baseUrl.includes('?') ? '&' : '?';
        return `${baseUrl}${joiner}match_id=${encodeURIComponent(currentMatchId)}`;
      };











      const lastVideoClipBtn = document.getElementById('last-video-clip-btn');
      const videoPanelToggleBtn = document.getElementById('video-panel-toggle');
      const matchVideoModal = document.getElementById('match-video-modal');
      const matchVideoCloseBtn = document.getElementById('match-video-close');
      const matchVideoEl = document.getElementById('match-video');
      const matchVideoSrcEl = document.getElementById('match-video-src');
      const matchVideoAngleSelect = document.getElementById('match-video-angle');
      const matchVideoStatusEl = document.getElementById('match-video-status');
      const matchVideoReplayBtn = document.getElementById('match-video-replay');
      const matchVideoMarkBtn = document.getElementById('match-video-mark');
      const matchVideoClipBtn = document.getElementById('match-video-clip');
      const matchVideoOpenStudioBtn = document.getElementById('match-video-open-studio');
      const teamName = String(boot.teamName || '');
      const matchdayQuickActions = (() => {
        try {
          const raw = document.getElementById('matchday-quick-actions')?.textContent || '[]';
          const parsed = JSON.parse(raw);
          return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
          return [];
        }
      })();
      const quickConfigModal = document.getElementById('quick-config-modal');
      const quickConfigRows = document.getElementById('quick-config-rows');
      const quickConfigOpen = document.getElementById('popup-quick-config-open');
      const quickConfigClose = document.getElementById('quick-config-close');
      const quickConfigAdd = document.getElementById('quick-config-add');
      const quickConfigSave = document.getElementById('quick-config-save');
      const quickConfigRole = String(boot.matchdayRoleKey || '');
      const createQuickConfigRow = (value = {}) => {
        const row = document.createElement('div');
        row.className = 'quick-config-row';
        const mkInput = (label, key, { placeholder = '', className = '' } = {}) => {
          const wrap = document.createElement('label');
          wrap.textContent = label;
          const input = document.createElement('input');
          input.type = 'text';
          input.placeholder = placeholder;
          input.value = String(value?.[key] || '').trim();
          if (className) input.className = className;
          wrap.appendChild(input);
          row.appendChild(wrap);
          return input;
        };
        const labelInput = mkInput('Label', 'label', { placeholder: 'Ej: Disparo' });
        const actionInputEl = mkInput('Acción', 'action', { placeholder: 'Ej: Disparo' });
        const resultInput = mkInput('Resultado', 'result', { placeholder: 'Ej: A puerta' });
        const hotkeyInput = mkInput('Tecla', 'hotkey', { placeholder: '1-9', className: 'mini' });
        const removeWrap = document.createElement('label');
        removeWrap.textContent = 'Quitar';
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'button ghost';
        removeBtn.textContent = '✕';
        removeBtn.addEventListener('click', () => row.remove());
        removeWrap.appendChild(removeBtn);
        row.appendChild(removeWrap);
        row._fields = { labelInput, actionInputEl, resultInput, hotkeyInput };
        return row;
      };
      const openQuickConfig = () => {
        if (!quickConfigModal || !quickConfigRows) return;
        quickConfigRows.innerHTML = '';
        const seed = matchdayQuickActions.length ? matchdayQuickActions : [];
        seed.slice(0, 18).forEach((item) => quickConfigRows.appendChild(createQuickConfigRow(item)));
        if (!seed.length) quickConfigRows.appendChild(createQuickConfigRow({}));
        quickConfigModal.hidden = false;
        try { quickConfigRows.querySelector('input')?.focus(); } catch (e) {}
      };
      const closeQuickConfig = () => {
        if (!quickConfigModal) return;
        quickConfigModal.hidden = true;
      };
      const collectQuickConfigItems = () => {
        if (!quickConfigRows) return [];
        const out = [];
        Array.from(quickConfigRows.children || []).forEach((row) => {
          const fields = row?._fields || {};
          const label = String(fields.labelInput?.value || '').trim();
          const action = String(fields.actionInputEl?.value || '').trim();
          const result = String(fields.resultInput?.value || '').trim();
          let hotkey = String(fields.hotkeyInput?.value || '').trim();
          hotkey = hotkey ? hotkey.slice(0, 1) : '';
          if (hotkey && !'123456789'.includes(hotkey)) hotkey = '';
          if (!action) return;
          out.push({ label: label || action, action, result, hotkey });
        });
        return out.slice(0, 30);
      };
      const saveQuickConfig = async () => {
        const items = collectQuickConfigItems();
        if (!items.length) {
          showPageStatus('Añade al menos un atajo.', 'warning', 2600);
          return;
        }
        try {
          const resp = await fetch(matchdayQuickButtonsApiUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ role: quickConfigRole, items }),
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok || !data?.ok) {
            const msg = data?.error || 'No se pudo guardar.';
            showPageStatus(msg, 'error', 3600);
            return;
          }
          // Recarga suave: actualizar atajos en vivo (sin refrescar página).
          try {
            const getResp = await fetch(matchdayQuickButtonsApiUrl, { credentials: 'same-origin' });
            const getData = await getResp.json().catch(() => ({}));
            if (getResp.ok && getData?.ok && Array.isArray(getData.items)) {
              matchdayQuickActions.splice(0, matchdayQuickActions.length, ...getData.items);
              if (quickButtonsContainer) {
                quickButtonsContainer.innerHTML = '';
                normalizeQuickConfigItems(matchdayQuickActions).slice(0, 18).forEach((row) => {
                  const b = document.createElement('button');
                  b.type = 'button';
                  b.className = 'pill-button quick-action';
                  b.dataset.action = row.action;
                  if (row.result) b.dataset.result = row.result;
                  if (row.hotkey) b.dataset.hotkey = row.hotkey;
                  b.title = row.hotkey ? `Tecla ${row.hotkey}` : 'Atajo';
                  b.textContent = row.label || row.action;
                  quickButtonsContainer.appendChild(b);
                });
              }
              try { renderProActionFavorites(); } catch (e) {}
            }
          } catch (e) {}
          showPageStatus('Atajos guardados.', 'success', 2800);
          closeQuickConfig();
        } catch (e) {
          showPageStatus('Error de red guardando atajos.', 'error', 3600);
        }
      };
      if (quickConfigOpen && quickConfigModal) {
        quickConfigOpen.addEventListener('click', openQuickConfig);
        quickConfigClose?.addEventListener('click', closeQuickConfig);
        quickConfigModal.addEventListener('click', (event) => {
          if (event.target === quickConfigModal) closeQuickConfig();
        });
        quickConfigAdd?.addEventListener('click', () => quickConfigRows?.appendChild(createQuickConfigRow({})));
        quickConfigSave?.addEventListener('click', () => { saveQuickConfig(); });
        window.addEventListener('keydown', (event) => {
          if (event.key === 'Escape' && !quickConfigModal.hidden) closeQuickConfig();
        });
      }


	      const lineupStorageKey = initialMatchDbIdEl?.textContent
	        ? `touchFieldLineup:${String(initialMatchDbIdEl.textContent).trim()}`
	        : '';
	      let lineupState = {
	        starters: [],
	        bench: [],
	      };
	      let lastLineupSignature = '';
	      let lineupPersistTimer = null;
	      let lastSavedLineupSnapshot = '';
	      let lineupPersistDisabled = false;
	      const lineupSignature = (state) => {
	        try {
	          const starters = Array.isArray(state?.starters) ? state.starters : [];
	          const bench = Array.isArray(state?.bench) ? state.bench : [];
	          return JSON.stringify({
	            starters: starters.map((row) => String(row?.id || '').trim()).filter(Boolean),
	            bench: bench.map((row) => String(row?.id || '').trim()).filter(Boolean),
	          });
	        } catch (e) {
	          return '';
	        }
	      };

	      const persistentClockEl = document.getElementById('persistent-clock');
	      const persistentYellowEl = document.getElementById('persistent-yellow');
	      const persistentRedEl = document.getElementById('persistent-red');
	      const persistentSubsUsedEl = document.getElementById('persistent-subs-used');
	      const persistentActionsEl = document.getElementById('persistent-actions');
	      const persistentPossessionEl = document.getElementById('persistent-possession');
		      const playerQuickBlock = document.getElementById('player-quick-block');
		      const playerQuickNameEl = document.getElementById('player-quick-name');
		      const playerQuickClearBtn = document.getElementById('player-quick-clear');
		      const playerQuickButtons = document.querySelectorAll('[data-quick-card]');
		      const playerQuickSubsToggleBtn = document.getElementById('player-quick-subs-toggle');
		      const playerQuickSubsSummaryEl = document.getElementById('player-quick-subs-summary');
		      const playerQuickReasonSelect = document.getElementById('player-quick-card-reason');

      const liveStatsHud = document.getElementById('live-stats-hud');
      const liveStatsToggle = document.getElementById('live-stats-toggle');
      const liveStatEls = {
        actions: document.getElementById('live-stat-actions'),
        possession: document.getElementById('live-stat-possession'),
        pace: document.getElementById('live-stat-pace'),
        pace5: document.getElementById('live-stat-pace5'),
        passAcc: document.getElementById('live-stat-pass-acc'),
        shots: document.getElementById('live-stat-shots'),
        shotsTarget: document.getElementById('live-stat-shots-target'),
        passes: document.getElementById('live-stat-passes'),
        turnovers: document.getElementById('live-stat-turnovers'),
        cards: document.getElementById('live-stat-cards'),
        subs: document.getElementById('live-stat-subs'),
        attack: document.getElementById('live-stat-attack'),
        abp: document.getElementById('live-stat-abp'),
        lossesDef: document.getElementById('live-stat-losses-def'),
        stealsHigh: document.getElementById('live-stat-steals-high'),
        duels: document.getElementById('live-stat-duels'),
        tercios: document.getElementById('live-stat-tercios'),
        alerts: document.getElementById('live-stat-alerts'),
      };
      const liveEventStore = new Map();


      const canManageWorkspace = !!boot.canManageWorkspace;
      let workspaceLiveKpiSlots = null;
      let workspaceLiveKpiLoaded = false;
      const liveAlertsPrefKey = 'matchday_live_alerts:v1';
      let workspaceLiveAlertsLoaded = false;
      let liveAlertsState = null;
      const defaultLiveAlerts = () => ({
        v: 1,
        enabled: {
          losses_def: true,
          no_shots: true,
          cards: true,
          abp: true,
          duels: true,
          aerial: true,
        },
        losses_def_last5: 3,
        no_shots_minute: 20,
        cards_total: 3,
        abp_total: 5,
        duels_min: 10,
        duels_rate_max: 40,
        aerial_min: 8,
        aerial_rate_max: 40,
      });
      const loadWorkspaceLiveKpis = async () => {
        if (workspaceLiveKpiLoaded) return workspaceLiveKpiSlots;
        workspaceLiveKpiLoaded = true;
        try {
          const url = `${workspacePrefGetUrl}?key=${encodeURIComponent('matchday_live_kpis:v1')}`;
          const resp = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok || !data || data.ok !== true) return null;
          const value = data.value;
          if (Array.isArray(value) && value.length === 4) {
            workspaceLiveKpiSlots = value.map((x) => String(x || '').trim());
            return workspaceLiveKpiSlots;
          }
        } catch (e) {}
        return null;
      };
      const saveWorkspaceLiveKpis = async (slots) => {
        if (!canManageWorkspace) return false;
        try {
          const resp = await fetch(workspacePrefSetUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, Accept: 'application/json' },
            body: JSON.stringify({ key: 'matchday_live_kpis:v1', value: Array.isArray(slots) ? slots : [] }),
          });
          const data = await resp.json().catch(() => ({}));
          return Boolean(resp.ok && data && data.ok === true);
        } catch (e) {}
        return false;
      };
      const loadWorkspaceLiveAlerts = async () => {
        if (workspaceLiveAlertsLoaded) return liveAlertsState;
        workspaceLiveAlertsLoaded = true;
        try {
          const url = `${workspacePrefGetUrl}?key=${encodeURIComponent(liveAlertsPrefKey)}`;
          const resp = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok || !data || data.ok !== true) return null;
          const value = data.value;
          if (value && typeof value === 'object') {
            liveAlertsState = value;
            return liveAlertsState;
          }
        } catch (e) {}
        return null;
      };
      const saveWorkspaceLiveAlerts = async (value) => {
        if (!canManageWorkspace) return false;
        try {
          const resp = await fetch(workspacePrefSetUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, Accept: 'application/json' },
            body: JSON.stringify({ key: liveAlertsPrefKey, value: value && typeof value === 'object' ? value : defaultLiveAlerts() }),
          });
          const data = await resp.json().catch(() => ({}));
          return Boolean(resp.ok && data && data.ok === true);
        } catch (e) {}
        return false;
      };

      // --- Plan A/B/C (prepartido) ---
      const matchPlanEls = {
        a: document.getElementById('match-plan-a'),
        b: document.getElementById('match-plan-b'),
        c: document.getElementById('match-plan-c'),
        checklist: document.getElementById('match-plan-checklist'),
      };
      const matchPlanCopyBtn = document.getElementById('match-plan-copy');
      const matchPlanSaveBtn = document.getElementById('match-plan-save');
      const matchPlanStatusEl = document.getElementById('match-plan-status');
      const matchPlanPrefKey = currentMatchId ? `match_plan_abc:v1:${currentMatchId}` : '';
      const defaultMatchPlan = () => ({ v: 1, a: '', b: '', c: '', checklist: '' });
      const applyMatchPlan = (value) => {
        const st = value && typeof value === 'object' ? value : defaultMatchPlan();
        if (matchPlanEls.a) matchPlanEls.a.value = String(st.a || '');
        if (matchPlanEls.b) matchPlanEls.b.value = String(st.b || '');
        if (matchPlanEls.c) matchPlanEls.c.value = String(st.c || '');
        if (matchPlanEls.checklist) matchPlanEls.checklist.value = String(st.checklist || '');
      };
      const collectMatchPlan = () => ({
        v: 1,
        a: String(matchPlanEls.a?.value || '').trim(),
        b: String(matchPlanEls.b?.value || '').trim(),
        c: String(matchPlanEls.c?.value || '').trim(),
        checklist: String(matchPlanEls.checklist?.value || '').trim(),
      });
      const loadMatchPlan = async () => {
        if (!matchPlanPrefKey || !workspacePrefGetUrl) return null;
        try {
          const url = `${workspacePrefGetUrl}?key=${encodeURIComponent(matchPlanPrefKey)}`;
          const resp = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok || !data || data.ok !== true) return null;
          const value = data.value;
          if (value && typeof value === 'object') {
            applyMatchPlan(value);
            if (matchPlanStatusEl) matchPlanStatusEl.textContent = 'Plan cargado (club).';
            return value;
          }
        } catch (e) {}
        if (matchPlanStatusEl) matchPlanStatusEl.textContent = 'Sin plan guardado.';
        return null;
      };
      const saveMatchPlan = async () => {
        if (!matchPlanPrefKey || !workspacePrefSetUrl) return false;
        if (!canManageWorkspace) {
          showPageStatus('No tienes permisos para guardar por club.', 'warning', 3200);
          return false;
        }
        try {
          const value = collectMatchPlan();
          const resp = await fetch(workspacePrefSetUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, Accept: 'application/json' },
            body: JSON.stringify({ key: matchPlanPrefKey, value }),
          });
          const data = await resp.json().catch(() => ({}));
          if (resp.ok && data && data.ok === true) {
            if (matchPlanStatusEl) matchPlanStatusEl.textContent = 'Plan guardado (club).';
            showPageStatus('Plan guardado.', 'success', 2600);
            return true;
          }
        } catch (e) {}
        showPageStatus('No se pudo guardar el plan.', 'error', 3600);
        return false;
      };
      const buildBenchSheetText = () => {
        const plan = collectMatchPlan();
        const info = matchInfoState || {};
        const opponent = String(info.opponent || '').trim() || 'Rival';
        const location = String(info.location || '').trim();
        const datetime = String(info.datetime || '').trim();
        const round = String(info.round || '').trim();
        const starters = Array.isArray(lineupState?.starters) ? lineupState.starters : [];
        const bench = Array.isArray(lineupState?.bench) ? lineupState.bench : [];
        const fmtList = (rows) => rows.map((p) => `#${p.number || '--'} ${String(p.name || '').toUpperCase()}`.trim()).filter(Boolean).join(', ');
        const lines = [];
        lines.push(`Hoja banquillo · ${teamName} vs ${opponent}`);
        if (round) lines.push(`Jornada: ${round}`);
        if (datetime) lines.push(`Fecha: ${datetime}`);
        if (location) lines.push(`Campo: ${location}`);
        if (starters.length) lines.push(`11: ${fmtList(starters.slice(0, 11))}`);
        if (bench.length) lines.push(`Suplentes: ${fmtList(bench)}`);
        if (plan.a) lines.push(`\nPLAN A:\n${plan.a}`);
        if (plan.b) lines.push(`\nPLAN B:\n${plan.b}`);
        if (plan.c) lines.push(`\nPLAN C:\n${plan.c}`);
        if (plan.checklist) lines.push(`\nCHECKLIST:\n${plan.checklist}`);
        return lines.join('\n');
      };
      if (matchPlanSaveBtn) matchPlanSaveBtn.addEventListener('click', () => { saveMatchPlan(); });
      if (matchPlanCopyBtn) matchPlanCopyBtn.addEventListener('click', async () => {
        const text = buildBenchSheetText();
        const ok = await copyTextToClipboard(text);
        if (ok) showPageStatus('Hoja copiada.', 'success', 2600);
        else showPageStatus('No se pudo copiar (iOS). Mantén pulsado para copiar manualmente.', 'warning', 4800);
      });
      try { loadMatchPlan(); } catch (e) {}
      let liveHudSnapshot = null;
      let showPageStatus;
      let setMatchInfoEditing;
      let collectMatchInfoPayload;
	      let renderMatchInfoState;
	      let showQuickHistoryModal;
	      let hideQuickHistoryModal;
	      let updateCloseSummary;
	      let updatePlayerQuickPanel = () => {};
      const containsText = (value, terms) => {
        const txt = String(value || '').toLowerCase();
        if (!txt) return false;
        return terms.some((term) => txt.includes(term));
      };
      const summarizeLiveEvent = ({ action = '', zone = '', result = '' }) => {
        const shot =
          containsText(action, ['tiro', 'remate', 'disparo', 'parad', 'ataj', 'blocaj']) ||
          containsText(result, ['tiro', 'remate', 'disparo', 'parad', 'ataj', 'blocaj']);
        const shotOnTarget =
          shot && (
            containsText(result, ['a puerta', 'apuerta', 'ap', 'a/p'])
            || containsText(result, ['ok', 'ganad', 'ganó'])
            || containsText(action, ['gol'])
            || containsText(result, ['gol'])
          );
        const pass = containsText(action, ['pase']) || containsText(result, ['pase']);
        const card = containsText(action, ['amarilla', 'roja', 'tarjeta']) || containsText(result, ['amarilla', 'roja']);
        const sub = containsText(action, ['sustituci', 'cambio']) || containsText(result, ['entrada', 'salida']) || containsText(zone, ['sustituci']);
        const setPiece =
          containsText(action, ['abp', 'balon parado', 'balón parado', 'corner', 'córner', 'saque de esquina', 'falta', 'libre directo', 'libre indirecto', 'penalti', 'penalti', 'saque']) ||
          containsText(result, ['abp', 'corner', 'córner', 'falta', 'penalti', 'saque']);
        const cross = containsText(action, ['centro', 'cross']) || containsText(result, ['centro']);
        const aerial =
          containsText(action, ['aereo', 'aéreo', 'balon aereo', 'balón aéreo', 'duelo aereo', 'duelo aéreo', 'cabece', 'cabeza', 'segundo balon', '2º balon', '2o balon']) ||
          containsText(result, ['aereo', 'aéreo', 'cabece', 'cabeza', 'segundo balon', '2º balon', '2o balon']);
        const loss =
          containsText(action, ['perdida', 'pérdida', 'perd']) ||
          containsText(result, ['perdid', 'error', 'fall']);
        const steal =
          containsText(action, ['robo', 'recuper', 'intercep', 'entrada']) ||
          containsText(result, ['robo', 'recuper', 'intercep']);
        const offensiveDuel =
          containsText(action, ['regate', 'dribbl', 'conduccion', 'conducción', 'encare', '1v1', '1x1']) ||
          containsText(result, ['regate', 'dribbl']);
        const defensiveDuel =
          containsText(action, ['duelo', 'robo', 'intercep', 'entrada', 'presion', 'disputa']) ||
          containsText(result, ['robo', 'intercep', 'recuper']) ||
          containsText(zone, ['duelo']);
        const duel = offensiveDuel || defensiveDuel;
        const offensiveSuccess = containsText(result, ['ganad', 'ok', 'superad', 'complet', 'favorable']);
        const offensiveFail = containsText(result, ['perdid', 'fall', 'error', 'falta', 'intercept', 'robad']);
        const defensiveSuccess = containsText(result, ['ganad', 'ok', 'robo', 'recuper', 'intercep', 'entrada', 'favorable']);
        const defensiveFail = containsText(result, ['perdid', 'fall', 'error', 'falta', 'superad', 'regatead', 'driblad']);
        const crossOk = cross && offensiveSuccess && !offensiveFail;
        const aerialWon = aerial && (offensiveSuccess || defensiveSuccess) && !(offensiveFail || defensiveFail);
        const duelWon = duel && (
          (offensiveDuel && offensiveSuccess && !offensiveFail) ||
          (defensiveDuel && defensiveSuccess && !defensiveFail)
        );
        const passOk = pass && offensiveSuccess && !offensiveFail;
        const zoneText = String(zone || '').toLowerCase();
        const tercio =
          zoneText.includes('porter') || zoneText.includes('defensa') ? 'def'
          : zoneText.includes('medio') ? 'mid'
          : zoneText.includes('ataque') ? 'att'
          : '';
        const lossDef = loss && tercio === 'def';
        const stealHigh = steal && tercio === 'att';
        return { shot, shotOnTarget, pass, passOk, card, sub, setPiece, cross, crossOk, aerial, aerialWon, loss, lossDef, steal, stealHigh, duel, duelWon, tercio };
      };
      const refreshLiveStatsHud = () => {
        // KPIs primarios (configurables)
        const kpiPrimaryEls = {
          l1: document.getElementById('live-kpi-l1'),
          v1: document.getElementById('live-kpi-v1'),
          l2: document.getElementById('live-kpi-l2'),
          v2: document.getElementById('live-kpi-v2'),
          l3: document.getElementById('live-kpi-l3'),
          v3: document.getElementById('live-kpi-v3'),
          l4: document.getElementById('live-kpi-l4'),
          v4: document.getElementById('live-kpi-v4'),
        };
        const primaryKey = currentMatchId ? `webstats:live:kpi_primary:v1:${currentMatchId}` : 'webstats:live:kpi_primary:v1';
        const readPrimarySlots = () => {
          try {
            const raw = localStorage.getItem(primaryKey) || '';
            const parsed = raw ? JSON.parse(raw) : null;
            if (Array.isArray(parsed) && parsed.length === 4) return parsed.map((x) => String(x || '').trim());
          } catch (e) {}
          if (Array.isArray(workspaceLiveKpiSlots) && workspaceLiveKpiSlots.length === 4) {
            return workspaceLiveKpiSlots.map((x) => String(x || '').trim());
          }
          return ['shots_target', 'shots', 'duels_rate', 'losses_def'];
        };
        const writePrimarySlots = (slots) => {
          try { localStorage.setItem(primaryKey, JSON.stringify(slots)); } catch (e) {}
        };
        const kpiCatalog = {
          shots_target: { label: 'A puerta', value: (t) => String(t.shotsTarget) },
          shots: { label: 'Tiros', value: (t) => String(t.shots) },
          shots_ap: { label: 'Tiros A/P', value: (t) => `${t.shotsTarget}/${t.shots}` },
          shots_ratio: { label: 'A puerta %', value: (t, extra) => `${extra.shotAcc}%` },
          duels_rate: { label: 'Duelos %', value: (t, extra) => `${extra.duelRate}%` },
          duels: { label: 'Duelos', value: (t) => `${t.duelsWon}/${t.duels}` },
          aerial_rate: { label: 'Aéreos %', value: (t, extra) => `${extra.aerialRate}%` },
          aerial: { label: 'Aéreos', value: (t) => `${t.aerialWon}/${t.aerial}` },
          passes_acc: { label: 'Pase %', value: (t, extra) => `${extra.passAcc}%` },
          pace5: { label: "Últ. 5'", value: (t, extra) => `${extra.pace5.toFixed(1)}/min` },
          losses_def: { label: 'Pérd salida', value: (t) => String(t.lossesDef) },
          losses: { label: 'Pérdidas', value: (t) => String(t.losses) },
          steals_high: { label: 'Recup altas', value: (t) => String(t.stealsHigh) },
          steals: { label: 'Robos', value: (t) => String(t.steals) },
          abp: { label: 'ABP', value: (t) => String(t.abp) },
          crosses: { label: 'Centros', value: (t) => String(t.crosses) },
          crosses_ok: { label: 'Centros OK', value: (t) => `${t.crossesOk}/${t.crosses}` },
          attack: { label: 'Ataque', value: (t) => String(t.tercio_att) },
          possession: { label: 'Posesión', value: (t, extra) => `${extra.possessionApprox}%` },
          cards: { label: 'Tarjetas', value: (t) => String(t.cards) },
          subs: { label: 'Cambios', value: (t) => String(t.subs) },
        };
        const totals = {
          actions: liveEventStore.size,
          shots: 0,
          shotsTarget: 0,
          passes: 0,
          passesOk: 0,
          cards: 0,
          subs: 0,
          abp: 0,
          crosses: 0,
          crossesOk: 0,
          aerial: 0,
          aerialWon: 0,
          duels: 0,
          duelsWon: 0,
          losses: 0,
          lossesDef: 0,
          steals: 0,
          stealsHigh: 0,
          tercio_def: 0,
          tercio_mid: 0,
          tercio_att: 0,
        };
        const currentMinute = Math.max(0, Math.floor(elapsedRef.value / 60));
        const windowStart = Math.max(0, currentMinute - 5);
        const last5 = {
          actions: 0,
          shots: 0,
          shotsTarget: 0,
          lossesDef: 0,
        };
        let subEntries = 0;
        let subExits = 0;
        liveEventStore.forEach((eventData) => {
          const summary = summarizeLiveEvent(eventData);
          if (summary.shot) totals.shots += 1;
          if (summary.shotOnTarget) totals.shotsTarget += 1;
          if (summary.pass) totals.passes += 1;
          if (summary.passOk) totals.passesOk += 1;
          if (summary.card) totals.cards += 1;
          if (summary.loss) totals.losses += 1;
          if (summary.lossDef) totals.lossesDef += 1;
          if (summary.steal) totals.steals += 1;
          if (summary.stealHigh) totals.stealsHigh += 1;
          if (summary.setPiece) totals.abp += 1;
          if (summary.cross) totals.crosses += 1;
          if (summary.crossOk) totals.crossesOk += 1;
          if (summary.aerial) totals.aerial += 1;
          if (summary.aerialWon) totals.aerialWon += 1;
          if (summary.sub) {
            const resultText = String(eventData?.result || '').toLowerCase();
            if (resultText.includes('salida')) subExits += 1;
            else if (resultText.includes('entrada')) subEntries += 1;
            else subEntries += 1;
          }
          if (summary.duel) totals.duels += 1;
          if (summary.duelWon) totals.duelsWon += 1;
          if (summary.tercio === 'def') totals.tercio_def += 1;
          else if (summary.tercio === 'mid') totals.tercio_mid += 1;
          else if (summary.tercio === 'att') totals.tercio_att += 1;

          const minute = Number(eventData?.minute);
          if (Number.isFinite(minute) && minute >= windowStart && minute <= currentMinute) {
            last5.actions += 1;
            if (summary.shot) last5.shots += 1;
            if (summary.shotOnTarget) last5.shotsTarget += 1;
            if (summary.lossDef) last5.lossesDef += 1;
          }
        });
        totals.subs = Math.max(subEntries, subExits);
        const minutes = Math.max(1, elapsedRef.value / 60);
        const pace = totals.actions / minutes;
        const pace5 = last5.actions / 5;
        const passAcc = totals.passes ? Math.round((totals.passesOk / totals.passes) * 100) : 0;
        const possessionApprox = totals.actions
          ? Math.round(Math.max(35, Math.min(75, 35 + (totals.passes / totals.actions) * 40)))
          : 50;
        const duelRate = totals.duels ? Math.round((totals.duelsWon / totals.duels) * 100) : 0;
        const aerialRate = totals.aerial ? Math.round((totals.aerialWon / totals.aerial) * 100) : 0;
        const shotAcc = totals.shots ? Math.round((totals.shotsTarget / totals.shots) * 100) : 0;
        const alerts = (() => {
          const cfg = (liveAlertsState && typeof liveAlertsState === 'object') ? liveAlertsState : defaultLiveAlerts();
          const enabled = (cfg && typeof cfg.enabled === 'object') ? cfg.enabled : {};
          const thLossesDef = Math.max(1, Number(cfg.losses_def_last5) || 3);
          const thNoShotsMin = Math.max(1, Number(cfg.no_shots_minute) || 20);
          const thCards = Math.max(1, Number(cfg.cards_total) || 3);
          const thAbp = Math.max(1, Number(cfg.abp_total) || 5);
          const thDuelsMin = Math.max(1, Number(cfg.duels_min) || 10);
          const thDuelsRate = Math.max(0, Math.min(100, Number(cfg.duels_rate_max) || 40));
          const thAerialMin = Math.max(1, Number(cfg.aerial_min) || 8);
          const thAerialRate = Math.max(0, Math.min(100, Number(cfg.aerial_rate_max) || 40));
          const parts = [];
          if (enabled.losses_def !== false && last5.lossesDef >= thLossesDef) parts.push('PÉRDIDAS EN SALIDA');
          if (totals.shotsTarget >= 3 && totals.shots >= 5) parts.push('MUCHO TIRO A PUERTA');
          if (enabled.no_shots !== false && currentMinute >= thNoShotsMin && totals.shots === 0) parts.push('SIN TIROS');
          if (enabled.cards !== false && totals.cards >= thCards) parts.push('RIESGO TARJETAS');
          if (enabled.duels !== false && totals.duels >= thDuelsMin && duelRate <= thDuelsRate) parts.push('DUELOS PERDIDOS');
          if (enabled.aerial !== false && totals.aerial >= thAerialMin && aerialRate <= thAerialRate) parts.push('AÉREOS PERDIDOS');
          if (enabled.abp !== false && totals.abp >= thAbp) parts.push('MUCHO ABP');
          if (!parts.length) return '—';
          return parts.slice(0, 2).join(' · ');
        })();
        if (liveStatEls.actions) liveStatEls.actions.textContent = String(totals.actions);
        if (liveStatEls.shots) liveStatEls.shots.textContent = String(totals.shots);
        if (liveStatEls.shotsTarget) liveStatEls.shotsTarget.textContent = String(totals.shotsTarget);
        if (liveStatEls.passAcc) liveStatEls.passAcc.textContent = `${passAcc}%`;
        if (liveStatEls.passes) liveStatEls.passes.textContent = `${totals.passesOk}/${totals.passes}`;
        if (liveStatEls.turnovers) liveStatEls.turnovers.textContent = `${totals.losses}/${totals.steals}`;
        if (liveStatEls.cards) liveStatEls.cards.textContent = String(totals.cards);
        if (liveStatEls.subs) liveStatEls.subs.textContent = String(totals.subs);
        if (liveStatEls.attack) liveStatEls.attack.textContent = String(totals.tercio_att);
        if (liveStatEls.abp) liveStatEls.abp.textContent = String(totals.abp);
        if (liveStatEls.lossesDef) liveStatEls.lossesDef.textContent = String(totals.lossesDef);
        if (liveStatEls.stealsHigh) liveStatEls.stealsHigh.textContent = String(totals.stealsHigh);
        if (liveStatEls.duels) liveStatEls.duels.textContent = `${totals.duelsWon}/${totals.duels} · ${duelRate}%`;
        if (liveStatEls.possession) liveStatEls.possession.textContent = `${possessionApprox}%`;
        if (liveStatEls.pace) liveStatEls.pace.textContent = `${pace.toFixed(1)}/min`;
        if (liveStatEls.pace5) liveStatEls.pace5.textContent = `${pace5.toFixed(1)}/min`;
        if (liveStatEls.tercios) liveStatEls.tercios.textContent = `D ${totals.tercio_def} · M ${totals.tercio_mid} · A ${totals.tercio_att}`;
        if (liveStatEls.alerts) liveStatEls.alerts.textContent = alerts;
        if (persistentActionsEl) persistentActionsEl.textContent = String(totals.actions);
        if (persistentPossessionEl) persistentPossessionEl.textContent = `${possessionApprox}%`;
        liveHudSnapshot = {
          minute: currentMinute,
          alerts,
          totals: { ...totals },
          extra: { passAcc, duelRate, aerialRate, shotAcc, possessionApprox, pace, pace5 },
        };

        // Render KPIs primarios
        try {
          const slots = readPrimarySlots();
          const extra = { passAcc, duelRate, aerialRate, shotAcc, possessionApprox, pace5 };
          const rows = [
            { l: kpiPrimaryEls.l1, v: kpiPrimaryEls.v1, key: slots[0] },
            { l: kpiPrimaryEls.l2, v: kpiPrimaryEls.v2, key: slots[1] },
            { l: kpiPrimaryEls.l3, v: kpiPrimaryEls.v3, key: slots[2] },
            { l: kpiPrimaryEls.l4, v: kpiPrimaryEls.v4, key: slots[3] },
          ];
          rows.forEach((row) => {
            const def = kpiCatalog[row.key] || null;
            if (row.l) row.l.textContent = def?.label || 'KPI';
            if (row.v) row.v.textContent = def ? String(def.value(totals, extra)) : '—';
          });
          // Config UI
          const configBtn = document.getElementById('live-kpi-settings');
          const configWrap = document.getElementById('live-kpi-config');
          const selects = [
            document.getElementById('live-kpi-s1'),
            document.getElementById('live-kpi-s2'),
            document.getElementById('live-kpi-s3'),
            document.getElementById('live-kpi-s4'),
          ];
          const ensureOptions = () => {
            const options = Object.entries(kpiCatalog).map(([key, def]) => ({ key, label: def.label }));
            selects.forEach((sel, idx) => {
              if (!sel || sel.dataset.bound === '1') return;
              sel.innerHTML = options.map((o) => `<option value="${o.key}">${o.label}</option>`).join('');
              sel.value = slots[idx] || options[0]?.key || '';
              sel.addEventListener('change', () => {
                const next = selects.map((s) => String(s?.value || '').trim());
                writePrimarySlots(next);
                scheduleRefreshLiveStatsHud();
              });
              sel.dataset.bound = '1';
            });
          };
          ensureOptions();
          if (configBtn && configWrap && configBtn.dataset.bound !== '1') {
            configBtn.addEventListener('click', () => {
              const open = !configWrap.hidden;
              configWrap.hidden = open;
            });
            configBtn.dataset.bound = '1';
          }
          // Preferencia compartida (club/workspace): opcional, para que el staff tenga los mismos KPIs en vivo.
          const wsStatus = document.getElementById('live-kpi-workspace-status');
          const wsUseBtn = document.getElementById('live-kpi-use-workspace');
          const wsSaveBtn = document.getElementById('live-kpi-save-workspace');
          const setWsStatus = (msg = '') => {
            if (!wsStatus) return;
            const txt = String(msg || '').trim();
            wsStatus.hidden = !txt;
            wsStatus.textContent = txt;
          };
          if (wsSaveBtn) wsSaveBtn.hidden = !canManageWorkspace;
          if (wsSaveBtn && wsSaveBtn.dataset.bound !== '1') {
            wsSaveBtn.addEventListener('click', async () => {
              const next = selects.map((s) => String(s?.value || '').trim());
              const ok = await saveWorkspaceLiveKpis(next);
              if (ok) {
                workspaceLiveKpiSlots = next;
                setWsStatus('KPIs del club actualizados.');
                showPageStatus && showPageStatus('KPIs guardados para el club.', 'success', 2600);
              } else {
                showPageStatus && showPageStatus('No se pudieron guardar los KPIs del club.', 'danger', 4200);
              }
            });
            wsSaveBtn.dataset.bound = '1';
          }
          if (wsUseBtn && wsUseBtn.dataset.bound !== '1') {
            wsUseBtn.addEventListener('click', () => {
              if (!(Array.isArray(workspaceLiveKpiSlots) && workspaceLiveKpiSlots.length === 4)) return;
              writePrimarySlots(workspaceLiveKpiSlots);
              selects.forEach((sel, idx) => {
                if (sel) sel.value = workspaceLiveKpiSlots[idx] || sel.value;
              });
              setWsStatus('Aplicados KPIs del club.');
              scheduleRefreshLiveStatsHud();
            });
            wsUseBtn.dataset.bound = '1';
          }
          if (!workspaceLiveKpiLoaded) {
            loadWorkspaceLiveKpis().then((val) => {
              if (Array.isArray(val) && val.length === 4) {
                // Mostrar opción "Usar club" si existe configuración.
                if (wsUseBtn) wsUseBtn.hidden = false;
                setWsStatus('KPIs del club disponibles.');
                // Si el usuario no tiene configuración local guardada, adopta la del club.
                try {
                  const raw = localStorage.getItem(primaryKey) || '';
                  const parsed = raw ? JSON.parse(raw) : null;
                  if (!(Array.isArray(parsed) && parsed.length === 4)) {
                    writePrimarySlots(val);
                    selects.forEach((sel, idx) => {
                      if (sel) sel.value = val[idx] || sel.value;
                    });
                    scheduleRefreshLiveStatsHud();
                  }
                } catch (e) {}
              }
            });
          }

          // Alertas configurables (club/workspace).
          const alertsSaveBtn = document.getElementById('live-alerts-save-workspace');
          const alertEls = {
            lossesEnabled: document.getElementById('live-alert-losses-def-enabled'),
            lossesTh: document.getElementById('live-alert-losses-def-th'),
            noShotsEnabled: document.getElementById('live-alert-no-shots-enabled'),
            noShotsMin: document.getElementById('live-alert-no-shots-min'),
            cardsEnabled: document.getElementById('live-alert-cards-enabled'),
            cardsTh: document.getElementById('live-alert-cards-th'),
            abpEnabled: document.getElementById('live-alert-abp-enabled'),
            abpTh: document.getElementById('live-alert-abp-th'),
            duelsEnabled: document.getElementById('live-alert-duels-enabled'),
            duelsMin: document.getElementById('live-alert-duels-min'),
            duelsRate: document.getElementById('live-alert-duels-rate'),
            aerialEnabled: document.getElementById('live-alert-aerial-enabled'),
            aerialMin: document.getElementById('live-alert-aerial-min'),
            aerialRate: document.getElementById('live-alert-aerial-rate'),
          };
          const readAlertsFromUi = () => {
            const num = (v, fallback) => {
              const n = Number(String(v ?? '').trim());
              return Number.isFinite(n) ? n : fallback;
            };
            const cfg = {
              v: 1,
              enabled: {
                losses_def: Boolean(alertEls.lossesEnabled?.checked),
                no_shots: Boolean(alertEls.noShotsEnabled?.checked),
                cards: Boolean(alertEls.cardsEnabled?.checked),
                abp: Boolean(alertEls.abpEnabled?.checked),
                duels: Boolean(alertEls.duelsEnabled?.checked),
                aerial: Boolean(alertEls.aerialEnabled?.checked),
              },
              losses_def_last5: Math.max(1, Math.round(num(alertEls.lossesTh?.value, 3))),
              no_shots_minute: Math.max(1, Math.round(num(alertEls.noShotsMin?.value, 20))),
              cards_total: Math.max(1, Math.round(num(alertEls.cardsTh?.value, 3))),
              abp_total: Math.max(1, Math.round(num(alertEls.abpTh?.value, 5))),
              duels_min: Math.max(1, Math.round(num(alertEls.duelsMin?.value, 10))),
              duels_rate_max: Math.max(0, Math.min(100, Math.round(num(alertEls.duelsRate?.value, 40)))),
              aerial_min: Math.max(1, Math.round(num(alertEls.aerialMin?.value, 8))),
              aerial_rate_max: Math.max(0, Math.min(100, Math.round(num(alertEls.aerialRate?.value, 40)))),
            };
            return cfg;
          };
          const renderAlertsUi = (cfg) => {
            const c = cfg && typeof cfg === 'object' ? cfg : defaultLiveAlerts();
            const en = c.enabled && typeof c.enabled === 'object' ? c.enabled : {};
            if (alertEls.lossesEnabled) alertEls.lossesEnabled.checked = en.losses_def !== false;
            if (alertEls.noShotsEnabled) alertEls.noShotsEnabled.checked = en.no_shots !== false;
            if (alertEls.cardsEnabled) alertEls.cardsEnabled.checked = en.cards !== false;
            if (alertEls.abpEnabled) alertEls.abpEnabled.checked = en.abp !== false;
            if (alertEls.duelsEnabled) alertEls.duelsEnabled.checked = en.duels !== false;
            if (alertEls.aerialEnabled) alertEls.aerialEnabled.checked = en.aerial !== false;
            if (alertEls.lossesTh) alertEls.lossesTh.value = String(Math.max(1, Number(c.losses_def_last5) || 3));
            if (alertEls.noShotsMin) alertEls.noShotsMin.value = String(Math.max(1, Number(c.no_shots_minute) || 20));
            if (alertEls.cardsTh) alertEls.cardsTh.value = String(Math.max(1, Number(c.cards_total) || 3));
            if (alertEls.abpTh) alertEls.abpTh.value = String(Math.max(1, Number(c.abp_total) || 5));
            if (alertEls.duelsMin) alertEls.duelsMin.value = String(Math.max(1, Number(c.duels_min) || 10));
            if (alertEls.duelsRate) alertEls.duelsRate.value = String(Math.max(0, Math.min(100, Number(c.duels_rate_max) || 40)));
            if (alertEls.aerialMin) alertEls.aerialMin.value = String(Math.max(1, Number(c.aerial_min) || 8));
            if (alertEls.aerialRate) alertEls.aerialRate.value = String(Math.max(0, Math.min(100, Number(c.aerial_rate_max) || 40)));
          };
          // Estado inicial.
          if (!liveAlertsState) liveAlertsState = defaultLiveAlerts();
          if (!workspaceLiveAlertsLoaded) {
            loadWorkspaceLiveAlerts().then((val) => {
              if (val && typeof val === 'object') {
                liveAlertsState = val;
                renderAlertsUi(liveAlertsState);
                scheduleRefreshLiveStatsHud();
              } else {
                renderAlertsUi(liveAlertsState);
              }
            });
          }
          // Bind cambios (feedback inmediato).
          Object.values(alertEls).forEach((el) => {
            if (!el || el.dataset.bound === '1') return;
            el.addEventListener('change', () => {
              liveAlertsState = readAlertsFromUi();
              scheduleRefreshLiveStatsHud();
            });
            el.dataset.bound = '1';
          });
          if (alertsSaveBtn) alertsSaveBtn.hidden = !canManageWorkspace;
          if (alertsSaveBtn && alertsSaveBtn.dataset.bound !== '1') {
            alertsSaveBtn.addEventListener('click', async () => {
              liveAlertsState = readAlertsFromUi();
              const ok = await saveWorkspaceLiveAlerts(liveAlertsState);
              if (ok) {
                showPageStatus && showPageStatus('Alertas guardadas para el club.', 'success', 2600);
              } else {
                showPageStatus && showPageStatus('No se pudieron guardar las alertas.', 'danger', 4200);
              }
            });
            alertsSaveBtn.dataset.bound = '1';
          }
          // Mantén el estado abierto/cerrado según lo que el usuario haya tocado.
        } catch (e) { /* ignore */ }
      };
      // Rendimiento: evita recalcular el HUD completo en cada toque (O(n) por evento).
      // Agrupa actualizaciones por frame.
      let liveStatsRaf = 0;
      const scheduleRefreshLiveStatsHud = () => {
        try {
          if (liveStatsRaf) return;
          liveStatsRaf = requestAnimationFrame(() => {
            liveStatsRaf = 0;
            refreshLiveStatsHud();
          });
        } catch (e) {
          // Fallback: si RAF no está disponible, refresca directo.
          refreshLiveStatsHud();
        }
      };
      const registerLiveEvent = ({ id = null, action = '', zone = '', result = '', minute = null }) => {
        const key = id ? `id:${id}` : `tmp:${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const minuteNum = Number(minute);
        liveEventStore.set(key, { action, zone, result, minute: Number.isFinite(minuteNum) ? minuteNum : null });
        scheduleRefreshLiveStatsHud();
      };
      const removeLiveEvent = (eventId) => {
        if (!eventId) return;
        liveEventStore.delete(`id:${eventId}`);
        scheduleRefreshLiveStatsHud();
      };

      highlight.className = 'touch-highlight';
      zoneLabel.className = 'zone-label';
      interactiveSurface.appendChild(highlight);
      interactiveSurface.appendChild(zoneLabel);
      const zoneOverlay = document.createElement('div');
      zoneOverlay.className = 'field-zone-overlay is-visible';
      fieldSurface.appendChild(zoneOverlay);
      const zoneOverlayToggleBtn = document.getElementById('zone-overlay-toggle');
      let zoneOverlayVisible = true;

      const renderZoneOverlay = () => {
        zoneOverlay.innerHTML = '';
        fieldZoneDefs.forEach((zone) => {
          const zoneEl = document.createElement('div');
          zoneEl.className = 'field-zone';
          zoneEl.style.left = zone.left;
          zoneEl.style.top = zone.top;
          zoneEl.style.width = zone.width;
          zoneEl.style.height = zone.height;
          zoneEl.dataset.zoneKey = zone.key;
          const label = document.createElement('span');
          label.textContent = zone.label;
          zoneEl.appendChild(label);
          zoneOverlay.appendChild(zoneEl);
        });
      };

      const setZoneOverlayVisibility = (visible) => {
        zoneOverlayVisible = visible;
        zoneOverlay.classList.toggle('is-visible', visible);
        if (zoneOverlayToggleBtn) {
          zoneOverlayToggleBtn.dataset.state = visible ? 'visible' : 'hidden';
          zoneOverlayToggleBtn.textContent = visible ? 'Ocultar zonas' : 'Ver zonas';
        }
      };

      renderZoneOverlay();
      if (zoneOverlayToggleBtn) {
        zoneOverlayToggleBtn.addEventListener('click', () => {
          setZoneOverlayVisibility(!zoneOverlayVisible);
        });
        setZoneOverlayVisibility(true);
      }
      if (matchInfoResetBtn) {
        matchInfoResetBtn.addEventListener('click', () => {
          renderMatchInfoState(matchInfoState);
          setMatchInfoEditing(false);
          showPageStatus('Datos de partido restablecidos en pantalla.', 'info', 2400);
        });
      }
      if (matchInfoSaveBtn) {
        matchInfoSaveBtn.addEventListener('click', async () => {
          Object.assign(matchInfoState, collectMatchInfoPayload());
          renderMatchInfoState(matchInfoState);
          setMatchInfoEditing(false);
          try {
            const response = await fetch(matchInfoSaveUrl, {
              method: 'POST',
              credentials: 'same-origin',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                Accept: 'application/json',
              },
              body: JSON.stringify({ match_info: matchInfoState }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
              showPageStatus(data.error || data.message || 'No se pudo guardar el partido.', 'danger', 5200);
              return;
            }
            try {
              if (Object.prototype.hasOwnProperty.call(data, 'score_for')) {
                matchInfoState.score_for = String(data.score_for ?? '').trim();
              }
              if (Object.prototype.hasOwnProperty.call(data, 'score_against')) {
                matchInfoState.score_against = String(data.score_against ?? '').trim();
              }
              renderMatchInfoState(matchInfoState);
              requestAnimationFrame(() => {
                if (typeof updateCloseSummary === 'function') updateCloseSummary({ matchInfo: { ...matchInfoState } });
              });
            } catch (e) {}
            showPageStatus('Datos del partido guardados.', 'success', 3200);
          } catch (err) {
            console.warn('No se pudo guardar el partido', err);
            showPageStatus('No se pudo guardar el partido (sin conexión).', 'warning', 5200);
          }
        });
      }
		      const hydrateLineupState = () => {
	        const parseEpoch = (value) => {
	          const raw = String(value || '').trim();
	          if (!raw) return 0;
	          const parsed = Date.parse(raw);
	          return Number.isFinite(parsed) ? parsed : 0;
	        };
		        const isRecentLocal = (persisted) => {
	          try {
	            const ts = Number(persisted?._meta?.local_ts || 0);
	            if (!Number.isFinite(ts) || ts <= 0) return false;
	            return (Date.now() - ts) < 120000; // 2 min
	          } catch (e) {
	            return false;
	          }
		        };
            const ensureLineupOrientationLR = () => {
              // Asegura que el 11 inicial esté en la misma orientación que el campo del registro (LR: izquierda→derecha).
              // El editor de "11 inicial" histórico guardaba coordenadas TB (vertical). Eso rompe el auto-jugador por zonas.
              try {
                const clampPct = (value, min = 0, max = 100) => {
                  const n = Number(value);
                  if (!Number.isFinite(n)) return NaN;
                  return Math.max(min, Math.min(max, n));
                };
                lineupState = lineupState && typeof lineupState === 'object' ? lineupState : { starters: [], bench: [] };
                if (!Array.isArray(lineupState.starters)) lineupState.starters = [];
                if (!Array.isArray(lineupState.bench)) lineupState.bench = [];
                lineupState._meta = (lineupState._meta && typeof lineupState._meta === 'object') ? lineupState._meta : {};
                const orientationRaw = String(lineupState._meta.orientation || '').trim().toLowerCase();
                const orientation = (orientationRaw === 'tb' || orientationRaw === 'portrait') ? 'tb' : 'lr';
                const looksTb = (() => {
                  const starters = Array.isArray(lineupState?.starters) ? lineupState.starters : [];
                  if (!starters.length) return false;
                  const findGk = starters.find((p) => {
                    const pos = String(p?.position || '').toLowerCase();
                    return Number(p?.slot_index) === 0 || pos.includes('por') || pos.includes('gk');
                  }) || starters[0];
                  const x = clampPct(findGk?.x_pct, 0, 100);
                  const y = clampPct(findGk?.y_pct, 0, 100);
                  return Number.isFinite(x) && Number.isFinite(y) && x >= 35 && x <= 65 && y >= 70;
                })();
                if (orientation === 'tb' || (orientationRaw === '' && looksTb)) {
                  lineupState.starters = (lineupState.starters || []).map((row) => {
                    const x = clampPct(row?.x_pct, 0, 100);
                    const y = clampPct(row?.y_pct, 0, 100);
                    if (!Number.isFinite(x) || !Number.isFinite(y)) return row;
                    // TB -> LR: x_lr = 100 - y_tb ; y_lr = x_tb
                    return { ...row, x_pct: clampPct(100 - y, 0, 100), y_pct: clampPct(x, 0, 100) };
                  });
                  lineupState._meta.orientation = 'lr';
                } else if (!orientationRaw) {
                  lineupState._meta.orientation = 'lr';
                }
              } catch (e) {}
            };
		        try {
		          const seedRaw = document.getElementById('initial-lineup-server')?.textContent || '';
		          if (seedRaw) {
		            const seed = JSON.parse(seedRaw);
		            if (seed && typeof seed === 'object') {
		              lineupState = seed;
		            }
		          }
		        } catch (err) {
		          console.warn('No se pudo leer el 11 inicial del servidor', err);
		        }
		        if (lineupStorageKey) {
		          try {
		            const rawPersisted = localStorage.getItem(lineupStorageKey);
		            if (rawPersisted) {
		              const persisted = JSON.parse(rawPersisted);
		              const serverSavedAt = parseEpoch(lineupState?._meta?.saved_at || lineupState?._meta?.server_saved_at);
		              const persistedServerSavedAt = parseEpoch(persisted?._meta?.server_saved_at || persisted?._meta?.saved_at);
		              const prefersServer = Boolean(
		                serverSavedAt
		                && (!persistedServerSavedAt || serverSavedAt > persistedServerSavedAt)
		                && !isRecentLocal(persisted),
		              );
		              if (prefersServer) {
		                try {
		                  localStorage.setItem(lineupStorageKey, JSON.stringify(lineupState || { starters: [], bench: [] }));
		                } catch (e) {}
		              } else if (persisted && typeof persisted === 'object') {
		                lineupState = persisted;
                    ensureLineupOrientationLR();
		                return;
		              }
		            }
		          } catch (err) {
		            console.warn('No se pudo recuperar el 11 inicial persistido', err);
		          }
		        }
	        if (!lineupInput?.value) {
            ensureLineupOrientationLR();
	          return;
	        }
		        try {
		          const current = JSON.parse(lineupInput.value);
		          lineupState = current && typeof current === 'object' ? current : lineupState;
		        } catch (err) {
		          console.error('Invalid lineup payload', err);
		        }
		        try {
		          if (!lineupState || typeof lineupState !== 'object') lineupState = { starters: [], bench: [] };
		          if (!Array.isArray(lineupState.starters)) lineupState.starters = [];
		          if (!Array.isArray(lineupState.bench)) lineupState.bench = [];
		        } catch (e) {}
            ensureLineupOrientationLR();
		        lastLineupSignature = lineupSignature(lineupState);
		        lastSavedLineupSnapshot = JSON.stringify(lineupState || { starters: [], bench: [] });
		      };
	      const refreshLineupFromServer = async ({ quiet = true } = {}) => {
	        if (!lineupGetUrl) return false;
	        try {
	          // `navigator.onLine` no es fiable en iOS/WKWebView: si reporta offline, verificamos contra servidor.
	          const reportedOffline = (typeof navigator !== 'undefined' && navigator && navigator.onLine === false);
	          if (reportedOffline) {
	            let reachable = false;
	            try {
	              const url = keepaliveUrl || '/api/session/keepalive/';
	              const opts = { method: 'GET', credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } };
	              if (typeof AbortController !== 'undefined') {
	                const ctrl = new AbortController();
	                const timer = window.setTimeout(() => { try { ctrl.abort(); } catch (e) {} }, 2500);
	                try {
	                  const resp = await fetch(url, { ...opts, signal: ctrl.signal });
	                  reachable = !!(resp && resp.ok);
	                } catch (e) {
	                  reachable = false;
	                } finally {
	                  try { window.clearTimeout(timer); } catch (e) {}
	                }
	              } else {
	                const resp = await fetch(url, opts);
	                reachable = !!(resp && resp.ok);
	              }
	            } catch (e) {
	              reachable = false;
	            }
	            if (!reachable) return false;
	          }
	        } catch (e) {}
	        try {
	          const response = await fetch(lineupGetUrl, {
	            method: 'GET',
	            credentials: 'same-origin',
	            headers: { Accept: 'application/json' },
	          });
	          const data = await response.json().catch(() => ({}));
	          if (!response.ok || !data || data.ok !== true || typeof data.lineup !== 'object') {
	            return false;
	          }
	          const incoming = data.lineup;
	          const parseEpoch = (value) => {
	            const raw = String(value || '').trim();
	            if (!raw) return 0;
	            const parsed = Date.parse(raw);
	            return Number.isFinite(parsed) ? parsed : 0;
	          };
	          const incomingSavedAt = parseEpoch(incoming?._meta?.saved_at || incoming?._meta?.server_saved_at);
	          const currentSavedAt = parseEpoch(lineupState?._meta?.server_saved_at || lineupState?._meta?.saved_at);
	          if (incomingSavedAt && currentSavedAt && incomingSavedAt <= currentSavedAt) {
	            return false;
	          }
	          lineupState = incoming;
	          try { lastLineupSignature = lineupSignature(lineupState); } catch (e) {}
	          lastSavedLineupSnapshot = JSON.stringify(lineupState || { starters: [], bench: [] });
	          if (lineupStorageKey) {
	            try { localStorage.setItem(lineupStorageKey, lastSavedLineupSnapshot); } catch (e) {}
	          }
	          if (lineupInput) lineupInput.value = lastSavedLineupSnapshot;
	          try { renderLineup(); } catch (e) {}
	          if (!quiet && typeof showPageStatus === 'function') {
	            showPageStatus('11 inicial sincronizado.', 'info', 1800);
	          }
	          return true;
	        } catch (err) {
	          return false;
	        }
	      };
	      const updateLineupInput = () => {
	        try {
	          lineupState = lineupState && typeof lineupState === 'object' ? lineupState : { starters: [], bench: [] };
	          if (!Array.isArray(lineupState.starters)) lineupState.starters = [];
	          if (!Array.isArray(lineupState.bench)) lineupState.bench = [];
	          lineupState._meta = lineupState._meta && typeof lineupState._meta === 'object' ? lineupState._meta : {};
	          const sig = lineupSignature(lineupState);
	          if (sig && sig !== lastLineupSignature) {
	            lastLineupSignature = sig;
	            lineupState._meta.local_ts = Date.now();
	          }
	          if (lineupState._meta.saved_at && !lineupState._meta.server_saved_at) {
	            lineupState._meta.server_saved_at = lineupState._meta.saved_at;
	          }
	        } catch (e) {}
	        const lineupSnapshot = JSON.stringify(lineupState || { starters: [], bench: [] });
	        if (lineupInput) {
	          lineupInput.value = lineupSnapshot;
	        }
	        if (lineupStorageKey) {
          try {
            localStorage.setItem(lineupStorageKey, lineupSnapshot);
          } catch (err) {
            console.warn('No se pudo persistir el 11 inicial', err);
          }
        }
        if (lineupPersistDisabled || lineupSnapshot === lastSavedLineupSnapshot) {
          return;
        }
        if (lineupPersistTimer) {
          clearTimeout(lineupPersistTimer);
        }
        lineupPersistTimer = setTimeout(async () => {
          try {
            const response = await fetch(lineupSaveUrl, {
              method: 'POST',
              credentials: 'same-origin',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                Accept: 'application/json',
              },
              body: JSON.stringify({ lineup: lineupState }),
            });
            if (!response.ok) {
              const data = await response.json().catch(() => ({}));
              if (response.status === 403) {
                lineupPersistDisabled = true;
              }
              showPageStatus(
                data.error || 'No se pudo guardar el 11 inicial.',
                response.status === 403 ? 'warning' : 'danger',
                5200,
              );
              return;
	            }
	            const data = await response.json().catch(() => ({}));
	            try {
	              const serverLineup = (data && typeof data.lineup === 'object') ? data.lineup : null;
	              const savedAt = (data && data.saved_at) ? String(data.saved_at) : '';
	              if (serverLineup) {
	                lineupState = serverLineup;
	              }
		              if (savedAt) {
		                lineupState = lineupState && typeof lineupState === 'object' ? lineupState : { starters: [], bench: [] };
		                lineupState._meta = lineupState._meta && typeof lineupState._meta === 'object' ? lineupState._meta : {};
		                lineupState._meta.server_saved_at = savedAt;
		                lineupState._meta.saved_at = savedAt;
		              }
		              try { lastLineupSignature = lineupSignature(lineupState); } catch (e) {}
		              lastSavedLineupSnapshot = JSON.stringify(lineupState || { starters: [], bench: [] });
		              if (lineupStorageKey) {
		                try { localStorage.setItem(lineupStorageKey, lastSavedLineupSnapshot); } catch (e) {}
		              }
	              if (lineupInput) lineupInput.value = lastSavedLineupSnapshot;
	              try { renderLineup(); } catch (e) {}
	            } catch (e) {
	              lastSavedLineupSnapshot = lineupSnapshot;
	            }
	          } catch (err) {
	            console.warn('No se pudo guardar el 11 inicial en servidor', err);
	            showPageStatus('No se pudo guardar el 11 inicial en servidor.', 'warning', 5200);
	          }
        }, 450);
      };
	      let selectedPlayerId = null;
	      let lastPlayerPickAt = 0;
	      let lastPlayerPickSource = 'manual';
	      let nextPlayerPickSource = 'manual';
	      const autoPlayerStorageKey = 'webstats:live:auto_player:v1';
	      let autoPlayerEnabled = (() => {
	        try {
	          const raw = localStorage.getItem(autoPlayerStorageKey);
	          if (raw === null || raw === undefined || raw === '') return true;
	          return String(raw) === '1';
	        } catch (e) {
	          return true;
	        }
	      })();
	      const syncAutoPlayerToggleUi = () => {
	        if (!autoPlayerToggleBtn) return;
	        autoPlayerToggleBtn.textContent = autoPlayerEnabled ? 'Auto: ON' : 'Auto: OFF';
	        autoPlayerToggleBtn.style.borderColor = autoPlayerEnabled ? 'rgba(34, 211, 238, 0.45)' : 'rgba(248, 113, 113, 0.4)';
	        autoPlayerToggleBtn.style.background = autoPlayerEnabled ? 'rgba(34, 211, 238, 0.12)' : 'rgba(127, 29, 29, 0.25)';
	        autoPlayerToggleBtn.style.color = autoPlayerEnabled ? 'rgba(224, 242, 254, 0.95)' : 'rgba(254, 202, 202, 0.95)';
	      };
	      if (autoPlayerToggleBtn) {
	        syncAutoPlayerToggleUi();
	        autoPlayerToggleBtn.addEventListener('click', () => {
	          autoPlayerEnabled = !autoPlayerEnabled;
	          try { localStorage.setItem(autoPlayerStorageKey, autoPlayerEnabled ? '1' : '0'); } catch (e) {}
	          syncAutoPlayerToggleUi();
	          showPageStatus(autoPlayerEnabled ? 'Auto-jugador activado.' : 'Auto-jugador desactivado.', 'info', 1800);
	        });
	      }
		      const clearPlayerSelection = () => {
		        selectedPlayerId = null;
	        lastPlayerPickAt = Date.now();
	        lastPlayerPickSource = 'manual';
	        if (playerInput) {
	          playerInput.value = '';
	        }
	        document.querySelectorAll('.lineup-chip.selected').forEach((chip) => chip.classList.remove('selected'));
	        convocationCards.forEach((card) => card.classList.remove('selected'));
	        if (playerQuickBlock) {
	          playerQuickBlock.classList.remove('is-visible');
	        }
		        if (typeof setSubTapMode === 'function') {
		          setSubTapMode(false);
		        }
		        try { writeProState({ player_id: '' }); } catch (e) {}
		      };
		      const selectPlayer = (playerId) => {
		        selectedPlayerId = playerId;
	        lastPlayerPickAt = Date.now();
	        lastPlayerPickSource = nextPlayerPickSource || 'manual';
	        nextPlayerPickSource = 'manual';
	        if (playerInput) {
	          playerInput.value = playerId;
	        }
	        document.querySelectorAll('.lineup-chip').forEach((chip) => {
	          chip.classList.toggle('selected', chip.dataset.playerId === playerId);
	        });
		        convocationCards.forEach((card) => {
		          card.classList.toggle('selected', card.dataset.playerId === playerId);
		        });
		        try { writeProState({ player_id: String(playerId || '').trim(), action: String(actionInput?.value || '').trim() }); } catch (e) {}
		        updatePlayerQuickPanel();
		        try { renderProQuickPlayers(); } catch (e) {}
		        try {
		          maybeHandleTapSubstitution(playerId);
		        } catch (err) {
		          // ignore
		        }
		      };
		      if (proClearPlayerBtn) {
		        proClearPlayerBtn.addEventListener('click', () => {
		          try { clearPlayerSelection(); } catch (e) {}
		        });
		      }
		      if (proUndoBtn) {
		        proUndoBtn.addEventListener('click', () => {
		          try { document.getElementById('undo-last-action-btn')?.click?.(); } catch (e) {}
		        });
		      }
		      function renderProQuickPlayers() {
		        if (!document.body.classList.contains('pro-mode')) return;
		        if (!proQuickPanel || !proOnfieldChips || !proBenchChips) return;
		        const starters = Array.isArray(lineupState?.starters) ? lineupState.starters : [];
		        const bench = Array.isArray(lineupState?.bench) ? lineupState.bench : [];
		        const build = (wrap, list, labelEmpty) => {
		          wrap.innerHTML = '';
		          if (!list.length) {
		            const span = document.createElement('span');
		            span.className = 'meta';
		            span.style.opacity = '0.8';
		            span.textContent = labelEmpty;
		            wrap.appendChild(span);
		            return;
		          }
		          list.slice(0, 30).forEach((player) => {
		            const id = String(player?.id || '').trim();
		            if (!id) return;
		            const btn = document.createElement('button');
		            btn.type = 'button';
		            btn.className = 'pro-chip';
		            const num = String(player?.number || '').trim();
		            const name = String(player?.name || 'JUGADOR').trim().toUpperCase();
		            btn.innerHTML = `${num ? `#${num}` : '#--'} <small>${name}</small>`;
		            btn.classList.toggle('is-selected', String(selectedPlayerId || '') === id);
		            btn.addEventListener('click', () => {
		              nextPlayerPickSource = 'pro';
		              selectPlayer(id);
		            });
		            wrap.appendChild(btn);
		          });
		        };
		        build(proOnfieldChips, starters, 'Define el 11 inicial para tener chips aquí.');
		        build(proBenchChips, bench, 'Sin suplentes.');
		        if (proQuickMeta) {
		          const selected = String(selectedPlayerId || '').trim();
		          if (!selected) proQuickMeta.textContent = 'Pulsa un jugador para seleccionar';
		          else proQuickMeta.textContent = 'Jugador seleccionado · toca Acción y luego una zona en el campo';
		        }
		      }
	      const proStateKey = currentMatchId ? `webstats:match_actions:pro_state:v1:${currentMatchId}` : '';
	      const proPresetsKey = currentMatchId ? `webstats:match_actions:pro_presets:v1:${currentMatchId}` : '';
		      const readProState = () => {
		        if (!proStateKey) return null;
		        try {
		          const raw = localStorage.getItem(proStateKey) || '';
		          const parsed = raw ? JSON.parse(raw) : null;
		          return parsed && typeof parsed === 'object' ? parsed : null;
		        } catch (e) {
		          return null;
		        }
		      };
		      const writeProState = (patch) => {
		        if (!proStateKey) return;
		        try {
		          const current = readProState() || {};
		          const next = { ...current, ...(patch && typeof patch === 'object' ? patch : {}) };
		          next._ts = Date.now();
		          localStorage.setItem(proStateKey, JSON.stringify(next));
		        } catch (e) {}
		      };
		      const restoreProState = () => {
		        const st = readProState();
		        if (!st) return;
		        // Ignora estados viejos (evita "arrastrar" selección a otro partido/otro día).
		        try {
		          const ts = Number(st._ts || 0);
		          if (ts && Date.now() - ts > 8 * 60 * 60 * 1000) return;
		        } catch (e) {}
		        try {
		          const pid = String(st.player_id || '').trim();
		          if (pid) {
		            nextPlayerPickSource = 'restore';
		            selectPlayer(pid);
		          }
		        } catch (e) {}
		        try {
		          const a = String(st.action || '').trim();
		          if (a && actionInput) {
		            actionInput.value = a;
		          }
		        } catch (e) {}
		        try {
		          const r = String(st.result || '').trim();
		          if (r && resultSelect) {
		            setResultValue(r, { silent: true });
		          }
		        } catch (e) {}
		      };
	      const readProPresets = () => {
	        if (!proPresetsKey) return [];
	        try {
	          const raw = localStorage.getItem(proPresetsKey) || '';
	          const parsed = raw ? JSON.parse(raw) : null;
	          return Array.isArray(parsed) ? parsed : [];
	        } catch (e) {
	          return [];
	        }
	      };
	      const writeProPresets = (list) => {
	        if (!proPresetsKey) return;
	        try {
	          localStorage.setItem(proPresetsKey, JSON.stringify(Array.isArray(list) ? list : []));
	        } catch (e) {}
	      };
	      const normalizePreset = (preset) => {
	        if (!preset || typeof preset !== 'object') return null;
	        const action = String(preset.action || '').trim();
	        const result = String(preset.result || '').trim();
	        if (!action || !result) return null;
	        return { action, result };
	      };
	      const applyPreset = (preset) => {
	        const p = normalizePreset(preset);
	        if (!p) return false;
	        if (actionInput) actionInput.value = p.action;
	        try { syncResultOptionsForAction(p.action); } catch (e) {}
	        if (resultSelect) resultSelect.value = p.result;
	        try { writeProState({ action: p.action, result: p.result, player_id: String(selectedPlayerId || '').trim() }); } catch (e) {}
	        try { showPageStatus(`Preset: ${p.action} · ${p.result}`, 'info', 1200); } catch (e) {}
	        return true;
	      };
	      const renderPresetButtons = () => {
	        const list = readProPresets();
	        proPresetBtns.forEach((btn, idx) => {
	          const p = normalizePreset(list[idx]);
	          const label = p ? `${p.action} · ${p.result}` : `Preset ${idx + 1}`;
	          btn.textContent = label.length > 22 ? `${label.slice(0, 21)}…` : label;
	          btn.dataset.presetIndex = String(idx);
	          btn.classList.toggle('is-selected', !!p);
	        });
	      };
	      const savePresetAt = (index) => {
	        const idx = Number(index);
	        if (!Number.isFinite(idx) || idx < 0 || idx >= proPresetBtns.length) return false;
	        const action = String(actionInput?.value || '').trim();
	        const result = String(resultSelect?.value || '').trim();
	        if (!action || !result) {
	          showPageStatus('Para guardar preset: selecciona Acción y Resultado.', 'warning', 2400);
	          return false;
	        }
	        const list = readProPresets();
	        while (list.length < proPresetBtns.length) list.push(null);
	        list[idx] = { action, result };
	        writeProPresets(list);
	        renderPresetButtons();
	        showPageStatus(`Guardado en Preset ${idx + 1}.`, 'success', 1600);
	        return true;
	      };
	      const bindPresetButton = (btn) => {
	        if (!btn) return;
	        const idx = Number(btn.dataset.presetIndex || '');
	        let pressTimer = null;
	        let longPressFired = false;
	        const clear = () => {
	          if (pressTimer) window.clearTimeout(pressTimer);
	          pressTimer = null;
	        };
	        const start = (ev) => {
	          longPressFired = false;
	          clear();
	          pressTimer = window.setTimeout(() => {
	            longPressFired = true;
	            savePresetAt(idx);
	          }, 650);
	          try { ev.preventDefault(); } catch (e) {}
	        };
	        const end = (ev) => {
	          clear();
	          if (longPressFired) return;
	          const list = readProPresets();
	          const p = normalizePreset(list[idx]);
	          if (!p) {
	            showPageStatus('Preset vacío. Mantén pulsado para guardar.', 'warning', 2000);
	            return;
	          }
	          applyPreset(p);
	          try { ev.preventDefault(); } catch (e) {}
	        };
	        btn.addEventListener('pointerdown', start);
	        btn.addEventListener('pointerup', end);
	        btn.addEventListener('pointercancel', clear);
	        btn.addEventListener('contextmenu', (ev) => { try { ev.preventDefault(); } catch (e) {} });
	      };
	      if (proPresetBtns.length) {
	        // set dataset indices now
	        proPresetBtns.forEach((btn, idx) => { btn.dataset.presetIndex = String(idx); });
	        renderPresetButtons();
	        proPresetBtns.forEach(bindPresetButton);
	      }
	      if (proRepeatLastBtn) {
	        // Tap: aplica última acción+resultado. Pulsación larga: registra directamente en la última zona tocada.
	        let pressTimer = null;
	        let longPressFired = false;
	        const clear = () => {
	          if (pressTimer) window.clearTimeout(pressTimer);
	          pressTimer = null;
	        };
	        proRepeatLastBtn.addEventListener('pointerdown', (ev) => {
	          longPressFired = false;
	          clear();
	          pressTimer = window.setTimeout(() => {
	            longPressFired = true;
	            try { liveController?.repeatLastAtLastZone?.(); } catch (e) {}
	          }, 650);
	          try { ev.preventDefault(); } catch (e) {}
	        });
	        proRepeatLastBtn.addEventListener('pointerup', (ev) => {
	          clear();
	          if (longPressFired) return;
	          const st = readProState() || {};
	          const action = String(st.action || '').trim();
	          const result = String(st.result || '').trim();
	          if (!action || !result) {
	            showPageStatus('Aún no hay “última” acción+resultado.', 'warning', 2000);
	            return;
	          }
	          applyPreset({ action, result });
	          try { ev.preventDefault(); } catch (e) {}
	        });
	        proRepeatLastBtn.addEventListener('pointercancel', clear);
	      }
      const createLineupChip = (player, sectionKey) => {
        const span = document.createElement('span');
        span.className = 'lineup-name lineup-chip';
        const displayName = (player.name || 'JUGADOR').toUpperCase();
        const numberLabel = `#${player.number || '--'}`;
        const title = document.createElement('strong');
        title.className = 'lineup-chip-name';
        title.textContent = displayName;
        span.appendChild(title);

        const photo = String(player.photo || '').trim();
        const img = document.createElement('img');
        img.src = photo || playerAvatarFallback;
        img.alt = displayName;
        img.loading = 'lazy';
        img.className = photo ? 'lineup-chip-avatar' : 'lineup-chip-avatar fallback';
        span.appendChild(img);
        const number = document.createElement('span');
        number.className = 'lineup-chip-number';
        number.textContent = numberLabel;
        span.appendChild(number);
	        span.dataset.playerId = player.id;
	        span.dataset.playerNumber = player.number || '';
	        span.dataset.section = sectionKey;
	        span.draggable = true;
	        span.addEventListener('dragstart', (event) => {
	          try { document.body.classList.add('is-dragging'); } catch (e) {}
	          event.dataTransfer?.setData('text/plain', JSON.stringify(player));
	          event.dataTransfer?.setData('source-section', sectionKey);
	        });
	        span.addEventListener('dragend', () => {
	          try { document.body.classList.remove('is-dragging'); } catch (e) {}
	        });
	        span.addEventListener('click', () => {
	          nextPlayerPickSource = 'manual';
	          selectPlayer(player.id);
	        });
	        span.addEventListener('dblclick', () => removeLineupEntry(player.id));
	        return span;
	      };
      const renderLineupSection = (sectionKey) => {
        const section = lineupSections[sectionKey];
        if (!section?.element) {
          return;
        }
        section.element.innerHTML = '';
        const players = lineupState[sectionKey] || [];
        if (!players.length) {
          const placeholder = document.createElement('span');
          placeholder.className = 'lineup-placeholder';
          placeholder.textContent = section.placeholder;
          section.element.appendChild(placeholder);
          return;
        }
        players.forEach((player) => {
          section.element.appendChild(createLineupChip(player, sectionKey));
        });
      };
      const refreshLineupCounts = () => {
        Object.keys(lineupSections).forEach((sectionKey) => {
          const section = lineupSections[sectionKey];
          if (!section) {
            return;
          }
          const count = lineupState[sectionKey]?.length || 0;
          if (section.countEl) {
            section.countEl.textContent =
              sectionKey === 'starters' ? `${count}/11` : `${count}`;
          }
        });
      };
      const refreshCardAssignments = () => {
        const assigned = new Map();
        Object.keys(lineupState).forEach((sectionKey) => {
          lineupState[sectionKey].forEach((player) => {
            if (player?.id) {
              assigned.set(String(player.id), sectionKey);
            }
          });
        });
        convocationCards.forEach((card) => {
          const playerId = String(card.dataset.playerId);
          const assignedSection = assigned.get(playerId);
          card.classList.toggle('is-assigned', Boolean(assignedSection));
          if (assignedSection) {
            card.dataset.assignedSection = assignedSection;
          } else {
            delete card.dataset.assignedSection;
          }
        });
      };
      const renderPreLineupSummary = () => {
        if (!preLineupCountEl || !preLineupChipsEl) return;
        const starters = lineupState.starters || [];
        preLineupCountEl.textContent = `${starters.length}/11`;
        preLineupChipsEl.innerHTML = '';
        if (!starters.length) {
          const empty = document.createElement('span');
          empty.className = 'pre-lineup-empty';
          empty.textContent = 'Arrastra titulares desde la convocatoria o usa “Cuerpo técnico → Partidos → 11 inicial”.';
          preLineupChipsEl.appendChild(empty);
          return;
        }
        starters.slice(0, 11).forEach((player) => {
          const chip = document.createElement('span');
          chip.className = 'pre-lineup-chip';
          const number = document.createElement('strong');
          number.textContent = `#${player.number || '--'}`;
          const name = document.createElement('span');
          name.textContent = String(player.name || 'JUGADOR').toUpperCase();
          chip.appendChild(number);
          chip.appendChild(name);
          preLineupChipsEl.appendChild(chip);
        });
      };
      // --- Táctica (Prepartido): once sobre el campo ---
      const tacticsPitch = document.getElementById('tactics-pitch');
      const tacticsTokensEl = document.getElementById('tactics-tokens');
      const tacticsResetBtn = document.getElementById('tactics-reset-positions');
      let renderTacticsBoard = () => {};
      const clampPct = (value, min, max) => Math.max(min, Math.min(max, value));
      const safeNumber = (raw, fallback = NaN) => {
        const n = Number(raw);
        return Number.isFinite(n) ? n : fallback;
      };
      const shortDisplayName = (full) => {
        const raw = String(full || '').trim();
        if (!raw) return '';
        const parts = raw.split(/\\s+/).filter(Boolean);
        if (parts.length === 1) return parts[0].slice(0, 10);
        const last = parts[parts.length - 1];
        return last.slice(0, 12);
      };
      const roleBucketFromPositionLite = (positionRaw) => {
        const pos = String(positionRaw || '').trim().toLowerCase();
        if (!pos) return 'any';
        const compact = pos.replace(/\\s+/g, '');
        if (compact.includes('por') || compact.includes('portero') || compact === 'gk') return 'gk';
        if (
          compact.includes('def')
          || compact.includes('central')
          || compact.includes('lateral')
          || compact.includes('carril')
          || compact.includes('cb')
          || compact.includes('lb')
          || compact.includes('rb')
        ) return 'def';
        if (
          compact.includes('mc')
          || compact.includes('mcd')
          || compact.includes('mco')
          || compact.includes('medio')
          || compact.includes('interior')
          || compact.includes('piv')
          || compact.includes('mp')
          || compact.includes('cm')
        ) return 'mid';
        if (
          compact.includes('del')
          || compact.includes('ext')
          || compact.includes('ei')
          || compact.includes('ed')
          || compact.includes('punta')
          || compact === 'dc'
          || compact.includes('st')
          || compact.includes('fw')
        ) return 'att';
        return 'any';
      };
      const defaultBaseSlots = [
        { x: 50, y: 86 }, // GK
        { x: 18, y: 72 },
        { x: 38, y: 74 },
        { x: 62, y: 74 },
        { x: 82, y: 72 },
        { x: 30, y: 52 },
        { x: 50, y: 56 },
        { x: 70, y: 52 },
        { x: 25, y: 30 },
        { x: 50, y: 26 },
        { x: 75, y: 30 },
      ];
      const pickPlayersByRole = (players, role) => {
        const list = Array.isArray(players) ? players.slice() : [];
        const inRole = [];
        const other = [];
        list.forEach((p) => {
          if (!p || !p.id) return;
          const bucket = roleBucketFromPositionLite(p.position);
          if (bucket === role) inRole.push(p);
          else other.push(p);
        });
        const sortKey = (p) => {
          const num = safeNumber(p.number, 999);
          const name = String(p.name || '').toLowerCase();
          return [Number.isFinite(num) ? num : 999, name, String(p.id)];
        };
        const cmp = (a, b) => {
          const ka = sortKey(a);
          const kb = sortKey(b);
          for (let i = 0; i < ka.length; i += 1) {
            if (ka[i] < kb[i]) return -1;
            if (ka[i] > kb[i]) return 1;
          }
          return 0;
        };
        inRole.sort(cmp);
        other.sort(cmp);
        return { inRole, other };
      };
      const applyBasePositionsToStarters = () => {
        const starters = Array.isArray(lineupState?.starters) ? lineupState.starters.slice(0, 11) : [];
        if (!starters.length) return;
        const pool = starters.map((p) => ({ ...p }));
        const picks = [];
        const consume = (role, count) => {
          const { inRole, other } = pickPlayersByRole(pool, role);
          const chosen = inRole.slice(0, count);
          const chosenIds = new Set(chosen.map((p) => String(p.id)));
          const rest = [...inRole.slice(count), ...other].filter((p) => !chosenIds.has(String(p.id)));
          pool.splice(0, pool.length, ...rest);
          picks.push(...chosen);
        };
        consume('gk', 1);
        consume('def', 4);
        consume('mid', 3);
        consume('att', 3);
        if (picks.length < starters.length) {
          picks.push(...pool.slice(0, Math.max(0, starters.length - picks.length)));
        }
        const byId = new Map(picks.map((p, idx) => [String(p.id), idx]));
        lineupState.starters = starters.map((row) => {
          const idx = byId.get(String(row.id));
          const slot = defaultBaseSlots[idx !== undefined ? idx : 0] || defaultBaseSlots[0];
          return { ...row, slot_index: (idx !== undefined ? idx : (safeNumber(row.slot_index, 0) || 0)), x_pct: slot.x, y_pct: slot.y };
        });
        updateLineupInput();
        try { renderTacticsBoard(); } catch (e) {}
      };
      const createTacticsToken = (player) => {
        const id = String(player?.id || '').trim();
        if (!id) return null;
        const el = document.createElement('div');
        el.className = 'tactics-token';
        el.dataset.playerId = id;
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        const photo = String(player?.photo || '').trim();
        if (photo) {
          avatar.style.backgroundImage = `url(\"${photo.replace(/\"/g, '\\\\\"')}\")`;
        } else {
          avatar.classList.add('fallback');
          avatar.textContent = String(getInitials(player?.name || player?.number || '?'));
        }
        const badge = document.createElement('div');
        badge.className = 'badge';
        badge.textContent = player?.number ? String(player.number).slice(0, 3) : '--';
        const name = document.createElement('div');
        name.className = 'name';
        name.textContent = shortDisplayName(player?.name || 'Jugador').toUpperCase();
        el.appendChild(avatar);
        el.appendChild(badge);
        el.appendChild(name);

        let dragging = false;
        let downAt = null;
        let offsetPx = { x: 0, y: 0 };
        const getPitchRect = () => tacticsPitch?.getBoundingClientRect?.() || null;
        const setFromClient = (clientX, clientY) => {
          const rect = getPitchRect();
          if (!rect) return;
          const x = clampPct(((clientX - rect.left) / rect.width) * 100, 4, 96);
          const y = clampPct(((clientY - rect.top) / rect.height) * 100, 6, 94);
          el.style.left = `${x}%`;
          el.style.top = `${y}%`;
        };
        const persistPctFromClient = (clientX, clientY) => {
          const rect = getPitchRect();
          if (!rect) return;
          const x = clampPct(((clientX - rect.left) / rect.width) * 100, 4, 96);
          const y = clampPct(((clientY - rect.top) / rect.height) * 100, 6, 94);
          const starters = Array.isArray(lineupState?.starters) ? lineupState.starters : [];
          lineupState.starters = starters.map((row) => (String(row?.id || '') === id ? { ...row, x_pct: x, y_pct: y } : row));
          updateLineupInput();
        };

        el.addEventListener('pointerdown', (event) => {
          if (!tacticsPitch) return;
          if (event.button !== undefined && event.button !== 0) return;
          try { el.setPointerCapture(event.pointerId); } catch (e) {}
          dragging = false;
          downAt = { x: event.clientX, y: event.clientY };
          el.classList.add('is-dragging');
          const rect = getPitchRect();
          if (rect) {
            const computedLeft = safeNumber(String(el.style.left || '').replace('%', ''), NaN);
            const computedTop = safeNumber(String(el.style.top || '').replace('%', ''), NaN);
            const pxLeft = Number.isFinite(computedLeft) ? (rect.left + (computedLeft / 100) * rect.width) : event.clientX;
            const pxTop = Number.isFinite(computedTop) ? (rect.top + (computedTop / 100) * rect.height) : event.clientY;
            offsetPx = { x: event.clientX - pxLeft, y: event.clientY - pxTop };
          }
        });
        el.addEventListener('pointermove', (event) => {
          if (!downAt) return;
          const dx = Math.abs(event.clientX - downAt.x);
          const dy = Math.abs(event.clientY - downAt.y);
          if (!dragging && (dx + dy) > 7) dragging = true;
          if (!dragging) return;
          setFromClient(event.clientX - offsetPx.x, event.clientY - offsetPx.y);
        });
        const endDrag = (event) => {
          if (!downAt) return;
          const wasDragging = dragging;
          downAt = null;
          dragging = false;
          el.classList.remove('is-dragging');
          if (wasDragging) {
            persistPctFromClient(event.clientX - offsetPx.x, event.clientY - offsetPx.y);
            try { renderTacticsBoard(); } catch (e) {}
            return;
          }
          try {
            nextPlayerPickSource = 'manual';
            selectPlayer(id);
            try { renderTacticsBoard(); } catch (e) {}
          } catch (e) {}
        };
        el.addEventListener('pointerup', endDrag);
        el.addEventListener('pointercancel', endDrag);
        return el;
      };
      const createRivalTacticsToken = (player) => {
        const code = String(player?.code || player?.id || player?.name || '').trim();
        if (!code) return null;
        const el = document.createElement('div');
        el.className = 'tactics-token is-rival';
        el.dataset.playerCode = code;
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        const badge = document.createElement('div');
        badge.className = 'badge';
        badge.textContent = player?.number ? String(player.number).slice(0, 3) : '--';
        const name = document.createElement('div');
        name.className = 'name';
        name.textContent = shortDisplayName(player?.name || 'Rival').toUpperCase();
        avatar.classList.add('fallback');
        avatar.textContent = String(getInitials(player?.name || player?.number || 'R'));
        el.appendChild(avatar);
        el.appendChild(badge);
        el.appendChild(name);

        let dragging = false;
        let downAt = null;
        let offsetPx = { x: 0, y: 0 };
        const getPitchRect = () => tacticsPitch?.getBoundingClientRect?.() || null;
        const setFromClient = (clientX, clientY) => {
          const rect = getPitchRect();
          if (!rect) return;
          const x = clampPct(((clientX - rect.left) / rect.width) * 100, 4, 96);
          const y = clampPct(((clientY - rect.top) / rect.height) * 100, 6, 94);
          el.style.left = `${x}%`;
          el.style.top = `${y}%`;
        };
        const persistPctFromClient = (clientX, clientY) => {
          const rect = getPitchRect();
          if (!rect) return;
          const x = clampPct(((clientX - rect.left) / rect.width) * 100, 4, 96);
          const y = clampPct(((clientY - rect.top) / rect.height) * 100, 6, 94);
          const starters = Array.isArray(rivalLineupState?.starters) ? rivalLineupState.starters : [];
          rivalLineupState.starters = starters.map((row) => {
            const rowCode = String(row?.code || row?.id || row?.name || '').trim();
            return rowCode === code ? { ...row, x_pct: x, y_pct: y } : row;
          });
          updateRivalLineupState();
        };

        el.addEventListener('pointerdown', (event) => {
          if (!tacticsPitch) return;
          if (!rivalVisible) return;
          if (event.button !== undefined && event.button !== 0) return;
          try { el.setPointerCapture(event.pointerId); } catch (e) {}
          dragging = false;
          downAt = { x: event.clientX, y: event.clientY };
          el.classList.add('is-dragging');
          const rect = getPitchRect();
          if (rect) {
            const computedLeft = safeNumber(String(el.style.left || '').replace('%', ''), NaN);
            const computedTop = safeNumber(String(el.style.top || '').replace('%', ''), NaN);
            const pxLeft = Number.isFinite(computedLeft) ? (rect.left + (computedLeft / 100) * rect.width) : event.clientX;
            const pxTop = Number.isFinite(computedTop) ? (rect.top + (computedTop / 100) * rect.height) : event.clientY;
            offsetPx = { x: event.clientX - pxLeft, y: event.clientY - pxTop };
          }
        });
        el.addEventListener('pointermove', (event) => {
          if (!downAt) return;
          const dx = Math.abs(event.clientX - downAt.x);
          const dy = Math.abs(event.clientY - downAt.y);
          if (!dragging && (dx + dy) > 7) dragging = true;
          if (!dragging) return;
          setFromClient(event.clientX - offsetPx.x, event.clientY - offsetPx.y);
        });
        const endDrag = (event) => {
          if (!downAt) return;
          const wasDragging = dragging;
          downAt = null;
          dragging = false;
          el.classList.remove('is-dragging');
          if (wasDragging) {
            persistPctFromClient(event.clientX - offsetPx.x, event.clientY - offsetPx.y);
            try { renderTacticsBoard(); } catch (e) {}
          }
        };
        el.addEventListener('pointerup', endDrag);
        el.addEventListener('pointercancel', endDrag);
        return el;
      };
      const renderTacticsBoardImpl = () => {
        if (!tacticsPitch || !tacticsTokensEl) return;
        const starters = Array.isArray(lineupState?.starters) ? lineupState.starters.slice(0, 11) : [];
        tacticsTokensEl.innerHTML = '';
        if (!starters.length) return;
        starters.forEach((player, idx) => {
          const token = createTacticsToken(player);
          if (!token) return;
          const x = safeNumber(player?.x_pct, NaN);
          const y = safeNumber(player?.y_pct, NaN);
          const fallback = defaultBaseSlots[idx] || defaultBaseSlots[0];
          token.style.left = `${Number.isFinite(x) ? x : fallback.x}%`;
          token.style.top = `${Number.isFinite(y) ? y : fallback.y}%`;
          token.classList.toggle('is-selected', String(selectedPlayerId || '') === String(player?.id || ''));
          tacticsTokensEl.appendChild(token);
        });
      };
      const renderRivalTacticsBoardImpl = () => {
        if (!tacticsPitch || !tacticsRivalTokensEl) return;
        const starters = Array.isArray(rivalLineupState?.starters) ? rivalLineupState.starters.slice(0, 11) : [];
        tacticsRivalTokensEl.innerHTML = '';
        if (!starters.length) {
          setRivalVisible(false, { persist: false, silent: true });
          return;
        }
        syncRivalToggleUi();
        if (!rivalVisible) return;
        starters.forEach((player, idx) => {
          const token = createRivalTacticsToken(player);
          if (!token) return;
          const x = safeNumber(player?.x_pct, NaN);
          const y = safeNumber(player?.y_pct, NaN);
          const fallback = defaultBaseSlotsRival[idx] || defaultBaseSlotsRival[0] || defaultBaseSlots[0];
          token.style.left = `${Number.isFinite(x) ? x : fallback.x}%`;
          token.style.top = `${Number.isFinite(y) ? y : fallback.y}%`;
          tacticsRivalTokensEl.appendChild(token);
        });
      };
      renderTacticsBoard = () => {
        renderTacticsBoardImpl();
        renderRivalTacticsBoardImpl();
      };
      if (tacticsResetBtn) {
        tacticsResetBtn.addEventListener('click', () => applyBasePositionsToStarters());
      }
	      const renderLineup = () => {
	        Object.keys(lineupSections).forEach(renderLineupSection);
	        refreshLineupCounts();
        const startersCount = lineupState.starters?.length || 0;
        const startersWrapper = lineupSections.starters?.wrapper;
        if (startersWrapper) {
          startersWrapper.classList.remove('is-valid', 'is-invalid');
          if (startersCount === 11) {
            startersWrapper.classList.add('is-valid');
          } else if (startersCount > 0) {
            startersWrapper.classList.add('is-invalid');
          }
        }
        if (lineupStatusMsg) {
          if (startersCount === 11) {
            lineupStatusMsg.textContent = 'Once inicial completo y listo (11/11).';
          } else {
            lineupStatusMsg.textContent = `Faltan ${Math.max(0, 11 - startersCount)} titulares para completar el once.`;
          }
        }
	        updateLineupInput();
	        refreshCardAssignments();
	        renderPreLineupSummary();
	        try { renderTacticsBoard(); } catch (e) {}
	        try { renderProQuickPlayers(); } catch (e) {}
	        if (typeof updateCloseSummary === 'function') {
	          updateCloseSummary();
	        }
	      };
      const quickHistoryState = {
        amarilla: [],
        roja: [],
        subs: [],
        corner_for: [],
        corner_against: [],
      };
      ({
        showPageStatus,
        setMatchInfoEditing,
        collectMatchInfoPayload,
        renderMatchInfoState,
        showQuickHistoryModal,
        hideQuickHistoryModal,
      } = window.initMatchActionsChrome({
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
      }));
      if (typeof renderMatchInfoState === 'function') {
        renderMatchInfoState(matchInfoState);
      }

	      const removeLineupEntry = (playerId) => {
	        let changed = false;
	        Object.keys(lineupState).forEach((sectionKey) => {
	          const originalLength = lineupState[sectionKey].length;
	          lineupState[sectionKey] = lineupState[sectionKey].filter((entry) => entry.id !== playerId);
	          if (lineupState[sectionKey].length !== originalLength) {
	            changed = true;
	          }
	        });
	        if (selectedPlayerId === playerId) {
	          clearPlayerSelection();
	        }
	        if (changed) {
	          renderLineup();
	        }
	      };
	      const findPlayerSection = (playerId) => {
	        if (!playerId) return null;
	        const id = String(playerId);
	        return (
	          Object.keys(lineupState).find((sectionKey) =>
	            (lineupState[sectionKey] || []).some((entry) => String(entry.id) === id),
	          ) || null
	        );
	      };
			      const pendingSubstitution = {
			        outPlayer: null,
			        inPlayer: null,
			        minute: null,
			        nextPick: 'out',
			      };
			      const clearPendingSubstitution = () => {
			        pendingSubstitution.outPlayer = null;
			        pendingSubstitution.inPlayer = null;
			        pendingSubstitution.minute = null;
			        pendingSubstitution.nextPick = 'out';
			      };
		      let subTapModeActive = false;
			      const renderSubTapSummary = () => {
		        if (!playerQuickSubsSummaryEl) return;
		        if (!subTapModeActive || activeStage !== 'live') {
		          playerQuickSubsSummaryEl.style.display = 'none';
		          playerQuickSubsSummaryEl.textContent = '';
		          return;
		        }
			        const outName = pendingSubstitution.outPlayer?.name ? String(pendingSubstitution.outPlayer.name).toUpperCase() : '';
			        const inName = pendingSubstitution.inPlayer?.name ? String(pendingSubstitution.inPlayer.name).toUpperCase() : '';
			        const minute = Number.isFinite(pendingSubstitution.minute) ? pendingSubstitution.minute : getCurrentMatchMinute();
			        const parts = [];
			        if (outName) parts.push(`SALE ${outName}`);
			        if (inName) parts.push(`ENTRA ${inName}`);
			        const body = parts.length
			          ? parts.join(' · ')
			          : pendingSubstitution.nextPick === 'out'
			            ? 'Toca el SALIENTE.'
			            : 'Toca el ENTRANTE.';
			        playerQuickSubsSummaryEl.textContent = `${minute}' · ${body}`;
			        playerQuickSubsSummaryEl.style.display = 'block';
			      };
			      const subsModeToggleBtn = document.getElementById('subs-mode-toggle');
			      const setSubTapMode = (enabled) => {
			        subTapModeActive = Boolean(enabled);
			        if (!subTapModeActive) {
			          clearPendingSubstitution();
			        }
			        if (playerQuickSubsToggleBtn) {
			          playerQuickSubsToggleBtn.classList.toggle('is-active', subTapModeActive);
			          playerQuickSubsToggleBtn.textContent = subTapModeActive ? '🔁 Modo cambios (activo)' : '🔁 Modo cambios';
			        }
			        if (subsModeToggleBtn) {
			          subsModeToggleBtn.classList.toggle('is-active', subTapModeActive);
			        }
			        renderSubTapSummary();
			      };
			      if (playerQuickSubsToggleBtn) {
			        playerQuickSubsToggleBtn.addEventListener('click', () => {
			          if (activeStage !== 'live') {
			            showPageStatus('Las sustituciones se registran en vivo.', 'warning', 3200);
			            return;
			          }
			          setSubTapMode(!subTapModeActive);
			          if (subTapModeActive) {
			            showPageStatus('Modo cambios activo: toca SALIENTE y luego ENTRANTE.', 'info', 3600);
			          }
			        });
			      }
				      if (subsModeToggleBtn) {
				        subsModeToggleBtn.addEventListener('click', () => {
				          if (activeStage !== 'live') {
				            showPageStatus('Las sustituciones se registran en vivo.', 'warning', 3200);
				            return;
				          }
				          setSubTapMode(!subTapModeActive);
				          if (subTapModeActive) {
				            showPageStatus('Modo cambios activo: toca SALIENTE y luego ENTRANTE.', 'info', 3600);
				          } else {
				            showPageStatus('Modo cambios desactivado.', 'info', 1800);
				          }
			        });
			      }
		      const commitPendingSubstitution = async () => {
		        if (!pendingSubstitution.outPlayer?.id || !pendingSubstitution.inPlayer?.id) return;
		        if (String(pendingSubstitution.outPlayer.id) === String(pendingSubstitution.inPlayer.id)) {
		          clearPendingSubstitution();
		          return;
		        }
	        const minute = Number.isFinite(pendingSubstitution.minute)
	          ? pendingSubstitution.minute
	          : getCurrentMatchMinute();
	        const applySubstitutionToLineupState = ({ outPlayer, inPlayer }) => {
	          try {
	            const outId = String(outPlayer?.id || '').trim();
	            const inId = String(inPlayer?.id || '').trim();
	            if (!outId || !inId) return;
	            lineupState = lineupState && typeof lineupState === 'object' ? lineupState : { starters: [], bench: [] };
	            if (!Array.isArray(lineupState.starters)) lineupState.starters = [];
	            if (!Array.isArray(lineupState.bench)) lineupState.bench = [];
	            const starters = [...lineupState.starters];
	            const bench = [...lineupState.bench];
	            const outIdx = starters.findIndex((row) => String(row?.id || '') === outId);
	            const outgoing = outIdx >= 0 ? starters[outIdx] : null;
	            const cleanedStarters = starters.filter((row) => {
	              const rid = String(row?.id || '');
	              return rid && rid !== outId && rid !== inId;
	            });
	            const insertIndex = outIdx >= 0 ? Math.max(0, Math.min(outIdx, cleanedStarters.length)) : cleanedStarters.length;
	            const incomingRow = {
	              ...inPlayer,
	            };
	            if (outgoing && typeof outgoing === 'object') {
	              if (outgoing.slot_index !== undefined) incomingRow.slot_index = outgoing.slot_index;
	              if (outgoing.x_pct !== undefined && outgoing.y_pct !== undefined) {
	                incomingRow.x_pct = outgoing.x_pct;
	                incomingRow.y_pct = outgoing.y_pct;
	              }
	            }
	            cleanedStarters.splice(insertIndex, 0, incomingRow);
	            lineupState.starters = cleanedStarters.slice(0, startersLimit);

	            const cleanedBench = bench.filter((row) => {
	              const rid = String(row?.id || '');
	              return rid && rid !== outId && rid !== inId;
	            });
	            // El saliente pasa al banquillo (si no estaba ya).
	            cleanedBench.unshift(outgoing || outPlayer);
	            // Dedup
	            const seen = new Set();
	            lineupState.bench = cleanedBench.filter((row) => {
	              const rid = String(row?.id || '');
	              if (!rid || seen.has(rid)) return false;
	              seen.add(rid);
	              return true;
	            });
	            try { renderLineup(); } catch (e) {}
	          } catch (e) {}
	        };
	        try {
	          showPageStatus(`Registrando cambio (${minute}')...`, 'info', 1800);
	          const ok = await liveController?.registerSubstitutionPair?.({
	            outPlayer: pendingSubstitution.outPlayer,
	            inPlayer: pendingSubstitution.inPlayer,
	            minute,
	          });
	          if (!ok) {
	            showPageStatus('No se pudo registrar el cambio. Usa la tarjeta de Sustituciones.', 'warning', 5200);
	            return;
	          }
	          // Mantiene el "en campo" actualizado para auto-jugador por zona.
	          applySubstitutionToLineupState({
	            outPlayer: pendingSubstitution.outPlayer,
	            inPlayer: pendingSubstitution.inPlayer,
	          });
		          showPageStatus(
		            `Cambio registrado · ${pendingSubstitution.outPlayer.name || 'Sale'} → ${pendingSubstitution.inPlayer.name || 'Entra'} · ${minute}'`,
		            'success',
		            3200,
		          );
		          clearPendingSubstitution();
		          renderSubTapSummary();
		        } catch (err) {
		          console.error(err);
		          showPageStatus('Error registrando el cambio por arrastre.', 'warning', 5200);
		        }
		      };
	      let activeStage = document.querySelector('[data-stage-tab].is-active')?.dataset.stageTab || 'live';
	      const findPlayerPayload = (playerId) => {
	        const id = String(playerId || '').trim();
	        if (!id) return null;
	        const card = Array.from(convocationCards).find((item) => String(item.dataset.playerId) === id);
	        if (card) {
	          return {
	            id: card.dataset.playerId,
	            name: card.dataset.playerName || '',
	            number: card.dataset.playerNumber || '',
	            photo: card.dataset.playerPhoto || '',
	            position: card.dataset.playerPosition || '',
	          };
	        }
	        const fallback = [...(lineupState.starters || []), ...(lineupState.bench || [])].find(
	          (entry) => String(entry.id) === id,
	        );
	        return fallback || null;
	      };
	      const roleBucketFromPosition = (positionRaw) => {
	        const pos = String(positionRaw || '').trim().toLowerCase();
	        if (!pos) return 'any';
	        const compact = pos.replace(/\s+/g, '');
	        if (compact.includes('por') || compact.includes('portero') || compact === 'gk') return 'gk';
	        if (
	          compact.includes('def')
	          || compact.includes('central')
	          || compact.includes('lateral')
	          || compact.includes('carril')
	          || compact.includes('cb')
	          || compact.includes('lb')
	          || compact.includes('rb')
	        ) return 'def';
	        if (
	          compact.includes('mc')
	          || compact.includes('mcd')
	          || compact.includes('mco')
	          || compact.includes('medio')
	          || compact.includes('interior')
	          || compact.includes('piv')
	          || compact.includes('mp')
	          || compact.includes('cm')
	        ) return 'mid';
	        if (
	          compact.includes('del')
	          || compact.includes('ext')
	          || compact.includes('ei')
	          || compact.includes('ed')
	          || compact.includes('punta')
	          || compact === 'dc'
	          || compact.includes('st')
	          || compact.includes('fw')
	        ) return 'att';
	        return 'any';
	      };
	      const tercioFromZoneLabel = (zoneLabelText) => {
	        const normalized = String(zoneLabelText || '').toLowerCase();
	        if (!normalized) return '';
	        if (normalized.includes('porter')) return 'def';
	        if (normalized.includes('defensa')) return 'def';
	        if (normalized.includes('medio')) return 'mid';
	        if (normalized.includes('ataque')) return 'att';
	        return '';
	      };
	      const scorePlayerForTap = ({ player, tapX, tapY, tercioKey }) => {
	        const x = Number(player?.x_pct);
	        const y = Number(player?.y_pct);
	        const hasXY = Number.isFinite(x) && Number.isFinite(y);
	        const dx = hasXY ? (x - tapX) : 0;
	        const dy = hasXY ? (y - tapY) : 0;
	        const distance = hasXY ? Math.sqrt((dx * dx) + (dy * dy)) : 999;
	        const bucket = roleBucketFromPosition(player?.position);
	        let bias = 0;
	        if (tercioKey === 'def') {
	          if (bucket === 'def') bias += 7;
	          else if (bucket === 'mid') bias += 4;
	          else if (bucket === 'gk') bias += 6;
	          else if (bucket === 'att') bias -= 2;
	        } else if (tercioKey === 'mid') {
	          if (bucket === 'mid') bias += 7;
	          else if (bucket === 'def') bias += 3;
	          else if (bucket === 'att') bias += 3;
	          else if (bucket === 'gk') bias -= 6;
	        } else if (tercioKey === 'att') {
	          if (bucket === 'att') bias += 7;
	          else if (bucket === 'mid') bias += 4;
	          else if (bucket === 'def') bias -= 2;
	          else if (bucket === 'gk') bias -= 10;
	        } else {
	          if (bucket === 'gk') bias -= 6;
	        }
	        // La cercanía pesa más que el rol, pero el rol ayuda cuando hay varios jugadores en la zona.
	        const score = (-distance * 1.0) + (bias * 1.2);
	        return { score, distance, bucket, hasXY };
	      };
	      const renderAutoPlayerSuggestions = (candidates) => {
	        if (!autoPlayerRow || !autoPlayerChips) return;
	        const list = Array.isArray(candidates) ? candidates.slice(0, 5) : [];
	        if (!list.length) {
	          autoPlayerRow.hidden = true;
	          autoPlayerChips.innerHTML = '';
	          return;
	        }
	        autoPlayerRow.hidden = false;
	        autoPlayerChips.innerHTML = '';
	        list.forEach((item) => {
	          const payload = item?.player;
	          if (!payload?.id) return;
	          const btn = document.createElement('button');
	          btn.type = 'button';
	          btn.className = 'auto-player-chip';
	          const numberLabel = payload.number ? `#${payload.number}` : '#--';
	          const name = String(payload.name || 'Jugador').toUpperCase();
	          const role = String(item.bucket || '').toUpperCase();
	          btn.textContent = `${numberLabel} ${name}`;
	          if (role) {
	            const small = document.createElement('small');
	            small.textContent = role;
	            btn.appendChild(small);
	          }
	          btn.addEventListener('click', () => {
	            nextPlayerPickSource = 'manual';
	            selectPlayer(String(payload.id));
	          });
	          autoPlayerChips.appendChild(btn);
	        });
	      };
	      const handleAutoPlayerForTap = ({ x_pct, y_pct, zone }) => {
	        const tapX = Number(x_pct);
	        const tapY = Number(y_pct);
	        if (!Number.isFinite(tapX) || !Number.isFinite(tapY)) return;
	        const tercioKey = tercioFromZoneLabel(zone);
	        const starters = Array.isArray(lineupState?.starters) ? lineupState.starters : [];
	        const onField = starters.filter((row) => row && row.id);
	        if (!onField.length) {
	          renderAutoPlayerSuggestions([]);
	          return;
	        }
	        const scored = onField.map((player) => {
	          const meta = scorePlayerForTap({ player, tapX, tapY, tercioKey });
	          return { ...meta, player };
	        });
	        scored.sort((a, b) => (b.score - a.score));
	        const best = scored[0];
	        const second = scored[1];
	        renderAutoPlayerSuggestions(scored);
	        if (!autoPlayerEnabled) return;
	        if (!best?.player?.id) return;
	        // Si el usuario acaba de elegir manualmente, respetamos unos segundos.
	        const sincePick = Date.now() - (Number(lastPlayerPickAt) || 0);
	        const justManual = lastPlayerPickSource === 'manual' && sincePick < 4500;
	        if (justManual) return;
	        // Confianza: muy cerca, o diferencia clara con el segundo.
	        const bestDist = Number(best.distance) || 999;
	        const secondDist = Number(second?.distance) || 999;
	        const confident = (bestDist <= 10) || ((secondDist - bestDist) >= 8) || (best.hasXY && !second?.hasXY);
	        if (!confident) return;
	        nextPlayerPickSource = 'auto';
	        selectPlayer(String(best.player.id));
	      };
		      updatePlayerQuickPanel = () => {
		        if (!playerQuickBlock) return;
		        const shouldShow = activeStage === 'live' && Boolean(selectedPlayerId);
		        playerQuickBlock.classList.toggle('is-visible', shouldShow);
		        if (!shouldShow) return;
		        const payload = findPlayerPayload(selectedPlayerId);
		        const number = payload?.number ? `#${payload.number}` : '#--';
		        const name = String(payload?.name || 'Jugador').toUpperCase();
		        if (playerQuickNameEl) {
		          playerQuickNameEl.textContent = `${number} ${name}`;
		        }
		        if (activeStage !== 'live') {
		          setSubTapMode(false);
		        } else {
		          renderSubTapSummary();
		        }
		      };
		      if (playerQuickClearBtn) {
		        playerQuickClearBtn.addEventListener('click', () => clearPlayerSelection());
		      }
			      const onLineupCrossMove = (fromSection, toSection, player) => {
			        if (activeStage !== 'live') return;
			        if (!fromSection || fromSection === toSection) return;
	        const safeMinute = getCurrentMatchMinute();
	        if (!Number.isFinite(pendingSubstitution.minute)) {
	          pendingSubstitution.minute = safeMinute;
	        }
		        if (fromSection === 'starters' && toSection === 'bench') {
		          pendingSubstitution.outPlayer = player;
		          pendingSubstitution.nextPick = 'in';
		          showPageStatus(`Cambio: SALE ${String(player.name || 'Jugador').toUpperCase()} · ahora arrastra el ENTRANTE al once.`, 'info', 3600);
		        } else if (fromSection === 'bench' && toSection === 'starters') {
		          pendingSubstitution.inPlayer = player;
		          pendingSubstitution.nextPick = 'out';
		          showPageStatus(`Cambio: ENTRA ${String(player.name || 'Jugador').toUpperCase()} · completa la SALIDA si falta.`, 'info', 3600);
		        } else {
		          return;
		        }
		        if (pendingSubstitution.outPlayer?.id && pendingSubstitution.inPlayer?.id) {
		          void commitPendingSubstitution();
		        }
		      };
			      function maybeHandleTapSubstitution(playerId) {
			        if (!subTapModeActive) return;
			        if (activeStage !== 'live') return;
			        const player = findPlayerPayload(playerId);
			        if (!player?.id) return;
			        const safeMinute = getCurrentMatchMinute();
			        if (!Number.isFinite(pendingSubstitution.minute)) {
			          pendingSubstitution.minute = safeMinute;
			        }
			        const upperName = String(player.name || 'Jugador').toUpperCase();
			        if (pendingSubstitution.nextPick === 'out') {
			          pendingSubstitution.outPlayer = player;
			          pendingSubstitution.nextPick = 'in';
			          showPageStatus(`Cambio: SALE ${upperName} · ahora toca el ENTRANTE.`, 'info', 3600);
			        } else {
			          pendingSubstitution.inPlayer = player;
			          pendingSubstitution.nextPick = 'out';
			          showPageStatus(`Cambio: ENTRA ${upperName} · registrando...`, 'info', 1800);
			        }
			        renderSubTapSummary();
			        if (pendingSubstitution.outPlayer?.id && pendingSubstitution.inPlayer?.id) {
			          void commitPendingSubstitution();
			        }
			      }
	      const addPlayerToSection = (sectionKey, player) => {
	        const section = lineupSections[sectionKey];
	        if (!section || !player?.id) {
	          return;
	        }
	        if (section.limit && lineupState[sectionKey].length >= section.limit) {
	          return;
	        }
	        const previousSection = findPlayerSection(player.id);
	        removeLineupEntry(player.id);
	        lineupState[sectionKey].push(player);
	        renderLineup();
	        selectPlayer(player.id);
	        onLineupCrossMove(previousSection, sectionKey, player);
	      };
      const normalizePositionText = (value) => String(value || '').trim().toLowerCase();
      const playerPositionRank = (player) => {
        const pos = normalizePositionText(player.position || '');
        if (pos.includes('portero')) return 0;
        if (pos.includes('defen')) return 1;
        if (pos.includes('medio') || pos.includes('centro') || pos.includes('interior') || pos.includes('pivote')) return 2;
        if (pos.includes('extremo') || pos.includes('delanter') || pos.includes('punta')) return 3;
        return 9;
      };
      const parsePlayerNumber = (value) => {
        const parsed = parseInt(String(value || '').replace(/[^\d]/g, ''), 10);
        return Number.isFinite(parsed) ? parsed : 999;
      };
      const getConvocationPlayerPool = () => {
        return Array.from(convocationCards).map((card) => ({
          id: card.dataset.playerId,
          name: card.dataset.playerName,
          number: card.dataset.playerNumber,
          photo: card.dataset.playerPhoto || '',
          position: card.dataset.playerPosition || '',
        }));
      };
      const autoPickStarters = () => {
        const pool = getConvocationPlayerPool();
        if (!pool.length) return;
        const sorted = [...pool].sort((a, b) => {
          const byRank = playerPositionRank(a) - playerPositionRank(b);
          if (byRank !== 0) return byRank;
          return parsePlayerNumber(a.number) - parsePlayerNumber(b.number);
        });
        const keeper = sorted.find((p) => playerPositionRank(p) === 0);
        const starters = [];
        if (keeper) {
          starters.push(keeper);
        }
        for (const player of sorted) {
          if (starters.length >= 11) break;
          if (starters.some((entry) => String(entry.id) === String(player.id))) continue;
          starters.push(player);
        }
        lineupState.starters = starters.slice(0, 11);
        lineupState.bench = pool.filter(
          (player) => !lineupState.starters.some((starter) => String(starter.id) === String(player.id)),
        );
        renderLineup();
      };
      const fillBenchFromRemaining = () => {
        const pool = getConvocationPlayerPool();
        const starters = lineupState.starters || [];
        lineupState.bench = pool.filter(
          (player) => !starters.some((starter) => String(starter.id) === String(player.id)),
        );
        renderLineup();
      };
      const clearLineupState = () => {
        lineupState = { starters: [], bench: [] };
        clearPlayerSelection();
        renderLineup();
      };
		      hydrateLineupState();
		      renderLineup();
		      try { restoreProState(); } catch (e) {}
	      // Mantiene registro de acciones sincronizado con el 11 inicial (si se edita desde otra pantalla).
	      try {
	        window.addEventListener('focus', () => { void refreshLineupFromServer({ quiet: true }); });
	        document.addEventListener('visibilitychange', () => {
	          if (!document.hidden) void refreshLineupFromServer({ quiet: true });
	        });
	        window.setTimeout(() => { void refreshLineupFromServer({ quiet: true }); }, 1200);
	      } catch (e) {}
	      if (lineupAutoPickBtn) {
	        lineupAutoPickBtn.addEventListener('click', autoPickStarters);
	      }
      if (lineupFillBenchBtn) {
        lineupFillBenchBtn.addEventListener('click', fillBenchFromRemaining);
      }
      if (lineupClearBtn) {
        lineupClearBtn.addEventListener('click', clearLineupState);
      }
	      convocationCards.forEach((card) => {
	        card.setAttribute('draggable', 'true');
	        card.addEventListener('dragstart', (event) => {
	          try { document.body.classList.add('is-dragging'); } catch (e) {}
	          event.dataTransfer?.setData(
	            'text/plain',
	            JSON.stringify({
	              id: card.dataset.playerId,
              name: card.dataset.playerName,
              number: card.dataset.playerNumber,
              photo: card.dataset.playerPhoto || '',
              position: card.dataset.playerPosition || '',
	            }),
	          );
	        });
	        card.addEventListener('dragend', () => {
	          try { document.body.classList.remove('is-dragging'); } catch (e) {}
	        });
	        card.addEventListener('click', () => {
	          nextPlayerPickSource = 'manual';
	          selectPlayer(card.dataset.playerId);
	        });
	      });
	      // Auto-scroll durante arrastres (útil en iPad/webview): evita sensación de pantalla "bloqueada".
	      (() => {
	        let lastScrollAt = 0;
	        document.addEventListener('dragover', (event) => {
	          if (!document.body.classList.contains('is-dragging')) return;
	          const now = Date.now();
	          if (now - lastScrollAt < 32) return;
	          lastScrollAt = now;
	          const y = event.clientY || 0;
	          const h = window.innerHeight || 0;
	          const edge = 84;
	          const speed = 18;
	          if (y < edge) window.scrollBy({ top: -speed, left: 0 });
	          else if (h && y > (h - edge)) window.scrollBy({ top: speed, left: 0 });
	        }, { passive: true });
	        document.addEventListener('drop', () => {
	          try { document.body.classList.remove('is-dragging'); } catch (e) {}
	        }, true);
	      })();
	      Object.keys(lineupSections).forEach((sectionKey) => {
	        const section = lineupSections[sectionKey];
	        const container = section?.element;
	        if (!container) {
	          return;
	        }
	        // Tap-to-add/move: en iPad es más fiable que el drag nativo.
	        container.addEventListener('click', (event) => {
	          if (event.target?.closest?.('.lineup-chip')) return;
	          if (!selectedPlayerId) return;
	          const payload = findPlayerPayload(selectedPlayerId);
	          if (!payload?.id) return;
	          addPlayerToSection(sectionKey, payload);
	        });
	        container.addEventListener('dragover', (event) => {
	          event.preventDefault();
	          container.classList.add('is-drag-over');
	        });
        container.addEventListener('dragleave', () => {
          container.classList.remove('is-drag-over');
        });
        container.addEventListener('drop', (event) => {
          event.preventDefault();
          container.classList.remove('is-drag-over');
          const payload = event.dataTransfer?.getData('text/plain');
          if (!payload) {
            return;
          }
          try {
            const player = JSON.parse(payload);
            addPlayerToSection(sectionKey, player);
          } catch (err) {
            console.error('Invalid lineup drop', err);
          }
        });
        container.addEventListener('dblclick', (event) => {
          const target = event.target.closest('.lineup-chip');
          if (!target) {
            return;
          }
          removeLineupEntry(target.dataset.playerId);
        });
      });

      const getCurrentMatchMinute = () => Math.floor(elapsedRef.value / 60);
      const computeTercioFromZone = (zoneLabelText) => {
        const normalized = (zoneLabelText || '').toLowerCase();
        if (!normalized) return '';
        if (normalized.includes('porter')) return 'Defensa';
        if (normalized.includes('defensa')) return 'Defensa';
        if (normalized.includes('medio')) return 'Construcción';
        if (normalized.includes('ataque')) return 'Ataque';
        return '';
      };
      const syncAutoFields = ({ zone = zoneInput?.value || '' } = {}) => {
        const minute = getCurrentMatchMinute();
        if (minuteInput) {
          minuteInput.value = minute;
        }
        if (minuteDisplay) {
          minuteDisplay.textContent = `${minute}'`;
        }
        const tercio = computeTercioFromZone(zone);
        if (tercioInput) {
          tercioInput.value = tercio;
        }
        if (tercioDisplay) {
          tercioDisplay.textContent = tercio || 'Se calcula por zona';
        }
      };
      const stageTabs = document.querySelectorAll('[data-stage-tab]');
      const stagePanels = document.querySelectorAll('[data-stage-panel]');
      const stageJumpButtons = document.querySelectorAll('[data-stage-jump]');
      const closeSummaryOpponent = document.getElementById('close-summary-opponent');
      const closeSummaryMeta = document.getElementById('close-summary-meta');
      const closeSummaryScore = document.getElementById('close-summary-score');
      const closeSummaryLineup = document.getElementById('close-summary-lineup');
      const closeSummaryLineupNote = document.getElementById('close-summary-lineup-note');
      const closeSummaryActions = document.getElementById('close-summary-actions');
      const closeSummaryBreakdown = document.getElementById('close-summary-breakdown');
      const closeSummaryClock = document.getElementById('close-summary-clock');
      const closeSummaryCorners = document.getElementById('close-summary-corners');
      const closeSummaryAlerts = document.getElementById('close-summary-alerts');
	      const closeFinalizeBtn = document.getElementById('match-finalize-btn');
      const copyBriefingBtn = document.getElementById('match-copy-briefing');
      let liveSummaryState = {
        actions: 0,
        yellow: 0,
        red: 0,
        subs: 0,
        cornerFor: 0,
        cornerAgainst: 0,
        elapsedSeconds: 0,
        matchInfo: { ...matchInfoState },
      };
      const copyTextToClipboard = async (text) => {
        const value = String(text || '').trim();
        if (!value) return false;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(value);
            return true;
          }
        } catch (e) {}
        try {
          const ta = document.createElement('textarea');
          ta.value = value;
          ta.setAttribute('readonly', 'readonly');
          ta.style.position = 'fixed';
          ta.style.left = '-9999px';
          document.body.appendChild(ta);
          ta.select();
          const ok = document.execCommand('copy');
          document.body.removeChild(ta);
          return Boolean(ok);
        } catch (e) {}
        return false;
      };
      const formatSummaryClock = (seconds) => {
        const safeSeconds = Math.max(0, Number(seconds) || 0);
        const minutes = Math.floor(safeSeconds / 60);
        const secs = safeSeconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      };
      updateCloseSummary = (nextSummary = {}) => {
        liveSummaryState = {
          ...liveSummaryState,
          ...nextSummary,
          matchInfo: {
            ...liveSummaryState.matchInfo,
            ...(nextSummary.matchInfo || {}),
          },
        };
        const summaryInfo = liveSummaryState.matchInfo || {};
        const startersCount = lineupState.starters?.length || 0;
        const benchCount = lineupState.bench?.length || 0;
        const requiredStarters = startersLimit;
        if (closeSummaryOpponent) {
          closeSummaryOpponent.textContent = summaryInfo.opponent || '-';
        }
        if (closeSummaryMeta) {
          const metaBits = [
            summaryInfo.location || '-',
            summaryInfo.datetime || '-',
            summaryInfo.round ? `Jornada ${summaryInfo.round}` : '',
          ].filter(Boolean);
          closeSummaryMeta.textContent = metaBits.join(' · ');
        }
        if (closeSummaryScore) {
          const forValue = String(summaryInfo.score_for || '').trim();
          const againstValue = String(summaryInfo.score_against || '').trim();
          if (!forValue && !againstValue) {
            closeSummaryScore.textContent = 'Marcador final: —';
          } else {
            closeSummaryScore.textContent = `Marcador final: ${forValue || '—'} - ${againstValue || '—'}`;
          }
        }
        if (closeSummaryLineup) {
          closeSummaryLineup.textContent = `${startersCount}/${requiredStarters}`;
        }
        if (closeSummaryLineupNote) {
          closeSummaryLineupNote.textContent = startersCount === requiredStarters
            ? `Once listo · ${benchCount} suplentes disponibles.`
            : `Faltan ${Math.max(0, requiredStarters - startersCount)} titulares para completar el once.`;
        }
        if (closeSummaryActions) {
          closeSummaryActions.textContent = String(liveSummaryState.actions || 0);
        }
        if (closeSummaryBreakdown) {
          closeSummaryBreakdown.textContent = `${liveSummaryState.yellow || 0} amarillas · ${liveSummaryState.red || 0} rojas · ${liveSummaryState.subs || 0} sustituciones`;
        }
        if (closeSummaryClock) {
          closeSummaryClock.textContent = formatSummaryClock(liveSummaryState.elapsedSeconds);
        }
        if (closeSummaryCorners) {
          closeSummaryCorners.textContent = `${liveSummaryState.cornerFor || 0} córners a favor · ${liveSummaryState.cornerAgainst || 0} en contra`;
        }
	        if (closeSummaryAlerts) {
	          const alerts = [];
          const forValue = String(summaryInfo.score_for || '').trim();
          const againstValue = String(summaryInfo.score_against || '').trim();
          if (!summaryInfo.opponent) {
            alerts.push('Falta definir el rival.');
          }
          if (!forValue && !againstValue) {
            alerts.push('Falta definir el marcador final.');
          }
          if (startersCount < requiredStarters) {
            alerts.push('El once inicial no está completo.');
          }
          if (!(liveSummaryState.actions > 0)) alerts.push('Todavía no hay acciones registradas en vivo.');
          if (!(liveSummaryState.elapsedSeconds > 0)) alerts.push('El cronómetro sigue en cero.');
          closeSummaryAlerts.innerHTML = '';
          const alertItems = alerts.length ? alerts : ['Todo listo para guardar el partido.'];
	          alertItems.forEach((message) => {
	            const item = document.createElement('li');
	            item.textContent = message;
	            closeSummaryAlerts.appendChild(item);
	          });
	          const warningTitle = alerts.length ? alerts.join(' ') : 'Guardar partido';
	          matchFinalizeBtn.forEach((button) => {
	            // No bloqueamos el cierre: el staff puede querer consolidar acciones aunque falten datos.
	            // La confirmación/validación se hace en servidor o con avisos en la UI.
	            button.title = warningTitle;
	          });
	        }
	      };
	      const activateStage = (stage) => {
	        activeStage = stage;
	        stageTabs.forEach((tab) => {
	          tab.classList.toggle('is-active', tab.dataset.stageTab === stage);
	        });
	        stagePanels.forEach((panel) => {
	          panel.classList.toggle('is-active', panel.dataset.stagePanel === stage);
	        });
	        if (stage !== 'live') {
	          setSubTapMode(false);
	        }
	        updatePlayerQuickPanel();
	      };
      stageTabs.forEach((tab) => {
        tab.addEventListener('click', () => activateStage(tab.dataset.stageTab));
      });
	      stageJumpButtons.forEach((button) => {
	        button.addEventListener('click', () => activateStage(button.dataset.stageJump));
	      });
	      // Inicializa el estado del cierre (deshabilita Guardar si falta rival/marcador/11).
	      requestAnimationFrame(() => updateCloseSummary({ matchInfo: { ...matchInfoState } }));
      if (copyBriefingBtn && copyBriefingBtn.dataset.bound !== '1') {
        copyBriefingBtn.addEventListener('click', async () => {
          const info = liveSummaryState.matchInfo || {};
          const opponent = String(info.opponent || '').trim() || 'Rival';
          const context = String(info.context || 'league').toLowerCase();
          const ctxLabel = context === 'tournament' ? (String(info.tournament_name || '').trim() || 'Torneo')
            : context === 'friendly' ? 'Amistoso'
            : 'Liga';
          const roundLabel = String(info.round || '').trim() ? `J${String(info.round || '').trim()}` : '';
          const scoreFor = String(info.score_for || '').trim() || '—';
          const scoreAgainst = String(info.score_against || '').trim() || '—';
          const metaBits = [];
          if (String(info.datetime || '').trim()) metaBits.push(String(info.datetime || '').trim());
          if (String(info.location || '').trim()) metaBits.push(String(info.location || '').trim());
          const hud = liveHudSnapshot;
          const lines = [];
          lines.push(`Resumen · ${teamName} vs ${opponent}${roundLabel ? ` · ${roundLabel}` : ''} · ${ctxLabel}`);
          if (metaBits.length) lines.push(metaBits.join(' · '));
          lines.push(`Marcador: ${scoreFor} - ${scoreAgainst}`);
          if (hud && hud.totals) {
            const t = hud.totals;
            const ex = hud.extra || {};
            lines.push(
              `Acciones: ${t.actions} · Tiros: ${t.shotsTarget}/${t.shots} A/P · Pase: ${ex.passAcc ?? 0}% · Duelos: ${t.duelsWon}/${t.duels} (${ex.duelRate ?? 0}%) · Pérd salida: ${t.lossesDef} · Recup altas: ${t.stealsHigh} · ABP: ${t.abp}`
            );
            if (String(hud.alerts || '').trim() && hud.alerts !== '—') lines.push(`Alertas: ${hud.alerts}`);
          }
          const ok = await copyTextToClipboard(lines.filter(Boolean).join('\n'));
          if (ok) {
            showPageStatus && showPageStatus('Resumen copiado al portapapeles.', 'success', 2600);
          } else {
            showPageStatus && showPageStatus('No se pudo copiar (iOS). Mantén pulsado para copiar manualmente.', 'warning', 4800);
          }
        });
        copyBriefingBtn.dataset.bound = '1';
      }
	      if (matchInfoSaveBtn) {
	        matchInfoSaveBtn.addEventListener('click', () => {
	          requestAnimationFrame(() => updateCloseSummary({ matchInfo: { ...matchInfoState } }));
	        });
	      }
      if (matchInfoResetBtn) {
        matchInfoResetBtn.addEventListener('click', () => {
          requestAnimationFrame(() => updateCloseSummary({ matchInfo: { ...matchInfoState } }));
        });
      }
	      const liveController = window.initMatchActionsLive({
	        quickHistoryState,
	        matchHalfMinutes: Number(boot.matchHalfMinutes || 45),
	        quickHistoryModal,
	        quickHistoryModalList,
	        quickHistoryModalTitle,
	        subsHistoryCard,
        showQuickHistoryModal,
        hideQuickHistoryModal,
        historyList,
        liveEventStore,
        refreshLiveStatsHud: scheduleRefreshLiveStatsHud,
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
        registerLiveEvent,
        removeLiveEvent,
        analysisVideoClipUrlTemplate,
        lastVideoClipBtn,
        onFieldTap: handleAutoPlayerForTap,
	        onSummaryChange: updateCloseSummary,
	      });

        // Replay (vídeo) integrado: carga el/los vídeos vinculados al partido y permite saltar al último momento.
        (function () {
          if (!matchVideoModal || !videoPanelToggleBtn || !matchVideoEl || !matchVideoAngleSelect) return;
          const lastVideoKey = currentMatchId ? `webstats:live:last_video_time:v1:${currentMatchId}` : '';
          let links = [];
          let activeLink = null;
          let lastSeek = null;
          let lastElapsedMs = 0;

          const setVideoStatus = (text) => {
            if (matchVideoStatusEl) matchVideoStatusEl.textContent = String(text || '').trim();
          };

          const open = async () => {
            try { matchVideoModal.hidden = false; } catch (e) {}
            await refreshLinks();
          };
          const close = () => {
            try { matchVideoModal.hidden = true; } catch (e) {}
          };
          matchVideoCloseBtn?.addEventListener('click', close);
          matchVideoModal.addEventListener('click', (ev) => {
            const card = matchVideoModal.querySelector('.match-video-card');
            if (card && ev.target && card.contains(ev.target)) return;
            close();
          });
          videoPanelToggleBtn.addEventListener('click', open);

          const renderAngles = () => {
            const options = (Array.isArray(links) ? links : []).map((l) => {
              const label = `${l.is_active ? '⭐ ' : ''}${l.title || 'Vídeo'}`;
              return `<option value="${String(l.id)}">${label}</option>`;
            }).join('');
            matchVideoAngleSelect.innerHTML = options || '<option value="">Sin vídeos</option>';
            if (activeLink) {
              matchVideoAngleSelect.value = String(activeLink.id);
            }
          };

          const setSource = async (link, { keepTime = true } = {}) => {
            if (!link || !matchVideoSrcEl) return;
            const url = String(link.video_url || '').trim();
            if (!url) return;
            if (keepTime) {
              try {
                const nowS = Number(matchVideoEl.currentTime) || 0;
                const prevKickoff = Number(activeLink?.kickoff_video_ms) || 0;
                lastElapsedMs = Math.max(0, Math.round(nowS * 1000) - prevKickoff);
              } catch (e) { /* ignore */ }
              try {
                const nextKickoff = Number(link.kickoff_video_ms) || 0;
                lastSeek = (nextKickoff + (Number(lastElapsedMs) || 0)) / 1000.0;
              } catch (e) { lastSeek = null; }
            } else {
              lastSeek = null;
            }
            activeLink = link;
            matchVideoSrcEl.setAttribute('src', url);
            try { matchVideoEl.load(); } catch (e) {}
            setVideoStatus(`Vídeo: ${link.title || '—'} · kickoff ${Math.round((Number(link.kickoff_video_ms)||0)/1000)}s`);
            try {
              if (matchVideoOpenStudioBtn && analysisVideoStudioUrlTemplate) {
                const base = String(analysisVideoStudioUrlTemplate || '').replace('/0/', `/${Number(link.video_id) || 0}/`);
                const u = new URL(base, window.location.href);
                if (currentMatchId) u.searchParams.set('collection', `Match ${currentMatchId}`);
                matchVideoOpenStudioBtn.setAttribute('href', u.toString());
              }
            } catch (e) { /* ignore */ }
          };

          matchVideoEl.addEventListener('loadedmetadata', () => {
            if (lastSeek != null) {
              try { matchVideoEl.currentTime = Math.max(0, Number(lastSeek) || 0); } catch (e) {}
              lastSeek = null;
            }
          });

          matchVideoAngleSelect.addEventListener('change', async () => {
            const id = Number(matchVideoAngleSelect.value) || 0;
            const link = links.find((l) => Number(l.id) === id) || null;
            if (!link) return;
            await setSource(link, { keepTime: true });
          });

          const refreshLinks = async () => {
            if (!matchVideoLinksApiUrl) return;
            matchVideoAngleSelect.innerHTML = '<option value="">Cargando…</option>';
            try {
              const resp = await fetch(matchVideoLinksApiUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
              const data = await resp.json().catch(() => ({}));
              if (!resp.ok || !data?.ok) {
                setVideoStatus(data?.error || 'No se pudo cargar vídeos vinculados.');
                links = [];
                activeLink = null;
                renderAngles();
                return;
              }
              links = Array.isArray(data.links) ? data.links : [];
              activeLink = links.find((l) => !!l.is_active) || links[0] || null;
              renderAngles();
              if (activeLink) {
                await setSource(activeLink, { keepTime: false });
              } else {
                setVideoStatus('No hay vídeo vinculado. Abre el editor del partido y añade “Vincular vídeo”.');
              }
            } catch (e) {
              setVideoStatus('Error cargando vídeos.');
            }
          };

          const readLastVideoTimeMs = () => {
            if (!lastVideoKey) return 0;
            try {
              const raw = window.localStorage.getItem(lastVideoKey) || '';
              const obj = JSON.parse(raw);
              const t = Number(obj?.time_ms) || 0;
              return t > 0 ? t : 0;
            } catch (e) {
              return 0;
            }
          };
          const readLastVideoAnchor = () => {
            if (!lastVideoKey) return { time_ms: 0, elapsed_ms: 0, kickoff_video_ms: 0, video_id: 0 };
            try {
              const raw = window.localStorage.getItem(lastVideoKey) || '';
              const obj = JSON.parse(raw);
              return {
                time_ms: Number(obj?.time_ms) || 0,
                elapsed_ms: Number(obj?.elapsed_ms) || 0,
                kickoff_video_ms: Number(obj?.kickoff_video_ms) || 0,
                video_id: Number(obj?.video_id) || 0,
              };
            } catch (e) {
              return { time_ms: 0, elapsed_ms: 0, kickoff_video_ms: 0, video_id: 0 };
            }
          };

          const computeTimeMsForLink = (link, { elapsedMs = 0, fallbackTimeMs = 0 } = {}) => {
            const elapsed = Number(elapsedMs) || 0;
            const kickoff = Number(link?.kickoff_video_ms) || 0;
            if (elapsed > 0) return Math.max(0, kickoff + elapsed);
            return Math.max(0, Number(fallbackTimeMs) || 0);
          };

          const replayAt = async ({ elapsedMs = 0, timeMs = 0 } = {}) => {
            if (!activeLink) await refreshLinks();
            if (!activeLink) {
              showPageStatus('No hay vídeo vinculado.', 'warning', 4200);
              return;
            }
            if (Number(elapsedMs) > 0) lastElapsedMs = Number(elapsedMs) || 0;
            // Asegura link seleccionado
            const selectedId = Number(matchVideoAngleSelect?.value) || 0;
            const selected = selectedId ? (links.find((l) => Number(l.id) === selectedId) || null) : null;
            if (selected && (!activeLink || Number(activeLink.id) !== Number(selected.id))) {
              await setSource(selected, { keepTime: false });
            }
            const safeLink = activeLink || selected;
            const anchorTimeMs = computeTimeMsForLink(safeLink, { elapsedMs, fallbackTimeMs: timeMs });
            const pre = Math.max(0, Number(safeLink.clip_pre_ms) || 0) / 1000.0;
            const post = Math.max(0, Number(safeLink.clip_post_ms) || 0) / 1000.0;
            const t = Math.max(0, (Number(anchorTimeMs) || 0) / 1000.0 - (pre || 6.0));
            const stopAt = Math.max(t + 0.25, (Number(anchorTimeMs) || 0) / 1000.0 + (post || 6.0));
            try { matchVideoEl.currentTime = t; } catch (e) {}
            try { await matchVideoEl.play(); } catch (e) {}
            const handler = () => {
              try {
                if ((Number(matchVideoEl.currentTime) || 0) >= stopAt - 0.03) {
                  matchVideoEl.pause();
                  matchVideoEl.removeEventListener('timeupdate', handler);
                }
              } catch (e) {}
            };
            matchVideoEl.addEventListener('timeupdate', handler);
          };

          const replayLast = async () => {
            const anchor = readLastVideoAnchor();
            const timeMs = Number(anchor.time_ms) || 0;
            const elapsedMs = Number(anchor.elapsed_ms) || 0;
            if ((!timeMs && !elapsedMs) || !activeLink) {
              showPageStatus('No hay “último momento” todavía. Registra una acción con vídeo vinculado.', 'warning', 4200);
              return;
            }
            // Asegura que el vídeo activo corresponde al link seleccionado.
            if (matchVideoAngleSelect.value && String(activeLink.id) !== String(matchVideoAngleSelect.value)) {
              const id = Number(matchVideoAngleSelect.value) || 0;
              const link = links.find((l) => Number(l.id) === id) || null;
              if (link) await setSource(link, { keepTime: false });
            }
            await replayAt({ elapsedMs, timeMs });
          };

          const postMarker = async ({ makeClip = false } = {}) => {
            if (!matchVideoMarkerApiUrl) return;
            const minute = getCurrentMatchMinute();
            const period = Number(liveController?.getCurrentHalf?.()) || 1;
            const label = window.prompt('Etiqueta (opcional):', '') || '';
            const fd = new FormData();
            fd.set('minute', String(minute));
            fd.set('period', String(period));
            if (label) fd.set('label', String(label).slice(0, 160));
            if (makeClip) fd.set('make_clip', '1');
            try {
              const resp = await fetch(matchVideoMarkerApiUrl, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' }, body: fd });
              const data = await resp.json().catch(() => ({}));
              if (!resp.ok || !data?.ok) {
                showPageStatus(data?.error || 'No se pudo marcar en vídeo.', 'warning', 4200);
                return;
              }
              showPageStatus(makeClip ? 'Clip creado.' : 'Marca creada.', 'success', 2200);
              if (data.clip_id) {
                const url = analysisVideoClipUrlTemplate.replace('/0/', `/${Number(data.clip_id)}/`);
                try { window.open(url, '_blank', 'noopener'); } catch (e) {}
              }
            } catch (e) {
              showPageStatus('Error creando marca/clip.', 'warning', 4200);
            }
          };

          matchVideoReplayBtn?.addEventListener('click', replayLast);
          matchVideoMarkBtn?.addEventListener('click', () => postMarker({ makeClip: false }));
          matchVideoClipBtn?.addEventListener('click', () => postMarker({ makeClip: true }));

          // Replay por acción: al pulsar 🎬 en historial.
          document.addEventListener('webstats:match-video:seek', async (ev) => {
            const d = ev?.detail || {};
            const elapsedMs = Number(d.elapsed_ms) || 0;
            const timeMs = Number(d.time_ms) || 0;
            try { matchVideoModal.hidden = false; } catch (e) {}
            await refreshLinks();
            await replayAt({ elapsedMs, timeMs });
          });

          // Si llega un evento de “acción registrada” con info de vídeo, abre botón de replay más útil.
          document.addEventListener('webstats:match-actions:recorded', (ev) => {
            const link = ev?.detail?.video_link;
            if (!link || !matchVideoModal) return;
            // si el modal está abierto, no molestamos; si está cerrado, dejamos que el usuario lo abra.
          });
        })();
	      if (proEditLastBtn) {
	        proEditLastBtn.addEventListener('click', () => {
	          try { liveController?.editLastAction?.(); } catch (e) {}
	        });
	      }
	      if (proRedoBtn) {
	        proRedoBtn.addEventListener('click', () => {
	          try { liveController?.redoLastUndo?.(); } catch (e) {}
	        });
	      }
		      playerQuickButtons.forEach((btn) => {
		        btn.addEventListener('click', async () => {
	          if (activeStage !== 'live') {
	            showPageStatus('Las tarjetas se registran en vivo.', 'warning', 3200);
	            return;
	          }
	          if (!selectedPlayerId) {
	            showPageStatus('Selecciona primero un jugador.', 'warning', 3200);
	            return;
	          }
		          const player = findPlayerPayload(selectedPlayerId);
		          if (!player?.id) {
		            showPageStatus('Jugador inválido.', 'warning', 3200);
		            return;
		          }
		          const getPlayerCardState = (playerId) => {
		            const state = { yellows: 0, reds: 0 };
		            if (!historyList || !playerId) return state;
		            const pid = String(playerId);
		            historyList.querySelectorAll('[data-event-id]').forEach((item) => {
		              if (String(item.dataset.playerId || '') !== pid) return;
		              const text = item.querySelector('.hist-text')?.textContent || '';
		              const parts = text.split('·').map((part) => part.trim());
		              const action = String(parts[0] || '').toLowerCase();
		              const result = String(parts[2] || '').toLowerCase();
		              if (action.includes('tarjeta roja') || result.includes('roja')) state.reds += 1;
		              else if (action.includes('tarjeta amarilla') || result.includes('amarilla')) state.yellows += 1;
		            });
		            return state;
		          };
		          const cardState = getPlayerCardState(selectedPlayerId);
		          const reason = String(playerQuickReasonSelect?.value || '').trim();
		          const reasonSuffix = reason ? ` · ${reason}` : '';
		          const key = btn.dataset.quickCard;
		          let config;
		          if (key === 'amarilla') {
		            if (cardState.reds > 0) {
		              showPageStatus('Este jugador ya tiene roja.', 'warning', 3200);
		              return;
		            }
		            if (cardState.yellows >= 1) {
		              config = {
		                eventType: 'Tarjeta Roja',
		                zoneLabel: 'Tarjeta Roja (2ª amarilla)',
		                result: `Roja (2ª amarilla)${reasonSuffix}`,
		                dropKey: 'roja',
		              };
		            } else {
		              config = {
		                eventType: 'Tarjeta Amarilla',
		                zoneLabel: 'Tarjeta Amarilla',
		                result: `Amarilla${reasonSuffix}`,
		                dropKey: 'amarilla',
		              };
		            }
		          } else {
		            if (cardState.reds > 0) {
		              showPageStatus('Este jugador ya tiene roja.', 'warning', 3200);
		              return;
		            }
		            config = {
		              eventType: 'Tarjeta Roja',
		              zoneLabel: 'Tarjeta Roja',
		              result: `Roja${reasonSuffix}`,
		              dropKey: 'roja',
		            };
		          }
		          try {
		            showPageStatus(`Registrando ${config.result.toLowerCase()}...`, 'info', 1600);
	            const data = await liveController?.registerQuickDropAction?.({
	              player,
	              eventType: config.eventType,
	              zoneLabel: config.zoneLabel,
	              result: config.result,
	              dropKey: config.dropKey,
	              teamOnly: false,
	              minuteOverride: getCurrentMatchMinute(),
	            });
	            if (!data) {
	              showPageStatus('No se pudo registrar la tarjeta.', 'warning', 4200);
	              return;
	            }
	            showPageStatus(
	              `Tarjeta ${config.result.toLowerCase()} registrada${data.duplicate ? ' (duplicado detectado)' : ''}.`,
	              data.duplicate ? 'warning' : 'success',
	              2600,
	            );
	          } catch (err) {
	            console.error(err);
	            showPageStatus('Error registrando tarjeta.', 'warning', 4200);
	          }
	        });
	      });
	      updateCloseSummary();
	      updatePlayerQuickPanel();

})();
