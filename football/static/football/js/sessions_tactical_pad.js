(function () {
  const shared = window.FootballTacticalShared || {};
  const debounce = shared.debounce || ((fn) => fn);
  const readStorageJson = shared.readStorageJson || (() => ({}));
  const writeStorageJson = shared.writeStorageJson || (() => false);
  const removeStorageKey = shared.removeStorageKey || (() => {});
  const readSessionValue = shared.readSessionValue || (() => '');
  const writeSessionValue = shared.writeSessionValue || (() => false);
  const removeSessionKey = shared.removeSessionKey || (() => {});
  const downloadDataUrl = shared.downloadDataUrl || (() => {});

  const collectCheckboxValues = (form, name) => (
    Array.from(form.querySelectorAll(`input[name="${name}"]:checked`)).map((input) => String(input.value || '').trim()).filter(Boolean)
  );

  const setGroupedCheckboxValues = (form, name, values) => {
    const selected = new Set(Array.isArray(values) ? values.map((value) => String(value)) : []);
    form.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
      input.checked = selected.has(String(input.value || ''));
    });
  };

  const serializeFormValues = (form) => {
    const values = {};
    form.querySelectorAll('input[name], select[name], textarea[name]').forEach((field) => {
      const name = String(field.name || '').trim();
      if (!name || name === 'csrfmiddlewaretoken' || name === 'planner_action') return;
      if (name.startsWith('draw_canvas_')) return;
      if (field.type === 'checkbox') return;
      if (field.type === 'radio') {
        if (field.checked) values[name] = field.value;
        return;
      }
      values[name] = field.value;
    });
    values.draw_constraints = collectCheckboxValues(form, 'draw_constraints');
    return values;
  };

  const restoreFormValues = (form, values) => {
    if (!values || typeof values !== 'object') return;
    Object.entries(values).forEach(([name, value]) => {
      if (name === 'draw_constraints') {
        setGroupedCheckboxValues(form, name, value);
        return;
      }
      const field = form.querySelector(`[name="${name}"]`);
      if (!field) return;
      if (field.type === 'radio') {
        form.querySelectorAll(`[name="${name}"]`).forEach((radio) => {
          radio.checked = String(radio.value || '') === String(value || '');
        });
        return;
      }
      field.value = value == null ? '' : value;
    });
  };

  const setActiveByDataset = (nodes, attr, value) => {
    nodes.forEach((node) => node.classList.toggle('is-active', String(node.dataset[attr] || '') === String(value || '')));
  };

  window.initSessionsTacticalPad = function initSessionsTacticalPad() {
    const createForm = document.querySelector('form input[name="planner_action"][value="create_draw_task"]')?.closest('form');
    const canvasEl = document.getElementById('create-task-canvas');
    const statusEl = document.getElementById('create-board-status');
    if (!window.fabric || !createForm || !canvasEl) {
      if (statusEl) {
        statusEl.textContent = 'Editor táctico no disponible (falta carga de librería). Mostrando campo base.';
        statusEl.style.color = '#facc15';
      }
      return;
    }

    const draftKey = `sessionsTacticalPadDraft:v3:${window.location.pathname}`;
    const submitMarkerKey = `${draftKey}:submitted`;
    const successAlert = document.querySelector('.alert.ok');
    if (successAlert && readSessionValue(submitMarkerKey) && /Tarea creada con pizarra táctica\./i.test(successAlert.textContent || '')) {
      removeStorageKey(draftKey);
      removeSessionKey(submitMarkerKey);
    }

    const presetSelect = createForm.querySelector('[name="draw_task_pitch_preset"]');
    const stateInput = document.getElementById('draw-canvas-state');
    const widthInput = document.getElementById('draw-canvas-width');
    const heightInput = document.getElementById('draw-canvas-height');
    const previewInput = document.getElementById('draw-canvas-preview-data');
    const colorInput = document.getElementById('create-board-color');
    const strokeInput = document.getElementById('create-board-width');
    const snapBtn = document.getElementById('create-board-snap-btn');
    const layerList = document.getElementById('create-layers-list');
    const resourceGrid = document.getElementById('create-resource-grid');
    const resourceButtons = Array.from(document.querySelectorAll('#create-resource-grid .create-resource-btn'));
    const catalogTabs = Array.from(document.querySelectorAll('#create-catalog-tabs [data-cat]'));
    const iconifyGrid = document.getElementById('create-iconify-grid');
    const iconifySearch = document.getElementById('create-iconify-search');
    const localPlayersGrid = document.getElementById('tpad-local-players-grid');
    const rivalPlayersGrid = document.getElementById('tpad-rival-players-grid');
    const localSearchInput = document.getElementById('tpad-local-search');
    const rivalSearchInput = document.getElementById('tpad-rival-search');
    const localNameInput = document.getElementById('tpad-local-name');
    const rivalNameInput = document.getElementById('tpad-rival-name');
    const localPrimaryInput = document.getElementById('tpad-local-color-primary');
    const localSecondaryInput = document.getElementById('tpad-local-color-secondary');
    const rivalPrimaryInput = document.getElementById('tpad-rival-color-primary');
    const rivalSecondaryInput = document.getElementById('tpad-rival-color-secondary');
    const playerCatalogNode = document.getElementById('tpad-players-catalog');
    const boardShell = document.getElementById('create-board-shell');
    const canvasWrap = canvasEl.closest('.create-board-wrap');
    const feedbackButtons = {
      tools: document.getElementById('tpad-tools-btn'),
      menu: document.getElementById('tpad-menu-btn'),
      board: document.getElementById('tpad-board-btn'),
      field: document.getElementById('tpad-field-btn'),
      save: document.getElementById('tpad-save-btn'),
      share: document.getElementById('tpad-share-btn'),
      project: document.getElementById('tpad-project-btn'),
      stadium: document.getElementById('tpad-3d-btn'),
      fullscreen: document.getElementById('tpad-fullscreen-btn'),
      recoverDraft: document.getElementById('create-board-recover-btn'),
      discardDraft: document.getElementById('create-board-discard-btn'),
    };
    const fieldModal = document.getElementById('tpad-field-modal');
    const fieldCloseBtn = document.getElementById('tpad-field-close');
    const fieldCancelBtn = document.getElementById('tpad-field-cancel');
    const fieldApplyBtn = document.getElementById('tpad-field-apply');
    const fieldPresetCards = Array.from(document.querySelectorAll('[data-field-preset]'));
    const fieldThemeChips = Array.from(document.querySelectorAll('[data-field-theme]'));
    const fieldCameraChips = Array.from(document.querySelectorAll('[data-field-camera]'));
    const toolButtons = Array.from(document.querySelectorAll('.tpad-tool-btn'));
    const toolSelectBtn = document.getElementById('tpad-tool-select');
    const toolDrawBtn = document.getElementById('tpad-tool-draw');
    const toolPlayerBtn = document.getElementById('tpad-tool-player');
    const toolZoneBtn = document.getElementById('tpad-tool-zone');
    const toolArrowBtn = document.getElementById('tpad-tool-arrow');
    const toolLineBtn = document.getElementById('tpad-tool-line');
    const toolColorRedBtn = document.getElementById('tpad-tool-color-red');
    const toolColorBlueBtn = document.getElementById('tpad-tool-color-blue');
    const toolColorWhiteBtn = document.getElementById('tpad-tool-color-white');
    const toolTextBtn = document.getElementById('tpad-tool-text');
    const toolUndoBtn = document.getElementById('tpad-tool-undo');
    const toolDeleteBtn = document.getElementById('tpad-tool-delete');
    const teamChips = boardShell ? {
      local: boardShell.querySelector('.tpad-team-chip.left'),
      rival: boardShell.querySelector('.tpad-team-chip.right'),
    } : { local: null, rival: null };

    let tacticalPlayers = [];
    try {
      tacticalPlayers = JSON.parse(playerCatalogNode?.textContent || '[]');
    } catch (error) {
      tacticalPlayers = [];
    }
    if (!Array.isArray(tacticalPlayers) || !tacticalPlayers.length) {
      tacticalPlayers = Array.from({ length: 23 }).map((_, index) => ({
        id: index + 1,
        name: `Jugador ${index + 1}`,
        number: index + 1,
        position: '',
        photo_url: '',
      }));
    }

    const gridSize = 20;
    let snapEnabled = true;
    let history = [];
    let currentFieldTheme = 'classic';
    let currentFieldCamera = 'full';
    let currentFieldPreset = 'full_pitch';
    let currentCatalogCategory = 'all';
    let pendingInsert = null;
    const teamPalette = {
      local: { name: 'LOCAL', primary: '#0f7ec7', secondary: '#f8fafc' },
      rival: { name: 'RIVAL', primary: '#f59e0b', secondary: '#f8fafc' },
    };

    const setStatus = (text, isError = false) => {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.style.color = isError ? '#fecaca' : 'rgba(225, 236, 255, 0.8)';
    };
    const normalizeHex = (value, fallback) => {
      const raw = String(value || '').trim();
      return /^#[0-9a-fA-F]{6}$/.test(raw) ? raw : fallback;
    };
    const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
    const teamStyle = (key) => {
      const data = key === 'rival' ? teamPalette.rival : teamPalette.local;
      return {
        name: safeText(data.name, key === 'rival' ? 'RIVAL' : 'LOCAL'),
        primary: normalizeHex(data.primary, key === 'rival' ? '#f59e0b' : '#0f7ec7'),
        secondary: normalizeHex(data.secondary, '#f8fafc'),
      };
    };
    const serializeCanvas = () => canvas.toJSON(['data', '__locked']);
    const pushHistory = () => {
      history.push(JSON.stringify(serializeCanvas()));
      if (history.length > 80) history = history.slice(history.length - 80);
    };
    const fitCanvas = () => {
      const width = Math.max(320, Math.round(canvasWrap?.clientWidth || 960));
      const height = Math.max(220, Math.round(canvasWrap?.clientHeight || 380));
      canvas.setDimensions({ width, height });
      canvas.renderAll();
    };
    const canvas = new fabric.Canvas(canvasEl, {
      isDrawingMode: true,
      selection: false,
      preserveObjectStacking: true,
    });
    fitCanvas();
    canvas.freeDrawingBrush.color = '#e11d48';
    canvas.freeDrawingBrush.width = 4;

    const saveDraft = (statusMessage = 'Borrador táctico actualizado.') => {
      const payload = {
        saved_at: new Date().toISOString(),
        canvas_state: serializeCanvas(),
        canvas_width: Math.round(canvas.getWidth()),
        canvas_height: Math.round(canvas.getHeight()),
        field_preset: currentFieldPreset,
        field_theme: currentFieldTheme,
        field_camera: currentFieldCamera,
        team_palette: teamPalette,
        snap_enabled: snapEnabled,
        form_values: serializeFormValues(createForm),
      };
      writeStorageJson(draftKey, payload);
      setStatus(statusMessage);
    };
    const scheduleDraftSave = debounce(() => saveDraft(), 900);
    const discardDraft = () => {
      removeStorageKey(draftKey);
      removeSessionKey(submitMarkerKey);
      setStatus('Borrador táctico eliminado.');
    };
    const clearPendingInsert = (statusMessage = '') => {
      pendingInsert = null;
      if (statusMessage) setStatus(statusMessage);
    };
    const startQuickInsert = (kind, options = {}, statusMessage = 'Haz clic en el campo para colocar el recurso.') => {
      pendingInsert = {
        kind: String(kind || '').trim(),
        options: options && typeof options === 'object' ? { ...options } : {},
      };
      setMode(false);
      setStatus(statusMessage);
    };
    const clampPlacement = (left, top) => {
      const width = Math.max(0, Math.round(canvas.getWidth() || 0));
      const height = Math.max(0, Math.round(canvas.getHeight() || 0));
      return {
        left: Math.max(18, Math.min(Math.round(left || (width / 2)), Math.max(18, width - 18))),
        top: Math.max(18, Math.min(Math.round(top || (height / 2)), Math.max(18, height - 18))),
      };
    };
    const positionItem = (item, left, top) => {
      if (!item) return item;
      const rect = item.getBoundingRect ? item.getBoundingRect() : { width: item.width || 0, height: item.height || 0 };
      const width = Math.max(0, Math.round(rect.width || item.width || 0));
      const height = Math.max(0, Math.round(rect.height || item.height || 0));
      item.set({
        originX: 'left',
        originY: 'top',
        left: Math.round(left - (width / 2)),
        top: Math.round(top - (height / 2)),
      });
      item.setCoords?.();
      return item;
    };
    const defaultPlacement = () => clampPlacement((canvas.getWidth() || 0) / 2, (canvas.getHeight() || 0) / 2);

    const refreshLayerList = () => {
      if (!layerList) return;
      const activeObject = canvas.getActiveObject();
      const objects = canvas.getObjects().slice().reverse();
      layerList.innerHTML = '';
      objects.forEach((obj, index) => {
        const row = document.createElement('div');
        row.className = 'create-layer-item';
        if (activeObject === obj) row.classList.add('active');
        const label = document.createElement('span');
        label.textContent = `${index + 1}. ${obj.type || 'objeto'}`;
        const selectBtn = document.createElement('button');
        selectBtn.type = 'button';
        selectBtn.textContent = 'Sel';
        selectBtn.addEventListener('click', () => {
          canvas.setActiveObject(obj);
          canvas.renderAll();
          refreshLayerList();
        });
        const lockBtn = document.createElement('button');
        lockBtn.type = 'button';
        lockBtn.textContent = obj.__locked ? 'Lock' : 'Free';
        lockBtn.addEventListener('click', () => {
          setObjectLocked(obj, !obj.__locked);
          canvas.discardActiveObject();
          canvas.renderAll();
          refreshLayerList();
          scheduleDraftSave();
        });
        row.appendChild(label);
        row.appendChild(selectBtn);
        row.appendChild(lockBtn);
        layerList.appendChild(row);
      });
    };

    const updateTeamChips = () => {
      const local = teamStyle('local');
      const rival = teamStyle('rival');
      if (teamChips.local) {
        teamChips.local.dataset.team = (local.name || 'L').slice(0, 1).toUpperCase();
        const span = teamChips.local.querySelector('span');
        if (span) span.textContent = local.name;
        teamChips.local.style.background = `linear-gradient(180deg, ${local.primary}, #0f172a)`;
        teamChips.local.style.borderColor = `${local.secondary}80`;
      }
      if (teamChips.rival) {
        teamChips.rival.dataset.team = (rival.name || 'R').slice(0, 1).toUpperCase();
        const span = teamChips.rival.querySelector('span');
        if (span) span.textContent = rival.name;
        teamChips.rival.style.background = `linear-gradient(180deg, ${rival.primary}, #0f172a)`;
        teamChips.rival.style.borderColor = `${rival.secondary}80`;
      }
    };
    const syncTeamPaletteFromInputs = () => {
      teamPalette.local.name = safeText(localNameInput?.value, 'LOCAL');
      teamPalette.local.primary = normalizeHex(localPrimaryInput?.value, '#0f7ec7');
      teamPalette.local.secondary = normalizeHex(localSecondaryInput?.value, '#f8fafc');
      teamPalette.rival.name = safeText(rivalNameInput?.value, 'RIVAL');
      teamPalette.rival.primary = normalizeHex(rivalPrimaryInput?.value, '#f59e0b');
      teamPalette.rival.secondary = normalizeHex(rivalSecondaryInput?.value, '#f8fafc');
      updateTeamChips();
    };
    const applyCatalogFilter = (cat) => {
      currentCatalogCategory = String(cat || 'all');
      catalogTabs.forEach((tab) => tab.classList.toggle('is-active', String(tab.dataset.cat || 'all') === currentCatalogCategory));
      resourceButtons.forEach((btn) => {
        const btnCat = String(btn.dataset.cat || 'all');
        btn.classList.toggle('is-hidden', currentCatalogCategory !== 'all' && btnCat !== currentCatalogCategory);
      });
    };
    const setToolsOpen = (open) => {
      if (!boardShell) return;
      boardShell.classList.toggle('tools-open', !!open);
      if (feedbackButtons.tools) {
        feedbackButtons.tools.style.background = open ? 'rgba(37, 99, 235, 0.75)' : 'rgba(15, 23, 42, 0.75)';
      }
      if (feedbackButtons.board) feedbackButtons.board.classList.toggle('is-active', !!open);
      window.setTimeout(() => {
        fitCanvas();
        canvas.renderAll();
      }, 120);
    };
    const openFieldModal = (open) => {
      if (!fieldModal) return;
      fieldModal.classList.toggle('is-open', !!open);
      if (feedbackButtons.field) feedbackButtons.field.classList.toggle('is-active', !!open);
    };
    const setActiveTool = (targetBtn) => {
      toolButtons.forEach((btn) => {
        if ([toolColorRedBtn, toolColorBlueBtn, toolColorWhiteBtn, toolUndoBtn, toolDeleteBtn].includes(btn)) return;
        btn.classList.toggle('is-active', btn === targetBtn);
      });
    };
    const setFieldCameraActive = (camera) => {
      fieldCameraChips.forEach((node) => node.classList.toggle('is-active', String(node.dataset.fieldCamera || '') === camera));
      if (feedbackButtons.stadium) feedbackButtons.stadium.classList.toggle('is-active', camera === 'stadium');
    };
    const dockButtons = [
      feedbackButtons.project,
      feedbackButtons.save,
      feedbackButtons.share,
      feedbackButtons.board,
      feedbackButtons.field,
      feedbackButtons.stadium,
      feedbackButtons.fullscreen,
    ].filter(Boolean);
    const setDockActive = (button, transient = false) => {
      dockButtons.forEach((btn) => btn.classList.remove('is-active'));
      if (!button) return;
      button.classList.add('is-active');
      if (transient) {
        button.classList.add('is-flash');
        window.setTimeout(() => button.classList.remove('is-flash'), 380);
      }
    };
    const setObjectLocked = (obj, locked) => {
      if (!obj) return;
      obj.__locked = !!locked;
      obj.lockMovementX = !!locked;
      obj.lockMovementY = !!locked;
      obj.lockRotation = !!locked;
      obj.lockScalingX = !!locked;
      obj.lockScalingY = !!locked;
      obj.selectable = !locked;
      obj.evented = !locked;
    };
    const getSelectedObjects = () => {
      const active = canvas.getActiveObject();
      if (!active) return [];
      if (active.type === 'activeSelection' && Array.isArray(active._objects)) return active._objects;
      return [active];
    };
    const applySnap = (obj) => {
      if (!snapEnabled || !obj || obj.__locked) return;
      obj.left = Math.round((obj.left || 0) / gridSize) * gridSize;
      obj.top = Math.round((obj.top || 0) / gridSize) * gridSize;
      obj.setCoords();
    };
    const alignSelected = (mode) => {
      const objects = getSelectedObjects().filter((obj) => !obj.__locked);
      if (!objects.length) {
        setStatus('Selecciona elementos para alinear.', true);
        return;
      }
      const bounds = objects.map((obj) => obj.getBoundingRect(true, true));
      const minLeft = Math.min(...bounds.map((item) => item.left));
      const maxRight = Math.max(...bounds.map((item) => item.left + item.width));
      const minTop = Math.min(...bounds.map((item) => item.top));
      const maxBottom = Math.max(...bounds.map((item) => item.top + item.height));
      const centerX = (minLeft + maxRight) / 2;
      const centerY = (minTop + maxBottom) / 2;
      objects.forEach((obj) => {
        const rect = obj.getBoundingRect(true, true);
        if (mode === 'left') obj.left += minLeft - rect.left;
        if (mode === 'center') obj.left += centerX - (rect.left + (rect.width / 2));
        if (mode === 'right') obj.left += maxRight - (rect.left + rect.width);
        if (mode === 'top') obj.top += minTop - rect.top;
        if (mode === 'middle') obj.top += centerY - (rect.top + (rect.height / 2));
        if (mode === 'bottom') obj.top += maxBottom - (rect.top + rect.height);
        applySnap(obj);
        obj.setCoords();
      });
      canvas.renderAll();
      pushHistory();
      refreshLayerList();
      scheduleDraftSave();
      setStatus('Alineación aplicada.');
    };
    const setMode = (drawMode) => {
      if (drawMode) clearPendingInsert();
      canvas.isDrawingMode = !!drawMode;
      canvas.selection = !drawMode;
      canvas.forEachObject((obj) => {
        if (obj.__locked) return;
        obj.selectable = !drawMode;
      });
      canvas.renderAll();
      setStatus(drawMode ? 'Modo dibujo activo.' : 'Modo selección activo.');
      setActiveTool(drawMode ? toolDrawBtn : toolSelectBtn);
    };

    const applyFieldBackground = (presetKey, opts = {}) => {
      const preset = String(presetKey || currentFieldPreset || 'full_pitch').trim();
      currentFieldPreset = preset;
      currentFieldTheme = String(opts.theme || currentFieldTheme || 'classic').trim();
      currentFieldCamera = String(opts.camera || currentFieldCamera || 'full').trim();
      setActiveByDataset(fieldPresetCards, 'fieldPreset', currentFieldPreset);
      setActiveByDataset(fieldThemeChips, 'fieldTheme', currentFieldTheme);
      setFieldCameraActive(currentFieldCamera);
      if (presetSelect) presetSelect.value = currentFieldPreset;

      const themes = {
        classic: ['#4f8d39', '#5b9840'],
        dark: ['#2f6f2a', '#3a7c2f'],
        mint: ['#4b9d74', '#58aa82'],
        dry: ['#769e46', '#88aa58'],
      };
      const palette = themes[currentFieldTheme] || themes.classic;
      canvas.clear();
      canvas.backgroundColor = '#ffffff';
      const common = { selectable: false, evented: false, excludeFromExport: false };
      const width = canvas.getWidth();
      const height = canvas.getHeight();
      let marginX = Math.round(width * 0.045);
      let marginY = Math.round(height * 0.055);
      let fieldLeft = 0;
      let fieldTop = 0;
      let fieldW = width;
      let fieldH = height;
      if (currentFieldCamera === 'stadium') {
        fieldTop = Math.round(height * 0.12);
        fieldH = Math.round(height * 0.82);
      }
      if (currentFieldCamera === 'left') {
        fieldW = Math.round(width * 0.62);
      } else if (currentFieldCamera === 'right') {
        fieldW = Math.round(width * 0.62);
        fieldLeft = width - fieldW;
      }
      const lineColor = 'rgba(255,255,255,0.82)';
      const lineSoft = 'rgba(255,255,255,0.62)';
      const addArcPath = (path, strokeWidth = 2.2, stroke = lineColor) => {
        canvas.add(new fabric.Path(path, { ...common, fill: '', stroke, strokeWidth }));
      };
      const addRect = (left, top, rectWidth, rectHeight, strokeWidth = 2.2, stroke = lineColor, options = {}) => {
        canvas.add(new fabric.Rect({
          ...common,
          left,
          top,
          width: rectWidth,
          height: rectHeight,
          fill: 'transparent',
          stroke,
          strokeWidth,
          ...options,
        }));
      };
      const addLine = (points, strokeWidth = 2.2, stroke = lineColor) => {
        canvas.add(new fabric.Line(points, { ...common, stroke, strokeWidth }));
      };
      const addCircle = (left, top, radius, strokeWidth = 2.2, stroke = lineColor, fill = 'transparent') => {
        canvas.add(new fabric.Circle({ ...common, left, top, radius, fill, stroke, strokeWidth }));
      };
      const addSpot = (centerX, centerY, radius = 2.8) => {
        canvas.add(new fabric.Circle({ ...common, left: centerX - radius, top: centerY - radius, radius, fill: '#ffffff', strokeWidth: 0 }));
      };
      const drawGoal = (left, top, goalWidth, goalDepth, inward = false) => {
        const x1 = left;
        const x2 = left + goalWidth;
        const frontY = inward ? top + goalDepth : top;
        const backY = inward ? top : top + goalDepth;
        addLine([x1, frontY, x1, backY], 2);
        addLine([x2, frontY, x2, backY], 2);
        addLine([x1, backY, x2, backY], 2);
      };
      const drawCornerArcs = (left, top, right, bottom, radius) => {
        addArcPath(`M ${left} ${top + radius} A ${radius} ${radius} 0 0 1 ${left + radius} ${top}`, 2);
        addArcPath(`M ${right - radius} ${top} A ${radius} ${radius} 0 0 1 ${right} ${top + radius}`, 2);
        addArcPath(`M ${left} ${bottom - radius} A ${radius} ${radius} 0 0 0 ${left + radius} ${bottom}`, 2);
        addArcPath(`M ${right - radius} ${bottom} A ${radius} ${radius} 0 0 0 ${right} ${bottom - radius}`, 2);
      };
      const drawPenaltyArc = (centerX, centerY, radius, facing) => {
        if (facing === 'down') addArcPath(`M ${centerX - radius} ${centerY} A ${radius} ${radius} 0 0 0 ${centerX + radius} ${centerY}`, 2.1, lineSoft);
        if (facing === 'up') addArcPath(`M ${centerX - radius} ${centerY} A ${radius} ${radius} 0 0 1 ${centerX + radius} ${centerY}`, 2.1, lineSoft);
      };
      const drawFullPitchMarkings = (rect) => {
        const left = rect.left;
        const top = rect.top;
        const innerWidth = rect.width;
        const innerHeight = rect.height;
        const right = left + innerWidth;
        const bottom = top + innerHeight;
        const centerX = left + (innerWidth / 2);
        const centerY = top + (innerHeight / 2);
        const penaltyBoxWidth = innerWidth * 0.44;
        const sixBoxWidth = innerWidth * 0.22;
        const penaltyBoxDepth = innerHeight * 0.19;
        const sixBoxDepth = innerHeight * 0.08;
        const goalWidth = innerWidth * 0.13;
        const goalDepth = innerHeight * 0.03;
        const penaltySpotOffset = innerHeight * 0.13;
        const centerRadius = Math.min(innerWidth, innerHeight) * 0.12;
        const cornerRadius = Math.min(innerWidth, innerHeight) * 0.03;
        const penaltyArcRadius = innerWidth * 0.09;
        const topPenaltyCenterY = top + penaltySpotOffset;
        const bottomPenaltyCenterY = bottom - penaltySpotOffset;

        addLine([centerX, top, centerX, bottom], 2.6);
        addCircle(centerX - centerRadius, centerY - centerRadius, centerRadius, 2.3);
        addSpot(centerX, centerY);
        addRect(centerX - (penaltyBoxWidth / 2), top, penaltyBoxWidth, penaltyBoxDepth, 2.25, lineSoft);
        addRect(centerX - (penaltyBoxWidth / 2), bottom - penaltyBoxDepth, penaltyBoxWidth, penaltyBoxDepth, 2.25, lineSoft);
        addRect(centerX - (sixBoxWidth / 2), top, sixBoxWidth, sixBoxDepth, 2.15, lineSoft);
        addRect(centerX - (sixBoxWidth / 2), bottom - sixBoxDepth, sixBoxWidth, sixBoxDepth, 2.15, lineSoft);
        addSpot(centerX, topPenaltyCenterY);
        addSpot(centerX, bottomPenaltyCenterY);
        drawGoal(centerX - (goalWidth / 2), top, goalWidth, goalDepth, false);
        drawGoal(centerX - (goalWidth / 2), bottom - goalDepth, goalWidth, goalDepth, true);
        drawPenaltyArc(centerX, topPenaltyCenterY, penaltyArcRadius, 'down');
        drawPenaltyArc(centerX, bottomPenaltyCenterY, penaltyArcRadius, 'up');
        drawCornerArcs(left, top, right, bottom, cornerRadius);
      };
      const drawHalfPitchMarkings = (rect) => {
        const left = rect.left;
        const top = rect.top;
        const innerWidth = rect.width;
        const innerHeight = rect.height;
        const right = left + innerWidth;
        const bottom = top + innerHeight;
        const centerX = left + (innerWidth / 2);
        const penaltyBoxWidth = innerWidth * 0.52;
        const sixBoxWidth = innerWidth * 0.24;
        const penaltyBoxDepth = innerHeight * 0.28;
        const sixBoxDepth = innerHeight * 0.11;
        const goalWidth = innerWidth * 0.16;
        const goalDepth = innerHeight * 0.035;
        const cornerRadius = Math.min(innerWidth, innerHeight) * 0.03;
        const centerRadius = Math.min(innerWidth, innerHeight) * 0.12;
        const penaltySpotY = top + (innerHeight * 0.18);
        const midfieldY = bottom;
        const penaltyArcRadius = innerWidth * 0.11;

        addRect(centerX - (penaltyBoxWidth / 2), top, penaltyBoxWidth, penaltyBoxDepth, 2.25, lineSoft);
        addRect(centerX - (sixBoxWidth / 2), top, sixBoxWidth, sixBoxDepth, 2.15, lineSoft);
        addSpot(centerX, penaltySpotY);
        drawGoal(centerX - (goalWidth / 2), top, goalWidth, goalDepth, false);
        drawPenaltyArc(centerX, penaltySpotY, penaltyArcRadius, 'down');
        addLine([left, midfieldY, right, midfieldY], 2.5);
        addCircle(centerX - centerRadius, midfieldY - centerRadius, centerRadius, 2.15, lineSoft);
        drawCornerArcs(left, top, right, bottom, cornerRadius);
      };
      const drawAttackingThirdMarkings = (rect) => {
        const left = rect.left;
        const top = rect.top;
        const innerWidth = rect.width;
        const innerHeight = rect.height;
        const right = left + innerWidth;
        const bottom = top + innerHeight;
        const centerX = left + (innerWidth / 2);
        const penaltyBoxWidth = innerWidth * 0.42;
        const sixBoxWidth = innerWidth * 0.2;
        const penaltyBoxDepth = innerHeight * 0.24;
        const sixBoxDepth = innerHeight * 0.09;
        const goalWidth = innerWidth * 0.13;
        const goalDepth = innerHeight * 0.03;
        const cornerRadius = Math.min(innerWidth, innerHeight) * 0.03;
        const penaltySpotY = top + (innerHeight * 0.16);
        const penaltyArcRadius = innerWidth * 0.085;
        const buildLineY = top + (innerHeight * 0.34);

        addRect(centerX - (penaltyBoxWidth / 2), top, penaltyBoxWidth, penaltyBoxDepth, 2.25, lineSoft);
        addRect(centerX - (sixBoxWidth / 2), top, sixBoxWidth, sixBoxDepth, 2.15, lineSoft);
        addSpot(centerX, penaltySpotY);
        drawGoal(centerX - (goalWidth / 2), top, goalWidth, goalDepth, false);
        drawPenaltyArc(centerX, penaltySpotY, penaltyArcRadius, 'down');
        addLine([left, buildLineY, right, buildLineY], 2.1, lineSoft);
        drawCornerArcs(left, top, right, bottom, cornerRadius);
      };
      const drawSevenSideMarkings = (rect) => {
        const left = rect.left;
        const top = rect.top;
        const innerWidth = rect.width;
        const innerHeight = rect.height;
        const right = left + innerWidth;
        const bottom = top + innerHeight;
        const centerX = left + (innerWidth / 2);
        const centerY = top + (innerHeight / 2);
        const areaWidth = innerWidth * 0.46;
        const areaDepth = innerHeight * 0.16;
        const goalAreaWidth = innerWidth * 0.24;
        const goalAreaDepth = innerHeight * 0.075;
        const goalWidth = innerWidth * 0.14;
        const goalDepth = innerHeight * 0.028;
        const cornerRadius = Math.min(innerWidth, innerHeight) * 0.028;
        const centerRadius = Math.min(innerWidth, innerHeight) * 0.1;
        const spotOffset = innerHeight * 0.12;

        addLine([centerX, top, centerX, bottom], 2.45);
        addCircle(centerX - centerRadius, centerY - centerRadius, centerRadius, 2.1);
        addSpot(centerX, centerY);
        addRect(centerX - (areaWidth / 2), top, areaWidth, areaDepth, 2.15, lineSoft);
        addRect(centerX - (areaWidth / 2), bottom - areaDepth, areaWidth, areaDepth, 2.15, lineSoft);
        addRect(centerX - (goalAreaWidth / 2), top, goalAreaWidth, goalAreaDepth, 2.05, lineSoft);
        addRect(centerX - (goalAreaWidth / 2), bottom - goalAreaDepth, goalAreaWidth, goalAreaDepth, 2.05, lineSoft);
        addSpot(centerX, top + spotOffset);
        addSpot(centerX, bottom - spotOffset);
        drawGoal(centerX - (goalWidth / 2), top, goalWidth, goalDepth, false);
        drawGoal(centerX - (goalWidth / 2), bottom - goalDepth, goalWidth, goalDepth, true);
        drawCornerArcs(left, top, right, bottom, cornerRadius);
      };
      const drawFutsalMarkings = (rect) => {
        const left = rect.left;
        const top = rect.top;
        const innerWidth = rect.width;
        const innerHeight = rect.height;
        const right = left + innerWidth;
        const bottom = top + innerHeight;
        const centerX = left + (innerWidth / 2);
        const centerY = top + (innerHeight / 2);
        const areaWidth = innerWidth * 0.34;
        const areaDepth = innerHeight * 0.18;
        const goalWidth = innerWidth * 0.14;
        const goalDepth = innerHeight * 0.03;
        const cornerRadius = Math.min(innerWidth, innerHeight) * 0.025;
        const centerRadius = Math.min(innerWidth, innerHeight) * 0.09;

        addLine([centerX, top, centerX, bottom], 2.35);
        addCircle(centerX - centerRadius, centerY - centerRadius, centerRadius, 2.05);
        addSpot(centerX, centerY);
        addRect(centerX - (areaWidth / 2), top, areaWidth, areaDepth, 2.1, lineSoft, { rx: 18, ry: 18 });
        addRect(centerX - (areaWidth / 2), bottom - areaDepth, areaWidth, areaDepth, 2.1, lineSoft, { rx: 18, ry: 18 });
        drawGoal(centerX - (goalWidth / 2), top, goalWidth, goalDepth, false);
        drawGoal(centerX - (goalWidth / 2), bottom - goalDepth, goalWidth, goalDepth, true);
        drawCornerArcs(left, top, right, bottom, cornerRadius);
      };
      const grass = new fabric.Rect({ ...common, left: fieldLeft, top: fieldTop, width: fieldW, height: fieldH, fill: palette[0], strokeWidth: 0 });
      const stripeCount = 12;
      const stripes = [];
      for (let index = 0; index < stripeCount; index += 1) {
        stripes.push(new fabric.Rect({
          ...common,
          left: fieldLeft + ((fieldW / stripeCount) * index),
          top: fieldTop,
          width: (fieldW / stripeCount) + 1,
          height: fieldH,
          fill: index % 2 === 0 ? palette[0] : palette[1],
          strokeWidth: 0,
          opacity: 0.96,
        }));
      }
      const field = new fabric.Rect({
        ...common,
        left: fieldLeft + marginX,
        top: fieldTop + marginY,
        width: fieldW - (marginX * 2),
        height: fieldH - (marginY * 2),
        fill: 'transparent',
        stroke: lineColor,
        strokeWidth: 3,
      });
      if (preset === 'blank') {
        canvas.backgroundColor = '#ffffff';
        canvas.renderAll();
        pushHistory();
        refreshLayerList();
        scheduleDraftSave();
        setStatus('Lienzo en blanco.');
        return;
      }
      if (currentFieldCamera === 'stadium') {
        const stands = [
          new fabric.Polygon([{ x: 0, y: 0 }, { x: width, y: 0 }, { x: width, y: height * 0.12 }, { x: 0, y: height * 0.2 }], { ...common, fill: '#334155', opacity: 0.85 }),
          new fabric.Polygon([{ x: 0, y: height * 0.22 }, { x: width * 0.14, y: height * 0.16 }, { x: width * 0.2, y: height * 0.58 }, { x: 0, y: height * 0.72 }], { ...common, fill: '#475569', opacity: 0.64 }),
          new fabric.Polygon([{ x: width, y: height * 0.18 }, { x: width * 0.86, y: height * 0.15 }, { x: width * 0.8, y: height * 0.58 }, { x: width, y: height * 0.72 }], { ...common, fill: '#475569', opacity: 0.64 }),
        ];
        stands.forEach((shape) => canvas.add(shape));
        marginY = Math.round(height * 0.12);
      }
      canvas.add(grass);
      stripes.forEach((stripe) => canvas.add(stripe));
      canvas.add(field);
      if (preset === 'half_pitch') {
        drawHalfPitchMarkings(field);
      } else if (preset === 'attacking_third') {
        drawAttackingThirdMarkings(field);
      } else if (preset === 'seven_side') {
        drawSevenSideMarkings(field);
      } else if (preset === 'futsal') {
        drawFutsalMarkings(field);
      } else {
        drawFullPitchMarkings(field);
      }
      canvas.renderAll();
      pushHistory();
      refreshLayerList();
      scheduleDraftSave();
      setStatus('Preset aplicado en pizarra táctica.');
    };

    const addPlayerToken = (profile = {}, teamKey = 'local', role = 'player', placement = {}) => {
      const team = teamStyle(teamKey);
      const fallbackPlacement = defaultPlacement();
      const baseLeft = Number.isFinite(placement.left) ? placement.left : fallbackPlacement.left;
      const baseTop = Number.isFinite(placement.top) ? placement.top : fallbackPlacement.top;
      const rawNumber = safeText(profile.number, role === 'goalkeeper' ? 'GK' : '');
      const number = rawNumber ? String(rawNumber).slice(0, 3) : '';
      const rawName = safeText(profile.name, team.name);
      const shortName = rawName.split(/\s+/).map((piece) => piece[0] || '').join('').slice(0, 2).toUpperCase() || rawName.slice(0, 2).toUpperCase();
      const photoUrl = safeText(profile.photo_url || profile.photo, '');
      const radius = role === 'goalkeeper' ? 24 : 20;
      const buildToken = (photoImage = null) => {
        const parts = [];
        parts.push(new fabric.Circle({ radius, fill: team.primary, stroke: team.secondary, strokeWidth: 2.2, shadow: 'rgba(2,6,23,0.36) 0 3px 10px' }));
        if (photoImage) {
          photoImage.set({ originX: 'center', originY: 'center', left: 0, top: 0 });
          photoImage.scaleToWidth(radius * 1.65);
          photoImage.clipPath = new fabric.Circle({ radius: radius * 0.78, originX: 'center', originY: 'center', left: 0, top: 0 });
          parts.push(photoImage);
        } else {
          parts.push(new fabric.Text(shortName, { fontSize: Math.max(10, Math.round(radius * 0.72)), fill: team.secondary, fontWeight: '700', originX: 'center', originY: 'center', left: 0, top: 0 }));
        }
        if (number) {
          parts.push(new fabric.Text(number, { fontSize: 10, fill: '#ffffff', backgroundColor: 'rgba(15,23,42,0.82)', fontWeight: '700', originX: 'center', originY: 'center', left: 0, top: radius + 10 }));
        }
        const group = new fabric.Group(parts, {});
        positionItem(group, baseLeft, baseTop);
        group.set({ data: { kind: role, team: teamKey, playerId: profile.id || '', playerName: rawName } });
        canvas.add(group);
        canvas.setActiveObject(group);
        canvas.renderAll();
        pushHistory();
        refreshLayerList();
        scheduleDraftSave();
        setStatus(`${role === 'goalkeeper' ? 'Portero' : 'Jugador'} ${rawName} añadido.`);
      };
      if (photoUrl) {
        fabric.Image.fromURL(photoUrl, (img) => buildToken(img || null), { crossOrigin: 'anonymous' });
        return;
      }
      buildToken(null);
    };

    const addResource = (kind, options = {}) => {
      const fallbackPlacement = defaultPlacement();
      const baseLeft = Number.isFinite(options.left) ? options.left : fallbackPlacement.left;
      const baseTop = Number.isFinite(options.top) ? options.top : fallbackPlacement.top;
      const variant = String(options.variant || '').trim().toLowerCase();
      const teamKey = String(options.team || 'local').trim().toLowerCase() === 'rival' ? 'rival' : 'local';
      let item = null;
      if (kind === 'player') return addPlayerToken(options.player || {}, teamKey, 'player', { left: baseLeft, top: baseTop });
      if (kind === 'goalkeeper') return addPlayerToken(options.player || {}, teamKey, 'goalkeeper', { left: baseLeft, top: baseTop });
      if (kind === 'ball') item = new fabric.Circle({ left: baseLeft, top: baseTop, radius: variant === 'flat' ? 9 : 10, fill: variant === 'flat' ? '#f8fafc' : '#ffffff', stroke: '#0f172a', strokeWidth: variant === 'flat' ? 1.3 : 2 });
      if (kind === 'cone') {
        if (variant === 'disc') item = new fabric.Circle({ left: baseLeft, top: baseTop, radius: 8, fill: '#fb923c', stroke: '#7c2d12', strokeWidth: 1.8 });
        else if (variant === 'pica') item = new fabric.Group([
          new fabric.Rect({ left: 0, top: 0, width: 4, height: 38, fill: '#facc15', originX: 'center', originY: 'center' }),
          new fabric.Triangle({ left: 0, top: 17, width: 16, height: 16, fill: '#f97316', originX: 'center', originY: 'center' }),
        ], { left: baseLeft, top: baseTop });
        else item = new fabric.Triangle({ left: baseLeft, top: baseTop, width: 26, height: 26, fill: '#f97316' });
      }
      if (kind === 'hurdle') item = new fabric.Group([
        new fabric.Rect({ left: -18, top: 6, width: 36, height: 6, rx: 3, ry: 3, fill: '#f8fafc', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: -13, top: 0, width: 4, height: 18, fill: '#f97316', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 13, top: 0, width: 4, height: 18, fill: '#f97316', originX: 'center', originY: 'center' }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'ladder') item = new fabric.Group([
        new fabric.Rect({ left: -24, top: 0, width: 4, height: 54, fill: '#facc15', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 24, top: 0, width: 4, height: 54, fill: '#facc15', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 0, top: -18, width: 48, height: 3, fill: '#fb923c', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 0, top: -6, width: 48, height: 3, fill: '#fb923c', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 0, top: 6, width: 48, height: 3, fill: '#fb923c', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 0, top: 18, width: 48, height: 3, fill: '#fb923c', originX: 'center', originY: 'center' }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'ring') item = new fabric.Circle({ left: baseLeft, top: baseTop, radius: 16, fill: 'transparent', stroke: '#38bdf8', strokeWidth: 4 });
      if (kind === 'mannequin') item = new fabric.Group([
        new fabric.Circle({ left: 0, top: -22, radius: 7, fill: '#f8fafc', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 0, top: -3, width: 18, height: 28, rx: 8, ry: 8, fill: '#f59e0b', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: -8, top: 18, width: 4, height: 20, fill: '#f8fafc', originX: 'center', originY: 'center', angle: 12 }),
        new fabric.Rect({ left: 8, top: 18, width: 4, height: 20, fill: '#f8fafc', originX: 'center', originY: 'center', angle: -12 }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'wall') item = new fabric.Group([
        new fabric.Rect({ left: -18, top: 0, width: 12, height: 34, rx: 6, ry: 6, fill: '#cbd5e1', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 0, top: 0, width: 12, height: 34, rx: 6, ry: 6, fill: '#94a3b8', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 18, top: 0, width: 12, height: 34, rx: 6, ry: 6, fill: '#cbd5e1', originX: 'center', originY: 'center' }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'target') item = new fabric.Group([
        new fabric.Circle({ left: 0, top: 0, radius: 18, fill: '#f8fafc', stroke: '#1d4ed8', strokeWidth: 3, originX: 'center', originY: 'center' }),
        new fabric.Circle({ left: 0, top: 0, radius: 10, fill: '#60a5fa', originX: 'center', originY: 'center' }),
        new fabric.Circle({ left: 0, top: 0, radius: 4, fill: '#dc2626', originX: 'center', originY: 'center' }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'bib') item = new fabric.Group([
        new fabric.Rect({ left: 0, top: 0, width: 28, height: 32, rx: 8, ry: 8, fill: '#a3e635', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: -7, top: -14, width: 8, height: 10, fill: '#0f172a', originX: 'center', originY: 'center', angle: 20 }),
        new fabric.Rect({ left: 7, top: -14, width: 8, height: 10, fill: '#0f172a', originX: 'center', originY: 'center', angle: -20 }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'zone') {
        if (variant === 'circle') item = new fabric.Circle({ left: baseLeft, top: baseTop, radius: 46, fill: 'rgba(14,165,233,0.18)', stroke: '#0ea5e9', strokeWidth: 2 });
        else if (variant === 'diamond') item = new fabric.Rect({ left: baseLeft, top: baseTop, width: 96, height: 96, fill: 'rgba(14,165,233,0.16)', stroke: '#0ea5e9', strokeWidth: 2, angle: 45 });
        else if (variant === 'lane') item = new fabric.Rect({ left: baseLeft, top: baseTop, width: 56, height: 162, fill: 'rgba(14,165,233,0.14)', stroke: '#38bdf8', strokeWidth: 2, strokeDashArray: [10, 6] });
        else if (variant === 'halfspace') item = new fabric.Polygon([
          { x: 0, y: 0 },
          { x: 86, y: 0 },
          { x: 126, y: 124 },
          { x: 40, y: 124 },
        ], { left: baseLeft, top: baseTop, fill: 'rgba(251,191,36,0.16)', stroke: '#fbbf24', strokeWidth: 2 });
        else item = new fabric.Rect({ left: baseLeft, top: baseTop, width: 130, height: 86, fill: 'rgba(14,165,233,0.18)', stroke: '#0ea5e9', strokeWidth: 2 });
      }
      if (kind === 'mini_goal') {
        const dims = variant === 'full' ? { width: 82, height: 42, strokeWidth: 2.4 } : variant === 'seven' ? { width: 68, height: 34, strokeWidth: 2.2 } : { width: 52, height: 26, strokeWidth: 2 };
        item = new fabric.Rect({ left: baseLeft, top: baseTop, width: dims.width, height: dims.height, fill: 'transparent', stroke: '#f8fafc', strokeWidth: dims.strokeWidth });
      }
      if (kind === 'gate') item = new fabric.Group([
        new fabric.Rect({ left: -18, top: 0, width: 4, height: 26, fill: '#f8fafc', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 18, top: 0, width: 4, height: 26, fill: '#f8fafc', originX: 'center', originY: 'center' }),
        new fabric.Rect({ left: 0, top: -11, width: 38, height: 4, fill: '#f8fafc', originX: 'center', originY: 'center' }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'slalom') item = new fabric.Group([
        new fabric.Circle({ left: -26, top: 0, radius: 5, fill: '#fb7185', originX: 'center', originY: 'center' }),
        new fabric.Circle({ left: -8, top: 0, radius: 5, fill: '#f59e0b', originX: 'center', originY: 'center' }),
        new fabric.Circle({ left: 10, top: 0, radius: 5, fill: '#38bdf8', originX: 'center', originY: 'center' }),
        new fabric.Circle({ left: 28, top: 0, radius: 5, fill: '#a3e635', originX: 'center', originY: 'center' }),
      ], { left: baseLeft, top: baseTop });
      if (kind === 'line') item = variant === 'dash'
        ? new fabric.Line([0, 0, 120, 0], { left: baseLeft, top: baseTop, stroke: '#f8fafc', strokeWidth: 3, strokeDashArray: [10, 7] })
        : variant === 'channel'
          ? new fabric.Group([
            new fabric.Line([0, 0, 0, 120], { stroke: '#38bdf8', strokeWidth: 3, strokeDashArray: [12, 8] }),
            new fabric.Line([58, 0, 58, 120], { stroke: '#38bdf8', strokeWidth: 3, strokeDashArray: [12, 8] }),
          ], { left: baseLeft, top: baseTop })
          : new fabric.Rect({ left: baseLeft, top: baseTop, width: 100, height: 2, fill: '#f8fafc' });
      if (kind === 'arrow') {
        if (variant === 'curve') {
          item = new fabric.Group([
            new fabric.Path('M 0 50 Q 55 0 120 40', { stroke: '#0ea5e9', fill: '', strokeWidth: 4 }),
            new fabric.Triangle({ left: 108, top: 31, width: 16, height: 16, angle: 112, fill: '#0ea5e9' }),
          ], { left: baseLeft, top: baseTop });
        } else if (variant === 'press') {
          item = new fabric.Group([
            new fabric.Path('M 0 54 C 30 26 54 18 82 18', { stroke: '#ef4444', fill: '', strokeWidth: 4 }),
            new fabric.Path('M 82 18 C 92 18 103 22 116 32', { stroke: '#ef4444', fill: '', strokeWidth: 4, strokeDashArray: [7, 5] }),
            new fabric.Triangle({ left: 108, top: 25, width: 16, height: 16, angle: 124, fill: '#ef4444' }),
          ], { left: baseLeft, top: baseTop });
        } else {
          item = new fabric.Group([
            new fabric.Line([0, 0, 100, 38], { stroke: '#0ea5e9', strokeWidth: 4 }),
            new fabric.Triangle({ left: 92, top: 29, width: 18, height: 18, angle: 120, fill: '#0ea5e9' }),
          ], { left: baseLeft, top: baseTop });
        }
      }
      if (!item) return;
      positionItem(item, baseLeft, baseTop);
      canvas.add(item);
      canvas.setActiveObject(item);
      canvas.renderAll();
      pushHistory();
      refreshLayerList();
      scheduleDraftSave();
      setStatus('Recurso colocado en la pizarra.');
    };

    const addTextToken = (label = 'Texto', options = {}) => {
      const fallbackPlacement = defaultPlacement();
      const text = new fabric.IText(String(label || 'Texto'), {
        fontSize: 22,
        fill: '#ffffff',
        fontWeight: '600',
      });
      positionItem(
        text,
        Number.isFinite(options.left) ? options.left : fallbackPlacement.left,
        Number.isFinite(options.top) ? options.top : fallbackPlacement.top,
      );
      canvas.add(text);
      canvas.setActiveObject(text);
      canvas.renderAll();
      pushHistory();
      refreshLayerList();
      scheduleDraftSave();
      setStatus('Texto colocado en la pizarra.');
    };

    const addIconifySvg = async (iconName, placement = {}) => {
      const name = String(iconName || '').trim();
      if (!name) return;
      try {
        const response = await fetch(`https://api.iconify.design/${encodeURIComponent(name)}.svg?height=80`);
        if (!response.ok) throw new Error('iconify_error');
        const svgText = await response.text();
        fabric.loadSVGFromString(svgText, (objects, options) => {
          if (!objects?.length) return;
          const iconObj = fabric.util.groupSVGElements(objects, options);
          iconObj.scaleToWidth(62);
          const fallbackPlacement = defaultPlacement();
          positionItem(
            iconObj,
            Number.isFinite(placement.left) ? placement.left : fallbackPlacement.left,
            Number.isFinite(placement.top) ? placement.top : fallbackPlacement.top,
          );
          canvas.add(iconObj);
          canvas.setActiveObject(iconObj);
          canvas.renderAll();
          pushHistory();
          refreshLayerList();
          scheduleDraftSave();
          setStatus(`Icono ${name} añadido.`);
        });
      } catch (error) {
        setStatus('No se pudo cargar el icono.', true);
      }
    };

    const placePendingInsert = async (pointer) => {
      if (!pendingInsert) return;
      const insert = pendingInsert;
      pendingInsert = null;
      const placement = clampPlacement(pointer?.x, pointer?.y);
      if (insert.kind === 'text') {
        addTextToken(insert.options.label || 'Texto', placement);
        return;
      }
      if (insert.kind === 'iconify') {
        await addIconifySvg(insert.options.iconName || '', placement);
        return;
      }
      addResource(insert.kind, { ...insert.options, ...placement });
    };

    const buildPlayerChip = (player, teamKey = 'local') => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'create-player-chip';
      button.dataset.playerName = safeText(player.name, '');
      button.dataset.playerNumber = safeText(player.number, '');
      const photo = safeText(player.photo_url, '');
      const side = document.createElement(photo ? 'img' : 'div');
      if (photo) {
        side.src = photo;
        side.alt = safeText(player.name, 'Jugador');
        side.loading = 'lazy';
      } else {
        side.className = 'fallback';
        side.textContent = (safeText(player.name, 'J') || 'J').slice(0, 1).toUpperCase();
      }
      const meta = document.createElement('p');
      meta.className = 'meta';
      meta.textContent = `#${safeText(player.number, '--')} ${safeText(player.name, 'Jugador')}`;
      button.appendChild(side);
      button.appendChild(meta);
      button.addEventListener('click', () => startQuickInsert('player', { team: teamKey, player }, `Haz clic en el campo para colocar a ${safeText(player.name, 'Jugador')}.`));
      return button;
    };
    const renderPlayerRepos = () => {
      if (localPlayersGrid) {
        localPlayersGrid.innerHTML = '';
        tacticalPlayers.forEach((player) => localPlayersGrid.appendChild(buildPlayerChip(player, 'local')));
      }
      if (rivalPlayersGrid) {
        rivalPlayersGrid.innerHTML = '';
        tacticalPlayers.forEach((player) => rivalPlayersGrid.appendChild(buildPlayerChip({ ...player, id: `r${player.id || ''}`, photo_url: '' }, 'rival')));
      }
    };
    const filterRepo = (grid, term) => {
      if (!grid) return;
      const query = String(term || '').toLowerCase().trim();
      grid.querySelectorAll('.create-player-chip').forEach((node) => {
        const text = `${node.dataset.playerName || ''} ${node.dataset.playerNumber || ''}`.toLowerCase();
        node.style.display = !query || text.includes(query) ? '' : 'none';
      });
    };

    const restoreInitialCanvas = () => {
      const raw = String(stateInput?.value || '').trim();
      if (!raw) return false;
      let parsed = null;
      try {
        parsed = JSON.parse(raw);
      } catch (error) {
        parsed = null;
      }
      if (!parsed || typeof parsed !== 'object') return false;
      currentFieldPreset = safeText(presetSelect?.value, 'full_pitch');
      setActiveByDataset(fieldPresetCards, 'fieldPreset', currentFieldPreset);
      canvas.__loading = true;
      canvas.loadFromJSON(parsed, () => {
        canvas.__loading = false;
        canvas.renderAll();
        refreshLayerList();
      });
      history = [JSON.stringify(parsed)];
      setStatus('Diseño táctico cargado.');
      return true;
    };

    const restoreDraft = () => {
      const draft = readStorageJson(draftKey, {});
      if (!draft || !draft.canvas_state) return false;
      restoreFormValues(createForm, draft.form_values || {});
      const palette = draft.team_palette || {};
      if (palette.local) teamPalette.local = { ...teamPalette.local, ...palette.local };
      if (palette.rival) teamPalette.rival = { ...teamPalette.rival, ...palette.rival };
      if (localNameInput) localNameInput.value = safeText(teamPalette.local.name, 'LOCAL');
      if (localPrimaryInput) localPrimaryInput.value = normalizeHex(teamPalette.local.primary, '#0f7ec7');
      if (localSecondaryInput) localSecondaryInput.value = normalizeHex(teamPalette.local.secondary, '#f8fafc');
      if (rivalNameInput) rivalNameInput.value = safeText(teamPalette.rival.name, 'RIVAL');
      if (rivalPrimaryInput) rivalPrimaryInput.value = normalizeHex(teamPalette.rival.primary, '#f59e0b');
      if (rivalSecondaryInput) rivalSecondaryInput.value = normalizeHex(teamPalette.rival.secondary, '#f8fafc');
      syncTeamPaletteFromInputs();
      snapEnabled = draft.snap_enabled !== false;
      if (snapBtn) snapBtn.textContent = snapEnabled ? 'Snap ON' : 'Snap OFF';
      currentFieldPreset = safeText(draft.field_preset, presetSelect?.value || 'full_pitch');
      currentFieldTheme = safeText(draft.field_theme, 'classic');
      currentFieldCamera = safeText(draft.field_camera, 'full');
      setActiveByDataset(fieldPresetCards, 'fieldPreset', currentFieldPreset);
      setActiveByDataset(fieldThemeChips, 'fieldTheme', currentFieldTheme);
      setFieldCameraActive(currentFieldCamera);
      if (presetSelect) presetSelect.value = currentFieldPreset;
      canvas.__loading = true;
      canvas.loadFromJSON(draft.canvas_state, () => {
        canvas.__loading = false;
        canvas.renderAll();
        refreshLayerList();
      });
      history = [JSON.stringify(draft.canvas_state)];
      setStatus(`Borrador recuperado (${safeText(draft.saved_at, 'sin fecha')}).`);
      return true;
    };

    const setFullscreen = async (enabled) => {
      if (!boardShell) return;
      try {
        if (enabled) {
          if (document.fullscreenElement !== boardShell && boardShell.requestFullscreen) await boardShell.requestFullscreen();
          boardShell.classList.add('is-fullscreen');
          if (feedbackButtons.fullscreen) feedbackButtons.fullscreen.classList.add('is-active');
          setStatus('Modo pantalla completa activado.');
        } else {
          if (document.fullscreenElement && document.exitFullscreen) await document.exitFullscreen();
          boardShell.classList.remove('is-fullscreen');
          if (feedbackButtons.fullscreen) feedbackButtons.fullscreen.classList.remove('is-active');
          setStatus('Modo pantalla completa desactivado.');
        }
        window.setTimeout(() => fitCanvas(), 140);
      } catch (error) {
        boardShell.classList.toggle('is-fullscreen', !!enabled);
        window.setTimeout(() => fitCanvas(), 140);
      }
    };

    canvas.on('path:created', () => { pushHistory(); refreshLayerList(); scheduleDraftSave(); });
    canvas.on('object:modified', () => { pushHistory(); refreshLayerList(); scheduleDraftSave(); });
    canvas.on('object:moving', (event) => { if (event?.target) applySnap(event.target); });
    canvas.on('mouse:down', (event) => {
      if (!pendingInsert) return;
      if (event?.target && event.target !== canvas.backgroundImage) {
        setStatus('Haz clic en una zona libre del campo para colocar el recurso.', true);
        return;
      }
      const pointer = canvas.getPointer(event.e);
      placePendingInsert(pointer);
    });
    canvas.on('object:added', () => {
      if (!canvas.__loading) {
        pushHistory();
        refreshLayerList();
        scheduleDraftSave();
      }
    });
    canvas.on('object:removed', () => { refreshLayerList(); scheduleDraftSave(); });
    canvas.on('selection:created', refreshLayerList);
    canvas.on('selection:updated', refreshLayerList);
    canvas.on('selection:cleared', refreshLayerList);

    document.getElementById('create-board-draw-btn')?.addEventListener('click', () => setMode(true));
    document.getElementById('create-board-select-btn')?.addEventListener('click', () => setMode(false));
    document.getElementById('create-board-select-btn')?.addEventListener('click', () => clearPendingInsert('Modo selección activo.'));
    toolSelectBtn?.addEventListener('click', () => setMode(false));
    toolSelectBtn?.addEventListener('click', () => clearPendingInsert('Modo selección activo.'));
    toolDrawBtn?.addEventListener('click', () => setMode(true));
    toolPlayerBtn?.addEventListener('click', () => startQuickInsert('player', {}, 'Haz clic en el campo para colocar un jugador.'));
    toolZoneBtn?.addEventListener('click', () => startQuickInsert('zone', {}, 'Haz clic en el campo para colocar una zona.'));
    toolArrowBtn?.addEventListener('click', () => startQuickInsert('arrow', {}, 'Haz clic en el campo para colocar una flecha.'));
    toolLineBtn?.addEventListener('click', () => startQuickInsert('line', {}, 'Haz clic en el campo para colocar una línea.'));
    toolTextBtn?.addEventListener('click', () => startQuickInsert('text', { label: 'Texto' }, 'Haz clic en el campo para colocar el texto.'));
    toolUndoBtn?.addEventListener('click', () => document.getElementById('create-board-undo-btn')?.click());
    toolDeleteBtn?.addEventListener('click', () => document.getElementById('create-board-delete-btn')?.click());
    toolColorRedBtn?.addEventListener('click', () => { if (colorInput) colorInput.value = '#e11d48'; canvas.freeDrawingBrush.color = '#e11d48'; setStatus('Color rojo aplicado.'); scheduleDraftSave(); });
    toolColorBlueBtn?.addEventListener('click', () => { if (colorInput) colorInput.value = '#2563eb'; canvas.freeDrawingBrush.color = '#2563eb'; setStatus('Color azul aplicado.'); scheduleDraftSave(); });
    toolColorWhiteBtn?.addEventListener('click', () => { if (colorInput) colorInput.value = '#f8fafc'; canvas.freeDrawingBrush.color = '#f8fafc'; setStatus('Color blanco aplicado.'); scheduleDraftSave(); });
    snapBtn?.addEventListener('click', () => {
      snapEnabled = !snapEnabled;
      snapBtn.textContent = snapEnabled ? 'Snap ON' : 'Snap OFF';
      setStatus(snapEnabled ? 'Snap activo.' : 'Snap desactivado.');
      scheduleDraftSave();
    });
    document.getElementById('create-board-player-btn')?.addEventListener('click', () => startQuickInsert('player', {}, 'Haz clic en el campo para colocar un jugador.'));
    document.getElementById('create-board-zone-btn')?.addEventListener('click', () => startQuickInsert('zone', {}, 'Haz clic en el campo para colocar una zona.'));
    document.getElementById('create-board-arrow-btn')?.addEventListener('click', () => startQuickInsert('arrow', {}, 'Haz clic en el campo para colocar una flecha.'));
    document.getElementById('create-board-text-btn')?.addEventListener('click', () => startQuickInsert('text', { label: 'Consigna' }, 'Haz clic en el campo para colocar el texto.'));
    document.getElementById('create-board-align-left-btn')?.addEventListener('click', () => alignSelected('left'));
    document.getElementById('create-board-align-center-btn')?.addEventListener('click', () => alignSelected('center'));
    document.getElementById('create-board-align-right-btn')?.addEventListener('click', () => alignSelected('right'));
    document.getElementById('create-board-align-top-btn')?.addEventListener('click', () => alignSelected('top'));
    document.getElementById('create-board-align-middle-btn')?.addEventListener('click', () => alignSelected('middle'));
    document.getElementById('create-board-align-bottom-btn')?.addEventListener('click', () => alignSelected('bottom'));
    document.getElementById('create-board-duplicate-btn')?.addEventListener('click', () => {
      const active = canvas.getActiveObject();
      if (!active) return;
      active.clone((cloned) => {
        cloned.set({ left: (active.left || 0) + 18, top: (active.top || 0) + 18 });
        canvas.add(cloned);
        canvas.setActiveObject(cloned);
        canvas.renderAll();
        pushHistory();
        refreshLayerList();
        scheduleDraftSave();
      });
    });
    document.getElementById('create-board-lock-btn')?.addEventListener('click', () => {
      const objects = getSelectedObjects();
      if (!objects.length) return;
      objects.forEach((obj) => setObjectLocked(obj, true));
      canvas.discardActiveObject();
      canvas.renderAll();
      refreshLayerList();
      scheduleDraftSave();
    });
    document.getElementById('create-board-unlock-btn')?.addEventListener('click', () => {
      const objects = canvas.getObjects().filter((obj) => obj.__locked);
      if (!objects.length) return;
      objects.forEach((obj) => setObjectLocked(obj, false));
      canvas.renderAll();
      refreshLayerList();
      scheduleDraftSave();
    });
    document.getElementById('create-board-delete-btn')?.addEventListener('click', () => {
      const active = canvas.getActiveObject();
      if (!active || active.__locked) return;
      canvas.remove(active);
      canvas.discardActiveObject();
      canvas.renderAll();
      pushHistory();
      refreshLayerList();
      scheduleDraftSave();
    });
    document.getElementById('create-board-front-btn')?.addEventListener('click', () => {
      const active = canvas.getActiveObject();
      if (!active) return;
      canvas.bringForward(active);
      canvas.renderAll();
      pushHistory();
      refreshLayerList();
      scheduleDraftSave();
    });
    document.getElementById('create-board-back-btn')?.addEventListener('click', () => {
      const active = canvas.getActiveObject();
      if (!active) return;
      canvas.sendBackwards(active);
      canvas.renderAll();
      pushHistory();
      refreshLayerList();
      scheduleDraftSave();
    });
    document.getElementById('create-board-undo-btn')?.addEventListener('click', () => {
      if (history.length <= 1) return;
      history.pop();
      const previous = history[history.length - 1];
      canvas.__loading = true;
      canvas.loadFromJSON(JSON.parse(previous), () => {
        canvas.__loading = false;
        canvas.renderAll();
        refreshLayerList();
        scheduleDraftSave();
      });
    });
    document.getElementById('create-board-clear-btn')?.addEventListener('click', () => applyFieldBackground(presetSelect?.value || 'full_pitch'));
    feedbackButtons.recoverDraft?.addEventListener('click', () => {
      if (!restoreDraft()) setStatus('No hay borrador para recuperar.', true);
    });
    feedbackButtons.discardDraft?.addEventListener('click', discardDraft);
    feedbackButtons.tools?.addEventListener('click', () => setToolsOpen(!(boardShell?.classList.contains('tools-open'))));
    feedbackButtons.menu?.addEventListener('click', () => {
      setToolsOpen(false);
      openFieldModal(false);
      setDockActive(feedbackButtons.project);
      setStatus('Modo presentación.');
    });
    feedbackButtons.board?.addEventListener('click', () => {
      setToolsOpen(!(boardShell?.classList.contains('tools-open')));
      setDockActive(feedbackButtons.board);
    });
    feedbackButtons.field?.addEventListener('click', () => {
      openFieldModal(true);
      setDockActive(feedbackButtons.field);
    });
    feedbackButtons.stadium?.addEventListener('click', () => {
      currentFieldCamera = 'stadium';
      setFieldCameraActive('stadium');
      applyFieldBackground(currentFieldPreset, { theme: currentFieldTheme, camera: 'stadium' });
      setDockActive(feedbackButtons.stadium);
      setStatus('Vista estadio 3D aplicada.');
    });
    feedbackButtons.save?.addEventListener('click', () => {
      setDockActive(feedbackButtons.save, true);
      setStatus('Guardando tarea...');
      createForm.requestSubmit();
    });
    feedbackButtons.share?.addEventListener('click', async () => {
      setDockActive(feedbackButtons.share, true);
      const dataUrl = canvas.toDataURL({ format: 'png', quality: 0.92, multiplier: 1 });
      if (navigator.clipboard?.writeText && dataUrl) {
        try {
          await navigator.clipboard.writeText(dataUrl);
          setStatus('Preview copiada al portapapeles y lista para compartir.');
        } catch (error) {
          downloadDataUrl(dataUrl, 'tactical-pad-preview.png');
          setStatus('No se pudo copiar; se descargó una preview PNG.');
        }
      } else {
        downloadDataUrl(dataUrl, 'tactical-pad-preview.png');
        setStatus('Preview descargada como PNG.');
      }
    });
    feedbackButtons.project?.addEventListener('click', () => {
      setDockActive(feedbackButtons.project, true);
      setStatus('Proyecto activo: creación de tarea.');
    });
    feedbackButtons.fullscreen?.addEventListener('click', () => {
      const willEnable = !(boardShell?.classList.contains('is-fullscreen'));
      setDockActive(feedbackButtons.fullscreen);
      setFullscreen(willEnable);
    });
    fieldCloseBtn?.addEventListener('click', () => openFieldModal(false));
    fieldCancelBtn?.addEventListener('click', () => openFieldModal(false));
    fieldApplyBtn?.addEventListener('click', () => openFieldModal(false));
    fieldModal?.addEventListener('click', (event) => { if (event.target === fieldModal) openFieldModal(false); });
    fieldPresetCards.forEach((card) => card.addEventListener('click', () => applyFieldBackground(card.dataset.fieldPreset || 'full_pitch', { theme: currentFieldTheme, camera: currentFieldCamera })));
    fieldThemeChips.forEach((chip) => chip.addEventListener('click', () => applyFieldBackground(currentFieldPreset, { theme: chip.dataset.fieldTheme || 'classic', camera: currentFieldCamera })));
    fieldCameraChips.forEach((chip) => chip.addEventListener('click', () => {
      const camera = String(chip.dataset.fieldCamera || 'full');
      setFieldCameraActive(camera);
      applyFieldBackground(currentFieldPreset, { theme: currentFieldTheme, camera });
    }));
    document.addEventListener('fullscreenchange', () => {
      if (!boardShell) return;
      const active = document.fullscreenElement === boardShell;
      boardShell.classList.toggle('is-fullscreen', active);
      if (feedbackButtons.fullscreen) feedbackButtons.fullscreen.classList.toggle('is-active', active);
      window.setTimeout(() => fitCanvas(), 120);
    });
    catalogTabs.forEach((tab) => tab.addEventListener('click', () => applyCatalogFilter(tab.dataset.cat || 'all')));
    localSearchInput?.addEventListener('input', () => filterRepo(localPlayersGrid, localSearchInput.value));
    rivalSearchInput?.addEventListener('input', () => filterRepo(rivalPlayersGrid, rivalSearchInput.value));
    [localNameInput, rivalNameInput, localPrimaryInput, localSecondaryInput, rivalPrimaryInput, rivalSecondaryInput]
      .filter(Boolean)
      .forEach((node) => node.addEventListener('input', () => {
        syncTeamPaletteFromInputs();
        scheduleDraftSave();
      }));
    resourceGrid?.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-resource]');
      if (!btn) return;
      const label = safeText(btn.textContent, 'recurso').toLowerCase();
      startQuickInsert(
        btn.dataset.resource,
        { variant: btn.dataset.variant || '', team: btn.dataset.team || 'local' },
        `Haz clic en el campo para colocar ${label}.`,
      );
    });
    iconifyGrid?.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-iconify]');
      if (btn) startQuickInsert('iconify', { iconName: btn.dataset.iconify || '' }, `Haz clic en el campo para colocar ${safeText(btn.dataset.label, 'el icono').toLowerCase()}.`);
    });
    iconifySearch?.addEventListener('input', () => {
      const term = String(iconifySearch.value || '').toLowerCase().trim();
      iconifyGrid?.querySelectorAll('[data-iconify]').forEach((btn) => {
        const text = `${btn.dataset.iconify || ''} ${btn.dataset.label || ''}`.toLowerCase();
        btn.classList.toggle('is-hidden', !!term && !text.includes(term));
      });
    });
    colorInput?.addEventListener('input', () => {
      const value = colorInput.value || '#e11d48';
      canvas.freeDrawingBrush.color = value;
      const active = canvas.getActiveObject();
      if (active?.set) {
        active.set('stroke', value);
        if (active.type === 'i-text') active.set('fill', value);
        canvas.renderAll();
      }
      scheduleDraftSave();
    });
    strokeInput?.addEventListener('input', () => {
      const value = parseInt(strokeInput.value || '4', 10);
      canvas.freeDrawingBrush.width = Math.max(1, Math.min(value || 4, 14));
      scheduleDraftSave();
    });
    presetSelect?.addEventListener('change', () => applyFieldBackground(presetSelect.value || 'full_pitch'));
    createForm.querySelectorAll('input[name], select[name], textarea[name]').forEach((field) => {
      if (String(field.name || '').startsWith('draw_canvas_') || field.name === 'csrfmiddlewaretoken' || field.name === 'planner_action') return;
      field.addEventListener('input', scheduleDraftSave);
      field.addEventListener('change', scheduleDraftSave);
    });
    createForm.addEventListener('submit', () => {
      const serialized = serializeCanvas();
      if (stateInput) stateInput.value = JSON.stringify(serialized);
      if (widthInput) widthInput.value = String(Math.round(canvas.getWidth()));
      if (heightInput) heightInput.value = String(Math.round(canvas.getHeight()));
      if (previewInput) previewInput.value = canvas.toDataURL({ format: 'png', quality: 0.92, multiplier: 1 });
      writeSessionValue(submitMarkerKey, '1');
      saveDraft('Último borrador sincronizado antes del envío.');
    });
    let resizeTimer = null;
    window.addEventListener('resize', () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        fitCanvas();
        refreshLayerList();
        setStatus('Pizarra reajustada.');
      }, 180);
    });

    const restored = restoreDraft();
    if (!restored && !restoreInitialCanvas()) applyFieldBackground(presetSelect?.value || 'full_pitch');
    renderPlayerRepos();
    applyCatalogFilter('all');
    syncTeamPaletteFromInputs();
    setDockActive(feedbackButtons.project);
    setToolsOpen(false);
    setMode(false);
    refreshLayerList();
  };
})();
