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
    if (stopBtn) stopBtn.hidden = true;
    if (playBtn) playBtn.hidden = false;
    setStatus('Reproducción detenida.');
  };

  const play = async () => {
    if (isPlaying) return;
    isPlaying = true;
    if (playBtn) playBtn.hidden = true;
    if (stopBtn) stopBtn.hidden = false;
    const run = async () => {
      if (!isPlaying) return;
      const step = steps[activeIndex];
      const duration = clamp(Number(step?.duration) || 3, 1, 20);
      await loadStep(activeIndex);
      if (!isPlaying) return;
      timer = window.setTimeout(async () => {
        activeIndex = (activeIndex + 1) % steps.length;
        await run();
      }, duration * 1000);
    };
    setStatus('Reproduciendo…');
    await run();
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

