/* eslint-disable no-console */
// Smoke test: editor táctico (tareas + tácticas) debe abrir popovers (Más acciones, Capas, Escenarios, Simulador)
// en iPad-like context (touch) sin quedarse "difuminado sin opciones".
//
// Usage:
//   E2E_BASE_URL=http://127.0.0.1:8012 E2E_USERNAME=smoke E2E_PASSWORD=smoke12345 node scripts/e2e_popovers_smoke.js
const { chromium, webkit } = require('playwright');

function pickBrowserType() {
  const raw = String(process.env.E2E_BROWSER || 'chromium').trim().toLowerCase();
  if (raw === 'webkit' || raw === 'safari') return webkit;
  return chromium;
}

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

async function login(page, baseUrl, username, password) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);
  if (page.url().includes('/login')) throw new Error('Login failed');
}

async function openLandingAndEnter(page) {
  // Landing is disabled in production; keep this helper as a no-op for backwards compat.
  const landing = page.locator('#task-landing');
  if ((await landing.count()) === 0) return;
  if (!(await landing.isVisible().catch(() => false))) return;
  await page.click('.task-landing-close[data-landing-go="close"]').catch(() => null);
  await page.waitForSelector('#task-landing', { state: 'hidden', timeout: 35_000 }).catch(() => null);
}

async function clickPopover(page, trigger, popover, label) {
  await page.waitForSelector(trigger, { state: 'visible', timeout: 35_000 });
  await page.click(trigger);
  await page.waitForSelector(popover, { state: 'attached', timeout: 35_000 });
  // En WebKit/iPad, algunos popovers están `position: fixed/absolute` y Playwright puede tardar
  // en considerarlos "visibles". Esperamos directamente al flag `hidden=false`.
  await page.waitForFunction((sel) => {
    const el = document.querySelector(sel);
    return !!(el && el.hidden === false);
  }, popover, { timeout: 35_000 });

  const box = await page.locator(popover).boundingBox();
  assert(box, `${label}: no boundingBox`);
  const viewport = page.viewportSize();
  assert(viewport, 'missing viewport');
  const inX = (box.x + box.width) > 0 && box.x < viewport.width;
  const inY = (box.y + box.height) > 0 && box.y < viewport.height;
  assert(inX && inY, `${label}: popover fuera de viewport (${JSON.stringify({ box, viewport })})`);

  // Close using the most reliable control (WebKit/iPad quirks with overlay/backdrop and fixed toolbars).
  const closeByPopover = {
    '#task-command-menu': trigger,
    '#task-layers-popover': '#task-layers-close',
    '#task-scenarios-popover': '#task-scenarios-close',
    '#task-sim-popover': '#task-sim-close',
  };
  const closeSelector = closeByPopover[popover] || '';
  if (closeSelector) {
    await page.click(closeSelector, { force: true });
    await page.waitForSelector(popover, { state: 'hidden', timeout: 35_000 });
    return;
  }

  // Fallback: Esc should close any floating menu.
  await page.keyboard.press('Escape').catch(() => null);
  await page.waitForSelector(popover, { state: 'hidden', timeout: 35_000 });
}

async function smokeEditor(page, baseUrl, path, label) {
  await page.goto(`${baseUrl}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#create-task-canvas', { state: 'visible', timeout: 35_000 });
  await openLandingAndEnter(page);

  await clickPopover(page, '#task-command-more', '#task-command-menu', `${label} · Más acciones`);
  await clickPopover(page, '#task-layers-btn', '#task-layers-popover', `${label} · Capas`);
  await clickPopover(page, '#task-scenarios-btn', '#task-scenarios-popover', `${label} · Escenarios`);
  await clickPopover(page, '#task-sim-btn', '#task-sim-popover', `${label} · Simulador`);
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'e2e_coach';
  const password = process.env.E2E_PASSWORD || 'e2e';
  const headless = String(process.env.E2E_HEADLESS || 'true').toLowerCase() !== 'false';

  const browserType = pickBrowserType();
  const browser = await browserType.launch({ headless });
  const context = await browser.newContext({
    viewport: { width: 1024, height: 768 },
    deviceScaleFactor: 2,
    hasTouch: true,
    ignoreHTTPSErrors: true,
    locale: 'es-ES',
  });
  const page = await context.newPage();
  page.setDefaultTimeout(35_000);
  page.setDefaultNavigationTimeout(60_000);

  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err && err.stack ? err.stack : err)));
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text() || '';
    // Headless WebKit en local puede bloquear recursos https externos (sin red) y loguea errores TLS.
    // No son errores funcionales del editor.
    if (/Failed to load resource: A TLS error/i.test(text)) return;
    if (/TypeError: Load failed/i.test(text)) return;
    errors.push(text);
  });

  try {
    await login(page, baseUrl, username, password);

    await smokeEditor(page, baseUrl, '/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1&device=tablet', 'Tareas');
    await smokeEditor(page, baseUrl, '/coach/tactica/?device=tablet', 'Táctica');

    if (errors.length) {
      throw new Error(`JS errors:\n- ${errors.slice(0, 20).join('\n- ')}`);
    }
    console.log('[e2e] OK');
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
  }
}

main().catch((err) => {
  console.error('[e2e] FAIL:', err && err.stack ? err.stack : err);
  process.exit(1);
});
