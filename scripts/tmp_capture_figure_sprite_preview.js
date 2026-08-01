/* eslint-disable no-console */
const path = require('path');
const { chromium } = require('playwright');

async function main() {
  const htmlPath = path.resolve(__dirname, '..', 'tmp', 'figure_sprite_preview.html');
  const outPath = '/Volumes/Mac Satecchi/Mac/Downloads/muestra_figura_sprite_v4.png';

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-angle=swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'],
  });
  const context = await browser.newContext({
    viewport: { width: 1700, height: 1000 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);

  try {
    await page.goto(`file://${htmlPath}`, { waitUntil: 'load' });
    await page.screenshot({ path: outPath });
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
