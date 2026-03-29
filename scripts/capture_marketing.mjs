import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseURL = process.env.CAPTURE_BASE_URL || 'http://127.0.0.1:8000';
const username = process.env.CAPTURE_USERNAME || 'capturebot';
const password = process.env.CAPTURE_PASSWORD || 'capture1234';
const outDir = path.resolve('football/static/football/images/marketing');

await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1.5 });

async function waitForStable() {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1200);
}

async function saveShot(name, targetPath) {
  await page.goto(`${baseURL}${targetPath}`, { waitUntil: 'domcontentloaded' });
  await waitForStable();
  console.log(`capture ${name} -> ${page.url()}`);
  await page.screenshot({ path: path.join(outDir, name), fullPage: true });
}

await page.goto(`${baseURL}/login/`, { waitUntil: 'domcontentloaded' });
await page.fill('#id_username', username);
await page.fill('#id_password', password);
await page.getByRole('button', { name: /entrar/i }).click();
await page.waitForURL((url) => !url.pathname.endsWith('/login/') && !url.pathname.endsWith('/login'), { timeout: 15000 }).catch(() => {});
await waitForStable();
console.log(`logged-in -> ${page.url()}`);

await saveShot('club-home.png', '/');
await saveShot('live-actions.png', '/registro-acciones/');
await saveShot('task-studio-home.png', '/task-studio/');
await saveShot('player-dashboard.png', '/players/');
await saveShot('platform-overview.png', '/platform/');

await browser.close();
console.log(`Saved screenshots in ${outDir}`);
