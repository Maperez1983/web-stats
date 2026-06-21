import * as THREE from '../../vendor/three/build/three.module.js';
import { GLTFLoader } from '../../vendor/three/examples/jsm/loaders/GLTFLoader.js';

(function () {
  const payloadEl = document.getElementById('task-detail-3d-payload');
  const modal = document.getElementById('task-detail-3d-modal');
  const canvas = document.getElementById('task-detail-3d-canvas');
  const openBtn = document.getElementById('task-detail-3d-open');
  if (!payloadEl || !modal || !canvas || !openBtn) return;

  const byId = (id) => document.getElementById(id);
  const closeBtn = byId('task-detail-3d-close');
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

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const lerp = (a, b, t) => a + ((b - a) * t);
  const smooth = (t) => t * t * (3 - (2 * t));
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const toNumber = (value, fallback = 0) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  };

  let payload = {};
  try {
    payload = JSON.parse(payloadEl.textContent || '{}');
  } catch (error) {
    payload = {};
  }

  const buildSteps = () => {
    const steps = [];
    const animationFrames = Array.isArray(payload.animationFrames) ? payload.animationFrames : [];
    animationFrames.forEach((frame, index) => {
      const state = frame && typeof frame.canvas_state === 'object' ? frame.canvas_state : null;
      if (!state || !Array.isArray(state.objects)) return;
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
    const state = editor.canvas_state && typeof editor.canvas_state === 'object' ? editor.canvas_state : null;
    if (state && Array.isArray(state.objects)) {
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
      payload.canvasWidth || firstState.width || (payload.graphicEditorState || {}).width,
      1280
    )),
    height: Math.max(180, toNumber(
      payload.canvasHeight || firstState.height || (payload.graphicEditorState || {}).height,
      720
    )),
    fieldWidth: 105,
    fieldHeight: 68,
  };

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: true,
  });
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
    broadcast: { theta: -0.64, phi: 1.02, radius: 134, targetX: -2, targetZ: 2 },
    tactic: { theta: 0.02, phi: 0.48, radius: 84, targetX: 0, targetZ: 0 },
    corner: { theta: -0.95, phi: 0.92, radius: 104, targetX: 10, targetZ: -4 },
    goal: { theta: Math.PI, phi: 0.76, radius: 74, targetX: 0, targetZ: 18 },
    drone: { theta: -0.01, phi: 0.16, radius: 70, targetX: 0, targetZ: 0 },
    tunnel: { theta: -1.55, phi: 1.08, radius: 88, targetX: -12, targetZ: 0 },
    analyst: { theta: -0.72, phi: 1.18, radius: 88, targetX: -3, targetZ: 6 },
    coach: { theta: -0.9, phi: 1.18, radius: 80, targetX: -6, targetZ: 10 },
    rosaleda: { theta: -0.82, phi: 1.01, radius: 128, targetX: -5, targetZ: 4 },
  };
  const orbit = { ...cameraPresets.broadcast };
  let currentPreset = 'broadcast';
  let currentStepIndex = 0;
  let isOpen = false;
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
      { bg: '#0a3b8f', fg: '#ffffff', text: '2J FOOTBALL INTELLIGENCE' },
      { bg: '#0d4dbc', fg: '#ffffff', text: 'LA ROSALEDA' },
      { bg: '#173b7a', fg: '#ffffff', text: 'MALAGA CF' },
      { bg: '#15253d', fg: '#ffffff', text: 'SPONSOR' },
      { bg: '#1a4fa8', fg: '#ffffff', text: 'PARTNER' },
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
    makeBanner('MALAGA CF', 42, 10, 0, 24, -36, 0, '#ffffff');
    makeBanner('MCF', 16, 16, -28, 24, -35, 0, '#dbeafe');
    const crest = new THREE.Mesh(
      new THREE.CircleGeometry(4.1, 48),
      new THREE.MeshBasicMaterial({ color: 0x2563eb, transparent: true, opacity: 0.96 })
    );
    crest.position.set(10, 35, -34.5);
    graphics.add(crest);
    makeBanner('MCF', 6.2, 6.2, 10, 35, -34.3, 0, '#ffffff');
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
            const scaleX = (stateMeta.fieldWidth * 2.12) / Math.max(size.x || 1, 1);
            const scaleZ = (stateMeta.fieldHeight * 2.04) / Math.max(size.z || 1, 1);
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
                  if ('envMapIntensity' in mat) mat.envMapIntensity = 0.5;
                  if ('metalness' in mat && typeof mat.metalness === 'number') mat.metalness *= 0.92;
                  if ('roughness' in mat && typeof mat.roughness === 'number') mat.roughness = Math.min(0.96, mat.roughness + 0.04);
                  if ('color' in mat && name.includes('TEAM_PRIMARY_DARKER_SEAT_FIELD')) mat.color.set('#174fba');
                  else if ('color' in mat && name.includes('TEAM_PRIMARY')) mat.color.set('#1f63d6');
                  else if ('color' in mat && name.includes('TEAM_ACCENT')) mat.color.set('#0d3f9c');
                  else if ('color' in mat && name.includes('TEAM_SECONDARY')) mat.color.set('#d6dde6');
                  else if ('color' in mat && name.includes('ARCH_PRECAST_CONCRETE')) mat.color.set('#95a3b3');
                  else if ('color' in mat && name.includes('ARCH_DARK_CONCRETE_STRUCTURE')) mat.color.set('#313b46');
                  else if ('color' in mat && name.includes('ARCH_STEEL_TRUSS')) mat.color.set('#66768a');
                  else if ('color' in mat && name.includes('ARCH_DARK_SERVICE_RING')) mat.color.set('#1b2631');
                  else if ('color' in mat && name.includes('ARCH_GLASS_GUARDRAIL')) {
                    mat.color.set('#d9efff');
                    mat.opacity = 0.22;
                    mat.transparent = true;
                  } else if ('color' in mat && name.includes('ARCH_FLOODLIGHT_LINE')) {
                    mat.color.set('#f4fbff');
                  } else if ('color' in mat && name.includes('ARCH_LED_RIBBON_FACE')) {
                    mat.color.set('#0b4fbe');
                    if ('emissive' in mat) mat.emissive.set('#1a66e8');
                    if ('emissiveIntensity' in mat) mat.emissiveIntensity = 1.4;
                  } else if ('color' in mat && name.includes('ROOF')) {
                    mat.color.offsetHSL(0, -0.02, 0.02);
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

  const clearGroup = (group) => {
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
      zones: [],
      goals: [],
      paths: [],
      notes: [],
    };
    let tokenIndex = 0;
    let ballIndex = 0;
    let goalIndex = 0;
    objects.forEach((obj, index) => {
      const extra = obj && typeof obj.data === 'object' ? obj.data : {};
      const kind = safeText(extra.kind);
      if (obj.type === 'rect' && kind === 'zone') {
        const world = canvasToWorld(obj.left, obj.top);
        data.zones.push({
          uid: `zone:${index}`,
          x: world.x,
          z: world.z,
          width: sizeToMeters(obj.width, stateMeta.width, stateMeta.fieldWidth, 2, stateMeta.fieldWidth),
          depth: sizeToMeters(obj.height, stateMeta.height, stateMeta.fieldHeight, 2, stateMeta.fieldHeight),
          fill: safeText(obj.fill, '#0ea5e9'),
          stroke: safeText(obj.stroke, '#fde047'),
          opacity: String(obj.fill || '').includes('0.00') ? 0.04 : 0.18,
        });
        return;
      }
      if (obj.type === 'circle' && kind === 'token') {
        const world = canvasToWorld(obj.left, obj.top);
        const label = safeText(extra.label, `J${tokenIndex + 1}`);
        data.tokens.set(`token:${label}:${tokenIndex}`, {
          uid: `token:${label}:${tokenIndex}`,
          label,
          x: world.x,
          z: world.z,
          radius: radiusToMeters(obj.radius),
          fill: safeText(obj.fill, '#2563eb'),
          stroke: safeText(obj.stroke, '#ffffff'),
        });
        tokenIndex += 1;
        return;
      }
      if (obj.type === 'text' && kind === 'emoji_ball') {
        const world = canvasToWorld(obj.left, obj.top);
        data.balls.set(`ball:${ballIndex}`, {
          uid: `ball:${ballIndex}`,
          x: world.x,
          z: world.z,
        });
        ballIndex += 1;
        return;
      }
      if (obj.type === 'text' && kind === 'emoji_mini_goal') {
        const world = canvasToWorld(obj.left, obj.top);
        data.goals.push({
          uid: `goal:${goalIndex}`,
          x: world.x,
          z: world.z,
          rotationY: world.x > 0 ? Math.PI / 2 : -Math.PI / 2,
        });
        goalIndex += 1;
        return;
      }
      if (obj.type === 'line') {
        const from = canvasToWorld(obj.x1, obj.y1);
        const to = canvasToWorld(obj.x2, obj.y2);
        data.paths.push({
          uid: `path:${index}`,
          from,
          to,
          color: safeText(obj.stroke, '#38bdf8'),
          dashed: Array.isArray(obj.strokeDashArray) && obj.strokeDashArray.length > 0,
        });
        return;
      }
      if (obj.type === 'textbox' || obj.type === 'text') {
        const label = safeText(obj.text || extra.label);
        if (!label || kind.startsWith('emoji_')) return;
        const world = canvasToWorld(obj.left, obj.top);
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

  const renderStaticWorld = (frameData) => {
    clearGroup(dynamicRoot);
    const world = {
      tokens: new Map(),
      balls: new Map(),
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
      dynamicRoot.add(line);
    });

    frameData.goals.forEach((goalData) => {
      const goal = createGoalFrame();
      goal.position.set(goalData.x, 0.08, goalData.z);
      goal.rotation.y = goalData.rotationY;
      dynamicRoot.add(goal);
    });

    frameData.paths.forEach((pathData) => {
      const curve = createArrowCurve(pathData.from, pathData.to);
      const points = curve.getPoints(36);
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
      const stride = Math.sin((elapsedSeconds * 8) + (x * 0.1) + (z * 0.06)) * moveStrength;
      group.position.x = x;
      group.position.z = z;
      group.position.y = Math.sin((elapsedSeconds * 3.2) + x * 0.08 + z * 0.08) * 0.06;
      group.rotation.y = next ? Math.atan2(dx, dz) : 0;
      if (group.userData.leftArm) group.userData.leftArm.rotation.x = stride * 0.55;
      if (group.userData.rightArm) group.userData.rightArm.rotation.x = -stride * 0.55;
      if (group.userData.leftLeg) group.userData.leftLeg.rotation.x = -stride * 0.34;
      if (group.userData.rightLeg) group.userData.rightLeg.rotation.x = stride * 0.34;
      if (group.userData.badge) group.userData.badge.position.y = 2.03 + (Math.sin(elapsedSeconds * 5 + x * 0.08) * 0.04);
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
    const card = modal.querySelector('.sim-3d-card');
    if (!card) return;
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await card.requestFullscreen?.();
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
    if (!isOpen) return;
    const now = timestamp || performance.now();
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
    renderer.render(scene, camera);
    rafId = window.requestAnimationFrame(renderLoop);
  };

  const open = () => {
    modal.hidden = false;
    isOpen = true;
    lastFrameTs = 0;
    resize();
    ensureStadiumModel().then(() => {
      if (isOpen) resize();
    });
    showStep(currentStepIndex);
    stopPlayback();
    if (rafId) window.cancelAnimationFrame(rafId);
    rafId = window.requestAnimationFrame(renderLoop);
  };

  const close = () => {
    modal.hidden = true;
    isOpen = false;
    stopPlayback();
    if (isRecording) stopRecording();
    if (rafId) {
      window.cancelAnimationFrame(rafId);
      rafId = null;
    }
  };

  openBtn.addEventListener('click', (event) => {
    event.preventDefault();
    open();
  });
  closeBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    close();
  });
  modal.addEventListener('click', (event) => {
    if (event.target === modal) close();
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
    if (isOpen) resize();
  });
  window.addEventListener('keydown', (event) => {
    if (!isOpen) return;
    if (event.key === 'Escape') close();
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
    if (isOpen) resize();
  });

  updateRecordButton();
  setCameraPreset('rosaleda');
  buildWorldForStep(0);
  applyInterpolatedState(0, 0, 0);
})();
