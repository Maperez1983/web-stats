import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import * as THREE from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';

globalThis.FileReader = class {
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then((buffer) => {
      this.result = buffer;
      this.onloadend?.();
    });
  }

  readAsDataURL(blob) {
    blob.arrayBuffer().then((buffer) => {
      this.result = `data:${blob.type || 'application/octet-stream'};base64,${Buffer.from(buffer).toString('base64')}`;
      this.onloadend?.();
    });
  }
};

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'football/static/football/models/pitch3d/stadium_benagalbon_reference.glb');

const scene = new THREE.Scene();
scene.name = 'pitch_3d_benagalbon_reference_dedicated_stadium';

const mats = {
  concrete: new THREE.MeshStandardMaterial({ name: 'REF_PRECAST_CONCRETE', color: 0xb8c0bb, roughness: 0.82, metalness: 0.02 }),
  darkConcrete: new THREE.MeshStandardMaterial({ name: 'REF_DARK_CONCRETE', color: 0x333b3a, roughness: 0.88, metalness: 0.02 }),
  green: new THREE.MeshStandardMaterial({ name: 'REF_BENAGALBON_GREEN_CHAIR', color: 0x047044, roughness: 0.58, metalness: 0.01 }),
  greenDark: new THREE.MeshStandardMaterial({ name: 'REF_DEEP_GREEN_CHAIR', color: 0x063f31, roughness: 0.62, metalness: 0.01 }),
  white: new THREE.MeshStandardMaterial({ name: 'REF_WHITE_LETTER_CHAIR', color: 0xf8faf5, roughness: 0.54, metalness: 0.01 }),
  metal: new THREE.MeshStandardMaterial({ name: 'REF_STEEL_TRUSS_METAL', color: 0x5f6b6f, roughness: 0.36, metalness: 0.42 }),
  darkMetal: new THREE.MeshStandardMaterial({ name: 'REF_DARK_STEEL', color: 0x1f2933, roughness: 0.42, metalness: 0.35 }),
  roof: new THREE.MeshStandardMaterial({ name: 'REF_LIGHT_ROOF_SOFFIT', color: 0xe6ebe7, roughness: 0.44, metalness: 0.18 }),
  glass: new THREE.MeshPhysicalMaterial({ name: 'REF_CLEAR_DUGOUT_GLASS', color: 0xc7efff, roughness: 0.08, metalness: 0.02, transparent: true, opacity: 0.34, transmission: 0.18, side: THREE.DoubleSide }),
  led: new THREE.MeshStandardMaterial({ name: 'REF_GREEN_LED_BOARD_FACE', color: 0x063b2f, roughness: 0.24, metalness: 0.04, emissive: 0x063b2f, emissiveIntensity: 0.20 }),
  light: new THREE.MeshBasicMaterial({ name: 'REF_WARM_FLOODLIGHT_LINE', color: 0xfff3ca, toneMapped: false }),
  black: new THREE.MeshStandardMaterial({ name: 'REF_DEEP_RECESSES', color: 0x030712, roughness: 0.94, metalness: 0.01 }),
  grassLight: new THREE.MeshStandardMaterial({ name: 'REF_GRASS_LIGHT_BAND', color: 0x4f8d28, roughness: 0.9, metalness: 0.0 }),
  grassDark: new THREE.MeshStandardMaterial({ name: 'REF_GRASS_DARK_BAND', color: 0x32731f, roughness: 0.94, metalness: 0.0 }),
};

const add = (mesh) => {
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
  return mesh;
};

const box = (name, material, position, scale, rotation = [0, 0, 0]) => {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(scale[0], scale[1], scale[2]), material);
  mesh.name = name;
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  return add(mesh);
};

const cyl = (name, material, position, radius, depth, rotation = [0, 0, 0], segments = 48) => {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, depth, segments), material);
  mesh.name = name;
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  return add(mesh);
};

const pitchW = 105;
const pitchH = 68;

for (let i = 0; i < 14; i += 1) {
  const z = -pitchH / 2 + (pitchH / 14) * (i + 0.5);
  box(`ref_pitch_mowing_band_${i}`, i % 2 ? mats.grassDark : mats.grassLight, [0, 0.015, z], [pitchW, 0.03, pitchH / 14 + 0.02]);
}
box('ref_grey_pitch_apron_north', mats.concrete, [0, 0.04, pitchH / 2 + 1.7], [pitchW + 5.5, 0.08, 2.2]);
box('ref_grey_pitch_apron_south', mats.concrete, [0, 0.04, -(pitchH / 2 + 1.7)], [pitchW + 5.5, 0.08, 2.2]);
box('ref_grey_pitch_apron_east', mats.concrete, [pitchW / 2 + 1.7, 0.04, 0], [2.2, 0.08, pitchH + 5.5]);
box('ref_grey_pitch_apron_west', mats.concrete, [-(pitchW / 2 + 1.7), 0.04, 0], [2.2, 0.08, pitchH + 5.5]);

const letterGlyphs = {
  A: ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
  B: ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
  C: ['01111', '10000', '10000', '10000', '10000', '10000', '01111'],
  D: ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
  E: ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
  G: ['01111', '10000', '10000', '10111', '10001', '10001', '01111'],
  L: ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
  N: ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
  O: ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
  ' ': ['00', '00', '00', '00', '00', '00', '00'],
};

const buildLetterMap = (text) => {
  const cols = [];
  text.split('').forEach((char, idx) => {
    const glyph = letterGlyphs[char] || letterGlyphs[' '];
    for (let x = 0; x < glyph[0].length; x += 1) cols.push(glyph.map((row) => row[x] === '1'));
    if (idx < text.length - 1) cols.push([false, false, false, false, false, false, false]);
  });
  return cols;
};

const mainLetters = buildLetterMap('BENAGALBON CD');

const addStand = ({ name, side, cols, rows, length, depthStart, zFixed, xFixed }) => {
  const longSide = side === 'north' || side === 'south';
  const sign = side === 'north' || side === 'east' ? 1 : -1;
  const span = length;
  const aisleCols = longSide
    ? new Set([5, Math.floor(cols * 0.2), Math.floor(cols * 0.36), Math.floor(cols * 0.5), Math.floor(cols * 0.64), Math.floor(cols * 0.8), cols - 6])
    : new Set([4, Math.floor(cols * 0.28), Math.floor(cols * 0.5), Math.floor(cols * 0.72), cols - 5]);

  for (let row = 0; row < rows; row += 1) {
    const y = 2.15 + row * 0.31;
    const depth = depthStart + sign * row * 0.58;
    for (let col = 0; col < cols; col += 1) {
      const t = col / (cols - 1) - 0.5;
      const offset = t * span;
      const isAisle = aisleCols.has(col);
      let material = (row + col) % 9 === 0 ? mats.greenDark : mats.green;
      if (side === 'north') {
        const start = Math.floor((cols - mainLetters.length) / 2);
        const letterCol = col - start;
        if (row >= 5 && row <= 11 && letterCol >= 0 && letterCol < mainLetters.length && mainLetters[letterCol][row - 5]) material = mats.white;
      }
      if (isAisle) material = mats.concrete;
      if (longSide) {
        box(`${name}_chair_${row}_${col}`, material, [offset, y, depth], [0.44, 0.18, 0.38], [-0.08 * sign, 0, 0]);
        if (!isAisle) box(`${name}_back_${row}_${col}`, material, [offset, y + 0.25, depth + sign * 0.24], [0.44, 0.38, 0.08], [-0.22 * sign, 0, 0]);
      } else {
        box(`${name}_chair_${row}_${col}`, material, [depth, y, offset], [0.38, 0.18, 0.44], [0, 0.08 * sign, 0]);
        if (!isAisle) box(`${name}_back_${row}_${col}`, material, [depth + sign * 0.24, y + 0.25, offset], [0.08, 0.38, 0.44], [0, 0.22 * sign, 0]);
      }
    }
  }

  if (longSide) {
    box(`${name}_front_wall`, mats.concrete, [0, 1.55, zFixed - sign * 1.2], [span + 7, 1.0, 0.5]);
    box(`${name}_upper_concourse_band`, mats.concrete, [0, 7.2, zFixed + sign * 6.5], [span + 10, 0.55, 0.72], [-0.03 * sign, 0, 0]);
  } else {
    box(`${name}_front_wall`, mats.concrete, [xFixed - sign * 1.2, 1.55, 0], [0.5, 1.0, span + 7]);
    box(`${name}_upper_concourse_band`, mats.concrete, [xFixed + sign * 6.5, 7.1, 0], [0.72, 0.55, span + 10], [0, 0.03 * sign, 0]);
  }
};

addStand({ name: 'north_main_stand', side: 'north', cols: 92, rows: 19, length: pitchW + 48, depthStart: pitchH / 2 + 10.2, zFixed: pitchH / 2 + 10.2 });
addStand({ name: 'south_stand', side: 'south', cols: 78, rows: 17, length: pitchW + 42, depthStart: -(pitchH / 2 + 10.2), zFixed: -(pitchH / 2 + 10.2) });
addStand({ name: 'east_stand', side: 'east', cols: 52, rows: 15, length: pitchH + 34, depthStart: pitchW / 2 + 10.0, xFixed: pitchW / 2 + 10.0 });
addStand({ name: 'west_stand', side: 'west', cols: 52, rows: 15, length: pitchH + 34, depthStart: -(pitchW / 2 + 10.0), xFixed: -(pitchW / 2 + 10.0) });

const addRoof = () => {
  const y = 15.8;
  box('north_thin_roof_skin', mats.roof, [0, y, pitchH / 2 + 34.2], [pitchW + 68, 0.34, 12.5], [-0.04, 0, 0]);
  box('south_thin_roof_skin', mats.roof, [0, y, -(pitchH / 2 + 34.2)], [pitchW + 60, 0.34, 10.5], [0.04, 0, 0]);
  box('east_thin_roof_skin', mats.roof, [pitchW / 2 + 34.2, y, 0], [10.5, 0.34, pitchH + 56], [0, 0.04, 0]);
  box('west_thin_roof_skin', mats.roof, [-(pitchW / 2 + 34.2), y, 0], [10.5, 0.34, pitchH + 56], [0, -0.04, 0]);
  [-1, 1].forEach((sign) => {
    for (let i = -12; i <= 12; i += 1) {
      const x = i * ((pitchW + 54) / 24);
      box(`long_roof_front_truss_${sign}_${i}`, mats.metal, [x, 14.55, sign * (pitchH / 2 + 27.2)], [0.16, 1.2, 8.6], [-0.62 * sign, 0, i % 2 ? 0.36 : -0.36]);
      if (i % 2 === 0) box(`long_roof_light_${sign}_${i}`, mats.light, [x, 13.52, sign * (pitchH / 2 + 22.8)], [3.2, 0.14, 0.28]);
    }
  });
};
addRoof();

const addBoards = () => {
  [
    [0, pitchH / 2 + 3.1, pitchW + 8, 0.22],
    [0, -(pitchH / 2 + 3.1), pitchW + 8, 0.22],
    [pitchW / 2 + 3.1, 0, 0.22, pitchH + 7],
    [-(pitchW / 2 + 3.1), 0, 0.22, pitchH + 7],
  ].forEach(([x, z, sx, sz], idx) => {
    box(`continuous_green_partner_board_${idx}`, mats.led, [x, 0.88, z], [sx, 1.0, sz]);
    box(`board_white_top_cap_${idx}`, mats.white, [x, 1.36, z], [sx, 0.08, sz + 0.04]);
  });
};
addBoards();

const addDugout = (x, label) => {
  const z = -(pitchH / 2 + 6.0);
  box(`dugout_${label}_base`, mats.darkMetal, [x, 0.25, z], [12.8, 0.28, 2.0]);
  for (let i = 0; i < 6; i += 1) {
    const t = i / 5;
    box(`dugout_${label}_curved_glass_${i}`, mats.glass, [x, 1.10 + Math.sin(t * Math.PI * 0.58), z - 0.75 + t * 1.38], [12.2, 0.06, 0.42], [-0.45 + t * 0.26, 0, 0]);
  }
  for (let i = 0; i < 8; i += 1) {
    const sx = x - 4.85 + i * 1.38;
    box(`dugout_${label}_chair_${i}`, mats.green, [sx, 0.68, z + 0.14], [0.78, 0.18, 0.56]);
    box(`dugout_${label}_back_${i}`, mats.green, [sx, 1.02, z + 0.46], [0.78, 0.70, 0.10], [-0.18, 0, 0]);
  }
};
addDugout(-22, 'home');
addDugout(0, 'central');
addDugout(22, 'away');

cyl('main_round_cdb_crest', mats.white, [0, 8.6, pitchH / 2 + 11.0], 3.4, 0.16, [Math.PI / 2, 0, 0], 96);
box('corner_scoreboard_frame', mats.black, [pitchW / 2 + 8.5, 6.4, pitchH / 2 + 8.6], [8.2, 4.6, 0.30], [0, -Math.PI / 4, 0]);
box('corner_scoreboard_face', mats.led, [pitchW / 2 + 8.25, 6.4, pitchH / 2 + 8.35], [7.5, 3.9, 0.08], [0, -Math.PI / 4, 0]);

scene.add(new THREE.AmbientLight(0xffffff, 0.62));
const sun = new THREE.DirectionalLight(0xfff0d0, 1.2);
sun.position.set(-80, 80, -120);
scene.add(sun);

fs.mkdirSync(path.dirname(out), { recursive: true });
const exporter = new GLTFExporter();
const result = await exporter.parseAsync(scene, {
  binary: true,
  trs: false,
  onlyVisible: true,
  maxTextureSize: 1024,
});
fs.writeFileSync(out, Buffer.from(result));
console.log(`Wrote ${path.relative(root, out)} (${Buffer.byteLength(Buffer.from(result))} bytes)`);
