/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

function timestampId() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

async function loginIfNeeded(page, baseUrl) {
  const username = process.env.E2E_USERNAME || '';
  const password = process.env.E2E_PASSWORD || '';
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  if (!/\/login\/?/.test(page.url())) return true;
  if (!username || !password) return false;
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  return !/\/login\/?/.test(page.url());
}

async function sampleCanvas(page) {
  return page.evaluate(() => {
    const canvas = document.querySelector('#task-pitch-3d-canvas');
    if (!canvas) return { ok: false, reason: 'missing_canvas' };
    const w = canvas.width || 0;
    const h = canvas.height || 0;
    if (w < 64 || h < 64) return { ok: false, reason: 'small_canvas', width: w, height: h };
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return { ok: false, reason: 'missing_2d_context', width: w, height: h };
    const points = [
      [0.25, 0.25],
      [0.50, 0.50],
      [0.75, 0.50],
      [0.50, 0.75],
      [0.15, 0.65],
      [0.85, 0.35],
    ];
    const colors = points.map(([px, py]) => {
      const data = ctx.getImageData(Math.floor(w * px), Math.floor(h * py), 1, 1).data;
      return Array.from(data);
    });
    const unique = new Set(colors.map((c) => c.join(','))).size;
    const nonBlack = colors.filter((c) => (c[0] + c[1] + c[2]) > 24 && c[3] > 0).length;
    return {
      ok: unique >= 3 && nonBlack >= 4,
      width: w,
      height: h,
      unique,
      nonBlack,
      perf: window.__WEBSTATS_PITCH3D_PERF || null,
      theme: document.querySelector('#task-pitch-3d-theme')?.value || '',
    };
  });
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'https://app.segundajugada.es').replace(/\/+$/, '');
  const teamId = process.env.E2E_TEAM_ID || '1';
  const outDir = process.env.E2E_OUT_DIR || path.join(process.cwd(), 'artifacts', 'pitch3d-visual', timestampId());
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: String(process.env.E2E_HEADLESS || 'true') !== 'false' });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 920 },
    deviceScaleFactor: 1.5,
    ignoreHTTPSErrors: true,
    storageState: process.env.E2E_STORAGE_STATE && fs.existsSync(process.env.E2E_STORAGE_STATE)
      ? process.env.E2E_STORAGE_STATE
      : undefined,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45_000);
  page.setDefaultNavigationTimeout(60_000);

  const log = {
    base_url: baseUrl,
    team_id: teamId,
    started_at: new Date().toISOString(),
    checks: [],
    console: [],
    page_errors: [],
  };
  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) log.console.push({ type: msg.type(), text: msg.text() });
  });
  page.on('pageerror', (err) => log.page_errors.push(String(err && err.stack ? err.stack : err)));

  try {
    const logged = await loginIfNeeded(page, baseUrl);
    if (!logged) throw new Error('login_required_set_E2E_USERNAME_E2E_PASSWORD_or_E2E_STORAGE_STATE');

    await page.goto(`${baseUrl}/coach/tactica/?team=${encodeURIComponent(teamId)}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => null);
    await page.screenshot({ path: path.join(outDir, '01-tactica.png'), fullPage: true });

    const openButton = page.locator('#pitch-3d-open-tactics, #pitch-3d-open-standard, #pitch-3d-open, button:has-text("Representación 3D")').first();
    await openButton.waitFor({ state: 'visible' });
    await openButton.click();
    await page.waitForSelector('#task-pitch-3d-canvas', { state: 'visible' });
    await page.waitForSelector('#task-pitch-3d-modal:not([hidden])', { state: 'attached' });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(outDir, '02-pitch3d-day-or-auto.png'), fullPage: true });
    log.checks.push({ name: 'auto_canvas', result: await sampleCanvas(page) });

    await page.selectOption('#task-pitch-3d-theme', 'night').catch(() => null);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(outDir, '03-pitch3d-night.png'), fullPage: true });
    log.checks.push({ name: 'night_canvas', result: await sampleCanvas(page) });

    const failed = log.checks.filter((c) => !c.result || !c.result.ok);
    log.ok = failed.length === 0 && log.page_errors.length === 0;
    fs.writeFileSync(path.join(outDir, 'pitch3d-visual-report.json'), JSON.stringify(log, null, 2));
    if (!log.ok) throw new Error(`pitch3d_visual_qa_failed:${failed.map((f) => f.name).join(',')}`);
    console.log(`[pitch3d-visual] ok ${outDir}`);
  } finally {
    await browser.close().catch(() => null);
  }
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
