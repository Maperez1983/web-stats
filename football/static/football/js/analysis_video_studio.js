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
		    if (!video) return;
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
	    const btnSnap = document.getElementById('vs-snap');
	    const btnDorsalOcr = document.getElementById('vs-dorsal-ocr');
	    const btnFreeze = document.getElementById('vs-freeze');

    const btnSelect = document.getElementById('vs-tool-select');
    const btnPen = document.getElementById('vs-tool-pen');
    const btnArrow = document.getElementById('vs-tool-arrow');
    const btnCurve = document.getElementById('vs-tool-curve');
    const btnText = document.getElementById('vs-tool-text');
    const btnPlayer = document.getElementById('vs-tool-player');
    const btnCallout = document.getElementById('vs-tool-callout');
    const btnSpot = document.getElementById('vs-tool-spot');
    const btnBlur = document.getElementById('vs-tool-blur');
    const btnUndo = document.getElementById('vs-undo');
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
	    const autocutUrl = safeText(document.getElementById('vs-autocut-url')?.value);
	    const dorsalOcrUrl = safeText(document.getElementById('vs-dorsal-ocr-url')?.value);

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
	      enforceTrimPlayback();
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
      if (obj.data.base_sx == null) obj.data.base_sx = Number(obj.scaleX) || 1;
      if (obj.data.base_sy == null) obj.data.base_sy = Number(obj.scaleY) || 1;
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
        if (!number || !name) return null;

        const p = { x: point.x, y: point.y };
        const radius = 22 + Math.round(strokeWidth() / 2);
        const prefsTeam = safeText(prefs?.team, 'home');
        const prefsStyle = safeText(prefs?.style, 'tag');
        const color = teamColor(prefsTeam) || strokeColor();

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

        const tagOffsetX = radius + 10 + (nameW / 2);
        tagRect.set({ left: p.x + tagOffsetX, top: p.y });
        nameText.set({ left: p.x + tagOffsetX, top: p.y + 0.5 });

        const objects = (prefsStyle === 'circle')
          ? [ringOuter, numText]
          : [ringOuter, numText, tagRect, nameText];

        const group = new fabric.Group(objects, { selectable: true });
        group.data = seedLayerDataNow({ kind: 'player_marker', number: String(number), name, team: prefsTeam, style: prefsStyle });
        fabricCanvas.add(group);
        pushHistory();
        try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
        selectedFxId = 0;
        updateLayerPanel();
        renderFxList();
        renderDrawLayers();
        return { number, name };
      };
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

	      Array.from([btnSelect, btnPen, btnArrow, btnCurve, btnText, btnPlayer, btnCallout, btnSpot, btnBlur]).forEach((b) => b?.classList.remove('primary'));
	      if (tool === 'select') btnSelect?.classList.add('primary');
	      if (tool === 'pen') btnPen?.classList.add('primary');
	      if (tool === 'arrow') btnArrow?.classList.add('primary');
	      if (tool === 'curve') btnCurve?.classList.add('primary');
	      if (tool === 'text') btnText?.classList.add('primary');
	      if (tool === 'player') btnPlayer?.classList.add('primary');
	      if (tool === 'callout') btnCallout?.classList.add('primary');
	      if (tool === 'spot') btnSpot?.classList.add('primary');
	      if (tool === 'blur') btnBlur?.classList.add('primary');
        if (tool !== 'player') closePlayerPop();
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
	      if (tool === 'arrow' || tool === 'curve') {
	        arrowStart = fabricCanvas.getPointer(opt.e);
	      }
	      if (tool === 'text') {
	        const p = fabricCanvas.getPointer(opt.e);
	        const t = new fabric.IText('Texto', {
	          left: p.x,
	          top: p.y,
	          fill: strokeColor(),
	          fontSize: 22,
	          fontWeight: '800',
	          shadow: 'rgba(15,23,42,0.65) 0 1px 3px',
	          editable: true,
	        });
	        t.data = seedLayerDataNow();
	        fabricCanvas.add(t);
	        pushHistory();
	        try { fabricCanvas.setActiveObject(t); } catch (e) { /* ignore */ }
	        try { t.enterEditing(); t.selectAll(); } catch (e) { /* ignore */ }
	        selectedFxId = 0;
	        updateLayerPanel();
	        renderFxList();
	        renderDrawLayers();
	      }
	      if (tool === 'player') {
	        const p = fabricCanvas.getPointer(opt.e);
	        openPlayerPopAt({ x: p.x, y: p.y }, { x: opt?.e?.clientX || 0, y: opt?.e?.clientY || 0 });
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
      if ((tool !== 'arrow' && tool !== 'curve') || !arrowStart) return;
      const end = fabricCanvas.getPointer(opt.e);
      const sw = strokeWidth();
      const color = strokeColor();
	      if (tool === 'curve') {
	        const dx = end.x - arrowStart.x;
	        const dy = end.y - arrowStart.y;
	        const dist = Math.max(1, Math.hypot(dx, dy));
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
        const group = new fabric.Group([path, head], { selectable: true });
        group.data = seedLayerDataNow({ kind: 'curve_arrow', anim: 'draw', anim_ms: 850 });
        fabricCanvas.add(group);
      } else {
        const line = new fabric.Line([arrowStart.x, arrowStart.y, end.x, end.y], {
          stroke: color,
          strokeWidth: sw,
          selectable: true,
        });
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
        const group = new fabric.Group([line, head], { selectable: true });
        group.data = seedLayerDataNow({ kind: 'arrow', anim: 'draw', anim_ms: 700 });
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
    fabricCanvas.on('selection:created', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); renderDrawLayers(); });
    fabricCanvas.on('selection:updated', () => { selectedFxId = 0; updateLayerPanel(); renderFxList(); renderDrawLayers(); });
    fabricCanvas.on('selection:cleared', () => { updateLayerPanel(); renderDrawLayers(); });

	    btnSelect?.addEventListener('click', () => setTool('select'));
	    btnPen?.addEventListener('click', () => setTool('pen'));
	    btnArrow?.addEventListener('click', () => setTool('arrow'));
	    btnCurve?.addEventListener('click', () => setTool('curve'));
	    btnText?.addEventListener('click', () => setTool('text'));
	    btnPlayer?.addEventListener('click', () => setTool('player'));
	    btnCallout?.addEventListener('click', () => setTool('callout'));
	    btnSpot?.addEventListener('click', () => setTool('spot'));
	    btnBlur?.addEventListener('click', () => setTool('blur'));

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
          });
        });
      };
      segWire(playerTeamSeg, 'team');
      segWire(playerStyleSeg, 'style');

      playerOkBtn?.addEventListener('click', () => {
        if (!playerPopCanvasPos) return;
        const number = safeText(playerNumberInput?.value, '').trim();
        const name = safeText(playerNameInput?.value, '').trim();
        if (!number || !name) { setStatus('Completa dorsal y nombre.', true); return; }
        const created = createPlayerMarkerAt(playerPopCanvasPos, number, name, playerPrefs);
        if (!created) { setStatus('No se pudo crear marcador.', true); return; }
        pushPlayerRecent(created.number, created.name);
        closePlayerPop();
        setStatus(`Jugador: ${created.number} ${created.name}`);
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
      const group = new fabric.Group(objs, { selectable: true });
      group.data = seedLayerDataNow({ kind: 'template', template: name });
      fabricCanvas.add(group);
      pushHistory();
      try { fabricCanvas.setActiveObject(group); } catch (e) { /* ignore */ }
      selectedFxId = 0;
      updateLayerPanel();
      renderFxList();
      renderDrawLayers();
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
      enforceTrimPlayback();
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
    }, { passive: false });

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
    let recLastProgressAt = 0;
	    let lastExportAssetId = 0;
	    let lastExportShareUrl = '';
	    let lastFailedExport = null;

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
          const vStream = typeof video.captureStream === 'function' ? video.captureStream() : (typeof video.mozCaptureStream === 'function' ? video.mozCaptureStream() : null);
          audioTracks = vStream ? (vStream.getAudioTracks?.() || []) : [];
        } catch (e) { audioTracks = []; }
        if (!audioTracks.length) {
          try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (Ctx) {
              if (!exportAudioCtx) exportAudioCtx = new Ctx();
              try { await exportAudioCtx.resume(); } catch (e) { /* ignore */ }
              if (!exportAudioDest) exportAudioDest = exportAudioCtx.createMediaStreamDestination();
              if (!exportAudioSource) {
                exportAudioSource = exportAudioCtx.createMediaElementSource(video);
                try { exportAudioSource.connect(exportAudioDest); } catch (e) { /* ignore */ }
                try { exportAudioSource.connect(exportAudioCtx.destination); } catch (e) { /* ignore */ }
              }
              audioTracks = exportAudioDest.stream.getAudioTracks?.() || [];
            }
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

	    btnExportServer?.addEventListener('click', async () => {
	      if (!exportServerUrl) {
	        setStatus('No hay endpoint para MP4 server.', true);
	        return;
	      }
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
	      const t = baseTitle ? (coll ? `${baseTitle} · ${coll}` : baseTitle) : `Clip ${fmtTimeShort(start)}-${fmtTimeShort(end)}`;

	      try {
	        btnExportServer.disabled = true;
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
	          return;
	        }
	        const url = String(data.url);
	        const downloadUrl = String(data.download_url || url);
	        lastExportAssetId = Number(data?.id) || lastExportAssetId || 0;
	        lastExportShareUrl = url;
	        try {
	          if (navigator.clipboard?.writeText) {
	            await navigator.clipboard.writeText(downloadUrl);
	            setStatus('MP4 server listo. Link copiado.');
	          } else {
	            setStatus('MP4 server listo. Copia el link.');
	            window.prompt('Copia este enlace:', downloadUrl);
	          }
	        } catch (e) {
	          window.prompt('Copia este enlace:', downloadUrl);
	        }
	        refreshShareLinks();
	      } catch (e) {
	        setStatus('Error exportando MP4 en servidor.', true);
	      } finally {
	        btnExportServer.disabled = false;
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
	        try {
	          if (navigator.clipboard?.writeText) {
	            await navigator.clipboard.writeText(downloadUrl);
	            setStatus('MP4 playlist listo. Link copiado.');
	          } else {
	            setStatus('MP4 playlist listo. Copia el link.');
	            window.prompt('Copia este enlace:', downloadUrl);
	          }
	        } catch (e) {
	          window.prompt('Copia este enlace:', downloadUrl);
	        }
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
		        try {
		          if (navigator.clipboard?.writeText) {
		            await navigator.clipboard.writeText(downloadUrl);
		            setStatus('MP4 timeline listo. Link copiado.');
	          } else {
	            setStatus('MP4 timeline listo. Copia el link.');
	            window.prompt('Copia este enlace:', downloadUrl);
	          }
	        } catch (e) {
	          window.prompt('Copia este enlace:', downloadUrl);
	        }
		        refreshShareLinks();
		      } catch (e) {
		        setJobUi({ show: false, canCancel: false });
		        tlActiveExportJobId = 0;
		        setStatus(e?.message || 'Error exportando MP4 timeline.', true);
		      } finally {
		        tlExportBtn.disabled = false;
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
		    });

		    tlFromSelectionBtn?.addEventListener('click', tlLoadFromSelection);
		    tlClearBtn?.addEventListener('click', tlClear);
		    tlSaveBtn?.addEventListener('click', tlSaveProject);
		    tlLoadBtn?.addEventListener('click', tlLoadProject);
		    tlExportBtn?.addEventListener('click', tlExportMp4);
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
	        const title = safeText(c?.title, `Clip ${id}`);
	        const coll = safeText(c?.collection, '');
	        const inS = Number(c?.in_s) || 0;
	        const outS = Number(c?.out_s) || 0;
	        const tags = Array.isArray(c?.tags) ? c.tags : [];
	        const tagsLabel = tags.length ? ` · ${tags.slice(0, 6).map((t) => `#${safeText(t)}`).join(' ')}` : '';
	        const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS || inS)}`;
	        const checked = selectedClipIds.has(id) ? 'checked' : '';
	        const reviewed = reviewedClipIds.has(id);
	        return `
	          <div class="row" style="${reviewed ? 'opacity:0.86;' : ''}">
	            <div style="display:flex; gap:0.6rem; align-items:flex-start; width:100%;">
                <input type="checkbox" data-vs-clip-select="${id}" ${checked} style="margin-top:0.25rem; width:18px;height:18px;accent-color:#22d3ee; flex:0 0 auto;" />
                <div style="width:76px;height:46px;border-radius:12px;overflow:hidden;background:rgba(2,6,23,0.35);border:1px solid rgba(148,163,184,0.14);flex:0 0 auto;">
                  <img data-vs-clip-thumb="${id}" alt="" style="width:100%;height:100%;object-fit:cover;display:block;" />
                </div>
	              <div style="display:flex; flex-direction:column; gap:0.05rem; min-width:0; flex:1;">
	                <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${title}</strong>
	                <small>${coll ? `${coll} · ` : ''}${label}${tagsLabel}</small>
	              </div>
		            <div style="display:flex; gap:0.35rem; flex-wrap:wrap; justify-content:flex-end;">
		              <button type="button" class="button ${reviewed ? 'primary' : 'ghost'}" data-vs-clip-review="${id}" title="Marcar revisado">${reviewed ? '✓' : '○'}</button>
		              <button type="button" class="button" data-vs-clip-play="${id}">Play</button>
		              <button type="button" class="button" data-vs-clip-load="${id}">Abrir</button>
		              <button type="button" class="button" data-vs-clip-link="${id}" data-vs-clip-view="${safeText(c?.view_url, '')}">Link</button>
		              <button type="button" class="button" data-vs-clip-export-server="${id}" title="Genera MP4 en servidor">MP4</button>
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
	        const start = Number(clip?.in_s) || 0;
	        const end = Number(clip?.out_s) || 0;
	        if (inInput) inInput.value = String(start.toFixed(1));
	        if (outInput) outInput.value = String(end.toFixed(1));
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
	            try {
	              if (navigator.clipboard?.writeText) {
	                await navigator.clipboard.writeText(downloadUrl);
	                setStatus('MP4 listo. Link copiado.');
	              } else {
	                setStatus('MP4 listo. Copia el link.');
	                window.prompt('Copia este enlace:', downloadUrl);
	              }
	            } catch (e) {
	              window.prompt('Copia este enlace:', downloadUrl);
	            }
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
		      if (!clipSaveUrl || !videoId) return;
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
        return;
      }
	      const overlay = { ...fabricCanvas.toDatalessJSON(['data']), fx: { layers: fxState.layers } };
	      try {
	        const clipId = forceNew ? 0 : (activeClipId || 0);
		        const resp = await fetch(clipSaveUrl, {
		          method: 'POST',
		          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
		          credentials: 'same-origin',
		          body: JSON.stringify({ id: clipId, video_id: videoId, title, collection, in_s: inS, out_s: outS, overlay, tags, notes }),
		        });
	        const data = await resp.json().catch(() => ({}));
	        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'error');
	        // Si estamos editando un clip cargado, conserva `activeClipId`. Si estamos creando uno nuevo, no lo dejes activo
	        // para que el siguiente Guardar cree otro (flujo multi-clips).
	        if (!forceNew && clipId) activeClipId = Number(data?.id) || activeClipId;
	        await refreshClips();
	        if (!clipId || forceNew) activeClipId = 0;
	        updateClipUiState();
	        try {
	          const d = new Date();
          const hh = String(d.getHours()).padStart(2, '0');
          const mm = String(d.getMinutes()).padStart(2, '0');
          const ss = String(d.getSeconds()).padStart(2, '0');
          const label = `${fmtTimeShort(inS)} → ${fmtTimeShort(outS)}`;
	          const savedId = Number(data?.id) || activeClipId || 0;
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
      } catch (e) {
        try { if (clipSavedMsg) clipSavedMsg.textContent = 'No se pudo guardar.'; } catch (e2) { /* ignore */ }
        setStatus('No se pudo guardar clip.', true);
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
      for (const obj of fabricCanvas.getObjects()) {
        ensureLayerData(obj);
        const alpha = computeTimedAlpha(obj.data, nowS);
        obj.visible = alpha > 0.001;
        obj.opacity = clamp(alpha, 0, 1);

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
            const head = obj._objects.find((x) => x?.type === 'polygon');
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
