(function () {
  const safeText = (value, fallback = '') => {
    const text = typeof value === 'string' ? value : (value == null ? '' : String(value));
    const trimmed = text.trim();
    return trimmed ? trimmed : fallback;
  };

  const safeJsonParse = (raw, fallback) => {
    try {
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const lerp = (a, b, t) => (Number(a) || 0) + ((Number(b) || 0) - (Number(a) || 0)) * t;
  const easeInOut = (t) => {
    const x = clamp(Number(t) || 0, 0, 1);
    return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
  };

  const payloadEl = document.getElementById('sim-share-payload');
  const payload = payloadEl ? safeJsonParse(payloadEl.textContent, {}) : {};
  const steps = Array.isArray(payload?.steps) ? payload.steps : [];
  const pitchSvg = safeText(payload?.pitch_svg);

  const statusEl = document.getElementById('sim-status');
  const stepsEl = document.getElementById('sim-steps');
  const prevBtn = document.getElementById('sim-prev');
  const nextBtn = document.getElementById('sim-next');
  const playBtn = document.getElementById('sim-play');
  const stopBtn = document.getElementById('sim-stop');
  const canvasEl = document.getElementById('sim-share-canvas');
  const trailsInput = document.getElementById('sim-trails');
  const speedSelect = document.getElementById('sim-speed');

  const readPlaybackSpeed = () => {
    const raw = safeText(speedSelect?.value, '1');
    const val = Number.parseFloat(raw);
    return clamp(Number.isFinite(val) ? val : 1, 0.5, 2.5);
  };

  const setStatus = (message) => {
    if (!statusEl) return;
    statusEl.textContent = safeText(message, '');
  };

  if (!canvasEl || !window.fabric) {
    setStatus('No se pudo iniciar el visor.');
    return;
  }

  if (!steps.length) {
    setStatus('No hay pasos en esta simulación.');
    return;
  }

  let activeIndex = 0;
  let isPlaying = false;
  let timer = null;
  let rafId = 0;
  let rafStartedAt = 0;
  let rafDurationMs = 0;
  let rafResolve = null;
  let rafStartMap = null;
  let rafEndMap = null;
  let pitchBackgroundImg = null;

  const readStepSize = (step) => {
    const w = Number.parseInt(String(step?.canvas_width || ''), 10);
    const h = Number.parseInt(String(step?.canvas_height || ''), 10);
    return {
      w: clamp(Number.isFinite(w) ? w : 0, 320, 2400),
      h: clamp(Number.isFinite(h) ? h : 0, 180, 2400),
    };
  };

  const firstSize = readStepSize(steps[0]);
  const canvas = new window.fabric.Canvas(canvasEl, {
    selection: false,
    preserveObjectStacking: true,
    enableRetinaScaling: true,
  });
  canvas.setWidth(firstSize.w || 960);
  canvas.setHeight(firstSize.h || 540);

  const loadPitchBackground = async () => {
    if (!pitchSvg) return;
    try {
      const blob = new Blob([pitchSvg], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const img = new Image();
      await new Promise((resolve) => {
        img.onload = resolve;
        img.onerror = resolve;
        img.src = url;
      });
      try { URL.revokeObjectURL(url); } catch (error) {}
      if (!img.complete || !img.naturalWidth) return;

      pitchBackgroundImg = new window.fabric.Image(img, {
        selectable: false,
        evented: false,
        excludeFromExport: true,
      });
      const scaleX = (canvas.getWidth() || 1) / (pitchBackgroundImg.width || 1);
      const scaleY = (canvas.getHeight() || 1) / (pitchBackgroundImg.height || 1);
      pitchBackgroundImg.set({ left: 0, top: 0, originX: 'left', originY: 'top', scaleX, scaleY });
      canvas.setBackgroundImage(pitchBackgroundImg, canvas.renderAll.bind(canvas));
    } catch (error) {
      // ignore
    }
  };

  const applyCanvasSizeForStep = async (step) => {
    const size = readStepSize(step);
    const nextW = size.w || (canvas.getWidth() || 960);
    const nextH = size.h || (canvas.getHeight() || 540);
    const changed = Math.abs((canvas.getWidth() || 0) - nextW) > 2 || Math.abs((canvas.getHeight() || 0) - nextH) > 2;
    if (!changed) return;
    canvas.setWidth(nextW);
    canvas.setHeight(nextH);
    if (pitchBackgroundImg) {
      const scaleX = nextW / (pitchBackgroundImg.width || 1);
      const scaleY = nextH / (pitchBackgroundImg.height || 1);
      pitchBackgroundImg.set({ scaleX, scaleY });
      canvas.setBackgroundImage(pitchBackgroundImg, canvas.renderAll.bind(canvas));
    }
  };

  const normalizeCanvasState = (raw) => {
    if (!raw) return { objects: [] };
    if (typeof raw === 'string') return safeJsonParse(raw, { objects: [] });
    if (typeof raw === 'object') return raw;
    return { objects: [] };
  };

  const mapFromCanvasState = (rawState) => {
    const state = normalizeCanvasState(rawState);
    const objects = Array.isArray(state?.objects) ? state.objects : [];
    const map = new Map();
    objects.forEach((obj, idx) => {
      if (!obj || typeof obj !== 'object') return;
      const key = safeText(obj?.data?.layer_uid);
      if (!key) return;
      map.set(key, {
        left: Number(obj.left) || 0,
        top: Number(obj.top) || 0,
        angle: Number(obj.angle) || 0,
        scaleX: Number(obj.scaleX) || 1,
        scaleY: Number(obj.scaleY) || 1,
        opacity: obj.opacity == null ? 1 : Number(obj.opacity),
      });
    });
    return map;
  };

  const clearOverlayObjects = () => {
    try {
      const objs = canvas.getObjects() || [];
      objs.forEach((obj) => {
        if (!obj) return;
        const kind = safeText(obj?.data?.kind);
        if (kind === 'sim-move' || kind === 'sim-move-line' || kind === 'sim-move-head') {
          try { canvas.remove(obj); } catch (error) {}
        }
      });
    } catch (error) {}
  };

  const addMoveArrow = (from, to) => {
    if (!window.fabric) return null;
    const x1 = Number(from?.x) || 0;
    const y1 = Number(from?.y) || 0;
    const x2 = Number(to?.x) || 0;
    const y2 = Number(to?.y) || 0;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const len = Math.hypot(dx, dy) || 0;
    if (len < 10) return null;
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
    const head = 14;
    const line = new window.fabric.Line([0, 0, Math.max(6, len - head), 0], {
      stroke: 'rgba(250,204,21,0.92)',
      strokeWidth: 4,
      strokeDashArray: [10, 8],
      strokeLineCap: 'round',
      selectable: false,
      evented: false,
      excludeFromExport: true,
      data: { base: true, kind: 'sim-move-line', layer_uid: `overlay_move_line_${Date.now()}_${Math.random().toString(16).slice(2)}` },
    });
    try { line.strokeUniform = true; } catch (error) {}
    const tri = new window.fabric.Triangle({
      width: head,
      height: head,
      fill: 'rgba(250,204,21,0.92)',
      left: Math.max(6, len - head),
      top: 0,
      originX: 'center',
      originY: 'center',
      angle: 90,
      selectable: false,
      evented: false,
      excludeFromExport: true,
      data: { base: true, kind: 'sim-move-head', layer_uid: `overlay_move_head_${Date.now()}_${Math.random().toString(16).slice(2)}` },
    });
    const group = new window.fabric.Group([line, tri], {
      left: x1,
      top: y1,
      originX: 'left',
      originY: 'center',
      angle,
      selectable: false,
      evented: false,
      excludeFromExport: true,
      opacity: 0.92,
      data: { base: true, kind: 'sim-move', layer_uid: `overlay_move_${Date.now()}_${Math.random().toString(16).slice(2)}` },
    });
    try { group.objectCaching = false; } catch (error) {}
    try { group.noScaleCache = true; } catch (error) {}
    canvas.add(group);
    try { canvas.sendToBack(group); } catch (error) {}
    return group;
  };

  const renderMoveOverlaysForStep = (step) => {
    clearOverlayObjects();
    const enabled = trailsInput ? !!trailsInput.checked : true;
    if (!enabled) return;
    const moves = Array.isArray(step?.moves) ? step.moves : [];
    if (!moves.length) return;
    moves.slice(0, 60).forEach((move) => {
      try { addMoveArrow(move?.from, move?.to); } catch (error) {}
    });
  };

  const setObjectsReadOnly = () => {
    try {
      canvas.getObjects().forEach((obj) => {
        if (!obj) return;
        obj.selectable = false;
        obj.evented = false;
      });
    } catch (error) {}
  };

  const loadStep = async (index) => {
    const idx = clamp(Number(index) || 0, 0, steps.length - 1);
    const step = steps[idx];
    if (!step) return false;
    activeIndex = idx;
    await applyCanvasSizeForStep(step);
    const state = normalizeCanvasState(step.canvas_state);
    return await new Promise((resolve) => {
      try {
        canvas.loadFromJSON(state, () => {
          setObjectsReadOnly();
          try { renderMoveOverlaysForStep(step); } catch (error) {}
          canvas.renderAll();
          renderStepsList();
          setStatus(`Paso ${activeIndex + 1}/${steps.length}: ${safeText(step.title, '—')}`);
          resolve(true);
        });
      } catch (error) {
        resolve(false);
      }
    });
  };

  const stop = () => {
    isPlaying = false;
    if (timer) window.clearTimeout(timer);
    timer = null;
    if (rafId) {
      try { window.cancelAnimationFrame(rafId); } catch (error) {}
    }
    rafId = 0;
    rafResolve = null;
    rafStartMap = null;
    rafEndMap = null;
    if (stopBtn) stopBtn.hidden = true;
    if (playBtn) playBtn.hidden = false;
    setStatus('Reproducción detenida.');
  };

  const applyPropsToObject = (obj, props) => {
    if (!obj || !props) return;
    try {
      obj.set({
        left: Number(props.left) || 0,
        top: Number(props.top) || 0,
        angle: Number(props.angle) || 0,
        scaleX: Number(props.scaleX) || 1,
        scaleY: Number(props.scaleY) || 1,
        opacity: props.opacity == null ? 1 : Number(props.opacity),
      });
      obj.setCoords?.();
    } catch (error) {
      // ignore
    }
  };

  const animateBetweenSteps = async (fromIndex, toIndex, durationSeconds) => {
    const startStep = steps[clamp(Number(fromIndex) || 0, 0, steps.length - 1)];
    const endStep = steps[clamp(Number(toIndex) || 0, 0, steps.length - 1)];
    if (!startStep || !endStep) return;
    const durationMs = clamp(Number(durationSeconds) || 0, 0.2, 20) * 1000;
    // Carga el estado inicial para que el canvas tenga objetos.
    await loadStep(fromIndex);
    rafStartMap = mapFromCanvasState(startStep.canvas_state);
    rafEndMap = mapFromCanvasState(endStep.canvas_state);
    rafStartedAt = performance.now();
    rafDurationMs = durationMs;
    return await new Promise((resolve) => {
      rafResolve = resolve;
      const tick = () => {
        if (!isPlaying) {
          rafResolve?.();
          rafResolve = null;
          return;
        }
        const now = performance.now();
        const t = clamp((now - rafStartedAt) / Math.max(1, rafDurationMs), 0, 1);
        const eased = easeInOut(t);
        try {
          const objs = canvas.getObjects() || [];
          const liveByUid = new Map();
          objs.forEach((obj) => {
            const uid = safeText(obj?.data?.layer_uid);
            if (uid) liveByUid.set(uid, obj);
          });
          const keys = new Set([...(rafStartMap?.keys?.() || []), ...(rafEndMap?.keys?.() || [])]);
          keys.forEach((uid) => {
            const obj = liveByUid.get(uid);
            if (!obj) return;
            const a = rafStartMap?.get(uid);
            const b = rafEndMap?.get(uid);
            if (!a && !b) return;
            if (!a) return applyPropsToObject(obj, b);
            if (!b) return applyPropsToObject(obj, a);
            return applyPropsToObject(obj, {
              left: lerp(a.left, b.left, eased),
              top: lerp(a.top, b.top, eased),
              angle: lerp(a.angle, b.angle, eased),
              scaleX: lerp(a.scaleX, b.scaleX, eased),
              scaleY: lerp(a.scaleY, b.scaleY, eased),
              opacity: lerp(a.opacity, b.opacity, eased),
            });
          });
          canvas.renderAll();
        } catch (error) {
          // ignore
        }
        if (t >= 1) {
          const done = rafResolve;
          rafResolve = null;
          done?.();
          return;
        }
        rafId = window.requestAnimationFrame(tick);
      };
      rafId = window.requestAnimationFrame(tick);
    });
  };

  const play = async () => {
    if (isPlaying) return;
    isPlaying = true;
    if (playBtn) playBtn.hidden = true;
    if (stopBtn) stopBtn.hidden = false;
    setStatus('Reproduciendo (animación)…');
    while (isPlaying) {
      const current = steps[activeIndex];
      const speed = readPlaybackSpeed();
      const duration = clamp(Number(current?.duration) || 3, 1, 20) / Math.max(0.2, speed);
      await animateBetweenSteps(activeIndex, (activeIndex + 1) % steps.length, duration);
      if (!isPlaying) return;
      activeIndex = (activeIndex + 1) % steps.length;
      // Snap exacto al estado final (incluye objetos nuevos/borrados).
      await loadStep(activeIndex);
    }
  };

  const renderStepsList = () => {
    if (!stepsEl) return;
    stepsEl.innerHTML = '';
    steps.forEach((step, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = index === activeIndex ? 'is-active' : '';
      button.innerHTML = `<span>${safeText(step?.title, `Paso ${index + 1}`)}</span><small>${clamp(Number(step?.duration) || 3, 1, 20)} s</small>`;
      button.addEventListener('click', async () => {
        stop();
        await loadStep(index);
      });
      stepsEl.appendChild(button);
    });
  };

  prevBtn?.addEventListener('click', async () => {
    stop();
    await loadStep(activeIndex - 1);
  });
  nextBtn?.addEventListener('click', async () => {
    stop();
    await loadStep(activeIndex + 1);
  });
  trailsInput?.addEventListener('change', async () => {
    if (isPlaying) return;
    await loadStep(activeIndex);
  });
  speedSelect?.addEventListener('change', () => {
    if (!isPlaying) return;
    setStatus(`Velocidad: ${readPlaybackSpeed()}×`);
  });
  playBtn?.addEventListener('click', async () => {
    await play();
  });
  stopBtn?.addEventListener('click', () => stop());

  document.addEventListener('keydown', async (event) => {
    const key = safeText(event.key).toLowerCase();
    if (key === 'arrowleft') {
      event.preventDefault();
      stop();
      await loadStep(activeIndex - 1);
    }
    if (key === 'arrowright') {
      event.preventDefault();
      stop();
      await loadStep(activeIndex + 1);
    }
    if (key === ' ') {
      event.preventDefault();
      if (isPlaying) stop();
      else await play();
    }
    if (key === 'escape') {
      if (isPlaying) stop();
    }
  });

  (async () => {
    await loadPitchBackground();
    renderStepsList();
    await loadStep(0);
    setStatus(`Paso 1/${steps.length}: ${safeText(steps[0]?.title, '—')}`);
  })();
})();
