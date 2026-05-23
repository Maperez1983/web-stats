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
    // MVP estable: renderizamos un campo "FM-like" (franjas verdes + líneas blancas via SVG referencia).
    const w = Math.max(1, Number(width) || 1);
    const h = Math.max(1, Number(height) || 1);

    // 1) Franjas de césped (no depende de assets externos).
    try {
      const stripeCount = 12;
      const stripeW = w / stripeCount;
      const stripes = [];
      for (let i = 0; i < stripeCount; i += 1) {
        const fill = (i % 2 === 0) ? 'rgba(34,197,94,0.34)' : 'rgba(22,163,74,0.34)';
        stripes.push(new window.fabric.Rect({
          left: i * stripeW,
          top: 0,
          width: Math.ceil(stripeW + 1),
          height: h,
          fill,
          selectable: false,
          evented: false,
          hoverCursor: 'default',
        }));
      }
      const grass = new window.fabric.Group(stripes, { selectable: false, evented: false });
      grass.set({ left: 0, top: 0 });
      // Tag interno para poder reconocerlos.
      grass.__t2Kind = 'pitch_grass';
      canvas.add(grass);
      grass.sendToBack();
    } catch (e) { /* ignore */ }

    // 2) Líneas de campo (SVG referencia).
    const svgUrl = '/static/football/images/surfaces/references/football_pitch_metric_reference.svg';
    return new Promise((resolve) => {
      try {
        window.fabric.loadSVGFromURL(svgUrl, (objects, options) => {
          try {
            const group = window.fabric.util.groupSVGElements(objects, options);
            group.set({ selectable: false, evented: false, hoverCursor: 'default' });
            group.__t2Kind = 'pitch_lines';
            // Ajuste a tamaño disponible.
            const scale = Math.min(w / (group.width || w), h / (group.height || h));
            group.scale(scale);
            group.left = (w - (group.getScaledWidth ? group.getScaledWidth() : (group.width * scale))) / 2;
            group.top = (h - (group.getScaledHeight ? group.getScaledHeight() : (group.height * scale))) / 2;
            canvas.add(group);
            // Debe quedar por encima del césped, pero por debajo de tokens.
            try { group.sendToBack(); } catch (e2) { /* ignore */ }
            // Re-subimos el césped al fondo para asegurar orden.
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
      text = new window.fabric.Text('•', {
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
      return new window.fabric.Group([circle, text], { left: 120, top: 120, hasControls: false });
    }
    return circle;
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
    const addHomeBtn = document.getElementById('t2-add-home');
    const addAwayBtn = document.getElementById('t2-add-away');
    const addBallBtn = document.getElementById('t2-add-ball');
    const undoBtn = document.getElementById('t2-undo');
    const redoBtn = document.getElementById('t2-redo');
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

    const setMode = (mode) => {
      const isDraw = mode === 'draw';
      canvas.isDrawingMode = isDraw;
      canvas.selection = !isDraw;
      if (isDraw) {
        canvas.freeDrawingBrush.width = 4;
        canvas.freeDrawingBrush.color = 'rgba(244,180,0,0.92)';
      }
      modeMoveBtn?.classList.toggle('primary', !isDraw);
      modeDrawBtn?.classList.toggle('primary', isDraw);
      setStatus(statusEl, isDraw ? 'Modo dibujar: arrastra para trazar.' : 'Modo mover: arrastra fichas.');
    };

    modeMoveBtn?.addEventListener('click', () => setMode('move'));
    modeDrawBtn?.addEventListener('click', () => setMode('draw'));
    setMode('move');

    const addTokenAtCenter = (kind) => {
      const token = makeToken(kind);
      if (token.left == null) token.left = canvas.getWidth() / 2;
      if (token.top == null) token.top = canvas.getHeight() / 2;
      canvas.add(token);
      try { token.bringToFront(); } catch (e) { /* ignore */ }
      canvas.setActiveObject(token);
      canvas.renderAll();
      snapshot();
    };

    addHomeBtn?.addEventListener('click', () => addTokenAtCenter('home'));
    addAwayBtn?.addEventListener('click', () => addTokenAtCenter('away'));
    addBallBtn?.addEventListener('click', () => addTokenAtCenter('ball'));

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
      downloadText('tactica-v2.json', JSON.stringify({ version: 2, canvas: json }, null, 2));
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
      setStatus(statusEl, 'Pizarra limpia.');
    });

    const buildClipSteps = () => {
      const json = normalizeCanvasJson(canvas.toDatalessJSON());
      const w = Math.max(1, Math.round(canvas.getWidth() || 0));
      const h = Math.max(1, Math.round(canvas.getHeight() || 0));
      return [
        {
          title: 'Paso 1',
          duration: 3,
          canvas_state: json,
          canvas_width: w,
          canvas_height: h,
          preset: 'full_pitch',
          orientation: 'landscape',
          grass_style: 'reference_svg',
          zoom: 1,
        },
      ];
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
          const steps = Array.isArray(item?.steps) ? item.steps : [];
          const step = steps[0] || null;
          const state = step?.canvas_state && typeof step.canvas_state === 'object' ? step.canvas_state : null;
          if (!state) {
            setStatus(statusEl, 'Este clip no tiene canvas_state en el paso 1.', true);
            return;
          }
          // Asegura que el canvas se adapte al contenedor actual antes de cargar.
          const { w, h } = resizeToStage();
          canvas.setWidth(w);
          canvas.setHeight(h);
          await restore(state);
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
