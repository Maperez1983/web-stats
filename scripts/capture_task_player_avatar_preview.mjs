import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { chromium } from 'playwright';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const staticRoot = path.join(root, 'football/static');
const out = path.join(process.env.HOME || '/Users/miguelperezrodriguez', 'Downloads/VER_AVATAR_QUATERNIUS_FUTBOLISTA.png');

const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.glb': 'model/gltf-binary',
  '.wasm': 'application/wasm',
};

const server = http.createServer((request, response) => {
  const url = new URL(request.url || '/', 'http://127.0.0.1');
  if (url.pathname === '/') {
    response.writeHead(200, { 'content-type': mime['.html'] });
    response.end(`<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #07130f; }
    canvas { width: 100%; height: 100%; display: block; }
  </style>
</head>
<body>
<script type="importmap">
{
  "imports": {
    "three": "/vendor/three/build/three.module.js"
  }
}
</script>
<script type="module">
  import * as THREE from '/vendor/three/build/three.module.js';
  import { GLTFLoader } from '/vendor/three/examples/jsm/loaders/GLTFLoader.js';

  console.log('preview boot');
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07130f);

  const camera = new THREE.PerspectiveCamera(34, innerWidth / innerHeight, 0.01, 100);
  camera.position.set(1.25, 1.12, 3.15);

  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  document.body.appendChild(renderer.domElement);

  const hemi = new THREE.HemisphereLight(0xffffff, 0x10261c, 2.1);
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xffffff, 2.8);
  key.position.set(2.6, 4.2, 3.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x8fd7ff, 1.6);
  rim.position.set(-2.2, 2.0, -2.4);
  scene.add(rim);

  const grass = new THREE.Group();
  const turfA = new THREE.MeshStandardMaterial({ color: 0x0f5f3d, roughness: 0.92, metalness: 0.0 });
  const turfB = new THREE.MeshStandardMaterial({ color: 0x0b4f35, roughness: 0.92, metalness: 0.0 });
  for (let i = 0; i < 9; i += 1) {
    const stripe = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 3.2), i % 2 ? turfA : turfB);
    stripe.rotation.x = -Math.PI / 2;
    stripe.position.set((i - 4) * 0.62, -0.004, 0);
    grass.add(stripe);
  }
  const lineMat = new THREE.MeshBasicMaterial({ color: 0xf8fafc, transparent: true, opacity: 0.72, toneMapped: false });
  const line = (w, h, x, z) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), lineMat);
    m.rotation.x = -Math.PI / 2;
    m.position.set(x, 0.002, z);
    grass.add(m);
  };
  line(5.1, 0.018, 0, 0);
  line(0.018, 3.0, 0, 0);
  const circle = new THREE.Mesh(new THREE.TorusGeometry(0.58, 0.008, 8, 96), lineMat);
  circle.rotation.x = -Math.PI / 2;
  circle.position.y = 0.004;
  grass.add(circle);
  scene.add(grass);

  const addKitOverlay = (avatar) => {
    const shirtMat = new THREE.MeshStandardMaterial({ color: 0x047857, roughness: 0.58, metalness: 0.02, transparent: true, opacity: 0.97 });
    const trimMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.62, metalness: 0.01, transparent: true, opacity: 0.95 });
    const shortsMat = new THREE.MeshStandardMaterial({ color: 0x07111f, roughness: 0.72, metalness: 0.01, transparent: true, opacity: 0.95 });
    const sockMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.72, metalness: 0.01, transparent: true, opacity: 0.94 });
    const bootMat = new THREE.MeshStandardMaterial({ color: 0x05070a, roughness: 0.58, metalness: 0.04 });
    const shirt = new THREE.Mesh(new THREE.CapsuleGeometry(0.185, 0.36, 8, 20), shirtMat);
    shirt.position.set(0, 1.10, 0);
    shirt.scale.set(1.38, 0.96, 0.72);
    avatar.add(shirt);
    const chest = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.30, 0.020), trimMat);
    chest.position.set(0, 1.10, 0.150);
    avatar.add(chest);
    const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.040, 0.39, 0.022), shirtMat);
    stripe.position.set(0, 1.10, 0.166);
    avatar.add(stripe);
    const shorts = new THREE.Mesh(new THREE.CylinderGeometry(0.195, 0.235, 0.18, 24), shortsMat);
    shorts.position.y = 0.72;
    shorts.scale.set(1.16, 1, 0.82);
    avatar.add(shorts);
    [-0.13, 0.13].forEach((x) => {
      const sock = new THREE.Mesh(new THREE.CapsuleGeometry(0.032, 0.32, 5, 12), sockMat);
      sock.position.set(x, 0.27, 0.006);
      avatar.add(sock);
      const boot = new THREE.Mesh(new THREE.BoxGeometry(0.105, 0.050, 0.19), bootMat);
      boot.position.set(x, 0.025, 0.06);
      avatar.add(boot);
    });
  };
  const applyReadyPose = (avatar) => {
    const byName = {};
    avatar.traverse((node) => { if (node?.name) byName[node.name] = node; });
    const set = (name, x, y, z) => {
      const bone = byName[name];
      if (!bone || !bone.rotation) return;
      bone.rotation.x += x;
      bone.rotation.y += y;
      bone.rotation.z += z;
    };
    set('upperarm_l', 0, 0.10, -1.18);
    set('lowerarm_l', 0, -0.08, -0.22);
    set('hand_l', 0.10, 0, -0.08);
    set('upperarm_r', 0, -0.10, 1.18);
    set('lowerarm_r', 0, 0.08, 0.22);
    set('hand_r', 0.10, 0, 0.08);
    set('thigh_l', -0.05, 0.03, 0.04);
    set('thigh_r', 0.05, -0.03, -0.04);
    set('calf_l', 0.08, 0, 0);
    set('calf_r', 0.05, 0, 0);
    set('spine_03', 0.04, -0.04, 0);
    try { avatar.updateMatrixWorld(true); } catch (e) { /* ignore */ }
  };

  const loader = new GLTFLoader();
  loader.load('/football/models/avatar/player_humanoid.glb', (gltf) => {
    console.log('gltf loaded');
    const avatar = gltf.scene;
    avatar.rotation.y = -0.22;
    applyReadyPose(avatar);
    scene.add(avatar);

    const box = new THREE.Box3().setFromObject(avatar);
    const center = box.getCenter(new THREE.Vector3());
    avatar.position.x -= center.x;
    avatar.position.z -= center.z;
    // The generated GLB already includes painted football kit materials.

    camera.lookAt(0, 0.9, 0);
    renderer.render(scene, camera);
    window.__avatarReady = true;
  }, (event) => {
    if (event.total) console.log('loading ' + Math.round((event.loaded / event.total) * 100) + '%');
  }, (error) => {
    console.error('gltf error ' + String(error && error.message ? error.message : error));
    window.__avatarError = String(error && error.message ? error.message : error);
  });
</script>
</body>
</html>`);
    return;
  }

  const file = path.resolve(staticRoot, decodeURIComponent(url.pathname.slice(1)));
  if (!file.startsWith(staticRoot)) {
    response.writeHead(403);
    response.end('forbidden');
    return;
  }
  fs.createReadStream(file)
    .on('error', () => {
      response.writeHead(404);
      response.end('not found');
    })
    .on('open', () => {
      response.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream' });
    })
    .pipe(response);
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-angle=metal', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1200, height: 1200 }, deviceScaleFactor: 1 });
page.on('console', (message) => console.log(`[browser:${message.type()}] ${message.text()}`));
page.on('pageerror', (error) => console.log(`[browser:error] ${error.message}`));
page.on('requestfailed', (request) => console.log(`[browser:requestfailed] ${request.url()} ${request.failure()?.errorText || ''}`));

await page.goto(`http://127.0.0.1:${port}/`);

await page.waitForFunction(() => window.__avatarReady || window.__avatarError, null, { timeout: 10000 });
const error = await page.evaluate(() => window.__avatarError || '');
if (error) throw new Error(error);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
server.close();
console.log(out);
