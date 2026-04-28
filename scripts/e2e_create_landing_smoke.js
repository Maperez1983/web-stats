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

    // Acciones como "pills" (no tarjetas folder-card dentro del bloque de acciones).
    const actionButtons = await page.locator('#create-mod-task .create-action-btn').count();
    if (actionButtons < 3) throw new Error(`Expected >=3 action buttons, got ${actionButtons}`);
    const folderCardsInTask = await page.locator('#create-mod-task .folder-card').count();
    if (folderCardsInTask !== 0) throw new Error('Unexpected .folder-card found inside task actions');

    // Toggle de módulos.
    const sessionBtn = page.locator('.create-mod-btn').filter({ hasText: 'Sesión' }).first();
    await sessionBtn.click();
    await page.waitForSelector('#create-mod-session:not([hidden])', { timeout: 10_000 });
    // Asegura que el panel anterior se ocultó (propiedad hidden=true).
    const taskHidden = await page.locator('#create-mod-task').evaluate((el) => Boolean(el && el.hidden));
    if (!taskHidden) throw new Error('Expected task view to be hidden after switching to Sesión');

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
