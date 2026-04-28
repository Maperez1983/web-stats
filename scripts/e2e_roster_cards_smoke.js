/* eslint-disable no-console */
// Smoke test: Plantilla (coach_roster) debe renderizar cards estilo "broadcast"
// con KPIs principales (Influencia/Importancia/%Part/%Disp) sin romper la página.
//
// Usage:
//   E2E_BASE_URL=http://127.0.0.1:8001 E2E_USERNAME=e2e_coach E2E_PASSWORD=e2e node scripts/e2e_roster_cards_smoke.js
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

    await page.goto(`${baseUrl}/coach/plantilla/?tab=stats&scope=league`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.card-grid', { timeout: 35_000 });

    const cardsCount = await page.locator('.player-card').count();
    if (cardsCount < 1) throw new Error('Expected at least 1 player card');

    // Al menos una card debe tener el bloque KPI.
    const kpiBlocks = await page.locator('.player-card .broadcast-kpis').count();
    if (kpiBlocks < 1) throw new Error('Expected at least 1 .broadcast-kpis block');

    // Debe contener labels clave.
    await page.locator('.broadcast-kpi .k', { hasText: 'Influencia' }).first().waitFor({ state: 'visible', timeout: 10_000 });
    await page.locator('.broadcast-kpi .k', { hasText: 'Importancia' }).first().waitFor({ state: 'visible', timeout: 10_000 });

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

