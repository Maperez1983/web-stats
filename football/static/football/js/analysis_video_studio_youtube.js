(function () {
  function byId(id) { return document.getElementById(id); }
  var videoId = Number((byId('vs-video-id') && byId('vs-video-id').value) || 0) || 0;
  var youtubeId = String((byId('vs-youtube-id') && byId('vs-youtube-id').value) || '').trim();
  var initialClipId = Number((byId('vs-initial-clip-id') && byId('vs-initial-clip-id').value) || 0) || 0;
  var clipsUrl = String((byId('vs-clips-url') && byId('vs-clips-url').value) || '').trim();
  var clipSaveUrl = String((byId('vs-clip-save-url') && byId('vs-clip-save-url').value) || '').trim();
  var clipDeleteUrl = String((byId('vs-clip-delete-url') && byId('vs-clip-delete-url').value) || '').trim();
  var assignUrl = String((byId('vs-assign-url') && byId('vs-assign-url').value) || '').trim();
  var sharePlaylistUrl = String((byId('vs-share-playlist-url') && byId('vs-share-playlist-url').value) || '').trim();
  var csrf = '';
  try {
    var inp = document.querySelector('#vs-csrf input[name="csrfmiddlewaretoken"]');
    csrf = inp ? String(inp.value || '') : '';
  } catch (e) { csrf = ''; }

  var btnPlay = byId('vs-play');
  var btnPause = byId('vs-pause');
  var btnMarkIn = byId('vs-mark-in');
  var btnMarkOut = byId('vs-mark-out');
  var btnBack5 = byId('vs-back-5');
  var btnForward5 = byId('vs-forward-5');
  var btnInMinus = byId('vs-in-minus');
  var btnInPlus = byId('vs-in-plus');
  var btnOutMinus = byId('vs-out-minus');
  var btnOutPlus = byId('vs-out-plus');
  var btnDrawToggle = byId('vs-draw-toggle');
  var btnDrawUndo = byId('vs-draw-undo');
  var btnDrawRedo = byId('vs-draw-redo');
  var btnDrawClear = byId('vs-draw-clear');
  var btnAddArrow = byId('vs-add-arrow');
  var btnAddCircle = byId('vs-add-circle');
  var btnAddZone = byId('vs-add-zone');
  var selSpeed = byId('vs-speed');
  var nowEl = byId('vs-now');
  var inLabel = byId('vs-in-label');
  var outLabel = byId('vs-out-label');
  var statusEl = byId('vs-status');
  var stageEl = document.querySelector('.stage');
  var stageInner = byId('vs-youtube-player');
  var effectLayer = byId('vs-effect-layer');
  var drawCanvas = byId('vs-draw-canvas');
  var timelineEl = byId('vs-timeline');

  var inInput = byId('vs-in-s');
  var outInput = byId('vs-out-s');
  var titleInput = byId('vs-clip-title');
  var collectionInput = byId('vs-clip-collection');
  var tagsInput = byId('vs-clip-tags');
  var notesInput = byId('vs-clip-notes');
  var btnSave = byId('vs-clip-save');
  var btnClear = byId('vs-clip-clear');
  var btnRefresh = byId('vs-clip-refresh');
  var clipStatus = byId('vs-clip-status');
  var clipsList = byId('vs-clips');
  var bulkBar = byId('vs-bulk-bar');
  var bulkCount = byId('vs-bulk-count');
  var bulkPlayBtn = byId('vs-bulk-play');
  var bulkShareBtn = byId('vs-bulk-share');
  var bulkClearBtn = byId('vs-bulk-clear');
  var toastEl = byId('vs-toast');
  var filterBtns = document.querySelectorAll('[data-video-filter]');
  var effectBtns = document.querySelectorAll('[data-video-effect]');
  var effectPresetBtns = document.querySelectorAll('[data-effect-preset]');
  var btnEffectClear = byId('vs-effect-clear');
  var effectIntensityInput = byId('vs-effect-intensity');
  var effectSizeInput = byId('vs-effect-size');
  var effectColorInput = byId('vs-effect-color');
  var btnEffectStartNow = byId('vs-effect-start-now');
  var btnEffectEndNow = byId('vs-effect-end-now');
  var effectRangeEl = byId('vs-effect-range');
  var tagPresetBtns = document.querySelectorAll('[data-tags]');
  var templateBtns = document.querySelectorAll('[data-template-title]');
  var assignTeamSelect = byId('vs-assign-team');
  var assignBtn = byId('vs-assign-btn');

  var player = null;
  var tickTimer = 0;
  var latestClips = [];
  var selectedClipIds = {};
  var playlistQueue = [];
  var playlistIndex = -1;
  var drawEnabled = false;
  var isDrawing = false;
  var activeStroke = null;
  var drawState = { version: 1, strokes: [] };
  var effectState = { filter: 'none', layer: 'none', x: 50, y: 50, intensity: 65, size: 18, color: '#facc15', start_s: 0, end_s: 0 };
  var redoStack = [];
  var dirty = false;
  var toastTimer = 0;

  function setText(el, text) { if (el) el.textContent = String(text || ''); }
  function setStatus(text) { setText(statusEl, text || ''); }
  function setClipStatus(text) { setText(clipStatus, text || ''); }
  function showToast(text) {
    if (!toastEl) return;
    toastEl.textContent = String(text || '');
    toastEl.classList.add('is-visible');
    try { if (toastTimer) window.clearTimeout(toastTimer); } catch (e) {}
    toastTimer = window.setTimeout(function () { toastEl.classList.remove('is-visible'); }, 3200);
  }
  function markDirty() {
    dirty = true;
  }
  function markClean() {
    dirty = false;
  }

  function fmtTime(sec) {
    var s = Math.max(0, Number(sec) || 0);
    var m = Math.floor(s / 60);
    var r = Math.floor(s - m * 60);
    return String(m) + ':' + (String(r).padStart ? String(r).padStart(2, '0') : (r < 10 ? ('0' + r) : String(r)));
  }

  function getNow() {
    if (!player) return 0;
    try {
      var t = player.getCurrentTime();
      return Number(t) || 0;
    } catch (e) {
      return 0;
    }
  }

  function setInOutLabels() {
    var inS = Number(inInput && inInput.value ? inInput.value : 0) || 0;
    var outS = Number(outInput && outInput.value ? outInput.value : 0) || 0;
    setText(inLabel, fmtTime(inS));
    setText(outLabel, fmtTime(outS));
  }

  function setIn(sec) {
    if (!inInput) return;
    inInput.value = String(Math.max(0, Math.round((Number(sec) || 0) * 10) / 10));
    setInOutLabels();
    markDirty();
  }
  function setOut(sec) {
    if (!outInput) return;
    outInput.value = String(Math.max(0, Math.round((Number(sec) || 0) * 10) / 10));
    setInOutLabels();
    markDirty();
  }

  function adjustInput(input, delta) {
    if (!input) return;
    var current = Number(input.value || 0) || 0;
    input.value = String(Math.max(0, Math.round((current + Number(delta || 0)) * 10) / 10));
    setInOutLabels();
    markDirty();
  }

  function seekBy(delta) {
    if (!player) return;
    var next = Math.max(0, getNow() + Number(delta || 0));
    try { player.seekTo(next, true); } catch (e) {}
    setText(nowEl, fmtTime(next));
    updatePlayhead(next);
  }

  function parseTags(raw) {
    var s = String(raw || '').trim();
    if (!s) return [];
    var parts = s.split(',');
    var out = [];
    for (var i = 0; i < parts.length; i += 1) {
      var t = String(parts[i] || '').trim();
      if (!t) continue;
      out.push(t.slice(0, 40));
      if (out.length >= 24) break;
    }
    return out;
  }

  function mergeTags(current, added) {
    var seen = {};
    var out = [];
    var all = parseTags(current).concat(parseTags(added));
    for (var i = 0; i < all.length; i += 1) {
      var tag = String(all[i] || '').trim();
      var key = tag.toLowerCase();
      if (!tag || seen[key]) continue;
      seen[key] = true;
      out.push(tag);
      if (out.length >= 24) break;
    }
    return out.join(', ');
  }

  function buildOverlayPayload() {
    return {
      youtubeStudio: {
        version: 1,
        strokes: drawState.strokes || [],
        effects: {
          filter: String(effectState.filter || 'none'),
          layer: String(effectState.layer || 'none'),
          x: Number(effectState.x || 50),
          y: Number(effectState.y || 50),
          intensity: Number(effectState.intensity || 65),
          size: Number(effectState.size || 18),
          color: String(effectState.color || '#facc15'),
          start_s: Number(effectState.start_s || 0),
          end_s: Number(effectState.end_s || 0)
        }
      }
    };
  }

  function loadOverlayPayload(overlay) {
    var payload = overlay && overlay.youtubeStudio && typeof overlay.youtubeStudio === 'object' ? overlay.youtubeStudio : {};
    var effects = payload && payload.effects && typeof payload.effects === 'object' ? payload.effects : {};
    drawState = {
      version: 1,
      strokes: Array.isArray(payload.strokes) ? payload.strokes.slice(0, 120) : []
    };
    effectState = {
      filter: String(effects.filter || 'none'),
      layer: String(effects.layer || 'none'),
      x: Number(effects.x || 50) || 50,
      y: Number(effects.y || 50) || 50,
      intensity: Number(effects.intensity || 65) || 65,
      size: Number(effects.size || 18) || 18,
      color: String(effects.color || '#facc15'),
      start_s: Number(effects.start_s || 0) || 0,
      end_s: Number(effects.end_s || 0) || 0
    };
    applyEffects();
    syncEffectControls();
    renderDrawing();
    redoStack = [];
    markClean();
  }

  function applyEffects() {
    var intensity = Math.max(0, Math.min(100, Number(effectState.intensity || 0)));
    var size = Math.max(8, Math.min(48, Number(effectState.size || 18)));
    var color = String(effectState.color || '#facc15');
    var alpha = Math.max(0.2, Math.min(0.88, 0.28 + (intensity / 130)));
    var soft = colorToRgba(color, Math.max(0.08, Math.min(0.32, intensity / 330)));
    var border = colorToRgba(color, Math.max(0.32, Math.min(0.74, intensity / 135)));
    if (stageInner) {
      stageInner.classList.remove('fx-contrast', 'fx-bw', 'fx-dim', 'fx-sharp');
      var filter = String(effectState.filter || 'none');
      stageInner.style.setProperty('--fx-intensity', String(intensity));
      if (filter !== 'none') stageInner.classList.add('fx-' + filter);
    }
    if (effectLayer) {
      effectLayer.classList.remove('is-visible', 'fx-spotlight', 'fx-focus-lane', 'fx-pause');
      var layer = String(effectState.layer || 'none');
      if (layer !== 'none') {
        effectLayer.classList.add('is-visible', 'fx-' + layer);
        effectLayer.style.setProperty('--fx-x', String(Math.max(0, Math.min(100, Number(effectState.x || 50)))) + '%');
        effectLayer.style.setProperty('--fx-y', String(Math.max(0, Math.min(100, Number(effectState.y || 50)))) + '%');
        effectLayer.style.setProperty('--fx-radius', String(size) + '%');
        effectLayer.style.setProperty('--fx-alpha', String(alpha));
        effectLayer.style.setProperty('--fx-color-soft', soft);
        effectLayer.style.setProperty('--fx-color-border', border);
        effectLayer.style.setProperty('--fx-color-text', color);
        effectLayer.style.setProperty('--fx-lane-left', String(Math.max(4, Math.min(80, 50 - size))) + '%');
        effectLayer.style.setProperty('--fx-lane-right', String(Math.max(20, Math.min(96, 50 + size))) + '%');
      }
    }
    updateEffectRangeLabel();
  }

  function colorToRgba(hex, alpha) {
    var raw = String(hex || '#facc15').replace('#', '').trim();
    if (raw.length === 3) raw = raw.split('').map(function (ch) { return ch + ch; }).join('');
    var n = parseInt(raw, 16);
    if (!Number.isFinite(n)) n = 0xfacc15;
    var r = (n >> 16) & 255;
    var g = (n >> 8) & 255;
    var b = n & 255;
    return 'rgba(' + r + ',' + g + ',' + b + ',' + String(alpha) + ')';
  }

  function syncEffectControls() {
    if (effectIntensityInput) effectIntensityInput.value = String(Math.max(0, Math.min(100, Number(effectState.intensity || 65))));
    if (effectSizeInput) effectSizeInput.value = String(Math.max(8, Math.min(48, Number(effectState.size || 18))));
    if (effectColorInput) effectColorInput.value = /^#[0-9a-fA-F]{6}$/.test(String(effectState.color || '')) ? String(effectState.color) : '#facc15';
    updateEffectRangeLabel();
  }

  function updateEffectRangeLabel() {
    if (!effectRangeEl) return;
    var a = Number(effectState.start_s || 0) || 0;
    var b = Number(effectState.end_s || 0) || 0;
    effectRangeEl.textContent = (a || b) ? (fmtTime(a) + ' - ' + (b ? fmtTime(b) : 'fin')) : 'todo';
  }

  function effectIsActiveAt(timeS) {
    var start = Number(effectState.start_s || 0) || 0;
    var end = Number(effectState.end_s || 0) || 0;
    if (!start && !end) return true;
    var t = Number(timeS || 0) || 0;
    if (start && t < start) return false;
    if (end && t > end) return false;
    return true;
  }

  function syncEffectVisibility(now) {
    if (!effectLayer) return;
    var active = String(effectState.layer || 'none') !== 'none' && effectIsActiveAt(now);
    effectLayer.classList.toggle('is-visible', active);
  }

  function setVideoFilter(filter) {
    effectState.filter = String(filter || 'none');
    applyEffects();
    markDirty();
    setStatus(effectState.filter === 'none' ? 'Filtro quitado.' : 'Filtro aplicado. Guarda el clip para conservarlo.');
  }

  function setVideoEffect(effect) {
    effectState.layer = String(effect || 'none');
    if (effectState.layer === 'spotlight') {
      effectState.x = 50;
      effectState.y = 50;
    }
    applyEffects();
    markDirty();
    setStatus(effectState.layer === 'none' ? 'Efecto quitado.' : 'Efecto aplicado. Guarda el clip para conservarlo.');
  }

  function clearEffects() {
    effectState = { filter: 'none', layer: 'none', x: 50, y: 50, intensity: 65, size: 18, color: '#facc15', start_s: 0, end_s: 0 };
    applyEffects();
    syncEffectControls();
    markDirty();
    setStatus('Efectos quitados. Guarda el clip para conservar el cambio.');
  }

  function applyEffectPreset(kind) {
    var k = String(kind || '').trim();
    if (k === 'defensive') {
      effectState.filter = 'dim';
      effectState.layer = 'focus-lane';
      effectState.intensity = 72;
      effectState.size = 22;
      effectState.color = '#38bdf8';
    } else if (k === 'free-space') {
      effectState.filter = 'contrast';
      effectState.layer = 'spotlight';
      effectState.intensity = 68;
      effectState.size = 24;
      effectState.color = '#facc15';
      effectState.x = 58;
      effectState.y = 42;
    } else if (k === 'key-player') {
      effectState.filter = 'sharp';
      effectState.layer = 'spotlight';
      effectState.intensity = 82;
      effectState.size = 15;
      effectState.color = '#fb7185';
    }
    applyEffects();
    syncEffectControls();
    markDirty();
    setStatus('Preset aplicado. Ajusta posición/tamaño y guarda el clip.');
  }

  function resizeCanvas() {
    if (!drawCanvas || !stageEl) return;
    var rect = stageEl.getBoundingClientRect();
    var dpr = Math.max(1, window.devicePixelRatio || 1);
    var w = Math.max(1, Math.round(rect.width));
    var h = Math.max(1, Math.round(rect.height));
    if (drawCanvas.width !== Math.round(w * dpr) || drawCanvas.height !== Math.round(h * dpr)) {
      drawCanvas.width = Math.round(w * dpr);
      drawCanvas.height = Math.round(h * dpr);
      drawCanvas.style.width = w + 'px';
      drawCanvas.style.height = h + 'px';
    }
    renderDrawing();
  }

  function canvasPoint(ev) {
    if (!drawCanvas) return { x: 0, y: 0 };
    var rect = drawCanvas.getBoundingClientRect();
    var x = rect.width ? (Number(ev.clientX || 0) - rect.left) / rect.width : 0;
    var y = rect.height ? (Number(ev.clientY || 0) - rect.top) / rect.height : 0;
    return { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) };
  }

  function drawStroke(ctx, stroke, width, height) {
    var type = String(stroke && stroke.type ? stroke.type : 'free');
    if (type === 'circle') {
      ctx.save();
      ctx.strokeStyle = String(stroke.color || '#fde047');
      ctx.lineWidth = Math.max(2, Number(stroke.width || 4)) * Math.max(1, window.devicePixelRatio || 1);
      ctx.beginPath();
      ctx.arc(Number(stroke.x || 0.5) * width, Number(stroke.y || 0.5) * height, Number(stroke.r || 0.12) * Math.min(width, height), 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
      return;
    }
    if (type === 'zone') {
      ctx.save();
      ctx.strokeStyle = String(stroke.color || '#38bdf8');
      ctx.fillStyle = String(stroke.fill || 'rgba(56,189,248,0.16)');
      ctx.lineWidth = Math.max(2, Number(stroke.width || 3)) * Math.max(1, window.devicePixelRatio || 1);
      var zx = Number(stroke.x || 0.3) * width;
      var zy = Number(stroke.y || 0.28) * height;
      var zw = Number(stroke.w || 0.4) * width;
      var zh = Number(stroke.h || 0.28) * height;
      ctx.fillRect(zx, zy, zw, zh);
      ctx.strokeRect(zx, zy, zw, zh);
      ctx.restore();
      return;
    }
    if (type === 'arrow') {
      ctx.save();
      ctx.strokeStyle = String(stroke.color || '#fde047');
      ctx.fillStyle = String(stroke.color || '#fde047');
      ctx.lineWidth = Math.max(2, Number(stroke.width || 5)) * Math.max(1, window.devicePixelRatio || 1);
      var x1 = Number(stroke.x1 || 0.28) * width;
      var y1 = Number(stroke.y1 || 0.5) * height;
      var x2 = Number(stroke.x2 || 0.72) * width;
      var y2 = Number(stroke.y2 || 0.5) * height;
      var angle = Math.atan2(y2 - y1, x2 - x1);
      var head = 18 * Math.max(1, window.devicePixelRatio || 1);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - head * Math.cos(angle - Math.PI / 6), y2 - head * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(x2 - head * Math.cos(angle + Math.PI / 6), y2 - head * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fill();
      ctx.restore();
      return;
    }
    var pts = stroke && Array.isArray(stroke.points) ? stroke.points : [];
    if (pts.length < 1) return;
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = String(stroke.color || '#fde047');
    ctx.lineWidth = Math.max(2, Number(stroke.width || 4)) * Math.max(1, window.devicePixelRatio || 1);
    ctx.beginPath();
    ctx.moveTo(Number(pts[0].x || 0) * width, Number(pts[0].y || 0) * height);
    for (var i = 1; i < pts.length; i += 1) {
      ctx.lineTo(Number(pts[i].x || 0) * width, Number(pts[i].y || 0) * height);
    }
    ctx.stroke();
    ctx.restore();
  }

  function renderDrawing() {
    if (!drawCanvas) return;
    var ctx = drawCanvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    var strokes = Array.isArray(drawState.strokes) ? drawState.strokes : [];
    for (var i = 0; i < strokes.length; i += 1) {
      drawStroke(ctx, strokes[i], drawCanvas.width, drawCanvas.height);
    }
  }

  function pushHistory() {
    redoStack = [];
    markDirty();
  }

  function setDrawing(on) {
    drawEnabled = Boolean(on);
    if (stageEl) stageEl.classList.toggle('is-drawing', drawEnabled);
    if (btnDrawToggle) btnDrawToggle.textContent = drawEnabled ? 'Dibujando' : 'Dibujar';
    if (drawEnabled) {
      try { player && player.pauseVideo(); } catch (e) {}
      setStatus('Dibujo activo. Traza encima del vídeo y guarda el clip.');
      resizeCanvas();
    }
  }

  function clearDrawing() {
    if (drawState.strokes && drawState.strokes.length) pushHistory();
    drawState = { version: 1, strokes: [] };
    renderDrawing();
    setStatus('Dibujo limpiado. Guarda el clip para conservar el cambio.');
  }

  function addShape(shape) {
    pushHistory();
    drawState.strokes.push(shape);
    if (drawState.strokes.length > 120) drawState.strokes.shift();
    renderDrawing();
    setStatus('Elemento añadido. Guarda el clip para conservar la telestración.');
  }

  function undoDrawing() {
    if (!drawState.strokes || !drawState.strokes.length) return;
    redoStack.push(drawState.strokes.pop());
    renderDrawing();
    markDirty();
    setStatus('Undo aplicado. Guarda el clip para conservar el cambio.');
  }

  function redoDrawing() {
    if (!redoStack.length) return;
    drawState.strokes.push(redoStack.pop());
    renderDrawing();
    markDirty();
    setStatus('Redo aplicado. Guarda el clip para conservar el cambio.');
  }

  function jsonPost(url, payload) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload || {})
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        return { ok: resp.ok, data: data };
      });
    });
  }

  function initAssign() {
    if (!assignUrl || !videoId || !assignTeamSelect || !assignBtn) return;
    assignBtn.addEventListener('click', function () {
      var targetTeamId = Number(assignTeamSelect.value || 0) || 0;
      if (!targetTeamId) {
        setStatus('Selecciona un equipo para asignar el vídeo.');
        return;
      }
      assignBtn.disabled = true;
      jsonPost(assignUrl, { video_id: videoId, team_id: targetTeamId })
        .then(function (res) {
          if (!res || !res.ok || !res.data || !res.data.ok) throw new Error((res.data && res.data.error) ? res.data.error : 'No se pudo asignar.');
          setStatus('Asignado. Recargando…');
          window.location.reload();
        })
        .catch(function (e) { setStatus((e && e.message) ? e.message : 'No se pudo asignar.'); })
        .finally(function () { assignBtn.disabled = false; });
    });
  }

  function loadClips() {
    if (!clipsUrl || !videoId) return Promise.resolve([]);
    var url = new URL(clipsUrl, window.location.href);
    url.searchParams.set('video_id', String(videoId));
    return fetch(url.toString(), { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (resp) {
        return resp.json().catch(function () { return {}; }).then(function (data) {
          if (!resp.ok || !data || !data.ok) throw new Error((data && data.error) ? data.error : 'No se pudo cargar.');
          return Array.isArray(data.items) ? data.items : [];
        });
      });
  }

  function renderClips(items) {
    if (!clipsList) return;
    var clips = Array.isArray(items) ? items : [];
    latestClips = clips;
    renderTimeline(clips);
    if (!clips.length) {
      clipsList.innerHTML = '<div class="hint">No hay clips todavía.</div>';
      return;
    }
    var html = '';
    for (var i = 0; i < clips.length; i += 1) {
      var c = clips[i] || {};
      var title = String(c.title || '').trim() || ('Clip ' + String(c.id || ''));
      var inS = Number(c.in_s || 0) || 0;
      var outS = Number(c.out_s || 0) || 0;
      var meta = fmtTime(inS) + ' → ' + (outS ? fmtTime(outS) : '…');
      var viewUrl = String(c.view_url || '').trim();
      var thumbUrl = String(c.thumbnail_url || '').trim() || (youtubeId ? ('https://img.youtube.com/vi/' + encodeURIComponent(youtubeId) + '/mqdefault.jpg') : '');
      var collection = String(c.collection || '').trim();
      var tags = Array.isArray(c.tags) ? c.tags : [];
      var tagsHtml = '';
      for (var ti = 0; ti < Math.min(tags.length, 5); ti += 1) {
        tagsHtml += '<span class="clip-tag">' + escapeHtml(tags[ti]) + '</span>';
      }
      html += ''
        + '<div class="row' + (selectedClipIds[String(c.id || '')] ? ' is-selected' : '') + '" data-clip-row="' + String(c.id || '') + '">'
        + '  <input type="checkbox" class="clip-check" data-clip-select="' + String(c.id || '') + '"' + (selectedClipIds[String(c.id || '')] ? ' checked' : '') + ' />'
        + (thumbUrl ? ('  <img class="clip-thumb" src="' + escapeAttr(thumbUrl) + '" alt="" loading="lazy" />') : '')
        + '  <div style="display:flex; flex-direction:column; gap:0.15rem; min-width:0; flex:1 1 auto;">'
        + '    <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">' + escapeHtml(title) + '</strong>'
        + '    <small>' + escapeHtml(meta + (collection ? (' · ' + collection) : '')) + '</small>'
        + (tagsHtml ? ('    <span class="clip-tags">' + tagsHtml + '</span>') : '')
        + '  </div>'
        + '  <div style="display:flex; gap:0.35rem; flex-wrap:wrap; justify-content:flex-end;">'
        + '    <button type="button" class="button ghost" data-clip-jump="' + String(c.id || '') + '">Ir</button>'
        + (viewUrl ? ('<a class="button ghost" href="' + escapeAttr(viewUrl) + '">Ver</a>') : '')
        + '    <button type="button" class="button ghost" data-clip-edit="' + String(c.id || '') + '">Editar</button>'
        + '    <button type="button" class="button ghost" data-clip-del="' + String(c.id || '') + '">Borrar</button>'
        + '  </div>'
        + '</div>';
    }
    clipsList.innerHTML = html;
    bindSelectionControls();

    var jumpBtns = clipsList.querySelectorAll('[data-clip-jump]');
    for (var j = 0; j < jumpBtns.length; j += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var cid = Number(btn.getAttribute('data-clip-jump') || 0) || 0;
          var clip = findClipById(clips, cid);
          if (!clip) return;
          jumpToClip(clip);
        });
      })(jumpBtns[j]);
    }
    var editBtns = clipsList.querySelectorAll('[data-clip-edit]');
    for (var k = 0; k < editBtns.length; k += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var cid = Number(btn.getAttribute('data-clip-edit') || 0) || 0;
          var clip = findClipById(clips, cid);
          if (!clip) return;
          fillFormFromClip(clip);
        });
      })(editBtns[k]);
    }
    var delBtns = clipsList.querySelectorAll('[data-clip-del]');
    for (var d = 0; d < delBtns.length; d += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var cid = Number(btn.getAttribute('data-clip-del') || 0) || 0;
          if (!cid) return;
          if (!window.confirm('¿Borrar este clip?')) return;
          deleteClip(cid);
        });
      })(delBtns[d]);
    }

    if (initialClipId) {
      var initial = findClipById(clips, initialClipId);
      if (initial) {
        fillFormFromClip(initial);
        jumpToClip(initial);
      }
      initialClipId = 0;
    }
  }

  function bindSelectionControls() {
    if (!clipsList) return;
    var checks = clipsList.querySelectorAll('[data-clip-select]');
    for (var i = 0; i < checks.length; i += 1) {
      (function (chk) {
        chk.addEventListener('change', function () {
          var cid = String(chk.getAttribute('data-clip-select') || '');
          if (!cid) return;
          if (chk.checked) selectedClipIds[cid] = true;
          else delete selectedClipIds[cid];
          updateBulkBar();
          var row = clipsList.querySelector('[data-clip-row="' + cid + '"]');
          if (row) row.classList.toggle('is-selected', Boolean(selectedClipIds[cid]));
        });
      })(checks[i]);
    }
    updateBulkBar();
  }

  function selectedClips() {
    var out = [];
    for (var i = 0; i < latestClips.length; i += 1) {
      var c = latestClips[i] || {};
      if (selectedClipIds[String(c.id || '')]) out.push(c);
    }
    out.sort(function (a, b) {
      return (Number(a.in_s || 0) - Number(b.in_s || 0)) || (Number(a.id || 0) - Number(b.id || 0));
    });
    return out;
  }

  function updateBulkBar() {
    var count = selectedClips().length;
    if (bulkBar) bulkBar.classList.toggle('is-visible', count > 0);
    if (bulkCount) bulkCount.textContent = String(count) + ' seleccionados';
  }

  function clearSelection() {
    selectedClipIds = {};
    renderClips(latestClips);
  }

  function playSelected() {
    playlistQueue = selectedClips();
    if (!playlistQueue.length) {
      showToast('Selecciona al menos un clip.');
      return;
    }
    playlistIndex = 0;
    jumpToClip(playlistQueue[playlistIndex]);
    showToast('Reproduciendo playlist seleccionada.');
  }

  function playNextInQueue() {
    if (!playlistQueue.length || playlistIndex < 0) return false;
    playlistIndex += 1;
    if (playlistIndex >= playlistQueue.length) {
      playlistQueue = [];
      playlistIndex = -1;
      setStatus('Fin de playlist.');
      return false;
    }
    jumpToClip(playlistQueue[playlistIndex]);
    return true;
  }

  function shareSelectedPlaylist() {
    var clips = selectedClips();
    if (!sharePlaylistUrl) {
      showToast('No hay endpoint de playlist configurado.');
      return;
    }
    if (!clips.length) {
      showToast('Selecciona al menos un clip.');
      return;
    }
    if (bulkShareBtn) bulkShareBtn.disabled = true;
    jsonPost(sharePlaylistUrl, { clip_ids: clips.map(function (c) { return Number(c.id || 0); }).filter(Boolean), valid_days: 14 })
      .then(function (r) {
        if (!r.ok || !r.data || !r.data.ok) throw new Error((r.data && (r.data.error || r.data.message)) ? (r.data.error || r.data.message) : 'No se pudo compartir.');
        var url = String(r.data.url || '');
        if (url && navigator.clipboard && navigator.clipboard.writeText) {
          return navigator.clipboard.writeText(url).catch(function () {}).then(function () {
            showToast('Playlist creada y enlace copiado.');
          });
        }
        showToast(url ? ('Playlist creada: ' + url) : 'Playlist creada.');
      })
      .catch(function (e) {
        showToast((e && e.message) ? e.message : 'No se pudo compartir la playlist.');
      })
      .finally(function () {
        if (bulkShareBtn) bulkShareBtn.disabled = false;
      });
  }

  function renderTimeline(clips) {
    if (!timelineEl) return;
    var list = Array.isArray(clips) ? clips : [];
    if (!list.length) {
      timelineEl.innerHTML = '<div class="timeline-empty">Sin clips en timeline</div>';
      return;
    }
    var duration = 0;
    try { duration = player && player.getDuration ? Number(player.getDuration() || 0) : 0; } catch (e) { duration = 0; }
    for (var i = 0; i < list.length; i += 1) {
      duration = Math.max(duration, Number(list[i].out_s || 0) || 0, Number(list[i].in_s || 0) || 0);
    }
    duration = Math.max(1, duration);
    var html = '<div class="timeline-playhead" id="vs-timeline-playhead" style="left:0%;"></div>';
    for (var c = 0; c < list.length; c += 1) {
      var clip = list[c] || {};
      var start = Math.max(0, Number(clip.in_s || 0) || 0);
      var end = Math.max(start + 0.5, Number(clip.out_s || 0) || (start + 5));
      var left = Math.max(0, Math.min(99, (start / duration) * 100));
      var width = Math.max(1.3, Math.min(100 - left, ((end - start) / duration) * 100));
      html += '<button type="button" class="timeline-clip" data-timeline-clip="' + String(clip.id || '') + '" title="' + escapeAttr(String(clip.title || 'Clip')) + '" style="left:' + String(left) + '%; width:' + String(width) + '%;"></button>';
    }
    timelineEl.innerHTML = html;
    var markers = timelineEl.querySelectorAll('[data-timeline-clip]');
    for (var m = 0; m < markers.length; m += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var cid = Number(btn.getAttribute('data-timeline-clip') || 0) || 0;
          var clip = findClipById(latestClips, cid);
          if (clip) {
            fillFormFromClip(clip);
            jumpToClip(clip);
          }
        });
      })(markers[m]);
    }
    updatePlayhead(getNow());
  }

  function updatePlayhead(now) {
    if (!timelineEl) return;
    var playhead = byId('vs-timeline-playhead');
    if (!playhead) return;
    var duration = 0;
    try { duration = player && player.getDuration ? Number(player.getDuration() || 0) : 0; } catch (e) { duration = 0; }
    for (var i = 0; i < latestClips.length; i += 1) {
      duration = Math.max(duration, Number(latestClips[i].out_s || 0) || 0);
    }
    duration = Math.max(1, duration);
    var pct = Math.max(0, Math.min(100, (Number(now || 0) / duration) * 100));
    playhead.style.left = String(pct) + '%';
  }

  function findClipById(clips, id) {
    for (var i = 0; i < clips.length; i += 1) {
      if (Number(clips[i] && clips[i].id) === Number(id)) return clips[i];
    }
    return null;
  }

  function fillFormFromClip(c) {
    if (!c) return;
    try { if (titleInput) titleInput.value = String(c.title || '').trim(); } catch (e) {}
    try { if (collectionInput) collectionInput.value = String(c.collection || '').trim(); } catch (e) {}
    try { if (notesInput) notesInput.value = String(c.notes || '').trim(); } catch (e) {}
    try {
      var tags = Array.isArray(c.tags) ? c.tags : [];
      if (tagsInput) tagsInput.value = tags.join(', ');
    } catch (e2) {}
    setIn(Number(c.in_s || 0) || 0);
    setOut(Number(c.out_s || 0) || 0);
    try { clipsList && clipsList.setAttribute('data-edit-id', String(c.id || '')); } catch (e3) {}
    loadOverlayPayload(c.overlay || {});
    setClipStatus('Editando clip #' + String(c.id || ''));
  }

  function clearForm() {
    try { if (titleInput) titleInput.value = ''; } catch (e) {}
    try { if (collectionInput) collectionInput.value = ''; } catch (e) {}
    try { if (notesInput) notesInput.value = ''; } catch (e) {}
    try { if (tagsInput) tagsInput.value = ''; } catch (e) {}
    setIn(0); setOut(0);
    clearDrawing();
    clearEffects();
    try { clipsList && clipsList.removeAttribute('data-edit-id'); } catch (e2) {}
    setClipStatus('');
  }

  function jumpToClip(c) {
    if (!player || !c) return;
    var start = Number(c.in_s || 0) || 0;
    try {
      player.seekTo(Math.max(0, start), true);
    } catch (e) {}
    try { player.playVideo(); } catch (e2) {}
    setStatus('Reproduciendo clip…');
    var out = Number(c.out_s || 0) || 0;
    if (out && out > start) {
      stopAt(out);
    }
  }

  var stopAtTimer = 0;
  function stopAt(outSec) {
    try { if (stopAtTimer) window.clearInterval(stopAtTimer); } catch (e) {}
    stopAtTimer = window.setInterval(function () {
      if (!player) return;
      var now = getNow();
      if (now >= outSec - 0.05) {
        try { player.pauseVideo(); } catch (e2) {}
        try { window.clearInterval(stopAtTimer); } catch (e3) {}
        stopAtTimer = 0;
        setStatus('Fin de clip.');
        playNextInQueue();
      }
    }, 80);
  }

  function deleteClip(id) {
    if (!clipDeleteUrl) return;
    if (!id) return;
    setClipStatus('Borrando…');
    if (btnSave) btnSave.disabled = true;
    return jsonPost(clipDeleteUrl, { id: id })
      .then(function (r) {
        if (!r.ok || !r.data || !r.data.ok) throw new Error((r.data && r.data.error) ? r.data.error : 'No se pudo borrar.');
        clearForm();
        return refreshClips();
      })
      .catch(function (e) {
        setClipStatus(String((e && e.message) || 'Error borrando.'));
      })
      .finally(function () {
        if (btnSave) btnSave.disabled = false;
      });
  }

  function refreshClips() {
    setClipStatus('');
    return loadClips()
      .then(function (items) { renderClips(items); return items; })
      .catch(function (e) {
        var msg = String((e && e.message) || 'No se pudo cargar.');
        if (clipsList) clipsList.innerHTML = '<div class="hint">' + escapeHtml(msg) + '</div>';
      });
  }

  function saveClip() {
    if (!clipSaveUrl || !videoId) return;
    var title = String(titleInput && titleInput.value ? titleInput.value : '').trim();
    var collection = String(collectionInput && collectionInput.value ? collectionInput.value : '').trim();
    var notes = String(notesInput && notesInput.value ? notesInput.value : '').trim();
    var tags = parseTags(tagsInput && tagsInput.value ? tagsInput.value : '');
    var inS = Number(inInput && inInput.value ? inInput.value : 0) || 0;
    var outS = Number(outInput && outInput.value ? outInput.value : 0) || 0;
    if (outS && outS < inS) { var tmp = inS; inS = outS; outS = tmp; }
    var editId = 0;
    try { editId = Number(clipsList && clipsList.getAttribute('data-edit-id') ? clipsList.getAttribute('data-edit-id') : 0) || 0; } catch (e) { editId = 0; }

    if (!title) title = 'Clip';

    setClipStatus('Guardando…');
    if (btnSave) btnSave.disabled = true;
    return jsonPost(clipSaveUrl, {
      id: editId || undefined,
      video_id: videoId,
      title: title,
      collection: collection,
      in_s: inS,
      out_s: outS,
      tags: tags,
      notes: notes,
      overlay: buildOverlayPayload()
    }).then(function (r) {
      if (!r.ok || !r.data || !r.data.ok) throw new Error((r.data && r.data.error) ? r.data.error : 'No se pudo guardar.');
      var savedId = Number(r.data.id || 0) || 0;
      setClipStatus('Clip guardado · #' + String(savedId) + ' · ' + fmtTime(inS) + (outS ? ('-' + fmtTime(outS)) : ''));
      showToast('Clip guardado.');
      markClean();
      try { clipsList && clipsList.setAttribute('data-edit-id', String(savedId)); } catch (e2) {}
      return refreshClips();
    }).catch(function (e) {
      setClipStatus(String((e && e.message) || 'Error guardando.'));
    }).finally(function () {
      if (btnSave) btnSave.disabled = false;
    });
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, '&quot;');
  }

  function tick() {
    if (!player) return;
    var now = getNow();
    setText(nowEl, fmtTime(now));
    updatePlayhead(now);
    syncEffectVisibility(now);
  }

  function startTicker() {
    try { if (tickTimer) window.clearInterval(tickTimer); } catch (e) {}
    tickTimer = window.setInterval(tick, 250);
  }

  function setPlaying(isPlaying) {
    if (btnPlay) btnPlay.hidden = isPlaying;
    if (btnPause) btnPause.hidden = !isPlaying;
  }

  function loadYouTubeApi() {
    return new Promise(function (resolve) {
      if (window.YT && window.YT.Player) { resolve(); return; }
      var tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      tag.async = true;
      var first = document.getElementsByTagName('script')[0];
      if (first && first.parentNode) first.parentNode.insertBefore(tag, first);
      else document.head.appendChild(tag);
      window.onYouTubeIframeAPIReady = function () { resolve(); };
    });
  }

  function initPlayer() {
    if (!youtubeId) { setStatus('Falta youtube_id.'); return; }
    loadYouTubeApi().then(function () {
      try {
        player = new window.YT.Player('vs-youtube-player', {
          videoId: youtubeId,
          playerVars: {
            rel: 0,
            modestbranding: 1,
            playsinline: 1
          },
          events: {
            onReady: function () {
              setStatus('Listo.');
              startTicker();
              setInOutLabels();
              refreshClips();
            },
            onStateChange: function (ev) {
              var st = Number(ev && ev.data) || 0;
              // 1 playing, 2 paused, 0 ended
              if (st === 1) setPlaying(true);
              else if (st === 2 || st === 0) setPlaying(false);
            }
          }
        });
      } catch (e) {
        setStatus('No se pudo inicializar el player.');
      }
    });
  }

  if (btnPlay) btnPlay.addEventListener('click', function () {
    if (!player) return;
    try { player.playVideo(); } catch (e) {}
  });
  if (btnPause) btnPause.addEventListener('click', function () {
    if (!player) return;
    try { player.pauseVideo(); } catch (e) {}
  });
  if (selSpeed) selSpeed.addEventListener('change', function () {
    if (!player) return;
    var v = Number(selSpeed.value || 1) || 1;
    try { player.setPlaybackRate(v); } catch (e) {}
  });
  if (btnMarkIn) btnMarkIn.addEventListener('click', function () {
    setIn(getNow());
  });
  if (btnMarkOut) btnMarkOut.addEventListener('click', function () {
    setOut(getNow());
  });
  if (btnBack5) btnBack5.addEventListener('click', function () { seekBy(-5); });
  if (btnForward5) btnForward5.addEventListener('click', function () { seekBy(5); });
  if (btnInMinus) btnInMinus.addEventListener('click', function () { adjustInput(inInput, -1); });
  if (btnInPlus) btnInPlus.addEventListener('click', function () { adjustInput(inInput, 1); });
  if (btnOutMinus) btnOutMinus.addEventListener('click', function () { adjustInput(outInput, -1); });
  if (btnOutPlus) btnOutPlus.addEventListener('click', function () { adjustInput(outInput, 1); });
  if (btnDrawToggle) btnDrawToggle.addEventListener('click', function () { setDrawing(!drawEnabled); });
  if (btnDrawUndo) btnDrawUndo.addEventListener('click', undoDrawing);
  if (btnDrawRedo) btnDrawRedo.addEventListener('click', redoDrawing);
  if (btnDrawClear) btnDrawClear.addEventListener('click', clearDrawing);
  if (btnAddArrow) btnAddArrow.addEventListener('click', function () {
    addShape({ type: 'arrow', color: '#fde047', width: 5, x1: 0.25, y1: 0.54, x2: 0.72, y2: 0.42 });
  });
  if (btnAddCircle) btnAddCircle.addEventListener('click', function () {
    addShape({ type: 'circle', color: '#fb7185', width: 4, x: 0.5, y: 0.5, r: 0.14 });
  });
  if (btnAddZone) btnAddZone.addEventListener('click', function () {
    addShape({ type: 'zone', color: '#38bdf8', fill: 'rgba(56,189,248,0.16)', width: 3, x: 0.32, y: 0.32, w: 0.36, h: 0.28 });
  });
  if (btnEffectClear) btnEffectClear.addEventListener('click', clearEffects);
  if (effectIntensityInput) effectIntensityInput.addEventListener('input', function () {
    effectState.intensity = Number(effectIntensityInput.value || 65) || 65;
    applyEffects();
    markDirty();
  });
  if (effectSizeInput) effectSizeInput.addEventListener('input', function () {
    effectState.size = Number(effectSizeInput.value || 18) || 18;
    applyEffects();
    markDirty();
  });
  if (effectColorInput) effectColorInput.addEventListener('input', function () {
    effectState.color = String(effectColorInput.value || '#facc15');
    applyEffects();
    markDirty();
  });
  if (btnEffectStartNow) btnEffectStartNow.addEventListener('click', function () {
    effectState.start_s = Math.max(0, Math.round(getNow() * 10) / 10);
    if (effectState.end_s && effectState.end_s < effectState.start_s) effectState.end_s = 0;
    updateEffectRangeLabel();
    markDirty();
    setStatus('FX IN marcado. Guarda el clip para conservarlo.');
  });
  if (btnEffectEndNow) btnEffectEndNow.addEventListener('click', function () {
    effectState.end_s = Math.max(0, Math.round(getNow() * 10) / 10);
    if (effectState.start_s && effectState.end_s < effectState.start_s) {
      var tmpFx = effectState.start_s;
      effectState.start_s = effectState.end_s;
      effectState.end_s = tmpFx;
    }
    updateEffectRangeLabel();
    markDirty();
    setStatus('FX OUT marcado. Guarda el clip para conservarlo.');
  });
  if (filterBtns && filterBtns.length) {
    for (var fb = 0; fb < filterBtns.length; fb += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          setVideoFilter(btn.getAttribute('data-video-filter') || 'none');
        });
      })(filterBtns[fb]);
    }
  }
  if (effectBtns && effectBtns.length) {
    for (var eb = 0; eb < effectBtns.length; eb += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          setVideoEffect(btn.getAttribute('data-video-effect') || 'none');
        });
      })(effectBtns[eb]);
    }
  }
  if (effectPresetBtns && effectPresetBtns.length) {
    for (var ep = 0; ep < effectPresetBtns.length; ep += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          applyEffectPreset(btn.getAttribute('data-effect-preset') || '');
        });
      })(effectPresetBtns[ep]);
    }
  }
  if (stageEl) {
    stageEl.addEventListener('click', function (ev) {
      if (drawEnabled || String(effectState.layer || 'none') !== 'spotlight') return;
      var rect = stageEl.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      effectState.x = Math.max(0, Math.min(100, ((Number(ev.clientX || 0) - rect.left) / rect.width) * 100));
      effectState.y = Math.max(0, Math.min(100, ((Number(ev.clientY || 0) - rect.top) / rect.height) * 100));
      applyEffects();
      markDirty();
      setStatus('Spotlight recolocado. Guarda el clip para conservarlo.');
    });
  }
  if (drawCanvas) {
    drawCanvas.addEventListener('pointerdown', function (ev) {
      if (!drawEnabled) return;
      isDrawing = true;
      pushHistory();
      activeStroke = { color: '#fde047', width: 4, points: [canvasPoint(ev)] };
      drawState.strokes.push(activeStroke);
      if (drawState.strokes.length > 120) drawState.strokes.shift();
      try { drawCanvas.setPointerCapture(ev.pointerId); } catch (e) {}
      renderDrawing();
    });
    drawCanvas.addEventListener('pointermove', function (ev) {
      if (!drawEnabled || !isDrawing || !activeStroke) return;
      activeStroke.points.push(canvasPoint(ev));
      if (activeStroke.points.length > 300) activeStroke.points.shift();
      renderDrawing();
    });
    drawCanvas.addEventListener('pointerup', function () {
      isDrawing = false;
      activeStroke = null;
    });
    drawCanvas.addEventListener('pointercancel', function () {
      isDrawing = false;
      activeStroke = null;
    });
  }
  window.addEventListener('resize', resizeCanvas);
  if (inInput) inInput.addEventListener('input', setInOutLabels);
  if (outInput) outInput.addEventListener('input', setInOutLabels);
  if (inInput) inInput.addEventListener('change', markDirty);
  if (outInput) outInput.addEventListener('change', markDirty);
  if (titleInput) titleInput.addEventListener('input', markDirty);
  if (collectionInput) collectionInput.addEventListener('input', markDirty);
  if (tagsInput) tagsInput.addEventListener('input', markDirty);
  if (notesInput) notesInput.addEventListener('input', markDirty);
  if (btnSave) btnSave.addEventListener('click', function () { saveClip(); });
  if (btnClear) btnClear.addEventListener('click', function () { clearForm(); });
  if (btnRefresh) btnRefresh.addEventListener('click', function () { refreshClips(); });
  if (tagPresetBtns && tagPresetBtns.length) {
    for (var p = 0; p < tagPresetBtns.length; p += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          if (!tagsInput) return;
          tagsInput.value = mergeTags(tagsInput.value, btn.getAttribute('data-tags') || '');
          markDirty();
          try { tagsInput.focus(); } catch (e) {}
        });
      })(tagPresetBtns[p]);
    }
  }
  if (templateBtns && templateBtns.length) {
    for (var tp = 0; tp < templateBtns.length; tp += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          if (titleInput) titleInput.value = btn.getAttribute('data-template-title') || '';
          if (collectionInput) collectionInput.value = btn.getAttribute('data-template-collection') || '';
          if (tagsInput) tagsInput.value = mergeTags(tagsInput.value, btn.getAttribute('data-template-tags') || '');
          if (notesInput && !String(notesInput.value || '').trim()) notesInput.value = btn.getAttribute('data-template-notes') || '';
          markDirty();
        });
      })(templateBtns[tp]);
    }
  }
  if (bulkPlayBtn) bulkPlayBtn.addEventListener('click', playSelected);
  if (bulkShareBtn) bulkShareBtn.addEventListener('click', shareSelectedPlaylist);
  if (bulkClearBtn) bulkClearBtn.addEventListener('click', clearSelection);
  window.addEventListener('beforeunload', function (ev) {
    if (!dirty) return;
    ev.preventDefault();
    ev.returnValue = '';
  });
  document.addEventListener('keydown', function (ev) {
    var tag = String(ev.target && ev.target.tagName ? ev.target.tagName : '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    var key = String(ev.key || '').toLowerCase();
    if (key === ' ') {
      ev.preventDefault();
      if (!player) return;
      try {
        if (btnPause && btnPause.hidden) player.playVideo();
        else player.pauseVideo();
      } catch (e) {}
    } else if (key === 'i') {
      ev.preventDefault();
      setIn(getNow());
      showToast('IN marcado.');
    } else if (key === 'o') {
      ev.preventDefault();
      setOut(getNow());
      showToast('OUT marcado.');
    } else if (key === 's') {
      ev.preventDefault();
      saveClip();
    } else if (key === 'arrowleft') {
      ev.preventDefault();
      seekBy(ev.shiftKey ? -5 : -1);
    } else if (key === 'arrowright') {
      ev.preventDefault();
      seekBy(ev.shiftKey ? 5 : 1);
    } else if ((ev.metaKey || ev.ctrlKey) && key === 'z') {
      ev.preventDefault();
      if (ev.shiftKey) redoDrawing();
      else undoDrawing();
    } else if (key === 'e') {
      ev.preventDefault();
      setVideoEffect(String(effectState.layer || 'none') === 'spotlight' ? 'none' : 'spotlight');
    }
  });

  initAssign();
  applyEffects();
  resizeCanvas();
  initPlayer();
})();
