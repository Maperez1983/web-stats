import { chromium } from 'playwright';

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8000';
const USERNAME = process.env.E2E_USER || 'e2e';
const PASSWORD = process.env.E2E_PASS || 'e2e';

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

async function applyTemplate(page, templateKey) {
  await page.locator('canvas.upper-canvas').first().waitFor({ state: 'attached', timeout: 20000 });
  const ok = await page.evaluate((key) => {
    const fn = window.__webstatsTaskBuilderApplyLocalTemplate;
    if (typeof fn !== 'function') return false;
    return !!fn(key);
  }, templateKey);
  assert(ok, `No se pudo aplicar la plantilla ${templateKey}`);
  await page.waitForTimeout(1200);
}

async function getCanvasObjectCount(page, draftKey) {
  return page.evaluate((key) => {
    const rawDraft = window.localStorage.getItem(key) || '';
    if (!rawDraft) return 0;
    try {
      const draft = JSON.parse(rawDraft);
      const state = JSON.parse(String(draft?.fields?.draw_canvas_state || '{}'));
      return Array.isArray(state?.objects) ? state.objects.length : 0;
    } catch (error) {
      return -1;
    }
  }, draftKey);
}

async function assertObjectCount(page, draftKey, expected, label) {
  await page.waitForTimeout(800);
  const count = await getCanvasObjectCount(page, draftKey);
  assert(count === expected, `${label}: se esperaban ${expected} objetos y hay ${count}`);
}

async function toggleOrientation(page) {
  const button = page.locator('#pitch-orientation-toggle, #pitch-orientation-toggle-quick').first();
  await button.waitFor({ state: 'visible', timeout: 20000 });
  await button.click({ force: true });
  await page.waitForTimeout(1200);
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--enable-gpu', '--use-angle=metal'],
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
    deviceScaleFactor: 1.25,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);

  const consoleErrors = [];
  page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err?.message || String(err)}`));
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text() || '';
    if (/Failed to load resource: A TLS error/i.test(text)) return;
    if (/Failed to load resource: the server responded with a status of 400 \(Bad Request\)/i.test(text)) return;
    if (/TypeError: Load failed/i.test(text)) return;
    consoleErrors.push(`console.error: ${text}`);
  });
  page.on('response', (response) => {
    const status = Number(response.status()) || 0;
    if (status < 400) return;
    const url = response.url() || '';
    if (url.includes('/dictionary/')) return;
    if (url.includes('/notifications/')) return;
    if (url.includes('/api/workspace/preferences/get/?key=kit2d.tokens')) return;
    consoleErrors.push(`http.${status}: ${url}`);
  });

  await page.goto(`${BASE_URL}/login/?next=/coach/sesiones/tareas/nueva/`, { waitUntil: 'domcontentloaded' });
  await page.locator('#id_username').fill(USERNAME);
  await page.locator('#id_password').fill(PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL('**/coach/sesiones/tareas/nueva/**', { timeout: 20000 });

  // Espera a que el editor esté listo.
  await page.locator('#create-task-canvas').waitFor({ state: 'visible' });
  const basePanelSelector = '.resource-panel[data-panel="base"]:not([hidden])';
  await page.waitForSelector(basePanelSelector, { timeout: 12000 }).catch(() => null);
  if (!(await page.locator(basePanelSelector).count())) {
    const baseTab = page.locator('button.resource-tab[data-resource="base"]').first();
    if (await baseTab.count()) {
      await baseTab.click({ force: true });
      await page.waitForSelector(basePanelSelector, { timeout: 12000 }).catch(() => null);
    }
  }
  await page.waitForTimeout(350);
  const draftKey = await page
    .$eval('#task-builder-form', (el) => (el && el.dataset ? String(el.dataset.draftKey || '') : ''))
    .catch(() => '');
  assert(draftKey, 'No se encontró data-draft-key en el formulario');

  await applyTemplate(page, 'formation_433');
  await assertObjectCount(page, draftKey, 11, 'Tras aplicar la formacion 4-3-3');

  await toggleOrientation(page);
  await assertObjectCount(page, draftKey, 11, 'Tras rotar a vertical');

  await applyTemplate(page, 'zone_14');
  await assertObjectCount(page, draftKey, 13, 'Tras anadir zona y texto');

  await toggleOrientation(page);
  await assertObjectCount(page, draftKey, 13, 'Tras volver a horizontal');

  if (consoleErrors.length) {
    throw new Error(`Se detectaron errores JS durante la prueba:\n- ${consoleErrors.join('\n- ')}`);
  }

  await browser.close();
  console.log('OK: la rotación del editor mantiene los elementos colocados.');
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});
