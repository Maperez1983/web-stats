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
  concreteLine: new THREE.MeshStandardMaterial({ name: 'REF_CONCRETE_EXPANSION_JOINT', color: 0x78827e, roughness: 0.9, metalness: 0.01 }),
  darkConcrete: new THREE.MeshStandardMaterial({ name: 'REF_DARK_CONCRETE', color: 0x333b3a, roughness: 0.88, metalness: 0.02 }),
  skyPanel: new THREE.MeshBasicMaterial({ name: 'REF_SOFT_SKY_BACKDROP', color: 0x9dc3dc, toneMapped: false }),
  mountain: new THREE.MeshStandardMaterial({ name: 'REF_DISTANCE_MOUNTAINS', color: 0x8fa39d, roughness: 0.98, metalness: 0.0 }),
  city: new THREE.MeshStandardMaterial({ name: 'REF_DISTANCE_CITY_BLOCKS', color: 0xd6ddd8, roughness: 0.86, metalness: 0.02 }),
  green: new THREE.MeshStandardMaterial({ name: 'REF_BENAGALBON_GREEN_CHAIR', color: 0x047044, roughness: 0.58, metalness: 0.01 }),
  greenDark: new THREE.MeshStandardMaterial({ name: 'REF_DEEP_GREEN_CHAIR', color: 0x063f31, roughness: 0.62, metalness: 0.01 }),
  crowdDark: new THREE.MeshStandardMaterial({ name: 'REF_CROWD_DARK_COATS', color: 0x14231f, roughness: 0.78, metalness: 0.0 }),
  crowdGreen: new THREE.MeshStandardMaterial({ name: 'REF_CROWD_GREEN_SHIRTS', color: 0x0a6f43, roughness: 0.74, metalness: 0.0 }),
  crowdWhite: new THREE.MeshStandardMaterial({ name: 'REF_CROWD_WHITE_SHIRTS', color: 0xe7eee7, roughness: 0.68, metalness: 0.0 }),
  white: new THREE.MeshStandardMaterial({ name: 'REF_WHITE_LETTER_CHAIR', color: 0xf8faf5, roughness: 0.54, metalness: 0.01 }),
  lineWhite: new THREE.MeshStandardMaterial({ name: 'REF_PAINTED_PITCH_LINES', color: 0xf4f7ef, roughness: 0.76, metalness: 0.0 }),
  metal: new THREE.MeshStandardMaterial({ name: 'REF_STEEL_TRUSS_METAL', color: 0x5f6b6f, roughness: 0.36, metalness: 0.42 }),
  darkMetal: new THREE.MeshStandardMaterial({ name: 'REF_DARK_STEEL', color: 0x1f2933, roughness: 0.42, metalness: 0.35 }),
  roof: new THREE.MeshStandardMaterial({ name: 'REF_LIGHT_ROOF_SOFFIT', color: 0xe6ebe7, roughness: 0.44, metalness: 0.18 }),
  roofShadow: new THREE.MeshStandardMaterial({ name: 'REF_ROOF_CAST_SHADOW', color: 0x111827, roughness: 0.96, metalness: 0.0, transparent: true, opacity: 0.22 }),
  glass: new THREE.MeshPhysicalMaterial({ name: 'REF_CLEAR_DUGOUT_GLASS', color: 0xc7efff, roughness: 0.08, metalness: 0.02, transparent: true, opacity: 0.34, transmission: 0.18, side: THREE.DoubleSide }),
  led: new THREE.MeshStandardMaterial({ name: 'REF_GREEN_LED_BOARD_FACE', color: 0x063b2f, roughness: 0.24, metalness: 0.04, emissive: 0x063b2f, emissiveIntensity: 0.20 }),
  light: new THREE.MeshBasicMaterial({ name: 'REF_WARM_FLOODLIGHT_LINE', color: 0xfff3ca, toneMapped: false }),
  black: new THREE.MeshStandardMaterial({ name: 'REF_DEEP_RECESSES', color: 0x030712, roughness: 0.94, metalness: 0.01 }),
  mesh: new THREE.MeshStandardMaterial({ name: 'REF_FINE_STADIUM_MESH', color: 0xaeb8b5, roughness: 0.48, metalness: 0.32 }),
  grassFiber: new THREE.MeshStandardMaterial({ name: 'REF_GRASS_FINE_FIBER_HIGHLIGHT', color: 0x7ab847, roughness: 0.95, metalness: 0.0 }),
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

const torus = (name, material, position, radius, tube, rotation = [0, 0, 0], segments = 96) => {
  const mesh = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 8, segments), material);
  mesh.name = name;
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  return add(mesh);
};

const tri = (name, material, points, z) => {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([
    points[0][0], points[0][1], z,
    points[1][0], points[1][1], z,
    points[2][0], points[2][1], z,
  ], 3));
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = name;
  return add(mesh);
};

const pitchW = 105;
const pitchH = 68;

for (let i = 0; i < 14; i += 1) {
  const z = -pitchH / 2 + (pitchH / 14) * (i + 0.5);
  box(`ref_pitch_mowing_band_${i}`, i % 2 ? mats.grassDark : mats.grassLight, [0, 0.015, z], [pitchW, 0.03, pitchH / 14 + 0.02]);
}
for (let i = 0; i < 44; i += 1) {
  const x = -pitchW / 2 + 1.4 + i * 2.42;
  const z = -pitchH / 2 + 1.0 + ((i * 17) % 66);
  box(`ref_grass_fiber_highlight_${i}`, mats.grassFiber, [x, 0.041, z], [1.3, 0.012, 0.045], [0, 0.18 + (i % 5) * 0.05, 0]);
}
const addPitchMarkings = () => {
  const y = 0.075;
  box('pitch_touchline_north', mats.lineWhite, [0, y, pitchH / 2], [pitchW, 0.035, 0.16]);
  box('pitch_touchline_south', mats.lineWhite, [0, y, -pitchH / 2], [pitchW, 0.035, 0.16]);
  box('pitch_goal_line_east', mats.lineWhite, [pitchW / 2, y, 0], [0.16, 0.035, pitchH]);
  box('pitch_goal_line_west', mats.lineWhite, [-pitchW / 2, y, 0], [0.16, 0.035, pitchH]);
  box('pitch_halfway_line', mats.lineWhite, [0, y, 0], [0.16, 0.035, pitchH]);
  torus('pitch_center_circle', mats.lineWhite, [0, y + 0.005, 0], 9.15, 0.055, [Math.PI / 2, 0, 0], 128);
  cyl('pitch_center_spot', mats.lineWhite, [0, y + 0.005, 0], 0.18, 0.035, [0, 0, 0], 24);
  [-1, 1].forEach((sign) => {
    const x = sign * pitchW / 2;
    box(`penalty_area_top_${sign}`, mats.lineWhite, [x - sign * 8.25, y, 20.16], [16.5, 0.035, 0.13]);
    box(`penalty_area_bottom_${sign}`, mats.lineWhite, [x - sign * 8.25, y, -20.16], [16.5, 0.035, 0.13]);
    box(`penalty_area_inner_${sign}`, mats.lineWhite, [x - sign * 16.5, y, 0], [0.13, 0.035, 40.32]);
    box(`six_yard_top_${sign}`, mats.lineWhite, [x - sign * 2.75, y, 9.16], [5.5, 0.035, 0.13]);
    box(`six_yard_bottom_${sign}`, mats.lineWhite, [x - sign * 2.75, y, -9.16], [5.5, 0.035, 0.13]);
    box(`six_yard_inner_${sign}`, mats.lineWhite, [x - sign * 5.5, y, 0], [0.13, 0.035, 18.32]);
    cyl(`penalty_spot_${sign}`, mats.lineWhite, [x - sign * 11, y + 0.005, 0], 0.16, 0.035, [0, 0, 0], 24);
  });
};
addPitchMarkings();
box('ref_grey_pitch_apron_north', mats.concrete, [0, 0.04, pitchH / 2 + 1.7], [pitchW + 5.5, 0.08, 2.2]);
box('ref_grey_pitch_apron_south', mats.concrete, [0, 0.04, -(pitchH / 2 + 1.7)], [pitchW + 5.5, 0.08, 2.2]);
box('ref_grey_pitch_apron_east', mats.concrete, [pitchW / 2 + 1.7, 0.04, 0], [2.2, 0.08, pitchH + 5.5]);
box('ref_grey_pitch_apron_west', mats.concrete, [-(pitchW / 2 + 1.7), 0.04, 0], [2.2, 0.08, pitchH + 5.5]);
for (let i = -12; i <= 12; i += 1) {
  const x = i * 4.5;
  box(`north_apron_expansion_joint_${i}`, mats.concreteLine, [x, 0.095, pitchH / 2 + 1.7], [0.045, 0.025, 2.15]);
  box(`south_apron_expansion_joint_${i}`, mats.concreteLine, [x, 0.095, -(pitchH / 2 + 1.7)], [0.045, 0.025, 2.15]);
}
for (let i = -8; i <= 8; i += 1) {
  const z = i * 4.1;
  box(`east_apron_expansion_joint_${i}`, mats.concreteLine, [pitchW / 2 + 1.7, 0.095, z], [2.15, 0.025, 0.045]);
  box(`west_apron_expansion_joint_${i}`, mats.concreteLine, [-(pitchW / 2 + 1.7), 0.095, z], [2.15, 0.025, 0.045]);
}

const letterGlyphs = {
  A: ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
  B: ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
  C: ['01111', '10000', '10000', '10000', '10000', '10000', '01111'],
  D: ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
  E: ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
  G: ['01111', '10000', '10000', '10111', '10001', '10001', '01111'],
  F: ['11111', '10000', '10000', '11110', '10000', '10000', '10000'],
  I: ['11111', '00100', '00100', '00100', '00100', '00100', '11111'],
  J: ['00111', '00010', '00010', '00010', '10010', '10010', '01100'],
  L: ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
  M: ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],
  N: ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
  O: ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
  P: ['11110', '10001', '10001', '11110', '10000', '10000', '10000'],
  R: ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
  S: ['01111', '10000', '10000', '01110', '00001', '00001', '11110'],
  T: ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
  U: ['10001', '10001', '10001', '10001', '10001', '10001', '01110'],
  V: ['10001', '10001', '10001', '10001', '10001', '01010', '00100'],
  '2': ['01110', '10001', '00001', '00010', '00100', '01000', '11111'],
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

const writeBlockText = ({ text, name, origin, cell = 0.18, material = mats.white, plane = 'xz', rotation = [0, 0, 0] }) => {
  const columns = buildLetterMap(text);
  columns.forEach((col, xIdx) => {
    col.forEach((on, yIdx) => {
      if (!on) return;
      if (plane === 'xy') {
        box(`${name}_glyph_${xIdx}_${yIdx}`, material, [origin[0] + xIdx * cell, origin[1] - yIdx * cell, origin[2]], [cell * 0.82, cell * 0.82, 0.045], rotation);
      } else if (plane === 'zy') {
        box(`${name}_glyph_${xIdx}_${yIdx}`, material, [origin[0], origin[1] - yIdx * cell, origin[2] + xIdx * cell], [0.045, cell * 0.82, cell * 0.82], rotation);
      } else {
        box(`${name}_glyph_${xIdx}_${yIdx}`, material, [origin[0] + xIdx * cell, origin[1], origin[2] + yIdx * cell], [cell * 0.82, 0.045, cell * 0.82], rotation);
      }
    });
  });
};

const addStand = ({ name, side, cols, rows, length, depthStart, zFixed, xFixed }) => {
  const longSide = side === 'north' || side === 'south';
  const sign = side === 'north' || side === 'east' ? 1 : -1;
  const span = length;
  const aisleCols = longSide
    ? new Set([5, Math.floor(cols * 0.2), Math.floor(cols * 0.36), Math.floor(cols * 0.5), Math.floor(cols * 0.64), Math.floor(cols * 0.8), cols - 6])
    : new Set([4, Math.floor(cols * 0.28), Math.floor(cols * 0.5), Math.floor(cols * 0.72), cols - 5]);
  const crowdMaterials = [mats.crowdDark, mats.crowdGreen, mats.crowdWhite];

  for (let row = 0; row < rows; row += 1) {
    const y = 2.15 + row * 0.31;
    const depth = depthStart + sign * row * 0.58;
    if (longSide) {
      box(`${name}_continuous_riser_${row}`, mats.darkConcrete, [0, y - 0.18, depth + sign * 0.18], [span + 3.2, 0.16, 0.22], [-0.03 * sign, 0, 0]);
    } else {
      box(`${name}_continuous_riser_${row}`, mats.darkConcrete, [depth + sign * 0.18, y - 0.18, 0], [0.22, 0.16, span + 3.2], [0, 0.03 * sign, 0]);
    }
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
        if (!isAisle) {
          box(`${name}_back_${row}_${col}`, material, [offset, y + 0.25, depth + sign * 0.24], [0.44, 0.38, 0.08], [-0.22 * sign, 0, 0]);
          if (row % 4 === 0 && col % 6 === 0) box(`${name}_seat_highlight_${row}_${col}`, mats.white, [offset - 0.05, y + 0.1, depth - sign * 0.03], [0.18, 0.018, 0.12], [-0.08 * sign, 0, 0]);
        }
      } else {
        box(`${name}_chair_${row}_${col}`, material, [depth, y, offset], [0.38, 0.18, 0.44], [0, 0.08 * sign, 0]);
        if (!isAisle) {
          box(`${name}_back_${row}_${col}`, material, [depth + sign * 0.24, y + 0.25, offset], [0.08, 0.38, 0.44], [0, 0.22 * sign, 0]);
          if (row % 4 === 0 && col % 6 === 0) box(`${name}_seat_highlight_${row}_${col}`, mats.white, [depth - sign * 0.03, y + 0.1, offset - 0.05], [0.12, 0.018, 0.18], [0, 0.08 * sign, 0]);
        }
      }
      const crowdSeed = (row * 37 + col * 17 + name.length) % 19;
      if (!isAisle && row >= Math.floor(rows * 0.45) && row % 2 === 1 && col % 4 === 1 && crowdSeed < 7) {
        const crowdMat = crowdMaterials[(row + col) % crowdMaterials.length];
        if (longSide) {
          box(`${name}_crowd_body_${row}_${col}`, crowdMat, [offset, y + 0.44, depth + sign * 0.03], [0.28, 0.46, 0.18], [-0.06 * sign, 0, 0]);
          box(`${name}_crowd_head_${row}_${col}`, mats.concrete, [offset, y + 0.77, depth + sign * 0.03], [0.18, 0.16, 0.16], [-0.04 * sign, 0, 0]);
        } else {
          box(`${name}_crowd_body_${row}_${col}`, crowdMat, [depth + sign * 0.03, y + 0.44, offset], [0.18, 0.46, 0.28], [0, 0.06 * sign, 0]);
          box(`${name}_crowd_head_${row}_${col}`, mats.concrete, [depth + sign * 0.03, y + 0.77, offset], [0.16, 0.16, 0.18], [0, 0.04 * sign, 0]);
        }
      }
    }
  }

  [...aisleCols].forEach((col, idx) => {
    const t = col / (cols - 1) - 0.5;
    const offset = t * span;
    const yMid = 2.15 + ((rows - 1) * 0.31) / 2;
    const run = rows * 0.58 + 0.55;
    if (longSide) {
      const zMid = depthStart + sign * ((rows - 1) * 0.58) / 2;
      box(`${name}_full_height_stair_run_${idx}`, mats.concrete, [offset, yMid - 0.04, zMid], [0.92, 0.10, run], [-0.11 * sign, 0, 0]);
      box(`${name}_stair_left_handrail_${idx}`, mats.metal, [offset - 0.55, yMid + 0.42, zMid], [0.07, 0.08, run + 0.4], [-0.11 * sign, 0, 0]);
      box(`${name}_stair_right_handrail_${idx}`, mats.metal, [offset + 0.55, yMid + 0.42, zMid], [0.07, 0.08, run + 0.4], [-0.11 * sign, 0, 0]);
      if (idx % 2 === 0) box(`${name}_stair_landing_${idx}`, mats.concrete, [offset, yMid + 0.9, zMid + sign * 2.1], [2.8, 0.12, 1.05], [-0.04 * sign, 0, 0]);
    } else {
      const xMid = depthStart + sign * ((rows - 1) * 0.58) / 2;
      box(`${name}_full_height_stair_run_${idx}`, mats.concrete, [xMid, yMid - 0.04, offset], [run, 0.10, 0.92], [0, 0.11 * sign, 0]);
      box(`${name}_stair_left_handrail_${idx}`, mats.metal, [xMid, yMid + 0.42, offset - 0.55], [run + 0.4, 0.08, 0.07], [0, 0.11 * sign, 0]);
      box(`${name}_stair_right_handrail_${idx}`, mats.metal, [xMid, yMid + 0.42, offset + 0.55], [run + 0.4, 0.08, 0.07], [0, 0.11 * sign, 0]);
      if (idx % 2 === 0) box(`${name}_stair_landing_${idx}`, mats.concrete, [xMid + sign * 2.1, yMid + 0.9, offset], [1.05, 0.12, 2.8], [0, 0.04 * sign, 0]);
    }
  });

  if (longSide) {
    box(`${name}_front_wall`, mats.concrete, [0, 1.55, zFixed - sign * 1.2], [span + 7, 1.0, 0.5]);
    box(`${name}_upper_concourse_band`, mats.concrete, [0, 7.2, zFixed + sign * 6.5], [span + 10, 0.55, 0.72], [-0.03 * sign, 0, 0]);
    [-0.34, 0, 0.34].forEach((slot, idx) => {
      box(`${name}_vomitory_shadow_${idx}`, mats.black, [slot * span, 3.7, zFixed + sign * 2.45], [4.8, 2.3, 0.18]);
      box(`${name}_vomitory_lintel_${idx}`, mats.concrete, [slot * span, 5.05, zFixed + sign * 2.34], [5.4, 0.32, 0.32]);
    });
  } else {
    box(`${name}_front_wall`, mats.concrete, [xFixed - sign * 1.2, 1.55, 0], [0.5, 1.0, span + 7]);
    box(`${name}_upper_concourse_band`, mats.concrete, [xFixed + sign * 6.5, 7.1, 0], [0.72, 0.55, span + 10], [0, 0.03 * sign, 0]);
    [-0.28, 0.28].forEach((slot, idx) => {
      box(`${name}_vomitory_shadow_${idx}`, mats.black, [xFixed + sign * 2.45, 3.65, slot * span], [0.18, 2.0, 4.4]);
      box(`${name}_vomitory_lintel_${idx}`, mats.concrete, [xFixed + sign * 2.34, 4.9, slot * span], [0.32, 0.32, 5.0]);
    });
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
  box('north_green_roof_fascia', mats.greenDark, [0, 14.6, pitchH / 2 + 27.0], [pitchW + 70, 1.1, 0.34], [-0.03, 0, 0]);
  box('south_green_roof_fascia', mats.greenDark, [0, 14.45, -(pitchH / 2 + 27.0)], [pitchW + 62, 1.0, 0.34], [0.03, 0, 0]);
  box('east_green_roof_fascia', mats.greenDark, [pitchW / 2 + 27.0, 14.35, 0], [0.34, 1.0, pitchH + 58], [0, 0.03, 0]);
  box('west_green_roof_fascia', mats.greenDark, [-(pitchW / 2 + 27.0), 14.35, 0], [0.34, 1.0, pitchH + 58], [0, -0.03, 0]);
  box('north_roof_shadow_on_seats', mats.roofShadow, [0, 9.8, pitchH / 2 + 21.5], [pitchW + 54, 0.06, 8.8], [-0.04, 0, 0]);
  box('south_roof_shadow_on_seats', mats.roofShadow, [0, 9.4, -(pitchH / 2 + 20.8)], [pitchW + 48, 0.06, 7.6], [0.04, 0, 0]);
  for (let i = -18; i <= 18; i += 1) {
    const x = i * ((pitchW + 66) / 36);
    box(`north_roof_corrugation_${i}`, mats.metal, [x, y + 0.22, pitchH / 2 + 34.0], [0.075, 0.12, 12.6], [-0.04, 0, 0]);
    if (i >= -16 && i <= 16) box(`south_roof_corrugation_${i}`, mats.metal, [x, y + 0.18, -(pitchH / 2 + 34.0)], [0.07, 0.11, 10.5], [0.04, 0, 0]);
  }
  for (let i = -12; i <= 12; i += 1) {
    const z = i * ((pitchH + 54) / 24);
    box(`east_roof_corrugation_${i}`, mats.metal, [pitchW / 2 + 34.0, y + 0.18, z], [10.5, 0.11, 0.07], [0, 0.04, 0]);
    box(`west_roof_corrugation_${i}`, mats.metal, [-(pitchW / 2 + 34.0), y + 0.18, z], [10.5, 0.11, 0.07], [0, -0.04, 0]);
  }
  [-1, 1].forEach((sign) => {
    for (let i = -12; i <= 12; i += 1) {
      const x = i * ((pitchW + 54) / 24);
      box(`long_roof_front_truss_${sign}_${i}`, mats.metal, [x, 14.55, sign * (pitchH / 2 + 27.2)], [0.16, 1.2, 8.6], [-0.62 * sign, 0, i % 2 ? 0.36 : -0.36]);
      box(`long_roof_back_column_${sign}_${i}`, mats.darkMetal, [x, 8.2, sign * (pitchH / 2 + 39.2)], [0.28, 12.2, 0.28]);
      box(`long_roof_rear_truss_${sign}_${i}`, mats.metal, [x, 14.7, sign * (pitchH / 2 + 38.7)], [0.18, 1.0, 5.2], [0.52 * sign, 0, i % 2 ? -0.28 : 0.28]);
      if (i % 2 === 0) box(`long_roof_light_${sign}_${i}`, mats.light, [x, 13.52, sign * (pitchH / 2 + 22.8)], [3.2, 0.14, 0.28]);
      if (i % 4 === 0) {
        box(`long_roof_light_cluster_left_${sign}_${i}`, mats.light, [x - 0.72, 13.28, sign * (pitchH / 2 + 23.05)], [0.55, 0.24, 0.26]);
        box(`long_roof_light_cluster_right_${sign}_${i}`, mats.light, [x + 0.72, 13.28, sign * (pitchH / 2 + 23.05)], [0.55, 0.24, 0.26]);
        const roofSpot = new THREE.SpotLight(0xfff2cd, 0.34, 96, Math.PI / 6, 0.48, 2.0);
        roofSpot.name = `roof_integrated_spot_${sign}_${i}`;
        roofSpot.position.set(x, 13.1, sign * (pitchH / 2 + 22.3));
        roofSpot.target.position.set(x * 0.25, 0.1, sign * 7.0);
        scene.add(roofSpot);
        scene.add(roofSpot.target);
      }
    }
  });
  for (let i = -6; i <= 6; i += 1) {
    const x = i * ((pitchW + 42) / 12);
    box(`north_cantilever_rear_mast_${i}`, mats.darkMetal, [x, 18.7, pitchH / 2 + 39.8], [0.34, 6.2, 0.34], [-0.07, 0, 0]);
    box(`north_cantilever_tension_rod_a_${i}`, mats.metal, [x - 0.5, 17.15, pitchH / 2 + 34.2], [0.10, 0.10, 11.2], [-0.58, 0, 0.06]);
    box(`north_cantilever_tension_rod_b_${i}`, mats.metal, [x + 0.5, 17.15, pitchH / 2 + 34.2], [0.10, 0.10, 11.2], [-0.58, 0, -0.06]);
    box(`north_roof_black_service_box_${i}`, mats.black, [x, 16.4, pitchH / 2 + 28.9], [2.1, 0.42, 0.54]);
  }
  [-1, 1].forEach((sign) => {
    for (let i = -7; i <= 7; i += 1) {
      const z = i * ((pitchH + 44) / 14);
      box(`short_roof_front_truss_${sign}_${i}`, mats.metal, [sign * (pitchW / 2 + 27.1), 14.35, z], [7.8, 1.0, 0.16], [0, -0.58 * sign, i % 2 ? 0.24 : -0.24]);
      box(`short_roof_back_column_${sign}_${i}`, mats.darkMetal, [sign * (pitchW / 2 + 39.0), 8.1, z], [0.26, 11.8, 0.26]);
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
  writeBlockText({ text: 'CAMPO MUNICIPAL', name: 'north_board_municipal', origin: [-39, 1.12, pitchH / 2 + 2.96], cell: 0.22, plane: 'xy' });
  writeBlockText({ text: 'PARTNER', name: 'north_board_partner_left', origin: [-7, 1.12, pitchH / 2 + 2.96], cell: 0.22, plane: 'xy' });
  writeBlockText({ text: '2J FOOTBALL INTELLIGENCE', name: 'north_board_2j', origin: [18, 1.12, pitchH / 2 + 2.96], cell: 0.16, plane: 'xy' });
  writeBlockText({ text: 'PARTNER', name: 'south_board_partner', origin: [-36, 1.12, -(pitchH / 2 + 2.96)], cell: 0.22, plane: 'xy' });
  writeBlockText({ text: 'BENAGALBON CD', name: 'south_board_name', origin: [2, 1.12, -(pitchH / 2 + 2.96)], cell: 0.19, plane: 'xy' });
  writeBlockText({ text: 'CDB', name: 'east_board_cdb', origin: [pitchW / 2 + 2.96, 1.12, -18], cell: 0.2, plane: 'zy' });
  writeBlockText({ text: 'PARTNER', name: 'east_board_partner', origin: [pitchW / 2 + 2.96, 1.12, 6], cell: 0.18, plane: 'zy' });
  writeBlockText({ text: 'CDB', name: 'west_board_cdb', origin: [-(pitchW / 2 + 2.96), 1.12, 14], cell: 0.2, plane: 'zy' });
  writeBlockText({ text: 'PARTNER', name: 'west_board_partner', origin: [-(pitchW / 2 + 2.96), 1.12, -12], cell: 0.18, plane: 'zy' });
};
addBoards();

const addPerimeterRails = () => {
  const rail = (name, x, z, sx, sz) => {
    box(`${name}_top_rail`, mats.metal, [x, 1.72, z], [sx, 0.08, sz]);
    box(`${name}_mid_rail`, mats.metal, [x, 1.18, z], [sx, 0.06, sz]);
  };
  rail('north_front_fence', 0, pitchH / 2 + 4.28, pitchW + 12, 0.08);
  rail('south_front_fence', 0, -(pitchH / 2 + 4.28), pitchW + 12, 0.08);
  rail('east_front_fence', pitchW / 2 + 4.28, 0, 0.08, pitchH + 12);
  rail('west_front_fence', -(pitchW / 2 + 4.28), 0, 0.08, pitchH + 12);
  for (let i = -28; i <= 28; i += 2) {
    box(`north_front_fence_post_${i}`, mats.metal, [i * 2.0, 1.05, pitchH / 2 + 4.28], [0.07, 1.28, 0.07]);
    box(`south_front_fence_post_${i}`, mats.metal, [i * 2.0, 1.05, -(pitchH / 2 + 4.28)], [0.07, 1.28, 0.07]);
  }
  for (let i = -18; i <= 18; i += 2) {
    box(`east_front_fence_post_${i}`, mats.metal, [pitchW / 2 + 4.28, 1.05, i * 2.0], [0.07, 1.28, 0.07]);
    box(`west_front_fence_post_${i}`, mats.metal, [-(pitchW / 2 + 4.28), 1.05, i * 2.0], [0.07, 1.28, 0.07]);
  }
};
addPerimeterRails();

const addGoalBackMesh = () => {
  [-1, 1].forEach((sign) => {
    const z = sign * (pitchH / 2 + 5.15);
    box(`goal_back_mesh_top_${sign}`, mats.mesh, [0, 3.0, z], [21.0, 0.06, 0.06]);
    box(`goal_back_mesh_bottom_${sign}`, mats.mesh, [0, 0.55, z], [21.0, 0.05, 0.05]);
    for (let i = -10; i <= 10; i += 1) {
      box(`goal_back_mesh_vertical_${sign}_${i}`, mats.mesh, [i, 1.78, z], [0.035, 2.45, 0.035]);
    }
    for (let i = 0; i <= 5; i += 1) {
      box(`goal_back_mesh_horizontal_${sign}_${i}`, mats.mesh, [0, 0.72 + i * 0.42, z], [20.8, 0.025, 0.025]);
    }
    box(`goal_back_service_gate_${sign}`, mats.darkMetal, [-12.5, 1.35, z], [1.35, 2.05, 0.06]);
    box(`goal_back_service_gate_handle_${sign}`, mats.light, [-12.0, 1.35, z - sign * 0.04], [0.08, 0.22, 0.04]);
  });
};
addGoalBackMesh();

const addCornerDetails = () => {
  [
    [-pitchW / 2, -pitchH / 2, 'sw'],
    [pitchW / 2, -pitchH / 2, 'se'],
    [-pitchW / 2, pitchH / 2, 'nw'],
    [pitchW / 2, pitchH / 2, 'ne'],
  ].forEach(([x, z, name]) => {
    cyl(`corner_flag_pole_${name}`, mats.white, [x, 0.85, z], 0.035, 1.7, [0, 0, 0], 16);
    box(`corner_flag_green_${name}`, mats.green, [x + (x > 0 ? -0.28 : 0.28), 1.52, z], [0.52, 0.32, 0.035]);
    box(`corner_apron_drain_${name}`, mats.darkConcrete, [x + (x > 0 ? 1.35 : -1.35), 0.08, z + (z > 0 ? 1.35 : -1.35)], [1.55, 0.035, 0.08]);
  });
};
addCornerDetails();

const addDugout = (x, label) => {
  const z = -(pitchH / 2 + 6.0);
  box(`dugout_${label}_base`, mats.darkMetal, [x, 0.25, z], [12.8, 0.28, 2.0]);
  box(`dugout_${label}_rear_green_panel`, mats.greenDark, [x, 0.95, z + 0.88], [12.6, 1.15, 0.10]);
  box(`dugout_${label}_front_metal_lip`, mats.metal, [x, 1.98, z - 1.34], [12.7, 0.08, 0.12]);
  cyl(`dugout_${label}_cdb_roundel_left`, mats.white, [x - 5.9, 1.18, z - 1.40], 0.42, 0.05, [Math.PI / 2, 0, 0], 48);
  cyl(`dugout_${label}_cdb_roundel_green_left`, mats.green, [x - 5.9, 1.18, z - 1.44], 0.30, 0.05, [Math.PI / 2, 0, 0], 48);
  cyl(`dugout_${label}_cdb_roundel_right`, mats.white, [x + 5.9, 1.18, z - 1.40], 0.42, 0.05, [Math.PI / 2, 0, 0], 48);
  cyl(`dugout_${label}_cdb_roundel_green_right`, mats.green, [x + 5.9, 1.18, z - 1.44], 0.30, 0.05, [Math.PI / 2, 0, 0], 48);
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
cyl('main_round_cdb_crest_green_ring', mats.green, [0, 8.61, pitchH / 2 + 10.88], 3.05, 0.18, [Math.PI / 2, 0, 0], 96);
cyl('main_round_cdb_crest_white_core', mats.white, [0, 8.62, pitchH / 2 + 10.75], 2.22, 0.20, [Math.PI / 2, 0, 0], 96);
writeBlockText({ text: 'CDB', name: 'main_crest_cdb_letters', origin: [-1.35, 8.92, pitchH / 2 + 10.58], cell: 0.18, plane: 'xy' });
box('main_stand_rear_green_facade', mats.greenDark, [0, 6.2, pitchH / 2 + 41.0], [pitchW + 66, 6.4, 0.38]);
box('main_stand_rear_concrete_plinth', mats.concrete, [0, 2.1, pitchH / 2 + 41.2], [pitchW + 72, 2.2, 0.52]);
for (let i = -10; i <= 10; i += 1) {
  const x = i * ((pitchW + 54) / 20);
  box(`rear_facade_vertical_frame_${i}`, mats.metal, [x, 7.8, pitchH / 2 + 40.72], [0.16, 7.8, 0.22]);
}
for (let i = -9; i <= 9; i += 1) {
  const x = i * ((pitchW + 47) / 18);
  box(`rear_facade_glass_panel_${i}`, mats.glass, [x, 5.45, pitchH / 2 + 40.45], [3.8, 1.45, 0.08]);
  box(`rear_facade_lower_shadow_${i}`, mats.black, [x, 4.43, pitchH / 2 + 40.43], [3.8, 0.18, 0.06]);
}
box('rear_facade_roof_edge_shadow', mats.roofShadow, [0, 9.45, pitchH / 2 + 40.38], [pitchW + 64, 0.18, 0.08]);
writeBlockText({ text: 'BENAGALBON CD', name: 'rear_facade_name', origin: [-19.8, 7.52, pitchH / 2 + 40.48], cell: 0.24, plane: 'xy' });
box('corner_scoreboard_frame', mats.black, [pitchW / 2 + 8.5, 6.4, pitchH / 2 + 8.6], [8.2, 4.6, 0.30], [0, -Math.PI / 4, 0]);
box('corner_scoreboard_face', mats.led, [pitchW / 2 + 8.25, 6.4, pitchH / 2 + 8.35], [7.5, 3.9, 0.08], [0, -Math.PI / 4, 0]);
writeBlockText({ text: 'CDB', name: 'scoreboard_cdb', origin: [pitchW / 2 + 6.58, 6.85, pitchH / 2 + 8.2], cell: 0.14, plane: 'xy', rotation: [0, -Math.PI / 4, 0] });

const addTechnicalAreas = () => {
  [-20, 0, 20].forEach((x, idx) => {
    box(`technical_area_dashed_front_${idx}`, mats.white, [x, 0.075, -(pitchH / 2 + 4.72)], [12.0, 0.04, 0.08]);
    box(`technical_area_dashed_left_${idx}`, mats.white, [x - 6.0, 0.075, -(pitchH / 2 + 5.9)], [0.08, 0.04, 2.3]);
    box(`technical_area_dashed_right_${idx}`, mats.white, [x + 6.0, 0.075, -(pitchH / 2 + 5.9)], [0.08, 0.04, 2.3]);
  });
};
addTechnicalAreas();

const addReferenceBackdrop = () => {
  box('reference_soft_sky_backdrop', mats.skyPanel, [0, 12.8, 74.6], [150.0, 21.0, 0.08]);
  tri('reference_mountain_left', mats.mountain, [[-76, 3.6], [-32, 14.4], [8, 3.6]], 74.4);
  tri('reference_mountain_center', mats.mountain, [[-10, 3.4], [30, 13.2], [68, 3.4]], 74.35);
  tri('reference_mountain_right', mats.mountain, [[38, 3.1], [72, 10.4], [94, 3.1]], 74.3);
  for (let i = -11; i <= 11; i += 1) {
    const h = 1.3 + ((i * i + 5) % 7) * 0.42;
    const x = i * 5.2;
    box(`reference_city_block_${i}`, mats.city, [x, 1.2 + h / 2, 73.2], [3.7, h, 0.38]);
    if (i % 3 === 0) box(`reference_city_green_roof_${i}`, mats.greenDark, [x, 1.2 + h + 0.13, 72.96], [3.8, 0.20, 0.32]);
  }
  box('reference_outer_service_road', mats.concreteLine, [0, 0.10, 67.8], [132.0, 0.04, 1.6]);
};
addReferenceBackdrop();

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
