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

	    const miniTimeline = document.getElementById('vs-mini-timeline');
	    const miniTrack = document.getElementById('vs-mini-track');
	    const miniCursor = document.getElementById('vs-mini-cursor');

	    const btnPlay = document.getElementById('vs-play');
	    const btnPause = document.getElementById('vs-pause');
	    const btnLoop = document.getElementById('vs-loop');
	    const speedSelect = document.getElementById('vs-speed');
	    const btnIn = document.getElementById('vs-mark-in');
	    const btnOut = document.getElementById('vs-mark-out');
	    const btnExportSeg = document.getElementById('vs-export-seg');
	    const btnExportShare = document.getElementById('vs-export-share');
	    const btnRecord = document.getElementById('vs-record');
	    const btnSnap = document.getElementById('vs-snap');
	    const btnFreeze = document.getElementById('vs-freeze');

    const btnSelect = document.getElementById('vs-tool-select');
    const btnPen = document.getElementById('vs-tool-pen');
    const btnArrow = document.getElementById('vs-tool-arrow');
    const btnText = document.getElementById('vs-tool-text');
    const btnCallout = document.getElementById('vs-tool-callout');
    const btnSpot = document.getElementById('vs-tool-spot');
    const btnBlur = document.getElementById('vs-tool-blur');
    const btnUndo = document.getElementById('vs-undo');
    const btnClear = document.getElementById('vs-clear');
    const colorInput = document.getElementById('vs-color');
    const widthInput = document.getElementById('vs-width');

    const inInput = document.getElementById('vs-in');
    const outInput = document.getElementById('vs-out');
    const qualitySelect = document.getElementById('vs-video-quality');
    const fpsSelect = document.getElementById('vs-video-fps');
    const audioToggle = document.getElementById('vs-video-audio');
    const slideAddBtn = document.getElementById('vs-slide-add');
    const slidesFromTimelineBtn = document.getElementById('vs-slides-from-timeline');
    const slidesClearBtn = document.getElementById('vs-slides-clear');
    const slidesList = document.getElementById('vs-slides');
    const exportPdfBtn = document.getElementById('vs-export-pdf');
    const exportPackageBtn = document.getElementById('vs-export-package');

	    const videoId = Number(document.getElementById('vs-video-id')?.value || 0);
	    const initialClipId = Number(document.getElementById('vs-initial-clip-id')?.value || 0);
	    const projectsUrl = safeText(document.getElementById('vs-projects-url')?.value);
    const projectSaveUrl = safeText(document.getElementById('vs-project-save-url')?.value);
    const projectDeleteUrl = safeText(document.getElementById('vs-project-delete-url')?.value);
    const clipsUrl = safeText(document.getElementById('vs-clips-url')?.value);
    const clipSaveUrl = safeText(document.getElementById('vs-clip-save-url')?.value);
	    const clipDeleteUrl = safeText(document.getElementById('vs-clip-delete-url')?.value);
	    const shareClipCreateUrl = safeText(document.getElementById('vs-share-clip-create-url')?.value);
	    const shareLinksUrl = safeText(document.getElementById('vs-share-links-url')?.value);
	    const timelineUrl = safeText(document.getElementById('vs-timeline-url')?.value);
    const timelineSaveUrl = safeText(document.getElementById('vs-timeline-save-url')?.value);
    const timelineDeleteUrl = safeText(document.getElementById('vs-timeline-delete-url')?.value);
	    const timelineExportUrl = safeText(document.getElementById('vs-timeline-export-url')?.value);
	    const timelineImportUrl = safeText(document.getElementById('vs-timeline-import-url')?.value);
	    const timelineClearUrl = safeText(document.getElementById('vs-timeline-clear-url')?.value);
	    const exportPdfUrl = safeText(document.getElementById('vs-export-pdf-url')?.value);
	    const exportPackageUrl = safeText(document.getElementById('vs-export-package-url')?.value);
	    const exportUploadUrl = safeText(document.getElementById('vs-export-upload-url')?.value);

    const projectTitleInput = document.getElementById('vs-project-title');
    const projectSaveBtn = document.getElementById('vs-project-save');
    const projectRefreshBtn = document.getElementById('vs-project-refresh');
    const projectsList = document.getElementById('vs-projects');

	    const clipTitleInput = document.getElementById('vs-clip-title');
	    const clipCollectionInput = document.getElementById('vs-clip-collection');
	    const clipTagsInput = document.getElementById('vs-clip-tags');
	    const clipNotesInput = document.getElementById('vs-clip-notes');
	    const clipSearchInput = document.getElementById('vs-clip-search');
	    const clipCollectionFilterSelect = document.getElementById('vs-clip-filter-collection');
	    const clipClearFiltersBtn = document.getElementById('vs-clip-clear-filters');
	    const clipCollectionsWrap = document.getElementById('vs-clip-collections');
	    const clipCountEl = document.getElementById('vs-clip-count');
	    const clipSaveBtn = document.getElementById('vs-clip-save');
	    const clipRefreshBtn = document.getElementById('vs-clip-refresh');
	    const clipsList = document.getElementById('vs-clips');

    const eventKindSelect = document.getElementById('vs-event-kind');
    const eventLabelInput = document.getElementById('vs-event-label');
    const eventAddBtn = document.getElementById('vs-event-add');
    const eventRefreshBtn = document.getElementById('vs-event-refresh');
    const timelineList = document.getElementById('vs-timeline');
	    const timelineSearchInput = document.getElementById('vs-timeline-search');
	    const timelineKindFilterSelect = document.getElementById('vs-timeline-filter-kind');
	    const timelineCountEl = document.getElementById('vs-timeline-count');
	    const timelinePrevBtn = document.getElementById('vs-timeline-prev');
	    const timelineNextBtn = document.getElementById('vs-timeline-next');
	    const timelineExportBtn = document.getElementById('vs-timeline-export');
    const timelineImportBtn = document.getElementById('vs-timeline-import');
    const timelineClearBtn = document.getElementById('vs-timeline-clear');
    const timelineImportFile = document.getElementById('vs-timeline-import-file');

	    const shareRefreshBtn = document.getElementById('vs-share-refresh');
	    const shareLinksList = document.getElementById('vs-share-links');

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
    const drawLayersList = document.getElementById('vs-draw-layers');

    const fxForm = document.getElementById('vs-fx-form');
    const fxSpotControls = document.getElementById('vs-fx-spot-controls');
    const fxBlurControls = document.getElementById('vs-fx-blur-controls');
    const fxIntensityInput = document.getElementById('vs-fx-intensity');
    const fxFeatherInput = document.getElementById('vs-fx-feather');
    const fxBlurInput = document.getElementById('vs-fx-blur');
    const fxOpacityInput = document.getElementById('vs-fx-opacity');

    const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

    const downloadResponseBlob = async (resp, fallbackName) => {
      const blob = await resp.blob();
      let name = fallbackName || 'export.bin';
      try {
        const cd = resp.headers.get('content-disposition') || '';
        const m = /filename=\"([^\"]+)\"/i.exec(cd);
        if (m && m[1]) name = m[1];
      } catch (e) { /* ignore */ }
      downloadBlob(blob, name);
    };

    const postJsonDownload = async ({ url, payload, fallbackName }) => {
      if (!url) return;
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(payload || {}),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err?.error || 'error');
      }
      await downloadResponseBlob(resp, fallbackName);
    };

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

	    // Playback helpers
	    let loopActive = false;
	    const updateLoopUi = () => {
	      if (!btnLoop) return;
	      btnLoop.classList.toggle('primary', loopActive);
	      btnLoop.textContent = loopActive ? 'Loop ✓' : 'Loop';
	    };
	    if (initialClipId && String(window.location.pathname || '').includes('/analysis/video/clip/')) {
	      loopActive = true;
	    }
	    updateLoopUi();
	    btnLoop?.addEventListener('click', () => {
	      loopActive = !loopActive;
	      updateLoopUi();
	      setStatus(loopActive ? 'Loop activado.' : 'Loop desactivado.');
	    });
	    speedSelect?.addEventListener('change', () => {
	      const sp = Number(speedSelect.value || 1) || 1;
	      try { video.playbackRate = clamp(sp, 0.25, 4); } catch (e) { /* ignore */ }
	      setStatus(`Velocidad: ${String(video.playbackRate || sp)}x`);
	    });
	    try {
	      const sp0 = Number(speedSelect?.value || 1) || 1;
	      video.playbackRate = clamp(sp0, 0.25, 4);
	    } catch (e) { /* ignore */ }

	    const enforceLoop = () => {
	      if (!loopActive) return;
	      const a = Number(inInput?.value || 0) || 0;
	      const b = Number(outInput?.value || 0) || 0;
	      const start = Math.max(0, Math.min(a, b));
	      const end = Math.max(a, b);
	      if (!end || end <= start) return;
	      const now = Number(video.currentTime) || 0;
	      if (now >= end) {
	        try { video.currentTime = start; } catch (e) { /* ignore */ }
	      }
	    };
	    const updateMiniCursor = () => {
	      if (!miniCursor) return;
	      const dur = Number(video.duration) || 0;
	      if (!dur || !Number.isFinite(dur)) return;
	      const now = Math.max(0, Number(video.currentTime) || 0);
	      const pct = clamp(now / dur, 0, 1) * 100;
	      miniCursor.style.left = `${pct}%`;
	    };
	    video.addEventListener('timeupdate', () => {
	      enforceLoop();
	      updateMiniCursor();
	    });

	    const renderMiniTimeline = () => {
	      if (!miniTimeline || !miniTrack) return;
	      const dur = Number(video.duration) || 0;
	      if (!dur || !Number.isFinite(dur)) {
	        miniTrack.innerHTML = '';
	        return;
	      }
	      const clips = Array.isArray(clipsCache) ? clipsCache : [];
	      const events = Array.isArray(timelineCache) ? timelineCache : [];
	      const segHtml = clips.slice(0, 220).map((c) => {
	        const a = Math.max(0, Number(c?.in_s) || 0);
	        const b = Math.max(0, Number(c?.out_s) || 0);
	        const start = Math.min(a, b);
	        const end = Math.max(a, b);
	        if (!end || end <= start) return '';
	        const left = clamp(start / dur, 0, 1) * 100;
	        const width = Math.max(0.4, clamp((end - start) / dur, 0, 1) * 100);
	        return `<div data-seek="${start}" title="${safeText(c?.title, 'Clip')}" style="position:absolute;left:${left}%;width:${width}%;top:0;bottom:0;background:rgba(34,211,238,0.16);border-right:1px solid rgba(34,211,238,0.22);"></div>`;
	      }).filter(Boolean).join('');
	      const evHtml = events.slice(0, 420).map((ev) => {
	        const t = Math.max(0, Number(ev?.time_s) || 0);
	        const left = clamp(t / dur, 0, 1) * 100;
	        const color = safeText(ev?.color, '') || 'rgba(250,204,21,0.95)';
	        return `<div data-seek="${t}" title="${safeText(ev?.label, safeText(ev?.kind, 'tag'))}" style="position:absolute;left:${left}%;top:50%;transform:translate(-50%,-50%);width:7px;height:7px;border-radius:999px;background:${color};border:1px solid rgba(255,255,255,0.35);"></div>`;
	      }).join('');
	      miniTrack.innerHTML = segHtml + evHtml;
	      updateMiniCursor();
	    };

	    miniTimeline?.addEventListener('click', (ev) => {
	      const dur = Number(video.duration) || 0;
	      if (!dur || !Number.isFinite(dur)) return;
	      const targetSeek = Number(ev.target?.getAttribute?.('data-seek') || 0);
	      if (targetSeek) {
	        try { video.currentTime = Math.max(0, targetSeek); } catch (e) { /* ignore */ }
	        setStatus(`→ ${fmtTimeShort(targetSeek)}`);
	        return;
	      }
	      const rect = miniTimeline.getBoundingClientRect();
	      const pct = clamp((ev.clientX - rect.left) / Math.max(1, rect.width), 0, 1);
	      const t = pct * dur;
	      try { video.currentTime = t; } catch (e) { /* ignore */ }
	      setStatus(`→ ${fmtTimeShort(t)}`);
	    });
	    video.addEventListener('loadedmetadata', renderMiniTimeline);

	    const history = [];
	    const pushHistory = () => {
      try {
        const json = fabricCanvas.toDatalessJSON(['data']);
        history.push(json);
        if (history.length > 40) history.shift();
      } catch (e) { /* ignore */ }
    };

    const newUid = () => {
      try {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
      } catch (e) { /* ignore */ }
      return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    };

    const ensureLayerData = (obj) => {
      if (!obj) return;
      if (!obj.data || typeof obj.data !== 'object') obj.data = {};
      if (!safeText(obj.data.uid)) obj.data.uid = newUid();
      if (obj.data.t_in_s == null) obj.data.t_in_s = 0;
      if (obj.data.t_out_s == null) obj.data.t_out_s = 0;
      if (obj.data.fade_in_ms == null) obj.data.fade_in_ms = 0;
      if (obj.data.fade_out_ms == null) obj.data.fade_out_ms = 0;
      if (obj.data.anim == null) obj.data.anim = 'none';
    };

    const seedLayerDataNow = (extra = {}) => ({
      uid: newUid(),
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

      const layers = Array.isArray(fxState.layers) ? fxState.layers : [];
      const freezeActive = [];
      const blurActive = [];
      const spotActive = [];

      for (const layer of layers) {
        const kind = safeText(layer?.kind);
        const alpha = computeTimedAlpha(layer, t);
        if (alpha <= 0.001) continue;
        if (kind === 'freeze') freezeActive.push({ layer, alpha });
        if (kind === 'blur') blurActive.push({ layer, alpha });
        if (kind === 'spotlight') spotActive.push({ layer, alpha });
      }

      if (!forExport && fxPreview && safeText(fxPreview?.kind) === 'spotlight') spotActive.push({ layer: fxPreview, alpha: 1 });
      if (!forExport && fxPreview && safeText(fxPreview?.kind) === 'blur') blurActive.push({ layer: fxPreview, alpha: 1 });

      // Freeze (overlay full-frame)
      const freezeCache = renderFx._freezeCache || (renderFx._freezeCache = new Map());
      for (const item of freezeActive) {
        const imgData = safeText(item.layer?.image_data, '');
        if (!imgData) continue;
        let img = freezeCache.get(imgData);
        if (!img) {
          img = new Image();
          img.src = imgData;
          freezeCache.set(imgData, img);
        }
        if (!img || !img.complete) continue;
        try {
          ctx.save();
          ctx.globalCompositeOperation = 'source-over';
          ctx.globalAlpha = clamp(item.alpha, 0, 1);
          ctx.drawImage(img, 0, 0, w, h);
          ctx.restore();
        } catch (e) { /* ignore */ }
      }

      // Blur (rect overlay)
      if (!freezeActive.length) {
        for (const item of blurActive) {
          const l = item.layer;
          const x = clamp(Number(l?.x) || 0, 0, w);
          const y = clamp(Number(l?.y) || 0, 0, h);
          const bw = clamp(Number(l?.w) || 0, 0, w);
          const bh = clamp(Number(l?.h) || 0, 0, h);
          const blurPx = clamp(Number(l?.blur_px ?? 10), 0, 40);
          const op = clamp(Number(l?.opacity ?? 1), 0, 1);
          if (bw < 6 || bh < 6 || blurPx <= 0 || op <= 0) continue;
          try {
            ctx.save();
            ctx.globalCompositeOperation = 'source-over';
            ctx.globalAlpha = clamp(item.alpha * op, 0, 1);
            ctx.filter = `blur(${blurPx}px)`;
            ctx.beginPath();
            ctx.rect(x, y, bw, bh);
            ctx.clip();
            ctx.drawImage(video, 0, 0, w, h);
            ctx.restore();
          } catch (e) { /* ignore */ }
        }
      }

      // Spotlight (darken outside)
      if (spotActive.length) {
        const base = Math.max(...spotActive.map((x) => clamp(Number(x.layer?.intensity ?? 0.68), 0, 0.9)));
        ctx.save();
        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = `rgba(0,0,0,${clamp(base, 0, 0.9)})`;
        ctx.fillRect(0, 0, w, h);

        ctx.globalCompositeOperation = 'destination-out';
        for (const item of spotActive) {
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
      }

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
        if (selected && selected.kind === 'blur') {
          try {
            ctx.save();
            ctx.globalCompositeOperation = 'source-over';
            ctx.strokeStyle = 'rgba(34,211,238,0.9)';
            ctx.lineWidth = 2;
            ctx.setLineDash([10, 8]);
            ctx.strokeRect(Number(selected.x) || 0, Number(selected.y) || 0, Number(selected.w) || 0, Number(selected.h) || 0);
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
        if (fxPreview && fxPreview.kind === 'blur') {
          try {
            ctx.save();
            ctx.globalCompositeOperation = 'source-over';
            ctx.strokeStyle = 'rgba(250,204,21,0.95)';
            ctx.lineWidth = 2;
            ctx.setLineDash([8, 6]);
            ctx.strokeRect(Number(fxPreview.x) || 0, Number(fxPreview.y) || 0, Number(fxPreview.w) || 0, Number(fxPreview.h) || 0);
            ctx.restore();
          } catch (e) { /* ignore */ }
        }
      }
    };

    const renderFxList = () => {
      if (!fxLayersList) return;
      const items = (Array.isArray(fxState.layers) ? fxState.layers : []).slice(0, 80);
      const rows = items.map((l) => {
        const id = Number(l?.id) || 0;
        if (!id) return '';
        const inS = Number(l?.t_in_s) || 0;
        const outS = Number(l?.t_out_s) || 0;
        const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS || inS)}`;
        const isSel = selectedFxId === id;
        const kind = safeText(l?.kind, 'fx');
        const title = kind === 'spotlight' ? 'Spotlight' : (kind === 'blur' ? 'Blur' : (kind === 'freeze' ? 'Freeze' : kind));
        return `
          <div class="row" style="${isSel ? 'border-color: rgba(34,211,238,0.55); background: rgba(34,211,238,0.07);' : ''}">
            <div style="display:flex; flex-direction:column; gap:0.05rem;">
              <strong>${title}</strong>
              <small>${label}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-vs-fx-edit="${id}">Editar</button>
              <button type="button" class="button danger" data-vs-fx-del="${id}">Borrar</button>
            </div>
          </div>
        `;
      }).filter(Boolean).join('');
      fxLayersList.innerHTML = rows || '<div class="hint">Sin FX.</div>';

      Array.from(fxLayersList.querySelectorAll('[data-vs-fx-edit]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = Number(btn.getAttribute('data-vs-fx-edit') || 0);
          if (!id) return;
          selectedFxId = id;
          try { fabricCanvas.discardActiveObject(); } catch (e) { /* ignore */ }
          updateLayerPanel();
          renderFxList();
          renderDrawLayers();
        });
      });
      Array.from(fxLayersList.querySelectorAll('[data-vs-fx-del]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = Number(btn.getAttribute('data-vs-fx-del') || 0);
          if (!id) return;
          const ok = window.confirm('¿Borrar FX?');
          if (!ok) return;
          fxState.layers = (Array.isArray(fxState.layers) ? fxState.layers : []).filter((x) => Number(x?.id) !== id);
          if (selectedFxId === id) selectedFxId = 0;
          reseedFxSeq();
          renderFxList();
          updateLayerPanel();
          renderDrawLayers();
        });
      });
    };

    const restoreJson = (json) => {
      if (!json) return;
      fabricCanvas.loadFromJSON(json, () => {
        try { fabricCanvas.getObjects().forEach((o) => ensureLayerData(o)); } catch (e) { /* ignore */ }
        fabricCanvas.renderAll();
        updateLayerPanel();
        renderDrawLayers();
      });
    };

    const kindLabel = (obj) => {
      const kind = safeText(obj?.data?.kind) || safeText(obj?.type);
      if (kind === 'arrow') return 'Flecha';
      if (kind === 'callout') return `Callout ${safeText(obj?.data?.callout_n)}`;
      if (kind === 'path') return 'Trazo';
      if (kind === 'text') return 'Texto';
      if (kind === 'group') return safeText(obj?.data?.kind, 'Grupo');
      return safeText(kind, 'Capa');
    };

    const renderDrawLayers = () => {
      if (!drawLayersList) return;
      const objs = (fabricCanvas.getObjects?.() || []).slice(0, 160);
      const rows = objs.slice().reverse().slice(0, 60).map((obj) => {
        ensureLayerData(obj);
        const uid = safeText(obj?.data?.uid);
        if (!uid) return '';
        const tIn = Number(obj?.data?.t_in_s) || 0;
        const tOut = Number(obj?.data?.t_out_s) || 0;
        const label = `${fmtTimeShort(tIn)} → ${fmtTimeShort(tOut || tIn)}`;
        const isSel = activeObject() === obj;
        return `
          <div class="row" style="${isSel ? 'border-color: rgba(34,211,238,0.55); background: rgba(34,211,238,0.07);' : ''}">
            <div style="display:flex; flex-direction:column; gap:0.05rem;">
              <strong>${kindLabel(obj)}</strong>
              <small>${label}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-vs-draw-select="${uid}">Seleccionar</button>
              <button type="button" class="button" data-vs-draw-seek="${uid}">Ir</button>
              <button type="button" class="button danger" data-vs-draw-del="${uid}">Borrar</button>
            </div>
          </div>
        `;
      }).filter(Boolean).join('');
      drawLayersList.innerHTML = rows || '<div class="hint">Sin dibujos.</div>';

      const uidMap = new Map();
      for (const o of objs) {
        ensureLayerData(o);
        const uid = safeText(o?.data?.uid);
        if (uid) uidMap.set(uid, o);
      }

      Array.from(drawLayersList.querySelectorAll('[data-vs-draw-select]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const uid = safeText(btn.getAttribute('data-vs-draw-select'));
          const obj = uidMap.get(uid);
          if (!obj) return;
          try { fabricCanvas.setActiveObject(obj); } catch (e) { /* ignore */ }
          selectedFxId = 0;
          updateLayerPanel();
          renderFxList();
          renderDrawLayers();
        });
      });
      Array.from(drawLayersList.querySelectorAll('[data-vs-draw-seek]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const uid = safeText(btn.getAttribute('data-vs-draw-seek'));
          const obj = uidMap.get(uid);
          if (!obj) return;
          const tIn = Number(obj?.data?.t_in_s) || 0;
          try { video.currentTime = Math.max(0, tIn); } catch (e) { /* ignore */ }
        });
      });
      Array.from(drawLayersList.querySelectorAll('[data-vs-draw-del]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const uid = safeText(btn.getAttribute('data-vs-draw-del'));
          const obj = uidMap.get(uid);
          if (!obj) return;
          const ok = window.confirm('¿Borrar dibujo?');
          if (!ok) return;
          try { fabricCanvas.remove(obj); } catch (e) { /* ignore */ }
          pushHistory();
          updateLayerPanel();
          renderDrawLayers();
        });
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

      if (tool !== 'spot' && tool !== 'blur') fxPreview = null;
      fxEl.style.pointerEvents = (tool === 'spot' || tool === 'blur') ? 'auto' : 'none';

      Array.from([btnSelect, btnPen, btnArrow, btnText, btnCallout, btnSpot, btnBlur]).forEach((b) => b?.classList.remove('primary'));
      if (tool === 'select') btnSelect?.classList.add('primary');
      if (tool === 'pen') btnPen?.classList.add('primary');
      if (tool === 'arrow') btnArrow?.classList.add('primary');
      if (tool === 'text') btnText?.classList.add('primary');
      if (tool === 'callout') btnCallout?.classList.add('primary');
      if (tool === 'spot') btnSpot?.classList.add('primary');
      if (tool === 'blur') btnBlur?.classList.add('primary');
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
        if (fxForm) fxForm.style.display = 'none';
        return;
      }
      layerEmpty.style.display = 'none';
      layerForm.style.display = 'grid';

      if (target.type === 'fx') {
        const fx = target.fx;
        const kind = safeText(fx?.kind, 'fx');
        const title = kind === 'spotlight' ? 'Spotlight' : (kind === 'blur' ? 'Blur' : (kind === 'freeze' ? 'Freeze' : kind));
        if (layerKind) layerKind.textContent = `FX · ${title}`;
        if (layerInInput) layerInInput.value = String((Number(fx.t_in_s) || 0).toFixed(1));
        if (layerOutInput) layerOutInput.value = String((Number(fx.t_out_s) || 0).toFixed(1));
        if (layerFadeInInput) layerFadeInInput.value = String(Math.max(0, Number(fx.fade_in_ms) || 0));
        if (layerFadeOutInput) layerFadeOutInput.value = String(Math.max(0, Number(fx.fade_out_ms) || 0));
        if (layerAnimSelect) layerAnimSelect.value = 'none';
        if (layerAnimSelect) layerAnimSelect.disabled = true;
        const showFxControls = kind === 'spotlight' || kind === 'blur';
        if (fxForm) fxForm.style.display = showFxControls ? '' : 'none';
        if (fxSpotControls) fxSpotControls.style.display = kind === 'spotlight' ? '' : 'none';
        if (fxBlurControls) fxBlurControls.style.display = kind === 'blur' ? '' : 'none';
        if (fxIntensityInput) fxIntensityInput.value = String(clamp(Number(fx.intensity ?? 0.68), 0.2, 0.9));
        if (fxFeatherInput) fxFeatherInput.value = String(clamp(Number(fx.feather ?? 0.18), 0.02, 0.6));
        if (fxBlurInput) fxBlurInput.value = String(clamp(Number(fx.blur_px ?? 10), 0, 40));
        if (fxOpacityInput) fxOpacityInput.value = String(clamp(Number(fx.opacity ?? 1), 0, 1));
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
      if (fxForm) fxForm.style.display = 'none';
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

    const applyFxPanelEdits = () => {
      const fx = selectedFxId ? getFxById(selectedFxId) : null;
      if (!fx) return;
      const kind = safeText(fx?.kind, 'fx');
      if (kind === 'spotlight') {
        fx.intensity = clamp(Number(fxIntensityInput?.value ?? fx.intensity ?? 0.68), 0.2, 0.9);
        fx.feather = clamp(Number(fxFeatherInput?.value ?? fx.feather ?? 0.18), 0.02, 0.6);
      } else if (kind === 'blur') {
        fx.blur_px = clamp(Number(fxBlurInput?.value ?? fx.blur_px ?? 10), 0, 40);
        fx.opacity = clamp(Number(fxOpacityInput?.value ?? fx.opacity ?? 1), 0, 1);
      }
      renderFxList();
    };

    [layerInInput, layerOutInput, layerFadeInInput, layerFadeOutInput, layerAnimSelect].forEach((el) => {
      el?.addEventListener('change', () => { applyLayerPanelEdits(); updateLayerPanel(); });
    });
    [fxIntensityInput, fxFeatherInput, fxBlurInput, fxOpacityInput].forEach((el) => {
      el?.addEventListener('change', () => { applyFxPanelEdits(); updateLayerPanel(); });
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
        renderDrawLayers();
        return;
      }
      try { fabricCanvas.remove(target.obj); } catch (e) { /* ignore */ }
      pushHistory();
      updateLayerPanel();
      renderDrawLayers();
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
        renderDrawLayers();
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
        renderDrawLayers();
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
      renderDrawLayers();
      arrowStart = null;
    });
    fabricCanvas.on('path:created', (opt) => {
      const p = opt?.path;
      if (p) p.data = seedLayerDataNow();
      pushHistory();
      updateLayerPanel();
      renderDrawLayers();
    });
    fabricCanvas.on('selection:created', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); renderDrawLayers(); });
    fabricCanvas.on('selection:updated', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); renderDrawLayers(); });
    fabricCanvas.on('selection:cleared', () => { updateLayerPanel(); renderDrawLayers(); });

    btnSelect?.addEventListener('click', () => setTool('select'));
    btnPen?.addEventListener('click', () => setTool('pen'));
    btnArrow?.addEventListener('click', () => setTool('arrow'));
    btnText?.addEventListener('click', () => setTool('text'));
    btnCallout?.addEventListener('click', () => setTool('callout'));
    btnSpot?.addEventListener('click', () => setTool('spot'));
    btnBlur?.addEventListener('click', () => setTool('blur'));

    // Spotlight tool (FX canvas)
    let spotDrag = null;
    let blurDrag = null;
    const pointerToFx = (ev) => {
      const rect = fxEl.getBoundingClientRect();
      const x = clamp(((ev.clientX - rect.left) / rect.width) * fxEl.width, 0, fxEl.width);
      const y = clamp(((ev.clientY - rect.top) / rect.height) * fxEl.height, 0, fxEl.height);
      return { x, y };
    };
    fxEl.addEventListener('pointerdown', (ev) => {
      if (tool !== 'spot' && tool !== 'blur') return;
      try { fxEl.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
      const p = pointerToFx(ev);
      if (tool === 'spot') {
        spotDrag = { start: p };
        blurDrag = null;
        fxPreview = { kind: 'spotlight', cx: p.x, cy: p.y, r: 8, intensity: 0.68, feather: 0.18 };
      } else {
        blurDrag = { start: p };
        spotDrag = null;
        fxPreview = { kind: 'blur', x: p.x, y: p.y, w: 1, h: 1, blur_px: 10, opacity: 1 };
      }
      selectedFxId = 0;
      try { fabricCanvas.discardActiveObject(); } catch (e) { /* ignore */ }
      updateLayerPanel();
      renderFxList();
    });
    fxEl.addEventListener('pointermove', (ev) => {
      if (tool === 'spot' && spotDrag && fxPreview && fxPreview.kind === 'spotlight') {
        const p = pointerToFx(ev);
        const dx = p.x - spotDrag.start.x;
        const dy = p.y - spotDrag.start.y;
        fxPreview.cx = spotDrag.start.x;
        fxPreview.cy = spotDrag.start.y;
        fxPreview.r = Math.max(10, Math.hypot(dx, dy));
      }
      if (tool === 'blur' && blurDrag && fxPreview && fxPreview.kind === 'blur') {
        const p = pointerToFx(ev);
        const x0 = blurDrag.start.x;
        const y0 = blurDrag.start.y;
        const x1 = p.x;
        const y1 = p.y;
        fxPreview.x = Math.min(x0, x1);
        fxPreview.y = Math.min(y0, y1);
        fxPreview.w = Math.max(1, Math.abs(x1 - x0));
        fxPreview.h = Math.max(1, Math.abs(y1 - y0));
      }
    });
    const endFx = (ev) => {
      if ((tool === 'spot' && !spotDrag) || (tool === 'blur' && !blurDrag)) return;
      try { fxEl.releasePointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
      const now = Number(video.currentTime) || 0;
      if (tool === 'spot' && fxPreview && fxPreview.kind === 'spotlight' && Number(fxPreview.r) >= 12) {
        const layer = {
          id: fxSeq++,
          ...seedLayerDataNow({ t_in_s: now, t_out_s: 0, fade_in_ms: 150, fade_out_ms: 150 }),
          ...fxPreview,
        };
        fxState.layers = [...(Array.isArray(fxState.layers) ? fxState.layers : []), layer].slice(0, 80);
        selectedFxId = layer.id;
        renderFxList();
        updateLayerPanel();
        setStatus('Spotlight añadido.');
      }
      if (tool === 'blur' && fxPreview && fxPreview.kind === 'blur' && Number(fxPreview.w) >= 12 && Number(fxPreview.h) >= 12) {
        const layer = {
          id: fxSeq++,
          ...seedLayerDataNow({ t_in_s: now, t_out_s: 0, fade_in_ms: 150, fade_out_ms: 150 }),
          ...fxPreview,
        };
        fxState.layers = [...(Array.isArray(fxState.layers) ? fxState.layers : []), layer].slice(0, 80);
        selectedFxId = layer.id;
        renderFxList();
        updateLayerPanel();
        setStatus('Blur añadido.');
      }
      spotDrag = null;
      blurDrag = null;
      fxPreview = null;
    };
    fxEl.addEventListener('pointerup', endFx);
    fxEl.addEventListener('pointercancel', endFx);

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
      renderDrawLayers();
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

    const captureVideoFrameDataUrl = () => {
      try {
        const w = fabricCanvas.getWidth();
        const h = fabricCanvas.getHeight();
        if (!w || !h) return null;
        const off = document.createElement('canvas');
        off.width = w;
        off.height = h;
        const ctx = off.getContext('2d');
        if (!ctx) return null;
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(video, 0, 0, w, h);
        return off.toDataURL('image/png');
      } catch (e) {
        return null;
      }
    };

    btnFreeze?.addEventListener('click', () => {
      const img = captureVideoFrameDataUrl();
      if (!img) {
        setStatus('No se pudo capturar freeze.', true);
        return;
      }
      const now = Number(video.currentTime) || 0;
      const layer = {
        id: fxSeq++,
        ...seedLayerDataNow({ t_in_s: now, t_out_s: now + 1.2, fade_in_ms: 150, fade_out_ms: 150 }),
        kind: 'freeze',
        image_data: img,
      };
      fxState.layers = [...(Array.isArray(fxState.layers) ? fxState.layers : []), layer].slice(0, 80);
      selectedFxId = layer.id;
      renderFxList();
      updateLayerPanel();
      setStatus(`Freeze creado en ${fmtTimeShort(now)}.`);
    });

    let recActive = false;
    let recMedia = null;
    let recStream = null;
    let recChunks = [];
    let recCanvas = null;
    let recCtx = null;
    let recRaf = null;
    let stopAt = null;
    let recStartAt = null;
    let recDestination = 'download';
    let recUploadMeta = null;
    let exportAudioCtx = null;
    let exportAudioDest = null;
    let exportAudioSource = null;

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
	      recStartAt = null;
	      recDestination = 'download';
	      recUploadMeta = null;
	      if (btnRecord) btnRecord.textContent = 'Grabar';
	      if (btnExportSeg) btnExportSeg.disabled = false;
	      if (btnExportShare) btnExportShare.disabled = false;
	      setStatus('Grabación finalizada.');
	    };

	    const uploadExportBlob = async (blob, { title = '', clipId = 0 } = {}) => {
	      if (!exportUploadUrl) {
	        setStatus('No hay endpoint de subida para export.', true);
	        return null;
	      }
	      if (!blob || !blob.size) {
	        setStatus('Export vacío.', true);
	        return null;
	      }
	      const ext = String(blob.type || '').includes('mp4') ? 'mp4' : 'webm';
	      const safeTitle = safeText(title, 'Export').slice(0, 160);
	      const filename = `video-studio-${videoId || 'export'}.${ext}`;

	      setStatus('Subiendo export…');
	      return await new Promise((resolve) => {
	        try {
	          const xhr = new XMLHttpRequest();
	          xhr.open('POST', exportUploadUrl);
	          xhr.withCredentials = true;
	          const fd = new FormData();
	          fd.append('csrfmiddlewaretoken', csrf);
	          fd.append('video_id', String(videoId || ''));
	          if (clipId) fd.append('clip_id', String(clipId));
	          fd.append('title', safeTitle);
	          fd.append('file', blob, filename);
	          xhr.upload.addEventListener('progress', (e) => {
	            if (!e.lengthComputable) return;
	            const pct = Math.max(0, Math.min(100, Math.round((e.loaded / e.total) * 100)));
	            setStatus(`Subiendo… ${pct}%`);
	          });
	          xhr.addEventListener('load', async () => {
	            try {
	              const data = JSON.parse(xhr.responseText || '{}');
	              if (xhr.status >= 200 && xhr.status < 300 && data?.ok && data?.url) {
	                const url = String(data.url);
	                try {
	                  if (navigator.clipboard?.writeText) {
	                    await navigator.clipboard.writeText(url);
	                    setStatus('Export subido. Link copiado.');
	                  } else {
	                    setStatus('Export subido. Copia el link.');
	                    window.prompt('Copia este enlace:', url);
	                  }
	                } catch (e) {
	                  window.prompt('Copia este enlace:', url);
	                }
	                resolve(url);
	                return;
	              }
	              setStatus(data?.error || 'No se pudo subir export.', true);
	              resolve(null);
	            } catch (e) {
	              setStatus('No se pudo subir export.', true);
	              resolve(null);
	            }
	          });
	          xhr.addEventListener('error', () => {
	            setStatus('Error de red al subir export.', true);
	            resolve(null);
	          });
	          xhr.send(fd);
	        } catch (e) {
	          setStatus('No se pudo subir export.', true);
	          resolve(null);
	        }
	      });
	    };

	    const startRecording = async ({ from = null, to = null, destination = 'download', uploadTitle = '', uploadClipId = 0 } = {}) => {
	      if (recActive) return;
	      if (!('MediaRecorder' in window)) {
	        setStatus('Este navegador no soporta export de vídeo.', true);
	        return;
	      }
	      recDestination = safeText(destination, 'download');
	      recUploadMeta = { title: safeText(uploadTitle, ''), clipId: Number(uploadClipId || 0) || 0 };
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

      const q = safeText(qualitySelect?.value, 'med');
      const fps = q === 'low' ? 24 : 30;
      const bps = q === 'high' ? 8_000_000 : (q === 'low' ? 2_200_000 : 4_000_000);
      const canvasStream = recCanvas.captureStream(fps);
      let audioTracks = [];
      try {
        const vStream = typeof video.captureStream === 'function' ? video.captureStream() : null;
        audioTracks = vStream ? (vStream.getAudioTracks?.() || []) : [];
      } catch (e) { audioTracks = []; }
	      recStream = new MediaStream([...(canvasStream.getVideoTracks?.() || []), ...(audioTracks || [])]);

	      recChunks = [];
	      const mimeCandidates = [
	        'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
	        'video/mp4',
	        'video/webm;codecs=vp9,opus',
	        'video/webm;codecs=vp8,opus',
	        'video/webm',
	      ];
	      let mime = '';
	      for (const cand of mimeCandidates) {
	        try {
	          if (MediaRecorder.isTypeSupported(cand)) { mime = cand; break; }
	        } catch (e) { /* ignore */ }
	      }
	      if (!mime) mime = 'video/webm';

      try {
        recMedia = new MediaRecorder(recStream, { mimeType: mime, videoBitsPerSecond: bps });
      } catch (e) {
        recMedia = new MediaRecorder(recStream);
      }
	      recMedia.ondataavailable = (ev) => { if (ev.data && ev.data.size) recChunks.push(ev.data); };
	      recMedia.onstop = async () => {
	        try {
	          const blob = new Blob(recChunks, { type: recChunks[0]?.type || 'video/webm' });
	          const ext = String(blob.type || '').includes('mp4') ? 'mp4' : 'webm';
	          if (safeText(recDestination) === 'upload') {
	            const t = safeText(recUploadMeta?.title, '') || `Export ${videoId || ''}`.trim();
	            await uploadExportBlob(blob, { title: t, clipId: Number(recUploadMeta?.clipId || 0) || 0 });
	          } else {
	            downloadBlob(blob, `video-studio-${videoId || 'export'}.${ext}`);
	          }
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
	      if (btnExportShare) btnExportShare.disabled = true;
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

	    btnExportShare?.addEventListener('click', async () => {
	      const a = Number(inInput?.value || 0) || 0;
	      const b = Number(outInput?.value || 0) || 0;
	      const start = Math.max(0, Math.min(a, b));
	      const end = Math.max(a, b);
	      if (!end || end <= start) {
	        setStatus('Define IN/OUT primero.', true);
	        return;
	      }
	      const baseTitle = safeText(clipTitleInput?.value, '').slice(0, 180);
	      const coll = safeText(clipCollectionInput?.value, '').slice(0, 120);
	      const t = baseTitle ? (coll ? `${baseTitle} · ${coll}` : baseTitle) : `Export ${fmtTimeShort(start)}-${fmtTimeShort(end)}`;
	      return await startRecording({ from: start, to: end, destination: 'upload', uploadTitle: t, uploadClipId: activeClipId || 0 });
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
	      } else if (key === 'l') {
	        event.preventDefault();
	        btnLoop?.click();
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
	    let clipsCache = [];
	    const clipFilterState = { q: '', collection: '' };
	    const clipNorm = (value) => safeText(value, '').toLowerCase();
	    const escHtml = (value) => safeText(value, '')
	      .replaceAll('&', '&amp;')
	      .replaceAll('<', '&lt;')
	      .replaceAll('>', '&gt;')
	      .replaceAll('"', '&quot;')
	      .replaceAll("'", '&#39;');
	
	    const syncClipFiltersFromUi = () => {
	      clipFilterState.q = clipNorm(clipSearchInput?.value || '');
	      clipFilterState.collection = safeText(clipCollectionFilterSelect?.value, '').trim();
	    };
	
	    const applyClipFilters = (items) => {
	      syncClipFiltersFromUi();
	      const q = clipFilterState.q;
	      const coll = clipFilterState.collection;
	      return (Array.isArray(items) ? items : []).filter((c) => {
	        if (!c) return false;
	        const cColl = safeText(c?.collection, '').trim();
	        if (coll && cColl !== coll) return false;
	        if (!q) return true;
	        const tags = Array.isArray(c?.tags) ? c.tags : [];
	        const hay = [
	          safeText(c?.title, ''),
	          cColl,
	          safeText(c?.notes, ''),
	          tags.map((t) => safeText(t)).join(' '),
	        ].join(' ').toLowerCase();
	        return hay.includes(q);
	      });
	    };
	
	    const rebuildCollectionFilters = (items) => {
	      const list = (Array.isArray(items) ? items : []);
	      const counts = new Map();
	      for (const c of list) {
	        const name = safeText(c?.collection, '').trim();
	        if (!name) continue;
	        counts.set(name, (counts.get(name) || 0) + 1);
	      }
	      const collections = Array.from(counts.entries())
	        .sort((a, b) => a[0].localeCompare(b[0]))
	        .map(([name, count]) => ({ name, count }));
	
	      // Select options
	      if (clipCollectionFilterSelect) {
	        const current = safeText(clipCollectionFilterSelect.value, '');
	        clipCollectionFilterSelect.innerHTML = '<option value="">Todas</option>' + collections
	          .map((row) => `<option value="${escHtml(row.name)}">${escHtml(row.name)} (${row.count})</option>`)
	          .join('');
	        if (current && collections.some((r) => r.name === current)) clipCollectionFilterSelect.value = current;
	      }
	
	      // Chips
	      if (clipCollectionsWrap) {
	        const active = safeText(clipCollectionFilterSelect?.value, '');
	        const chips = collections.slice(0, 30).map((row) => {
	          const isActive = active && active === row.name;
	          return `<button type="button" class="button ${isActive ? 'primary' : 'ghost'}" data-vs-clip-coll="${escHtml(row.name)}">${escHtml(row.name)} <span style="opacity:0.75;">(${row.count})</span></button>`;
	        }).join('');
	        clipCollectionsWrap.innerHTML = chips || '<span class="hint">Sin colecciones.</span>';
	        Array.from(clipCollectionsWrap.querySelectorAll('[data-vs-clip-coll]')).forEach((btn) => {
	          btn.addEventListener('click', () => {
	            const name = safeText(btn.getAttribute('data-vs-clip-coll'), '');
	            if (!clipCollectionFilterSelect) return;
	            clipCollectionFilterSelect.value = (clipCollectionFilterSelect.value === name) ? '' : name;
	            renderClips(applyClipFilters(clipsCache));
	            rebuildCollectionFilters(clipsCache);
	          });
	        });
	      }
	    };

	    const clipUrlForId = (id) => {
	      try {
	        const u = new URL(window.location.href);
	        u.searchParams.set('clip', String(id));
	        return u.toString();
	      } catch (e) {
	        return `${window.location.pathname}?clip=${encodeURIComponent(String(id))}`;
	      }
	    };
	    const parseTagsInput = () => {
	      const raw = safeText(clipTagsInput?.value, '');
	      if (!raw) return [];
	      return raw
	        .split(',')
	        .map((t) => safeText(t).toLowerCase())
	        .filter(Boolean)
	        .slice(0, 24);
	    };

	    const fmtIsoShort = (iso) => {
	      const s = safeText(iso, '');
	      if (!s) return '';
	      try {
	        const d = new Date(s);
	        if (Number.isNaN(Number(d.getTime()))) return s.slice(0, 19).replace('T', ' ');
	        return d.toISOString().slice(0, 19).replace('T', ' ');
	      } catch (e) {
	        return s.slice(0, 19).replace('T', ' ');
	      }
	    };

	    const refreshShareLinks = async () => {
	      if (!shareLinksUrl || !videoId || !shareLinksList) return;
	      shareLinksList.innerHTML = '<div class="meta">Cargando…</div>';
	      try {
	        const resp = await fetch(`${shareLinksUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        const items = Array.isArray(data?.items) ? data.items : [];
	        const rows = items.slice(0, 220).map((l) => {
	          const token = safeText(l?.token, '');
	          if (!token) return '';
	          const kind = safeText(l?.kind, '').replaceAll('_', ' ').toUpperCase();
	          const title = safeText(l?.title, '');
	          const url = safeText(l?.share_url, '');
	          const revokeUrl = safeText(l?.revoke_url, '');
	          const exp = fmtIsoShort(l?.expires_at);
	          const active = Boolean(l?.is_active);
	          const hits = Number(l?.access_count) || 0;
	          return `
	            <div class="row">
	              <div style="display:flex; flex-direction:column; gap:0.05rem; min-width:0;">
	                <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escHtml(title || kind)}</strong>
	                <small>${escHtml(kind)}${exp ? ` · caduca ${escHtml(exp)}` : ''}${hits ? ` · ${hits} visitas` : ''}${active ? '' : ' · INACTIVO'}</small>
	              </div>
	              <div style="display:flex; gap:0.35rem; flex-wrap:wrap; align-items:center;">
	                <button type="button" class="button" data-vs-share-copy="${escHtml(url)}">Copiar</button>
	                <button type="button" class="button danger" data-vs-share-revoke="${escHtml(revokeUrl)}" ${active ? '' : 'disabled'}>Revocar</button>
	              </div>
	            </div>
	          `;
	        }).filter(Boolean).join('');
	        shareLinksList.innerHTML = rows || '<div class="meta">Sin enlaces.</div>';

	        Array.from(shareLinksList.querySelectorAll('[data-vs-share-copy]')).forEach((btn) => {
	          btn.addEventListener('click', async () => {
	            const url = safeText(btn.getAttribute('data-vs-share-copy'));
	            if (!url) return;
	            try {
	              if (navigator.clipboard?.writeText) {
	                await navigator.clipboard.writeText(url);
	                setStatus('Enlace copiado.');
	                return;
	              }
	            } catch (e) { /* ignore */ }
	            window.prompt('Copia este enlace:', url);
	          });
	        });
	        Array.from(shareLinksList.querySelectorAll('[data-vs-share-revoke]')).forEach((btn) => {
	          btn.addEventListener('click', async () => {
	            const url = safeText(btn.getAttribute('data-vs-share-revoke'));
	            if (!url) return;
	            const ok = window.confirm('¿Revocar este enlace?');
	            if (!ok) return;
	            try {
	              const resp2 = await fetch(url, {
	                method: 'POST',
	                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	                credentials: 'same-origin',
	                body: JSON.stringify({}),
	              });
	              const data2 = await resp2.json().catch(() => ({}));
	              if (!resp2.ok || !data2?.ok) throw new Error(data2?.error || 'error');
	              await refreshShareLinks();
	              setStatus('Enlace revocado.');
	            } catch (e) {
	              setStatus('No se pudo revocar.', true);
	            }
	          });
	        });
	      } catch (e) {
	        shareLinksList.innerHTML = '<div class="meta">No se pudieron cargar enlaces.</div>';
	      }
	    };

	    const renderClips = (items) => {
	      if (!clipsList) return;
	      const total = Array.isArray(clipsCache) ? clipsCache.length : 0;
	      const shown = Array.isArray(items) ? items.length : 0;
	      if (clipCountEl) clipCountEl.textContent = `${shown}/${total} clips`;
	      const rows = (Array.isArray(items) ? items : []).slice(0, 120).map((c) => {
	        const id = Number(c?.id) || 0;
	        if (!id) return '';
	        const title = safeText(c?.title, `Clip ${id}`);
	        const coll = safeText(c?.collection, '');
	        const inS = Number(c?.in_s) || 0;
	        const outS = Number(c?.out_s) || 0;
	        const tags = Array.isArray(c?.tags) ? c.tags : [];
	        const tagsLabel = tags.length ? ` · ${tags.slice(0, 6).map((t) => `#${safeText(t)}`).join(' ')}` : '';
	        const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS || inS)}`;
	        return `
	          <div class="row">
	            <div style="display:flex; flex-direction:column; gap:0.05rem;">
	              <strong>${title}</strong>
	              <small>${coll ? `${coll} · ` : ''}${label}${tagsLabel}</small>
	            </div>
		            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
		              <button type="button" class="button" data-vs-clip-load="${id}">Abrir</button>
		              <button type="button" class="button" data-vs-clip-link="${id}" data-vs-clip-view="${safeText(c?.view_url, '')}">Link</button>
		              <button type="button" class="button" data-vs-clip-share="${id}">Share</button>
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
	            if (clipTagsInput) clipTagsInput.value = (Array.isArray(found?.tags) ? found.tags : []).map((t) => safeText(t)).filter(Boolean).join(', ');
	            if (clipNotesInput) clipNotesInput.value = safeText(found?.notes, '');
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
	      Array.from(clipsList.querySelectorAll('[data-vs-clip-link]')).forEach((btn) => {
	        btn.addEventListener('click', async () => {
	          const id = Number(btn.getAttribute('data-vs-clip-link') || 0);
	          if (!id) return;
	          const viewUrl = safeText(btn.getAttribute('data-vs-clip-view'), '');
	          const link = viewUrl ? (new URL(viewUrl, window.location.origin)).toString() : clipUrlForId(id);
	          try {
	            if (navigator.clipboard?.writeText) {
	              await navigator.clipboard.writeText(link);
	              setStatus('Link copiado al portapapeles.');
	              return;
	            }
	          } catch (e) { /* ignore */ }
	          window.prompt('Copia este enlace:', link);
	        });
	      });
	      Array.from(clipsList.querySelectorAll('[data-vs-clip-share]')).forEach((btn) => {
	        btn.addEventListener('click', async () => {
	          const id = Number(btn.getAttribute('data-vs-clip-share') || 0);
	          if (!id) return;
	          if (!shareClipCreateUrl) {
	            setStatus('No hay endpoint de share.', true);
	            return;
	          }
	          setStatus('Creando enlace…');
	          try {
	            const body = new URLSearchParams();
	            body.set('clip_id', String(id));
	            body.set('valid_days', '14');
	            const resp = await fetch(shareClipCreateUrl, {
	              method: 'POST',
	              headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
	              credentials: 'same-origin',
	              body: body.toString(),
	            });
	            const data = await resp.json().catch(() => ({}));
	            if (!resp.ok || !data?.ok || !data?.url) throw new Error(data?.error || 'error');
	            const url = String(data.url);
	            try {
	              if (navigator.clipboard?.writeText) {
	                await navigator.clipboard.writeText(url);
	                setStatus('Enlace compartible copiado.');
	                refreshShareLinks();
	                return;
	              }
	            } catch (e) { /* ignore */ }
	            refreshShareLinks();
	            window.prompt('Copia este enlace:', url);
	          } catch (e) {
	            setStatus('No se pudo crear enlace.', true);
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
		        clipsCache = Array.isArray(data?.items) ? data.items : [];
		        rebuildCollectionFilters(clipsCache);
		        renderClips(applyClipFilters(clipsCache));
		        renderMiniTimeline();
		      } catch (e) {
		        clipsCache = [];
		        rebuildCollectionFilters([]);
		        renderClips([]);
		        renderMiniTimeline();
		      }
		    };

	    const saveClip = async () => {
	      if (!clipSaveUrl || !videoId) return;
	      const title = safeText(clipTitleInput?.value, 'Clip').slice(0, 180);
	      const collection = safeText(clipCollectionInput?.value, '').slice(0, 120);
	      const tags = parseTagsInput();
	      const notes = safeText(clipNotesInput?.value, '').slice(0, 5000);
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
	          body: JSON.stringify({ id: activeClipId || 0, video_id: videoId, title, collection, in_s: inS, out_s: outS, overlay, tags, notes }),
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
	    clipSearchInput?.addEventListener('input', () => renderClips(applyClipFilters(clipsCache)));
	    clipCollectionFilterSelect?.addEventListener('change', () => renderClips(applyClipFilters(clipsCache)));
	    clipClearFiltersBtn?.addEventListener('click', () => {
	      if (clipSearchInput) clipSearchInput.value = '';
	      if (clipCollectionFilterSelect) clipCollectionFilterSelect.value = '';
	      rebuildCollectionFilters(clipsCache);
	      renderClips(applyClipFilters(clipsCache));
	    });
	    refreshClips().then(() => {
	      if (!initialClipId) return;
	      try {
	        const btn = clipsList?.querySelector?.(`[data-vs-clip-load="${initialClipId}"]`);
	        if (btn) btn.click();
	      } catch (e) { /* ignore */ }
	    });

	    shareRefreshBtn?.addEventListener('click', refreshShareLinks);
	    refreshShareLinks();

    // Timeline (server)
    let timelineCache = [];
    const timelineSelectedKinds = () => {
      try {
        const opts = Array.from(timelineKindFilterSelect?.selectedOptions || []);
        const values = opts.map((o) => safeText(o?.value, '')).filter(Boolean);
        if (!values.length) return null;
        return new Set(values);
      } catch (e) {
        return null;
      }
    };
    const applyTimelineFilters = (items) => {
      const raw = Array.isArray(items) ? items : [];
      const q = safeText(timelineSearchInput?.value, '').toLowerCase();
      const kinds = timelineSelectedKinds();
      return raw.filter((ev) => {
        const kind = safeText(ev?.kind, 'tag');
        const label = safeText(ev?.label, '');
        if (kinds && !kinds.has(kind)) return false;
        if (!q) return true;
        return `${kind} ${label}`.toLowerCase().includes(q);
      }).sort((a, b) => (Number(a?.time_s) || 0) - (Number(b?.time_s) || 0) || (Number(a?.id) || 0) - (Number(b?.id) || 0));
    };
    const renderTimeline = (items) => {
      if (!timelineList) return;
      timelineCache = Array.isArray(items) ? items.slice() : [];
      const filtered = applyTimelineFilters(timelineCache);
      if (timelineCountEl) timelineCountEl.textContent = `${filtered.length} evento(s)`;
      const rows = filtered.slice(0, 360).map((ev) => {
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
      renderMiniTimeline();

      Array.from(timelineList.querySelectorAll('[data-vs-ev-go]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-ev-go') || 0);
          if (!id) return;
          try {
            const found = (Array.isArray(timelineCache) ? timelineCache : []).find((x) => Number(x?.id) === id);
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

    const timelineJump = (direction) => {
      const items = applyTimelineFilters(timelineCache);
      if (!items.length) { setStatus('No hay eventos.', true); return; }
      const now = Number(video.currentTime) || 0;
      let idx = -1;
      for (let i = 0; i < items.length; i += 1) {
        const t = Number(items[i]?.time_s) || 0;
        if (t >= now - 0.05) { idx = i; break; }
      }
      if (direction < 0) {
        // anterior: si estamos exactamente en un evento, ir al anterior.
        let prev = idx - 1;
        if (idx === -1) prev = items.length - 1;
        if (prev < 0) prev = 0;
        const t = Number(items[prev]?.time_s) || 0;
        try { video.currentTime = Math.max(0, t); } catch (e) { /* ignore */ }
        setStatus(`← ${fmtTimeShort(t)}`);
        return;
      }
      // siguiente
      let next = idx;
      if (next < 0) next = 0;
      const t = Number(items[next]?.time_s) || 0;
      try { video.currentTime = Math.max(0, t); } catch (e) { /* ignore */ }
      setStatus(`→ ${fmtTimeShort(t)}`);
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
    timelineSearchInput?.addEventListener('input', () => renderTimeline(timelineCache));
    timelineKindFilterSelect?.addEventListener('change', () => renderTimeline(timelineCache));
    timelinePrevBtn?.addEventListener('click', () => timelineJump(-1));
    timelineNextBtn?.addEventListener('click', () => timelineJump(1));

    const exportTimelineJson = async () => {
      if (!timelineExportUrl || !videoId) { setStatus('No disponible.', true); return; }
      try {
        const resp = await fetch(`${timelineExportUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        const payload = {
          version: 1,
          video_id: videoId,
          exported_at: new Date().toISOString(),
          items: Array.isArray(data?.items) ? data.items : [],
        };
        downloadBlob(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }), `timeline-${videoId}.json`);
        setStatus('Timeline exportada.');
      } catch (e) {
        setStatus('No se pudo exportar timeline.', true);
      }
    };

    const importTimelineJson = async (payloadObj) => {
      if (!timelineImportUrl || !videoId) { setStatus('No disponible.', true); return; }
      const items = Array.isArray(payloadObj?.items) ? payloadObj.items : [];
      if (!items.length) { setStatus('JSON sin items.', true); return; }
      const ok = window.confirm('¿Reemplazar timeline actual por la importada? (Aceptar = reemplaza / Cancelar = fusiona)');
      const mode = ok ? 'replace' : 'merge';
      try {
        const resp = await fetch(timelineImportUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ video_id: videoId, mode, items }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        await refreshTimeline();
        setStatus(`Timeline importada (${mode}).`);
      } catch (e) {
        setStatus('No se pudo importar.', true);
      }
    };

    timelineExportBtn?.addEventListener('click', exportTimelineJson);
    timelineImportBtn?.addEventListener('click', () => {
      try { timelineImportFile?.click(); } catch (e) { /* ignore */ }
    });
    timelineImportFile?.addEventListener('change', async () => {
      const file = timelineImportFile?.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const obj = JSON.parse(text || '{}');
        await importTimelineJson(obj);
      } catch (e) {
        setStatus('JSON inválido.', true);
      } finally {
        try { timelineImportFile.value = ''; } catch (e) { /* ignore */ }
      }
    });
    timelineClearBtn?.addEventListener('click', async () => {
      if (!timelineClearUrl || !videoId) return;
      const ok = window.confirm('¿Vaciar timeline del vídeo?');
      if (!ok) return;
      try {
        const resp = await fetch(timelineClearUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ video_id: videoId }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        await refreshTimeline();
        setStatus('Timeline vaciada.');
      } catch (e) {
        setStatus('No se pudo vaciar.', true);
      }
    });
    refreshTimeline();

    // Slides + Export Pro
    let slides = [];

    const captureFrameDataUrl = () => {
      const w = fabricCanvas.getWidth();
      const h = fabricCanvas.getHeight();
      const off = document.createElement('canvas');
      off.width = w;
      off.height = h;
      const ctx = off.getContext('2d');
      if (!ctx) return '';
      try { ctx.drawImage(video, 0, 0, w, h); } catch (e) { /* ignore */ }
      try { renderFx(ctx, { width: w, height: h, nowS: Number(video.currentTime) || 0, forExport: true }); } catch (e) { /* ignore */ }
      try { ctx.drawImage(canvasEl, 0, 0, w, h); } catch (e) { /* ignore */ }
      try { return off.toDataURL('image/jpeg', 0.92); } catch (e) { return ''; }
    };

    const renderSlides = () => {
      if (!slidesList) return;
      const rows = slides.slice(0, 24).map((s, idx) => {
        const id = safeText(s?.id, String(idx));
        const label = safeText(s?.label, `Slide ${idx + 1}`);
        const at = fmtTimeShort(Number(s?.time_s) || 0);
        const safeLabel = label.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;');
        return `
          <div class="row">
            <div style="display:flex; flex-direction:column; gap:0.25rem; min-width:0; flex:1;">
              <input type="text" value="${safeLabel}" data-vs-slide-label="${id}" />
              <small>${at}</small>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-vs-slide-go="${id}">Ir</button>
              <button type="button" class="button danger" data-vs-slide-del="${id}">X</button>
            </div>
          </div>
        `;
      }).join('');
      slidesList.innerHTML = rows || '<div class="meta">Sin slides todavía.</div>';

      Array.from(slidesList.querySelectorAll('[data-vs-slide-label]')).forEach((inp) => {
        inp.addEventListener('input', () => {
          const id = inp.getAttribute('data-vs-slide-label');
          const value = safeText(inp.value, '').slice(0, 140);
          slides = slides.map((s) => (String(s.id) === String(id) ? { ...s, label: value } : s));
        });
      });
      Array.from(slidesList.querySelectorAll('[data-vs-slide-go]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = btn.getAttribute('data-vs-slide-go');
          const found = slides.find((s) => String(s.id) === String(id));
          if (!found) return;
          try { video.currentTime = Number(found.time_s) || 0; } catch (e) { /* ignore */ }
        });
      });
      Array.from(slidesList.querySelectorAll('[data-vs-slide-del]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = btn.getAttribute('data-vs-slide-del');
          slides = slides.filter((s) => String(s.id) !== String(id));
          renderSlides();
        });
      });
    };

    const addSlideNow = () => {
      const img = captureFrameDataUrl();
      if (!img) {
        setStatus('No se pudo capturar slide.', true);
        return;
      }
      const timeS = Number(video.currentTime) || 0;
      const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      slides = [...slides, { id, label: `Slide ${slides.length + 1}`, time_s: timeS, image_data: img }].slice(0, 24);
      renderSlides();
      setStatus(`Slide capturado en ${fmtTimeShort(timeS)}.`);
    };

    const seekTo = (t) => new Promise((resolve) => {
      let done = false;
      const onSeeked = () => {
        if (done) return;
        done = true;
        try { window.clearTimeout(timeout); } catch (e) { /* ignore */ }
        try { video.removeEventListener('seeked', onSeeked); } catch (e) { /* ignore */ }
        resolve(true);
      };
      const timeout = window.setTimeout(() => {
        if (done) return;
        done = true;
        try { video.removeEventListener('seeked', onSeeked); } catch (e) { /* ignore */ }
        resolve(false);
      }, 1800);
      video.addEventListener('seeked', onSeeked, { once: true });
      try { video.currentTime = Math.max(0, Number(t) || 0); } catch (e) { resolve(false); }
    });

    const slidesFromTimeline = async () => {
      const items = Array.isArray(timelineCache) ? timelineCache.slice(0, 12) : [];
      if (!items.length) {
        setStatus('No hay timeline para generar slides.', true);
        return;
      }
      const wasPlaying = !video.paused;
      const prevTime = Number(video.currentTime) || 0;
      try { video.pause(); } catch (e) { /* ignore */ }
      setStatus('Generando slides desde timeline…');
      for (const ev of items) {
        const t = Number(ev?.time_s) || 0;
        // eslint-disable-next-line no-await-in-loop
        await seekTo(t);
        // eslint-disable-next-line no-await-in-loop
        await sleep(120);
        const img = captureFrameDataUrl();
        if (!img) continue;
        const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        slides = [...slides, { id, label: safeText(ev?.label, safeText(ev?.kind, 'Evento')).slice(0, 140), time_s: t, image_data: img }].slice(0, 24);
        renderSlides();
        // eslint-disable-next-line no-await-in-loop
        await sleep(60);
      }
      try { video.currentTime = prevTime; } catch (e) { /* ignore */ }
      if (wasPlaying) { try { await video.play(); } catch (e) { /* ignore */ } }
      setStatus('Slides generados.');
    };

    slideAddBtn?.addEventListener('click', addSlideNow);
    slidesFromTimelineBtn?.addEventListener('click', slidesFromTimeline);
    slidesClearBtn?.addEventListener('click', () => { slides = []; renderSlides(); setStatus('Slides limpiados.'); });
    renderSlides();

    const buildExportTitle = () => {
      const fromProject = safeText(projectTitleInput?.value, '').slice(0, 160);
      if (fromProject) return fromProject;
      const fromHeader = safeText(document.querySelector('.vs-head h1')?.textContent, '').replace(/^Video Studio\s*·\s*/i, '').trim();
      return safeText(fromHeader, 'Video Studio').slice(0, 160);
    };

    const exportSlidesPdf = async () => {
      if (!exportPdfUrl || !videoId) return;
      if (!slides.length) { setStatus('Añade al menos 1 slide.', true); return; }
      try {
        await postJsonDownload({
          url: exportPdfUrl,
          payload: {
            video_id: videoId,
            title: buildExportTitle(),
            source: 'studio',
            slides: slides.map((s) => ({ label: s.label, time_s: s.time_s, image_data: s.image_data })),
          },
          fallbackName: 'video-studio-slides.pdf',
        });
        setStatus('PDF descargado.');
      } catch (e) {
        setStatus(`No se pudo exportar PDF. ${safeText(e?.message, '')}`, true);
      }
    };

    const exportSlidesPackage = async () => {
      if (!exportPackageUrl || !videoId) return;
      if (!slides.length) { setStatus('Añade al menos 1 slide.', true); return; }
      try {
        await postJsonDownload({
          url: exportPackageUrl,
          payload: {
            video_id: videoId,
            title: buildExportTitle(),
            source: 'studio',
            slides: slides.map((s) => ({ label: s.label, time_s: s.time_s, image_data: s.image_data })),
          },
          fallbackName: 'video-studio-package.zip',
        });
        setStatus('Paquete descargado.');
      } catch (e) {
        setStatus(`No se pudo exportar paquete. ${safeText(e?.message, '')}`, true);
      }
    };

    exportPdfBtn?.addEventListener('click', exportSlidesPdf);
    exportPackageBtn?.addEventListener('click', exportSlidesPackage);

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
    renderDrawLayers();
    setStatus('Listo.');
  };

  document.addEventListener('DOMContentLoaded', init);
})();
