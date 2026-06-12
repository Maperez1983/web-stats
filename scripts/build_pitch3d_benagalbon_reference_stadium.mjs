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
  darkConcrete: new THREE.MeshStandardMaterial({ name: 'REF_DARK_CONCRETE', color: 0x68716d, roughness: 0.88, metalness: 0.02 }),
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
  darkMetal: new THREE.MeshStandardMaterial({ name: 'REF_DARK_STEEL', color: 0x4c5653, roughness: 0.48, metalness: 0.18 }),
  roof: new THREE.MeshStandardMaterial({ name: 'REF_LIGHT_ROOF_SOFFIT', color: 0xe6ebe7, roughness: 0.44, metalness: 0.18 }),
  roofShadow: new THREE.MeshStandardMaterial({ name: 'REF_ROOF_CAST_SHADOW', color: 0x111827, roughness: 0.96, metalness: 0.0, transparent: true, opacity: 0.22 }),
  concreteStain: new THREE.MeshStandardMaterial({ name: 'REF_CONCRETE_WEATHERING_VARIATION', color: 0x7f8984, roughness: 0.96, metalness: 0.0 }),
  seatShadow: new THREE.MeshStandardMaterial({ name: 'REF_SEAT_ROW_CONTACT_SHADOW', color: 0x01251d, roughness: 0.88, metalness: 0.0 }),
  lightPool: new THREE.MeshBasicMaterial({ name: 'REF_WARM_FLOODLIGHT_POOL_ON_TURF', color: 0xffe6a4, transparent: true, opacity: 0.16, toneMapped: false }),
  glass: new THREE.MeshPhysicalMaterial({ name: 'REF_CLEAR_DUGOUT_GLASS', color: 0xc7efff, roughness: 0.08, metalness: 0.02, transparent: true, opacity: 0.34, transmission: 0.18, side: THREE.DoubleSide }),
  led: new THREE.MeshStandardMaterial({ name: 'REF_GREEN_LED_BOARD_FACE', color: 0x0b5f45, roughness: 0.24, metalness: 0.04, emissive: 0x063b2f, emissiveIntensity: 0.18 }),
  light: new THREE.MeshBasicMaterial({ name: 'REF_WARM_FLOODLIGHT_LINE', color: 0xfff3ca, toneMapped: false }),
  black: new THREE.MeshStandardMaterial({ name: 'REF_DEEP_RECESSES', color: 0x39413d, roughness: 0.94, metalness: 0.01 }),
  mesh: new THREE.MeshStandardMaterial({ name: 'REF_FINE_STADIUM_MESH', color: 0xaeb8b5, roughness: 0.48, metalness: 0.32 }),
  orange: new THREE.MeshStandardMaterial({ name: 'REF_TOUCHLINE_EQUIPMENT_ORANGE', color: 0xf97316, roughness: 0.72, metalness: 0.01 }),
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
for (let i = 0; i < 30; i += 1) {
  const x = -pitchW / 2 + 2.0 + i * 3.55;
  const z = -pitchH / 2 + 2.2 + ((i * 23) % 63);
  box(`ref_grass_close_cut_dark_blade_${i}`, mats.grassDark, [x, 0.044, z], [1.75, 0.01, 0.032], [0, -0.22 + (i % 7) * 0.06, 0]);
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

const addStand = ({ name, side, cols, rows, length, depthStart, zFixed, xFixed }) => {
  const longSide = side === 'north' || side === 'south';
  const sign = side === 'north' || side === 'east' ? 1 : -1;
  const span = length;
  const aisleCols = (() => {
    if (side === 'north') return new Set([8, Math.floor(cols * 0.24), Math.floor(cols * 0.5), Math.floor(cols * 0.76), cols - 9]);
    return new Set();
  })();

  for (let row = 0; row < rows; row += 1) {
    const y = 2.15 + row * 0.31;
    const depth = depthStart + sign * row * 0.58;
    if (longSide) {
      box(`${name}_continuous_riser_${row}`, mats.darkConcrete, [0, y - 0.18, depth + sign * 0.18], [span + 3.2, 0.16, 0.22], [-0.03 * sign, 0, 0]);
    } else {
      box(`${name}_continuous_riser_${row}`, mats.darkConcrete, [depth + sign * 0.18, y - 0.18, 0], [0.22, 0.16, span + 3.2], [0, 0.03 * sign, 0]);
    }
    const sortedAisles = [...aisleCols].sort((a, b) => a - b);
    const segments = [];
    let segmentStart = 0;
    sortedAisles.forEach((aisle) => {
      if (aisle > segmentStart) segments.push([segmentStart, aisle - 1]);
      segmentStart = aisle + 1;
    });
    if (segmentStart < cols) segments.push([segmentStart, cols - 1]);
    segments.forEach(([startCol, endCol], segIdx) => {
      const startOffset = (startCol / (cols - 1) - 0.5) * span;
      const endOffset = (endCol / (cols - 1) - 0.5) * span;
      const offset = (startOffset + endOffset) / 2;
      const segW = Math.max(0.45, Math.abs(endOffset - startOffset) + (span / Math.max(1, cols - 1)) * 0.56);
      let material = row % 6 === 0 && side === 'north' ? mats.greenDark : mats.green;
      if (longSide) {
        box(`${name}_clean_seat_row_${row}_${segIdx}`, material, [offset, y, depth], [segW, 0.16, 0.34], [-0.08 * sign, 0, 0]);
        if (side === 'north') {
          box(`${name}_clean_back_row_${row}_${segIdx}`, material, [offset, y + 0.23, depth + sign * 0.22], [segW, 0.30, 0.07], [-0.20 * sign, 0, 0]);
        }
      } else {
        box(`${name}_clean_seat_row_${row}_${segIdx}`, material, [depth, y, offset], [0.34, 0.16, segW], [0, 0.08 * sign, 0]);
      }
    });
  }

  if (side === 'north') {
    [...aisleCols].forEach((col, idx) => {
      const t = col / (cols - 1) - 0.5;
      const offset = t * span;
      const yMid = 2.15 + ((rows - 1) * 0.31) / 2;
      const run = rows * 0.58 + 0.55;
      const zMid = depthStart + sign * ((rows - 1) * 0.58) / 2;
      box(`${name}_full_height_stair_run_${idx}`, mats.concrete, [offset, yMid - 0.035, zMid], [1.08, 0.11, run], [-0.11 * sign, 0, 0]);
    });
  }

  if (longSide) {
    box(`${name}_front_wall`, mats.concrete, [0, 1.55, zFixed - sign * 1.2], [span + 7, 1.0, 0.5]);
    if (side === 'north') {
      box(`${name}_upper_concourse_band`, mats.concrete, [0, 7.2, zFixed + sign * 6.5], [span + 10, 0.55, 0.72], [-0.03 * sign, 0, 0]);
      box(`${name}_glass_balustrade_top`, mats.glass, [0, 7.82, zFixed + sign * 6.04], [span + 6.5, 0.72, 0.08], [-0.03 * sign, 0, 0]);
      box(`${name}_front_safety_rail`, mats.metal, [0, 2.28, zFixed - sign * 1.52], [span + 6.0, 0.08, 0.08]);
    }
  } else {
    box(`${name}_front_wall`, mats.concrete, [xFixed - sign * 1.2, 1.55, 0], [0.5, 1.0, span + 7]);
  }
};

addStand({ name: 'north_main_stand', side: 'north', cols: 108, rows: 18, length: pitchW + 66, depthStart: pitchH / 2 + 9.7, zFixed: pitchH / 2 + 9.7 });
addStand({ name: 'south_low_stand', side: 'south', cols: 24, rows: 3, length: pitchW + 8, depthStart: -(pitchH / 2 + 8.2), zFixed: -(pitchH / 2 + 8.2) });
addStand({ name: 'east_low_stand', side: 'east', cols: 18, rows: 3, length: pitchH - 8, depthStart: pitchW / 2 + 8.5, xFixed: pitchW / 2 + 8.5 });
addStand({ name: 'west_low_stand', side: 'west', cols: 16, rows: 3, length: pitchH - 18, depthStart: -(pitchW / 2 + 8.2), xFixed: -(pitchW / 2 + 8.2) });

const addMainStandSeatLettering = () => {
  const bands = [
    [-32, 10, 18, 'left'],
    [0, 11, 22, 'center'],
    [32, 10, 18, 'right'],
  ];
  bands.forEach(([x, row, w, id]) => {
    const y = 2.15 + row * 0.31 + 0.15;
    const z = pitchH / 2 + 9.7 + row * 0.58 - 0.04;
    box(`north_main_stand_clean_white_seat_band_${id}`, mats.white, [x, y, z], [w, 0.055, 0.40], [-0.08, 0, 0]);
  });
};
addMainStandSeatLettering();

const addRoof = () => {
  const y = 15.8;
  box('north_thin_roof_skin', mats.roof, [0, y + 0.5, pitchH / 2 + 35.6], [pitchW + 82, 0.34, 15.2], [-0.045, 0, 0]);
  box('north_green_roof_fascia', mats.greenDark, [0, 15.0, pitchH / 2 + 27.4], [pitchW + 84, 1.12, 0.34], [-0.03, 0, 0]);
  box('north_roof_front_gutter', mats.darkMetal, [0, 14.08, pitchH / 2 + 26.65], [pitchW + 72, 0.18, 0.22], [-0.03, 0, 0]);
  box('north_press_box_glass', mats.glass, [0, 13.7, pitchH / 2 + 39.72], [17.5, 2.4, 0.12]);
  box('north_press_box_roof', mats.darkMetal, [0, 15.05, pitchH / 2 + 39.58], [18.4, 0.28, 1.3]);
  box('north_press_box_floor', mats.concrete, [0, 12.42, pitchH / 2 + 39.75], [18.6, 0.24, 1.45]);
  for (let i = -14; i <= 14; i += 2) {
    const x = i * ((pitchW + 66) / 36);
    box(`north_roof_corrugation_${i}`, mats.metal, [x, y + 0.22, pitchH / 2 + 34.0], [0.075, 0.12, 12.6], [-0.04, 0, 0]);
  }
  [1].forEach((sign) => {
    for (let i = -10; i <= 10; i += 2) {
      const x = i * ((pitchW + 54) / 24);
      box(`long_roof_front_truss_${sign}_${i}`, mats.metal, [x, 14.55, sign * (pitchH / 2 + 27.2)], [0.14, 0.9, 7.6], [-0.52 * sign, 0, 0.18]);
      box(`long_roof_back_column_${sign}_${i}`, mats.darkMetal, [x, 8.2, sign * (pitchH / 2 + 39.2)], [0.28, 12.2, 0.28]);
      if (i % 4 === 0) box(`long_roof_light_${sign}_${i}`, mats.light, [x, 13.52, sign * (pitchH / 2 + 22.8)], [3.2, 0.14, 0.28]);
      if (i % 4 === 0) {
        const roofSpot = new THREE.SpotLight(0xfff2cd, 0.34, 96, Math.PI / 6, 0.48, 2.0);
        roofSpot.name = `roof_integrated_spot_${sign}_${i}`;
        roofSpot.position.set(x, 13.1, sign * (pitchH / 2 + 22.3));
        roofSpot.target.position.set(x * 0.25, 0.1, sign * 7.0);
        scene.add(roofSpot);
        scene.add(roofSpot.target);
      }
    }
  });
  for (let i = -5; i <= 5; i += 2) {
    const x = i * ((pitchW + 42) / 12);
    box(`north_cantilever_rear_mast_${i}`, mats.darkMetal, [x, 18.7, pitchH / 2 + 39.8], [0.34, 6.2, 0.34], [-0.07, 0, 0]);
    box(`north_cantilever_tension_rod_${i}`, mats.metal, [x, 17.0, pitchH / 2 + 34.4], [0.09, 0.09, 10.6], [-0.54, 0, 0]);
  }
};
addRoof();

const addFloodlightPools = () => {
  [-36, -18, 0, 18, 36].forEach((x, idx) => {
    box(`north_roof_warm_light_pool_${idx}`, mats.lightPool, [x, 0.082, pitchH / 2 - 10.5], [13.5, 0.012, 5.1], [0, 0.02 * (idx - 2), 0]);
    box(`south_roof_warm_light_pool_${idx}`, mats.lightPool, [x, 0.083, -(pitchH / 2 - 10.5)], [12.2, 0.012, 4.6], [0, -0.02 * (idx - 2), 0]);
  });
  [-28, 0, 28].forEach((x, idx) => {
    box(`center_pitch_soft_light_overlap_${idx}`, mats.lightPool, [x, 0.084, 0], [16.0, 0.012, 6.2], [0, 0.04 * (idx - 1), 0]);
  });
};
addFloodlightPools();

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
// La referencia tiene una primera línea limpia con LED y separadores bajos. Evitamos una segunda
// valla completa delante de las gradas, porque en cámara general se leía como vallado duplicado.

const addExternalAccessDetails = () => {
  [-1, 1].forEach((side) => {
    const x = side * (pitchW / 2 + 21.5);
    box(`side_outer_stair_spine_${side}`, mats.concrete, [x, 2.65, pitchH / 2 + 18.5], [3.1, 0.28, 13.0], [0, -0.08 * side, 0]);
    for (let i = 0; i < 8; i += 1) {
      box(`side_outer_stair_step_${side}_${i}`, mats.concreteLine, [x, 1.15 + i * 0.33, pitchH / 2 + 13.0 + i * 1.48], [3.4, 0.08, 0.48]);
    }
    box(`side_outer_stair_handrail_a_${side}`, mats.metal, [x - side * 1.72, 3.6, pitchH / 2 + 19.0], [0.08, 0.08, 13.6], [0, -0.08 * side, 0]);
    box(`side_outer_stair_handrail_b_${side}`, mats.metal, [x + side * 1.72, 3.6, pitchH / 2 + 19.0], [0.08, 0.08, 13.6], [0, -0.08 * side, 0]);
    box(`side_service_door_${side}`, mats.black, [side * (pitchW / 2 + 9.8), 2.42, pitchH / 2 + 10.05], [2.0, 2.2, 0.16]);
  });
};
// Las escaleras exteriores laterales añadían siluetas cruzadas sobre la grada. Las dejamos fuera
// del modelo dedicado para priorizar una grada limpia y reconocible.

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
// La malla alta detrás de porterías competía con los fondos y parecía otro vallado superpuesto.

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
  const z = -(pitchH / 2 + 5.15);
  box(`dugout_${label}_base`, mats.concrete, [x, 0.24, z], [12.4, 0.24, 1.28]);
  box(`dugout_${label}_rear_green_panel`, mats.greenDark, [x, 0.92, z + 0.56], [12.2, 1.04, 0.10]);
  box(`dugout_${label}_front_metal_lip`, mats.metal, [x, 1.72, z - 0.86], [12.1, 0.06, 0.08]);
  for (let i = 0; i < 6; i += 1) {
    const t = i / 5;
    box(`dugout_${label}_curved_glass_${i}`, mats.glass, [x, 1.02 + Math.sin(t * Math.PI * 0.58) * 0.82, z - 0.56 + t * 0.96], [11.8, 0.055, 0.32], [-0.38 + t * 0.22, 0, 0]);
  }
  for (let i = 0; i < 8; i += 1) {
    const sx = x - 4.85 + i * 1.38;
    box(`dugout_${label}_chair_${i}`, mats.green, [sx, 0.65, z + 0.05], [0.72, 0.16, 0.46]);
    box(`dugout_${label}_back_${i}`, mats.green, [sx, 0.96, z + 0.31], [0.72, 0.58, 0.09], [-0.16, 0, 0]);
  }
};
addDugout(-22, 'home');
addDugout(22, 'away');

box('main_stand_rear_green_facade', mats.greenDark, [0, 6.2, pitchH / 2 + 41.0], [pitchW + 66, 6.4, 0.38]);
box('main_stand_rear_concrete_plinth', mats.concrete, [0, 2.1, pitchH / 2 + 41.2], [pitchW + 72, 2.2, 0.52]);
for (let i = -6; i <= 6; i += 1) {
  const x = i * ((pitchW + 54) / 12);
  box(`rear_facade_vertical_frame_${i}`, mats.metal, [x, 7.8, pitchH / 2 + 40.72], [0.14, 7.2, 0.20]);
}
for (let i = -5; i <= 5; i += 1) {
  const x = i * ((pitchW + 45) / 10);
  box(`rear_facade_glass_panel_${i}`, mats.glass, [x, 5.45, pitchH / 2 + 40.45], [6.2, 1.35, 0.08]);
}
box('rear_facade_roof_edge_shadow', mats.roofShadow, [0, 9.45, pitchH / 2 + 40.38], [pitchW + 64, 0.18, 0.08]);
box('main_scoreboard_face', mats.led, [38.0, 5.9, pitchH / 2 + 8.02], [6.4, 2.4, 0.08]);

const addTechnicalAreas = () => {
  [-20, 0, 20].forEach((x, idx) => {
    box(`technical_area_dashed_front_${idx}`, mats.white, [x, 0.076, -(pitchH / 2 + 2.65)], [11.4, 0.035, 0.07]);
    box(`technical_area_dashed_left_${idx}`, mats.white, [x - 5.7, 0.076, -(pitchH / 2 + 3.48)], [0.07, 0.035, 1.55]);
    box(`technical_area_dashed_right_${idx}`, mats.white, [x + 5.7, 0.076, -(pitchH / 2 + 3.48)], [0.07, 0.035, 1.55]);
  });
};
addTechnicalAreas();

const addTouchlineEquipment = () => {
};
addTouchlineEquipment();

const addReferenceBackdrop = () => {
  box('reference_soft_sky_backdrop', mats.skyPanel, [0, 12.8, 74.6], [150.0, 21.0, 0.08]);
  tri('reference_mountain_left', mats.mountain, [[-76, 3.6], [-32, 14.4], [8, 3.6]], 74.4);
  tri('reference_mountain_center', mats.mountain, [[-10, 3.4], [30, 13.2], [68, 3.4]], 74.35);
  tri('reference_mountain_right', mats.mountain, [[38, 3.1], [72, 10.4], [94, 3.1]], 74.3);
  for (let i = -9; i <= 9; i += 1) {
    const h = 0.7 + ((i * i + 3) % 5) * 0.22;
    const x = i * 6.2;
    box(`reference_low_city_hint_${i}`, mats.city, [x, 0.72 + h / 2, 73.2], [4.4, h, 0.26]);
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
