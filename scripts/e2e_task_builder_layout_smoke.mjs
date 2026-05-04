import { chromium, webkit } from 'playwright';

const BASE_URL = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const USERNAME = process.env.E2E_USERNAME || process.env.E2E_USER || 'e2e';
const PASSWORD = process.env.E2E_PASSWORD || process.env.E2E_PASS || 'e2e';
const HEADLESS = String(process.env.E2E_HEADLESS || 'true').toLowerCase() !== 'false';

function pickBrowserType() {
  const raw = String(process.env.E2E_BROWSER || 'webkit').trim().toLowerCase();
  if (raw === 'chromium' || raw === 'chrome') return chromium;
  return webkit;
}

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

async function login(page) {
  await page.goto(`${BASE_URL}/login/`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[name="username"]').fill(USERNAME);
  await page.locator('input[name="password"]').fill(PASSWORD);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('button[type="submit"], input[type="submit"]').click(),
  ]);
  if (page.url().includes('/login')) throw new Error('Login failed');
}

async function ensureEditorReady(page) {
  await page.locator('#create-task-canvas').waitFor({ state: 'visible', timeout: 35_000 });
  // Landing puede estar activa en dev.
  const landing = page.locator('#task-landing');
  if ((await landing.count()) && (await landing.isVisible().catch(() => false))) {
    await page.locator('.task-landing-close[data-landing-go="close"]').click().catch(() => null);
    await landing.waitFor({ state: 'hidden', timeout: 35_000 }).catch(() => null);
  }
}

async function assertVisibleInViewport(page, selector, label) {
  await page.locator(selector).first().waitFor({ state: 'visible', timeout: 35_000 });
  const box = await page.locator(selector).first().boundingBox();
  assert(box, `${label}: no boundingBox`);
  const viewport = page.viewportSize();
  assert(viewport, 'missing viewport');
  const inX = (box.x + box.width) > 0 && box.x < viewport.width;
  const inY = (box.y + box.height) > 0 && box.y < viewport.height;
  assert(inX && inY, `${label}: fuera de viewport (${JSON.stringify({ box, viewport })})`);
}

async function assertLayout(page, modeLabel) {
  // 1) Toolbar superior debe ser usable.
  await assertVisibleInViewport(page, '#surface-trigger', `${modeLabel} · Superficie`);
  await assertVisibleInViewport(page, '#pitch-view-menu summary', `${modeLabel} · Vista`);
  await assertVisibleInViewport(page, '#task-focus-toggle', `${modeLabel} · Presentación`);

  // 2) Recursos: el panel debe existir y ser accesible (aunque esté colapsado).
  await page.locator('#task-library-toggle').waitFor({ state: 'attached', timeout: 35_000 });
  await page.evaluate(() => {
    try { window.__webstatsTpadSetLibraryCollapsed?.(false); } catch {}
  });
  await page.waitForTimeout(250);
  await assertVisibleInViewport(page, '#task-resource-details', `${modeLabel} · Recursos`);

  // 3) Estructura: en landscape suele ser lateral; en portrait esperamos recursos abajo.
  const pitchBox = await page.locator('#task-pitch-viewport').boundingBox();
  const sideBox = await page.locator('.pitch-side').boundingBox();
  if (pitchBox && sideBox) {
    const portrait = (page.viewportSize()?.height || 0) > (page.viewportSize()?.width || 0);
    if (portrait) {
      assert(sideBox.y > pitchBox.y, `${modeLabel}: recursos deberían ir debajo (portrait)`);
    } else {
      assert(sideBox.x >= pitchBox.x, `${modeLabel}: recursos deberían estar a la derecha (landscape)`);
    }
  }
}

async function main() {
  const browserType = pickBrowserType();
  const browser = await browserType.launch({ headless: HEADLESS });
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
    if (/Failed to load resource: A TLS error/i.test(text)) return;
    if (/TypeError: Load failed/i.test(text)) return;
    errors.push(text);
  });

  try {
    await login(page);
    await page.goto(`${BASE_URL}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1&device=tablet`, { waitUntil: 'domcontentloaded' });
    await ensureEditorReady(page);

    await assertLayout(page, 'iPad landscape');

    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(900);
    await assertLayout(page, 'iPad portrait');

    if (errors.length) throw new Error(`JS errors:\n- ${errors.slice(0, 20).join('\n- ')}`);
    console.log('[e2e] OK: layout task builder (iPad portrait/landscape)');
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

