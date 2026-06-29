import fs from 'node:fs/promises';
import path from 'node:path';
import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const inputObj = '/Volumes/Mac Satecchi/Mac/Downloads/uploads-files-5391804-free+seat.obj';
const outputGlb = path.join(repoRoot, 'football/static/football/models/pitch3d/free_seat_real.glb');

async function loadText(filePath) {
  return fs.readFile(filePath, 'utf8');
}

function centerAndScaleSeat(root) {
  const bounds = new THREE.Box3().setFromObject(root);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  bounds.getSize(size);
  bounds.getCenter(center);

  root.position.sub(center);
  root.position.y += size.y * 0.5;

  // Normalize to a plausible stadium seat footprint in meters.
  const targetWidth = 0.58;
  const scale = targetWidth / Math.max(0.0001, size.x);
  root.scale.setScalar(scale);
  root.updateMatrixWorld(true);
}

function restyleMaterials(root) {
  const shellColor = new THREE.Color('#eef4fb');
  const cushionColor = new THREE.Color('#1f63d6');
  const darkColor = new THREE.Color('#0b2f7a');

  root.traverse((node) => {
    if (!node?.isMesh) return;
    const name = String(node.name || '').toLowerCase();
    const sourceMat = Array.isArray(node.material) ? node.material[0] : node.material;
    const baseColor = sourceMat?.color ? sourceMat.color.clone() : new THREE.Color('#cccccc');
    const isCushion = name.includes('seat') || name.includes('pad') || name.includes('back');
    const isFrame = name.includes('leg') || name.includes('base') || name.includes('support') || name.includes('metal');
    const color = isFrame ? darkColor : (isCushion ? cushionColor : shellColor.clone().lerp(baseColor, 0.12));
    node.material = new THREE.MeshStandardMaterial({
      color,
      roughness: isFrame ? 0.48 : 0.64,
      metalness: isFrame ? 0.28 : 0.04,
    });
    node.castShadow = true;
    node.receiveShadow = true;
  });
}

async function parseSeatObject() {
  const objText = await loadText(inputObj);
  const objLoader = new OBJLoader();
  const root = objLoader.parse(objText);
  root.name = 'free_seat_real';
  centerAndScaleSeat(root);
  restyleMaterials(root);
  return root;
}

async function exportGlb(scene) {
  const exporter = new GLTFExporter();
  const arrayBuffer = await new Promise((resolve, reject) => {
    exporter.parse(
      scene,
      (result) => {
        if (result instanceof ArrayBuffer) resolve(result);
        else reject(new Error('Expected binary GLB ArrayBuffer result'));
      },
      (error) => reject(error),
      { binary: true, trs: false, onlyVisible: true },
    );
  });
  await fs.writeFile(outputGlb, Buffer.from(arrayBuffer));
}

const scene = new THREE.Scene();
scene.add(await parseSeatObject());
await exportGlb(scene);
console.log(outputGlb);
