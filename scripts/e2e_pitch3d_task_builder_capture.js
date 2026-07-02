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

async function openPitch3dModal(page) {
  const candidates = [
    '#pitch-3d-open-tactics',
    '#pitch-3d-open-standard',
    '#pitch-3d-open',
    '[data-pitch3d-trigger="1"]',
  ];
  const exact3dButton = page.getByRole('button', { name: /^3D$/ }).first();
  const exact3dTab = page.locator('button, a').filter({ hasText: /^3D$/ }).first();
  const presentationButton = page.getByRole('button', { name: /Representación 3D/i }).first();

  const tryClick = async (locator) => {
    try {
      const count = await locator.count();
      if (!count) return false;
      const target = locator.first();
      await target.waitFor({ state: 'visible', timeout: 2500 });
      await target.click({ timeout: 2500 });
      return true;
    } catch (e) {
      return false;
    }
  };

  const waitModal = async () => {
    try {
      await page.waitForSelector('#task-pitch-3d-modal:not([hidden])', { state: 'attached', timeout: 2500 });
      await page.waitForSelector('#task-pitch-3d-canvas', { state: 'visible', timeout: 2500 });
      return true;
    } catch (e) {
      return false;
    }
  };

  if (await waitModal()) return;
  if (await tryClick(exact3dButton) && await waitModal()) return;
  if (await tryClick(exact3dTab) && await waitModal()) return;
  if (await tryClick(presentationButton) && await waitModal()) return;

  for (const selector of candidates) {
    const locator = page.locator(selector);
    if (await tryClick(locator) && await waitModal()) return;
  }

  const forced = await page.evaluate(() => {
    const selectors = [
      '#pitch-3d-open-tactics',
      '#pitch-3d-open-standard',
      '#pitch-3d-open',
      '[data-pitch3d-trigger="1"]',
    ];
    let clicked = false;
    selectors.forEach((selector) => {
      const el = document.querySelector(selector);
      if (el && typeof el.click === 'function') {
        el.click();
        clicked = true;
      }
    });
    const plain3d = Array.from(document.querySelectorAll('button, a'))
      .find((el) => (el.textContent || '').trim() === '3D');
    if (!clicked && plain3d && typeof plain3d.click === 'function') {
      plain3d.click();
      clicked = true;
    }
    return {
      clicked,
      hasModal: !!document.getElementById('task-pitch-3d-modal'),
      modalHidden: !!document.getElementById('task-pitch-3d-modal')?.hidden,
      hasCanvas: !!document.getElementById('task-pitch-3d-canvas'),
      hasTrigger: !!document.querySelector('[data-pitch3d-trigger="1"]'),
    };
  });

  if (await waitModal()) return;
  throw new Error(`pitch3d_modal_not_opened:${JSON.stringify(forced)}`);
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const teamId = process.env.E2E_TEAM_ID || '151';
  const username = process.env.E2E_USERNAME || 'e2e';
  const password = process.env.E2E_PASSWORD || 'e2e1234';
  const cameraValue = process.env.E2E_CAMERA || 'lower_bowl_interior';
  const themeValue = process.env.E2E_THEME || 'day';
  const downloadSnap = String(process.env.E2E_DOWNLOAD_SNAP || '').trim() === '1';
  const outBefore = process.env.E2E_OUT_BEFORE || '/Volumes/Mac Satecchi/Mac/Downloads/estadio_editor_local_before_modal.png';
  const outModal = process.env.E2E_OUT_MODAL || '/Volumes/Mac Satecchi/Mac/Downloads/estadio_editor_local_modal.png';
  const outCanvas = process.env.E2E_OUT_CANVAS || '/Volumes/Mac Satecchi/Mac/Downloads/estadio_editor_local_canvas.png';
  const outSnap = process.env.E2E_OUT_SNAP || '/Volumes/Mac Satecchi/Mac/Downloads/estadio_editor_local_snap.png';
  const headlessValue = String(process.env.E2E_HEADLESS || 'false').trim().toLowerCase();
  const isHeadless = !['0', 'false', 'no', 'off'].includes(headlessValue);

  const browser = await chromium.launch({
    headless: isHeadless,
    args: [
      '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader',
      '--ignore-gpu-blocklist',
      '--enable-webgl',
      '--enable-accelerated-2d-canvas',
      '--disable-gpu-sandbox',
    ],
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 920 }, deviceScaleFactor: 1.25 });
  page.setDefaultTimeout(45_000);
  page.setDefaultNavigationTimeout(60_000);

  try {
    await login(page, baseUrl, username, password);
    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/?team=${encodeURIComponent(teamId)}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => null);
    await page.screenshot({ path: outBefore, fullPage: true });

    await openPitch3dModal(page);
    await page.selectOption('#task-pitch-3d-camera', cameraValue).catch(() => null);
    await page.waitForTimeout(1200);
    await page.selectOption('#task-pitch-3d-theme', themeValue).catch(() => null);
    await page.waitForFunction(() => {
      const canvas = document.getElementById('task-pitch-3d-canvas');
      if (!canvas) return false;
      const width = Number(canvas.getAttribute('width') || 0);
      const height = Number(canvas.getAttribute('height') || 0);
      return width > 0 && height > 0;
    }, { timeout: 15000 }).catch(() => null);
    await page.waitForTimeout(6_500);
    const modal = page.locator('#task-pitch-3d-modal .sim-3d-card').first();
    await modal.screenshot({ path: outModal });
    const canvas = page.locator('#task-pitch-3d-canvas').first();
    await canvas.screenshot({ path: outCanvas });
    if (downloadSnap) {
      const downloadPromise = page.waitForEvent('download', { timeout: 20000 }).catch(() => null);
      await page.click('#task-pitch-3d-snap').catch(() => null);
      const download = await downloadPromise;
      if (download) {
        await download.saveAs(outSnap).catch(() => null);
      }
    }
    console.log(`[pitch3d-capture] ok ${outModal} ${outCanvas} ${downloadSnap ? outSnap : ''}`.trim());
  } finally {
    await browser.close().catch(() => null);
  }
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
