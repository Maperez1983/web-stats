import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Document, NodeIO } from '@gltf-transform/core';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const mpfbRoot = path.join(
  process.env.HOME || '/Users/miguelperezrodriguez',
  'Library/Application Support/Blender/5.1/extensions/user_default/mpfb',
);
const baseObj = path.join(mpfbRoot, 'data/3dobjs/base.obj');
const out = path.join(root, 'football/static/football/models/avatar/player_humanoid.glb');
const premiumOut = path.join(root, 'football/static/football/models/avatar/player_premium_mpfb.glb');
const downloadsOut = path.join(process.env.HOME || '/Users/miguelperezrodriguez', 'Downloads/player_premium_mpfb.glb');

const scale = 0.1075;

const normalize = (v) => {
  const len = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / len, v[1] / len, v[2] / len];
};

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const cross = (a, b) => [
  (a[1] * b[2]) - (a[2] * b[1]),
  (a[2] * b[0]) - (a[0] * b[2]),
  (a[0] * b[1]) - (a[1] * b[0]),
];

function parseMpfbObj(file) {
  const sourceVertices = [];
  const sourceTriangles = [];
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  let group = '';

  for (const line of lines) {
    if (line.startsWith('v ')) {
      const [, x, y, z] = line.trim().split(/\s+/).map(Number);
      sourceVertices.push([x * scale, y * scale, -z * scale]);
    } else if (line.startsWith('g ')) {
      group = line.trim().slice(2);
    } else if (group === 'body' && line.startsWith('f ')) {
      const parts = line.trim().slice(2).split(/\s+/).map((part) => Number(part.split('/')[0]) - 1);
      for (let i = 1; i < parts.length - 1; i += 1) {
        sourceTriangles.push(parts[0], parts[i], parts[i + 1]);
      }
    }
  }

  const remap = new Map();
  const vertices = [];
  const triangles = [];
  for (const index of sourceTriangles) {
    if (!remap.has(index)) {
      remap.set(index, vertices.length);
      vertices.push(sourceVertices[index]);
    }
    triangles.push(remap.get(index));
  }

  const minY = vertices.reduce((min, vertex) => Math.min(min, vertex[1]), Infinity);
  for (const vertex of vertices) vertex[1] -= minY;

  const normals = Array.from({ length: vertices.length }, () => [0, 0, 0]);
  for (let i = 0; i < triangles.length; i += 3) {
    const ia = triangles[i];
    const ib = triangles[i + 1];
    const ic = triangles[i + 2];
    const normal = normalize(cross(sub(vertices[ib], vertices[ia]), sub(vertices[ic], vertices[ia])));
    for (const index of [ia, ib, ic]) {
      normals[index][0] += normal[0];
      normals[index][1] += normal[1];
      normals[index][2] += normal[2];
    }
  }

  return {
    positions: new Float32Array(vertices.flat()),
    normals: new Float32Array(normals.map(normalize).flat()),
    indices: new Uint32Array(triangles),
  };
}

function cylinderGeometry({ radius = 1, height = 1, segments = 48, center = [0, 0, 0], scale: s = [1, 1, 1], axis = 'y' }) {
  const positions = [];
  const indices = [];
  const normals = [];
  const half = height / 2;

  const map = (x, y, z) => {
    if (axis === 'x') return [center[0] + y, center[1] + z, center[2] + x];
    if (axis === 'z') return [center[0] + x, center[1] + y, center[2] + z];
    return [center[0] + x, center[1] + y, center[2] + z];
  };

  for (let i = 0; i <= segments; i += 1) {
    const a = (i / segments) * Math.PI * 2;
    const x = Math.cos(a) * radius * s[0];
    const z = Math.sin(a) * radius * s[2];
    const n = normalize([Math.cos(a) / s[0], 0, Math.sin(a) / s[2]]);
    positions.push(...map(x, -half * s[1], z), ...map(x, half * s[1], z));
    normals.push(...n, ...n);
  }
  for (let i = 0; i < segments; i += 1) {
    const a = i * 2;
    indices.push(a, a + 1, a + 3, a, a + 3, a + 2);
  }
  return { positions, normals, indices };
}

function sphereGeometry({ radius = 1, width = 32, height = 16, center = [0, 0, 0], scale: s = [1, 1, 1] }) {
  const positions = [];
  const normals = [];
  const indices = [];

  for (let y = 0; y <= height; y += 1) {
    const v = y / height;
    const theta = v * Math.PI;
    for (let x = 0; x <= width; x += 1) {
      const u = x / width;
      const phi = u * Math.PI * 2;
      const nx = Math.cos(phi) * Math.sin(theta);
      const ny = Math.cos(theta);
      const nz = Math.sin(phi) * Math.sin(theta);
      positions.push(center[0] + nx * radius * s[0], center[1] + ny * radius * s[1], center[2] + nz * radius * s[2]);
      normals.push(...normalize([nx / s[0], ny / s[1], nz / s[2]]));
    }
  }
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const a = y * (width + 1) + x;
      const b = a + width + 1;
      indices.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }
  return { positions, normals, indices };
}

function boxGeometry({ center = [0, 0, 0], size = [1, 1, 1] }) {
  const [cx, cy, cz] = center;
  const [sx, sy, sz] = size.map((value) => value / 2);
  const faces = [
    [[1, 0, 0], [[sx, -sy, -sz], [sx, sy, -sz], [sx, sy, sz], [sx, -sy, sz]]],
    [[-1, 0, 0], [[-sx, -sy, sz], [-sx, sy, sz], [-sx, sy, -sz], [-sx, -sy, -sz]]],
    [[0, 1, 0], [[-sx, sy, -sz], [-sx, sy, sz], [sx, sy, sz], [sx, sy, -sz]]],
    [[0, -1, 0], [[-sx, -sy, sz], [-sx, -sy, -sz], [sx, -sy, -sz], [sx, -sy, sz]]],
    [[0, 0, 1], [[sx, -sy, sz], [sx, sy, sz], [-sx, sy, sz], [-sx, -sy, sz]]],
    [[0, 0, -1], [[-sx, -sy, -sz], [-sx, sy, -sz], [sx, sy, -sz], [sx, -sy, -sz]]],
  ];
  const positions = [];
  const normals = [];
  const indices = [];
  for (const [normal, verts] of faces) {
    const offset = positions.length / 3;
    for (const vertex of verts) {
      positions.push(cx + vertex[0], cy + vertex[1], cz + vertex[2]);
      normals.push(...normal);
    }
    indices.push(offset, offset + 1, offset + 2, offset, offset + 2, offset + 3);
  }
  return { positions, normals, indices };
}

function addMesh(document, scene, buffer, name, geometry, material) {
  const positions = geometry.positions instanceof Float32Array ? geometry.positions : new Float32Array(geometry.positions);
  const normals = geometry.normals instanceof Float32Array ? geometry.normals : new Float32Array(geometry.normals);
  const indices = geometry.indices instanceof Uint32Array ? geometry.indices : new Uint32Array(geometry.indices);
  const primitive = document.createPrimitive()
    .setAttribute('POSITION', document.createAccessor(`${name}_position`).setType('VEC3').setArray(positions).setBuffer(buffer))
    .setAttribute('NORMAL', document.createAccessor(`${name}_normal`).setType('VEC3').setArray(normals).setBuffer(buffer))
    .setIndices(document.createAccessor(`${name}_indices`).setType('SCALAR').setArray(indices).setBuffer(buffer))
    .setMaterial(material);
  const mesh = document.createMesh(name).addPrimitive(primitive);
  scene.addChild(document.createNode(name).setMesh(mesh));
}

const document = new Document();
const buffer = document.createBuffer();
const scene = document.createScene('premium_task_player_avatar');
document.getRoot().setDefaultScene(scene);

const makeMaterial = (name, color, roughness = 0.55) => document.createMaterial(name)
  .setBaseColorFactor(color)
  .setRoughnessFactor(roughness)
  .setMetallicFactor(0);

const skin = makeMaterial('natural_skin_warm_mpfb', [0.72, 0.45, 0.32, 1], 0.62);
const kit = makeMaterial('deep_green_training_kit', [0.0, 0.28, 0.18, 1], 0.45);
const kitDark = makeMaterial('shadow_green_shorts', [0.0, 0.12, 0.10, 1], 0.5);
const white = makeMaterial('white_kit_details', [0.95, 0.97, 0.96, 1], 0.4);
const boots = makeMaterial('matte_black_boots', [0.015, 0.018, 0.02, 1], 0.5);
const hair = makeMaterial('short_dark_hair', [0.025, 0.018, 0.014, 1], 0.7);
const ballWhite = makeMaterial('training_ball_white', [0.96, 0.96, 0.9, 1], 0.45);
const ballGreen = makeMaterial('training_ball_green_panels', [0.0, 0.34, 0.22, 1], 0.45);

addMesh(document, scene, buffer, 'mpfb_hm08_athlete_body', parseMpfbObj(baseObj), skin);
addMesh(document, scene, buffer, 'fitted_jersey_torso', cylinderGeometry({ radius: 0.24, height: 0.48, center: [0, 1.14, -0.015], scale: [0.83, 1, 0.48] }), kit);
addMesh(document, scene, buffer, 'athletic_shorts', cylinderGeometry({ radius: 0.21, height: 0.23, center: [0, 0.84, -0.01], scale: [0.95, 1, 0.54] }), kitDark);
addMesh(document, scene, buffer, 'short_dark_hair_cap', sphereGeometry({ radius: 0.12, center: [0, 1.73, -0.02], scale: [0.96, 0.5, 0.78] }), hair);
addMesh(document, scene, buffer, 'front_kit_stripe', boxGeometry({ center: [0, 1.15, -0.135], size: [0.19, 0.35, 0.018] }), white);
addMesh(document, scene, buffer, 'neck_trim', cylinderGeometry({ radius: 0.115, height: 0.025, center: [0, 1.39, -0.02], scale: [1, 1, 0.65] }), white);

for (const side of [-1, 1]) {
  addMesh(document, scene, buffer, side < 0 ? 'left_short_sleeve' : 'right_short_sleeve', cylinderGeometry({ axis: 'x', radius: 0.055, height: 0.22, center: [side * 0.255, 1.30, -0.01], scale: [1, 0.82, 1] }), kit);
  addMesh(document, scene, buffer, side < 0 ? 'left_sock' : 'right_sock', cylinderGeometry({ radius: 0.052, height: 0.34, center: [side * 0.135, 0.34, 0.0], scale: [0.72, 1, 0.6] }), kit);
  addMesh(document, scene, buffer, side < 0 ? 'left_boot' : 'right_boot', boxGeometry({ center: [side * 0.135, 0.045, -0.05], size: [0.105, 0.055, 0.2] }), boots);
}

addMesh(document, scene, buffer, 'training_ball', sphereGeometry({ radius: 0.075, center: [0.34, 0.12, -0.18] }), ballWhite);
addMesh(document, scene, buffer, 'training_ball_band', cylinderGeometry({ axis: 'z', radius: 0.058, height: 0.005, center: [0.34, 0.12, -0.255], scale: [1, 1, 1] }), ballGreen);

fs.mkdirSync(path.dirname(out), { recursive: true });
await new NodeIO().write(out, document);
fs.copyFileSync(out, premiumOut);
fs.copyFileSync(out, downloadsOut);

console.log(`source: ${baseObj}`);
console.log(out);
console.log(premiumOut);
console.log(downloadsOut);
