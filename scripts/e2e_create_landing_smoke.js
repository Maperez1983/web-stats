/* eslint-disable no-console */
// Smoke test: Entrenos → Sesiones → pestaña "Crear" debe mostrar hero tipo pizarra,
// lateral de módulos (Tarea/Sesión/Microciclo/Táctica) y acciones como botones (no tarjetas grandes).
//
// Usage:
//   E2E_BASE_URL=http://127.0.0.1:8001 E2E_USERNAME=e2e_coach E2E_PASSWORD=e2e node scripts/e2e_create_landing_smoke.js
const { chromium } = require('playwright');

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'e2e_coach';
  const password = process.env.E2E_PASSWORD || 'e2e';
  const headless = String(process.env.E2E_HEADLESS || 'true').toLowerCase() !== 'false';

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 820 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(35_000);
  page.setDefaultNavigationTimeout(60_000);

  try {
    await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.click('button[type="submit"]'),
    ]);
    if (page.url().includes('/login')) throw new Error('Login failed');

    await page.goto(`${baseUrl}/coach/sesiones/?team=1&tab=create`, { waitUntil: 'domcontentloaded' });

    await page.waitForSelector('#coach-create-landing', { timeout: 35_000 });
    await page.waitForSelector('.create-hero-pitch', { timeout: 35_000 });
    await page.waitForSelector('.create-mod-btn', { timeout: 35_000 });

    // Landing no debe mostrar acciones del módulo: solo hero + módulos (links).
    const actionPanels = await page.locator('.create-actions-panel').count();
    if (actionPanels !== 0) throw new Error(`Expected 0 action panels on landing, got ${actionPanels}`);

    // Módulos deben navegar a otra "página" (create_page=...).
    const sessionLink = page.locator('a.create-mod-btn').filter({ hasText: 'Sesión' }).first();
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      sessionLink.click(),
    ]);
    if (!page.url().includes('create_page=session')) throw new Error(`Unexpected URL after clicking Sesión: ${page.url()}`);
    await page.waitForSelector('.create-actions-panel', { timeout: 10_000 });

    console.log('[e2e] OK');
  } catch (err) {
    console.error('[e2e] FAIL:', err && err.stack ? err.stack : err);
    process.exitCode = 1;
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
  }
}

main();
