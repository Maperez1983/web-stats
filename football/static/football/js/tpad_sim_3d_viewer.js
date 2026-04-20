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
    if (kind === 'token') {
      const pid = safeText(data.playerId);
      const num = safeText(data.playerNumber);
      const tkind = safeText(data.token_kind);
      return `token:${tkind}:${pid || num || index}`;
    }
    const id = safeText(obj?.id);
    return `${kind || obj?.type || 'obj'}:${id || index}`;
  };

  const extractRenderable = (state, dims) => {
    const objects = Array.isArray(state?.objects) ? state.objects : [];
    const out = [];
    objects.forEach((obj, index) => {
      const data = obj?.data || {};
      const kind = safeText(data.kind);
      const left = Number(obj?.left);
      const top = Number(obj?.top);
      if (!Number.isFinite(left) || !Number.isFinite(top)) return;
      const xN = clamp(left / (dims.w || 1280), 0, 1);
      const yN = clamp(top / (dims.h || 720), 0, 1);

      // Filtra a lo útil.
      if (kind === 'token') {
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
        out.push({ k: keyForObject(obj, index), kind: 'ball', xN, yN });
        return;
      }
      if (kind === 'cone' || kind === 'cone_striped') {
        out.push({ k: keyForObject(obj, index), kind: 'cone', xN, yN });
        return;
      }
      if (kind === 'goal') {
        out.push({ k: keyForObject(obj, index), kind: 'goal', xN, yN, angle: Number(obj?.angle) || 0 });
      }
    });
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

    createMeshForItem(item) {
      if (!window.THREE) return null;
      const { x, z } = this.toWorld(item);
      if (item.kind === 'ball') {
        const mesh = new THREE.Mesh(
          new THREE.SphereGeometry(1.0, 16, 16),
          new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.6, metalness: 0.0 }),
        );
        mesh.position.set(x, 1.0, z);
        return mesh;
      }
      if (item.kind === 'cone') {
        const mesh = new THREE.Mesh(
          new THREE.ConeGeometry(1.2, 2.8, 14),
          new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.75, metalness: 0.0 }),
        );
        mesh.position.set(x, 1.4, z);
        return mesh;
      }
      if (item.kind === 'goal') {
        const mesh = new THREE.Mesh(
          new THREE.BoxGeometry(4.2, 2.0, 1.2),
          new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.95, metalness: 0.0 }),
        );
        mesh.position.set(x, 1.0, z);
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
        return mesh;
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
        const a = this.toWorld(prevItem);
        const b = this.toWorld(nextItem);
        const x = a.x + (b.x - a.x) * ease;
        const z = a.z + (b.z - a.z) * ease;
        mesh.position.x = x;
        mesh.position.z = z;
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
    if (!openBtn || !modal || !canvas) return;

    let viewer = null;

    const buildSteps = () => {
      const dims = readCanvasDims(form);
      const simSteps = readSimSteps(form);
      if (simSteps.length) {
        return simSteps.map((step, idx) => {
          const state = (step && typeof step === 'object') ? step.canvas_state : null;
          return {
            title: safeText(step?.title, `Paso ${idx + 1}`),
            duration: clamp(Number(step?.duration) || 3, 1, 20),
            items: extractRenderable(state, dims),
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
    };

    const close = () => {
      modal.hidden = true;
      document.body.style.overflow = '';
      if (viewer) viewer.stop();
      if (playBtn) playBtn.textContent = 'Reproducir';
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
    document.addEventListener('keydown', (ev) => {
      if (modal.hidden) return;
      if (ev.key === 'Escape') close();
    });
  });
})();

