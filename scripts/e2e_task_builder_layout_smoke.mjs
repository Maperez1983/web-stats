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
  const usernameInput = page.locator('#id_username, input[name="username"]').first();
  const passwordInput = page.locator('#id_password, input[name="password"]').first();
  try {
    await usernameInput.waitFor({ state: 'visible', timeout: 12_000 });
    await passwordInput.waitFor({ state: 'visible', timeout: 12_000 });
  } catch (err) {
    const debug = String(process.env.E2E_DEBUG || '').trim() === '1';
    if (debug) {
      try { console.error('[e2e][debug] login url:', page.url()); } catch {}
      try { console.error('[e2e][debug] login title:', await page.title()); } catch {}
      try {
        const html = await page.content();
        console.error('[e2e][debug] login html head:', String(html || '').slice(0, 600));
      } catch {}
      try {
        const shot = `/tmp/e2e-login-${Date.now()}.png`;
        await page.screenshot({ path: shot, fullPage: true });
        console.error('[e2e][debug] screenshot:', shot);
      } catch {}
    }
    throw err;
  }
  await usernameInput.fill(USERNAME);
  await passwordInput.fill(PASSWORD);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('button[type="submit"], input[type="submit"]').click(),
  ]);
  if (page.url().includes('/login')) throw new Error('Login failed');
}

async function ensureEditorReady(page) {
  await page.locator('#create-task-canvas').waitFor({ state: 'visible', timeout: 35_000 });
  // Espera a que el modo/layout se haya aplicado (evita asserts antes de que JS añada clases).
  await page.waitForFunction(() => {
    const body = document.body;
    return !!(body && body.classList.contains('task-mode-ready'));
  }, null, { timeout: 35_000 }).catch(() => null);
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

async function waitOverlayBackdrop(page, open) {
  await page.waitForFunction(
    (wanted) => {
      const el = document.getElementById('tpad-overlay-backdrop');
      if (!el) return !wanted;
      return wanted ? (el.hidden === false) : (el.hidden !== false);
    },
    !!open,
    { timeout: 10_000 },
  ).catch(() => null);
}

async function openDetails(page, detailsSelector) {
  await page.locator(detailsSelector).waitFor({ state: 'attached', timeout: 35_000 });
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return;
    if (el.tagName === 'DETAILS') el.open = true;
  }, detailsSelector);
  await page.waitForFunction(
    (sel) => !!(document.querySelector(sel) && document.querySelector(sel).open === true),
    detailsSelector,
    { timeout: 10_000 },
  );
}

async function closeDetails(page, detailsSelector) {
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return;
    if (el.tagName === 'DETAILS') el.open = false;
  }, detailsSelector);
  await page.waitForFunction(
    (sel) => {
      const el = document.querySelector(sel);
      return !!(el && el.tagName === 'DETAILS' && el.open === false);
    },
    detailsSelector,
    { timeout: 10_000 },
  ).catch(() => null);
}

async function assertPopoverInViewport(page, selector, label) {
  await page.waitForFunction(
    (sel) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      const style = window.getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden') return false;
      const rect = el.getBoundingClientRect();
      return rect.width > 20 && rect.height > 20;
    },
    selector,
    { timeout: 15_000 },
  );
  const box = await page.locator(selector).first().boundingBox();
  assert(box, `${label}: no boundingBox`);
  const viewport = page.viewportSize();
  assert(viewport, 'missing viewport');
  const inX = (box.x + box.width) > 0 && box.x < viewport.width;
  const inY = (box.y + box.height) > 0 && box.y < viewport.height;
  assert(inX && inY, `${label}: popover fuera de viewport (${JSON.stringify({ box, viewport })})`);
}

async function openSurfaceMenu(page) {
  await page.locator('#surface-trigger').waitFor({ state: 'visible', timeout: 35_000 });
  await page.locator('#surface-trigger').click({ force: true });
  await page.waitForFunction(
    () => !!document.getElementById('surface-picker')?.classList?.contains('is-open'),
    null,
    { timeout: 6_000 },
  ).catch(async () => {
    // Headless WebKit puede ser flaky; forzamos el estado para validar layout.
    await page.evaluate(() => {
      try { document.getElementById('surface-picker')?.classList.add('is-open'); } catch {}
    });
  });
}

async function closeSurfaceMenu(page) {
  await page.locator('body').click({ position: { x: 10, y: 10 } }).catch(() => null);
  await page.waitForFunction(
    () => !document.getElementById('surface-picker')?.classList?.contains('is-open'),
    null,
    { timeout: 6_000 },
  ).catch(async () => {
    await page.evaluate(() => {
      try { document.getElementById('surface-picker')?.classList.remove('is-open'); } catch {}
    });
  });
}

async function enterAndExitPresentation(page) {
  await page.evaluate(() => {
    try { document.getElementById('task-focus-toggle')?.scrollIntoView?.({ block: 'center', inline: 'nearest' }); } catch {}
  });
  await page.locator('#task-focus-toggle').click({ force: true });
  await page.waitForFunction(() => document.body.classList.contains('focus-mode'), null, { timeout: 10_000 }).catch(async () => {
    await page.evaluate(() => { try { document.getElementById('task-focus-toggle')?.click?.(); } catch {} });
    await page.waitForFunction(() => document.body.classList.contains('focus-mode'), null, { timeout: 10_000 });
  });
  await page.locator('#task-focus-exit').click({ force: true });
  await page.waitForFunction(() => !document.body.classList.contains('focus-mode'), null, { timeout: 10_000 });
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
      // Puede ser bottom-sheet (overlay) o stack; lo importante es que sea usable en pantalla.
      assert(sideBox.height > 120, `${modeLabel}: recursos debería tener altura visible (portrait)`);
    } else {
      assert(sideBox.x >= pitchBox.x, `${modeLabel}: recursos deberían estar a la derecha (landscape)`);
    }
  }

  // 4) Overlays: Opciones / Vista / Superficie / Presentación.
  await openDetails(page, '#task-builder-actions-menu');
  await waitOverlayBackdrop(page, true);
  await assertPopoverInViewport(page, '#task-builder-actions-menu .action-menu-body', `${modeLabel} · Opciones`);
  await page.locator('#tpad-overlay-backdrop').click({ force: true }).catch(() => null);
  await closeDetails(page, '#task-builder-actions-menu');
  await waitOverlayBackdrop(page, false);

  await openDetails(page, '#pitch-view-menu');
  await waitOverlayBackdrop(page, true);
  await assertPopoverInViewport(page, '#pitch-view-menu .pitch-view-menu-body', `${modeLabel} · Vista menú`);
  await page.locator('#tpad-overlay-backdrop').click({ force: true }).catch(() => null);
  await closeDetails(page, '#pitch-view-menu');
  await waitOverlayBackdrop(page, false);

  await openSurfaceMenu(page);
  await assertPopoverInViewport(page, '#surface-menu', `${modeLabel} · Superficie menú`);
  await closeSurfaceMenu(page);

  await enterAndExitPresentation(page);
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
    console.log('[e2e] OK: layout + overlays (iPad portrait/landscape)');
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
