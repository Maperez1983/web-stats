import sharp from 'sharp';
import { NodeIO } from '@gltf-transform/core';
import * as THREE from 'three';

const GLB_PATH = '/Volumes/Mac Satecchi/Mac/Web-stats/football/static/football/models/pitch3d/stadium_zero_rebuild.glb';
const OUT_HERO = '/Volumes/Mac Satecchi/Mac/Downloads/stadium-zero-rebuild-hero-software.png';
const OUT_CORNER = '/Volumes/Mac Satecchi/Mac/Downloads/stadium-zero-rebuild-corner-software.png';
const WIDTH = 1800;
const HEIGHT = 1000;
const LIGHT_DIR = new THREE.Vector3(-0.42, 0.88, -0.22).normalize();

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function colorToHex(r, g, b) {
  const toByte = (v) => Math.round(clamp(v, 0, 1) * 255);
  return `rgb(${toByte(r)},${toByte(g)},${toByte(b)})`;
}

function multiplyColor(rgb, factor) {
  return colorToHex(rgb[0] * factor, rgb[1] * factor, rgb[2] * factor);
}

function projectPoint(vector, viewProjectionMatrix) {
  const projected = vector.clone().applyMatrix4(viewProjectionMatrix);
  return {
    x: (projected.x * 0.5 + 0.5) * WIDTH,
    y: (-projected.y * 0.5 + 0.5) * HEIGHT,
    z: projected.z,
  };
}

function getMaterialColor(material) {
  if (!material) return [0.7, 0.7, 0.7];
  if (typeof material.getBaseColorFactor === 'function') {
    const base = material.getBaseColorFactor();
    return [base[0], base[1], base[2]];
  }
  return [0.7, 0.7, 0.7];
}

function shouldSkipMaterial(material) {
  const name = String(material?.getName?.() || '');
  return /GLASS|NET/.test(name);
}

function* walkNode(node) {
  yield node;
  for (const child of node.listChildren()) {
    yield* walkNode(child);
  }
}

async function loadDocument() {
  const io = new NodeIO();
  return await io.read(GLB_PATH);
}

function collectTriangles(document, camera) {
  const root = document.getRoot();
  const scene = root.listScenes()[0];
  const cameraMatrix = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
  const triangles = [];

  for (const rootNode of scene.listChildren()) {
    for (const node of walkNode(rootNode)) {
      const mesh = node.getMesh();
      if (!mesh) continue;
      const world = new THREE.Matrix4().fromArray(node.getWorldMatrix());
      const normalMatrix = new THREE.Matrix3().getNormalMatrix(world);

      for (const primitive of mesh.listPrimitives()) {
        const material = primitive.getMaterial();
        if (shouldSkipMaterial(material)) continue;
        const color = getMaterialColor(material);
        const positionAccessor = primitive.getAttribute('POSITION');
        const normalAccessor = primitive.getAttribute('NORMAL');
        const indexAccessor = primitive.getIndices();
        if (!positionAccessor || !indexAccessor) continue;
        const positions = positionAccessor.getArray();
        const normals = normalAccessor ? normalAccessor.getArray() : null;
        const indices = indexAccessor.getArray();

        for (let i = 0; i < indices.length; i += 3) {
          const i0 = indices[i] * 3;
          const i1 = indices[i + 1] * 3;
          const i2 = indices[i + 2] * 3;

          const v0 = new THREE.Vector3(positions[i0], positions[i0 + 1], positions[i0 + 2]).applyMatrix4(world);
          const v1 = new THREE.Vector3(positions[i1], positions[i1 + 1], positions[i1 + 2]).applyMatrix4(world);
          const v2 = new THREE.Vector3(positions[i2], positions[i2 + 1], positions[i2 + 2]).applyMatrix4(world);

          const faceNormal = normals
            ? new THREE.Vector3(
                (normals[i0] + normals[i1] + normals[i2]) / 3,
                (normals[i0 + 1] + normals[i1 + 1] + normals[i2 + 1]) / 3,
                (normals[i0 + 2] + normals[i1 + 2] + normals[i2 + 2]) / 3,
              ).applyMatrix3(normalMatrix).normalize()
            : new THREE.Vector3().subVectors(v1, v0).cross(new THREE.Vector3().subVectors(v2, v0)).normalize();

          const camDir = new THREE.Vector3().subVectors(camera.position, v0).normalize();
          if (faceNormal.dot(camDir) <= 0.02) continue;

          const p0 = projectPoint(v0, cameraMatrix);
          const p1 = projectPoint(v1, cameraMatrix);
          const p2 = projectPoint(v2, cameraMatrix);
          const area = Math.abs((p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y));
          if (area < 0.35) continue;

          const shade = 0.46 + Math.max(0, faceNormal.dot(LIGHT_DIR)) * 0.64;
          triangles.push({
            depth: (p0.z + p1.z + p2.z) / 3,
            fill: multiplyColor(color, shade),
            points: `${p0.x.toFixed(1)},${p0.y.toFixed(1)} ${p1.x.toFixed(1)},${p1.y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`,
          });
        }
      }
    }
  }

  triangles.sort((a, b) => a.depth - b.depth);
  return triangles;
}

function makeCamera(position, target, fov = 32) {
  const camera = new THREE.PerspectiveCamera(fov, WIDTH / HEIGHT, 0.1, 2000);
  camera.position.copy(position);
  camera.lookAt(target);
  camera.updateMatrixWorld(true);
  camera.updateProjectionMatrix();
  return camera;
}

async function renderView(document, outputPath, camera) {
  const triangles = collectTriangles(document, camera);
  const svg = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">`,
    '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#d7e9fb"/><stop offset="100%" stop-color="#f6fbff"/></linearGradient></defs>',
    `<rect width="${WIDTH}" height="${HEIGHT}" fill="url(#bg)"/>`,
    ...triangles.map((triangle) => `<polygon points="${triangle.points}" fill="${triangle.fill}" stroke="none"/>`),
    '</svg>',
  ].join('');

  await sharp(Buffer.from(svg)).png().toFile(outputPath);
}

const document = await loadDocument();
const target = new THREE.Vector3(0, 10, 0);
await renderView(document, OUT_HERO, makeCamera(new THREE.Vector3(-150, 88, -124), target, 30));
await renderView(document, OUT_CORNER, makeCamera(new THREE.Vector3(0, 34, -112), new THREE.Vector3(0, 8, 8), 36));
console.log(`Wrote ${OUT_HERO}`);
console.log(`Wrote ${OUT_CORNER}`);
