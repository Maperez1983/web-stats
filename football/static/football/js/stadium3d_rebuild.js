import * as THREE from '/static/vendor/three/build/three.module.js';
import { GLTFLoader } from '/static/vendor/three/examples/jsm/loaders/GLTFLoader.js';

const root = document.getElementById('stadium3d-root');
const loading = document.getElementById('stadium3d-loading');
const modelSrc = root?.dataset?.modelSrc;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xcfe6f5);
scene.fog = new THREE.Fog(0xcfe6f5, 120, 260);

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
root.appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 500);
const target = new THREE.Vector3(0, 2.5, 0);

const hemi = new THREE.HemisphereLight(0xddefff, 0x24402f, 1.7);
scene.add(hemi);

const sun = new THREE.DirectionalLight(0xffffff, 2.1);
sun.position.set(-60, 92, 75);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.near = 1;
sun.shadow.camera.far = 220;
sun.shadow.camera.left = -90;
sun.shadow.camera.right = 90;
sun.shadow.camera.top = 90;
sun.shadow.camera.bottom = -90;
scene.add(sun);

const cameras = {
  tv: { pos: new THREE.Vector3(-76, 32, 64), target: new THREE.Vector3(0, 3.2, 0) },
  air: { pos: new THREE.Vector3(-92, 78, 88), target: new THREE.Vector3(0, 1.4, 0) },
  goal: { pos: new THREE.Vector3(64, 8, 12), target: new THREE.Vector3(40, 2.2, 0) },
};

let desiredPos = cameras.tv.pos.clone();
let desiredTarget = cameras.tv.target.clone();
camera.position.copy(desiredPos);
target.copy(desiredTarget);

function setCamera(key) {
  const cfg = cameras[key] || cameras.tv;
  desiredPos = cfg.pos.clone();
  desiredTarget = cfg.target.clone();
  document.querySelectorAll('[data-camera]').forEach((btn) => {
    btn.classList.toggle('is-active', btn.dataset.camera === key);
  });
}

document.querySelectorAll('[data-camera]').forEach((btn) => {
  btn.addEventListener('click', () => setCamera(btn.dataset.camera));
});

let dragging = false;
let lastX = 0;
let lastY = 0;
let yaw = 0;
let pitch = 0;
let distanceScale = 1;

renderer.domElement.addEventListener('pointerdown', (ev) => {
  dragging = true;
  lastX = ev.clientX;
  lastY = ev.clientY;
  renderer.domElement.setPointerCapture(ev.pointerId);
});

renderer.domElement.addEventListener('pointermove', (ev) => {
  if (!dragging) return;
  yaw += (ev.clientX - lastX) * 0.004;
  pitch = Math.max(-0.55, Math.min(0.45, pitch + (ev.clientY - lastY) * 0.003));
  lastX = ev.clientX;
  lastY = ev.clientY;
});

renderer.domElement.addEventListener('pointerup', () => {
  dragging = false;
});

renderer.domElement.addEventListener('wheel', (ev) => {
  ev.preventDefault();
  distanceScale = Math.max(0.55, Math.min(1.55, distanceScale + ev.deltaY * 0.0008));
}, { passive: false });

new GLTFLoader().load(
  modelSrc,
  (gltf) => {
    gltf.scene.traverse((obj) => {
      if (obj.isMesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
      }
    });
    scene.add(gltf.scene);
    loading?.classList.add('is-hidden');
  },
  (event) => {
    if (!loading || !event.total) return;
    const pct = Math.max(1, Math.min(99, Math.round((event.loaded / event.total) * 100)));
    loading.textContent = `Cargando fase 1 · ${pct}%`;
  },
  () => {
    if (loading) loading.textContent = 'No se pudo cargar la fase 1';
  },
);

function resize() {
  const width = root.clientWidth || window.innerWidth;
  const height = root.clientHeight || window.innerHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}

window.addEventListener('resize', resize);
resize();

function animate() {
  requestAnimationFrame(animate);
  target.lerp(desiredTarget, 0.055);
  const base = desiredPos.clone().sub(desiredTarget).multiplyScalar(distanceScale);
  const spherical = new THREE.Spherical().setFromVector3(base);
  spherical.theta += yaw;
  spherical.phi = Math.max(0.22, Math.min(Math.PI - 0.22, spherical.phi + pitch));
  const current = new THREE.Vector3().setFromSpherical(spherical).add(target);
  camera.position.lerp(current, 0.08);
  camera.lookAt(target);
  renderer.render(scene, camera);
}

animate();
