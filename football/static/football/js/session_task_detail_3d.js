import * as THREE from '../../vendor/three/build/three.module.js';

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

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x08111d);
  scene.fog = new THREE.Fog(0x08111d, 120, 250);

  const camera = new THREE.PerspectiveCamera(42, 16 / 9, 0.1, 500);
  const root = new THREE.Group();
  const dynamicRoot = new THREE.Group();
  scene.add(root);
  scene.add(dynamicRoot);

  const cameraPresets = {
    broadcast: { theta: -0.18, phi: 0.86, radius: 118, targetX: 0, targetZ: 0 },
    tactic: { theta: 0.02, phi: 0.48, radius: 84, targetX: 0, targetZ: 0 },
    corner: { theta: -0.95, phi: 0.92, radius: 104, targetX: 10, targetZ: -4 },
    goal: { theta: Math.PI, phi: 0.76, radius: 74, targetX: 0, targetZ: 18 },
    drone: { theta: -0.01, phi: 0.16, radius: 70, targetX: 0, targetZ: 0 },
    tunnel: { theta: -1.55, phi: 1.08, radius: 88, targetX: -12, targetZ: 0 },
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

  const canvasTexture = (() => {
    const offscreen = document.createElement('canvas');
    offscreen.width = 1024;
    offscreen.height = 768;
    const ctx = offscreen.getContext('2d');
    const stripeColors = ['#5c8f42', '#649848', '#6e9f4f', '#77a756', '#6a9c4b', '#5e9144'];
    const stripeH = offscreen.height / stripeColors.length;
    stripeColors.forEach((color, index) => {
      ctx.fillStyle = color;
      ctx.fillRect(0, stripeH * index, offscreen.width, stripeH + 2);
    });
    ctx.fillStyle = 'rgba(255,255,255,0.045)';
    for (let x = 0; x < offscreen.width; x += 112) {
      ctx.fillRect(x, 0, 2, offscreen.height);
    }
    return new THREE.CanvasTexture(offscreen);
  })();
  canvasTexture.wrapS = THREE.ClampToEdgeWrapping;
  canvasTexture.wrapT = THREE.ClampToEdgeWrapping;

  const pitchPlane = new THREE.Mesh(
    new THREE.PlaneGeometry(stateMeta.fieldWidth, stateMeta.fieldHeight),
    new THREE.MeshStandardMaterial({ map: canvasTexture, roughness: 0.96, metalness: 0.02 })
  );
  pitchPlane.rotation.x = -Math.PI / 2;
  pitchPlane.receiveShadow = true;
  root.add(pitchPlane);

  const outerGlow = new THREE.Mesh(
    new THREE.CircleGeometry(95, 96),
    new THREE.MeshBasicMaterial({ color: 0x050b14, transparent: true, opacity: 0.9 })
  );
  outerGlow.rotation.x = -Math.PI / 2;
  outerGlow.position.y = -0.08;
  root.add(outerGlow);

  const skyRing = new THREE.Mesh(
    new THREE.CylinderGeometry(88, 88, 28, 72, 1, true),
    new THREE.MeshBasicMaterial({
      color: 0x11233d,
      transparent: true,
      opacity: 0.16,
      side: THREE.DoubleSide,
    })
  );
  skyRing.position.y = 13;
  root.add(skyRing);

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

  const ambient = new THREE.HemisphereLight(0xdbeafe, 0x0a1424, 1.45);
  scene.add(ambient);

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.22);
  dirLight.position.set(-38, 72, 26);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.set(2048, 2048);
  dirLight.shadow.camera.left = -90;
  dirLight.shadow.camera.right = 90;
  dirLight.shadow.camera.top = 90;
  dirLight.shadow.camera.bottom = -90;
  scene.add(dirLight);

  const rimLight = new THREE.DirectionalLight(0x7dd3fc, 0.38);
  rimLight.position.set(34, 28, -26);
  scene.add(rimLight);

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

  const createGoalFrame = (color = 0xe5e7eb) => {
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
    return new THREE.Line(geometry, material);
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
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(radius, radius * 0.94, 2.45, 28),
      new THREE.MeshStandardMaterial({ color: fill, roughness: 0.52, metalness: 0.06 })
    );
    body.position.y = 1.2;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const rim = new THREE.Mesh(
      new THREE.TorusGeometry(radius * 0.92, 0.08, 14, 36),
      new THREE.MeshStandardMaterial({ color: parseColor(entry.stroke, '#ffffff'), roughness: 0.58 })
    );
    rim.rotation.x = Math.PI / 2;
    rim.position.y = 0.06;
    group.add(rim);

    const head = new THREE.Mesh(
      new THREE.SphereGeometry(radius * 0.58, 24, 20),
      new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.92, metalness: 0.01 })
    );
    head.position.y = 2.66;
    head.castShadow = true;
    group.add(head);

    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(radius * 1.16, 24),
      new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.24 })
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.03;
    group.add(shadow);

    const label = createLabelSprite(entry.label, '#ffffff');
    label.position.set(0, 1.55, radius + 0.26);
    group.add(label);

    group.userData = { baseY: 0, radius };
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
      const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(zone.width, 0.01, zone.depth));
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: parseColor(zone.stroke, '#fde047') })
      );
      line.position.set(zone.x, 0.06, zone.z);
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
      world.paths.push({ line, dashed: !!pathData.dashed });
    });

    frameData.notes.forEach((noteData) => {
      const label = createLabelSprite(noteData.label, '#dbeafe');
      label.scale.set(7.2, 3.2, 1);
      label.position.set(noteData.x, 1.8, noteData.z);
      dynamicRoot.add(label);
      world.notes.push(label);
    });

    frameData.tokens.forEach((entry, uid) => {
      const actor = createTokenActor(entry);
      dynamicRoot.add(actor);
      world.tokens.set(uid, { group: actor, entry });
    });

    frameData.balls.forEach((entry, uid) => {
      const actor = createBallActor(entry);
      dynamicRoot.add(actor);
      world.balls.set(uid, { group: actor, entry });
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

    activeWorld.tokens.forEach(({ group, entry }, uid) => {
      const next = nextFrameData.tokens.get(uid);
      const target = next || entry;
      const x = lerp(entry.x, target.x, next ? eased : 0);
      const z = lerp(entry.z, target.z, next ? eased : 0);
      group.position.x = x;
      group.position.z = z;
      group.position.y = Math.sin((elapsedSeconds * 3.2) + x * 0.08 + z * 0.08) * 0.06;
      group.rotation.y = next ? Math.atan2(target.x - entry.x, target.z - entry.z) : 0;
    });

    activeWorld.balls.forEach(({ group, entry }, uid) => {
      const next = nextFrameData.balls.get(uid);
      const target = next || entry;
      group.position.x = lerp(entry.x, target.x, next ? eased : 0);
      group.position.z = lerp(entry.z, target.z, next ? eased : 0);
      group.position.y = (next ? Math.sin(eased * Math.PI) * 1.1 : 0) + 0.02;
      group.rotation.y += 0.05;
    });

    activeWorld.paths.forEach(({ line, dashed }, index) => {
      if (!line.material) return;
      const alpha = dashed ? 0.5 + (Math.sin(elapsedSeconds * 4 + index) * 0.18) : 0.82 + (Math.sin(elapsedSeconds * 3 + index) * 0.08);
      line.material.opacity = clamp(alpha, 0.28, 1);
      if (dashed && typeof line.material.dashOffset === 'number') {
        line.material.dashOffset = -elapsedSeconds * 2.2;
      }
    });

    activeWorld.notes.forEach((note, index) => {
      note.position.y = 1.8 + Math.sin(elapsedSeconds * 2 + index) * 0.08;
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
  setCameraPreset('broadcast');
  buildWorldForStep(0);
  applyInterpolatedState(0, 0, 0);
})();
