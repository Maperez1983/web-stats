/* eslint-disable no-console */
// Smoke test: Biblioteca de tareas debe permitir filtrar por origen (Importadas / Creadas / Dibujadas)
// sin errores 500 ni redirecciones inesperadas.
//
// Usage:
//   E2E_BASE_URL=http://127.0.0.1:8001 E2E_USERNAME=e2e_coach E2E_PASSWORD=e2e node scripts/e2e_library_source_smoke.js
const { chromium } = require('playwright');

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'e2e_coach';
  const password = process.env.E2E_PASSWORD || 'e2e';
  const headless = String(process.env.E2E_HEADLESS || 'true').toLowerCase() !== 'false';

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(35_000);
  page.setDefaultNavigationTimeout(60_000);

  try {
    await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name=\"username\"]', username);
    await page.fill('input[name=\"password\"]', password);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.click('button[type=\"submit\"]'),
    ]);
    if (page.url().includes('/login')) throw new Error('Login failed');

    await page.goto(
      `${baseUrl}/coach/sesiones/?team=1&tab=library&library_repo=traditional&library_view=source&library_key=imported`,
      { waitUntil: 'domcontentloaded' },
    );

    await page.waitForSelector('text=Biblioteca de tareas', { timeout: 35_000 });
    await page
      .locator('a.tab-link.is-active')
      .filter({ hasText: 'Importadas' })
      .first()
      .waitFor({ state: 'visible', timeout: 35_000 });

    const creadasLink = page.locator('a.tab-link').filter({ hasText: 'Creadas' }).first();
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      creadasLink.click(),
    ]);
    if (!page.url().includes('library_view=source') || !page.url().includes('library_key=created')) {
      throw new Error(`Unexpected URL after switching to Creadas: ${page.url()}`);
    }

    const dibujadasLink = page.locator('a.tab-link').filter({ hasText: 'Dibujadas' }).first();
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      dibujadasLink.click(),
    ]);
    if (!page.url().includes('library_key=drawn')) {
      throw new Error(`Unexpected URL after switching to Dibujadas: ${page.url()}`);
    }

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

