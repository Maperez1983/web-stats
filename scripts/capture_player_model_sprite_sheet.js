/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'tmp', 'player_model_renders');
const HTML_PATH = path.join(ROOT, 'tmp', 'player_model_sprite_viewer.html');

const FRAMES = [
  { name: 'frame_00', time: 0.0 },
  { name: 'frame_01', time: 0.35 },
  { name: 'frame_02', time: 0.7 },
  { name: 'frame_03', time: 1.05 },
  { name: 'frame_04', time: 1.4 },
  { name: 'frame_05', time: 1.75 },
  { name: 'frame_06', time: 2.1 },
  { name: 'frame_07', time: 2.45 },
  { name: 'frame_08', time: 2.8 },
  { name: 'frame_09', time: 3.15 },
  { name: 'frame_10', time: 3.5 },
  { name: 'frame_11', time: 3.85 },
];

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-angle=swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'],
  });
  const context = await browser.newContext({
    viewport: { width: 1024, height: 1024 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  page.on('console', (msg) => console.log('[console]', msg.type(), msg.text()));
  page.on('pageerror', (error) => console.log('[pageerror]', error.message));
  page.on('requestfailed', (request) => console.log('[requestfailed]', request.url(), request.failure()?.errorText));

  try {
    await page.goto('http://127.0.0.1:8766/tmp/player_model_sprite_viewer.html', { waitUntil: 'load' });
    await page.waitForFunction(() => window.__spriteReady === true || String(window.__spriteReady || '').startsWith('error:'), null, { timeout: 30000 });
    const ready = await page.evaluate(() => window.__spriteReady);
    if (ready !== true) {
      throw new Error(String(ready));
    }

    for (const frame of FRAMES) {
      await page.evaluate((payload) => window.__setPose(payload), { time: frame.time });
      await page.waitForTimeout(60);
      await page.locator('canvas').screenshot({
        path: path.join(OUT_DIR, `${frame.name}.png`),
        omitBackground: true,
      });
    }

    console.log(JSON.stringify({ outDir: OUT_DIR, frames: FRAMES.length }, null, 2));
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
