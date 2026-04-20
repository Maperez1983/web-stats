/* global THREE */
(() => {
  const safeText = (value, fallback = '') => {
    const v = (value == null ? '' : String(value)).trim();
    return v || fallback;
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const readJson = (value) => {
    try {
      return value ? JSON.parse(value) : null;
    } catch (e) {
      return null;
    }
  };

  const buildSimStorageKey = (form) => {
    if (!form) return 'webstats:tpad:draft:unknown:simsteps_v1';
    const base = safeText(form.dataset.draftKey) || safeText(form.dataset.draftNewKey) || 'webstats:tpad:draft:unknown';
    return `${base}:simsteps_v1`;
  };

  const readSimSteps = (form) => {
    const key = buildSimStorageKey(form);
    try {
      const raw = window.localStorage?.getItem(key) || '';
      const parsed = raw ? JSON.parse(raw) : null;
      const steps = Array.isArray(parsed?.steps) ? parsed.steps : [];
      return steps.slice(0, 24);
    } catch (e) {
      return [];
    }
  };

  const readCanvasState = (form) => {
    const input = form?.querySelector('#draw-canvas-state');
    const raw = safeText(input?.value);
    const parsed = readJson(raw);
    return (parsed && typeof parsed === 'object') ? parsed : null;
  };

  const readCanvasDims = (form) => {
    const w = Number.parseInt(safeText(form?.querySelector('#draw-canvas-width')?.value), 10) || 1280;
    const h = Number.parseInt(safeText(form?.querySelector('#draw-canvas-height')?.value), 10) || 720;
    return { w, h };
  };

  const keyForObject = (obj, index) => {
    const data = obj?.data || {};
    const kind = safeText(data.kind);
    const uid = safeText(data.layer_uid);
    if (uid) return `uid:${uid}`;
    if (kind === 'token') {
      const pid = safeText(data.playerId);
      const num = safeText(data.playerNumber);
      const tkind = safeText(data.token_kind);
      return `token:${tkind}:${pid || num || index}`;
    }
    const id = safeText(obj?.id);
    return `${kind || obj?.type || 'obj'}:${id || index}`;
  };

  const degToRad = (deg) => (Number(deg) || 0) * (Math.PI / 180);

  const transformPoint = (pt, tf) => {
    const x0 = Number(pt?.x) || 0;
    const y0 = Number(pt?.y) || 0;
    const sx = Number(tf?.sx);
    const sy = Number(tf?.sy);
    const angle = degToRad(tf?.angle || 0);
    const tx = Number(tf?.tx) || 0;
    const ty = Number(tf?.ty) || 0;
    const x = x0 * (Number.isFinite(sx) ? sx : 1);
    const y = y0 * (Number.isFinite(sy) ? sy : 1);
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const xr = x * cos - y * sin;
    const yr = x * sin + y * cos;
    return { x: xr + tx, y: yr + ty };
  };

  const sampleQuadratic = (p0, p1, p2, t) => {
    const a = 1 - t;
    return {
      x: a * a * p0.x + 2 * a * t * p1.x + t * t * p2.x,
      y: a * a * p0.y + 2 * a * t * p1.y + t * t * p2.y,
    };
  };

  const sampleCubic = (p0, p1, p2, p3, t) => {
    const a = 1 - t;
    return {
      x: a * a * a * p0.x + 3 * a * a * t * p1.x + 3 * a * t * t * p2.x + t * t * t * p3.x,
      y: a * a * a * p0.y + 3 * a * a * t * p1.y + 3 * a * t * t * p2.y + t * t * t * p3.y,
    };
  };

  const sampleFabricPath = (pathArr, segments = 14) => {
    const path = Array.isArray(pathArr) ? pathArr : [];
    const points = [];
    let cursor = { x: 0, y: 0 };
    let start = { x: 0, y: 0 };
    path.forEach((cmd) => {
      if (!Array.isArray(cmd) || !cmd.length) return;
      const op = String(cmd[0] || '').trim().toUpperCase();
      if (op === 'M') {
        cursor = { x: Number(cmd[1]) || 0, y: Number(cmd[2]) || 0 };
        start = { ...cursor };
        points.push({ ...cursor });
      } else if (op === 'L') {
        cursor = { x: Number(cmd[1]) || 0, y: Number(cmd[2]) || 0 };
        points.push({ ...cursor });
      } else if (op === 'Q') {
        const p0 = { ...cursor };
        const p1 = { x: Number(cmd[1]) || 0, y: Number(cmd[2]) || 0 };
        const p2 = { x: Number(cmd[3]) || 0, y: Number(cmd[4]) || 0 };
        for (let i = 1; i <= segments; i += 1) {
          points.push(sampleQuadratic(p0, p1, p2, i / segments));
        }
        cursor = { ...p2 };
      } else if (op === 'C') {
        const p0 = { ...cursor };
        const p1 = { x: Number(cmd[1]) || 0, y: Number(cmd[2]) || 0 };
        const p2 = { x: Number(cmd[3]) || 0, y: Number(cmd[4]) || 0 };
        const p3 = { x: Number(cmd[5]) || 0, y: Number(cmd[6]) || 0 };
        for (let i = 1; i <= segments; i += 1) {
          points.push(sampleCubic(p0, p1, p2, p3, i / segments));
        }
        cursor = { ...p3 };
      } else if (op === 'Z') {
        cursor = { ...start };
        points.push({ ...cursor });
      }
    });
    return points;
  };

  const extractRenderable = (state, dims, extra = {}) => {
    const objects = Array.isArray(state?.objects) ? state.objects : [];
    const out = [];
    const baseTf = { tx: 0, ty: 0, angle: 0, sx: 1, sy: 1 };

    const walk = (obj, index, tf) => {
      if (!obj || typeof obj !== 'object') return;
      const data = obj?.data || {};
      const rawKind = safeText(data.kind) || safeText(obj?.type);
      const kind = rawKind.replace(/_/g, '-').toLowerCase();
      const left = Number(obj?.left);
      const top = Number(obj?.top);
      const angle = Number(obj?.angle) || 0;
      const sx = Number(obj?.scaleX);
      const sy = Number(obj?.scaleY);
      const nextTf = {
        tx: (Number.isFinite(left) ? left : 0) + (Number(tf?.tx) || 0),
        ty: (Number.isFinite(top) ? top : 0) + (Number(tf?.ty) || 0),
        angle: (Number(tf?.angle) || 0) + angle,
        sx: (Number.isFinite(sx) ? sx : 1) * (Number(tf?.sx) || 1),
        sy: (Number.isFinite(sy) ? sy : 1) * (Number(tf?.sy) || 1),
      };

      // Grupos: procesamos hijos con la transform acumulada.
      if (safeText(obj?.type) === 'group' && Array.isArray(obj?.objects)) {
        obj.objects.forEach((child, childIndex) => walk(child, childIndex, nextTf));
        return;
      }

      // Tokens y objetos clave (dinámicos).
      if (kind === 'token') {
        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
        const xN = clamp(nextTf.tx / (dims.w || 1280), 0, 1);
        const yN = clamp(nextTf.ty / (dims.h || 720), 0, 1);
        out.push({
          k: keyForObject(obj, index),
          kind: 'token',
          token_kind: safeText(data.token_kind) || 'player_local',
          xN,
          yN,
          label: safeText(data.playerNumber) || safeText(data.playerName),
        });
        return;
      }
      if (kind === 'ball') {
        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
        out.push({ k: keyForObject(obj, index), kind: 'ball', xN: clamp(nextTf.tx / (dims.w || 1280), 0, 1), yN: clamp(nextTf.ty / (dims.h || 720), 0, 1) });
        return;
      }
      if (kind === 'cone' || kind === 'cone-striped') {
        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
        out.push({ k: keyForObject(obj, index), kind: 'cone', xN: clamp(nextTf.tx / (dims.w || 1280), 0, 1), yN: clamp(nextTf.ty / (dims.h || 720), 0, 1) });
        return;
      }
      if (kind === 'goal') {
        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
        out.push({ k: keyForObject(obj, index), kind: 'goal', xN: clamp(nextTf.tx / (dims.w || 1280), 0, 1), yN: clamp(nextTf.ty / (dims.h || 720), 0, 1), angle });
        return;
      }

      // Texto (incluye emojis).
      if (kind === 'text' || kind === 'i-text') {
        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
        const text = safeText(obj?.text);
        if (!text) return;
        out.push({
          k: keyForObject(obj, index),
          kind: 'text',
          xN: clamp(nextTf.tx / (dims.w || 1280), 0, 1),
          yN: clamp(nextTf.ty / (dims.h || 720), 0, 1),
          text: text.slice(0, 22),
        });
        return;
      }

      // Figuras (zonas/rect/circle) para táctica.
      if (kind.startsWith('shape-') || kind === 'rect' || kind === 'circle') {
        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
        const fill = safeText(obj?.fill);
        const stroke = safeText(obj?.stroke);
        const opacity = Number.isFinite(Number(obj?.opacity)) ? Number(obj.opacity) : 1;
        if (safeText(obj?.type) === 'circle') {
          const r = Number(obj?.radius) || 40;
          out.push({
            k: keyForObject(obj, index),
            kind: 'zone-circle',
            xN: clamp(nextTf.tx / (dims.w || 1280), 0, 1),
            yN: clamp(nextTf.ty / (dims.h || 720), 0, 1),
            rN: clamp(r / (dims.w || 1280), 0.005, 0.5),
            fill,
            stroke,
            opacity,
          });
          return;
        }
        if (safeText(obj?.type) === 'rect') {
          const w = Number(obj?.width) || 100;
          const h = Number(obj?.height) || 70;
          out.push({
            k: keyForObject(obj, index),
            kind: 'zone-rect',
            xN: clamp(nextTf.tx / (dims.w || 1280), 0, 1),
            yN: clamp(nextTf.ty / (dims.h || 720), 0, 1),
            wN: clamp(w / (dims.w || 1280), 0.01, 1),
            hN: clamp(h / (dims.h || 720), 0.01, 1),
            angle,
            fill,
            stroke,
            opacity,
          });
        }
        return;
      }

      // Flechas/lineas: grupos con kind arrow-*, o paths/lines con kind line-*.
      const arrowKinds = new Set(['arrow', 'arrow-thick', 'arrow-dash', 'arrow-dot', 'arrow-curve']);
      const lineKinds = new Set(['line-solid', 'line-dash', 'line-dot', 'line-curve', 'line-wave']);
      if (arrowKinds.has(kind) || lineKinds.has(kind) || kind === 'line' || kind === 'path') {
        const stroke = safeText(obj?.stroke) || safeText(data?.stroke) || '#f8fafc';
        const strokeWidth = Number(obj?.strokeWidth) || 4;
        const dash = Array.isArray(obj?.strokeDashArray) ? obj.strokeDashArray : null;
        const isArrow = arrowKinds.has(kind) || kind.startsWith('arrow');
        // Line
        if (safeText(obj?.type) === 'line') {
          const x1 = Number(obj?.x1) || 0;
          const y1 = Number(obj?.y1) || 0;
          const x2 = Number(obj?.x2) || 0;
          const y2 = Number(obj?.y2) || 0;
          const p1 = transformPoint({ x: x1, y: y1 }, nextTf);
          const p2 = transformPoint({ x: x2, y: y2 }, nextTf);
          out.push({
            k: keyForObject(obj, index),
            kind: isArrow ? 'arrow-line' : 'polyline',
            pointsN: [
              { xN: clamp(p1.x / (dims.w || 1280), 0, 1), yN: clamp(p1.y / (dims.h || 720), 0, 1) },
              { xN: clamp(p2.x / (dims.w || 1280), 0, 1), yN: clamp(p2.y / (dims.h || 720), 0, 1) },
            ],
            stroke,
            strokeWidth,
            dash,
          });
          return;
        }
        // Path
        const rawPath = obj?.path;
        if (Array.isArray(rawPath) && rawPath.length) {
          const pts = sampleFabricPath(rawPath, 10)
            .slice(0, 220)
            .map((pt) => transformPoint(pt, nextTf))
            .map((p) => ({ xN: clamp(p.x / (dims.w || 1280), 0, 1), yN: clamp(p.y / (dims.h || 720), 0, 1) }));
          if (pts.length >= 2) {
            out.push({
              k: keyForObject(obj, index),
              kind: isArrow ? 'arrow-line' : 'polyline',
              pointsN: pts,
              stroke,
              strokeWidth,
              dash,
            });
          }
        }
      }
    };

    objects.forEach((obj, index) => walk(obj, index, baseTf));

    // Trayectorias de simulación: vienen en step.moves (coordenadas de canvas).
    const moves = Array.isArray(extra?.moves) ? extra.moves : [];
    if (moves.length) {
      moves.slice(0, 80).forEach((move, idx) => {
        const from = move?.from || {};
        const to = move?.to || {};
        const x1 = Number(from.x);
        const y1 = Number(from.y);
        const x2 = Number(to.x);
        const y2 = Number(to.y);
        if (!Number.isFinite(x1) || !Number.isFinite(y1) || !Number.isFinite(x2) || !Number.isFinite(y2)) return;
        out.push({
          k: `sim-move:${safeText(move?.uid) || idx}`,
          kind: 'sim-move',
          pointsN: [
            { xN: clamp(x1 / (dims.w || 1280), 0, 1), yN: clamp(y1 / (dims.h || 720), 0, 1) },
            { xN: clamp(x2 / (dims.w || 1280), 0, 1), yN: clamp(y2 / (dims.h || 720), 0, 1) },
          ],
          stroke: 'rgba(250,204,21,0.95)',
          strokeWidth: 4,
          dash: [12, 8],
        });
      });
    }
    return out;
  };

  class Sim3DViewer {
    constructor(canvas, labelEl, speedEl) {
      this.canvas = canvas;
      this.labelEl = labelEl;
      this.speedEl = speedEl;
      this.renderer = null;
      this.scene = null;
      this.camera = null;
      this.pitchGroup = null;
      this.meshByKey = new Map();
      this.steps = [];
      this.stepIndex = 0;
      this.playing = false;
      this.playTimer = null;
      this.animFrame = null;
      this.transition = null;
      this.cameraState = { yaw: 0.0, zoom: 1.0, tilt: 0.86 };
      this.drag = { active: false, x: 0, y: 0, yaw0: 0 };
      this.onResize = this.onResize.bind(this);
      this.tick = this.tick.bind(this);
    }

    init() {
      if (!window.THREE) throw new Error('THREE no disponible');
      const rect = this.canvas.getBoundingClientRect();
      this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true, preserveDrawingBuffer: false });
      this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
      this.renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height), false);

      this.scene = new THREE.Scene();
      this.scene.background = null;

      const w = 100;
      const h = 65;
      this.pitchGroup = new THREE.Group();
      this.scene.add(this.pitchGroup);

      const ambient = new THREE.AmbientLight(0xffffff, 0.85);
      this.scene.add(ambient);
      const dir = new THREE.DirectionalLight(0xffffff, 0.55);
      dir.position.set(40, 80, 40);
      this.scene.add(dir);

      // Césped (simple).
      const grass = new THREE.Mesh(
        new THREE.PlaneGeometry(w, h, 1, 1),
        new THREE.MeshStandardMaterial({ color: 0x166534, roughness: 0.95, metalness: 0.0 }),
      );
      grass.rotation.x = -Math.PI / 2;
      grass.position.y = 0;
      this.pitchGroup.add(grass);

      // Líneas.
      const lineMat = new THREE.LineBasicMaterial({ color: 0xf8fafc, transparent: true, opacity: 0.85 });
      const lineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-w / 2, 0.02, -h / 2),
        new THREE.Vector3(w / 2, 0.02, -h / 2),
        new THREE.Vector3(w / 2, 0.02, h / 2),
        new THREE.Vector3(-w / 2, 0.02, h / 2),
        new THREE.Vector3(-w / 2, 0.02, -h / 2),
      ]);
      const outline = new THREE.Line(lineGeo, lineMat);
      this.pitchGroup.add(outline);

      this.camera = new THREE.PerspectiveCamera(40, 1, 0.1, 500);
      this.applyCamera();

      this.bindControls();
      window.addEventListener('resize', this.onResize);
      this.onResize();
      this.tick();
    }

    destroy() {
      this.stop();
      window.removeEventListener('resize', this.onResize);
      if (this.animFrame) cancelAnimationFrame(this.animFrame);
      this.animFrame = null;
      try { this.renderer?.dispose?.(); } catch (e) {}
      this.renderer = null;
      this.scene = null;
      this.camera = null;
      this.meshByKey.clear();
    }

    bindControls() {
      const onDown = (ev) => {
        this.drag.active = true;
        this.drag.x = ev.clientX || 0;
        this.drag.y = ev.clientY || 0;
        this.drag.yaw0 = this.cameraState.yaw;
      };
      const onMove = (ev) => {
        if (!this.drag.active) return;
        const dx = (ev.clientX || 0) - this.drag.x;
        this.cameraState.yaw = this.drag.yaw0 + (dx / 300);
        this.applyCamera();
      };
      const onUp = () => { this.drag.active = false; };
      this.canvas.addEventListener('pointerdown', (ev) => {
        try { this.canvas.setPointerCapture(ev.pointerId); } catch (e) {}
        onDown(ev);
      });
      this.canvas.addEventListener('pointermove', onMove);
      this.canvas.addEventListener('pointerup', onUp);
      this.canvas.addEventListener('pointercancel', onUp);
      this.canvas.addEventListener('wheel', (ev) => {
        ev.preventDefault();
        const delta = Math.sign(ev.deltaY || 0);
        this.cameraState.zoom = clamp(this.cameraState.zoom + (delta * 0.08), 0.55, 1.6);
        this.applyCamera();
      }, { passive: false });
    }

    onResize() {
      if (!this.renderer || !this.camera) return;
      const rect = this.canvas.getBoundingClientRect();
      const w = Math.max(1, rect.width);
      const h = Math.max(1, rect.height);
      this.renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    }

    applyCamera() {
      if (!this.camera) return;
      const zoom = Number(this.cameraState.zoom) || 1.0;
      const yaw = Number(this.cameraState.yaw) || 0;
      const tilt = clamp(Number(this.cameraState.tilt) || 0.86, 0.45, 1.25);
      const radius = 140 / zoom;
      const x = Math.sin(yaw) * radius;
      const z = Math.cos(yaw) * radius;
      const y = 92 * tilt;
      this.camera.position.set(x, y, z);
      this.camera.lookAt(0, 0, 0);
    }

    setSteps(steps) {
      this.steps = Array.isArray(steps) ? steps : [];
      this.stepIndex = clamp(this.stepIndex, 0, Math.max(0, this.steps.length - 1));
    }

    setStep(index, { transitionMs = 320 } = {}) {
      if (!this.steps.length) {
        this.stepIndex = 0;
        this.updateLabel();
        return;
      }
      const idx = clamp(Number(index) || 0, 0, Math.max(0, this.steps.length - 1));
      const prev = this.steps[this.stepIndex] || null;
      const next = this.steps[idx] || null;
      this.stepIndex = idx;
      this.updateLabel();
      if (!next) return;

      const prevMap = new Map((prev?.items || []).map((it) => [it.k, it]));
      const nextMap = new Map((next?.items || []).map((it) => [it.k, it]));
      const allKeys = new Set([...prevMap.keys(), ...nextMap.keys()]);

      // Crea/borra meshes.
      allKeys.forEach((k) => {
        const n = nextMap.get(k);
        const mesh = this.meshByKey.get(k);
        if (!n) {
          if (mesh) {
            try { this.pitchGroup.remove(mesh); } catch (e) {}
            this.meshByKey.delete(k);
          }
          return;
        }
        // Elementos "estáticos" (líneas, zonas, texto) se recrean para reflejar cambios de geometría.
        if (mesh && mesh?.userData?.static) {
          try { this.pitchGroup.remove(mesh); } catch (e) {}
          this.meshByKey.delete(k);
        }
        if (!mesh) {
          const created = this.createMeshForItem(n);
          if (created) {
            this.meshByKey.set(k, created);
            this.pitchGroup.add(created);
          }
        }
      });

      // Transición.
      const startAt = performance.now();
      const dur = clamp(Number(transitionMs) || 320, 80, 1600);
      this.transition = {
        startAt,
        dur,
        prevMap,
        nextMap,
      };
    }

    updateLabel() {
      if (!this.labelEl) return;
      const total = this.steps.length || 1;
      const idx = (this.steps.length ? (this.stepIndex + 1) : 1);
      const title = safeText(this.steps[this.stepIndex]?.title, `Paso ${idx}`);
      this.labelEl.textContent = `${idx}/${total} · ${title}`;
    }

    stop() {
      this.playing = false;
      if (this.playTimer) window.clearTimeout(this.playTimer);
      this.playTimer = null;
    }

    play() {
      if (!this.steps.length) return;
      if (this.playing) {
        this.stop();
        return;
      }
      this.playing = true;
      const advance = () => {
        if (!this.playing) return;
        const step = this.steps[this.stepIndex] || {};
        const speed = clamp(Number(this.speedEl?.value) || 1, 0.25, 3);
        const duration = clamp(Number(step.duration) || 3, 1, 20);
        const totalMs = Math.round((duration / speed) * 1000);
        const transMs = clamp(Math.round(totalMs * 0.35), 220, 900);
        this.setStep(this.stepIndex, { transitionMs: transMs });
        this.playTimer = window.setTimeout(() => {
          this.stepIndex = (this.stepIndex + 1) % this.steps.length;
          this.updateLabel();
          advance();
        }, Math.max(180, totalMs));
      };
      advance();
    }

    // Helpers de render.
    toWorld(item) {
      const pitchW = 100;
      const pitchH = 65;
      const x = (Number(item.xN) - 0.5) * pitchW;
      const z = (Number(item.yN) - 0.5) * pitchH;
      return { x, z };
    }

    toWorldFromN(xN, yN) {
      const pitchW = 100;
      const pitchH = 65;
      const x = (Number(xN) - 0.5) * pitchW;
      const z = (Number(yN) - 0.5) * pitchH;
      return { x, z };
    }

    parseCssColor(value, fallback = 0xf8fafc) {
      const raw = safeText(value).toLowerCase();
      if (!raw) return { color: fallback, opacity: 1 };
      if (raw.startsWith('#')) {
        const hex = raw.slice(1);
        const full = hex.length === 3
          ? `${hex[0]}${hex[0]}${hex[1]}${hex[1]}${hex[2]}${hex[2]}`
          : hex.slice(0, 6);
        const n = Number.parseInt(full, 16);
        return { color: Number.isFinite(n) ? n : fallback, opacity: 1 };
      }
      const m = raw.match(/rgba?\(([^)]+)\)/);
      if (m) {
        const parts = m[1].split(',').map((p) => Number(String(p).trim()));
        const r = clamp(parts[0] || 248, 0, 255);
        const g = clamp(parts[1] || 250, 0, 255);
        const b = clamp(parts[2] || 252, 0, 255);
        const a = Number.isFinite(parts[3]) ? clamp(parts[3], 0, 1) : 1;
        return { color: (r << 16) + (g << 8) + b, opacity: a };
      }
      return { color: fallback, opacity: 1 };
    }

    buildLine(points, options = {}) {
      const pts = Array.isArray(points) ? points : [];
      if (pts.length < 2) return null;
      const { color, opacity } = this.parseCssColor(options.stroke, 0xf8fafc);
      const dashed = Array.isArray(options.dash) && options.dash.length >= 2;
      const mat = dashed
        ? new THREE.LineDashedMaterial({ color, transparent: opacity < 1, opacity, dashSize: 3, gapSize: 2 })
        : new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity });
      const geo = new THREE.BufferGeometry().setFromPoints(pts.map((p) => new THREE.Vector3(p.x, p.y, p.z)));
      const line = new THREE.Line(geo, mat);
      if (dashed) {
        try { line.computeLineDistances(); } catch (e) {}
      }
      return line;
    }

    buildArrow(points, options = {}) {
      const pts = Array.isArray(points) ? points : [];
      if (pts.length < 2) return null;
      const group = new THREE.Group();
      const line = this.buildLine(pts, options);
      if (line) group.add(line);
      const last = pts[pts.length - 1];
      const prev = pts[pts.length - 2];
      const dir = new THREE.Vector3(last.x - prev.x, 0, last.z - prev.z);
      const len = Math.max(1e-3, dir.length());
      dir.normalize();
      const { color, opacity } = this.parseCssColor(options.stroke, 0xf8fafc);
      const head = new THREE.Mesh(
        new THREE.ConeGeometry(1.2, 3.0, 14),
        new THREE.MeshStandardMaterial({ color, transparent: opacity < 1, opacity, roughness: 0.75, metalness: 0 }),
      );
      head.position.set(last.x, 1.6, last.z);
      // Orienta el cono hacia la dirección (en XZ).
      const yaw = Math.atan2(dir.x, dir.z);
      head.rotation.y = yaw;
      head.rotation.x = Math.PI; // apunta hacia delante
      group.add(head);
      return group;
    }

    buildTextSprite(text, options = {}) {
      const t = safeText(text);
      if (!t) return null;
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const fontSize = 28;
      const padX = 16;
      const padY = 10;
      ctx.font = `800 ${fontSize}px system-ui, -apple-system, Segoe UI, Roboto, Arial`;
      const metrics = ctx.measureText(t);
      canvas.width = Math.ceil(metrics.width + padX * 2);
      canvas.height = fontSize + padY * 2;
      const ctx2 = canvas.getContext('2d');
      ctx2.font = ctx.font;
      ctx2.fillStyle = 'rgba(15,23,42,0.85)';
      ctx2.strokeStyle = 'rgba(255,255,255,0.16)';
      ctx2.lineWidth = 2;
      const r = 14;
      const w = canvas.width;
      const h = canvas.height;
      ctx2.beginPath();
      ctx2.moveTo(r, 0);
      ctx2.arcTo(w, 0, w, h, r);
      ctx2.arcTo(w, h, 0, h, r);
      ctx2.arcTo(0, h, 0, 0, r);
      ctx2.arcTo(0, 0, w, 0, r);
      ctx2.closePath();
      ctx2.fill();
      ctx2.stroke();
      ctx2.fillStyle = 'rgba(248,250,252,0.95)';
      ctx2.textBaseline = 'middle';
      ctx2.fillText(t, padX, h / 2);
      const tex = new THREE.CanvasTexture(canvas);
      tex.minFilter = THREE.LinearFilter;
      tex.magFilter = THREE.LinearFilter;
      const mat = new THREE.SpriteMaterial({ map: tex, transparent: true });
      const sprite = new THREE.Sprite(mat);
      const scale = clamp(canvas.width / 60, 1.6, 6.2);
      sprite.scale.set(scale * 6, scale * 2.3, 1);
      sprite.position.y = 6;
      return sprite;
    }

    createMeshForItem(item) {
      if (!window.THREE) return null;
      const { x, z } = this.toWorld(item);
      if (item.kind === 'ball') {
        const mesh = new THREE.Mesh(
          new THREE.SphereGeometry(1.0, 16, 16),
          new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.6, metalness: 0.0 }),
        );
        mesh.position.set(x, 1.0, z);
        mesh.userData = { kind: 'ball' };
        return mesh;
      }
      if (item.kind === 'cone') {
        const mesh = new THREE.Mesh(
          new THREE.ConeGeometry(1.2, 2.8, 14),
          new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.75, metalness: 0.0 }),
        );
        mesh.position.set(x, 1.4, z);
        mesh.userData = { kind: 'cone' };
        return mesh;
      }
      if (item.kind === 'goal') {
        const mesh = new THREE.Mesh(
          new THREE.BoxGeometry(4.2, 2.0, 1.2),
          new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.95, metalness: 0.0 }),
        );
        mesh.position.set(x, 1.0, z);
        mesh.userData = { kind: 'goal' };
        return mesh;
      }
      if (item.kind === 'token') {
        const tk = safeText(item.token_kind);
        const isRival = tk.includes('rival') || tk === 'player_rival';
        const isGk = tk.includes('goalkeeper');
        const color = isRival ? 0xef4444 : (isGk ? 0xf59e0b : 0x22c55e);
        const mesh = new THREE.Mesh(
          new THREE.CylinderGeometry(1.25, 1.25, 2.6, 18),
          new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.0 }),
        );
        mesh.position.set(x, 1.3, z);
        mesh.userData = { kind: 'token' };
        return mesh;
      }
      if (item.kind === 'polyline' || item.kind === 'arrow-line' || item.kind === 'sim-move') {
        const pointsN = Array.isArray(item.pointsN) ? item.pointsN : [];
        const pts = pointsN
          .slice(0, 240)
          .map((p) => this.toWorldFromN(p.xN, p.yN))
          .map((p) => ({ x: p.x, y: 0.08, z: p.z }));
        const opts = { stroke: item.stroke, dash: item.dash };
        const obj = (item.kind === 'arrow-line' || item.kind === 'sim-move') ? this.buildArrow(pts, opts) : this.buildLine(pts, opts);
        if (!obj) return null;
        obj.userData = { kind: item.kind, static: true };
        return obj;
      }
      if (item.kind === 'zone-rect') {
        const pitchW = 100;
        const pitchH = 65;
        const { color, opacity } = this.parseCssColor(item.fill, 0x22d3ee);
        const w = clamp(Number(item.wN) * pitchW, 2, pitchW);
        const h = clamp(Number(item.hN) * pitchH, 2, pitchH);
        const mesh = new THREE.Mesh(
          new THREE.PlaneGeometry(w, h, 1, 1),
          new THREE.MeshStandardMaterial({ color, transparent: true, opacity: clamp((opacity || 0.12) * 0.55, 0.05, 0.45), roughness: 0.95, metalness: 0 }),
        );
        mesh.rotation.x = -Math.PI / 2;
        const { x: cx, z: cz } = this.toWorldFromN(item.xN, item.yN);
        mesh.position.set(cx, 0.04, cz);
        mesh.userData = { kind: 'zone-rect', static: true };
        return mesh;
      }
      if (item.kind === 'zone-circle') {
        const pitchW = 100;
        const pitchH = 65;
        const { color, opacity } = this.parseCssColor(item.fill, 0x22d3ee);
        const r = clamp(Number(item.rN) * pitchW, 1.6, 26);
        const mesh = new THREE.Mesh(
          new THREE.CircleGeometry(r, 46),
          new THREE.MeshStandardMaterial({ color, transparent: true, opacity: clamp((opacity || 0.12) * 0.55, 0.05, 0.45), roughness: 0.95, metalness: 0 }),
        );
        mesh.rotation.x = -Math.PI / 2;
        const { x: cx, z: cz } = this.toWorldFromN(item.xN, item.yN);
        mesh.position.set(cx, 0.04, cz);
        mesh.userData = { kind: 'zone-circle', static: true };
        return mesh;
      }
      if (item.kind === 'text') {
        const sprite = this.buildTextSprite(item.text);
        if (!sprite) return null;
        const { x: cx, z: cz } = this.toWorldFromN(item.xN, item.yN);
        sprite.position.x = cx;
        sprite.position.z = cz;
        sprite.userData = { kind: 'text', static: true };
        return sprite;
      }
      return null;
    }

    applyTransition(now) {
      if (!this.transition) return;
      const t = this.transition;
      const progress = clamp((now - t.startAt) / (t.dur || 1), 0, 1);
      const ease = progress < 0.5 ? (2 * progress * progress) : (1 - Math.pow(-2 * progress + 2, 2) / 2);
      t.nextMap.forEach((nextItem, k) => {
        const mesh = this.meshByKey.get(k);
        if (!mesh) return;
        const prevItem = t.prevMap.get(k) || nextItem;
        const kind = safeText(mesh?.userData?.kind);
        const isDynamic = (kind === 'token' || kind === 'ball' || kind === 'cone' || kind === 'goal');
        if (!isDynamic) return;
        const a = this.toWorld(prevItem);
        const b = this.toWorld(nextItem);
        mesh.position.x = a.x + (b.x - a.x) * ease;
        mesh.position.z = a.z + (b.z - a.z) * ease;
      });
      if (progress >= 1) this.transition = null;
    }

    tick() {
      if (!this.renderer || !this.scene || !this.camera) return;
      const now = performance.now();
      this.applyTransition(now);
      this.renderer.render(this.scene, this.camera);
      this.animFrame = requestAnimationFrame(this.tick);
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('task-builder-form');
    const openBtn = document.getElementById('task-sim-view-3d');
    const modal = document.getElementById('task-sim-3d-modal');
    const closeBtn = document.getElementById('task-sim-3d-close');
    const canvas = document.getElementById('task-sim-3d-canvas');
    const labelEl = document.getElementById('task-sim-3d-step-label');
    const prevBtn = document.getElementById('task-sim-3d-prev');
    const nextBtn = document.getElementById('task-sim-3d-next');
    const playBtn = document.getElementById('task-sim-3d-play');
    const speedEl = document.getElementById('task-sim-3d-speed');
    const fullscreenBtn = document.getElementById('task-sim-3d-fullscreen');
    const recordBtn = document.getElementById('task-sim-3d-record');
    if (!openBtn || !modal || !canvas) return;

    let viewer = null;
    let recorder = null;
    let recordChunks = [];
    let recordStream = null;
    let recording = false;

    const canRecord = () => {
      try {
        return typeof canvas.captureStream === 'function' && typeof window.MediaRecorder !== 'undefined';
      } catch (e) {
        return false;
      }
    };

    const downloadBlob = (blob, filename) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename || `tactical_${Date.now()}.webm`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => {
        try { URL.revokeObjectURL(url); } catch (e) {}
      }, 2500);
    };

    const fileSafeSlug = (value) => safeText(value || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'tactica';

    const setRecordUi = (isOn) => {
      recording = !!isOn;
      if (recordBtn) {
        recordBtn.textContent = recording ? 'Parar' : 'Grabar vídeo';
        recordBtn.classList.toggle('danger', recording);
      }
    };

    const stopRecording = async () => {
      if (!recorder) return;
      try { recorder.stop(); } catch (e) {}
    };

    const startRecording = () => {
      if (!canRecord()) {
        window.alert('Tu navegador no soporta grabación de vídeo aquí. Prueba en Chrome/desktop.');
        return;
      }
      recordChunks = [];
      try {
        recordStream = canvas.captureStream(30);
      } catch (e) {
        recordStream = null;
      }
      if (!recordStream) {
        window.alert('No se pudo iniciar la captura de vídeo.');
        return;
      }
      const mimeCandidates = [
        'video/webm;codecs=vp9,opus',
        'video/webm;codecs=vp8,opus',
        'video/webm',
      ];
      let mimeType = '';
      mimeCandidates.some((mt) => {
        try {
          if (window.MediaRecorder.isTypeSupported(mt)) {
            mimeType = mt;
            return true;
          }
        } catch (e) {}
        return false;
      });
      try {
        recorder = new window.MediaRecorder(recordStream, mimeType ? { mimeType } : undefined);
      } catch (e) {
        recorder = null;
      }
      if (!recorder) {
        window.alert('No se pudo crear el grabador de vídeo.');
        return;
      }
      recorder.ondataavailable = (ev) => {
        if (ev?.data && ev.data.size > 0) recordChunks.push(ev.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(recordChunks, { type: recorder?.mimeType || 'video/webm' });
        const title = fileSafeSlug(document.querySelector('[name="draw_task_title"]')?.value || 'tactica');
        downloadBlob(blob, `${title}-3d.webm`);
        try { recordStream?.getTracks?.().forEach((t) => t.stop()); } catch (e) {}
        recorder = null;
        recordStream = null;
        recordChunks = [];
        setRecordUi(false);
      };
      try { recorder.start(250); } catch (e) {
        window.alert('No se pudo iniciar la grabación.');
        recorder = null;
        recordStream = null;
        recordChunks = [];
        return;
      }
      setRecordUi(true);
    };

    const toggleRecording = () => {
      if (recording) return stopRecording();
      return startRecording();
    };

    const isFullscreen = () => {
      try { return !!document.fullscreenElement; } catch (e) { return false; }
    };
    const setFsUi = () => {
      if (!fullscreenBtn) return;
      fullscreenBtn.textContent = isFullscreen() ? 'Salir pantalla completa' : 'Pantalla completa';
    };
    const toggleFullscreen = async () => {
      const target = modal?.querySelector('.sim-3d-card') || modal;
      try {
        if (!isFullscreen()) {
          await target.requestFullscreen();
        } else {
          await document.exitFullscreen();
        }
      } catch (e) {
        window.alert('No se pudo activar pantalla completa.');
      }
      setFsUi();
    };

    const buildSteps = () => {
      const dims = readCanvasDims(form);
      const simSteps = readSimSteps(form);
      if (simSteps.length) {
        return simSteps.map((step, idx) => {
          const state = (step && typeof step === 'object') ? step.canvas_state : null;
          return {
            title: safeText(step?.title, `Paso ${idx + 1}`),
            duration: clamp(Number(step?.duration) || 3, 1, 20),
            items: extractRenderable(state, dims, { moves: step?.moves }),
          };
        }).filter((s) => Array.isArray(s.items));
      }
      // Fallback: estado actual como único paso.
      const state = readCanvasState(form);
      return [{
        title: 'Estado actual',
        duration: 4,
        items: extractRenderable(state, dims),
      }];
    };

    const open = () => {
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      const steps = buildSteps();
      if (!viewer) {
        viewer = new Sim3DViewer(canvas, labelEl, speedEl);
        try { viewer.init(); } catch (e) {
          modal.hidden = true;
          document.body.style.overflow = '';
          window.alert('No se pudo abrir la vista 3D (tu navegador no soporta WebGL o falta Three.js).');
          viewer = null;
          return;
        }
      }
      viewer.setSteps(steps);
      viewer.stepIndex = 0;
      viewer.setStep(0, { transitionMs: 1 });
      viewer.updateLabel();
      if (playBtn) playBtn.textContent = 'Reproducir';
      setFsUi();
      setRecordUi(false);
      if (recordBtn) recordBtn.disabled = !canRecord();
    };

    const close = () => {
      modal.hidden = true;
      document.body.style.overflow = '';
      if (viewer) viewer.stop();
      if (playBtn) playBtn.textContent = 'Reproducir';
      if (recording) {
        try { stopRecording(); } catch (e) {}
      }
    };

    openBtn.addEventListener('click', () => {
      try { open(); } catch (e) { window.alert('No se pudo abrir la vista 3D.'); }
    });
    closeBtn?.addEventListener('click', close);
    modal.addEventListener('click', (ev) => {
      if (ev.target === modal) close();
    });
    prevBtn?.addEventListener('click', () => {
      if (!viewer) return;
      viewer.stop();
      viewer.stepIndex = clamp(viewer.stepIndex - 1, 0, Math.max(0, viewer.steps.length - 1));
      viewer.setStep(viewer.stepIndex, { transitionMs: 320 });
      if (playBtn) playBtn.textContent = 'Reproducir';
    });
    nextBtn?.addEventListener('click', () => {
      if (!viewer) return;
      viewer.stop();
      viewer.stepIndex = clamp(viewer.stepIndex + 1, 0, Math.max(0, viewer.steps.length - 1));
      viewer.setStep(viewer.stepIndex, { transitionMs: 320 });
      if (playBtn) playBtn.textContent = 'Reproducir';
    });
    playBtn?.addEventListener('click', () => {
      if (!viewer) return;
      viewer.play();
      playBtn.textContent = viewer.playing ? 'Parar' : 'Reproducir';
    });
    fullscreenBtn?.addEventListener('click', () => {
      void toggleFullscreen();
    });
    recordBtn?.addEventListener('click', () => {
      void toggleRecording();
    });
    document.addEventListener('fullscreenchange', () => {
      setFsUi();
    });
    document.addEventListener('keydown', (ev) => {
      if (modal.hidden) return;
      if (ev.key === 'Escape') close();
    });
  });
})();
