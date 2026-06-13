import fs from 'node:fs';
import https from 'node:https';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const fallbackSourceUrl = 'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Xbot.glb';
const sourceUrl = String(process.env.TASK_PLAYER_MODEL_SOURCE_URL || fallbackSourceUrl).trim();
const sourceFile = String(process.env.TASK_PLAYER_MODEL_SOURCE_FILE || '').trim();
const out = path.join(root, 'football/static/football/models/avatar/player_humanoid.glb');
const downloads = path.join(process.env.HOME || '/Users/miguelperezrodriguez', 'Downloads/player_humanoid.glb');

const download = (url) => new Promise((resolve, reject) => {
  https.get(url, (response) => {
    if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
      response.resume();
      download(response.headers.location).then(resolve, reject);
      return;
    }
    if (response.statusCode !== 200) {
      reject(new Error(`download_failed:${response.statusCode}:${url}`));
      response.resume();
      return;
    }
    const chunks = [];
    response.on('data', (chunk) => chunks.push(chunk));
    response.on('end', () => resolve(Buffer.concat(chunks)));
  }).on('error', reject);
});

const buffer = sourceFile
  ? fs.readFileSync(path.resolve(sourceFile))
  : await download(sourceUrl);
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, buffer);
fs.writeFileSync(downloads, buffer);

console.log(`source: ${sourceFile || sourceUrl}`);
console.log(out);
console.log(downloads);
