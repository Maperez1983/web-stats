(function () {
  const safeText = (value, fallback = '') => String(value ?? '').trim() || fallback;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const sleep = (ms) => new Promise((r) => window.setTimeout(r, ms));

  const setStatus = (text, isError = false) => {
    const el = document.getElementById('vs-status');
    if (!el) return;
    el.textContent = safeText(text, '');
    el.style.color = isError ? '#fecaca' : 'rgba(226,232,240,0.72)';
  };

  const downloadBlob = (blob, filename) => {
    try {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'export.webm';
      document.body.appendChild(a);
      a.click();
      window.setTimeout(() => {
        try { URL.revokeObjectURL(url); } catch (e) { /* ignore */ }
        try { a.remove(); } catch (e) { /* ignore */ }
      }, 500);
    } catch (e) { /* ignore */ }
  };

  const init = () => {
    const video = document.getElementById('vs-video');
    const canvasEl = document.getElementById('vs-canvas');
    const fxEl = document.getElementById('vs-fx');
    const stage = document.getElementById('vs-stage');
    if (!video || !canvasEl || !fxEl || !stage || !window.fabric) return;

    const btnPlay = document.getElementById('vs-play');
    const btnPause = document.getElementById('vs-pause');
    const btnIn = document.getElementById('vs-mark-in');
    const btnOut = document.getElementById('vs-mark-out');
    const btnExportSeg = document.getElementById('vs-export-seg');
    const btnRecord = document.getElementById('vs-record');
    const btnSnap = document.getElementById('vs-snap');

    const btnSelect = document.getElementById('vs-tool-select');
    const btnPen = document.getElementById('vs-tool-pen');
    const btnArrow = document.getElementById('vs-tool-arrow');
    const btnText = document.getElementById('vs-tool-text');
    const btnCallout = document.getElementById('vs-tool-callout');
    const btnSpot = document.getElementById('vs-tool-spot');
    const btnUndo = document.getElementById('vs-undo');
    const btnClear = document.getElementById('vs-clear');
    const colorInput = document.getElementById('vs-color');
    const widthInput = document.getElementById('vs-width');

    const inInput = document.getElementById('vs-in');
    const outInput = document.getElementById('vs-out');

    const videoId = Number(document.getElementById('vs-video-id')?.value || 0);
    const projectsUrl = safeText(document.getElementById('vs-projects-url')?.value);
    const projectSaveUrl = safeText(document.getElementById('vs-project-save-url')?.value);
    const projectDeleteUrl = safeText(document.getElementById('vs-project-delete-url')?.value);
    const clipsUrl = safeText(document.getElementById('vs-clips-url')?.value);
    const clipSaveUrl = safeText(document.getElementById('vs-clip-save-url')?.value);
    const clipDeleteUrl = safeText(document.getElementById('vs-clip-delete-url')?.value);
    const timelineUrl = safeText(document.getElementById('vs-timeline-url')?.value);
    const timelineSaveUrl = safeText(document.getElementById('vs-timeline-save-url')?.value);
    const timelineDeleteUrl = safeText(document.getElementById('vs-timeline-delete-url')?.value);

    const projectTitleInput = document.getElementById('vs-project-title');
    const projectSaveBtn = document.getElementById('vs-project-save');
    const projectRefreshBtn = document.getElementById('vs-project-refresh');
    const projectsList = document.getElementById('vs-projects');

    const clipTitleInput = document.getElementById('vs-clip-title');
    const clipCollectionInput = document.getElementById('vs-clip-collection');
    const clipSaveBtn = document.getElementById('vs-clip-save');
    const clipRefreshBtn = document.getElementById('vs-clip-refresh');
    const clipsList = document.getElementById('vs-clips');

    const eventKindSelect = document.getElementById('vs-event-kind');
    const eventLabelInput = document.getElementById('vs-event-label');
    const eventAddBtn = document.getElementById('vs-event-add');
    const eventRefreshBtn = document.getElementById('vs-event-refresh');
    const timelineList = document.getElementById('vs-timeline');

    const layerEmpty = document.getElementById('vs-layer-empty');
    const layerForm = document.getElementById('vs-layer-form');
    const layerKind = document.getElementById('vs-layer-kind');
    const layerInInput = document.getElementById('vs-layer-in');
    const layerOutInput = document.getElementById('vs-layer-out');
    const layerInNowBtn = document.getElementById('vs-layer-in-now');
    const layerOutNowBtn = document.getElementById('vs-layer-out-now');
    const layerFadeInInput = document.getElementById('vs-layer-fade-in');
    const layerFadeOutInput = document.getElementById('vs-layer-fade-out');
    const layerAnimSelect = document.getElementById('vs-layer-anim');
    const layerDelBtn = document.getElementById('vs-layer-del');
    const fxLayersList = document.getElementById('vs-fx-layers');

    const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

    const fabricCanvas = new fabric.Canvas(canvasEl, { preserveObjectStacking: true, selection: true });
    try { fabricCanvas.freeDrawingBrush.width = 6; } catch (e) { /* ignore */ }
    try { fabricCanvas.freeDrawingBrush.color = '#22d3ee'; } catch (e) { /* ignore */ }

    const fxCtx = fxEl.getContext('2d');

    const fmtTimeShort = (seconds) => {
      const s = Math.max(0, Number(seconds) || 0);
      const mm = Math.floor(s / 60);
      const ss = Math.floor(s % 60);
      return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
    };
    const fmtTime = (t) => {
      const v = Math.max(0, Number(t) || 0);
      const m = Math.floor(v / 60);
      const s = v - (m * 60);
      return `${m}:${String(Math.floor(s)).padStart(2, '0')}.${String(Math.round((s % 1) * 10))}`;
    };

    const history = [];
    const pushHistory = () => {
      try {
        const json = fabricCanvas.toDatalessJSON(['data']);
        history.push(json);
        if (history.length > 40) history.shift();
      } catch (e) { /* ignore */ }
    };

    const ensureLayerData = (obj) => {
      if (!obj) return;
      if (!obj.data || typeof obj.data !== 'object') obj.data = {};
      if (obj.data.t_in_s == null) obj.data.t_in_s = 0;
      if (obj.data.t_out_s == null) obj.data.t_out_s = 0;
      if (obj.data.fade_in_ms == null) obj.data.fade_in_ms = 0;
      if (obj.data.fade_out_ms == null) obj.data.fade_out_ms = 0;
      if (obj.data.anim == null) obj.data.anim = 'none';
    };

    const seedLayerDataNow = (extra = {}) => ({
      t_in_s: Number(video.currentTime) || 0,
      t_out_s: 0,
      fade_in_ms: 0,
      fade_out_ms: 0,
      anim: 'none',
      ...extra,
    });

    const computeTimedAlpha = (timing, nowS) => {
      const tIn = Math.max(0, Number(timing?.t_in_s) || 0);
      const tOut = Math.max(0, Number(timing?.t_out_s) || 0);
      const fadeInS = Math.max(0, (Number(timing?.fade_in_ms) || 0) / 1000);
      const fadeOutS = Math.max(0, (Number(timing?.fade_out_ms) || 0) / 1000);

      if (!tIn && !tOut) return 1;
      if (nowS < tIn) return 0;
      if (tOut > 0 && nowS > tOut) return 0;

      let a = 1;
      if (fadeInS > 0) a = Math.min(a, clamp((nowS - tIn) / fadeInS, 0, 1));
      if (tOut > 0 && fadeOutS > 0) a = Math.min(a, clamp((tOut - nowS) / fadeOutS, 0, 1));
      return clamp(a, 0, 1);
    };

    let fxSeq = 1;
    const fxState = { layers: [] };
    let fxPreview = null;
    let selectedFxId = 0;
    const getFxById = (id) => (Array.isArray(fxState.layers) ? fxState.layers : []).find((l) => Number(l?.id) === Number(id));
    const reseedFxSeq = () => {
      const maxId = Math.max(0, ...((Array.isArray(fxState.layers) ? fxState.layers : []).map((l) => Number(l?.id) || 0)));
      fxSeq = maxId + 1;
    };

    const renderFx = (ctx, { width, height, nowS, forExport = false } = {}) => {
      if (!ctx) return;
      const w = Math.max(1, Number(width) || fxEl.width || 1);
      const h = Math.max(1, Number(height) || fxEl.height || 1);
      const t = Number.isFinite(nowS) ? Number(nowS) : (Number(video.currentTime) || 0);

      try { ctx.clearRect(0, 0, w, h); } catch (e) { /* ignore */ }

      const active = [];
      for (const layer of (Array.isArray(fxState.layers) ? fxState.layers : [])) {
        if (safeText(layer?.kind) !== 'spotlight') continue;
        const alpha = computeTimedAlpha(layer, t);
        if (alpha <= 0.001) continue;
        active.push({ layer, alpha });
      }
      if (!forExport && fxPreview && safeText(fxPreview?.kind) === 'spotlight') {
        active.push({ layer: fxPreview, alpha: 1 });
      }
      if (!active.length) return;

      const base = Math.max(...active.map((x) => clamp(Number(x.layer?.intensity ?? 0.68), 0, 0.9)));
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = `rgba(0,0,0,${clamp(base, 0, 0.9)})`;
      ctx.fillRect(0, 0, w, h);

      ctx.globalCompositeOperation = 'destination-out';
      for (const item of active) {
        const l = item.layer;
        const cx = clamp(Number(l?.cx) || 0, 0, w);
        const cy = clamp(Number(l?.cy) || 0, 0, h);
        const r = clamp(Number(l?.r) || 0, 0, Math.max(w, h));
        const feather = clamp(Number(l?.feather ?? 0.18), 0.02, 0.6);
        const rr0 = Math.max(1, r * (1 - feather));
        const rr1 = Math.max(rr0 + 1, r);
        const g = ctx.createRadialGradient(cx, cy, rr0, cx, cy, rr1);
        g.addColorStop(0, `rgba(0,0,0,${clamp(item.alpha, 0, 1)})`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(cx, cy, rr1, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      if (!forExport) {
        const selected = selectedFxId ? getFxById(selectedFxId) : null;
        if (selected && selected.kind === 'spotlight') {
          try {
            ctx.save();
            ctx.globalCompositeOperation = 'source-over';
            ctx.strokeStyle = 'rgba(34,211,238,0.9)';
            ctx.lineWidth = 2;
            ctx.setLineDash([10, 8]);
            ctx.beginPath();
            ctx.arc(Number(selected.cx) || 0, Number(selected.cy) || 0, Number(selected.r) || 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();
          } catch (e) { /* ignore */ }
        }
        if (fxPreview && fxPreview.kind === 'spotlight') {
          try {
            ctx.save();
            ctx.globalCompositeOperation = 'source-over';
            ctx.strokeStyle = 'rgba(250,204,21,0.95)';
            ctx.lineWidth = 2;
            ctx.setLineDash([8, 6]);
            ctx.beginPath();
            ctx.arc(Number(fxPreview.cx) || 0, Number(fxPreview.cy) || 0, Number(fxPreview.r) || 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();
          } catch (e) { /* ignore */ }
        }
      }
    };

    const renderFxList = () => {
      if (!fxLayersList) return;
      const items = (Array.isArray(fxState.layers) ? fxState.layers : []).filter((l) => safeText(l?.kind) === 'spotlight').slice(0, 60);
      const rows = items.map((l) => {
        const id = Number(l?.id) || 0;
        if (!id) return '';
        const inS = Number(l?.t_in_s) || 0;
        const outS = Number(l?.t_out_s) || 0;
        const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS || inS)}`;
        const isSel = selectedFxId === id;
        return `
          <div class="row" style="${isSel ? 'border-color: rgba(34,211,238,0.55); background: rgba(34,211,238,0.07);' : ''}">
            <div style="display:flex; flex-direction:column; gap:0.05rem;">
              <strong>Spotlight</strong>
              <small>${label}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-vs-fx-edit="${id}">Editar</button>
              <button type="button" class="button danger" data-vs-fx-del="${id}">Borrar</button>
            </div>
          </div>
        `;
      }).filter(Boolean).join('');
      fxLayersList.innerHTML = rows || '<div class="hint">Sin spotlights.</div>';

      Array.from(fxLayersList.querySelectorAll('[data-vs-fx-edit]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = Number(btn.getAttribute('data-vs-fx-edit') || 0);
          if (!id) return;
          selectedFxId = id;
          try { fabricCanvas.discardActiveObject(); } catch (e) { /* ignore */ }
          updateLayerPanel();
          renderFxList();
        });
      });
      Array.from(fxLayersList.querySelectorAll('[data-vs-fx-del]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = Number(btn.getAttribute('data-vs-fx-del') || 0);
          if (!id) return;
          const ok = window.confirm('¿Borrar spotlight?');
          if (!ok) return;
          fxState.layers = (Array.isArray(fxState.layers) ? fxState.layers : []).filter((x) => Number(x?.id) !== id);
          if (selectedFxId === id) selectedFxId = 0;
          reseedFxSeq();
          renderFxList();
          updateLayerPanel();
        });
      });
    };

    const restoreJson = (json) => {
      if (!json) return;
      fabricCanvas.loadFromJSON(json, () => {
        try { fabricCanvas.getObjects().forEach((o) => ensureLayerData(o)); } catch (e) { /* ignore */ }
        fabricCanvas.renderAll();
        updateLayerPanel();
      });
    };

    const resizeToVideo = () => {
      const rect = video.getBoundingClientRect();
      const w = Math.max(1, Math.round(rect.width));
      const h = Math.max(1, Math.round(rect.height));
      canvasEl.width = w;
      canvasEl.height = h;
      fxEl.width = w;
      fxEl.height = h;
      fabricCanvas.setWidth(w);
      fabricCanvas.setHeight(h);
      fabricCanvas.renderAll();
    };
    const scheduleResize = (() => {
      let t = null;
      return () => {
        if (t) window.clearTimeout(t);
        t = window.setTimeout(() => resizeToVideo(), 50);
      };
    })();
    window.addEventListener('resize', scheduleResize);
    video.addEventListener('loadedmetadata', () => {
      try {
        if (outInput) outInput.value = String(Math.max(0, Number(video.duration) || 0).toFixed(1));
      } catch (e) { /* ignore */ }
      scheduleResize();
    });
    video.addEventListener('loadeddata', scheduleResize);
    scheduleResize();

    const strokeColor = () => safeText(colorInput?.value, '#22d3ee');
    const strokeWidth = () => clamp(Number(widthInput?.value || 6), 1, 26);
    colorInput?.addEventListener('change', () => {
      try { fabricCanvas.freeDrawingBrush.color = strokeColor(); } catch (e) { /* ignore */ }
    });
    widthInput?.addEventListener('input', () => {
      try { fabricCanvas.freeDrawingBrush.width = strokeWidth(); } catch (e) { /* ignore */ }
    });

    let tool = 'select';
    let arrowStart = null;
    let calloutSeq = 1;

    const setTool = (next) => {
      tool = next;
      const isSelect = tool === 'select';
      const isPen = tool === 'pen';
      fabricCanvas.isDrawingMode = isPen;
      try { fabricCanvas.selection = isSelect; } catch (e) { /* ignore */ }

      if (tool !== 'spot') fxPreview = null;
      fxEl.style.pointerEvents = tool === 'spot' ? 'auto' : 'none';

      Array.from([btnSelect, btnPen, btnArrow, btnText, btnCallout, btnSpot]).forEach((b) => b?.classList.remove('primary'));
      if (tool === 'select') btnSelect?.classList.add('primary');
      if (tool === 'pen') btnPen?.classList.add('primary');
      if (tool === 'arrow') btnArrow?.classList.add('primary');
      if (tool === 'text') btnText?.classList.add('primary');
      if (tool === 'callout') btnCallout?.classList.add('primary');
      if (tool === 'spot') btnSpot?.classList.add('primary');
      setStatus(`Herramienta: ${tool}`);
    };
    setTool('select');

    const activeObject = () => {
      try { return fabricCanvas.getActiveObject(); } catch (e) { return null; }
    };
    const currentLayerTarget = () => {
      const fx = selectedFxId ? getFxById(selectedFxId) : null;
      if (fx) return { type: 'fx', fx };
      const obj = activeObject();
      if (obj) return { type: 'fabric', obj };
      return null;
    };

    const updateLayerPanel = () => {
      if (!layerEmpty || !layerForm) return;
      const target = currentLayerTarget();
      if (!target) {
        layerEmpty.style.display = '';
        layerForm.style.display = 'none';
        return;
      }
      layerEmpty.style.display = 'none';
      layerForm.style.display = 'grid';

      if (target.type === 'fx') {
        const fx = target.fx;
        if (layerKind) layerKind.textContent = 'FX · Spotlight';
        if (layerInInput) layerInInput.value = String((Number(fx.t_in_s) || 0).toFixed(1));
        if (layerOutInput) layerOutInput.value = String((Number(fx.t_out_s) || 0).toFixed(1));
        if (layerFadeInInput) layerFadeInInput.value = String(Math.max(0, Number(fx.fade_in_ms) || 0));
        if (layerFadeOutInput) layerFadeOutInput.value = String(Math.max(0, Number(fx.fade_out_ms) || 0));
        if (layerAnimSelect) layerAnimSelect.value = 'none';
        if (layerAnimSelect) layerAnimSelect.disabled = true;
        return;
      }

      const obj = target.obj;
      ensureLayerData(obj);
      if (layerKind) layerKind.textContent = `Dibujo · ${safeText(obj?.type, 'obj')}`;
      if (layerInInput) layerInInput.value = String((Number(obj.data.t_in_s) || 0).toFixed(1));
      if (layerOutInput) layerOutInput.value = String((Number(obj.data.t_out_s) || 0).toFixed(1));
      if (layerFadeInInput) layerFadeInInput.value = String(Math.max(0, Number(obj.data.fade_in_ms) || 0));
      if (layerFadeOutInput) layerFadeOutInput.value = String(Math.max(0, Number(obj.data.fade_out_ms) || 0));
      if (layerAnimSelect) layerAnimSelect.value = safeText(obj.data.anim, 'none');
      if (layerAnimSelect) layerAnimSelect.disabled = false;
    };

    const applyLayerPanelEdits = () => {
      const target = currentLayerTarget();
      if (!target) return;
      const tIn = Number(layerInInput?.value || 0) || 0;
      const tOut = Number(layerOutInput?.value || 0) || 0;
      const fadeIn = Math.max(0, Number(layerFadeInInput?.value || 0) || 0);
      const fadeOut = Math.max(0, Number(layerFadeOutInput?.value || 0) || 0);
      const anim = safeText(layerAnimSelect?.value, 'none');
      if (target.type === 'fx') {
        target.fx.t_in_s = tIn;
        target.fx.t_out_s = tOut;
        target.fx.fade_in_ms = fadeIn;
        target.fx.fade_out_ms = fadeOut;
        renderFxList();
        return;
      }
      const obj = target.obj;
      ensureLayerData(obj);
      obj.data.t_in_s = tIn;
      obj.data.t_out_s = tOut;
      obj.data.fade_in_ms = fadeIn;
      obj.data.fade_out_ms = fadeOut;
      obj.data.anim = anim;
      pushHistory();
    };

    [layerInInput, layerOutInput, layerFadeInInput, layerFadeOutInput, layerAnimSelect].forEach((el) => {
      el?.addEventListener('change', () => { applyLayerPanelEdits(); updateLayerPanel(); });
    });
    layerInNowBtn?.addEventListener('click', () => {
      const target = currentLayerTarget();
      if (!target) return;
      const now = Number(video.currentTime) || 0;
      if (target.type === 'fx') {
        target.fx.t_in_s = now;
        renderFxList();
        updateLayerPanel();
        return;
      }
      ensureLayerData(target.obj);
      target.obj.data.t_in_s = now;
      pushHistory();
      updateLayerPanel();
    });
    layerOutNowBtn?.addEventListener('click', () => {
      const target = currentLayerTarget();
      if (!target) return;
      const now = Number(video.currentTime) || 0;
      if (target.type === 'fx') {
        target.fx.t_out_s = now;
        renderFxList();
        updateLayerPanel();
        return;
      }
      ensureLayerData(target.obj);
      target.obj.data.t_out_s = now;
      pushHistory();
      updateLayerPanel();
    });
    layerDelBtn?.addEventListener('click', () => {
      const target = currentLayerTarget();
      if (!target) return;
      const ok = window.confirm('¿Borrar capa seleccionada?');
      if (!ok) return;
      if (target.type === 'fx') {
        fxState.layers = (Array.isArray(fxState.layers) ? fxState.layers : []).filter((x) => Number(x?.id) !== Number(target.fx.id));
        selectedFxId = 0;
        reseedFxSeq();
        renderFxList();
        updateLayerPanel();
        return;
      }
      try { fabricCanvas.remove(target.obj); } catch (e) { /* ignore */ }
      pushHistory();
      updateLayerPanel();
    });

    fabricCanvas.on('mouse:down', (opt) => {
      if (tool === 'arrow') {
        arrowStart = fabricCanvas.getPointer(opt.e);
      }
      if (tool === 'text') {
        const p = fabricCanvas.getPointer(opt.e);
        const txt = window.prompt('Texto');
        if (!txt) return;
        const t = new fabric.Text(txt.slice(0, 60), {
          left: p.x,
          top: p.y,
          fill: strokeColor(),
          fontSize: 22,
          fontWeight: '800',
          shadow: 'rgba(15,23,42,0.65) 0 1px 3px',
        });
        t.data = seedLayerDataNow();
        fabricCanvas.add(t);
        pushHistory();
        fabricCanvas.setActiveObject(t);
        selectedFxId = 0;
        updateLayerPanel();
        renderFxList();
      }
      if (tool === 'callout') {
        const p = fabricCanvas.getPointer(opt.e);
        const n = calloutSeq++;
        const circle = new fabric.Circle({
          left: p.x,
          top: p.y,
          radius: 16 + Math.round(strokeWidth() / 2),
          fill: 'rgba(2,6,23,0.65)',
          stroke: strokeColor(),
          strokeWidth: 3,
          originX: 'center',
          originY: 'center',
        });
        const text = new fabric.Text(String(n), {
          left: p.x,
          top: p.y,
          fill: '#ffffff',
          fontSize: 18,
          fontWeight: '900',
          originX: 'center',
          originY: 'center',
          shadow: 'rgba(0,0,0,0.45) 0 1px 2px',
        });
        const group = new fabric.Group([circle, text], { selectable: true });
        group.data = seedLayerDataNow({ kind: 'callout', callout_n: n });
        fabricCanvas.add(group);
        pushHistory();
        fabricCanvas.setActiveObject(group);
        selectedFxId = 0;
        updateLayerPanel();
        renderFxList();
      }
    });
    fabricCanvas.on('mouse:up', (opt) => {
      if (tool !== 'arrow' || !arrowStart) return;
      const end = fabricCanvas.getPointer(opt.e);
      const line = new fabric.Line([arrowStart.x, arrowStart.y, end.x, end.y], {
        stroke: strokeColor(),
        strokeWidth: strokeWidth(),
        selectable: true,
      });
      const ang = Math.atan2(end.y - arrowStart.y, end.x - arrowStart.x);
      const headLen = 14 + strokeWidth();
      const hx1 = end.x - headLen * Math.cos(ang - Math.PI / 7);
      const hy1 = end.y - headLen * Math.sin(ang - Math.PI / 7);
      const hx2 = end.x - headLen * Math.cos(ang + Math.PI / 7);
      const hy2 = end.y - headLen * Math.sin(ang + Math.PI / 7);
      const head = new fabric.Polygon([
        { x: end.x, y: end.y },
        { x: hx1, y: hy1 },
        { x: hx2, y: hy2 },
      ], { fill: strokeColor(), selectable: true });
      const group = new fabric.Group([line, head], { selectable: true });
      group.data = seedLayerDataNow({ kind: 'arrow', anim: 'draw', anim_ms: 700 });
      fabricCanvas.add(group);
      pushHistory();
      fabricCanvas.setActiveObject(group);
      selectedFxId = 0;
      updateLayerPanel();
      renderFxList();
      arrowStart = null;
    });
    fabricCanvas.on('path:created', (opt) => {
      const p = opt?.path;
      if (p) p.data = seedLayerDataNow();
      pushHistory();
      updateLayerPanel();
    });
    fabricCanvas.on('selection:created', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); });
    fabricCanvas.on('selection:updated', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); });
    fabricCanvas.on('selection:cleared', updateLayerPanel);

    btnSelect?.addEventListener('click', () => setTool('select'));
    btnPen?.addEventListener('click', () => setTool('pen'));
    btnArrow?.addEventListener('click', () => setTool('arrow'));
    btnText?.addEventListener('click', () => setTool('text'));
    btnCallout?.addEventListener('click', () => setTool('callout'));
    btnSpot?.addEventListener('click', () => setTool('spot'));

    // Spotlight tool (FX canvas)
    let spotDrag = null;
    const pointerToFx = (ev) => {
      const rect = fxEl.getBoundingClientRect();
      const x = clamp(((ev.clientX - rect.left) / rect.width) * fxEl.width, 0, fxEl.width);
      const y = clamp(((ev.clientY - rect.top) / rect.height) * fxEl.height, 0, fxEl.height);
      return { x, y };
    };
    fxEl.addEventListener('pointerdown', (ev) => {
      if (tool !== 'spot') return;
      try { fxEl.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
      const p = pointerToFx(ev);
      spotDrag = { start: p };
      fxPreview = { kind: 'spotlight', cx: p.x, cy: p.y, r: 8, intensity: 0.68, feather: 0.18 };
      selectedFxId = 0;
      try { fabricCanvas.discardActiveObject(); } catch (e) { /* ignore */ }
      updateLayerPanel();
      renderFxList();
    });
    fxEl.addEventListener('pointermove', (ev) => {
      if (tool !== 'spot' || !spotDrag || !fxPreview) return;
      const p = pointerToFx(ev);
      const dx = p.x - spotDrag.start.x;
      const dy = p.y - spotDrag.start.y;
      fxPreview.cx = spotDrag.start.x;
      fxPreview.cy = spotDrag.start.y;
      fxPreview.r = Math.max(10, Math.hypot(dx, dy));
    });
    const endSpot = (ev) => {
      if (tool !== 'spot' || !spotDrag) return;
      try { fxEl.releasePointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
      const now = Number(video.currentTime) || 0;
      if (fxPreview && Number(fxPreview.r) >= 12) {
        const layer = {
          id: fxSeq++,
          kind: 'spotlight',
          cx: Number(fxPreview.cx) || 0,
          cy: Number(fxPreview.cy) || 0,
          r: Number(fxPreview.r) || 0,
          intensity: 0.68,
          feather: 0.18,
          t_in_s: now,
          t_out_s: 0,
          fade_in_ms: 150,
          fade_out_ms: 150,
        };
        fxState.layers.push(layer);
        reseedFxSeq();
        selectedFxId = layer.id;
        renderFxList();
        updateLayerPanel();
        setStatus('Spotlight añadido.');
      }
      spotDrag = null;
      fxPreview = null;
    };
    fxEl.addEventListener('pointerup', endSpot);
    fxEl.addEventListener('pointercancel', endSpot);

    btnUndo?.addEventListener('click', () => {
      if (history.length <= 1) {
        fabricCanvas.clear();
        fabricCanvas.renderAll();
        setStatus('Undo.');
        return;
      }
      history.pop();
      restoreJson(history[history.length - 1]);
      setStatus('Undo.');
    });
    btnClear?.addEventListener('click', () => {
      const ok = window.confirm('¿Limpiar dibujos?');
      if (!ok) return;
      fabricCanvas.clear();
      pushHistory();
      fabricCanvas.renderAll();
      updateLayerPanel();
      setStatus('Lienzo limpio.');
    });

    const syncPlayButtons = () => {
      const playing = !video.paused && !video.ended;
      if (btnPlay) btnPlay.hidden = playing;
      if (btnPause) btnPause.hidden = !playing;
    };
    btnPlay?.addEventListener('click', async () => {
      try { await video.play(); } catch (e) { /* ignore */ }
      syncPlayButtons();
    });
    btnPause?.addEventListener('click', () => { try { video.pause(); } catch (e) { /* ignore */ } syncPlayButtons(); });
    video.addEventListener('play', syncPlayButtons);
    video.addEventListener('pause', syncPlayButtons);
    syncPlayButtons();

    const markIn = () => {
      const t = Number(video.currentTime) || 0;
      if (inInput) inInput.value = String(t.toFixed(1));
      setStatus(`IN: ${fmtTime(t)}`);
    };
    const markOut = () => {
      const t = Number(video.currentTime) || 0;
      if (outInput) outInput.value = String(t.toFixed(1));
      setStatus(`OUT: ${fmtTime(t)}`);
    };
    btnIn?.addEventListener('click', markIn);
    btnOut?.addEventListener('click', markOut);

    const snapshotPng = () => {
      const w = fabricCanvas.getWidth();
      const h = fabricCanvas.getHeight();
      const off = document.createElement('canvas');
      off.width = w;
      off.height = h;
      const ctx = off.getContext('2d');
      if (!ctx) return;
      try { ctx.drawImage(video, 0, 0, w, h); } catch (e) { /* ignore */ }
      try { renderFx(ctx, { width: w, height: h, nowS: Number(video.currentTime) || 0, forExport: true }); } catch (e) { /* ignore */ }
      try { ctx.drawImage(canvasEl, 0, 0, w, h); } catch (e) { /* ignore */ }
      off.toBlob((blob) => {
        if (!blob) return;
        downloadBlob(blob, `telestracion-${videoId || 'video'}.png`);
      }, 'image/png');
    };
    btnSnap?.addEventListener('click', snapshotPng);

    let recActive = false;
    let recMedia = null;
    let recStream = null;
    let recChunks = [];
    let recCanvas = null;
    let recCtx = null;
    let recRaf = null;
    let stopAt = null;

    const stopRecording = async () => {
      if (!recActive) return;
      recActive = false;
      try { if (recRaf) window.cancelAnimationFrame(recRaf); } catch (e) { /* ignore */ }
      recRaf = null;
      try { recMedia?.stop?.(); } catch (e) { /* ignore */ }
      try { recStream?.getTracks?.().forEach((t) => t.stop()); } catch (e) { /* ignore */ }
      recStream = null;
      recMedia = null;
      recCanvas = null;
      recCtx = null;
      stopAt = null;
      if (btnRecord) btnRecord.textContent = 'Grabar';
      if (btnExportSeg) btnExportSeg.disabled = false;
      setStatus('Grabación finalizada.');
    };

    const startRecording = async ({ from = null, to = null } = {}) => {
      if (recActive) return;
      if (!('MediaRecorder' in window)) {
        setStatus('Este navegador no soporta export de vídeo.', true);
        return;
      }
      const w = fabricCanvas.getWidth();
      const h = fabricCanvas.getHeight();
      if (!w || !h) return;

      stopAt = (Number.isFinite(to) && to != null) ? Number(to) : null;
      if (Number.isFinite(from) && from != null) {
        try { video.currentTime = Math.max(0, Number(from) || 0); } catch (e) { /* ignore */ }
        await sleep(120);
      }

      recCanvas = document.createElement('canvas');
      recCanvas.width = w;
      recCanvas.height = h;
      recCtx = recCanvas.getContext('2d', { alpha: false });
      if (!recCtx) return;

      const canvasStream = recCanvas.captureStream(30);
      let audioTracks = [];
      try {
        const vStream = typeof video.captureStream === 'function' ? video.captureStream() : null;
        audioTracks = vStream ? (vStream.getAudioTracks?.() || []) : [];
      } catch (e) { audioTracks = []; }
      recStream = new MediaStream([...(canvasStream.getVideoTracks?.() || []), ...(audioTracks || [])]);

      recChunks = [];
      let mime = 'video/webm;codecs=vp9,opus';
      if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/webm;codecs=vp8,opus';
      if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/webm';

      try {
        recMedia = new MediaRecorder(recStream, { mimeType: mime, videoBitsPerSecond: 4_000_000 });
      } catch (e) {
        recMedia = new MediaRecorder(recStream);
      }
      recMedia.ondataavailable = (ev) => { if (ev.data && ev.data.size) recChunks.push(ev.data); };
      recMedia.onstop = () => {
        try {
          const blob = new Blob(recChunks, { type: recChunks[0]?.type || 'video/webm' });
          downloadBlob(blob, `video-studio-${videoId || 'export'}.webm`);
        } catch (e) { /* ignore */ }
      };

      const draw = () => {
        if (!recActive || !recCtx || !recCanvas) return;
        try {
          recCtx.fillStyle = '#000';
          recCtx.fillRect(0, 0, w, h);
          try { recCtx.drawImage(video, 0, 0, w, h); } catch (e) { /* ignore */ }
          try { renderFx(recCtx, { width: w, height: h, nowS: Number(video.currentTime) || 0, forExport: true }); } catch (e) { /* ignore */ }
          try { recCtx.drawImage(canvasEl, 0, 0, w, h); } catch (e) { /* ignore */ }
        } catch (e) { /* ignore */ }
        if (stopAt != null && (Number(video.currentTime) || 0) >= stopAt) {
          stopRecording();
          return;
        }
        recRaf = window.requestAnimationFrame(draw);
      };

      recActive = true;
      if (btnRecord) btnRecord.textContent = 'Parar';
      if (btnExportSeg) btnExportSeg.disabled = true;
      try { recMedia.start(250); } catch (e) { setStatus('No se pudo iniciar la grabación.', true); recActive = false; return; }
      try { await video.play(); } catch (e) { /* ignore */ }
      recRaf = window.requestAnimationFrame(draw);
      setStatus('Grabando…');
    };

    btnRecord?.addEventListener('click', async () => {
      if (recActive) return stopRecording();
      return await startRecording({});
    });

    btnExportSeg?.addEventListener('click', async () => {
      const a = Number(inInput?.value || 0) || 0;
      const b = Number(outInput?.value || 0) || 0;
      const start = Math.max(0, Math.min(a, b));
      const end = Math.max(a, b);
      if (!end || end <= start) {
        setStatus('Define IN/OUT primero.', true);
        return;
      }
      return await startRecording({ from: start, to: end });
    });

    // Shortcuts
    document.addEventListener('keydown', (event) => {
      const key = String(event.key || '').toLowerCase();
      const tag = String(event.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (key === ' ') {
        event.preventDefault();
        if (video.paused) video.play().catch(() => {});
        else video.pause();
      } else if (key === 'i') {
        event.preventDefault();
        btnIn?.click();
      } else if (key === 'o') {
        event.preventDefault();
        btnOut?.click();
      } else if (key === 'c') {
        event.preventDefault();
        clipSaveBtn?.click();
      } else if (key === 't') {
        event.preventDefault();
        eventAddBtn?.click();
      }
    });

    // Projects (server)
    let activeProjectId = 0;
    const renderProjects = (items) => {
      if (!projectsList) return;
      const rows = (Array.isArray(items) ? items : []).slice(0, 120).map((p) => {
        const id = Number(p?.id) || 0;
        if (!id) return '';
        const title = safeText(p?.title, `Proyecto ${id}`);
        const when = safeText(p?.updated_at || p?.created_at, '').slice(0, 10);
        return `
          <div class="row">
            <div style="display:flex; flex-direction:column; gap:0.05rem;">
              <strong>${title}</strong>
              <small>${when}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-vs-load="${id}">Cargar</button>
              <button type="button" class="button danger" data-vs-del="${id}">Borrar</button>
            </div>
          </div>
        `;
      }).filter(Boolean).join('');
      projectsList.innerHTML = rows || '<div class="meta">Sin proyectos guardados.</div>';

      Array.from(projectsList.querySelectorAll('[data-vs-load]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-load') || 0);
          if (!id) return;
          try {
            const resp = await fetch(`${projectsUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
            const data = await resp.json().catch(() => ({}));
            const items2 = Array.isArray(data?.items) ? data.items : [];
            const found = items2.find((x) => Number(x?.id) === id);
            if (!found) return;
            const payload = found?.payload || {};
            const canvasJson = payload?.canvas;
            if (canvasJson) restoreJson(canvasJson);
            const fxPayload = payload?.fx;
            if (fxPayload && typeof fxPayload === 'object' && Array.isArray(fxPayload?.layers)) {
              fxState.layers = fxPayload.layers.map((l) => ({ ...l }));
              selectedFxId = 0;
              reseedFxSeq();
              renderFxList();
            }
            activeProjectId = id;
            if (projectTitleInput) projectTitleInput.value = safeText(found?.title);
            pushHistory();
            updateLayerPanel();
            setStatus('Proyecto cargado.');
          } catch (e) {
            setStatus('No se pudo cargar.', true);
          }
        });
      });
      Array.from(projectsList.querySelectorAll('[data-vs-del]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-del') || 0);
          if (!id) return;
          const ok = window.confirm('¿Borrar proyecto?');
          if (!ok) return;
          try {
            const resp = await fetch(projectDeleteUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
              credentials: 'same-origin',
              body: JSON.stringify({ id }),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
            if (activeProjectId === id) activeProjectId = 0;
            await refreshProjects();
            setStatus('Proyecto borrado.');
          } catch (e) {
            setStatus('No se pudo borrar.', true);
          }
        });
      });
    };

    const refreshProjects = async () => {
      if (!projectsUrl || !videoId) return;
      try {
        const resp = await fetch(`${projectsUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        renderProjects(Array.isArray(data?.items) ? data.items : []);
      } catch (e) {
        renderProjects([]);
      }
    };

    const saveProject = async () => {
      if (!projectSaveUrl || !videoId) return;
      const title = safeText(projectTitleInput?.value, 'Proyecto').slice(0, 180);
      const payload = { canvas: fabricCanvas.toDatalessJSON(['data']), fx: { layers: fxState.layers }, in: Number(inInput?.value || 0) || 0, out: Number(outInput?.value || 0) || 0 };
      try {
        const resp = await fetch(projectSaveUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ id: activeProjectId || 0, video_id: videoId, title, payload }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        activeProjectId = Number(data?.id) || activeProjectId;
        await refreshProjects();
        setStatus('Proyecto guardado.');
      } catch (e) {
        setStatus('No se pudo guardar.', true);
      }
    };
    projectSaveBtn?.addEventListener('click', saveProject);
    projectRefreshBtn?.addEventListener('click', refreshProjects);
    refreshProjects();

    // Clips (server)
    let activeClipId = 0;
    const renderClips = (items) => {
      if (!clipsList) return;
      const rows = (Array.isArray(items) ? items : []).slice(0, 120).map((c) => {
        const id = Number(c?.id) || 0;
        if (!id) return '';
        const title = safeText(c?.title, `Clip ${id}`);
        const coll = safeText(c?.collection, '');
        const inS = Number(c?.in_s) || 0;
        const outS = Number(c?.out_s) || 0;
        const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS || inS)}`;
        return `
          <div class="row">
            <div style="display:flex; flex-direction:column; gap:0.05rem;">
              <strong>${title}</strong>
              <small>${coll ? `${coll} · ` : ''}${label}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-vs-clip-load="${id}">Abrir</button>
              <button type="button" class="button danger" data-vs-clip-del="${id}">Borrar</button>
            </div>
          </div>
        `;
      }).filter(Boolean).join('');
      clipsList.innerHTML = rows || '<div class="meta">Sin clips guardados.</div>';

      Array.from(clipsList.querySelectorAll('[data-vs-clip-load]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-clip-load') || 0);
          if (!id) return;
          try {
            const resp = await fetch(`${clipsUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
            const data = await resp.json().catch(() => ({}));
            const items2 = Array.isArray(data?.items) ? data.items : [];
            const found = items2.find((x) => Number(x?.id) === id);
            if (!found) return;
            activeClipId = id;
            if (clipTitleInput) clipTitleInput.value = safeText(found?.title);
            if (clipCollectionInput) clipCollectionInput.value = safeText(found?.collection);
            if (inInput) inInput.value = String((Number(found?.in_s) || 0).toFixed(1));
            if (outInput) outInput.value = String((Number(found?.out_s) || 0).toFixed(1));
            const overlay = found?.overlay || {};
            if (overlay && typeof overlay === 'object' && Array.isArray(overlay?.objects)) {
              restoreJson(overlay);
            }
            const fxPayload = overlay?.fx;
            if (fxPayload && typeof fxPayload === 'object' && Array.isArray(fxPayload?.layers)) {
              fxState.layers = fxPayload.layers.map((l) => ({ ...l }));
              selectedFxId = 0;
              reseedFxSeq();
              renderFxList();
            }
            try { video.currentTime = Number(found?.in_s) || 0; } catch (e) { /* ignore */ }
            pushHistory();
            updateLayerPanel();
            setStatus('Clip cargado.');
          } catch (e) {
            setStatus('No se pudo cargar clip.', true);
          }
        });
      });
      Array.from(clipsList.querySelectorAll('[data-vs-clip-del]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-clip-del') || 0);
          if (!id) return;
          const ok = window.confirm('¿Borrar clip?');
          if (!ok) return;
          try {
            const resp = await fetch(clipDeleteUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
              credentials: 'same-origin',
              body: JSON.stringify({ id }),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
            if (activeClipId === id) activeClipId = 0;
            await refreshClips();
            setStatus('Clip borrado.');
          } catch (e) {
            setStatus('No se pudo borrar clip.', true);
          }
        });
      });
    };

    const refreshClips = async () => {
      if (!clipsUrl || !videoId) return;
      try {
        const resp = await fetch(`${clipsUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        renderClips(Array.isArray(data?.items) ? data.items : []);
      } catch (e) {
        renderClips([]);
      }
    };

    const saveClip = async () => {
      if (!clipSaveUrl || !videoId) return;
      const title = safeText(clipTitleInput?.value, 'Clip').slice(0, 180);
      const collection = safeText(clipCollectionInput?.value, '').slice(0, 120);
      const inS = Number(inInput?.value || 0) || 0;
      const outS = Number(outInput?.value || 0) || 0;
      if (!outS || outS <= inS) {
        setStatus('Define IN/OUT para el clip.', true);
        return;
      }
      const overlay = { ...fabricCanvas.toDatalessJSON(['data']), fx: { layers: fxState.layers } };
      try {
        const resp = await fetch(clipSaveUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ id: activeClipId || 0, video_id: videoId, title, collection, in_s: inS, out_s: outS, overlay }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        activeClipId = Number(data?.id) || activeClipId;
        await refreshClips();
        setStatus('Clip guardado.');
      } catch (e) {
        setStatus('No se pudo guardar clip.', true);
      }
    };
    clipSaveBtn?.addEventListener('click', saveClip);
    clipRefreshBtn?.addEventListener('click', refreshClips);
    refreshClips();

    // Timeline (server)
    const renderTimeline = (items) => {
      if (!timelineList) return;
      const rows = (Array.isArray(items) ? items : []).slice(0, 260).map((ev) => {
        const id = Number(ev?.id) || 0;
        if (!id) return '';
        const kind = safeText(ev?.kind, 'tag').toUpperCase();
        const label = safeText(ev?.label, '');
        const color = safeText(ev?.color, '');
        const at = fmtTimeShort(Number(ev?.time_s) || 0);
        return `
          <div class="row">
            <div style="display:flex; flex-direction:column; gap:0.05rem;">
              <strong>${at} · ${kind}</strong>
              <small>${label || '—'}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap; align-items:center;">
              ${color ? `<span style="width:12px;height:12px;border-radius:999px;background:${color};display:inline-block;border:1px solid rgba(255,255,255,0.25);"></span>` : ''}
              <button type="button" class="button" data-vs-ev-go="${id}">Ir</button>
              <button type="button" class="button danger" data-vs-ev-del="${id}">Borrar</button>
            </div>
          </div>
        `;
      }).filter(Boolean).join('');
      timelineList.innerHTML = rows || '<div class="meta">Sin eventos.</div>';

      Array.from(timelineList.querySelectorAll('[data-vs-ev-go]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-ev-go') || 0);
          if (!id) return;
          try {
            const resp = await fetch(`${timelineUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
            const data = await resp.json().catch(() => ({}));
            const items2 = Array.isArray(data?.items) ? data.items : [];
            const found = items2.find((x) => Number(x?.id) === id);
            if (!found) return;
            const seek = Number(found?.time_s) || 0;
            video.currentTime = seek;
            setStatus(`Timeline → ${fmtTimeShort(seek)}`);
          } catch (e) {
            setStatus('No se pudo ir al evento.', true);
          }
        });
      });
      Array.from(timelineList.querySelectorAll('[data-vs-ev-del]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-ev-del') || 0);
          if (!id) return;
          const ok = window.confirm('¿Borrar evento?');
          if (!ok) return;
          try {
            const resp = await fetch(timelineDeleteUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
              credentials: 'same-origin',
              body: JSON.stringify({ id }),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
            await refreshTimeline();
            setStatus('Evento borrado.');
          } catch (e) {
            setStatus('No se pudo borrar.', true);
          }
        });
      });
    };

    const refreshTimeline = async () => {
      if (!timelineUrl || !videoId) return;
      try {
        const resp = await fetch(`${timelineUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        renderTimeline(Array.isArray(data?.items) ? data.items : []);
      } catch (e) {
        renderTimeline([]);
      }
    };

    const addTimelineEvent = async () => {
      if (!timelineSaveUrl || !videoId) return;
      const kind = safeText(eventKindSelect?.value, 'tag');
      const label = safeText(eventLabelInput?.value, '');
      const color = strokeColor();
      const timeS = Number(video.currentTime) || 0;
      try {
        const resp = await fetch(timelineSaveUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ video_id: videoId, time_s: timeS, kind, label, color }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        if (eventLabelInput) eventLabelInput.value = '';
        await refreshTimeline();
        setStatus(`Evento añadido en ${fmtTimeShort(timeS)}.`);
      } catch (e) {
        setStatus('No se pudo añadir evento.', true);
      }
    };
    eventAddBtn?.addEventListener('click', addTimelineEvent);
    eventRefreshBtn?.addEventListener('click', refreshTimeline);
    refreshTimeline();

    const applyTimedLayers = () => {
      const nowS = Number(video.currentTime) || 0;
      let anyAnim = false;
      for (const obj of fabricCanvas.getObjects()) {
        ensureLayerData(obj);
        const alpha = computeTimedAlpha(obj.data, nowS);
        obj.visible = alpha > 0.001;
        obj.opacity = clamp(alpha, 0, 1);

        if (safeText(obj.data.anim, 'none') === 'draw') {
          anyAnim = true;
          const tIn = Math.max(0, Number(obj.data.t_in_s) || 0);
          const animMs = Math.max(50, Number(obj.data.anim_ms) || 700);
          const prog = clamp((nowS - tIn) / (animMs / 1000), 0, 1);
          if (obj.type === 'group' && Array.isArray(obj._objects)) {
            const line = obj._objects.find((x) => x?.type === 'line');
            const head = obj._objects.find((x) => x?.type === 'polygon');
            if (line && Number.isFinite(line.x1) && Number.isFinite(line.x2)) {
              const len = Math.max(1, Math.hypot((line.x2 - line.x1), (line.y2 - line.y1)));
              line.strokeDashArray = [len, len];
              line.strokeDashOffset = len * (1 - prog);
              line.dirty = true;
            }
            if (head) {
              head.opacity = prog >= 0.98 ? 1 : 0;
              head.dirty = true;
            }
          }
        }
      }
      if (!video.paused || anyAnim) {
        try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
      }
      try { renderFx(fxCtx, { width: fxEl.width, height: fxEl.height, nowS, forExport: false }); } catch (e) { /* ignore */ }
    };

    const tick = () => {
      try { applyTimedLayers(); } catch (e) { /* ignore */ }
      window.requestAnimationFrame(tick);
    };
    window.requestAnimationFrame(tick);
    video.addEventListener('timeupdate', () => { if (video.paused) applyTimedLayers(); });

    pushHistory();
    reseedFxSeq();
    renderFxList();
    updateLayerPanel();
    setStatus('Listo.');
  };

  document.addEventListener('DOMContentLoaded', init);
})();
