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
  const lerpAngle = (a, b, t) => {
    const from = Number(a) || 0;
    let to = Number(b) || 0;
    let delta = ((to - from + 540) % 360) - 180;
    if (!Number.isFinite(delta)) delta = to - from;
    to = from + delta;
    return from + (to - from) * t;
  };
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
  const presentBtn = document.getElementById('sim-present');
  const scrubInput = document.getElementById('sim-scrub');
  const canvasEl = document.getElementById('sim-share-canvas');
  const canvasWrap = document.getElementById('sim-canvas-wrap');
  const trailsInput = document.getElementById('sim-trails');
  const labelsInput = document.getElementById('sim-labels');
  const cameraInput = document.getElementById('sim-camera');
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
  let presentEnabled = false;
  const focusRingsByUid = new Map();

  const safeObj = (value) => ((value && typeof value === 'object') ? value : {});
  const safeArr = (value) => (Array.isArray(value) ? value : []);

  const routePoint = (p, fallback) => {
    const x = Number(p?.x);
    const y = Number(p?.y);
    if (Number.isFinite(x) && Number.isFinite(y)) return { x, y };
    return fallback || { x: 0, y: 0 };
  };

  const catmullRom = (p0, p1, p2, p3, t) => {
    const tt = t * t;
    const ttt = tt * t;
    const a0 = (-0.5 * ttt) + (tt) - (0.5 * t);
    const a1 = (1.5 * ttt) - (2.5 * tt) + 1;
    const a2 = (-1.5 * ttt) + (2 * tt) + (0.5 * t);
    const a3 = (0.5 * ttt) - (0.5 * tt);
    return {
      x: (p0.x * a0) + (p1.x * a1) + (p2.x * a2) + (p3.x * a3),
      y: (p0.y * a0) + (p1.y * a1) + (p2.y * a2) + (p3.y * a3),
    };
  };

  const sampleRoutePolyline = (points, t) => {
    const pts = safeArr(points).map((p) => routePoint(p)).filter(Boolean);
    if (pts.length <= 1) return pts[0] || { x: 0, y: 0 };
    const segs = [];
    let total = 0;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const a = pts[i];
      const b = pts[i + 1];
      const len = Math.hypot((b.x - a.x), (b.y - a.y)) || 0;
      segs.push({ a, b, len });
      total += len;
    }
    if (total <= 0.01) return pts[pts.length - 1];
    let dist = clamp(Number(t) || 0, 0, 1) * total;
    for (const seg of segs) {
      if (dist <= seg.len || seg.len <= 0.01) {
        const local = seg.len <= 0.01 ? 0 : (dist / seg.len);
        return { x: lerp(seg.a.x, seg.b.x, local), y: lerp(seg.a.y, seg.b.y, local) };
      }
      dist -= seg.len;
    }
    return pts[pts.length - 1];
  };

  const sampleRouteSpline = (points, t) => {
    const pts = safeArr(points).map((p) => routePoint(p)).filter(Boolean);
    if (pts.length <= 1) return pts[0] || { x: 0, y: 0 };
    const n = pts.length;
    const scaled = clamp(Number(t) || 0, 0, 1) * (n - 1);
    const i = clamp(Math.floor(scaled), 0, n - 2);
    const localT = scaled - i;
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(n - 1, i + 2)];
    return catmullRom(p0, p1, p2, p3, localT);
  };

  const sampleRoute = (points, t, spline) => (spline ? sampleRouteSpline(points, t) : sampleRoutePolyline(points, t));

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
  try { canvas.backgroundVpt = true; } catch (error) {}
  canvas.setWidth(firstSize.w || 960);
  canvas.setHeight(firstSize.h || 540);

  const controlsWrap = document.querySelector('.controls');
  let controlsHideTimer = null;
  const showControls = () => {
    try { document.body.classList.remove('is-controls-hidden'); } catch (error) {}
    if (controlsHideTimer) window.clearTimeout(controlsHideTimer);
    controlsHideTimer = null;
  };
  const scheduleHideControls = () => {
    if (!presentEnabled) return;
    if (controlsHideTimer) window.clearTimeout(controlsHideTimer);
    controlsHideTimer = window.setTimeout(() => {
      try { document.body.classList.add('is-controls-hidden'); } catch (error) {}
    }, 2400);
  };

  const fitCanvasInWrap = () => {
    if (!canvasWrap || !canvasEl) return;
    const wrapRect = canvasWrap.getBoundingClientRect();
    const wrapW = Math.max(1, Number(wrapRect.width) || 1);
    const wrapH = Math.max(1, Number(wrapRect.height) || 1);
    const cW = Math.max(1, Number(canvas.getWidth?.() || canvasEl.width || 1));
    const cH = Math.max(1, Number(canvas.getHeight?.() || canvasEl.height || 1));
    const wrapAR = wrapW / wrapH;
    const canvasAR = cW / cH;
    try {
      if (wrapAR > canvasAR) {
        canvasEl.style.height = '100%';
        canvasEl.style.width = 'auto';
      } else {
        canvasEl.style.width = '100%';
        canvasEl.style.height = 'auto';
      }
      canvasEl.style.maxWidth = '100%';
      canvasEl.style.maxHeight = '100%';
      canvasEl.style.display = 'block';
    } catch (error) {}
  };

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
    try { fitCanvasInWrap(); } catch (error) {}
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
        if (
          kind === 'sim-move'
          || kind === 'sim-move-line'
          || kind === 'sim-move-head'
          || kind === 'sim-route'
          || kind === 'sim-focus'
          || kind === 'sim-label'
        ) {
          if (kind === 'sim-focus') {
            const tuid = safeText(obj?.data?.target_uid);
            if (tuid) focusRingsByUid.delete(tuid);
          }
          if (kind === 'sim-label') {
            const tuid = safeText(obj?.data?.target_uid);
            if (tuid) labelsByUid.delete(tuid);
          }
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
    const enabled = trailsInput ? !!trailsInput.checked : true;
    if (!enabled) return;
    const moves = Array.isArray(step?.moves) ? step.moves : [];
    if (!moves.length) return;
    moves.slice(0, 60).forEach((move) => {
      try { addMoveArrow(move?.from, move?.to); } catch (error) {}
    });
  };

  const findUidByKind = (desiredKind) => {
    try {
      const objs = canvas.getObjects() || [];
      const hit = objs.find((obj) => safeText(obj?.data?.kind) === desiredKind && !obj?.data?.base);
      return safeText(hit?.data?.layer_uid);
    } catch (error) {
      return '';
    }
  };

  const addRouteOverlay = (points, opts = {}) => {
    if (!window.fabric) return null;
    const pts = safeArr(points).map((p) => routePoint(p)).filter(Boolean);
    if (pts.length < 2) return null;
    const stroke = safeText(opts.stroke, 'rgba(34,211,238,0.58)');
    const width = clamp(Number(opts.strokeWidth) || 3, 1, 10);
    const dash = Array.isArray(opts.dash) ? opts.dash : null;
    const poly = new window.fabric.Polyline(pts.slice(0, 60), {
      fill: '',
      stroke,
      strokeWidth: width,
      strokeDashArray: dash || undefined,
      strokeLineCap: 'round',
      strokeLineJoin: 'round',
      selectable: false,
      evented: false,
      excludeFromExport: true,
      opacity: Number.isFinite(Number(opts.opacity)) ? Number(opts.opacity) : 0.95,
      data: { base: true, kind: 'sim-route', layer_uid: `overlay_route_${Date.now()}_${Math.random().toString(16).slice(2)}` },
    });
    try { poly.strokeUniform = true; } catch (error) {}
    canvas.add(poly);
    try { canvas.sendToBack(poly); } catch (error) {}
    return poly;
  };

  const buildRouteDrawPoints = (rawPoints, spline) => {
    const pts = safeArr(rawPoints).map((p) => routePoint(p)).filter(Boolean);
    if (pts.length < 2) return pts;
    if (!spline) return pts.slice(0, 60);
    const samples = [];
    const stepsCount = clamp(Math.round(pts.length * 8), 16, 48);
    for (let i = 0; i <= stepsCount; i += 1) {
      samples.push(sampleRouteSpline(pts, i / stepsCount));
    }
    return samples.slice(0, 60);
  };

  const labelsByUid = new Map();
  const clearLabelOverlays = () => {
    labelsByUid.forEach((label, uid) => {
      try { canvas.remove(label); } catch (error) {}
      labelsByUid.delete(uid);
    });
  };

  const buildLabelText = (obj) => {
    const data = safeObj(obj?.data);
    const number = safeText(data?.playerNumber);
    const name = safeText(data?.playerName);
    const short = number || (name ? name.split(' ')[0] : '');
    return safeText(short);
  };

  const ensureLabel = (uid) => {
    const existing = labelsByUid.get(uid);
    if (existing) return existing;
    if (!window.fabric) return null;
    const txt = new window.fabric.Text('', {
      left: 0,
      top: 0,
      originX: 'center',
      originY: 'bottom',
      fontSize: 20,
      fontWeight: 900,
      fill: 'rgba(226,232,240,0.96)',
      stroke: 'rgba(2,6,23,0.85)',
      strokeWidth: 4,
      paintFirst: 'stroke',
      selectable: false,
      evented: false,
      excludeFromExport: true,
      opacity: 0.98,
      data: { base: true, kind: 'sim-label', target_uid: uid, layer_uid: `overlay_label_${Date.now()}_${Math.random().toString(16).slice(2)}` },
    });
    try { txt.strokeUniform = true; } catch (error) {}
    try { txt.objectCaching = false; } catch (error) {}
    canvas.add(txt);
    canvas.bringToFront?.(txt);
    labelsByUid.set(uid, txt);
    return txt;
  };

  const updateLabelOverlays = (liveByUid) => {
    const enabled = !!labelsInput?.checked;
    if (!enabled) {
      clearLabelOverlays();
      return;
    }
    const desiredUids = [];
    liveByUid?.forEach((obj, uid) => {
      if (safeText(obj?.data?.kind) !== 'token') return;
      desiredUids.push(uid);
    });
    // Limita para no saturar si hay demasiados tokens.
    const limited = desiredUids.slice(0, 40);
    labelsByUid.forEach((label, uid) => {
      if (limited.includes(uid)) return;
      try { canvas.remove(label); } catch (error) {}
      labelsByUid.delete(uid);
    });
    limited.forEach((uid) => {
      const obj = liveByUid?.get(uid);
      if (!obj) return;
      const text = buildLabelText(obj);
      if (!text) return;
      const label = ensureLabel(uid);
      if (!label) return;
      try {
        const center = obj.getCenterPoint?.() || { x: Number(obj.left) || 0, y: Number(obj.top) || 0 };
        const offset = clamp((Math.max(Number(obj.getScaledWidth?.()) || 0, Number(obj.getScaledHeight?.()) || 0) / 2) + 10, 20, 64);
        label.set({
          text,
          left: Number(center.x) || 0,
          top: (Number(center.y) || 0) - offset,
          opacity: presentEnabled ? 1 : 0.92,
        });
        label.setCoords?.();
        canvas.bringToFront?.(label);
      } catch (error) {}
    });
  };

  const ensureFocusRing = (uid) => {
    if (!uid || !window.fabric) return null;
    const existing = focusRingsByUid.get(uid);
    if (existing) return existing;
    const ring = new window.fabric.Circle({
      left: 0,
      top: 0,
      originX: 'center',
      originY: 'center',
      radius: 28,
      fill: 'rgba(0,0,0,0)',
      stroke: 'rgba(34,211,238,0.95)',
      strokeWidth: 5,
      selectable: false,
      evented: false,
      excludeFromExport: true,
      opacity: 0.95,
      data: { base: true, kind: 'sim-focus', target_uid: uid, layer_uid: `overlay_focus_${Date.now()}_${Math.random().toString(16).slice(2)}` },
    });
    try { ring.strokeUniform = true; } catch (error) {}
    canvas.add(ring);
    try { canvas.bringToFront(ring); } catch (error) {}
    focusRingsByUid.set(uid, ring);
    return ring;
  };

  const updateFocusOverlays = (uids, liveByUid) => {
    const desired = (Array.isArray(uids) ? uids : []).map((u) => safeText(u)).filter(Boolean).slice(0, 3);
    focusRingsByUid.forEach((ring, tuid) => {
      if (desired.includes(tuid)) return;
      try { canvas.remove(ring); } catch (error) {}
      focusRingsByUid.delete(tuid);
    });

    desired.forEach((uid) => {
      const target = liveByUid?.get(uid);
      if (!target) return;
      const ring = ensureFocusRing(uid);
      if (!ring) return;
      try {
        const center = target.getCenterPoint?.() || { x: Number(target.left) || 0, y: Number(target.top) || 0 };
        const radius = clamp((Math.max(Number(target.getScaledWidth?.()) || 0, Number(target.getScaledHeight?.()) || 0) / 2) + 12, 22, 70);
        ring.set({ left: Number(center.x) || 0, top: Number(center.y) || 0, radius });
        ring.setCoords?.();
        canvas.bringToFront?.(ring);
      } catch (error) {}
    });
  };

  const computeFocusUidsForSegment = (step, startMap, endMap, liveByUid) => {
    const focus = [];
    const follow = safeText(step?.ball_follow_uid);
    if (follow) focus.push(follow);
    const ballUid = findUidByKind('ball');
    const routes = safeObj(step?.routes);
    const ballRoute = ballUid ? routes?.[ballUid] : null;
    const points = safeArr(ballRoute?.points);
    if (!follow && ballUid && points.length >= 2) {
      const startPos = startMap?.get(ballUid);
      const endPos = endMap?.get(ballUid);
      const startPt = startPos ? { x: Number(startPos.left) || 0, y: Number(startPos.top) || 0 } : routePoint(points[0]);
      const endPt = endPos ? { x: Number(endPos.left) || 0, y: Number(endPos.top) || 0 } : routePoint(points[points.length - 1]);
      const tokenUids = [];
      liveByUid?.forEach((obj, uid) => {
        if (safeText(obj?.data?.kind) !== 'token') return;
        tokenUids.push(uid);
      });
      const nearestToken = (pt, map) => {
        let best = { uid: '', d: Infinity };
        tokenUids.forEach((uid) => {
          const st = map?.get(uid);
          if (!st) return;
          const dx = (Number(st.left) || 0) - (Number(pt.x) || 0);
          const dy = (Number(st.top) || 0) - (Number(pt.y) || 0);
          const d = Math.hypot(dx, dy);
          if (d < best.d) best = { uid, d };
        });
        return best.d <= 120 ? best.uid : '';
      };
      const a = nearestToken(startPt, startMap);
      const b = nearestToken(endPt, endMap);
      if (a) focus.push(a);
      if (b && b !== a) focus.push(b);
    }
    return Array.from(new Set(focus)).slice(0, 3);
  };

  const computeFocusUidsForStaticStep = (step, stateMap, liveByUid) => {
    const focus = [];
    const follow = safeText(step?.ball_follow_uid);
    if (follow) return [follow];
    const ballUid = findUidByKind('ball');
    if (!ballUid) return [];
    const ballState = stateMap?.get(ballUid);
    const pt = ballState ? { x: Number(ballState.left) || 0, y: Number(ballState.top) || 0 } : null;
    if (!pt) return [];
    const tokenUids = [];
    liveByUid?.forEach((obj, uid) => {
      if (safeText(obj?.data?.kind) !== 'token') return;
      tokenUids.push(uid);
    });
    let best = { uid: '', d: Infinity };
    tokenUids.forEach((uid) => {
      const st = stateMap?.get(uid);
      if (!st) return;
      const dx = (Number(st.left) || 0) - (Number(pt.x) || 0);
      const dy = (Number(st.top) || 0) - (Number(pt.y) || 0);
      const d = Math.hypot(dx, dy);
      if (d < best.d) best = { uid, d };
    });
    if (best.uid && best.d <= 130) focus.push(best.uid);
    return focus;
  };

  const resetViewport = () => {
    try { canvas.setViewportTransform([1, 0, 0, 1, 0, 0]); } catch (error) {}
  };

  const applyCameraToUids = (uids, liveByUid, opts = {}) => {
    if (!presentEnabled) {
      resetViewport();
      return;
    }
    const enabled = !!cameraInput?.checked;
    if (!enabled) {
      resetViewport();
      return;
    }
    const ids = (Array.isArray(uids) ? uids : []).map((u) => safeText(u)).filter(Boolean).slice(0, 4);
    if (!ids.length) {
      resetViewport();
      return;
    }
    const box = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
    ids.forEach((uid) => {
      const obj = liveByUid?.get(uid);
      if (!obj) return;
      try {
        const rect = obj.getBoundingRect?.(true) || null;
        const left = Number(rect?.left);
        const top = Number(rect?.top);
        const w = Number(rect?.width);
        const h = Number(rect?.height);
        if ([left, top, w, h].some((n) => !Number.isFinite(n))) return;
        box.minX = Math.min(box.minX, left);
        box.minY = Math.min(box.minY, top);
        box.maxX = Math.max(box.maxX, left + w);
        box.maxY = Math.max(box.maxY, top + h);
      } catch (error) {}
    });
    if (!Number.isFinite(box.minX) || !Number.isFinite(box.minY) || !Number.isFinite(box.maxX) || !Number.isFinite(box.maxY)) {
      resetViewport();
      return;
    }
    const margin = 140;
    box.minX -= margin;
    box.minY -= margin;
    box.maxX += margin;
    box.maxY += margin;
    const boxW = Math.max(220, box.maxX - box.minX);
    const boxH = Math.max(160, box.maxY - box.minY);
    const cW = Math.max(1, Number(canvas.getWidth?.() || 1));
    const cH = Math.max(1, Number(canvas.getHeight?.() || 1));
    const zoom = clamp(Math.min(cW / boxW, cH / boxH) * 0.95, 0.9, 2.35);
    const cx = (box.minX + box.maxX) / 2;
    const cy = (box.minY + box.maxY) / 2;
    const tx = (cW / 2) - (zoom * cx);
    const ty = (cH / 2) - (zoom * cy);
    const target = [zoom, 0, 0, zoom, tx, ty];
    const current = canvas.viewportTransform || [1, 0, 0, 1, 0, 0];
    const smooth = opts.smooth !== false;
    const alpha = smooth ? 0.14 : 1;
    const next = [
      lerp(current[0], target[0], alpha),
      0,
      0,
      lerp(current[3], target[3], alpha),
      lerp(current[4], target[4], alpha),
      lerp(current[5], target[5], alpha),
    ];
    try { canvas.setViewportTransform(next); } catch (error) {}
  };

  const renderRouteOverlaysForStep = (step) => {
    const enabled = trailsInput ? !!trailsInput.checked : true;
    if (!enabled) return;
    const routes = safeObj(step?.routes);
    const entries = Object.entries(routes).slice(0, 50);
    if (!entries.length) return;
    const ballUid = findUidByKind('ball');
    entries.forEach(([uid, route]) => {
      const pts = safeArr(route?.points);
      if (pts.length < 2) return;
      const spline = !!route?.spline;
      const drawPts = buildRouteDrawPoints(pts, spline);
      const isBall = ballUid && uid === ballUid;
      if (isBall) {
        addRouteOverlay(drawPts, { stroke: 'rgba(249,115,22,0.24)', strokeWidth: 11, dash: null, opacity: 0.9 });
        addRouteOverlay(drawPts, { stroke: 'rgba(249,115,22,0.98)', strokeWidth: 5, dash: null, opacity: 0.98 });
      } else {
        addRouteOverlay(drawPts, {
          stroke: 'rgba(34,211,238,0.55)',
          strokeWidth: 4,
          dash: [10, 10],
          opacity: 0.85,
        });
      }
    });
  };

  const renderOverlaysForStep = (step) => {
    clearOverlayObjects();
    renderRouteOverlaysForStep(step);
    renderMoveOverlaysForStep(step);
    try {
      const liveByUid = new Map();
      (canvas.getObjects() || []).forEach((obj) => {
        const uid = safeText(obj?.data?.layer_uid);
        if (uid) liveByUid.set(uid, obj);
      });
      const stateMap = mapFromCanvasState(step.canvas_state);
      const focusUids = computeFocusUidsForStaticStep(step, stateMap, liveByUid);
      updateFocusOverlays(focusUids, liveByUid);
      updateLabelOverlays(liveByUid);
      applyCameraToUids(focusUids, liveByUid, { smooth: false });
      canvas.renderAll();
    } catch (error) {}
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
          try { renderOverlaysForStep(step); } catch (error) {}
          canvas.renderAll();
          renderStepsList();
          if (scrubInput) {
            try { scrubInput.value = String(activeIndex); } catch (error) {}
          }
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
    const startRoutes = safeObj(startStep?.routes);
    rafStartedAt = performance.now();
    rafDurationMs = durationMs;
    return await new Promise((resolve) => {
      rafResolve = resolve;
      let animTargets = [];
      try {
        const liveByUid = new Map();
        (canvas.getObjects() || []).forEach((obj) => {
          const uid = safeText(obj?.data?.layer_uid);
          if (uid) liveByUid.set(uid, obj);
        });
        const keys = new Set([...(rafStartMap?.keys?.() || []), ...(rafEndMap?.keys?.() || [])]);
        animTargets = Array.from(keys).map((uid) => {
          const obj = liveByUid.get(uid);
          if (!obj) return null;
          const a = rafStartMap?.get(uid);
          const b = rafEndMap?.get(uid);
          if (!a && !b) return null;
          const route = safeObj(startRoutes?.[uid]);
          const pts = safeArr(route?.points);
          const spline = !!route?.spline;
          const hasRoute = pts.length >= 2;
          const startPt = { x: Number((a || b)?.left) || 0, y: Number((a || b)?.top) || 0 };
          const endPt = { x: Number((b || a)?.left) || 0, y: Number((b || a)?.top) || 0 };
          let combined = null;
          if (hasRoute) {
            const routePts = pts.map((p) => routePoint(p)).filter(Boolean);
            const out = routePts.slice();
            const first = out[0];
            const last = out[out.length - 1];
            if (!first || Math.hypot((first.x - startPt.x), (first.y - startPt.y)) > 6) out.unshift(startPt);
            if (!last || Math.hypot((last.x - endPt.x), (last.y - endPt.y)) > 6) out.push(endPt);
            combined = out.slice(0, 80);
          }
          return {
            uid,
            obj,
            a,
            b,
            hasRoute,
            routePoints: combined,
            routeSpline: spline,
          };
        }).filter(Boolean);
      } catch (error) {
        animTargets = [];
      }
      const focusUids = [];
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
          animTargets.forEach((target) => {
            const obj = target.obj;
            const a = target.a;
            const b = target.b;
            if (!obj || (!a && !b)) return;
            if (!a) return applyPropsToObject(obj, b);
            if (!b) return applyPropsToObject(obj, a);
            let left = lerp(a.left, b.left, eased);
            let top = lerp(a.top, b.top, eased);
            if (target.hasRoute && target.routePoints && target.routePoints.length >= 2) {
              const sampled = sampleRoute(target.routePoints, eased, !!target.routeSpline);
              left = Number.isFinite(sampled?.x) ? sampled.x : left;
              top = Number.isFinite(sampled?.y) ? sampled.y : top;
            }
            return applyPropsToObject(obj, {
              left,
              top,
              angle: lerpAngle(a.angle, b.angle, eased),
              scaleX: lerp(a.scaleX, b.scaleX, eased),
              scaleY: lerp(a.scaleY, b.scaleY, eased),
              opacity: lerp(a.opacity, b.opacity, eased),
            });
          });

          // Balón pegado (si aplica) cuando no hay ruta del balón.
          const followUid = safeText(startStep?.ball_follow_uid);
          const liveByUid = new Map();
          (canvas.getObjects() || []).forEach((obj) => {
            const uid = safeText(obj?.data?.layer_uid);
            if (uid) liveByUid.set(uid, obj);
          });
          const ballUid = findUidByKind('ball');
          const ballObj = ballUid ? liveByUid.get(ballUid) : null;
          const followObj = followUid ? liveByUid.get(followUid) : null;
          const ballRoute = ballUid ? safeObj(startRoutes?.[ballUid]) : null;
          const ballHasRoute = safeArr(ballRoute?.points).length >= 2;
          if (ballObj && followObj && !ballHasRoute) {
            ballObj.set({ left: Number(followObj.left) || 0, top: Number(followObj.top) || 0 });
            ballObj.setCoords?.();
          }
          const segmentFocus = computeFocusUidsForSegment(startStep, rafStartMap, rafEndMap, liveByUid);
          updateFocusOverlays(segmentFocus, liveByUid);
          updateLabelOverlays(liveByUid);
          applyCameraToUids(segmentFocus, liveByUid, { smooth: true });
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
  labelsInput?.addEventListener('change', async () => {
    if (isPlaying) return;
    await loadStep(activeIndex);
  });
  cameraInput?.addEventListener('change', async () => {
    if (isPlaying) return;
    await loadStep(activeIndex);
  });

  let scrubTimer = null;
  const scrubTo = async (rawIndex) => {
    const idx = clamp(Number(rawIndex) || 0, 0, steps.length - 1);
    stop();
    await loadStep(idx);
  };
  scrubInput?.addEventListener('input', () => {
    showControls();
    scheduleHideControls();
    const idx = clamp(Number(scrubInput.value) || 0, 0, steps.length - 1);
    setStatus(`Paso ${idx + 1}/${steps.length}`);
    if (scrubTimer) window.clearTimeout(scrubTimer);
    scrubTimer = window.setTimeout(() => {
      void scrubTo(idx);
    }, 90);
  });
  scrubInput?.addEventListener('change', () => {
    const idx = clamp(Number(scrubInput.value) || 0, 0, steps.length - 1);
    void scrubTo(idx);
  });

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
    if (key === 'f') {
      event.preventDefault();
      presentBtn?.click?.();
    }
    if (key === 't') {
      event.preventDefault();
      if (trailsInput) trailsInput.checked = !trailsInput.checked;
      await loadStep(activeIndex);
    }
    if (key === 'l') {
      event.preventDefault();
      if (labelsInput) labelsInput.checked = !labelsInput.checked;
      await loadStep(activeIndex);
    }
    if (key === 'c') {
      event.preventDefault();
      if (cameraInput) cameraInput.checked = !cameraInput.checked;
      await loadStep(activeIndex);
    }
    if (key === 'n') {
      event.preventDefault();
      stop();
      await loadStep(activeIndex + 1);
    }
    if (key === 'p') {
      event.preventDefault();
      stop();
      await loadStep(activeIndex - 1);
    }
    if (/^[1-9]$/.test(key)) {
      event.preventDefault();
      const idx = clamp(Number(key) - 1, 0, steps.length - 1);
      stop();
      await loadStep(idx);
    }
    showControls();
    scheduleHideControls();
  });

  const setPresentMode = (enabled) => {
    presentEnabled = !!enabled;
    try { document.body.classList.toggle('is-present', presentEnabled); } catch (error) {}
    if (presentBtn) presentBtn.textContent = presentEnabled ? 'Salir' : 'Presentación';
    showControls();
    scheduleHideControls();
    try { fitCanvasInWrap(); } catch (error) {}
  };

  const requestFullscreen = async () => {
    try {
      if (document.fullscreenElement) return true;
      if (document.documentElement?.requestFullscreen) {
        await document.documentElement.requestFullscreen();
        return true;
      }
      return false;
    } catch (error) {
      return false;
    }
  };

  const exitFullscreen = async () => {
    try {
      if (!document.fullscreenElement) return true;
      if (document.exitFullscreen) {
        await document.exitFullscreen();
        return true;
      }
      return false;
    } catch (error) {
      return false;
    }
  };

  presentBtn?.addEventListener('click', async () => {
    if (presentEnabled) {
      setPresentMode(false);
      await exitFullscreen();
      return;
    }
    setPresentMode(true);
    await requestFullscreen();
  });

  document.addEventListener('fullscreenchange', () => {
    if (document.fullscreenElement) return;
    if (presentEnabled) setPresentMode(false);
  });

  (async () => {
    await loadPitchBackground();
    renderStepsList();
    if (scrubInput) {
      scrubInput.min = '0';
      scrubInput.max = String(Math.max(0, steps.length - 1));
      scrubInput.value = '0';
    }
    try { fitCanvasInWrap(); } catch (error) {}
    try {
      const ro = window.ResizeObserver ? new window.ResizeObserver(() => fitCanvasInWrap()) : null;
      ro?.observe?.(canvasWrap || canvasEl);
      window.addEventListener('resize', () => fitCanvasInWrap(), { passive: true });
    } catch (error) {}
    try {
      ['mousemove', 'touchstart', 'pointerdown'].forEach((ev) => {
        document.addEventListener(ev, () => {
          if (!presentEnabled) return;
          showControls();
          scheduleHideControls();
        }, { passive: true });
      });
    } catch (error) {}
    await loadStep(0);
    setStatus(`Paso 1/${steps.length}: ${safeText(steps[0]?.title, '—')}`);
  })();
})();
