import * as THREE from '../../vendor/three/build/three.module.js';
import { GLTFLoader } from '../../vendor/three/examples/jsm/loaders/GLTFLoader.js';
import { SkeletonUtils } from '../../vendor/three/examples/jsm/utils/SkeletonUtils.js';

(function () {
  const payloadEl = document.getElementById('task-detail-3d-payload');
  const sceneHost = document.getElementById('task-detail-3d-inline');
  const canvas = document.getElementById('task-detail-3d-canvas');
  const openBtn = document.getElementById('task-detail-3d-open');
  const enterEditBtn = document.getElementById('task-detail-enter-edit');
  const enterEditEmptyBtn = document.getElementById('task-detail-enter-edit-empty');
  const openSequenceBtn = document.getElementById('task-detail-open-sequence');
  const focusEditorBtn = document.getElementById('task-detail-focus-editor');
  if (!payloadEl || !sceneHost || !canvas) return;
  canvas.dataset.ollanaSurface = 'task-3d-scene';
  canvas.dataset.ollanaLabel = 'Representacion 3D de tarea';
  const sceneCard = canvas.closest('.sim-3d-card');

  const byId = (id) => document.getElementById(id);
  const prevBtn = byId('task-detail-3d-prev');
  const nextBtn = byId('task-detail-3d-next');
  const playBtn = byId('task-detail-3d-play');
  const snapBtn = byId('task-detail-3d-snap');
  const cameraSelect = byId('task-detail-3d-camera');
  const titleEl = byId('task-detail-3d-step-title');
  const metaEl = byId('task-detail-3d-step-meta');
  const fullBtn = byId('task-detail-3d-fullscreen');
  const recordBtn = byId('task-detail-3d-record');
  const progressBar = byId('task-detail-3d-progress-bar');
  const progressLabel = byId('task-detail-3d-progress-label');
  const fallbackEl = byId('task-detail-3d-fallback');
  const fallbackPreviewEl = byId('task-detail-3d-fallback-preview');
  const fallbackStatusEl = byId('task-detail-3d-fallback-status');
  const fallbackReasonEl = byId('task-detail-3d-fallback-reason');

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const lerp = (a, b, t) => a + ((b - a) * t);
  const smooth = (t) => t * t * (3 - (2 * t));
  const normalizeAngle = (angle) => {
    let value = angle % (Math.PI * 2);
    if (value <= -Math.PI) value += Math.PI * 2;
    if (value > Math.PI) value -= Math.PI * 2;
    return value;
  };
  const lerpAngle = (from, to, t) => {
    const normalizedFrom = normalizeAngle(from);
    const normalizedTo = normalizeAngle(to);
    let delta = normalizedTo - normalizedFrom;
    if (delta > Math.PI) delta -= Math.PI * 2;
    if (delta < -Math.PI) delta += Math.PI * 2;
    return normalizeAngle(normalizedFrom + (delta * clamp(t, 0, 1)));
  };
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const __seatTextureCache = new Map();
  const toNumber = (value, fallback = 0) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  };
  const getSeatPatternTexture = (baseHex = '#1f63d6', accentHex = '#0d3f9c') => {
    const key = `${baseHex}|${accentHex}`;
    if (__seatTextureCache.has(key)) return __seatTextureCache.get(key);
    const offscreen = document.createElement('canvas');
    offscreen.width = 256;
    offscreen.height = 128;
    const ctx = offscreen.getContext('2d');
    ctx.clearRect(0, 0, offscreen.width, offscreen.height);
    ctx.fillStyle = baseHex;
    ctx.fillRect(0, 0, offscreen.width, offscreen.height);
    for (let i = 0; i < 8; i += 1) {
      const x = i * 32;
      ctx.fillStyle = accentHex;
      ctx.fillRect(x + 3, 22, 26, 72);
      ctx.fillStyle = 'rgba(255,255,255,0.18)';
      ctx.fillRect(x + 6, 26, 20, 5);
      ctx.fillStyle = 'rgba(255,255,255,0.10)';
      ctx.fillRect(x + 7, 54, 18, 18);
      ctx.fillStyle = 'rgba(6,14,30,0.22)';
      ctx.fillRect(x + 1, 22, 2, 72);
      ctx.fillRect(x + 29, 22, 2, 72);
      ctx.fillRect(x + 3, 94, 26, 4);
    }
    const texture = new THREE.CanvasTexture(offscreen);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(10, 2);
    texture.anisotropy = 8;
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    __seatTextureCache.set(key, texture);
    return texture;
  };

  let payload = {};
  try {
    payload = JSON.parse(payloadEl.textContent || '{}');
  } catch (error) {
    payload = {};
  }
  const playerModelUrl = safeText(payload.playerModelUrl);
  const pitch3dContext = payload.pitch3dContext && typeof payload.pitch3dContext === 'object'
    ? payload.pitch3dContext
    : {};
  const stadiumPalette = (() => {
    const palette = pitch3dContext.stadiumPalette && typeof pitch3dContext.stadiumPalette === 'object'
      ? pitch3dContext.stadiumPalette
      : {};
    return {
      primary: safeText(palette.primary, '#047857'),
      secondary: safeText(palette.secondary, '#f8fafc'),
      accent: safeText(palette.accent, '#073b32'),
    };
  })();
  const stadiumAds = (() => {
    const ads = pitch3dContext.stadiumAds && typeof pitch3dContext.stadiumAds === 'object'
      ? pitch3dContext.stadiumAds
      : {};
    const teamName = safeText(pitch3dContext.teamName, 'Club');
    return {
      top: safeText(ads.top, teamName || 'Club'),
      right: safeText(ads.right, '2J Football Intelligence'),
      bottom: safeText(ads.bottom, teamName || 'Club'),
      left: safeText(ads.left, 'Partner'),
      teamName,
    };
  })();

  const buildSteps = () => {
    const steps = [];
    const animationFrames = Array.isArray(payload.animationFrames) ? payload.animationFrames : [];
    const normalizeFrameState = (state) => {
      if (!state || typeof state !== 'object') return null;
      const objects = Array.isArray(state.objects) ? state.objects : (
        Array.isArray(state._objects) ? state._objects : (Array.isArray(state.tokens) ? state.tokens : null)
      );
      return {
        ...state,
        objects: Array.isArray(objects) ? objects : [],
      };
    };
    const parseCanvasState = (frame) => {
      if (!frame || typeof frame !== 'object') return null;
      let rawState = frame.canvas_state;
      if (typeof rawState === 'string') {
        try {
          rawState = JSON.parse(rawState);
        } catch (error) {
          rawState = null;
        }
      }
      if (!rawState || typeof rawState !== 'object') {
        rawState = frame.state;
        if (typeof rawState === 'string') {
          try {
            rawState = JSON.parse(rawState);
          } catch (error) {
            rawState = null;
          }
        }
      }
      if (!rawState || typeof rawState !== 'object') return null;
      return normalizeFrameState(rawState);
    };
    animationFrames.forEach((frame, index) => {
      const state = parseCanvasState(frame);
      if (!state) return;
      steps.push({
        title: safeText(frame.title, `Fase ${index + 1}`),
        duration: Math.max(1, toNumber(frame.duration, 4)),
        state,
      });
    });
    if (steps.length) return steps;
    const editor = payload.graphicEditorState && typeof payload.graphicEditorState === 'object'
      ? payload.graphicEditorState
      : {};
    const state = parseCanvasState(editor);
    if (state && state.objects.length) {
      steps.push({
        title: safeText(payload.taskTitle, 'Pizarra'),
        duration: 4,
        state,
      });
    }
    return steps;
  };

  const steps = buildSteps();
  if (!steps.length) {
    openBtn.disabled = true;
    openBtn.title = 'Esta tarea no tiene pizarra 3D disponible';
    return;
  }

  const firstState = steps[0].state || {};
  const stateMeta = {
    width: Math.max(320, toNumber(
      payload.canvasWidth
      || firstState.width
      || firstState.canvas_width
      || (payload.graphicEditorState || {}).canvas_width
      || (payload.graphicEditorState || {}).width,
      1280
    )),
    height: Math.max(180, toNumber(
      payload.canvasHeight
      || firstState.height
      || firstState.canvas_height
      || (payload.graphicEditorState || {}).canvas_height
      || (payload.graphicEditorState || {}).height,
      720
    )),
    fieldWidth: 105,
    fieldHeight: 68,
  };

  const setFallbackStatus = (message, reason = '') => {
    if (fallbackStatusEl) fallbackStatusEl.textContent = safeText(message, 'Vista alternativa disponible.');
    if (fallbackReasonEl) {
      const cleanReason = safeText(reason, '');
      fallbackReasonEl.textContent = cleanReason ? `Motivo detectado: ${cleanReason}` : '';
      fallbackReasonEl.hidden = !Boolean(cleanReason);
      fallbackReasonEl.style.display = cleanReason ? 'block' : 'none';
    }
  };
  const setControlsDisabled = (disabled) => {
    [prevBtn, nextBtn, playBtn, fullBtn, recordBtn, cameraSelect].forEach((control) => {
      if (!control) return;
      control.disabled = !!disabled;
    });
  };
  const syncFallbackPreview = () => {
    if (!fallbackPreviewEl) return false;
    try {
      const previewImg = document.getElementById('task-preview-image');
      if (previewImg && previewImg.getAttribute('src')) {
        fallbackPreviewEl.src = previewImg.getAttribute('src');
        fallbackPreviewEl.hidden = false;
        return true;
      }
      const sourceCanvas = document.getElementById('task-graphic-canvas');
      if (!sourceCanvas || !sourceCanvas.width || !sourceCanvas.height) return false;
      fallbackPreviewEl.src = sourceCanvas.toDataURL('image/png');
      fallbackPreviewEl.hidden = false;
      return true;
    } catch (error) {
      return false;
    }
  };
  const activateFallback = (reason) => {
    canvas.hidden = true;
    fallbackEl?.removeAttribute('hidden');
    sceneCard?.setAttribute('data-render-mode', 'fallback');
    titleEl && (titleEl.textContent = 'Vista alternativa');
    metaEl && (metaEl.textContent = '3D no disponible');
    progressLabel && (progressLabel.textContent = '-');
    if (progressBar) progressBar.style.width = '0%';
    setControlsDisabled(true);
    recordBtn && (recordBtn.title = 'El modo 3D no está disponible en este dispositivo');
    setFallbackStatus(
      'El visor 3D no pudo iniciarse. Se muestra la pizarra base como referencia.',
      safeText(reason, 'Recurso 3D no disponible en este entorno.')
    );
    const copied = syncFallbackPreview();
    if (!copied) {
      window.setTimeout(syncFallbackPreview, 300);
      window.setTimeout(syncFallbackPreview, 1200);
    }
    const root = window.__ollanaDiagnostics && typeof window.__ollanaDiagnostics === 'object'
      ? window.__ollanaDiagnostics
      : {};
    if (!root.render_surfaces || typeof root.render_surfaces !== 'object') root.render_surfaces = {};
    root.render_surfaces[canvas.id || 'task-detail-3d-canvas'] = {
      id: canvas.id || 'task-detail-3d-canvas',
      label: 'Representacion 3D de tarea',
      kind: 'three_scene',
      visible: true,
      webgl_context: '',
      scene_status: 'fallback_2d',
      issue: 'webgl_unavailable',
      step_index: 0,
      step_count: steps.length,
      object_count: Array.isArray((steps[0] || {}).state?.objects) ? steps[0].state.objects.length : 0,
      reason: safeText(reason, 'webgl_unavailable'),
    };
    window.__ollanaDiagnostics = root;
  };

  let renderer = null;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
  } catch (error) {
    activateFallback('Este navegador no ha podido crear el contexto WebGL necesario para la representación 3D.');
    openBtn?.addEventListener('click', (event) => {
      event.preventDefault();
      sceneHost.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    snapBtn?.addEventListener('click', (event) => {
      event.preventDefault();
      syncFallbackPreview();
      const src = fallbackPreviewEl?.getAttribute('src') || '';
      if (!src) return;
      const link = document.createElement('a');
      link.href = src;
      link.download = `tarea-vista-alternativa-${Date.now()}.png`;
      link.click();
    });
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.16;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xaed6f3);
  scene.fog = new THREE.Fog(0xa3cdef, 190, 420);

  const camera = new THREE.PerspectiveCamera(42, 16 / 9, 0.1, 500);
  const root = new THREE.Group();
  const dynamicRoot = new THREE.Group();
  scene.add(root);
  scene.add(dynamicRoot);

  const cameraPresets = {
    broadcast: { theta: -0.76, phi: 0.94, radius: 146, targetX: -6, targetZ: 4 },
    tactic: { theta: 0.02, phi: 0.48, radius: 84, targetX: 0, targetZ: 0 },
    corner: { theta: -0.95, phi: 0.92, radius: 104, targetX: 10, targetZ: -4 },
    goal: { theta: Math.PI, phi: 0.76, radius: 74, targetX: 0, targetZ: 18 },
    drone: { theta: -0.01, phi: 0.16, radius: 70, targetX: 0, targetZ: 0 },
    top_h: { theta: 0, phi: 0.14, radius: 128, targetX: 0, targetZ: 0 },
    top_v: { theta: Math.PI / 2, phi: 0.14, radius: 128, targetX: 0, targetZ: 0 },
    tunnel: { theta: -1.55, phi: 1.08, radius: 88, targetX: -12, targetZ: 0 },
    analyst: { theta: -0.72, phi: 1.18, radius: 88, targetX: -3, targetZ: 6 },
    coach: { theta: -0.9, phi: 1.18, radius: 80, targetX: -6, targetZ: 10 },
    rosaleda: { theta: -0.94, phi: 0.92, radius: 142, targetX: -8, targetZ: 6 },
  };
  const orbit = { ...cameraPresets.broadcast };
  let currentPreset = 'broadcast';
  let currentStepIndex = 0;
  let isPlaying = false;
  let rafId = null;
  let dragging = null;
  let playbackState = null;
  let progress = 0;
  let lastFrameTs = 0;
  let activeWorld = null;
  let mediaRecorder = null;
  let recordingChunks = [];
  let isRecording = false;
  let stadiumLoadPromise = null;
  let stadiumScene = null;
  let playerModelLoadPromise = null;
  let playerModelAsset = null;
  let renderFrameCount = 0;
  let lastRenderAt = 0;
  const modelMixers = new Set();
  const ollanaDiagnostics = (() => {
    const root = window.__ollanaDiagnostics && typeof window.__ollanaDiagnostics === 'object'
      ? window.__ollanaDiagnostics
      : {};
    if (!root.render_surfaces || typeof root.render_surfaces !== 'object') root.render_surfaces = {};
    window.__ollanaDiagnostics = root;
    return root;
  })();

  const publishRenderDiagnostics = (extra = {}) => {
    const key = canvas.id || 'task-detail-3d-canvas';
    const currentStep = steps[currentStepIndex] || steps[0] || {};
    const currentState = currentStep && typeof currentStep.state === 'object' ? currentStep.state : {};
    const stepObjects = Array.isArray(currentState.objects) ? currentState.objects : [];
    const rect = canvas.getBoundingClientRect();
    const renderCalls = Number(renderer?.info?.render?.calls || 0);
    const triangleCount = Number(renderer?.info?.render?.triangles || 0);
    const pointsCount = Number(renderer?.info?.render?.points || 0);
    const linesCount = Number(renderer?.info?.render?.lines || 0);
    const contextType = (() => {
      try {
        const gl = renderer.getContext?.();
        if (!gl) return '';
        const name = gl.constructor && gl.constructor.name ? String(gl.constructor.name) : '';
        if (/webgl2/i.test(name)) return 'webgl2';
        return 'webgl';
      } catch (error) {
        return '';
      }
    })();
    const worldPlayers = activeWorld?.tokens instanceof Map ? activeWorld.tokens.size : 0;
    const worldBalls = activeWorld?.balls instanceof Map ? activeWorld.balls.size : 0;
    const worldCones = activeWorld?.cones instanceof Map ? activeWorld.cones.size : 0;
    const worldPaths = Array.isArray(activeWorld?.paths) ? activeWorld.paths.length : 0;
    const worldNotes = Array.isArray(activeWorld?.notes) ? activeWorld.notes.length : 0;
    const sceneStatus = !steps.length
      ? 'missing_steps'
      : (!activeWorld
        ? 'initializing'
        : (stepObjects.length
          ? 'rendering'
          : 'empty_scene'));
    let issue = '';
    if (!steps.length) issue = 'no_3d_steps';
    else if (!contextType) issue = 'webgl_unavailable';
    else if (rect.width > 0 && rect.height > 0 && !stepObjects.length) issue = 'scene_has_no_objects';
    else if (renderFrameCount < 2) issue = 'scene_not_rendering_yet';
    ollanaDiagnostics.render_surfaces[key] = {
      id: key,
      label: 'Representacion 3D de tarea',
      kind: 'three_scene',
      modal_open: false,
      visible: Boolean(rect.width > 0 && rect.height > 0),
      webgl_context: contextType,
      scene_status: sceneStatus,
      issue,
      step_index: currentStepIndex,
      step_count: steps.length,
      object_count: stepObjects.length,
      player_count: worldPlayers,
      ball_count: worldBalls,
      cone_count: worldCones,
      path_count: worldPaths,
      note_count: worldNotes,
      render_calls: renderCalls,
      triangle_count: triangleCount,
      points_count: pointsCount,
      lines_count: linesCount,
      rendered_frames: renderFrameCount,
      canvas_width: Math.max(0, Math.round(rect.width || 0)),
      canvas_height: Math.max(0, Math.round(rect.height || 0)),
      buffer_width: Math.max(0, Math.round(canvas.width || 0)),
      buffer_height: Math.max(0, Math.round(canvas.height || 0)),
      last_render_at: lastRenderAt,
      ...extra,
    };
  };

  const canvasTexture = (() => {
    const offscreen = document.createElement('canvas');
    offscreen.width = 1024;
    offscreen.height = 768;
    const ctx = offscreen.getContext('2d');
    const stripeColors = ['#6a9c42', '#76aa49', '#82b553', '#78ab4c', '#6e9f46', '#62923e'];
    const stripeH = offscreen.height / stripeColors.length;
    stripeColors.forEach((color, index) => {
      ctx.fillStyle = color;
      ctx.fillRect(0, stripeH * index, offscreen.width, stripeH + 2);
    });
    for (let i = 0; i < 4000; i += 1) {
      const alpha = Math.random() * 0.025;
      ctx.fillStyle = `rgba(255,255,255,${alpha})`;
      ctx.fillRect(Math.random() * offscreen.width, Math.random() * offscreen.height, 1.5, 1.5);
    }
    ctx.fillStyle = 'rgba(255,255,255,0.045)';
    for (let x = 0; x < offscreen.width; x += 112) {
      ctx.fillRect(x, 0, 2, offscreen.height);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 3;
    for (let y = 38; y < offscreen.height; y += 92) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(offscreen.width, y);
      ctx.stroke();
    }
    return new THREE.CanvasTexture(offscreen);
  })();
  canvasTexture.wrapS = THREE.ClampToEdgeWrapping;
  canvasTexture.wrapT = THREE.ClampToEdgeWrapping;
  canvasTexture.colorSpace = THREE.SRGBColorSpace;

  const skyTexture = (() => {
    const offscreen = document.createElement('canvas');
    offscreen.width = 1024;
    offscreen.height = 512;
    const ctx = offscreen.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, offscreen.height);
    grad.addColorStop(0, '#8cc2f7');
    grad.addColorStop(0.42, '#b9dcff');
    grad.addColorStop(1, '#eef6ff');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, offscreen.width, offscreen.height);
    for (let i = 0; i < 18; i += 1) {
      const x = Math.random() * offscreen.width;
      const y = 30 + Math.random() * 180;
      const w = 90 + Math.random() * 180;
      const h = 28 + Math.random() * 46;
      ctx.fillStyle = 'rgba(255,255,255,0.72)';
      ctx.beginPath();
      ctx.ellipse(x, y, w * 0.32, h * 0.5, 0, 0, Math.PI * 2);
      ctx.ellipse(x - w * 0.22, y + 6, w * 0.24, h * 0.42, 0, 0, Math.PI * 2);
      ctx.ellipse(x + w * 0.24, y + 8, w * 0.28, h * 0.44, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    const texture = new THREE.CanvasTexture(offscreen);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  })();

  const skyDome = new THREE.Mesh(
    new THREE.SphereGeometry(260, 48, 32),
    new THREE.MeshBasicMaterial({ map: skyTexture, side: THREE.BackSide, fog: false })
  );
  skyDome.position.y = 20;
  root.add(skyDome);

  const pitchPlane = new THREE.Mesh(
    new THREE.PlaneGeometry(stateMeta.fieldWidth, stateMeta.fieldHeight),
    new THREE.MeshStandardMaterial({ map: canvasTexture, roughness: 0.96, metalness: 0.02 })
  );
  pitchPlane.rotation.x = -Math.PI / 2;
  pitchPlane.receiveShadow = true;
  root.add(pitchPlane);

  const apron = new THREE.Mesh(
    new THREE.RingGeometry(stateMeta.fieldWidth * 0.54, stateMeta.fieldWidth * 0.67, 80),
    new THREE.MeshStandardMaterial({ color: 0x323c46, roughness: 0.96, metalness: 0.02 })
  );
  apron.rotation.x = -Math.PI / 2;
  apron.position.y = -0.01;
  apron.scale.set(1, stateMeta.fieldHeight / stateMeta.fieldWidth, 1);
  root.add(apron);

  const stadiumRoot = new THREE.Group();
  root.add(stadiumRoot);

  const outerGlow = new THREE.Mesh(
    new THREE.CircleGeometry(95, 96),
    new THREE.MeshBasicMaterial({ color: 0x1a2432, transparent: true, opacity: 0.55 })
  );
  outerGlow.rotation.x = -Math.PI / 2;
  outerGlow.position.y = -0.08;
  root.add(outerGlow);

  const skyRing = new THREE.Mesh(
    new THREE.CylinderGeometry(88, 88, 28, 72, 1, true),
    new THREE.MeshBasicMaterial({
      color: 0x85b4ea,
      transparent: true,
      opacity: 0.12,
      side: THREE.DoubleSide,
    })
  );
  skyRing.position.y = 13;
  root.add(skyRing);

  const addPitchBoards = () => {
    const boardGroup = new THREE.Group();
    const boardTextures = [
      { bg: stadiumPalette.primary, fg: stadiumPalette.secondary, text: stadiumAds.top || stadiumAds.teamName || 'Club' },
      { bg: stadiumPalette.accent, fg: stadiumPalette.secondary, text: stadiumAds.right || '2J Football Intelligence' },
      { bg: stadiumPalette.primary, fg: stadiumPalette.secondary, text: stadiumAds.bottom || stadiumAds.teamName || 'Club' },
      { bg: stadiumPalette.accent, fg: stadiumPalette.secondary, text: stadiumAds.left || 'Partner' },
      { bg: stadiumPalette.primary, fg: stadiumPalette.secondary, text: safeText(payload.taskTitle, stadiumAds.teamName || 'Task') },
    ].map((item) => {
      const off = document.createElement('canvas');
      off.width = 1024;
      off.height = 96;
      const ctx = off.getContext('2d');
      ctx.fillStyle = item.bg;
      ctx.fillRect(0, 0, off.width, off.height);
      ctx.fillStyle = item.fg;
      ctx.font = '900 46px Montserrat, Arial, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      for (let x = 96; x < off.width; x += 184) {
        ctx.fillText(item.text, x, off.height / 2);
      }
      const texture = new THREE.CanvasTexture(off);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.needsUpdate = true;
      return texture;
    });
    const lengths = [
      { width: stateMeta.fieldWidth + 8, z: -(stateMeta.fieldHeight / 2) - 2.1, rot: 0 },
      { width: stateMeta.fieldWidth + 8, z: (stateMeta.fieldHeight / 2) + 2.1, rot: Math.PI },
      { width: stateMeta.fieldHeight + 2, x: -(stateMeta.fieldWidth / 2) - 2.1, rot: Math.PI / 2 },
      { width: stateMeta.fieldHeight + 2, x: (stateMeta.fieldWidth / 2) + 2.1, rot: -Math.PI / 2 },
    ];
    lengths.forEach((item, index) => {
      const boardMat = new THREE.MeshBasicMaterial({ map: boardTextures[index % boardTextures.length], side: THREE.DoubleSide });
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(item.width, 1.4), boardMat);
      mesh.position.set(item.x || 0, 0.9, item.z || 0);
      mesh.rotation.y = item.rot;
      boardGroup.add(mesh);
    });
    root.add(boardGroup);
  };
  addPitchBoards();

  const addPitchPerimeterDetails = () => {
    const detailGroup = new THREE.Group();
    const cornerFlagMat = new THREE.MeshStandardMaterial({ color: 0x1d4ed8, roughness: 0.5 });
    const cornerPoleMat = new THREE.MeshStandardMaterial({ color: 0xe5e7eb, roughness: 0.7 });
    const addCornerFlag = (x, z, rotY) => {
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 1.5, 10), cornerPoleMat);
      pole.position.set(x, 0.75, z);
      detailGroup.add(pole);
      const cloth = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.42), cornerFlagMat);
      cloth.position.set(x + Math.cos(rotY) * 0.24, 1.28, z + Math.sin(rotY) * 0.24);
      cloth.rotation.y = rotY;
      detailGroup.add(cloth);
    };
    const hw = stateMeta.fieldWidth / 2;
    const hh = stateMeta.fieldHeight / 2;
    addCornerFlag(-hw + 0.15, -hh + 0.15, 0.2);
    addCornerFlag(hw - 0.15, -hh + 0.15, -0.2);
    addCornerFlag(-hw + 0.15, hh - 0.15, Math.PI - 0.2);
    addCornerFlag(hw - 0.15, hh - 0.15, Math.PI + 0.2);

    const dugoutMat = new THREE.MeshStandardMaterial({
      color: 0xdbeafe,
      transparent: true,
      opacity: 0.22,
      roughness: 0.08,
      metalness: 0.02,
    });
    const benchMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.42 });
    const createDugout = (x, z, rotY) => {
      const dugout = new THREE.Group();
      const shell = new THREE.Mesh(new THREE.CylinderGeometry(2.4, 2.4, 4.8, 18, 1, true, Math.PI, Math.PI), dugoutMat);
      shell.rotation.z = Math.PI / 2;
      shell.position.y = 1.36;
      dugout.add(shell);
      const base = new THREE.Mesh(new THREE.BoxGeometry(4.8, 0.16, 2.5), new THREE.MeshStandardMaterial({ color: 0xcbd5e1, roughness: 0.84 }));
      base.position.y = 0.08;
      dugout.add(base);
      for (let i = -1; i <= 1; i += 1) {
        const seat = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.55, 0.68), benchMat);
        seat.position.set(i * 1.12, 0.44, 0.28);
        dugout.add(seat);
      }
      dugout.position.set(x, 0, z);
      dugout.rotation.y = rotY;
      detailGroup.add(dugout);
    };
    createDugout(-18, hh + 5.2, Math.PI);
    createDugout(8, hh + 5.2, Math.PI);

    const tunnel = new THREE.Mesh(
      new THREE.BoxGeometry(5.6, 2.7, 3.2),
      new THREE.MeshStandardMaterial({ color: 0x4b5563, roughness: 0.84 })
    );
    tunnel.position.set(0, 1.35, hh + 6.9);
    detailGroup.add(tunnel);

    const sidelineDeck = new THREE.Mesh(
      new THREE.BoxGeometry(38, 0.16, 2.6),
      new THREE.MeshStandardMaterial({ color: 0xbfc7d1, roughness: 0.9 })
    );
    sidelineDeck.position.set(-5, 0.08, hh + 4.35);
    detailGroup.add(sidelineDeck);

    const shade = new THREE.Mesh(
      new THREE.PlaneGeometry(stateMeta.fieldWidth * 0.92, stateMeta.fieldHeight * 0.38),
      new THREE.MeshBasicMaterial({ color: 0x0f172a, transparent: true, opacity: 0.17, depthWrite: false })
    );
    shade.rotation.x = -Math.PI / 2;
    shade.position.set(-14, 0.07, -hh * 0.1);
    detailGroup.add(shade);

    root.add(detailGroup);
  };
  addPitchPerimeterDetails();

  const lineMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.92 });
  const makeLine = (points) => {
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    return new THREE.Line(geometry, lineMaterial);
  };

  const drawPitchMarkings = () => {
    const halfW = stateMeta.fieldWidth / 2;
    const halfH = stateMeta.fieldHeight / 2;
    const y = 0.04;
    const marks = new THREE.Group();
    const rect = [
      new THREE.Vector3(-halfW, y, -halfH),
      new THREE.Vector3(halfW, y, -halfH),
      new THREE.Vector3(halfW, y, halfH),
      new THREE.Vector3(-halfW, y, halfH),
      new THREE.Vector3(-halfW, y, -halfH),
    ];
    marks.add(makeLine(rect));
    marks.add(makeLine([new THREE.Vector3(0, y, -halfH), new THREE.Vector3(0, y, halfH)]));
    const centerCircle = new THREE.EllipseCurve(0, 0, 9.15, 9.15, 0, Math.PI * 2, false, 0);
    const centerPoints = centerCircle.getPoints(72).map((point) => new THREE.Vector3(point.x, y, point.y));
    marks.add(makeLine(centerPoints));
    const boxDepth = 16.5;
    const boxWidth = 40.32;
    const sixDepth = 5.5;
    const sixWidth = 18.32;
    const penaltyYards = 11;
    const drawBox = (dir) => {
      const x = dir * halfW;
      const sign = dir > 0 ? -1 : 1;
      marks.add(makeLine([
        new THREE.Vector3(x, y, -boxWidth / 2),
        new THREE.Vector3(x + sign * boxDepth, y, -boxWidth / 2),
        new THREE.Vector3(x + sign * boxDepth, y, boxWidth / 2),
        new THREE.Vector3(x, y, boxWidth / 2),
      ]));
      marks.add(makeLine([
        new THREE.Vector3(x, y, -sixWidth / 2),
        new THREE.Vector3(x + sign * sixDepth, y, -sixWidth / 2),
        new THREE.Vector3(x + sign * sixDepth, y, sixWidth / 2),
        new THREE.Vector3(x, y, sixWidth / 2),
      ]));
      const penSpot = new THREE.Mesh(
        new THREE.CircleGeometry(0.25, 16),
        new THREE.MeshBasicMaterial({ color: 0xffffff })
      );
      penSpot.rotation.x = -Math.PI / 2;
      penSpot.position.set(x + sign * penaltyYards, y + 0.01, 0);
      marks.add(penSpot);
    };
    drawBox(-1);
    drawBox(1);
    root.add(marks);
  };
  drawPitchMarkings();

  const ambient = new THREE.HemisphereLight(0xf8fcff, 0x3d5a3f, 2.2);
  scene.add(ambient);

  const dirLight = new THREE.DirectionalLight(0xfffaf0, 2.9);
  dirLight.position.set(-72, 102, 20);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.set(2048, 2048);
  dirLight.shadow.camera.left = -110;
  dirLight.shadow.camera.right = 110;
  dirLight.shadow.camera.top = 110;
  dirLight.shadow.camera.bottom = -110;
  dirLight.shadow.bias = -0.00015;
  scene.add(dirLight);

  const rimLight = new THREE.DirectionalLight(0xb7dbff, 0.92);
  rimLight.position.set(58, 42, -38);
  scene.add(rimLight);

  const floodLight = new THREE.PointLight(0xeaf6ff, 0.84, 300, 1.9);
  floodLight.position.set(0, 58, 0);
  scene.add(floodLight);

  const sunShadow = new THREE.Mesh(
    new THREE.PlaneGeometry(stateMeta.fieldWidth * 0.94, stateMeta.fieldHeight * 0.72),
    new THREE.MeshBasicMaterial({ color: 0x07111d, transparent: true, opacity: 0.11, depthWrite: false })
  );
  sunShadow.rotation.x = -Math.PI / 2;
  sunShadow.position.set(-18, 0.06, -8);
  root.add(sunShadow);

  const addStandGraphics = () => {
    const graphics = new THREE.Group();
    const makeBanner = (text, width, height, x, y, z, rotY, fill = '#ffffff', bg = 'rgba(0,0,0,0)') => {
      const off = document.createElement('canvas');
      off.width = 2048;
      off.height = 512;
      const ctx = off.getContext('2d');
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, off.width, off.height);
      ctx.fillStyle = fill;
      ctx.font = '900 280px Montserrat, Arial, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, off.width / 2, off.height / 2);
      const texture = new THREE.CanvasTexture(off);
      texture.colorSpace = THREE.SRGBColorSpace;
      const mesh = new THREE.Mesh(
        new THREE.PlaneGeometry(width, height),
        new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false })
      );
      mesh.position.set(x, y, z);
      mesh.rotation.y = rotY;
      graphics.add(mesh);
    };
    const teamName = stadiumAds.teamName || 'Club';
    const teamMark = teamName.split(/\s+/).map((chunk) => chunk[0] || '').join('').slice(0, 3).toUpperCase() || 'CLB';
    makeBanner(teamName, 42, 10, 0, 24, -36, 0, stadiumPalette.secondary);
    makeBanner(teamMark, 16, 16, -28, 24, -35, 0, stadiumPalette.secondary);
    let crestColor;
    try {
      crestColor = new THREE.Color(stadiumPalette.primary || '#2563eb');
    } catch (error) {
      crestColor = new THREE.Color('#2563eb');
    }
    const crest = new THREE.Mesh(
      new THREE.CircleGeometry(4.1, 48),
      new THREE.MeshBasicMaterial({ color: crestColor, transparent: true, opacity: 0.96 })
    );
    crest.position.set(10, 35, -34.5);
    graphics.add(crest);
    makeBanner(teamMark, 6.2, 6.2, 10, 35, -34.3, 0, stadiumPalette.secondary);
    root.add(graphics);
  };
  addStandGraphics();

  const addFloodlightRibbon = () => {
    const ribbonGroup = new THREE.Group();
    const points = [];
    const rx = stateMeta.fieldWidth * 0.78;
    const rz = stateMeta.fieldHeight * 0.74;
    for (let i = 0; i <= 72; i += 1) {
      const angle = (i / 72) * Math.PI * 2;
      points.push(new THREE.Vector3(Math.cos(angle) * rx, 34 + Math.sin(angle * 2) * 0.6, Math.sin(angle) * rz));
    }
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({ color: 0xf8fdff, transparent: true, opacity: 0.9 })
    );
    ribbonGroup.add(line);
    points.forEach((point, index) => {
      if (index % 3 !== 0) return;
      const bulb = new THREE.Mesh(
        new THREE.SphereGeometry(0.22, 10, 10),
        new THREE.MeshBasicMaterial({ color: 0xffffff })
      );
      bulb.position.copy(point);
      ribbonGroup.add(bulb);
    });
    root.add(ribbonGroup);
  };
  addFloodlightRibbon();

  const canvasToWorld = (left, top) => {
    const x = ((toNumber(left) / stateMeta.width) - 0.5) * stateMeta.fieldWidth;
    const z = ((toNumber(top) / stateMeta.height) - 0.5) * stateMeta.fieldHeight;
    return { x, z };
  };
  const degToRad = (deg) => toNumber(deg, 0) * (Math.PI / 180);
  const transformPoint2d = (localX, localY, obj) => {
    const scaleX = Number.isFinite(Number(obj?.scaleX)) ? Number(obj.scaleX) : 1;
    const scaleY = Number.isFinite(Number(obj?.scaleY)) ? Number(obj.scaleY) : 1;
    const angle = degToRad(obj?.angle || 0);
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const x = toNumber(localX, 0) * scaleX;
    const y = toNumber(localY, 0) * scaleY;
    const rx = (x * cos) - (y * sin);
    const ry = (x * sin) + (y * cos);
    return {
      x: toNumber(obj?.left, 0) + rx,
      y: toNumber(obj?.top, 0) + ry,
    };
  };
  const objectBaseWidth2d = (obj) => {
    if (!obj || typeof obj !== 'object') return 0;
    if (Number.isFinite(Number(obj.width)) && Number(obj.width) > 0) return Number(obj.width);
    if (Number.isFinite(Number(obj.radius)) && Number(obj.radius) > 0) return Number(obj.radius) * 2;
    if (Number.isFinite(Number(obj.rx)) && Number(obj.rx) > 0) return Number(obj.rx) * 2;
    return 0;
  };
  const objectBaseHeight2d = (obj) => {
    if (!obj || typeof obj !== 'object') return 0;
    if (Number.isFinite(Number(obj.height)) && Number(obj.height) > 0) return Number(obj.height);
    if (Number.isFinite(Number(obj.radius)) && Number(obj.radius) > 0) return Number(obj.radius) * 2;
    if (Number.isFinite(Number(obj.ry)) && Number(obj.ry) > 0) return Number(obj.ry) * 2;
    return 0;
  };
  const parseColorChannels = (value) => {
    const color = safeText(value, '').toLowerCase().trim();
    if (!color) return null;
    let match = color.match(/^#([0-9a-f]{3,8})$/i);
    if (match) {
      const hex = match[1];
      const expand = (part) => {
        if (hex.length === 3 || hex.length === 4) return parseInt(part.repeat(2), 16);
        if (hex.length === 6 || hex.length === 8) return parseInt(part, 16);
        return 0;
      };
      const isLong = hex.length > 4;
      const r = expand(isLong ? hex.slice(0, 2) : hex[0]);
      const g = expand(isLong ? hex.slice(2, 4) : hex[1]);
      const b = expand(isLong ? hex.slice(4, 6) : hex[2]);
      const a = hex.length > 6 ? (expand(hex.slice(6, 8)) / 255) : 1;
      return { r, g, b, a };
    }
    match = color.match(/^rgba?\(([^)]+)\)/);
    if (!match) {
      if (color === 'white') return { r: 255, g: 255, b: 255, a: 1 };
      if (color === 'black') return { r: 0, g: 0, b: 0, a: 1 };
      return null;
    }
    const parts = match[1].split(',').map((entry) => Number(entry));
    if (parts.some((part) => Number.isNaN(part))) return null;
    return {
      r: parts[0],
      g: parts[1],
      b: parts[2],
      a: parts.length >= 4 ? parts[3] : 1,
    };
  };
  const isWhiteToneColor = (value) => {
    const channels = parseColorChannels(value);
    if (!channels) return false;
    return (channels.r >= 220 && channels.g >= 220 && channels.b >= 220 && channels.a > 0.28);
  };
  const isTokenTeamColor = (value) => {
    const color = safeText(value).toLowerCase().trim();
    if (!color) return false;
    if (['#ef4444', '#3b82f6', '#2563eb', '#dc2626', '#fecaca', '#dbeafe', '#93c5fd'].includes(color)) return true;
    if (color.includes('rgba(239,68,68') || color.includes('rgb(239,68,68)') || color.includes('rgba(14,165,233')) return true;
    if (color.includes('rgba(37,99,235') || color.includes('rgb(37,99,235)')) return true;
    return false;
  };
  const isOrangeConeColor = (value) => {
    const color = safeText(value).toLowerCase().trim();
    if (!color) return false;
    if (['#f59e0b', '#f97316', '#fde68a', '#fcd34d', '#b45309', '#92400e'].includes(color)) return true;
    if (color.includes('f59e0b') || color.includes('f97316') || color.includes('fcd34d') || color.includes('b45309')) return true;
    const channels = parseColorChannels(value);
    if (!channels) return false;
    return channels.r >= 170 && channels.r >= channels.g * 1.2 && channels.r >= channels.b * 1.3;
  };
  const normalizeTextIconKind = (value) => {
    const text = safeText(value);
    if (!text) return '';
    if (text.includes('🔺') || text.includes('◀') || text.includes('△') || text.includes('▲')) return 'emoji_cone';
    if (text.includes('⚽') || text.includes('◯') || text.includes('⚪') || text.includes('⚫')) return 'emoji_ball';
    if (text.includes('🥅') || text.includes('⚽️') || text.includes('🥅') || text.includes('⛳')) return 'emoji_goal';
    if (text.includes('📍')) return 'cone';
    if (text.includes('🚧')) return 'cone';
    if (text.includes('🧱')) return 'cone';
    return '';
  };
  const normalizeObjectKind = (value) => safeText(value, '').toLowerCase().trim().replace(/[\s-]+/g, '_');
  const normalizeObjectKindAlias = (value) => {
    const normalized = normalizeObjectKind(value);
    if (normalized === 'cone_striped') return 'cone_striped';
    if (normalized === 'goalpost' || normalized === 'goal_post') return 'goal';
    if (normalized === 'player' || normalized === 'goalkeeper' || normalized.startsWith('player_') || normalized.startsWith('goalkeeper_')) return 'token';
    if (normalized.endsWith('_arrow_head')) return 'arrow_head';
    if (normalized === 'cone-striped') return 'cone_striped';
    return normalized;
  };
  const isTokenObject = (value) => normalizeObjectKindAlias(value) === 'token';
  const isArrowHeadKind = (value) => {
    const normalized = normalizeObjectKindAlias(value);
    return normalized === 'arrow_head' || normalized.endsWith('_arrow_head');
  };
  const isArrowKind = (value) => {
    const normalized = normalizeObjectKindAlias(value);
    return normalized.startsWith('arrow') || normalized.includes('arrow');
  };
  const extractFacingDegrees = (obj, childObjects = []) => {
    const childFacing = Array.isArray(childObjects)
      ? childObjects
        .map((child) => toNumber(child?.data?.facing_deg, Number.NaN))
        .find((value) => Number.isFinite(value))
      : Number.NaN;
    const candidates = [
      childFacing,
      toNumber(obj?.data?.facing_deg, Number.NaN),
      toNumber(obj?.data?.facingDeg, Number.NaN),
      toNumber(obj?.facing_deg, Number.NaN),
      toNumber(obj?.facingDeg, Number.NaN),
    ];
    const firstFacing = candidates.find((value) => Number.isFinite(value));
    if (Number.isFinite(firstFacing)) return normalizeAngle(degToRad(firstFacing));
    return NaN;
  };
  const inferObjectKind = (obj, childObjects = []) => {
    const data = obj && typeof obj === 'object' ? obj.data || {} : {};
    const dataKind = data && typeof data === 'object' && data.kind ? data.kind : '';
    const directKind = normalizeObjectKindAlias(dataKind || obj?.kind || '');
    const tokenKind = normalizeObjectKindAlias(data.token_kind || data.playerKind || '');
    if (!directKind) {
      const iconKind = normalizeTextIconKind(obj?.text);
      if (iconKind) return iconKind;
    }
    if (directKind) return directKind;
    if (isTokenObject(tokenKind)) return 'token';
    const type = safeText(obj?.type).toLowerCase();
    const fill = safeText(obj?.fill);
    const stroke = safeText(obj?.stroke);
    const width = toNumber(objectBaseWidth2d(obj), 0);
    const height = toNumber(objectBaseHeight2d(obj), 0);
    const radius = toNumber(obj?.radius, 0);
    const childRoles = Array.isArray(childObjects)
      ? childObjects.map((child) => safeText((child?.data || {}).role))
      : [];
    const hasConeRole = childRoles.some((role) => role.startsWith('cone_') || role === 'cone' || role === 'cone_shadow' || role === 'gate_cone');
    const hasTokenRole = childRoles.some((role) => role.startsWith('token_') || role === 'token_name' || role === 'token_number');
    if (type === 'i-text') return 'note';
    if (type === 'group') {
      const hasCircle = Array.isArray(childObjects) && childObjects.some((child) => safeText(child?.type).toLowerCase() === 'circle');
      if (hasConeRole && Array.isArray(childObjects)) return 'cone';
      if (hasTokenRole && Array.isArray(childObjects)) return 'token';
      if (hasCircle && Array.isArray(childObjects)) return 'token';
      if (tokenKind) return 'token';
    }
    if (type === 'circle') {
      if (isWhiteToneColor(fill) || isWhiteToneColor(stroke)) return 'emoji_ball';
      if (radius >= 6 || (width > 12 && height > 12)) return 'token';
      if (isTokenTeamColor(fill) || isTokenTeamColor(stroke)) return 'token';
    }
    if (type === 'triangle') {
      if (isOrangeConeColor(fill) || isOrangeConeColor(stroke)) return 'cone';
    }
    if (type === 'rect') {
      if (isWhiteToneColor(fill) && width > 22 && width < 95 && height > 10 && height < 45) return 'emoji_mini_goal';
      if ((fill.includes('rgba(14,165,233') || fill.includes('rgba(2,132,199')) || isTokenTeamColor(fill)) return 'zone';
    }
    return '';
  };
  const objectCenter2d = (obj) => {
    if (!obj || typeof obj !== 'object') return { x: 0, y: 0 };
    const ox = safeText(obj.originX, 'center');
    const oy = safeText(obj.originY, 'center');
    const width = objectBaseWidth2d(obj);
    const height = objectBaseHeight2d(obj);
    const localX = ox === 'left' ? (width / 2) : (ox === 'right' ? -(width / 2) : 0);
    const localY = oy === 'top' ? (height / 2) : (oy === 'bottom' ? -(height / 2) : 0);
    return transformPoint2d(localX, localY, obj);
  };
  const childPointInGroup2d = (groupObj, childObj, localX, localY) => {
    const child = childObj && typeof childObj === 'object' ? childObj : {};
    const childLocalX = toNumber(child.left, 0) + toNumber(localX, 0);
    const childLocalY = toNumber(child.top, 0) + toNumber(localY, 0);
    return transformPoint2d(childLocalX, childLocalY, groupObj);
  };
  const sizeToMeters = (size, total, fieldTotal, minimum, maximum) => {
    return clamp((toNumber(size, minimum) / total) * fieldTotal, minimum, maximum);
  };
  const radiusToMeters = (radius) => clamp((toNumber(radius, 20) / stateMeta.width) * stateMeta.fieldWidth * 0.9, 0.7, 2.2);

  const parseColor = (value, fallback) => {
    try {
      return new THREE.Color(String(value || fallback || '#ffffff'));
    } catch (error) {
      return new THREE.Color(fallback || '#ffffff');
    }
  };
  const tintColor = (colorLike, amount = 0) => {
    const color = colorLike instanceof THREE.Color ? colorLike.clone() : parseColor(colorLike, '#ffffff');
    color.offsetHSL(0, 0, amount);
    return color;
  };
  const normalizeNodeName = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const resolveNodeByName = (root, candidates) => {
    if (!root || !Array.isArray(candidates)) return null;
    const normalizedCandidates = candidates
      .map((name) => String(name || '').trim())
      .filter(Boolean)
      .map((name) => ({
        exact: name,
        normalized: normalizeNodeName(name),
      }));
    const uniqueExact = [...new Set(normalizedCandidates.map((entry) => entry.exact))];
    for (const candidate of uniqueExact) {
      const found = root.getObjectByName ? root.getObjectByName(candidate, true) : null;
      if (found) return found;
    }
    const targetSet = new Set(normalizedCandidates.map((entry) => entry.normalized));
    let fallback = null;
    root.traverse((node) => {
      if (fallback || !node?.name) return;
      if (targetSet.has(normalizeNodeName(node.name))) fallback = node;
    });
    return fallback;
  };
  const hasMeshInSubtree = (root) => {
    if (!root || typeof root.traverse !== 'function') return false;
    let hasMesh = false;
    root.traverse((node) => {
      if (hasMesh) return;
      if (node?.isMesh) hasMesh = true;
    });
    return hasMesh;
  };
  const pickHumanoidPlayerSource = (root) => {
    if (!root || typeof root.traverse !== 'function') return null;
    const candidates = [];
    const normalizedNames = (value) => safeText(value).toLowerCase();
    root.traverse((node) => {
      const nodeName = normalizedNames(node?.name);
      if (!nodeName) return;
      if (nodeName.includes('gltf_created') || nodeName.includes('object_')) return;
      const isHumanoid = nodeName.includes('metarig') || nodeName.includes('soccer man') || nodeName.includes('soccer woman');
      if (!isHumanoid || !Array.isArray(node.children) || !node.children.length) return;
      candidates.push(node);
    });
    if (!candidates.length) return null;
    const ranked = candidates.filter((node) => hasMeshInSubtree(node));
    const normalizedPrefer = (node) => {
      const name = normalizedNames(node.name);
      if (name.includes('metarig')) return 0;
      if (name.includes('soccer')) return 1;
      return 2;
    };
    const filtered = ranked.length ? ranked : candidates;
    filtered.sort((a, b) => normalizedPrefer(a) - normalizedPrefer(b));
    return filtered[0];
  };
  const getHumanoidAnimationClip = (source, humanoidRoot) => {
    if (!source || !humanoidRoot) return null;
    const sourceTracks = Array.isArray(source.tracks) ? source.tracks : [];
    const filteredTracks = sourceTracks.filter((track) => {
      if (!track?.name) return false;
      const trackName = String(track.name);
      const lastDot = trackName.lastIndexOf('.');
      if (lastDot <= 0) return false;
      const nodeName = trackName.slice(0, lastDot);
      return !!humanoidRoot.getObjectByName(nodeName, true);
    });
    if (!filteredTracks.length) return null;
    if (filteredTracks.length === sourceTracks.length) return source;
    return new THREE.AnimationClip(source.name || 'PlayerAction', source.duration || -1, filteredTracks);
  };
  const classifyHumanoidClip = (clip) => {
    if (!clip) return 'generic';
    const name = String(clip.name || '').toLowerCase();
    if (name.includes('idle') || name.includes('stand') || name.includes('rest') || name.includes('wait')) return 'idle';
    if (name.includes('run') || name.includes('sprint') || name.includes('dash')) return 'run';
    if (name.includes('walk') || name.includes('jog') || name.includes('move')) return 'walk';
    return 'generic';
  };
  const applyHumanoidAnimationState = (group, moveStrength) => {
    const motion = group?.userData?.humanoidMotion;
    if (!motion || !motion.mixer) return;
    const actions = motion.actions || {};
    const idleAction = actions.idle || actions.generic;
    const walkAction = actions.walk || actions.generic;
    const runAction = actions.run || actions.walk || actions.generic;
    const target = moveStrength <= 0.06 ? 'idle' : moveStrength <= 0.3 ? 'walk' : 'run';
    const action = target === 'run' ? runAction : target === 'walk' ? walkAction : idleAction;
    if (!action) return;
    if (motion.activeAction !== action) {
      const previous = motion.activeAction;
      action.enabled = true;
      action.setLoop(THREE.LoopRepeat, Infinity);
      action.play();
      if (previous && previous !== action) {
        action.crossFadeFrom(previous, 0.2, true);
        action.time = previous.time;
      } else {
        action.time = 0;
      }
      motion.activeAction = action;
      motion.state = target;
    }

    const moving = moveStrength > 0.06;
    const walkSpeed = 0.55 + (moveStrength * 1.45);
    const runSpeed = 0.88 + (moveStrength * 1.45);
    if (!moving) {
      motion.state = 'idle';
      if (idleAction) {
        idleAction.timeScale = 0;
      }
      if (motion.activeAction !== idleAction && idleAction) {
        idleAction.reset();
        idleAction.play();
        motion.activeAction = idleAction;
      }
      if (motion.activeAction?.timeScale !== undefined) {
        motion.activeAction.timeScale = 0;
      }
      motion.lastMoveStrength = 0;
      return;
    }
    const speed = target === 'run' ? runSpeed : walkSpeed;
    const profileSpeed = target === 'run' ? 1.22 : target === 'walk' ? 1.05 : 1;
    if (motion.activeAction && motion.activeAction.timeScale !== undefined) {
      motion.activeAction.timeScale = clamp(speed * profileSpeed, 0.08, 2.2);
      if (motion.activeAction.paused) motion.activeAction.paused = false;
    }
    if (motion.lastMoveStrength !== undefined && moveStrength > 0.06) {
      const phaseShift = motion.lastMoveStrength - moveStrength;
      if (phaseShift > 0.2 && motion.activeAction?.timeScale !== undefined) {
        motion.activeAction.timeScale = clamp(motion.activeAction.timeScale * 0.97, 0.12, 2.2);
      }
      if (phaseShift < -0.18 && motion.activeAction?.timeScale !== undefined) {
        motion.activeAction.timeScale = clamp(motion.activeAction.timeScale * 1.03, 0.08, 2.2);
      }
    }
    motion.isIdle = false;
    motion.lastMoveStrength = moveStrength;
  };
  const scaleClamped = (value, minScale, maxScale) => Math.max(minScale, Math.min(maxScale, value));
  const shouldSkipMaterialTint = (material) => {
    if (!material || typeof material !== 'object') return true;
    const hasColorMap = !!material.map;
    const hasEmissiveMap = !!material.emissiveMap;
    const hasNormalMap = !!material.normalMap;
    const hasRoughnessMap = !!material.roughnessMap;
    return hasColorMap || hasEmissiveMap || hasNormalMap || hasRoughnessMap;
  };
  const resolveTokenPhotoUrl = (obj, childObjects = []) => {
    const extra = obj && typeof obj.data === 'object' ? obj.data : {};
    const childPhoto = childObjects.find((child) => String((child?.data || {}).role || '').trim() === 'token_photo');
    return safeText(
      extra.playerPhotoUrl
      || extra.photo_url
      || extra.photoUrl
      || childPhoto?.src
      || childPhoto?.crossOriginSrc
      || childPhoto?._element?.src
    );
  };

  const createLabelSprite = (text, fillHex = '#ffffff') => {
    const off = document.createElement('canvas');
    off.width = 256;
    off.height = 128;
    const ctx = off.getContext('2d');
    ctx.clearRect(0, 0, off.width, off.height);
    ctx.font = '900 62px Montserrat, Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = fillHex;
    ctx.fillText(String(text || ''), off.width / 2, off.height / 2);
    const texture = new THREE.CanvasTexture(off);
    texture.needsUpdate = true;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(5.6, 2.8, 1);
    return sprite;
  };

  const createCardLabel = (text) => {
    const label = safeText(text, '');
    const off = document.createElement('canvas');
    off.width = 512;
    off.height = 192;
    const ctx = off.getContext('2d');
    ctx.clearRect(0, 0, off.width, off.height);
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = 'rgba(15,23,42,0.24)';
    ctx.lineWidth = 10;
    const radius = 24;
    ctx.beginPath();
    ctx.moveTo(radius, 12);
    ctx.lineTo(off.width - radius, 12);
    ctx.quadraticCurveTo(off.width - 12, 12, off.width - 12, radius);
    ctx.lineTo(off.width - 12, off.height - radius);
    ctx.quadraticCurveTo(off.width - 12, off.height - 12, off.width - radius, off.height - 12);
    ctx.lineTo(radius, off.height - 12);
    ctx.quadraticCurveTo(12, off.height - 12, 12, off.height - radius);
    ctx.lineTo(12, radius);
    ctx.quadraticCurveTo(12, 12, radius, 12);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#111827';
    ctx.font = '900 78px Montserrat, Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, off.width / 2, off.height / 2 + 2);
    const texture = new THREE.CanvasTexture(off);
    texture.needsUpdate = true;
    const group = new THREE.Group();
    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(8.6, 3.2),
      new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, side: THREE.DoubleSide })
    );
    plane.rotation.x = -Math.PI / 2;
    plane.position.y = 0.12;
    group.add(plane);
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(8.9, 3.45),
      new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.16, depthWrite: false })
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.set(0.18, 0.05, 0.28);
    group.add(shadow);
    group.userData = { floatPhase: Math.random() * Math.PI * 2 };
    return group;
  };

  const createPlayerCutoutSprite = (photoUrl, radius, accentColor) => {
    const src = safeText(photoUrl);
    if (!src) return null;
    const group = new THREE.Group();
    group.userData = { kind: 'photo_cutout_group' };
    const halo = new THREE.Mesh(
      new THREE.CircleGeometry(radius * 1.02, 28),
      new THREE.MeshBasicMaterial({ color: accentColor, transparent: true, opacity: 0.22, depthWrite: false })
    );
    halo.rotation.x = -Math.PI / 2;
    halo.position.y = 0.04;
    group.add(halo);

    const loader = new THREE.TextureLoader();
    try { loader.setCrossOrigin('anonymous'); } catch (error) {}
    loader.load(src, (texture) => {
      texture.needsUpdate = true;
      texture.colorSpace = THREE.SRGBColorSpace;
      const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthWrite: false,
        alphaTest: 0.02,
      });
      const sprite = new THREE.Sprite(material);
      sprite.center.set(0.5, 0);
      const width = radius * 2.45;
      const height = radius * 4.5;
      sprite.scale.set(width, height, 1);
      sprite.position.set(0, 0.06, 0);
      sprite.renderOrder = 8;
      group.userData.sprite = sprite;
      group.add(sprite);
    }, undefined, () => {});
    return group;
  };

  const buildPhotoBadgeSprite = (photoUrl, radius) => {
    const src = safeText(photoUrl);
    if (!src) return null;
    const group = new THREE.Group();
    const loader = new THREE.TextureLoader();
    try { loader.setCrossOrigin('anonymous'); } catch (error) {}
    loader.load(src, (texture) => {
      texture.needsUpdate = true;
      texture.colorSpace = THREE.SRGBColorSpace;
      const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthWrite: false,
        alphaTest: 0.02,
      });
      const sprite = new THREE.Sprite(material);
      sprite.center.set(0.5, 0);
      sprite.scale.set(radius * 1.15, radius * 1.15, 1);
      sprite.position.set(0, 0, radius * 0.42);
      group.add(sprite);
    }, undefined, () => {});
    return group;
  };

  const upgradeActorToHumanoidModel = (group, entry, fillColor, accentColor) => {
    ensurePlayerModel().then((asset) => {
      if (!asset?.scene || !group?.parent) return;
      const sourceClone = SkeletonUtils.clone(asset.scene);
      const selectedSource = pickHumanoidPlayerSource(sourceClone) || sourceClone;
      const clone = selectedSource === sourceClone ? sourceClone : selectedSource.clone(true);
      const fill = fillColor instanceof THREE.Color ? fillColor.clone() : parseColor(fillColor, '#2563eb');
      const accent = accentColor instanceof THREE.Color ? accentColor.clone() : parseColor(accentColor, '#ffffff');
      const darkerFill = tintColor(fill, -0.16);
      const skin = parseColor('#f1c27d', '#f1c27d');
      const strayNodes = [];
      clone.traverse((node) => {
        const nodeName = safeText(node.name).toLowerCase();
        if (nodeName.includes('esfera geod') || nodeName === 'camera' || nodeName === 'light') {
          strayNodes.push(node);
          return;
        }
        if (!node.isMesh || !node.material) return;
        node.material = Array.isArray(node.material)
          ? node.material.map((item) => item.clone())
          : node.material.clone();
        const materials = Array.isArray(node.material) ? node.material : [node.material];
        materials.forEach((material) => {
          const hasRichMap = shouldSkipMaterialTint(material);
          const materialName = safeText(material.name).toLowerCase();
          if (!('color' in material)) return;
          if (hasRichMap) {
            return;
          }
          if (materialName.includes('skin') || materialName.includes('hair') || materialName.includes('face')) {
            material.color.copy(skin);
          } else if (materialName.includes('eyes') || materialName.includes('eye')) {
            material.color.setHex(0x2f2f2f);
          } else if (materialName.includes('short')) {
            material.color.copy(darkerFill);
          } else if (materialName.includes('sock')) {
            material.color.copy(fill);
          } else if (materialName.includes('kitlight')) {
            material.color.copy(accent);
          } else {
            material.color.copy(fill);
          }
          if ('roughness' in material) material.roughness = 0.72;
          if ('metalness' in material) material.metalness = 0.04;
        });
        node.castShadow = true;
        node.receiveShadow = true;
      });
      strayNodes.forEach((node) => node.parent?.remove(node));

      clearGroup(group);

      const radius = Number(entry?.radius) || 1;
      const baseGlow = new THREE.Mesh(
        new THREE.CircleGeometry(radius * 1.36, 28),
        new THREE.MeshBasicMaterial({ color: fill, transparent: true, opacity: 0.22, depthWrite: false })
      );
      baseGlow.rotation.x = -Math.PI / 2;
      baseGlow.position.y = 0.035;
      group.add(baseGlow);

      const feetShadow = new THREE.Mesh(
        new THREE.CircleGeometry(radius * 0.96, 24),
        new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.22, depthWrite: false })
      );
      feetShadow.rotation.x = -Math.PI / 2;
      feetShadow.position.y = 0.04;
      group.add(feetShadow);
      group.add(createShadowStreak(radius));

      const bounds = new THREE.Box3().setFromObject(clone);
      const size = bounds.getSize(new THREE.Vector3());
      const measuredWidth = Math.max(size.x, size.z, 0.01);
      const targetRadius = radius * 0.95;
      const normalizedScale = scaleClamped(targetRadius / measuredWidth, 0.35, 1.8);
      clone.scale.setScalar(normalizedScale);
      const normalizedBounds = new THREE.Box3().setFromObject(clone);
      const normalizedMinY = normalizedBounds.min.y;
      clone.position.y = normalizedMinY < 0 ? Math.abs(normalizedMinY) : 0;
      group.add(clone);

      let mixer = null;
      let humanoidMotion = null;
      if (Array.isArray(asset.clips) && asset.clips.length) {
        const prepared = [];
        asset.clips.forEach((clip) => {
          const matched = getHumanoidAnimationClip(clip, clone);
          if (matched) prepared.push(matched);
        });
        if (prepared.length) {
          mixer = new THREE.AnimationMixer(clone);
          const actions = {};
          prepared.forEach((clip) => {
            const key = classifyHumanoidClip(clip);
            const action = mixer.clipAction(clip);
            if (key === 'generic' && actions.generic) return;
            if (key === 'idle' && actions.idle) return;
            if (key === 'walk' && actions.walk) return;
            if (key === 'run' && actions.run) return;
            action.setLoop(THREE.LoopRepeat, Infinity);
            action.enabled = false;
            action.clampWhenFinished = false;
            action.weight = 0;
            actions[key] = action;
            action.play();
          });
          Object.values(actions).forEach((action) => {
            if (action !== actions.generic && actions.generic) {
              action.crossFadeFrom(actions.generic, 0, true);
            }
          });
          const fallback = actions.idle || actions.walk || actions.run || actions.generic;
          if (fallback) {
            fallback.weight = 1;
            fallback.timeScale = 0;
            fallback.enabled = true;
            fallback.paused = true;
          }
          humanoidMotion = {
            mixer,
            actions,
            activeAction: fallback || null,
            state: fallback ? 'idle' : null,
            lastMoveStrength: 0,
            isIdle: true,
          };
          modelMixers.add(mixer);
        }
      }

      const badge = createLabelSprite(entry.label, '#ffffff');
      badge.scale.set(2.8, 1.4, 1);
      badge.position.set(0, 2.22, radius * 0.72);
      group.add(badge);

      if (safeText(entry.photoUrl)) {
        const portrait = buildPhotoBadgeSprite(entry.photoUrl, radius);
        if (portrait) {
          portrait.position.set(0, 2.48, 0.04);
          group.add(portrait);
          group.userData.portrait = portrait;
        }
      }

      group.userData = {
        ...group.userData,
        baseY: 0,
        radius,
        badge,
        isHumanoidModel: true,
        leftArm: resolveNodeByName(clone, ['upperarm_l', 'upper_arm_l', 'leftarm', 'LeftArmPivot']),
        rightArm: resolveNodeByName(clone, ['upperarm_r', 'upper_arm_r', 'rightarm', 'RightArmPivot']),
        leftLeg: resolveNodeByName(clone, ['thigh_l', 'thigh_left', 'LeftLegPivot']),
        rightLeg: resolveNodeByName(clone, ['thigh_r', 'thigh_right', 'RightLegPivot']),
        torsoPivot: resolveNodeByName(clone, ['spine_02', 'spine_01', 'spine', 'TorsoPivot']),
        modelRoot: clone,
        mixer,
        humanoidMotion,
      };
    }).catch(() => {});
  };

  const createGoalFrame = (color = 0xe5e7eb) => {
    const group = new THREE.Group();
    const material = new THREE.LineBasicMaterial({ color });
    const geometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-1.8, 0, 0),
      new THREE.Vector3(1.8, 0, 0),
      new THREE.Vector3(1.8, 1.2, 0),
      new THREE.Vector3(-1.8, 1.2, 0),
      new THREE.Vector3(-1.8, 0, 0),
      new THREE.Vector3(-1.2, 0, -1),
      new THREE.Vector3(-1.2, 1.2, -1),
      new THREE.Vector3(1.2, 1.2, -1),
      new THREE.Vector3(1.2, 0, -1),
      new THREE.Vector3(1.8, 0, 0),
    ]);
    group.add(new THREE.Line(geometry, material));
    const net = new THREE.Mesh(
      new THREE.PlaneGeometry(2.2, 1.05, 6, 4),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.22, wireframe: true })
    );
    net.position.set(0, 0.58, -0.92);
    group.add(net);
    return group;
  };

  const createArrowCurve = (from, to) => {
    const start = new THREE.Vector3(from.x, 0.36, from.z);
    const end = new THREE.Vector3(to.x, 0.36, to.z);
    const mid = start.clone().lerp(end, 0.5);
    mid.y += clamp(start.distanceTo(end) * 0.035, 0.45, 2.4);
    return new THREE.QuadraticBezierCurve3(start, mid, end);
  };

  const createArrowHead = (from, to, color) => {
    const dir = new THREE.Vector3().subVectors(to, from);
    const length = dir.length();
    if (!length) return null;
    dir.normalize();
    const cone = new THREE.Mesh(
      new THREE.ConeGeometry(0.45, 1.4, 12),
      new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.08 })
    );
    cone.position.copy(to);
    cone.position.y += 0.12;
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().setY(0.16).normalize());
    return cone;
  };

  const createShadowStreak = (radius) => {
    const geometry = new THREE.PlaneGeometry(radius * 1.2, radius * 4.8);
    const material = new THREE.MeshBasicMaterial({
      color: 0x020617,
      transparent: true,
      opacity: 0.18,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.rotation.x = -Math.PI / 2;
    mesh.rotation.z = 0.26;
    mesh.position.set(radius * 0.55, 0.035, radius * 1.55);
    return mesh;
  };

  const disposeChild = (child) => {
    child.traverse?.((node) => {
      if (node.geometry) node.geometry.dispose?.();
      if (node.material) {
        if (Array.isArray(node.material)) node.material.forEach((item) => item.dispose?.());
        else node.material.dispose?.();
      }
      if (node.material?.map) node.material.map.dispose?.();
      if (node.texture) node.texture.dispose?.();
    });
  };

  const ensureStadiumModel = async () => {
    if (stadiumScene) return stadiumScene;
    if (stadiumLoadPromise) return stadiumLoadPromise;
    const modelUrl = safeText(payload.stadiumModelUrl);
    const isArchitecturalReference = /stadium_architectural_complete(?:\.[a-f0-9]+)?\.glb(?:[?#].*)?$/i.test(modelUrl);
    if (!modelUrl) return null;
    const loader = new GLTFLoader();
    stadiumLoadPromise = new Promise((resolve) => {
      loader.load(
        modelUrl,
        (gltf) => {
          try {
            const group = gltf.scene || gltf.scenes?.[0] || null;
            if (!group) {
              resolve(null);
              return;
            }
            const box = new THREE.Box3().setFromObject(group);
            const size = new THREE.Vector3();
            const center = new THREE.Vector3();
            box.getSize(size);
            box.getCenter(center);
            const scaleX = ((stateMeta.fieldWidth * (isArchitecturalReference ? 2.22 : 2.12))) / Math.max(size.x || 1, 1);
            const scaleZ = ((stateMeta.fieldHeight * (isArchitecturalReference ? 2.14 : 2.04))) / Math.max(size.z || 1, 1);
            const scale = Math.min(scaleX, scaleZ);
            group.position.sub(center);
            group.scale.setScalar(scale);
            const liftedBox = new THREE.Box3().setFromObject(group);
            const minY = liftedBox.min.y;
            group.position.y -= minY;
            group.position.y -= 0.02;
            group.traverse((node) => {
              if (!node.isMesh) return;
              node.castShadow = true;
              node.receiveShadow = true;
              if (node.material) {
                const mats = Array.isArray(node.material) ? node.material : [node.material];
                mats.forEach((mat) => {
                  const name = String(mat.name || '').toUpperCase();
                  const meshName = String(node.name || '').toUpperCase();
                  if ('envMapIntensity' in mat) mat.envMapIntensity = isArchitecturalReference ? 0.72 : 0.5;
                  if ('metalness' in mat && typeof mat.metalness === 'number') mat.metalness *= isArchitecturalReference ? 0.98 : 0.92;
                  if ('roughness' in mat && typeof mat.roughness === 'number') mat.roughness = Math.min(0.92, mat.roughness + (isArchitecturalReference ? 0.01 : 0.04));
                  const isSeatRow = meshName.includes('SEAT_ROW') || meshName.includes('SEAT_PLATE') || meshName.includes('SEATING_FIELD');
                  if (isArchitecturalReference && isSeatRow && 'map' in mat) {
                    mat.map = getSeatPatternTexture('#1f63d6', '#0d3f9c');
                    mat.color.set('#ffffff');
                    mat.needsUpdate = true;
                    if ('roughness' in mat) mat.roughness = 0.72;
                    if ('metalness' in mat) mat.metalness = 0.04;
                  }
                  if ('color' in mat && name.includes('TEAM_PRIMARY_DARKER_SEAT_FIELD')) mat.color.set('#174fba');
                  else if ('color' in mat && name.includes('TEAM_PRIMARY')) mat.color.set('#1f63d6');
                  else if ('color' in mat && name.includes('TEAM_ACCENT')) mat.color.set('#0d3f9c');
                  else if ('color' in mat && name.includes('TEAM_SECONDARY')) mat.color.set('#d6dde6');
                  else if ('color' in mat && name.includes('ARCH_PRECAST_CONCRETE')) mat.color.set(isArchitecturalReference ? '#b8c4d1' : '#95a3b3');
                  else if ('color' in mat && name.includes('ARCH_DARK_CONCRETE_STRUCTURE')) mat.color.set(isArchitecturalReference ? '#2a3542' : '#313b46');
                  else if ('color' in mat && name.includes('ARCH_STEEL_TRUSS')) mat.color.set(isArchitecturalReference ? '#7b8da3' : '#66768a');
                  else if ('color' in mat && name.includes('ARCH_DARK_SERVICE_RING')) mat.color.set('#1b2631');
                  else if ('color' in mat && name.includes('ARCH_GLASS_GUARDRAIL')) {
                    mat.color.set('#d9efff');
                    mat.opacity = isArchitecturalReference ? 0.18 : 0.22;
                    mat.transparent = true;
                  } else if ('color' in mat && name.includes('ARCH_FLOODLIGHT_LINE')) {
                    mat.color.set('#f4fbff');
                  } else if ('color' in mat && name.includes('ARCH_LED_RIBBON_FACE')) {
                    mat.color.set('#0b4fbe');
                    if ('emissive' in mat) mat.emissive.set('#1a66e8');
                    if ('emissiveIntensity' in mat) mat.emissiveIntensity = isArchitecturalReference ? 1.9 : 1.4;
                  } else if ('color' in mat && name.includes('ROOF')) {
                    mat.color.offsetHSL(0, isArchitecturalReference ? -0.03 : -0.02, isArchitecturalReference ? 0.05 : 0.02);
                  }
                });
              }
            });
            stadiumScene = group;
            stadiumRoot.add(group);
            resolve(group);
          } catch (error) {
            resolve(null);
          }
        },
        undefined,
        () => resolve(null)
      );
    });
    return stadiumLoadPromise;
  };

  const ensurePlayerModel = async () => {
    if (playerModelAsset) return playerModelAsset;
    if (playerModelLoadPromise) return playerModelLoadPromise;
    if (!playerModelUrl) return null;
    const loader = new GLTFLoader();
    playerModelLoadPromise = new Promise((resolve) => {
      loader.load(
        playerModelUrl,
        (gltf) => {
          const sceneRef = gltf.scene || gltf.scenes?.[0] || null;
          if (!sceneRef) {
            resolve(null);
            return;
          }
          playerModelAsset = {
            scene: sceneRef,
            clips: Array.isArray(gltf.animations) ? gltf.animations : [],
          };
          resolve(playerModelAsset);
        },
        undefined,
        () => resolve(null)
      );
    });
    return playerModelLoadPromise;
  };

  const clearGroup = (group) => {
    const humanoidMotion = group?.userData?.humanoidMotion;
    if (humanoidMotion?.mixer) {
      if (humanoidMotion?.activeAction) humanoidMotion.activeAction.stop();
      if (humanoidMotion?.actions) {
        Object.values(humanoidMotion.actions).forEach((action) => {
          action.stop();
        });
      }
      humanoidMotion.mixer.stopAllAction();
      humanoidMotion.mixer.uncacheRoot(group.userData?.modelRoot || group);
      modelMixers.delete(humanoidMotion.mixer);
    }
    if (group?.userData?.mixer) modelMixers.delete(group.userData.mixer);
    while (group.children.length) {
      const child = group.children[0];
      group.remove(child);
      disposeChild(child);
    }
  };

  const buildFrameData = (step) => {
    const state = step && typeof step.state === 'object' ? step.state : {};
    const objects = Array.isArray(state.objects) ? state.objects : [];
    const data = {
      tokens: new Map(),
      balls: new Map(),
      cones: new Map(),
      zones: [],
      shapes: [],
      goals: [],
      paths: [],
      notes: [],
    };
    let tokenIndex = 0;
    let ballIndex = 0;
    let coneIndex = 0;
    let goalIndex = 0;
    objects.forEach((obj, index) => {
      const extra = obj && typeof obj.data === 'object' ? obj.data : {};
      const childObjects = Array.isArray(obj.objects) ? obj.objects : [];
      const kind = inferObjectKind(obj, childObjects);
      const tokenFacingRad = extractFacingDegrees(obj, childObjects);
      const tokenIdentity = safeText(
        extra.token_id
        || extra.tokenId
        || extra.playerId
        || extra.player_id
        || extra.layer_uid
        || extra.uid
        || extra.id
        || ''
      );
      const extractSolidColor = (value, fallback = '#2563eb') => {
        if (typeof value === 'string' && value.trim()) return value.trim();
        if (value && typeof value === 'object' && Array.isArray(value.colorStops) && value.colorStops.length) {
          const first = value.colorStops.find((row) => row && typeof row.color === 'string' && row.color.trim());
          if (first) return first.color.trim();
        }
        return fallback;
      };
      const childByRole = (role) => childObjects.find((child) => String((child?.data || {}).role || '').trim() === role);
      const center2d = objectCenter2d(obj);
      const measuredWidth = Math.max(
        8,
        objectBaseWidth2d(obj) * (Number(obj?.scaleX) || 1),
        toNumber(obj.width, 0) * (Number(obj?.scaleX) || 1)
      );
      const measuredHeight = Math.max(
        8,
        objectBaseHeight2d(obj) * (Number(obj?.scaleY) || 1),
        toNumber(obj.height, 0) * (Number(obj?.scaleY) || 1)
      );
      if (obj.type === 'rect' && kind === 'zone') {
        const world = canvasToWorld(center2d.x, center2d.y);
        data.zones.push({
          uid: `zone:${index}`,
          x: world.x,
          z: world.z,
          width: sizeToMeters(measuredWidth, stateMeta.width, stateMeta.fieldWidth, 2, stateMeta.fieldWidth),
          depth: sizeToMeters(measuredHeight, stateMeta.height, stateMeta.fieldHeight, 2, stateMeta.fieldHeight),
          fill: safeText(obj.fill, '#0ea5e9'),
          stroke: safeText(obj.stroke, '#fde047'),
          opacity: String(obj.fill || '').includes('0.00') ? 0.04 : 0.18,
          rotationY: -degToRad(obj.angle || 0),
        });
        return;
      }
      if (
        ((obj.type === 'rect' || obj.type === 'triangle' || obj.type === 'circle') && (
          kind === 'shape-square'
          || kind === 'shape-rect'
          || kind === 'shape-rect-long'
          || kind === 'shape-circle'
          || kind === 'shape-triangle'
          || kind === 'shape-diamond'
        ))
        || (obj.type === 'group' && (
          kind === 'shape-square'
          || kind === 'shape-rect'
          || kind === 'shape-rect-long'
          || kind.startsWith('shape-lane-')
          || kind.startsWith('shape-band-')
        ))
      ) {
        const world = canvasToWorld(center2d.x, center2d.y);
        data.shapes.push({
          uid: `shape:${index}`,
          x: world.x,
          z: world.z,
          width: sizeToMeters(measuredWidth, stateMeta.width, stateMeta.fieldWidth, 0.9, stateMeta.fieldWidth),
          depth: sizeToMeters(measuredHeight, stateMeta.height, stateMeta.fieldHeight, 0.9, stateMeta.fieldHeight),
          fill: safeText(obj.fill, safeText(extra.color, '#22d3ee')),
          stroke: safeText(obj.stroke, safeText(extra.color, '#22d3ee')),
          opacity: safeText(obj.fill).includes('rgba') ? 0.18 : 0.24,
          rotationY: -degToRad(obj.angle || 0),
          shapeKind: kind,
        });
        return;
      }
      if (obj.type === 'circle' && ['token', 'player', 'player_red', 'player_blue', 'ball_token'].includes(kind)) {
        const world = canvasToWorld(center2d.x, center2d.y);
        const label = safeText(extra.label, `J${tokenIndex + 1}`);
        data.tokens.set(`token:${label}:${tokenIndex}`, {
          uid: `token:${label}:${tokenIndex}`,
          label,
          x: world.x,
          z: world.z,
          radius: radiusToMeters(obj.radius),
          fill: safeText(obj.fill, '#2563eb'),
          stroke: safeText(obj.stroke, '#ffffff'),
          facingRad: Number.isFinite(tokenFacingRad) ? tokenFacingRad : NaN,
          photoUrl: resolveTokenPhotoUrl(obj),
        });
        tokenIndex += 1;
        return;
      }
      if (obj.type === 'group' && ['token', 'player', 'player_red', 'player_blue'].includes(kind)) {
        const world = canvasToWorld(center2d.x, center2d.y);
        const label = safeText(
          extra.playerName || extra.label || childByRole('token_name')?.text || childByRole('token_number')?.text,
          `J${tokenIndex + 1}`
        );
        const fillNode = childByRole('token_fill');
        const ringNode = childByRole('token_outer_ring') || childByRole('token_base');
        const measuredRadius = radiusToMeters(Math.max(toNumber(obj.width, 44), toNumber(obj.height, 44)) / 2.4) || 1.1;
        const tokenKey = tokenIdentity ? `token:${tokenIdentity}` : `token:${label}:${tokenIndex}`;
        data.tokens.set(tokenKey, {
          uid: tokenKey,
          label,
          x: world.x,
          z: world.z,
          radius: measuredRadius,
          fill: extractSolidColor(fillNode?.fill, safeText(extra.token_base_color, '#2563eb')),
          stroke: extractSolidColor(ringNode?.stroke, safeText(ringNode?.fill, '#ffffff')),
          facingRad: Number.isFinite(tokenFacingRad) ? tokenFacingRad : NaN,
          photoUrl: resolveTokenPhotoUrl(obj, childObjects),
        });
        tokenIndex += 1;
        return;
      }
      if (obj.type === 'group' && (kind === 'cone' || kind === 'cone_striped')) {
        const world = canvasToWorld(center2d.x, center2d.y);
        const baseRadius = kind === 'cone_striped' ? 0.62 : 0.58;
        data.cones.set(`cone:${coneIndex}`, {
          uid: `cone:${coneIndex}`,
          x: world.x,
          z: world.z,
          radius: radiusToMeters((toNumber(obj.width, 28) + toNumber(obj.height, 28)) / 4) || baseRadius,
          height: radiusToMeters(Math.max(toNumber(obj.height, 28), 28)) * 2.25 || 1.45,
          fill: safeText(obj.fill, kind === 'cone_striped' ? '#f59e0b' : '#ef4444'),
          stroke: safeText(obj.stroke, '#fff7ed'),
          striped: kind === 'cone_striped',
          shape: 'round_cone',
        });
        coneIndex += 1;
        return;
      }
      if ((obj.type === 'circle' || obj.type === 'text' || obj.type === 'i-text') && kind === 'ball') {
        const world = canvasToWorld(center2d.x, center2d.y);
        data.balls.set(`ball:${ballIndex}`, {
          uid: `ball:${ballIndex}`,
          x: world.x,
          z: world.z,
        });
        ballIndex += 1;
        return;
      }
      if ((obj.type === 'text' || obj.type === 'i-text') && kind === 'emoji_ball') {
        const world = canvasToWorld(center2d.x, center2d.y);
        data.balls.set(`ball:${ballIndex}`, {
          uid: `ball:${ballIndex}`,
          x: world.x,
          z: world.z,
        });
        ballIndex += 1;
        return;
      }
      if (
        ((obj.type === 'text' || obj.type === 'i-text') && kind === 'emoji_cone')
        || ((obj.type === 'triangle' || obj.type === 'text' || obj.type === 'i-text') && (kind === 'cone' || kind === 'cone_striped'))
        || (obj.type === 'triangle' && !isArrowHeadKind(kind))
      ) {
        const world = canvasToWorld(center2d.x, center2d.y);
        const baseRadius = kind === 'cone_striped' ? 0.62 : 0.58;
        data.cones.set(`cone:${coneIndex}`, {
          uid: `cone:${coneIndex}`,
          x: world.x,
          z: world.z,
          radius: radiusToMeters((toNumber(obj.width, 30) + toNumber(obj.height, 30)) / 4) || baseRadius,
          height: radiusToMeters(Math.max(toNumber(obj.height, 30), 22)) * 2.25 || 1.45,
          fill: safeText(obj.fill, kind === 'cone_striped' ? '#f59e0b' : '#f97316'),
          stroke: safeText(obj.stroke, '#fff7ed'),
          striped: kind === 'cone_striped',
          shape: obj.type === 'triangle' ? 'triangle_marker' : 'round_cone',
        });
        coneIndex += 1;
        return;
      }
      if (
        (obj.type === 'text' || obj.type === 'i-text' || obj.type === 'rect')
        && (kind === 'emoji_mini_goal' || kind === 'emoji_goal' || kind === 'goal' || kind === 'mini_goal')
      ) {
        const world = canvasToWorld(center2d.x, center2d.y);
        data.goals.push({
          uid: `goal:${goalIndex}`,
          x: world.x,
          z: world.z,
          rotationY: world.x > 0 ? Math.PI / 2 : -Math.PI / 2,
          scale: kind === 'emoji_goal' ? 1.28 : 1,
        });
        goalIndex += 1;
        return;
      }
      if (obj.type === 'group' && (kind === 'goal' || kind === 'mini_goal')) {
        const world = canvasToWorld(center2d.x, center2d.y);
        data.goals.push({
          uid: `goal:${goalIndex}`,
          x: world.x,
          z: world.z,
          rotationY: world.x > 0 ? Math.PI / 2 : -Math.PI / 2,
          scale: 1.03,
        });
        goalIndex += 1;
        return;
      }
      if (obj.type === 'line') {
        const start2d = transformPoint2d(obj.x1, obj.y1, obj);
        const end2d = transformPoint2d(obj.x2, obj.y2, obj);
        const from = canvasToWorld(start2d.x, start2d.y);
        const to = canvasToWorld(end2d.x, end2d.y);
        data.paths.push({
          uid: `path:${index}`,
          from,
          to,
          color: safeText(obj.stroke, '#38bdf8'),
          dashed: Array.isArray(obj.strokeDashArray) && obj.strokeDashArray.length > 0,
          curved: false,
        });
        return;
      }
      if (obj.type === 'group' && (isArrowKind(kind) || kind === 'arrow_head')) {
        const lineNode = childObjects.find((child) => safeText(child?.type).toLowerCase() === 'line') || null;
        const start2d = lineNode
          ? childPointInGroup2d(obj, lineNode, lineNode.x1, lineNode.y1)
          : transformPoint2d(-(measuredWidth / 2), 0, obj);
        const end2d = lineNode
          ? childPointInGroup2d(obj, lineNode, lineNode.x2, lineNode.y2)
          : transformPoint2d(measuredWidth / 2, 0, obj);
        const from = canvasToWorld(start2d.x, start2d.y);
        const to = canvasToWorld(end2d.x, end2d.y);
        data.paths.push({
          uid: `path:${index}`,
          from,
          to,
          color: safeText(lineNode?.stroke, safeText(obj.stroke, '#38bdf8')),
          dashed: kind === 'arrow-dot' || kind === 'arrow-dash' || (Array.isArray(lineNode?.strokeDashArray) && lineNode.strokeDashArray.length > 0),
          curved: kind === 'arrow-curve',
        });
        return;
      }
      if (obj.type === 'textbox' || obj.type === 'text') {
        const label = safeText(obj.text || extra.label);
        if (!label || kind.startsWith('emoji_')) return;
        const world = canvasToWorld(center2d.x, center2d.y);
        data.notes.push({
          uid: `note:${index}`,
          label,
          x: world.x,
          z: world.z,
        });
      }
    });
    return data;
  };

  const framesData = steps.map(buildFrameData);

  const createTokenActor = (entry) => {
    const radius = entry.radius;
    const group = new THREE.Group();
    const fill = parseColor(entry.fill, '#2563eb');
    const accent = parseColor(entry.stroke, '#ffffff');
    const playerPhotoUrl = safeText(entry.photoUrl, '');
    if (playerPhotoUrl) {
      const darkerFill = tintColor(fill, -0.16);
      const sockColor = accent.getHSL({ h: 0, s: 0, l: 0 }).l > 0.72 ? fill : accent;
      const baseGlow = new THREE.Mesh(
        new THREE.CircleGeometry(radius * 1.42, 28),
        new THREE.MeshBasicMaterial({ color: fill, transparent: true, opacity: 0.24, depthWrite: false })
      );
      baseGlow.rotation.x = -Math.PI / 2;
      baseGlow.position.y = 0.035;
      group.add(baseGlow);

      const feetShadow = new THREE.Mesh(
        new THREE.CircleGeometry(radius * 0.96, 24),
        new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.24, depthWrite: false })
      );
      feetShadow.rotation.x = -Math.PI / 2;
      feetShadow.position.y = 0.04;
      group.add(feetShadow);
      group.add(createShadowStreak(radius));

      const shorts = new THREE.Mesh(
        new THREE.BoxGeometry(radius * 1.18, 0.68, radius * 0.72),
        new THREE.MeshStandardMaterial({ color: darkerFill, roughness: 0.66, metalness: 0.04 })
      );
      shorts.position.y = 0.98;
      shorts.castShadow = true;
      group.add(shorts);

      const armGeo = new THREE.CapsuleGeometry(radius * 0.12, 0.82, 4, 10);
      const leftArm = new THREE.Mesh(armGeo, new THREE.MeshStandardMaterial({ color: fill, roughness: 0.5 }));
      leftArm.position.set(-radius * 0.56, 1.74, 0);
      leftArm.rotation.z = 0.34;
      leftArm.castShadow = true;
      group.add(leftArm);
      const rightArm = leftArm.clone();
      rightArm.position.x = radius * 0.56;
      rightArm.rotation.z = -0.34;
      group.add(rightArm);

      const legGeo = new THREE.CapsuleGeometry(radius * 0.15, 1.2, 4, 10);
      const leftLeg = new THREE.Mesh(legGeo, new THREE.MeshStandardMaterial({ color: 0xe5e7eb, roughness: 0.64 }));
      leftLeg.position.set(-radius * 0.22, 0.42, 0);
      leftLeg.castShadow = true;
      group.add(leftLeg);
      const rightLeg = leftLeg.clone();
      rightLeg.position.x = radius * 0.22;
      group.add(rightLeg);

      const leftSock = new THREE.Mesh(
        new THREE.CylinderGeometry(radius * 0.11, radius * 0.11, 0.5, 10),
        new THREE.MeshStandardMaterial({ color: sockColor, roughness: 0.58 })
      );
      leftSock.position.set(-radius * 0.22, 0.06, 0);
      group.add(leftSock);
      const rightSock = leftSock.clone();
      rightSock.position.x = radius * 0.22;
      group.add(rightSock);

      const torsoPivot = new THREE.Group();
      torsoPivot.position.y = 0.18;
      group.add(torsoPivot);

      const cutout = createPlayerCutoutSprite(playerPhotoUrl, radius, fill);
      if (cutout) torsoPivot.add(cutout);

      const badge = createLabelSprite(entry.label, '#ffffff');
      badge.scale.set(2.8, 1.4, 1);
      badge.position.set(0, 2.12, radius * 0.72);
      group.add(badge);

      group.userData = {
        baseY: 0,
        radius,
        badge,
        isPhotoPlayer: true,
        leftArm,
        rightArm,
        leftLeg,
        rightLeg,
        leftSock,
        rightSock,
        torsoPivot,
        cutout,
      };
      group.position.set(entry.x, 0, entry.z);
      upgradeActorToHumanoidModel(group, entry, fill, accent);
      return group;
    }
    const darkerFill = tintColor(fill, -0.16);
    const sockColor = accent.getHSL({ h: 0, s: 0, l: 0 }).l > 0.72 ? fill : accent;
    const baseGlow = new THREE.Mesh(
      new THREE.CircleGeometry(radius * 1.42, 28),
      new THREE.MeshBasicMaterial({ color: fill, transparent: true, opacity: 0.26, depthWrite: false })
    );
    baseGlow.rotation.x = -Math.PI / 2;
    baseGlow.position.y = 0.035;
    group.add(baseGlow);

    const feetShadow = new THREE.Mesh(
      new THREE.CircleGeometry(radius * 0.92, 24),
      new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.22, depthWrite: false })
    );
    feetShadow.rotation.x = -Math.PI / 2;
    feetShadow.position.y = 0.04;
    group.add(feetShadow);
    group.add(createShadowStreak(radius));

    const shorts = new THREE.Mesh(
      new THREE.BoxGeometry(radius * 1.3, 0.8, radius * 0.88),
      new THREE.MeshStandardMaterial({ color: darkerFill, roughness: 0.66, metalness: 0.04 })
    );
    shorts.position.y = 1.05;
    shorts.castShadow = true;
    group.add(shorts);

    const torso = new THREE.Mesh(
      new THREE.CapsuleGeometry(radius * 0.45, 1.35, 6, 14),
      new THREE.MeshStandardMaterial({ color: fill, roughness: 0.46, metalness: 0.04 })
    );
    torso.position.y = 1.9;
    torso.castShadow = true;
    group.add(torso);

    const chestBand = new THREE.Mesh(
      new THREE.BoxGeometry(radius * 1.1, 0.18, radius * 0.75),
      new THREE.MeshStandardMaterial({ color: accent, roughness: 0.48 })
    );
    chestBand.position.y = 1.96;
    chestBand.position.z = radius * 0.08;
    group.add(chestBand);

    const armGeo = new THREE.CapsuleGeometry(radius * 0.14, 0.85, 4, 10);
    const skinMat = new THREE.MeshStandardMaterial({ color: 0xf1c27d, roughness: 0.9 });
    const leftArm = new THREE.Mesh(armGeo, new THREE.MeshStandardMaterial({ color: fill, roughness: 0.5 }));
    leftArm.position.set(-radius * 0.56, 1.86, 0);
    leftArm.rotation.z = 0.3;
    leftArm.castShadow = true;
    group.add(leftArm);
    const rightArm = leftArm.clone();
    rightArm.position.x = radius * 0.56;
    rightArm.rotation.z = -0.3;
    group.add(rightArm);

    const legGeo = new THREE.CapsuleGeometry(radius * 0.16, 1.18, 4, 10);
    const leftLeg = new THREE.Mesh(legGeo, new THREE.MeshStandardMaterial({ color: 0xe5e7eb, roughness: 0.64 }));
    leftLeg.position.set(-radius * 0.24, 0.42, 0);
    leftLeg.castShadow = true;
    group.add(leftLeg);
    const rightLeg = leftLeg.clone();
    rightLeg.position.x = radius * 0.24;
    group.add(rightLeg);

    const leftSock = new THREE.Mesh(
      new THREE.CylinderGeometry(radius * 0.12, radius * 0.12, 0.54, 10),
      new THREE.MeshStandardMaterial({ color: sockColor, roughness: 0.58 })
    );
    leftSock.position.set(-radius * 0.24, 0.06, 0);
    group.add(leftSock);
    const rightSock = leftSock.clone();
    rightSock.position.x = radius * 0.24;
    group.add(rightSock);

    const head = new THREE.Mesh(new THREE.SphereGeometry(radius * 0.38, 20, 18), skinMat);
    head.position.y = 2.85;
    head.castShadow = true;
    group.add(head);

    const hair = new THREE.Mesh(
      new THREE.SphereGeometry(radius * 0.26, 18, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.82 })
    );
    hair.position.set(0, 2.96, -radius * 0.04);
    group.add(hair);

    const badge = createLabelSprite(entry.label, '#ffffff');
    badge.scale.set(2.8, 1.4, 1);
    badge.position.set(0, 2.05, radius * 0.5);
    group.add(badge);

    group.userData = { baseY: 0, radius, leftArm, rightArm, leftLeg, rightLeg, badge };
    group.position.set(entry.x, 0, entry.z);
    upgradeActorToHumanoidModel(group, entry, fill, accent);
    return group;
  };

  const createBallActor = (entry) => {
    const group = new THREE.Group();
    const ball = new THREE.Mesh(
      new THREE.SphereGeometry(0.46, 24, 24),
      new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.34, metalness: 0.08 })
    );
    ball.castShadow = true;
    ball.position.y = 0.56;
    group.add(ball);
    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(0.56, 24),
      new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.2 })
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.03;
    group.add(shadow);
    group.position.set(entry.x, 0, entry.z);
    return group;
  };

  const createConeActor = (entry) => {
    const group = new THREE.Group();
    const fill = parseColor(entry.fill, entry.striped ? '#f59e0b' : '#f97316');
    const stripe = parseColor(entry.stroke, '#fff7ed');
    const markerShape = safeText(entry.shape, 'round_cone');

    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(entry.radius * 1.05, 20),
      new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.22, depthWrite: false })
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.035;
    group.add(shadow);

    const base = new THREE.Mesh(
      new THREE.CylinderGeometry(entry.radius * 0.86, entry.radius * 0.94, 0.16, 18),
      new THREE.MeshStandardMaterial({ color: tintColor(fill, -0.18), roughness: 0.78, metalness: 0.04 })
    );
    base.position.y = 0.08;
    base.castShadow = true;
    group.add(base);

    const bodyGeometry = markerShape === 'triangle_marker'
      ? new THREE.ConeGeometry(entry.radius * 0.88, entry.height, 3)
      : new THREE.ConeGeometry(entry.radius * 0.72, entry.height, 20);
    const body = new THREE.Mesh(
      bodyGeometry,
      new THREE.MeshStandardMaterial({ color: fill, roughness: 0.44, metalness: 0.08 })
    );
    body.position.y = (entry.height / 2) + 0.12;
    if (markerShape === 'triangle_marker') body.rotation.y = Math.PI / 3;
    body.castShadow = true;
    group.add(body);

    if (entry.striped || markerShape === 'triangle_marker') {
      const ring = new THREE.Mesh(
        markerShape === 'triangle_marker'
          ? new THREE.CylinderGeometry(entry.radius * 0.42, entry.radius * 0.5, 0.08, 3)
          : new THREE.TorusGeometry(entry.radius * 0.44, entry.radius * 0.1, 10, 24),
        new THREE.MeshStandardMaterial({ color: stripe, roughness: 0.38, metalness: 0.05 })
      );
      if (markerShape === 'triangle_marker') {
        ring.rotation.y = Math.PI / 3;
      } else {
        ring.rotation.x = Math.PI / 2;
      }
      ring.position.y = Math.max(0.26, (entry.height * 0.52));
      group.add(ring);
    }

    group.position.set(entry.x, 0, entry.z);
    return group;
  };

  const createShapePlane = (entry) => {
    const shapeKind = safeText(entry.shapeKind, 'shape-rect');
    const group = new THREE.Group();
    const fill = parseColor(entry.fill, '#22d3ee');
    const stroke = parseColor(entry.stroke, '#22d3ee');
    const isCircle = shapeKind === 'shape-circle';
    const planeGeometry = isCircle
      ? new THREE.CircleGeometry(Math.max(entry.width, entry.depth) / 2, 36)
      : new THREE.PlaneGeometry(entry.width, entry.depth);
    const plane = new THREE.Mesh(
      planeGeometry,
      new THREE.MeshBasicMaterial({
        color: fill,
        transparent: true,
        opacity: clamp(entry.opacity || 0.18, 0.08, 0.34),
        side: THREE.DoubleSide,
        depthWrite: false,
      })
    );
    plane.rotation.x = -Math.PI / 2;
    plane.position.y = 0.055;
    group.add(plane);

    if (!isCircle) {
      const edgePoints = [
        new THREE.Vector3(-entry.width / 2, 0.085, -entry.depth / 2),
        new THREE.Vector3(entry.width / 2, 0.085, -entry.depth / 2),
        new THREE.Vector3(entry.width / 2, 0.085, entry.depth / 2),
        new THREE.Vector3(-entry.width / 2, 0.085, entry.depth / 2),
        new THREE.Vector3(-entry.width / 2, 0.085, -entry.depth / 2),
      ];
      group.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(edgePoints),
        new THREE.LineBasicMaterial({ color: stroke, transparent: true, opacity: 0.94 })
      ));
    }

    group.position.set(entry.x, 0, entry.z);
    group.rotation.y = toNumber(entry.rotationY, 0);
    return group;
  };

  const renderStaticWorld = (frameData) => {
    clearGroup(dynamicRoot);
    const world = {
      tokens: new Map(),
      balls: new Map(),
      cones: new Map(),
      paths: [],
      notes: [],
      trails: [],
    };

    frameData.zones.forEach((zone) => {
      const plane = new THREE.Mesh(
        new THREE.PlaneGeometry(zone.width, zone.depth),
        new THREE.MeshBasicMaterial({
          color: parseColor(zone.fill, '#0ea5e9'),
          transparent: true,
          opacity: zone.opacity,
          side: THREE.DoubleSide,
        })
      );
      plane.rotation.x = -Math.PI / 2;
      plane.position.set(zone.x, 0.05, zone.z);
      plane.rotation.z = 0;
      plane.rotation.y = toNumber(zone.rotationY, 0);
      dynamicRoot.add(plane);
      const edgePoints = [
        new THREE.Vector3(-zone.width / 2, 0.08, -zone.depth / 2),
        new THREE.Vector3(zone.width / 2, 0.08, -zone.depth / 2),
        new THREE.Vector3(zone.width / 2, 0.08, zone.depth / 2),
        new THREE.Vector3(-zone.width / 2, 0.08, zone.depth / 2),
        new THREE.Vector3(-zone.width / 2, 0.08, -zone.depth / 2),
      ];
      const edgeGeometry = new THREE.BufferGeometry().setFromPoints(edgePoints);
      const line = new THREE.Line(
        edgeGeometry,
        new THREE.LineDashedMaterial({
          color: parseColor(zone.stroke, '#fde047'),
          dashSize: 1.4,
          gapSize: 0.6,
          transparent: true,
          opacity: 0.94,
        })
      );
      line.computeLineDistances();
      line.position.set(zone.x, 0, zone.z);
      line.rotation.y = toNumber(zone.rotationY, 0);
      dynamicRoot.add(line);
    });

    frameData.shapes.forEach((shapeData) => {
      const shape = createShapePlane(shapeData);
      dynamicRoot.add(shape);
    });

    frameData.goals.forEach((goalData) => {
      const goal = createGoalFrame();
      goal.position.set(goalData.x, 0.08, goalData.z);
      goal.rotation.y = goalData.rotationY;
      goal.scale.setScalar(toNumber(goalData.scale, 1));
      dynamicRoot.add(goal);
    });

    frameData.cones.forEach((entry, uid) => {
      const actor = createConeActor(entry);
      dynamicRoot.add(actor);
      world.cones.set(uid, { group: actor, entry });
    });

    frameData.paths.forEach((pathData) => {
      const points = pathData.curved
        ? createArrowCurve(pathData.from, pathData.to).getPoints(36)
        : [
          new THREE.Vector3(pathData.from.x, 0.36, pathData.from.z),
          new THREE.Vector3(pathData.to.x, 0.36, pathData.to.z),
        ];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const color = parseColor(pathData.color, '#38bdf8');
      const glow = new THREE.Line(
        geometry.clone(),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.16 })
      );
      glow.scale.setScalar(1.004);
      dynamicRoot.add(glow);
      let line;
      if (pathData.dashed) {
        line = new THREE.Line(
          geometry,
          new THREE.LineDashedMaterial({ color, dashSize: 1.6, gapSize: 1.1, transparent: true, opacity: 0.92 })
        );
        line.computeLineDistances();
      } else {
        line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95 }));
      }
      dynamicRoot.add(line);
      const arrowHead = createArrowHead(points[points.length - 2], points[points.length - 1], color);
      if (arrowHead) dynamicRoot.add(arrowHead);
      world.paths.push({ line, glow, dashed: !!pathData.dashed });
    });

    frameData.notes.forEach((noteData) => {
      const card = createCardLabel(noteData.label);
      card.position.set(noteData.x, 0.14, noteData.z);
      card.rotation.y = -0.12;
      dynamicRoot.add(card);
      world.notes.push(card);
    });

    frameData.tokens.forEach((entry, uid) => {
      const actor = createTokenActor(entry);
      dynamicRoot.add(actor);
      const trail = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(entry.x, 0.16, entry.z),
          new THREE.Vector3(entry.x, 0.16, entry.z),
        ]),
        new THREE.LineBasicMaterial({ color: tintColor(entry.fill, 0.12), transparent: true, opacity: 0.0 })
      );
      dynamicRoot.add(trail);
      world.trails.push({ line: trail, type: 'token', entry });
      world.tokens.set(uid, { group: actor, entry, trail });
    });

    frameData.balls.forEach((entry, uid) => {
      const actor = createBallActor(entry);
      dynamicRoot.add(actor);
      const trail = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(entry.x, 0.18, entry.z),
          new THREE.Vector3(entry.x, 0.18, entry.z),
        ]),
        new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.0 })
      );
      dynamicRoot.add(trail);
      world.trails.push({ line: trail, type: 'ball', entry });
      world.balls.set(uid, { group: actor, entry, trail });
    });

    return world;
  };

  const setProgressUI = (value) => {
    const normalized = clamp(value, 0, 1);
    const pct = Math.round(normalized * 100);
    if (progressBar) progressBar.style.width = `${pct}%`;
    if (progressLabel) progressLabel.textContent = `${pct}%`;
  };

  const updateHud = (stepIndex, localProgress = 0) => {
    const step = steps[stepIndex] || steps[0];
    if (titleEl) titleEl.textContent = safeText(step.title, `Fase ${stepIndex + 1}`);
    if (metaEl) metaEl.textContent = `Paso ${stepIndex + 1}/${steps.length} · ${Math.max(1, toNumber(step.duration, 4))} s`;
    setProgressUI(((stepIndex + clamp(localProgress, 0, 1)) / Math.max(steps.length, 1)));
  };

  const applyInterpolatedState = (stepIndex, localProgress = 0, elapsedSeconds = 0) => {
    if (!activeWorld) return;
    const eased = smooth(clamp(localProgress, 0, 1));
    const frameData = framesData[stepIndex] || framesData[0];
    const nextFrameData = framesData[(stepIndex + 1) % framesData.length] || frameData;

    activeWorld.tokens.forEach(({ group, entry, trail }, uid) => {
      const next = nextFrameData.tokens.get(uid);
      const target = next || entry;
      const x = lerp(entry.x, target.x, next ? eased : 0);
      const z = lerp(entry.z, target.z, next ? eased : 0);
      const dx = target.x - entry.x;
      const dz = target.z - entry.z;
      const moveStrength = clamp(Math.sqrt((dx * dx) + (dz * dz)) / 8, 0, 1);
      const entryFacing = Number.isFinite(entry.facingRad) ? entry.facingRad : NaN;
      const nextFacing = next && Number.isFinite(next.facingRad) ? next.facingRad : NaN;
      const stride = Math.sin((elapsedSeconds * 8) + (x * 0.1) + (z * 0.06)) * moveStrength;
      const idleSwing = Math.sin((elapsedSeconds * 2.6) + (x * 0.04) + (z * 0.05)) * 0.06;
      group.position.x = x;
      group.position.z = z;
      const isMoving = moveStrength > 0.032;
      const movementTargetRotation = Math.atan2(dx, dz);
      const explicitTargetRotation = Number.isFinite(nextFacing) ? nextFacing : (Number.isFinite(entryFacing) ? entryFacing : movementTargetRotation);
      const shouldForceFacing = Number.isFinite(entryFacing) || Number.isFinite(nextFacing);
      const targetRotation = shouldForceFacing ? explicitTargetRotation : (isMoving ? movementTargetRotation : (group.userData?.heading ?? explicitTargetRotation));
      const currentHeading = typeof group.userData?.heading === 'number' ? group.userData.heading : targetRotation;
      const smoothedHeading = (isMoving || shouldForceFacing)
        ? lerpAngle(currentHeading, targetRotation, 0.22)
        : currentHeading;
      const baseHeight = group.userData?.isHumanoidModel ? 0.018 : 0;
      group.position.y = isMoving
        ? (baseHeight + Math.sin((elapsedSeconds * 3.2) + x * 0.08 + z * 0.08) * 0.06)
        : baseHeight;
      group.userData = { ...(group.userData || {}), heading: smoothedHeading };
      group.rotation.y = smoothedHeading;
      if (!group.userData?.humanoidMotion?.mixer) {
        if (group.userData.leftArm) group.userData.leftArm.rotation.x = stride * 0.55;
        if (group.userData.rightArm) group.userData.rightArm.rotation.x = -stride * 0.55;
        if (group.userData.leftLeg) group.userData.leftLeg.rotation.x = -stride * 0.34;
        if (group.userData.rightLeg) group.userData.rightLeg.rotation.x = stride * 0.34;
      }
      if (group.userData.isPhotoPlayer || (group.userData.isHumanoidModel && !group.userData?.humanoidMotion?.mixer)) {
        if (group.userData.leftArm) group.userData.leftArm.rotation.x = (stride * 0.66) + idleSwing;
        if (group.userData.rightArm) group.userData.rightArm.rotation.x = (-stride * 0.66) - idleSwing;
        if (group.userData.leftLeg) group.userData.leftLeg.rotation.x = (-stride * 0.46) + (idleSwing * 0.35);
        if (group.userData.rightLeg) group.userData.rightLeg.rotation.x = (stride * 0.46) - (idleSwing * 0.35);
        if (group.userData.torsoPivot) {
          group.userData.torsoPivot.position.y = 0.18 + Math.max(0, moveStrength) * 0.12 + Math.sin(elapsedSeconds * 6 + x * 0.08) * 0.03;
          group.userData.torsoPivot.rotation.x = (-stride * 0.08) + (idleSwing * 0.16);
          group.userData.torsoPivot.rotation.z = idleSwing * 0.12;
        }
        if (group.userData.cutout) {
          group.userData.cutout.rotation.y = Math.sin(elapsedSeconds * 3.2 + z * 0.04) * 0.05;
        }
        if (group.userData.portrait) {
          group.userData.portrait.position.y = 2.48 + Math.sin(elapsedSeconds * 4.2 + x * 0.08) * 0.04;
          group.userData.portrait.rotation.y = Math.sin(elapsedSeconds * 2.8 + z * 0.05) * 0.08;
        }
      }
      applyHumanoidAnimationState(group, moveStrength);
      if (group.userData.badge) {
        group.userData.badge.position.y = (group.userData.isPhotoPlayer || group.userData.isHumanoidModel)
          ? 2.12 + (Math.sin(elapsedSeconds * 5 + x * 0.08) * 0.04)
          : 2.03 + (Math.sin(elapsedSeconds * 5 + x * 0.08) * 0.04);
      }
      if (trail?.geometry) {
        const trailPoints = [
          new THREE.Vector3(x - (dx * 0.28), 0.14, z - (dz * 0.28)),
          new THREE.Vector3(x, 0.14, z),
        ];
        trail.geometry.dispose?.();
        trail.geometry = new THREE.BufferGeometry().setFromPoints(trailPoints);
        trail.material.opacity = moveStrength * 0.52;
      }
      group.children.forEach((child) => {
        if (child.material && typeof child.material.opacity === 'number' && child.geometry?.type === 'CircleGeometry') {
          child.material.opacity = 0.18 + Math.sin(elapsedSeconds * 4.6 + x * 0.06) * 0.06;
        }
      });
    });

    activeWorld.balls.forEach(({ group, entry, trail }, uid) => {
      const next = nextFrameData.balls.get(uid);
      const target = next || entry;
      const dx = target.x - entry.x;
      const dz = target.z - entry.z;
      const moveStrength = clamp(Math.sqrt((dx * dx) + (dz * dz)) / 10, 0, 1);
      group.position.x = lerp(entry.x, target.x, next ? eased : 0);
      group.position.z = lerp(entry.z, target.z, next ? eased : 0);
      group.position.y = (next ? Math.sin(eased * Math.PI) * 1.1 : 0) + 0.02;
      group.rotation.y += 0.05;
      if (trail?.geometry) {
        const trailPoints = [
          new THREE.Vector3(group.position.x - (dx * 0.38), 0.18, group.position.z - (dz * 0.38)),
          new THREE.Vector3(group.position.x, 0.18, group.position.z),
        ];
        trail.geometry.dispose?.();
        trail.geometry = new THREE.BufferGeometry().setFromPoints(trailPoints);
        trail.material.opacity = moveStrength * 0.68;
      }
    });

    activeWorld.cones.forEach(({ group, entry }, uid) => {
      const next = nextFrameData.cones.get(uid);
      const target = next || entry;
      group.position.x = lerp(entry.x, target.x, next ? eased : 0);
      group.position.z = lerp(entry.z, target.z, next ? eased : 0);
      group.rotation.y = next ? Math.atan2(target.x - entry.x, target.z - entry.z) : 0;
    });

    activeWorld.paths.forEach(({ line, glow, dashed }, index) => {
      if (!line.material) return;
      const alpha = dashed ? 0.5 + (Math.sin(elapsedSeconds * 4 + index) * 0.18) : 0.82 + (Math.sin(elapsedSeconds * 3 + index) * 0.08);
      line.material.opacity = clamp(alpha, 0.28, 1);
      if (glow?.material) glow.material.opacity = clamp(alpha * 0.28, 0.08, 0.36);
      if (dashed && typeof line.material.dashOffset === 'number') {
        line.material.dashOffset = -elapsedSeconds * 2.2;
      }
    });

    activeWorld.notes.forEach((note, index) => {
      note.position.y = 0.14 + Math.sin(elapsedSeconds * 2 + index) * 0.02;
      note.rotation.z = Math.sin(elapsedSeconds * 1.6 + note.userData.floatPhase) * 0.02;
    });

    updateHud(stepIndex, localProgress);
  };

  const buildWorldForStep = (stepIndex) => {
    const frameData = framesData[stepIndex] || framesData[0];
    activeWorld = renderStaticWorld(frameData);
    updateHud(stepIndex, progress);
  };

  const applyCamera = () => {
    const pitch = clamp(orbit.phi, 0.12, 1.42);
    const radius = clamp(orbit.radius, 40, 180);
    const x = orbit.targetX + Math.cos(orbit.theta) * Math.sin(pitch) * radius;
    const y = Math.cos(pitch) * radius + 16;
    const z = orbit.targetZ + Math.sin(orbit.theta) * Math.sin(pitch) * radius;
    camera.position.set(x, y, z);
    camera.lookAt(orbit.targetX, 0, orbit.targetZ);
  };

  const setCameraPreset = (name) => {
    const preset = cameraPresets[name] || cameraPresets.broadcast;
    currentPreset = cameraPresets[name] ? name : 'broadcast';
    Object.assign(orbit, preset);
    applyCamera();
    if (cameraSelect) cameraSelect.value = currentPreset;
  };

  const resize = () => {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(320, Math.round(rect.width || 960));
    const height = Math.max(240, Math.round(rect.height || 540));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    applyCamera();
    publishRenderDiagnostics();
  };

  const stopPlayback = () => {
    isPlaying = false;
    playbackState = null;
    progress = 0;
    if (playBtn) playBtn.textContent = 'Reproducir';
    buildWorldForStep(currentStepIndex);
    applyInterpolatedState(currentStepIndex, 0, 0);
  };

  const showStep = (index) => {
    currentStepIndex = (index + steps.length) % steps.length;
    progress = 0;
    playbackState = null;
    buildWorldForStep(currentStepIndex);
    applyInterpolatedState(currentStepIndex, 0, 0);
    applyCamera();
    publishRenderDiagnostics();
  };

  const startPlayback = () => {
    if (!steps.length) return;
    isPlaying = true;
    playbackState = {
      stepIndex: currentStepIndex,
      startedAt: performance.now(),
      durationMs: Math.max(1, toNumber((steps[currentStepIndex] || steps[0]).duration, 4)) * 1000,
    };
    if (playBtn) playBtn.textContent = 'Pausar';
    buildWorldForStep(currentStepIndex);
  };

  const togglePlayback = () => {
    if (isPlaying) {
      stopPlayback();
      return;
    }
    startPlayback();
  };

  const toggleFullscreen = async () => {
    if (!sceneCard) return;
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await sceneCard.requestFullscreen?.();
    } catch (error) {
      // ignore
    }
  };

  const updateRecordButton = () => {
    if (!recordBtn) return;
    recordBtn.textContent = isRecording ? 'Detener grabación' : 'Grabar WebM';
    recordBtn.disabled = typeof window.MediaRecorder === 'undefined';
    if (recordBtn.disabled) recordBtn.title = 'Tu navegador no soporta MediaRecorder';
    else recordBtn.title = '';
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    isRecording = false;
    updateRecordButton();
  };

  const toggleRecording = () => {
    if (typeof window.MediaRecorder === 'undefined') return;
    if (isRecording) {
      stopRecording();
      return;
    }
    try {
      const stream = canvas.captureStream(60);
      const mimeTypes = [
        'video/webm;codecs=vp9',
        'video/webm;codecs=vp8',
        'video/webm',
      ];
      const mimeType = mimeTypes.find((item) => {
        try {
          return typeof window.MediaRecorder.isTypeSupported !== 'function'
            ? item === 'video/webm'
            : window.MediaRecorder.isTypeSupported(item);
        } catch (error) {
          return false;
        }
      });
      mediaRecorder = mimeType
        ? new window.MediaRecorder(stream, { mimeType })
        : new window.MediaRecorder(stream);
      recordingChunks = [];
      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size) recordingChunks.push(event.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(recordingChunks, { type: 'video/webm' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `tarea-3d-${Date.now()}.webm`;
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 2000);
      };
      mediaRecorder.start();
      isRecording = true;
      updateRecordButton();
    } catch (error) {
      isRecording = false;
      updateRecordButton();
    }
  };

  const renderLoop = (timestamp) => {
    const now = timestamp || performance.now();
    const deltaSeconds = lastFrameTs ? ((now - lastFrameTs) / 1000) : 0;
    const elapsedSeconds = lastFrameTs ? (now / 1000) : 0;
    lastFrameTs = now;

    if (isPlaying) {
      if (!playbackState) startPlayback();
      if (currentPreset === 'broadcast' || currentPreset === 'analyst' || currentPreset === 'tactic' || currentPreset === 'coach') {
        orbit.theta += 0.0008;
      }
      const frame = framesData[playbackState.stepIndex] || framesData[0];
      const focusBall = frame.balls.values().next().value;
      if (focusBall && (currentPreset === 'analyst' || currentPreset === 'coach')) {
        orbit.targetX = lerp(orbit.targetX, focusBall.x * 0.45, 0.015);
        orbit.targetZ = lerp(orbit.targetZ, focusBall.z * 0.45, 0.015);
      }
      const current = steps[playbackState.stepIndex] || steps[0];
      const durationMs = Math.max(1, toNumber(current.duration, 4)) * 1000;
      const raw = clamp((now - playbackState.startedAt) / durationMs, 0, 1);
      progress = raw;
      applyInterpolatedState(playbackState.stepIndex, raw, elapsedSeconds);
      if (raw >= 1) {
        currentStepIndex = (playbackState.stepIndex + 1) % steps.length;
        playbackState = {
          stepIndex: currentStepIndex,
          startedAt: now,
          durationMs: Math.max(1, toNumber((steps[currentStepIndex] || steps[0]).duration, 4)) * 1000,
        };
        buildWorldForStep(currentStepIndex);
        progress = 0;
      }
    } else {
      applyInterpolatedState(currentStepIndex, progress, elapsedSeconds);
    }

    applyCamera();
    modelMixers.forEach((mixer) => mixer.update(deltaSeconds));
    renderer.render(scene, camera);
    renderFrameCount += 1;
    lastRenderAt = Date.now();
    publishRenderDiagnostics();
    rafId = window.requestAnimationFrame(renderLoop);
  };

  const focus3DPanel = () => {
    sceneHost.scrollIntoView({ behavior: 'smooth', block: 'center' });
    canvas.focus?.();
  };
  const switchTaskTab = (tabName) => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('tab', tabName);
      if (url.searchParams.get('mode')) url.searchParams.delete('mode');
      window.location.href = url.toString();
    } catch (error) {
      const query = new URLSearchParams(window.location.search || '');
      query.set('tab', tabName);
      query.delete('mode');
      const separator = query.toString() ? '?' : '';
      window.location.href = `${window.location.pathname}${separator}${query.toString()}`;
    }
  };
  const focusTaskInlineEditor = () => {
    const editor = document.getElementById('task-inline-editor');
    if (!editor) return false;
    editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return true;
  };

  openBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    focus3DPanel();
  });
  enterEditBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    switchTaskTab('edit');
  });
  enterEditEmptyBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    switchTaskTab('edit');
  });
  openSequenceBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    switchTaskTab('presentation');
    window.setTimeout(() => {
      focus3DPanel();
      if (playBtn && playBtn.hidden !== true && playBtn.getAttribute('disabled') === null) {
        playBtn.click();
      }
    }, 180);
  });
  focusEditorBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    if (!focusTaskInlineEditor()) {
      switchTaskTab('edit');
      return;
    }
    window.setTimeout(() => focusTaskInlineEditor(), 280);
  });
  prevBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    stopPlayback();
    showStep(currentStepIndex - 1);
  });
  nextBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    stopPlayback();
    showStep(currentStepIndex + 1);
  });
  playBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    togglePlayback();
  });
  snapBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    try {
      const link = document.createElement('a');
      link.href = canvas.toDataURL('image/png');
      link.download = `tarea-3d-${Date.now()}.png`;
      link.click();
    } catch (error) {
      // ignore
    }
  });
  fullBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    toggleFullscreen();
  });
  recordBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    toggleRecording();
  });
  cameraSelect?.addEventListener('change', () => {
    setCameraPreset(cameraSelect.value);
  });

  const onPointerDown = (event) => {
    dragging = {
      x: event.clientX,
      y: event.clientY,
      theta: orbit.theta,
      phi: orbit.phi,
    };
  };
  const onPointerMove = (event) => {
    if (!dragging) return;
    const dx = (event.clientX - dragging.x) * 0.0085;
    const dy = (event.clientY - dragging.y) * 0.006;
    orbit.theta = dragging.theta - dx;
    orbit.phi = clamp(dragging.phi + dy, 0.12, 1.42);
  };
  const onPointerUp = () => {
    dragging = null;
  };
  const onWheel = (event) => {
    event.preventDefault();
    orbit.radius = clamp(orbit.radius + (event.deltaY * 0.05), 40, 180);
  };

  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerup', onPointerUp);
  canvas.addEventListener('pointercancel', onPointerUp);
  canvas.addEventListener('pointerleave', onPointerUp);
  canvas.addEventListener('wheel', onWheel, { passive: false });

  window.addEventListener('resize', () => {
    resize();
  });
  window.addEventListener('keydown', (event) => {
    if (/input|textarea|select/i.test(event.target?.tagName || '')) return;
    if (event.key === ' ') {
      event.preventDefault();
      togglePlayback();
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      stopPlayback();
      showStep(currentStepIndex - 1);
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      stopPlayback();
      showStep(currentStepIndex + 1);
    }
  });
  document.addEventListener('fullscreenchange', () => {
    resize();
  });

  updateRecordButton();
  setCameraPreset('rosaleda');
  buildWorldForStep(0);
  applyInterpolatedState(0, 0, 0);
  resize();
  ensureStadiumModel().then(() => {
    resize();
    publishRenderDiagnostics();
  });
  if (rafId) window.cancelAnimationFrame(rafId);
  rafId = window.requestAnimationFrame(renderLoop);
  publishRenderDiagnostics();
})();
