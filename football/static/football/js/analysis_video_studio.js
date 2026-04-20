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
    const stage = document.getElementById('vs-stage');
    if (!video || !canvasEl || !stage || !window.fabric) return;

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

    const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

    const fabricCanvas = new fabric.Canvas(canvasEl, { preserveObjectStacking: true, selection: true });
    try { fabricCanvas.freeDrawingBrush.width = 6; } catch (e) { /* ignore */ }
    try { fabricCanvas.freeDrawingBrush.color = '#22d3ee'; } catch (e) { /* ignore */ }

    const history = [];
    const pushHistory = () => {
      try {
        const json = fabricCanvas.toDatalessJSON(['data']);
        history.push(json);
        if (history.length > 40) history.shift();
      } catch (e) { /* ignore */ }
    };
    const restoreJson = (json) => {
      if (!json) return;
      fabricCanvas.loadFromJSON(json, () => {
        fabricCanvas.renderAll();
      });
    };

    const resizeToVideo = () => {
      const rect = video.getBoundingClientRect();
      const w = Math.max(1, Math.round(rect.width));
      const h = Math.max(1, Math.round(rect.height));
      canvasEl.width = w;
      canvasEl.height = h;
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

    const fmtTime = (seconds) => {
      const s = Math.max(0, Number(seconds) || 0);
      const mm = Math.floor(s / 60);
      const ss = Math.floor(s % 60);
      return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
    };

    let tool = 'select';
    let arrowStart = null;
    const setTool = (next) => {
      tool = next;
      const isSelect = tool === 'select';
      const isPen = tool === 'pen';
      fabricCanvas.isDrawingMode = isPen;
      try { fabricCanvas.selection = isSelect; } catch (e) { /* ignore */ }
      Array.from([btnSelect, btnPen, btnArrow, btnText]).forEach((b) => b?.classList.remove('primary'));
      if (tool === 'select') btnSelect?.classList.add('primary');
      if (tool === 'pen') btnPen?.classList.add('primary');
      if (tool === 'arrow') btnArrow?.classList.add('primary');
      if (tool === 'text') btnText?.classList.add('primary');
      setStatus(`Herramienta: ${tool}`);
    };
    setTool('select');

    const strokeColor = () => safeText(colorInput?.value, '#22d3ee');
    const strokeWidth = () => clamp(Number(widthInput?.value || 6), 1, 26);
    colorInput?.addEventListener('change', () => {
      try { fabricCanvas.freeDrawingBrush.color = strokeColor(); } catch (e) { /* ignore */ }
    });
    widthInput?.addEventListener('input', () => {
      try { fabricCanvas.freeDrawingBrush.width = strokeWidth(); } catch (e) { /* ignore */ }
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
        fabricCanvas.add(t);
        pushHistory();
        fabricCanvas.setActiveObject(t);
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
      // Punta simple.
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
      fabricCanvas.add(group);
      pushHistory();
      arrowStart = null;
    });
    fabricCanvas.on('path:created', () => pushHistory());

    btnSelect?.addEventListener('click', () => setTool('select'));
    btnPen?.addEventListener('click', () => setTool('pen'));
    btnArrow?.addEventListener('click', () => setTool('arrow'));
    btnText?.addEventListener('click', () => setTool('text'));

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
      setStatus('Lienzo limpio.');
    });

    const fmtTime = (t) => {
      const v = Math.max(0, Number(t) || 0);
      const m = Math.floor(v / 60);
      const s = v - (m * 60);
      return `${m}:${String(Math.floor(s)).padStart(2, '0')}.${String(Math.round((s % 1) * 10))}`;
    };

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
      btnRecord.textContent = 'Grabar';
      btnExportSeg.disabled = false;
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
          try { recCtx.drawImage(canvasEl, 0, 0, w, h); } catch (e) { /* ignore */ }
        } catch (e) { /* ignore */ }
        if (stopAt != null && (Number(video.currentTime) || 0) >= stopAt) {
          stopRecording();
          return;
        }
        recRaf = window.requestAnimationFrame(draw);
      };

      recActive = true;
      btnRecord.textContent = 'Parar';
      btnExportSeg.disabled = true;
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

    // Shortcuts (Video Analysis Pro)
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
      const rows = (Array.isArray(items) ? items : []).slice(0, 60).map((p) => {
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
            activeProjectId = id;
            if (projectTitleInput) projectTitleInput.value = safeText(found?.title);
            pushHistory();
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
      const payload = { canvas: fabricCanvas.toDatalessJSON(['data']), in: Number(inInput?.value || 0) || 0, out: Number(outInput?.value || 0) || 0 };
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
        const label = `${fmtTime(inS)} → ${fmtTime(outS || inS)}`;
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
            try {
              video.currentTime = Number(found?.in_s) || 0;
            } catch (e) { /* ignore */ }
            pushHistory();
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
      const overlay = fabricCanvas.toDatalessJSON(['data']);
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
        const at = fmtTime(Number(ev?.time_s) || 0);
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
            setStatus(`Timeline → ${fmtTime(seek)}`);
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
        setStatus(`Evento añadido en ${fmtTime(timeS)}.`);
      } catch (e) {
        setStatus('No se pudo añadir evento.', true);
      }
    };
    eventAddBtn?.addEventListener('click', addTimelineEvent);
    eventRefreshBtn?.addEventListener('click', refreshTimeline);
    refreshTimeline();

    pushHistory();
    setStatus('Listo.');
  };

  document.addEventListener('DOMContentLoaded', init);
})();
