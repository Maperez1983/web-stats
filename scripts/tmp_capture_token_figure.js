/* eslint-disable no-console */
const path = require('path');
const { chromium } = require('playwright');

async function login(page, baseUrl, username, password) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  if (!/\/login\/?/.test(page.url())) return true;
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  return !/\/login\/?/.test(page.url());
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'localadmin';
  const password = process.env.E2E_PASSWORD || 'localadmin';
  const outDir = process.env.E2E_OUT_DIR || '/Volumes/Mac Satecchi/Mac/Downloads';
  const outPath = path.join(outDir, 'task_builder_token_figure_sample.png');

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-angle=swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'],
  });
  const context = await browser.newContext({
    viewport: { width: 1720, height: 1180 },
    deviceScaleFactor: 2,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);

  try {
    const ok = await login(page, baseUrl, username, password);
    if (!ok) throw new Error('login_failed');

    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#task-pitch-stage', { state: 'visible' });
    await page.waitForFunction(() => window.__WEBSTATS_TPAD_READY === true, null, { timeout: 15000 }).catch(() => null);
    await page.waitForTimeout(1200);

    await page.evaluate(() => {
      try { window.localStorage.setItem('webstats:tpad:token-style', 'figure'); } catch (e) { /* ignore */ }
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#task-pitch-stage', { state: 'visible' });
    await page.waitForFunction(() => window.__WEBSTATS_TPAD_READY === true, null, { timeout: 15000 }).catch(() => null);
    await page.waitForTimeout(1200);

    const placed = await page.evaluate(() => {
      const world = { w: 1200, h: 720 };
      const rows = [
        { kind: 'goalkeeper_local', name: '1', number: '1', left: world.w * 0.50, top: world.h * 0.83, facing_deg: 0 },
        { kind: 'player_local', name: '2', number: '2', left: world.w * 0.26, top: world.h * 0.67, facing_deg: -10 },
        { kind: 'player_local', name: '5', number: '5', left: world.w * 0.41, top: world.h * 0.66, facing_deg: -4 },
        { kind: 'player_local', name: '6', number: '6', left: world.w * 0.59, top: world.h * 0.66, facing_deg: 6 },
        { kind: 'player_local', name: '3', number: '3', left: world.w * 0.74, top: world.h * 0.67, facing_deg: 10 },
        { kind: 'player_local', name: '8', number: '8', left: world.w * 0.34, top: world.h * 0.48, facing_deg: -12 },
        { kind: 'player_local', name: '10', number: '10', left: world.w * 0.50, top: world.h * 0.45, facing_deg: 0 },
        { kind: 'player_local', name: '7', number: '7', left: world.w * 0.66, top: world.h * 0.48, facing_deg: 14 },
        { kind: 'player_local', name: '9', number: '9', left: world.w * 0.50, top: world.h * 0.28, facing_deg: 0 },
      ];
      return rows
        .map((item) => window.__webstatsTpadPlaceToken?.({ ...item, style: 'figure' }))
        .filter(Boolean)
        .length;
    });
    if (!placed) throw new Error('figure_tokens_not_placed');

    await page.keyboard.press('Escape').catch(() => null);
    await page.waitForTimeout(600);
    await page.evaluate(() => {
      const closeBtn = document.querySelector('.tpad-selection-dock__close, [data-selection-dock-close], .contextual-selection-dock__close');
      if (closeBtn) closeBtn.click();
    }).catch(() => null);
    await page.waitForTimeout(700);
    await page.locator('#task-pitch-stage').screenshot({ path: outPath });
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
