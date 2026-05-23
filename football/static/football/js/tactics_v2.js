(function () {
  const safeText = (value, fallback = '') => String(value ?? '').trim() || fallback;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const getCookie = (name) => {
    try {
      const raw = String(document.cookie || '');
      const parts = raw.split(';').map((x) => x.trim());
      for (const part of parts) {
        if (!part) continue;
        const idx = part.indexOf('=');
        if (idx < 0) continue;
        const k = part.slice(0, idx).trim();
        const v = part.slice(idx + 1);
        if (k === name) return decodeURIComponent(v);
      }
    } catch (e) { /* ignore */ }
    return '';
  };

  const downloadText = (filename, text) => {
    const blob = new Blob([text], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const downloadDataUrl = (filename, dataUrl) => {
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const setStatus = (el, msg, isError = false) => {
    if (!el) return;
    el.textContent = safeText(msg, '—');
    el.classList.toggle('is-error', !!isError);
  };

  const ensureFabric = async () => {
    if (window.fabric) return;
    // Espera a que el script `defer` haya ejecutado.
    await new Promise((resolve) => setTimeout(resolve, 0));
    if (window.fabric) return;
    await new Promise((resolve) => setTimeout(resolve, 80));
  };

  const normalizeCanvasJson = (json) => {
    const obj = json && typeof json === 'object' ? json : {};
    // Garantiza campos básicos para loader legacy.
    if (!obj.objects) obj.objects = [];
    if (!obj.version) obj.version = '5';
    return obj;
  };

  const buildPitchBackground = async (canvas, { width, height }) => {
    // Césped de calidad: textura tile + franjas + líneas SVG.
    const w = Math.max(1, Number(width) || 1);
    const h = Math.max(1, Number(height) || 1);

    // 1) Textura base (tile).
    try {
      const baseRect = new window.fabric.Rect({
        left: 0,
        top: 0,
        width: w,
        height: h,
        selectable: false,
        evented: false,
        hoverCursor: 'default',
      });

      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        try {
          const patternSourceCanvas = document.createElement('canvas');
          const ctx = patternSourceCanvas.getContext('2d');
          if (!ctx) return;
          patternSourceCanvas.width = img.width;
          patternSourceCanvas.height = img.height;
          ctx.drawImage(img, 0, 0);
          const pattern = new window.fabric.Pattern({ source: patternSourceCanvas, repeat: 'repeat' });
          baseRect.set('fill', pattern);
          baseRect.__t2Kind = 'pitch_grass';
          canvas.add(baseRect);
          baseRect.sendToBack();

          // 2) Franjas sutiles encima para profundidad.
          const stripeCount = 12;
          const stripeW = w / stripeCount;
          for (let i = 0; i < stripeCount; i += 1) {
            const alpha = (i % 2 === 0) ? 0.10 : 0.04;
            const stripe = new window.fabric.Rect({
              left: i * stripeW,
              top: 0,
              width: Math.ceil(stripeW + 1),
              height: h,
              fill: `rgba(22,163,74,${alpha})`,
              selectable: false,
              evented: false,
              hoverCursor: 'default',
            });
            stripe.__t2Kind = 'pitch_stripe';
            canvas.add(stripe);
            stripe.sendToBack();
          }
          baseRect.sendToBack();
          canvas.requestRenderAll();
        } catch (e) { /* ignore */ }
      };
      img.src = '/static/football/images/surfaces/grass_uefa_b_tile.png';
    } catch (e) { /* ignore */ }

    // 3) Líneas de campo (SVG referencia).
    const svgUrl = '/static/football/images/surfaces/references/football_pitch_metric_reference.svg';
    return new Promise((resolve) => {
      try {
        window.fabric.loadSVGFromURL(svgUrl, (objects, options) => {
          try {
            const group = window.fabric.util.groupSVGElements(objects, options);
            group.set({ selectable: false, evented: false, hoverCursor: 'default' });
            group.__t2Kind = 'pitch_lines';
            const scale = Math.min(w / (group.width || w), h / (group.height || h));
            group.scale(scale);
            group.left = (w - (group.getScaledWidth ? group.getScaledWidth() : (group.width * scale))) / 2;
            group.top = (h - (group.getScaledHeight ? group.getScaledHeight() : (group.height * scale))) / 2;
            canvas.add(group);
            try { group.sendToBack(); } catch (e2) { /* ignore */ }
            try {
              const grass = canvas.getObjects().find((o) => o && o.__t2Kind === 'pitch_grass');
              if (grass) grass.sendToBack();
            } catch (e3) { /* ignore */ }
            resolve(group);
          } catch (e) {
            resolve(null);
          }
        });
      } catch (e) {
        resolve(null);
      }
    });
  };

  const makeToken = (kind) => {
    const isBall = kind === 'ball';
    const isHome = kind === 'home';
    const fill = isBall ? '#f8fafc' : isHome ? '#16a34a' : '#ef4444';
    const stroke = isBall ? 'rgba(15,23,42,0.55)' : 'rgba(255,255,255,0.74)';
    const radius = isBall ? 12 : 20;
    const circle = new window.fabric.Circle({
      radius,
      fill,
      stroke,
      strokeWidth: isBall ? 2 : 2,
      originX: 'center',
      originY: 'center',
      shadow: new window.fabric.Shadow({ color: 'rgba(2,6,23,0.35)', blur: 10, offsetX: 0, offsetY: 4 }),
    });
    let text = null;
    if (!isBall) {
      text = new window.fabric.Text('0', {
        fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, sans-serif',
        fontSize: 16,
        fill: '#0b1220',
        fontWeight: '800',
        originX: 'center',
        originY: 'center',
        selectable: false,
        evented: false,
      });
    }
    if (text) {
      const tag = new window.fabric.Text('', {
        fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, sans-serif',
        fontSize: 11,
        fill: 'rgba(248,250,252,0.92)',
        fontWeight: '800',
        originX: 'center',
        originY: 'center',
        top: -36,
        selectable: false,
        evented: false,
        shadow: new window.fabric.Shadow({ color: 'rgba(2,6,23,0.45)', blur: 6, offsetX: 0, offsetY: 2 }),
      });
      const grp = new window.fabric.Group([circle, text, tag], { left: 120, top: 120, hasControls: false });
      grp.__t2Kind = 'player_token';
      grp.__t2Team = isHome ? 'home' : 'away';
      grp.__t2Number = 0;
      grp.__t2Name = '';
      return grp;
    }
    return circle;
  };

  const setTokenMeta = (token, { number, name }) => {
    if (!token || token.__t2Kind !== 'player_token') return;
    const n = Number.isFinite(Number(number)) ? Number(number) : parseInt(String(number || '0'), 10);
    const safeN = Number.isFinite(n) ? clamp(Math.round(n), 0, 99) : 0;
    const safeName = safeText(name, '').slice(0, 22);
    token.__t2Number = safeN;
    token.__t2Name = safeName;
    try {
      const objs = typeof token.getObjects === 'function' ? token.getObjects() : [];
      const numText = objs.find((o) => o && o.type === 'text' && Number(o.fontSize) === 16);
      if (numText) numText.text = String(safeN || '');
      const tag = objs.find((o) => o && o.type === 'text' && Number(o.fontSize) === 11);
      if (tag) tag.text = safeName ? safeName.toUpperCase() : '';
    } catch (e) { /* ignore */ }
  };

  const makeArrow = ({ x1, y1, x2, y2, color = 'rgba(244,180,0,0.95)', width = 4 }) => {
    const line = new window.fabric.Line([x1, y1, x2, y2], {
      stroke: color,
      strokeWidth: width,
      selectable: false,
      evented: false,
      strokeLineCap: 'round',
    });
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const headLen = 14 + width * 1.3;
    const tri = new window.fabric.Triangle({
      left: x2,
      top: y2,
      originX: 'center',
      originY: 'center',
      angle: (angle * 180) / Math.PI + 90,
      width: headLen,
      height: headLen,
      fill: color,
      selectable: false,
      evented: false,
    });
    const grp = new window.fabric.Group([line, tri], { hasControls: false, hasBorders: false });
    grp.__t2Kind = 'arrow';
    return grp;
  };

  const makeZoneRect = ({ x, y, w, h }) => {
    const rect = new window.fabric.Rect({
      left: x,
      top: y,
      width: w,
      height: h,
      fill: 'rgba(34,211,238,0.14)',
      stroke: 'rgba(34,211,238,0.60)',
      strokeWidth: 2,
      rx: 10,
      ry: 10,
    });
    rect.__t2Kind = 'zone';
    return rect;
  };

  const makeCone = ({ x, y }) => {
    const tri = new window.fabric.Triangle({
      left: x,
      top: y,
      originX: 'center',
      originY: 'center',
      width: 22,
      height: 22,
      fill: 'rgba(244,180,0,0.95)',
      stroke: 'rgba(15,23,42,0.28)',
      strokeWidth: 1,
      shadow: new window.fabric.Shadow({ color: 'rgba(2,6,23,0.35)', blur: 10, offsetX: 0, offsetY: 4 }),
    });
    tri.__t2Kind = 'cone';
    return tri;
  };

  const makeGoal = ({ x, y }) => {
    const frame = new window.fabric.Rect({
      left: x,
      top: y,
      originX: 'center',
      originY: 'center',
      width: 64,
      height: 34,
      fill: 'rgba(255,255,255,0.02)',
      stroke: 'rgba(248,250,252,0.86)',
      strokeWidth: 2,
      rx: 6,
      ry: 6,
    });
    const back = new window.fabric.Rect({
      left: x + 10,
      top: y + 10,
      originX: 'center',
      originY: 'center',
      width: 64,
      height: 34,
      fill: 'rgba(248,250,252,0.04)',
      stroke: 'rgba(248,250,252,0.22)',
      strokeWidth: 1,
      rx: 6,
      ry: 6,
    });
    const grp = new window.fabric.Group([back, frame], { hasControls: false });
    grp.__t2Kind = 'goal';
    return grp;
  };

  const init = async () => {
    const root = document.getElementById('t2-root');
    if (!root) return;
    const statusEl = document.getElementById('t2-status');
    const canvasEl = document.getElementById('t2-canvas');
    const clipsEl = document.getElementById('t2-clips');

    const clipsUrl = safeText(root.dataset.clipsUrl);
    const clipSaveUrl = safeText(root.dataset.clipSaveUrl);
    const backUrl = safeText(root.dataset.backUrl, '/');

    const backBtn = document.getElementById('t2-back');
    const modeMoveBtn = document.getElementById('t2-mode-move');
    const modeDrawBtn = document.getElementById('t2-mode-draw');
    const toolArrowBtn = document.getElementById('t2-tool-arrow');
    const toolZoneBtn = document.getElementById('t2-tool-zone');
    const toolConeBtn = document.getElementById('t2-tool-cone');
    const toolGoalBtn = document.getElementById('t2-tool-goal');
    const toolTextBtn = document.getElementById('t2-tool-text');
    const deleteBtn = document.getElementById('t2-delete');
    const addHomeBtn = document.getElementById('t2-add-home');
    const addAwayBtn = document.getElementById('t2-add-away');
    const addBallBtn = document.getElementById('t2-add-ball');
    const undoBtn = document.getElementById('t2-undo');
    const redoBtn = document.getElementById('t2-redo');
    const captureStepBtn = document.getElementById('t2-capture-step');
    const stepPrevBtn = document.getElementById('t2-step-prev');
    const stepNextBtn = document.getElementById('t2-step-next');
    const stepsStatusEl = document.getElementById('t2-steps-status');
    const exportPngBtn = document.getElementById('t2-export-png');
    const exportJsonBtn = document.getElementById('t2-export-json');
    const saveClipBtn = document.getElementById('t2-save-clip');
    const clearBtn = document.getElementById('t2-clear');
    const clipNameEl = document.getElementById('t2-clip-name');
    const clipFolderEl = document.getElementById('t2-clip-folder');

    backBtn?.addEventListener('click', () => { window.location.href = backUrl; });

    await ensureFabric();
    if (!window.fabric) {
      setStatus(statusEl, 'No se pudo cargar Fabric. Recarga la página.', true);
      return;
    }

    const resizeToStage = () => {
      const stage = canvasEl?.parentElement;
      if (!stage) return { w: 900, h: 560 };
      const rect = stage.getBoundingClientRect();
      const w = Math.max(320, Math.floor(rect.width));
      const h = Math.max(320, Math.floor(rect.height));
      return { w, h };
    };

    const { w: initialW, h: initialH } = resizeToStage();
    const canvas = new window.fabric.Canvas(canvasEl, {
      width: initialW,
      height: initialH,
      preserveObjectStacking: true,
      selection: true,
      fireRightClick: true,
      stopContextMenu: true,
    });

    // Fondo + grid simple
    canvas.setBackgroundColor('rgba(2,6,23,0.10)', canvas.renderAll.bind(canvas));
    await buildPitchBackground(canvas, { width: initialW, height: initialH });
    canvas.renderAll();

    // Historial simple (JSON).
    const history = { past: [], future: [], lock: false };
    const snapshot = () => {
      const json = normalizeCanvasJson(canvas.toDatalessJSON());
      history.past.push(json);
      history.future = [];
      if (history.past.length > 50) history.past.shift();
      undoBtn && (undoBtn.disabled = history.past.length < 2);
      redoBtn && (redoBtn.disabled = history.future.length === 0);
    };
    const restore = async (json) => {
      history.lock = true;
      await new Promise((resolve) => {
        canvas.loadFromJSON(json, () => {
          // Garantiza que el fondo (SVG) se quede atrás.
          try {
            canvas.getObjects().forEach((obj) => {
              if (obj && obj.evented === false && obj.selectable === false) obj.sendToBack();
            });
          } catch (e) { /* ignore */ }
          canvas.renderAll();
          resolve();
        });
      });
      history.lock = false;
      undoBtn && (undoBtn.disabled = history.past.length < 2);
      redoBtn && (redoBtn.disabled = history.future.length === 0);
    };

    const pushSnapshotThrottled = (() => {
      let t = null;
      return () => {
        if (history.lock) return;
        if (t) return;
        t = window.setTimeout(() => {
          t = null;
          try { snapshot(); } catch (e) { /* ignore */ }
        }, 180);
      };
    })();

    canvas.on('object:added', pushSnapshotThrottled);
    canvas.on('object:modified', pushSnapshotThrottled);
    canvas.on('object:removed', pushSnapshotThrottled);

    snapshot(); // estado inicial

    // --- Pasos (clips multi-frame) ---
    let steps = [];
    let activeStepIndex = 0;
    const updateStepsUi = () => {
      const total = steps.length || 0;
      const idx = clamp(activeStepIndex + 1, 1, Math.max(1, total));
      if (stepsStatusEl) stepsStatusEl.textContent = `Pasos: ${idx}/${Math.max(1, total)}`;
      if (stepPrevBtn) stepPrevBtn.disabled = activeStepIndex <= 0;
      if (stepNextBtn) stepNextBtn.disabled = activeStepIndex >= (total - 1);
    };
    const captureStep = () => {
      const json = normalizeCanvasJson(canvas.toDatalessJSON());
      const w = Math.max(1, Math.round(canvas.getWidth() || 0));
      const h = Math.max(1, Math.round(canvas.getHeight() || 0));
      return {
        title: `Paso ${steps.length + 1}`,
        duration: 3,
        canvas_state: json,
        canvas_width: w,
        canvas_height: h,
        preset: 'full_pitch',
        orientation: 'landscape',
        grass_style: 'grass_uefa_b_tile',
        zoom: 1,
      };
    };

    const syncActiveStepFromCanvas = () => {
      if (!steps.length) {
        steps = [captureStep()];
        activeStepIndex = 0;
        updateStepsUi();
        return;
      }
      const prev = steps[activeStepIndex] || null;
      const next = captureStep();
      // Mantén metadatos del paso actual si existían.
      if (prev && typeof prev === 'object') {
        next.title = safeText(prev.title, next.title);
        next.duration = Number.isFinite(Number(prev.duration)) ? Number(prev.duration) : next.duration;
        next.preset = safeText(prev.preset, next.preset);
        next.orientation = safeText(prev.orientation, next.orientation);
        next.grass_style = safeText(prev.grass_style, next.grass_style);
        next.zoom = Number.isFinite(Number(prev.zoom)) ? Number(prev.zoom) : next.zoom;
      }
      steps[activeStepIndex] = next;
    };
    const loadStep = async (step) => {
      const state = step?.canvas_state && typeof step.canvas_state === 'object' ? step.canvas_state : null;
      if (!state) return;
      await restore(state);
    };

    steps = [captureStep()];
    activeStepIndex = 0;
    updateStepsUi();

    // --- Herramientas ---
    let tool = 'move'; // move|draw|arrow|zone|cone|goal|text
    const setTool = (next) => {
      tool = safeText(next, 'move');
      canvas.isDrawingMode = tool === 'draw';
      canvas.selection = tool === 'move';
      if (canvas.isDrawingMode) {
        canvas.freeDrawingBrush.width = 4;
        canvas.freeDrawingBrush.color = 'rgba(244,180,0,0.92)';
      }
      const map = [
        [modeMoveBtn, tool === 'move'],
        [modeDrawBtn, tool === 'draw'],
        [toolArrowBtn, tool === 'arrow'],
        [toolZoneBtn, tool === 'zone'],
        [toolConeBtn, tool === 'cone'],
        [toolGoalBtn, tool === 'goal'],
        [toolTextBtn, tool === 'text'],
      ];
      map.forEach(([btn, active]) => { if (btn) btn.classList.toggle('primary', !!active); });
      setStatus(statusEl, `Herramienta: ${tool}`);
    };
    modeMoveBtn?.addEventListener('click', () => setTool('move'));
    modeDrawBtn?.addEventListener('click', () => setTool('draw'));
    toolArrowBtn?.addEventListener('click', () => setTool('arrow'));
    toolZoneBtn?.addEventListener('click', () => setTool('zone'));
    toolConeBtn?.addEventListener('click', () => setTool('cone'));
    toolGoalBtn?.addEventListener('click', () => setTool('goal'));
    toolTextBtn?.addEventListener('click', () => setTool('text'));
    setTool('move');

    const addTokenAtCenter = (kind) => {
      const token = makeToken(kind);
      if (token.left == null) token.left = canvas.getWidth() / 2;
      if (token.top == null) token.top = canvas.getHeight() / 2;
      canvas.add(token);
      try { token.bringToFront(); } catch (e) { /* ignore */ }
      canvas.setActiveObject(token);
      if (token && token.__t2Kind === 'player_token') {
        try {
          const sameTeam = canvas.getObjects().filter((o) => o && o.__t2Kind === 'player_token' && o.__t2Team === token.__t2Team);
          setTokenMeta(token, { number: sameTeam.length, name: '' });
        } catch (e) { /* ignore */ }
      }
      canvas.renderAll();
      snapshot();
    };

    addHomeBtn?.addEventListener('click', () => addTokenAtCenter('home'));
    addAwayBtn?.addEventListener('click', () => addTokenAtCenter('away'));
    addBallBtn?.addEventListener('click', () => addTokenAtCenter('ball'));

    // Edit rápido de ficha (doble click): nombre + dorsal.
    canvas.on('mouse:dblclick', (opt) => {
      try {
        const target = opt?.target;
        if (!target || target.__t2Kind !== 'player_token') return;
        const currentName = safeText(target.__t2Name, '');
        const currentNumber = Number(target.__t2Number || 0) || 0;
        const nextName = window.prompt('Nombre / apodo (máx 22):', currentName) ?? currentName;
        const nextNumRaw = window.prompt('Dorsal (0-99):', String(currentNumber)) ?? String(currentNumber);
        setTokenMeta(target, { name: nextName, number: nextNumRaw });
        canvas.requestRenderAll();
        snapshot();
      } catch (e) { /* ignore */ }
    });

    // Borrar selección
    deleteBtn?.addEventListener('click', () => {
      const active = canvas.getActiveObjects ? canvas.getActiveObjects() : [];
      if (!active || !active.length) {
        setStatus(statusEl, 'No hay selección para borrar.', true);
        return;
      }
      active.forEach((obj) => {
        if (!obj) return;
        if (obj.evented === false && obj.selectable === false) return;
        canvas.remove(obj);
      });
      canvas.discardActiveObject();
      canvas.requestRenderAll();
      snapshot();
      setStatus(statusEl, 'Borrado.');
    });

    // Interacción de herramientas (unificada)
    let zoneDrag = null;
    let arrowStart = null;
    canvas.on('mouse:down', (opt) => {
      if (!opt || !opt.e) return;
      const p = canvas.getPointer(opt.e);
      if (tool === 'zone') {
        const rect = makeZoneRect({ x: p.x, y: p.y, w: 1, h: 1 });
        canvas.add(rect);
        zoneDrag = { x0: p.x, y0: p.y, rect };
        canvas.requestRenderAll();
        return;
      }
      if (tool === 'arrow') {
        arrowStart = { x: p.x, y: p.y };
        return;
      }
      if (tool === 'cone') {
        canvas.add(makeCone({ x: p.x, y: p.y }));
        canvas.requestRenderAll();
        snapshot();
        return;
      }
      if (tool === 'goal') {
        canvas.add(makeGoal({ x: p.x, y: p.y }));
        canvas.requestRenderAll();
        snapshot();
        return;
      }
      if (tool === 'text') {
        const t = window.prompt('Texto:', '') || '';
        if (safeText(t)) {
          const txt = new window.fabric.Textbox(String(t).slice(0, 60), {
            left: p.x,
            top: p.y,
            originX: 'left',
            originY: 'top',
            fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, sans-serif',
            fontSize: 18,
            fill: 'rgba(248,250,252,0.95)',
            fontWeight: '800',
            shadow: new window.fabric.Shadow({ color: 'rgba(2,6,23,0.45)', blur: 8, offsetX: 0, offsetY: 3 }),
          });
          txt.__t2Kind = 'text';
          canvas.add(txt);
          canvas.requestRenderAll();
          snapshot();
        }
      }
    });
    canvas.on('mouse:move', (opt) => {
      if (!zoneDrag || tool !== 'zone') return;
      if (!opt || !opt.e) return;
      const p = canvas.getPointer(opt.e);
      const rect = zoneDrag.rect;
      if (!rect) return;
      rect.set({
        left: Math.min(zoneDrag.x0, p.x),
        top: Math.min(zoneDrag.y0, p.y),
        width: Math.abs(p.x - zoneDrag.x0),
        height: Math.abs(p.y - zoneDrag.y0),
      });
      rect.setCoords();
      canvas.requestRenderAll();
    });
    canvas.on('mouse:up', (opt) => {
      if (tool === 'zone' && zoneDrag) {
        zoneDrag = null;
        snapshot();
        return;
      }
      if (tool === 'arrow' && arrowStart && opt && opt.e) {
        const p = canvas.getPointer(opt.e);
        const dx = Math.abs(p.x - arrowStart.x);
        const dy = Math.abs(p.y - arrowStart.y);
        if (dx + dy >= 8) {
          const arrow = makeArrow({ x1: arrowStart.x, y1: arrowStart.y, x2: p.x, y2: p.y });
          canvas.add(arrow);
          canvas.requestRenderAll();
          snapshot();
        }
        arrowStart = null;
      }
    });

    captureStepBtn?.addEventListener('click', () => {
      steps.push(captureStep());
      activeStepIndex = steps.length - 1;
      updateStepsUi();
      setStatus(statusEl, `Paso capturado: ${activeStepIndex + 1}/${steps.length}`);
    });
    stepPrevBtn?.addEventListener('click', async () => {
      if (activeStepIndex <= 0) return;
      // Antes de cambiar, guarda el estado actual en el paso activo.
      try { syncActiveStepFromCanvas(); } catch (e) { /* ignore */ }
      activeStepIndex -= 1;
      await loadStep(steps[activeStepIndex]);
      updateStepsUi();
    });
    stepNextBtn?.addEventListener('click', async () => {
      if (activeStepIndex >= steps.length - 1) return;
      // Antes de cambiar, guarda el estado actual en el paso activo.
      try { syncActiveStepFromCanvas(); } catch (e) { /* ignore */ }
      activeStepIndex += 1;
      await loadStep(steps[activeStepIndex]);
      updateStepsUi();
    });

    undoBtn && (undoBtn.disabled = true);
    redoBtn && (redoBtn.disabled = true);
    undoBtn?.addEventListener('click', async () => {
      if (history.past.length < 2) return;
      const current = history.past.pop();
      history.future.unshift(current);
      const prev = history.past[history.past.length - 1];
      await restore(prev);
    });
    redoBtn?.addEventListener('click', async () => {
      if (!history.future.length) return;
      const next = history.future.shift();
      history.past.push(next);
      await restore(next);
    });

	    exportJsonBtn?.addEventListener('click', () => {
	      const json = normalizeCanvasJson(canvas.toDatalessJSON());
	      const payload = { version: 2, canvas: json, steps: steps.slice(), active_step: activeStepIndex };
	      downloadText('tactica-v2.json', JSON.stringify(payload, null, 2));
	      setStatus(statusEl, 'JSON exportado.');
	    });

    exportPngBtn?.addEventListener('click', () => {
      const dataUrl = canvas.toDataURL({ format: 'png', multiplier: 2 });
      downloadDataUrl('tactica-v2.png', dataUrl);
      setStatus(statusEl, 'PNG exportado.');
    });

    clearBtn?.addEventListener('click', async () => {
      const ok = window.confirm('¿Limpiar la pizarra?');
      if (!ok) return;
      // Reset: recarga el fondo y limpia objetos interactivos.
      history.lock = true;
      const keep = canvas.getObjects().filter((obj) => obj && obj.evented === false && obj.selectable === false);
      canvas.clear();
      canvas.setBackgroundColor('rgba(2,6,23,0.10)', canvas.renderAll.bind(canvas));
      keep.forEach((obj) => canvas.add(obj));
      keep.forEach((obj) => obj.sendToBack());
      canvas.renderAll();
	      history.past = [];
	      history.future = [];
	      history.lock = false;
	      snapshot();
	      steps = [captureStep()];
	      activeStepIndex = 0;
	      updateStepsUi();
	      setStatus(statusEl, 'Pizarra limpia.');
	    });

    const buildClipSteps = () => {
      return steps.slice();
    };

    const renderClips = (items) => {
      if (!clipsEl) return;
      clipsEl.innerHTML = '';
      const list = Array.isArray(items) ? items : [];
      if (!list.length) {
        const empty = document.createElement('div');
        empty.className = 't2-status';
        empty.textContent = 'No hay clips todavía.';
        clipsEl.appendChild(empty);
        return;
      }
      list.forEach((item) => {
        const row = document.createElement('div');
        row.className = 't2-item';
        const meta = document.createElement('div');
        meta.className = 'meta';
        const title = document.createElement('strong');
        title.textContent = safeText(item?.name, 'Clip');
        const sub = document.createElement('span');
        const folder = safeText(item?.folder, '');
        sub.textContent = folder ? `Carpeta: ${folder}` : '—';
        meta.appendChild(title);
        meta.appendChild(sub);
        const actions = document.createElement('div');
        actions.className = 'actions';
        const openBtn = document.createElement('button');
        openBtn.className = 't2-btn';
        openBtn.type = 'button';
        openBtn.textContent = 'Abrir';
	        openBtn.addEventListener('click', async () => {
	          const clipSteps = Array.isArray(item?.steps) ? item.steps : [];
	          const first = clipSteps[0] || null;
	          const state = first?.canvas_state && typeof first.canvas_state === 'object' ? first.canvas_state : null;
	          if (!state || !clipSteps.length) {
	            setStatus(statusEl, 'Este clip no tiene canvas_state en el paso 1.', true);
	            return;
	          }
	          // Asegura que el canvas se adapte al contenedor actual antes de cargar.
	          const { w, h } = resizeToStage();
	          canvas.setWidth(w);
	          canvas.setHeight(h);
	          steps = clipSteps.slice();
	          activeStepIndex = 0;
	          await loadStep(steps[0]);
	          updateStepsUi();
	          setStatus(statusEl, `Clip cargado: ${safeText(item?.name, '—')}`);
	        });
        actions.appendChild(openBtn);
        row.appendChild(meta);
        row.appendChild(actions);
        clipsEl.appendChild(row);
      });
    };

    const loadClips = async () => {
      if (!clipsUrl) return;
      try {
        const url = new URL(clipsUrl, window.location.origin);
        url.searchParams.set('scope', 'team');
        url.searchParams.set('latest', '1');
        const resp = await fetch(url.toString(), { credentials: 'same-origin' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudieron cargar clips.');
        renderClips(data.items || []);
      } catch (e) {
        setStatus(statusEl, e?.message || 'Error al cargar clips.', true);
      }
    };

    saveClipBtn?.addEventListener('click', async () => {
      const name = safeText(clipNameEl?.value);
      if (!name) {
        setStatus(statusEl, 'Pon un nombre para el clip.', true);
        clipNameEl?.focus?.();
        return;
      }
      if (!clipSaveUrl) {
        setStatus(statusEl, 'Falta la URL de guardado.', true);
        return;
      }
      const folder = safeText(clipFolderEl?.value);
      const csrf = getCookie('csrftoken');
      if (!csrf) {
        setStatus(statusEl, 'Falta CSRF (cookie). Recarga la página.', true);
        return;
      }
      // Asegura que el clip capture el estado actual (si no pulsaron "+ Paso").
      try { syncActiveStepFromCanvas(); } catch (e) { /* ignore */ }
      const payload = {
        scope: 'team',
        name,
        folder,
        tags: [],
        steps: buildClipSteps(),
        overwrite: false,
        new_version: false,
      };
      setStatus(statusEl, 'Guardando clip…');
      try {
        const resp = await fetch(clipSaveUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify(payload),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) {
          if (data?.error === 'exists') {
            setStatus(statusEl, 'Ya existe un clip con ese nombre. Cambia el nombre o habilita overwrite (pendiente).', true);
            return;
          }
          throw new Error(data?.error || 'No se pudo guardar.');
        }
        setStatus(statusEl, 'Clip guardado ✅');
        await loadClips();
      } catch (e) {
        setStatus(statusEl, e?.message || 'Error al guardar.', true);
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      const { w, h } = resizeToStage();
      if (Math.abs(canvas.getWidth() - w) < 2 && Math.abs(canvas.getHeight() - h) < 2) return;
      canvas.setWidth(w);
      canvas.setHeight(h);
      canvas.renderAll();
    });
    try {
      resizeObserver.observe(canvasEl.parentElement);
    } catch (e) { /* ignore */ }

    await loadClips();
    setStatus(statusEl, 'Listo.');
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { void init(); }, { once: true });
  } else {
    void init();
  }
})();
