/* eslint-disable no-console */
// Smoke test: any PDF link should open the internal /pdf/viewer/ page (avoids "trap" in iOS webviews).
//
// Usage:
//   E2E_BASE_URL=http://127.0.0.1:8001 E2E_USERNAME=e2e_coach E2E_PASSWORD=e2e node scripts/e2e_pdf_viewer_smoke.js
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
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.click('button[type="submit"]'),
    ]);
    if (page.url().includes('/login')) throw new Error('Login failed');

    // Go to roster and open first player
    await page.goto(`${baseUrl}/coach/plantilla/`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('a.player-card', { timeout: 35_000 });
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.click('a.player-card'),
    ]);

    // Click any player PDF link and ensure we land in the viewer.
    const pdfLink = page.locator('a[href*="/pdf/"]').first();
    await pdfLink.waitFor({ state: 'visible', timeout: 35_000 });
    await Promise.all([
      page.waitForURL(/\/pdf\/viewer\/\?/),
      pdfLink.click(),
    ]);

    await page.waitForSelector('iframe', { timeout: 35_000 });
    await page.waitForSelector('a.btn.ghost', { timeout: 35_000 }); // Volver
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

