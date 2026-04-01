/* eslint-disable no-console */
const { chromium, firefox, webkit } = require('playwright');
const { spawn } = require('child_process');
const http = require('http');

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve({ status: res.statusCode || 0 });
    });
    req.on('error', reject);
    req.setTimeout(5000, () => {
      req.destroy(new Error('timeout'));
    });
  });
}

async function waitForServer(baseUrl, { timeoutMs = 60_000 } = {}) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await httpGet(`${baseUrl}/login/`);
      if (res.status >= 200 && res.status < 500) return true;
    } catch (err) {
      // ignore
    }
    await wait(500);
  }
  return false;
}

function extractFirstObjectOfKind(state, kind) {
  const objects = state && Array.isArray(state.objects) ? state.objects : [];
  for (const obj of objects) {
    if (!obj) continue;
    const k = obj.data && typeof obj.data === 'object' ? String(obj.data.kind || '') : '';
    if (k === kind) return obj;
  }
  return null;
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'localadmin';
  const password = process.env.E2E_PASSWORD || 'localadmin';
  const browserName = String(process.env.E2E_BROWSER || 'webkit').toLowerCase();
  const headless = String(process.env.E2E_HEADLESS || 'true').toLowerCase() !== 'false';

  const env = {
    ...process.env,
    DEBUG: 'true',
    SECRET_KEY: process.env.SECRET_KEY || 'dev',
    BOOTSTRAP_ADMIN_USERNAME: username,
    BOOTSTRAP_ADMIN_PASSWORD: password,
    BOOTSTRAP_ADMIN_EMAIL: process.env.BOOTSTRAP_ADMIN_EMAIL || 'localadmin@example.com',
    BOOTSTRAP_ADMIN_RESET_PASSWORD: 'true',
  };

  console.log(`[e2e] baseUrl=${baseUrl} browser=${browserName}`);

  // 1) migrate (crea/actualiza DB + bootstrap admin)
  await new Promise((resolve, reject) => {
    const proc = spawn('python3', ['manage.py', 'migrate', '--noinput'], {
      cwd: process.cwd(),
      env,
      stdio: 'inherit',
    });
    proc.on('exit', (code) => {
      if (code === 0) resolve(true);
      else reject(new Error(`migrate failed: ${code}`));
    });
  });

  // 2) start server
  const serverProc = spawn('python3', ['manage.py', 'runserver', '8000'], {
    cwd: process.cwd(),
    env,
    stdio: 'inherit',
  });

  const serverOk = await waitForServer(baseUrl, { timeoutMs: 90_000 });
  if (!serverOk) {
    serverProc.kill('SIGTERM');
    throw new Error('Server did not start');
  }

  // 3) run browser test
  let browserType = webkit;
  if (browserName === 'chromium') browserType = chromium;
  if (browserName === 'firefox') browserType = firefox;

  const browser = await browserType.launch({ headless });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  page.setDefaultNavigationTimeout(60_000);

  try {
    // login
    await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.click('button[type="submit"]'),
    ]);
    if (page.url().includes('/login')) throw new Error('Login failed');

    // open editor
    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#create-task-canvas', { timeout: 30_000 });
    const draftKey = await page
      .$eval('#task-builder-form', (el) => (el && el.dataset ? String(el.dataset.draftKey || '') : ''))
      .catch(() => '');
    if (!draftKey) throw new Error('No se encontró data-draft-key en el form');
    // Espera a que el JS del editor active el panel "base" (por defecto en escritorio).
    const basePanelSelector = '.resource-panel[data-panel="base"]:not([hidden])';
    await page.waitForSelector(basePanelSelector, { timeout: 12_000 }).catch(() => null);

    // open resources + base (desktop muestra pestañas; móvil usa <summary>)
    const baseTab = page.locator('button.resource-tab[data-resource="base"]');
    // Si el panel base no está visible todavía, lo activamos explícitamente.
    if (!(await page.locator(basePanelSelector).count())) {
      if (await baseTab.isVisible()) {
        await baseTab.click();
      } else {
        await page.click('#task-resource-details > summary');
        await baseTab.click();
      }
      await page.waitForSelector(basePanelSelector, { timeout: 12_000 }).catch(() => null);
    }
    // No hacemos click extra si ya está activo, porque el tab alterna (y podría cerrarlo).

    // place a cone (Fabric recibe input sobre el canvas superior)
    await page.click('#task-basic-tools button[data-add="cone"]');
    const canvas = page.locator('#task-pitch-stage canvas.upper-canvas');
    await canvas.click({ position: { x: 260, y: 220 } });
    // Espera al autosave del borrador (900ms debounce).
    await page.waitForTimeout(1200);

    const stateAfterAddRaw = await page.evaluate((key) => window.localStorage.getItem(key) || '', draftKey);
    const draftAfterAdd = JSON.parse(stateAfterAddRaw || '{}');
    const canvasStateAfterAdd = JSON.parse(String(draftAfterAdd?.fields?.draw_canvas_state || '{}'));
    const stateAfterAdd = canvasStateAfterAdd;
    const coneAfterAdd = extractFirstObjectOfKind(stateAfterAdd, 'cone');
    if (!coneAfterAdd) throw new Error('Cone not found after add');
    const beforeLeft = Number(coneAfterAdd.left);
    const beforeTop = Number(coneAfterAdd.top);
    if (!Number.isFinite(beforeLeft) || !Number.isFinite(beforeTop)) throw new Error('Invalid cone coords after add');

    // drag it
    const box = await canvas.boundingBox();
    if (!box) throw new Error('No canvas bounding box');
    const startX = box.x + 260;
    const startY = box.y + 220;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 120, startY + 60, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(1200);

    const stateAfterDragRaw = await page.evaluate((key) => window.localStorage.getItem(key) || '', draftKey);
    const draftAfterDrag = JSON.parse(stateAfterDragRaw || '{}');
    const canvasStateAfterDrag = JSON.parse(String(draftAfterDrag?.fields?.draw_canvas_state || '{}'));
    const stateAfterDrag = canvasStateAfterDrag;
    const coneAfterDrag = extractFirstObjectOfKind(stateAfterDrag, 'cone');
    if (!coneAfterDrag) throw new Error('Cone not found after drag');
    const afterLeft = Number(coneAfterDrag.left);
    const afterTop = Number(coneAfterDrag.top);

    const dx = Math.abs(afterLeft - beforeLeft);
    const dy = Math.abs(afterTop - beforeTop);
    console.log(`[e2e] cone moved dx=${dx.toFixed(2)} dy=${dy.toFixed(2)}`);
    if (dx + dy <= 10) throw new Error(`Cone did not move (dx=${dx} dy=${dy})`);

    console.log('[e2e] OK');
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
    serverProc.kill('SIGTERM');
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
