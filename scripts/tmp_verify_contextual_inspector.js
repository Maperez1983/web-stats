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
  const outPath = path.join(outDir, 'task_builder_contextual_inspector.png');

  const browser = await chromium.launch({ headless: true });
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
      const select = document.getElementById('pitch-grass-select');
      if (select) {
        select.value = 'stadium_native';
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    await page.waitForTimeout(1800);

    await page.click('.resource-tab[data-resource="pro"]').catch(() => null);
    await page.waitForTimeout(350);
    await page.click('[data-material-family-toggle="porterias"]').catch(() => null);
    await page.waitForTimeout(350);
    await page.click('.task-material-family[data-material-family="porterias"] [data-add="goal_futsal"]').catch(() => null);
    await page.waitForTimeout(250);

    const stage = page.locator('#task-pitch-stage');
    const box = await stage.boundingBox();
    if (!box) throw new Error('stage_not_found');

    await page.mouse.click(box.x + box.width * 0.52, box.y + box.height * 0.68);
    await page.waitForTimeout(700);

    const canvasDebug = await page.evaluate(() => {
      const app = window.fabric;
      const stage = document.getElementById('task-pitch-stage');
      const canvases = Array.from(stage?.querySelectorAll('canvas') || []);
      const upper = canvases.find((node) => String(node.className || '').includes('upper-canvas')) || null;
      const lower = canvases.find((node) => String(node.className || '').includes('lower-canvas')) || null;
      const fabricCanvas = app?.Canvas?.activeInstance || null;
      const active = fabricCanvas?.getActiveObject?.() || null;
      const objects = fabricCanvas?.getObjects?.() || [];
      return {
        upperFound: !!upper,
        lowerFound: !!lower,
        objects: objects.length,
        activeKind: active?.data?.kind || active?.type || '',
        activeUid: active?.data?.layer_uid || '',
      };
    }).catch(() => null);

    await page.evaluate(() => {
      const dock = document.getElementById('task-selection-dock');
      if (dock) dock.hidden = false;
    }).catch(() => null);
    await page.waitForTimeout(400);

    const visible = await page.evaluate(() => {
      const dock = document.getElementById('task-selection-dock');
      const toolbar = document.getElementById('task-selection-toolbar');
      const summary = document.getElementById('task-selection-summary');
      const color = document.getElementById('task-color');
      return {
        dockHidden: !!dock?.hidden,
        dockClass: String(dock?.className || ''),
        toolbarHidden: !!toolbar?.hidden,
        summary: String(summary?.textContent || '').trim(),
        colorVisible: !!color && !color.disabled,
      };
    });

    if (visible.dockHidden || visible.toolbarHidden) {
      throw new Error(`contextual_inspector_not_visible: ${JSON.stringify({ visible, canvasDebug })}`);
    }

    await page.screenshot({ path: outPath, fullPage: true });
    console.log(JSON.stringify({ outPath, visible }, null, 2));
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
