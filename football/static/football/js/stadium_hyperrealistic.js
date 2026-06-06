import * as THREE from 'three';
import { GLTFLoader } from '/static/vendor/three/examples/jsm/loaders/GLTFLoader.js';

const root = document.getElementById('stadium-root');
const loading = document.getElementById('stadium-loading');
const modelSrc = root.dataset.modelSrc || '/static/football/models/stadium/benagalbon-hyperrealistic-stadium.glb';

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
} catch (error) {
  if (loading) loading.classList.add('is-hidden');
  root.innerHTML = '<div style="display:grid;place-items:center;width:100%;height:100%;color:#fff;background:#05080b;font:700 16px system-ui">WebGL no esta disponible en este navegador.</div>';
  throw error;
}

renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(root.clientWidth, root.clientHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.96;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
root.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9fcaec);
scene.fog = new THREE.Fog(0x9fcaec, 150, 360);

const camera = new THREE.PerspectiveCamera(38, root.clientWidth / root.clientHeight, 0.1, 700);
const target = new THREE.Vector3(0, 0, 3.5);
const cam = {
  yaw: -2.34,
  pitch: 0.52,
  radius: 142,
  auto: true,
  dragging: false,
  x: 0,
  y: 0,
};

scene.add(new THREE.HemisphereLight(0xd5ebff, 0x1f2d1f, 1.6));
const sun = new THREE.DirectionalLight(0xffedc9, 4.2);
sun.position.set(-86, -110, 118);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
sun.shadow.camera.left = -150;
sun.shadow.camera.right = 150;
sun.shadow.camera.top = 150;
sun.shadow.camera.bottom = -150;
sun.shadow.camera.near = 10;
sun.shadow.camera.far = 320;
scene.add(sun);

function enhanceMaterial(material) {
  if (!material) return material;
  const name = `${material.name || ''}`.toLowerCase();
  const mat = material.clone();
  mat.needsUpdate = true;
  if (name.includes('grass')) {
    mat.roughness = 0.82;
  } else if (name.includes('concrete')) {
    mat.roughness = 0.92;
  } else if (name.includes('steel') || name.includes('roof')) {
    mat.metalness = name.includes('steel') ? 0.46 : 0.25;
    mat.roughness = name.includes('steel') ? 0.34 : 0.45;
  } else if (name.includes('glass')) {
    mat.transparent = true;
    mat.opacity = 0.42;
    mat.roughness = 0.08;
  } else if (name.includes('light')) {
    mat.emissive = new THREE.Color(0xffe2a3);
    mat.emissiveIntensity = 1.8;
  }
  return mat;
}

new GLTFLoader().load(
  modelSrc,
  (gltf) => {
    const model = gltf.scene;
    model.name = 'benagalbon_blender_stadium';
    model.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = true;
      node.receiveShadow = true;
      if (Array.isArray(node.material)) {
        node.material = node.material.map(enhanceMaterial);
      } else {
        node.material = enhanceMaterial(node.material);
      }
    });
    scene.add(model);
    loading?.classList.add('is-hidden');
  },
  undefined,
  (error) => {
    console.error(error);
    if (loading) loading.innerHTML = '<span>No se pudo cargar el modelo Blender</span>';
  }
);

function setPreset(name) {
  cam.auto = false;
  if (name === 'aerial') {
    cam.yaw = -0.72;
    cam.pitch = 0.68;
    cam.radius = 160;
  } else if (name === 'touchline') {
    cam.yaw = -1.02;
    cam.pitch = 0.26;
    cam.radius = 92;
  } else {
    cam.yaw = -2.34;
    cam.pitch = 0.52;
    cam.radius = 142;
  }
}

function updateCamera(t) {
  if (cam.auto) cam.yaw = -2.34 + Math.sin(t * 0.00012) * 0.08;
  cam.pitch = Math.max(0.14, Math.min(1.1, cam.pitch));
  cam.radius = Math.max(60, Math.min(230, cam.radius));
  const horizontal = Math.cos(cam.pitch) * cam.radius;
  camera.position.set(
    target.x + Math.sin(cam.yaw) * horizontal,
    target.y + Math.sin(cam.pitch) * cam.radius,
    target.z + Math.cos(cam.yaw) * horizontal
  );
  camera.lookAt(target);
}

function bindControls() {
  renderer.domElement.addEventListener('pointerdown', (ev) => {
    cam.dragging = true;
    cam.auto = false;
    cam.x = ev.clientX;
    cam.y = ev.clientY;
    renderer.domElement.setPointerCapture(ev.pointerId);
  });
  renderer.domElement.addEventListener('pointermove', (ev) => {
    if (!cam.dragging) return;
    const dx = ev.clientX - cam.x;
    const dy = ev.clientY - cam.y;
    cam.x = ev.clientX;
    cam.y = ev.clientY;
    cam.yaw -= dx * 0.004;
    cam.pitch += dy * 0.0025;
  });
  renderer.domElement.addEventListener('pointerup', () => {
    cam.dragging = false;
  });
  renderer.domElement.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    cam.auto = false;
    cam.radius += ev.deltaY * 0.08;
  }, { passive: false });
  document.querySelectorAll('[data-camera]').forEach((button) => {
    button.addEventListener('click', () => setPreset(button.dataset.camera || 'broadcast'));
  });
}

function resize() {
  const w = Math.max(1, root.clientWidth);
  const h = Math.max(1, root.clientHeight);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

function frame(t) {
  updateCamera(t);
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

bindControls();
resize();
window.addEventListener('resize', resize);
requestAnimationFrame(frame);
