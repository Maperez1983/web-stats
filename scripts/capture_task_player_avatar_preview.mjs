import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { chromium } from 'playwright';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const staticRoot = path.join(root, 'football/static');
const out = path.join(process.env.HOME || '/Users/miguelperezrodriguez', 'Downloads/VER_AVATAR_PREMIUM_MPFB.png');

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
  camera.position.set(1.45, 1.15, 3.1);

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

  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(1.3, 96),
    new THREE.MeshStandardMaterial({ color: 0x123c2b, roughness: 0.88, metalness: 0.0 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.002;
  scene.add(floor);

  const loader = new GLTFLoader();
  loader.load('/football/models/avatar/player_humanoid.glb', (gltf) => {
    console.log('gltf loaded');
    const avatar = gltf.scene;
    avatar.rotation.y = -0.35;
    scene.add(avatar);

    const box = new THREE.Box3().setFromObject(avatar);
    const center = box.getCenter(new THREE.Vector3());
    avatar.position.x -= center.x;
    avatar.position.z -= center.z;

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
