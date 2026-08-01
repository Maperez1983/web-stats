/* eslint-disable no-console */
const path = require('path');
const { chromium } = require('playwright');

async function main() {
  const outPath = '/Volumes/Mac Satecchi/Mac/Downloads/muestra_avatar_render_v1.png';

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-angle=swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'],
  });
  const context = await browser.newContext({
    viewport: { width: 900, height: 1200 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);

  try {
    await page.goto('http://127.0.0.1:8765/tmp/avatar_render_preview.html', { waitUntil: 'load' });
    await page.waitForFunction(() => window.__avatarReady === true || window.__avatarReady === 'error', null, { timeout: 15000 });
    const status = await page.evaluate(() => window.__avatarReady);
    if (status !== true) throw new Error(`avatar_render_failed:${status}`);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: outPath, omitBackground: false });
    console.log(JSON.stringify({ outPath }, null, 2));
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
