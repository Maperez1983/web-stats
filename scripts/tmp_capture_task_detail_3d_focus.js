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
  const password = process.env.E2E_PASSWORD || 'admin1234';
  const taskId = process.env.E2E_TASK_ID || '376';
  const outDir = process.env.E2E_OUT_DIR || path.join(process.cwd(), 'tmp', 'detail-3d-focus');

  const browser = await chromium.launch({
    headless: true,
    args: ['--enable-gpu', '--use-angle=metal'],
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 2200 },
    deviceScaleFactor: 1,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  page.on('console', (msg) => console.log(`[console:${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => console.log(`[pageerror] ${err && err.stack ? err.stack : err}`));

  try {
    const ok = await login(page, baseUrl, username, password);
    if (!ok) throw new Error('login_failed');

    await page.goto(`${baseUrl}/coach/sesiones/tarea/${taskId}/?tab=presentation&format=club`, { waitUntil: 'domcontentloaded' });
    const card = page.locator('#task-detail-3d-inline');
    try {
      await card.waitFor({ state: 'visible', timeout: 60000 });
    } catch (error) {
      const fs = require('fs');
      const failHtml = path.join(outDir, `task-${taskId}-3d-focus-fail.html`);
      const failShot = path.join(outDir, `task-${taskId}-3d-focus-fail.png`);
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(failHtml, await page.content(), 'utf8');
      await page.screenshot({ path: failShot, fullPage: true }).catch(() => null);
      throw error;
    }
    await card.scrollIntoViewIfNeeded();
    await page.waitForTimeout(5000);
    const canvas = page.locator('#task-detail-3d-canvas');
    await canvas.waitFor({ state: 'visible', timeout: 30000 });
    await page.waitForTimeout(4000);

    const outPath = path.join(outDir, `task-${taskId}-3d-focus.png`);
    await card.screenshot({ path: outPath });

    const diagnostics = await page.evaluate(() => {
      const canvasEl = document.getElementById('task-detail-3d-canvas');
      return {
        version: window.__taskDetail3DStadiumVersion || null,
        presentationMode: window.__taskDetail3DPresentationMode || null,
        rect: canvasEl ? canvasEl.getBoundingClientRect().toJSON() : null,
      };
    });
    console.log(JSON.stringify({ outPath, diagnostics }, null, 2));
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
