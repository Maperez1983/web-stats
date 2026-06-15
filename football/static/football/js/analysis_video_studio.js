(function () {
  const safeText = (value, fallback = '') => String(value ?? '').trim() || fallback;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const sleep = (ms) => new Promise((r) => window.setTimeout(r, ms));
  const colorToRgba = (color, alpha, fallback = 'rgba(255,255,255,0.2)') => {
    if (color && color.startsWith('#') && (color.length === 7 || color.length === 4)) {
      const hex = color.length === 4
        ? `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}`
        : color;
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return `rgba(${r},${g},${b},${alpha})`;
    }
    return fallback;
  };

  const waitNextVideoFrame = (videoEl, timeoutMs = 350) => new Promise((resolve) => {
    if (!videoEl) return resolve(false);
    try {
      if (typeof videoEl.requestVideoFrameCallback === 'function') {
        let done = false;
        const t = window.setTimeout(() => {
          if (done) return;
          done = true;
          resolve(false);
        }, Math.max(60, Number(timeoutMs) || 350));
        videoEl.requestVideoFrameCallback(() => {
          if (done) return;
          done = true;
          try { window.clearTimeout(t); } catch (e) { /* ignore */ }
          resolve(true);
        });
        return;
      }
    } catch (e) { /* ignore */ }
    window.requestAnimationFrame(() => resolve(false));
  });

  const drawVideoFrameSmart = async (ctx, videoEl, w, h) => {
    if (!ctx || !videoEl || !w || !h) return false;
    try {
      const rs = Number(videoEl.readyState) || 0;
      const vw = Number(videoEl.videoWidth) || 0;
      const vh = Number(videoEl.videoHeight) || 0;
      if (rs < 2 || !vw || !vh) return false;
    } catch (e) { /* ignore */ }
    try { await waitNextVideoFrame(videoEl, 350); } catch (e) { /* ignore */ }
    // En Safari/iOS, `drawImage(video)` puede devolver negro. `createImageBitmap(video)` suele ser más fiable.
    try {
      if (typeof createImageBitmap === 'function') {
        const bmp = await createImageBitmap(videoEl);
        try { ctx.drawImage(bmp, 0, 0, w, h); } finally { try { bmp.close?.(); } catch (e) { /* ignore */ } }
        return true;
      }
    } catch (e) { /* ignore */ }
    try { ctx.drawImage(videoEl, 0, 0, w, h); return true; } catch (e) { /* ignore */ }
    return false;
  };

  const setStatus = (text, isError = false, { flash = true } = {}) => {
    const el = document.getElementById('vs-status');
    if (!el) return;
    el.textContent = safeText(text, '');
    el.style.color = isError ? '#fecaca' : 'rgba(226,232,240,0.72)';
    if (!flash) return;
    try {
      el.classList.remove('vs-flash');
      void el.offsetWidth; // fuerza reflow
      el.classList.add('vs-flash');
      window.clearTimeout(setStatus._t);
      setStatus._t = window.setTimeout(() => {
        try { el.classList.remove('vs-flash'); } catch (e) { /* ignore */ }
      }, 1800);
    } catch (e) { /* ignore */ }
  };

  const canvasLooksBlank = (ctx, w, h) => {
    if (!ctx || !w || !h) return false;
    try {
      const points = [
        [0.1, 0.1], [0.5, 0.1], [0.9, 0.1],
        [0.1, 0.5], [0.5, 0.5], [0.9, 0.5],
        [0.1, 0.9], [0.5, 0.9], [0.9, 0.9],
      ];
      let minL = 255;
      let maxL = 0;
      let sumL = 0;
      let n = 0;
      for (const [ux, uy] of points) {
        const x = Math.max(0, Math.min(w - 1, Math.floor(ux * w)));
        const y = Math.max(0, Math.min(h - 1, Math.floor(uy * h)));
        const d = ctx.getImageData(x, y, 1, 1).data;
        const a = Number(d[3] || 0);
        if (a < 6) continue;
        const l = (Number(d[0] || 0) + Number(d[1] || 0) + Number(d[2] || 0)) / 3;
        minL = Math.min(minL, l);
        maxL = Math.max(maxL, l);
        sumL += l;
        n += 1;
      }
      if (!n) return true;
      const avg = sumL / n;
      if (maxL < 8) return true;
      if (minL > 248) return true;
      if ((maxL - minL) < 1.5 && (avg < 16 || avg > 240)) return true;
      return false;
    } catch (e) {
      return false;
    }
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
			    const freezeBgEl = document.getElementById('vs-freeze-bg');
		    const resetCacheBtn = document.getElementById('vs-reset-cache');
			    if (!video) return;

	    // Botón de emergencia: reinicia cachés offline/SW (Safari/PWA) para forzar a cargar JS/CSS nuevos tras deploys.
	    try {
	      if (resetCacheBtn) {
	        const canReset = Boolean((window.caches && typeof window.caches.keys === 'function') || (navigator.serviceWorker && navigator.serviceWorker.getRegistrations));
	        if (!canReset) {
	          resetCacheBtn.style.display = 'none';
	        } else {
	          resetCacheBtn.addEventListener('click', async () => {
	            const ok = window.confirm('¿Reiniciar caché offline y recargar? (Soluciona cambios que no aparecen en Safari)');
	            if (!ok) return;
	            try {
	              if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
	                const regs = await navigator.serviceWorker.getRegistrations();
	                await Promise.all((regs || []).map((r) => r.unregister().catch(() => false)));
	              }
	            } catch (e) { /* ignore */ }
	            try {
	              if (window.caches && typeof window.caches.keys === 'function') {
	                const keys = await window.caches.keys();
	                await Promise.all((keys || []).map((k) => window.caches.delete(k).catch(() => false)));
	              }
	            } catch (e) { /* ignore */ }
	            try { window.localStorage?.removeItem?.('vs_player_recents_v1'); } catch (e) { /* ignore */ }
	            try { window.localStorage?.removeItem?.('vs_player_marker_prefs_v1'); } catch (e) { /* ignore */ }
	            try { window.location.reload(); } catch (e) { /* ignore */ }
	          });
	        }
	      }
	    } catch (e) { /* ignore */ }
		    const hasFabric = Boolean(window.fabric && window.fabric.Canvas);
		    const canTelestrate = Boolean(hasFabric && canvasEl && fxEl && stage);
		    if (!canTelestrate) {
		      // Sin Fabric (o sin canvas): mantenemos el editor de tiempo (IN/OUT, loop, clips) funcionando.
		      // Desactivamos herramientas de telestración para evitar errores en iPad/Safari.
		      try {
		        [
		          document.getElementById('vs-tool-select'),
		          document.getElementById('vs-tool-pen'),
		          document.getElementById('vs-tool-arrow'),
		          document.getElementById('vs-tool-curve'),
		          document.getElementById('vs-tool-text'),
		          document.getElementById('vs-tool-player'),
		          document.getElementById('vs-tool-callout'),
		          document.getElementById('vs-tool-base'),
		          document.getElementById('vs-tool-area'),
		          document.getElementById('vs-tool-move'),
		          document.getElementById('vs-tool-spot'),
		          document.getElementById('vs-tool-blur'),
		          document.getElementById('vs-undo'),
		          document.getElementById('vs-clear'),
		          document.getElementById('vs-snap'),
		          document.getElementById('vs-freeze'),
		          document.getElementById('vs-record'),
		        ]
		          .filter(Boolean)
		          .forEach((btn) => {
		            btn.disabled = true;
		            btn.title = 'Telestración no disponible: no se pudo cargar Fabric.js.';
		          });
		      } catch (e) { /* ignore */ }
		    }

	    // Safari/iOS: si el vídeo viene de S3 sin CORS, `crossorigin="anonymous"` puede bloquear la carga
	    // y el vídeo se queda negro. En ese caso activamos un fallback (sin CORS) para que al menos se vea.
	    // Nota: en modo fallback no se puede dibujar el vídeo en canvas (export/miniaturas pueden degradar).
	    const appendUrlParam = (url, key, value) => {
	      const raw = safeText(url, '');
	      if (!raw) return raw;
	      try {
	        const u = new URL(raw, window.location.href);
	        u.searchParams.set(String(key), String(value));
	        return u.toString();
	      } catch (e) {
	        const joiner = raw.includes('?') ? '&' : '?';
	        return `${raw}${joiner}${encodeURIComponent(String(key))}=${encodeURIComponent(String(value))}`;
	      }
	    };
	    const videoSource = (() => {
	      try { return video.querySelector('source'); } catch (e) { return null; }
	    })();
	    let compatNoCorsApplied = false;
	    const disableCanvasDependentActions = () => {
	      try {
	        [
	          document.getElementById('vs-snap'),
	          document.getElementById('vs-freeze'),
	          document.getElementById('vs-record'),
	          document.getElementById('vs-export-seg'),
	          document.getElementById('vs-export-share'),
	        ]
	          .filter(Boolean)
	          .forEach((btn) => {
	            btn.disabled = true;
	            btn.title = 'El vídeo se ha cargado en modo compatibilidad (sin CORS). Para exportar, configura CORS en el bucket S3.';
	          });
	      } catch (e) { /* ignore */ }
	    };
	    const applyNoCorsCompatMode = (reason) => {
	      if (compatNoCorsApplied) return;
	      compatNoCorsApplied = true;
	      try { video.removeAttribute('crossorigin'); } catch (e) { /* ignore */ }
	      try { video.crossOrigin = null; } catch (e) { /* ignore */ }
	      const src = safeText(videoSource?.getAttribute?.('src') || videoSource?.src || '', '');
	      if (src && videoSource) {
	        const nextSrc = appendUrlParam(appendUrlParam(src, 'vs_nocors', '1'), 'vs_ts', String(Date.now()));
	        try { videoSource.setAttribute('src', nextSrc); } catch (e) { /* ignore */ }
	      }
	      try { video.load(); } catch (e) { /* ignore */ }
	      setStatus(`El vídeo estaba bloqueado (${safeText(reason, 'CORS')}). Activado modo compatibilidad.`, true);
	      disableCanvasDependentActions();
	    };
	    try {
	      video.addEventListener('error', () => {
	        // Evita bucles: solo una vez.
	        applyNoCorsCompatMode('CORS/permiso');
	      }, { once: true });
	      // Si tras unos segundos sigue sin metadata, suele indicar bloqueo por CORS/403.
	      window.setTimeout(() => {
	        try {
	          if (compatNoCorsApplied) return;
	          const rs = video.readyState || 0;
	          const hasMeta = rs >= 1 || Number.isFinite(video.duration) && video.duration > 0;
	          if (!hasMeta) applyNoCorsCompatMode('sin respuesta');
	        } catch (e) { /* ignore */ }
	      }, 4500);
	    } catch (e) { /* ignore */ }

			    const miniTimeline = document.getElementById('vs-mini-timeline');
			    const miniTrack = document.getElementById('vs-mini-track');
			    const miniRange = document.getElementById('vs-mini-range');
			    const miniCursor = document.getElementById('vs-mini-cursor');

	    const btnPlay = document.getElementById('vs-play');
	    const btnPause = document.getElementById('vs-pause');
	    const btnLoop = document.getElementById('vs-loop');
	    const speedSelect = document.getElementById('vs-speed');
	    const btnIn = document.getElementById('vs-mark-in');
	    const btnOut = document.getElementById('vs-mark-out');
	    const btnExportSeg = document.getElementById('vs-export-seg');
	    const btnExportShare = document.getElementById('vs-export-share');
		    const btnExportServer = document.getElementById('vs-export-server');
		    const btnExportServerPlaylist = document.getElementById('vs-export-server-playlist');
		    const btnExportRetry = document.getElementById('vs-export-retry');
		    const btnRecord = document.getElementById('vs-record');
		    const btnStillClip = document.getElementById('vs-still-clip');
			    const btnSnap = document.getElementById('vs-snap');
			    const btnCapturePrimary = document.getElementById('vs-capture-primary');
			    const btnDorsalOcr = document.getElementById('vs-dorsal-ocr');
			    const btnFreeze = document.getElementById('vs-freeze');
			    const btnTrackAuto = document.getElementById('vs-track-auto');
			    const btnTrackAi = document.getElementById('vs-track-ai');
			    const btnAiProCorrect = document.getElementById('vs-ai-pro-correct');
			    const btnAiProQuality = document.getElementById('vs-ai-pro-quality');
			    const btnSpaceAiOccupancy = document.getElementById('vs-space-ai-occupancy');
			    const btnAiProPanel = document.getElementById('vs-ai-pro-panel');
			    const trackSmoothSelect = document.getElementById('vs-track-smooth');
			    const trackAntiJumpToggle = document.getElementById('vs-track-antijump');
			    const btnTrackSmoothSelected = document.getElementById('vs-track-smooth-selected');
		    const btnDebug = document.getElementById('vs-debug');
		    const lineStyleSelect = document.getElementById('vs-line-style');
		    const arrowDoubleBtn = document.getElementById('vs-arrow-double');

	    const btnSelect = document.getElementById('vs-tool-select');
	    const btnPen = document.getElementById('vs-tool-pen');
	    const btnLine = document.getElementById('vs-tool-line');
	    const btnRect = document.getElementById('vs-tool-rect');
	    const btnCircle = document.getElementById('vs-tool-circle');
	    const btnMeasure = document.getElementById('vs-tool-measure');
	    const btnArrow = document.getElementById('vs-tool-arrow');
	    const btnCurve = document.getElementById('vs-tool-curve');
    const btnText = document.getElementById('vs-tool-text');
    const btnPlayer = document.getElementById('vs-tool-player');
    const btnStructure = document.getElementById('vs-tool-structure');
    const btnCallout = document.getElementById('vs-tool-callout');
    const btnBase = document.getElementById('vs-tool-base');
    const btnArea = document.getElementById('vs-tool-area');
    const btnSpace = document.getElementById('vs-tool-space');
    const btnSpaceFollowPlay = document.getElementById('vs-space-follow-play');
    const btnSpaceFollowPlayer = document.getElementById('vs-space-follow-player');
    const btnSpaceFollowManual = document.getElementById('vs-space-follow-manual');
    const btnLayerFollowPlayer = document.getElementById('vs-layer-follow-player');
    const btnLayerFollowPlay = document.getElementById('vs-layer-follow-play');
    const btnLayerFollowManual = document.getElementById('vs-layer-follow-manual');
    const btnMove = document.getElementById('vs-tool-move');
    const btnSpot = document.getElementById('vs-tool-spot');
    const btnBlur = document.getElementById('vs-tool-blur');
	    const btnUndo = document.getElementById('vs-undo');
	    const btnRedo = document.getElementById('vs-redo');
	    const btnViewReset = document.getElementById('vs-view-reset');
	    const btnClear = document.getElementById('vs-clear');
    const colorInput = document.getElementById('vs-color');
    const widthInput = document.getElementById('vs-width');

    const inInput = document.getElementById('vs-in');
    const outInput = document.getElementById('vs-out');
    const trimSavedMsg = document.getElementById('vs-trim-saved-msg');
    const trimEnabledToggle = document.getElementById('vs-trim-enabled');
    const trimInInput = document.getElementById('vs-trim-in');
    const trimOutInput = document.getElementById('vs-trim-out');
    const trimFromSegmentBtn = document.getElementById('vs-trim-from-segment');
    const trimClearBtn = document.getElementById('vs-trim-clear');
    const trimSetInBtn = document.getElementById('vs-trim-set-in');
    const trimSetOutBtn = document.getElementById('vs-trim-set-out');
    const trimSaveBtn = document.getElementById('vs-trim-save');
    const qualitySelect = document.getElementById('vs-video-quality');
    const fpsSelect = document.getElementById('vs-video-fps');
    const audioToggle = document.getElementById('vs-video-audio');
    const slideAddBtn = document.getElementById('vs-slide-add');
    const slidesFromTimelineBtn = document.getElementById('vs-slides-from-timeline');
    const slidesClearBtn = document.getElementById('vs-slides-clear');
    const slidesList = document.getElementById('vs-slides');
    const exportPdfBtn = document.getElementById('vs-export-pdf');
    const exportPackageBtn = document.getElementById('vs-export-package');
	    const reportPdfBtn = document.getElementById('vs-report-pdf');
	    const templateSelect = document.getElementById('vs-template');
	    const templateApplyBtn = document.getElementById('vs-template-apply');
	    const templateClearBtn = document.getElementById('vs-template-clear');
	    const resourcesMenu = document.getElementById('vs-resources-menu');
	    const resourcesRecentWrap = document.getElementById('vs-resources-recent');
	    const resourceSearchInput = document.getElementById('vs-resource-search');
	    const resourceTabsWrap = document.getElementById('vs-resource-tabs');
	    const resourcePreview = document.getElementById('vs-resource-preview');
	    const resourcePreviewTitle = document.getElementById('vs-resource-preview-title');
	    const resourcePreviewText = document.getElementById('vs-resource-preview-text');
	    const templateParamsWrap = document.getElementById('vs-template-params');
	    const templateLanesCountInput = document.getElementById('vs-template-lanes-count');
	    const templateLanesStrokeInput = document.getElementById('vs-template-lanes-stroke');

	    const snapGridToggle = document.getElementById('vs-snap-grid');
	    const gridSizeInput = document.getElementById('vs-grid-size');
	    const alignLeftBtn = document.getElementById('vs-align-left');
	    const alignHCenterBtn = document.getElementById('vs-align-hcenter');
	    const alignRightBtn = document.getElementById('vs-align-right');
	    const alignTopBtn = document.getElementById('vs-align-top');
	    const alignVCenterBtn = document.getElementById('vs-align-vcenter');
	    const alignBottomBtn = document.getElementById('vs-align-bottom');
	    const distHBtn = document.getElementById('vs-dist-h');
	    const distVBtn = document.getElementById('vs-dist-v');
	    const styleApplyBtn = document.getElementById('vs-style-apply');
	    const calibStartBtn = document.getElementById('vs-calib-start');
	    const calibResetBtn = document.getElementById('vs-calib-reset');
	    const calibStatusEl = document.getElementById('vs-calib-status');

	    const videoId = Number(document.getElementById('vs-video-id')?.value || 0);
	    const uiMode = safeText(document.getElementById('vs-ui-mode')?.value || '').toLowerCase();
	    const simpleUI = uiMode === 'simple';
	    const initialClipId = Number(document.getElementById('vs-initial-clip-id')?.value || 0);
	    const projectsUrl = safeText(document.getElementById('vs-projects-url')?.value);
    const projectSaveUrl = safeText(document.getElementById('vs-project-save-url')?.value);
    const projectDeleteUrl = safeText(document.getElementById('vs-project-delete-url')?.value);
    const clipsUrl = safeText(document.getElementById('vs-clips-url')?.value);
    const clipSaveUrl = safeText(document.getElementById('vs-clip-save-url')?.value);
	    const clipDeleteUrl = safeText(document.getElementById('vs-clip-delete-url')?.value);
	    const assignUrl = safeText(document.getElementById('vs-assign-url')?.value);
	    const assignTeamSelect = document.getElementById('vs-assign-team');
	    const assignBtn = document.getElementById('vs-assign-btn');
	    const shareClipCreateUrl = safeText(document.getElementById('vs-share-clip-create-url')?.value);
	    const shareReportCreateUrl = safeText(document.getElementById('vs-share-report-create-url')?.value);
	    const sharePlaylistCreateUrl = safeText(document.getElementById('vs-share-playlist-create-url')?.value);
		    const shareLinksUrl = safeText(document.getElementById('vs-share-links-url')?.value);
		    const inboxRecipientsUrl = safeText(document.getElementById('vs-inbox-recipients-url')?.value);
		    const inboxSendUrl = safeText(document.getElementById('vs-inbox-send-url')?.value);
		    const timelineUrl = safeText(document.getElementById('vs-timeline-url')?.value);
	    const timelineSaveUrl = safeText(document.getElementById('vs-timeline-save-url')?.value);
	    const timelineDeleteUrl = safeText(document.getElementById('vs-timeline-delete-url')?.value);
		    const timelineExportUrl = safeText(document.getElementById('vs-timeline-export-url')?.value);
		    const timelineImportUrl = safeText(document.getElementById('vs-timeline-import-url')?.value);
		    const timelineClearUrl = safeText(document.getElementById('vs-timeline-clear-url')?.value);
		    const reviewUrl = safeText(document.getElementById('vs-review-url')?.value);
		    const exportPdfUrl = safeText(document.getElementById('vs-export-pdf-url')?.value);
		    const exportPackageUrl = safeText(document.getElementById('vs-export-package-url')?.value);
			    const exportUploadUrl = safeText(document.getElementById('vs-export-upload-url')?.value);
			    const exportServerUrl = safeText(document.getElementById('vs-export-server-url')?.value);
			    const exportServerPlaylistUrl = safeText(document.getElementById('vs-export-server-playlist-url')?.value);
			    const exportJobCreateUrl = safeText(document.getElementById('vs-export-job-create-url')?.value);
			    const exportJobStatusUrl = safeText(document.getElementById('vs-export-job-status-url')?.value);
			    const exportJobCancelUrl = safeText(document.getElementById('vs-export-job-cancel-url')?.value);
			    const reportPdfUrl = safeText(document.getElementById('vs-report-pdf-url')?.value);
		    const aiUrl = safeText(document.getElementById('vs-ai-url')?.value);
		    const aiProUrl = safeText(document.getElementById('vs-ai-pro-url')?.value);
			    const autocutUrl = safeText(document.getElementById('vs-autocut-url')?.value);
			    const dorsalOcrUrl = safeText(document.getElementById('vs-dorsal-ocr-url')?.value);
			    const frameCaptureUrl = safeText(document.getElementById('vs-frame-capture-url')?.value);
			    const trackUrl = safeText(document.getElementById('vs-track-url')?.value);
			    const aiTrackUrl = safeText(document.getElementById('vs-ai-track-url')?.value);

		    const isIOS = (() => {
		      try {
		        const ua = String(navigator.userAgent || '');
		        if (/iPad|iPhone|iPod/.test(ua)) return true;
		        // iPadOS 13+ informa como Mac, pero con touchpoints.
		        if (navigator.platform === 'MacIntel' && Number(navigator.maxTouchPoints || 0) > 1) return true;
		      } catch (e) { /* ignore */ }
		      return false;
		    })();

      // Popover marcador jugador (sin prompts)
      const playerPop = document.getElementById('vs-player-pop');
      const playerNumberInput = document.getElementById('vs-player-number');
      const playerNameInput = document.getElementById('vs-player-name');
      const playerTeamSeg = document.getElementById('vs-player-team-seg');
      const playerStyleSeg = document.getElementById('vs-player-style-seg');
      const playerOkBtn = document.getElementById('vs-player-ok');
      const playerCancelBtn = document.getElementById('vs-player-cancel');
      const playerRecentsWrap = document.getElementById('vs-player-recents');
      let playerPopCanvasPos = null;
      const playerRecentsKey = 'vs_player_recents_v1';
      const playerPrefsKey = 'vs_player_marker_prefs_v1';

      const defaultPlayerPrefs = () => ({ team: 'home', style: 'tag' });
      const loadPlayerPrefs = () => {
        try {
          const raw = window.localStorage?.getItem?.(playerPrefsKey) || '';
          const obj = raw ? JSON.parse(raw) : null;
          const team = safeText(obj?.team, '').toLowerCase();
          const style = safeText(obj?.style, '').toLowerCase();
          return {
            team: (team === 'away' || team === 'home') ? team : 'home',
            style: (style === 'circle' || style === 'tag') ? style : 'tag',
          };
        } catch (e) {
          return defaultPlayerPrefs();
        }
      };
      const savePlayerPrefs = (prefs) => {
        try { window.localStorage?.setItem?.(playerPrefsKey, JSON.stringify(prefs || defaultPlayerPrefs())); } catch (e) { /* ignore */ }
      };
      let playerPrefs = loadPlayerPrefs();
      const setSegActive = (wrap, key, value) => {
        if (!wrap) return;
        Array.from(wrap.querySelectorAll('button[data-vs-team],button[data-vs-style]')).forEach((btn) => btn.classList.remove('active'));
        const selector = key === 'team' ? `button[data-vs-team="${value}"]` : `button[data-vs-style="${value}"]`;
        const btn = wrap.querySelector(selector);
        if (btn) btn.classList.add('active');
      };

      const loadPlayerRecents = () => {
        try {
          const raw = window.localStorage?.getItem?.(playerRecentsKey) || '[]';
          const arr = JSON.parse(raw);
          return Array.isArray(arr) ? arr.slice(0, 12) : [];
        } catch (e) {
          return [];
        }
      };
      const savePlayerRecents = (items) => {
        try { window.localStorage?.setItem?.(playerRecentsKey, JSON.stringify((Array.isArray(items) ? items : []).slice(0, 12))); } catch (e) { /* ignore */ }
      };
      const renderPlayerRecents = () => {
        if (!playerRecentsWrap) return;
        const items = loadPlayerRecents();
        if (!items.length) { playerRecentsWrap.innerHTML = ''; return; }
        playerRecentsWrap.innerHTML = items
          .map((it, idx) => {
            const num = safeText(it?.number, '').trim();
            const name = safeText(it?.name, '').trim();
            if (!num || !name) return '';
            const label = `${num} ${name}`.trim();
            return `<button type="button" class="button ghost" data-vs-player-recent="${idx}">${escHtml(label)}</button>`;
          })
          .filter(Boolean)
          .join('');
        Array.from(playerRecentsWrap.querySelectorAll('[data-vs-player-recent]')).forEach((btn) => {
          btn.addEventListener('click', () => {
            const idx = Number(btn.getAttribute('data-vs-player-recent') || -1);
            const items2 = loadPlayerRecents();
            const it = items2[idx];
            if (!it) return;
            if (playerNumberInput) playerNumberInput.value = safeText(it.number, '');
            if (playerNameInput) playerNameInput.value = safeText(it.name, '');
            try { playerNameInput?.focus?.(); } catch (e) { /* ignore */ }
          });
        });
      };
      const closePlayerPop = () => {
        playerPopCanvasPos = null;
        if (!playerPop) return;
        playerPop.style.display = 'none';
      };
      const openPlayerPopAt = (canvasPoint, clientPoint) => {
        if (!playerPop || !stage) return;
        playerPopCanvasPos = canvasPoint || null;
        setSegActive(playerTeamSeg, 'team', playerPrefs.team);
        setSegActive(playerStyleSeg, 'style', playerPrefs.style);
        renderPlayerRecents();
        const rect = stage.getBoundingClientRect();
        const x = clamp((clientPoint?.x ?? (rect.left + rect.width * 0.5)) - rect.left, 8, Math.max(8, rect.width - 328));
        const y = clamp((clientPoint?.y ?? (rect.top + rect.height * 0.5)) - rect.top, 8, Math.max(8, rect.height - 180));
        playerPop.style.left = `${Math.round(x)}px`;
        playerPop.style.top = `${Math.round(y)}px`;
        playerPop.style.display = 'block';
        try { (playerNumberInput || playerNameInput)?.focus?.(); } catch (e) { /* ignore */ }
      };

      // Fallback: en algunos navegadores/estados (Safari, overlays) Fabric puede no disparar mouse:down.
      // Abrimos el popover también desde el canvas DOM si la herramienta activa es "player".
      const domPlayerPointerHandler = (ev) => {
        try {
          if (!ev) return;
          const activeTool = safeText(stage?.getAttribute?.('data-vs-tool'), '');
          if (activeTool !== 'player') return;
          if (!playerPop || !stage || !canvasEl) return;
          const tgt = ev.target;
          if (tgt && playerPop.contains(tgt)) return;
          // Si el pop-up ya está abierto, no lo re-dispares.
          try {
            if (playerPop.style && String(playerPop.style.display || '') !== 'none') return;
          } catch (e0) { /* ignore */ }
          const rect = canvasEl.getBoundingClientRect();
          const x = clamp((ev.clientX ?? 0) - rect.left, 0, rect.width);
          const y = clamp((ev.clientY ?? 0) - rect.top, 0, rect.height);
          openPlayerPopAt({ x, y }, { x: ev.clientX || 0, y: ev.clientY || 0 });
          try { ev.preventDefault?.(); } catch (e2) { /* ignore */ }
          try { ev.stopPropagation?.(); } catch (e3) { /* ignore */ }
        } catch (e) { /* ignore */ }
      };
      try {
        canvasEl.addEventListener('pointerdown', domPlayerPointerHandler, { passive: false });
      } catch (e) { /* ignore */ }
      try {
        // Capture en el contenedor para cubrir el caso de Fabric (upperCanvasEl) u otros overlays.
        stage.addEventListener('pointerdown', domPlayerPointerHandler, { passive: false, capture: true });
      } catch (e) { /* ignore */ }

	    // Timeline editor (clips)
	    const tlFromSelectionBtn = document.getElementById('vs-tl-from-selection');
	    const tlClearBtn = document.getElementById('vs-tl-clear');
	    const tlSaveBtn = document.getElementById('vs-tl-save-project');
	    const tlLoadBtn = document.getElementById('vs-tl-load-project');
	    const tlIncludeAudioToggle = document.getElementById('vs-tl-include-audio');
	    const tlProjectSelect = document.getElementById('vs-tl-project-select');
				    const tlItemsEl = document.getElementById('vs-tl-items');
				    const tlTotalEl = document.getElementById('vs-tl-total');
				    const tlExportBtn = document.getElementById('vs-tl-export-mp4');
				    const tlExportOverlaysBtn = document.getElementById('vs-tl-export-overlays');
				    const tlExportCancelBtn = document.getElementById('vs-tl-export-cancel');
				    const tlJobWrap = document.getElementById('vs-tl-job-wrap');
				    const tlJobMsg = document.getElementById('vs-tl-job-msg');
				    const tlJobProgress = document.getElementById('vs-tl-job-progress');
			    const tlTransitionInput = document.getElementById('vs-tl-transition');
    const tlItemDialog = document.getElementById('vs-tl-item-dialog');
		    const tlItemInInput = document.getElementById('vs-tl-item-in');
		    const tlItemOutInput = document.getElementById('vs-tl-item-out');
		    const tlSpeedStartInput = document.getElementById('vs-tl-speed-start');
		    const tlSpeedEndInput = document.getElementById('vs-tl-speed-end');
		    const tlFadeInInput = document.getElementById('vs-tl-fade-in');
		    const tlFadeOutInput = document.getElementById('vs-tl-fade-out');
	    const tlItemResetBtn = document.getElementById('vs-tl-item-reset');
	    const tlItemSaveBtn = document.getElementById('vs-tl-item-save');

	    const aiGenerateBtn = document.getElementById('vs-ai-generate');
	    const aiForceBtn = document.getElementById('vs-ai-force');
	    const aiToTimelineBtn = document.getElementById('vs-ai-to-timeline');
	    const aiCopyBtn = document.getElementById('vs-ai-copy');
	    const aiContextInput = document.getElementById('vs-ai-context');
	    const aiIncludeReportToggle = document.getElementById('vs-ai-include-report');
	    const aiMetaEl = document.getElementById('vs-ai-meta');
	    const aiOutputEl = document.getElementById('vs-ai-output');

	    const projectTitleInput = document.getElementById('vs-project-title');
    const projectSaveBtn = document.getElementById('vs-project-save');
    const projectRefreshBtn = document.getElementById('vs-project-refresh');
    const projectsList = document.getElementById('vs-projects');
    const proLiveModeBtn = document.getElementById('vs-pro-live-mode');
    const proModelPackBtn = document.getElementById('vs-pro-model-pack');
    const proCompareBtn = document.getElementById('vs-pro-compare');
    const proComparePanel = document.getElementById('vs-pro-compare-panel');
    const proPresentationBtn = document.getElementById('vs-pro-presentation');
    const proAiQuestionBtn = document.getElementById('vs-pro-ai-question');
    const proGuidedTrackBtn = document.getElementById('vs-pro-guided-track');
    const proCoachExportBtn = document.getElementById('vs-pro-coach-export');
    const proPlayerExportBtn = document.getElementById('vs-pro-player-export');
    const patternTitleInput = document.getElementById('vs-pattern-title');
    const patternSaveBtn = document.getElementById('vs-pattern-save');
    const patternSelect = document.getElementById('vs-pattern-select');
    const patternApplyBtn = document.getElementById('vs-pattern-apply');
    const patternList = document.getElementById('vs-pattern-list');

	    const clipTitleInput = document.getElementById('vs-clip-title');
	    const clipCollectionInput = document.getElementById('vs-clip-collection');
	    const clipTagsInput = document.getElementById('vs-clip-tags');
	    const clipNotesInput = document.getElementById('vs-clip-notes');
	    const clipSearchInput = document.getElementById('vs-clip-search');
	    const clipCollectionFilterSelect = document.getElementById('vs-clip-filter-collection');
	    const clipClearFiltersBtn = document.getElementById('vs-clip-clear-filters');
	    const clipCollectionsWrap = document.getElementById('vs-clip-collections');
	    const clipCountEl = document.getElementById('vs-clip-count');
	    const playlistPlayBtn = document.getElementById('vs-playlist-play');
	    const playlistStopBtn = document.getElementById('vs-playlist-stop');
		    const playlistClearBtn = document.getElementById('vs-playlist-clear');
		    const playlistShareBtn = document.getElementById('vs-playlist-share');
		    const playlistCountEl = document.getElementById('vs-playlist-count');
		    const clipSaveBtn = document.getElementById('vs-clip-save');
        const clipSaveQuickBtn = document.getElementById('vs-clip-save-quick');
        const clipSaveMp4Btn = document.getElementById('vs-clip-save-mp4');
        const openMainCutBtn = document.getElementById('vs-open-main-cut');
		    const clipDupBtn = document.getElementById('vs-clip-dup');
		    const clipSplitBtn = document.getElementById('vs-clip-split');
		    const clipRefreshBtn = document.getElementById('vs-clip-refresh');
		    const clipsList = document.getElementById('vs-clips');
        const clipsCountSimpleEl = document.getElementById('vs-clips-count-simple');
	    const dashboardEl = document.getElementById('vs-dashboard');
	    const filterUnreviewedClipsToggle = document.getElementById('vs-filter-unreviewed-clips');
	    const filterUnreviewedEventsToggle = document.getElementById('vs-filter-unreviewed-events');
	    const reportShareBtn = document.getElementById('vs-report-share');
      const clipSavedMsg = document.getElementById('vs-clip-saved-msg');

    const eventKindSelect = document.getElementById('vs-event-kind');
    const eventLabelInput = document.getElementById('vs-event-label');
    const ctxTeamSelect = document.getElementById('vs-ctx-team');
    const ctxPhaseSelect = document.getElementById('vs-ctx-phase');
    const eventPresetsWrap = document.getElementById('vs-event-presets');
    const presetsPackSelect = document.getElementById('vs-presets-pack');
    const defaultPackInput = document.getElementById('vs-default-pack');
    const defaultPack = safeText(defaultPackInput?.value, 'rival') === 'own' ? 'own' : 'rival';
    const presetsAutoClipSelect = document.getElementById('vs-presets-autoclip');
    const presetsPreInput = document.getElementById('vs-presets-pre');
    const presetsPostInput = document.getElementById('vs-presets-post');
    const presetsJson = document.getElementById('vs-presets-json');
    const presetsSaveBtn = document.getElementById('vs-presets-save');
    const presetsResetBtn = document.getElementById('vs-presets-reset');
    const presetsStatusEl = document.getElementById('vs-presets-status');
    const eventAddBtn = document.getElementById('vs-event-add');
    const eventRefreshBtn = document.getElementById('vs-event-refresh');
    const autocutRunBtn = document.getElementById('vs-autocut-run');
    const timelineList = document.getElementById('vs-timeline');
	    const timelineSearchInput = document.getElementById('vs-timeline-search');
	    const timelineKindFilterSelect = document.getElementById('vs-timeline-filter-kind');
	    const timelineCountEl = document.getElementById('vs-timeline-count');
	    const timelinePrevBtn = document.getElementById('vs-timeline-prev');
	    const timelineNextBtn = document.getElementById('vs-timeline-next');
    const timelineFormatSelect = document.getElementById('vs-timeline-format');
    const timelineExportBtn = document.getElementById('vs-timeline-export');
    const timelineImportBtn = document.getElementById('vs-timeline-import');
    const timelineToClipsBtn = document.getElementById('vs-timeline-to-clips');
    const timelineClearBtn = document.getElementById('vs-timeline-clear');
    const timelineImportFile = document.getElementById('vs-timeline-import-file');

	    const shareRefreshBtn = document.getElementById('vs-share-refresh');
	    const shareLinksList = document.getElementById('vs-share-links');
	    const inboxUsersSelect = document.getElementById('vs-inbox-users');
	    const inboxMessageInput = document.getElementById('vs-inbox-message');
	    const inboxSendClipBtn = document.getElementById('vs-inbox-send-clip');
	    const inboxSendPlaylistBtn = document.getElementById('vs-inbox-send-playlist');
	    const inboxSendExportBtn = document.getElementById('vs-inbox-send-export');
	    const inboxSendReportBtn = document.getElementById('vs-inbox-send-report');

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
    const layerStyleForm = document.getElementById('vs-layer-style-form');
    const layerColorInput = document.getElementById('vs-layer-color');
    const layerWidthInput = document.getElementById('vs-layer-width');
    const layerOpacityInput = document.getElementById('vs-layer-opacity');
    const layerLineStyleSelect = document.getElementById('vs-layer-line-style');
    const layerDoubleHeadToggle = document.getElementById('vs-layer-double-head');
    const layerLockedToggle = document.getElementById('vs-layer-locked');
    const layerDuplicateBtn = document.getElementById('vs-layer-duplicate');
    const layerFrontBtn = document.getElementById('vs-layer-front');
    const layerBackBtn = document.getElementById('vs-layer-back');

    const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    const wsPrefGetUrl = safeText(document.getElementById('vs-ws-pref-get-url')?.value);
    const wsPrefSetUrl = safeText(document.getElementById('vs-ws-pref-set-url')?.value);
    const teamId = Number(document.getElementById('vs-team-id')?.value || 0);
    const trimSaveUrl = safeText(document.getElementById('vs-video-trim-url')?.value);
    const trimEnabledInitial = safeText(document.getElementById('vs-video-trim-enabled')?.value) === '1';
    const trimInMsInitial = Number(document.getElementById('vs-video-trim-in-ms')?.value || 0) || 0;
    const trimOutMsInitial = Number(document.getElementById('vs-video-trim-out-ms')?.value || 0) || 0;

    // --- Corte base (trim): rango útil de trabajo persistente por vídeo.
    let trimEnabled = Boolean(trimEnabledInitial);
    let trimInS = Math.max(0, trimInMsInitial / 1000);
    let trimOutS = Math.max(0, trimOutMsInitial / 1000);
    let trimAutosaveT = 0;

    const readTrimInputs = () => {
      const a = Math.max(0, Number(trimInInput?.value || 0) || 0);
      const b = Math.max(0, Number(trimOutInput?.value || 0) || 0);
      trimEnabled = Boolean(trimEnabledToggle?.checked);
      trimInS = a;
      trimOutS = b;
    };
    const writeTrimInputs = () => {
      if (trimEnabledToggle) trimEnabledToggle.checked = Boolean(trimEnabled);
      if (trimInInput) trimInInput.value = String((Number(trimInS) || 0).toFixed(1));
      if (trimOutInput) trimOutInput.value = String((Number(trimOutS) || 0).toFixed(1));
    };
    const trimIsValid = () => {
      if (!trimEnabled) return true;
      if (!trimOutS) return true;
      return trimOutS > trimInS;
    };
    const clampToTrim = (t) => {
      const now = Math.max(0, Number(t) || 0);
      if (!trimEnabled) return now;
      const start = Math.max(0, Number(trimInS) || 0);
      const end = Math.max(0, Number(trimOutS) || 0);
      let next = now;
      if (next < start) next = start;
      if (end && end > start && next > end) next = end;
      return next;
    };
    const enforceTrimPlayback = () => {
      if (!trimEnabled) return;
      if (!trimIsValid()) return;
      const start = Math.max(0, Number(trimInS) || 0);
      const end = Math.max(0, Number(trimOutS) || 0);
      const now = Number(video.currentTime) || 0;
      if (now < start - 0.04) {
        try { video.currentTime = start; } catch (e) { /* ignore */ }
        return;
      }
      if (end && end > start && now > end + 0.04) {
        try { video.pause(); } catch (e) { /* ignore */ }
        try { video.currentTime = end; } catch (e) { /* ignore */ }
      }
    };
    const seekToTrim = (t, label = '') => {
      const next = clampToTrim(t);
      try { video.currentTime = next; } catch (e) { /* ignore */ }
      if (label) setStatus(`${label} ${fmtTimeShort(next)}`);
    };
    const saveTrim = async ({ silent = false } = {}) => {
      if (!trimSaveUrl || !videoId) return;
      readTrimInputs();
      if (!trimIsValid()) {
        if (!silent) setStatus('Corte base: OUT debe ser mayor que IN.', true);
        return;
      }
      try {
        const payload = { video_id: videoId, enabled: Boolean(trimEnabled), trim_in_s: Number(trimInS) || 0, trim_out_s: Number(trimOutS) || 0 };
        const resp = await fetch(trimSaveUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify(payload),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        trimEnabled = Boolean(data?.enabled);
        trimInS = Math.max(0, (Number(data?.trim_in_ms) || 0) / 1000);
        trimOutS = Math.max(0, (Number(data?.trim_out_ms) || 0) / 1000);
        writeTrimInputs();
        try {
          const d = new Date();
          const hh = String(d.getHours()).padStart(2, '0');
          const mm = String(d.getMinutes()).padStart(2, '0');
          const ss = String(d.getSeconds()).padStart(2, '0');
          const inLbl = fmtTimeShort(trimInS);
          const outLbl = trimOutS ? fmtTimeShort(trimOutS) : '—';
          if (trimSavedMsg) trimSavedMsg.textContent = `${trimEnabled ? 'Guardado ✓' : 'Guardado (desactivado)'} · ${hh}:${mm}:${ss} · IN ${inLbl} · OUT ${outLbl}`;
        } catch (e) { /* ignore */ }
        if (!silent) setStatus('Corte base guardado.');
        // Si está activo, asegúrate de estar dentro del rango.
        if (trimEnabled) enforceTrimPlayback();
      } catch (e) {
        try { if (trimSavedMsg) trimSavedMsg.textContent = 'No se pudo guardar.'; } catch (e2) { /* ignore */ }
        if (!silent) setStatus('No se pudo guardar el corte base.', true);
      }
    };
    const scheduleTrimAutosave = () => {
      if (!trimSaveUrl) return;
      window.clearTimeout(trimAutosaveT);
      trimAutosaveT = window.setTimeout(() => {
        // Solo autosave si está activo o si ya había un trim guardado.
        const should = Boolean(trimEnabledToggle?.checked) || Boolean(trimEnabledInitial);
        if (!should) return;
        saveTrim({ silent: true });
      }, 700);
    };
    // Inicializa UI desde backend
    writeTrimInputs();
    try {
      const inLbl = fmtTimeShort(trimInS);
      const outLbl = trimOutS ? fmtTimeShort(trimOutS) : '—';
      if (trimSavedMsg) trimSavedMsg.textContent = `${trimEnabled ? 'Corte base activo' : 'Corte base desactivado'} · IN ${inLbl} · OUT ${outLbl}`;
    } catch (e) { /* ignore */ }
    try {
      const in0 = Number(inInput?.value || 0) || 0;
      const out0 = Number(outInput?.value || 0) || 0;
      if (trimEnabled && trimIsValid() && !in0 && !out0) {
        if (inInput) inInput.value = String((Number(trimInS) || 0).toFixed(1));
        if (trimOutS && outInput) outInput.value = String((Number(trimOutS) || 0).toFixed(1));
      }
    } catch (e) { /* ignore */ }

    // Export settings persistence (client-side, sin coste servidor).
    const exportSettingsKey = () => `vs_export_settings:v1:${teamId || 'personal'}`;
    const loadExportSettings = () => {
      try {
        const raw = window.localStorage.getItem(exportSettingsKey()) || '';
        const obj = raw ? JSON.parse(raw) : {};
        if (obj && typeof obj === 'object') return obj;
      } catch (e) { /* ignore */ }
      return {};
    };
    const saveExportSettings = () => {
      try {
        const payload = {
          quality: safeText(qualitySelect?.value, 'med'),
          fps: safeText(fpsSelect?.value, ''),
          audio: Boolean(audioToggle?.checked),
        };
        window.localStorage.setItem(exportSettingsKey(), JSON.stringify(payload));
      } catch (e) { /* ignore */ }
    };
    try {
      const s = loadExportSettings();
      if (qualitySelect && s.quality) qualitySelect.value = String(s.quality);
      if (fpsSelect && (s.fps !== undefined)) fpsSelect.value = String(s.fps);
      if (audioToggle && (s.audio !== undefined)) audioToggle.checked = Boolean(s.audio);
    } catch (e) { /* ignore */ }
    qualitySelect?.addEventListener('change', saveExportSettings);
    fpsSelect?.addEventListener('change', saveExportSettings);
    audioToggle?.addEventListener('change', saveExportSettings);

    const initPersonalAssign = () => {
      if (!assignUrl || !videoId || !assignTeamSelect || !assignBtn) return;
      assignBtn.addEventListener('click', async () => {
        const targetTeamId = Number(assignTeamSelect.value || 0);
        if (!targetTeamId) {
          setStatus('Selecciona un equipo para asignar el vídeo.', true);
          return;
        }
        assignBtn.disabled = true;
        try {
          const resp = await fetch(assignUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            credentials: 'same-origin',
            body: JSON.stringify({ video_id: videoId, team_id: targetTeamId }),
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo asignar.');
          setStatus('Asignado. Recargando…');
          window.location.reload();
        } catch (e) {
          setStatus(e?.message || 'No se pudo asignar.', true);
        } finally {
          assignBtn.disabled = false;
        }
      });
    };
    initPersonalAssign();

    const setPresetsStatus = (text, isError = false) => {
      if (!presetsStatusEl) return;
      presetsStatusEl.textContent = safeText(text, '—');
      presetsStatusEl.style.color = isError ? '#fecaca' : 'rgba(226,232,240,0.72)';
    };

    const allowedEventKinds = new Set(['tag', 'note', 'goal', 'shot', 'press', 'turnover', 'abp']);

    const prefKeyForPackSelection = () => `vs_event_presets_pack:v1:${teamId || 'personal'}`;

    const prefKeyForEventPresets = (pack) => {
      const p = (safeText(pack, 'rival') === 'own') ? 'own' : 'rival';
      return `vs_event_presets:v2:${teamId || 'personal'}:${p}`;
    };

    const legacyPrefKeyForEventPresets = () => {
      if (!teamId) return '';
      return `vs_event_presets:team:${teamId}`;
    };

    const prefKeyForAutoClip = (pack) => {
      const p = (safeText(pack, 'rival') === 'own') ? 'own' : 'rival';
      return `vs_event_autoclip:v1:${teamId || 'personal'}:${p}`;
    };

    const wsPrefGet = async (key) => {
      if (!wsPrefGetUrl || !key) return null;
      const url = `${wsPrefGetUrl}?key=${encodeURIComponent(String(key))}`;
      const resp = await fetch(url, { credentials: 'same-origin' });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
      return data?.value ?? null;
    };

    const wsPrefSet = async (key, value) => {
      if (!wsPrefSetUrl || !key) return;
      const resp = await fetch(wsPrefSetUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        credentials: 'same-origin',
        body: JSON.stringify({ key: String(key), value: value ?? {} }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
    };

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

    const fabricCanvas = (() => {
      if (canTelestrate) {
        const c = new fabric.Canvas(canvasEl, { preserveObjectStacking: true, selection: true });
        try { c.freeDrawingBrush.width = 6; } catch (e) { /* ignore */ }
        try { c.freeDrawingBrush.color = '#22d3ee'; } catch (e) { /* ignore */ }
        // Asegura que el `upper-canvas` (que recibe los eventos) quede por encima del <video>.
        try { if (c.upperCanvasEl) c.upperCanvasEl.style.zIndex = '3'; } catch (e) { /* ignore */ }
        try { if (c.lowerCanvasEl) c.lowerCanvasEl.style.zIndex = '3'; } catch (e) { /* ignore */ }
        try { if (c.wrapperEl) c.wrapperEl.style.zIndex = '3'; } catch (e) { /* ignore */ }
        return c;
      }
      // Stub para que el resto del editor (IN/OUT, clips, timeline) no rompa si Fabric no está.
      return {
        isDrawingMode: false,
        selection: false,
        freeDrawingBrush: { width: 0, color: '#22d3ee' },
        toDatalessJSON: () => ({}),
        getWidth: () => 0,
        getHeight: () => 0,
        getPointer: () => ({ x: 0, y: 0 }),
        setWidth: () => {},
        setHeight: () => {},
        renderAll: () => {},
        clear: () => {},
        add: () => {},
        remove: () => {},
        getActiveObject: () => null,
        discardActiveObject: () => {},
        getObjects: () => [],
        setActiveObject: () => {},
        loadFromJSON: (_json, cb) => { try { cb && cb(); } catch (e) { /* ignore */ } },
        on: () => {},
        requestRenderAll: () => {},
      };
    })();

    const fxCtx = (() => {
      try { return fxEl?.getContext?.('2d') || null; } catch (e) { return null; }
    })();

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
      let clipBoundActive = false;
      let clipBoundStart = 0;
      let clipBoundEnd = 0;
	    const updateLoopUi = () => {
	      if (!btnLoop) return;
	      btnLoop.classList.toggle('primary', loopActive);
	      btnLoop.textContent = loopActive ? 'Loop ✓' : 'Loop';
	    };
	    if (initialClipId && String(window.location.pathname || '').includes('/analysis/video/clip/')) {
	      loopActive = true;
        clipBoundActive = true;
	    }
	    updateLoopUi();
	    btnLoop?.addEventListener('click', () => {
	      loopActive = !loopActive;
	      updateLoopUi();
	      setStatus(loopActive ? 'Loop activado.' : 'Loop desactivado.');
	    });
	    speedSelect?.addEventListener('change', () => {
	      const sp = Number(speedSelect.value || 1) || 1;
	      try { video.playbackRate = clamp(sp, 0.25, 5); } catch (e) { /* ignore */ }
	      setStatus(`Velocidad: ${String(video.playbackRate || sp)}x`);
	    });
	    try {
	      const sp0 = Number(speedSelect?.value || 1) || 1;
	      video.playbackRate = clamp(sp0, 0.25, 5);
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
      const enforceClipBound = () => {
        if (!clipBoundActive) return;
        if (playlistActive) return;
        // Usa los límites cacheados como fuente de verdad; si no existen, cae a inputs.
        const rawA = Number.isFinite(Number(clipBoundStart)) && (Number(clipBoundStart) > 0) ? Number(clipBoundStart) : (Number(inInput?.value || 0) || 0);
        const rawB = Number.isFinite(Number(clipBoundEnd)) && (Number(clipBoundEnd) > 0) ? Number(clipBoundEnd) : (Number(outInput?.value || 0) || 0);
        const start = Math.max(0, Math.min(rawA, rawB));
        const end = Math.max(rawA, rawB);
        if (!end || end <= start) return;
        clipBoundStart = start;
        clipBoundEnd = end;
        const now = Number(video.currentTime) || 0;
        if (now < start - 0.04) {
          try { video.currentTime = start; } catch (e) { /* ignore */ }
          return;
        }
        if (now >= end - 0.02) {
          // Si hay Loop activo, NO pausamos: dejamos que enforceLoop haga wrap a IN.
          if (!loopActive) {
            try { video.pause(); } catch (e) { /* ignore */ }
            try { video.currentTime = end; } catch (e) { /* ignore */ }
            // “Vuelve a la normalidad” tras reproducir un clip: desactiva el bound.
            clipBoundActive = false;
          }
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
	      enforceTrimPlayback();
        enforceClipBound();
	      enforceLoop();
	      updateMiniCursor();
	    });
      video.addEventListener('seeking', () => {
        if (!clipBoundActive) return;
        if (playlistActive) return;
        const start = Number(clipBoundStart) || 0;
        const end = Number(clipBoundEnd) || 0;
        if (!end || end <= start) return;
        const now = Number(video.currentTime) || 0;
        // UX: si el usuario intenta salir del rango IN/OUT mientras el "clip bound" está activo,
        // interpretamos que quiere volver al vídeo completo y desactivamos el bound.
        if (now < start - 0.04 || now > end + 0.04) {
          clipBoundActive = false;
          return;
        }
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
	      // Capa seleccionada (overlay) como barra editable (IN/OUT)
	      const range = currentLayerRange();
	      const rangeHtml = (() => {
	        if (!range) return '';
	        const a = Math.max(0, Number(range.tIn) || 0);
	        const b = Math.max(0, Number(range.tOut) || 0);
	        const start = Math.min(a, b);
	        const end = Math.max(a, b);
	        if (!end || end <= start + 0.02) return '';
	        const left = clamp(start / dur, 0, 1) * 100;
	        const width = Math.max(0.6, clamp((end - start) / dur, 0, 1) * 100);
	        const title = safeText(range.kind, 'capa');
	        return `
	          <div data-vs-layer-range="1" title="IN/OUT de la capa seleccionada · arrastra los tiradores" style="position:absolute;left:${left}%;width:${width}%;top:2px;bottom:2px;border-radius:999px;background:rgba(250,204,21,0.14);border:1px solid rgba(250,204,21,0.55);">
	            <div data-vs-layer-handle="in" title="IN · ${title}" style="position:absolute;left:-2px;top:-2px;bottom:-2px;width:12px;border-radius:999px;background:rgba(250,204,21,0.95);box-shadow:0 6px 18px rgba(0,0,0,0.35);cursor:ew-resize;"></div>
	            <div data-vs-layer-handle="out" title="OUT · ${title}" style="position:absolute;right:-2px;top:-2px;bottom:-2px;width:12px;border-radius:999px;background:rgba(250,204,21,0.95);box-shadow:0 6px 18px rgba(0,0,0,0.35);cursor:ew-resize;"></div>
	          </div>
	        `;
	      })();
	      miniTrack.innerHTML = segHtml + evHtml + rangeHtml;
	      updateMiniCursor();
	    };

      // Scrubbing en mini-timeline (iPad friendly): soporta drag con Pointer Events.
      // Motivo: `click` en iOS es lento/errático y no permite arrastrar.
      let scrubActive = false;
      let scrubPointerId = null;
      let scrubRect = null;
	      let scrubRaf = null;
	      let scrubTarget = null;
	      let lastPointerAt = 0;
	      let layerDrag = null;
	      let clipRangeDrag = null;
	      const setMiniRangeUi = (startS, endS) => {
	        if (!miniRange) return;
	        const dur = Number(video.duration) || 0;
	        if (!dur || !Number.isFinite(dur)) { miniRange.style.display = 'none'; return; }
	        const a = Math.max(0, Number(startS) || 0);
	        const b = Math.max(0, Number(endS) || 0);
	        const start = Math.min(a, b);
	        const end = Math.max(a, b);
	        if (!end || end <= start + 0.02) { miniRange.style.display = 'none'; return; }
	        const left = clamp(start / dur, 0, 1) * 100;
	        const width = Math.max(0.6, clamp((end - start) / dur, 0, 1) * 100);
	        miniRange.style.display = '';
	        miniRange.style.left = `${left}%`;
	        miniRange.style.width = `${width}%`;
	      };
	      const setClipInOut = (startS, endS, { commit = false } = {}) => {
	        const a = Math.max(0, Number(startS) || 0);
	        const b = Math.max(0, Number(endS) || 0);
	        const start = Math.min(a, b);
	        const end = Math.max(a, b);
	        try { if (inInput) inInput.value = String(start.toFixed(1)); } catch (e) { /* ignore */ }
	        try { if (outInput) outInput.value = String(end.toFixed(1)); } catch (e) { /* ignore */ }
	        if (commit) {
	          try { setStatus(`IN/OUT: ${fmtTimeShort(start)} → ${fmtTimeShort(end)}`); } catch (e) { /* ignore */ }
	        }
	      };
	      const setLayerRangeFromMini = (clientX, which, { commit = false } = {}) => {
	        const dur = Number(video.duration) || 0;
	        if (!dur || !Number.isFinite(dur)) return false;
	        const rect = (layerDrag?.rect) || (scrubRect) || miniTimeline.getBoundingClientRect();
	        const pct = clamp((Number(clientX) - rect.left) / Math.max(1, rect.width), 0, 1);
	        const range = currentLayerRange();
	        if (!range) return false;
	        const t = pct * dur;
	        const minDur = 0.2;
	        let tIn = Number(range.tIn) || 0;
	        let tOut = Number(range.tOut) || 0;
	        if (which === 'in') tIn = Math.min(t, tOut - minDur);
	        else tOut = Math.max(t, tIn + minDur);
	        try { if (layerInInput) layerInInput.value = String((Number(tIn) || 0).toFixed(1)); } catch (e) { /* ignore */ }
	        try { if (layerOutInput) layerOutInput.value = String((Number(tOut) || 0).toFixed(1)); } catch (e) { /* ignore */ }
	        try { setCurrentLayerRange(tIn, tOut, { commit }); } catch (e) { /* ignore */ }
	        try { renderMiniTimeline(); } catch (e) { /* ignore */ }
	        return true;
	      };
	      const seekFromMiniEvent = (ev, { commit = false, showLabel = false, preferTargetSeek = true } = {}) => {
	        const dur = Number(video.duration) || 0;
	        if (!dur || !Number.isFinite(dur)) return;
        let t = null;
        if (preferTargetSeek) {
          try {
            const hasAttr = Boolean(ev?.target?.getAttribute?.('data-seek') != null);
            if (hasAttr) {
              const direct = Number(ev?.target?.getAttribute?.('data-seek'));
              if (Number.isFinite(direct) && direct >= 0) t = direct;
            }
          } catch (e) {
            t = null;
          }
        }
        if (t == null) {
          const rect = scrubRect || miniTimeline.getBoundingClientRect();
          const clientX = Number(ev?.clientX);
          if (!Number.isFinite(clientX)) return;
          const pct = clamp((clientX - rect.left) / Math.max(1, rect.width), 0, 1);
          t = pct * dur;
        }
        const next = clampToTrim(t);
        scrubTarget = next;
        if (scrubRaf) return;
        scrubRaf = window.requestAnimationFrame(() => {
          scrubRaf = null;
          const target = Number(scrubTarget);
          if (!Number.isFinite(target)) return;
          try { video.currentTime = target; } catch (e) { /* ignore */ }
          try {
            const pct = clamp(target / dur, 0, 1) * 100;
            if (miniCursor) miniCursor.style.left = `${pct}%`;
          } catch (e) { /* ignore */ }
          if (commit && showLabel) setStatus(`→ ${fmtTimeShort(target)}`);
        });
      };

	      try {
	        miniTimeline.addEventListener('pointerdown', (ev) => {
	          const dur = Number(video.duration) || 0;
	          if (!dur || !Number.isFinite(dur)) return;
	          // Shift+drag: seleccionar IN/OUT para crear recortes/clips rápido
	          if (ev.shiftKey) {
	            clipRangeDrag = { pointerId: ev.pointerId, rect: miniTimeline.getBoundingClientRect(), startX: Number(ev.clientX) || 0 };
	            scrubActive = false;
	            scrubPointerId = null;
	            scrubRect = null;
	            layerDrag = null;
	            lastPointerAt = Date.now();
	            try { miniTimeline.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
	            try { ev.preventDefault(); } catch (e) { /* ignore */ }
	            const x0 = Number(ev.clientX);
	            const pct0 = clamp((x0 - clipRangeDrag.rect.left) / Math.max(1, clipRangeDrag.rect.width), 0, 1);
	            const t0 = pct0 * dur;
	            clipRangeDrag.t0 = t0;
	            clipRangeDrag.t1 = t0;
	            setMiniRangeUi(t0, t0 + 0.25);
	            setClipInOut(t0, t0 + 0.25, { commit: false });
	            return;
	          }
	          const handle = safeText(ev?.target?.getAttribute?.('data-vs-layer-handle'), '');
	          if (handle === 'in' || handle === 'out') {
	            layerDrag = { which: handle, pointerId: ev.pointerId, rect: miniTimeline.getBoundingClientRect() };
	            scrubActive = false;
	            scrubPointerId = null;
	            scrubRect = null;
	            lastPointerAt = Date.now();
	            try { miniTimeline.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
	            try { ev.preventDefault(); } catch (e) { /* ignore */ }
	            setLayerRangeFromMini(ev.clientX, handle, { commit: false });
	            return;
	          }
	          scrubActive = true;
	          scrubPointerId = ev.pointerId;
	          scrubRect = miniTimeline.getBoundingClientRect();
	          lastPointerAt = Date.now();
          try { miniTimeline.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
          try { ev.preventDefault(); } catch (e) { /* ignore */ }
          // Primer salto: si toca un clip/marker, permite "snap" al inicio.
          seekFromMiniEvent(ev, { preferTargetSeek: true });
        });
	        miniTimeline.addEventListener('pointermove', (ev) => {
	          if (clipRangeDrag) {
	            if (clipRangeDrag.pointerId != null && ev.pointerId !== clipRangeDrag.pointerId) return;
	            lastPointerAt = Date.now();
	            try { ev.preventDefault(); } catch (e) { /* ignore */ }
	            const dur = Number(video.duration) || 0;
	            if (!dur || !Number.isFinite(dur)) return;
	            const rect = clipRangeDrag.rect || miniTimeline.getBoundingClientRect();
	            const pct = clamp((Number(ev.clientX) - rect.left) / Math.max(1, rect.width), 0, 1);
	            const t = pct * dur;
	            clipRangeDrag.t1 = t;
	            setMiniRangeUi(clipRangeDrag.t0, clipRangeDrag.t1);
	            setClipInOut(clipRangeDrag.t0, clipRangeDrag.t1, { commit: false });
	            return;
	          }
	          if (layerDrag) {
	            if (layerDrag.pointerId != null && ev.pointerId !== layerDrag.pointerId) return;
	            lastPointerAt = Date.now();
	            try { ev.preventDefault(); } catch (e) { /* ignore */ }
	            setLayerRangeFromMini(ev.clientX, layerDrag.which, { commit: false });
	            return;
	          }
	          if (!scrubActive) return;
	          if (scrubPointerId != null && ev.pointerId !== scrubPointerId) return;
	          lastPointerAt = Date.now();
	          try { ev.preventDefault(); } catch (e) { /* ignore */ }
          // Durante el drag, ignora `data-seek` del target inicial (Pointer Events mantiene `target` fijo).
          seekFromMiniEvent(ev, { preferTargetSeek: false });
        });
	        const endScrub = (ev) => {
	          if (clipRangeDrag) {
	            if (clipRangeDrag.pointerId != null && ev && ev.pointerId != null && ev.pointerId !== clipRangeDrag.pointerId) return;
	            const dur = Number(video.duration) || 0;
	            if (dur && Number.isFinite(dur)) {
	              const t0 = Number(clipRangeDrag.t0) || 0;
	              const t1 = (ev && Number.isFinite(Number(ev.clientX))) ? (() => {
	                const rect = clipRangeDrag.rect || miniTimeline.getBoundingClientRect();
	                const pct = clamp((Number(ev.clientX) - rect.left) / Math.max(1, rect.width), 0, 1);
	                return pct * dur;
	              })() : (Number(clipRangeDrag.t1) || 0);
	              setMiniRangeUi(t0, t1);
	              setClipInOut(t0, t1, { commit: true });
	              // Alt+soltar: guardar clip directamente
	              try { if (ev && ev.altKey) clipSaveQuickBtn?.click?.(); } catch (e) { /* ignore */ }
	            }
	            clipRangeDrag = null;
	            return;
	          }
	          if (layerDrag) {
	            if (layerDrag.pointerId != null && ev && ev.pointerId != null && ev.pointerId !== layerDrag.pointerId) return;
	            try { if (ev) setLayerRangeFromMini(ev.clientX, layerDrag.which, { commit: true }); } catch (e) { /* ignore */ }
	            layerDrag = null;
	            return;
	          }
	          if (!scrubActive) return;
	          if (scrubPointerId != null && ev && ev.pointerId != null && ev.pointerId !== scrubPointerId) return;
	          scrubActive = false;
	          scrubPointerId = null;
          scrubRect = null;
          // En el final, un seek "commit" para fijar y mostrar feedback.
          try { if (ev) seekFromMiniEvent(ev, { commit: true, showLabel: true, preferTargetSeek: false }); } catch (e) { /* ignore */ }
        };
	        miniTimeline.addEventListener('pointerup', endScrub);
	        miniTimeline.addEventListener('pointercancel', endScrub);
	      } catch (e) {
        // Si no hay Pointer Events, el `click` seguirá funcionando.
      }

	    miniTimeline?.addEventListener('click', (ev) => {
        // Evita "ghost click" tras pointerup/touch.
        if (Date.now() - (lastPointerAt || 0) < 450) return;
	      const dur = Number(video.duration) || 0;
	      if (!dur || !Number.isFinite(dur)) return;
	      const hasAttr = (ev.target?.getAttribute?.('data-seek') != null);
	      const targetSeek = hasAttr ? Number(ev.target?.getAttribute?.('data-seek')) : NaN;
	      if (Number.isFinite(targetSeek) && targetSeek >= 0) {
	        seekToTrim(targetSeek, '→');
	        return;
	      }
	      const rect = miniTimeline.getBoundingClientRect();
	      const pct = clamp((ev.clientX - rect.left) / Math.max(1, rect.width), 0, 1);
	      const t = pct * dur;
	      seekToTrim(t, '→');
	    });
	    video.addEventListener('loadedmetadata', () => {
	      renderMiniTimeline();
	      enforceTrimPlayback();
	    });

	    const history = [];
	    const redo = [];
	    const pushHistory = () => {
	      try {
	        const json = fabricCanvas.toDatalessJSON(['data']);
	        history.push(json);
	        if (history.length > 40) history.shift();
	        redo.length = 0;
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
	      if (obj.data.base_sx == null) obj.data.base_sx = Number(obj.scaleX) || 1;
	      if (obj.data.base_sy == null) obj.data.base_sy = Number(obj.scaleY) || 1;
        // Bloqueo persistente
        try {
          const locked = Boolean(obj.data.locked);
          if (locked) {
            obj.set({
              lockMovementX: true,
              lockMovementY: true,
              lockScalingX: true,
              lockScalingY: true,
              lockRotation: true,
              hasControls: false,
              selectable: true,
              evented: true,
            });
          }
        } catch (e) { /* ignore */ }
        // Estilo persistente (líneas)
        try {
          const ls = safeText(obj.data.line_style, '');
          if ((ls === 'dash' || ls === 'dot' || ls === 'solid') && safeText(obj.data.__ls_applied, '') !== ls) {
            const sw = Number(obj?._objects?.[0]?.strokeWidth) || Number(obj?.strokeWidth) || 6;
            if (obj.type === 'group' && Array.isArray(obj._objects)) {
              obj._objects.forEach((child) => {
                if (child?.type === 'line' || child?.type === 'path' || child?.type === 'polyline') applyStrokeStyle(child, ls, sw);
              });
            } else if (obj?.type === 'line' || obj?.type === 'path' || obj?.type === 'polyline') {
              applyStrokeStyle(obj, ls, sw);
            }
            obj.data.__ls_applied = ls;
          }
        } catch (e) { /* ignore */ }
	    };

	    const seedLayerDataNow = (extra = {}) => {
	      const tIn = Number(video.currentTime) || 0;
      // Por defecto, limita la capa al tramo actual (OUT) si existe.
      // Esto evita que FX (spotlight/blur) y anotaciones se queden "para todo el vídeo" por sorpresa.
	      let tOut = 0;
	      try {
	        const rawOut = Number(outInput?.value);
	        if (Number.isFinite(rawOut) && rawOut > (tIn + 0.05)) tOut = rawOut;
	      } catch (e) { /* ignore */ }
	      // Duración por defecto (si el usuario no ha marcado OUT).
	      // Player marker se usa para “seguir” al jugador un rato → por defecto 5s.
	      const kind = safeText(extra?.kind, '');
	      const defaultDur = kind === 'player_marker' ? 5.0 : 2.0;
	      if (!tOut) tOut = tIn + defaultDur;
	      return {
	        uid: newUid(),
	        t_in_s: tIn,
	        t_out_s: tOut,
        fade_in_ms: 0,
        fade_out_ms: 0,
        anim: 'none',
	        ...extra,
	      };
	    };

      // Preferencias rápidas de estilo (flechas/trayectorias)
      const lsGet = (k, fallback = '') => {
        try {
          const v = window.localStorage?.getItem?.(k);
          return v == null ? fallback : String(v);
        } catch (e) { return fallback; }
      };
      const lsSet = (k, v) => {
        try { window.localStorage?.setItem?.(k, String(v)); } catch (e) { /* ignore */ }
      };
      const lineStyleKey = 'vs_line_style_v1';
      const arrowDoubleKey = 'vs_arrow_double_v1';
      const getLineStyle = () => {
        const v = safeText(lineStyleSelect?.value, 'solid');
        return (v === 'dash' || v === 'dot' || v === 'solid') ? v : 'solid';
      };
      const isArrowDouble = () => safeText(arrowDoubleBtn?.getAttribute?.('data-on'), '0') === '1';
      const setArrowDouble = (on) => {
        const v = on ? '1' : '0';
        try { arrowDoubleBtn?.setAttribute?.('data-on', v); } catch (e) { /* ignore */ }
        try { arrowDoubleBtn?.classList?.toggle?.('primary', Boolean(on)); } catch (e) { /* ignore */ }
        lsSet(arrowDoubleKey, v);
      };
      const applyStrokeStyle = (obj, style, sw) => {
        if (!obj) return;
        const st = (style === 'dash' || style === 'dot' || style === 'solid') ? style : '';
        if (!st || st === 'solid') {
          try { obj.set({ strokeDashArray: null }); } catch (e) { /* ignore */ }
          return;
        }
        const w = clamp(Number(sw) || 6, 1, 80);
        const dash = st === 'dot'
          ? [Math.max(0.1, Math.round(w * 0.35)), Math.max(3, Math.round(w * 1.9))]
          : [Math.max(6, Math.round(w * 3.2)), Math.max(4, Math.round(w * 2.1))];
        try {
          obj.set({
            strokeDashArray: dash,
            strokeLineCap: 'round',
            strokeLineJoin: 'round',
          });
        } catch (e) { /* ignore */ }
      };
      const applyArrowDefaultsFromStorage = () => {
        const ls = safeText(lsGet(lineStyleKey, ''), '');
        if (lineStyleSelect && (ls === 'solid' || ls === 'dash' || ls === 'dot')) {
          try { lineStyleSelect.value = ls; } catch (e) { /* ignore */ }
        }
        const dbl = safeText(lsGet(arrowDoubleKey, ''), '0');
        setArrowDouble(dbl === '1');
      };
      applyArrowDefaultsFromStorage();
      lineStyleSelect?.addEventListener('change', () => lsSet(lineStyleKey, getLineStyle()));
      arrowDoubleBtn?.addEventListener('click', () => setArrowDouble(!isArrowDouble()));

	    const normalizeKeyframes = (raw) => {
	      const arr = Array.isArray(raw) ? raw : [];
	      const items = arr
	        .map((k) => ({
	          t: Number(k?.t),
	          x: Number(k?.x),
	          y: Number(k?.y),
	        }))
	        .filter((k) => Number.isFinite(k.t) && Number.isFinite(k.x) && Number.isFinite(k.y))
	        .sort((a, b) => a.t - b.t);
	      // Dedup por tiempo (dejamos el último por si el usuario reajusta en el mismo instante)
	      const out = [];
	      for (const k of items) {
	        const last = out[out.length - 1];
	        if (last && Math.abs(last.t - k.t) < 0.04) out[out.length - 1] = k;
	        else out.push(k);
	      }
	      return out.slice(0, 80);
	    };

	    const upsertKeyframe = (obj, { t, x, y } = {}) => {
	      if (!obj || !obj.data) return;
	      if (!Number.isFinite(t) || !Number.isFinite(x) || !Number.isFinite(y)) return;
	      const next = normalizeKeyframes([...(Array.isArray(obj.data.kf) ? obj.data.kf : []), { t, x, y }]);
	      obj.data.kf = next;
	    };

	    const interpKeyframes = (kf, nowS) => {
	      const frames = normalizeKeyframes(kf);
	      if (!frames.length) return null;
	      if (frames.length === 1) return { x: frames[0].x, y: frames[0].y };
	      const t = Number(nowS) || 0;
	      if (t <= frames[0].t) return { x: frames[0].x, y: frames[0].y };
	      const last = frames[frames.length - 1];
	      if (t >= last.t) return { x: last.x, y: last.y };
	      for (let i = 0; i < frames.length - 1; i += 1) {
	        const a = frames[i];
	        const b = frames[i + 1];
	        if (t < a.t || t > b.t) continue;
	        const span = Math.max(0.001, b.t - a.t);
	        const u = clamp((t - a.t) / span, 0, 1);
	        return { x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u };
	      }
	      return { x: last.x, y: last.y };
	    };

	    const objectCenterPoint = (obj) => {
	      if (!obj) return null;
	      try {
	        const p = obj.getCenterPoint?.();
	        if (p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y))) return { x: Number(p.x), y: Number(p.y) };
	      } catch (e) { /* ignore */ }
	      const x = Number(obj.left);
	      const y = Number(obj.top);
	      return (Number.isFinite(x) && Number.isFinite(y)) ? { x, y } : null;
	    };

	    const setObjectCenterPoint = (obj, p) => {
	      if (!obj || !p || !Number.isFinite(Number(p.x)) || !Number.isFinite(Number(p.y))) return false;
	      try {
	        obj.setPositionByOrigin(new fabric.Point(Number(p.x), Number(p.y)), 'center', 'center');
	      } catch (e) {
	        try { obj.set({ left: Number(p.x), top: Number(p.y) }); } catch (e2) { return false; }
	      }
	      try { obj.setCoords?.(); } catch (e) { /* ignore */ }
	      obj.dirty = true;
	      return true;
	    };

	    const markerPointAt = (obj, nowS) => {
	      if (!obj || safeText(obj?.data?.kind) !== 'player_marker') return null;
	      if (Array.isArray(obj?.data?.kf) && obj.data.kf.length) {
	        const p = interpKeyframes(obj.data.kf, nowS);
	        if (p) return p;
	      }
	      return objectCenterPoint(obj);
	    };

	    const getPlayerMarkers = () => {
	      try {
	        return (fabricCanvas.getObjects?.() || []).filter((obj) => safeText(obj?.data?.kind) === 'player_marker');
	      } catch (e) {
	        return [];
	      }
	    };

	    const playCentroidAt = (nowS) => {
	      const pts = [];
	      for (const obj of getPlayerMarkers()) {
	        ensureLayerData(obj);
	        const alpha = computeTimedAlpha(obj.data, nowS);
	        if (alpha <= 0.001) continue;
	        const p = markerPointAt(obj, nowS);
	        if (p && Number.isFinite(p.x) && Number.isFinite(p.y)) pts.push(p);
	      }
	      if (!pts.length) return null;
	      return {
	        x: pts.reduce((acc, p) => acc + p.x, 0) / pts.length,
	        y: pts.reduce((acc, p) => acc + p.y, 0) / pts.length,
	      };
	    };

	    const selectedObjectsForSpace = () => {
	      try {
	        const active = fabricCanvas.getActiveObject?.() || null;
	        if (!active) return [];
	        if (active.type === 'activeSelection' && typeof active.getObjects === 'function') return active.getObjects() || [];
	        return [active];
	      } catch (e) {
	        return [];
	      }
	    };

	    const selectedSpaceZone = () => (
	      selectedObjectsForSpace().find((obj) => {
	        const k = safeText(obj?.data?.kind, '');
	        return k === 'space_zone' || k === 'surface_area';
	      }) || null
	    );

	    const selectedMarkerForSpace = (spaceObj = null) => (
	      selectedObjectsForSpace().find((obj) => obj !== spaceObj && safeText(obj?.data?.kind) === 'player_marker') || null
	    );

	    const selectedPlayerMarkers = () => {
	      const rows = selectedObjectsForSpace()
	        .filter((obj) => safeText(obj?.data?.kind) === 'player_marker')
	        .map((obj) => {
	          ensureLayerData(obj);
	          const p = markerPointAt(obj, Number(video.currentTime) || 0) || objectCenterPoint(obj) || { x: Number(obj.left) || 0, y: Number(obj.top) || 0 };
	          return { obj, x: Number(p.x) || 0, y: Number(p.y) || 0 };
	        });
	      rows.sort((a, b) => (a.x - b.x) || (a.y - b.y));
	      return rows.map((row) => row.obj);
	    };

	    const updateTacticalLink = (obj, nowS) => {
	      if (!obj || safeText(obj?.data?.kind) !== 'tactical_link') return false;
	      const fromUid = safeText(obj.data.from_uid, '');
	      const toUid = safeText(obj.data.to_uid, '');
	      if (!fromUid || !toUid) return false;
	      const markers = getPlayerMarkers();
	      const from = markers.find((m) => safeText(m?.data?.uid, '') === fromUid);
	      const to = markers.find((m) => safeText(m?.data?.uid, '') === toUid);
	      if (!from || !to) return false;
	      const p0 = markerPointAt(from, nowS) || objectCenterPoint(from);
	      const p1 = markerPointAt(to, nowS) || objectCenterPoint(to);
	      if (!p0 || !p1) return false;
	      try {
	        obj.set({
	          x1: Number(p0.x) || 0,
	          y1: Number(p0.y) || 0,
	          x2: Number(p1.x) || 0,
	          y2: Number(p1.y) || 0,
	        });
	        obj.setCoords?.();
	        obj.dirty = true;
	        return true;
	      } catch (e) {
	        return false;
	      }
	    };

	    const createTacticalStructureFromSelection = () => {
	      const markers = selectedPlayerMarkers().slice(0, 6);
	      if (markers.length < 2) {
	        setStatus('Estructura: selecciona 2-6 marcadores Jugador.', true);
	        return;
	      }
	      const nowS = Number(video.currentTime) || 0;
	      const color = strokeColor() || '#22d3ee';
	      const sw = clamp(Number(strokeWidth()) || 6, 2, 16);
	      const style = getLineStyle();
	      const pairs = [];
	      for (let i = 0; i < markers.length - 1; i += 1) pairs.push([markers[i], markers[i + 1]]);
	      if (markers.length === 3) pairs.push([markers[2], markers[0]]);
	      if (markers.length >= 4) {
	        pairs.push([markers[0], markers[markers.length - 1]]);
	      }
	      const created = [];
	      for (const [from, to] of pairs) {
	        ensureLayerData(from);
	        ensureLayerData(to);
	        const p0 = markerPointAt(from, nowS) || objectCenterPoint(from);
	        const p1 = markerPointAt(to, nowS) || objectCenterPoint(to);
	        if (!p0 || !p1) continue;
	        const line = new fabric.Line([p0.x, p0.y, p1.x, p1.y], {
	          stroke: color,
	          strokeWidth: sw,
	          strokeLineCap: 'round',
	          strokeLineJoin: 'round',
	          strokeDashArray: null,
	          selectable: true,
	          evented: true,
	          objectCaching: false,
	          shadow: 'rgba(0,0,0,0.30) 0 2px 6px',
	          strokeUniform: true,
	          perPixelTargetFind: true,
	          padding: 0,
	          cornerStyle: 'circle',
	          cornerColor: 'rgba(250,204,21,0.95)',
	          transparentCorners: false,
	          cornerSize: 14,
	        });
	        applyStrokeStyle(line, style, sw);
	        line.data = seedLayerDataNow({
	          kind: 'tactical_link',
	          from_uid: safeText(from.data.uid, ''),
	          to_uid: safeText(to.data.uid, ''),
	          line_style: style,
	          track: true,
	          anim: 'none',
	        });
	        try {
	          const tIn = Math.min(...markers.map((m) => Number(m?.data?.t_in_s) || nowS), Number(line.data.t_in_s) || nowS);
	          const tOuts = markers.map((m) => Number(m?.data?.t_out_s) || 0).filter((v) => v > nowS + 0.05);
	          line.data.t_in_s = Number.isFinite(tIn) ? tIn : nowS;
	          if (tOuts.length) line.data.t_out_s = Math.max(Number(line.data.t_out_s) || 0, ...tOuts);
	        } catch (e) { /* ignore */ }
	        fabricCanvas.add(line);
	        try { line.sendToBack?.(); } catch (e) { /* ignore */ }
	        created.push(line);
	      }
	      if (!created.length) {
	        setStatus('Estructura: no se pudieron crear líneas.', true);
	        return;
	      }
	      pushHistory();
	      try {
	        if (created.length === 1) fabricCanvas.setActiveObject(created[0]);
	        else fabricCanvas.setActiveObject(new fabric.ActiveSelection(created, { canvas: fabricCanvas }));
	      } catch (e) { /* ignore */ }
	      selectedFxId = 0;
	      updateLayerPanel();
	      renderFxList();
	      renderDrawLayers();
	      try { applyTimedLayers(); fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      setStatus(`Estructura creada: ${created.length} línea(s). Si los jugadores tienen AutoTrack, se moverá con ellos.`);
	    };

	    const promoteToSpaceZone = (obj) => {
	      if (!obj) return null;
	      ensureLayerData(obj);
	      obj.data.kind = 'space_zone';
	      obj.data.track = true;
	      if (!safeText(obj.data.space_base_fill, '')) obj.data.space_base_fill = safeText(obj.fill, 'rgba(34,211,238,0.20)');
	      if (!safeText(obj.data.space_base_stroke, '')) obj.data.space_base_stroke = safeText(obj.stroke, 'rgba(34,211,238,0.95)');
	      try {
	        obj.set({
	          fill: 'rgba(34,211,238,0.20)',
	          stroke: 'rgba(34,211,238,0.95)',
	          strokeWidth: Math.max(2, Number(obj.strokeWidth) || 2),
	          strokeDashArray: [10, 6],
	          objectCaching: false,
	        });
	      } catch (e) { /* ignore */ }
	      return obj;
	    };

	    const pointInsideObjectBounds = (obj, p, margin = 0) => {
	      if (!obj || !p) return false;
	      try {
	        const r = obj.getBoundingRect?.(true, true);
	        if (!r) return false;
	        return p.x >= (Number(r.left) - margin)
	          && p.x <= (Number(r.left) + Number(r.width) + margin)
	          && p.y >= (Number(r.top) - margin)
	          && p.y <= (Number(r.top) + Number(r.height) + margin);
	      } catch (e) {
	        return false;
	      }
	    };

	    const applySpaceZoneLiveStyle = (obj, occupied) => {
	      if (!obj || safeText(obj?.data?.kind) !== 'space_zone') return;
	      const fill = occupied ? 'rgba(244,63,94,0.24)' : 'rgba(34,211,238,0.20)';
	      const stroke = occupied ? 'rgba(244,63,94,0.96)' : 'rgba(34,211,238,0.95)';
	      try {
	        obj.set({ fill, stroke, strokeDashArray: occupied ? [4, 5] : [10, 6] });
	        obj.data.space_occupied = Boolean(occupied);
	        obj.dirty = true;
	      } catch (e) { /* ignore */ }
	    };

	    const isSpaceZoneOccupied = (obj, nowS) => {
	      if (!obj || safeText(obj?.data?.kind) !== 'space_zone') return false;
	      const aiRows = Array.isArray(obj?.data?.space_occ) ? obj.data.space_occ : [];
	      if (aiRows.length) {
	        const near = aiRows.reduce((best, row) => {
	          const dt = Math.abs((Number(row?.t) || 0) - (Number(nowS) || 0));
	          if (!best || dt < best.dt) return { dt, row };
	          return best;
	        }, null);
	        if (near && near.dt <= 0.18) {
	          try {
	            obj.data.space_occupied_count = Number(near.row?.count || 0) || 0;
	            obj.data.space_occupied_people = Array.isArray(near.row?.people) ? near.row.people.slice(0, 8) : [];
	          } catch (e) { /* ignore */ }
	          return Boolean(near.row?.occupied);
	        }
	      }
	      const margin = Math.max(8, Math.min(Number(obj.getScaledWidth?.()) || 0, Number(obj.getScaledHeight?.()) || 0) * 0.06);
	      for (const marker of getPlayerMarkers()) {
	        if (!marker.visible && computeTimedAlpha(marker?.data || {}, nowS) <= 0.001) continue;
	        const p = markerPointAt(marker, nowS);
	        if (p && pointInsideObjectBounds(obj, p, margin)) return true;
	      }
	      return false;
	    };

	    const applySpaceFollow = (obj, nowS) => {
	      if (!obj || safeText(obj?.data?.kind) !== 'space_zone') return false;
	      const mode = safeText(obj.data.follow_mode, 'manual');
	      if (mode === 'play') {
	        const ref = playCentroidAt(nowS);
	        const off = obj.data.follow_offset || {};
	        if (ref && Number.isFinite(Number(off.x)) && Number.isFinite(Number(off.y))) {
	          return setObjectCenterPoint(obj, { x: ref.x + Number(off.x), y: ref.y + Number(off.y) });
	        }
	      }
	      if (mode === 'player') {
	        const uid = safeText(obj.data.follow_player_uid, '');
	        const marker = getPlayerMarkers().find((m) => safeText(m?.data?.uid, '') === uid);
	        const ref = marker ? markerPointAt(marker, nowS) : null;
	        const off = obj.data.follow_offset || {};
	        if (ref && Number.isFinite(Number(off.x)) && Number.isFinite(Number(off.y))) {
	          return setObjectCenterPoint(obj, { x: ref.x + Number(off.x), y: ref.y + Number(off.y) });
	        }
	      }
	      if (mode === 'manual' && obj.data?.track && Array.isArray(obj.data.kf)) {
	        const pos = interpKeyframes(obj.data.kf, nowS);
	        if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) return setObjectCenterPoint(obj, pos);
	      }
	      return false;
	    };

	    const applyObjectFollow = (obj, nowS) => {
	      if (!obj || !obj.data || !obj.data.track) return false;
	      const kind = safeText(obj?.data?.kind, '');
	      if (kind === 'player_marker' || kind === 'tactical_link') return false;
	      const mode = safeText(obj.data.follow_mode, 'manual');
	      if (mode === 'play') {
	        const ref = playCentroidAt(nowS);
	        const off = obj.data.follow_offset || {};
	        if (ref && Number.isFinite(Number(off.x)) && Number.isFinite(Number(off.y))) {
	          return setObjectCenterPoint(obj, { x: ref.x + Number(off.x), y: ref.y + Number(off.y) });
	        }
	      }
	      if (mode === 'player') {
	        const uid = safeText(obj.data.follow_player_uid, '');
	        const marker = getPlayerMarkers().find((m) => safeText(m?.data?.uid, '') === uid);
	        const ref = marker ? markerPointAt(marker, nowS) : null;
	        const off = obj.data.follow_offset || {};
	        if (ref && Number.isFinite(Number(off.x)) && Number.isFinite(Number(off.y))) {
	          return setObjectCenterPoint(obj, { x: ref.x + Number(off.x), y: ref.y + Number(off.y) });
	        }
	      }
	      if (mode === 'manual' && Array.isArray(obj.data.kf)) {
	        const pos = interpKeyframes(obj.data.kf, nowS);
	        if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) return setObjectCenterPoint(obj, pos);
	      }
	      return false;
	    };

	    const getTrackSmoothStrength = () => clamp(Number(trackSmoothSelect?.value ?? 0.45) || 0, 0, 0.85);
	    const isTrackAntiJumpEnabled = () => Boolean(trackAntiJumpToggle ? trackAntiJumpToggle.checked : true);

	    const cleanTrackKeyframes = (raw, {
	      smooth = getTrackSmoothStrength(),
	      antiJump = isTrackAntiJumpEnabled(),
	      maxJumpPx = 0,
	    } = {}) => {
	      const frames = normalizeKeyframes(raw);
	      if (frames.length <= 2) return frames;
	      const cleaned = [frames[0]];
	      const baseSize = Math.max(
	        1,
	        Number(fabricCanvas?.getWidth?.()) || Number(canvasEl?.clientWidth) || 0,
	        Number(fabricCanvas?.getHeight?.()) || Number(canvasEl?.clientHeight) || 0
	      );
	      const jumpLimit = Math.max(Number(maxJumpPx) || 0, Math.min(baseSize * 0.12, 180));
	      let dropped = 0;
	      for (let i = 1; i < frames.length; i += 1) {
	        const prev = cleaned[cleaned.length - 1];
	        const cur = frames[i];
	        const dt = Math.max(0.08, Math.abs((Number(cur.t) || 0) - (Number(prev.t) || 0)));
	        const dx = (Number(cur.x) || 0) - (Number(prev.x) || 0);
	        const dy = (Number(cur.y) || 0) - (Number(prev.y) || 0);
	        const dist = Math.hypot(dx, dy);
	        if (antiJump && dist > Math.max(jumpLimit, jumpLimit * dt * 6)) {
	          dropped += 1;
	          continue;
	        }
	        cleaned.push(cur);
	      }
	      if (cleaned.length <= 2 || !smooth) {
	        cleaned.dropped = dropped;
	        return cleaned;
	      }
	      const strength = clamp(Number(smooth) || 0, 0, 0.85);
	      const forward = [];
	      for (let i = 0; i < cleaned.length; i += 1) {
	        const cur = cleaned[i];
	        if (!i) {
	          forward.push({ ...cur });
	          continue;
	        }
	        const prev = forward[forward.length - 1];
	        forward.push({
	          t: cur.t,
	          x: (prev.x * strength) + (cur.x * (1 - strength)),
	          y: (prev.y * strength) + (cur.y * (1 - strength)),
	        });
	      }
	      const out = [];
	      for (let i = forward.length - 1; i >= 0; i -= 1) {
	        const cur = forward[i];
	        if (i === forward.length - 1) {
	          out.unshift({ ...cur });
	          continue;
	        }
	        const next = out[0];
	        out.unshift({
	          t: cur.t,
	          x: (next.x * strength) + (cur.x * (1 - strength)),
	          y: (next.y * strength) + (cur.y * (1 - strength)),
	        });
	      }
	      const normalized = normalizeKeyframes(out);
	      normalized.dropped = dropped;
	      return normalized;
	    };

	    const smoothSelectedTrackMarker = () => {
	      const active = (() => { try { return fabricCanvas.getActiveObject?.() || null; } catch (e) { return null; } })();
	      const objs = (() => {
	        try {
	          if (!active) return [];
	          if (active.type === 'activeSelection' && typeof active.getObjects === 'function') return active.getObjects() || [];
	          return [active];
	        } catch (e) { return []; }
	      })();
	      let changed = 0;
	      let dropped = 0;
	      for (const obj of objs) {
	        if (safeText(obj?.data?.kind) !== 'player_marker') continue;
	        const kf = Array.isArray(obj?.data?.kf) ? obj.data.kf : [];
	        if (kf.length < 3) continue;
	        const next = cleanTrackKeyframes(kf, { smooth: Math.max(0.35, getTrackSmoothStrength()), antiJump: true });
	        dropped += Number(next.dropped || 0);
	        obj.data.kf = normalizeKeyframes(next);
	        changed += 1;
	      }
	      if (!changed) {
	        setStatus('Selecciona un marcador Jugador con tracking para suavizar.', true);
	        return;
	      }
	      pushHistory();
	      try { applyTimedLayers(); } catch (e) { /* ignore */ }
	      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      renderDrawLayers();
	      updateLayerPanel();
	      setStatus(`Tracking suavizado (${changed}). Saltos descartados: ${dropped}.`);
	    };

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
	          renderMiniTimeline();
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
	          renderMiniTimeline();
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
	      if (kind === 'curve_arrow') return 'Flecha curva';
	      if (kind === 'movement_line') return 'Trayectoria';
	      if (kind === 'tactical_link') return 'Estructura';
	      if (kind === 'line') return 'Línea';
	      if (kind === 'shape_rect' || kind === 'rect') return 'Rect';
	      if (kind === 'shape_ellipse' || kind === 'ellipse') return 'Círculo';
	      if (kind === 'measure') return 'Medición';
	      if (kind === 'player_marker') return 'Jugador';
	      if (kind === 'base') return 'Base';
	      if (kind === 'surface_area') return 'Área';
	      if (kind === 'space_zone') return 'Espacio';
      if (kind === 'template') return 'Plantilla';
      if (kind === 'callout') return `Callout ${safeText(obj?.data?.callout_n)}`;
      if (kind === 'path') return 'Trazo';
      if (kind === 'text' || String(kind).startsWith('text_')) return 'Texto';
      if (kind === 'group') return safeText(obj?.data?.kind, 'Grupo');
      return safeText(kind, 'Capa');
    };

    const renderDrawLayers = () => {
      if (!drawLayersList) return;
      const objs = (fabricCanvas.getObjects?.() || []).slice(0, 160);
      const dur = Math.max(1, Number(video.duration) || Number(outInput?.value) || 90);
      const rows = objs.slice().reverse().slice(0, 60).map((obj) => {
        ensureLayerData(obj);
        if (obj?.data?.hidden_list) return '';
        const uid = safeText(obj?.data?.uid);
        if (!uid) return '';
        const tIn = Number(obj?.data?.t_in_s) || 0;
        const tOut = Number(obj?.data?.t_out_s) || 0;
        const label = `${fmtTimeShort(tIn)} → ${fmtTimeShort(tOut || tIn)}`;
        const left = clamp((Math.min(tIn, tOut || tIn) / dur) * 100, 0, 100);
        const right = clamp((Math.max(tIn, tOut || tIn) / dur) * 100, 0, 100);
        const width = clamp(Math.max(2, right - left), 2, 100 - left);
        const isSel = activeObject() === obj;
        return `
          <div class="row" style="${isSel ? 'border-color: rgba(34,211,238,0.55); background: rgba(34,211,238,0.07);' : ''}">
            <div style="display:flex; flex-direction:column; gap:0.05rem;">
              <strong>${kindLabel(obj)}</strong>
              <small>${label}</small>
              <div class="vs-layer-timeline"><span style="margin-left:${left}%;width:${width}%;"></span></div>
            </div>
            <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
              <button type="button" class="button" data-vs-draw-select="${uid}">Seleccionar</button>
              <button type="button" class="button" data-vs-draw-seek="${uid}">Ir</button>
              <button type="button" class="button" data-vs-draw-kf="${uid}">Keyframe</button>
              <button type="button" class="button" data-vs-draw-dup="${uid}">Duplicar</button>
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
      Array.from(drawLayersList.querySelectorAll('[data-vs-draw-kf]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const uid = safeText(btn.getAttribute('data-vs-draw-kf'));
          const obj = uidMap.get(uid);
          if (!obj) return;
          try { fabricCanvas.setActiveObject(obj); } catch (e) { /* ignore */ }
          selectedFxId = 0;
          assignLayerFollowMode('manual');
        });
      });
      Array.from(drawLayersList.querySelectorAll('[data-vs-draw-dup]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const uid = safeText(btn.getAttribute('data-vs-draw-dup'));
          const obj = uidMap.get(uid);
          if (!obj) return;
          try { fabricCanvas.setActiveObject(obj); } catch (e) { /* ignore */ }
          selectedFxId = 0;
          updateLayerPanel();
          try { layerDuplicateBtn?.click?.(); } catch (e) { /* ignore */ }
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

      const parsePlayerMarkerInput = (raw) => {
        const txt = safeText(raw, '').trim();
        if (!txt) return { number: '', name: '' };
        const m = txt.match(/^\s*(\d{1,3})\s*[-–—.:]*\s*(.*)\s*$/);
        if (!m) return { number: '', name: '' };
        const number = safeText(m[1], '').trim();
        const name = safeText(m[2], '').trim();
        return { number, name };
      };

	      const teamColor = (team) => {
	        const t = safeText(team, 'home').toLowerCase();
	        if (t === 'away') return '#f59e0b'; // amber
	        return '#22d3ee'; // cyan
	      };

	    const createPlayerMarkerAt = (point, rawNumber, rawName, prefs) => {
        if (!point || typeof point.x !== 'number' || typeof point.y !== 'number') return null;
        const number = safeText(rawNumber, '').trim().slice(0, 3);
        const name = safeText(rawName, '').trim().toUpperCase().slice(0, 18);
        if (!number) return null;

        const p = { x: point.x, y: point.y };
	        const radius = 22 + Math.round(strokeWidth() / 2);
	        const prefsTeam = safeText(prefs?.team, 'home');
	        const prefsStyle = safeText(prefs?.style, 'tag');
	        // Por defecto respeta el color del editor. El selector Local/Rival actúa como preset (y metadato).
	        const color = strokeColor() || teamColor(prefsTeam);

        const ringOuter = new fabric.Circle({
          left: p.x,
          top: p.y,
          radius,
          fill: color,
          stroke: 'rgba(255,255,255,0.92)',
          strokeWidth: 3,
          originX: 'center',
          originY: 'center',
          shadow: 'rgba(0,0,0,0.35) 0 2px 6px',
        });
        const numText = new fabric.Text(String(number), {
          left: p.x,
          top: p.y + 1,
          fill: '#ffffff',
          fontSize: 18,
          fontWeight: '950',
          originX: 'center',
          originY: 'center',
          shadow: 'rgba(0,0,0,0.45) 0 1px 2px',
        });

        const nameText = new fabric.Text(name, {
          left: p.x,
          top: p.y,
          fill: '#ffffff',
          fontSize: 14,
          fontWeight: '950',
          originX: 'center',
          originY: 'center',
          shadow: 'rgba(0,0,0,0.45) 0 1px 2px',
        });
        try { nameText.initDimensions(); } catch (e) { /* ignore */ }
        const padX = 12;
        const padY = 7;
        const nameW = Math.max(52, Math.round((nameText.width || 0) + padX * 2));
        const nameH = Math.max(26, Math.round((nameText.height || 0) + padY * 2));
        const tagRect = new fabric.Rect({
          left: p.x,
          top: p.y,
          width: nameW,
          height: nameH,
          rx: 999,
          ry: 999,
          fill: 'rgba(2,6,23,0.68)',
          stroke: 'rgba(255,255,255,0.18)',
          strokeWidth: 1,
          originX: 'center',
          originY: 'center',
          shadow: 'rgba(0,0,0,0.25) 0 2px 6px',
        });

        const canvasW = Number(fabricCanvas.getWidth?.()) || 0;
        const canvasH = Number(fabricCanvas.getHeight?.()) || 0;
        const safeY = (canvasH && nameH) ? clamp(p.y, nameH / 2 + 2, canvasH - (nameH / 2) - 2) : p.y;
        // Por defecto, etiqueta a la derecha. Si no cabe, la pasamos a la izquierda.
        const defaultOffX = radius + 10 + (nameW / 2);
        const fitsRight = canvasW ? ((p.x + defaultOffX + (nameW / 2)) <= (canvasW - 4)) : true;
        const fitsLeft = canvasW ? ((p.x - defaultOffX - (nameW / 2)) >= 4) : true;
        const tagOffsetX = fitsRight ? defaultOffX : (fitsLeft ? -defaultOffX : defaultOffX);
        const tagX = canvasW ? clamp(p.x + tagOffsetX, (nameW / 2) + 2, canvasW - (nameW / 2) - 2) : (p.x + tagOffsetX);
        tagRect.set({ left: tagX, top: safeY });
        nameText.set({ left: tagX, top: safeY + 0.5 });

        const showTag = prefsStyle !== 'circle' && Boolean(name);
        const objects = showTag
          ? [ringOuter, numText, tagRect, nameText]
          : [ringOuter, numText];

	        const group = new fabric.Group(objects, { selectable: true });
	        group.data = seedLayerDataNow({ kind: 'player_marker', number: String(number), name, team: prefsTeam, style: prefsStyle, track: true });
	        // Keyframes: permite “seguir” al jugador moviendo el marcador y guardando posiciones por tiempo.
	        // En reproducción interpolamos entre keyframes (útil en clips donde el jugador se desplaza).
	        try {
	          const t0 = Number(group.data?.t_in_s) || (Number(video.currentTime) || 0);
	          const cx0 = Number(p.x) || 0;
	          const cy0 = Number(p.y) || 0;
	          group.data.kf = normalizeKeyframes([{ t: t0, x: cx0, y: cy0 }]);
	        } catch (e) { /* ignore */ }
	        fabricCanvas.add(group);
	        pushHistory();
	        try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	        setStatus('Jugador creado. Tip: en Play puedes arrastrarlo para que lo siga (se guardan keyframes).');
	        return { number, name };
	      };

      // Popover texto (multilínea)
      const textPop = document.getElementById('vs-text-pop');
      const textStyleSeg = document.getElementById('vs-text-style-seg');
      const textValueInput = document.getElementById('vs-text-value');
      const textCancelBtn = document.getElementById('vs-text-cancel');
      const textOkBtn = document.getElementById('vs-text-ok');
      let textPopCanvasPos = null;
      let textStyle = 'caption';

      const setTextSegActive = (root, value) => {
        if (!root) return;
        Array.from(root.querySelectorAll('button[data-vs-text-style]')).forEach((b) => {
          b.classList.toggle('active', safeText(b.getAttribute('data-vs-text-style')) === value);
        });
      };
      try {
        Array.from(textStyleSeg?.querySelectorAll?.('button[data-vs-text-style]') || []).forEach((b) => {
          b.addEventListener('click', () => {
            textStyle = safeText(b.getAttribute('data-vs-text-style'), 'caption');
            setTextSegActive(textStyleSeg, textStyle);
          });
        });
      } catch (e) { /* ignore */ }

	      const closeTextPop = () => {
	        textPopCanvasPos = null;
	        if (!textPop) return;
	        textPop.style.display = 'none';
	      };
      const openTextPopAt = (canvasPoint, clientPoint) => {
        if (!textPop || !stage) return;
        textPopCanvasPos = canvasPoint || null;
        setTextSegActive(textStyleSeg, textStyle);
        const rect = stage.getBoundingClientRect();
        const x = clamp((clientPoint?.x ?? (rect.left + rect.width * 0.5)) - rect.left, 8, Math.max(8, rect.width - 560));
        const y = clamp((clientPoint?.y ?? (rect.top + rect.height * 0.5)) - rect.top, 8, Math.max(8, rect.height - 220));
        textPop.style.left = `${Math.round(x)}px`;
        textPop.style.top = `${Math.round(y)}px`;
	        textPop.style.display = 'block';
	        try { textValueInput?.focus?.(); } catch (e) { /* ignore */ }
	      };

	      // Fallback (iPad/Safari): a veces Fabric no dispara `mouse:down` (o llega tarde).
	      // Abrimos el popover también desde el DOM cuando la herramienta activa es "text".
	      const domTextPointerHandler = (ev) => {
	        try {
	          if (!ev) return;
	          const activeTool = safeText(stage?.getAttribute?.('data-vs-tool'), '');
	          if (activeTool !== 'text') return;
	          if (!textPop || !stage || !canvasEl) return;
	          const tgt = ev.target;
	          if (tgt && textPop.contains(tgt)) return;
	          // Si el pop-up ya está abierto, no lo re-dispares.
	          try {
	            if (textPop.style && String(textPop.style.display || '') !== 'none') return;
	          } catch (e0) { /* ignore */ }
	          const rect = canvasEl.getBoundingClientRect();
	          const x = clamp((ev.clientX ?? 0) - rect.left, 0, rect.width);
	          const y = clamp((ev.clientY ?? 0) - rect.top, 0, rect.height);
	          openTextPopAt({ x, y }, { x: ev.clientX || 0, y: ev.clientY || 0 });
	          try { ev.preventDefault?.(); } catch (e2) { /* ignore */ }
	          try { ev.stopPropagation?.(); } catch (e3) { /* ignore */ }
	        } catch (e) { /* ignore */ }
	      };
	      try { canvasEl.addEventListener('pointerdown', domTextPointerHandler, { passive: false }); } catch (e) { /* ignore */ }
	      try { stage.addEventListener('pointerdown', domTextPointerHandler, { passive: false, capture: true }); } catch (e) { /* ignore */ }

	      const createTextOverlayAt = (point, rawText, styleName) => {
	        if (!point || typeof point.x !== 'number' || typeof point.y !== 'number') return null;
	        const text = safeText(rawText, '').trim();
	        if (!text) return null;
        const style = safeText(styleName, 'caption');
        const canvasW = Number(fabricCanvas.getWidth?.()) || 0;
        const maxW = canvasW ? clamp(Math.round(canvasW * 0.78), 260, 880) : 560;
        const fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif';

        const makeLowerThird = () => {
          const t = new fabric.Textbox(text, {
            left: point.x,
            top: point.y,
            width: maxW,
            fill: '#ffffff',
            fontSize: 26,
            fontWeight: '950',
            fontFamily,
            textAlign: 'left',
            shadow: 'rgba(0,0,0,0.55) 0 2px 8px',
            selectable: false,
            evented: false,
          });
          const padX = 16;
          const padY = 12;
          const bw = clamp(Math.round((t.width || maxW) + padX * 2), 240, maxW + padX * 2);
          const bh = clamp(Math.round((t.height || 40) + padY * 2), 44, 420);
          const bg = new fabric.Rect({
            left: point.x,
            top: point.y,
            width: bw,
            height: bh,
            rx: 18,
            ry: 18,
            fill: 'rgba(2,6,23,0.68)',
            stroke: 'rgba(255,255,255,0.14)',
            strokeWidth: 1,
            originX: 'left',
            originY: 'top',
            selectable: false,
            evented: false,
          });
          t.set({ left: point.x + padX, top: point.y + padY });
          const group = new fabric.Group([bg, t], { selectable: true });
          group.data = seedLayerDataNow({ kind: 'text_lower3', style });
          return group;
        };

        const makeCaption = () => {
          const t = new fabric.Textbox(text, {
            left: point.x,
            top: point.y,
            width: maxW,
            fill: '#ffffff',
            fontSize: 24,
            fontWeight: '900',
            fontFamily,
            textAlign: 'left',
            shadow: 'rgba(0,0,0,0.55) 0 2px 8px',
            selectable: false,
            evented: false,
          });
          // Stroke suave para legibilidad sobre césped
          t.set({ stroke: 'rgba(2,6,23,0.85)', strokeWidth: 2, paintFirst: 'stroke' });
          const group = new fabric.Group([t], { selectable: true });
          group.data = seedLayerDataNow({ kind: 'text_caption', style });
          return group;
        };

        const makePlain = () => {
          const t = new fabric.Textbox(text, {
            left: point.x,
            top: point.y,
            width: maxW,
            fill: strokeColor(),
            fontSize: 22,
            fontWeight: '850',
            fontFamily,
            textAlign: 'left',
            shadow: 'rgba(0,0,0,0.35) 0 1px 4px',
            selectable: false,
            evented: false,
          });
          const group = new fabric.Group([t], { selectable: true });
          group.data = seedLayerDataNow({ kind: 'text_plain', style });
          return group;
        };

        if (style === 'lower3') return makeLowerThird();
        if (style === 'plain') return makePlain();
        return makeCaption();
      };

      textCancelBtn?.addEventListener('click', () => closeTextPop());
      textOkBtn?.addEventListener('click', () => {
        if (!textPopCanvasPos) { closeTextPop(); return; }
        const value = safeText(textValueInput?.value, '').trim();
        if (!value) { closeTextPop(); return; }
        const group = createTextOverlayAt(textPopCanvasPos, value, textStyle);
        closeTextPop();
        try { if (textValueInput) textValueInput.value = ''; } catch (e) { /* ignore */ }
        if (!group) return;
        fabricCanvas.add(group);
        pushHistory();
        try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
        selectedFxId = 0;
        updateLayerPanel();
        renderFxList();
        renderDrawLayers();
      });
    colorInput?.addEventListener('change', () => {
      try { fabricCanvas.freeDrawingBrush.color = strokeColor(); } catch (e) { /* ignore */ }
    });
    widthInput?.addEventListener('input', () => {
      try { fabricCanvas.freeDrawingBrush.width = strokeWidth(); } catch (e) { /* ignore */ }
    });

		    let tool = 'select';
		    let arrowStart = null;
		    let lineStart = null;
		    let shapeStart = null;
		    let shapeDraft = null;
		    let measureStart = null;
		    let moveStart = null;
		    let lastArrowSig = '';
		    let lastArrowAt = 0;
		    let calloutSeq = 1;
	    // Tracking manual (player marker): auto-guardar keyframes mientras se mueve durante reproducción.
	    let trackingAutoKeyframes = true;
	    let trackingLastKfAtS = 0;
	    let trackingLastKfPos = null;
    // Surface Area (polígono)
    let areaDraftPoints = [];
    let areaDraftPolyline = null;
    let areaLastClickAt = 0;

		    const setTool = (next) => {
		      tool = next;
	      try { stage?.setAttribute?.('data-vs-tool', String(tool || '')); } catch (e) { /* ignore */ }
	      const isSelect = tool === 'select';
	      const isPen = tool === 'pen';
      fabricCanvas.isDrawingMode = isPen;
      try { fabricCanvas.selection = isSelect; } catch (e) { /* ignore */ }

      if (tool !== 'spot' && tool !== 'blur') fxPreview = null;
      fxEl.style.pointerEvents = (tool === 'spot' || tool === 'blur') ? 'auto' : 'none';
      // Cuando usamos FX (spot/blur) los eventos deben ir al canvas `vs-fx`.
      // Fabric coloca `upperCanvasEl` por encima y puede "comerse" el pointerdown,
      // haciendo que Spotlight parezca no funcionar.
      try {
        if (fabricCanvas?.upperCanvasEl) {
          fabricCanvas.upperCanvasEl.style.pointerEvents = (tool === 'spot' || tool === 'blur') ? 'none' : 'auto';
        }
      } catch (e) { /* ignore */ }

		      Array.from([btnSelect, btnPen, btnLine, btnRect, btnCircle, btnMeasure, btnArrow, btnCurve, btnText, btnPlayer, btnStructure, btnCallout, btnBase, btnArea, btnSpace, btnMove, btnSpot, btnBlur]).forEach((b) => b?.classList.remove('primary'));
		      if (tool === 'select') btnSelect?.classList.add('primary');
		      if (tool === 'pen') btnPen?.classList.add('primary');
		      if (tool === 'line') btnLine?.classList.add('primary');
		      if (tool === 'rect') btnRect?.classList.add('primary');
		      if (tool === 'circle') btnCircle?.classList.add('primary');
		      if (tool === 'measure') btnMeasure?.classList.add('primary');
		      if (tool === 'arrow') btnArrow?.classList.add('primary');
		      if (tool === 'curve') btnCurve?.classList.add('primary');
	      if (tool === 'text') btnText?.classList.add('primary');
	      if (tool === 'player') btnPlayer?.classList.add('primary');
	      if (tool === 'structure') btnStructure?.classList.add('primary');
	      if (tool === 'callout') btnCallout?.classList.add('primary');
	      if (tool === 'base') btnBase?.classList.add('primary');
	      if (tool === 'area') btnArea?.classList.add('primary');
	      if (tool === 'space') btnSpace?.classList.add('primary');
	      if (tool === 'move') btnMove?.classList.add('primary');
		      if (tool === 'spot') btnSpot?.classList.add('primary');
		      if (tool === 'blur') btnBlur?.classList.add('primary');
	        if (tool !== 'player') closePlayerPop();
	        if (tool !== 'text') closeTextPop();
	        if (tool !== 'area' && tool !== 'space') {
	          // Cancela borrador de área si cambiamos de herramienta.
	          try { if (areaDraftPolyline) fabricCanvas.remove(areaDraftPolyline); } catch (e) { /* ignore */ }
	          areaDraftPolyline = null;
          areaDraftPoints = [];
        }
		      const toolLabel = (() => {
		        if (tool === 'select') return 'Select';
		        if (tool === 'pen') return 'Pen';
		        if (tool === 'line') return 'Línea';
		        if (tool === 'rect') return 'Rect';
		        if (tool === 'circle') return 'Círculo';
		        if (tool === 'measure') return 'Medir';
		        if (tool === 'arrow') return 'Arrow';
		        if (tool === 'curve') return 'Curve';
		        if (tool === 'text') return 'Texto';
	        if (tool === 'player') return 'Jugador';
	        if (tool === 'callout') return 'Callout';
	        if (tool === 'base') return 'Base';
	        if (tool === 'area') return 'Área';
	        if (tool === 'space') return 'Espacio';
	        if (tool === 'move') return 'Trayectoria';
	        if (tool === 'spot') return 'Spotlight';
	        if (tool === 'blur') return 'Blur';
	        return String(tool || '');
	      })();
	      if (tool === 'player') setStatus('Herramienta: Jugador. Haz clic sobre el futbolista en el vídeo; luego pon dorsal/nombre y OK.');
	      else if (tool === 'text') setStatus('Herramienta: Texto. Haz clic sobre el vídeo y escribe la explicación.');
	      else if (tool === 'area' || tool === 'space') setStatus(`Herramienta: ${toolLabel}. Clic para añadir puntos; doble clic para cerrar; Esc cancela.`);
	      else if (tool === 'spot' || tool === 'blur') setStatus(`Herramienta: ${toolLabel}. Arrastra sobre el vídeo para definir la zona.`);
	      else if (tool === 'arrow' || tool === 'curve' || tool === 'move' || tool === 'line' || tool === 'rect' || tool === 'circle' || tool === 'measure') setStatus(`Herramienta: ${toolLabel}. Arrastra sobre el vídeo para dibujar.`);
	      else setStatus(`Herramienta: ${toolLabel}`);
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

	    const currentLayerRange = () => {
	      const target = currentLayerTarget();
	      if (!target) return null;
	      if (target.type === 'fx') {
	        const tIn = Math.max(0, Number(target.fx?.t_in_s) || 0);
	        const tOut = Math.max(0, Number(target.fx?.t_out_s) || 0);
	        return { tIn, tOut, type: 'fx', kind: safeText(target.fx?.kind, 'fx') };
	      }
	      const obj = target.obj;
	      ensureLayerData(obj);
	      const tIn = Math.max(0, Number(obj?.data?.t_in_s) || 0);
	      const tOut = Math.max(0, Number(obj?.data?.t_out_s) || 0);
	      return { tIn, tOut, type: 'fabric', kind: safeText(obj?.data?.kind, safeText(obj?.type, 'obj')) };
	    };

	    const setCurrentLayerRange = (tIn, tOut, { commit = true } = {}) => {
	      const target = currentLayerTarget();
	      if (!target) return false;
	      const a = Math.max(0, Number(tIn) || 0);
	      const b = Math.max(0, Number(tOut) || 0);
	      const start = Math.min(a, b);
	      const end = Math.max(a, b);
	      if (target.type === 'fx') {
	        target.fx.t_in_s = start;
	        target.fx.t_out_s = end;
	        renderFxList();
	        updateLayerPanel();
	        return true;
	      }
	      ensureLayerData(target.obj);
	      target.obj.data.t_in_s = start;
	      target.obj.data.t_out_s = end;
	      if (commit) pushHistory();
	      updateLayerPanel();
	      if (commit) renderDrawLayers();
	      return true;
	    };

	    const walkFabricObject = (obj, fn) => {
	      if (!obj || typeof fn !== 'function') return;
	      try { fn(obj); } catch (e) { /* ignore */ }
	      try {
	        if (Array.isArray(obj._objects)) obj._objects.forEach((child) => walkFabricObject(child, fn));
	      } catch (e) { /* ignore */ }
	    };
	    const firstPaintColor = (obj) => {
	      let found = '';
	      walkFabricObject(obj, (child) => {
	        if (found) return;
	        const stroke = safeText(child?.stroke, '');
	        const fill = safeText(child?.fill, '');
	        if (stroke && !stroke.startsWith('rgba(0,0,0,0')) found = stroke;
	        else if (fill && !fill.startsWith('rgba(0,0,0,0')) found = fill;
	      });
	      const m = String(found || '').match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
	      return m ? found : strokeColor();
	    };
	    const firstStrokeWidth = (obj) => {
	      let found = 0;
	      walkFabricObject(obj, (child) => {
	        if (!found && Number(child?.strokeWidth)) found = Number(child.strokeWidth);
	      });
	      return clamp(Math.round(found || strokeWidth() || 6), 1, 32);
	    };

	    const updateLayerPanel = () => {
	      if (!layerEmpty || !layerForm) return;
	      const target = currentLayerTarget();
      if (!target) {
        layerEmpty.style.display = '';
        layerForm.style.display = 'none';
        if (fxForm) fxForm.style.display = 'none';
        if (layerStyleForm) layerStyleForm.style.display = 'none';
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
        if (layerStyleForm) layerStyleForm.style.display = 'none';
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
	      const kind = safeText(obj?.data?.kind, '');
	      const showLineStyle = (kind === 'arrow' || kind === 'curve_arrow' || kind === 'movement_line' || kind === 'line' || kind === 'shape_rect' || kind === 'shape_ellipse');
	      const showDoubleHead = (kind === 'arrow' || kind === 'curve_arrow' || kind === 'movement_line');
	      if (layerStyleForm) layerStyleForm.style.display = '';
	      if (layerColorInput) layerColorInput.value = firstPaintColor(obj);
	      if (layerWidthInput) layerWidthInput.value = String(firstStrokeWidth(obj));
	      if (layerOpacityInput) layerOpacityInput.value = String(clamp(Number(obj.opacity ?? 1), 0.05, 1));
	      if (layerLineStyleSelect) {
	        const ls = safeText(obj?.data?.line_style, '');
	        layerLineStyleSelect.value = (ls === 'solid' || ls === 'dash' || ls === 'dot') ? ls : '';
	        layerLineStyleSelect.disabled = !showLineStyle;
	      }
	      if (layerDoubleHeadToggle) {
	        layerDoubleHeadToggle.checked = Boolean(obj?.data?.double_head);
	        layerDoubleHeadToggle.disabled = !showDoubleHead;
	      }
      if (layerLockedToggle) layerLockedToggle.checked = Boolean(obj?.data?.locked);
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

    const applyLayerStyleEdits = () => {
      const target = currentLayerTarget();
      if (!target || target.type !== 'fabric') return;
	      const obj = target.obj;
	      ensureLayerData(obj);

	      const kind = safeText(obj?.data?.kind, '');
	      const showLineStyle = (kind === 'arrow' || kind === 'curve_arrow' || kind === 'movement_line' || kind === 'line' || kind === 'shape_rect' || kind === 'shape_ellipse');
	      const showDoubleHead = (kind === 'arrow' || kind === 'curve_arrow' || kind === 'movement_line');
	      const color = safeText(layerColorInput?.value, '');
	      const width = clamp(Math.round(Number(layerWidthInput?.value || 0) || strokeWidth() || 6), 1, 32);
	      const opacity = clamp(Number(layerOpacityInput?.value ?? 1), 0.05, 1);

	      try {
	        obj.set({ opacity });
	        walkFabricObject(obj, (child) => {
	          const type = safeText(child?.type, '');
	          if (color && (child?.stroke || type === 'line' || type === 'path' || type === 'polyline')) child.set?.({ stroke: color });
	          if (color && child?.fill && !String(child.fill || '').startsWith('rgba(0,0,0,0)') && type !== 'textbox' && type !== 'text') child.set?.({ fill: colorToRgba(color, 0.18, color) });
	          if (Number(child?.strokeWidth)) child.set?.({ strokeWidth: width, strokeUniform: true });
	        });
	        obj.dirty = true;
	      } catch (e) { /* ignore */ }

	      if (showLineStyle && layerLineStyleSelect) {
	        const v = safeText(layerLineStyleSelect.value, '');
	        if (v === 'solid' || v === 'dash' || v === 'dot') obj.data.line_style = v;
	        else delete obj.data.line_style;
	        try {
          const sw = Number(obj?._objects?.[0]?.strokeWidth) || Number(obj?.strokeWidth) || Number(strokeWidth()) || 6;
          if (obj.type === 'group' && Array.isArray(obj._objects)) {
            obj._objects.forEach((child) => {
              if (child?.type === 'line' || child?.type === 'path' || child?.type === 'polyline') applyStrokeStyle(child, safeText(obj.data.line_style, ''), sw);
            });
          } else if (obj?.type === 'line' || obj?.type === 'path' || obj?.type === 'polyline') {
            applyStrokeStyle(obj, safeText(obj.data.line_style, ''), sw);
          }
          obj.dirty = true;
	        } catch (e) { /* ignore */ }
	      }

	      if (showDoubleHead && layerDoubleHeadToggle) {
	        obj.data.double_head = Boolean(layerDoubleHeadToggle.checked);
	      }

      if (layerLockedToggle) {
        const locked = Boolean(layerLockedToggle.checked);
        obj.data.locked = locked;
        try {
          obj.set({
            lockMovementX: locked,
            lockMovementY: locked,
            lockScalingX: locked,
            lockScalingY: locked,
            lockRotation: locked,
            hasControls: !locked,
            evented: true,
            selectable: true,
          });
          obj.dirty = true;
        } catch (e) { /* ignore */ }
      }

      pushHistory();
      updateLayerPanel();
      renderDrawLayers();
      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
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
      el?.addEventListener('change', () => { applyLayerPanelEdits(); updateLayerPanel(); renderMiniTimeline(); });
    });
    [layerColorInput, layerWidthInput, layerOpacityInput, layerLineStyleSelect, layerDoubleHeadToggle, layerLockedToggle].forEach((el) => {
      el?.addEventListener('change', () => applyLayerStyleEdits());
    });
    [fxIntensityInput, fxFeatherInput, fxBlurInput, fxOpacityInput].forEach((el) => {
      el?.addEventListener('change', () => { applyFxPanelEdits(); updateLayerPanel(); });
    });

    layerFrontBtn?.addEventListener('click', () => {
      const target = currentLayerTarget();
      if (!target || target.type !== 'fabric') return;
      try { fabricCanvas.bringToFront(target.obj); } catch (e) { /* ignore */ }
      pushHistory();
      renderDrawLayers();
    });
    layerBackBtn?.addEventListener('click', () => {
      const target = currentLayerTarget();
      if (!target || target.type !== 'fabric') return;
      try { fabricCanvas.sendToBack(target.obj); } catch (e) { /* ignore */ }
      pushHistory();
      renderDrawLayers();
    });
    layerDuplicateBtn?.addEventListener('click', () => {
      const target = currentLayerTarget();
      if (!target || target.type !== 'fabric') return;
      try {
        target.obj.clone((cloned) => {
          if (!cloned) return;
          try { ensureLayerData(cloned); } catch (e) { /* ignore */ }
          try { cloned.data = { ...(target.obj?.data || {}), uid: newUid() }; } catch (e) { /* ignore */ }
          try {
            cloned.left = (Number(cloned.left) || 0) + 18;
            cloned.top = (Number(cloned.top) || 0) + 12;
          } catch (e) { /* ignore */ }
          try { fabricCanvas.add(cloned); } catch (e) { /* ignore */ }
          pushHistory();
          try { fabricCanvas.setActiveObject(cloned); } catch (e) { /* ignore */ }
          selectedFxId = 0;
          updateLayerPanel();
          renderDrawLayers();
          renderFxList();
          setStatus('Capa duplicada.');
        });
      } catch (e) {
        setStatus('No se pudo duplicar la capa.', true);
      }
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
      deleteCurrentLayer({ confirm: true });
    });

	    const deleteCurrentLayer = ({ confirm = false } = {}) => {
      const target = currentLayerTarget();
      if (!target) return false;
      if (confirm) {
        const ok = window.confirm('¿Borrar capa seleccionada?');
        if (!ok) return false;
      }
      if (target.type === 'fx') {
        fxState.layers = (Array.isArray(fxState.layers) ? fxState.layers : []).filter((x) => Number(x?.id) !== Number(target.fx.id));
        selectedFxId = 0;
        reseedFxSeq();
        renderFxList();
        updateLayerPanel();
        renderDrawLayers();
        setStatus('Capa borrada.');
        return true;
      }
      try { fabricCanvas.remove(target.obj); } catch (e) { /* ignore */ }
      try { fabricCanvas.discardActiveObject?.(); } catch (e) { /* ignore */ }
      pushHistory();
      updateLayerPanel();
      renderDrawLayers();
      setStatus('Capa borrada.');
      return true;
    };

		    fabricCanvas.on('mouse:down', (opt) => {
		      if (calibMode) {
		        const p = fabricCanvas.getPointer(opt.e);
		        calibPts.push({ x: p.x, y: p.y });
		        const dot = new fabric.Circle({
		          left: p.x,
		          top: p.y,
		          radius: 6,
		          fill: 'rgba(250,204,21,0.95)',
		          stroke: 'rgba(255,255,255,0.75)',
		          strokeWidth: 1,
		          originX: 'center',
		          originY: 'center',
		          selectable: false,
		          evented: false,
		          objectCaching: false,
		        });
		        dot.data = seedLayerDataNow({ kind: 'calib_point' });
		        try { fabricCanvas.add(dot); fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
		        setCalibStatus(`Calibración: ${calibPts.length}/4`);
		        if (calibPts.length >= 4) {
		          calibMode = false;
		          const fieldW = 105;
		          const fieldH = 68;
		          const dst = [
		            { x: 0, y: 0 },
		            { x: fieldW, y: 0 },
		            { x: fieldW, y: fieldH },
		            { x: 0, y: fieldH },
		          ];
		          const H = computeHomography8(calibPts.slice(0, 4), dst);
		          if (!H) {
		            setCalibStatus('Calibración inválida (puntos colineales).', true);
		            setStatus('Calibración inválida. Repite.', true);
		          } else {
		            pitchCalib = { pts: calibPts.slice(0, 4), H, w: fieldW, h: fieldH };
		            savePitchCalib();
		            setCalibStatus(`OK · Campo ${fieldW}×${fieldH}m`);
		            setStatus('Calibración OK. Usa herramienta Medir.');
		          }
		        }
		        return;
		      }
		      if (tool === 'line') {
		        lineStart = fabricCanvas.getPointer(opt.e);
		      }
		      if (tool === 'rect' || tool === 'circle') {
		        shapeStart = fabricCanvas.getPointer(opt.e);
		        const sw = strokeWidth();
		        const c = strokeColor();
		        const fill = colorToRgba(c, 0.16, 'rgba(34,211,238,0.16)');
		        if (tool === 'rect') {
		          const r = new fabric.Rect({
		            left: shapeStart.x,
		            top: shapeStart.y,
		            width: 1,
		            height: 1,
		            fill,
		            stroke: c,
		            strokeWidth: clamp(sw, 1, 18),
		            strokeDashArray: null,
		            rx: 10,
		            ry: 10,
		            selectable: false,
		            evented: false,
		            objectCaching: false,
		            strokeUniform: true,
		          });
		          shapeDraft = r;
		          fabricCanvas.add(r);
		        } else {
		          const e = new fabric.Ellipse({
		            left: shapeStart.x,
		            top: shapeStart.y,
		            rx: 1,
		            ry: 1,
		            fill,
		            stroke: c,
		            strokeWidth: clamp(sw, 1, 18),
		            strokeDashArray: null,
		            originX: 'left',
		            originY: 'top',
		            selectable: false,
		            evented: false,
		            objectCaching: false,
		            strokeUniform: true,
		          });
		          shapeDraft = e;
		          fabricCanvas.add(e);
		        }
		      }
		      if (tool === 'measure') {
		        measureStart = fabricCanvas.getPointer(opt.e);
		      }
		      if (tool === 'arrow' || tool === 'curve') {
		        arrowStart = fabricCanvas.getPointer(opt.e);
		      }
	      if (tool === 'move') {
	        moveStart = fabricCanvas.getPointer(opt.e);
	      }
	      if (tool === 'text') {
	        const p = fabricCanvas.getPointer(opt.e);
	        // En Studio (con popover) usamos textarea multilínea. En otras vistas, fallback a prompt.
	        if (textPop) {
	          openTextPopAt({ x: p.x, y: p.y }, { x: opt?.e?.clientX || 0, y: opt?.e?.clientY || 0 });
	          return;
	        }
	        let entered = '';
	        try {
	          const v = window.prompt('Texto:', '');
	          if (v === null) return;
	          entered = safeText(v, '').trim();
	        } catch (e) { /* ignore */ }
	        if (!entered) return;
	        const group = createTextOverlayAt({ x: p.x, y: p.y }, entered, 'caption');
	        if (!group) return;
	        fabricCanvas.add(group);
	        pushHistory();
	        try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	      }
	      if (tool === 'player') {
	        const p = fabricCanvas.getPointer(opt.e);
	        openPlayerPopAt({ x: p.x, y: p.y }, { x: opt?.e?.clientX || 0, y: opt?.e?.clientY || 0 });
	      }
	      if (tool === 'base') {
	        const p = fabricCanvas.getPointer(opt.e);
	        const rx = clamp(26 + Math.round(strokeWidth() * 1.6), 18, 170);
	        const ry = clamp(14 + Math.round(strokeWidth() * 1.1), 10, 130);
	        const c = strokeColor();
	        const colorToRgba = (color, alpha, fallback) => {
	          if (color && color.startsWith('#') && (color.length === 7 || color.length === 4)) {
	            const hex = color.length === 4
	              ? `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}`
	              : color;
	            const r = parseInt(hex.slice(1, 3), 16);
	            const g = parseInt(hex.slice(3, 5), 16);
	            const b = parseInt(hex.slice(5, 7), 16);
	            return `rgba(${r},${g},${b},${alpha})`;
	          }
	          return fallback;
	        };
	        // Efecto "peana TV": relleno suave + aro brillante.
	        const fill = colorToRgba(c, 0.24, 'rgba(250,204,21,0.24)');
	        const glow = colorToRgba(c, 0.55, 'rgba(250,204,21,0.55)');
	        const baseFill = new fabric.Ellipse({
	          left: p.x,
	          top: p.y,
	          rx,
	          ry,
	          originX: 'center',
	          originY: 'center',
	          fill,
	          stroke: 'rgba(255,255,255,0.12)',
	          strokeWidth: 1,
	          selectable: false,
	          evented: false,
	        });
	        const baseRing = new fabric.Ellipse({
	          left: p.x,
	          top: p.y,
	          rx: rx + 2,
	          ry: ry + 2,
	          originX: 'center',
	          originY: 'center',
	          fill: 'rgba(0,0,0,0)',
	          stroke: 'rgba(255,255,255,0.78)',
	          strokeWidth: 2,
	          shadow: `rgba(0,0,0,0.35) 0 6px 14px`,
	          selectable: false,
	          evented: false,
	        });
	        const baseGlow = new fabric.Ellipse({
	          left: p.x,
	          top: p.y,
	          rx: rx + 6,
	          ry: ry + 6,
	          originX: 'center',
	          originY: 'center',
	          fill: 'rgba(0,0,0,0)',
	          stroke: glow,
	          strokeWidth: 10,
	          opacity: 0.35,
	          selectable: false,
	          evented: false,
	        });
	        const group = new fabric.Group([baseGlow, baseFill, baseRing], { selectable: true });
	        group.data = seedLayerDataNow({ kind: 'base' });
	        fabricCanvas.add(group);
	        pushHistory();
	        try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	      }
	      if (tool === 'area' || tool === 'space') {
	        const p = fabricCanvas.getPointer(opt.e);
	        const isSpaceTool = tool === 'space';
	        const now = Date.now();
	        const isDouble = (now - areaLastClickAt) < 380;
	        areaLastClickAt = now;
	        if (!areaDraftPolyline) {
	          areaDraftPoints = [{ x: p.x, y: p.y }];
	          areaDraftPolyline = new fabric.Polyline(areaDraftPoints, {
	            fill: 'rgba(0,0,0,0)',
	            stroke: isSpaceTool ? 'rgba(34,211,238,0.95)' : 'rgba(250,204,21,0.95)',
	            strokeWidth: 2,
	            strokeDashArray: [8, 6],
	            selectable: false,
	            evented: false,
	          });
	          fabricCanvas.add(areaDraftPolyline);
	          setStatus(`${isSpaceTool ? 'Espacio' : 'Área'}: añade puntos y doble clic para cerrar.`);
	          return;
	        }
	        // Añade punto
	        areaDraftPoints = [...areaDraftPoints, { x: p.x, y: p.y }];
	        try { areaDraftPolyline.set({ points: areaDraftPoints }); } catch (e) { /* ignore */ }
	        try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }

	        if (isDouble && areaDraftPoints.length >= 3) {
	          // Cierra polígono
	          try { fabricCanvas.remove(areaDraftPolyline); } catch (e) { /* ignore */ }
	          areaDraftPolyline = null;
	          const poly = new fabric.Polygon(areaDraftPoints, {
	            fill: (() => {
	              if (isSpaceTool) return 'rgba(34,211,238,0.20)';
	              const c = strokeColor();
	              if (c && c.startsWith('#') && (c.length === 7 || c.length === 4)) {
	                const hex = c.length === 4
	                  ? `#${c[1]}${c[1]}${c[2]}${c[2]}${c[3]}${c[3]}`
	                  : c;
	                const r = parseInt(hex.slice(1, 3), 16);
	                const g = parseInt(hex.slice(3, 5), 16);
	                const b = parseInt(hex.slice(5, 7), 16);
	                return `rgba(${r},${g},${b},0.22)`;
	              }
	              return 'rgba(245,158,11,0.22)';
	            })(),
	            stroke: isSpaceTool ? 'rgba(34,211,238,0.95)' : 'rgba(255,255,255,0.35)',
	            strokeWidth: isSpaceTool ? 2 : 1,
	            strokeDashArray: isSpaceTool ? [10, 6] : null,
	            shadow: 'rgba(0,0,0,0.25) 0 10px 22px',
	            selectable: true,
	            objectCaching: false,
	          });
	          poly.data = seedLayerDataNow({
	            kind: isSpaceTool ? 'space_zone' : 'surface_area',
	            track: isSpaceTool,
	            follow_mode: isSpaceTool ? 'manual' : '',
	            space_base_fill: isSpaceTool ? 'rgba(34,211,238,0.20)' : '',
	            space_base_stroke: isSpaceTool ? 'rgba(34,211,238,0.95)' : '',
	          });
	          if (isSpaceTool) {
	            const c = objectCenterPoint(poly);
	            if (c) poly.data.kf = normalizeKeyframes([{ t: Number(video.currentTime) || 0, x: c.x, y: c.y }]);
	          }
	          fabricCanvas.add(poly);
	          pushHistory();
	          try { fabricCanvas.setActiveObject(poly); } catch (e) { /* ignore */ }
	          selectedFxId = 0;
	          updateLayerPanel();
	          renderFxList();
	          renderDrawLayers();
	          areaDraftPoints = [];
	          setStatus(isSpaceTool ? 'Espacio móvil creado.' : 'Área creada.');
	        }
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
	      if (tool === 'measure' && measureStart) {
	        const end = fabricCanvas.getPointer(opt.e);
	        const start = measureStart;
	        measureStart = null;
	        const dx = end.x - start.x;
	        const dy = end.y - start.y;
	        const px = Math.hypot(dx, dy);
	        if (px < 8) return;
	        const m = distMeters(start, end);
	        const label = (m != null) ? `${m.toFixed(1)} m` : `${Math.round(px)} px`;
	        const color = strokeColor();
	        const sw = clamp(Number(strokeWidth()) || 6, 1, 18);
	        const line = new fabric.Line([start.x, start.y, end.x, end.y], {
	          stroke: color,
	          strokeWidth: clamp(sw, 2, 14),
	          strokeLineCap: 'round',
	          strokeDashArray: [10, 8],
	          selectable: false,
	          evented: false,
	          objectCaching: false,
	        });
	        const text = new fabric.Text(label, {
	          left: (start.x + end.x) / 2,
	          top: (start.y + end.y) / 2,
	          originX: 'center',
	          originY: 'center',
	          fill: '#ffffff',
	          fontSize: 18,
	          fontWeight: '900',
	          shadow: 'rgba(0,0,0,0.55) 0 2px 6px',
	        });
	        const padX = 10;
	        const padY = 6;
	        const bg = new fabric.Rect({
	          left: text.left,
	          top: text.top,
	          originX: 'center',
	          originY: 'center',
	          width: (Number(text.width) || 60) + padX * 2,
	          height: (Number(text.height) || 20) + padY * 2,
	          rx: 12,
	          ry: 12,
	          fill: 'rgba(2,6,23,0.65)',
	          stroke: 'rgba(255,255,255,0.18)',
	          strokeWidth: 1,
	          selectable: false,
	          evented: false,
	          objectCaching: false,
	        });
	        const group = new fabric.Group([line, bg, text], { selectable: true });
	        group.data = seedLayerDataNow({ kind: 'measure', meters: (m != null) ? Number(m) : null });
	        fabricCanvas.add(group);
	        pushHistory();
	        try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	        setStatus(m != null ? `Medición: ${label}` : 'Medición: sin calibración (px).');
	        return;
	      }
	      if ((tool === 'rect' || tool === 'circle') && shapeStart && shapeDraft) {
	        const end0 = fabricCanvas.getPointer(opt.e);
	        const start = shapeStart;
	        const draft = shapeDraft;
	        shapeStart = null;
	        shapeDraft = null;

	        let x0 = start.x;
	        let y0 = start.y;
	        let x1 = end0.x;
	        let y1 = end0.y;
	        // Shift = cuadrado/círculo perfecto
	        try {
	          if (opt?.e?.shiftKey) {
	            const dx = x1 - x0;
	            const dy = y1 - y0;
	            const m = Math.max(Math.abs(dx), Math.abs(dy));
	            x1 = x0 + (dx >= 0 ? m : -m);
	            y1 = y0 + (dy >= 0 ? m : -m);
	          }
	        } catch (e) { /* ignore */ }
	        const left = Math.min(x0, x1);
	        const top = Math.min(y0, y1);
	        const w = Math.max(1, Math.abs(x1 - x0));
	        const h = Math.max(1, Math.abs(y1 - y0));
	        if (Math.max(w, h) < 8) {
	          try { fabricCanvas.remove(draft); } catch (e) { /* ignore */ }
	          return;
	        }
	        try {
	          if (draft.type === 'rect') {
	            draft.set({ left, top, width: w, height: h });
	            draft.data = seedLayerDataNow({ kind: 'shape_rect' });
	          } else if (draft.type === 'ellipse') {
	            draft.set({ left, top, rx: w / 2, ry: h / 2 });
	            draft.data = seedLayerDataNow({ kind: 'shape_ellipse' });
	          }
	          draft.set({
	            selectable: true,
	            evented: true,
	            perPixelTargetFind: true,
	            padding: 0,
	            cornerStyle: 'circle',
	            cornerColor: 'rgba(250,204,21,0.95)',
	            transparentCorners: false,
	            cornerSize: 14,
	          });
	          draft.setCoords?.();
	        } catch (e) { /* ignore */ }
	        pushHistory();
	        try { fabricCanvas.setActiveObject(draft); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	        return;
	      }
	      if (tool === 'line' && lineStart) {
	        const end0 = fabricCanvas.getPointer(opt.e);
	        const sw = strokeWidth();
	        const color = strokeColor();
	        const style = getLineStyle();
	        const start = lineStart;
	        lineStart = null;
	        let end = { x: end0.x, y: end0.y };
	        try {
	          if (opt?.e?.shiftKey) {
	            const dx = end.x - start.x;
	            const dy = end.y - start.y;
	            if (Math.abs(dx) >= Math.abs(dy)) end.y = start.y;
	            else end.x = start.x;
	          }
	        } catch (e) { /* ignore */ }
	        const dx = end.x - start.x;
	        const dy = end.y - start.y;
	        if (Math.hypot(dx, dy) < 8) return;
	        const line = new fabric.Line([start.x, start.y, end.x, end.y], {
	          stroke: color,
	          strokeWidth: clamp(sw, 2, 18),
	          strokeLineCap: 'round',
	          strokeDashArray: null,
	          selectable: true,
	          evented: true,
	          objectCaching: false,
	          shadow: 'rgba(0,0,0,0.25) 0 2px 6px',
	          strokeUniform: true,
	          perPixelTargetFind: true,
	          padding: 0,
	          cornerStyle: 'circle',
	          cornerColor: 'rgba(250,204,21,0.95)',
	          transparentCorners: false,
	          cornerSize: 14,
	        });
	        applyStrokeStyle(line, style, sw);
	        line.data = seedLayerDataNow({ kind: 'line', line_style: style });
	        fabricCanvas.add(line);
	        pushHistory();
	        try { fabricCanvas.setActiveObject(line); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	        return;
	      }
	      if (tool === 'move' && moveStart) {
	        const end = fabricCanvas.getPointer(opt.e);
	        const sw = strokeWidth();
	        const color = strokeColor();
        const style = getLineStyle();
        const doubleHead = isArrowDouble();
        const dx = end.x - moveStart.x;
        const dy = end.y - moveStart.y;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const steps = clamp(Math.round(dist / 32), 2, 18);
        const pts = [];
        for (let i = 0; i <= steps; i += 1) {
          const t = i / steps;
          pts.push({ x: moveStart.x + dx * t, y: moveStart.y + dy * t });
        }
        const path = new fabric.Polyline(pts, {
          fill: 'rgba(0,0,0,0)',
          stroke: color,
          strokeWidth: clamp(sw, 2, 18),
          strokeLineCap: 'round',
          strokeLineJoin: 'round',
          strokeDashArray: null,
          selectable: false,
          evented: false,
          objectCaching: false,
          shadow: 'rgba(0,0,0,0.25) 0 2px 6px',
        });
        applyStrokeStyle(path, style, sw);
        const ang = Math.atan2(dy, dx);
        const headLen = clamp(18 + sw * 1.2, 16, 42);
        const headW = clamp(10 + sw * 0.8, 10, 28);
        const hx1 = end.x - headLen * Math.cos(ang) + headW * Math.cos(ang + Math.PI / 2);
        const hy1 = end.y - headLen * Math.sin(ang) + headW * Math.sin(ang + Math.PI / 2);
        const hx2 = end.x - headLen * Math.cos(ang) + headW * Math.cos(ang - Math.PI / 2);
        const hy2 = end.y - headLen * Math.sin(ang) + headW * Math.sin(ang - Math.PI / 2);
        const head = new fabric.Polygon([
          { x: end.x, y: end.y },
          { x: hx1, y: hy1 },
          { x: hx2, y: hy2 },
        ], {
          fill: color,
          stroke: 'rgba(255,255,255,0.65)',
          strokeWidth: 1,
          selectable: false,
          evented: false,
          shadow: 'rgba(0,0,0,0.25) 0 2px 6px',
        });
        const objects = [path, head];
        if (doubleHead) {
          const sx = moveStart.x;
          const sy = moveStart.y;
          const shx1 = sx + headLen * Math.cos(ang) + headW * Math.cos(ang + Math.PI / 2);
          const shy1 = sy + headLen * Math.sin(ang) + headW * Math.sin(ang + Math.PI / 2);
          const shx2 = sx + headLen * Math.cos(ang) + headW * Math.cos(ang - Math.PI / 2);
          const shy2 = sy + headLen * Math.sin(ang) + headW * Math.sin(ang - Math.PI / 2);
          const headStart = new fabric.Polygon([
            { x: sx, y: sy },
            { x: shx1, y: shy1 },
            { x: shx2, y: shy2 },
          ], {
            fill: color,
            stroke: 'rgba(255,255,255,0.65)',
            strokeWidth: 1,
            selectable: false,
            evented: false,
            shadow: 'rgba(0,0,0,0.25) 0 2px 6px',
          });
          objects.push(headStart);
        }
        const group = new fabric.Group(objects, { selectable: true });
        group.data = seedLayerDataNow({ kind: 'movement_line', line_style: style, double_head: doubleHead, anim: 'none' });
        fabricCanvas.add(group);
        pushHistory();
        try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
        selectedFxId = 0;
        updateLayerPanel();
        renderFxList();
        renderDrawLayers();
        moveStart = null;
      }
      if ((tool !== 'arrow' && tool !== 'curve') || !arrowStart) return;
      const end = fabricCanvas.getPointer(opt.e);
      const sw = strokeWidth();
      const color = strokeColor();
      // iOS/Safari puede disparar eventos duplicados (touchend + mouseup) → evita duplicar flechas.
      try {
        const sig = [
          tool,
          Math.round((arrowStart.x || 0) / 3),
          Math.round((arrowStart.y || 0) / 3),
          Math.round((end.x || 0) / 3),
          Math.round((end.y || 0) / 3),
          Math.round(sw || 0),
          String(color || ''),
        ].join(':');
        const nowTs = Date.now();
        if (sig && sig === lastArrowSig && (nowTs - lastArrowAt) < 260) {
          arrowStart = null;
          return;
        }
        lastArrowSig = sig;
        lastArrowAt = nowTs;
      } catch (e) { /* ignore */ }
      if (tool === 'curve') {
        const dx = end.x - arrowStart.x;
        const dy = end.y - arrowStart.y;
	        const dist = Math.max(1, Math.hypot(dx, dy));
          const style = getLineStyle();
          const doubleHead = isArrowDouble();
	        const mx = (arrowStart.x + end.x) / 2;
	        const my = (arrowStart.y + end.y) / 2;
	        const perpX = -dy / dist;
	        const perpY = dx / dist;
	        const offset = clamp(dist * 0.22, 18, 120);
	        const invert = Boolean(opt?.e?.shiftKey);
	        const sign = invert ? -1 : 1;
	        const cx = mx + perpX * offset * sign;
	        const cy = my + perpY * offset * sign;
	        const pathStr = `M ${arrowStart.x} ${arrowStart.y} Q ${cx} ${cy} ${end.x} ${end.y}`;
	        const path = new fabric.Path(pathStr, {
	          fill: '',
          stroke: color,
          strokeWidth: sw,
          strokeLineCap: 'round',
          strokeLineJoin: 'round',
          selectable: true,
        });
        applyStrokeStyle(path, style, sw);
        path.data = { draw_len: Math.round(dist * 1.25) };
        const ang = Math.atan2(end.y - cy, end.x - cx);
        const headLen = 14 + sw;
        const hx1 = end.x - headLen * Math.cos(ang - Math.PI / 7);
        const hy1 = end.y - headLen * Math.sin(ang - Math.PI / 7);
        const hx2 = end.x - headLen * Math.cos(ang + Math.PI / 7);
        const hy2 = end.y - headLen * Math.sin(ang + Math.PI / 7);
        const head = new fabric.Polygon([
          { x: end.x, y: end.y },
          { x: hx1, y: hy1 },
          { x: hx2, y: hy2 },
        ], { fill: color, selectable: true });
        const objects = [path, head];
        if (doubleHead) {
          const sAng = Math.atan2(cy - arrowStart.y, cx - arrowStart.x);
          const shx1 = arrowStart.x + (14 + sw) * Math.cos(sAng - Math.PI / 7);
          const shy1 = arrowStart.y + (14 + sw) * Math.sin(sAng - Math.PI / 7);
          const shx2 = arrowStart.x + (14 + sw) * Math.cos(sAng + Math.PI / 7);
          const shy2 = arrowStart.y + (14 + sw) * Math.sin(sAng + Math.PI / 7);
          const headStart = new fabric.Polygon([
            { x: arrowStart.x, y: arrowStart.y },
            { x: shx1, y: shy1 },
            { x: shx2, y: shy2 },
          ], { fill: color, selectable: true });
          objects.push(headStart);
        }
        const group = new fabric.Group(objects, { selectable: true });
        // Nota: el anim "draw" usa strokeDashArray como máscara; para estilos dash/dot dejamos anim en none.
        const anim = (style === 'solid') ? 'draw' : 'none';
        group.data = seedLayerDataNow({ kind: 'curve_arrow', anim, anim_ms: 850, line_style: style, double_head: doubleHead });
        fabricCanvas.add(group);
      } else {
        const line = new fabric.Line([arrowStart.x, arrowStart.y, end.x, end.y], {
          stroke: color,
          strokeWidth: sw,
          selectable: true,
        });
        const style = getLineStyle();
        const doubleHead = isArrowDouble();
        applyStrokeStyle(line, style, sw);
        const ang = Math.atan2(end.y - arrowStart.y, end.x - arrowStart.x);
        const headLen = 14 + sw;
        const hx1 = end.x - headLen * Math.cos(ang - Math.PI / 7);
        const hy1 = end.y - headLen * Math.sin(ang - Math.PI / 7);
        const hx2 = end.x - headLen * Math.cos(ang + Math.PI / 7);
        const hy2 = end.y - headLen * Math.sin(ang + Math.PI / 7);
        const head = new fabric.Polygon([
          { x: end.x, y: end.y },
          { x: hx1, y: hy1 },
          { x: hx2, y: hy2 },
        ], { fill: color, selectable: true });
        const objects = [line, head];
        if (doubleHead) {
          const sx = arrowStart.x;
          const sy = arrowStart.y;
          const sAng = ang + Math.PI;
          const shx1 = sx - headLen * Math.cos(sAng - Math.PI / 7);
          const shy1 = sy - headLen * Math.sin(sAng - Math.PI / 7);
          const shx2 = sx - headLen * Math.cos(sAng + Math.PI / 7);
          const shy2 = sy - headLen * Math.sin(sAng + Math.PI / 7);
          const headStart = new fabric.Polygon([
            { x: sx, y: sy },
            { x: shx1, y: shy1 },
            { x: shx2, y: shy2 },
          ], { fill: color, selectable: true });
          objects.push(headStart);
        }
        const group = new fabric.Group(objects, { selectable: true });
        const anim = (style === 'solid') ? 'draw' : 'none';
        group.data = seedLayerDataNow({ kind: 'arrow', anim, anim_ms: 700, line_style: style, double_head: doubleHead });
        fabricCanvas.add(group);
      }
      pushHistory();
      try { fabricCanvas.setActiveObject(fabricCanvas.getObjects().slice(-1)[0]); } catch (e) { /* ignore */ }
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
		    // Auto-keyframes mientras arrastras el marcador durante reproducción (sin tener que pausar cada vez).
		    fabricCanvas.on('object:moving', (opt) => {
		      const obj = opt?.target;
		      if (!obj || !obj.data) return;
		      const kind = safeText(obj.data.kind);
		      if (kind === 'tactical_link') return;
		      if (!obj.data.track) return;
		      if (kind !== 'player_marker' && safeText(obj.data.follow_mode, 'manual') !== 'manual') return;
		      if (video.paused) return;
		      if (!trackingAutoKeyframes) return;
		      try {
		        const t = Number(video.currentTime) || 0;
		        if (t <= 0) return;
		        // Throttle: evita miles de keyframes.
		        if ((t - trackingLastKfAtS) < 0.18) return;
		        const c = obj.getCenterPoint ? obj.getCenterPoint() : null;
		        const x = Number(c?.x ?? obj.left) || 0;
		        const y = Number(c?.y ?? obj.top) || 0;
		        if (trackingLastKfPos) {
		          const dx = x - (Number(trackingLastKfPos.x) || 0);
		          const dy = y - (Number(trackingLastKfPos.y) || 0);
		          if (Math.hypot(dx, dy) < 1.6) return;
		        }
		        upsertKeyframe(obj, { t, x, y });
		        trackingLastKfAtS = t;
		        trackingLastKfPos = { x, y };
		        // No hacemos pushHistory en cada move (sería pesado); se guarda al soltar (object:modified).
		      } catch (e) { /* ignore */ }
		    });
		    // Guardar keyframes al mover un marcador de jugador (tracking manual).
		    fabricCanvas.on('object:modified', (opt) => {
		      const obj = opt?.target;
		      if (!obj || !obj.data) return;
		      const kind = safeText(obj.data.kind);
	      if (kind === 'tactical_link') return;
	      if (!obj.data.track) return;
		      try {
		        const t = Number(video.currentTime) || 0;
		        const c = obj.getCenterPoint ? obj.getCenterPoint() : null;
		        const x = Number(c?.x ?? obj.left) || 0;
		        const y = Number(c?.y ?? obj.top) || 0;
		        upsertKeyframe(obj, { t, x, y });
		        if (kind !== 'player_marker') {
		          obj.data.follow_mode = 'manual';
		          obj.data.follow_player_uid = '';
		          obj.data.follow_offset = null;
		        }
		        trackingLastKfAtS = t;
		        trackingLastKfPos = { x, y };
		        pushHistory();
		        renderDrawLayers();
		        setStatus(`${kind === 'player_marker' ? 'Jugador' : (kind === 'space_zone' ? 'Espacio' : 'Recurso')}: posición guardada @ ${fmtTime(t)}`);
		      } catch (e) { /* ignore */ }
		    });
    fabricCanvas.on('selection:created', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); renderDrawLayers(); renderMiniTimeline(); });
    fabricCanvas.on('selection:updated', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); renderDrawLayers(); renderMiniTimeline(); });
    fabricCanvas.on('selection:cleared', () => { updateLayerPanel(); renderDrawLayers(); renderMiniTimeline(); });

		    btnSelect?.addEventListener('click', () => setTool('select'));
		    btnPen?.addEventListener('click', () => setTool('pen'));
		    btnLine?.addEventListener('click', () => setTool('line'));
		    btnRect?.addEventListener('click', () => setTool('rect'));
		    btnCircle?.addEventListener('click', () => setTool('circle'));
		    btnMeasure?.addEventListener('click', () => setTool('measure'));
		    btnArrow?.addEventListener('click', () => setTool('arrow'));
		    btnCurve?.addEventListener('click', () => setTool('curve'));
	    btnText?.addEventListener('click', () => setTool('text'));
	    btnPlayer?.addEventListener('click', () => setTool('player'));
	    btnStructure?.addEventListener('click', () => { setTool('structure'); createTacticalStructureFromSelection(); });
	    btnCallout?.addEventListener('click', () => setTool('callout'));
	    btnBase?.addEventListener('click', () => setTool('base'));
	    btnArea?.addEventListener('click', () => setTool('area'));
	    btnSpace?.addEventListener('click', () => setTool('space'));
	    btnMove?.addEventListener('click', () => setTool('move'));
	    btnSpot?.addEventListener('click', () => setTool('spot'));
	    btnBlur?.addEventListener('click', () => setTool('blur'));

	    const assignSpaceFollowMode = (mode) => {
	      const space = promoteToSpaceZone(selectedSpaceZone());
	      if (!space) { setStatus('Selecciona un Área/Espacio para aplicar seguimiento.', true); return; }
	      const nowS = Number(video.currentTime) || 0;
	      const center = objectCenterPoint(space);
	      if (!center) { setStatus('No se pudo leer el centro del espacio.', true); return; }
	      if (mode === 'play') {
	        const ref = playCentroidAt(nowS);
	        if (!ref) { setStatus('No hay marcadores Jugador visibles para seguir la jugada.', true); return; }
	        space.data.follow_mode = 'play';
	        space.data.follow_offset = { x: center.x - ref.x, y: center.y - ref.y };
	        space.data.follow_player_uid = '';
	        space.data.track = true;
	        upsertKeyframe(space, { t: nowS, x: center.x, y: center.y });
	        setStatus('Espacio: seguirá la jugada.');
	      } else if (mode === 'player') {
	        const marker = selectedMarkerForSpace(space);
	        if (!marker) { setStatus('Selecciona a la vez el espacio y un marcador Jugador.', true); return; }
	        const ref = markerPointAt(marker, nowS);
	        if (!ref) { setStatus('No se pudo leer la posición del jugador.', true); return; }
	        ensureLayerData(marker);
	        space.data.follow_mode = 'player';
	        space.data.follow_player_uid = safeText(marker.data.uid, '');
	        space.data.follow_offset = { x: center.x - ref.x, y: center.y - ref.y };
	        space.data.track = true;
	        upsertKeyframe(space, { t: nowS, x: center.x, y: center.y });
	        setStatus('Espacio: seguirá al jugador seleccionado.');
	      } else {
	        space.data.follow_mode = 'manual';
	        space.data.follow_player_uid = '';
	        space.data.follow_offset = null;
	        space.data.track = true;
	        upsertKeyframe(space, { t: nowS, x: center.x, y: center.y });
	        setStatus(`Espacio: keyframe manual @ ${fmtTime(nowS)}`);
	      }
	      pushHistory();
	      updateLayerPanel();
	      renderDrawLayers();
	      try { applyTimedLayers(); fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	    };
	    btnSpaceFollowPlay?.addEventListener('click', () => assignSpaceFollowMode('play'));
	    btnSpaceFollowPlayer?.addEventListener('click', () => assignSpaceFollowMode('player'));
	    btnSpaceFollowManual?.addEventListener('click', () => assignSpaceFollowMode('manual'));

	    const selectedFollowResources = () => (
	      selectedObjectsForSpace().filter((obj) => {
	        const kind = safeText(obj?.data?.kind, '');
	        return obj && kind !== 'player_marker' && kind !== 'tactical_link';
	      })
	    );

	    const selectedFollowMarker = () => (
	      selectedObjectsForSpace().find((obj) => safeText(obj?.data?.kind, '') === 'player_marker') || null
	    );

	    const assignLayerFollowMode = (mode) => {
	      const resources = selectedFollowResources();
	      if (!resources.length) {
	        setStatus('Selecciona un recurso visual para aplicar seguimiento.', true);
	        return;
	      }
	      const nowS = Number(video.currentTime) || 0;
	      const marker = mode === 'player' ? selectedFollowMarker() : null;
	      if (mode === 'player' && !marker) {
	        setStatus('Selecciona a la vez el recurso y un marcador Jugador.', true);
	        return;
	      }
	      const ref = (() => {
	        if (mode === 'play') return playCentroidAt(nowS);
	        if (mode === 'player') return markerPointAt(marker, nowS);
	        return null;
	      })();
	      if ((mode === 'play' || mode === 'player') && !ref) {
	        setStatus(mode === 'play' ? 'No hay marcadores Jugador visibles para seguir la jugada.' : 'No se pudo leer la posición del jugador.', true);
	        return;
	      }
	      let changed = 0;
	      resources.forEach((obj) => {
	        ensureLayerData(obj);
	        const center = objectCenterPoint(obj);
	        if (!center) return;
	        obj.data.track = true;
	        if (mode === 'play') {
	          obj.data.follow_mode = 'play';
	          obj.data.follow_player_uid = '';
	          obj.data.follow_offset = { x: center.x - ref.x, y: center.y - ref.y };
	        } else if (mode === 'player') {
	          ensureLayerData(marker);
	          obj.data.follow_mode = 'player';
	          obj.data.follow_player_uid = safeText(marker.data.uid, '');
	          obj.data.follow_offset = { x: center.x - ref.x, y: center.y - ref.y };
	        } else {
	          obj.data.follow_mode = 'manual';
	          obj.data.follow_player_uid = '';
	          obj.data.follow_offset = null;
	        }
	        upsertKeyframe(obj, { t: nowS, x: center.x, y: center.y });
	        changed += 1;
	      });
	      if (!changed) {
	        setStatus('No se pudo leer la posición del recurso.', true);
	        return;
	      }
	      pushHistory();
	      updateLayerPanel();
	      renderDrawLayers();
	      try { applyTimedLayers(); fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      if (mode === 'player') setStatus(`${changed} recurso(s): seguirán al jugador seleccionado.`);
	      else if (mode === 'play') setStatus(`${changed} recurso(s): seguirán la jugada.`);
	      else setStatus(`${changed} recurso(s): keyframe @ ${fmtTime(nowS)}.`);
	    };
	    btnLayerFollowPlayer?.addEventListener('click', () => assignLayerFollowMode('player'));
	    btnLayerFollowPlay?.addEventListener('click', () => assignLayerFollowMode('play'));
	    btnLayerFollowManual?.addEventListener('click', () => assignLayerFollowMode('manual'));

      const pushPlayerRecent = (number, name) => {
        const n = safeText(number, '').trim();
        const nm = safeText(name, '').trim().toUpperCase();
        if (!n || !nm) return;
        const items = loadPlayerRecents();
        const next = [{ number: n, name: nm }, ...items.filter((x) => !(safeText(x?.number, '').trim() === n && safeText(x?.name, '').trim().toUpperCase() === nm))].slice(0, 12);
        savePlayerRecents(next);
      };

      playerCancelBtn?.addEventListener('click', closePlayerPop);
	      const segWire = (wrap, key) => {
	        if (!wrap) return;
	        Array.from(wrap.querySelectorAll('button')).forEach((btn) => {
	          btn.addEventListener('click', () => {
	            const value = key === 'team' ? safeText(btn.getAttribute('data-vs-team'), '') : safeText(btn.getAttribute('data-vs-style'), '');
	            if (!value) return;
	            playerPrefs = { ...playerPrefs, [key]: value };
	            savePlayerPrefs(playerPrefs);
	            setSegActive(wrap, key, value);
	            // UX: Local/Rival actúa como preset de color (para que el usuario vea el cambio).
	            if (key === 'team' && colorInput) {
	              const preset = teamColor(value);
	              if (preset) colorInput.value = preset;
	            }
	          });
	        });
	      };
      segWire(playerTeamSeg, 'team');
      segWire(playerStyleSeg, 'style');

      playerOkBtn?.addEventListener('click', () => {
        if (!playerPopCanvasPos) return;
        const number = safeText(playerNumberInput?.value, '').trim() || '?';
        const name = safeText(playerNameInput?.value, '').trim();
        const created = createPlayerMarkerAt(playerPopCanvasPos, number, name, playerPrefs);
        if (!created) { setStatus('No se pudo crear marcador.', true); return; }
        pushPlayerRecent(created.number, created.name);
        closePlayerPop();
        setStatus(`Jugador: ${created.number}${created.name ? ` ${created.name}` : ''}`);
      });
      const handlePlayerKey = (ev) => {
        const key = safeText(ev?.key, '');
        if (key === 'Escape') { ev.preventDefault(); closePlayerPop(); return; }
        if (key === 'Enter') { ev.preventDefault(); playerOkBtn?.click?.(); }
      };
      playerNumberInput?.addEventListener('keydown', handlePlayerKey);
      playerNameInput?.addEventListener('keydown', handlePlayerKey);

	    const clearTemplates = () => {
	      const toRemove = [];
	      for (const obj of fabricCanvas.getObjects()) {
	        const kind = safeText(obj?.data?.kind, '');
	        if (kind === 'template') toRemove.push(obj);
      }
      for (const obj of toRemove) {
        try { fabricCanvas.remove(obj); } catch (e) { /* ignore */ }
      }
      if (toRemove.length) {
        pushHistory();
        updateLayerPanel();
        renderDrawLayers();
        setStatus('Plantillas eliminadas.');
	      }
	    };

	    // Portapapeles simple (copiar/pegar de objetos Fabric)
	    let clipboardObj = null;
	    const copyActiveObject = () => {
	      const obj = activeObject();
	      if (!obj) { setStatus('Nada que copiar.', true); return; }
	      try {
	        obj.clone((cloned) => {
	          clipboardObj = cloned || null;
	          setStatus(clipboardObj ? 'Copiado.' : 'No se pudo copiar.', !clipboardObj);
	        });
	      } catch (e) {
	        setStatus('No se pudo copiar.', true);
	      }
	    };
	    const pasteClipboardObject = () => {
	      if (!clipboardObj) { setStatus('Portapapeles vacío.', true); return; }
	      try {
	        clipboardObj.clone((cloned) => {
	          if (!cloned) { setStatus('No se pudo pegar.', true); return; }
	          try { ensureLayerData(cloned); } catch (e) { /* ignore */ }
	          try { cloned.data = { ...(cloned.data || {}), uid: newUid() }; } catch (e) { /* ignore */ }
	          try {
	            cloned.left = (Number(cloned.left) || 0) + 18;
	            cloned.top = (Number(cloned.top) || 0) + 12;
	          } catch (e) { /* ignore */ }
	          try { fabricCanvas.add(cloned); } catch (e) { /* ignore */ }
	          pushHistory();
	          try { fabricCanvas.setActiveObject(cloned); } catch (e) { /* ignore */ }
	          selectedFxId = 0;
	          updateLayerPanel();
	          renderDrawLayers();
	          renderFxList();
	          setStatus('Pegado.');
	        });
	      } catch (e) {
	        setStatus('No se pudo pegar.', true);
	      }
	    };

	    let nudgeTimer = 0;
	    const nudgeActiveObject = (dx, dy) => {
	      const obj = activeObject();
	      if (!obj) return false;
	      try { ensureLayerData(obj); } catch (e) { /* ignore */ }
	      if (obj?.data?.locked) { setStatus('Capa bloqueada.', true); return false; }
	      try {
	        obj.left = (Number(obj.left) || 0) + dx;
	        obj.top = (Number(obj.top) || 0) + dy;
	        obj.setCoords?.();
	        fabricCanvas.requestRenderAll?.();
	        updateLayerPanel();
	        renderDrawLayers();
	      } catch (e) { /* ignore */ }
	      if (nudgeTimer) window.clearTimeout(nudgeTimer);
	      nudgeTimer = window.setTimeout(() => {
	        nudgeTimer = 0;
	        pushHistory();
	      }, 240);
	      return true;
	    };

	    // Snap a rejilla (mientras mueves objetos)
	    const gridSize = () => clamp(Math.round(Number(gridSizeInput?.value || 10) || 10), 2, 80);
	    const snapEnabled = () => Boolean(snapGridToggle?.checked);
	    const snapToGrid = (v, step) => Math.round(v / step) * step;
	    try {
	      fabricCanvas.on('object:moving', (opt) => {
	        if (!snapEnabled()) return;
	        const t = opt?.target;
	        if (!t) return;
	        try { ensureLayerData(t); } catch (e) { /* ignore */ }
	        if (t?.data?.locked) return;
	        const step = gridSize();
	        const left0 = Number(t.left) || 0;
	        const top0 = Number(t.top) || 0;
	        const left = snapToGrid(left0, step);
	        const top = snapToGrid(top0, step);
	        if (left !== left0 || top !== top0) {
	          t.set({ left, top });
	          t.setCoords?.();
	        }
	      });
	    } catch (e) { /* ignore */ }

	    const selectedObjects = () => {
	      const obj = activeObject();
	      if (!obj) return [];
	      if (obj.type === 'activeSelection' && Array.isArray(obj._objects)) return obj._objects.slice(0);
	      return [obj];
	    };
	    const selectionBounds = () => {
	      const obj = activeObject();
	      if (!obj) return null;
	      try { return obj.getBoundingRect(true, true); } catch (e) { /* ignore */ }
	      return null;
	    };
	    const alignSelection = (mode) => {
	      const items = selectedObjects();
	      if (!items.length) { setStatus('No hay selección.', true); return; }
	      const b = selectionBounds();
	      if (!b) return;
	      const bx = Number(b.left) || 0;
	      const by = Number(b.top) || 0;
	      const bw = Number(b.width) || 0;
	      const bh = Number(b.height) || 0;
	      if (!bw || !bh) return;
	      for (const it of items) {
	        try { ensureLayerData(it); } catch (e) { /* ignore */ }
	        if (it?.data?.locked) continue;
	        try {
	          const ib = it.getBoundingRect(true, true);
	          if (!ib) continue;
	          const iw = Number(ib.width) || 0;
	          const ih = Number(ib.height) || 0;
	          if (!iw || !ih) continue;
	          const dx = Number(it.left) || 0;
	          const dy = Number(it.top) || 0;
	          let nx = dx;
	          let ny = dy;
	          if (mode === 'left') nx = dx + (bx - (Number(ib.left) || 0));
	          if (mode === 'right') nx = dx + ((bx + bw) - ((Number(ib.left) || 0) + iw));
	          if (mode === 'hcenter') nx = dx + ((bx + bw / 2) - ((Number(ib.left) || 0) + iw / 2));
	          if (mode === 'top') ny = dy + (by - (Number(ib.top) || 0));
	          if (mode === 'bottom') ny = dy + ((by + bh) - ((Number(ib.top) || 0) + ih));
	          if (mode === 'vcenter') ny = dy + ((by + bh / 2) - ((Number(ib.top) || 0) + ih / 2));
	          it.set({ left: nx, top: ny });
	          it.setCoords?.();
	        } catch (e) { /* ignore */ }
	      }
	      pushHistory();
	      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      renderDrawLayers();
	      setStatus('Alineado.');
	    };
	    const distributeSelection = (axis) => {
	      const items = selectedObjects().filter((it) => it);
	      if (items.length < 3) { setStatus('Selecciona 3+ objetos.', true); return; }
	      const b = selectionBounds();
	      if (!b) return;
	      const bx = Number(b.left) || 0;
	      const by = Number(b.top) || 0;
	      const bw = Number(b.width) || 0;
	      const bh = Number(b.height) || 0;
	      const keyed = items.map((it) => {
	        try {
	          const ib = it.getBoundingRect(true, true);
	          return { it, ib, key: axis === 'h' ? (Number(ib.left) || 0) : (Number(ib.top) || 0) };
	        } catch (e) {
	          return { it, ib: null, key: 0 };
	        }
	      }).filter((x) => x.ib);
	      keyed.sort((a, b2) => a.key - b2.key);
	      if (keyed.length < 3) return;
	      // Mantén extremos; distribuye los intermedios por centro.
	      const first = keyed[0];
	      const last = keyed[keyed.length - 1];
	      const span = axis === 'h'
	        ? ((Number(last.ib.left) || 0) - (Number(first.ib.left) || 0))
	        : ((Number(last.ib.top) || 0) - (Number(first.ib.top) || 0));
	      if (!span) return;
	      const step = span / (keyed.length - 1);
	      for (let i = 1; i < keyed.length - 1; i += 1) {
	        const { it, ib } = keyed[i];
	        try { ensureLayerData(it); } catch (e) { /* ignore */ }
	        if (it?.data?.locked) continue;
	        if (axis === 'h') {
	          const targetLeft = (Number(first.ib.left) || 0) + step * i;
	          const delta = targetLeft - (Number(ib.left) || 0);
	          it.left = (Number(it.left) || 0) + delta;
	        } else {
	          const targetTop = (Number(first.ib.top) || 0) + step * i;
	          const delta = targetTop - (Number(ib.top) || 0);
	          it.top = (Number(it.top) || 0) + delta;
	        }
	        it.setCoords?.();
	      }
	      pushHistory();
	      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      renderDrawLayers();
	      setStatus('Distribuido.');
	    };

	    alignLeftBtn?.addEventListener('click', () => alignSelection('left'));
	    alignHCenterBtn?.addEventListener('click', () => alignSelection('hcenter'));
	    alignRightBtn?.addEventListener('click', () => alignSelection('right'));
	    alignTopBtn?.addEventListener('click', () => alignSelection('top'));
	    alignVCenterBtn?.addEventListener('click', () => alignSelection('vcenter'));
	    alignBottomBtn?.addEventListener('click', () => alignSelection('bottom'));
	    distHBtn?.addEventListener('click', () => distributeSelection('h'));
	    distVBtn?.addEventListener('click', () => distributeSelection('v'));

	    const applyCurrentStyleToSelection = () => {
	      const items = selectedObjects();
	      if (!items.length) { setStatus('No hay selección.', true); return; }
	      const color = strokeColor();
	      const sw = clamp(Number(strokeWidth()) || 6, 1, 22);
	      const style = getLineStyle();
	      let applied = 0;
	      const applyToObj = (obj) => {
	        if (!obj) return;
	        try { ensureLayerData(obj); } catch (e) { /* ignore */ }
	        if (obj?.data?.locked) return;
	        const kind = safeText(obj?.data?.kind, '');
	        // Objetos simples con stroke
	        if (obj.type === 'line' || obj.type === 'path' || obj.type === 'polyline') {
	          try {
	            obj.set({ stroke: color, strokeWidth: sw });
	            applyStrokeStyle(obj, style, sw);
	            obj.dirty = true;
	            applied += 1;
	          } catch (e) { /* ignore */ }
	          return;
	        }
	        // Formas
	        if (obj.type === 'rect' || obj.type === 'ellipse' || kind === 'shape_rect' || kind === 'shape_ellipse') {
	          try {
	            obj.set({ stroke: color, strokeWidth: sw, fill: colorToRgba(color, 0.16, obj.fill) });
	            applyStrokeStyle(obj, style, sw);
	            obj.dirty = true;
	            applied += 1;
	          } catch (e) { /* ignore */ }
	          return;
	        }
	        // Grupos (flechas/trayectorias/callouts/markers)
	        if (obj.type === 'group' && Array.isArray(obj._objects)) {
	          obj._objects.forEach((child) => {
	            if (!child) return;
	            if (child.type === 'line' || child.type === 'path' || child.type === 'polyline') {
	              try {
	                child.set({ stroke: color, strokeWidth: sw });
	                applyStrokeStyle(child, style, sw);
	                child.dirty = true;
	              } catch (e) { /* ignore */ }
	            } else if (child.type === 'polygon') {
	              // Arrow heads suelen ser polygons con fill
	              try { child.set({ fill: color }); child.dirty = true; } catch (e) { /* ignore */ }
	            } else if (child.type === 'circle' || child.type === 'ellipse' || child.type === 'rect') {
	              try {
	                if (child.stroke != null) child.set({ stroke: color, strokeWidth: clamp(sw, 1, 12) });
	                if (kind === 'base' && child.fill != null) child.set({ fill: colorToRgba(color, 0.22, child.fill) });
	                child.dirty = true;
	              } catch (e) { /* ignore */ }
	            }
	          });
	          try {
	            obj.data = { ...(obj.data || {}), line_style: style };
	            obj.dirty = true;
	            applied += 1;
	          } catch (e) { /* ignore */ }
	        }
	      };
	      items.forEach(applyToObj);
	      if (applied) {
	        pushHistory();
	        try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        renderDrawLayers();
	        updateLayerPanel();
	        setStatus('Estilo aplicado.');
	      } else {
	        setStatus('No se pudo aplicar estilo a la selección.', true);
	      }
	    };

	    styleApplyBtn?.addEventListener('click', () => applyCurrentStyleToSelection());
	    // Presets rápidos: cambian el color global
	    try {
	      Array.from(document.querySelectorAll('[data-vs-style-preset]')).forEach((btn) => {
	        btn.addEventListener('click', () => {
	          const c = safeText(btn.getAttribute('data-vs-style-preset'), '');
	          if (!c) return;
	          if (colorInput) colorInput.value = c;
	          try { fabricCanvas.freeDrawingBrush.color = strokeColor(); } catch (e) { /* ignore */ }
	          setStatus(`Preset: ${c}`);
	        });
	      });
	    } catch (e) { /* ignore */ }

	    // ---- Calibración 2D (campo) + medición ----
	    const pitchKey = () => `vs_pitch_calib_v1:${videoId || 0}`;
	    let pitchCalib = null; // { pts: [{x,y}*4], H: [8], w:105, h:68 }
	    let calibMode = false;
	    let calibPts = [];
	    const setCalibStatus = (text, isError = false) => {
	      if (!calibStatusEl) return;
	      calibStatusEl.textContent = safeText(text, '—');
	      calibStatusEl.style.color = isError ? '#fecaca' : 'rgba(226,232,240,0.72)';
	    };
	    const savePitchCalib = () => {
	      try {
	        if (!pitchCalib) { window.localStorage?.removeItem?.(pitchKey()); return; }
	        window.localStorage?.setItem?.(pitchKey(), JSON.stringify(pitchCalib));
	      } catch (e) { /* ignore */ }
	    };
	    const loadPitchCalib = () => {
	      try {
	        const raw = window.localStorage?.getItem?.(pitchKey()) || '';
	        if (!raw) return null;
	        const obj = JSON.parse(raw);
	        if (!obj || !Array.isArray(obj.pts) || obj.pts.length !== 4 || !Array.isArray(obj.H) || obj.H.length !== 8) return null;
	        return obj;
	      } catch (e) {
	        return null;
	      }
	    };
	    pitchCalib = loadPitchCalib();
	    if (pitchCalib) setCalibStatus(`OK · Campo ${pitchCalib.w || 105}×${pitchCalib.h || 68}m`);

	    const solveLinearSystem = (A, b) => {
	      // A: NxN, b: N
	      const n = A.length;
	      const M = A.map((row, i) => row.slice(0).concat([b[i]]));
	      for (let col = 0; col < n; col += 1) {
	        // pivot
	        let pivot = col;
	        let best = Math.abs(M[col][col] || 0);
	        for (let r = col + 1; r < n; r += 1) {
	          const v = Math.abs(M[r][col] || 0);
	          if (v > best) { best = v; pivot = r; }
	        }
	        if (best < 1e-9) return null;
	        if (pivot !== col) {
	          const tmp = M[col]; M[col] = M[pivot]; M[pivot] = tmp;
	        }
	        const div = M[col][col];
	        for (let c = col; c <= n; c += 1) M[col][c] /= div;
	        for (let r = 0; r < n; r += 1) {
	          if (r === col) continue;
	          const f = M[r][col];
	          if (!f) continue;
	          for (let c = col; c <= n; c += 1) M[r][c] -= f * M[col][c];
	        }
	      }
	      return M.map((row) => row[n]);
	    };

	    const computeHomography8 = (srcPts, dstPts) => {
	      // src: [{x,y}*4], dst: [{x,y}*4] ; returns [h11,h12,h13,h21,h22,h23,h31,h32]
	      const A = [];
	      const b = [];
	      for (let i = 0; i < 4; i += 1) {
	        const x = Number(srcPts[i].x) || 0;
	        const y = Number(srcPts[i].y) || 0;
	        const X = Number(dstPts[i].x) || 0;
	        const Y = Number(dstPts[i].y) || 0;
	        A.push([x, y, 1, 0, 0, 0, -X * x, -X * y]); b.push(X);
	        A.push([0, 0, 0, x, y, 1, -Y * x, -Y * y]); b.push(Y);
	      }
	      return solveLinearSystem(A, b);
	    };
	    const mapImageToField = (pt) => {
	      if (!pitchCalib || !Array.isArray(pitchCalib.H) || pitchCalib.H.length !== 8) return null;
	      const h = pitchCalib.H;
	      const x = Number(pt?.x) || 0;
	      const y = Number(pt?.y) || 0;
	      const den = (h[6] * x) + (h[7] * y) + 1;
	      if (!den) return null;
	      const X = ((h[0] * x) + (h[1] * y) + h[2]) / den;
	      const Y = ((h[3] * x) + (h[4] * y) + h[5]) / den;
	      if (!Number.isFinite(X) || !Number.isFinite(Y)) return null;
	      return { x: X, y: Y };
	    };
	    const distMeters = (a, b2) => {
	      const pa = mapImageToField(a);
	      const pb = mapImageToField(b2);
	      if (!pa || !pb) return null;
	      return Math.hypot(pb.x - pa.x, pb.y - pa.y);
	    };

	    const clearCalibrationMarks = () => {
	      const toRemove = [];
	      try {
	        for (const obj of (fabricCanvas.getObjects?.() || [])) {
	          if (safeText(obj?.data?.kind, '') === 'calib_point') toRemove.push(obj);
	        }
	      } catch (e) { /* ignore */ }
	      toRemove.forEach((o) => { try { fabricCanvas.remove(o); } catch (e) { /* ignore */ } });
	      if (toRemove.length) { try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ } }
	    };

	    const startCalibration = () => {
	      calibMode = true;
	      calibPts = [];
	      clearCalibrationMarks();
	      setTool('select');
	      setStatus('Calibración: click 4 puntos (Esquina sup-izq, sup-der, inf-der, inf-izq).');
	      setCalibStatus('Calibración: 0/4');
	    };
	    const resetCalibration = () => {
	      calibMode = false;
	      calibPts = [];
	      pitchCalib = null;
	      savePitchCalib();
	      clearCalibrationMarks();
	      setCalibStatus('Sin calibración.');
	      setStatus('Calibración reseteada.');
	    };
	    calibStartBtn?.addEventListener('click', () => startCalibration());
	    calibResetBtn?.addEventListener('click', () => resetCalibration());

	    const updateTemplateParamsUi = () => {
	      if (!templateParamsWrap) return;
	      const v = safeText(templateSelect?.value, '');
	      templateParamsWrap.style.display = (v === 'lanes_manual') ? 'grid' : 'none';
	    };
	    updateTemplateParamsUi();
	    templateSelect?.addEventListener('change', updateTemplateParamsUi);

	    const buildManualLanesTemplate = ({ w, h, laneCount, strokeW }) => {
	      // "Manual" debe significar editable. Devuelve objetos sueltos para poder ajustar
	      // cada línea a mano (separación según jugadores/cámara).
	      const objs = [];
	      const count = clamp(Math.round(Number(laneCount) || 5), 2, 12);
	      const sw = clamp(Math.round(Number(strokeW) || 2), 1, 16);
	      const templateUid = newUid();

	      const mkData = (extra) => seedLayerDataNow({
	        kind: 'template',
	        template: 'lanes_manual',
	        template_uid: templateUid,
	        lane_count: count,
	        stroke_w: sw,
	        ...(extra || {}),
	      });

	      const laneW = w / count;
	      for (let i = 0; i < count; i += 1) {
	        const fill = (i % 2 === 0) ? 'rgba(255,255,255,0.035)' : 'rgba(255,255,255,0.018)';
	        const r = new fabric.Rect({
	          left: i * laneW,
	          top: 0,
	          width: laneW,
	          height: h,
	          fill,
	          selectable: false,
	          evented: false,
	          objectCaching: false,
	        });
	        r.data = mkData({ lane_role: 'shade', lane_i: i, hidden_list: true });
	        objs.push(r);
	      }

	      const dash = 8 + sw * 2;
	      const mkLine = (points, extra) => {
	        const line = new fabric.Line(points, {
	          stroke: 'rgba(255,255,255,0.42)',
	          strokeWidth: sw,
	          strokeDashArray: [dash, dash],
	          strokeLineCap: 'round',
	          strokeUniform: true,
	          selectable: true,
	          evented: true,
	          perPixelTargetFind: true,
	          padding: 6,
	          cornerStyle: 'circle',
	          cornerColor: 'rgba(250,204,21,0.95)',
	          transparentCorners: false,
	          cornerSize: 14,
	          objectCaching: false,
	          lockMovementY: true,
	        });
	        line.data = mkData({ lane_role: 'divider', ...(extra || {}) });
	        return line;
	      };

	      for (let i = 1; i <= count - 1; i += 1) {
	        const x = (w * i) / count;
	        objs.push(mkLine([x, 0, x, h], { lane_divider_i: i }));
	      }

	      const border = new fabric.Rect({
	        left: 0,
	        top: 0,
	        width: w,
	        height: h,
	        fill: 'rgba(0,0,0,0)',
	        stroke: 'rgba(255,255,255,0.55)',
	        strokeWidth: sw,
	        strokeUniform: true,
	        selectable: false,
	        evented: false,
	        objectCaching: false,
	      });
	      border.data = mkData({ lane_role: 'border', hidden_list: true });
	      objs.push(border);

	      return { objs, meta: { templateUid, count, sw } };
	    };

	    const addTacticalPreset = (presetKey) => {
	      const key = safeText(presetKey, '');
	      const w = Number(fabricCanvas.getWidth?.()) || 0;
	      const h = Number(fabricCanvas.getHeight?.()) || 0;
	      if (!key || !w || !h) { setStatus('Preset táctico no disponible.', true); return false; }
	      const px = (x) => clamp(Number(x) || 0, 0.02, 0.98) * w;
	      const py = (y) => clamp(Number(y) || 0, 0.02, 0.98) * h;
	      const sw = clamp(Math.round(strokeWidth() || 6), 3, 14);
	      const cyan = '#22d3ee';
	      const yellow = '#facc15';
	      const red = '#fb7185';
	      const white = '#ffffff';
	      const green = '#34d399';
	      const blue = '#60a5fa';
	      const makeLabel = (text, x, y, color = white, scale = 1) => {
	        const label = new fabric.Textbox(safeText(text, ''), {
	          left: px(x),
	          top: py(y),
	          width: Math.min(w * 0.34, 260),
	          fontSize: clamp(Math.round(21 * scale), 14, 34),
	          fontFamily: 'Arial',
	          fontWeight: 900,
	          fill: color,
	          textAlign: 'center',
	          originX: 'center',
	          originY: 'center',
	          stroke: 'rgba(2,6,23,0.9)',
	          strokeWidth: 3,
	          paintFirst: 'stroke',
	          selectable: true,
	          evented: true,
	        });
	        label.data = seedLayerDataNow({ kind: 'text_caption', preset: key, text: safeText(text, '') });
	        return label;
	      };
	      const makeZone = (x, y, rw, rh, color = cyan, label = '') => {
	        const rect = new fabric.Rect({
	          left: px(x),
	          top: py(y),
	          width: clamp(Number(rw) || 0.16, 0.04, 0.9) * w,
	          height: clamp(Number(rh) || 0.16, 0.04, 0.9) * h,
	          originX: 'center',
	          originY: 'center',
	          fill: colorToRgba(color, 0.13, 'rgba(34,211,238,0.13)'),
	          stroke: colorToRgba(color, 0.72, 'rgba(34,211,238,0.72)'),
	          strokeWidth: Math.max(2, Math.round(sw * 0.45)),
	          strokeDashArray: [10, 8],
	          rx: 12,
	          ry: 12,
	          selectable: true,
	          evented: true,
	          strokeUniform: true,
	          objectCaching: false,
	        });
	        rect.data = seedLayerDataNow({ kind: 'space_zone', preset: key, label: safeText(label, '') });
	        return rect;
	      };
	      const makeLine = (a, b, color = white, opts = {}) => {
	        const line = new fabric.Line([px(a[0]), py(a[1]), px(b[0]), py(b[1])], {
	          stroke: colorToRgba(color, opts.alpha ?? 0.8, color),
	          strokeWidth: opts.strokeWidth || Math.max(2, Math.round(sw * 0.45)),
	          strokeDashArray: opts.dash || null,
	          strokeLineCap: 'round',
	          selectable: true,
	          evented: true,
	          strokeUniform: true,
	          objectCaching: false,
	        });
	        line.data = seedLayerDataNow({ kind: 'line', preset: key, line_style: opts.dash ? 'dash' : 'solid' });
	        return line;
	      };
	      const makeArrow = (a, b, color = yellow, opts = {}) => {
	        const x1 = px(a[0]); const y1 = py(a[1]);
	        const x2 = px(b[0]); const y2 = py(b[1]);
	        const line = new fabric.Line([x1, y1, x2, y2], {
	          stroke: color,
	          strokeWidth: opts.strokeWidth || sw,
	          strokeLineCap: 'round',
	          selectable: false,
	          evented: false,
	          objectCaching: false,
	          strokeUniform: true,
	          shadow: 'rgba(0,0,0,0.25) 0 2px 6px',
	        });
	        applyStrokeStyle(line, opts.style || 'solid', sw);
	        const ang = Math.atan2(y2 - y1, x2 - x1);
	        const headLen = clamp(16 + sw, 16, 34);
	        const head = new fabric.Polygon([
	          { x: x2, y: y2 },
	          { x: x2 - headLen * Math.cos(ang - Math.PI / 7), y: y2 - headLen * Math.sin(ang - Math.PI / 7) },
	          { x: x2 - headLen * Math.cos(ang + Math.PI / 7), y: y2 - headLen * Math.sin(ang + Math.PI / 7) },
	        ], { fill: color, selectable: false, evented: false, shadow: 'rgba(0,0,0,0.25) 0 2px 6px' });
	        const group = new fabric.Group([line, head], { selectable: true, evented: true });
	        group.data = seedLayerDataNow({ kind: opts.kind || 'arrow', preset: key, anim: opts.style ? 'none' : 'draw', anim_ms: 700, line_style: opts.style || 'solid' });
	        return group;
	      };
	      const makePlayer = (x, y, color = white, label = '') => {
	        const r = clamp(Math.min(w, h) * 0.025, 12, 24);
	        const circle = new fabric.Circle({
	          left: px(x),
	          top: py(y),
	          radius: r,
	          originX: 'center',
	          originY: 'center',
	          fill: colorToRgba(color, 0.9, color),
	          stroke: 'rgba(2,6,23,0.85)',
	          strokeWidth: 3,
	          selectable: false,
	          evented: false,
	        });
	        const text = new fabric.Text(safeText(label, ''), {
	          left: px(x),
	          top: py(y),
	          originX: 'center',
	          originY: 'center',
	          fontSize: clamp(Math.round(r * 0.95), 10, 20),
	          fontWeight: 900,
	          fill: '#0f172a',
	          selectable: false,
	          evented: false,
	        });
	        const group = new fabric.Group([circle, text], { selectable: true, evented: true });
	        group.data = seedLayerDataNow({ kind: 'player_marker', preset: key, number: safeText(label, '') });
	        return group;
	      };
	      const add = [];
	      if (key === '2v1') {
	        add.push(makeZone(0.66, 0.54, 0.25, 0.22, yellow, 'superioridad'));
	        add.push(makePlayer(0.55, 0.62, red, 'A'));
	        add.push(makePlayer(0.72, 0.62, red, 'B'));
	        add.push(makePlayer(0.64, 0.49, blue, 'D'));
	        add.push(makeArrow([0.55, 0.61], [0.69, 0.57], yellow));
	        add.push(makeArrow([0.72, 0.62], [0.81, 0.50], white));
	        add.push(makeLabel('2v1', 0.66, 0.40, white, 1.15));
	      } else if (key === 'third_man') {
	        add.push(makePlayer(0.38, 0.60, red, '1'));
	        add.push(makePlayer(0.52, 0.48, red, '2'));
	        add.push(makePlayer(0.68, 0.58, red, '3'));
	        add.push(makeArrow([0.38, 0.60], [0.52, 0.48], yellow));
	        add.push(makeArrow([0.52, 0.48], [0.68, 0.58], cyan));
	        add.push(makeZone(0.68, 0.58, 0.18, 0.14, green, 'tercer hombre'));
	        add.push(makeLabel('3er hombre', 0.55, 0.36, white, 1));
	      } else if (key === 'defensive_line') {
	        add.push(makeLine([0.18, 0.56], [0.84, 0.56], cyan, { dash: [12, 8], strokeWidth: Math.max(3, sw * 0.75) }));
	        [0.25, 0.40, 0.55, 0.70].forEach((x, i) => add.push(makePlayer(x, 0.56, blue, String(i + 2))));
	        add.push(makeArrow([0.55, 0.48], [0.55, 0.36], red, { style: 'dash', kind: 'movement_line' }));
	        add.push(makeLabel('Línea defensiva', 0.50, 0.43, white, 0.9));
	      } else if (key === 'block_low' || key === 'block_mid' || key === 'block_high') {
	        const y = key === 'block_low' ? 0.68 : (key === 'block_mid' ? 0.52 : 0.36);
	        const label = key === 'block_low' ? 'Bloque bajo' : (key === 'block_mid' ? 'Bloque medio' : 'Bloque alto');
	        add.push(makeZone(0.50, y, 0.62, 0.28, blue, label));
	        add.push(makeLine([0.20, y - 0.08], [0.80, y - 0.08], white, { dash: [10, 8] }));
	        add.push(makeLine([0.24, y + 0.06], [0.76, y + 0.06], white, { dash: [10, 8] }));
	        [0.28, 0.42, 0.56, 0.70].forEach((x, i) => add.push(makePlayer(x, y - 0.08, blue, String(i + 1))));
	        [0.34, 0.50, 0.66].forEach((x, i) => add.push(makePlayer(x, y + 0.06, blue, String(i + 5))));
	        add.push(makeLabel(label, 0.50, y - 0.20, white, 1));
	      } else if (key === 'free_space') {
	        add.push(makeZone(0.64, 0.44, 0.26, 0.20, green, 'espacio libre'));
	        add.push(makeArrow([0.36, 0.62], [0.58, 0.48], yellow, { kind: 'movement_line' }));
	        add.push(makeArrow([0.48, 0.54], [0.64, 0.44], cyan, { style: 'dash' }));
	        add.push(makeLabel('Espacio libre', 0.64, 0.32, white, 0.95));
	      } else if (key === 'press_jump') {
	        add.push(makePlayer(0.45, 0.54, blue, '6'));
	        add.push(makePlayer(0.60, 0.48, red, '8'));
	        add.push(makePlayer(0.69, 0.56, red, '9'));
	        add.push(makeArrow([0.45, 0.54], [0.60, 0.48], red, { kind: 'movement_line' }));
	        add.push(makeZone(0.60, 0.48, 0.18, 0.14, red, 'salto'));
	        add.push(makeLabel('Salto presión', 0.56, 0.36, white, 0.95));
	      } else if (key === 'shift') {
	        add.push(makeZone(0.48, 0.52, 0.58, 0.25, blue, 'bloque'));
	        add.push(makeArrow([0.36, 0.50], [0.52, 0.50], cyan, { kind: 'movement_line' }));
	        add.push(makeArrow([0.50, 0.58], [0.66, 0.58], cyan, { kind: 'movement_line' }));
	        add.push(makeLine([0.26, 0.44], [0.72, 0.44], white, { dash: [10, 8] }));
	        add.push(makeLabel('Basculación', 0.52, 0.36, white, 1));
	      }
	      if (!add.length) { setStatus('Preset táctico no soportado.', true); return false; }
	      add.forEach((obj) => {
	        try { fabricCanvas.add(obj); } catch (e) { /* ignore */ }
	      });
	      pushHistory();
	      try {
	        const sel = new fabric.ActiveSelection(add, { canvas: fabricCanvas });
	        fabricCanvas.setActiveObject(sel);
	      } catch (e) {
	        try { fabricCanvas.setActiveObject(add[add.length - 1]); } catch (e2) { /* ignore */ }
	      }
	      selectedFxId = 0;
	      updateLayerPanel();
	      renderFxList();
	      renderDrawLayers();
	      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      setStatus(`Recurso táctico aplicado: ${labelForResourceKey(`tactic:${key}`) || key}.`);
	      return true;
	    };

	    const replaceTemplateInPlace = (oldObj, newObj) => {
	      if (!oldObj || !newObj) return false;
	      const idx = (() => {
	        try { return (fabricCanvas.getObjects?.() || []).indexOf(oldObj); } catch (e) { return -1; }
	      })();
	      // Copia transform
	      try {
	        newObj.set({
	          left: oldObj.left,
	          top: oldObj.top,
	          scaleX: oldObj.scaleX,
	          scaleY: oldObj.scaleY,
	          angle: oldObj.angle,
	          flipX: oldObj.flipX,
	          flipY: oldObj.flipY,
	          originX: oldObj.originX,
	          originY: oldObj.originY,
	          skewX: oldObj.skewX,
	          skewY: oldObj.skewY,
	        });
	      } catch (e) { /* ignore */ }
	      // Preserva timing / flags (sin pisar parámetros nuevos)
	      try {
	        const prev = (oldObj.data && typeof oldObj.data === 'object') ? oldObj.data : {};
	        const carry = {
	          uid: safeText(prev.uid),
	          t_in_s: Number(prev.t_in_s) || 0,
	          t_out_s: Number(prev.t_out_s) || 0,
	          fade_in_ms: Math.max(0, Number(prev.fade_in_ms) || 0),
	          fade_out_ms: Math.max(0, Number(prev.fade_out_ms) || 0),
	          anim: safeText(prev.anim, 'none'),
	          locked: Boolean(prev.locked),
	        };
	        newObj.data = { ...carry, ...(newObj.data || {}), kind: 'template', template: safeText(newObj?.data?.template, 'lanes_manual') };
	      } catch (e) { /* ignore */ }
	      ensureLayerData(newObj);
	      try { fabricCanvas.remove(oldObj); } catch (e) { /* ignore */ }
	      try {
	        if (idx >= 0 && typeof fabricCanvas.insertAt === 'function') fabricCanvas.insertAt(newObj, idx, false);
	        else fabricCanvas.add(newObj);
	      } catch (e) {
	        try { fabricCanvas.add(newObj); } catch (e2) { /* ignore */ }
	      }
	      pushHistory();
	      try { fabricCanvas.setActiveObject(newObj); } catch (e) { /* ignore */ }
	      selectedFxId = 0;
	      updateLayerPanel();
	      renderFxList();
	      renderDrawLayers();
	      return true;
	    };

		    const applyTemplate = () => {
		      const name = safeText(templateSelect?.value, '');
		      if (!name) { setStatus('Elige una plantilla.', true); return; }
	      const w = fabricCanvas.getWidth();
	      const h = fabricCanvas.getHeight();
	      if (!w || !h) return;
	      const objs = [];
	      if (name === 'lanes') {
	        for (let i = 1; i <= 4; i += 1) {
	          const x = (w * i) / 5;
	          objs.push(new fabric.Line([x, 0, x, h], { stroke: 'rgba(255,255,255,0.35)', strokeWidth: 2, selectable: false, evented: false }));
	        }
	        objs.push(new fabric.Rect({ left: 0, top: 0, width: w, height: h, fill: 'rgba(255,255,255,0.02)', selectable: false, evented: false }));
	      } else if (name === 'lanes_manual') {
	        const lanes = clamp(Math.round(Number(templateLanesCountInput?.value || 5) || 5), 2, 12);
	        const strokeW = clamp(Math.round(Number(templateLanesStrokeInput?.value || 2) || 2), 1, 16);
	        const existing = (() => {
	          try {
	            return (fabricCanvas.getObjects?.() || []).filter((o) => safeText(o?.data?.kind, '') === 'template' && safeText(o?.data?.template, '') === 'lanes_manual');
	          } catch (e) {
	            return [];
	          }
	        })();
	        const existingCount = existing.length ? (Number(existing[0]?.data?.lane_count) || 0) : 0;
	        const hasLegacyGroup = existing.some((o) => safeText(o?.type, '') === 'group');
	        const canUpdateInPlace = existing.length && !hasLegacyGroup && existingCount === lanes;

	        if (canUpdateInPlace) {
	          // Actualiza grosor/estilo sin destruir la colocación manual.
	          const dash = 8 + strokeW * 2;
	          existing.forEach((obj) => {
	            try {
	              ensureLayerData(obj);
	              if (obj.type === 'line' && safeText(obj?.data?.lane_role, '') === 'divider') {
	                obj.set({ strokeWidth: strokeW, strokeDashArray: [dash, dash], strokeUniform: true });
	              } else if (obj.type === 'rect' && safeText(obj?.data?.lane_role, '') === 'border') {
	                obj.set({ strokeWidth: strokeW, strokeUniform: true });
	              }
	              obj.data.lane_count = lanes;
	              obj.data.stroke_w = strokeW;
	              obj.dirty = true;
	            } catch (e) { /* ignore */ }
	          });
	          pushHistory();
	          try {
	            const divs = existing.filter((o) => o?.type === 'line' && safeText(o?.data?.lane_role, '') === 'divider');
	            const sel = new fabric.ActiveSelection(divs, { canvas: fabricCanvas });
	            fabricCanvas.setActiveObject(sel);
	          } catch (e) { /* ignore */ }
	          selectedFxId = 0;
	          updateLayerPanel();
	          renderFxList();
	          renderDrawLayers();
	          try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	          setStatus(`Carriles manual actualizados: ${lanes} carriles · grosor ${strokeW}px.`);
	          return;
	        }

	        // Reemplaza el set existente (evita "apilar" carriles) si cambia nº de carriles o no existe.
	        try {
	          existing.forEach((o) => { try { fabricCanvas.remove(o); } catch (e) { /* ignore */ } });
	        } catch (e) { /* ignore */ }

	        const built = buildManualLanesTemplate({ w, h, laneCount: lanes, strokeW });
	        const created = Array.isArray(built?.objs) ? built.objs : [];
	        created.forEach((o) => { try { fabricCanvas.add(o); } catch (e) { /* ignore */ } });
	        pushHistory();
	        try {
	          const sel = new fabric.ActiveSelection(created.filter((o) => safeText(o?.data?.lane_role, '') === 'divider'), { canvas: fabricCanvas });
	          fabricCanvas.setActiveObject(sel);
	        } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	        setStatus(`Carriles manual: ${lanes} carriles · grosor ${strokeW}px.\nTip: mueve cada línea (solo X). Selecciona 2+ y usa Distribuir (H) para igualar separaciones.`);
	        return;
	      } else if (name === 'grid') {
	        const cols = 6;
	        const rows = 4;
	        for (let c = 1; c <= cols - 1; c += 1) {
	          const x = (w * c) / cols;
	          objs.push(new fabric.Line([x, 0, x, h], { stroke: 'rgba(255,255,255,0.30)', strokeWidth: 2, selectable: false, evented: false }));
	        }
	        for (let r = 1; r <= rows - 1; r += 1) {
	          const y = (h * r) / rows;
	          objs.push(new fabric.Line([0, y, w, y], { stroke: 'rgba(255,255,255,0.30)', strokeWidth: 2, selectable: false, evented: false }));
	        }
	      } else if (name === 'grid_manual') {
	        const cols = 6;
	        const rows = 4;
	        const mkLine = (points, dataExtra) => {
	          const line = new fabric.Line(points, {
	            stroke: 'rgba(255,255,255,0.42)',
	            strokeWidth: 2,
	            selectable: true,
	            evented: true,
	            strokeUniform: true,
	            perPixelTargetFind: true,
	            padding: 0,
	            cornerStyle: 'circle',
	            cornerColor: 'rgba(250,204,21,0.95)',
	            transparentCorners: false,
	            cornerSize: 14,
	          });
	          line.data = seedLayerDataNow({ kind: 'template', template: name, ...dataExtra });
	          return line;
	        };
	        for (let c = 1; c <= cols - 1; c += 1) {
	          const x = (w * c) / cols;
	          objs.push(mkLine([x, 0, x, h], { grid_axis: 'v', grid_i: c }));
	        }
	        for (let r = 1; r <= rows - 1; r += 1) {
	          const y = (h * r) / rows;
	          objs.push(mkLine([0, y, w, y], { grid_axis: 'h', grid_i: r }));
	        }
	        objs.forEach((o) => fabricCanvas.add(o));
	        pushHistory();
	        try {
	          const sel = new fabric.ActiveSelection(objs, { canvas: fabricCanvas });
	          fabricCanvas.setActiveObject(sel);
	        } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	        setStatus('Cuadrícula manual: usa Select y mueve/rota líneas (puedes seleccionar varias).');
	        return;
	      } else if (name === 'central_box') {
	        const bw = w * 0.52;
	        const bh = h * 0.52;
	        objs.push(new fabric.Rect({
	          left: (w - bw) / 2,
          top: (h - bh) / 2,
          width: bw,
          height: bh,
          fill: 'rgba(34,211,238,0.08)',
          stroke: 'rgba(34,211,238,0.6)',
          strokeWidth: 2,
          rx: 16,
          ry: 16,
          selectable: false,
          evented: false,
        }));
      } else if (name === 'final_third') {
        const x0 = w * 0.67;
        objs.push(new fabric.Rect({
          left: x0,
          top: 0,
          width: w - x0,
          height: h,
          fill: 'rgba(250,204,21,0.10)',
          stroke: 'rgba(250,204,21,0.55)',
          strokeWidth: 2,
          selectable: false,
          evented: false,
        }));
      } else {
        setStatus('Plantilla no soportada.', true);
        return;
      }
      const layer = objs.length === 1 ? objs[0] : new fabric.Group(objs, { selectable: true });
      layer.set?.({ selectable: true, evented: true });
      layer.data = seedLayerDataNow({ kind: 'template', template: name });
      fabricCanvas.add(layer);
      pushHistory();
      try { fabricCanvas.setActiveObject(layer); } catch (e) { /* ignore */ }
      selectedFxId = 0;
      updateLayerPanel();
      renderFxList();
      renderDrawLayers();
      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
      setStatus('Plantilla aplicada.');
    };

	    templateApplyBtn?.addEventListener('click', applyTemplate);
	    templateClearBtn?.addEventListener('click', () => {
      const ok = window.confirm('¿Quitar todas las plantillas?');
      if (!ok) return;
      clearTemplates();
    });

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
          ...seedLayerDataNow({ t_in_s: now, fade_in_ms: 150, fade_out_ms: 150 }),
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
          ...seedLayerDataNow({ t_in_s: now, fade_in_ms: 150, fade_out_ms: 150 }),
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
	      const last = history.pop();
	      if (last) redo.push(last);
	      restoreJson(history[history.length - 1]);
	      setStatus('Undo.');
	    });

	    // Recursos rápidos (estilo Táctica): 1 clic para insertar plantillas o activar herramientas.
	    const resourcesRecentsKey = () => `vs_resources_recents_v1:${videoId || 0}`;
	    const readResourceRecents = () => {
	      try {
	        const raw = window.localStorage?.getItem?.(resourcesRecentsKey()) || '';
	        const arr = JSON.parse(raw || '[]');
	        return Array.isArray(arr) ? arr.map((x) => safeText(x, '')).filter(Boolean).slice(0, 12) : [];
	      } catch (e) {
	        return [];
	      }
	    };
	    const writeResourceRecents = (items) => {
	      try { window.localStorage?.setItem?.(resourcesRecentsKey(), JSON.stringify((items || []).slice(0, 12))); } catch (e) { /* ignore */ }
	    };
	    const labelForResourceKey = (key) => {
	      const k = safeText(key, '');
	      if (!k) return '';
	      if (k === 'template:lanes_manual') return 'Carriles manual';
	      if (k === 'template:grid_manual') return 'Cuadrícula manual';
	      if (k === 'template:central_box') return 'Caja central';
	      if (k === 'template:final_third') return 'Último tercio';
	      if (k === 'tactic:2v1') return '2v1';
	      if (k === 'tactic:third_man') return 'Tercer hombre';
	      if (k === 'tactic:defensive_line') return 'Línea defensiva';
	      if (k === 'tactic:block_low') return 'Bloque bajo';
	      if (k === 'tactic:block_mid') return 'Bloque medio';
	      if (k === 'tactic:block_high') return 'Bloque alto';
	      if (k === 'tactic:free_space') return 'Zona libre';
	      if (k === 'tactic:press_jump') return 'Presión/salto';
	      if (k === 'tactic:shift') return 'Basculación';
	      if (k === 'tv:dashed_pass') return 'Pase discontinuo';
	      if (k === 'tv:white_run') return 'Carrera blanca';
	      if (k === 'tv:curved_run') return 'Desmarque curvo';
	      if (k === 'tv:player_ring') return 'Aro jugador';
	      if (k === 'tv:spot_player') return 'Foco jugador';
	      if (k === 'tv:duel_2v1') return '2v1 TV';
	      if (k === 'tv:pressure_jump') return 'Salto presión TV';
	      if (k === 'tech:smart_curve') return 'Curva inteligente';
	      if (k === 'tech:animated_arrow') return 'Flecha animada';
	      if (k === 'tech:player_shadow') return 'Sombra jugador';
	      if (k === 'tech:labelled_zone') return 'Zona + nombre';
	      if (k === 'tech:defensive_line_auto') return 'Línea automática';
	      if (k === 'tech:distance_meter') return 'Medidor distancia';
	      if (k === 'tech:visual_timer') return 'Temporizador';
	      if (k === 'tech:tactical_zoom') return 'Lupa táctica';
	      if (k === 'tech:advanced_focus') return 'Foco avanzado';
	      if (k === 'tech:before_after') return 'Antes/después';
	      if (k === 'tech:relation_marker') return 'Relación jugadores';
	      if (k === 'tech:block_templates') return 'Plantillas bloque';
	      if (k === 'tool:arrow') return 'Flecha';
	      if (k === 'tool:move') return 'Trayectoria';
	      if (k === 'tool:text') return 'Texto';
	      if (k === 'tool:player') return 'Jugador';
	      if (k === 'tool:area') return 'Área';
	      if (k === 'tool:space') return 'Espacio móvil';
	      if (k === 'fx:spot') return 'Spotlight';
	      if (k === 'fx:blur') return 'Blur';
	      if (k === 'fx:freeze') return 'Freeze';
	      return k;
	    };
	    const kindForResourceKey = (key) => {
	      const k = safeText(key, '');
	      if (k.startsWith('template:')) return 'template';
	      if (k.startsWith('tactic:')) return 'tactic';
	      if (k.startsWith('tv:')) return 'tv';
	      if (k.startsWith('tech:')) return 'tech';
	      if (k.startsWith('tool:')) return 'tool';
	      if (k.startsWith('fx:')) return 'fx';
	      return '';
	    };
	    let activeResourceFilter = 'all';
	    const resourceDescriptionForKey = (key) => {
	      const k = safeText(key, '');
	      if (k === 'template:lanes_manual') return 'Divide el campo en carriles editables para explicar ocupación y amplitud.';
	      if (k === 'template:grid_manual') return 'Añade cuadrícula editable para ubicar zonas y alturas.';
	      if (k === 'template:central_box') return 'Marca una zona central para estructura, pivotes o superioridades.';
	      if (k === 'template:final_third') return 'Resalta el último tercio para ataques y finalizaciones.';
	      if (k === 'tactic:2v1') return 'Plantilla de superioridad con jugadores, zona y flechas.';
	      if (k === 'tactic:third_man') return 'Secuencia para explicar tercer hombre y continuidad.';
	      if (k === 'tactic:defensive_line') return 'Línea defensiva con referencias de salto y altura.';
	      if (k === 'tactic:block_low') return 'Bloque bajo: dos líneas y zona defensiva.';
	      if (k === 'tactic:block_mid') return 'Bloque medio: estructura compacta a media altura.';
	      if (k === 'tactic:block_high') return 'Bloque alto: presión y altura defensiva.';
	      if (k === 'tactic:free_space') return 'Zona libre con flechas de pase/movimiento.';
	      if (k === 'tactic:press_jump') return 'Salto de presión con referencia de jugador y zona.';
	      if (k === 'tactic:shift') return 'Basculación del bloque hacia un lado.';
	      if (k === 'tv:dashed_pass') return 'Flecha de pase discontinua estilo retransmisión.';
	      if (k === 'tv:white_run') return 'Flecha blanca de carrera o desmarque.';
	      if (k === 'tv:curved_run') return 'Desmarque curvo para atacar espalda o intervalo.';
	      if (k === 'tv:player_ring') return 'Aro para señalar un futbolista en imagen parada.';
	      if (k === 'tv:spot_player') return 'Foco visual para destacar un jugador o duelo.';
	      if (k === 'tv:duel_2v1') return 'Paquete TV con aros, flechas y etiqueta 2v1.';
	      if (k === 'tv:pressure_jump') return 'Recurso TV para salto de presión.';
	      if (k === 'tech:smart_curve') return 'Flecha curva con puntos de referencia para ajustar trayectorias de pase o desmarque.';
	      if (k === 'tech:animated_arrow') return 'Flecha progresiva con animación de trazo para explicar el timing.';
	      if (k === 'tech:player_shadow') return 'Marca posición real e ideal del jugador con silueta fantasma.';
	      if (k === 'tech:labelled_zone') return 'Zona sombreada editable con etiqueta táctica.';
	      if (k === 'tech:defensive_line_auto') return 'Línea de bloque con cuatro referencias de jugador.';
	      if (k === 'tech:distance_meter') return 'Medición rápida; si el campo está calibrado muestra metros.';
	      if (k === 'tech:visual_timer') return 'Contador visual para presión, repliegue o toma de decisión.';
	      if (k === 'tech:tactical_zoom') return 'Lupa táctica para encuadrar una zona concreta.';
	      if (k === 'tech:advanced_focus') return 'Foco avanzado combinando spotlight FX y aro editable.';
	      if (k === 'tech:before_after') return 'Compara posición real vs posición ideal en una misma imagen.';
	      if (k === 'tech:relation_marker') return 'Triángulo/líneas de relación entre jugadores: apoyo, cobertura o 2v1.';
	      if (k === 'tech:block_templates') return 'Guías rápidas de bloque bajo, medio y alto.';
	      if (k.startsWith('tool:')) return 'Activa la herramienta manual para dibujar sobre el vídeo.';
	      if (k === 'fx:spot') return 'Crea un spotlight editable en la capa FX.';
	      if (k === 'fx:blur') return 'Crea un blur editable para tapar o enfatizar zonas.';
	      if (k === 'fx:freeze') return 'Congela el frame actual para anotar encima.';
	      return 'Recurso de edición rápida.';
	    };
	    const previewClassForResourceKey = (key) => {
	      const k = safeText(key, '');
	      if (k.includes('dash') || k.includes('pass')) return 'dash';
	      if (k.includes('curve') || k.includes('run') || k.includes('arrow')) return 'curve';
	      if (k.includes('ring') || k.includes('spot_player') || k.includes('focus') || k.includes('zoom')) return 'ring';
	      if (k.includes('block') || k.includes('zone') || k.includes('lanes') || k.includes('third') || k.includes('relation')) return 'zone';
	      return '';
	    };
	    const updateResourcePreview = (key) => {
	      if (!resourcePreview) return;
	      const k = safeText(key, '');
	      const title = labelForResourceKey(k) || 'Recursos';
	      if (resourcePreviewTitle) resourcePreviewTitle.textContent = title;
	      if (resourcePreviewText) resourcePreviewText.textContent = resourceDescriptionForKey(k);
	      try {
	        const mark = resourcePreview.querySelector('.vs-preview-mark');
	        if (mark) mark.className = `vs-preview-mark ${previewClassForResourceKey(k)}`.trim();
	      } catch (e) { /* ignore */ }
	    };
	    const applyResourceFilter = () => {
	      const q = safeText(resourceSearchInput?.value, '').trim().toLowerCase();
	      const filter = safeText(activeResourceFilter, 'all');
	      const chips = Array.from(resourcesMenu?.querySelectorAll?.('[data-vs-resource]') || []);
	      chips.forEach((btn) => {
	        const key = safeText(btn.getAttribute('data-vs-resource'), '');
	        const kind = safeText(btn.getAttribute('data-vs-kind'), kindForResourceKey(key));
	        const label = safeText(btn.textContent, '').toLowerCase();
	        const text = `${key} ${label} ${resourceDescriptionForKey(key)}`.toLowerCase();
	        const inFilter = filter === 'all' || kind === filter;
	        const inSearch = !q || text.includes(q);
	        btn.hidden = !(inFilter && inSearch);
	      });
	      try {
	        Array.from(document.querySelectorAll?.('[data-vs-resource-section]') || []).forEach((section) => {
	          const visible = Array.from(section.querySelectorAll('[data-vs-resource]')).some((b) => !b.hidden);
	          section.style.display = visible ? '' : 'none';
	          const muted = section.previousElementSibling;
	          if (muted && muted.classList?.contains('vs-menu-muted')) muted.style.display = visible ? '' : 'none';
	        });
	      } catch (e) { /* ignore */ }
	    };
	    const renderResourceRecents = () => {
	      if (!resourcesRecentWrap) return;
	      const items = readResourceRecents();
	      if (!items.length) {
	        resourcesRecentWrap.innerHTML = '<div class="hint">—</div>';
	        return;
	      }
	      const escapeHtml = (value) => safeText(value, '')
	        .replaceAll('&', '&amp;')
	        .replaceAll('<', '&lt;')
	        .replaceAll('>', '&gt;')
	        .replaceAll('"', '&quot;')
	        .replaceAll("'", '&#39;');
	      const html = items.map((k) => {
	        const kind = kindForResourceKey(k);
	        const label = labelForResourceKey(k);
	        return `<button type="button" class="vs-chip" data-vs-resource="${k}" data-vs-kind="${kind}"><span class="dot"></span>${escapeHtml(label)}</button>`;
	      }).join('');
	      resourcesRecentWrap.innerHTML = html;
	    };
	    const pushResourceRecent = (key) => {
	      const k = safeText(key, '');
	      if (!k) return;
	      const items = readResourceRecents();
	      const next = [k, ...items.filter((x) => x !== k)].slice(0, 12);
	      writeResourceRecents(next);
	      renderResourceRecents();
	    };
	    const closeResourcesMenu = () => {
	      try { if (resourcesMenu && resourcesMenu.tagName === 'DETAILS') resourcesMenu.open = false; } catch (e) { /* ignore */ }
	    };
	    const addTvResource = (resourceKey) => {
	      const key = safeText(resourceKey, '');
	      const w = Number(fabricCanvas.getWidth?.()) || 0;
	      const h = Number(fabricCanvas.getHeight?.()) || 0;
	      if (!key || !w || !h) { setStatus('Recurso TV no disponible.', true); return false; }
	      const px = (x) => clamp(Number(x) || 0, 0.02, 0.98) * w;
	      const py = (y) => clamp(Number(y) || 0, 0.02, 0.98) * h;
	      const sw = clamp(Math.round(strokeWidth() || 6), 4, 16);
	      const yellow = '#facc15';
	      const white = '#ffffff';
	      const red = '#fb7185';
	      const cyan = '#22d3ee';
	      const makeHead = (x2, y2, angle, color) => {
	        const headLen = clamp(18 + sw, 18, 38);
	        return new fabric.Polygon([
	          { x: x2, y: y2 },
	          { x: x2 - headLen * Math.cos(angle - Math.PI / 7), y: y2 - headLen * Math.sin(angle - Math.PI / 7) },
	          { x: x2 - headLen * Math.cos(angle + Math.PI / 7), y: y2 - headLen * Math.sin(angle + Math.PI / 7) },
	        ], { fill: color, selectable: false, evented: false, shadow: 'rgba(0,0,0,0.32) 0 2px 7px' });
	      };
	      const makeArrow = (a, b, color = white, opts = {}) => {
	        const x1 = px(a[0]); const y1 = py(a[1]);
	        const x2 = px(b[0]); const y2 = py(b[1]);
	        const line = new fabric.Line([x1, y1, x2, y2], {
	          stroke: color,
	          strokeWidth: opts.strokeWidth || sw,
	          strokeDashArray: opts.dash || null,
	          strokeLineCap: 'round',
	          strokeLineJoin: 'round',
	          selectable: false,
	          evented: false,
	          strokeUniform: true,
	          objectCaching: false,
	          shadow: 'rgba(0,0,0,0.32) 0 2px 7px',
	        });
	        const group = new fabric.Group([line, makeHead(x2, y2, Math.atan2(y2 - y1, x2 - x1), color)], { selectable: true, evented: true });
	        group.data = seedLayerDataNow({ kind: opts.kind || 'arrow', preset: key, anim: 'draw', anim_ms: 700, line_style: opts.dash ? 'dash' : 'solid' });
	        return group;
	      };
	      const makeCurve = (a, c, b, color = yellow, opts = {}) => {
	        const x1 = px(a[0]); const y1 = py(a[1]);
	        const cx = px(c[0]); const cy = py(c[1]);
	        const x2 = px(b[0]); const y2 = py(b[1]);
	        const path = new fabric.Path(`M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`, {
	          fill: '',
	          stroke: color,
	          strokeWidth: opts.strokeWidth || sw,
	          strokeDashArray: opts.dash || null,
	          strokeLineCap: 'round',
	          strokeLineJoin: 'round',
	          selectable: false,
	          evented: false,
	          strokeUniform: true,
	          objectCaching: false,
	          shadow: 'rgba(0,0,0,0.32) 0 2px 7px',
	        });
	        const group = new fabric.Group([path, makeHead(x2, y2, Math.atan2(y2 - cy, x2 - cx), color)], { selectable: true, evented: true });
	        group.data = seedLayerDataNow({ kind: 'movement_line', preset: key, anim: 'draw', anim_ms: 750, line_style: opts.dash ? 'dash' : 'solid' });
	        return group;
	      };
	      const makeRing = (x, y, color = yellow, opts = {}) => {
	        const r = clamp(Math.min(w, h) * (opts.scale || 0.032), 14, 36);
	        const halo = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: r * 1.28,
	          originX: 'center',
	          originY: 'center',
	          fill: colorToRgba(color, 0.14, 'rgba(250,204,21,0.14)'),
	          stroke: colorToRgba(color, 0.34, 'rgba(250,204,21,0.34)'),
	          strokeWidth: Math.max(2, Math.round(sw * 0.30)),
	          selectable: false,
	          evented: false,
	        });
	        const ring = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: r,
	          originX: 'center',
	          originY: 'center',
	          fill: 'rgba(0,0,0,0)',
	          stroke: color,
	          strokeWidth: Math.max(3, Math.round(sw * 0.55)),
	          selectable: false,
	          evented: false,
	          strokeUniform: true,
	          shadow: 'rgba(0,0,0,0.32) 0 2px 7px',
	        });
	        const group = new fabric.Group([halo, ring], {
	          left: px(x),
	          top: py(y),
	          originX: 'center',
	          originY: 'center',
	          selectable: true,
	          evented: true,
	        });
	        group.data = seedLayerDataNow({ kind: 'player_ring', preset: key, anim: 'pop', anim_ms: 450 });
	        return group;
	      };
	      const makeSpot = (x, y, color = yellow) => {
	        const r = clamp(Math.min(w, h) * 0.082, 36, 92);
	        const ringR = clamp(Math.min(w, h) * 0.027, 14, 36);
	        const spot = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: r,
	          originX: 'center',
	          originY: 'center',
	          fill: colorToRgba(color, 0.17, 'rgba(250,204,21,0.17)'),
	          stroke: colorToRgba(color, 0.42, 'rgba(250,204,21,0.42)'),
	          strokeWidth: Math.max(2, Math.round(sw * 0.35)),
	          selectable: false,
	          evented: false,
	          strokeUniform: true,
	        });
	        const halo = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: ringR,
	          originX: 'center',
	          originY: 'center',
	          fill: 'rgba(0,0,0,0)',
	          stroke: color,
	          strokeWidth: Math.max(3, Math.round(sw * 0.55)),
	          selectable: false,
	          evented: false,
	          strokeUniform: true,
	          shadow: 'rgba(0,0,0,0.32) 0 2px 7px',
	        });
	        const group = new fabric.Group([spot, halo], {
	          left: px(x),
	          top: py(y),
	          originX: 'center',
	          originY: 'center',
	          selectable: true,
	          evented: true,
	        });
	        group.data = seedLayerDataNow({ kind: 'spotlight_marker', preset: key, anim: 'pop', anim_ms: 450 });
	        return group;
	      };
	      const makeLabel = (text, x, y, color = white) => {
	        const label = new fabric.Textbox(safeText(text, ''), {
	          left: px(x),
	          top: py(y),
	          width: Math.min(w * 0.26, 220),
	          fontSize: clamp(Math.round(Math.min(w, h) * 0.042), 18, 34),
	          fontFamily: 'Arial',
	          fontWeight: 900,
	          fill: color,
	          textAlign: 'center',
	          originX: 'center',
	          originY: 'center',
	          stroke: 'rgba(2,6,23,0.92)',
	          strokeWidth: 4,
	          paintFirst: 'stroke',
	          selectable: true,
	          evented: true,
	        });
	        label.data = seedLayerDataNow({ kind: 'text_caption', preset: key, text: safeText(text, '') });
	        return label;
	      };
	      const add = [];
	      if (key === 'dashed_pass') {
	        add.push(makeArrow([0.20, 0.54], [0.43, 0.47], white, { dash: [14, 12], strokeWidth: Math.max(4, sw * 0.75), kind: 'pass_line' }));
	      } else if (key === 'white_run') {
	        add.push(makeArrow([0.45, 0.70], [0.73, 0.43], white, { strokeWidth: Math.max(5, sw * 0.85), kind: 'movement_line' }));
	      } else if (key === 'curved_run') {
	        add.push(makeCurve([0.28, 0.70], [0.48, 0.36], [0.68, 0.51], yellow, { strokeWidth: Math.max(5, sw * 0.85) }));
	      } else if (key === 'player_ring') {
	        add.push(makeRing(0.72, 0.34, yellow));
	      } else if (key === 'spot_player') {
	        add.push(makeSpot(0.72, 0.34, yellow));
	      } else if (key === 'duel_2v1') {
	        add.push(makeRing(0.47, 0.52, red, { scale: 0.030 }));
	        add.push(makeRing(0.67, 0.43, yellow, { scale: 0.030 }));
	        add.push(makeArrow([0.21, 0.55], [0.43, 0.49], white, { dash: [14, 12], strokeWidth: Math.max(4, sw * 0.72), kind: 'pass_line' }));
	        add.push(makeArrow([0.50, 0.55], [0.73, 0.40], white, { strokeWidth: Math.max(5, sw * 0.82), kind: 'movement_line' }));
	        add.push(makeCurve([0.36, 0.66], [0.50, 0.38], [0.63, 0.49], yellow, { strokeWidth: Math.max(5, sw * 0.82) }));
	        add.push(makeLabel('2v1', 0.55, 0.38, white));
	      } else if (key === 'pressure_jump') {
	        add.push(makeRing(0.44, 0.55, red, { scale: 0.030 }));
	        add.push(makeArrow([0.30, 0.66], [0.48, 0.52], red, { dash: [12, 10], strokeWidth: Math.max(5, sw * 0.82), kind: 'pressure_jump' }));
	        add.push(makeLabel('SALTO', 0.49, 0.43, white));
	      }
	      if (!add.length) { setStatus('Recurso TV no soportado.', true); return false; }
	      add.forEach((obj) => {
	        try { fabricCanvas.add(obj); } catch (e) { /* ignore */ }
	      });
	      pushHistory();
	      try {
	        const sel = new fabric.ActiveSelection(add, { canvas: fabricCanvas });
	        fabricCanvas.setActiveObject(sel);
	      } catch (e) {
	        try { fabricCanvas.setActiveObject(add[add.length - 1]); } catch (e2) { /* ignore */ }
	      }
	      selectedFxId = 0;
	      updateLayerPanel();
	      renderFxList();
	      renderDrawLayers();
	      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      setStatus(`Recurso TV aplicado: ${labelForResourceKey(`tv:${key}`) || key}.`);
	      return true;
	    };
	    const addTechResource = (resourceKey) => {
	      const key = safeText(resourceKey, '');
	      const w = Number(fabricCanvas.getWidth?.()) || 0;
	      const h = Number(fabricCanvas.getHeight?.()) || 0;
	      if (!key || !w || !h) { setStatus('Recurso técnico no disponible.', true); return false; }
	      const px = (x) => clamp(Number(x) || 0, 0.02, 0.98) * w;
	      const py = (y) => clamp(Number(y) || 0, 0.02, 0.98) * h;
	      const sw = clamp(Math.round(strokeWidth() || 6), 3, 16);
	      const color = strokeColor();
	      const cyan = '#22d3ee';
	      const yellow = '#facc15';
	      const red = '#fb7185';
	      const green = '#34d399';
	      const blue = '#60a5fa';
	      const white = '#ffffff';
	      const shadow = 'rgba(0,0,0,0.32) 0 2px 7px';
	      const baseData = (extra = {}) => seedLayerDataNow({ preset: `tech:${key}`, ...(extra || {}) });

	      const makeLabel = (text, x, y, opts = {}) => {
	        const label = new fabric.Textbox(safeText(text, ''), {
	          left: px(x),
	          top: py(y),
	          width: Math.min(w * 0.36, opts.width || 280),
	          fontSize: opts.fontSize || clamp(Math.round(Math.min(w, h) * 0.04), 16, 34),
	          fontFamily: 'Arial',
	          fontWeight: 900,
	          fill: opts.color || white,
	          textAlign: 'center',
	          originX: 'center',
	          originY: 'center',
	          stroke: 'rgba(2,6,23,0.92)',
	          strokeWidth: opts.strokeWidth || 4,
	          paintFirst: 'stroke',
	          selectable: false,
	          evented: false,
	        });
	        return label;
	      };
	      const makeHead = (x2, y2, angle, c) => {
	        const headLen = clamp(18 + sw, 18, 40);
	        return new fabric.Polygon([
	          { x: x2, y: y2 },
	          { x: x2 - headLen * Math.cos(angle - Math.PI / 7), y: y2 - headLen * Math.sin(angle - Math.PI / 7) },
	          { x: x2 - headLen * Math.cos(angle + Math.PI / 7), y: y2 - headLen * Math.sin(angle + Math.PI / 7) },
	        ], { fill: c, selectable: false, evented: false, shadow });
	      };
	      const makeArrow = (a, b, c = color, opts = {}) => {
	        const x1 = px(a[0]); const y1 = py(a[1]);
	        const x2 = px(b[0]); const y2 = py(b[1]);
	        const line = new fabric.Line([x1, y1, x2, y2], {
	          stroke: c,
	          strokeWidth: opts.strokeWidth || sw,
	          strokeDashArray: opts.dash || null,
	          strokeLineCap: 'round',
	          strokeUniform: true,
	          selectable: false,
	          evented: false,
	          objectCaching: false,
	          shadow,
	        });
	        const group = new fabric.Group([line, makeHead(x2, y2, Math.atan2(y2 - y1, x2 - x1), c)], { selectable: true, evented: true });
	        group.data = baseData({ kind: opts.kind || 'arrow', anim: opts.anim || 'draw', anim_ms: opts.animMs || 800, line_style: opts.dash ? 'dash' : 'solid' });
	        return group;
	      };
	      const makeCurve = (a, cpt, b, c = color, opts = {}) => {
	        const x1 = px(a[0]); const y1 = py(a[1]);
	        const cx = px(cpt[0]); const cy = py(cpt[1]);
	        const x2 = px(b[0]); const y2 = py(b[1]);
	        const path = new fabric.Path(`M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`, {
	          fill: '',
	          stroke: c,
	          strokeWidth: opts.strokeWidth || sw,
	          strokeDashArray: opts.dash || null,
	          strokeLineCap: 'round',
	          strokeLineJoin: 'round',
	          selectable: false,
	          evented: false,
	          strokeUniform: true,
	          objectCaching: false,
	          shadow,
	        });
	        const control = new fabric.Circle({
	          left: cx,
	          top: cy,
	          radius: clamp(sw * 0.85, 5, 13),
	          originX: 'center',
	          originY: 'center',
	          fill: c,
	          stroke: 'rgba(2,6,23,0.8)',
	          strokeWidth: 2,
	          selectable: false,
	          evented: false,
	        });
	        const group = new fabric.Group([path, makeHead(x2, y2, Math.atan2(y2 - cy, x2 - cx), c), control], { selectable: true, evented: true });
	        group.data = baseData({ kind: 'curve_arrow', anim: opts.anim || 'draw', anim_ms: opts.animMs || 850, line_style: opts.dash ? 'dash' : 'solid', control_hint: true });
	        return group;
	      };
	      const makeRing = (x, y, c = yellow, scale = 0.034, opts = {}) => {
	        const r = clamp(Math.min(w, h) * scale, 14, 40);
	        const halo = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: r * 1.32,
	          originX: 'center',
	          originY: 'center',
	          fill: colorToRgba(c, opts.ghost ? 0.07 : 0.16, 'rgba(250,204,21,0.16)'),
	          stroke: colorToRgba(c, opts.ghost ? 0.24 : 0.40, 'rgba(250,204,21,0.40)'),
	          strokeWidth: 2,
	          selectable: false,
	          evented: false,
	        });
	        const ring = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: r,
	          originX: 'center',
	          originY: 'center',
	          fill: 'rgba(0,0,0,0)',
	          stroke: c,
	          strokeDashArray: opts.ghost ? [8, 7] : null,
	          strokeWidth: Math.max(3, Math.round(sw * 0.55)),
	          strokeUniform: true,
	          selectable: false,
	          evented: false,
	          opacity: opts.ghost ? 0.65 : 1,
	          shadow,
	        });
	        const group = new fabric.Group([halo, ring], {
	          left: px(x),
	          top: py(y),
	          originX: 'center',
	          originY: 'center',
	          selectable: true,
	          evented: true,
	        });
	        group.data = baseData({ kind: opts.kind || 'player_ring', anim: opts.ghost ? 'none' : 'pop', anim_ms: 450, ghost: Boolean(opts.ghost) });
	        return group;
	      };
	      const makePlayerDot = (x, y, c = blue, text = '') => {
	        const r = clamp(Math.min(w, h) * 0.025, 12, 24);
	        const circle = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: r,
	          originX: 'center',
	          originY: 'center',
	          fill: colorToRgba(c, 0.92, c),
	          stroke: 'rgba(2,6,23,0.85)',
	          strokeWidth: 3,
	          selectable: false,
	          evented: false,
	        });
	        const label = new fabric.Text(safeText(text, ''), {
	          left: 0,
	          top: 0,
	          originX: 'center',
	          originY: 'center',
	          fill: '#0f172a',
	          fontSize: clamp(Math.round(r * 0.9), 10, 18),
	          fontWeight: 900,
	          selectable: false,
	          evented: false,
	        });
	        const group = new fabric.Group([circle, label], { left: px(x), top: py(y), originX: 'center', originY: 'center', selectable: true, evented: true });
	        group.data = baseData({ kind: 'player_marker', number: safeText(text, '') });
	        return group;
	      };
	      const makeZone = (x, y, rw, rh, c = cyan, text = '') => {
	        const rect = new fabric.Rect({
	          left: px(x),
	          top: py(y),
	          width: clamp(Number(rw) || 0.18, 0.04, 0.92) * w,
	          height: clamp(Number(rh) || 0.18, 0.04, 0.92) * h,
	          originX: 'center',
	          originY: 'center',
	          fill: colorToRgba(c, 0.15, 'rgba(34,211,238,0.15)'),
	          stroke: colorToRgba(c, 0.82, 'rgba(34,211,238,0.82)'),
	          strokeWidth: Math.max(2, Math.round(sw * 0.45)),
	          strokeDashArray: [10, 8],
	          rx: 14,
	          ry: 14,
	          strokeUniform: true,
	          selectable: false,
	          evented: false,
	          objectCaching: false,
	        });
	        const label = makeLabel(text || 'Zona', x, y - ((rh || 0.18) * 0.56), { color: white, fontSize: clamp(Math.round(Math.min(w, h) * 0.032), 14, 26), width: 230, strokeWidth: 3 });
	        const group = new fabric.Group([rect, label], { selectable: true, evented: true });
	        group.data = baseData({ kind: 'space_zone', label: safeText(text, ''), space_base_fill: colorToRgba(c, 0.15, ''), space_base_stroke: colorToRgba(c, 0.82, '') });
	        return group;
	      };
	      const makeLine = (a, b, c = white, opts = {}) => {
	        const line = new fabric.Line([px(a[0]), py(a[1]), px(b[0]), py(b[1])], {
	          stroke: colorToRgba(c, opts.alpha ?? 0.84, c),
	          strokeWidth: opts.strokeWidth || Math.max(3, Math.round(sw * 0.56)),
	          strokeDashArray: opts.dash || null,
	          strokeLineCap: 'round',
	          strokeUniform: true,
	          selectable: true,
	          evented: true,
	          objectCaching: false,
	          shadow,
	        });
	        line.data = baseData({ kind: 'line', line_style: opts.dash ? 'dash' : 'solid' });
	        return line;
	      };

	      const add = [];
	      if (key === 'smart_curve') {
	        add.push(makeCurve([0.24, 0.68], [0.50, 0.34], [0.76, 0.54], yellow, { animMs: 900 }));
	        add.push(makeLabel('Curva editable', 0.50, 0.29, { color: white, fontSize: 20, strokeWidth: 3 }));
	      } else if (key === 'animated_arrow') {
	        add.push(makeArrow([0.28, 0.60], [0.72, 0.42], color, { anim: 'draw', animMs: 1100, kind: 'movement_line' }));
	        add.push(makeLabel('Timing', 0.52, 0.37, { color: white, fontSize: 22, strokeWidth: 3 }));
	      } else if (key === 'player_shadow') {
	        add.push(makeRing(0.42, 0.58, white, 0.032, { ghost: true, kind: 'player_shadow_from' }));
	        add.push(makeRing(0.60, 0.46, yellow, 0.032, { kind: 'player_shadow_to' }));
	        add.push(makeArrow([0.43, 0.56], [0.58, 0.47], yellow, { dash: [10, 8], kind: 'movement_line' }));
	        add.push(makeLabel('ideal', 0.62, 0.38, { color: yellow, fontSize: 20, strokeWidth: 3 }));
	      } else if (key === 'labelled_zone') {
	        add.push(makeZone(0.58, 0.46, 0.30, 0.22, green, 'Espacio libre'));
	      } else if (key === 'defensive_line_auto') {
	        add.push(makeLine([0.20, 0.55], [0.82, 0.55], cyan, { dash: [12, 8], strokeWidth: Math.max(3, sw * 0.72) }));
	        [0.26, 0.42, 0.58, 0.74].forEach((x, idx) => add.push(makePlayerDot(x, 0.55, blue, String(idx + 2))));
	        add.push(makeLabel('altura del bloque', 0.52, 0.45, { color: white, fontSize: 20, strokeWidth: 3 }));
	      } else if (key === 'distance_meter') {
	        const a = { x: px(0.34), y: py(0.58) };
	        const b = { x: px(0.66), y: py(0.46) };
	        const meters = distMeters(a, b);
	        const label = meters != null ? `${meters.toFixed(1)} m` : 'Distancia';
	        const line = makeLine([0.34, 0.58], [0.66, 0.46], yellow, { dash: [10, 8], strokeWidth: Math.max(3, sw * 0.65) });
	        line.data.kind = 'measure';
	        line.data.meters = meters != null ? Number(meters) : null;
	        add.push(line);
	        add.push(makeLabel(label, 0.50, 0.48, { color: white, fontSize: 22, strokeWidth: 3 }));
	      } else if (key === 'visual_timer') {
	        const ring = new fabric.Circle({
	          left: px(0.50),
	          top: py(0.42),
	          radius: clamp(Math.min(w, h) * 0.055, 26, 62),
	          originX: 'center',
	          originY: 'center',
	          fill: 'rgba(2,6,23,0.50)',
	          stroke: yellow,
	          strokeWidth: Math.max(4, sw * 0.6),
	          strokeDashArray: [18, 8],
	          selectable: false,
	          evented: false,
	          shadow,
	        });
	        const txt = makeLabel('3s', 0.50, 0.42, { color: white, fontSize: clamp(Math.round(Math.min(w, h) * 0.062), 26, 58), strokeWidth: 3 });
	        const group = new fabric.Group([ring, txt], { selectable: true, evented: true });
	        group.data = baseData({ kind: 'timer', anim: 'pulse', anim_ms: 1000, seconds: 3 });
	        add.push(group);
	      } else if (key === 'tactical_zoom') {
	        const lens = new fabric.Circle({
	          left: 0,
	          top: 0,
	          radius: clamp(Math.min(w, h) * 0.105, 54, 118),
	          originX: 'center',
	          originY: 'center',
	          fill: 'rgba(255,255,255,0.08)',
	          stroke: white,
	          strokeWidth: Math.max(3, sw * 0.55),
	          strokeUniform: true,
	          selectable: false,
	          evented: false,
	          shadow,
	        });
	        const handle = new fabric.Line([54, 54, 106, 106], { stroke: white, strokeWidth: Math.max(5, sw * 0.72), strokeLineCap: 'round', selectable: false, evented: false, shadow });
	        const txt = makeLabel('ZOOM', 0.50, 0.40, { color: white, fontSize: 20, strokeWidth: 3 });
	        const group = new fabric.Group([lens, handle, txt], { left: px(0.50), top: py(0.48), originX: 'center', originY: 'center', selectable: true, evented: true });
	        group.data = baseData({ kind: 'tactical_zoom', anim: 'pop', anim_ms: 450 });
	        add.push(group);
	      } else if (key === 'advanced_focus') {
	        const fw = Number(fxEl?.width) || w;
	        const fh = Number(fxEl?.height) || h;
	        const layer = {
	          id: fxSeq++,
	          ...seedLayerDataNow({ t_in_s: Number(video.currentTime) || 0, fade_in_ms: 180, fade_out_ms: 180 }),
	          kind: 'spotlight',
	          cx: fw * 0.58,
	          cy: fh * 0.46,
	          r: Math.max(56, Math.min(fw, fh) * 0.17),
	          intensity: 0.74,
	          feather: 0.24,
	        };
	        fxState.layers = [...(Array.isArray(fxState.layers) ? fxState.layers : []), layer].slice(0, 80);
	        selectedFxId = layer.id;
	        add.push(makeRing(0.58, 0.46, yellow, 0.038, { kind: 'advanced_focus_ring' }));
	      } else if (key === 'before_after') {
	        add.push(makeRing(0.40, 0.58, red, 0.030, { ghost: true, kind: 'before_position' }));
	        add.push(makeLabel('REAL', 0.40, 0.68, { color: red, fontSize: 18, strokeWidth: 3 }));
	        add.push(makeRing(0.62, 0.47, green, 0.032, { kind: 'after_position' }));
	        add.push(makeLabel('IDEAL', 0.62, 0.37, { color: green, fontSize: 18, strokeWidth: 3 }));
	        add.push(makeArrow([0.43, 0.56], [0.59, 0.49], white, { dash: [10, 8], kind: 'movement_line' }));
	      } else if (key === 'relation_marker') {
	        add.push(makePlayerDot(0.40, 0.58, blue, '6'));
	        add.push(makePlayerDot(0.56, 0.46, blue, '8'));
	        add.push(makePlayerDot(0.70, 0.60, blue, '10'));
	        add.push(makeLine([0.40, 0.58], [0.56, 0.46], cyan, { dash: [10, 8] }));
	        add.push(makeLine([0.56, 0.46], [0.70, 0.60], cyan, { dash: [10, 8] }));
	        add.push(makeLine([0.70, 0.60], [0.40, 0.58], cyan, { dash: [10, 8] }));
	        add.push(makeLabel('apoyo / cobertura', 0.55, 0.36, { color: white, fontSize: 20, strokeWidth: 3 }));
	      } else if (key === 'block_templates') {
	        add.push(makeZone(0.50, 0.34, 0.58, 0.13, red, 'Bloque alto'));
	        add.push(makeZone(0.50, 0.52, 0.58, 0.13, yellow, 'Bloque medio'));
	        add.push(makeZone(0.50, 0.70, 0.58, 0.13, blue, 'Bloque bajo'));
	      }
	      if (!add.length && key !== 'advanced_focus') { setStatus('Recurso técnico no soportado.', true); return false; }
	      add.forEach((obj) => {
	        try { fabricCanvas.add(obj); } catch (e) { /* ignore */ }
	      });
	      if (add.length) {
	        pushHistory();
	        try {
	          const sel = new fabric.ActiveSelection(add, { canvas: fabricCanvas });
	          fabricCanvas.setActiveObject(sel);
	        } catch (e) {
	          try { fabricCanvas.setActiveObject(add[add.length - 1]); } catch (e2) { /* ignore */ }
	        }
	      }
	      if (key !== 'advanced_focus') selectedFxId = 0;
	      updateLayerPanel();
	      renderFxList();
	      renderDrawLayers();
	      try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      setStatus(`Recurso técnico aplicado: ${labelForResourceKey(`tech:${key}`) || key}.`);
	      return true;
	    };
	    const useResource = (key) => {
	      const k = safeText(key, '');
	      if (!k) return;
	      // Plantillas
	      if (k.startsWith('template:')) {
	        const name = k.split(':').slice(1).join(':');
	        if (!templateSelect || !templateApplyBtn) { setStatus('No se pudo aplicar plantilla.', true); return; }
	        try { templateSelect.value = name; } catch (e) { /* ignore */ }
	        templateApplyBtn.click();
	        pushResourceRecent(k);
	        closeResourcesMenu();
	        return;
	      }
	      if (k.startsWith('tactic:')) {
	        const presetKey = k.split(':').slice(1).join(':');
	        if (addTacticalPreset(presetKey)) {
	          pushResourceRecent(k);
	          closeResourcesMenu();
	        }
	        return;
	      }
	      if (k.startsWith('tv:')) {
	        const presetKey = k.split(':').slice(1).join(':');
	        if (addTvResource(presetKey)) {
	          pushResourceRecent(k);
	          closeResourcesMenu();
	        }
	        return;
	      }
	      if (k.startsWith('tech:')) {
	        const presetKey = k.split(':').slice(1).join(':');
	        if (addTechResource(presetKey)) {
	          pushResourceRecent(k);
	          closeResourcesMenu();
	        }
	        return;
	      }
	      // Herramientas
	      if (k.startsWith('tool:')) {
	        const toolKey = k.split(':').slice(1).join(':');
	        setTool(toolKey);
	        pushResourceRecent(k);
	        closeResourcesMenu();
	        setStatus(`Tool: ${labelForResourceKey(k)}`);
	        return;
	      }
	      // FX: el menú crea un efecto usable de inmediato; los botones superiores permiten dibujarlo a mano.
	      if (k === 'fx:spot') {
	        const layer = {
	          id: fxSeq++,
	          ...seedLayerDataNow({ t_in_s: Number(video.currentTime) || 0, fade_in_ms: 150, fade_out_ms: 150 }),
	          kind: 'spotlight',
	          cx: (Number(fxEl?.width) || 1280) * 0.5,
	          cy: (Number(fxEl?.height) || 720) * 0.48,
	          r: Math.max(42, Math.min(Number(fxEl?.width) || 1280, Number(fxEl?.height) || 720) * 0.15),
	          intensity: 0.68,
	          feather: 0.18,
	        };
	        fxState.layers = [...(Array.isArray(fxState.layers) ? fxState.layers : []), layer].slice(0, 80);
	        selectedFxId = layer.id;
	        setTool('select');
	        renderFxList();
	        updateLayerPanel();
	        pushResourceRecent(k);
	        closeResourcesMenu();
	        setStatus('Spotlight añadido.');
	        return;
	      }
	      if (k === 'fx:blur') {
	        const fw = Number(fxEl?.width) || 1280;
	        const fh = Number(fxEl?.height) || 720;
	        const layer = {
	          id: fxSeq++,
	          ...seedLayerDataNow({ t_in_s: Number(video.currentTime) || 0, fade_in_ms: 150, fade_out_ms: 150 }),
	          kind: 'blur',
	          x: fw * 0.34,
	          y: fh * 0.34,
	          w: fw * 0.32,
	          h: fh * 0.24,
	          blur_px: 10,
	          opacity: 1,
	        };
	        fxState.layers = [...(Array.isArray(fxState.layers) ? fxState.layers : []), layer].slice(0, 80);
	        selectedFxId = layer.id;
	        setTool('select');
	        renderFxList();
	        updateLayerPanel();
	        pushResourceRecent(k);
	        closeResourcesMenu();
	        setStatus('Blur añadido.');
	        return;
	      }
	      if (k === 'fx:freeze') { try { btnFreeze?.click?.(); } catch (e) { /* ignore */ } pushResourceRecent(k); closeResourcesMenu(); return; }
	    };

	    // Rehidrata recientes y cablea botones (incluye los generados dinámicamente).
	    renderResourceRecents();
	    const wireResourceButtons = (root) => {
	      try {
	        Array.from((root || document).querySelectorAll?.('[data-vs-resource]') || []).forEach((btn) => {
	          if (btn.__vsResourceWired) return;
	          btn.__vsResourceWired = true;
	          btn.addEventListener('mouseenter', () => updateResourcePreview(btn.getAttribute('data-vs-resource')));
	          btn.addEventListener('focus', () => updateResourcePreview(btn.getAttribute('data-vs-resource')));
	          btn.addEventListener('click', () => useResource(btn.getAttribute('data-vs-resource')));
	        });
	      } catch (e) { /* ignore */ }
	    };
	    wireResourceButtons(document);
	    resourceSearchInput?.addEventListener?.('input', () => applyResourceFilter());
	    try {
	      Array.from(resourceTabsWrap?.querySelectorAll?.('[data-vs-resource-filter]') || []).forEach((btn) => {
	        btn.addEventListener('click', () => {
	          activeResourceFilter = safeText(btn.getAttribute('data-vs-resource-filter'), 'all');
	          Array.from(resourceTabsWrap.querySelectorAll('[data-vs-resource-filter]')).forEach((b) => b.classList.toggle('active', b === btn));
	          applyResourceFilter();
	        });
	      });
	    } catch (e) { /* ignore */ }
	    btnCapturePrimary?.addEventListener?.('click', () => {
	      try { btnSnap?.click?.(); } catch (e) { /* ignore */ }
	    });
	    resourcesMenu?.addEventListener?.('toggle', () => {
	      // Al abrir, re-cablea los "recientes" (se re-renderizan).
	      if (resourcesMenu?.open) {
	        renderResourceRecents();
	        wireResourceButtons(resourcesMenu);
	        applyResourceFilter();
	        updateResourcePreview('tv:dashed_pass');
	      }
	    });
	    btnRedo?.addEventListener('click', () => {
	      if (!redo.length) { setStatus('Redo.', true); return; }
	      const json = redo.pop();
	      if (!json) { setStatus('Redo.', true); return; }
	      history.push(json);
	      restoreJson(json);
	      setStatus('Redo.');
	    });

	    const resetView = () => {
	      try {
	        if (!fabricCanvas) return false;
	        fabricCanvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
	        fabricCanvas.setZoom?.(1);
	        fabricCanvas.requestRenderAll?.();
	        setStatus('Vista: 1:1');
	        return true;
	      } catch (e) {
	        return false;
	      }
	    };
	    btnViewReset?.addEventListener('click', () => resetView());
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

	    const isTextEntryEl = (el) => {
	      const tag = safeText(el?.tagName, '').toLowerCase();
	      if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
	      try { if (el?.isContentEditable) return true; } catch (e) { /* ignore */ }
	      return false;
	    };

	    // Atajos “premium”
		    document.addEventListener('keydown', (ev) => {
	      const key = safeText(ev?.key, '');
	      if (!key) return;
	      if (isTextEntryEl(document.activeElement)) return;

	      const mod = Boolean(ev.metaKey || ev.ctrlKey);
	      const shift = Boolean(ev.shiftKey);

	      // Undo / Redo
	      if (mod && (key === 'z' || key === 'Z')) {
	        ev.preventDefault();
	        if (shift) btnRedo?.click?.();
	        else btnUndo?.click?.();
	        return;
	      }
	      if (mod && (key === '0')) { ev.preventDefault(); resetView(); return; }
	      if (mod && (key === 'y' || key === 'Y')) {
	        ev.preventDefault();
	        btnRedo?.click?.();
	        return;
	      }

		      // Copiar / Pegar / Duplicar
		      if (mod && (key === 'c' || key === 'C')) { ev.preventDefault(); copyActiveObject(); return; }
		      if (mod && (key === 'v' || key === 'V')) { ev.preventDefault(); pasteClipboardObject(); return; }
		      if (mod && (key === 'd' || key === 'D')) { ev.preventDefault(); layerDuplicateBtn?.click?.(); return; }
		      // Clip: guardar rápido IN/OUT
		      if (mod && (key === 'k' || key === 'K' || key === 'Enter')) { ev.preventDefault(); clipSaveQuickBtn?.click?.(); return; }

	      // Borrar
	      if (key === 'Delete' || key === 'Backspace') {
	        ev.preventDefault();
	        deleteCurrentLayer({ confirm: false });
	        return;
	      }

		      // Mover con flechas (nudge)
	      const step = shift ? 10 : 1;
	      if (key === 'ArrowLeft') { ev.preventDefault(); nudgeActiveObject(-step, 0); return; }
	      if (key === 'ArrowRight') { ev.preventDefault(); nudgeActiveObject(step, 0); return; }
	      if (key === 'ArrowUp') { ev.preventDefault(); nudgeActiveObject(0, -step); return; }
	      if (key === 'ArrowDown') { ev.preventDefault(); nudgeActiveObject(0, step); return; }

		      // Herramientas (atajos)
	      if (key === 'v' || key === 'V') { setTool('select'); return; }
	      if (key === 'b' || key === 'B') { setTool('pen'); return; }
	      if (key === 'l' || key === 'L') { setTool('line'); return; }
	      if (key === 'r' || key === 'R') { setTool('rect'); return; }
	      if (key === 'o' || key === 'O') { setTool('circle'); return; }
	      if (key === 'm' || key === 'M') { setTool('measure'); return; }
	      if (key === 'a' || key === 'A') { setTool('arrow'); return; }
	      if (key === 't' || key === 'T') { setTool('text'); return; }
		      if (key === 'Escape') {
	        try { fabricCanvas.discardActiveObject?.(); fabricCanvas.requestRenderAll?.(); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	      }
	    });

    const syncPlayButtons = () => {
      const playing = !video.paused && !video.ended;
      if (btnPlay) btnPlay.hidden = playing;
      if (btnPause) btnPause.hidden = !playing;
    };
	    btnPlay?.addEventListener('click', async () => {
	      enforceTrimPlayback();
        // Si hay un segmento IN/OUT válido, reprodúcelo como “clip” (se detiene en OUT).
        try {
          const a = Number(inInput?.value || 0) || 0;
          const b = Number(outInput?.value || 0) || 0;
          const start = Math.max(0, Math.min(a, b));
          const end = Math.max(a, b);
          if (end && end > start) {
            const now = Number(video.currentTime) || 0;
            // UX: si estás ya en OUT (o muy cerca), el usuario normalmente quiere seguir viendo el vídeo completo.
            // No activamos el bound porque provocaría una pausa inmediata y "parece que Play no avanza".
            if (now >= end - 0.02) {
              clipBoundActive = false;
            } else {
              clipBoundActive = true;
              clipBoundStart = start;
              clipBoundEnd = end;
              if (now < start - 0.04) {
                try { video.currentTime = start; } catch (e) { /* ignore */ }
              }
            }
          }
        } catch (e) { /* ignore */ }
	      try { await video.play(); } catch (e) { /* ignore */ }
	      syncPlayButtons();
	    });
	    btnPause?.addEventListener('click', () => { try { video.pause(); } catch (e) { /* ignore */ } syncPlayButtons(); });
		    video.addEventListener('play', syncPlayButtons);
		    video.addEventListener('play', () => {
		      // En reproducción, oculta la selección para evitar marcos flotantes al entrar/salir capas.
		      // Excepción: si hay un marcador de jugador seleccionado, permitimos moverlo mientras reproduce
		      // (para grabar keyframes y que el marcador "siga" al jugador).
		      try {
		        const active = fabricCanvas.getActiveObject?.() || null;
		        const keep = Boolean(active && active.data && safeText(active.data.kind) === 'player_marker' && active.data.track);
		        if (!keep) fabricCanvas.discardActiveObject?.();
		      } catch (e) { /* ignore */ }
		      selectedFxId = 0;
		      try { updateLayerPanel(); } catch (e) { /* ignore */ }
		      try { renderFxList(); } catch (e) { /* ignore */ }
		      try { renderDrawLayers(); } catch (e) { /* ignore */ }
		    });
	    video.addEventListener('pause', syncPlayButtons);
      video.addEventListener('pause', () => {
        // Si el usuario pausa durante un bound (play segmento), liberamos el rango para no "atrapar" el scrub.
        // El loop explícito se gestiona por separado.
        if (!loopActive) clipBoundActive = false;
      });
	    syncPlayButtons();

	    const markIn = () => {
	      const t = Number(video.currentTime) || 0;
	      if (inInput) inInput.value = String(t.toFixed(1));
        // Mantén el bound alineado para que play pare en OUT cuando esté definido.
        clipBoundStart = Math.max(0, t);
	      setStatus(`IN: ${fmtTime(t)}`);
	    };
	    const markOut = () => {
	      const t = Number(video.currentTime) || 0;
	      if (outInput) outInput.value = String(t.toFixed(1));
        clipBoundEnd = Math.max(0, t);
	      setStatus(`OUT: ${fmtTime(t)}`);
	    };
    btnIn?.addEventListener('click', markIn);
    btnOut?.addEventListener('click', markOut);

    // Corte base (trim) UI
    const setTrimInNow = () => {
      const t = clampToTrim(Number(video.currentTime) || 0);
      if (trimInInput) trimInInput.value = String(t.toFixed(1));
      setStatus(`Corte base IN: ${fmtTime(t)}`);
      scheduleTrimAutosave();
    };
    const setTrimOutNow = () => {
      const t = clampToTrim(Number(video.currentTime) || 0);
      if (trimOutInput) trimOutInput.value = String(t.toFixed(1));
      setStatus(`Corte base OUT: ${fmtTime(t)}`);
      scheduleTrimAutosave();
    };
    trimSetInBtn?.addEventListener('click', setTrimInNow);
    trimSetOutBtn?.addEventListener('click', setTrimOutNow);
    trimFromSegmentBtn?.addEventListener('click', () => {
      const a = Math.max(0, Number(inInput?.value || 0) || 0);
      const b = Math.max(0, Number(outInput?.value || 0) || 0);
      const start = Math.min(a, b);
      const end = Math.max(a, b);
      if (!end || end <= start) { setStatus('Primero define IN/OUT del segmento.', true); return; }
      if (trimInInput) trimInInput.value = String(start.toFixed(1));
      if (trimOutInput) trimOutInput.value = String(end.toFixed(1));
      if (trimEnabledToggle) trimEnabledToggle.checked = true;
      setStatus('Corte base: valores copiados desde IN/OUT.');
      saveTrim({ silent: true });
      enforceTrimPlayback();
    });
    trimClearBtn?.addEventListener('click', () => {
      if (trimEnabledToggle) trimEnabledToggle.checked = false;
      if (trimInInput) trimInInput.value = '0';
      if (trimOutInput) trimOutInput.value = '0';
      trimEnabled = false;
      trimInS = 0;
      trimOutS = 0;
      saveTrim({ silent: true });
      setStatus('Corte base limpiado.');
    });
    trimSaveBtn?.addEventListener('click', () => saveTrim());
    trimEnabledToggle?.addEventListener('change', () => saveTrim({ silent: true }));
    trimInInput?.addEventListener('change', scheduleTrimAutosave);
    trimOutInput?.addEventListener('change', scheduleTrimAutosave);

    // Shortcuts (tipo Sportscode básico): J/K/L, I/O, Space
    const isTypingTarget = (el) => {
      const tag = String(el?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
      if (el && el.isContentEditable) return true;
      return false;
    };
    const seekBy = (deltaSeconds) => {
      const cur = Number(video.currentTime) || 0;
      const dur = Number(video.duration);
      const maxT = Number.isFinite(dur) && dur > 0 ? dur : 1e12;
      const nextRaw = clamp(cur + (Number(deltaSeconds) || 0), 0, maxT);
      const next = clampToTrim(nextRaw);
      try { video.currentTime = next; } catch (e) { /* ignore */ }
      setStatus(`Seek: ${fmtTime(next)}`);
    };
    document.addEventListener('keydown', async (ev) => {
      if (!ev || ev.defaultPrevented) return;
      if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
      if (isTypingTarget(ev.target)) return;
      const k = String(ev.key || '');
      if (k === ' ' || k === 'Spacebar') {
        ev.preventDefault();
        if (video.paused) { try { await video.play(); } catch (e) { /* ignore */ } } else { try { video.pause(); } catch (e) { /* ignore */ } }
        syncPlayButtons();
        return;
      }
      if (k === 'i' || k === 'I') { ev.preventDefault(); markIn(); return; }
      if (k === 'o' || k === 'O') { ev.preventDefault(); markOut(); return; }
      if (k === 'k' || k === 'K') { ev.preventDefault(); try { video.pause(); } catch (e) { /* ignore */ } syncPlayButtons(); return; }
      if (k === 'j' || k === 'J') { ev.preventDefault(); seekBy(ev.shiftKey ? -5 : -2); return; }
      if (k === 'l' || k === 'L') { ev.preventDefault(); seekBy(ev.shiftKey ? 5 : 2); return; }
    }, { passive: false });

	    const loadImageFromDataUrl = (dataUrl) => new Promise((resolve, reject) => {
	      try {
	        const img = new Image();
	        img.onload = () => resolve(img);
	        img.onerror = (e) => reject(e);
	        img.src = String(dataUrl || '');
	      } catch (e) {
	        reject(e);
	      }
	    });

		    const snapshotPng = async () => {
		      const wasPlaying = !video.paused;
		      setStatus('PNG: capturando…', false, { flash: false });
		      try { if (wasPlaying) video.pause(); } catch (e) { /* ignore */ }
		      if (wasPlaying) await sleep(80);
		      const w = fabricCanvas.getWidth();
		      const h = fabricCanvas.getHeight();
		      const off = document.createElement('canvas');
		      off.width = w;
	      off.height = h;
			      const ctx = off.getContext('2d');
			      if (!ctx) return;
			      let baseDrawn = false;
			      if (!compatNoCorsApplied) {
			        try { baseDrawn = await drawVideoFrameSmart(ctx, video, w, h); } catch (e) { /* ignore */ }
			        if (baseDrawn && canvasLooksBlank(ctx, w, h)) baseDrawn = false;
			      }
			      if (!baseDrawn) {
			        try {
			          const dataUrl = await captureVideoFrameDataUrl({ maxW: Math.max(480, Math.min(1920, Math.round(w || 1280))) });
			          if (dataUrl) {
			            const img = await loadImageFromDataUrl(dataUrl);
		            try { ctx.drawImage(img, 0, 0, w, h); baseDrawn = true; } catch (e) { /* ignore */ }
		          }
		        } catch (e) { /* ignore */ }
		        if (baseDrawn && canvasLooksBlank(ctx, w, h)) baseDrawn = false;
		      }
		      if (!baseDrawn) {
		        try {
		          ctx.fillStyle = '#000';
		          ctx.fillRect(0, 0, w, h);
		        } catch (e) { /* ignore */ }
		        const msg = 'PNG: no se pudo capturar el frame del vídeo.\nSe exporta solo la pizarra (anotaciones).';
		        setStatus(msg, true);
		        const proceed = window.confirm('No se pudo capturar el frame del vídeo.\n\n¿Descargar igualmente? (saldrá solo la pizarra/anotaciones)');
		        if (!proceed) {
		          setStatus('PNG cancelado.', true);
		          if (wasPlaying) { try { await video.play(); } catch (e) { /* ignore */ } }
		          return;
		        }
		        try {
		          if (btnSnap) {
		            const old = safeText(btnSnap.textContent, 'PNG');
		            btnSnap.textContent = 'PNG ⚠︎';
		            window.setTimeout(() => { try { btnSnap.textContent = old; } catch (e2) { /* ignore */ } }, 1200);
		          }
		        } catch (e) { /* ignore */ }
		      }
		      try { renderFx(ctx, { width: w, height: h, nowS: Number(video.currentTime) || 0, forExport: true }); } catch (e) { /* ignore */ }
		      try { ctx.drawImage(canvasEl, 0, 0, w, h); } catch (e) { /* ignore */ }
		      off.toBlob((blob) => {
		        if (!blob) return;
	        downloadBlob(blob, `telestracion-${videoId || 'video'}.png`);
	      }, 'image/png');
	      if (wasPlaying) { try { await video.play(); } catch (e) { /* ignore */ } }
	    };
    btnSnap?.addEventListener('click', snapshotPng);

    // --- OCR dorsal (asistido): el usuario marca una ROI sobre el dorsal.
    const roiEl = document.getElementById('vs-roi');
    let dorsalMode = false;
    let roiDragging = false;
    let roiStart = null;

    const stageRect = () => {
      try { return stage.getBoundingClientRect(); } catch (e) { return null; }
    };

    const setRoiBox = (x0, y0, x1, y1) => {
      if (!roiEl) return;
      const left = Math.min(x0, x1);
      const top = Math.min(y0, y1);
      const w = Math.max(0, Math.abs(x1 - x0));
      const h = Math.max(0, Math.abs(y1 - y0));
      roiEl.style.left = `${left}px`;
      roiEl.style.top = `${top}px`;
      roiEl.style.width = `${w}px`;
      roiEl.style.height = `${h}px`;
      roiEl.style.display = (w >= 8 && h >= 8) ? 'block' : 'none';
    };

    const clearRoiBox = () => {
      if (!roiEl) return;
      roiEl.style.display = 'none';
      roiEl.style.width = '0px';
      roiEl.style.height = '0px';
      roiEl.style.left = '0px';
      roiEl.style.top = '0px';
    };

    const toggleDorsalMode = (force) => {
      const next = (typeof force === 'boolean') ? force : !dorsalMode;
      dorsalMode = next;
      roiDragging = false;
      roiStart = null;
      clearRoiBox();
      if (dorsalMode) setStatus('Dorsal OCR: arrastra un recuadro sobre el dorsal y suelta.', false);
    };

    btnDorsalOcr?.addEventListener('click', () => toggleDorsalMode());

    const roiFromStageToVideoPx = (roiStagePx) => {
      const rect = stageRect();
      if (!rect) return null;
      const vw = Number(video.videoWidth) || 0;
      const vh = Number(video.videoHeight) || 0;
      if (!vw || !vh) return null;
      const scaleX = vw / rect.width;
      const scaleY = vh / rect.height;
      return {
        x: Math.max(0, Math.round(roiStagePx.x * scaleX)),
        y: Math.max(0, Math.round(roiStagePx.y * scaleY)),
        w: Math.max(1, Math.round(roiStagePx.w * scaleX)),
        h: Math.max(1, Math.round(roiStagePx.h * scaleY)),
      };
    };

    const postDorsalOcr = async (roiPx) => {
      if (!dorsalOcrUrl) {
        setStatus('OCR dorsal: endpoint no configurado.', true);
        return;
      }
      const csrf = document.querySelector('#vs-csrf input[name=\"csrfmiddlewaretoken\"]')?.value || '';
      const timeS = Number(video.currentTime) || 0;
      try {
        setStatus('OCR dorsal…', false);
        const resp = await fetch(dorsalOcrUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
          body: JSON.stringify({ video_id: videoId, time_s: timeS, roi: roiPx }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) {
          const msg = data?.error || 'No se pudo hacer OCR del dorsal.';
          setStatus(msg, true);
          alert(msg);
          return;
        }
        const best = Number(data?.best || 0) || 0;
        const ranked = Array.isArray(data?.ranked) ? data.ranked : [];
        const own = Array.isArray(data?.own_matches) ? data.own_matches : [];
        const rival = Array.isArray(data?.rival_matches) ? data.rival_matches : [];

        let chosen = best;
        if (!chosen && ranked.length) chosen = Number(ranked[0]?.number || 0) || 0;

        // Confirmación rápida:
        // - En vídeo 640x360 el dorsal puede salir borroso. Si hay candidatos (ranked),
        //   permitimos confirmar el número con un prompt simple.
        const rankedNums = ranked.map((x) => Number(x?.number || 0) || 0).filter((n) => n > 0 && n < 100);
        const hasTwoDigits = rankedNums.some((n) => n >= 10);
        const bestIsSingle = chosen > 0 && chosen < 10;
        const shouldConfirm = (!chosen) || (rankedNums.length >= 2 && hasTwoDigits && bestIsSingle && !own.length && !rival.length);
        if (shouldConfirm) {
          const hint = rankedNums.slice(0, 6).join(', ');
          const manual = prompt(`Confirma dorsal (candidatos: ${hint || '—'}):`, chosen ? String(chosen) : '');
          const manualNum = Number(String(manual || '').trim()) || 0;
          if (!manualNum) { setStatus('OCR dorsal cancelado.', true); return; }
          chosen = manualNum;
        }

        const label = (() => {
          const hitR = rival && rival.length ? rival[0] : null;
          const hitO = own && own.length ? own[0] : null;
          const name = hitR?.name || hitO?.name || '';
          return name ? `#${chosen} · ${name}` : `#${chosen}`;
        })();

        const labelEl = document.getElementById('vs-event-label');
        if (labelEl && (!safeText(labelEl.value) || safeText(labelEl.value).startsWith('#'))) {
          labelEl.value = label;
        }
        setStatus(`Dorsal: ${label}`, false);
      } catch (e) {
        setStatus('Error en OCR dorsal.', true);
        alert('Error en OCR dorsal.');
      }
    };

    const onRoiPointerDown = (ev) => {
      if (!dorsalMode) return;
      const rect = stageRect();
      if (!rect) return;
      ev.preventDefault();
      ev.stopPropagation();
      roiDragging = true;
      const x = clamp((ev.clientX - rect.left), 0, rect.width);
      const y = clamp((ev.clientY - rect.top), 0, rect.height);
      roiStart = { x, y };
      setRoiBox(x, y, x, y);
      try { stage.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
    };
    const onRoiPointerMove = (ev) => {
      if (!dorsalMode || !roiDragging || !roiStart) return;
      const rect = stageRect();
      if (!rect) return;
      ev.preventDefault();
      ev.stopPropagation();
      const x = clamp((ev.clientX - rect.left), 0, rect.width);
      const y = clamp((ev.clientY - rect.top), 0, rect.height);
      setRoiBox(roiStart.x, roiStart.y, x, y);
    };
    const onRoiPointerUp = (ev) => {
      if (!dorsalMode || !roiDragging || !roiStart) return;
      const rect = stageRect();
      if (!rect) return;
      ev.preventDefault();
      ev.stopPropagation();
      roiDragging = false;
      const x = clamp((ev.clientX - rect.left), 0, rect.width);
      const y = clamp((ev.clientY - rect.top), 0, rect.height);
      const left = Math.min(roiStart.x, x);
      const top = Math.min(roiStart.y, y);
      const w = Math.abs(x - roiStart.x);
      const h = Math.abs(y - roiStart.y);
      roiStart = null;
      if (w < 10 || h < 10) { clearRoiBox(); return; }
      const roiVideoPx = roiFromStageToVideoPx({ x: left, y: top, w, h });
      clearRoiBox();
      toggleDorsalMode(false);
      if (!roiVideoPx) {
        setStatus('OCR dorsal: el vídeo aún no está listo (metadata).', true);
        return;
      }
      postDorsalOcr(roiVideoPx);
    };

    // Capturamos en fase capture para no interferir con Fabric/Canvas.
    stage.addEventListener('pointerdown', onRoiPointerDown, true);
    stage.addEventListener('pointermove', onRoiPointerMove, true);
    stage.addEventListener('pointerup', onRoiPointerUp, true);
    stage.addEventListener('pointercancel', onRoiPointerUp, true);

    document.addEventListener('keydown', (ev) => {
      if (!ev || ev.defaultPrevented) return;
      if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const tag = String((ev.target && ev.target.tagName) || '').toLowerCase();
      const isTyping = tag === 'input' || tag === 'textarea' || tag === 'select' || (ev.target && ev.target.isContentEditable);
      if (isTyping) return;
      const k = String(ev.key || '').toLowerCase();
      if (k === 'd') {
        ev.preventDefault();
        toggleDorsalMode();
      }
      if (k === 'delete' || k === 'backspace') {
        // Borrar capa/efecto seleccionado (dibujo o FX) con teclado.
        const did = deleteCurrentLayer({ confirm: false });
        if (did) {
          ev.preventDefault();
          try { ev.stopPropagation?.(); } catch (e) { /* ignore */ }
        }
      }
      if (k === '[' || k === ']') {
        // Atajos tipo KlipDraw: ajustar IN/OUT de la capa seleccionada al playhead.
        const target = currentLayerTarget();
        if (!target) return;
        ev.preventDefault();
        const now = Number(video.currentTime) || 0;
        if (k === '[') {
          if (target.type === 'fx') {
            target.fx.t_in_s = now;
            renderFxList();
          } else {
            ensureLayerData(target.obj);
            target.obj.data.t_in_s = now;
            pushHistory();
          }
          updateLayerPanel();
          setStatus('IN=Ahora');
        } else {
          if (target.type === 'fx') {
            target.fx.t_out_s = now;
            renderFxList();
          } else {
            ensureLayerData(target.obj);
            target.obj.data.t_out_s = now;
            pushHistory();
          }
          updateLayerPanel();
          setStatus('OUT=Ahora');
        }
      }
      if (k === 'escape') {
        // Cancelar borrador de área.
        if (tool === 'area') {
          try { if (areaDraftPolyline) fabricCanvas.remove(areaDraftPolyline); } catch (e) { /* ignore */ }
          areaDraftPolyline = null;
          areaDraftPoints = [];
          setStatus('Área cancelada.');
        }
      }
    }, { passive: false });

			    const captureVideoFrameDataUrl = async ({ maxW } = {}) => {
		      const tryLocal = async () => {
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
		          const ok = await drawVideoFrameSmart(ctx, video, w, h);
		          if (!ok) return null;
		          if (canvasLooksBlank(ctx, w, h)) return null;
		          return off.toDataURL('image/png');
		        } catch (e) {
		          return null;
		        }
		      };

		      const tryServer = async () => {
		        try {
		          if (!frameCaptureUrl || !videoId) return null;
		          const timeS = Math.max(0, Number(video.currentTime) || 0);
	          const w = Number(fabricCanvas.getWidth?.()) || 0;
	          const hint = Number(maxW) || 0;
	          const desired = hint || (w ? Math.round(w) : 1280);
	          const payload = { video_id: videoId, time_s: timeS, max_w: Math.max(480, Math.min(1920, desired)) };
	          const resp = await fetch(frameCaptureUrl, {
	            method: 'POST',
	            credentials: 'same-origin',
	            cache: 'no-store',
	            headers: { 'content-type': 'application/json' },
	            body: JSON.stringify(payload),
	          });
		          const data = await resp.json().catch(() => ({}));
		          if (!resp.ok || !data?.ok) {
		            const msg = safeText(data?.error, `HTTP ${resp.status || 0}`) || 'error';
		            setStatus(`No se pudo capturar frame en servidor.\n${msg}`, true);
		            try {
		              window.__vsLastFrameCapture = { ok: false, status: resp.status || 0, error: msg, at: Date.now(), payload };
		            } catch (e) { /* ignore */ }
		            return null;
		          }
		          const img = safeText(data?.image_data, '');
		          if (!img || !img.startsWith('data:image/')) {
		            setStatus('Captura servidor inválida (sin imagen).', true);
		            try {
		              window.__vsLastFrameCapture = { ok: false, status: resp.status || 200, error: 'sin imagen', at: Date.now(), payload, dataKeys: Object.keys(data || {}) };
		            } catch (e) { /* ignore */ }
		            return null;
		          }
		          try {
		            window.__vsLastFrameCapture = { ok: true, status: resp.status || 200, at: Date.now(), payload, len: img.length, prefix: img.slice(0, 28) };
		          } catch (e) { /* ignore */ }
		          return img || null;
		        } catch (e) {
		          setStatus(`No se pudo capturar frame en servidor.\n${safeText(e?.message, 'error')}`, true);
		          try {
		            window.__vsLastFrameCapture = { ok: false, status: 0, error: safeText(e?.message, 'error'), at: Date.now() };
		          } catch (e2) { /* ignore */ }
		          return null;
		        }
		      };

		      // iOS/Safari: prioriza captura en servidor (evita frames negros).
		      if (isIOS) {
		        const server = await tryServer();
		        if (server) return server;
		      }
		      const local = await tryLocal();
		      if (local) return local;
		      return await tryServer();
		    };

	    // Freeze "modo trabajo": bloquea la reproducción/click-to-play para poder dibujar encima sin que el vídeo arranque
	    // (especialmente en Safari, donde al tocar el <video> se reanuda).
	    let freezeHoldOn = false;
	    let freezeHoldPrevControls = null;

	    let stageFreezeSrc = '';
	    let stageFreezeOn = false;
	    const getActiveFreezeLayerAt = (nowS) => {
	      const t = Number.isFinite(nowS) ? Number(nowS) : (Number(video.currentTime) || 0);
	      const layers = Array.isArray(fxState.layers) ? fxState.layers : [];
	      let found = null;
	      for (const layer of layers) {
	        if (safeText(layer?.kind) !== 'freeze') continue;
	        const alpha = computeTimedAlpha(layer, t);
	        if (alpha <= 0.001) continue;
	        found = layer;
	      }
	      return found;
	    };
	    const setStageFreezeBackground = (dataUrl) => {
	      if (!freezeBgEl) return;
	      const src = safeText(dataUrl, '');
	      const on = Boolean(src);
	      if (on === stageFreezeOn && (!on || src === stageFreezeSrc)) return;
	      stageFreezeOn = on;
	      stageFreezeSrc = src;
	      try {
	        if (on) {
	          freezeBgEl.src = src;
	          freezeBgEl.style.display = 'block';
	        } else {
	          try { freezeBgEl.removeAttribute('src'); } catch (e) { /* ignore */ }
	          freezeBgEl.style.display = 'none';
	        }
	      } catch (e) { /* ignore */ }
	      try {
	        if (on) {
	          video.style.opacity = '0';
	          video.style.pointerEvents = 'none';
	        } else {
	          video.style.opacity = '';
	          if (!freezeHoldOn) video.style.pointerEvents = '';
	        }
	      } catch (e) { /* ignore */ }
	    };
	    const syncFreezeBackground = (nowS) => {
	      if (!freezeBgEl) return;
	      const active = getActiveFreezeLayerAt(nowS);
	      const src = safeText(active?.image_data, '');
	      setStageFreezeBackground(src);
	    };
	    const setFreezeHold = (on) => {
	      freezeHoldOn = Boolean(on);
	      try {
	        btnFreeze?.classList?.toggle?.('primary', freezeHoldOn);
	        if (btnFreeze) btnFreeze.textContent = freezeHoldOn ? 'Freeze ✓' : 'Freeze';
      } catch (e) { /* ignore */ }
      try {
        if (freezeHoldOn) {
          if (freezeHoldPrevControls === null) freezeHoldPrevControls = Boolean(video?.controls);
          try { video.pause?.(); } catch (e) { /* ignore */ }
          try { video.controls = false; } catch (e) { /* ignore */ }
          try { video.style.pointerEvents = 'none'; } catch (e) { /* ignore */ }
        } else {
          try { if (freezeHoldPrevControls !== null) video.controls = Boolean(freezeHoldPrevControls); } catch (e) { /* ignore */ }
          freezeHoldPrevControls = null;
          try { video.style.pointerEvents = ''; } catch (e) { /* ignore */ }
        }
      } catch (e) { /* ignore */ }
    };

	    try {
	      video.addEventListener('play', () => {
	        if (!freezeHoldOn) return;
	        try { video.pause?.(); } catch (e) { /* ignore */ }
	      }, { passive: true });
      video.addEventListener('click', (ev) => {
        if (!freezeHoldOn) return;
        try { ev.preventDefault?.(); } catch (e) { /* ignore */ }
        try { ev.stopPropagation?.(); } catch (e) { /* ignore */ }
        try { video.pause?.(); } catch (e) { /* ignore */ }
      }, { passive: false });
    } catch (e) { /* ignore */ }

		    btnFreeze?.addEventListener('click', async () => {
		      if (freezeHoldOn) {
		        setFreezeHold(false);
		        try { syncFreezeBackground(); } catch (e) { /* ignore */ }
		        setStatus('Freeze desactivado.');
		        return;
		      }
		      const inS = Number(inInput?.value || 0) || 0;
		      const outS = Number(outInput?.value || 0) || 0;
		      if (!outS || outS <= inS + 0.05) {
		        setStatus('Freeze: define IN/OUT (rango del clip).', true);
		        return;
		      }
		      const img = await captureVideoFrameDataUrl({ maxW: 1280 });
		      if (!img) {
		        setStatus('No se pudo capturar freeze.', true);
		        return;
		      }
	      const now = Number(video.currentTime) || 0;
	      const layer = {
	        id: fxSeq++,
	        ...seedLayerDataNow({ t_in_s: inS, t_out_s: outS, fade_in_ms: 120, fade_out_ms: 120 }),
	        kind: 'freeze',
	        image_data: img,
	      };
	      const prevLayers = Array.isArray(fxState.layers) ? fxState.layers : [];
	      const cleaned = prevLayers.filter((x) => {
	        if (safeText(x?.kind) !== 'freeze') return true;
	        const a = Number(x?.t_in_s) || 0;
	        const b = Number(x?.t_out_s) || 0;
	        return !(Math.abs(a - inS) < 0.02 && Math.abs(b - outS) < 0.02);
	      });
	      fxState.layers = [...cleaned, layer].slice(0, 80);
	      selectedFxId = layer.id;
	      renderFxList();
	      updateLayerPanel();
	      setFreezeHold(true);
	      try { syncFreezeBackground(now); } catch (e) { /* ignore */ }
	      setStatus(`Freeze creado (${fmtTimeShort(inS)} → ${fmtTimeShort(outS)}).`);
	    });

	    btnStillClip?.addEventListener('click', async () => {
	      if (!clipSaveUrl || !videoId) { setStatus('Foto→Clip no disponible.', true); return; }
	      const wasPlaying = !video.paused;
	      try { if (wasPlaying) video.pause(); } catch (e) { /* ignore */ }
	      if (wasPlaying) await sleep(80);

	      const hasDraw = (() => {
	        try { return (fabricCanvas.getObjects?.() || []).length > 0; } catch (e) { return false; }
	      })();
	      const hasFx = (() => {
	        try { return (Array.isArray(fxState.layers) ? fxState.layers : []).length > 0; } catch (e) { return false; }
	      })();
	      if (hasDraw || hasFx) {
	        const ok = window.confirm('Esto creará un nuevo clip de foto y reemplazará las anotaciones/FX actuales.\n\n¿Continuar?');
	        if (!ok) { if (wasPlaying) { try { await video.play(); } catch (e) { /* ignore */ } } return; }
	      }

	      const now = Math.max(0, Number(video.currentTime) || 0);
	      const dur = Number.isFinite(Number(video.duration)) ? Number(video.duration) : 0;
	      const defaultDur = 3.0;
	      let inS = now;
	      let outS = now + defaultDur;
	      if (dur > 0) outS = Math.min(outS, dur);
	      if (outS <= inS + 0.05) outS = inS + 0.25;

	      setStatus('Foto→Clip: capturando…', false, { flash: false });
	      const img = await captureVideoFrameDataUrl({ maxW: 1280 });
	      if (!img) {
	        setStatus('Foto→Clip: no se pudo capturar el frame.', true);
	        if (wasPlaying) { try { await video.play(); } catch (e) { /* ignore */ } }
	        return;
	      }

	      // Limpia overlays actuales para evitar “arrastrar” anotaciones anteriores.
	      try {
	        fabricCanvas.clear();
	        pushHistory();
	        fabricCanvas.renderAll();
	      } catch (e) { /* ignore */ }
	      try {
	        fxState.layers = [];
	        selectedFxId = 0;
	        reseedFxSeq();
	        renderFxList();
	      } catch (e) { /* ignore */ }
	      try { updateLayerPanel(); } catch (e) { /* ignore */ }
	      try { renderDrawLayers(); } catch (e) { /* ignore */ }

	      // Rango del clip still
	      if (inInput) inInput.value = String(inS.toFixed(1));
	      if (outInput) outInput.value = String(outS.toFixed(1));
	      try { video.currentTime = inS; } catch (e) { /* ignore */ }

	      const layer = {
	        id: fxSeq++,
	        ...seedLayerDataNow({ t_in_s: inS, t_out_s: outS, fade_in_ms: 0, fade_out_ms: 0 }),
	        kind: 'freeze',
	        image_data: img,
	        mute: true,
	      };
	      fxState.layers = [...(Array.isArray(fxState.layers) ? fxState.layers : []), layer].slice(0, 80);
	      selectedFxId = layer.id;
	      renderFxList();
	      updateLayerPanel();

	      // Metadatos del clip
	      try {
	        if (clipTitleInput) clipTitleInput.value = `Foto · ${fmtTimeShort(inS)}`.slice(0, 180);
	        if (clipTagsInput) clipTagsInput.value = '';
	        if (clipNotesInput) clipNotesInput.value = '';
	      } catch (e) { /* ignore */ }

	      setFreezeHold(true);
	      try { syncFreezeBackground(inS); } catch (e) { /* ignore */ }

	      // Crea el clip en servidor (como iMovie: ya existe y luego se edita).
	      try {
	        await saveClip({ forceNew: true });
	        setStatus('Foto→Clip creado. Edita encima y pulsa “Actualizar” para guardar cambios.');
	      } catch (e) {
	        setStatus('Foto→Clip: no se pudo crear el clip.', true);
	      } finally {
	        if (wasPlaying) { try { await video.play(); } catch (e) { /* ignore */ } }
	      }
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
	    let exportAudioGain = null;
	    let exportAudioWired = false;
    let recLastProgressAt = 0;
	    let lastExportAssetId = 0;
	    let lastExportShareUrl = '';
	    let lastFailedExport = null;

      const triggerDownload = (url, { filename = '' } = {}) => {
        const href = safeText(url, '');
        if (!href) return false;
        try {
          const a = document.createElement('a');
          a.href = href;
          a.rel = 'noopener';
          // En Safari (Mac), `target=_blank` a veces abre el player en una pestaña nueva.
          // Preferimos navegar en la misma pestaña para que `Content-Disposition: attachment`
          // se traduzca en descarga “normal”.
          if (filename) a.download = safeText(filename, '').slice(0, 180);
          a.style.display = 'none';
          document.body.appendChild(a);
          a.click();
          a.remove();
          return true;
        } catch (e) {
          try {
            window.location.assign(href);
            return true;
          } catch (e2) { /* ignore */ }
        }
        return false;
      };

      const tryCopy = async (text) => {
        try {
          const value = safeText(text, '');
          if (!value) return false;
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(value);
            return true;
          }
        } catch (e) { /* ignore */ }
        return false;
      };

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
	      recLastProgressAt = 0;
		      recDestination = 'download';
		      recUploadMeta = null;
		      try { if (exportAudioGain && exportAudioGain.gain) exportAudioGain.gain.value = 1; } catch (e) { /* ignore */ }
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
	      lastFailedExport = { blob, title: safeTitle, clipId: Number(clipId) || 0 };
	      if (btnExportRetry) btnExportRetry.hidden = true;

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
		                const warn = safeText(data?.warning, '');
		                lastExportAssetId = Number(data?.id) || lastExportAssetId || 0;
		                lastExportShareUrl = url;
		                lastFailedExport = null;
		                if (btnExportRetry) btnExportRetry.hidden = true;
		                try {
		                  if (navigator.clipboard?.writeText) {
		                    await navigator.clipboard.writeText(url);
		                    setStatus(warn ? `Export subido. Link copiado. ${warn}` : 'Export subido. Link copiado.');
		                  } else {
		                    setStatus(warn ? `Export subido. Copia el link. ${warn}` : 'Export subido. Copia el link.');
		                    window.prompt('Copia este enlace:', url);
		                  }
		                } catch (e) {
		                  window.prompt('Copia este enlace:', url);
		                }
	                refreshShareLinks();
	                resolve(url);
	                return;
	              }
	              setStatus(data?.error || 'No se pudo subir export.', true);
	              if (btnExportRetry) btnExportRetry.hidden = false;
	              resolve(null);
	            } catch (e) {
	              setStatus('No se pudo subir export.', true);
	              if (btnExportRetry) btnExportRetry.hidden = false;
	              resolve(null);
	            }
	          });
	          xhr.addEventListener('error', () => {
	            setStatus('Error de red al subir export.', true);
	            if (btnExportRetry) btnExportRetry.hidden = false;
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
      recStartAt = Number(video.currentTime) || 0;

      recCanvas = document.createElement('canvas');
      recCanvas.width = w;
      recCanvas.height = h;
      recCtx = recCanvas.getContext('2d', { alpha: false });
      if (!recCtx) return;

	      const q = safeText(qualitySelect?.value, 'med');
	      let fps = Number(safeText(fpsSelect?.value, '')) || 0;
	      if (!fps) fps = q === 'low' ? 24 : 30;
	      fps = clamp(fps, 12, 60);
	      const bps = q === 'high' ? 8_000_000 : (q === 'low' ? 2_200_000 : 4_000_000);
      const canvasStream = recCanvas.captureStream(fps);
	      let audioTracks = [];
	      const includeAudio = audioToggle ? Boolean(audioToggle.checked) : true;
	      if (includeAudio) {
	        try {
	          const Ctx = window.AudioContext || window.webkitAudioContext;
	          if (Ctx) {
	            if (!exportAudioCtx) exportAudioCtx = new Ctx();
	            try { await exportAudioCtx.resume(); } catch (e) { /* ignore */ }
	            if (!exportAudioDest) exportAudioDest = exportAudioCtx.createMediaStreamDestination();
	            if (!exportAudioSource) exportAudioSource = exportAudioCtx.createMediaElementSource(video);
	            if (!exportAudioGain) exportAudioGain = exportAudioCtx.createGain();
	            if (!exportAudioWired) {
	              try { exportAudioSource.connect(exportAudioCtx.destination); } catch (e) { /* ignore */ }
	              try { exportAudioSource.connect(exportAudioGain); } catch (e) { /* ignore */ }
	              try { exportAudioGain.connect(exportAudioDest); } catch (e) { /* ignore */ }
	              exportAudioWired = true;
	            }
	            try { exportAudioGain.gain.value = 1; } catch (e) { /* ignore */ }
	            audioTracks = exportAudioDest.stream.getAudioTracks?.() || [];
	          }
	        } catch (e) { audioTracks = []; }
	        if (!audioTracks.length) {
	          try {
	            const vStream = typeof video.captureStream === 'function' ? video.captureStream() : (typeof video.mozCaptureStream === 'function' ? video.mozCaptureStream() : null);
	            audioTracks = vStream ? (vStream.getAudioTracks?.() || []) : [];
	          } catch (e) { /* ignore */ }
	        }
	      }
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
      const isMp4 = String(mime || '').toLowerCase().includes('mp4');
      if (!isMp4) {
        if (safeText(recDestination) === 'upload') {
          setStatus('Tu navegador exporta en WebM; al subir se intentará convertir a MP4.');
        } else {
          setStatus('Tu navegador exporta en WebM. Para MP4 usa "Export/Compartir".');
        }
      }

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
	          if (includeAudio && exportAudioGain && exportAudioGain.gain) {
	            const nowS = Number(video.currentTime) || 0;
	            const fr = getActiveFreezeLayerAt(nowS);
	            const wantMute = Boolean(fr && fr.mute);
	            exportAudioGain.gain.value = wantMute ? 0 : 1;
	          }
	        } catch (e) { /* ignore */ }
	        try {
	          recCtx.fillStyle = '#000';
	          recCtx.fillRect(0, 0, w, h);
	          try { recCtx.drawImage(video, 0, 0, w, h); } catch (e) { /* ignore */ }
          try { renderFx(recCtx, { width: w, height: h, nowS: Number(video.currentTime) || 0, forExport: true }); } catch (e) { /* ignore */ }
          try { recCtx.drawImage(canvasEl, 0, 0, w, h); } catch (e) { /* ignore */ }
        } catch (e) { /* ignore */ }
        if (stopAt != null && recStartAt != null) {
          const nowS = Number(video.currentTime) || 0;
          const total = Math.max(0.01, Number(stopAt) - Number(recStartAt));
          const done = clamp((nowS - Number(recStartAt)) / total, 0, 1);
          if (!recLastProgressAt || nowS - recLastProgressAt >= 0.5) {
            recLastProgressAt = nowS;
            setStatus(`Grabando… ${Math.round(done * 100)}%`);
          }
        }
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

	    const exportMp4ServerForCurrentSegment = async ({ disableEl = null } = {}) => {
	      if (!exportServerUrl) {
	        setStatus('No hay endpoint para MP4 server.', true);
	        return null;
	      }
	      const a = Number(inInput?.value || 0) || 0;
	      const b = Number(outInput?.value || 0) || 0;
	      const start = Math.max(0, Math.min(a, b));
	      const end = Math.max(a, b);
	      if (!end || end <= start) {
	        setStatus('Define IN/OUT primero.', true);
	        return null;
	      }
	      const baseTitle = safeText(clipTitleInput?.value, '').slice(0, 180);
	      const coll = safeText(clipCollectionInput?.value, '').slice(0, 120);
	      const t = baseTitle ? (coll ? `${baseTitle} · ${coll}` : baseTitle) : `Clip ${fmtTimeShort(start)}-${fmtTimeShort(end)}`;

	      try {
	        if (disableEl) disableEl.disabled = true;
	        if (btnExportServer) btnExportServer.disabled = true;
	        setStatus('Generando MP4 en servidor…');
	        const payload = { video_id: videoId || 0, in_s: start, out_s: end, title: t };
	        if (activeClipId) payload.clip_id = activeClipId;
	        const resp = await fetch(exportServerUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	          body: JSON.stringify(payload),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok || !data?.url) {
	          setStatus(data?.error || 'No se pudo exportar MP4 en servidor.', true);
	          return null;
	        }
	        const url = String(data.url);
	        const downloadUrl = String(data.download_url || url);
	        lastExportAssetId = Number(data?.id) || lastExportAssetId || 0;
	        lastExportShareUrl = url;
	        triggerDownload(downloadUrl);
	        try { await tryCopy(downloadUrl); } catch (e) { /* ignore */ }
	        setStatus('MP4 listo. Descargando…');
	        refreshShareLinks();
	        return data;
	      } catch (e) {
	        setStatus('Error exportando MP4 en servidor.', true);
	        return null;
	      } finally {
	        if (btnExportServer) btnExportServer.disabled = false;
	        if (disableEl) disableEl.disabled = false;
	      }
	    };

	    btnExportServer?.addEventListener('click', async () => {
	      await exportMp4ServerForCurrentSegment({ disableEl: btnExportServer });
	    });

      clipSaveMp4Btn?.addEventListener('click', async () => {
        try {
          clipSaveMp4Btn.disabled = true;
          setStatus('Guardando clip…');
          const saved = await saveClip({ forceNew: true });
          if (!saved) return;
          // `saveClip` deja el clip recién guardado como activo (activeClipId), así el MP4 queda ligado al clip.
          await exportMp4ServerForCurrentSegment({ disableEl: clipSaveMp4Btn });
        } catch (e) {
          setStatus('No se pudo completar Guardar+MP4.', true);
        } finally {
          clipSaveMp4Btn.disabled = false;
        }
      });

	    const updatePlaylistExportAvailability = () => {
	      if (!btnExportServerPlaylist) return;
	      const okTeam = Number(teamId || 0) > 0;
	      const okClips = selectedClipIds.size >= 2;
	      btnExportServerPlaylist.disabled = !(okTeam && okClips && exportServerPlaylistUrl);
	    };

	    btnExportServerPlaylist?.addEventListener('click', async () => {
	      if (!exportServerPlaylistUrl) {
	        setStatus('No hay endpoint para MP4 playlist.', true);
	        return;
	      }
	      if (!teamId) {
	        setStatus('Asigna el vídeo a un equipo antes de exportar playlist.', true);
	        return;
	      }
	      const ids = Array.from(selectedClipIds.values()).map((x) => Number(x) || 0).filter((x) => x > 0);
	      if (ids.length < 2) {
	        setStatus('Selecciona al menos 2 clips.', true);
	        return;
	      }
	      const t = `Playlist · ${ids.length} clips`;
	      try {
	        btnExportServerPlaylist.disabled = true;
	        setStatus('Generando MP4 playlist en servidor…');
	        const resp = await fetch(exportServerPlaylistUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	          body: JSON.stringify({ video_id: videoId || 0, clip_ids: ids, title: t }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok || !data?.url) {
	          setStatus(data?.error || 'No se pudo exportar MP4 playlist en servidor.', true);
	          return;
	        }
	        const url = String(data.url);
	        const downloadUrl = String(data.download_url || url);
	        lastExportAssetId = Number(data?.id) || lastExportAssetId || 0;
	        lastExportShareUrl = url;
          triggerDownload(downloadUrl);
          try { await tryCopy(downloadUrl); } catch (e) { /* ignore */ }
          setStatus('MP4 playlist listo. Descargando…');
	        refreshShareLinks();
	      } catch (e) {
	        setStatus('Error exportando MP4 playlist en servidor.', true);
	      } finally {
	        updatePlaylistExportAvailability();
	      }
	    });

	    btnExportRetry?.addEventListener('click', async () => {
	      if (!lastFailedExport || !lastFailedExport.blob) {
	        setStatus('No hay export pendiente de reintento.', true);
	        return;
	      }
	      await uploadExportBlob(lastFailedExport.blob, { title: lastFailedExport.title, clipId: lastFailedExport.clipId });
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

    let projectsCache = [];
    const refreshProjects = async () => {
      if (!projectsUrl || !videoId) return;
      try {
        const resp = await fetch(`${projectsUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        projectsCache = Array.isArray(data?.items) ? data.items : [];
        renderProjects(projectsCache);
        try { renderTimelineProjectSelect(projectsCache); } catch (e) { /* ignore */ }
      } catch (e) {
        projectsCache = [];
        renderProjects([]);
        try { renderTimelineProjectSelect([]); } catch (e2) { /* ignore */ }
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
    // refreshProjects() se dispara más abajo, cuando el Timeline editor ya ha definido sus helpers.

	    // Clips (server)
	    let activeClipId = 0;
	    let clipsCache = [];
	    let timelineCache = [];
	    let playlistActive = false;
	    let playlistIds = [];
	    let playlistIndex = 0;
	    let playlistBusy = false;
	    const selectedClipIds = new Set();
	    const reviewedClipIds = new Set();
	    const reviewedEventIds = new Set();
	    const reviewFilterState = { clipsOnlyUnreviewed: false, eventsOnlyUnreviewed: false };
	    const thumbCache = new Map();
	    const thumbQueue = [];
	    const thumbQueued = new Set();
	    let thumbBusy = false;
	    let thumbObserver = null;
	    const thumbVideo = document.createElement('video');
	    try {
	      const baseSrc = safeText(video.currentSrc, '') || safeText(video.querySelector('source')?.src, '');
	      if (baseSrc) thumbVideo.src = baseSrc;
	      thumbVideo.crossOrigin = 'anonymous';
	      thumbVideo.muted = true;
	      thumbVideo.playsInline = true;
	      thumbVideo.preload = 'auto';
	    } catch (e) { /* ignore */ }
	    const clipFilterState = { q: '', collection: '' };
	    const clipNorm = (value) => safeText(value, '').toLowerCase();
	    const escHtml = (value) => safeText(value, '')
	      .replaceAll('&', '&amp;')
	      .replaceAll('<', '&lt;')
	      .replaceAll('>', '&gt;')
	      .replaceAll('"', '&quot;')
	      .replaceAll("'", '&#39;');

	    const refreshReviewState = async () => {
	      if (!reviewUrl || !videoId) return;
	      try {
	        const resp = await fetch(`${reviewUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        reviewedClipIds.clear();
	        reviewedEventIds.clear();
	        (Array.isArray(data?.clips) ? data.clips : []).forEach((id) => { const n = Number(id) || 0; if (n > 0) reviewedClipIds.add(n); });
	        (Array.isArray(data?.events) ? data.events : []).forEach((id) => { const n = Number(id) || 0; if (n > 0) reviewedEventIds.add(n); });
	      } catch (e) {
	        reviewedClipIds.clear();
	        reviewedEventIds.clear();
	      }
	    };

		    // Timeline editor (beta) - v2 (FX por clip + export servidor)
		    const voiceoversUrl = safeText(document.getElementById('vs-voiceovers-url')?.value);
		    const voiceoverUploadUrl = safeText(document.getElementById('vs-voiceover-upload-url')?.value);
		    const voiceoverDeleteUrl = safeText(document.getElementById('vs-voiceover-delete-url')?.value);
		    const musicUrl = safeText(document.getElementById('vs-music-url')?.value);
		    const musicUploadUrl = safeText(document.getElementById('vs-music-upload-url')?.value);
		    const musicDeleteUrl = safeText(document.getElementById('vs-music-delete-url')?.value);
		    const voiceoverSelect = document.getElementById('vs-voiceover-select');
			    const voiceoverRecordBtn = document.getElementById('vs-voiceover-record');
			    const voiceoverDeleteBtn = document.getElementById('vs-voiceover-delete');
			    const voiceoverVolInput = document.getElementById('vs-voiceover-vol');
			    const videoVolInput = document.getElementById('vs-video-vol');
			    const musicSelect = document.getElementById('vs-music-select');
			    const musicFileInput = document.getElementById('vs-music-file');
			    const musicUploadBtn = document.getElementById('vs-music-upload');
			    const musicDeleteBtn = document.getElementById('vs-music-delete');
			    const musicVolInput = document.getElementById('vs-music-vol');
			    const audioNormalizeToggle = document.getElementById('vs-audio-normalize');
			    const audioLimiterToggle = document.getElementById('vs-audio-limiter');
			    const voiceoverOffsetInput = document.getElementById('vs-voiceover-offset');
			    const voiceoverDuckingToggle = document.getElementById('vs-voiceover-ducking');
			    const voiceoverDuckStrengthInput = document.getElementById('vs-voiceover-duck-strength');

		    let tlItems = [];
		    let tlLastLoadedProjectId = 0;
		    let tlEditingIdx = -1;
		    let tlActiveExportJobId = 0;
		    let tlExportPollToken = 0;

	    const tlNum = (v, d = 0) => {
	      try {
	        if (v == null || v === '') return Number(d) || 0;
	        const n = Number(v);
	        return Number.isFinite(n) ? n : (Number(d) || 0);
	      } catch (e) {
	        return Number(d) || 0;
	      }
	    };
	    const tlClamp = (v, a, b) => Math.max(a, Math.min(b, Number(v) || 0));

		    const tlNormalizeItem = (raw) => {
		      if (!raw || typeof raw !== 'object') return null;
		      const clipId = Number(raw.clip_id || raw.id || raw.clip) || 0;
		      if (!clipId) return null;
		      const speed = tlClamp(tlNum(raw.speed, 1), 0.1, 4);
		      const spA = tlClamp(tlNum(raw.speed_start, speed), 0.1, 4);
		      const spB = tlClamp(tlNum(raw.speed_end, spA), 0.1, 4);
		      const fadeIn = tlClamp(tlNum(raw.fade_in, 0), 0, 2);
		      const fadeOut = tlClamp(tlNum(raw.fade_out, 0), 0, 2);
		      const inS = (raw.in_s != null && raw.in_s !== '') ? Math.max(0, tlNum(raw.in_s, 0)) : null;
		      const outS = (raw.out_s != null && raw.out_s !== '') ? Math.max(0, tlNum(raw.out_s, 0)) : null;
		      return {
		        clip_id: clipId,
		        in_s: inS,
		        out_s: outS,
		        speed,
		        speed_start: spA,
		        speed_end: spB,
		        fade_in: fadeIn,
		        fade_out: fadeOut,
		      };
		    };

		    const showDebug = async () => {
		      const info = [];
		      try { info.push(`videoId=${Number(videoId) || 0}`); } catch (e) { /* ignore */ }
		      try { info.push(`t=${(Number(video.currentTime) || 0).toFixed(3)}s`); } catch (e) { /* ignore */ }
		      try { info.push(`readyState=${Number(video.readyState) || 0}`); } catch (e) { /* ignore */ }
		      try { info.push(`dur=${Number.isFinite(video.duration) ? video.duration.toFixed(3) : 'n/a'}`); } catch (e) { /* ignore */ }
		      try { info.push(`vw×vh=${Number(video.videoWidth) || 0}×${Number(video.videoHeight) || 0}`); } catch (e) { /* ignore */ }
		      try { info.push(`stage=${Math.round(stage?.getBoundingClientRect?.().width || 0)}×${Math.round(stage?.getBoundingClientRect?.().height || 0)}`); } catch (e) { /* ignore */ }
		      try { info.push(`iOS=${Boolean(isIOS)}`); } catch (e) { /* ignore */ }
		      try { info.push(`compatNoCors=${Boolean(compatNoCorsApplied)}`); } catch (e) { /* ignore */ }
		      try {
		        const src = safeText(video.querySelector('source')?.getAttribute?.('src') || video.currentSrc || '');
		        info.push(`src=${src.slice(0, 180)}${src.length > 180 ? '…' : ''}`);
		      } catch (e) { /* ignore */ }
		      try {
		        const last = window.__vsLastFrameCapture;
		        if (last) info.push(`lastFrameCapture=${JSON.stringify(last).slice(0, 420)}`);
		      } catch (e) { /* ignore */ }

		      const wantOpen = window.confirm(`${info.join('\\n')}\n\n¿Probar captura de frame en servidor y abrirla en una pestaña?`);
		      if (!wantOpen) return;
		      const dataUrl = await captureVideoFrameDataUrl({ maxW: 1280 });
		      if (!dataUrl) {
		        window.alert('No se pudo capturar el frame (mira el status y vuelve a pulsar Debug).');
		        return;
		      }
		      try {
		        const w = window.open('', '_blank');
		        if (w) {
		          w.document.write(`<img src="${dataUrl}" style="max-width:100%;height:auto;"/>`);
		          w.document.title = 'Frame debug';
		        } else {
		          window.location.href = dataUrl;
		        }
		      } catch (e) {
		        try { window.location.href = dataUrl; } catch (e2) { /* ignore */ }
		      }
		    };
		    btnDebug?.addEventListener('click', showDebug);
	    const tlDefaultItem = (clipId) => tlNormalizeItem({ clip_id: clipId, speed: 1, speed_start: 1, speed_end: 1, fade_in: 0, fade_out: 0 });

	    const isTimelineProject = (p) => {
	      const payload = p?.payload;
	      if (!payload || typeof payload !== 'object') return false;
	      const kind = String(payload?.kind || '');
	      return (kind === 'timeline_v2' && Array.isArray(payload?.items)) || (kind === 'timeline_v1' && Array.isArray(payload?.clip_ids));
	    };

	    const renderTimelineProjectSelect = (items) => {
	      if (!tlProjectSelect) return;
	      const timelines = (Array.isArray(items) ? items : []).filter(isTimelineProject).slice(0, 80);
	      const opts = [`<option value=\"\">(Proyecto)</option>`].concat(
	        timelines.map((p) => {
	          const id = Number(p?.id) || 0;
	          if (!id) return '';
	          const title = escHtml(safeText(p?.title, `Timeline ${id}`));
	          return `<option value=\"${id}\">${title}</option>`;
	        }).filter(Boolean)
	      );
	      tlProjectSelect.innerHTML = opts.join('');
	      if (tlLastLoadedProjectId) {
	        try { tlProjectSelect.value = String(tlLastLoadedProjectId); } catch (e) { /* ignore */ }
	      }
	    };

	    const fmtDur = (s) => {
	      const v = Math.max(0, Number(s) || 0);
	      return `${Math.round(v * 10) / 10}s`;
	    };

	    const tlTotalSeconds = () => {
	      let sum = 0;
		      for (const it of (Array.isArray(tlItems) ? tlItems : [])) {
		        const clipId = Number(it?.clip_id) || 0;
		        if (!clipId) continue;
		        const c = clipById(clipId);
		        if (!c) continue;
		        const clipIn = Number(c?.in_s) || 0;
		        const clipOut = Number(c?.out_s) || 0;
		        const a = (it?.in_s != null) ? Math.max(0, Number(it.in_s) || 0) : clipIn;
		        const b0 = (it?.out_s != null) ? Math.max(0, Number(it.out_s) || 0) : clipOut;
		        const b = (b0 > a) ? b0 : Math.max(a, (clipOut || a));
		        const srcDur = Math.max(0, b - a);
		        const spA = tlClamp(tlNum(it?.speed_start, tlNum(it?.speed, 1)), 0.1, 4);
		        const spB = tlClamp(tlNum(it?.speed_end, spA), 0.1, 4);
		        const avg = Math.max(0.1, (spA + spB) / 2);
		        sum += (srcDur / avg);
		      }
	      return sum;
	    };

	    const renderTimelineItems = () => {
	      if (!tlItemsEl) return;
		      const rows = (Array.isArray(tlItems) ? tlItems : []).map((it, idx) => {
		        const id = Number(it?.clip_id) || 0;
		        const c = clipById(id);
		        const title = escHtml(safeText(c?.title, `Clip ${id}`));
		        const coll = escHtml(safeText(c?.collection, ''));
		        const clipIn = Number(c?.in_s) || 0;
		        const clipOut = Number(c?.out_s) || 0;
		        const a = (it?.in_s != null) ? Math.max(0, Number(it.in_s) || 0) : clipIn;
		        const b0 = (it?.out_s != null) ? Math.max(0, Number(it.out_s) || 0) : clipOut;
		        const b = (b0 > a) ? b0 : Math.max(a, (clipOut || a));
		        const srcDur = Math.max(0, b - a);
		        const spA = tlClamp(tlNum(it?.speed_start, tlNum(it?.speed, 1)), 0.1, 4);
		        const spB = tlClamp(tlNum(it?.speed_end, spA), 0.1, 4);
		        const avg = Math.max(0.1, (spA + spB) / 2);
		        const outDur = srcDur / avg;
		        const fi = tlClamp(tlNum(it?.fade_in, 0), 0, 2);
		        const fo = tlClamp(tlNum(it?.fade_out, 0), 0, 2);
		        const label = `${fmtTimeShort(a)} → ${fmtTimeShort(b || a)} · ${fmtDur(outDur)} · x${Math.round(spA * 100) / 100}${Math.abs(spA - spB) >= 1e-3 ? `→${Math.round(spB * 100) / 100}` : ''}${(fi || fo) ? ` · fade ${fi}/${fo}` : ''}`;
		        return `
		          <div class="row" draggable="true" data-tl-idx="${idx}" style="gap:0.75rem;">
	            <div style="display:flex; flex-direction:column; gap:0.05rem; min-width:0;">
	              <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${idx + 1}. ${title}</strong>
	              <small>${coll ? `${coll} · ` : ''}${label}</small>
		            </div>
		            <div style="display:flex; gap:0.35rem; flex-wrap:wrap; justify-content:flex-end;">
		              <button type="button" class="button" data-tl-fx="${idx}">FX</button>
		              <button type="button" class="button ghost" data-tl-dup="${idx}">Dup</button>
		              <button type="button" class="button ghost" data-tl-split="${idx}">Split</button>
		              <button type="button" class="button" data-tl-open="${id}">Editar</button>
		              <button type="button" class="button" data-tl-jump="${id}">Ir</button>
		              <button type="button" class="button" data-tl-up="${idx}">↑</button>
	              <button type="button" class="button" data-tl-down="${idx}">↓</button>
	              <button type="button" class="button danger" data-tl-rm="${idx}">✕</button>
	            </div>
	          </div>
	        `;
	      }).join('');
	      tlItemsEl.innerHTML = rows || '<div class="meta">Sin clips en timeline. Selecciona clips y pulsa “Cargar selección”.</div>';
	      if (tlTotalEl) tlTotalEl.textContent = tlItems.length ? `${tlItems.length} clips · ${fmtDur(tlTotalSeconds())}` : '—';

		      Array.from(tlItemsEl.querySelectorAll('[data-tl-rm]')).forEach((btn) => {
		        btn.addEventListener('click', () => {
		          const idx = Number(btn.getAttribute('data-tl-rm') || -1);
		          if (idx < 0 || idx >= tlItems.length) return;
		          tlItems.splice(idx, 1);
		          renderTimelineItems();
		          updatePlaylistExportAvailability();
		        });
		      });
		      Array.from(tlItemsEl.querySelectorAll('[data-tl-dup]')).forEach((btn) => {
		        btn.addEventListener('click', () => {
		          const idx = Number(btn.getAttribute('data-tl-dup') || -1);
		          if (idx < 0 || idx >= tlItems.length) return;
		          const it = tlItems[idx] || {};
		          tlItems.splice(idx + 1, 0, { ...it });
		          renderTimelineItems();
		          updatePlaylistExportAvailability();
		        });
		      });
		      Array.from(tlItemsEl.querySelectorAll('[data-tl-split]')).forEach((btn) => {
		        btn.addEventListener('click', () => {
		          const idx = Number(btn.getAttribute('data-tl-split') || -1);
		          if (idx < 0 || idx >= tlItems.length) return;
		          const it = tlItems[idx] || {};
		          const clipId = Number(it?.clip_id) || 0;
		          const c = clipById(clipId);
		          if (!c) return;
		          const clipIn = Number(c?.in_s) || 0;
		          const clipOut = Number(c?.out_s) || 0;
		          const a = (it?.in_s != null) ? Math.max(0, Number(it.in_s) || 0) : clipIn;
		          const b0 = (it?.out_s != null) ? Math.max(0, Number(it.out_s) || 0) : clipOut;
		          const b = (b0 > a) ? b0 : Math.max(a, (clipOut || a));
		          const t = Number(video.currentTime) || 0;
		          const splitAt = Math.max(a + 0.05, Math.min(b - 0.05, t));
		          if (!(splitAt > a) || !(b > splitAt)) return;
		          const first = { ...it, out_s: splitAt, fade_out: 0 };
		          const second = { ...it, in_s: splitAt, fade_in: 0 };
		          tlItems[idx] = first;
		          tlItems.splice(idx + 1, 0, second);
		          renderTimelineItems();
		          updatePlaylistExportAvailability();
		        });
		      });
		      Array.from(tlItemsEl.querySelectorAll('[data-tl-up]')).forEach((btn) => {
		        btn.addEventListener('click', () => {
		          const idx = Number(btn.getAttribute('data-tl-up') || -1);
		          if (idx <= 0 || idx >= tlItems.length) return;
	          const tmp = tlItems[idx - 1];
	          tlItems[idx - 1] = tlItems[idx];
	          tlItems[idx] = tmp;
	          renderTimelineItems();
	        });
	      });
	      Array.from(tlItemsEl.querySelectorAll('[data-tl-down]')).forEach((btn) => {
	        btn.addEventListener('click', () => {
	          const idx = Number(btn.getAttribute('data-tl-down') || -1);
	          if (idx < 0 || idx >= tlItems.length - 1) return;
	          const tmp = tlItems[idx + 1];
	          tlItems[idx + 1] = tlItems[idx];
	          tlItems[idx] = tmp;
	          renderTimelineItems();
	        });
	      });
		      Array.from(tlItemsEl.querySelectorAll('[data-tl-fx]')).forEach((btn) => {
		        btn.addEventListener('click', () => {
		          const idx = Number(btn.getAttribute('data-tl-fx') || -1);
		          if (!tlItemDialog || idx < 0 || idx >= tlItems.length) return;
		          tlEditingIdx = idx;
		          const it = tlItems[idx] || {};
		          try { tlItemDialog.returnValue = ''; } catch (e) { /* ignore */ }
		          const clipId = Number(it?.clip_id) || 0;
		          const c = clipById(clipId);
		          const clipIn = Number(c?.in_s) || 0;
		          const clipOut = Number(c?.out_s) || 0;
		          const inS = (it?.in_s != null) ? Math.max(0, Number(it.in_s) || 0) : clipIn;
		          const outS0 = (it?.out_s != null) ? Math.max(0, Number(it.out_s) || 0) : clipOut;
		          const outS = (outS0 > inS) ? outS0 : Math.max(inS, (clipOut || inS));
		          if (tlItemInInput) tlItemInInput.value = String(inS);
		          if (tlItemOutInput) tlItemOutInput.value = String(outS);
		          if (tlSpeedStartInput) tlSpeedStartInput.value = String(tlClamp(tlNum(it.speed_start, tlNum(it.speed, 1)), 0.1, 4));
		          if (tlSpeedEndInput) tlSpeedEndInput.value = String(tlClamp(tlNum(it.speed_end, tlNum(it.speed_start, tlNum(it.speed, 1))), 0.1, 4));
		          if (tlFadeInInput) tlFadeInInput.value = String(tlClamp(tlNum(it.fade_in, 0), 0, 2));
		          if (tlFadeOutInput) tlFadeOutInput.value = String(tlClamp(tlNum(it.fade_out, 0), 0, 2));
		          try { tlItemDialog.showModal(); } catch (e2) { /* ignore */ }
		        });
		      });
	      Array.from(tlItemsEl.querySelectorAll('[data-tl-jump]')).forEach((btn) => {
	        btn.addEventListener('click', () => {
	          const id = Number(btn.getAttribute('data-tl-jump') || 0);
	          const c = clipById(id);
	          if (!c) return;
	          try { video.currentTime = Number(c?.in_s) || 0; } catch (e) { /* ignore */ }
	          video.play().catch(() => {});
	        });
	      });
	      Array.from(tlItemsEl.querySelectorAll('[data-tl-open]')).forEach((btn) => {
	        btn.addEventListener('click', () => {
	          const id = Number(btn.getAttribute('data-tl-open') || 0);
	          const c = clipById(id);
	          if (!c) return;
	          activeClipId = id;
	          if (clipTitleInput) clipTitleInput.value = safeText(c?.title);
	          if (clipCollectionInput) clipCollectionInput.value = safeText(c?.collection);
	          if (clipTagsInput) clipTagsInput.value = (Array.isArray(c?.tags) ? c.tags : []).map((t) => safeText(t)).filter(Boolean).join(', ');
	          if (clipNotesInput) clipNotesInput.value = safeText(c?.notes, '');
	          if (inInput) inInput.value = String((Number(c?.in_s) || 0).toFixed(1));
	          if (outInput) outInput.value = String((Number(c?.out_s) || 0).toFixed(1));
	          const overlay = c?.overlay || {};
	          if (overlay && typeof overlay === 'object' && Array.isArray(overlay?.objects)) restoreJson(overlay);
	          const fxPayload = overlay?.fx;
	          if (fxPayload && typeof fxPayload === 'object' && Array.isArray(fxPayload?.layers)) {
	            fxState.layers = fxPayload.layers.map((l) => ({ ...l }));
	            selectedFxId = 0;
	            reseedFxSeq();
	            renderFxList();
	          }
	          pushHistory();
	          updateLayerPanel();
	          setStatus('Clip cargado.');
	        });
	      });

	      const rowsEls = Array.from(tlItemsEl.querySelectorAll('[data-tl-idx]'));
	      rowsEls.forEach((row) => {
	        row.addEventListener('dragstart', (ev) => {
	          try { ev.dataTransfer.setData('text/plain', String(row.getAttribute('data-tl-idx') || '')); } catch (e) { /* ignore */ }
	        });
	        row.addEventListener('dragover', (ev) => { ev.preventDefault(); });
	        row.addEventListener('drop', (ev) => {
	          ev.preventDefault();
	          const fromIdx = Number((ev.dataTransfer && ev.dataTransfer.getData('text/plain')) || -1);
	          const toIdx = Number(row.getAttribute('data-tl-idx') || -1);
	          if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx) return;
	          const moved = tlItems.splice(fromIdx, 1)[0];
	          tlItems.splice(toIdx, 0, moved);
	          renderTimelineItems();
	        });
	      });
	    };

	    const tlLoadFromSelection = () => {
	      const items = selectedClipsOrdered();
	      tlItems = items.map((c) => tlDefaultItem(Number(c?.id) || 0)).filter(Boolean);
	      renderTimelineItems();
	      updatePlaylistExportAvailability();
	    };

	    const tlClear = () => {
	      tlItems = [];
	      renderTimelineItems();
	      updatePlaylistExportAvailability();
	    };

	    const tlSaveProject = async () => {
	      if (!projectSaveUrl || !videoId) return;
	      if (!tlItems.length) { setStatus('No hay clips en timeline.', true); return; }
	      const title = window.prompt('Nombre del timeline:', `Timeline · ${tlItems.length} clips`);
	      if (!title) return;
	      const payload = { kind: 'timeline_v2', items: tlItems.slice(0, 200), clip_ids: tlItems.map((x) => Number(x?.clip_id) || 0).filter((x) => x > 0).slice(0, 200) };
	      try {
	        const resp = await fetch(projectSaveUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify({ id: 0, video_id: videoId, title: String(title).slice(0, 180), payload }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        await refreshProjects();
	        setStatus('Timeline guardado.');
	      } catch (e) {
	        setStatus('No se pudo guardar timeline.', true);
	      }
	    };

	    const tlLoadProject = async () => {
	      const id = Number(tlProjectSelect?.value || 0);
	      if (!id) { setStatus('Selecciona un proyecto timeline.', true); return; }
	      try {
	        const found = (Array.isArray(projectsCache) ? projectsCache : []).find((x) => Number(x?.id) === id);
	        const payload = found?.payload || {};
	        const raw = Array.isArray(payload?.items) ? payload.items : null;
	        if (raw && Array.isArray(raw)) {
	          tlItems = raw.map(tlNormalizeItem).filter(Boolean);
	        } else {
	          const ids = Array.isArray(payload?.clip_ids) ? payload.clip_ids : [];
	          tlItems = ids.map((x) => tlDefaultItem(Number(x) || 0)).filter(Boolean);
	        }
	        tlLastLoadedProjectId = id;
	        renderTimelineItems();
	        setStatus('Timeline cargado.');
	      } catch (e) {
	        setStatus('No se pudo cargar timeline.', true);
	      }
	    };

		    const tlExportMp4 = async () => {
		      const supportsJobs = Boolean(exportJobCreateUrl && exportJobStatusUrl && exportJobCancelUrl);
		      if (!supportsJobs && !exportServerPlaylistUrl) { setStatus('No hay endpoint MP4 playlist.', true); return; }
		      if (!teamId) { setStatus('Asigna el vídeo a un equipo antes de exportar MP4.', true); return; }
		      if (tlItems.length < 2) { setStatus('Añade al menos 2 clips al timeline.', true); return; }
		      const t = `Timeline · ${tlItems.length} clips`;

		      const setJobUi = ({ show, msg, progress, canCancel } = {}) => {
		        try {
		          if (tlJobWrap) tlJobWrap.style.display = show ? 'block' : 'none';
		          if (tlExportCancelBtn) tlExportCancelBtn.style.display = (show && canCancel) ? 'inline-block' : 'none';
		          if (tlJobMsg && msg != null) tlJobMsg.textContent = safeText(msg, '—');
		          if (tlJobProgress && progress != null) tlJobProgress.value = clamp(Number(progress) || 0, 0, 100);
		        } catch (e) { /* ignore */ }
		      };

		      const pollJobUntilDone = async (jobId) => {
		        const token = ++tlExportPollToken;
		        const started = Date.now();
		        const maxWaitMs = 20 * 60 * 1000;
		        while (Date.now() - started < maxWaitMs) {
		          if (token !== tlExportPollToken) return null;
		          try {
		            const resp = await fetch(`${exportJobStatusUrl}?job_id=${encodeURIComponent(String(jobId))}`, { credentials: 'same-origin' });
		            const data = await resp.json().catch(() => ({}));
		            const job = data?.job || {};
		            const st = safeText(job?.status, '');
		            setJobUi({ show: true, msg: safeText(job?.message, st || '—'), progress: Number(job?.progress) || 0, canCancel: st === 'pending' || st === 'running' });
		            if (st === 'done') return job;
		            if (st === 'error') throw new Error(safeText(job?.error, 'Job error'));
		            if (st === 'canceled') throw new Error('Cancelado');
		          } catch (e) {
		            if (token !== tlExportPollToken) return null;
		            const elapsed = Date.now() - started;
		            if (elapsed > 15 * 1000) throw e;
		          }
		          await sleep(1200);
		        }
		        throw new Error('Timeout esperando el export.');
		      };

		      const cancelActiveJob = async () => {
		        const jobId = Number(tlActiveExportJobId) || 0;
		        if (!jobId || !exportJobCancelUrl) return;
		        try {
		          await fetch(exportJobCancelUrl, {
		            method: 'POST',
		            credentials: 'same-origin',
		            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
		            body: JSON.stringify({ job_id: jobId }),
		          });
		        } catch (e) { /* ignore */ }
		        tlExportPollToken += 1;
		        tlActiveExportJobId = 0;
		        setJobUi({ show: false, canCancel: false });
		        setStatus('Cancelado.', true);
		      };

		      if (tlExportCancelBtn) tlExportCancelBtn.onclick = cancelActiveJob;
		      try {
		        tlExportBtn.disabled = true;
		        setStatus('Preparando export…');
			        const includeAudio = tlIncludeAudioToggle ? Boolean(tlIncludeAudioToggle.checked) : true;
			        const voiceoverId = Number(voiceoverSelect?.value || 0) || 0;
			        const voiceoverVol = tlClamp(tlNum(voiceoverVolInput?.value, 1), 0, 2);
			        const musicId = Number(musicSelect?.value || 0) || 0;
			        const musicVol = tlClamp(tlNum(musicVolInput?.value, 0.4), 0, 2);
			        const videoVol = tlClamp(tlNum(videoVolInput?.value, 1), 0, 2);
			        const normalize = audioNormalizeToggle ? Boolean(audioNormalizeToggle.checked) : false;
			        const limiter = audioLimiterToggle ? Boolean(audioLimiterToggle.checked) : false;
			        const transitionS = tlClamp(tlNum(tlTransitionInput?.value, 0), 0, 1);
			        const voiceoverOffsetS = tlClamp(tlNum(voiceoverOffsetInput?.value, 0), -600, 600);
			        const ducking = voiceoverDuckingToggle ? Boolean(voiceoverDuckingToggle.checked) : false;
			        const duckStrength = tlClamp(tlNum(voiceoverDuckStrengthInput?.value, 1), 0, 1);
		        const items = tlItems.slice(0, 60).map((it) => ({
		          clip_id: Number(it?.clip_id) || 0,
		          in_s: (it?.in_s != null) ? (Number(it.in_s) || 0) : undefined,
		          out_s: (it?.out_s != null) ? (Number(it.out_s) || 0) : undefined,
		          speed: tlClamp(tlNum(it?.speed, 1), 0.1, 4),
		          speed_start: tlClamp(tlNum(it?.speed_start, tlNum(it?.speed, 1)), 0.1, 4),
		          speed_end: tlClamp(tlNum(it?.speed_end, tlNum(it?.speed_start, tlNum(it?.speed, 1))), 0.1, 4),
		          fade_in: tlClamp(tlNum(it?.fade_in, 0), 0, 2),
		          fade_out: tlClamp(tlNum(it?.fade_out, 0), 0, 2),
		        })).filter((x) => x.clip_id > 0);
		        const exportPayload = {
		          video_id: videoId || 0,
		          items,
		          title: t,
		          include_audio: includeAudio,
		          voiceover_id: voiceoverId > 0 ? voiceoverId : undefined,
		          voiceover_volume: voiceoverVol,
		          music_id: musicId > 0 ? musicId : undefined,
		          music_volume: musicVol,
		          video_volume: videoVol,
		          normalize,
		          limiter,
		          ducking,
		          duck_strength: duckStrength,
		          transition_s: transitionS,
		          voiceover_offset_s: voiceoverOffsetS,
		        };

		        let url = '';
		        let downloadUrl = '';
		        if (supportsJobs) {
		          setStatus('Export en cola…');
		          setJobUi({ show: true, msg: 'En cola…', progress: 0, canCancel: true });
		          const createResp = await fetch(exportJobCreateUrl, {
		            method: 'POST',
		            credentials: 'same-origin',
		            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
		            body: JSON.stringify(exportPayload),
		          });
		          const createData = await createResp.json().catch(() => ({}));
		          if (!createResp.ok || !createData?.ok || !createData?.job_id) throw new Error(createData?.error || 'No se pudo crear job.');
		          tlActiveExportJobId = Number(createData.job_id) || 0;
		          const job = await pollJobUntilDone(tlActiveExportJobId);
		          url = safeText(job?.url, '');
		          downloadUrl = safeText(job?.download_url, url);
		          lastExportAssetId = Number(job?.export_id) || lastExportAssetId || 0;
		          lastExportShareUrl = url || lastExportShareUrl || '';
		          setJobUi({ show: false, canCancel: false });
		          tlActiveExportJobId = 0;
		        } else {
		          setStatus('Generando MP4 timeline en servidor…');
		          const resp = await fetch(exportServerPlaylistUrl, {
		            method: 'POST',
		            credentials: 'same-origin',
		            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
		            body: JSON.stringify(exportPayload),
		          });
		          const data = await resp.json().catch(() => ({}));
		          if (!resp.ok || !data?.ok || !data?.url) throw new Error(data?.error || 'No se pudo exportar MP4 timeline.');
		          url = String(data.url);
		          downloadUrl = String(data.download_url || url);
		          lastExportAssetId = Number(data?.id) || lastExportAssetId || 0;
		          lastExportShareUrl = url;
		        }

		        if (!url) {
		          setStatus('No se pudo exportar MP4 timeline.', true);
		          return;
		        }
            triggerDownload(downloadUrl);
            try { await tryCopy(downloadUrl); } catch (e) { /* ignore */ }
            setStatus('MP4 timeline listo. Descargando…');
		        refreshShareLinks();
		      } catch (e) {
		        setJobUi({ show: false, canCancel: false });
		        tlActiveExportJobId = 0;
		        setStatus(e?.message || 'Error exportando MP4 timeline.', true);
		      } finally {
		        tlExportBtn.disabled = false;
		      }
			    };

			    const tlExportOverlays = async () => {
			      if (recActive) { setStatus('Ya hay una grabación en curso.', true); return; }
			      if (!exportUploadUrl) { setStatus('No hay endpoint de subida para export.', true); return; }
			      if (!tlItems.length) { setStatus('Timeline vacío.', true); return; }

			      const steps = [];
			      for (const it of tlItems.slice(0, 60)) {
			        const clipId = Number(it?.clip_id) || 0;
			        if (!clipId) continue;
			        const c = clipById(clipId);
			        if (!c) continue;
			        const clipIn = Number(c?.in_s) || 0;
			        const clipOut0 = Number(c?.out_s) || 0;
			        const clipOut = clipOut0 > clipIn ? clipOut0 : (clipIn + 0.2);
			        const inS = (it?.in_s != null) ? Math.max(0, Number(it.in_s) || 0) : clipIn;
			        const outS0 = (it?.out_s != null) ? Math.max(0, Number(it.out_s) || 0) : clipOut;
			        const outS = outS0 > inS + 0.05 ? outS0 : (inS + 0.25);
			        const sp = tlClamp(tlNum(it?.speed_start, tlNum(it?.speed, 1)), 0.1, 4);
			        steps.push({ clip: c, clipId, inS, outS, speed: sp });
			      }
			      if (!steps.length) { setStatus('Timeline sin clips válidos.', true); return; }

			      const prevState = (() => {
			        const snap = {};
			        try { snap.activeClipId = Number(activeClipId) || 0; } catch (e) { snap.activeClipId = 0; }
			        try { snap.inV = safeText(inInput?.value, ''); } catch (e) { snap.inV = ''; }
			        try { snap.outV = safeText(outInput?.value, ''); } catch (e) { snap.outV = ''; }
			        try { snap.title = safeText(clipTitleInput?.value, ''); } catch (e) { snap.title = ''; }
			        try { snap.collection = safeText(clipCollectionInput?.value, ''); } catch (e) { snap.collection = ''; }
			        try { snap.tags = safeText(clipTagsInput?.value, ''); } catch (e) { snap.tags = ''; }
			        try { snap.notes = safeText(clipNotesInput?.value, ''); } catch (e) { snap.notes = ''; }
			        try { snap.fx = (Array.isArray(fxState.layers) ? fxState.layers : []).map((l) => ({ ...l })); } catch (e) { snap.fx = []; }
			        try { snap.selFx = Number(selectedFxId) || 0; } catch (e) { snap.selFx = 0; }
			        try { snap.canvas = fabricCanvas.toDatalessJSON(['data']); } catch (e) { snap.canvas = null; }
			        try { snap.playbackRate = Number(video.playbackRate) || 1; } catch (e) { snap.playbackRate = 1; }
			        try { snap.time = Number(video.currentTime) || 0; } catch (e) { snap.time = 0; }
			        try { snap.freezeHold = Boolean(freezeHoldOn); } catch (e) { snap.freezeHold = false; }
			        return snap;
			      })();

			      const restoreJsonAsync = (json) => new Promise((resolve) => {
			        if (!json) return resolve(false);
			        try {
			          fabricCanvas.loadFromJSON(json, () => {
			            try { fabricCanvas.getObjects().forEach((o) => ensureLayerData(o)); } catch (e) { /* ignore */ }
			            try { fabricCanvas.renderAll(); } catch (e) { /* ignore */ }
			            try { updateLayerPanel(); } catch (e) { /* ignore */ }
			            try { renderDrawLayers(); } catch (e) { /* ignore */ }
			            resolve(true);
			          });
			        } catch (e) {
			          resolve(false);
			        }
			      });

			      const loadClipOverlay = async (clip) => {
			        const overlay = clip?.overlay || {};
			        if (overlay && typeof overlay === 'object' && Array.isArray(overlay?.objects)) {
			          await restoreJsonAsync(overlay);
			        } else {
			          try { fabricCanvas.clear(); } catch (e) { /* ignore */ }
			        }
			        const fxPayload = overlay?.fx;
			        if (fxPayload && typeof fxPayload === 'object' && Array.isArray(fxPayload?.layers)) {
			          fxState.layers = fxPayload.layers.map((l) => ({ ...l }));
			          selectedFxId = 0;
			          reseedFxSeq();
			          renderFxList();
			        } else {
			          fxState.layers = [];
			          selectedFxId = 0;
			          reseedFxSeq();
			          renderFxList();
			        }
			      };

			      const waitUntil = (pred, timeoutMs = 30000) => new Promise((resolve) => {
			        const started = Date.now();
			        const tick = () => {
			          if (pred()) return resolve(true);
			          if (Date.now() - started > timeoutMs) return resolve(false);
			          window.requestAnimationFrame(tick);
			        };
			        tick();
			      });

			      const stopRecordingAndWait = async () => {
			        const media = recMedia;
			        if (!media) { try { await stopRecording(); } catch (e) { /* ignore */ } return; }
			        await new Promise((resolve) => {
			          const prevOnStop = media.onstop;
			          media.onstop = async () => {
			            try { if (prevOnStop) await prevOnStop(); } catch (e) { /* ignore */ }
			            resolve(true);
			          };
			          stopRecording();
			        });
			      };

			      const setUiBusy = (on) => {
			        const busy = Boolean(on);
			        try { if (tlExportOverlaysBtn) tlExportOverlaysBtn.disabled = busy; } catch (e) { /* ignore */ }
			        try { if (tlExportBtn) tlExportBtn.disabled = busy; } catch (e) { /* ignore */ }
			        try { if (btnExportShare) btnExportShare.disabled = busy; } catch (e) { /* ignore */ }
			        try { if (btnExportSeg) btnExportSeg.disabled = busy; } catch (e) { /* ignore */ }
			        try { if (btnRecord) btnRecord.disabled = busy; } catch (e) { /* ignore */ }
			      };

			      setUiBusy(true);
			      playlistActive = false;
			      playlistIds = [];
			      playlistIndex = 0;
			      clipBoundActive = false;

			      const baseTitle = `Timeline · ${steps.length} clips · overlays`;
			      setStatus('Export + overlays: preparando…');
			      try { video.pause(); } catch (e) { /* ignore */ }

			      try {
			        const first = steps[0];
			        await loadClipOverlay(first.clip);
			        if (inInput) inInput.value = String(first.inS.toFixed(1));
			        if (outInput) outInput.value = String(first.outS.toFixed(1));
			        try { await seekTo(first.inS); } catch (e) { /* ignore */ }
			        try { video.playbackRate = first.speed; } catch (e) { /* ignore */ }
			        setFreezeHold(true);
			        try { syncFreezeBackground(first.inS); } catch (e) { /* ignore */ }

			        await startRecording({ from: first.inS, to: null, destination: 'upload', uploadTitle: baseTitle, uploadClipId: 0 });

			        for (let i = 0; i < steps.length; i += 1) {
			          const step = steps[i];
			          setStatus(`Export + overlays: ${i + 1}/${steps.length}`);
			          await loadClipOverlay(step.clip);
			          if (inInput) inInput.value = String(step.inS.toFixed(1));
			          if (outInput) outInput.value = String(step.outS.toFixed(1));
			          try { video.playbackRate = step.speed; } catch (e) { /* ignore */ }
			          try { await seekTo(step.inS); } catch (e) { /* ignore */ }
			          try { syncFreezeBackground(step.inS); } catch (e) { /* ignore */ }
			          try { await video.play(); } catch (e) { /* ignore */ }
			          const ok = await waitUntil(() => (Number(video.currentTime) || 0) >= (step.outS - 0.03), 120000);
			          try { video.pause(); } catch (e) { /* ignore */ }
			          if (!ok) throw new Error('Timeout exportando un clip.');
			          await sleep(80);
			        }
			        await stopRecordingAndWait();
			        setStatus('Export + overlays: finalizando…');
			      } catch (e) {
			        try { await stopRecordingAndWait(); } catch (e2) { /* ignore */ }
			        setStatus(safeText(e?.message, 'Error exportando.'), true);
			      } finally {
			        // Restaurar estado previo
			        try { activeClipId = Number(prevState.activeClipId) || 0; } catch (e) { /* ignore */ }
			        try { if (clipTitleInput) clipTitleInput.value = safeText(prevState.title, ''); } catch (e) { /* ignore */ }
			        try { if (clipCollectionInput) clipCollectionInput.value = safeText(prevState.collection, ''); } catch (e) { /* ignore */ }
			        try { if (clipTagsInput) clipTagsInput.value = safeText(prevState.tags, ''); } catch (e) { /* ignore */ }
			        try { if (clipNotesInput) clipNotesInput.value = safeText(prevState.notes, ''); } catch (e) { /* ignore */ }
			        try { if (inInput) inInput.value = safeText(prevState.inV, ''); } catch (e) { /* ignore */ }
			        try { if (outInput) outInput.value = safeText(prevState.outV, ''); } catch (e) { /* ignore */ }
			        try { video.playbackRate = Number(prevState.playbackRate) || 1; } catch (e) { /* ignore */ }
			        try { await seekTo(Number(prevState.time) || 0); } catch (e) { /* ignore */ }
			        try {
			          if (prevState.canvas) await restoreJsonAsync(prevState.canvas);
			        } catch (e) { /* ignore */ }
			        try {
			          fxState.layers = (Array.isArray(prevState.fx) ? prevState.fx : []).map((l) => ({ ...l }));
			          selectedFxId = Number(prevState.selFx) || 0;
			          reseedFxSeq();
			          renderFxList();
			          updateLayerPanel();
			        } catch (e) { /* ignore */ }
			        try { setFreezeHold(Boolean(prevState.freezeHold)); } catch (e) { /* ignore */ }
			        try { syncFreezeBackground(); } catch (e) { /* ignore */ }
			        setUiBusy(false);
			      }
			    };

		    if (tlItemDialog) {
		      tlItemDialog.addEventListener('close', () => {
		        const action = safeText(tlItemDialog.returnValue, '');
		        const idx = Number(tlEditingIdx);
	        tlEditingIdx = -1;
	        if (idx < 0 || idx >= tlItems.length) return;
	        if (action === 'reset') {
	          const id = Number(tlItems[idx]?.clip_id) || 0;
	          tlItems[idx] = tlDefaultItem(id);
	          renderTimelineItems();
	          return;
		        }
		        if (action !== 'save') return;
		        const clipId = Number(tlItems[idx]?.clip_id) || 0;
		        const c = clipById(clipId);
		        const clipIn = Number(c?.in_s) || 0;
		        const clipOut = Number(c?.out_s) || 0;
		        const rawIn = tlNum(tlItemInInput?.value, clipIn);
		        const rawOut = tlNum(tlItemOutInput?.value, clipOut || rawIn);
		        const inS = Math.max(0, Math.min(rawIn, rawOut));
		        const outS = Math.max(inS, rawOut);
		        const spA = tlClamp(tlNum(tlSpeedStartInput?.value, 1), 0.1, 4);
		        const spB = tlClamp(tlNum(tlSpeedEndInput?.value, spA), 0.1, 4);
		        const fi = tlClamp(tlNum(tlFadeInInput?.value, 0), 0, 2);
		        const fo = tlClamp(tlNum(tlFadeOutInput?.value, 0), 0, 2);
		        const prev = tlItems[idx] || {};
		        const saveIn = (Math.abs(inS - clipIn) >= 1e-3) ? inS : null;
		        const saveOut = (Math.abs(outS - (clipOut || inS)) >= 1e-3) ? outS : null;
		        tlItems[idx] = { ...prev, in_s: saveIn, out_s: saveOut, speed: spA, speed_start: spA, speed_end: spB, fade_in: fi, fade_out: fo };
		        renderTimelineItems();
		      });
		    }

	    const voiceoverKey = () => `vs_voiceover_settings:v1:${teamId || 'na'}:${videoId || 'na'}`;
	    const loadVoiceoverSettings = () => {
	      try {
	        const raw = window.localStorage.getItem(voiceoverKey()) || '';
	        return raw ? JSON.parse(raw) : {};
	      } catch (e) { return {}; }
	    };
		    const saveVoiceoverSettings = () => {
		      try {
		        const payload = {
		          voiceover_id: Number(voiceoverSelect?.value || 0) || 0,
		          voiceover_vol: tlClamp(tlNum(voiceoverVolInput?.value, 1), 0, 2),
		          music_id: Number(musicSelect?.value || 0) || 0,
		          music_vol: tlClamp(tlNum(musicVolInput?.value, 0.4), 0, 2),
		          video_vol: tlClamp(tlNum(videoVolInput?.value, 1), 0, 2),
		          normalize: audioNormalizeToggle ? Boolean(audioNormalizeToggle.checked) : false,
		          limiter: audioLimiterToggle ? Boolean(audioLimiterToggle.checked) : false,
		          transition_s: tlClamp(tlNum(tlTransitionInput?.value, 0), 0, 1),
		          voiceover_offset_s: tlClamp(tlNum(voiceoverOffsetInput?.value, 0), -600, 600),
		          ducking: voiceoverDuckingToggle ? Boolean(voiceoverDuckingToggle.checked) : false,
		          duck_strength: tlClamp(tlNum(voiceoverDuckStrengthInput?.value, 1), 0, 1),
		        };
		        window.localStorage.setItem(voiceoverKey(), JSON.stringify(payload));
		      } catch (e) { /* ignore */ }
		    };
	    const refreshVoiceovers = async () => {
	      if (!voiceoversUrl || !videoId || !voiceoverSelect) return;
	      try {
	        const resp = await fetch(`${voiceoversUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        const items = Array.isArray(data?.items) ? data.items : [];
	        const current = Number(voiceoverSelect.value || 0) || 0;
	        const opts = ['<option value=\"\">(Voz en off)</option>'].concat(items.map((it) => {
	          const id = Number(it?.id) || 0;
	          if (!id) return '';
	          const title = escHtml(safeText(it?.title, `Voz ${id}`));
	          return `<option value=\"${id}\">${title}</option>`;
	        }).filter(Boolean));
	        voiceoverSelect.innerHTML = opts.join('');
	        if (current && items.some((x) => Number(x?.id) === current)) {
	          voiceoverSelect.value = String(current);
	        }
	      } catch (e) { /* ignore */ }
	    };

	    const refreshMusic = async () => {
	      if (!musicUrl || !videoId || !musicSelect) return;
	      try {
	        const resp = await fetch(`${musicUrl}?video_id=${encodeURIComponent(String(videoId))}`, { credentials: 'same-origin' });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        const items = Array.isArray(data?.items) ? data.items : [];
	        const current = Number(musicSelect.value || 0) || 0;
	        const opts = ['<option value=\"\">(Música / BGM)</option>'].concat(items.map((it) => {
	          const id = Number(it?.id) || 0;
	          if (!id) return '';
	          const title = escHtml(safeText(it?.title, `Música ${id}`));
	          return `<option value=\"${id}\">${title}</option>`;
	        }).filter(Boolean));
	        musicSelect.innerHTML = opts.join('');
	        if (current && items.some((x) => Number(x?.id) === current)) {
	          musicSelect.value = String(current);
	        }
	      } catch (e) { /* ignore */ }
	    };

	    const uploadMusicFile = async (file) => {
	      if (!musicUploadUrl || !videoId || !file) return;
	      const fd = new FormData();
	      fd.append('video_id', String(videoId));
	      const fallbackTitle = `Música · ${new Date().toLocaleString()}`.slice(0, 180);
	      const rawName = safeText(file?.name, fallbackTitle);
	      fd.append('title', rawName.slice(0, 180));
	      fd.append('file', file, rawName);
	      const resp = await fetch(musicUploadUrl, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf }, body: fd });
	      const data = await resp.json().catch(() => ({}));
	      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo subir música.');
	      await refreshMusic();
	      const id = Number(data?.item?.id) || 0;
	      if (id && musicSelect) musicSelect.value = String(id);
	      saveVoiceoverSettings();
	    };

	    const pickMusicUpload = async () => {
	      if (!musicFileInput) return;
	      try { musicFileInput.value = ''; } catch (e) { /* ignore */ }
	      musicFileInput.click();
	    };

	    const deleteSelectedMusic = async () => {
	      const id = Number(musicSelect?.value || 0) || 0;
	      if (!id || !musicDeleteUrl || !videoId) return;
	      if (!window.confirm('¿Borrar esta música?')) return;
	      try {
	        const resp = await fetch(musicDeleteUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          body: JSON.stringify({ id, video_id: videoId }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        await refreshMusic();
	        if (musicSelect) musicSelect.value = '';
	        saveVoiceoverSettings();
	        setStatus('Música borrada.');
	      } catch (e) {
	        setStatus('No se pudo borrar la música.', true);
	      }
	    };
	    const pickRecordMime = () => {
	      const cands = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/ogg'];
	      for (const m of cands) {
	        try { if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) return m; } catch (e) { /* ignore */ }
	      }
	      return '';
	    };
	    let voRecorder = null;
	    let voChunks = [];
	    let voStream = null;
	    const stopVoiceStream = () => {
	      try { (voStream?.getTracks?.() || []).forEach((t) => t.stop()); } catch (e) { /* ignore */ }
	      voStream = null;
	    };
	    const uploadVoiceoverBlob = async (blob) => {
	      if (!voiceoverUploadUrl || !videoId) return;
	      const ext = (String(blob?.type || '').includes('mp4')) ? 'm4a' : (String(blob?.type || '').includes('ogg') ? 'ogg' : 'webm');
	      const fd = new FormData();
	      fd.append('video_id', String(videoId));
	      fd.append('title', `Voz · ${new Date().toLocaleString()}`.slice(0, 180));
	      fd.append('file', blob, `voiceover.${ext}`);
	      const resp = await fetch(voiceoverUploadUrl, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf }, body: fd });
	      const data = await resp.json().catch(() => ({}));
	      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo subir voz.');
	      await refreshVoiceovers();
	      const id = Number(data?.item?.id) || 0;
	      if (id && voiceoverSelect) voiceoverSelect.value = String(id);
	      saveVoiceoverSettings();
	    };
	    const toggleVoiceRecording = async () => {
	      if (!voiceoverRecordBtn) return;
	      if (voRecorder && voRecorder.state === 'recording') {
	        try { voRecorder.stop(); } catch (e) { /* ignore */ }
	        voiceoverRecordBtn.textContent = 'Grabar voz';
	        return;
	      }
	      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
	        setStatus('Grabación no soportada en este navegador.', true);
	        return;
	      }
	      voiceoverRecordBtn.textContent = 'Parar';
	      setStatus('Grabando voz en off…');
	      try {
	        voStream = await navigator.mediaDevices.getUserMedia({ audio: true });
	        const mimeType = pickRecordMime();
	        voChunks = [];
	        voRecorder = new MediaRecorder(voStream, mimeType ? { mimeType } : undefined);
	        voRecorder.addEventListener('dataavailable', (ev) => {
	          if (ev?.data && ev.data.size > 0) voChunks.push(ev.data);
	        });
	        voRecorder.addEventListener('stop', async () => {
	          stopVoiceStream();
	          const blob = new Blob(voChunks, { type: voRecorder?.mimeType || '' });
	          voRecorder = null;
	          voChunks = [];
	          try {
	            setStatus('Subiendo voz en off…');
	            await uploadVoiceoverBlob(blob);
	            setStatus('Voz en off guardada.');
	          } catch (e) {
	            setStatus(e?.message || 'No se pudo subir voz.', true);
	          }
	        });
	        voRecorder.start(250);
	      } catch (e) {
	        stopVoiceStream();
	        voRecorder = null;
	        voChunks = [];
	        voiceoverRecordBtn.textContent = 'Grabar voz';
	        setStatus('No se pudo acceder al micrófono.', true);
	      }
	    };
	    const deleteSelectedVoiceover = async () => {
	      const id = Number(voiceoverSelect?.value || 0) || 0;
	      if (!id || !voiceoverDeleteUrl || !videoId) return;
	      if (!window.confirm('¿Borrar esta voz en off?')) return;
	      try {
	        const resp = await fetch(voiceoverDeleteUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          body: JSON.stringify({ id, video_id: videoId }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        await refreshVoiceovers();
	        if (voiceoverSelect) voiceoverSelect.value = '';
	        saveVoiceoverSettings();
	        setStatus('Voz borrada.');
	      } catch (e) {
	        setStatus('No se pudo borrar la voz.', true);
	      }
	    };

		    try {
		      const s = loadVoiceoverSettings();
		      if (voiceoverSelect && s.voiceover_id) voiceoverSelect.value = String(s.voiceover_id);
		      if (voiceoverVolInput && s.voiceover_vol != null) voiceoverVolInput.value = String(s.voiceover_vol);
		      if (musicSelect && s.music_id) musicSelect.value = String(s.music_id);
		      if (musicVolInput && s.music_vol != null) musicVolInput.value = String(s.music_vol);
		      if (videoVolInput && s.video_vol != null) videoVolInput.value = String(s.video_vol);
		      if (audioNormalizeToggle && s.normalize != null) audioNormalizeToggle.checked = Boolean(s.normalize);
		      if (audioLimiterToggle && s.limiter != null) audioLimiterToggle.checked = Boolean(s.limiter);
		      if (tlTransitionInput && s.transition_s != null) tlTransitionInput.value = String(s.transition_s);
		      if (voiceoverOffsetInput && s.voiceover_offset_s != null) voiceoverOffsetInput.value = String(s.voiceover_offset_s);
		      if (voiceoverDuckingToggle && s.ducking != null) voiceoverDuckingToggle.checked = Boolean(s.ducking);
		      if (voiceoverDuckStrengthInput && s.duck_strength != null) voiceoverDuckStrengthInput.value = String(s.duck_strength);
		    } catch (e) { /* ignore */ }
		    voiceoverSelect?.addEventListener('change', saveVoiceoverSettings);
		    voiceoverVolInput?.addEventListener('change', saveVoiceoverSettings);
		    videoVolInput?.addEventListener('change', saveVoiceoverSettings);
		    musicSelect?.addEventListener('change', saveVoiceoverSettings);
		    musicVolInput?.addEventListener('change', saveVoiceoverSettings);
		    audioNormalizeToggle?.addEventListener('change', saveVoiceoverSettings);
		    audioLimiterToggle?.addEventListener('change', saveVoiceoverSettings);
		    tlTransitionInput?.addEventListener('change', saveVoiceoverSettings);
		    voiceoverOffsetInput?.addEventListener('change', saveVoiceoverSettings);
		    voiceoverDuckingToggle?.addEventListener('change', saveVoiceoverSettings);
		    voiceoverDuckStrengthInput?.addEventListener('change', saveVoiceoverSettings);
		    voiceoverRecordBtn?.addEventListener('click', toggleVoiceRecording);
		    voiceoverDeleteBtn?.addEventListener('click', deleteSelectedVoiceover);
		    musicUploadBtn?.addEventListener('click', pickMusicUpload);
		    musicDeleteBtn?.addEventListener('click', deleteSelectedMusic);

		    musicFileInput?.addEventListener('change', async () => {
		      const file = (musicFileInput && musicFileInput.files && musicFileInput.files[0]) ? musicFileInput.files[0] : null;
		      if (!file) return;
		      try {
		        setStatus('Subiendo música…');
		        await uploadMusicFile(file);
		        setStatus('Música guardada.');
		      } catch (e) {
		        setStatus(e?.message || 'No se pudo subir música.', true);
		      }

		      // Atajos de recorte/clips (tipo editor)
		      if (key === '[') {
		        ev.preventDefault();
		        const t = Math.max(0, Number(video.currentTime) || 0);
		        try { if (inInput) inInput.value = String(t.toFixed(1)); } catch (e) { /* ignore */ }
		        setStatus(`IN = ${fmtTimeShort(t)}`);
		        return;
		      }
		      if (key === ']') {
		        ev.preventDefault();
		        const t = Math.max(0, Number(video.currentTime) || 0);
		        try { if (outInput) outInput.value = String(t.toFixed(1)); } catch (e) { /* ignore */ }
		        setStatus(`OUT = ${fmtTimeShort(t)}`);
		        return;
		      }
		      if (key === ',' || key === '<' || key === '.' || key === '>') {
		        ev.preventDefault();
		        const fps = clamp(Math.round(Number(fpsSelect?.value || 25) || 25), 10, 120);
		        const dt = 1 / fps;
		        const dir = (key === ',' || key === '<') ? -1 : 1;
		        const t = Math.max(0, (Number(video.currentTime) || 0) + dir * dt);
		        try { video.pause(); } catch (e) { /* ignore */ }
		        try { video.currentTime = t; } catch (e) { /* ignore */ }
		        setStatus(`Frame ${dir < 0 ? '←' : '→'} ${fmtTimeShort(t)}`);
		      }
		    });

			    tlFromSelectionBtn?.addEventListener('click', tlLoadFromSelection);
			    tlClearBtn?.addEventListener('click', tlClear);
			    tlSaveBtn?.addEventListener('click', tlSaveProject);
			    tlLoadBtn?.addEventListener('click', tlLoadProject);
			    tlExportBtn?.addEventListener('click', tlExportMp4);
			    tlExportOverlaysBtn?.addEventListener('click', tlExportOverlays);
	        if (!simpleUI) {
			      refreshVoiceovers();
			      refreshMusic();
			      refreshProjects();
	        }

	    const setReviewed = async ({ kind, objectId, done }) => {
	      if (!reviewUrl || !videoId) return false;
	      try {
	        const resp = await fetch(reviewUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify({ video_id: videoId, kind, object_id: objectId, done: Boolean(done) }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        return true;
	      } catch (e) {
	        return false;
	      }
	    };
	
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

	    const renderDashboard = () => {
	      if (!dashboardEl) return;
	      const clipTotal = Array.isArray(clipsCache) ? clipsCache.length : 0;
	      const evTotal = Array.isArray(timelineCache) ? timelineCache.length : 0;
	      const clipDone = Math.min(clipTotal, reviewedClipIds.size);
	      const evDone = Math.min(evTotal, reviewedEventIds.size);

	      const kindCounts = {};
	      for (const ev of (Array.isArray(timelineCache) ? timelineCache : [])) {
	        const k = safeText(ev?.kind, 'tag');
	        kindCounts[k] = (kindCounts[k] || 0) + 1;
	      }
	      const kindLabel = (k) => ({
	        goal: 'Goles',
	        shot: 'Disparos',
	        press: 'Presión',
	        turnover: 'Pérdidas',
	        abp: 'ABP',
	        note: 'Notas',
	        tag: 'Tags',
	      }[k] || k);
	      const orderedKinds = ['goal', 'shot', 'press', 'turnover', 'abp', 'note', 'tag'];
	      const kindsLine = orderedKinds
	        .filter((k) => (kindCounts[k] || 0) > 0)
	        .slice(0, 7)
	        .map((k) => `<span class="k">${kindLabel(k)}: ${kindCounts[k]}</span>`)
	        .join(' ') || '<span class="hint">Sin eventos aún.</span>';

	      const tokenCounts = new Map();
	      const bump = (t, w = 1) => {
	        const key = safeText(t, '').toLowerCase();
	        if (!key || key.length < 3) return;
	        if (['con', 'para', 'por', 'del', 'las', 'los', 'una', 'uno', 'que', 'the', 'and'].includes(key)) return;
	        tokenCounts.set(key, (tokenCounts.get(key) || 0) + w);
	      };
	      for (const c of (Array.isArray(clipsCache) ? clipsCache : []).slice(0, 240)) {
	        const tags = Array.isArray(c?.tags) ? c.tags : [];
	        tags.slice(0, 18).forEach((t) => bump(t, 2));
	        safeText(c?.title, '').split(/\s+/).slice(0, 12).forEach((t) => bump(t, 1));
	      }
	      for (const ev of (Array.isArray(timelineCache) ? timelineCache : []).slice(0, 700)) {
	        safeText(ev?.label, '').split(/\s+/).slice(0, 14).forEach((t) => bump(t, 1));
	      }
	      const top = Array.from(tokenCounts.entries())
	        .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
	        .slice(0, 10)
	        .map(([t]) => `#${escHtml(t)}`)
	        .join(' ');

	      const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
	      const clipPct = pct(clipDone, clipTotal);
	      const evPct = pct(evDone, evTotal);
	      const bar = (p) => `<div style="height:10px;border-radius:999px;border:1px solid rgba(148,163,184,0.18);background:rgba(2,6,23,0.35);overflow:hidden;"><div style="height:100%;width:${p}%;background:linear-gradient(135deg,#22d3ee,#67e8f9);"></div></div>`;

	      dashboardEl.innerHTML = `
	        <div class="row" style="align-items:center;">
	          <div style="display:flex;flex-direction:column;gap:0.2rem;min-width:0;">
	            <strong>Revisión</strong>
	            <small>Clips ${clipDone}/${clipTotal} · Timeline ${evDone}/${evTotal}</small>
	          </div>
	          <div style="display:grid;gap:0.3rem;min-width:180px;">
	            <div>${bar(clipPct)}</div>
	            <div style="opacity:0.78;">${bar(evPct)}</div>
	          </div>
	        </div>
	        <div class="row">
	          <div style="display:flex;flex-direction:column;gap:0.25rem;min-width:0;">
	            <strong>Eventos</strong>
	            <small>${kindsLine}</small>
	          </div>
	        </div>
	        <div class="row">
	          <div style="display:flex;flex-direction:column;gap:0.25rem;min-width:0;">
	            <strong>Temas</strong>
	            <small style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${top || '—'}</small>
	          </div>
	        </div>
	      `;
	    };

	    const updatePlaylistCount = () => {
	      if (!playlistCountEl) return;
	      playlistCountEl.textContent = `${selectedClipIds.size} seleccionados`;
	      try { updatePlaylistExportAvailability(); } catch (e) { /* ignore */ }
	    };

	    const clipById = (id) => {
	      const x = (Array.isArray(clipsCache) ? clipsCache : []).find((c) => Number(c?.id) === Number(id));
	      return x || null;
	    };

	    const selectedClipsOrdered = () => {
	      const items = [];
	      for (const id of selectedClipIds) {
	        const c = clipById(id);
	        if (c) items.push(c);
	      }
	      return items.sort((a, b) => (Number(a?.in_s) || 0) - (Number(b?.in_s) || 0) || (Number(a?.id) || 0) - (Number(b?.id) || 0));
	    };

	    // AI helper (server)
	    let aiLastPayload = null;
	    const buildAiClipIds = () => {
	      if (selectedClipIds.size > 0) {
	        return selectedClipsOrdered().map((c) => Number(c?.id) || 0).filter((x) => x > 0).slice(0, 120);
	      }
	      const q = safeText(clipSearchInput?.value, '');
	      const coll = safeText(clipCollectionFilterSelect?.value, '');
	      const hasFilter = Boolean(q || coll);
	      if (!hasFilter) return [];
	      const filtered = applyClipFilters(clipsCache);
	      return filtered.slice(0, 120).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
	    };

	    const renderAiPayload = (payload, meta = {}) => {
	      if (!aiOutputEl) return;
	      const p = payload && typeof payload === 'object' ? payload : {};
	      aiLastPayload = p;
	      const lines = [];
	      const summary = safeText(p.summary, '');
	      if (summary) lines.push(summary, '');
	      const moments = Array.isArray(p.key_moments) ? p.key_moments : [];
	      if (moments.length) {
	        lines.push('Momentos clave:');
	        for (const m of moments.slice(0, 14)) {
	          const t = fmtTimeShort(Number(m?.time_s) || 0);
	          const title = safeText(m?.title, safeText(m?.kind, 'Momento')).slice(0, 140);
	          lines.push(`- ${t} · ${title}`);
	        }
	        lines.push('');
	      }
	      const focus = Array.isArray(p.training_focus) ? p.training_focus : [];
	      if (focus.length) {
	        lines.push('Foco de entrenamiento:');
	        for (const f of focus.slice(0, 10)) lines.push(`- ${safeText(f).slice(0, 220)}`);
	        lines.push('');
	      }
	      const tags = Array.isArray(p.recommended_tags) ? p.recommended_tags : [];
	      if (tags.length) lines.push(`Tags sugeridos: ${tags.slice(0, 12).map((t) => safeText(t)).filter(Boolean).join(', ')}`, '');
	      const caveats = Array.isArray(p.caveats) ? p.caveats : [];
	      if (caveats.length) {
	        lines.push('Notas:');
	        for (const c of caveats.slice(0, 8)) lines.push(`- ${safeText(c).slice(0, 220)}`);
	      }
	      if (!lines.length) lines.push('Sin resultado IA todavía.');
	      aiOutputEl.textContent = lines.join('\n').trim() + '\n';
	      if (aiMetaEl) {
	        const provider = safeText(meta.provider, safeText(p.provider_note, ''));
	        const model = safeText(meta.model, '');
	        const when = safeText(meta.updated_at, '');
	        const cached = meta.cached ? ' · cache' : '';
	        aiMetaEl.textContent = [provider ? `Proveedor: ${provider}` : '', model ? `Modelo: ${model}` : '', when ? `Actualizado: ${fmtIsoShort(when)}` : '']
	          .filter(Boolean).join(' · ') + cached;
	      }
	    };

	    const fetchAi = async (force = false) => {
	      if (!aiUrl || !videoId) return;
	      try {
	        if (aiMetaEl) aiMetaEl.textContent = force ? 'Generando (recalcular)…' : 'Generando…';
	        setStatus('Asistente IA: generando…');
	        const resp = await fetch(aiUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify({ video_id: videoId, clip_ids: buildAiClipIds(), force: Boolean(force), context: safeText(aiContextInput?.value, '').slice(0, 600) }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        renderAiPayload(data?.payload, { provider: data?.provider, model: data?.model, cached: Boolean(data?.cached), updated_at: data?.updated_at || '' });
	        if (safeText(data?.error, '')) setStatus(`IA (fallback). ${safeText(data?.error)}`, false);
	        else setStatus('IA lista.');
	      } catch (e) {
	        if (aiMetaEl) aiMetaEl.textContent = 'No se pudo generar.';
	        setStatus(`No se pudo generar IA. ${safeText(e?.message, '')}`, true);
	      }
	    };

	    aiGenerateBtn?.addEventListener('click', () => fetchAi(false));
	    aiForceBtn?.addEventListener('click', () => fetchAi(true));
	    aiToTimelineBtn?.addEventListener('click', async () => {
	      if (!timelineSaveUrl || !videoId) return;
	      const p = aiLastPayload && typeof aiLastPayload === 'object' ? aiLastPayload : {};
	      const moments = Array.isArray(p.key_moments) ? p.key_moments : [];
	      if (!moments.length) { setStatus('IA sin momentos clave.', true); return; }
	      const ok = window.confirm(`Crear ${Math.min(12, moments.length)} eventos en Timeline a partir de la IA?`);
	      if (!ok) return;
	      const mapKind = (k) => {
	        const v = safeText(k, '').toLowerCase();
	        if (['goal', 'gol'].includes(v)) return 'goal';
	        if (['shot', 'disparo', 'tiro'].includes(v)) return 'shot';
	        if (['press', 'presión', 'presion'].includes(v)) return 'press';
	        if (['turnover', 'pérdida', 'perdida'].includes(v)) return 'turnover';
	        if (['abp', 'set_piece', 'balón parado', 'balon parado'].includes(v)) return 'abp';
	        if (['note', 'nota'].includes(v)) return 'note';
	        return 'tag';
	      };
	      try {
	        setStatus('Creando eventos IA…');
	        for (const m of moments.slice(0, 12)) {
	          const timeS = Number(m?.time_s) || 0;
	          const kind = mapKind(m?.kind);
	          const label = safeText(m?.title, safeText(m?.kind, 'IA')).slice(0, 160);
	          // eslint-disable-next-line no-await-in-loop
	          const resp = await fetch(timelineSaveUrl, {
	            method: 'POST',
	            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	            credentials: 'same-origin',
	            body: JSON.stringify({ video_id: videoId, time_s: timeS, kind, label, color: strokeColor() }),
	          });
	          const data = await resp.json().catch(() => ({}));
	          if (!resp.ok || !data?.ok) break;
	          // eslint-disable-next-line no-await-in-loop
	          await sleep(40);
	        }
	        await refreshTimeline();
	        setStatus('Eventos IA añadidos a Timeline.');
	      } catch (e) {
	        setStatus('No se pudieron crear eventos IA.', true);
	      }
	    });
	    aiCopyBtn?.addEventListener('click', async () => {
	      const text = safeText(aiOutputEl?.textContent, '');
	      if (!text) return;
	      try {
	        await navigator.clipboard.writeText(text);
	        setStatus('IA copiada.');
	      } catch (e) {
	        setStatus('No se pudo copiar.', true);
	      }
	    });

	    const drawThumbDataUrl = () => {
	      try {
	        const w = 320;
	        const h = 180;
	        const off = document.createElement('canvas');
	        off.width = w;
	        off.height = h;
	        const ctx = off.getContext('2d', { alpha: false });
	        if (!ctx) return null;
	        ctx.fillStyle = '#000';
	        ctx.fillRect(0, 0, w, h);
	        ctx.drawImage(thumbVideo, 0, 0, w, h);
	        return off.toDataURL('image/jpeg', 0.72);
	      } catch (e) {
	        return null;
	      }
	    };

	    const seekThumb = (t) => new Promise((resolve) => {
	      let done = false;
	      const onSeeked = () => {
	        if (done) return;
	        done = true;
	        try { thumbVideo.removeEventListener('seeked', onSeeked); } catch (e) { /* ignore */ }
	        resolve(true);
	      };
	      const timeout = window.setTimeout(() => {
	        if (done) return;
	        done = true;
	        try { thumbVideo.removeEventListener('seeked', onSeeked); } catch (e) { /* ignore */ }
	        resolve(false);
	      }, 2200);
	      thumbVideo.addEventListener('seeked', () => {
	        try { window.clearTimeout(timeout); } catch (e) { /* ignore */ }
	        onSeeked();
	      }, { once: true });
	      try { thumbVideo.currentTime = Math.max(0, Number(t) || 0); } catch (e) { resolve(false); }
	    });

	    const captureThumbDataUrlAt = async (t) => {
	      try {
	        if (!thumbVideo.src) return null;
	        // Mantenerlo ligero: best-effort. Si no se puede (CORS/seek), devolvemos null.
	        const ok = await seekThumb(t);
	        if (!ok) return null;
	        await sleep(70);
	        return drawThumbDataUrl();
	      } catch (e) {
	        return null;
	      }
	    };

	    const processThumbQueue = async () => {
	      if (thumbBusy) return;
	      if (thumbQueue.length === 0) return;
	      if (!thumbVideo.src) return;
	      // Evitar generar thumbs mientras se exporta/graba.
	      if (recActive) return;
	      thumbBusy = true;
	      try {
	        while (thumbQueue.length && thumbCache.size < 42) {
	          const id = thumbQueue.shift();
	          thumbQueued.delete(id);
	          if (!id || thumbCache.has(id)) continue;
	          const clip = clipById(id);
	          if (!clip) continue;
	          // No interrumpir reproducción/lista: solo generamos si el vídeo principal está en pausa.
	          if (!video.paused) break;
	          const t = Number(clip?.in_s) || 0;
	          // eslint-disable-next-line no-await-in-loop
	          const ok = await seekThumb(t);
	          if (!ok) continue;
	          // eslint-disable-next-line no-await-in-loop
	          await sleep(80);
	          const dataUrl = drawThumbDataUrl();
	          if (!dataUrl) continue;
	          thumbCache.set(id, dataUrl);
	          try {
	            const img = clipsList?.querySelector?.(`[data-vs-clip-thumb="${id}"]`);
	            if (img && !img.src) img.src = dataUrl;
	          } catch (e) { /* ignore */ }
	        }
	      } finally {
	        thumbBusy = false;
	      }
	    };

	    const ensureThumb = (id) => {
	      if (!id) return;
	      if (thumbCache.has(id)) return;
	      if (thumbQueued.has(id)) return;
	      thumbQueued.add(id);
	      thumbQueue.push(id);
	      processThumbQueue();
	    };

	    try {
	      video.addEventListener('pause', () => processThumbQueue());
	    } catch (e) { /* ignore */ }

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

	    const loadInboxRecipients = async () => {
	      if (!inboxRecipientsUrl || !inboxUsersSelect) return;
	      inboxUsersSelect.innerHTML = '';
	      try {
	        const resp = await fetch(inboxRecipientsUrl, { credentials: 'same-origin' });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        const items = Array.isArray(data?.items) ? data.items : [];
	        inboxUsersSelect.innerHTML = items.slice(0, 240).map((u) => {
	          const id = Number(u?.id) || 0;
	          if (!id) return '';
	          const label = escHtml(safeText(u?.label, safeText(u?.username, `User ${id}`)));
	          return `<option value="${id}">${label}</option>`;
	        }).filter(Boolean).join('');
	      } catch (e) {
	        inboxUsersSelect.innerHTML = '<option value="">(No disponible)</option>';
	      }
	    };

	    const selectedInboxUserIds = () => {
	      try {
	        const opts = Array.from(inboxUsersSelect?.selectedOptions || []);
	        return opts.map((o) => Number(o.value) || 0).filter((x) => x > 0).slice(0, 40);
	      } catch (e) {
	        return [];
	      }
	    };

	    const sendInbox = async (payload) => {
	      if (!inboxSendUrl) { setStatus('Inbox no disponible.', true); return false; }
	      const userIds = selectedInboxUserIds();
	      if (!userIds.length) { setStatus('Elige destinatarios.', true); return false; }
	      const message = safeText(inboxMessageInput?.value, '').slice(0, 2000);
	      try {
	        const resp = await fetch(inboxSendUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify({ ...payload, user_ids: userIds, message }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        setStatus(`Enviado a ${data?.created || userIds.length} usuario(s).`);
	        return true;
	      } catch (e) {
	        setStatus('No se pudo enviar.', true);
	        return false;
	      }
	    };

	    inboxSendClipBtn?.addEventListener('click', async () => {
	      if (!activeClipId) { setStatus('Selecciona o guarda un clip.', true); return; }
	      const clip = clipById(activeClipId);
	      const title = clip ? safeText(clip?.title, '') : '';
	      await sendInbox({ kind: 'clip', clip_id: activeClipId, title });
	    });
	    inboxSendPlaylistBtn?.addEventListener('click', async () => {
	      const picked = selectedClipsOrdered();
	      const base = picked.length ? picked : applyClipFilters(clipsCache);
	      const ids = base.slice(0, 80).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
	      if (!ids.length) { setStatus('No hay clips para enviar.', true); return; }
	      await sendInbox({ kind: 'playlist', video_id: videoId, clip_ids: ids, title: `Playlist · ${ids.length} clips` });
	    });
	    inboxSendExportBtn?.addEventListener('click', async () => {
	      if (!lastExportAssetId) { setStatus('Primero sube un export (Export + compartir).', true); return; }
	      await sendInbox({ kind: 'export', export_id: lastExportAssetId, title: safeText(clipTitleInput?.value, '') || 'Export' });
	    });
	    inboxSendReportBtn?.addEventListener('click', async () => {
	      const computeReportClipIds = () => {
	        if (selectedClipIds.size > 0) {
	          return selectedClipsOrdered().slice(0, 260).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
	        }
	        const q = safeText(clipSearchInput?.value, '');
	        const coll = safeText(clipCollectionFilterSelect?.value, '');
	        const hasFilter = Boolean(q || coll);
	        if (!hasFilter) return [];
	        const filtered = applyClipFilters(clipsCache);
	        return filtered.slice(0, 260).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
	      };
	      await sendInbox({
	        kind: 'report',
	        video_id: videoId,
	        clip_ids: computeReportClipIds(),
	        include_ai: Boolean(aiIncludeReportToggle?.checked),
	        title: safeText(buildExportTitle(), 'Informe'),
	      });
	    });
	    loadInboxRecipients();

		    const renderClips = (items) => {
		      if (!clipsList) return;
	      const total = Array.isArray(clipsCache) ? clipsCache.length : 0;
	      const baseItems = Array.isArray(items) ? items : [];
	      const filteredItems = reviewFilterState.clipsOnlyUnreviewed
	        ? baseItems.filter((c) => {
	          const id = Number(c?.id) || 0;
	          return id > 0 && !reviewedClipIds.has(id);
	        })
	        : baseItems;
		      const shown = filteredItems.length;
		      if (clipCountEl) clipCountEl.textContent = `${shown}/${total} clips`;
          if (clipsCountSimpleEl) {
            clipsCountSimpleEl.textContent = (shown === total) ? `${total} clips` : `${shown}/${total} clips`;
          }
	      const rows = filteredItems.slice(0, 120).map((c) => {
	        const id = Number(c?.id) || 0;
	        if (!id) return '';
	        const title = safeText(c?.title, `Clip #${id}`);
	        const coll = safeText(c?.collection, '');
	        const thumbUrl = safeText(c?.thumbnail_url, '');
	        const inS = Number(c?.in_s) || 0;
	        const outS = Number(c?.out_s) || 0;
	        const tags = Array.isArray(c?.tags) ? c.tags : [];
	        const tagsLabel = tags.length ? ` · ${tags.slice(0, 6).map((t) => `#${safeText(t)}`).join(' ')}` : '';
	        const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS || inS)}`;
	        const durS = Math.max(0, (outS || 0) - (inS || 0));
	        const durLabel = durS ? fmtTimeShort(durS) : '00:00';
	        const checked = selectedClipIds.has(id) ? 'checked' : '';
	        const reviewed = reviewedClipIds.has(id);
	        return `
	            <div class="row" style="${reviewed ? 'opacity:0.86;' : ''}">
	            <div style="display:flex; gap:0.6rem; align-items:flex-start; width:100%; flex-wrap:wrap;">
                <input type="checkbox" data-vs-clip-select="${id}" ${checked} style="margin-top:0.25rem; width:18px;height:18px;accent-color:#22d3ee; flex:0 0 auto;" />
                <div style="width:76px;height:46px;border-radius:12px;overflow:hidden;background:rgba(2,6,23,0.35);border:1px solid rgba(148,163,184,0.14);flex:0 0 auto;">
                  <img data-vs-clip-thumb="${id}" data-vs-clip-thumb-url="${escHtml(thumbUrl)}" alt="" style="width:100%;height:100%;object-fit:cover;display:block;" />
                </div>
	              <div style="display:flex; flex-direction:column; gap:0.1rem; min-width:240px; flex:1;">
	                <div style="display:flex; gap:0.45rem; align-items:baseline; min-width:0;">
	                  <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; min-width:0;">${title}</strong>
	                  <small style="white-space:nowrap; opacity:0.9; flex:0 0 auto;">⏱ ${durLabel}</small>
	                </div>
	                <small style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${coll ? `${coll} · ` : ''}${label}${tagsLabel}</small>
	              </div>
		            <div style="display:flex; gap:0.35rem; flex-wrap:wrap; justify-content:flex-end; margin-left:auto;">
		              <button type="button" class="button ${reviewed ? 'primary' : 'ghost'}" data-vs-clip-review="${id}" title="Marcar revisado">${reviewed ? '✓' : '○'}</button>
		              <button type="button" class="button" data-vs-clip-play="${id}">Play</button>
		              <button type="button" class="button" data-vs-clip-load="${id}">Abrir</button>
		              <button type="button" class="button" data-vs-clip-link="${id}" data-vs-clip-view="${safeText(c?.view_url, '')}">Link</button>
		              <button type="button" class="button" data-vs-clip-export-server="${id}" title="Descargar MP4 (servidor)">Descargar</button>
		              <button type="button" class="button" data-vs-clip-share="${id}">Share</button>
		              <button type="button" class="button danger" data-vs-clip-del="${id}">Borrar</button>
		            </div>
              </div>
	          </div>
	        `;
      }).filter(Boolean).join('');
      clipsList.innerHTML = rows || '<div class="meta">Sin clips guardados.</div>';

      // Miniaturas (lazy)
      try {
        if (!thumbObserver && 'IntersectionObserver' in window) {
          thumbObserver = new IntersectionObserver((entries) => {
            for (const ent of entries) {
              if (!ent.isIntersecting) continue;
              const img = ent.target;
              const id = Number(img?.getAttribute?.('data-vs-clip-thumb') || 0);
              if (id) ensureThumb(id);
              try { thumbObserver.unobserve(img); } catch (e) { /* ignore */ }
            }
          }, { root: null, rootMargin: '160px', threshold: 0.12 });
        }
        Array.from(clipsList.querySelectorAll('[data-vs-clip-thumb]')).forEach((img) => {
          const id = Number(img.getAttribute('data-vs-clip-thumb') || 0);
          const serverUrl = safeText(img.getAttribute('data-vs-clip-thumb-url'), '');
          if (serverUrl) {
            img.src = serverUrl;
            try { if (thumbObserver) thumbObserver.unobserve(img); } catch (e) { /* ignore */ }
            return;
          }
          const cached = id ? thumbCache.get(id) : '';
          if (cached) {
            img.src = cached;
            return;
          }
          img.src = '';
          if (thumbObserver) thumbObserver.observe(img);
        });
      } catch (e) { /* ignore */ }

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
                updateClipUiState();
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

	      Array.from(clipsList.querySelectorAll('[data-vs-clip-review]')).forEach((btn) => {
	        btn.addEventListener('click', async () => {
	          const id = Number(btn.getAttribute('data-vs-clip-review') || 0);
	          if (!id) return;
	          const next = !reviewedClipIds.has(id);
	          const ok = await setReviewed({ kind: 'clip', objectId: id, done: next });
	          if (!ok) { setStatus('No se pudo marcar.', true); return; }
	          if (next) reviewedClipIds.add(id);
	          else reviewedClipIds.delete(id);
	          renderClips(applyClipFilters(clipsCache));
	          renderDashboard();
	          setStatus(next ? 'Clip revisado.' : 'Revisión quitada.');
	        });
	      });

	      Array.from(clipsList.querySelectorAll('[data-vs-clip-select]')).forEach((chk) => {
	        chk.addEventListener('change', () => {
	          const id = Number(chk.getAttribute('data-vs-clip-select') || 0);
	          if (!id) return;
	          if (chk.checked) selectedClipIds.add(id);
	          else selectedClipIds.delete(id);
	          updatePlaylistCount();
	        });
	      });

	      const playClipOnce = async (clip) => {
	        if (!clip) return;
	        playlistActive = false;
	        playlistIds = [];
	        playlistIndex = 0;
	        clipBoundActive = true;
	        const start = Number(clip?.in_s) || 0;
	        const end = Number(clip?.out_s) || 0;
	        if (inInput) inInput.value = String(start.toFixed(1));
	        if (outInput) outInput.value = String(end.toFixed(1));
	        clipBoundStart = Math.max(0, Math.min(start, end));
	        clipBoundEnd = Math.max(start, end);
	        try { video.currentTime = Math.max(0, start); } catch (e) { /* ignore */ }
	        try { await video.play(); } catch (e) { /* ignore */ }
	        setStatus(`Play clip: ${fmtTimeShort(start)} → ${fmtTimeShort(end || start)}`);
	      };

	      Array.from(clipsList.querySelectorAll('[data-vs-clip-play]')).forEach((btn) => {
	        btn.addEventListener('click', async () => {
	          const id = Number(btn.getAttribute('data-vs-clip-play') || 0);
	          if (!id) return;
	          const clip = clipById(id);
	          await playClipOnce(clip);
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
	      Array.from(clipsList.querySelectorAll('[data-vs-clip-export-server]')).forEach((btn) => {
	        btn.addEventListener('click', async () => {
	          const id = Number(btn.getAttribute('data-vs-clip-export-server') || 0);
	          if (!id) return;
	          if (!exportServerUrl) {
	            setStatus('No hay endpoint para MP4 server.', true);
	            return;
	          }
	          try {
	            btn.disabled = true;
	            setStatus('Generando MP4 en servidor…');
	            const resp = await fetch(exportServerUrl, {
	              method: 'POST',
	              credentials: 'same-origin',
	              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	              body: JSON.stringify({ video_id: videoId || 0, clip_id: id }),
	            });
	            const data = await resp.json().catch(() => ({}));
	            if (!resp.ok || !data?.ok || !data?.url) {
	              setStatus(data?.error || 'No se pudo exportar MP4 en servidor.', true);
	              return;
	            }
	            const url = String(data.url);
	            const downloadUrl = String(data.download_url || url);
	            lastExportAssetId = Number(data?.id) || lastExportAssetId || 0;
	            lastExportShareUrl = url;
              triggerDownload(downloadUrl);
              try { await tryCopy(downloadUrl); } catch (e) { /* ignore */ }
              setStatus('MP4 listo. Descargando…');
	            refreshShareLinks();
	          } catch (e) {
	            setStatus('Error exportando MP4 en servidor.', true);
	          } finally {
	            btn.disabled = false;
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
		        renderDashboard();
		        renderMiniTimeline();
		      } catch (e) {
		        clipsCache = [];
		        rebuildCollectionFilters([]);
		        renderClips([]);
		        renderDashboard();
		        renderMiniTimeline();
		      }
		    };

		    const updateClipUiState = () => {
		      try {
		        const isEditing = Boolean(activeClipId);
		        if (clipSaveBtn) clipSaveBtn.textContent = isEditing ? 'Actualizar' : 'Guardar';
		        if (clipSaveBtn) clipSaveBtn.title = isEditing ? 'Actualiza el clip cargado' : 'Crea un clip nuevo';
		        if (clipSaveQuickBtn) clipSaveQuickBtn.title = 'Crea un clip nuevo con el segmento IN/OUT';
		      } catch (e) { /* ignore */ }
		    };

		    const clearActiveClip = () => {
		      activeClipId = 0;
		      updateClipUiState();
		      setStatus('Nuevo clip.');
		    };

	    const saveClip = async (opts = {}) => {
	      if (!clipSaveUrl || !videoId) return null;
	      const forceNew = Boolean(opts?.forceNew);
	      const title = safeText(clipTitleInput?.value, 'Clip').slice(0, 180);
	      const ctxTeam = safeText(ctxTeamSelect?.value, '').toUpperCase();
	      const ctxPhase = safeText(ctxPhaseSelect?.value, '');
	      let collection = safeText(clipCollectionInput?.value, '').slice(0, 120);
	      const tags = parseTagsInput();
	      if (ctxTeam && !tags.includes(`team:${ctxTeam}`)) tags.push(`team:${ctxTeam}`);
	      if (ctxPhase && !tags.includes(`phase:${ctxPhase}`)) tags.push(`phase:${ctxPhase}`);
	      if (!collection && ctxTeam) collection = ctxTeam;
	      const notes = safeText(clipNotesInput?.value, '').slice(0, 5000);
	      const inS = Number(inInput?.value || 0) || 0;
	      const outS = Number(outInput?.value || 0) || 0;
      if (!outS || outS <= inS) {
        setStatus('Define IN/OUT para el clip.', true);
        return null;
      }
	      const overlay = { ...fabricCanvas.toDatalessJSON(['data']), fx: { layers: fxState.layers } };
	      try {
	        const clipId = forceNew ? 0 : (activeClipId || 0);
	        const thumbDataUrl = await captureThumbDataUrlAt(inS);
	        const payload = { id: clipId, video_id: videoId, title, collection, in_s: inS, out_s: outS, overlay, tags, notes };
	        if (thumbDataUrl) payload.thumbnail_data_url = thumbDataUrl;
		        const resp = await fetch(clipSaveUrl, {
		          method: 'POST',
		          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
		          credentials: 'same-origin',
		          body: JSON.stringify(payload),
		        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        const savedId = Number(data?.id) || 0;
	        // Mantener el clip recién creado como "activo" evita duplicados al editar título/notas desde la barra lateral.
	        // El botón "Guardar" rápido (toolbar) siempre usa `forceNew:true`, así que seguirá creando múltiples clips aunque
	        // exista `activeClipId`.
	        if (savedId) activeClipId = savedId;
	        await refreshClips();
	        updateClipUiState();
	        try {
	          const d = new Date();
          const hh = String(d.getHours()).padStart(2, '0');
          const mm = String(d.getMinutes()).padStart(2, '0');
          const ss = String(d.getSeconds()).padStart(2, '0');
          const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS)}`;
	          if (clipSavedMsg) clipSavedMsg.textContent = `Guardado ✓ · ${hh}:${mm}:${ss} · id ${savedId || ''} · ${label}`;
	        } catch (e) { /* ignore */ }
        try {
          if (clipSaveBtn) {
            const old = clipSaveBtn.textContent;
            clipSaveBtn.textContent = 'Guardado ✓';
            window.setTimeout(() => { try { clipSaveBtn.textContent = old; } catch (e2) { /* ignore */ } }, 900);
          }
        } catch (e) { /* ignore */ }
        try {
          const flash = (el) => {
            if (!el || !el.classList) return;
            el.classList.remove('vs-flash');
            // Fuerza reflow
            void el.offsetWidth;
            el.classList.add('vs-flash');
            window.setTimeout(() => { try { el.classList.remove('vs-flash'); } catch (e2) { /* ignore */ } }, 1800);
          };
	          const revealClipRow = () => {
	            const savedId = Number(data?.id) || activeClipId || 0;
	            if (!savedId || !clipsList) return false;
	            const btn = clipsList.querySelector?.(`[data-vs-clip-load="${savedId}"]`);
	            const row = btn?.closest?.('.row') || btn?.parentElement;
	            if (!row) return false;
	            try { row.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) { /* ignore */ }
	            flash(row);
	            return true;
	          };
          const hasFilters = Boolean(safeText(clipSearchInput?.value, '') || safeText(clipCollectionFilterSelect?.value, '') || Boolean(filterUnreviewedClipsToggle?.checked));
          let ok = revealClipRow();
          if (!ok && hasFilters && clipClearFiltersBtn) {
            clipClearFiltersBtn.click();
            window.setTimeout(() => { revealClipRow(); }, 50);
          }
        } catch (e) { /* ignore */ }
        setStatus(`Clip guardado (#${activeClipId || ''}).`);
        return savedId || null;
      } catch (e) {
        try { if (clipSavedMsg) clipSavedMsg.textContent = 'No se pudo guardar.'; } catch (e2) { /* ignore */ }
        setStatus('No se pudo guardar clip.', true);
        return null;
      }
	    };

	    const duplicateActiveClip = async () => {
	      if (!clipSaveUrl || !videoId) return;
	      if (!activeClipId) { setStatus('Abre un clip primero.', true); return; }
	      const c = clipById(activeClipId);
	      if (!c) { setStatus('Clip no encontrado en cache.', true); return; }
	      const title = (safeText(c?.title, '').slice(0, 160) || `Clip ${activeClipId}`) + ' (copia)';
	      try {
	        const resp = await fetch(clipSaveUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify({
	            id: 0,
	            video_id: videoId,
	            title,
	            collection: safeText(c?.collection, '').slice(0, 120),
	            in_s: Number(c?.in_s) || 0,
	            out_s: Number(c?.out_s) || 0,
	            tags: Array.isArray(c?.tags) ? c.tags : [],
	            notes: safeText(c?.notes, ''),
	            overlay: c?.overlay || {},
	          }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        await refreshClips();
	        setStatus('Clip duplicado.');
	      } catch (e) {
	        setStatus('No se pudo duplicar.', true);
	      }
	    };

	    const splitActiveClipAtPlayhead = async () => {
	      if (!clipSaveUrl || !videoId) return;
	      if (!activeClipId) { setStatus('Abre un clip primero.', true); return; }
	      const c = clipById(activeClipId);
	      if (!c) { setStatus('Clip no encontrado en cache.', true); return; }
	      const inS = Number(c?.in_s) || 0;
	      const outS = Number(c?.out_s) || 0;
	      const t = Number(video.currentTime || 0) || 0;
	      if (!outS || outS <= inS) { setStatus('Clip sin OUT válido.', true); return; }
	      if (t <= inS + 0.05 || t >= outS - 0.05) { setStatus('El playhead debe estar dentro del clip.', true); return; }
	      try {
	        // 1) Actualiza el clip actual (OUT = t)
	        const resp1 = await fetch(clipSaveUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify({
	            id: activeClipId,
	            video_id: videoId,
	            title: safeText(c?.title, '').slice(0, 180),
	            collection: safeText(c?.collection, '').slice(0, 120),
	            in_s: inS,
	            out_s: t,
	            tags: Array.isArray(c?.tags) ? c.tags : [],
	            notes: safeText(c?.notes, ''),
	            overlay: c?.overlay || {},
	          }),
	        });
	        const data1 = await resp1.json().catch(() => ({}));
	        if (!resp1.ok || !data1?.ok) throw new Error(data1?.error || 'error');

	        // 2) Crea el segundo clip (IN = t, OUT = oldOut)
	        const title2 = (safeText(c?.title, '').slice(0, 160) || `Clip ${activeClipId}`) + ' (2)';
	        const resp2 = await fetch(clipSaveUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify({
	            id: 0,
	            video_id: videoId,
	            title: title2,
	            collection: safeText(c?.collection, '').slice(0, 120),
	            in_s: t,
	            out_s: outS,
	            tags: Array.isArray(c?.tags) ? c.tags : [],
	            notes: safeText(c?.notes, ''),
	            overlay: c?.overlay || {},
	          }),
	        });
	        const data2 = await resp2.json().catch(() => ({}));
	        if (!resp2.ok || !data2?.ok) throw new Error(data2?.error || 'error');

	        await refreshClips();
	        setStatus('Clip dividido.');
	      } catch (e) {
	        setStatus('No se pudo dividir.', true);
	      }
		    };
		    clipSaveBtn?.addEventListener('click', () => saveClip({ forceNew: false }));
        clipSaveQuickBtn?.addEventListener('click', () => saveClip({ forceNew: true }));
        openMainCutBtn?.addEventListener('click', () => {
          try {
            const tabAdvanced = document.getElementById('vs-tab-advanced');
            tabAdvanced?.click?.();
          } catch (e) { /* ignore */ }
          window.setTimeout(() => {
            try {
              const details = document.getElementById('vs-acc-edit');
              if (details && details.tagName === 'DETAILS') details.open = true;
              details?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
            } catch (e) { /* ignore */ }
          }, 50);
        });
		    clipDupBtn?.addEventListener('click', duplicateActiveClip);
		    clipSplitBtn?.addEventListener('click', splitActiveClipAtPlayhead);
		    clipRefreshBtn?.addEventListener('click', refreshClips);
	    clipSearchInput?.addEventListener('input', () => renderClips(applyClipFilters(clipsCache)));
	    clipCollectionFilterSelect?.addEventListener('change', () => renderClips(applyClipFilters(clipsCache)));
	    filterUnreviewedClipsToggle?.addEventListener('change', () => {
	      reviewFilterState.clipsOnlyUnreviewed = Boolean(filterUnreviewedClipsToggle.checked);
	      renderClips(applyClipFilters(clipsCache));
	      renderDashboard();
	    });
	    clipClearFiltersBtn?.addEventListener('click', () => {
	      if (clipSearchInput) clipSearchInput.value = '';
	      if (clipCollectionFilterSelect) clipCollectionFilterSelect.value = '';
	      rebuildCollectionFilters(clipsCache);
	      renderClips(applyClipFilters(clipsCache));
	    });
	    const initialCollection = (() => {
	      try {
	        const url = new URL(window.location.href);
	        return safeText(url.searchParams.get('collection'), '').trim();
	      } catch (e) {
	        return '';
	      }
	    })();
		    refreshClips().then(() => {
          updateClipUiState();
		      if (initialCollection && clipCollectionFilterSelect) {
	        // Solo aplica si existe como opción (rebuildCollectionFilters ya ha poblado el select).
	        const has = Array.from(clipCollectionFilterSelect.options || []).some((opt) => safeText(opt?.value, '') === initialCollection);
	        if (has) {
	          clipCollectionFilterSelect.value = initialCollection;
	          renderClips(applyClipFilters(clipsCache));
	          rebuildCollectionFilters(clipsCache);
	        }
	      }
	      if (!initialClipId) return;
	      try {
	        const btn = clipsList?.querySelector?.(`[data-vs-clip-load="${initialClipId}"]`);
	        if (btn) btn.click();
	      } catch (e) { /* ignore */ }
	    });

	    updatePlaylistCount();
	    const stopPlaylist = () => {
	      playlistActive = false;
	      playlistIds = [];
	      playlistIndex = 0;
	      setStatus('Lista detenida.');
	    };
	    const startPlaylist = async () => {
	      const picked = selectedClipsOrdered();
	      const base = picked.length ? picked : applyClipFilters(clipsCache);
	      const ids = base.slice(0, 120).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
	      if (!ids.length) { setStatus('No hay clips para reproducir.', true); return; }
	      playlistActive = true;
	      playlistIds = ids;
	      playlistIndex = 0;
	      const first = clipById(ids[0]);
	      if (!first) { stopPlaylist(); return; }
	      const start = Number(first?.in_s) || 0;
	      const end = Number(first?.out_s) || 0;
	      if (inInput) inInput.value = String(start.toFixed(1));
	      if (outInput) outInput.value = String(end.toFixed(1));
	      try { video.currentTime = Math.max(0, start); } catch (e) { /* ignore */ }
	      try { await video.play(); } catch (e) { /* ignore */ }
	      setStatus(`Lista: 1/${playlistIds.length}`);
	    };

	    const playNextInPlaylist = async () => {
	      if (!playlistActive) return;
	      if (!playlistIds.length) return stopPlaylist();
	      playlistIndex += 1;
	      if (playlistIndex >= playlistIds.length) {
	        playlistActive = false;
	        setStatus('Lista finalizada.');
	        return;
	      }
	      const next = clipById(playlistIds[playlistIndex]);
	      if (!next) return stopPlaylist();
	      const start = Number(next?.in_s) || 0;
	      const end = Number(next?.out_s) || 0;
	      if (inInput) inInput.value = String(start.toFixed(1));
	      if (outInput) outInput.value = String(end.toFixed(1));
	      try { video.currentTime = Math.max(0, start); } catch (e) { /* ignore */ }
	      try { await video.play(); } catch (e) { /* ignore */ }
	      setStatus(`Lista: ${playlistIndex + 1}/${playlistIds.length}`);
	    };

	    const playlistAdvanceIfNeeded = () => {
	      if (!playlistActive) return;
	      if (playlistBusy) return;
	      const id = playlistIds[playlistIndex];
	      const clip = clipById(id);
	      if (!clip) return;
	      const end = Number(clip?.out_s) || 0;
	      if (!end) return;
	      const now = Number(video.currentTime) || 0;
	      if (now >= end - 0.03) {
	        playlistBusy = true;
	        playNextInPlaylist().finally(() => {
	          window.setTimeout(() => { playlistBusy = false; }, 120);
	        });
	      }
	    };

	    // Integración en timeupdate
	    video.addEventListener('timeupdate', playlistAdvanceIfNeeded);

	    playlistPlayBtn?.addEventListener('click', startPlaylist);
	    playlistStopBtn?.addEventListener('click', stopPlaylist);
	    playlistClearBtn?.addEventListener('click', () => {
	      selectedClipIds.clear();
	      updatePlaylistCount();
	      renderClips(applyClipFilters(clipsCache));
	    });
	    playlistShareBtn?.addEventListener('click', async () => {
	      if (!sharePlaylistCreateUrl) { setStatus('No hay endpoint para compartir lista.', true); return; }
	      const picked = selectedClipsOrdered();
	      const base = picked.length ? picked : applyClipFilters(clipsCache);
	      const ids = base.slice(0, 60).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
	      if (!ids.length) { setStatus('No hay clips para compartir.', true); return; }
	      setStatus('Creando enlace de lista…');
	      try {
	        const body = { clip_ids: ids, valid_days: 14 };
	        const resp = await fetch(sharePlaylistCreateUrl, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
	          credentials: 'same-origin',
	          body: JSON.stringify(body),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok || !data?.url) throw new Error(data?.error || 'error');
	        const url = String(data.url);
	        try {
	          if (navigator.clipboard?.writeText) {
	            await navigator.clipboard.writeText(url);
	            setStatus('Enlace de lista copiado.');
	          } else {
	            window.prompt('Copia este enlace:', url);
	            setStatus('Copia el enlace de lista.');
	          }
	        } catch (e) {
	          window.prompt('Copia este enlace:', url);
	        }
	        refreshShareLinks();
	      } catch (e) {
	        setStatus('No se pudo crear enlace de lista.', true);
	      }
	    });

		    shareRefreshBtn?.addEventListener('click', refreshShareLinks);
        if (!simpleUI) refreshShareLinks();

    // Timeline (server)
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
        const id = Number(ev?.id) || 0;
        if (kinds && !kinds.has(kind)) return false;
        if (reviewFilterState.eventsOnlyUnreviewed && id && reviewedEventIds.has(id)) return false;
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
        const kind = safeText(ev?.kind, 'tag');
        const label = safeText(ev?.label, '');
        const color = safeText(ev?.color, '');
        const payload = (ev && typeof ev.payload === 'object' && ev.payload) ? ev.payload : {};
        const ctxTeam = safeText(payload?.team, '').toUpperCase();
        const ctxPhase = safeText(payload?.phase, '');
        const ctxBadge = (ctxTeam || ctxPhase)
          ? `<span class="k" style="border-radius:999px; padding:0.12rem 0.6rem; min-width:auto;">${escHtml([ctxTeam, ctxPhase].filter(Boolean).join(' · '))}</span>`
          : '';
        const at = fmtTimeShort(Number(ev?.time_s) || 0);
      const timeVal = (Number(ev?.time_s) || 0).toFixed(1);
      const reviewed = reviewedEventIds.has(id);
      return `
          <div class="row" style="${reviewed ? 'opacity:0.86;' : ''}">
            <div style="display:grid; gap:0.4rem; width:100%;">
              <div style="display:flex; align-items:center; justify-content:space-between; gap:0.6rem;">
                <strong style="display:flex; gap:0.5rem; align-items:center;">
                  ${color ? `<span style="width:12px;height:12px;border-radius:999px;background:${color};display:inline-block;border:1px solid rgba(255,255,255,0.25);"></span>` : ''}
                  ${at} · ${safeText(kind, 'tag').toUpperCase()} ${ctxBadge}
                </strong>
                <div style="display:flex; gap:0.35rem; flex-wrap:wrap; align-items:center;">
                  <button type="button" class="button ${reviewed ? 'primary' : 'ghost'}" data-vs-ev-review="${id}" title="Marcar revisado">${reviewed ? '✓' : '○'}</button>
                  <button type="button" class="button" data-vs-ev-go="${id}">Ir</button>
                  <button type="button" class="button" data-vs-ev-now="${id}">Ahora</button>
                  <button type="button" class="button" data-vs-ev-clip="${id}" title="Crear clip alrededor de este evento">Clip</button>
                  <button type="button" class="button" data-vs-ev-save="${id}">Guardar</button>
                  <button type="button" class="button danger" data-vs-ev-del="${id}">Borrar</button>
                </div>
              </div>
              <div style="display:grid; grid-template-columns: 0.9fr 1fr 2fr; gap:0.45rem; align-items:center;">
                <input type="number" step="0.1" min="0" value="${escHtml(timeVal)}" data-vs-ev-time="${id}" title="Tiempo (s)" />
                <select data-vs-ev-kind="${id}" title="Tipo">
                  <option value="tag" ${kind === 'tag' ? 'selected' : ''}>Tag</option>
                  <option value="note" ${kind === 'note' ? 'selected' : ''}>Nota</option>
                  <option value="goal" ${kind === 'goal' ? 'selected' : ''}>Gol</option>
                  <option value="shot" ${kind === 'shot' ? 'selected' : ''}>Disparo</option>
                  <option value="press" ${kind === 'press' ? 'selected' : ''}>Presión</option>
                  <option value="turnover" ${kind === 'turnover' ? 'selected' : ''}>Pérdida</option>
                  <option value="abp" ${kind === 'abp' ? 'selected' : ''}>ABP</option>
                </select>
                <input type="text" value="${escHtml(label)}" data-vs-ev-label="${id}" placeholder="Etiqueta..." />
              </div>
            </div>
          </div>
        `;
      }).filter(Boolean).join('');
      timelineList.innerHTML = rows || '<div class="meta">Sin eventos.</div>';
      renderMiniTimeline();

      Array.from(timelineList.querySelectorAll('[data-vs-ev-review]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-ev-review') || 0);
          if (!id) return;
          const next = !reviewedEventIds.has(id);
          const ok = await setReviewed({ kind: 'event', objectId: id, done: next });
          if (!ok) { setStatus('No se pudo marcar.', true); return; }
          if (next) reviewedEventIds.add(id);
          else reviewedEventIds.delete(id);
          renderTimeline(timelineCache);
          renderDashboard();
          setStatus(next ? 'Evento revisado.' : 'Revisión quitada.');
        });
      });

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

      const createClipFromEvent = async (evItem) => {
        if (!clipSaveUrl || !videoId) return false;
        const timeS = Number(evItem?.time_s) || 0;
        const kind = safeText(evItem?.kind, 'tag').toLowerCase();
        const label = safeText(evItem?.label, '');
        const payload = (evItem && typeof evItem.payload === 'object' && evItem.payload) ? evItem.payload : {};
        const ctxTeam = safeText(payload?.team, safeText(ctxTeamSelect?.value, '')).toUpperCase();
        const ctxPhase = safeText(payload?.phase, safeText(ctxPhaseSelect?.value, ''));
        // Usamos el mismo pre/post que el auto-clip de presets (aunque esté desactivado).
        const pre = clamp(Number(autoClipState?.pre ?? 8) || 8, 0, 90);
        const post = clamp(Number(autoClipState?.post ?? 8) || 8, 0, 90);
        const inS = Math.max(0, timeS - pre);
        const outS = Math.max(inS + 0.2, timeS + post);
        const title = (label || `${kind.toUpperCase()} · ${fmtTimeShort(timeS)}`).slice(0, 180);
        let collection = safeText(clipCollectionInput?.value, '').slice(0, 120);
        if (!collection) collection = ctxTeam || (activePresetsPack === 'own' ? 'Propio' : 'Rival');
        const tags = [kind, 'timeline', ctxTeam ? `team:${ctxTeam}` : '', ctxPhase ? `phase:${ctxPhase}` : ''].filter(Boolean);
        try {
          const resp = await fetch(clipSaveUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ id: 0, video_id: videoId, title, collection, in_s: inS, out_s: outS, overlay: {}, tags, notes: '' }),
          });
          const data = await resp.json().catch(() => ({}));
          return Boolean(resp.ok && data?.ok);
        } catch (e) {
          return false;
        }
      };

      Array.from(timelineList.querySelectorAll('[data-vs-ev-clip]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-ev-clip') || 0);
          if (!id) return;
          const found = (Array.isArray(timelineCache) ? timelineCache : []).find((x) => Number(x?.id) === id) || null;
          if (!found) return;
          btn.disabled = true;
          const ok = await createClipFromEvent(found);
          btn.disabled = false;
          if (!ok) { setStatus('No se pudo crear clip desde evento.', true); return; }
          await refreshClips();
          setStatus('Clip creado desde evento.');
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

      Array.from(timelineList.querySelectorAll('[data-vs-ev-now]')).forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = Number(btn.getAttribute('data-vs-ev-now') || 0);
          if (!id) return;
          const inp = timelineList.querySelector(`[data-vs-ev-time="${id}"]`);
          if (!inp) return;
          try { inp.value = (Number(video.currentTime) || 0).toFixed(1); } catch (e) { /* ignore */ }
          setStatus('Tiempo actualizado (Ahora).');
        });
      });

      Array.from(timelineList.querySelectorAll('[data-vs-ev-save]')).forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = Number(btn.getAttribute('data-vs-ev-save') || 0);
          if (!id) return;
          if (!timelineSaveUrl || !videoId) return;
          const timeInp = timelineList.querySelector(`[data-vs-ev-time="${id}"]`);
          const kindSel = timelineList.querySelector(`[data-vs-ev-kind="${id}"]`);
          const labelInp = timelineList.querySelector(`[data-vs-ev-label="${id}"]`);
          const timeS = Number(timeInp?.value || 0) || 0;
          const kind = safeText(kindSel?.value, 'tag');
          const label = safeText(labelInp?.value, '');
          try {
            const resp = await fetch(timelineSaveUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
              credentials: 'same-origin',
              body: JSON.stringify({ id, video_id: videoId, time_s: timeS, kind, label, color: strokeColor() }),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
            await refreshTimeline();
            setStatus('Evento guardado.');
          } catch (e) {
            setStatus('No se pudo guardar evento.', true);
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
        renderDashboard();
      } catch (e) {
        renderTimeline([]);
        renderDashboard();
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
      const ctxTeam = safeText(ctxTeamSelect?.value, '').toUpperCase();
      const ctxPhase = safeText(ctxPhaseSelect?.value, '');
      const payload = {};
      if (ctxTeam) payload.team = ctxTeam;
      if (ctxPhase) payload.phase = ctxPhase;
      try {
        const resp = await fetch(timelineSaveUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ video_id: videoId, time_s: timeS, kind, label, color, payload }),
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

	    const runAutoCut = async () => {
	      if (!autocutUrl || !videoId) { setStatus('AutoCut no disponible.', true); return; }
	      const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
	      const pre = clamp(Number(autoClipState?.pre ?? 8) || 8, 0, 60);
	      const post = clamp(Number(autoClipState?.post ?? 8) || 8, 0, 60);
	      const profile = safeText(document.getElementById('vs-autocut-profile')?.value, 'balanced');
	      const includeKinds = [];
	      try {
	        if (document.getElementById('vs-autocut-kind-goal')?.checked) includeKinds.push('goal');
	        if (document.getElementById('vs-autocut-kind-shot')?.checked) includeKinds.push('shot');
	        if (document.getElementById('vs-autocut-kind-abp')?.checked) includeKinds.push('abp');
	        if (document.getElementById('vs-autocut-kind-press')?.checked) includeKinds.push('press');
	        if (document.getElementById('vs-autocut-kind-tag')?.checked) includeKinds.push('tag');
	      } catch (e) { /* ignore */ }
	      try {
	        if (autocutRunBtn) autocutRunBtn.disabled = true;
	        setStatus('AutoCut: analizando… (puede tardar)');
	        const resp = await fetch(autocutUrl, {
	          method: 'POST',
          credentials: 'same-origin',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	          body: JSON.stringify({
	            video_id: videoId,
	            profile,
	            include_kinds: includeKinds.length ? includeKinds : undefined,
	            max_moments: 18,
	            min_gap_s: 25,
	            pre_s: pre,
	            post_s: post,
	            replace: false,
	          }),
	        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo ejecutar AutoCut.');
        await refreshTimeline();
        await refreshClips();
        setStatus(`AutoCut OK · eventos ${Number(data?.created_events || 0)} · clips ${Number(data?.created_clips || 0)}`);
      } catch (e) {
        setStatus('AutoCut: error analizando.', true);
        try { alert(String(e?.message || 'Error AutoCut')); } catch (err) { /* ignore */ }
      } finally {
        if (autocutRunBtn) autocutRunBtn.disabled = false;
      }
    };
    autocutRunBtn?.addEventListener('click', runAutoCut);

    const defaultEventPresets = () => ([
      { kind: 'press', label: 'Presión tras pérdida', hotkey: '1', color: '#22d3ee' },
      { kind: 'turnover', label: 'Pérdida / riesgo en inicio', hotkey: '2', color: '#fb7185' },
      { kind: 'abp', label: 'ABP (córner / falta)', hotkey: '3', color: '#facc15' },
      { kind: 'shot', label: 'Finalización (disparo)', hotkey: '4', color: '#a78bfa' },
      { kind: 'goal', label: 'Gol', hotkey: '5', color: '#f59e0b' },
      { kind: 'note', label: 'Nota táctica', hotkey: '6', color: '#60a5fa' },
      { kind: 'tag', label: 'Centro lateral', hotkey: '7', color: '#34d399' },
      { kind: 'tag', label: 'Salida vs presión', hotkey: '8', color: '#38bdf8' },
      { kind: 'tag', label: 'Transición', hotkey: '9', color: '#cbd5e1' },
    ]);
    const defaultEventPresetsForPack = (pack) => {
      const p = safeText(pack, defaultPack) === 'own' ? 'own' : 'rival';
      if (p === 'own') return defaultEventPresets();
      return [
        { kind: 'press', label: 'Presión rival', hotkey: '1', color: '#fb7185' },
        { kind: 'turnover', label: 'Pérdida rival', hotkey: '2', color: '#f59e0b' },
        { kind: 'shot', label: 'Finalización rival', hotkey: '3', color: '#facc15' },
        { kind: 'abp', label: 'ABP rival', hotkey: '4', color: '#a78bfa' },
        { kind: 'tag', label: 'Transición rival', hotkey: '5', color: '#60a5fa' },
        { kind: 'tag', label: 'Salida rival', hotkey: '6', color: '#38bdf8' },
        { kind: 'tag', label: 'Centro rival', hotkey: '7', color: '#34d399' },
        { kind: 'tag', label: 'Bloque rival', hotkey: '8', color: '#cbd5e1' },
        { kind: 'note', label: 'Nota rival', hotkey: '9', color: '#94a3b8' },
      ];
    };
    let eventPresets = defaultEventPresets();

    const sanitizeEventPresets = (raw) => {
      const items = Array.isArray(raw) ? raw : [];
      const out = [];
      const usedHotkeys = new Set();
      for (const it of items.slice(0, 24)) {
        const kind = safeText(it?.kind, 'tag').toLowerCase();
        const label = safeText(it?.label, '');
        if (!label) continue;
        if (!allowedEventKinds.has(kind)) continue;
        const hotkeyRaw = safeText(it?.hotkey, '');
        const hotkey = (hotkeyRaw && hotkeyRaw.length <= 2) ? hotkeyRaw : '';
        const hk = hotkey || '';
        if (hk && usedHotkeys.has(hk)) continue;
        if (hk) usedHotkeys.add(hk);
        const color = safeText(it?.color, '');
        out.push({ kind, label: label.slice(0, 140), hotkey: hk, color: color.slice(0, 16) });
      }
      // Asigna hotkeys 1..9 si faltan (para productividad).
      const digits = ['1','2','3','4','5','6','7','8','9'];
      for (let i = 0; i < out.length && i < digits.length; i += 1) {
        const d = digits[i];
        if (!out[i].hotkey) out[i].hotkey = d;
      }
      return out;
    };

    const presetsToJson = (items) => {
      try { return JSON.stringify(items, null, 2); } catch (e) { return '[]'; }
    };
    const autoClipState = { enabled: false, pre: 8, post: 8 };

    const renderAutoClipUi = () => {
      if (presetsAutoClipSelect) presetsAutoClipSelect.value = autoClipState.enabled ? '1' : '0';
      if (presetsPreInput) presetsPreInput.value = String(autoClipState.pre ?? 8);
      if (presetsPostInput) presetsPostInput.value = String(autoClipState.post ?? 8);
    };

    const readAutoClipUi = () => {
      autoClipState.enabled = safeText(presetsAutoClipSelect?.value, '0') === '1';
      autoClipState.pre = clamp(Number(presetsPreInput?.value || 0) || 0, 0, 90);
      autoClipState.post = clamp(Number(presetsPostInput?.value || 0) || 0, 0, 90);
    };

    const loadPackSelection = async () => {
      if (!presetsPackSelect) return;
      const key = prefKeyForPackSelection();
      let next = defaultPack;
      if (key && wsPrefGetUrl) {
        try {
          const v = await wsPrefGet(key);
          const raw = safeText(v?.pack, safeText(v, ''));
          if (raw === 'own' || raw === 'rival') next = raw;
        } catch (e) { /* ignore */ }
      }
      activePresetsPack = next === 'own' ? 'own' : 'rival';
      presetsPackSelect.value = activePresetsPack;
    };

    const savePackSelection = async () => {
      const key = prefKeyForPackSelection();
      if (!key) return;
      await wsPrefSet(key, { pack: activePresetsPack });
    };

    const loadAutoClipPrefs = async () => {
      const key = prefKeyForAutoClip(activePresetsPack);
      if (!key || !wsPrefGetUrl) {
        renderAutoClipUi();
        return;
      }
      try {
        const v = await wsPrefGet(key);
        autoClipState.enabled = Boolean(v?.enabled);
        autoClipState.pre = clamp(Number(v?.pre ?? 8) || 8, 0, 90);
        autoClipState.post = clamp(Number(v?.post ?? 8) || 8, 0, 90);
      } catch (e) { /* ignore */ }
      renderAutoClipUi();
    };

    const saveAutoClipPrefs = async () => {
      const key = prefKeyForAutoClip(activePresetsPack);
      if (!key) return;
      await wsPrefSet(key, { enabled: Boolean(autoClipState.enabled), pre: Number(autoClipState.pre || 0), post: Number(autoClipState.post || 0) });
    };

    const createQuickClipFromPreset = async (preset) => {
      if (!autoClipState.enabled || !clipSaveUrl || !videoId) return;
      const nowS = Number(video.currentTime) || 0;
      const inS = Math.max(0, nowS - (Number(autoClipState.pre) || 0));
      const outS = Math.max(inS + 0.2, nowS + (Number(autoClipState.post) || 0));
      const title = safeText(preset?.label, 'Clip').slice(0, 180);
      const kind = safeText(preset?.kind, 'tag').toLowerCase();
      const ctxTeam = safeText(ctxTeamSelect?.value, '').toUpperCase();
      const ctxPhase = safeText(ctxPhaseSelect?.value, '');
      const tags = [kind, 'preset', ctxTeam ? `team:${ctxTeam}` : '', ctxPhase ? `phase:${ctxPhase}` : ''].filter(Boolean);
      const collection = (activePresetsPack === 'own') ? 'Propio' : 'Rival';
      try {
        const resp = await fetch(clipSaveUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({ id: 0, video_id: videoId, title, collection, in_s: inS, out_s: outS, overlay: {}, tags, notes: '' }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
        await refreshClips();
      } catch (e) { /* ignore */ }
    };

	    const loadEventPresets = async () => {
	      const key = prefKeyForEventPresets(activePresetsPack);
	      if (!key || !wsPrefGetUrl) {
	        eventPresets = defaultEventPresetsForPack(activePresetsPack);
	        if (presetsJson) presetsJson.value = presetsToJson(eventPresets);
	        await loadAutoClipPrefs();
	        return;
	      }
	      try {
	        let value = await wsPrefGet(key);
	        let buttons = Array.isArray(value?.buttons) ? value.buttons : (Array.isArray(value) ? value : null);
	        if ((!buttons || !buttons.length) && teamId) {
	          // Backward-compat: lee el formato legacy si no hay presets guardados con key v2.
	          try {
	            const legacyKey = legacyPrefKeyForEventPresets();
	            if (legacyKey) {
	              const legacyValue = await wsPrefGet(legacyKey);
	              const legacyButtons = Array.isArray(legacyValue?.buttons) ? legacyValue.buttons : (Array.isArray(legacyValue) ? legacyValue : null);
	              if (legacyButtons && legacyButtons.length) {
	                value = legacyValue;
	                buttons = legacyButtons;
	              }
	            }
	          } catch (e) { /* ignore */ }
	        }
	        if (buttons) {
	          const sanitized = sanitizeEventPresets(buttons);
	          if (sanitized.length) eventPresets = sanitized;
	          else eventPresets = defaultEventPresetsForPack(activePresetsPack);
	        } else {
          eventPresets = defaultEventPresetsForPack(activePresetsPack);
        }
        if (presetsJson) presetsJson.value = presetsToJson(eventPresets);
        await loadAutoClipPrefs();
        setPresetsStatus('OK · presets cargados');
      } catch (e) {
        eventPresets = defaultEventPresetsForPack(activePresetsPack);
        if (presetsJson) presetsJson.value = presetsToJson(eventPresets);
        await loadAutoClipPrefs();
        setPresetsStatus('No se pudieron cargar presets (usando default).', true);
      }
    };

    const renderEventPresets = () => {
      if (!eventPresetsWrap) return;
      const buttons = eventPresets.slice(0, 12).map((p, idx) => (
        `<button type="button" class="button ghost" data-vs-preset="${idx}" title="Click: preparar · Shift+Click: añadir">${escHtml(p.hotkey ? `[${p.hotkey}] ` : '')}${escHtml(p.label)}</button>`
      )).join('');
      eventPresetsWrap.innerHTML = buttons || '<span class="hint">—</span>';
      Array.from(eventPresetsWrap.querySelectorAll('[data-vs-preset]')).forEach((btn) => {
        btn.addEventListener('click', async (ev) => {
          const idx = Number(btn.getAttribute('data-vs-preset') || 0);
          const p = eventPresets[idx];
          if (!p) return;
          if (eventKindSelect) eventKindSelect.value = safeText(p.kind, 'tag');
          if (eventLabelInput) eventLabelInput.value = safeText(p.label, '');
          if (safeText(p.color, '')) {
            try { if (colorInput) colorInput.value = String(p.color); } catch (e) { /* ignore */ }
          }
          if (ev?.shiftKey) {
            await addTimelineEvent();
            await createQuickClipFromPreset(p);
          }
        });
      });
    };
    loadPackSelection().then(loadEventPresets).finally(() => renderEventPresets());

    const saveEventPresets = async (items) => {
      const key = prefKeyForEventPresets(activePresetsPack);
      if (!key) return;
      await wsPrefSet(key, { buttons: items });
    };

    presetsSaveBtn?.addEventListener('click', async () => {
      try {
        const raw = safeText(presetsJson?.value, '');
        const parsed = raw ? JSON.parse(raw) : [];
        const sanitized = sanitizeEventPresets(parsed);
        if (!sanitized.length) {
          setPresetsStatus('JSON vacío o inválido: añade al menos 1 preset.', true);
          return;
        }
        eventPresets = sanitized;
        await saveEventPresets(eventPresets);
        if (presetsJson) presetsJson.value = presetsToJson(eventPresets);
        renderEventPresets();
        setPresetsStatus('Guardado.');
      } catch (e) {
        setPresetsStatus('No se pudo guardar (JSON inválido).', true);
      }
    });

    presetsResetBtn?.addEventListener('click', async () => {
      try {
        eventPresets = defaultEventPresetsForPack(activePresetsPack);
        await saveEventPresets(eventPresets);
        if (presetsJson) presetsJson.value = presetsToJson(eventPresets);
        renderEventPresets();
        setPresetsStatus('Reset OK.');
      } catch (e) {
        setPresetsStatus('No se pudo resetear.', true);
      }
    });

    presetsPackSelect?.addEventListener('change', async () => {
      const next = safeText(presetsPackSelect?.value, defaultPack);
      activePresetsPack = next === 'own' ? 'own' : 'rival';
      try { await savePackSelection(); } catch (e) { /* ignore */ }
      await loadEventPresets();
      renderEventPresets();
      setPresetsStatus(`Pack: ${activePresetsPack === 'own' ? 'Propio' : 'Rival'}`);
    });

    const onAutoClipChange = async () => {
      readAutoClipUi();
      try { await saveAutoClipPrefs(); setPresetsStatus('Auto-clip guardado.'); } catch (e) { setPresetsStatus('No se pudo guardar auto-clip.', true); }
    };
    presetsAutoClipSelect?.addEventListener('change', onAutoClipChange);
    presetsPreInput?.addEventListener('change', onAutoClipChange);
    presetsPostInput?.addEventListener('change', onAutoClipChange);

    const proModelPresets = () => sanitizeEventPresets([
      { kind: 'press', label: 'Presión alta: salto', hotkey: '1', color: '#22d3ee' },
      { kind: 'press', label: 'Presión tras pérdida', hotkey: '2', color: '#38bdf8' },
      { kind: 'tag', label: 'Bloque alto', hotkey: '3', color: '#34d399' },
      { kind: 'tag', label: 'Bloque medio', hotkey: '4', color: '#facc15' },
      { kind: 'tag', label: 'Bloque bajo', hotkey: '5', color: '#fb7185' },
      { kind: 'tag', label: 'Carril exterior', hotkey: '6', color: '#60a5fa' },
      { kind: 'tag', label: 'Carril interior', hotkey: '7', color: '#a78bfa' },
      { kind: 'turnover', label: 'Pérdida por dentro', hotkey: '8', color: '#f97316' },
      { kind: 'tag', label: '2v1 banda', hotkey: '9', color: '#67e8f9' },
      { kind: 'note', label: 'Nota entrenador', hotkey: '0', color: '#cbd5e1' },
    ]);

    const proPatternStorageKey = () => `vs_patterns_v1:${videoId || 'local'}`;

    const loadProPatterns = () => {
      try {
        const raw = window.localStorage?.getItem?.(proPatternStorageKey()) || '[]';
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.slice(0, 60) : [];
      } catch (e) {
        return [];
      }
    };

    const saveProPatterns = (items) => {
      try { window.localStorage?.setItem?.(proPatternStorageKey(), JSON.stringify((Array.isArray(items) ? items : []).slice(0, 60))); } catch (e) { /* ignore */ }
    };

    const renderProPatterns = () => {
      const items = loadProPatterns();
      if (patternSelect) {
        patternSelect.innerHTML = items.length
          ? items.map((it, idx) => `<option value="${idx}">${escHtml(safeText(it?.title, `Patrón ${idx + 1}`))}</option>`).join('')
          : '<option value="">Sin patrones</option>';
      }
      if (patternList) {
        patternList.innerHTML = items.length
          ? items.map((it, idx) => `<button type="button" class="button ghost" data-vs-pattern-pick="${idx}">${escHtml(safeText(it?.title, `Patrón ${idx + 1}`))}</button>`).join('')
          : '<span class="hint">Selecciona un recurso en el canvas y guárdalo como patrón.</span>';
        Array.from(patternList.querySelectorAll('[data-vs-pattern-pick]')).forEach((btn) => {
          btn.addEventListener('click', () => {
            const idx = Number(btn.getAttribute('data-vs-pattern-pick') || -1);
            if (patternSelect && idx >= 0) patternSelect.value = String(idx);
            patternApplyBtn?.click?.();
          });
        });
      }
    };

    const activePatternObjects = () => {
      const active = (() => { try { return fabricCanvas.getActiveObject?.() || null; } catch (e) { return null; } })();
      if (!active) return [];
      if (safeText(active.type, '') === 'activeSelection' && typeof active.getObjects === 'function') {
        return active.getObjects().filter(Boolean);
      }
      return [active];
    };

    const saveActiveProPattern = () => {
      const objects = activePatternObjects();
      if (!objects.length) {
        setStatus('Selecciona uno o varios recursos antes de guardar patrón.', true);
        return;
      }
      const payload = objects.map((obj) => {
        try { ensureLayerData(obj); } catch (e) { /* ignore */ }
        try { return obj.toObject(['data']); } catch (e) { return null; }
      }).filter(Boolean);
      if (!payload.length) {
        setStatus('No se pudo leer el patrón seleccionado.', true);
        return;
      }
      const title = safeText(patternTitleInput?.value, '') || `Patrón ${loadProPatterns().length + 1}`;
      const items = loadProPatterns();
      items.unshift({ title: title.slice(0, 80), objects: payload, created_at: new Date().toISOString() });
      saveProPatterns(items);
      if (patternTitleInput) patternTitleInput.value = '';
      renderProPatterns();
      setStatus('Patrón guardado.');
    };

    const applyProPattern = () => {
      const items = loadProPatterns();
      const idx = Number(patternSelect?.value || 0);
      const pattern = items[idx];
      const objects = Array.isArray(pattern?.objects) ? pattern.objects : [];
      if (!objects.length || !window.fabric?.util?.enlivenObjects) {
        setStatus('No hay patrón aplicable.', true);
        return;
      }
      try {
        fabric.util.enlivenObjects(objects, (enlivened) => {
          const add = (Array.isArray(enlivened) ? enlivened : []).filter(Boolean);
          if (!add.length) { setStatus('No se pudo aplicar el patrón.', true); return; }
          add.forEach((obj, i) => {
            try {
              ensureLayerData(obj);
              obj.data = { ...(obj.data || {}), uid: newUid(), pattern: safeText(pattern?.title, '') };
              obj.set({ left: (Number(obj.left) || 0) + 24 + (i * 4), top: (Number(obj.top) || 0) + 24 + (i * 4) });
              fabricCanvas.add(obj);
            } catch (e) { /* ignore */ }
          });
          try {
            if (add.length > 1) fabricCanvas.setActiveObject(new fabric.ActiveSelection(add, { canvas: fabricCanvas }));
            else fabricCanvas.setActiveObject(add[0]);
          } catch (e) { /* ignore */ }
          try { pushHistory(); updateLayerPanel(); renderDrawLayers(); renderMiniTimeline(); fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
          setStatus('Patrón aplicado.');
        });
      } catch (e) {
        setStatus('No se pudo aplicar el patrón.', true);
      }
    };

    const compareClipCandidates = () => {
      const selected = selectedClipsOrdered();
      if (selected.length >= 2) return selected.slice(0, 2);
      const filtered = applyClipFilters(clipsCache);
      return filtered.slice(0, 2);
    };

    const openClipForPro = (clip, play = false) => {
      if (!clip) return;
      const start = Number(clip?.in_s) || 0;
      const end = Number(clip?.out_s) || start;
      activeClipId = Number(clip?.id) || activeClipId;
      if (inInput) inInput.value = String(start.toFixed(1));
      if (outInput) outInput.value = String(end.toFixed(1));
      if (clipTitleInput) clipTitleInput.value = safeText(clip?.title, '');
      if (clipCollectionInput) clipCollectionInput.value = safeText(clip?.collection, '');
      if (clipTagsInput) clipTagsInput.value = (Array.isArray(clip?.tags) ? clip.tags : []).map((t) => safeText(t)).filter(Boolean).join(', ');
      if (clipNotesInput) clipNotesInput.value = safeText(clip?.notes, '');
      const overlay = clip?.overlay || {};
      if (overlay && typeof overlay === 'object' && Array.isArray(overlay?.objects)) {
        try { restoreJson(overlay); } catch (e) { /* ignore */ }
      }
      try { video.currentTime = Math.max(0, start); } catch (e) { /* ignore */ }
      if (play) {
        try { video.play?.(); } catch (e) { /* ignore */ }
      }
      try { updateClipUiState(); updateLayerPanel(); } catch (e) { /* ignore */ }
    };

    const renderProCompare = () => {
      if (!proComparePanel) return;
      const clips = compareClipCandidates();
      if (clips.length < 2) {
        proComparePanel.style.display = 'none';
        setStatus('Selecciona dos clips o crea al menos dos clips para comparar.', true);
        return;
      }
      proComparePanel.style.display = 'grid';
      proComparePanel.innerHTML = clips.map((clip, idx) => {
        const title = safeText(clip?.title, `Clip ${idx + 1}`);
        const inS = Number(clip?.in_s) || 0;
        const outS = Number(clip?.out_s) || inS;
        const tags = Array.isArray(clip?.tags) ? clip.tags : [];
        return `
          <div class="vs-compare-card">
            <strong>${idx === 0 ? 'A' : 'B'} · ${escHtml(title)}</strong>
            <small>${escHtml(fmtTimeShort(inS))} → ${escHtml(fmtTimeShort(outS))}${tags.length ? ` · ${escHtml(tags.slice(0, 4).join(', '))}` : ''}</small>
            <div class="vs-pro-actions">
              <button type="button" class="button" data-vs-pro-open-clip="${idx}">Abrir</button>
              <button type="button" class="button primary" data-vs-pro-play-clip="${idx}">Play</button>
            </div>
          </div>
        `;
      }).join('');
      Array.from(proComparePanel.querySelectorAll('[data-vs-pro-open-clip]')).forEach((btn) => {
        btn.addEventListener('click', () => openClipForPro(clips[Number(btn.getAttribute('data-vs-pro-open-clip') || 0)], false));
      });
      Array.from(proComparePanel.querySelectorAll('[data-vs-pro-play-clip]')).forEach((btn) => {
        btn.addEventListener('click', () => openClipForPro(clips[Number(btn.getAttribute('data-vs-pro-play-clip') || 0)], true));
      });
      setStatus('Comparador preparado con dos clips.');
    };

    const createProIssue = async (key) => {
      const map = {
        perfil: { kind: 'note', label: 'Error recurrente: mal perfil corporal', color: '#facc15' },
        intervalo: { kind: 'tag', label: 'Error recurrente: no cerrar intervalo', color: '#fb7185' },
        perdida_dentro: { kind: 'turnover', label: 'Error recurrente: pérdida por dentro', color: '#f97316' },
        linea_hundida: { kind: 'tag', label: 'Error recurrente: línea hundida', color: '#60a5fa' },
        area: { kind: 'shot', label: 'Error recurrente: no atacar área', color: '#34d399' },
      };
      const item = map[safeText(key, '')] || map.perfil;
      if (eventKindSelect) eventKindSelect.value = item.kind;
      if (eventLabelInput) eventLabelInput.value = item.label;
      try { if (colorInput) colorInput.value = item.color; } catch (e) { /* ignore */ }
      await addTimelineEvent();
      await createQuickClipFromPreset(item);
      setStatus(`${item.label} añadido a Timeline.`);
    };

    proLiveModeBtn?.addEventListener('click', async () => {
      autoClipState.enabled = true;
      autoClipState.pre = Math.max(6, Number(autoClipState.pre) || 8);
      autoClipState.post = Math.max(6, Number(autoClipState.post) || 8);
      renderAutoClipUi();
      try { await saveAutoClipPrefs(); } catch (e) { /* ignore */ }
      try { document.getElementById('vs-acc-events')?.setAttribute?.('open', ''); } catch (e) { /* ignore */ }
      setStatus('Modo partido activo: cada evento puede crear clip automático con IN/OUT alrededor del playhead.');
    });

    proModelPackBtn?.addEventListener('click', async () => {
      eventPresets = proModelPresets();
      if (presetsJson) presetsJson.value = presetsToJson(eventPresets);
      renderEventPresets();
      try { await saveEventPresets(eventPresets); } catch (e) { /* ignore */ }
      setPresetsStatus('Pack modelo cargado.');
      setStatus('Pack modelo de juego cargado en botones de evento.');
    });

    proCompareBtn?.addEventListener('click', renderProCompare);
    patternSaveBtn?.addEventListener('click', saveActiveProPattern);
    patternApplyBtn?.addEventListener('click', applyProPattern);

    proPresentationBtn?.addEventListener('click', async () => {
      if (Array.isArray(timelineCache) && timelineCache.length) {
        try { await slidesFromTimeline(); } catch (e) { slidesFromTimelineBtn?.click?.(); }
      } else {
        slideAddBtn?.click?.();
      }
      setStatus('Presentación preparada en slides.');
    });

    proAiQuestionBtn?.addEventListener('click', () => {
      if (aiContextInput) {
        aiContextInput.value = [
          'Analiza esta jugada como entrenador.',
          'Identifica bloque alto/medio/bajo, carriles ocupados, superioridades, riesgos y corrección práctica para jugador.',
          'Devuelve momentos clave, errores recurrentes y tareas de entrenamiento.'
        ].join(' ');
      }
      fetchAi(true);
    });

    proGuidedTrackBtn?.addEventListener('click', () => {
      try { setTool('player'); } catch (e) { btnPlayer?.click?.(); }
      setStatus('Seguimiento guiado: marca el jugador en este frame y usa AutoTrack IA o keyframes para que el recurso lo siga.');
    });

    proCoachExportBtn?.addEventListener('click', () => {
      reportPdfBtn?.click?.();
      setStatus('Export entrenador iniciado.');
    });

    proPlayerExportBtn?.addEventListener('click', () => {
      if (!slides.length) {
        if (Array.isArray(timelineCache) && timelineCache.length) slidesFromTimelineBtn?.click?.();
        else slideAddBtn?.click?.();
      }
      window.setTimeout(() => exportPdfBtn?.click?.(), 250);
      setStatus('Export jugador iniciado.');
    });

    Array.from(document.querySelectorAll('[data-vs-pro-issue]')).forEach((btn) => {
      btn.addEventListener('click', () => createProIssue(btn.getAttribute('data-vs-pro-issue')));
    });
    renderProPatterns();

    eventRefreshBtn?.addEventListener('click', refreshTimeline);
    timelineSearchInput?.addEventListener('input', () => renderTimeline(timelineCache));
    timelineKindFilterSelect?.addEventListener('change', () => renderTimeline(timelineCache));
    filterUnreviewedEventsToggle?.addEventListener('change', () => {
      reviewFilterState.eventsOnlyUnreviewed = Boolean(filterUnreviewedEventsToggle.checked);
      renderTimeline(timelineCache);
      renderDashboard();
    });
    timelinePrevBtn?.addEventListener('click', () => timelineJump(-1));
    timelineNextBtn?.addEventListener('click', () => timelineJump(1));

    document.addEventListener('keydown', (ev) => {
      const k = safeText(ev?.key, '');
      if (!k) return;
      const tag = safeText(ev?.target?.tagName, '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      // Contexto rápido (scouting): equipo + fase, sin romper el flujo.
      // M/B -> MAR/BAE ; A/F -> Ataque/Defensa ; X/Z -> Transiciones ; P/Shift+P -> ABP a favor/en contra.
      const kk = k.toLowerCase();
      if (kk === 'm') { try { if (ctxTeamSelect) ctxTeamSelect.value = 'MAR'; } catch (e) {} setStatus('Contexto: MAR'); return; }
      if (kk === 'b') { try { if (ctxTeamSelect) ctxTeamSelect.value = 'BAE'; } catch (e) {} setStatus('Contexto: BAE'); return; }
      if (kk === 'a') { try { if (ctxPhaseSelect) ctxPhaseSelect.value = 'attack'; } catch (e) {} setStatus('Fase: Ataque'); return; }
      if (kk === 'f') { try { if (ctxPhaseSelect) ctxPhaseSelect.value = 'defense'; } catch (e) {} setStatus('Fase: Defensa'); return; }
      if (kk === 'x') { try { if (ctxPhaseSelect) ctxPhaseSelect.value = 'transition_of'; } catch (e) {} setStatus('Fase: Transición OF'); return; }
      if (kk === 'z') { try { if (ctxPhaseSelect) ctxPhaseSelect.value = 'transition_def'; } catch (e) {} setStatus('Fase: Transición DEF'); return; }
      if (kk === 'p') {
        try { if (ctxPhaseSelect) ctxPhaseSelect.value = ev.shiftKey ? 'abp_against' : 'abp_for'; } catch (e) {}
        setStatus(`Fase: ${ev.shiftKey ? 'ABP en contra' : 'ABP a favor'}`);
        return;
      }
      // Atajos globales (productividad): Espacio play/pausa · I/O marcar IN/OUT · C guardar clip · T tag.
      if (k === ' ' || k === 'Spacebar') {
        ev.preventDefault();
        try {
          if (video.paused || video.ended) video.play();
          else video.pause();
        } catch (e) { /* ignore */ }
        syncPlayButtons();
        return;
      }
      if (k === 'i' || k === 'I') {
        ev.preventDefault();
        markIn();
        return;
      }
      if (k === 'o' || k === 'O') {
        ev.preventDefault();
        markOut();
        return;
      }
      // Compatibilidad con otros editores: S=IN, R=OUT (tipo "quick tagging").
      if (k === 's' || k === 'S') {
        ev.preventDefault();
        markIn();
        return;
      }
      if (k === 'r' || k === 'R') {
        ev.preventDefault();
        markOut();
        return;
      }
      if (k === 'c' || k === 'C') {
        ev.preventDefault();
        saveClip();
        return;
      }
      if (k === 't' || k === 'T') {
        ev.preventDefault();
        try {
          if (eventKindSelect) eventKindSelect.value = 'tag';
          if (eventLabelInput && !safeText(eventLabelInput.value, '')) eventLabelInput.value = 'Tag';
        } catch (e) { /* ignore */ }
        addTimelineEvent();
        return;
      }
      if (k >= '1' && k <= '9') {
        // Tecla rápida: busca preset por hotkey; si no existe, fallback por índice.
        const byHotkey = eventPresets.find((p) => safeText(p?.hotkey, '') === k);
        const idx = Number(k) - 1;
        const p = byHotkey || eventPresets[idx];
        if (!p) return;
        if (eventKindSelect) eventKindSelect.value = safeText(p.kind, 'tag');
        if (eventLabelInput) eventLabelInput.value = safeText(p.label, '');
        if (safeText(p.color, '')) {
          try { if (colorInput) colorInput.value = String(p.color); } catch (e) { /* ignore */ }
        }
        setStatus(`Preset: ${safeText(p.label)}`);
        // Por defecto: añadir al momento (más rápido). Shift = solo preparar.
        if (!ev?.shiftKey) {
          addTimelineEvent();
          createQuickClipFromPreset(p);
        }
      }
    });

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

    const exportTimelineFile = async (format) => {
      if (!timelineExportUrl || !videoId) { setStatus('No disponible.', true); return; }
      const fmt = safeText(format, 'csv');
      try {
        const resp = await fetch(
          `${timelineExportUrl}?video_id=${encodeURIComponent(String(videoId))}&format=${encodeURIComponent(fmt)}`,
          { credentials: 'same-origin' },
        );
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data?.error || 'error');
        }
        await downloadResponseBlob(resp, `timeline-${videoId}.${fmt}`);
        setStatus(`Timeline exportada (${fmt.toUpperCase()}).`);
      } catch (e) {
        setStatus('No se pudo exportar timeline.', true);
      }
    };

    const parseCsvLine = (line) => {
      const out = [];
      let cur = '';
      let inQ = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (inQ) {
          if (ch === '"') {
            if (line[i + 1] === '"') { cur += '"'; i++; continue; }
            inQ = false;
            continue;
          }
          cur += ch;
          continue;
        }
        if (ch === '"') { inQ = true; continue; }
        if (ch === ',') { out.push(cur); cur = ''; continue; }
        cur += ch;
      }
      out.push(cur);
      return out;
    };

    const parseTimelineCsv = (text) => {
      const lines = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(l => l.trim().length);
      if (lines.length < 2) return [];
      const head = parseCsvLine(lines[0]).map(h => safeText(h).trim().toLowerCase());
      const idxTimeMs = head.indexOf('time_ms');
      const idxKind = head.indexOf('kind');
      const idxLabel = head.indexOf('label');
      const idxColor = head.indexOf('color');
      const items = [];
      for (let i = 1; i < lines.length; i++) {
        const cols = parseCsvLine(lines[i]);
        const time_ms = Number(cols[idxTimeMs] || 0) || 0;
        const kind = safeText(cols[idxKind] || 'tag', 'tag');
        const label = safeText(cols[idxLabel] || '', '');
        const color = safeText(cols[idxColor] || '', '');
        items.push({ time_ms, kind, label, color, payload: {} });
      }
      return items.filter(it => Number.isFinite(it.time_ms));
    };

    const parseTimelineXml = (text) => {
      const items = [];
      try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(String(text || ''), 'application/xml');
        const errs = doc.getElementsByTagName('parsererror');
        if (errs && errs.length) return [];
        const events = Array.from(doc.getElementsByTagName('event') || []);
        for (const ev of events) {
          const timeMs = Number(ev.getAttribute('time_ms') || 0) || 0;
          const kind = safeText(ev.getAttribute('kind') || 'tag', 'tag');
          const color = safeText(ev.getAttribute('color') || '', '');
          let label = '';
          const labelEl = ev.getElementsByTagName('label')?.[0];
          if (labelEl) label = safeText(labelEl.textContent || '', '');
          items.push({ time_ms: timeMs, kind, label, color, payload: {} });
        }
      } catch (e) { /* ignore */ }
      return items;
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

    timelineExportBtn?.addEventListener('click', async () => {
      const fmt = safeText(timelineFormatSelect?.value, 'json').trim().toLowerCase();
      if (fmt === 'csv' || fmt === 'xml') return exportTimelineFile(fmt);
      return exportTimelineJson();
    });
    timelineImportBtn?.addEventListener('click', () => {
      try { timelineImportFile?.click(); } catch (e) { /* ignore */ }
    });

    timelineToClipsBtn?.addEventListener('click', async () => {
      if (!clipSaveUrl || !videoId) { setStatus('No disponible.', true); return; }
      const items = applyTimelineFilters(timelineCache);
      if (!items.length) { setStatus('No hay eventos para convertir.', true); return; }
      const ok = window.confirm(`Esto creará clips para ${items.length} eventos (máx 30 por seguridad). ¿Continuar?`);
      if (!ok) return;
      const batch = items.slice(0, 30);
      timelineToClipsBtn.disabled = true;
      let created = 0;
      try {
        const buildAutofxOverlayForEvent = () => ({ objects: [], version: '5.3.0', fx: { layers: [] } });

        for (let i = 0; i < batch.length; i += 1) {
          setStatus(`Creando clips… (${i + 1}/${batch.length})`);
          // eslint-disable-next-line no-await-in-loop
          const did = await (async () => {
            if (!clipSaveUrl || !videoId) return false;
            const timeS = Number(batch[i]?.time_s) || 0;
            const kind = safeText(batch[i]?.kind, 'tag').toLowerCase();
            const label = safeText(batch[i]?.label, '');
            const payload = (batch[i] && typeof batch[i].payload === 'object' && batch[i].payload) ? batch[i].payload : {};
            const ctxTeam = safeText(payload?.team, safeText(ctxTeamSelect?.value, '')).toUpperCase();
            const ctxPhase = safeText(payload?.phase, safeText(ctxPhaseSelect?.value, ''));
            const pre = clamp(Number(autoClipState?.pre ?? 8) || 8, 0, 90);
            const post = clamp(Number(autoClipState?.post ?? 8) || 8, 0, 90);
            const inS = Math.max(0, timeS - pre);
            const outS = Math.max(inS + 0.2, timeS + post);
            const title = (label || `${kind.toUpperCase()} · ${fmtTimeShort(timeS)}`).slice(0, 180);
            let collection = safeText(clipCollectionInput?.value, '').slice(0, 120);
            if (!collection) collection = ctxTeam || (activePresetsPack === 'own' ? 'Propio' : 'Rival');
            const tags = [kind, 'timeline', ctxTeam ? `team:${ctxTeam}` : '', ctxPhase ? `phase:${ctxPhase}` : ''].filter(Boolean);
            const overlay = buildAutofxOverlayForEvent({ kind, timeS });
            try {
              const resp = await fetch(clipSaveUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ id: 0, video_id: videoId, title, collection, in_s: inS, out_s: outS, overlay, tags, notes: '' }),
              });
              const data = await resp.json().catch(() => ({}));
              return Boolean(resp.ok && data?.ok);
            } catch (e) {
              return false;
            }
          })();
          if (did) created += 1;
          // eslint-disable-next-line no-await-in-loop
          await sleep(120);
        }
        await refreshClips();
        setStatus(`OK · clips creados: ${created}/${batch.length}`);
      } catch (e) {
        setStatus('Error creando clips desde timeline.', true);
      } finally {
        timelineToClipsBtn.disabled = false;
      }
    });
    timelineImportFile?.addEventListener('change', async () => {
      const file = timelineImportFile?.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const name = safeText(file.name || '', '').toLowerCase();
        if (name.endsWith('.csv') || safeText(file.type || '', '').includes('csv')) {
          const items = parseTimelineCsv(text);
          if (!items.length) { setStatus('CSV sin eventos.', true); return; }
          await importTimelineJson({ items });
        } else if (name.endsWith('.xml') || safeText(file.type || '', '').includes('xml')) {
          const items = parseTimelineXml(text);
          if (!items.length) { setStatus('XML sin eventos.', true); return; }
          await importTimelineJson({ items });
        } else {
          const obj = JSON.parse(text || '{}');
          await importTimelineJson(obj);
        }
      } catch (e) {
        setStatus('Archivo inválido.', true);
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
	    const bootstrapReviewState = async () => {
	      await refreshReviewState();
	      renderClips(applyClipFilters(clipsCache));
	      renderTimeline(timelineCache);
	      renderDashboard();
	    };
	    let advancedEnabled = false;
	    const enableAdvancedFeatures = async () => {
	      if (advancedEnabled) return;
	      advancedEnabled = true;
	      try { await refreshVoiceovers(); } catch (e) { /* ignore */ }
	      try { await refreshMusic(); } catch (e) { /* ignore */ }
	      try { await refreshProjects(); } catch (e) { /* ignore */ }
	      try { await refreshShareLinks(); } catch (e) { /* ignore */ }
	      try { await refreshTimeline(); } catch (e) { /* ignore */ }
	      try { await bootstrapReviewState(); } catch (e) { /* ignore */ }
	    };
	    try {
	      window.__vsEnableAdvancedFeatures = () => { enableAdvancedFeatures(); };
	    } catch (e) { /* ignore */ }
	    if (!simpleUI) enableAdvancedFeatures();

    // Slides + Export Pro
    let slides = [];

		    const captureFrameDataUrl = async () => {
		      const w = fabricCanvas.getWidth();
		      const h = fabricCanvas.getHeight();
		      const off = document.createElement('canvas');
		      off.width = w;
		      off.height = h;
		      const ctx = off.getContext('2d');
		      if (!ctx) return '';
		      let baseDrawn = false;
		      if (!compatNoCorsApplied) {
		        try { baseDrawn = await drawVideoFrameSmart(ctx, video, w, h); } catch (e) { /* ignore */ }
		        if (baseDrawn && canvasLooksBlank(ctx, w, h)) baseDrawn = false;
		      }
		      if (!baseDrawn) {
		        try {
		          const dataUrl = await captureVideoFrameDataUrl({ maxW: Math.max(480, Math.min(1920, Math.round(w || 1280))) });
		          if (dataUrl) {
		            const img = await loadImageFromDataUrl(dataUrl);
	            try { ctx.drawImage(img, 0, 0, w, h); baseDrawn = true; } catch (e) { /* ignore */ }
	          }
	        } catch (e) { /* ignore */ }
	      }
	      if (!baseDrawn) {
	        try {
	          ctx.fillStyle = '#000';
	          ctx.fillRect(0, 0, w, h);
	        } catch (e) { /* ignore */ }
	      }
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

	    const addSlideNow = async () => {
	      const img = await captureFrameDataUrl();
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
	        const img = await captureFrameDataUrl();
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

    const exportVideoReportPdf = async () => {
      if (!reportPdfUrl || !videoId) return;
      try {
        const computeReportClipIds = () => {
          if (selectedClipIds.size > 0) {
            return selectedClipsOrdered().slice(0, 260).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
          }
          const q = safeText(clipSearchInput?.value, '');
          const coll = safeText(clipCollectionFilterSelect?.value, '');
          const hasFilter = Boolean(q || coll);
          if (!hasFilter) return [];
          const filtered = applyClipFilters(clipsCache);
          return filtered.slice(0, 260).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
        };
        const clipIds = computeReportClipIds();
        await postJsonDownload({
          url: reportPdfUrl,
          payload: {
            video_id: videoId,
            title: buildExportTitle(),
            clip_ids: clipIds,
            include_ai: Boolean(aiIncludeReportToggle?.checked),
          },
          fallbackName: 'video-informe.pdf',
        });
        setStatus('Informe descargado.');
      } catch (e) {
        setStatus(`No se pudo exportar informe. ${safeText(e?.message, '')}`, true);
      }
    };

    const shareVideoReport = async () => {
      if (!shareReportCreateUrl || !videoId) { setStatus('No disponible.', true); return; }
      const computeReportClipIds = () => {
        if (selectedClipIds.size > 0) {
          return selectedClipsOrdered().slice(0, 260).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
        }
        const q = safeText(clipSearchInput?.value, '');
        const coll = safeText(clipCollectionFilterSelect?.value, '');
        const hasFilter = Boolean(q || coll);
        if (!hasFilter) return [];
        const filtered = applyClipFilters(clipsCache);
        return filtered.slice(0, 260).map((c) => Number(c?.id) || 0).filter((x) => x > 0);
      };
      try {
        setStatus('Creando enlace de informe…');
        const resp = await fetch(shareReportCreateUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: JSON.stringify({
            video_id: videoId,
            title: buildExportTitle(),
            clip_ids: computeReportClipIds(),
            include_ai: Boolean(aiIncludeReportToggle?.checked),
            valid_days: 14,
          }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data?.ok || !data?.url) throw new Error(data?.error || 'error');
        const url = String(data.url);
        try {
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(url);
            setStatus('Enlace de informe copiado.');
          } else {
            window.prompt('Copia este enlace:', url);
            setStatus('Copia el enlace de informe.');
          }
        } catch (e) {
          window.prompt('Copia este enlace:', url);
        }
        refreshShareLinks();
      } catch (e) {
        setStatus('No se pudo crear enlace de informe.', true);
      }
    };

    exportPdfBtn?.addEventListener('click', exportSlidesPdf);
    exportPackageBtn?.addEventListener('click', exportSlidesPackage);
    reportPdfBtn?.addEventListener('click', exportVideoReportPdf);
    reportShareBtn?.addEventListener('click', shareVideoReport);

	    const applyTimedLayers = () => {
	      const nowS = Number(video.currentTime) || 0;
      let anyAnim = false;
      let activeAlpha = 1;
      const activeObj = (() => {
        try { return fabricCanvas.getActiveObject?.() || null; } catch (e) { return null; }
      })();
	      const isTransforming = Boolean(fabricCanvas?._currentTransform);
	      for (const obj of fabricCanvas.getObjects()) {
	        ensureLayerData(obj);
	        const alpha = computeTimedAlpha(obj.data, nowS);
	        obj.visible = alpha > 0.001;
	        obj.opacity = clamp(alpha, 0, 1);
	        if (activeObj && obj === activeObj) activeAlpha = alpha;

	        // Player marker tracking (manual). Durante reproducción y scrubbing, interpolamos.
	        // En edición (drag), no sobreescribimos la posición.
	        if (safeText(obj?.data?.kind) === 'player_marker' && obj.visible && obj.data?.track && Array.isArray(obj.data.kf)) {
	          if (!(video.paused && isTransforming)) {
	            const pos = interpKeyframes(obj.data.kf, nowS);
	            if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
	              try {
	                obj.setPositionByOrigin(new fabric.Point(pos.x, pos.y), 'center', 'center');
	              } catch (e) {
	                obj.set({ left: pos.x, top: pos.y });
	              }
	              try { obj.setCoords?.(); } catch (e) { /* ignore */ }
	              obj.dirty = true;
	            }
	          }
	        }

	        if (safeText(obj?.data?.kind) === 'space_zone' && obj.visible) {
	          anyAnim = true;
	          const editingThis = Boolean(activeObj && obj === activeObj && video.paused && isTransforming);
	          if (!editingThis) {
	            try { applySpaceFollow(obj, nowS); } catch (e) { /* ignore */ }
	          }
	          try { applySpaceZoneLiveStyle(obj, isSpaceZoneOccupied(obj, nowS)); } catch (e) { /* ignore */ }
	        }

	        if (safeText(obj?.data?.kind) !== 'space_zone' && obj.visible && obj.data?.track) {
	          anyAnim = true;
	          const editingThis = Boolean(activeObj && obj === activeObj && video.paused && isTransforming);
	          if (!editingThis) {
	            try { applyObjectFollow(obj, nowS); } catch (e) { /* ignore */ }
	          }
	        }

	        if (safeText(obj?.data?.kind) === 'tactical_link' && obj.visible) {
	          anyAnim = true;
	          try { updateTacticalLink(obj, nowS); } catch (e) { /* ignore */ }
	        }

	        const anim = safeText(obj.data.anim, 'none');
	        if (anim === 'pulse') {
          anyAnim = true;
          const tIn = Math.max(0, Number(obj.data.t_in_s) || 0);
          const baseX = Number(obj.data.base_sx) || 1;
          const baseY = Number(obj.data.base_sy) || 1;
          const phase = (nowS - tIn) * Math.PI * 2 * 1.2;
          const k = 1 + Math.sin(phase) * 0.08;
          obj.scaleX = baseX * k;
          obj.scaleY = baseY * k;
          obj.dirty = true;
        }

        if (anim === 'draw') {
          anyAnim = true;
          const tIn = Math.max(0, Number(obj.data.t_in_s) || 0);
          const animMs = Math.max(50, Number(obj.data.anim_ms) || 700);
          const prog = clamp((nowS - tIn) / (animMs / 1000), 0, 1);
          if (obj.type === 'group' && Array.isArray(obj._objects)) {
            const line = obj._objects.find((x) => x?.type === 'line');
            const path = obj._objects.find((x) => x?.type === 'path');
            const heads = obj._objects.filter((x) => x?.type === 'polygon');
            if (line && Number.isFinite(line.x1) && Number.isFinite(line.x2)) {
              const len = Math.max(1, Math.hypot((line.x2 - line.x1), (line.y2 - line.y1)));
              line.strokeDashArray = [len, len];
              line.strokeDashOffset = len * (1 - prog);
              line.dirty = true;
            }
            if (path) {
              const len = Math.max(1, Number(path?.data?.draw_len) || 800);
              path.strokeDashArray = [len, len];
              path.strokeDashOffset = len * (1 - prog);
              path.dirty = true;
            }
            if (heads && heads.length) {
              const op = prog >= 0.98 ? 1 : 0;
              heads.forEach((h) => {
                h.opacity = op;
                h.dirty = true;
              });
            }
          }
        }
      }
      try {
        for (const obj of fabricCanvas.getObjects()) {
          if (safeText(obj?.data?.kind) === 'tactical_link' && obj.visible) {
            updateTacticalLink(obj, nowS);
          }
        }
      } catch (e) { /* ignore */ }
      // Durante reproducción, no queremos ver el "marco de selección" (controles) flotando
      // cuando la capa está entrando/saliendo (la selección no sigue el alpha).
      // En iOS/Safari esto distrae mucho y parece un bug visual.
      if (!video.paused && activeObj && activeAlpha < 0.35) {
        try { fabricCanvas.discardActiveObject?.(); } catch (e) { /* ignore */ }
      }
	      if (!video.paused || anyAnim) {
	        try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	      }
	      try { syncFreezeBackground(nowS); } catch (e) { /* ignore */ }
	      try { renderFx(fxCtx, { width: fxEl.width, height: fxEl.height, nowS, forExport: false }); } catch (e) { /* ignore */ }
	    };

    const tick = () => {
      try { applyTimedLayers(); } catch (e) { /* ignore */ }
      window.requestAnimationFrame(tick);
    };
    window.requestAnimationFrame(tick);
	    video.addEventListener('timeupdate', () => { if (video.paused) applyTimedLayers(); });

	    const autoTrackPlayers = async () => {
	      if (!btnTrackAuto) return;
	      if (!trackUrl || !videoId) { setStatus('AutoTrack no disponible.', true); return; }
	      const a = Math.max(0, Number(inInput?.value || 0) || 0);
	      const b = Math.max(0, Number(outInput?.value || 0) || 0);
	      const start = Math.min(a, b);
	      const end = Math.max(a, b);
	      if (!end || end <= start + 0.05) { setStatus('AutoTrack: define IN/OUT de la jugada.', true); return; }

	      const wasPlaying = !video.paused;
	      try { video.pause(); } catch (e) { /* ignore */ }
	      btnTrackAuto.disabled = true;
	      const prevLabel = safeText(btnTrackAuto.textContent, 'AutoTrack');
	      btnTrackAuto.textContent = 'AutoTrack…';
	      setStatus('AutoTrack: preparando (ir a IN)…');

	      try {
	        await seekTo(start);
	        await sleep(120);
	        try { applyTimedLayers(); } catch (e0) { /* ignore */ }

	        const canvasW = Number(fabricCanvas.getWidth?.()) || 0;
	        const canvasH = Number(fabricCanvas.getHeight?.()) || 0;
	        if (!canvasW || !canvasH) throw new Error('Canvas no listo');

	        const active = (() => { try { return fabricCanvas.getActiveObject?.() || null; } catch (e2) { return null; } })();
	        const selectedObjs = (() => {
	          try {
	            if (!active) return [];
	            if (active.type === 'activeSelection' && typeof active.getObjects === 'function') return active.getObjects() || [];
	            return [active];
	          } catch (e3) { return []; }
	        })();
	        const hasSelectedMarkers = selectedObjs.some((o) => safeText(o?.data?.kind) === 'player_marker');
	        const pool = hasSelectedMarkers ? selectedObjs : (fabricCanvas.getObjects?.() || []);

	        const markers = [];
	        const uidToObj = new Map();
	        const defaultBoxPx = clamp(Math.round(Math.min(canvasW, canvasH) * 0.13), 56, 170);
	        for (const obj of pool) {
	          ensureLayerData(obj);
	          if (safeText(obj?.data?.kind) !== 'player_marker') continue;
	          if (!obj.visible) continue; // sólo lo que está "en pantalla" en IN
	          const uid = safeText(obj?.data?.uid, '');
	          if (!uid) continue;
	          let p = null;
	          try { p = obj.getCenterPoint?.(); } catch (e4) { p = null; }
	          const cx = Number(p?.x ?? obj.left) || 0;
	          const cy = Number(p?.y ?? obj.top) || 0;
	          if (!Number.isFinite(cx) || !Number.isFinite(cy)) continue;
	          const bw = clamp(Number(obj?.data?.track_box_w_px ?? defaultBoxPx), 40, Math.max(60, canvasW));
	          const bh = clamp(Number(obj?.data?.track_box_h_px ?? defaultBoxPx), 40, Math.max(60, canvasH));
	          markers.push({
	            uid,
	            x_rel: clamp(cx / canvasW, 0, 1),
	            y_rel: clamp(cy / canvasH, 0, 1),
	            bw_rel: clamp(bw / canvasW, 0.02, 0.35),
	            bh_rel: clamp(bh / canvasH, 0.02, 0.35),
	            anchors: normalizeKeyframes(obj?.data?.kf || [])
	              .filter((k) => Number(k.t) >= start - 0.08 && Number(k.t) <= end + 0.08)
	              .map((k) => ({
	                t: Number(k.t),
	                x_rel: clamp((Number(k.x) || 0) / canvasW, 0, 1),
	                y_rel: clamp((Number(k.y) || 0) / canvasH, 0, 1),
	              })),
	          });
	          uidToObj.set(uid, obj);
	        }
	        if (!markers.length) throw new Error('No hay marcadores Jugador visibles en IN (selecciona uno o crea varios).');

	        setStatus(`AutoTrack: siguiendo ${markers.length} jugador(es)… (beta)`);
	        const smooth = getTrackSmoothStrength();
	        const antiJump = isTrackAntiJumpEnabled();
	        const resp = await fetch(trackUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          cache: 'no-store',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	          body: JSON.stringify({ video_id: videoId, start_s: start, end_s: end, fps: 10, max_w: 1280, markers, smooth, anti_jump: antiJump }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(safeText(data?.error, 'No se pudo hacer tracking.'));

	        const tracks = data.tracks && typeof data.tracks === 'object' ? data.tracks : {};
	        const meta = data.track_meta && typeof data.track_meta === 'object' ? data.track_meta : {};
	        let applied = 0;
	        let dropped = 0;
	        for (const [uid, points] of Object.entries(tracks)) {
	          const obj = uidToObj.get(String(uid));
	          if (!obj || !Array.isArray(points) || !points.length) continue;
	          const rawKf = points
	            .map((p0) => ({
	              t: Number(p0?.t),
	              x: Number(p0?.x_rel) * canvasW,
	              y: Number(p0?.y_rel) * canvasH,
	            }))
	            .filter((p0) => Number.isFinite(p0.t) && Number.isFinite(p0.x) && Number.isFinite(p0.y));
	          const kf = cleanTrackKeyframes(rawKf, { smooth, antiJump });
	          dropped += Number(kf.dropped || 0);
	          dropped += Number(meta?.[uid]?.dropped || 0);
	          if (!kf.length) continue;
	          ensureLayerData(obj);
	          obj.data.track = true;
	          obj.data.kf = normalizeKeyframes(kf);
	          obj.data.t_in_s = start;
	          obj.data.t_out_s = end;
	          obj.data.track_smooth = smooth;
	          obj.data.track_antijump = antiJump;
	          applied += 1;
	        }
	        if (!applied) throw new Error('No se pudo aplicar tracking (sin resultados).');
	        pushHistory();
	        renderDrawLayers();
	        updateLayerPanel();
	        setStatus(`AutoTrack: OK (${applied}/${markers.length}). Saltos filtrados: ${dropped}. Puedes corregir arrastrando en Play.`);
	      } catch (e) {
	        setStatus(`AutoTrack: ${safeText(e?.message, 'error')}`, true);
	      } finally {
	        btnTrackAuto.textContent = prevLabel;
	        btnTrackAuto.disabled = false;
	        if (wasPlaying) { try { await video.play(); } catch (e9) { /* ignore */ } }
	      }
	    };
	    btnTrackAuto?.addEventListener('click', () => { autoTrackPlayers(); });
	    btnTrackSmoothSelected?.addEventListener('click', () => { smoothSelectedTrackMarker(); });

	    const showAiCandidatePicker = async (candidateGroups = [], rawAnchors = []) => new Promise((resolve) => {
	      const groups = Array.isArray(candidateGroups) ? candidateGroups : [];
	      if (!groups.length) { resolve(rawAnchors); return; }
	      const wrap = document.createElement('div');
	      wrap.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(2,6,23,0.74);display:flex;align-items:center;justify-content:center;padding:18px;';
	      const selected = new Map();
	      const groupHtml = groups.map((g, idx) => {
	        const anchor = g?.anchor || rawAnchors[idx] || {};
	        const dets = Array.isArray(g?.detections) ? g.detections : [];
	        const buttons = dets.slice(0, 6).map((d, j) => {
	          const tid = safeText(d?.track_id ?? '?');
	          const conf = Math.round((Number(d?.conf) || 0) * 100);
	          const dist = Number(d?.distance || 0).toFixed(3);
	          const best = d?.ocr?.best ? ` · dorsal ${escHtml(String(d.ocr.best))}` : '';
	          return `<button type="button" class="button" data-ai-cand="${idx}:${j}" style="text-align:left;justify-content:flex-start;min-height:42px;">ID ${escHtml(tid)} · ${conf}% · d ${escHtml(dist)}${best}</button>`;
	        }).join('') || '<div class="meta">Sin candidato claro en este anclaje.</div>';
	        return `
	          <div style="border:1px solid rgba(148,163,184,0.22);border-radius:12px;padding:10px;background:rgba(15,23,42,0.72);">
	            <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px;">
	              <strong>Anclaje ${idx + 1}</strong>
	              <small style="opacity:.76;">${fmtTimeShort(Number(anchor?.t) || Number(g?.frame_t) || 0)}</small>
	            </div>
	            <div style="display:grid;gap:7px;">${buttons}</div>
	          </div>
	        `;
	      }).join('');
	      wrap.innerHTML = `
	        <div style="width:min(760px,96vw);max-height:86vh;overflow:auto;border:1px solid rgba(148,163,184,0.28);border-radius:16px;background:#0f172a;color:#f8fafc;box-shadow:0 24px 80px rgba(0,0,0,.42);padding:16px;">
	          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;">
	            <div>
	              <h3 style="margin:0 0 4px;font-size:1rem;">Candidatos AutoTrack IA</h3>
	              <p style="margin:0;color:#cbd5e1;font-size:.86rem;">Elige el jugador correcto en cada anclaje dudoso. Si no eliges, se mantiene el anclaje manual.</p>
	            </div>
	            <button type="button" class="button" data-ai-close>Cerrar</button>
	          </div>
	          <div style="display:grid;gap:10px;margin-bottom:14px;">${groupHtml}</div>
	          <div style="display:flex;justify-content:flex-end;gap:8px;position:sticky;bottom:0;background:#0f172a;padding-top:10px;">
	            <button type="button" class="button" data-ai-skip>Usar anclas</button>
	            <button type="button" class="button primary" data-ai-apply>Aplicar selección</button>
	          </div>
	        </div>
	      `;
	      const cleanup = (value) => {
	        try { wrap.remove(); } catch (e) { /* ignore */ }
	        resolve(value);
	      };
	      wrap.addEventListener('click', (ev) => {
	        const closeBtn = ev.target?.closest?.('[data-ai-close]');
	        if (closeBtn) { cleanup(null); return; }
	        const skipBtn = ev.target?.closest?.('[data-ai-skip]');
	        if (skipBtn) { cleanup(rawAnchors); return; }
	        const applyBtn = ev.target?.closest?.('[data-ai-apply]');
	        if (applyBtn) {
	          const next = rawAnchors.map((a, idx) => {
	            const det = selected.get(idx);
	            if (!det) return a;
	            return { ...a, x_rel: clamp(Number(det.x_rel) || Number(a.x_rel) || 0, 0, 1), y_rel: clamp(Number(det.y_rel) || Number(a.y_rel) || 0, 0, 1), selected_track_id: det.track_id ?? null };
	          });
	          cleanup(next);
	          return;
	        }
	        const candBtn = ev.target?.closest?.('[data-ai-cand]');
	        if (!candBtn) return;
	        const parts = safeText(candBtn.getAttribute('data-ai-cand')).split(':').map((x) => Number(x));
	        const gi = Number(parts[0]);
	        const di = Number(parts[1]);
	        const det = groups?.[gi]?.detections?.[di];
	        if (!det) return;
	        selected.set(gi, det);
	        try {
	          Array.from(wrap.querySelectorAll(`[data-ai-cand^="${gi}:"]`)).forEach((b) => b.classList.remove('primary'));
	          candBtn.classList.add('primary');
	        } catch (e) { /* ignore */ }
	      });
	      document.body.appendChild(wrap);
	    });

	    const pollAiTrackJob = async (jobId, { timeoutMs = 900000 } = {}) => {
	      const started = Date.now();
	      let last = null;
	      while (Date.now() - started < timeoutMs) {
	        await new Promise((resolve) => window.setTimeout(resolve, 1600));
	        const resp = await fetch(aiTrackUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          cache: 'no-store',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	          body: JSON.stringify({ action: 'status', job_id: jobId }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(safeText(data?.error, 'No se pudo consultar el job IA.'));
	        const job = data.job || {};
	        last = job;
	        const status = safeText(job.status);
	        const progress = Number(job.progress || 0) || 0;
	        const message = safeText(job.message || '');
	        setStatus(`AutoTrack IA: ${message || status} ${progress}%`);
	        if (status === 'done') return job.result || {};
	        if (status === 'error') throw new Error(safeText(job.error, 'Job IA con error.'));
	        if (status === 'canceled') throw new Error('Job IA cancelado.');
	      }
	      throw new Error(safeText(last?.message, 'Tiempo agotado esperando AutoTrack IA.'));
	    };

	    const aiProPost = async (payload = {}) => {
	      if (!aiProUrl) throw new Error('IA Pro no disponible.');
	      const resp = await fetch(aiProUrl, {
	        method: 'POST',
	        credentials: 'same-origin',
	        cache: 'no-store',
	        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	        body: JSON.stringify({ video_id: videoId, ...payload }),
	      });
	      const data = await resp.json().catch(() => ({}));
	      if (!resp.ok || !data?.ok) throw new Error(safeText(data?.error, 'Error IA Pro.'));
	      return data;
	    };

	    const selectedPlayerMarker = () => {
	      try {
	        const active = fabricCanvas.getActiveObject?.() || null;
	        if (!active) return null;
	        const items = active.type === 'activeSelection' && typeof active.getObjects === 'function' ? active.getObjects() : [active];
	        return (items || []).find((obj) => safeText(obj?.data?.kind) === 'player_marker') || null;
	      } catch (e) {
	        return null;
	      }
	    };

	    const ensureActiveClipForAiPro = async () => {
	      let id = Number(activeClipId || initialClipId || 0) || 0;
	      if (id) return id;
	      id = Number(await saveClip({ forceNew: true }) || 0);
	      return id || 0;
	    };

	    const aiProCorrectCurrent = async () => {
	      const marker = selectedPlayerMarker();
	      if (!marker) { setStatus('IA Pro: selecciona un marcador Jugador.', true); return; }
	      const clipId = await ensureActiveClipForAiPro();
	      if (!clipId) { setStatus('IA Pro: no se pudo guardar el clip base.', true); return; }
	      const canvasW = Number(fabricCanvas.getWidth?.()) || 0;
	      const canvasH = Number(fabricCanvas.getHeight?.()) || 0;
	      const t = Number(video.currentTime || 0) || 0;
	      const c = marker.getCenterPoint ? marker.getCenterPoint() : null;
	      const x = Number(c?.x ?? marker.left) || 0;
	      const y = Number(c?.y ?? marker.top) || 0;
	      ensureLayerData(marker);
	      marker.data.track = true;
	      upsertKeyframe(marker, { t, x, y });
	      marker.data.ai_corrected = true;
	      marker.data.ai_corrections = Number(marker.data.ai_corrections || 0) + 1;
	      pushHistory();
	      renderDrawLayers();
	      updateLayerPanel();
	      try {
	        const data = await aiProPost({
	          action: 'correction',
	          clip_id: clipId,
	          marker_uid: safeText(marker?.data?.uid || ''),
	          time_s: t,
	          x_rel: clamp(x / Math.max(1, canvasW), 0, 1),
	          y_rel: clamp(y / Math.max(1, canvasH), 0, 1),
	          label: safeText(marker?.data?.number || 'target_player'),
	          payload: { source: 'manual_frame_correction' },
	        });
	        setStatus(`IA Pro: corrección guardada (#${data.example_id || ''}).`);
	      } catch (e) {
	        setStatus(`IA Pro: ${safeText(e?.message, 'error')}`, true);
	      }
	    };

	    const aiProQualitySelected = async () => {
	      const marker = selectedPlayerMarker();
	      const clipId = await ensureActiveClipForAiPro();
	      if (!clipId) { setStatus('IA Pro: no hay clip activo.', true); return; }
	      try {
	        const data = await aiProPost({ action: 'quality', clip_id: clipId, marker_uid: safeText(marker?.data?.uid || '') });
	        const q = data.quality || {};
	        if (marker) {
	          ensureLayerData(marker);
	          marker.data.ai_quality = q;
	          marker.data.ai_needs_correction = Boolean(q.needs_correction);
	          updateLayerPanel();
	        }
	        const label = safeText(q.label || '');
	        const score = Math.round((Number(q.score || 0) || 0) * 100);
	        const low = Array.isArray(q.low_ranges) ? q.low_ranges.length : 0;
	        const jumps = Array.isArray(q.jumps) ? q.jumps.length : 0;
	        setStatus(`IA Pro calidad: ${label || 'n/d'} ${score}% · dudas ${low} · saltos ${jumps}.`);
	      } catch (e) {
	        setStatus(`IA Pro: ${safeText(e?.message, 'error')}`, true);
	      }
	    };

	    const extractAiFreezeAnnotations = () => {
	      const canvasW = Number(fabricCanvas.getWidth?.()) || 1;
	      const canvasH = Number(fabricCanvas.getHeight?.()) || 1;
	      const normPoint = (x, y) => ({
	        x: clamp((Number(x) || 0) / Math.max(1, canvasW), 0, 1),
	        y: clamp((Number(y) || 0) / Math.max(1, canvasH), 0, 1),
	      });
	      const normBox = (obj) => {
	        let r = null;
	        try { r = obj?.getBoundingRect?.(true, true); } catch (e) { try { r = obj?.getBoundingRect?.(); } catch (e2) { r = null; } }
	        if (!r) return null;
	        return {
	          x: clamp((Number(r.left) || 0) / Math.max(1, canvasW), 0, 1),
	          y: clamp((Number(r.top) || 0) / Math.max(1, canvasH), 0, 1),
	          w: clamp((Number(r.width) || 0) / Math.max(1, canvasW), 0, 1),
	          h: clamp((Number(r.height) || 0) / Math.max(1, canvasH), 0, 1),
	        };
	      };
	      const objectText = (obj) => {
	        const texts = [];
	        const scan = (item) => {
	          if (!item) return;
	          if (typeof item.text === 'string' && item.text.trim()) texts.push(item.text.trim());
	          if (Array.isArray(item._objects)) item._objects.forEach(scan);
	        };
	        scan(obj);
	        return texts.join(' ').trim();
	      };
	      const linePoints = (obj) => {
	        try {
	          if (obj?.type === 'line') return [normPoint(obj.x1, obj.y1), normPoint(obj.x2, obj.y2)];
	          if ((obj?.type === 'polygon' || obj?.type === 'polyline') && Array.isArray(obj.points)) return obj.points.slice(0, 12).map((p) => normPoint((Number(p.x) || 0) + (Number(obj.left) || 0), (Number(p.y) || 0) + (Number(obj.top) || 0)));
	          if (obj?.type === 'group' && Array.isArray(obj._objects)) {
	            const childLine = obj._objects.find((x) => x?.type === 'line');
	            if (childLine) {
	              const a = obj.calcTransformMatrix?.();
	              const p1 = fabric.util.transformPoint(new fabric.Point(childLine.x1, childLine.y1), a);
	              const p2 = fabric.util.transformPoint(new fabric.Point(childLine.x2, childLine.y2), a);
	              return [normPoint(p1.x, p1.y), normPoint(p2.x, p2.y)];
	            }
	          }
	        } catch (e) { /* ignore */ }
	        return [];
	      };
	      const rows = [];
	      try {
	        (fabricCanvas.getObjects?.() || []).forEach((obj) => {
	          const data = obj?.data || {};
	          const kind = safeText(data.kind || obj?.type || 'annotation', 'annotation');
	          if (kind === 'calib_point') return;
	          const row = {
	            uid: safeText(data.uid || ''),
	            kind,
	            text: objectText(obj),
	            color: safeText(obj?.stroke || obj?.fill || obj?._objects?.[0]?.stroke || obj?._objects?.[0]?.fill || ''),
	            line_style: safeText(data.line_style || ''),
	            box: normBox(obj),
	            points: linePoints(obj),
	          };
	          if (row.box || row.points.length || row.text) rows.push(row);
	        });
	      } catch (e) { /* ignore */ }
	      try {
	        (Array.isArray(fxState.layers) ? fxState.layers : []).forEach((layer) => {
	          const kind = safeText(layer?.kind || layer?.type || 'fx', 'fx');
	          if (kind === 'freeze') return;
	          const row = { uid: safeText(layer?.id || ''), kind, text: '', color: '', line_style: '', points: [] };
	          if (kind === 'spotlight') {
	            row.box = {
	              x: clamp((Number(layer.cx || 0) - Number(layer.r || 0)) / Math.max(1, canvasW), 0, 1),
	              y: clamp((Number(layer.cy || 0) - Number(layer.r || 0)) / Math.max(1, canvasH), 0, 1),
	              w: clamp((Number(layer.r || 0) * 2) / Math.max(1, canvasW), 0, 1),
	              h: clamp((Number(layer.r || 0) * 2) / Math.max(1, canvasH), 0, 1),
	            };
	          } else {
	            row.box = {
	              x: clamp(Number(layer.x || 0) / Math.max(1, canvasW), 0, 1),
	              y: clamp(Number(layer.y || 0) / Math.max(1, canvasH), 0, 1),
	              w: clamp(Number(layer.w || 0) / Math.max(1, canvasW), 0, 1),
	              h: clamp(Number(layer.h || 0) / Math.max(1, canvasH), 0, 1),
	            };
	          }
	          rows.push(row);
	        });
	      } catch (e) { /* ignore */ }
	      return rows.slice(0, 120);
	    };

	    const showAiProPanel = () => {
	      const wrap = document.createElement('div');
	      wrap.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(2,6,23,.72);display:flex;align-items:center;justify-content:center;padding:18px;';
	      wrap.innerHTML = `
	        <div style="width:min(680px,96vw);max-height:86vh;overflow:auto;border:1px solid rgba(148,163,184,.28);border-radius:16px;background:#0f172a;color:#f8fafc;box-shadow:0 24px 80px rgba(0,0,0,.42);padding:16px;">
	          <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px;">
	            <div>
	              <h3 style="margin:0 0 4px;font-size:1rem;">IA Pro</h3>
	              <p style="margin:0;color:#cbd5e1;font-size:.86rem;">Herramientas de analista para mejorar seguimiento, aprender de correcciones y preparar exports.</p>
	            </div>
	            <button type="button" class="button" data-ai-pro-close>Cerrar</button>
	          </div>
	          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px;">
	            <button type="button" class="button" data-ai-pro-act="profile">Modelo jugador</button>
	            <button type="button" class="button" data-ai-pro-act="identity_profile">Identidad jugador</button>
	            <button type="button" class="button primary" data-ai-pro-act="select_player_click">Seleccionar con clic</button>
	            <button type="button" class="button primary" data-ai-pro-act="manual_anchor">Anclar jugador</button>
	            <button type="button" class="button" data-ai-pro-act="manual_anchor_list">Ver anclajes</button>
	            <button type="button" class="button" data-ai-pro-act="anchor_suggestions">Sugerir anclajes</button>
	            <button type="button" class="button primary" data-ai-pro-act="export_follow">Exportar seguimiento</button>
	            <button type="button" class="button" data-ai-pro-act="batch">Batch clips</button>
	            <button type="button" class="button" data-ai-pro-act="train">Entrenar</button>
	            <button type="button" class="button" data-ai-pro-act="export_pro">Export pro</button>
	            <button type="button" class="button" data-ai-pro-act="patterns">Patrones</button>
	            <button type="button" class="button primary" data-ai-pro-act="detect_actions">Detectar acciones</button>
	            <button type="button" class="button" data-ai-pro-act="action_dataset">Dataset acciones</button>
	            <button type="button" class="button primary" data-ai-pro-act="tactical_labels">Etiquetas tácticas</button>
	            <button type="button" class="button primary" data-ai-pro-act="freeze_annotation_feedback">Enseñar freeze</button>
	            <button type="button" class="button" data-ai-pro-act="ai_review">Revisión IA</button>
	            <button type="button" class="button" data-ai-pro-act="active_learning">Qué necesita aprender</button>
	            <button type="button" class="button" data-ai-pro-act="contrast_pair">Par comparativo</button>
	            <button type="button" class="button" data-ai-pro-act="team_profile">Perfil equipo/rival</button>
	            <button type="button" class="button" data-ai-pro-act="ball_example">Ejemplo balón</button>
	            <button type="button" class="button" data-ai-pro-act="field_homography">Campo real</button>
	            <button type="button" class="button" data-ai-pro-act="sequence_detect">Secuencia eventos</button>
	            <button type="button" class="button" data-ai-pro-act="model_plan">Plan fine-tune</button>
	            <button type="button" class="button" data-ai-pro-act="train_actions">Entrenar acciones</button>
	            <button type="button" class="button" data-ai-pro-act="cut_feedback">Feedback corte</button>
	            <button type="button" class="button" data-ai-pro-act="feedback_positive">Acción OK</button>
	            <button type="button" class="button danger" data-ai-pro-act="feedback_negative">Acción NO</button>
	            <button type="button" class="button primary" data-ai-pro-act="calibration_save">Calibrar campo</button>
	            <button type="button" class="button" data-ai-pro-act="calibration_get">Ver calibración</button>
	            <button type="button" class="button primary" data-ai-pro-act="knowledge_seed">Estudiar táctica</button>
	            <button type="button" class="button primary" data-ai-pro-act="senior_analyst_seed">Criterio senior</button>
	            <button type="button" class="button primary" data-ai-pro-act="senior_coach_seed">Criterio entrenador</button>
	            <button type="button" class="button" data-ai-pro-act="knowledge">Base táctica</button>
	          </div>
	          <div style="margin-top:12px;border-top:1px solid rgba(148,163,184,.18);padding-top:12px;">
	            <div style="font-size:.78rem;color:#cbd5e1;margin-bottom:8px;">Etiquetado táctico rápido</div>
	            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:6px;">
	              <button type="button" class="button primary" data-ai-tactical-key="bloque_bajo">Bloque bajo +</button>
	              <button type="button" class="button primary" data-ai-tactical-key="bloque_medio">Bloque medio +</button>
	              <button type="button" class="button primary" data-ai-tactical-key="bloque_alto">Bloque alto +</button>
	              <button type="button" class="button" data-ai-tactical-key="ocupacion_5_carriles">5 carriles +</button>
	              <button type="button" class="button" data-ai-tactical-key="carril_exterior">Carril exterior +</button>
	              <button type="button" class="button" data-ai-tactical-key="carril_interior">Carril interior +</button>
	              <button type="button" class="button" data-ai-tactical-key="carril_central">Carril central +</button>
	              <button type="button" class="button" data-ai-tactical-key="presion_alta">Presión alta +</button>
	              <button type="button" class="button" data-ai-tactical-key="linea_alta">Línea alta +</button>
	              <button type="button" class="button" data-ai-tactical-key="bloque_compacto">Bloque compacto +</button>
	              <button type="button" class="button danger" data-ai-tactical-negative>Etiqueta NO</button>
	            </div>
	          </div>
	          <pre data-ai-pro-out style="white-space:pre-wrap;background:rgba(2,6,23,.45);border:1px solid rgba(148,163,184,.18);border-radius:12px;padding:10px;min-height:110px;margin-top:12px;color:#dbeafe;font-size:.78rem;"></pre>
	        </div>
	      `;
	      const out = wrap.querySelector('[data-ai-pro-out]');
	      const write = (text) => { if (out) out.textContent = text; };
	      const run = async (act) => {
	        const marker = selectedPlayerMarker();
	        const clipId = await ensureActiveClipForAiPro();
	        const markerUid = safeText(marker?.data?.uid || '');
	        const selectedIds = (() => {
	          try {
	            if (selectedClipIds && selectedClipIds.size) return Array.from(selectedClipIds).map((x) => Number(x) || 0).filter((x) => x > 0);
	          } catch (e) { /* ignore */ }
	          return clipId ? [clipId] : [];
	        })();
	        write('Ejecutando…');
	        if (act === 'profile') {
	          const data = await aiProPost({ action: 'profile', clip_id: clipId, marker_uid: markerUid });
	          write(JSON.stringify(data.profile || {}, null, 2));
	          setStatus('IA Pro: modelo de jugador actualizado.');
	          return;
	        }
	        if (act === 'identity_profile') {
	          const data = await aiProPost({ action: 'identity_profile', clip_id: clipId, marker_uid: markerUid });
	          write(JSON.stringify(data.profile || {}, null, 2));
	          setStatus('IA Pro: identidad del jugador cargada.');
	          return;
	        }
	        if (act === 'select_player_click') {
	          wrap.style.display = 'none';
	          setStatus('IA Pro: haz clic sobre el jugador en el vídeo.');
	          const once = async (opt) => {
	            try {
	              fabricCanvas.off('mouse:down', once);
	              const p = fabricCanvas.getPointer(opt.e);
	              const num = window.prompt('Dorsal/ID del jugador', safeText(marker?.data?.number || '10')) || '10';
	              const created = createPlayerMarkerAt(p, num, 'OBJETIVO', { team: 'away', style: 'tag' });
	              const obj = fabricCanvas.getActiveObject?.();
	              if (obj && safeText(obj?.data?.kind) === 'player_marker') {
	                const c = obj.getCenterPoint ? obj.getCenterPoint() : p;
	                const canvasW = Number(fabricCanvas.getWidth?.()) || 1;
	                const canvasH = Number(fabricCanvas.getHeight?.()) || 1;
	                const data = await aiProPost({
	                  action: 'correction',
	                  clip_id: clipId,
	                  marker_uid: safeText(obj?.data?.uid || ''),
	                  time_s: Number(video.currentTime || 0) || 0,
	                  x_rel: clamp(Number(c.x || p.x) / canvasW, 0, 1),
	                  y_rel: clamp(Number(c.y || p.y) / canvasH, 0, 1),
	                  label: safeText(num),
	                  payload: { source: 'click_player_selector' },
	                });
	                write(JSON.stringify({ created, anchor: data }, null, 2));
	                setStatus('IA Pro: jugador seleccionado y anclaje inicial guardado.');
	              }
	            } catch (e) {
	              setStatus(`IA Pro: ${safeText(e?.message, 'error')}`, true);
	            } finally {
	              wrap.style.display = 'flex';
	            }
	          };
	          fabricCanvas.on('mouse:down', once);
	          return;
	        }
	        if (act === 'manual_anchor') {
	          if (!marker) { write('Selecciona un marcador Jugador.'); setStatus('IA Pro: selecciona un marcador Jugador.', true); return; }
	          await aiProCorrectCurrent();
	          const data = await aiProPost({ action: 'correction_list', clip_id: clipId, marker_uid: markerUid });
	          write(JSON.stringify({ count: data.count || 0, anchors: data.anchors || [] }, null, 2));
	          setStatus(`IA Pro: anclaje guardado. Total ${data.count || 0}.`);
	          return;
	        }
	        if (act === 'manual_anchor_list') {
	          const data = await aiProPost({ action: 'correction_list', clip_id: clipId, marker_uid: markerUid });
	          write(JSON.stringify({ count: data.count || 0, anchors: data.anchors || [] }, null, 2));
	          setStatus(`IA Pro: ${data.count || 0} anclajes cargados.`);
	          return;
	        }
	        if (act === 'anchor_suggestions') {
	          const data = await aiProPost({ action: 'anchor_suggestions', clip_id: clipId, marker_uid: markerUid });
	          write(JSON.stringify({ quality: data.quality || {}, suggestions: data.suggestions || [] }, null, 2));
	          const first = Array.isArray(data.suggestions) && data.suggestions.length ? data.suggestions[0] : null;
	          if (first && Number.isFinite(Number(first.time_s))) {
	            try { video.currentTime = Number(first.time_s); } catch (e) { /* ignore */ }
	          }
	          setStatus(`IA Pro: ${Array.isArray(data.suggestions) ? data.suggestions.length : 0} sugerencias de anclaje.`);
	          return;
	        }
	        if (act === 'export_follow') {
	          const data = await aiProPost({
	            action: 'export_follow',
	            clip_id: clipId,
	            marker_uid: markerUid,
	            start_s: Number(inInput?.value || 0) || undefined,
	            end_s: Number(outInput?.value || 0) || undefined,
	          });
	          const result = await pollAiTrackJob(Number(data.job_id), { timeoutMs: 900000 });
	          write(JSON.stringify(result, null, 2));
	          setStatus('IA Pro: seguimiento exportado a Descargas.');
	          return;
	        }
	        if (act === 'batch') {
	          const data = await aiProPost({ action: 'batch', clip_id: clipId, clip_ids: selectedIds });
	          const result = await pollAiTrackJob(Number(data.job_id), { timeoutMs: 900000 });
	          write(JSON.stringify(result, null, 2));
	          setStatus('IA Pro: batch completado.');
	          return;
	        }
	        if (act === 'train') {
	          const data = await aiProPost({ action: 'train', clip_id: clipId });
	          const result = await pollAiTrackJob(Number(data.job_id), { timeoutMs: 900000 });
	          write(JSON.stringify(result, null, 2));
	          setStatus('IA Pro: entrenamiento evaluado.');
	          return;
	        }
	        if (act === 'export_pro') {
	          const data = await aiProPost({ action: 'export_pro', clip_id: clipId, marker_uid: markerUid, title: safeText(clipTitleInput?.value || '') });
	          write(JSON.stringify(data.preset || {}, null, 2));
	          setStatus('IA Pro: preset de export pro guardado en el clip.');
	          return;
	        }
	        if (act === 'patterns') {
	          const data = await aiProPost({ action: 'patterns' });
	          write(JSON.stringify(data.patterns || [], null, 2));
	          setStatus('IA Pro: biblioteca táctica cargada.');
	          return;
	        }
	        if (act === 'detect_actions') {
	          const data = await aiProPost({ action: 'detect_actions', clip_id: clipId, clip_ids: selectedIds });
	          const result = await pollAiTrackJob(Number(data.job_id), { timeoutMs: 900000 });
	          write(JSON.stringify(result, null, 2));
	          setStatus('IA Pro: acciones detectadas.');
	          return;
	        }
	        if (act === 'action_dataset') {
	          const data = await aiProPost({ action: 'action_dataset', clip_id: clipId });
	          write(JSON.stringify({ examples: data.examples, labels: data.labels || [], dataset: data.dataset || {} }, null, 2));
	          setStatus('IA Pro: dataset de acciones cargado.');
	          return;
	        }
	        if (act === 'tactical_labels') {
	          const data = await aiProPost({ action: 'tactical_labels', clip_id: clipId });
	          write(JSON.stringify({ labels: data.labels || [], learning: data.learning || {} }, null, 2));
	          setStatus('IA Pro: etiquetas tácticas cargadas.');
	          return;
	        }
	        if (act === 'freeze_annotation_feedback') {
	          const annotations = extractAiFreezeAnnotations();
	          if (!annotations.length) {
	            write('No hay flechas, textos, áreas o FX para enseñar.');
	            setStatus('IA Pro: dibuja flechas/textos/zonas antes de enseñar el freeze.', true);
	            return;
	          }
	          const savedClipId = Number(await saveClip({ forceNew: false }) || clipId) || clipId;
	          const rawLabels = (window.prompt('Etiquetas opcionales separadas por coma', '2v1, ultimo_tercio') || '')
	            .split(',')
	            .map((x) => safeText(x).trim())
	            .filter(Boolean);
	          const canvasPayload = (() => {
	            try { return fabricCanvas.toDatalessJSON(['data']); } catch (e) { return {}; }
	          })();
	          const data = await aiProPost({
	            action: 'freeze_annotation_feedback',
	            clip_id: savedClipId,
	            time_s: Number(video.currentTime || 0) || 0,
	            annotations,
	            labels: rawLabels,
	            canvas: canvasPayload,
	            fx: { layers: Array.isArray(fxState.layers) ? fxState.layers : [] },
	            note: 'freeze_frame_anotado_manual',
	          });
	          write(JSON.stringify({ created: data.created || [], annotations: data.annotations, concepts: data.concepts || [], learning: data.learning || {} }, null, 2));
	          setStatus(`IA Pro: freeze enseñado (${data.annotations || annotations.length} anotaciones).`);
	          return;
	        }
	        if (act === 'contrast_pair') {
	          const key = (window.prompt('Etiqueta comparativa', 'bloque_bajo') || '').trim();
	          if (!key) { write('Cancelado.'); return; }
	          const negativeId = Number(window.prompt('Clip negativo / NO es esa etiqueta', '') || 0) || 0;
	          if (!negativeId) { write('Cancelado: falta clip negativo.'); return; }
	          const data = await aiProPost({
	            action: 'contrast_pair',
	            clip_id: clipId,
	            positive_clip_id: clipId,
	            negative_clip_id: negativeId,
	            action_key: key,
	            note: 'par_comparativo_desde_panel_ia_pro',
	          });
	          write(JSON.stringify(data, null, 2));
	          setStatus(`IA Pro: par comparativo guardado para ${safeText(key)}.`);
	          return;
	        }
	        if (['ai_review', 'active_learning', 'team_profile', 'field_homography', 'sequence_detect', 'model_plan'].includes(act)) {
	          const data = await aiProPost({ action: act, clip_id: clipId });
	          write(JSON.stringify(data, null, 2));
	          setStatus(`IA Pro: ${safeText(act)} cargado.`);
	          return;
	        }
	        if (act === 'ball_example') {
	          const x = window.prompt('X balón normalizado 0..1 (vacío = centro)', '0.5');
	          const y = window.prompt('Y balón normalizado 0..1 (vacío = centro)', '0.5');
	          const data = await aiProPost({
	            action: 'ball_example',
	            clip_id: clipId,
	            time_s: Number(video.currentTime || 0) || 0,
	            x_rel: clamp(Number(x || 0.5) || 0.5, 0, 1),
	            y_rel: clamp(Number(y || 0.5) || 0.5, 0, 1),
	          });
	          write(JSON.stringify(data, null, 2));
	          setStatus('IA Pro: ejemplo de balón guardado.');
	          return;
	        }
	        if (act === 'train_actions') {
	          const data = await aiProPost({ action: 'train_actions', clip_id: clipId });
	          const result = await pollAiTrackJob(Number(data.job_id), { timeoutMs: 900000 });
	          write(JSON.stringify(result, null, 2));
	          setStatus('IA Pro: entrenamiento de acciones evaluado.');
	          return;
	        }
	        if (act === 'cut_feedback') {
	          const feedback = (window.prompt('Feedback del corte: ok, starts_late, starts_early, ends_late, ends_early, wrong_action', 'starts_late') || '').trim();
	          if (!feedback) { write('Cancelado.'); return; }
	          const data = await aiProPost({
	            action: 'cut_feedback',
	            clip_id: clipId,
	            feedback,
	            suggested_start_s: Number(inInput?.value || 0) || undefined,
	            suggested_end_s: Number(outInput?.value || 0) || undefined,
	            note: 'feedback_desde_panel_ia_pro',
	          });
	          write(JSON.stringify(data, null, 2));
	          setStatus(`IA Pro: feedback de corte guardado (#${data.example_id || ''}).`);
	          return;
	        }
	        if (act === 'calibration_get') {
	          const data = await aiProPost({ action: 'calibration_get', clip_id: clipId });
	          write(JSON.stringify(data.calibration || {}, null, 2));
	          setStatus('IA Pro: calibración cargada.');
	          return;
	        }
	        if (act === 'calibration_save') {
	          const direction = (window.prompt('Dirección de ataque de tu equipo: ltr = izquierda a derecha, rtl = derecha a izquierda', 'ltr') || '').trim().toLowerCase();
	          if (!['ltr', 'rtl', 'unknown'].includes(direction)) { write('Cancelado: usa ltr, rtl o unknown.'); return; }
	          const canvasW = Number(fabricCanvas.getWidth?.()) || 1;
	          const canvasH = Number(fabricCanvas.getHeight?.()) || 1;
	          const obj = fabricCanvas.getActiveObject?.();
	          let rect = null;
	          if (obj && typeof obj.getBoundingRect === 'function') {
	            try { rect = obj.getBoundingRect(true, true); } catch (e) { rect = obj.getBoundingRect(); }
	          }
	          const x0 = clamp(Number(rect?.left || 0) / Math.max(1, canvasW), 0, 1);
	          const y0 = clamp(Number(rect?.top || 0) / Math.max(1, canvasH), 0, 1);
	          const x1 = clamp(Number((rect ? rect.left + rect.width : canvasW)) / Math.max(1, canvasW), 0, 1);
	          const y1 = clamp(Number((rect ? rect.top + rect.height : canvasH)) / Math.max(1, canvasH), 0, 1);
	          const confidence = rect ? 0.72 : 0.48;
	          const data = await aiProPost({
	            action: 'calibration_save',
	            clip_id: clipId,
	            attack_direction: direction,
	            field_points: {
	              tl: { x: x0, y: y0 },
	              tr: { x: x1, y: y0 },
	              br: { x: x1, y: y1 },
	              bl: { x: x0, y: y1 },
	            },
	            confidence,
	            payload: { source: rect ? 'selected_canvas_region' : 'full_video_frame', current_time_s: Number(video.currentTime || 0) || 0 },
	          });
	          write(JSON.stringify(data.calibration || data, null, 2));
	          setStatus(`IA Pro: calibración guardada (${direction}, ${Math.round(confidence * 100)}%).`);
	          return;
	        }
	        if (act === 'feedback_positive' || act === 'feedback_negative') {
	          const key = window.prompt('Etiqueta de acción', '1v1_banda');
	          if (!key) { write('Cancelado.'); return; }
	          const data = await aiProPost({
	            action: 'action_feedback',
	            clip_id: clipId,
	            action_key: safeText(key).slice(0, 80),
	            label: safeText(key).replace(/_/g, ' '),
	            is_positive: act === 'feedback_positive',
	            start_s: Number(inInput?.value || 0) || 0,
	            end_s: Number(outInput?.value || 0) || 0,
	            confidence: 1,
	            payload: { source: 'analyst_feedback_panel' },
	          });
	          write(JSON.stringify(data, null, 2));
	          setStatus(`IA Pro: feedback de acción guardado (#${data.example_id || ''}).`);
	          return;
	        }
	        if (act === 'knowledge_seed' || act === 'senior_analyst_seed' || act === 'senior_coach_seed') {
	          const data = await aiProPost({ action: 'knowledge_seed' });
	          write(JSON.stringify(data, null, 2));
	          setStatus(`IA Pro: base táctica/entrenador senior inicializada (${data.created || 0} nuevos, ${data.updated || 0} actualizados).`);
	          return;
	        }
	        if (act === 'knowledge') {
	          const data = await aiProPost({ action: 'knowledge' });
	          write(JSON.stringify({ sources: data.sources || [], packs: data.packs || {}, entries: data.entries || [] }, null, 2));
	          setStatus(`IA Pro: ${Array.isArray(data.entries) ? data.entries.length : 0} conceptos tácticos cargados.`);
	        }
	      };
	      wrap.addEventListener('click', async (ev) => {
	        if (ev.target?.closest?.('[data-ai-pro-close]')) { try { wrap.remove(); } catch (e) { /* ignore */ } return; }
	        const tacticalBtn = ev.target?.closest?.('[data-ai-tactical-key],[data-ai-tactical-negative]');
	        if (tacticalBtn) {
	          try {
	            const clipId = await ensureActiveClipForAiPro();
	            const key = safeText(tacticalBtn.getAttribute('data-ai-tactical-key') || '') || safeText(window.prompt('Etiqueta táctica negativa', 'bloque_bajo') || '');
	            if (!key) { write('Cancelado.'); return; }
	            const isNegative = Boolean(tacticalBtn.hasAttribute('data-ai-tactical-negative'));
	            const data = await aiProPost({
	              action: 'tactical_quick_feedback',
	              clip_id: clipId,
	              labels: [key],
	              is_positive: !isNegative,
	              evidence_level: isNegative ? 'human_negative' : 'confirmed',
	              start_s: Number(inInput?.value || 0) || undefined,
	              end_s: Number(outInput?.value || 0) || undefined,
	              note: 'etiqueta_rapida_panel_ia_pro',
	            });
	            write(JSON.stringify({ created: data.created || [], learning: data.learning || {} }, null, 2));
	            setStatus(`IA Pro: etiqueta ${isNegative ? 'negativa' : 'positiva'} guardada (${safeText(key)}).`);
	          } catch (e) {
	            write(safeText(e?.message, 'error'));
	            setStatus(`IA Pro: ${safeText(e?.message, 'error')}`, true);
	          }
	          return;
	        }
	        const btn = ev.target?.closest?.('[data-ai-pro-act]');
	        if (!btn) return;
	        try { await run(safeText(btn.getAttribute('data-ai-pro-act'))); }
	        catch (e) { write(safeText(e?.message, 'error')); setStatus(`IA Pro: ${safeText(e?.message, 'error')}`, true); }
	      });
	      document.body.appendChild(wrap);
	    };

	    btnAiProCorrect?.addEventListener('click', () => { aiProCorrectCurrent(); });
	    btnAiProQuality?.addEventListener('click', () => { aiProQualitySelected(); });
	    btnAiProPanel?.addEventListener('click', () => { showAiProPanel(); });

	    const buildSpaceOccupancyPayload = (obj, canvasW, canvasH, start, end) => {
	      const space = promoteToSpaceZone(obj);
	      if (!space || !canvasW || !canvasH) return null;
	      ensureLayerData(space);
	      const uid = safeText(space.data.uid, '');
	      if (!uid) return null;
	      let rect = null;
	      try { rect = space.getBoundingRect?.(true, true); } catch (e) { rect = null; }
	      const center = objectCenterPoint(space);
	      const wPx = Math.max(4, Number(rect?.width) || Number(space.getScaledWidth?.()) || 40);
	      const hPx = Math.max(4, Number(rect?.height) || Number(space.getScaledHeight?.()) || 40);
	      const base = {
	        t: Number(video.currentTime) || start,
	        x_rel: clamp((Number(center?.x ?? space.left) || 0) / canvasW, 0, 1),
	        y_rel: clamp((Number(center?.y ?? space.top) || 0) / canvasH, 0, 1),
	        w_rel: clamp(wPx / canvasW, 0.002, 1),
	        h_rel: clamp(hPx / canvasH, 0.002, 1),
	      };
	      const mode = safeText(space.data.follow_mode, 'manual') || 'manual';
	      let kf = normalizeKeyframes(space.data.kf || [])
	        .filter((k) => Number(k.t) >= start - 0.12 && Number(k.t) <= end + 0.12)
	        .map((k) => ({
	          t: Number(k.t),
	          x_rel: clamp((Number(k.x) || 0) / canvasW, 0, 1),
	          y_rel: clamp((Number(k.y) || 0) / canvasH, 0, 1),
	          w_rel: base.w_rel,
	          h_rel: base.h_rel,
	        }));
	      if (mode === 'player') {
	        const followedUid = safeText(space.data.follow_player_uid, '');
	        const marker = getPlayerMarkers().find((m) => safeText(m?.data?.uid, '') === followedUid) || null;
	        const off = space.data.follow_offset || {};
	        const ox = Number(off.x) || 0;
	        const oy = Number(off.y) || 0;
	        const markerFrames = normalizeKeyframes(marker?.data?.kf || [])
	          .filter((k) => Number(k.t) >= start - 0.12 && Number(k.t) <= end + 0.12);
	        if (markerFrames.length) {
	          kf = markerFrames.map((k) => ({
	            t: Number(k.t),
	            x_rel: clamp(((Number(k.x) || 0) + ox) / canvasW, 0, 1),
	            y_rel: clamp(((Number(k.y) || 0) + oy) / canvasH, 0, 1),
	            w_rel: base.w_rel,
	            h_rel: base.h_rel,
	          }));
	        }
	      }
	      if (!kf.length) kf = [{ ...base, t: start }];
	      const off = space.data.follow_offset || {};
	      return {
	        uid,
	        follow_mode: mode,
	        follow_offset: {
	          x_rel: clamp((Number(off.x) || 0) / canvasW, -1, 1),
	          y_rel: clamp((Number(off.y) || 0) / canvasH, -1, 1),
	        },
	        x_rel: base.x_rel,
	        y_rel: base.y_rel,
	        w_rel: base.w_rel,
	        h_rel: base.h_rel,
	        kf,
	      };
	    };

	    const applySpaceAiOccupancy = async () => {
	      if (!btnSpaceAiOccupancy) return;
	      if (!aiTrackUrl || !videoId) { setStatus('Ocupación IA no disponible.', true); return; }
	      const a = Math.max(0, Number(inInput?.value || 0) || 0);
	      const b = Math.max(0, Number(outInput?.value || 0) || 0);
	      const start = Math.min(a, b);
	      const end = Math.max(a, b);
	      if (!end || end <= start + 0.05) { setStatus('Ocupación IA: define IN/OUT.', true); return; }
	      const canvasW = Number(fabricCanvas.getWidth?.()) || 0;
	      const canvasH = Number(fabricCanvas.getHeight?.()) || 0;
	      if (!canvasW || !canvasH) { setStatus('Ocupación IA: canvas no listo.', true); return; }
	      const spaces = selectedObjectsForSpace()
	        .filter((obj) => {
	          const k = safeText(obj?.data?.kind, '');
	          return k === 'space_zone' || k === 'surface_area';
	        })
	        .map((obj) => promoteToSpaceZone(obj))
	        .filter(Boolean);
	      if (!spaces.length) { setStatus('Ocupación IA: selecciona uno o varios Espacios.', true); return; }
	      const zones = spaces.map((obj) => buildSpaceOccupancyPayload(obj, canvasW, canvasH, start, end)).filter(Boolean);
	      if (!zones.length) { setStatus('Ocupación IA: no se pudo preparar el espacio.', true); return; }
	      const prev = safeText(btnSpaceAiOccupancy.textContent, 'Ocupación IA');
	      btnSpaceAiOccupancy.disabled = true;
	      btnSpaceAiOccupancy.textContent = 'Ocupando…';
	      setStatus(`Ocupación IA: detectando jugadores para ${zones.length} espacio(s)…`);
	      try {
	        const resp = await fetch(aiTrackUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          cache: 'no-store',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	          body: JSON.stringify({
	            action: 'space_occupancy',
	            video_id: videoId,
	            start_s: start,
	            end_s: end,
	            zones,
	            conf: 0.20,
	            person_conf: 0.18,
	            async: (end - start) > 20,
	          }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(safeText(data?.error, 'No se pudo calcular ocupación.'));
	        const result = data.action === 'job' && data.job_id ? await pollAiTrackJob(Number(data.job_id)) : data;
	        const occupancy = result.occupancy && typeof result.occupancy === 'object' ? result.occupancy : {};
	        const summary = result.summary && typeof result.summary === 'object' ? result.summary : {};
	        let applied = 0;
	        for (const space of spaces) {
	          ensureLayerData(space);
	          const uid = safeText(space.data.uid, '');
	          const rows = Array.isArray(occupancy[uid]) ? occupancy[uid] : [];
	          if (!rows.length) continue;
	          space.data.space_occ = rows.slice(0, 720);
	          space.data.space_occ_summary = summary[uid] || {};
	          space.data.space_occ_source = 'yolo-person';
	          applied += 1;
	        }
	        if (!applied) throw new Error('IA sin ocupación aplicable para los espacios seleccionados.');
	        pushHistory();
	        try { applyTimedLayers(); fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        renderDrawLayers();
	        updateLayerPanel();
	        const ratios = spaces.map((s) => {
	          const r = s?.data?.space_occ_summary || {};
	          return `${Math.round((Number(r.occupied_ratio) || 0) * 100)}%`;
	        }).slice(0, 4).join(', ');
	        setStatus(`Ocupación IA aplicada (${applied}). Ocupado: ${ratios || '0%'}.`);
	      } catch (e) {
	        setStatus(`Ocupación IA: ${safeText(e?.message, 'error')}`, true);
	      } finally {
	        btnSpaceAiOccupancy.textContent = prev;
	        btnSpaceAiOccupancy.disabled = false;
	      }
	    };
	    btnSpaceAiOccupancy?.addEventListener('click', () => { applySpaceAiOccupancy(); });

	    const autoTrackPlayersAi = async () => {
	      if (!btnTrackAi) return;
	      if (!aiTrackUrl || !videoId) { setStatus('AutoTrack IA no disponible.', true); return; }
	      const a = Math.max(0, Number(inInput?.value || 0) || 0);
	      const b = Math.max(0, Number(outInput?.value || 0) || 0);
	      const start = Math.min(a, b);
	      const end = Math.max(a, b);
	      if (!end || end <= start + 0.05) { setStatus('AutoTrack IA: define IN/OUT.', true); return; }

	      const active = (() => { try { return fabricCanvas.getActiveObject?.() || null; } catch (e) { return null; } })();
	      const selected = (() => {
	        try {
	          if (!active) return [];
	          if (active.type === 'activeSelection' && typeof active.getObjects === 'function') return active.getObjects() || [];
	          return [active];
	        } catch (e) { return []; }
	      })();
	      const marker = selected.find((obj) => safeText(obj?.data?.kind) === 'player_marker') || null;
	      if (!marker) { setStatus('AutoTrack IA: selecciona un marcador Jugador.', true); return; }
	      ensureLayerData(marker);

	      const canvasW = Number(fabricCanvas.getWidth?.()) || 0;
	      const canvasH = Number(fabricCanvas.getHeight?.()) || 0;
	      if (!canvasW || !canvasH) { setStatus('AutoTrack IA: canvas no listo.', true); return; }
	      let center = null;
	      try { center = marker.getCenterPoint?.(); } catch (e) { center = null; }
	      const uid = safeText(marker?.data?.uid, `ai-${Date.now()}`) || `ai-${Date.now()}`;
	      const rawAnchors = normalizeKeyframes(marker?.data?.kf || [])
	        .filter((k) => Number(k.t) >= start - 0.08 && Number(k.t) <= end + 0.08)
	        .map((k) => ({
	          t: Number(k.t),
	          x_rel: clamp((Number(k.x) || 0) / canvasW, 0, 1),
	          y_rel: clamp((Number(k.y) || 0) / canvasH, 0, 1),
	        }));
	      if (!rawAnchors.length) {
	        rawAnchors.push({
	          t: start,
	          x_rel: clamp((Number(center?.x ?? marker.left) || 0) / canvasW, 0, 1),
	          y_rel: clamp((Number(center?.y ?? marker.top) || 0) / canvasH, 0, 1),
	        });
	      }
	      let targetClipId = activeClipId || initialClipId || Number(document.getElementById('vs-current-clip-id')?.value || 0) || 0;
	      if (!targetClipId) {
	        setStatus('AutoTrack IA: guardando clip base…');
	        targetClipId = Number(await saveClip({ forceNew: true }) || 0);
	        if (!targetClipId) {
	          setStatus('AutoTrack IA: no se pudo crear el clip base.', true);
	          return;
	        }
	      }

	      const prev = safeText(btnTrackAi.textContent, 'AutoTrack IA');
	      btnTrackAi.disabled = true;
	      btnTrackAi.textContent = 'IA…';
	      setStatus(`AutoTrack IA: detectando candidatos (${rawAnchors.length} anclaje/s)…`);
	      try {
	        let anchors = rawAnchors;
	        if ((end - start) <= 20) {
	          const candResp = await fetch(aiTrackUrl, {
	            method: 'POST',
	            credentials: 'same-origin',
	            cache: 'no-store',
	            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	            body: JSON.stringify({
	              action: 'candidates',
	              video_id: videoId,
	              start_s: start,
	              end_s: end,
	              expected_number: safeText(marker?.data?.number || ''),
	              anchors: rawAnchors,
	            }),
	          });
	          const candData = await candResp.json().catch(() => ({}));
	          if (candResp.ok && candData?.ok) {
	            const picked = await showAiCandidatePicker(candData.candidates || [], rawAnchors);
	            if (picked === null) {
	              setStatus('AutoTrack IA cancelado.');
	              return;
	            }
	            anchors = Array.isArray(picked) && picked.length ? picked : rawAnchors;
	          }
	        }
	        setStatus(`AutoTrack IA: reidentificando (${anchors.length} anclaje/s)…`);
	        const resp = await fetch(aiTrackUrl, {
	          method: 'POST',
	          credentials: 'same-origin',
	          cache: 'no-store',
	          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, Accept: 'application/json' },
	          body: JSON.stringify({
	            action: 'reid',
	            video_id: videoId,
	            clip_id: targetClipId,
	            start_s: start,
	            end_s: end,
	            marker_uid: uid,
	            output_uid: uid,
	            expected_number: safeText(marker?.data?.number || ''),
	            anchors,
	            async: (end - start) > 20,
	            identity_lock: true,
	            identity_threshold: 0.74,
	          }),
	        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(safeText(data?.error, 'No se pudo ejecutar IA.'));
	        const result = data.action === 'job' && data.job_id ? await pollAiTrackJob(Number(data.job_id)) : data;
	        const points = Array.isArray(data.points) ? data.points : [];
	        const finalPoints = Array.isArray(result.points) ? result.points : points;
	        const kf = cleanTrackKeyframes(finalPoints.map((p) => ({
	          t: Number(p?.t),
	          x: Number(p?.x_rel) * canvasW,
	          y: Number(p?.y_rel) * canvasH,
	        })), { smooth: Math.max(0.25, getTrackSmoothStrength()), antiJump: true });
	        if (!kf.length) throw new Error('IA sin puntos aplicables.');
	        marker.data.track = true;
	        marker.data.kf = normalizeKeyframes(kf);
	        marker.data.t_in_s = start;
	        marker.data.t_out_s = end;
	        marker.data.track_ai = true;
	        marker.data.identity_lock = true;
	        marker.data.track_ai_meta = result.meta || data.meta || {};
	        pushHistory();
	        try { applyTimedLayers(); fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        renderDrawLayers();
	        updateLayerPanel();
	        const conf = safeText((result.meta || data.meta || {})?.confidence?.label || '');
	        setStatus(`AutoTrack IA: OK (${kf.length} puntos${conf ? `, confianza ${conf}` : ''}).`);
	      } catch (e) {
	        setStatus(`AutoTrack IA: ${safeText(e?.message, 'error')}`, true);
	      } finally {
	        btnTrackAi.textContent = prev;
	        btnTrackAi.disabled = false;
	      }
	    };
	    btnTrackAi?.addEventListener('click', () => { autoTrackPlayersAi(); });

		    pushHistory();
		    reseedFxSeq();
		    renderFxList();
	    updateLayerPanel();
	    renderDrawLayers();
	    setStatus('Listo.');

	    // Zoom “premium” (Ctrl/Cmd + rueda)
	    try {
	      if (stage && canTelestrate && fabricCanvas?.zoomToPoint) {
	        stage.addEventListener('wheel', (ev) => {
	          const mod = Boolean(ev.ctrlKey || ev.metaKey);
	          if (!mod) return;
	          ev.preventDefault();
	          const delta = Number(ev.deltaY) || 0;
	          const current = Number(fabricCanvas.getZoom?.() || 1) || 1;
	          // Sensibilidad suave
	          let next = current * Math.pow(0.999, delta);
	          next = clamp(next, 0.5, 4.0);
	          const p = fabricCanvas.getPointer(ev);
	          fabricCanvas.zoomToPoint(new fabric.Point(p.x, p.y), next);
	          try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        }, { passive: false });
	      }
	    } catch (e) { /* ignore */ }

	    // Pan “premium” (Space + arrastrar)
	    try {
	      if (stage && canTelestrate && fabricCanvas?.viewportTransform) {
	        let spaceDown = false;
	        let panActive = false;
	        let panPointerId = null;
	        let panStart = null;
	        let vtStart = null;

	        const setPanCursor = (mode) => {
	          try {
	            if (!stage) return;
	            stage.style.cursor = mode === 'active' ? 'grabbing' : (mode === 'ready' ? 'grab' : '');
	          } catch (e) { /* ignore */ }
	        };

	        window.addEventListener('keydown', (ev) => {
	          const key = safeText(ev?.key, '');
	          if (key !== ' ' && key !== 'Spacebar') return;
	          if (isTextEntryEl(document.activeElement)) return;
	          spaceDown = true;
	          if (!panActive) setPanCursor('ready');
	        });
	        window.addEventListener('keyup', (ev) => {
	          const key = safeText(ev?.key, '');
	          if (key !== ' ' && key !== 'Spacebar') return;
	          spaceDown = false;
	          if (!panActive) setPanCursor('off');
	        });

	        stage.addEventListener('pointerdown', (ev) => {
	          if (!spaceDown) return;
	          try { ev.preventDefault(); } catch (e) { /* ignore */ }
	          panActive = true;
	          panPointerId = ev.pointerId;
	          panStart = { x: ev.clientX, y: ev.clientY };
	          vtStart = (fabricCanvas.viewportTransform || [1, 0, 0, 1, 0, 0]).slice(0);
	          setPanCursor('active');
	          try { stage.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
	        });
	        stage.addEventListener('pointermove', (ev) => {
	          if (!panActive) return;
	          if (panPointerId != null && ev.pointerId !== panPointerId) return;
	          try { ev.preventDefault(); } catch (e) { /* ignore */ }
	          const dx = (ev.clientX - (panStart?.x || 0));
	          const dy = (ev.clientY - (panStart?.y || 0));
	          const vt = vtStart ? vtStart.slice(0) : [1, 0, 0, 1, 0, 0];
	          vt[4] = (Number(vtStart?.[4]) || 0) + dx;
	          vt[5] = (Number(vtStart?.[5]) || 0) + dy;
	          try { fabricCanvas.setViewportTransform(vt); } catch (e) { /* ignore */ }
	          try { fabricCanvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        });
	        const endPan = (ev) => {
	          if (!panActive) return;
	          if (panPointerId != null && ev && ev.pointerId != null && ev.pointerId !== panPointerId) return;
	          panActive = false;
	          panPointerId = null;
	          panStart = null;
	          vtStart = null;
	          setPanCursor(spaceDown ? 'ready' : 'off');
	        };
	        stage.addEventListener('pointerup', endPan);
	        stage.addEventListener('pointercancel', endPan);
	        stage.addEventListener('lostpointercapture', endPan);
	      }
	    } catch (e) { /* ignore */ }
	  };

  document.addEventListener('DOMContentLoaded', init);
})();
