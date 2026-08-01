/* eslint-disable no-console */
const path = require('path');
const fs = require('fs');
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
  const username = process.env.E2E_USERNAME || 'admin';
  const password = process.env.E2E_PASSWORD || 'admin1234';
  const taskId = process.env.E2E_TASK_ID || '90';
  const outDir = process.env.E2E_OUT_DIR || path.join(process.cwd(), 'artifacts', 'tmp-verify-task-detail-3d');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--enable-gpu', '--use-angle=metal'],
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1400 },
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

    await page.goto(`${baseUrl}/coach/sesiones/tarea/${taskId}/`, { waitUntil: 'domcontentloaded' });
    const canvasFound = await page.waitForSelector('#task-detail-3d-canvas', { state: 'attached', timeout: 15000 }).then(() => true).catch(() => false);
    await page.waitForTimeout(3000);
    await page.evaluate(() => {
      const panel = document.querySelector('[data-task-tab-panel="presentation"]') || document.body;
      panel.scrollIntoView({ block: 'start' });
    }).catch(() => null);
    await page.waitForTimeout(1000);

    const state = await page.evaluate(() => {
      const canvas = document.getElementById('task-detail-3d-canvas');
      const fallback = document.getElementById('task-detail-3d-fallback');
      return {
        version: window.__taskDetail3DStadiumVersion || null,
        canvasVisible: !!(canvas && !canvas.hidden),
        canvasRect: canvas ? canvas.getBoundingClientRect().toJSON() : null,
        fallbackVisible: !!(fallback && !fallback.hidden),
      };
    });

    const card = page.locator('.sim-3d-card').first();
    const cardPath = path.join(outDir, 'task-detail-3d-card.png');
    if (await card.count()) {
      await card.screenshot({ path: cardPath });
    }

    const pagePath = path.join(outDir, 'task-detail-page.png');
    await page.screenshot({ path: pagePath, fullPage: false });
    const htmlPath = path.join(outDir, 'task-detail-page.html');
    fs.writeFileSync(htmlPath, await page.content(), 'utf8');

    console.log(JSON.stringify({ canvasFound, state, cardPath, pagePath, htmlPath, pageUrl: page.url() }, null, 2));
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
