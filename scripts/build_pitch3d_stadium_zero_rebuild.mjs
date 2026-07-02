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
const out = path.join(root, 'football/static/football/models/pitch3d/stadium_zero_rebuild.glb');

const scene = new THREE.Scene();
scene.name = 'pitch_3d_stadium_zero_rebuild';
scene.background = new THREE.Color(0xd7e9fb);

const mats = {
  grassLight: new THREE.MeshStandardMaterial({ name: 'ZR_GRASS_LIGHT', color: 0x86cd61, roughness: 0.95 }),
  grassDark: new THREE.MeshStandardMaterial({ name: 'ZR_GRASS_DARK', color: 0x5ca13d, roughness: 0.97 }),
  grassFiber: new THREE.MeshStandardMaterial({ name: 'ZR_GRASS_FIBER', color: 0xbfe49e, roughness: 0.93 }),
  line: new THREE.MeshStandardMaterial({ name: 'ZR_LINE', color: 0xf5f7f1, roughness: 0.8 }),
  apron: new THREE.MeshStandardMaterial({ name: 'ZR_APRON', color: 0x324047, roughness: 0.96 }),
  board: new THREE.MeshStandardMaterial({ name: 'ZR_BOARD', color: 0x143943, roughness: 0.24, emissive: 0x1c6870, emissiveIntensity: 0.25 }),
  concrete: new THREE.MeshStandardMaterial({ name: 'ZR_CONCRETE', color: 0xe7edf1, roughness: 0.94 }),
  concreteDark: new THREE.MeshStandardMaterial({ name: 'ZR_CONCRETE_DARK', color: 0x264a88, roughness: 0.82 }),
  aisle: new THREE.MeshStandardMaterial({ name: 'ZR_AISLE', color: 0xcfd7de, roughness: 0.9 }),
  seatBlue: new THREE.MeshStandardMaterial({ name: 'ZR_SEAT_BLUE', color: 0x2d71f0, roughness: 0.54 }),
  seatBlueDark: new THREE.MeshStandardMaterial({ name: 'ZR_SEAT_BLUE_DARK', color: 0x153f9c, roughness: 0.58 }),
  seatWhite: new THREE.MeshStandardMaterial({ name: 'ZR_SEAT_WHITE', color: 0xf3f6f9, roughness: 0.62 }),
  glass: new THREE.MeshPhysicalMaterial({ name: 'ZR_GLASS', color: 0xd9efff, roughness: 0.05, transparent: true, opacity: 0.18, transmission: 0.22 }),
  metal: new THREE.MeshStandardMaterial({ name: 'ZR_METAL', color: 0x71808a, roughness: 0.42, metalness: 0.35 }),
  darkMetal: new THREE.MeshStandardMaterial({ name: 'ZR_DARK_METAL', color: 0x283038, roughness: 0.54, metalness: 0.18 }),
  roofTop: new THREE.MeshStandardMaterial({ name: 'ZR_ROOF_TOP', color: 0xdfe4e7, roughness: 0.38, metalness: 0.14 }),
  roofUnderside: new THREE.MeshStandardMaterial({ name: 'ZR_ROOF_UNDERSIDE', color: 0x4a5562, roughness: 0.52 }),
  facade: new THREE.MeshStandardMaterial({ name: 'ZR_FACADE', color: 0xecf0f2, roughness: 0.74 }),
  plinth: new THREE.MeshStandardMaterial({ name: 'ZR_PLINTH', color: 0x5e6872, roughness: 0.9 }),
  tunnel: new THREE.MeshStandardMaterial({ name: 'ZR_TUNNEL', color: 0xf0f3f6, roughness: 0.82 }),
};

const pitchW = 105;
const pitchH = 68;
const apron = 4.0;
const halfW = pitchW / 2;
const halfH = pitchH / 2;
const pitchBorderW = pitchW + apron * 2;
const pitchBorderH = pitchH + apron * 2;

const lowerRows = 20;
const upperRows = 18;
const rowDepth = 0.98;
const rowRise = 0.24;
const lowerFrontGap = 5.5;
const concourseGap = 4.8;
const upperGap = 12.0;
const roofOverhang = 10.8;
const bowlCornerRadius = 12.0;
const lowerStartY = 0.18;
const upperStartY = lowerStartY + lowerRows * rowRise + 1.4;
const lowerFrontGapOuter = lowerFrontGap + lowerRows * rowDepth;
const upperFrontGapInner = lowerFrontGapOuter + concourseGap;
const upperFrontGapOuter = upperFrontGapInner + upperRows * rowDepth;

const add = (mesh) => {
  mesh.castShadow = false;
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

const sphere = (name, material, radius, position = [0, 0, 0], rotation = [0, 0, 0]) => {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 48, 32), material);
  mesh.name = name;
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  return add(mesh);
};

const cylinder = (name, material, position, radiusTop, radiusBottom, height, rotation = [0, 0, 0], radialSegments = 32, openEnded = false, thetaStart = 0, thetaLength = Math.PI * 2) => {
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(radiusTop, radiusBottom, height, radialSegments, 1, openEnded, thetaStart, thetaLength),
    material,
  );
  mesh.name = name;
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  return add(mesh);
};

function roundedRectShape(halfWidth, halfHeight, radius) {
  const radiusClamped = Math.max(0.2, Math.min(radius, halfWidth - 0.1, halfHeight - 0.1));
  const shape = new THREE.Shape();
  shape.moveTo(-halfWidth + radiusClamped, -halfHeight);
  shape.lineTo(halfWidth - radiusClamped, -halfHeight);
  shape.absarc(halfWidth - radiusClamped, -halfHeight + radiusClamped, radiusClamped, -Math.PI / 2, 0, false);
  shape.lineTo(halfWidth, halfHeight - radiusClamped);
  shape.absarc(halfWidth - radiusClamped, halfHeight - radiusClamped, radiusClamped, 0, Math.PI / 2, false);
  shape.lineTo(-halfWidth + radiusClamped, halfHeight);
  shape.absarc(-halfWidth + radiusClamped, halfHeight - radiusClamped, radiusClamped, Math.PI / 2, Math.PI, false);
  shape.lineTo(-halfWidth, -halfHeight + radiusClamped);
  shape.absarc(-halfWidth + radiusClamped, -halfHeight + radiusClamped, radiusClamped, Math.PI, Math.PI * 1.5, false);
  shape.closePath();
  return shape;
}

function addRingSurface(name, material, y, outerHalfW, outerHalfH, outerRadius, innerHalfW, innerHalfH, innerRadius) {
  const shape = roundedRectShape(outerHalfW, outerHalfH, outerRadius);
  shape.holes.push(roundedRectShape(innerHalfW, innerHalfH, innerRadius));
  const geometry = new THREE.ShapeGeometry(shape, 96);
  geometry.rotateX(-Math.PI / 2);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = name;
  mesh.position.y = y;
  return add(mesh);
}

function addExtrudedRing(name, material, y, height, outerHalfW, outerHalfH, outerRadius, innerHalfW, innerHalfH, innerRadius) {
  const shape = roundedRectShape(outerHalfW, outerHalfH, outerRadius);
  shape.holes.push(roundedRectShape(innerHalfW, innerHalfH, innerRadius));
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: height,
    steps: 1,
    bevelEnabled: false,
    curveSegments: 48,
  });
  geometry.rotateX(-Math.PI / 2);
  geometry.translate(0, y, 0);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = name;
  return add(mesh);
}

function addPitch() {
  for (let i = 0; i < 14; i += 1) {
    const z = -halfH + (pitchH / 14) * (i + 0.5);
    box(`pitch_band_${i}`, i % 2 ? mats.grassDark : mats.grassLight, [0, 0.015, z], [pitchW, 0.03, pitchH / 14 + 0.04]);
  }
  for (let i = 0; i < 120; i += 1) {
    const x = -halfW + 1.2 + (i % 20) * 5.2;
    const z = -halfH + 0.6 + ((i * 11) % 68);
    box(`grass_fiber_${i}`, mats.grassFiber, [x, 0.035, z], [1.14, 0.006, 0.035], [0, 0.08 + (i % 7) * 0.03, 0]);
  }

  const y = 0.07;
  box('touchline_north', mats.line, [0, y, halfH], [pitchW, 0.03, 0.14]);
  box('touchline_south', mats.line, [0, y, -halfH], [pitchW, 0.03, 0.14]);
  box('goal_line_west', mats.line, [-halfW, y, 0], [0.14, 0.03, pitchH]);
  box('goal_line_east', mats.line, [halfW, y, 0], [0.14, 0.03, pitchH]);
  box('halfway', mats.line, [0, y, 0], [0.14, 0.03, pitchH]);

  const circle = new THREE.Mesh(new THREE.TorusGeometry(9.15, 0.05, 8, 96), mats.line);
  circle.name = 'center_circle';
  circle.rotation.x = Math.PI / 2;
  circle.position.set(0, y + 0.004, 0);
  add(circle);
  cylinder('center_spot', mats.line, [0, y + 0.004, 0], 0.15, 0.15, 0.03);

  [-1, 1].forEach((sign) => {
    const x = sign * halfW;
    box(`penalty_area_top_${sign}`, mats.line, [x - sign * 8.25, y, 20.16], [16.5, 0.03, 0.12]);
    box(`penalty_area_bottom_${sign}`, mats.line, [x - sign * 8.25, y, -20.16], [16.5, 0.03, 0.12]);
    box(`penalty_area_inner_${sign}`, mats.line, [x - sign * 16.5, y, 0], [0.12, 0.03, 40.32]);
    box(`six_area_top_${sign}`, mats.line, [x - sign * 2.75, y, 9.16], [5.5, 0.03, 0.12]);
    box(`six_area_bottom_${sign}`, mats.line, [x - sign * 2.75, y, -9.16], [5.5, 0.03, 0.12]);
    box(`six_area_inner_${sign}`, mats.line, [x - sign * 5.5, y, 0], [0.12, 0.03, 18.32]);
    cylinder(`penalty_spot_${sign}`, mats.line, [x - sign * 11, y + 0.004, 0], 0.15, 0.15, 0.03);
  });
}

function addApronAndBoards() {
  box('apron_north', mats.apron, [0, 0.045, halfH + apron / 2], [pitchBorderW + 1.8, 0.08, apron]);
  box('apron_south', mats.apron, [0, 0.045, -(halfH + apron / 2)], [pitchBorderW + 1.8, 0.08, apron]);
  box('apron_east', mats.apron, [halfW + apron / 2, 0.045, 0], [apron, 0.08, pitchBorderH + 1.8]);
  box('apron_west', mats.apron, [-(halfW + apron / 2), 0.045, 0], [apron, 0.08, pitchBorderH + 1.8]);

  addRingSurface(
    'service_ring',
    mats.concreteDark,
    0.10,
    pitchBorderW / 2 + 1.2,
    pitchBorderH / 2 + 1.2,
    8.8,
    pitchBorderW / 2 + 0.25,
    pitchBorderH / 2 + 0.25,
    8.0,
  );

  const boards = [
    [0, halfH + 2.9, pitchW + 12, 0.22],
    [0, -(halfH + 2.9), pitchW + 12, 0.22],
    [halfW + 2.9, 0, 0.22, pitchH + 12],
    [-(halfW + 2.9), 0, 0.22, pitchH + 12],
  ];
  boards.forEach(([x, z, sx, sz], idx) => {
    box(`board_${idx}`, mats.board, [x, 0.84, z], [sx, 0.9, sz]);
  });
}

function addGoals() {
  [-1, 1].forEach((sign) => {
    const x = sign * (halfW + 0.74);
    box(`goal_post_left_${sign}`, mats.line, [x, 1.22, -3.66], [0.10, 2.44, 0.10]);
    box(`goal_post_right_${sign}`, mats.line, [x, 1.22, 3.66], [0.10, 2.44, 0.10]);
    box(`goal_crossbar_${sign}`, mats.line, [x, 2.44, 0], [0.10, 0.10, 7.32]);
    box(`goal_net_base_${sign}`, mats.line, [x - sign * 1.75, 0.08, 0], [3.2, 0.04, 7.2]);
    box(`goal_net_top_${sign}`, mats.line, [x - sign * 1.75, 2.34, 0], [3.2, 0.04, 7.2]);
    box(`goal_net_left_${sign}`, mats.line, [x - sign * 1.75, 1.2, -3.6], [3.2, 2.2, 0.04]);
    box(`goal_net_right_${sign}`, mats.line, [x - sign * 1.75, 1.2, 3.6], [3.2, 2.2, 0.04]);
  });
}

function seatStripe(row) {
  if (row % 10 === 0 || row % 10 === 1) return mats.seatWhite;
  return row % 2 === 0 ? mats.seatBlue : mats.seatBlueDark;
}

function addBowlTier(prefix, rows, startY, startGap) {
  for (let row = 0; row < rows; row += 1) {
    const innerOffset = startGap + row * rowDepth;
    const outerOffset = innerOffset + rowDepth;
    const innerHalfWidth = pitchBorderW / 2 + innerOffset;
    const innerHalfHeight = pitchBorderH / 2 + innerOffset;
    const outerHalfWidth = pitchBorderW / 2 + outerOffset;
    const outerHalfHeight = pitchBorderH / 2 + outerOffset;
    const y = startY + row * rowRise;
    addExtrudedRing(
      `${prefix}_row_mass_${row}`,
      mats.concreteDark,
      y - rowRise * 0.78,
      rowRise * 0.84,
      outerHalfWidth,
      outerHalfHeight,
      bowlCornerRadius + outerOffset,
      innerHalfWidth,
      innerHalfHeight,
      bowlCornerRadius + innerOffset,
    );
    addRingSurface(
      `${prefix}_seat_band_${row}`,
      seatStripe(row),
      y + 0.01,
      outerHalfWidth - 0.02,
      outerHalfHeight - 0.02,
      bowlCornerRadius + outerOffset - 0.02,
      innerHalfWidth + 0.18,
      innerHalfHeight + 0.18,
      bowlCornerRadius + innerOffset + 0.18,
    );
    addRingSurface(
      `${prefix}_seat_back_${row}`,
      row % 2 === 0 ? mats.seatBlueDark : mats.seatBlue,
      y + 0.12,
      outerHalfWidth - 0.12,
      outerHalfHeight - 0.12,
      bowlCornerRadius + outerOffset - 0.12,
      innerHalfWidth + 0.72,
      innerHalfHeight + 0.72,
      bowlCornerRadius + innerOffset + 0.72,
    );
  }
}

function addConcourseBands() {
  addRingSurface(
    'lower_concourse_band',
    mats.concreteDark,
    lowerStartY + lowerRows * rowRise + 0.08,
    pitchBorderW / 2 + upperFrontGapInner,
    pitchBorderH / 2 + upperFrontGapInner,
    bowlCornerRadius + upperFrontGapInner,
    pitchBorderW / 2 + lowerFrontGapOuter,
    pitchBorderH / 2 + lowerFrontGapOuter,
    bowlCornerRadius + lowerFrontGapOuter,
  );

  addRingSurface(
    'lower_front_fascia',
    mats.seatBlueDark,
    lowerStartY + 0.52,
    pitchBorderW / 2 + lowerFrontGap + 0.66,
    pitchBorderH / 2 + lowerFrontGap + 0.66,
    bowlCornerRadius + lowerFrontGap + 0.66,
    pitchBorderW / 2 + lowerFrontGap - 0.26,
    pitchBorderH / 2 + lowerFrontGap - 0.26,
    bowlCornerRadius + lowerFrontGap - 0.26,
  );

  addRingSurface(
    'upper_front_fascia',
    mats.seatBlueDark,
    upperStartY + 0.72,
    pitchBorderW / 2 + upperFrontGapInner + 0.62,
    pitchBorderH / 2 + upperFrontGapInner + 0.62,
    bowlCornerRadius + upperFrontGapInner + 0.62,
    pitchBorderW / 2 + upperFrontGapInner - 0.18,
    pitchBorderH / 2 + upperFrontGapInner - 0.18,
    bowlCornerRadius + upperFrontGapInner - 0.18,
  );

  addRingSurface(
    'lower_seat_backdrop',
    mats.seatBlue,
    lowerStartY + lowerRows * rowRise * 0.42,
    pitchBorderW / 2 + lowerFrontGapOuter - 0.34,
    pitchBorderH / 2 + lowerFrontGapOuter - 0.34,
    bowlCornerRadius + lowerFrontGapOuter - 0.34,
    pitchBorderW / 2 + lowerFrontGap + 1.8,
    pitchBorderH / 2 + lowerFrontGap + 1.8,
    bowlCornerRadius + lowerFrontGap + 1.8,
  );

  addRingSurface(
    'upper_seat_backdrop',
    mats.seatBlueDark,
    upperStartY + upperRows * rowRise * 0.48,
    pitchBorderW / 2 + upperFrontGapOuter - 0.28,
    pitchBorderH / 2 + upperFrontGapOuter - 0.28,
    bowlCornerRadius + upperFrontGapOuter - 0.28,
    pitchBorderW / 2 + upperFrontGapInner + 1.2,
    pitchBorderH / 2 + upperFrontGapInner + 1.2,
    bowlCornerRadius + upperFrontGapInner + 1.2,
  );

  const vomitorySpecs = [
    { name: 'vomitory_north', x: 0, z: pitchBorderH / 2 + lowerFrontGapOuter + concourseGap * 0.5, sx: 3.2, sz: concourseGap + 1.2 },
    { name: 'vomitory_south', x: 0, z: -(pitchBorderH / 2 + lowerFrontGapOuter + concourseGap * 0.5), sx: 3.2, sz: concourseGap + 1.2 },
    { name: 'vomitory_east', x: pitchBorderW / 2 + lowerFrontGapOuter + concourseGap * 0.5, z: 0, sx: concourseGap + 1.2, sz: 3.2 },
    { name: 'vomitory_west', x: -(pitchBorderW / 2 + lowerFrontGapOuter + concourseGap * 0.5), z: 0, sx: concourseGap + 1.2, sz: 3.2 },
  ];
  vomitorySpecs.forEach((spec) => {
    box(spec.name, mats.aisle, [spec.x, lowerStartY + lowerRows * rowRise - 0.6, spec.z], [spec.sx, 1.1, spec.sz]);
    box(`${spec.name}_portal`, mats.darkMetal, [spec.x, lowerStartY + lowerRows * rowRise - 0.08, spec.z], [spec.sx - 0.3, 0.26, spec.sz - 0.3]);
  });

  [-26, 0, 26].forEach((x, idx) => {
    box(`north_aisle_${idx}`, mats.aisle, [x, upperStartY + upperRows * rowRise * 0.62, pitchBorderH / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48], [1.2, 3.6, 2.2], [-0.44, 0, 0]);
    box(`south_aisle_${idx}`, mats.aisle, [x, upperStartY + upperRows * rowRise * 0.62, -(pitchBorderH / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48)], [1.2, 3.6, 2.2], [0.44, 0, 0]);
  });
  [-18, 18].forEach((z, idx) => {
    box(`east_aisle_${idx}`, mats.aisle, [pitchBorderW / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48, upperStartY + upperRows * rowRise * 0.62, z], [2.2, 3.6, 1.2], [0, 0, -0.44]);
    box(`west_aisle_${idx}`, mats.aisle, [-(pitchBorderW / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48), upperStartY + upperRows * rowRise * 0.62, z], [2.2, 3.6, 1.2], [0, 0, 0.44]);
  });
}

function addRoundedTunnelAndDugouts() {
  const tunnelZ = -(halfH + apron + lowerFrontGap + 0.4);
  cylinder('tunnel_shell', mats.tunnel, [0, 1.18, tunnelZ], 1.45, 1.45, 2.8, [0, 0, Math.PI / 2], 40, true, Math.PI, Math.PI);
  box('tunnel_floor', mats.apron, [0, 0.08, tunnelZ], [2.4, 0.08, 1.8]);
  box('tunnel_shadow', mats.darkMetal, [0, 0.84, tunnelZ + 0.72], [2.0, 1.2, 0.06]);

  const addDugout = (label, x) => {
    const z = -(halfH + apron - 0.6);
    box(`dugout_${label}_platform`, mats.concrete, [x, 0.14, z], [10.2, 0.16, 1.34]);
    cylinder(`dugout_${label}_canopy`, mats.glass, [x, 1.1, z + 0.16], 1.18, 1.18, 9.4, [0, 0, Math.PI / 2], 28, true, 0, Math.PI);
    box(`dugout_${label}_rear`, mats.darkMetal, [x, 0.94, z + 0.74], [9.1, 0.48, 0.08]);
    box(`dugout_${label}_front_rail`, mats.metal, [x, 0.82, z - 0.56], [8.9, 0.08, 0.08]);
    box(`dugout_${label}_base_shadow`, mats.darkMetal, [x, 0.10, z + 0.58], [9.4, 0.06, 0.18]);
    for (let i = 0; i < 7; i += 1) {
      const sx = x - 3.6 + i * 1.2;
      box(`dugout_${label}_seat_${i}`, mats.seatBlue, [sx, 0.44, z + 0.18], [0.56, 0.12, 0.40]);
      box(`dugout_${label}_back_${i}`, mats.seatBlue, [sx, 0.72, z + 0.34], [0.56, 0.38, 0.07], [-0.18, 0, 0]);
    }
  };

  addDugout('home', -16.5);
  addDugout('away', 16.5);
}

function addReadableStandPlanes() {
  const addLongStand = (label, zSign) => {
    box(
      `display_lower_${label}`,
      mats.seatBlueDark,
      [0, 3.0, zSign * (pitchBorderH / 2 + lowerFrontGap + 9.4)],
      [pitchW + 34, 0.22, 18.5],
      [zSign * 0.58, 0, 0],
    );
    box(
      `display_upper_${label}`,
      mats.seatBlue,
      [0, 8.0, zSign * (pitchBorderH / 2 + upperFrontGapInner + 12.8)],
      [pitchW + 26, 0.22, 15.2],
      [zSign * 0.66, 0, 0],
    );
    [-32, -12, 12, 32].forEach((x, idx) => {
      box(
        `display_aisle_${label}_${idx}`,
        mats.seatWhite,
        [x, 5.1, zSign * (pitchBorderH / 2 + lowerFrontGap + 12.2)],
        [1.24, 0.42, 22.5],
        [zSign * 0.61, 0, 0],
      );
    });
  };

  const addShortStand = (label, xSign) => {
    box(
      `display_lower_${label}`,
      mats.seatBlueDark,
      [xSign * (pitchBorderW / 2 + lowerFrontGap + 10.0), 3.0, 0],
      [18.5, 0.22, pitchH + 20],
      [0, 0, xSign * -0.58],
    );
    box(
      `display_upper_${label}`,
      mats.seatBlue,
      [xSign * (pitchBorderW / 2 + upperFrontGapInner + 13.0), 8.0, 0],
      [15.2, 0.22, pitchH + 14],
      [0, 0, xSign * -0.66],
    );
    [-18, 0, 18].forEach((z, idx) => {
      box(
        `display_aisle_${label}_${idx}`,
        mats.seatWhite,
        [xSign * (pitchBorderW / 2 + lowerFrontGap + 12.4), 5.2, z],
        [22.8, 0.42, 1.16],
        [0, 0, xSign * -0.61],
      );
    });
  };

  addLongStand('north', 1);
  addLongStand('south', -1);
  addShortStand('east', 1);
  addShortStand('west', -1);
}

function addFacadeAndRoof() {
  const outerOffset = Math.max(lowerFrontGapOuter, upperFrontGapOuter) + roofOverhang;
  const innerRoofOffset = Math.max(lowerFrontGapOuter, upperFrontGapOuter) - 0.8;
  const roofY = upperStartY + upperRows * rowRise + 1.35;
  const facadeY = roofY - 2.8;

  addRingSurface(
    'roof_plate',
    mats.roofTop,
    roofY,
    pitchBorderW / 2 + outerOffset,
    pitchBorderH / 2 + outerOffset,
    bowlCornerRadius + outerOffset + 6,
    pitchBorderW / 2 + innerRoofOffset,
    pitchBorderH / 2 + innerRoofOffset,
    bowlCornerRadius + innerRoofOffset + 2.8,
  );

  addRingSurface(
    'roof_underside',
    mats.roofUnderside,
    roofY - 0.36,
    pitchBorderW / 2 + outerOffset - 0.4,
    pitchBorderH / 2 + outerOffset - 0.4,
    bowlCornerRadius + outerOffset + 5.2,
    pitchBorderW / 2 + innerRoofOffset + 1.2,
    pitchBorderH / 2 + innerRoofOffset + 1.2,
    bowlCornerRadius + innerRoofOffset + 4.0,
  );

  const outerW = pitchBorderW / 2 + outerOffset - 0.8;
  const outerH = pitchBorderH / 2 + outerOffset - 0.8;
  const innerW = pitchBorderW / 2 + innerRoofOffset + 2.6;
  const innerH = pitchBorderH / 2 + innerRoofOffset + 2.6;

  box('facade_north', mats.facade, [0, facadeY, outerH], [outerW * 2 - 18, 5.4, 2.4], [-0.03, 0, 0]);
  box('facade_south', mats.facade, [0, facadeY, -outerH], [outerW * 2 - 18, 5.4, 2.4], [0.03, 0, 0]);
  box('facade_east', mats.facade, [outerW, facadeY, 0], [2.4, 5.4, innerH * 2 - 14], [0, 0, -0.03]);
  box('facade_west', mats.facade, [-outerW, facadeY, 0], [2.4, 5.4, innerH * 2 - 14], [0, 0, 0.03]);
  box('inner_parapet_north', mats.darkMetal, [0, roofY - 1.22, pitchBorderH / 2 + lowerFrontGap + lowerRows * rowDepth + concourseGap + upperRows * rowDepth - 0.6], [pitchW + 34, 0.56, 1.5], [0.06, 0, 0]);
  box('inner_parapet_south', mats.darkMetal, [0, roofY - 1.22, -(pitchBorderH / 2 + lowerFrontGap + lowerRows * rowDepth + concourseGap + upperRows * rowDepth - 0.6)], [pitchW + 34, 0.56, 1.5], [-0.06, 0, 0]);
  box('inner_parapet_east', mats.darkMetal, [pitchBorderW / 2 + lowerFrontGap + lowerRows * rowDepth + concourseGap + upperRows * rowDepth - 0.6, roofY - 1.22, 0], [1.5, 0.56, pitchH + 26], [0, 0, -0.06]);
  box('inner_parapet_west', mats.darkMetal, [-(pitchBorderW / 2 + lowerFrontGap + lowerRows * rowDepth + concourseGap + upperRows * rowDepth - 0.6), roofY - 1.22, 0], [1.5, 0.56, pitchH + 26], [0, 0, 0.06]);
  box('roof_lip_north', mats.roofUnderside, [0, roofY - 0.36, pitchBorderH / 2 + innerRoofOffset + 1.8], [pitchW + 26, 0.28, 0.9], [0.08, 0, 0]);
  box('roof_lip_south', mats.roofUnderside, [0, roofY - 0.36, -(pitchBorderH / 2 + innerRoofOffset + 1.8)], [pitchW + 26, 0.28, 0.9], [-0.08, 0, 0]);
  box('roof_lip_east', mats.roofUnderside, [pitchBorderW / 2 + innerRoofOffset + 1.8, roofY - 0.36, 0], [0.9, 0.28, pitchH + 20], [0, 0, -0.08]);
  box('roof_lip_west', mats.roofUnderside, [-(pitchBorderW / 2 + innerRoofOffset + 1.8), roofY - 0.36, 0], [0.9, 0.28, pitchH + 20], [0, 0, 0.08]);

  [-1, 1].forEach((sign) => {
    for (let i = -4; i <= 4; i += 2) {
      box(
        `roof_truss_long_${sign}_${i}`,
        mats.metal,
        [i * 10.5, roofY - 0.72, sign * (pitchBorderH / 2 + innerRoofOffset + 1.6)],
        [0.22, 0.22, 2.8],
        [0.28 * sign, 0, 0],
      );
    }
  });

  [[1, 1, Math.PI * 1.5], [-1, 1, Math.PI], [-1, -1, Math.PI * 0.5], [1, -1, 0]].forEach(([sx, sz, theta], idx) => {
    cylinder(
      `facade_corner_${idx}`,
      mats.facade,
      [sx * outerW, facadeY, sz * outerH],
      5.0,
      5.0,
      5.4,
      [0, 0, 0],
      40,
      false,
      theta,
      Math.PI / 2,
    );
  });

  box('scoreboard_shell', mats.darkMetal, [0, upperStartY + upperRows * rowRise + 2.4, pitchBorderH / 2 + lowerFrontGap + lowerRows * rowDepth + 0.9], [8.2, 2.4, 0.72]);
  box('scoreboard_face', mats.board, [0, upperStartY + upperRows * rowRise + 2.4, pitchBorderH / 2 + lowerFrontGap + lowerRows * rowDepth + 1.25], [7.4, 1.8, 0.12]);
}

function addExteriorPlinth() {
  const plinthOffset = lowerFrontGapOuter + 7.2;
  addRingSurface(
    'outer_plinth',
    mats.plinth,
    -0.08,
    pitchBorderW / 2 + plinthOffset,
    pitchBorderH / 2 + plinthOffset,
    bowlCornerRadius + plinthOffset + 3.4,
    pitchBorderW / 2 + lowerFrontGapOuter + 1.0,
    pitchBorderH / 2 + lowerFrontGapOuter + 1.0,
    bowlCornerRadius + lowerFrontGapOuter + 0.8,
  );
}

function addPitchEdgeShadow() {
  addRingSurface(
    'pitch_edge_shadow',
    new THREE.MeshBasicMaterial({ name: 'ZR_EDGE_SHADOW', color: 0x17222a, transparent: true, opacity: 0.22 }),
    0.055,
    pitchBorderW / 2 + 0.32,
    pitchBorderH / 2 + 0.32,
    8.0,
    pitchW / 2 - 0.32,
    pitchH / 2 - 0.32,
    0.2,
  );
}

scene.add(new THREE.AmbientLight(0xffffff, 1.08));
const sun = new THREE.DirectionalLight(0xfff1d8, 0.78);
sun.position.set(-90, 130, -60);
scene.add(sun);

addPitch();
addApronAndBoards();
addGoals();
addBowlTier('lower', lowerRows, lowerStartY, lowerFrontGap);
addConcourseBands();
addBowlTier('upper', upperRows, upperStartY, lowerFrontGap + lowerRows * rowDepth + concourseGap);
addRoundedTunnelAndDugouts();
addReadableStandPlanes();
addFacadeAndRoof();
addExteriorPlinth();
addPitchEdgeShadow();

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
