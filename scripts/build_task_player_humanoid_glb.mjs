import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';

if (typeof globalThis.FileReader === 'undefined') {
  globalThis.FileReader = class FileReader {
    constructor() {
      this.onloadend = null;
      this.onerror = null;
      this.result = null;
    }

    readAsArrayBuffer(blob) {
      Promise.resolve(blob.arrayBuffer())
        .then((buffer) => {
          this.result = buffer;
          if (typeof this.onloadend === 'function') this.onloadend({ target: this });
        })
        .catch((error) => {
          if (typeof this.onerror === 'function') this.onerror(error);
        });
    }
  };
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'football/static/football/models/avatar/player_humanoid.glb');
const downloads = path.join(process.env.HOME || '/Users/miguelperezrodriguez', 'Downloads/player_humanoid.glb');

const mats = {
  skin: new THREE.MeshStandardMaterial({ name: 'skin_face_arms_legs', color: 0xf2d2b6, roughness: 0.58, metalness: 0.0 }),
  hair: new THREE.MeshStandardMaterial({ name: 'hair', color: 0x172554, roughness: 0.74, metalness: 0.0 }),
  shirt: new THREE.MeshStandardMaterial({ name: 'jersey_shirt_torso', color: 0x047857, roughness: 0.60, metalness: 0.02 }),
  trim: new THREE.MeshStandardMaterial({ name: 'jersey_trim_stripe_number', color: 0xffffff, roughness: 0.66, metalness: 0.01 }),
  shorts: new THREE.MeshStandardMaterial({ name: 'shorts_pants', color: 0x0f172a, roughness: 0.70, metalness: 0.01 }),
  socks: new THREE.MeshStandardMaterial({ name: 'socks', color: 0xffffff, roughness: 0.70, metalness: 0.01 }),
  boots: new THREE.MeshStandardMaterial({ name: 'boots_shoes_cleats', color: 0x0b1020, roughness: 0.56, metalness: 0.06 }),
  eye: new THREE.MeshBasicMaterial({ name: 'eyes_brows_mouth', color: 0x0f172a }),
};

const player = new THREE.Group();
player.name = 'player_humanoid_root';

function mesh(name, geometry, material, position = [0, 0, 0], rotation = [0, 0, 0], scale = [1, 1, 1]) {
  const item = new THREE.Mesh(geometry, material);
  item.name = name;
  item.position.set(...position);
  item.rotation.set(...rotation);
  item.scale.set(...scale);
  item.castShadow = true;
  item.receiveShadow = true;
  player.add(item);
  return item;
}

// Cuerpo atlético en escala real aproximada: pies en y=0, cabeza en y~1.76.
mesh('jersey_torso_athletic_capsule', new THREE.CapsuleGeometry(0.23, 0.54, 8, 22), mats.shirt, [0, 1.02, 0], [0, 0, 0], [1.18, 1.05, 0.72]);
mesh('jersey_chest_panel', new THREE.BoxGeometry(0.38, 0.42, 0.045), mats.trim, [0, 1.06, -0.19]);
mesh('jersey_collar_ring', new THREE.TorusGeometry(0.095, 0.011, 8, 24), mats.trim, [0, 1.31, -0.035], [Math.PI / 2, 0, 0], [1.35, 0.55, 1]);
[-0.13, 0.13].forEach((x) => mesh(`jersey_front_seam_${x > 0 ? 'r' : 'l'}`, new THREE.BoxGeometry(0.027, 0.40, 0.052), mats.trim, [x, 1.05, -0.205]));
mesh('shorts_pants_body', new THREE.CylinderGeometry(0.245, 0.285, 0.20, 22), mats.shorts, [0, 0.66, 0], [0, 0, 0], [1.04, 1, 0.82]);

mesh('skin_neck', new THREE.CylinderGeometry(0.062, 0.072, 0.12, 14), mats.skin, [0, 1.38, 0]);
mesh('skin_head_face', new THREE.SphereGeometry(0.18, 32, 24), mats.skin, [0, 1.58, -0.005], [0, 0, 0], [0.92, 1.10, 0.92]);
mesh('hair_cap', new THREE.SphereGeometry(0.184, 28, 12, 0, Math.PI * 2, 0, Math.PI * 0.50), mats.hair, [0, 1.69, -0.006], [Math.PI, 0, 0], [0.96, 0.60, 0.96]);
[-0.145, 0.145].forEach((x) => mesh(`skin_ear_${x > 0 ? 'r' : 'l'}`, new THREE.SphereGeometry(0.037, 12, 8), mats.skin, [x, 1.58, 0.002], [0, 0, 0], [0.62, 1.08, 0.34]));
[-0.050, 0.050].forEach((x) => mesh(`eye_${x > 0 ? 'r' : 'l'}`, new THREE.SphereGeometry(0.014, 10, 8), mats.eye, [x, 1.595, -0.164], [0, 0, 0], [1.0, 0.72, 0.34]));
mesh('skin_nose', new THREE.ConeGeometry(0.026, 0.082, 10, 1), mats.skin, [0, 1.565, -0.178], [-Math.PI / 2, 0, 0]);
mesh('mouth', new THREE.BoxGeometry(0.060, 0.008, 0.010), mats.eye, [0, 1.515, -0.173]);

mesh('jersey_shoulder_bar', new THREE.CapsuleGeometry(0.075, 0.43, 6, 14), mats.shirt, [0, 1.28, -0.005], [0, 0, Math.PI / 2], [1, 1, 0.72]);
[
  [-1, -0.28],
  [1, 0.28],
].forEach(([side, rot]) => {
  const sx = side < 0 ? 'l' : 'r';
  mesh(`jersey_sleeve_${sx}`, new THREE.CapsuleGeometry(0.055, 0.18, 5, 12), mats.shirt, [side * 0.265, 1.17, -0.012], [0, 0, rot * 0.62]);
  mesh(`skin_forearm_${sx}`, new THREE.CapsuleGeometry(0.041, 0.32, 6, 12), mats.skin, [side * 0.33, 0.98, -0.020], [0, 0, rot]);
  mesh(`skin_hand_${sx}`, new THREE.SphereGeometry(0.052, 14, 10), mats.skin, [side * 0.435, 0.84, -0.020]);
});

[-0.105, 0.105].forEach((x) => {
  const side = x < 0 ? 'l' : 'r';
  mesh(`shorts_thigh_${side}`, new THREE.CapsuleGeometry(0.062, 0.30, 6, 12), mats.shorts, [x, 0.48, 0], [0, 0, x < 0 ? 0.06 : -0.06]);
  mesh(`skin_knee_${side}`, new THREE.SphereGeometry(0.050, 12, 10), mats.skin, [x, 0.315, -0.012], [0, 0, 0], [1, 0.62, 0.75]);
  mesh(`socks_lower_leg_${side}`, new THREE.CapsuleGeometry(0.045, 0.29, 5, 10), mats.socks, [x, 0.18, 0]);
  mesh(`boots_shoes_cleats_${side}`, new THREE.BoxGeometry(0.155, 0.060, 0.275), mats.boots, [x, 0.025, -0.065], [-0.08, 0, 0]);
  mesh(`boots_studs_${side}`, new THREE.BoxGeometry(0.125, 0.012, 0.175), mats.trim, [x, -0.015, -0.065]);
});

// Pequeña flecha integrada para que el usuario entienda la orientación del jugador.
mesh('orientation_boot_shadow', new THREE.ConeGeometry(0.065, 0.25, 12, 1), new THREE.MeshStandardMaterial({ name: 'orientation_marker', color: 0x22c55e, roughness: 0.55, metalness: 0.02 }), [0, 0.10, -0.42], [-Math.PI / 2, 0, 0]);

player.traverse((node) => {
  if (node.isMesh) {
    node.geometry.computeVertexNormals();
    node.userData.kind = node.name;
  }
});

const scene = new THREE.Scene();
scene.name = 'task_player_humanoid_scene';
scene.add(player);

const exporter = new GLTFExporter();
const arrayBuffer = await exporter.parseAsync(scene, { binary: true, trs: true });
const buffer = Buffer.from(arrayBuffer);

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, buffer);
fs.writeFileSync(downloads, buffer);

console.log(out);
console.log(downloads);
