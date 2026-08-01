import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import * as THREE from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import { addProtectedPitchBase } from './lib/pitch3d_stadium_zero_rebuild_base.mjs';

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
  grassFiber: new THREE.MeshStandardMaterial({ name: 'ZR_GRASS_FIBER', color: 0x9dd37c, roughness: 0.98 }),
  line: new THREE.MeshStandardMaterial({ name: 'ZR_LINE', color: 0xf5f7f1, roughness: 0.8 }),
  apron: new THREE.MeshStandardMaterial({ name: 'ZR_APRON', color: 0x324047, roughness: 0.96 }),
  board: new THREE.MeshStandardMaterial({ name: 'ZR_BOARD', color: 0x143943, roughness: 0.24, emissive: 0x1c6870, emissiveIntensity: 0.25 }),
  concrete: new THREE.MeshStandardMaterial({ name: 'ZR_CONCRETE', color: 0xf2f5f7, roughness: 0.92 }),
  concreteDark: new THREE.MeshStandardMaterial({ name: 'ZR_CONCRETE_DARK', color: 0x626f7d, roughness: 0.84 }),
  aisle: new THREE.MeshStandardMaterial({ name: 'ZR_AISLE', color: 0xcfd7de, roughness: 0.9 }),
  seatBlue: new THREE.MeshStandardMaterial({ name: 'ZR_SEAT_BLUE', color: 0x72a3ff, roughness: 0.52, emissive: 0x1e478f, emissiveIntensity: 0.04 }),
  seatBlueDark: new THREE.MeshStandardMaterial({ name: 'ZR_SEAT_BLUE_DARK', color: 0x2f5fc4, roughness: 0.54, emissive: 0x12356e, emissiveIntensity: 0.05 }),
  seatWhite: new THREE.MeshStandardMaterial({ name: 'ZR_SEAT_WHITE', color: 0xf3f6fb, roughness: 0.68 }),
  seatShadow: new THREE.MeshStandardMaterial({ name: 'ZR_SEAT_SHADOW', color: 0x9baec4, roughness: 0.74 }),
  glass: new THREE.MeshPhysicalMaterial({ name: 'ZR_GLASS', color: 0xdff2ff, roughness: 0.04, transparent: true, opacity: 0.14, transmission: 0.24 }),
  metal: new THREE.MeshStandardMaterial({ name: 'ZR_METAL', color: 0x71808a, roughness: 0.42, metalness: 0.35 }),
  darkMetal: new THREE.MeshStandardMaterial({ name: 'ZR_DARK_METAL', color: 0x283038, roughness: 0.54, metalness: 0.18 }),
  roofTop: new THREE.MeshStandardMaterial({ name: 'ZR_ROOF_TOP', color: 0xdfe6ec, roughness: 0.56, metalness: 0.14 }),
  roofUnderside: new THREE.MeshStandardMaterial({ name: 'ZR_ROOF_UNDERSIDE', color: 0x566473, roughness: 0.62 }),
  facade: new THREE.MeshStandardMaterial({ name: 'ZR_FACADE', color: 0xeef4f8, roughness: 0.54, metalness: 0.08 }),
  plinth: new THREE.MeshStandardMaterial({ name: 'ZR_PLINTH', color: 0x5e6872, roughness: 0.9 }),
  tunnel: new THREE.MeshStandardMaterial({ name: 'ZR_TUNNEL', color: 0xf0f3f6, roughness: 0.82 }),
  ledLine: new THREE.MeshStandardMaterial({ name: 'ZR_LED_LINE', color: 0xd9f7ff, roughness: 0.18, emissive: 0x79ebff, emissiveIntensity: 0.55 }),
  net: new THREE.MeshPhysicalMaterial({ name: 'ZR_NET', color: 0xf8fbff, roughness: 0.72, transparent: true, opacity: 0.26, transmission: 0.02 }),
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
const roofOverhang = 3.4;
const bowlCornerRadius = 14.5;
const lowerStartY = 0.18;
const upperStartY = lowerStartY + lowerRows * rowRise + 1.4;
const lowerFrontGapOuter = lowerFrontGap + lowerRows * rowDepth;
const upperFrontGapInner = lowerFrontGapOuter + concourseGap;
const upperFrontGapOuter = upperFrontGapInner + upperRows * rowDepth;
const seatShellInset = 1.35;

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

const plane = (name, material, position, size, rotation = [0, 0, 0]) => {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(size[0], size[1]), material);
  mesh.name = name;
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  scene.add(mesh);
  return mesh;
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

function seatStripe(row) {
  if (row % 14 === 0) return mats.seatWhite;
  if (row % 6 === 0) return mats.seatShadow;
  return row % 3 === 0 ? mats.seatBlueDark : mats.seatBlue;
}

function addCommercialBowlContinuous() {
  const lowerRowsCompact = 13;
  const upperRowsCompact = 10;
  const lowerDepth = 1.78;
  const upperDepth = 1.74;
  const lowerRise = 0.36;
  const upperRise = 0.40;
  const lowerGap = lowerFrontGap + 1.1;
  const upperGapLocal = lowerGap + lowerRowsCompact * lowerDepth + 4.2;

  for (let row = 0; row < lowerRowsCompact; row += 1) {
    const innerOffset = lowerGap + row * lowerDepth;
    const outerOffset = innerOffset + lowerDepth;
    const y = 0.28 + row * lowerRise;
    const seatMat = row % 5 === 0 ? mats.seatWhite : row % 2 === 0 ? mats.seatBlue : mats.seatBlueDark;
    addExtrudedRing(
      `commercial_lower_mass_${row}`,
      mats.concreteDark,
      y,
      lowerRise * 0.88,
      pitchBorderW / 2 + outerOffset,
      pitchBorderH / 2 + outerOffset,
      bowlCornerRadius + outerOffset,
      pitchBorderW / 2 + innerOffset,
      pitchBorderH / 2 + innerOffset,
      bowlCornerRadius + innerOffset,
    );
    addRingSurface(
      `commercial_lower_seat_${row}`,
      seatMat,
      y + lowerRise * 0.78,
      pitchBorderW / 2 + outerOffset - 0.03,
      pitchBorderH / 2 + outerOffset - 0.03,
      bowlCornerRadius + outerOffset - 0.03,
      pitchBorderW / 2 + innerOffset + 0.20,
      pitchBorderH / 2 + innerOffset + 0.20,
      bowlCornerRadius + innerOffset + 0.20,
    );
    addExtrudedRing(
      `commercial_lower_seat_thickness_${row}`,
      seatMat,
      y + lowerRise * 0.54,
      0.14,
      pitchBorderW / 2 + outerOffset - 0.02,
      pitchBorderH / 2 + outerOffset - 0.02,
      bowlCornerRadius + outerOffset - 0.02,
      pitchBorderW / 2 + innerOffset + 0.34,
      pitchBorderH / 2 + innerOffset + 0.34,
      bowlCornerRadius + innerOffset + 0.34,
    );
    addRingSurface(
      `commercial_lower_back_band_${row}`,
      row % 2 === 0 ? mats.seatBlueDark : mats.seatShadow,
      y + lowerRise * 0.94,
      pitchBorderW / 2 + outerOffset - 0.10,
      pitchBorderH / 2 + outerOffset - 0.10,
      bowlCornerRadius + outerOffset - 0.10,
      pitchBorderW / 2 + innerOffset + 0.92,
      pitchBorderH / 2 + innerOffset + 0.92,
      bowlCornerRadius + innerOffset + 0.92,
    );
  }

  addRingSurface(
    'commercial_mid_concourse',
    mats.aisle,
    0.28 + lowerRowsCompact * lowerRise + 0.22,
    pitchBorderW / 2 + upperGapLocal - 1.0,
    pitchBorderH / 2 + upperGapLocal - 1.0,
    bowlCornerRadius + upperGapLocal - 1.0,
    pitchBorderW / 2 + lowerGap + lowerRowsCompact * lowerDepth + 0.5,
    pitchBorderH / 2 + lowerGap + lowerRowsCompact * lowerDepth + 0.5,
    bowlCornerRadius + lowerGap + lowerRowsCompact * lowerDepth + 0.5,
  );

  for (let row = 0; row < upperRowsCompact; row += 1) {
    const innerOffset = upperGapLocal + row * upperDepth;
    const outerOffset = innerOffset + upperDepth;
    const y = 5.7 + row * upperRise;
    const seatMat = row % 4 === 0 ? mats.seatWhite : row % 2 === 0 ? mats.seatBlueDark : mats.seatBlue;
    addExtrudedRing(
      `commercial_upper_mass_${row}`,
      mats.concreteDark,
      y,
      upperRise * 0.92,
      pitchBorderW / 2 + outerOffset,
      pitchBorderH / 2 + outerOffset,
      bowlCornerRadius + outerOffset,
      pitchBorderW / 2 + innerOffset,
      pitchBorderH / 2 + innerOffset,
      bowlCornerRadius + innerOffset,
    );
    addRingSurface(
      `commercial_upper_seat_${row}`,
      seatMat,
      y + upperRise * 0.82,
      pitchBorderW / 2 + outerOffset - 0.03,
      pitchBorderH / 2 + outerOffset - 0.03,
      bowlCornerRadius + outerOffset - 0.03,
      pitchBorderW / 2 + innerOffset + 0.18,
      pitchBorderH / 2 + innerOffset + 0.18,
      bowlCornerRadius + innerOffset + 0.18,
    );
    addExtrudedRing(
      `commercial_upper_seat_thickness_${row}`,
      seatMat,
      y + upperRise * 0.58,
      0.14,
      pitchBorderW / 2 + outerOffset - 0.02,
      pitchBorderH / 2 + outerOffset - 0.02,
      bowlCornerRadius + outerOffset - 0.02,
      pitchBorderW / 2 + innerOffset + 0.30,
      pitchBorderH / 2 + innerOffset + 0.30,
      bowlCornerRadius + innerOffset + 0.30,
    );
    addRingSurface(
      `commercial_upper_back_band_${row}`,
      row % 2 === 0 ? mats.seatBlue : mats.seatShadow,
      y + upperRise * 0.96,
      pitchBorderW / 2 + outerOffset - 0.12,
      pitchBorderH / 2 + outerOffset - 0.12,
      bowlCornerRadius + outerOffset - 0.12,
      pitchBorderW / 2 + innerOffset + 0.84,
      pitchBorderH / 2 + innerOffset + 0.84,
      bowlCornerRadius + innerOffset + 0.84,
    );
  }

  addRingSurface(
    'commercial_front_fascia',
    mats.seatBlueDark,
    0.76,
    pitchBorderW / 2 + lowerGap + 0.62,
    pitchBorderH / 2 + lowerGap + 0.62,
    bowlCornerRadius + lowerGap + 0.62,
    pitchBorderW / 2 + lowerGap + 0.10,
    pitchBorderH / 2 + lowerGap + 0.10,
    bowlCornerRadius + lowerGap + 0.10,
  );

  const rearBandOffset = upperGapLocal + upperRowsCompact * upperDepth + 1.0;
  addRingSurface(
    'commercial_rear_band',
    mats.seatBlueDark,
    10.8,
    pitchBorderW / 2 + rearBandOffset + 0.8,
    pitchBorderH / 2 + rearBandOffset + 0.8,
    bowlCornerRadius + rearBandOffset + 0.8,
    pitchBorderW / 2 + rearBandOffset - 0.1,
    pitchBorderH / 2 + rearBandOffset - 0.1,
    bowlCornerRadius + rearBandOffset - 0.1,
  );
  addExtrudedRing(
    'commercial_rear_wall',
    mats.concreteDark,
    9.6,
    2.2,
    pitchBorderW / 2 + rearBandOffset + 1.0,
    pitchBorderH / 2 + rearBandOffset + 1.0,
    bowlCornerRadius + rearBandOffset + 1.0,
    pitchBorderW / 2 + rearBandOffset - 0.16,
    pitchBorderH / 2 + rearBandOffset - 0.16,
    bowlCornerRadius + rearBandOffset - 0.16,
  );
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
      y - rowRise * 0.70,
      rowRise * 0.54,
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
      y + 0.03,
      outerHalfWidth - 0.01,
      outerHalfHeight - 0.01,
      bowlCornerRadius + outerOffset - 0.01,
      innerHalfWidth + 0.04,
      innerHalfHeight + 0.04,
      bowlCornerRadius + innerOffset + 0.04,
    );
    addRingSurface(
      `${prefix}_seat_back_${row}`,
      row % 4 === 0 ? mats.seatBlueDark : mats.seatBlue,
      y + 0.16,
      outerHalfWidth - 0.09,
      outerHalfHeight - 0.09,
      bowlCornerRadius + outerOffset - 0.09,
      innerHalfWidth + 0.52,
      innerHalfHeight + 0.52,
      bowlCornerRadius + innerOffset + 0.52,
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
    box(`north_aisle_${idx}`, mats.aisle, [x, upperStartY + upperRows * rowRise * 0.62, pitchBorderH / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48], [0.62, 2.8, 1.3], [-0.34, 0, 0]);
    box(`south_aisle_${idx}`, mats.aisle, [x, upperStartY + upperRows * rowRise * 0.62, -(pitchBorderH / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48)], [0.62, 2.8, 1.3], [0.34, 0, 0]);
  });
  [-18, 18].forEach((z, idx) => {
    box(`east_aisle_${idx}`, mats.aisle, [pitchBorderW / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48, upperStartY + upperRows * rowRise * 0.62, z], [1.3, 2.8, 0.62], [0, 0, -0.34]);
    box(`west_aisle_${idx}`, mats.aisle, [-(pitchBorderW / 2 + upperFrontGapInner + upperRows * rowDepth * 0.48), upperStartY + upperRows * rowRise * 0.62, z], [1.3, 2.8, 0.62], [0, 0, 0.34]);
  });

  [-38, -12, 12, 38].forEach((x, idx) => {
    box(`lower_vertical_cut_north_${idx}`, mats.aisle, [x, 2.7, pitchBorderH / 2 + lowerFrontGap + 10.2], [0.56, 3.2, 6.2], [-0.48, 0, 0]);
    box(`lower_vertical_cut_south_${idx}`, mats.aisle, [x, 2.7, -(pitchBorderH / 2 + lowerFrontGap + 10.2)], [0.56, 3.2, 6.2], [0.48, 0, 0]);
  });
  [-24, 0, 24].forEach((z, idx) => {
    box(`lower_vertical_cut_east_${idx}`, mats.aisle, [pitchBorderW / 2 + lowerFrontGap + 10.2, 2.7, z], [6.2, 3.2, 0.56], [0, 0, -0.48]);
    box(`lower_vertical_cut_west_${idx}`, mats.aisle, [-(pitchBorderW / 2 + lowerFrontGap + 10.2), 2.7, z], [6.2, 3.2, 0.56], [0, 0, 0.48]);
  });
}

function addRoundedTunnelAndDugouts() {
  const tunnelZ = -(halfH + apron + lowerFrontGap + 0.98);
  cylinder('tunnel_shell_outer', mats.tunnel, [0, 0.62, tunnelZ], 0.76, 0.76, 1.62, [0, 0, Math.PI / 2], 48, true, Math.PI, Math.PI);
  cylinder('tunnel_shell_inner', mats.glass, [0, 0.60, tunnelZ + 0.03], 0.62, 0.62, 1.34, [0, 0, Math.PI / 2], 40, true, Math.PI, Math.PI);
  box('tunnel_floor', mats.apron, [0, 0.06, tunnelZ], [1.38, 0.06, 0.92]);
  box('tunnel_back_wall', mats.concreteDark, [0, 0.40, tunnelZ + 0.48], [1.48, 0.44, 0.06]);
  box('tunnel_side_left', mats.concrete, [-0.70, 0.24, tunnelZ], [0.06, 0.30, 0.94]);
  box('tunnel_side_right', mats.concrete, [0.70, 0.24, tunnelZ], [0.06, 0.30, 0.94]);
  box('tunnel_top_trim', mats.metal, [0, 0.92, tunnelZ + 0.02], [1.56, 0.04, 0.08]);
  box('tunnel_led_strip', mats.ledLine, [0, 0.76, tunnelZ - 0.28], [1.06, 0.02, 0.03]);

  const addDugout = (label, x) => {
    const z = -(halfH + apron - 0.28);
    box(`dugout_${label}_platform`, mats.concrete, [x, 0.08, z], [7.6, 0.10, 1.42]);
    box(`dugout_${label}_platform_nose`, mats.concreteDark, [x, 0.06, z - 0.60], [7.2, 0.03, 0.18]);
    cylinder(`dugout_${label}_canopy_outer`, mats.glass, [x, 0.72, z + 0.10], 0.68, 0.68, 6.6, [0, 0, Math.PI / 2], 48, true, 0, Math.PI);
    cylinder(`dugout_${label}_canopy_inner`, mats.glass, [x, 0.69, z + 0.12], 0.56, 0.56, 6.18, [0, 0, Math.PI / 2], 42, true, 0, Math.PI);
    box(`dugout_${label}_rear`, mats.darkMetal, [x, 0.64, z + 0.56], [6.3, 0.16, 0.06]);
    box(`dugout_${label}_front_rail`, mats.metal, [x, 0.38, z - 0.48], [6.0, 0.04, 0.04]);
    box(`dugout_${label}_base_shadow`, mats.darkMetal, [x, 0.08, z + 0.46], [6.2, 0.02, 0.10]);
    box(`dugout_${label}_branding`, mats.seatBlueDark, [x, 0.16, z - 0.70], [6.8, 0.08, 0.08]);
    box(`dugout_${label}_step`, mats.concreteDark, [x, 0.04, z - 0.18], [6.2, 0.02, 0.18]);
    box(`dugout_${label}_roof_led`, mats.ledLine, [x, 0.84, z + 0.10], [5.8, 0.02, 0.02]);
    box(`dugout_${label}_blue_skirt`, mats.seatBlueDark, [x, 0.16, z + 0.62], [6.8, 0.12, 0.05]);
    box(`dugout_${label}_glass_front`, mats.glass, [x, 0.44, z - 0.28], [5.8, 0.34, 0.03]);
    [-2.84, 2.84].forEach((offset, idx) => {
      box(`dugout_${label}_side_${idx}`, mats.metal, [x + offset, 0.54, z + 0.10], [0.05, 0.58, 1.22]);
      box(`dugout_${label}_side_glass_${idx}`, mats.glass, [x + offset * 0.97, 0.54, z], [0.03, 0.52, 0.78]);
    });
    [-2.2, -1.1, 0, 1.1, 2.2].forEach((offset, idx) => {
      box(`dugout_${label}_roof_rib_${idx}`, mats.metal, [x + offset, 0.86, z + 0.10], [0.05, 0.06, 1.20], [0.24, 0, 0]);
    });
    for (let i = 0; i < 5; i += 1) {
      const sx = x - 2.04 + i * 1.02;
      box(`dugout_${label}_seat_${i}`, mats.seatBlue, [sx, 0.24, z + 0.08], [0.42, 0.07, 0.28]);
      box(`dugout_${label}_seat_front_${i}`, mats.seatBlueDark, [sx, 0.22, z - 0.02], [0.38, 0.03, 0.06]);
      box(`dugout_${label}_back_${i}`, mats.seatBlue, [sx, 0.42, z + 0.22], [0.40, 0.24, 0.04], [-0.38, 0, 0]);
      box(`dugout_${label}_headrest_${i}`, mats.seatWhite, [sx, 0.54, z + 0.24], [0.20, 0.04, 0.03], [-0.38, 0, 0]);
      box(`dugout_${label}_leg_${i}`, mats.darkMetal, [sx, 0.12, z + 0.08], [0.05, 0.14, 0.05]);
    }
  };

  addDugout('home', -16.5);
  addDugout('away', 16.5);
}

function addArchitecturalGrandstands() {
  const addLongStand = (label, zSign) => {
    const baseZ = zSign * (pitchBorderH / 2 + lowerFrontGap + 18.4);
    box(`grandstand_lower_wall_${label}`, mats.concreteDark, [0, 2.9, baseZ], [pitchW + 18, 0.78, 1.1], [zSign * 0.16, 0, 0]);
    box(`grandstand_upper_wall_${label}`, mats.concreteDark, [0, 8.7, zSign * (pitchBorderH / 2 + upperFrontGapInner + 16.4)], [pitchW + 12, 0.72, 1.0], [zSign * 0.16, 0, 0]);
    [-42, -16, 16, 42].forEach((x, idx) => {
      box(`grandstand_vomitory_${label}_${idx}`, mats.aisle, [x, 6.3, zSign * (pitchBorderH / 2 + upperFrontGapInner + 8.6)], [0.82, 5.8, 1.2], [zSign * 0.22, 0, 0]);
    });
    box(`grandstand_led_${label}`, mats.ledLine, [0, 9.2, zSign * (pitchBorderH / 2 + upperFrontGapInner + 8.0)], [pitchW + 8, 0.08, 0.16], [zSign * 0.14, 0, 0]);
  };

  const addShortStand = (label, xSign) => {
    const baseX = xSign * (pitchBorderW / 2 + lowerFrontGap + 16.8);
    box(`grandstand_lower_wall_${label}`, mats.concreteDark, [baseX, 2.9, 0], [1.1, 0.78, pitchH + 4], [0, 0, -xSign * 0.16]);
    box(`grandstand_upper_wall_${label}`, mats.concreteDark, [xSign * (pitchBorderW / 2 + upperFrontGapInner + 15.0), 8.7, 0], [1.0, 0.72, pitchH - 3], [0, 0, -xSign * 0.16]);
    [-18, 18].forEach((z, idx) => {
      box(`grandstand_vomitory_${label}_${idx}`, mats.aisle, [xSign * (pitchBorderW / 2 + upperFrontGapInner + 8.4), 6.2, z], [1.2, 5.8, 0.82], [0, 0, -xSign * 0.22]);
    });
    box(`grandstand_led_${label}`, mats.ledLine, [xSign * (pitchBorderW / 2 + upperFrontGapInner + 7.8), 9.2, 0], [0.16, 0.08, pitchH + 2], [0, 0, -xSign * 0.14]);
  };

  addLongStand('north', 1);
  addLongStand('south', -1);
  addShortStand('east', 1);
  addShortStand('west', -1);
}

function addCornerGrandstandBlocks() {
  [
    { name: 'ne', sx: 1, sz: 1, ry: -Math.PI / 4 },
    { name: 'nw', sx: -1, sz: 1, ry: Math.PI / 4 },
    { name: 'sw', sx: -1, sz: -1, ry: Math.PI * 0.75 },
    { name: 'se', sx: 1, sz: -1, ry: -Math.PI * 0.75 },
  ].forEach((corner) => {
    const lowerX = corner.sx * (pitchBorderW / 2 + lowerFrontGap + 9.8);
    const lowerZ = corner.sz * (pitchBorderH / 2 + lowerFrontGap + 9.2);
    box(`corner_block_lower_${corner.name}`, mats.concreteDark, [lowerX, 2.25, lowerZ], [7.8, 0.42, 10.8], [corner.sz * 0.18, corner.ry, 0]);
    const upperX = corner.sx * (pitchBorderW / 2 + upperFrontGapInner + 8.6);
    const upperZ = corner.sz * (pitchBorderH / 2 + upperFrontGapInner + 8.0);
    box(`corner_block_upper_${corner.name}`, mats.concreteDark, [upperX, 7.55, upperZ], [6.8, 0.34, 9.2], [corner.sz * 0.14, corner.ry, 0]);
  });
}

function addPremiumSeatBands() {
  [
    { name: 'north_lower', x: 0, y: 4.5, z: pitchBorderH / 2 + lowerFrontGap + 14.6, sx: pitchW + 18, sz: 1.18, rx: 0.32 },
    { name: 'south_lower', x: 0, y: 4.5, z: -(pitchBorderH / 2 + lowerFrontGap + 14.6), sx: pitchW + 18, sz: 1.18, rx: -0.32 },
    { name: 'north_upper', x: 0, y: 9.6, z: pitchBorderH / 2 + upperFrontGapInner + 13.9, sx: pitchW + 13, sz: 1.06, rx: 0.34 },
    { name: 'south_upper', x: 0, y: 9.6, z: -(pitchBorderH / 2 + upperFrontGapInner + 13.9), sx: pitchW + 13, sz: 1.06, rx: -0.34 },
  ].forEach((band) => {
    box(`premium_band_${band.name}_blue`, mats.seatBlueDark, [band.x, band.y, band.z], [band.sx, 0.08, band.sz], [band.rx, 0, 0]);
    box(`premium_band_${band.name}_white`, mats.seatWhite, [band.x, band.y + 0.02, band.z], [band.sx * 0.92, 0.04, band.sz * 0.30], [band.rx, 0, 0]);
  });
}

function addSeatMosaicOverlays() {
  const longRows = [
    { name: 'north_lower', x: 0, y: 3.06, z: pitchBorderH / 2 + lowerFrontGap + 7.8, sx: pitchW + 20, sz: 11.8, rx: 0.44, material: mats.seatBlueDark },
    { name: 'south_lower', x: 0, y: 3.06, z: -(pitchBorderH / 2 + lowerFrontGap + 7.8), sx: pitchW + 20, sz: 11.8, rx: -0.44, material: mats.seatBlueDark },
    { name: 'north_upper', x: 0, y: 8.34, z: pitchBorderH / 2 + upperFrontGapInner + 8.0, sx: pitchW + 14, sz: 10.8, rx: 0.40, material: mats.seatBlue },
    { name: 'south_upper', x: 0, y: 8.34, z: -(pitchBorderH / 2 + upperFrontGapInner + 8.0), sx: pitchW + 14, sz: 10.8, rx: -0.40, material: mats.seatBlue },
  ];
  longRows.forEach((row) => {
    box(`seat_mosaic_${row.name}`, row.material, [row.x, row.y, row.z], [row.sx, 0.07, row.sz], [row.rx, 0, 0]);
    box(`seat_mosaic_${row.name}_stripe`, mats.seatWhite, [row.x, row.y + 0.02, row.z], [row.sx * 0.90, 0.03, row.sz * 0.12], [row.rx, 0, 0]);
  });

  const shortRows = [
    { name: 'east_lower', x: pitchBorderW / 2 + lowerFrontGap + 8.2, y: 3.04, z: 0, sx: 10.8, sz: pitchH + 10, rz: -0.44, material: mats.seatBlueDark },
    { name: 'west_lower', x: -(pitchBorderW / 2 + lowerFrontGap + 8.2), y: 3.04, z: 0, sx: 10.8, sz: pitchH + 10, rz: 0.44, material: mats.seatBlueDark },
    { name: 'east_upper', x: pitchBorderW / 2 + upperFrontGapInner + 8.0, y: 8.28, z: 0, sx: 10.0, sz: pitchH + 6, rz: -0.40, material: mats.seatBlue },
    { name: 'west_upper', x: -(pitchBorderW / 2 + upperFrontGapInner + 8.0), y: 8.28, z: 0, sx: 10.0, sz: pitchH + 6, rz: 0.40, material: mats.seatBlue },
  ];
  shortRows.forEach((row) => {
    box(`seat_mosaic_${row.name}`, row.material, [row.x, row.y, row.z], [row.sx, 0.07, row.sz], [0, 0, row.rz]);
    box(`seat_mosaic_${row.name}_stripe`, mats.seatWhite, [row.x, row.y + 0.02, row.z], [row.sx * 0.12, 0.03, row.sz * 0.88], [0, 0, row.rz]);
  });
}

function addLowerBowlCornerSeams() {}

function addPitchsidePremiumEdge() {
  const y = 0.34;
  box('pitchside_edge_north', mats.darkMetal, [0, y, halfH + apron + 0.14], [pitchW + 2.8, 0.18, 0.20]);
  box('pitchside_edge_south', mats.darkMetal, [0, y, -(halfH + apron + 0.14)], [pitchW + 2.8, 0.18, 0.20]);
  box('pitchside_edge_east', mats.darkMetal, [halfW + apron + 0.14, y, 0], [0.20, 0.18, pitchH + 2.8]);
  box('pitchside_edge_west', mats.darkMetal, [-(halfW + apron + 0.14), y, 0], [0.20, 0.18, pitchH + 2.8]);
  box('pitchside_glow_north', mats.ledLine, [0, y + 0.08, halfH + apron + 0.02], [pitchW + 1.2, 0.02, 0.04]);
  box('pitchside_glow_south', mats.ledLine, [0, y + 0.08, -(halfH + apron + 0.02)], [pitchW + 1.2, 0.02, 0.04]);
}

function addRoofInnerTrim() {
  const trimY = upperStartY + upperRows * rowRise + 1.02;
  const innerW = pitchBorderW / 2 + upperFrontGapInner + 7.0;
  const innerH = pitchBorderH / 2 + upperFrontGapInner + 7.0;
  addRingSurface(
    'roof_inner_trim',
    mats.darkMetal,
    trimY,
    innerW + 2.6,
    innerH + 2.6,
    bowlCornerRadius + upperFrontGapInner + 10.0,
    innerW + 1.4,
    innerH + 1.4,
    bowlCornerRadius + upperFrontGapInner + 8.8,
  );
  addRingSurface(
    'roof_inner_trim_led',
    mats.ledLine,
    trimY + 0.04,
    innerW + 1.9,
    innerH + 1.9,
    bowlCornerRadius + upperFrontGapInner + 9.3,
    innerW + 1.6,
    innerH + 1.6,
    bowlCornerRadius + upperFrontGapInner + 9.0,
  );
}

function addCornerGrandstandBowls() {
  const buildCornerRows = (tierName, rows, startY, startGap, rowStep, yLift) => {
    const cornerDefs = [
      { name: 'ne', sx: 1, sz: 1, baseRot: -Math.PI / 4 },
      { name: 'nw', sx: -1, sz: 1, baseRot: Math.PI / 4 },
      { name: 'sw', sx: -1, sz: -1, baseRot: Math.PI * 0.75 },
      { name: 'se', sx: 1, sz: -1, baseRot: -Math.PI * 0.75 },
    ];

    for (let row = 0; row < rows; row += rowStep) {
      const y = startY + row * rowRise + yLift;
      const ringOffset = startGap + row * rowDepth + 2.0;
      const xBase = pitchBorderW / 2 + ringOffset + 3.2;
      const zBase = pitchBorderH / 2 + ringOffset + 3.0;
      const rowMat = row % 5 === 0 ? mats.seatWhite : row % 2 === 0 ? mats.seatBlue : mats.seatBlueDark;
      const rowBackMat = row % 3 === 0 ? mats.seatBlueDark : mats.seatShadow;

      cornerDefs.forEach((corner) => {
        for (let seg = 0; seg < 6; seg += 1) {
          const spread = seg - 2.5;
          const stretch = Math.abs(spread);
          const px = corner.sx * (xBase + Math.max(0, spread) * 2.35);
          const pz = corner.sz * (zBase + Math.max(0, -spread) * 2.15);
          const rotY = corner.baseRot + spread * 0.11;
          const seatLength = 6.4 - stretch * 0.42;
          const backLength = seatLength * 0.84;

          box(
            `${tierName}_corner_row_${row}_${corner.name}_${seg}`,
            rowMat,
            [px, y, pz],
            [seatLength, 0.08, rowDepth * 0.92],
            [corner.sz * 0.10, rotY, 0],
          );
          box(
            `${tierName}_corner_back_${row}_${corner.name}_${seg}`,
            rowBackMat,
            [px, y + 0.15, pz + corner.sz * 0.06],
            [backLength, 0.12, rowDepth * 0.34],
            [corner.sz * 0.28, rotY, 0],
          );
        }
      });
    }
  };

  buildCornerRows('lower', lowerRows, lowerStartY, lowerFrontGap, 1, 0.04);
  buildCornerRows('upper', upperRows, upperStartY, upperFrontGapInner, 1, 0.04);
}

function addCornerSeatTransitions() {
  [
    { name: 'north_east', x: 46, z: pitchBorderH / 2 + lowerFrontGap + 10.8, rx: 0.28 },
    { name: 'north_west', x: -46, z: pitchBorderH / 2 + lowerFrontGap + 10.8, rx: 0.28 },
    { name: 'south_east', x: 46, z: -(pitchBorderH / 2 + lowerFrontGap + 10.8), rx: -0.28 },
    { name: 'south_west', x: -46, z: -(pitchBorderH / 2 + lowerFrontGap + 10.8), rx: -0.28 },
  ].forEach((spec) => {
    box(`seat_transition_${spec.name}`, mats.seatWhite, [spec.x, 3.9, spec.z], [5.2, 0.05, 0.92], [spec.rx, 0, 0]);
  });
}

function addBowlCornerClosureShells() {
  const specs = [
    { name: 'ne', x: 1, z: 1, rot: -Math.PI / 4 },
    { name: 'nw', x: -1, z: 1, rot: Math.PI / 4 },
    { name: 'sw', x: -1, z: -1, rot: Math.PI * 0.75 },
    { name: 'se', x: 1, z: -1, rot: -Math.PI * 0.75 },
  ];
  specs.forEach((spec) => {
    const lowerX = spec.x * (pitchBorderW / 2 + lowerFrontGap + 6.8);
    const lowerZ = spec.z * (pitchBorderH / 2 + lowerFrontGap + 6.2);
    box(`corner_lower_shell_${spec.name}`, mats.seatBlueDark, [lowerX, 2.9, lowerZ], [10.6, 0.16, 8.2], [spec.z * 0.30, spec.rot, 0]);
    box(`corner_lower_shell_trim_${spec.name}`, mats.seatWhite, [lowerX, 2.98, lowerZ], [8.8, 0.04, 0.96], [spec.z * 0.30, spec.rot, 0]);

    const upperX = spec.x * (pitchBorderW / 2 + upperFrontGapInner + 6.1);
    const upperZ = spec.z * (pitchBorderH / 2 + upperFrontGapInner + 5.7);
    box(`corner_upper_shell_${spec.name}`, mats.seatBlue, [upperX, 8.0, upperZ], [9.0, 0.14, 6.8], [spec.z * 0.26, spec.rot, 0]);
    box(`corner_upper_shell_trim_${spec.name}`, mats.seatWhite, [upperX, 8.07, upperZ], [7.4, 0.03, 0.82], [spec.z * 0.26, spec.rot, 0]);
  });
}

function addCornerRoofClosures() {
  const roofY = upperStartY + upperRows * rowRise + 1.28;
  const corners = [
    { name: 'ne', x: 1, z: 1, rot: -Math.PI / 4, tilt: 0.14 },
    { name: 'nw', x: -1, z: 1, rot: Math.PI / 4, tilt: 0.14 },
    { name: 'sw', x: -1, z: -1, rot: Math.PI * 0.75, tilt: -0.14 },
    { name: 'se', x: 1, z: -1, rot: -Math.PI * 0.75, tilt: -0.14 },
  ];
  corners.forEach((corner) => {
    const x = corner.x * 96.0;
    const z = corner.z * 79.2;
    box(`roof_corner_cap_${corner.name}`, mats.roofTop, [x, roofY, z], [18.4, 0.18, 11.4], [corner.tilt, corner.rot, 0]);
    box(`roof_corner_cap_under_${corner.name}`, mats.roofUnderside, [x, roofY - 0.18, z + corner.z * 0.14], [17.2, 0.10, 10.6], [corner.tilt, corner.rot, 0]);
    box(`roof_corner_cap_led_${corner.name}`, mats.ledLine, [x, roofY + 0.06, z], [16.0, 0.04, 0.16], [corner.tilt, corner.rot, 0]);
    cylinder(`roof_corner_curve_${corner.name}`, mats.roofTop, [corner.x * 100.8, roofY + 0.02, corner.z * 84.0], 7.2, 7.2, 0.20, [Math.PI / 2, 0, 0], 40, false, corner.rot - Math.PI / 2, Math.PI / 2);
  });
}

function addPerimeterRetainingWall() {
  const wallY = 0.54;
  const wallH = 0.88;
  box('retaining_north', mats.concreteDark, [0, wallY, halfH + apron + 0.82], [pitchBorderW + 0.8, wallH, 0.34]);
  box('retaining_south', mats.concreteDark, [0, wallY, -(halfH + apron + 0.82)], [pitchBorderW + 0.8, wallH, 0.34]);
  box('retaining_east', mats.concreteDark, [halfW + apron + 1.24, wallY, 0], [0.26, wallH, pitchBorderH + 0.8]);
  box('retaining_west', mats.concreteDark, [-(halfW + apron + 1.24), wallY, 0], [0.26, wallH, pitchBorderH + 0.8]);
  box('track_edge_north', mats.board, [0, 0.44, halfH + apron + 0.38], [pitchBorderW + 0.2, 0.12, 0.16]);
  box('track_edge_south', mats.board, [0, 0.44, -(halfH + apron + 0.38)], [pitchBorderW + 0.2, 0.12, 0.16]);
  box('track_edge_east', mats.board, [halfW + apron + 0.38, 0.44, 0], [0.16, 0.12, pitchBorderH + 0.2]);
  box('track_edge_west', mats.board, [-(halfW + apron + 0.38), 0.44, 0], [0.16, 0.12, pitchBorderH + 0.2]);
}

function addFacadeFinRows() {
  const outerOffset = upperFrontGapOuter + roofOverhang - 1.0;
  const shellHalfW = pitchBorderW / 2 + outerOffset;
  const shellHalfH = pitchBorderH / 2 + outerOffset;
  const baseY = upperStartY + upperRows * rowRise + 0.72;
  for (let i = 0; i < 4; i += 1) {
    const y = baseY + i * 0.56;
    box(`fin_north_${i}`, mats.metal, [0, y, shellHalfH + 0.12], [pitchW + 30 - i * 1.8, 0.06, 0.10]);
    box(`fin_south_${i}`, mats.metal, [0, y, -(shellHalfH + 0.12)], [pitchW + 30 - i * 1.8, 0.06, 0.10]);
    box(`fin_east_${i}`, mats.metal, [shellHalfW + 0.12, y, 0], [0.10, 0.06, pitchH + 22 - i * 1.4]);
    box(`fin_west_${i}`, mats.metal, [-(shellHalfW + 0.12), y, 0], [0.10, 0.06, pitchH + 22 - i * 1.4]);
  }
}

function addRoofCornerShells() {
  const outerOffset = upperFrontGapOuter + roofOverhang - 1.2;
  const shellHalfW = pitchBorderW / 2 + outerOffset;
  const shellHalfH = pitchBorderH / 2 + outerOffset;
  const roofY = upperStartY + upperRows * rowRise + 1.52;
  [
    { name: 'ne', x: 1, z: 1, rot: -Math.PI / 4 },
    { name: 'nw', x: -1, z: 1, rot: Math.PI / 4 },
    { name: 'sw', x: -1, z: -1, rot: Math.PI * 0.75 },
    { name: 'se', x: 1, z: -1, rot: -Math.PI * 0.75 },
  ].forEach((spec) => {
    box(
      `roof_corner_shell_${spec.name}`,
      mats.roofTop,
      [spec.x * (shellHalfW - 2.2), roofY, spec.z * (shellHalfH - 2.2)],
      [10.2, 0.20, 12.8],
      [spec.z * 0.14, spec.rot, 0],
    );
    box(
      `roof_corner_shell_under_${spec.name}`,
      mats.roofUnderside,
      [spec.x * (shellHalfW - 2.2), roofY - 0.24, spec.z * (shellHalfH - 2.2)],
      [9.4, 0.14, 12.0],
      [spec.z * 0.14, spec.rot, 0],
    );
  });
}

function addContinuousOuterEnvelope() {
  const outerOffset = upperFrontGapOuter + roofOverhang - 2.1;
  const shellHalfW = pitchBorderW / 2 + outerOffset;
  const shellHalfH = pitchBorderH / 2 + outerOffset;
  const shellY = upperStartY + upperRows * rowRise + 0.48;
  const shellHeight = 1.92;

  box('shell_north', mats.facade, [0, shellY, shellHalfH], [pitchW + 44, shellHeight, 0.44], [-0.06, 0, 0]);
  box('shell_south', mats.facade, [0, shellY, -shellHalfH], [pitchW + 44, shellHeight, 0.44], [0.06, 0, 0]);
  box('shell_east', mats.facade, [shellHalfW, shellY, 0], [0.44, shellHeight, pitchH + 34], [0, 0, -0.06]);
  box('shell_west', mats.facade, [-shellHalfW, shellY, 0], [0.44, shellHeight, pitchH + 34], [0, 0, 0.06]);

  [[1, 1, Math.PI * 1.5], [-1, 1, Math.PI], [-1, -1, Math.PI * 0.5], [1, -1, 0]].forEach(([sx, sz, theta], idx) => {
    cylinder(`shell_corner_${idx}`, mats.facade, [sx * shellHalfW, shellY, sz * shellHalfH], 6.4, 6.4, shellHeight, [0, 0, 0], 64, false, theta, Math.PI / 2);
  });
}

function addFacadeGlazing() {
  const outerOffset = upperFrontGapOuter + roofOverhang - 2.6;
  const shellHalfW = pitchBorderW / 2 + outerOffset;
  const shellHalfH = pitchBorderH / 2 + outerOffset;
  const glassY = upperStartY + upperRows * rowRise - 0.10;

  box('glass_north', mats.glass, [0, glassY, shellHalfH], [pitchW + 30, 2.8, 0.10]);
  box('glass_south', mats.glass, [0, glassY, -shellHalfH], [pitchW + 30, 2.8, 0.10]);
  box('glass_east', mats.glass, [shellHalfW, glassY, 0], [0.10, 2.8, pitchH + 20]);
  box('glass_west', mats.glass, [-shellHalfW, glassY, 0], [0.10, 2.8, pitchH + 20]);
  box('led_north', mats.ledLine, [0, glassY + 1.42, shellHalfH], [pitchW + 26, 0.08, 0.06]);
  box('led_south', mats.ledLine, [0, glassY + 1.42, -shellHalfH], [pitchW + 26, 0.08, 0.06]);
  box('led_east', mats.ledLine, [shellHalfW, glassY + 1.42, 0], [0.06, 0.08, pitchH + 16]);
  box('led_west', mats.ledLine, [-shellHalfW, glassY + 1.42, 0], [0.06, 0.08, pitchH + 16]);
  [[1, 1, Math.PI * 1.5], [-1, 1, Math.PI], [-1, -1, Math.PI * 0.5], [1, -1, 0]].forEach(([sx, sz, theta], idx) => {
    cylinder(`glass_corner_${idx}`, mats.glass, [sx * shellHalfW, glassY, sz * shellHalfH], 3.2, 3.2, 2.8, [0, 0, 0], 48, false, theta, Math.PI / 2);
    cylinder(`glass_corner_led_${idx}`, mats.ledLine, [sx * shellHalfW, glassY + 1.42, sz * shellHalfH], 3.06, 3.06, 0.08, [0, 0, 0], 40, false, theta, Math.PI / 2);
  });
}

function addFacadeRibbons() {
  const outerOffset = upperFrontGapOuter + roofOverhang - 2.1;
  const shellHalfW = pitchBorderW / 2 + outerOffset;
  const shellHalfH = pitchBorderH / 2 + outerOffset;
  const ribbonY = upperStartY + upperRows * rowRise + 0.18;

  for (let i = 0; i < 6; i += 1) {
    const y = ribbonY + i * 0.26;
    box(`ribbon_north_${i}`, i % 2 === 0 ? mats.facade : mats.metal, [0, y, shellHalfH - i * 0.06], [pitchW + 40 - i * 1.6, 0.06, 0.08], [-0.04, 0, 0]);
    box(`ribbon_south_${i}`, i % 2 === 0 ? mats.facade : mats.metal, [0, y, -(shellHalfH - i * 0.06)], [pitchW + 40 - i * 1.6, 0.06, 0.08], [0.04, 0, 0]);
    box(`ribbon_east_${i}`, i % 2 === 0 ? mats.facade : mats.metal, [shellHalfW - i * 0.06, y, 0], [0.08, 0.06, pitchH + 30 - i * 1.1], [0, 0, -0.04]);
    box(`ribbon_west_${i}`, i % 2 === 0 ? mats.facade : mats.metal, [-(shellHalfW - i * 0.06), y, 0], [0.08, 0.06, pitchH + 30 - i * 1.1], [0, 0, 0.04]);
  }
}

function addRoofCanopyBridges() {
  const outerOffset = upperFrontGapOuter + roofOverhang - 1.0;
  const innerOffset = upperFrontGapInner + 10.8;
  const roofY = upperStartY + upperRows * rowRise + 1.84;

  addRingSurface(
    'roof_clean_plate',
    mats.roofTop,
    roofY,
    pitchBorderW / 2 + outerOffset,
    pitchBorderH / 2 + outerOffset,
    bowlCornerRadius + outerOffset + 5.4,
    pitchBorderW / 2 + innerOffset,
    pitchBorderH / 2 + innerOffset,
    bowlCornerRadius + innerOffset + 2.2,
  );

  addRingSurface(
    'roof_clean_plate_upper',
    mats.roofTop,
    roofY + 0.18,
    pitchBorderW / 2 + outerOffset + 0.8,
    pitchBorderH / 2 + outerOffset + 0.8,
    bowlCornerRadius + outerOffset + 6.2,
    pitchBorderW / 2 + innerOffset + 1.2,
    pitchBorderH / 2 + innerOffset + 1.2,
    bowlCornerRadius + innerOffset + 2.8,
  );

  addRingSurface(
    'roof_clean_under',
    mats.roofUnderside,
    roofY - 0.26,
    pitchBorderW / 2 + outerOffset - 0.6,
    pitchBorderH / 2 + outerOffset - 0.6,
    bowlCornerRadius + outerOffset + 4.8,
    pitchBorderW / 2 + innerOffset + 0.8,
    pitchBorderH / 2 + innerOffset + 0.8,
    bowlCornerRadius + innerOffset + 3.0,
  );

  addRingSurface(
    'roof_shadow_band',
    mats.roofUnderside,
    roofY - 0.42,
    pitchBorderW / 2 + outerOffset - 0.2,
    pitchBorderH / 2 + outerOffset - 0.2,
    bowlCornerRadius + outerOffset + 5.0,
    pitchBorderW / 2 + innerOffset + 2.8,
    pitchBorderH / 2 + innerOffset + 2.8,
    bowlCornerRadius + innerOffset + 4.6,
  );

  const northZ = pitchBorderH / 2 + upperFrontGapInner + 12.6;
  const southZ = -northZ;
  [-42, -18, 18, 42].forEach((x, idx) => {
    box(`roof_rib_north_${idx}`, mats.metal, [x, roofY - 0.08, northZ], [1.1, 0.08, 7.4], [0.24, 0, 0]);
    box(`roof_rib_south_${idx}`, mats.metal, [x, roofY - 0.08, southZ], [1.1, 0.08, 7.4], [-0.24, 0, 0]);
  });

  const eastX = pitchBorderW / 2 + upperFrontGapInner + 12.4;
  const westX = -eastX;
  [-20, 20].forEach((z, idx) => {
    box(`roof_rib_east_${idx}`, mats.metal, [eastX, roofY - 0.08, z], [7.2, 0.08, 1.0], [0, 0, -0.24]);
    box(`roof_rib_west_${idx}`, mats.metal, [westX, roofY - 0.08, z], [7.2, 0.08, 1.0], [0, 0, 0.24]);
  });

  box('roof_fascia_north', mats.roofUnderside, [0, roofY - 0.34, pitchBorderH / 2 + upperFrontGapInner + 8.2], [pitchW + 34, 0.18, 0.56], [0.12, 0, 0]);
  box('roof_fascia_south', mats.roofUnderside, [0, roofY - 0.34, -(pitchBorderH / 2 + upperFrontGapInner + 8.2)], [pitchW + 34, 0.18, 0.56], [-0.12, 0, 0]);
  box('roof_fascia_east', mats.roofUnderside, [pitchBorderW / 2 + upperFrontGapInner + 8.0, roofY - 0.34, 0], [0.56, 0.18, pitchH + 28], [0, 0, -0.12]);
  box('roof_fascia_west', mats.roofUnderside, [-(pitchBorderW / 2 + upperFrontGapInner + 8.0), roofY - 0.34, 0], [0.56, 0.18, pitchH + 28], [0, 0, 0.12]);
  box('roof_led_north', mats.ledLine, [0, roofY - 0.16, pitchBorderH / 2 + upperFrontGapInner + 8.1], [pitchW + 26, 0.03, 0.08], [0.10, 0, 0]);
  box('roof_led_south', mats.ledLine, [0, roofY - 0.16, -(pitchBorderH / 2 + upperFrontGapInner + 8.1)], [pitchW + 26, 0.03, 0.08], [-0.10, 0, 0]);
}

function addBenchPremiumDetails() {
  const z = -(halfH + apron - 0.38);
  [-16.5, 16.5].forEach((x, idx) => {
    box(`bench_glow_strip_${idx}`, mats.ledLine, [x, 0.98, z + 0.12], [5.8, 0.03, 0.04]);
    box(`bench_nameplate_${idx}`, mats.board, [x, 0.22, z - 0.54], [5.6, 0.10, 0.06]);
    box(`bench_base_line_${idx}`, mats.seatWhite, [x, 0.16, z - 0.40], [5.9, 0.02, 0.03]);
    box(`bench_rear_shadow_${idx}`, mats.darkMetal, [x, 0.68, z + 0.66], [6.2, 0.08, 0.03]);
    box(`bench_rear_glass_${idx}`, mats.glass, [x, 0.60, z + 0.56], [6.0, 0.32, 0.03]);
    box(`bench_side_panel_left_${idx}`, mats.glass, [x - 3.10, 0.58, z + 0.12], [0.03, 0.48, 0.82]);
    box(`bench_side_panel_right_${idx}`, mats.glass, [x + 3.10, 0.58, z + 0.12], [0.03, 0.48, 0.82]);
  });
}

function addFacadeAndRoof() {
  box('scoreboard_ribbon_north', mats.board, [0, upperStartY + upperRows * rowRise + 2.22, pitchBorderH / 2 + lowerFrontGap + lowerRows * rowDepth + 1.84], [12.0, 0.28, 0.08]);
  box('scoreboard_ribbon_south', mats.board, [0, upperStartY + upperRows * rowRise + 2.22, -(pitchBorderH / 2 + lowerFrontGap + lowerRows * rowDepth + 1.84)], [12.0, 0.28, 0.08]);
}

function addExteriorPlinth() {
  const plinthOffset = lowerFrontGapOuter + 2.8;
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

function addPitchEdgeShadow() {}

scene.add(new THREE.AmbientLight(0xffffff, 1.08));
const sun = new THREE.DirectionalLight(0xfff1d8, 0.78);
sun.position.set(-90, 130, -60);
scene.add(sun);

addProtectedPitchBase({
  box,
  cylinder,
  plane,
  add,
  THREE,
  mats,
  halfW,
  halfH,
  pitchW,
  pitchH,
  apron,
  pitchBorderW,
  pitchBorderH,
  addRingSurface,
});
addCommercialBowlContinuous();
addRoundedTunnelAndDugouts();
addBenchPremiumDetails();
addPerimeterRetainingWall();
addPitchsidePremiumEdge();
addContinuousOuterEnvelope();
addFacadeGlazing();
addRoofCanopyBridges();
addRoofInnerTrim();
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
