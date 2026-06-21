/* eslint-disable no-console */
const { chromium } = require('playwright');

async function login(page, baseUrl, username, password) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const teamId = process.env.E2E_TEAM_ID || '151';
  const username = process.env.E2E_USERNAME || 'e2e';
  const password = process.env.E2E_PASSWORD || 'e2e1234';
  const outBefore = process.env.E2E_OUT_BEFORE || '/Volumes/Mac Satecchi/Mac/Downloads/estadio_editor_local_before_modal.png';
  const outModal = process.env.E2E_OUT_MODAL || '/Volumes/Mac Satecchi/Mac/Downloads/estadio_editor_local_modal.png';

  const browser = await chromium.launch({ headless: String(process.env.E2E_HEADLESS || 'false') !== 'false' ? true : false });
  const page = await browser.newPage({ viewport: { width: 1440, height: 920 }, deviceScaleFactor: 1.25 });
  page.setDefaultTimeout(45_000);
  page.setDefaultNavigationTimeout(60_000);

  try {
    await login(page, baseUrl, username, password);
    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/?team=${encodeURIComponent(teamId)}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => null);
    await page.screenshot({ path: outBefore, fullPage: true });

    const button = page.locator('#pitch-3d-open-standard, #pitch-3d-open, button:has-text("Representación 3D")').first();
    await button.waitFor({ state: 'visible' });
    await button.click();
    await page.waitForSelector('#task-pitch-3d-canvas', { state: 'visible' });
    await page.waitForTimeout(3_500);
    await page.screenshot({ path: outModal, fullPage: true });
    console.log(`[pitch3d-capture] ok ${outModal}`);
  } finally {
    await browser.close().catch(() => null);
  }
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
